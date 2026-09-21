"""Resumable, isolated phase runners for high-value content automations."""

from __future__ import annotations

import json
import os
import random
import re
import uuid

import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
PHT = timezone(timedelta(hours=8))  # Philippine Standard Time (UTC+8)


def pht_timestamp() -> str:
    """Return formatted Philippine Standard Time (e.g. 2026-08-14 09:18:04 AM PHT)."""
    return datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")

import requests
from PIL import Image, UnidentifiedImageError

from .airtable_client import current_pht_timestamp
from .akeneo_client import AkeneoClient, split_item_name
from .assets import AssetCatalog
from .errors import AssetValidationError, AutomationError, ProviderError
from .fal_client import FalClient
from .isolated_config import IsolatedAutomationSettings
from .item_tagger import (
    TARGET_BLENDED_FIELD,
    tag_and_upload_blended_image,
    tag_blended_image,
)
from .krea_client import KreaClient
from .overlay import HOMECARTEL_STORY_LOGO_BOX, stamp_logo
from .prompts import build_vision_blending_instruction
from .scraping.airtable import ScrapeAirtableClient
from .scraping.categories import akeneo_category_code
from .scraping.furniture_item import (
    fetch_all_base_existing_identities,
    format_item_name_with_product_type,
)
from .scraping.products import (
    ProductItem,
    existing_product_identities,
    select_new_products,
)
from .shopify_client import ShopifyCatalogIndex, ShopifyClient


KREA_ASPECT_RATIO = "9:16"
KREA_MODEL_LABEL = "krea-2-medium"
FAL_GROK_VIDEO_MODEL = "xai/grok-imagine-video/v1.5/image-to-video"
FAL_ELEVENLABS_MUSIC_MODEL = "fal-ai/elevenlabs/music"
FAL_VISION_MODEL = "anthropic/claude-sonnet-5"
FAL_NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"

# Toggle to enable/disable AI background jazz music generation (Phase 7).
# Set to False to turn OFF, True to turn ON. Can also be overridden with DAY_NIGHT_GENERATE_MUSIC=true|false in .env.
ENABLE_DAY_NIGHT_MUSIC: bool = os.getenv("DAY_NIGHT_GENERATE_MUSIC", "false").strip().lower() in ("true", "1", "yes")

DAY_NIGHT_MUSIC_DURATION = 18.0
DAY_NIGHT_VIDEO_DURATION = 15.0
DAY_NIGHT_VIDEO_RESOLUTION = "720p"
DAY_NIGHT_OUTRO_DURATION = 3.0
DAY_NIGHT_TIMELAPSE_PROMPT = (
    'Generate a timelapse of this "day" photo. Start from 7am and timelapse '
    "to 9pm. Consider appropriate lighting, shadows, and natural light coming "
    "from the lighting fixture and outside the interior. Do not change the "
    "angle of the camera and do not change the lighting fixture."
)

TERMINAL_AND_PROTECTED_STATUSES = {
    "complete", "completed", "done", "finished",
    "posted", "scheduled", "schedule",
    "discard", "discarded",
    "for manual", "minor revision", "minor revisions", "fm",
    "skip", "skipped", "ignore", "disabled", "error",
}

    
@dataclass(frozen=True)
class PipelineDefinition:
    key: str
    table_id: str
    category_code: str
    moodboard_id: str
    interior_field: str
    blended_field: str
    final_field: str
    phase_count: int
    interior_prompt: str
    video_field: str = ""
    music_field: str = ""
    outro_field: str = ""
    layout_field: str = ""
    layout_asset: str = ""
    final_prompt_asset: str = ""
    interior_prompts: tuple[str, ...] = ()
    outro_asset: str = ""


def get_day_night_table(category_code: str, default_table_id: str) -> str:
    """Resolve Airtable Table ID dynamically from environment variables with fallback."""
    env_keys = {
        "chandeliers": [
            "AIRTABLE_TABLE_ID_CHANDELIER_DAY_AND_NIGHT_REEL",
            "AIRTABLE_TABLE_ID_CHANDELIERS_DAY_AND_NIGHT_REEL",
            "AIRTABLE_TABLE_ID_BEFORE_AFTER_CHANDELIER",
            "AIRTABLE_TABLE_ID_CHANDELIER_DAY_NIGHT_STORY",
        ],
        "pendant_lights": [
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_AND_NIGHT_REEL",
            "AIRTABLE_TABLE_ID_PENDANT_DAY_AND_NIGHT_REEL",
            "AIRTABLE_TABLE_ID_BEFORE_AFTER_PENDANT_LIGHTS",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_NIGHT_STORY",
        ],
        "floor_lamps": [
            "AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL",
            "AIRTABLE_TABLE_ID_FLOOR_LAMPS_DAY_AND_NIGHT_REEL",
            "AIRTABLE_TABLE_ID_MYTH_AND_FACT_FLOOR_LAMPS",
            "AIRTABLE_TABLE_ID_FLOOR_LAMPS_DAY_NIGHT_STORY",
        ],
    }
    for key in env_keys.get(category_code, []):
        val = os.getenv(key, "").strip()
        if val:
            return val
    return default_table_id


DAY_NIGHT_REEL_CHANDELIER = PipelineDefinition(
    key="day_night_reel_chandeliers",
    table_id=get_day_night_table("chandeliers", "tbl35JySlNuWh61tL"),
    category_code="chandeliers",
    moodboard_id="de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    interior_field="Interior",
    blended_field="Day and Night Blended",
    video_field="REEL - Day & Night",
    music_field="Music Generated",
    outro_field="Outro",
    outro_asset="assets/outro_layout.jpg",
    final_field="Day and Night Reel with Music and Outro",
    phase_count=8,
    interior_prompt="Generate me a modern living room",
)

DAY_NIGHT_REEL_PENDANT = PipelineDefinition(
    key="day_night_reel_pendant_lights",
    table_id=get_day_night_table("pendant_lights", "tblkTuM627s2f0FTN"),
    category_code="pendant_lights",
    moodboard_id="de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    interior_field="Interior",
    blended_field="Day and Night Blended",
    video_field="REEL - Day & Night",
    music_field="Music Generated",
    outro_field="Outro",
    outro_asset="assets/outro_layout.jpg",
    final_field="Day and Night Reel with Music and Outro",
    phase_count=8,
    interior_prompt="Generate me a modern dining room hanging chandelier",
)

DAY_NIGHT_REEL_FLOOR_LAMP = PipelineDefinition(
    key="day_night_reel_floor_lamps",
    table_id=get_day_night_table("floor_lamps", "tblVPgI4C6HEFcKW9"),
    category_code="floor_lamps",
    moodboard_id="b1641228-beec-4823-8d01-1de3eec8410d",
    interior_field="Interior",
    blended_field="Day and Night Blended",
    video_field="REEL - Day & Night",
    music_field="Music Generated",
    outro_field="Outro",
    outro_asset="assets/outro_layout.jpg",
    final_field="Day and Night Reel with Music and Outro",
    phase_count=8,
    interior_prompt="Generate me a bedroom that have beside a floor lamp",
)

# Default Day & Night Reel pipeline definition
DAY_NIGHT_REEL = DAY_NIGHT_REEL_PENDANT

DAY_NIGHT_REEL_PIPELINES: dict[str, PipelineDefinition] = {
    "pendant_lights": DAY_NIGHT_REEL_PENDANT,
    "chandeliers": DAY_NIGHT_REEL_CHANDELIER,
    "floor_lamps": DAY_NIGHT_REEL_FLOOR_LAMP,
    "pendant": DAY_NIGHT_REEL_PENDANT,
    "chandelier": DAY_NIGHT_REEL_CHANDELIER,
    "floor": DAY_NIGHT_REEL_FLOOR_LAMP,
    "floor_lamp": DAY_NIGHT_REEL_FLOOR_LAMP,
}

# Dynamically register each active pipeline by its table ID:
for _pipe in (DAY_NIGHT_REEL_PENDANT, DAY_NIGHT_REEL_CHANDELIER, DAY_NIGHT_REEL_FLOOR_LAMP):
    if _pipe.table_id:
        DAY_NIGHT_REEL_PIPELINES[_pipe.table_id] = _pipe
        DAY_NIGHT_REEL_PIPELINES[_pipe.table_id.lower()] = _pipe



PENDANT_TIPS_EDU_PROMPTS = (
    "Generate a premium modern dining room interior in a vertical 9:16 composition featuring a sleek dining table centered beneath the ceiling. Clean, bright, photorealistic, elegant modern styling, with a clear ceiling focal point for a pendant light. No text or unrelated lighting fixtures.",
    "Generate a premium modern kitchen interior in a vertical 9:16 composition featuring a marble kitchen island counter. Bright, photorealistic, elegant modern styling, with a clear ceiling focal point over the island for a pendant light. No text or unrelated lighting fixtures.",
    "Generate a premium modern breakfast nook dining area in a vertical 9:16 composition beside sunlit windows. Bright, photorealistic, elegant modern styling with a clear ceiling focal point for a pendant light. No text or unrelated lighting fixtures.",
    "Generate a premium modern bedroom interior in a vertical 9:16 composition beside a stylish bed and nightstand. Bright, photorealistic, elegant modern styling with a clear ceiling focal drop point for a bedside pendant light. No text or unrelated lighting fixtures.",
    "Generate a premium modern living room corner in a vertical 9:16 composition featuring minimalist modern furniture. Bright, photorealistic, elegant modern styling with an uncluttered ceiling focal point for a pendant light. No text or unrelated lighting fixtures.",
    "Generate a premium modern entryway foyer in a vertical 9:16 composition with a stylish console and tall doorway. Bright, photorealistic, elegant modern styling with a clear central ceiling focal point for a pendant light. No text or unrelated lighting fixtures.",
)

TIPS_EDU_STORY_PENDANT = PipelineDefinition(
    key="tips_edu_story_pendant_lights",
    table_id="tblwnFN5a8fLzKuP4",
    category_code="pendant_lights",
    moodboard_id="de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    interior_field="Interior Photo Generated",
    blended_field="Blended Image",
    final_field="Tips and Edu Story Converted",
    phase_count=5,
    interior_prompt="Generate me a modern dining room",
    interior_prompts=("Generate me a modern dining room",) + PENDANT_TIPS_EDU_PROMPTS,
    layout_field="Tips and Edu Story Layout",
    layout_asset="Tips and Edu Story/stories (33).jpg",
    final_prompt_asset="Tips and Edu Story/tips-and-edu.json",
)

FLOOR_LAMP_TIPS_EDU_PROMPTS = (
    "Generate a premium modern interior in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp beside an armchair. The floor lamp must be fully in frame and clearly visible from top to base. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern living room interior in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp positioned at the end of a sofa. The floor lamp must be fully in frame and clearly visible from top to base. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern reading corner interior with a bookshelf in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp. The floor lamp must be fully in frame and clearly visible next to the seating and bookshelf. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern interior beside a lounge chair near curtains and window in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp. The floor lamp must be fully in frame and clearly visible. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern bedroom corner interior in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp standing in the corner. The floor lamp must be fully in frame and clearly visible from top to base. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern living room console area in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp standing next to the console table. The floor lamp must be fully in frame and clearly visible from top to base. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
)

TIPS_EDU_STORY_FLOOR_LAMP = PipelineDefinition(
    key="tips_edu_story_floor_lamps",
    table_id="tblJxWwZexgBHl26B",
    category_code="floor_lamps",
    moodboard_id="b1641228-beec-4823-8d01-1de3eec8410d",
    interior_field="Interior Photo Generated",
    blended_field="Blended Image",
    final_field="Tips and Edu Story Converted",
    phase_count=5,
    interior_prompt=FLOOR_LAMP_TIPS_EDU_PROMPTS[0],
    interior_prompts=FLOOR_LAMP_TIPS_EDU_PROMPTS,
    layout_field="Tips and Edu Story Layout",
    layout_asset="Tips and Edu Story/stories (33).jpg",
    final_prompt_asset="Tips and Edu Story/tips-and-edu.json",
)

CHANDELIER_TIPS_EDU_PROMPTS = (
    "Generate me a modern living room",
)

TIPS_EDU_STORY_CHANDELIER = PipelineDefinition(
    key="tips_edu_story_chandeliers",
    table_id="tblpFiaNn1Ym9fTTk",
    category_code="chandeliers",
    moodboard_id="b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    interior_field="Interior Photo Generated",
    blended_field="Blended Image",
    final_field="Tips and Edu Story Converted",
    phase_count=5,
    interior_prompt=CHANDELIER_TIPS_EDU_PROMPTS[0],
    interior_prompts=CHANDELIER_TIPS_EDU_PROMPTS,
    layout_field="Tips and Edu Story Layout",
    layout_asset="Tips and Edu Story/stories (33).jpg",
    final_prompt_asset="Tips and Edu Story/tips-and-edu.json",
)

CEILING_MOUNTED_TIPS_EDU_PROMPTS = (
    "Generate a premium modern hallway interior in a vertical 9:16 composition with clean walls and a plain, flat ceiling with a central focal point for a flush-mount ceiling light. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern bedroom interior in a vertical 9:16 composition with clean minimalist furniture and a plain flat ceiling with a central ceiling-mount light fixture focal point. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern kitchen interior in a vertical 9:16 composition with sleek cabinetry and a plain flat ceiling with a central flush ceiling light focal point. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern entryway interior in a vertical 9:16 composition with a stylish console and a clean, flat ceiling with a central ceiling light focal point. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern home office interior in a vertical 9:16 composition with a wooden desk and a plain, flat ceiling with a central ceiling light focal point. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern compact living room in a vertical 9:16 composition with modern sofa and a clean, flat ceiling with a central flush ceiling light focal point. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
)

TIPS_EDU_STORY_CEILING_MOUNTED = PipelineDefinition(
    key="tips_edu_story_ceiling_mounted",
    table_id="tblGlRibUZXB9R3Gt",
    category_code="ceiling_mounted",
    moodboard_id="b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    interior_field="Interior Photo Generated",
    blended_field="Blended Image",
    final_field="Tips and Edu Story Converted",
    phase_count=5,
    interior_prompt=CEILING_MOUNTED_TIPS_EDU_PROMPTS[0],
    interior_prompts=CEILING_MOUNTED_TIPS_EDU_PROMPTS,
    layout_field="Tips and Edu Story Layout",
    layout_asset="Tips and Edu Story/stories (33).jpg",
    final_prompt_asset="Tips and Edu Story/tips-and-edu.json",
)

TABLE_LAMP_TIPS_EDU_PROMPTS = (
    "Generate a premium modern bedroom interior in a vertical 9:16 composition with a prominent bedside nightstand table surface in full view for a table lamp. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern living room interior in a vertical 9:16 composition with a prominent side table beside a contemporary sofa in full view for a table lamp. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern entryway interior in a vertical 9:16 composition with a stylish console table surface in full view for a table lamp. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern home office interior in a vertical 9:16 composition with a clean wooden desk workspace surface in full view for a table lamp. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern reading nook in a vertical 9:16 composition with a cozy armchair and an accent table in full view for a table lamp. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern living room credenza in a vertical 9:16 composition with a clean wooden surface in full view for a table lamp. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
)

TIPS_EDU_STORY_TABLE_LAMP = PipelineDefinition(
    key="tips_edu_story_table_lamps",
    table_id="tblZtENqILDAekLv2",
    category_code="table_lamps",
    moodboard_id="257569e1-7be8-4412-a90f-acbc347e4646",
    interior_field="Interior Photo Generated",
    blended_field="Blended Image",
    final_field="Tips and Edu Story Converted",
    phase_count=5,
    interior_prompt=TABLE_LAMP_TIPS_EDU_PROMPTS[0],
    interior_prompts=TABLE_LAMP_TIPS_EDU_PROMPTS,
    layout_field="Tips and Edu Story Layout",
    layout_asset="Tips and Edu Story/stories (33).jpg",
    final_prompt_asset="Tips and Edu Story/tips-and-edu.json",
)

CLUSTER_CHANDELIER_TIPS_EDU_PROMPTS = (
    "Generate a premium modern high-ceiling living room interior in a vertical 9:16 composition with a spacious vertical ceiling volume for a hanging cluster chandelier. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern dining room interior in a vertical 9:16 composition with an expansive dining table centered under a tall ceiling for a dramatic hanging cluster chandelier. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern two-story staircase foyer in a vertical 9:16 composition with a high open vertical drop for a cascading cluster chandelier. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern double-height ceiling lounge in a vertical 9:16 composition with luxury seating and an ample vertical headroom for a cluster chandelier. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern great room in a vertical 9:16 composition with floor-to-ceiling windows and a grand central ceiling focal point for a cluster chandelier. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern open-concept kitchen and bar in a vertical 9:16 composition with high ceilings and a clear focal point above the island for a cluster chandelier. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
)

TIPS_EDU_STORY_CLUSTER_CHANDELIER = PipelineDefinition(
    key="tips_edu_story_cluster_chandeliers",
    table_id="tbllzkE2prSyj9BaD",
    category_code="cluster_chandeliers",
    moodboard_id="b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    interior_field="Interior Photo Generated",
    blended_field="Blended Image",
    final_field="Tips and Edu Story Converted",
    phase_count=5,
    interior_prompt=CLUSTER_CHANDELIER_TIPS_EDU_PROMPTS[0],
    interior_prompts=CLUSTER_CHANDELIER_TIPS_EDU_PROMPTS,
    layout_field="Tips and Edu Story Layout",
    layout_asset="Tips and Edu Story/stories (33).jpg",
    final_prompt_asset="Tips and Edu Story/tips-and-edu.json",
)

def load_tips_edu_story_config(workspace: Path | None = None) -> dict[str, Any]:
    """Load customized Tips & Edu Story configuration from JSON Prompts/Tips and Edu Story/settings.json."""
    ws = (workspace or WORKSPACE).resolve()
    config_path = ws / "JSON Prompts" / "Tips and Edu Story" / "settings.json"
    if config_path.is_file():
        try:
            with config_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def find_tips_edu_story_entry(
    config: dict[str, Any],
    category_or_table: str,
) -> dict[str, Any] | None:
    """Find category entry from settings.json matching category_code or table_id."""
    if not config or not category_or_table:
        return None
    target = str(category_or_table).strip().lower()
    if target in config:
        return config[target]
    for key, val in config.items():
        if not isinstance(val, dict):
            continue
        tid = str(val.get("table_id") or "").strip().lower()
        if tid and tid == target:
            return val
        k = key.lower()
        if target in k or k in target:
            return val
    return None


def _normalize_tips_edu_category(category_code: str) -> str:
    cat = category_code.lower().strip()
    if "pendant" in cat:
        return "pendant_lights"
    if "floor" in cat:
        return "floor_lamps"
    if "cluster" in cat:
        return "cluster_chandeliers"
    if "ceiling" in cat:
        return "ceiling_mounted"
    if "table" in cat:
        return "table_lamps"
    if "chand" in cat:
        return "chandeliers"
    return cat


def resolve_tips_edu_table_id(category_code: str, fallback: str = "") -> str:
    """Resolve Airtable destination table ID for Tips & Edu Story from .env or fallback."""
    cat = _normalize_tips_edu_category(category_code)
    candidate_keys: list[str] = []
    if cat == "pendant_lights":
        candidate_keys = [
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHT_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_PENDANT_TIPS_EDU_STORY",
        ]
    elif cat == "floor_lamps":
        candidate_keys = [
            "AIRTABLE_TABLE_ID_FLOOR_LAMPS_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_TIPS_EDU_STORY",
        ]
    elif cat == "chandeliers":
        candidate_keys = [
            "AIRTABLE_TABLE_ID_CHANDELIERS_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_CHANDELIER_TIPS_EDU_STORY",
        ]
    elif cat == "ceiling_mounted":
        candidate_keys = [
            "AIRTABLE_TABLE_ID_CEILING_MOUNTED_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_CEILING_LIGHTS_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_CEILING_LIGHT_TIPS_EDU_STORY",
        ]
    elif cat == "table_lamps":
        candidate_keys = [
            "AIRTABLE_TABLE_ID_TABLE_LAMPS_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_TABLE_LAMP_TIPS_EDU_STORY",
        ]
    elif cat == "cluster_chandeliers":
        candidate_keys = [
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIERS_TIPS_EDU_STORY",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_TIPS_EDU_STORY",
        ]

    for key in candidate_keys:
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return fallback


def resolve_krea_moodboard_id(
    category_code: str,
    fallback: str = "",
    workspace: Path | None = None,
) -> str:
    """Resolve category or table-specific Krea moodboard ID from .env, settings.json, or fallback."""
    cat = _normalize_tips_edu_category(category_code)
    candidate_keys: list[str] = []
    if cat == "pendant_lights":
        candidate_keys = [
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_PENDANT_LIGHT_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ]
    elif cat == "floor_lamps":
        candidate_keys = [
            "KREA_MOODBOARD_ID_FLOOR_LAMPS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_FLOOR_LAMP_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ]
    elif cat == "table_lamps":
        candidate_keys = [
            "KREA_MOODBOARD_ID_TABLE_LAMPS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_TABLE_LAMP_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ]
    elif cat == "cluster_chandeliers":
        candidate_keys = [
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIERS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ]
    elif cat == "ceiling_mounted":
        candidate_keys = [
            "KREA_MOODBOARD_ID_CEILING_MOUNTED_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CEILING_LIGHTS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CEILING_LIGHT_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_WALL_SCONCE",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ]
    elif cat == "chandeliers":
        candidate_keys = [
            "KREA_MOODBOARD_ID_CHANDELIERS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CHANDELIER_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ]

    for key in candidate_keys:
        val = (os.getenv(key) or "").strip()
        if val:
            return val

    # Fallback to settings.json
    config = load_tips_edu_story_config(workspace)
    entry = find_tips_edu_story_entry(config, category_code)
    if entry and isinstance(entry, dict):
        val = str(entry.get("moodboard_id") or "").strip()
        if val:
            return val

    return fallback


def load_tips_edu_json_prompts(
    workspace: Path,
    category_code: str,
    fallback_prompts: tuple[str, ...] | list[str],
) -> list[str]:
    """Load customized interior prompts from .env, settings.json, interior_prompts.json, or fallback."""
    cat = _normalize_tips_edu_category(category_code)
    env_keys: list[str] = []
    if cat == "pendant_lights":
        env_keys = [
            "TIPS_EDU_PROMPTS_PENDANT_LIGHTS",
            "TIPS_EDU_PROMPT_PENDANT_LIGHTS",
            "TIPS_EDU_PROMPT_PENDANT_LIGHT",
            "TIPS_EDU_PROMPT_PENDANT",
        ]
    elif cat == "floor_lamps":
        env_keys = [
            "TIPS_EDU_PROMPTS_FLOOR_LAMPS",
            "TIPS_EDU_PROMPT_FLOOR_LAMPS",
            "TIPS_EDU_PROMPT_FLOOR_LAMP",
        ]
    elif cat == "chandeliers":
        env_keys = [
            "TIPS_EDU_PROMPTS_CHANDELIERS",
            "TIPS_EDU_PROMPT_CHANDELIERS",
            "TIPS_EDU_PROMPT_CHANDELIER",
        ]
    elif cat == "ceiling_mounted":
        env_keys = [
            "TIPS_EDU_PROMPTS_CEILING_MOUNTED",
            "TIPS_EDU_PROMPT_CEILING_MOUNTED",
            "TIPS_EDU_PROMPT_CEILING_LIGHT",
        ]
    elif cat == "table_lamps":
        env_keys = [
            "TIPS_EDU_PROMPTS_TABLE_LAMPS",
            "TIPS_EDU_PROMPT_TABLE_LAMPS",
            "TIPS_EDU_PROMPT_TABLE_LAMP",
        ]
    elif cat == "cluster_chandeliers":
        env_keys = [
            "TIPS_EDU_PROMPTS_CLUSTER_CHANDELIERS",
            "TIPS_EDU_PROMPT_CLUSTER_CHANDELIERS",
            "TIPS_EDU_PROMPT_CLUSTER_CHANDELIER",
        ]

    for key in env_keys:
        raw_val = (os.getenv(key) or "").strip()
        if raw_val:
            if raw_val.startswith("[") and raw_val.endswith("]"):
                try:
                    parsed = json.loads(raw_val)
                    if isinstance(parsed, list) and parsed:
                        cleaned = [str(p).strip() for p in parsed if str(p).strip()]
                        if cleaned:
                            return cleaned
                except Exception:
                    pass
            if "|" in raw_val:
                prompts = [p.strip() for p in raw_val.split("|") if p.strip()]
                if prompts:
                    return prompts
            return [raw_val]

    # Check indexed variables: TIPS_EDU_PROMPT_{CAT}_1, _2, etc.
    base_prefix = env_keys[1] if len(env_keys) > 1 else (env_keys[0] if env_keys else "")
    if base_prefix:
        indexed: list[str] = []
        idx = 1
        while True:
            val = (os.getenv(f"{base_prefix}_{idx}") or "").strip()
            if not val:
                break
            indexed.append(val)
            idx += 1
        if indexed:
            return indexed

    # Fallback to settings.json
    config = load_tips_edu_story_config(workspace)
    entry = find_tips_edu_story_entry(config, category_code)
    if entry and isinstance(entry, dict):
        prompts = entry.get("prompts")
        if isinstance(prompts, list) and prompts:
            return prompts

    # Fallback to interior_prompts.json
    json_path = workspace / "JSON Prompts" / "Tips and Edu Story" / "interior_prompts.json"
    if json_path.is_file():
        try:
            with json_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    cat_key = category_code.lower()
                    for key, prompts in data.items():
                        if key.lower() in cat_key or cat_key in key.lower():
                            if isinstance(prompts, list) and prompts:
                                return prompts
        except Exception:
            pass
    return list(fallback_prompts)


def apply_tips_edu_story_settings(
    pipeline: PipelineDefinition,
    workspace: Path | None = None,
) -> PipelineDefinition:
    """Return a PipelineDefinition updated with overrides from .env or settings.json."""
    ws = (workspace or WORKSPACE).resolve()
    table_id = resolve_tips_edu_table_id(pipeline.category_code, fallback=pipeline.table_id)
    moodboard_id = resolve_krea_moodboard_id(
        pipeline.category_code, fallback=pipeline.moodboard_id, workspace=ws
    )
    prompts_list = load_tips_edu_json_prompts(
        ws,
        pipeline.category_code,
        pipeline.interior_prompts or (pipeline.interior_prompt,),
    )
    prompts = tuple(prompts_list) if prompts_list else pipeline.interior_prompts
    interior_prompt = prompts[0] if prompts else pipeline.interior_prompt

    # Fallback overrides from settings.json if table_id/moodboard_id still unchanged
    config = load_tips_edu_story_config(ws)
    entry = find_tips_edu_story_entry(config, pipeline.category_code) or find_tips_edu_story_entry(
        config, pipeline.table_id
    )
    if entry and isinstance(entry, dict):
        if table_id == pipeline.table_id:
            table_id = str(entry.get("table_id") or table_id).strip() or table_id
        if moodboard_id == pipeline.moodboard_id:
            moodboard_id = str(entry.get("moodboard_id") or moodboard_id).strip() or moodboard_id

    return dataclasses.replace(
        pipeline,
        table_id=table_id,
        moodboard_id=moodboard_id,
        interior_prompt=interior_prompt,
        interior_prompts=prompts,
    )



# Default Tips & Edu Story pipeline definition
TIPS_EDU_STORY = TIPS_EDU_STORY_PENDANT

TIPS_EDU_STORY_PIPELINES: dict[str, PipelineDefinition] = {
    "pendant_lights": TIPS_EDU_STORY_PENDANT,
    "floor_lamps": TIPS_EDU_STORY_FLOOR_LAMP,
    "chandeliers": TIPS_EDU_STORY_CHANDELIER,
    "ceiling_mounted": TIPS_EDU_STORY_CEILING_MOUNTED,
    "table_lamps": TIPS_EDU_STORY_TABLE_LAMP,
    "cluster_chandeliers": TIPS_EDU_STORY_CLUSTER_CHANDELIER,
    "pendant": TIPS_EDU_STORY_PENDANT,
    "pendant_light": TIPS_EDU_STORY_PENDANT,
    "floor": TIPS_EDU_STORY_FLOOR_LAMP,
    "floor_lamp": TIPS_EDU_STORY_FLOOR_LAMP,
    "chandelier": TIPS_EDU_STORY_CHANDELIER,
    "ceiling": TIPS_EDU_STORY_CEILING_MOUNTED,
    "ceiling_light": TIPS_EDU_STORY_CEILING_MOUNTED,
    "ceiling_lights": TIPS_EDU_STORY_CEILING_MOUNTED,
    "table": TIPS_EDU_STORY_TABLE_LAMP,
    "table_lamp": TIPS_EDU_STORY_TABLE_LAMP,
    "cluster": TIPS_EDU_STORY_CLUSTER_CHANDELIER,
    "cluster_chandelier": TIPS_EDU_STORY_CLUSTER_CHANDELIER,
    "tblwnFN5a8fLzKuP4": TIPS_EDU_STORY_PENDANT,
    "tblJxWwZexgBHl26B": TIPS_EDU_STORY_FLOOR_LAMP,
    "tblpFiaNn1Ym9fTTk": TIPS_EDU_STORY_CHANDELIER,
    "tblGlRibUZXB9R3Gt": TIPS_EDU_STORY_CEILING_MOUNTED,
    "tblZtENqILDAekLv2": TIPS_EDU_STORY_TABLE_LAMP,
    "tbllzkE2prSyj9BaD": TIPS_EDU_STORY_CLUSTER_CHANDELIER,
}



class JsonlRunLogger:
    """Append redacted, machine-readable events without leaking credentials."""

    _SENSITIVE_KEY = re.compile(
        r"(?:key|token|authorization|secret|password|base64|data_uri|url)$",
        re.IGNORECASE,
    )

    def __init__(self, workspace: Path, automation: str, run_id: str) -> None:
        root = workspace / "output" / "logs" / automation
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / f"{datetime.now(PHT):%Y-%m-%d}.jsonl"
        self.run_id = run_id

    @classmethod
    def _redact(cls, value: Any, key: str = "") -> Any:
        if cls._SENSITIVE_KEY.search(key):
            return "[REDACTED]"
        if isinstance(value, str):
            if "data:" in value or "Authorization:" in value:
                return "[REDACTED]"
            shortened = re.sub(r"https?://[^\s'\"]+", "[REDACTED_URL]", value[:1000])
            return re.sub(r"\bsk-[A-Za-z0-9._-]+", "[REDACTED]", shortened)
        if isinstance(value, dict):
            return {str(k): cls._redact(v, str(k)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._redact(item, key) for item in value]
        return value

    def event(self, event: str, **details: Any) -> None:
        payload = self._redact(details)
        line = {
            "timestamp": pht_timestamp(),
            "run_id": self.run_id,
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")


def append_audit_log(log_entry: dict[str, Any], log_path: Path) -> None:
    """Append a complete, raw, and indented JSON audit record for human auditing."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            content = log_path.read_text(encoding="utf-8").strip()
            if content:
                logs = json.loads(content)
                if not isinstance(logs, list):
                    logs = [logs]
        except Exception:
            logs = []
    logs.append(log_entry)
    log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"[AUDIT LOG] Appended raw log entry to {log_path.name}")


class PhasedContentRunner:
    """One-record pipeline with output-based resume checkpoints."""

    def __init__(
        self,
        definition: PipelineDefinition,
        settings: IsolatedAutomationSettings,
        *,
        airtable: ScrapeAirtableClient | None = None,
        akeneo: AkeneoClient | None = None,
        krea: KreaClient | None = None,
        fal: FalClient | None = None,
        logger: JsonlRunLogger | None = None,
    ) -> None:
        if definition.key.startswith("tips_edu_story"):
            definition = apply_tips_edu_story_settings(definition, settings.workspace)
        self.definition = definition
        self.settings = settings
        self.airtable = airtable or ScrapeAirtableClient(
            settings.airtable_token, settings.airtable_base_id, definition.table_id
        )
        self.akeneo = akeneo or AkeneoClient(
            settings.akeneo_host,
            settings.akeneo_client_id,
            settings.akeneo_secret,
            settings.akeneo_username,
            settings.akeneo_password,
            channel_name=settings.channel_name,
        )
        self.krea = krea or KreaClient(settings.krea_token, settings.krea_base_url)
        self.fal = fal or FalClient(settings.fal_key)
        self.run_id = uuid.uuid4().hex
        self.logger = logger or JsonlRunLogger(settings.workspace, definition.key, self.run_id)

    @property
    def is_day_night(self) -> bool:
        return self.definition.key.startswith("day_night_reel")

    @property
    def audit_log_dir(self) -> Path:
        path = self.settings.workspace / "output" / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def artifact_root(self) -> Path:
        path = self.settings.output_dir / self.definition.key / "phase_artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _artifact_path(self, record_id: str, filename: str) -> Path:
        path = self.artifact_root / record_id
        path.mkdir(parents=True, exist_ok=True)
        return path / filename

    def _schema_fields(self) -> dict[str, str]:
        required = {
            "Furniture Item": "multipleAttachments",
            "SKU": "multilineText",
            "Item Name": "multilineText",
            self.definition.interior_field: "multipleAttachments",
            "Prompt for Blending": "multilineText",
            self.definition.blended_field: "multipleAttachments",
            self.definition.final_field: "multipleAttachments",
        }
        if self.definition.key.startswith("tips_edu_story") or self.is_day_night:
            required[TARGET_BLENDED_FIELD] = "multipleAttachments"
        if self.definition.video_field:
            required[self.definition.video_field] = "multipleAttachments"
        if self.definition.music_field:
            required[self.definition.music_field] = "multipleAttachments"
        if self.definition.outro_field:
            required[self.definition.outro_field] = "multipleAttachments"
        if self.definition.layout_field:
            required[self.definition.layout_field] = "multipleAttachments"
        return required

    def _status_values(self) -> list[str]:
        values = ["Standby", "Complete", "Error"]
        for phase in range(2, self.definition.phase_count + 1):
            values.extend(
                [
                    f"Phase {phase} - Processing",
                    f"Phase {phase} - Ready",
                    f"Phase {phase} - Failed",
                ]
            )
        return values

    def preflight(self) -> None:
        self.airtable.ensure_fields(self._schema_fields())
        self.airtable.ensure_single_select_options("Status", self._status_values())
        if self.definition.final_prompt_asset:
            asset = AssetCatalog(self.settings.workspace).path(self.definition.final_prompt_asset)
            if not asset.is_file():
                raise AssetValidationError(f"Missing prompt asset: {asset}")
        if self.definition.layout_asset:
            layout = AssetCatalog(self.settings.workspace).path(self.definition.layout_asset)
            if not layout.is_file():
                raise AssetValidationError(f"Missing layout asset: {layout}")
        if self.definition.outro_asset:
            outro = AssetCatalog(self.settings.workspace).path(self.definition.outro_asset)
            if not outro.is_file():
                raise AssetValidationError(f"Missing outro asset: {outro}")
        self.logger.event("preflight_completed", table_id=self.definition.table_id)

    def _backfill_missing_outro(self) -> int:
        """Auto-attach outro asset to existing records in Airtable that lack an Outro attachment."""
        outro_field = self.definition.outro_field
        if not outro_field or not self.definition.outro_asset:
            return 0

        outro_source: Path | None = None
        if self.definition.outro_asset:
            candidate = AssetCatalog(self.settings.workspace).path(self.definition.outro_asset)
            if candidate.is_file():
                outro_source = candidate
        if not outro_source:
            workspace_outro = self.settings.workspace / "Outro for All Reels" / "Outro.jpg"
            if workspace_outro.is_file():
                outro_source = workspace_outro
        if not outro_source:
            return 0

        records = self._records()
        backfilled_count = 0
        for record in records:
            record_id = record.get("id")
            fields = record.get("fields", {})
            status_cf = str(fields.get("Status") or "").strip().casefold()
            if status_cf in TERMINAL_AND_PROTECTED_STATUSES or "complete" in status_cf:
                continue
            if self._has_attachment(fields, self.definition.final_field):
                continue
            if not self._has_attachment(fields, outro_field):
                item_label = fields.get("Item Name") or fields.get("SKU") or record_id
                print(f"[INFO] Auto-backfilling missing '{outro_field}' ({outro_source.name}) for {item_label}...", flush=True)
                try:
                    self.airtable.upload_attachment(
                        record_id,
                        outro_field,
                        outro_source,
                        outro_source.name,
                    )
                    fields[outro_field] = [{"id": "backfilled", "filename": outro_source.name}]
                    backfilled_count += 1
                    print(f"[OK] Backfilled '{outro_field}' on record {record_id}", flush=True)
                except Exception as err:
                    print(f"[WARN] Failed backfilling '{outro_field}' on record {record_id}: {err}", flush=True)
        if backfilled_count > 0:
            print(f"[OK] Successfully backfilled Outro on {backfilled_count} record(s).", flush=True)
        return backfilled_count

    def run(self, phase: int | str = "all", *, resume: bool = False, max_items: int = 1) -> None:
        self.preflight()
        if self.definition.outro_field and self.definition.outro_asset:
            try:
                self._backfill_missing_outro()
            except Exception as b_err:
                print(f"[WARN] Outro auto-backfill note: {b_err}", flush=True)
        if phase == "all":
            items_to_process = max(1, int(max_items or 1))
            for item_idx in range(items_to_process):
                if items_to_process > 1:
                    print(f"\n[BATCH] Processing item {item_idx + 1} of {items_to_process}...", flush=True)
                record = None
                start_phase = 2
                if resume and item_idx == 0:
                    # User explicitly requested to resume an incomplete / interrupted row (first item only)
                    record, start_phase = self._next_incomplete()
                    if record:
                        item_name = record.get("fields", {}).get("Item Name") or record.get("fields", {}).get("SKU") or record["id"]
                        print(f"[INFO] Resuming interrupted row {record['id']} ('{item_name}') starting from Phase {start_phase}...", flush=True)
                    else:
                        print("[INFO] No incomplete rows found to resume. Scraping a new candidate...", flush=True)
                if record is None:
                    print("[INFO] Creating a new row: scraping product candidate from Akeneo...", flush=True)
                    record = self._phase_1()
                    start_phase = 2
                for phase_number in range(start_phase, self.definition.phase_count + 1):
                    self._run_phase(phase_number, record["id"])
            return
        phase_number = int(phase)
        if phase_number == 1:
            self._phase_1()
            return
        record = self._find_for_phase(phase_number)
        if record is None:
            raise AutomationError(f"No Airtable row is eligible for phase {phase_number}")
        self._run_phase(phase_number, record["id"])

    def _records(self) -> list[dict[str, Any]]:
        fields = list(self._schema_fields()) + ["Status"]
        records = self.airtable.list_records(fields)
        return sorted(
            records,
            key=lambda item: (str(item.get("createdTime") or ""), str(item.get("id") or "")),
        )

    @staticmethod
    def _has_attachment(fields: dict[str, Any], field_name: str) -> bool:
        return bool(fields.get(field_name) or [])

    def _phase_for_record(self, record: dict[str, Any]) -> int | None:
        fields = record.get("fields", {})
        status = str(fields.get("Status") or "").strip()
        status_cf = status.casefold()
        # Strictly ignore any completed, protected, scheduled, posted, discarded, or error records
        if status_cf in TERMINAL_AND_PROTECTED_STATUSES or "complete" in status_cf or "error" in status_cf:
            return None
        # Also, if final media is already attached, it's 100% complete
        if self._has_attachment(fields, self.definition.final_field):
            return None
        if not self._has_attachment(fields, "Furniture Item"):
            return None
        if not self._has_attachment(fields, self.definition.interior_field):
            return 2
        if not str(fields.get("Prompt for Blending") or "").strip():
            return 3
        if self.is_day_night:
            local_blend = self._artifact_path(record["id"], "day_and_night_blended.jpg")
            if not self._has_attachment(fields, self.definition.blended_field):
                return 5 if local_blend.is_file() else 4
            if not self._has_attachment(fields, self.definition.video_field or "REEL - Day & Night"):
                return 6
            if ENABLE_DAY_NIGHT_MUSIC and not self._has_attachment(fields, self.definition.music_field or "Music Generated"):
                return 7
            if not self._has_attachment(fields, self.definition.final_field):
                return 8
            return None
        elif not self._has_attachment(fields, self.definition.blended_field):
            return 4
        if not self._has_attachment(fields, self.definition.final_field):
            return self.definition.phase_count
        return None

    def _next_incomplete(self) -> tuple[dict[str, Any] | None, int]:
        for record in self._records():
            next_phase = self._phase_for_record(record)
            if next_phase:
                return record, next_phase
        return None, 0

    def _find_for_phase(self, phase: int) -> dict[str, Any] | None:
        # Search newest first for the latest row that needs this phase
        for record in reversed(self._records()):
            if self._phase_for_record(record) == phase:
                return record
        return None

    def _update_status(self, record_id: str, status: str) -> None:
        fields: dict[str, Any] = {"Status": status}
        if str(status).strip().casefold() == "complete":
            fields["Date and Time Generated"] = current_pht_timestamp()
        self.airtable.update_records([(record_id, fields)])
        self.logger.event("status_updated", record_id=record_id, status=status)

    def _run_phase(self, phase: int, record_id: str) -> None:
        if self.is_day_night:
            phase_names = {
                1: "Akeneo Scrape",
                2: "Krea AI Room Interior",
                3: "Claude Sonnet 5 Prompt Analysis (via Fal AI)",
                4: "Fal AI Nano Banana Pro Day & Night Blending (9:16)",
                5: "Airtable Blended Image Sync",
                6: "Fal AI Kling 15s Timelapse Video Generation",
                7: "Fal AI Stable Audio 3 Jazz Music Generation (Claude Sonnet 5)",
                8: "Video + Outro + Jazz Music Merging & Final Upload",
            }
        else:
            phase_names = {
                1: "Akeneo Scrape (Random Eligible Candidate)",
                2: "Krea AI Room Interior",
                3: "Claude Sonnet 5 Prompt Analysis (via Fal AI)",
                4: "Fal AI Nano Banana Pro Blending (9:16)",
                5: "Fal AI Nano Banana Pro Final Story Conversion (9:16)",
            }
        phase_label = phase_names.get(phase, f"Phase {phase}")
        print(f"\n[INFO] >>> Starting Phase {phase}/{self.definition.phase_count}: {phase_label} for record {record_id}...", flush=True)
        self._update_status(record_id, f"Phase {phase} - Processing")
        self.logger.event("phase_started", record_id=record_id, phase=phase)
        try:
            actions = {
                2: self._phase_2,
                3: self._phase_3,
                4: self._phase_4,
                5: self._phase_5,
                6: self._phase_6,
                7: self._phase_7,
                8: self._phase_8,
            }
            actions[phase](record_id)
            if phase == self.definition.phase_count:
                self._update_status(record_id, "Complete")
                print(f"[OK] Record {record_id} is 100% COMPLETE! Final media uploaded to '{self.definition.final_field}'.\n", flush=True)
            else:
                self._update_status(record_id, f"Phase {phase} - Ready")
                print(f"[OK] Phase {phase} completed successfully for record {record_id}.\n", flush=True)
            self.logger.event("phase_completed", record_id=record_id, phase=phase)
        except Exception as error:
            self._update_status(record_id, f"Phase {phase} - Failed")
            print(f"[ERROR] Phase {phase} failed for record {record_id}: {error}\n", flush=True)
            self.logger.event(
                "phase_failed",
                record_id=record_id,
                phase=phase,
                error=str(error),
            )
            raise

    def _phase_1(self) -> dict[str, Any]:
        self.logger.event("phase_started", phase=1)
        self.akeneo.authenticate()

        # Global base-wide deduplication across ALL tables in the Airtable base
        base_skus: set[str] = set()
        base_names: set[str] = set()
        base_files: set[str] = set()
        if getattr(self.airtable, "base_id", None):
            try:
                base_skus, base_names, base_files = fetch_all_base_existing_identities(self.airtable)
                print(
                    f"[INFO] Cross-table deduplication active: Found {len(base_skus)} existing SKU(s), "
                    f"{len(base_names)} item name(s), and {len(base_files)} media file(s) across all Airtable tables.",
                    flush=True,
                )
            except Exception as dedup_err:
                print(f"[WARN] Base-wide deduplication scan note: {dedup_err}", flush=True)

        local_skus, _ = self.airtable.load_inventory()
        existing_skus = set(base_skus) | set(local_skus)

        ak_cat = akeneo_category_code(self.definition.category_code)
        query = {
            "categories": [
                {"operator": "IN", "value": [ak_cat]}
            ],
            "enabled": [{"operator": "=", "value": True}],
        }
        if self.settings.style_code and self.settings.style_code.lower() != "all":
            query["Style2"] = [{"operator": "IN", "value": [self.settings.style_code]}]
        products = self.akeneo.fetch_products(query)
        existing_names, existing_media = existing_product_identities(products, existing_skus)
        all_names = set(base_names) | set(existing_names)
        all_media = set(base_files) | set(existing_media)

        candidates, _ = select_new_products(
            products,
            existing_skus,
            existing_item_names=all_names,
            existing_media_codes=all_media,
            category_code=self.definition.category_code,
        )
        if not candidates and self.settings.style_code and self.settings.style_code.lower() != "all":
            print(f"[INFO] Style '{self.settings.style_code}' yielded no new candidates. Broadening search across all styles...", flush=True)
            fallback_query = {
                "categories": [{"operator": "IN", "value": [ak_cat]}],
                "enabled": [{"operator": "=", "value": True}],
            }
            products = self.akeneo.fetch_products(fallback_query)
            existing_names, existing_media = existing_product_identities(products, existing_skus)
            all_names = set(base_names) | set(existing_names)
            all_media = set(base_files) | set(existing_media)
            candidates, _ = select_new_products(
                products,
                existing_skus,
                existing_item_names=all_names,
                existing_media_codes=all_media,
                category_code=self.definition.category_code,
            )
        if not candidates:
            raise AutomationError("Akeneo returned no new eligible product to scrape (all products already exist across Airtable tables)")

        # Cross-check candidates against published products on Shopify (Strict Verification)
        print(f"[INFO] Cross-checking {len(candidates)} Akeneo candidate(s) against Shopify published catalog...", flush=True)
        try:
            shopify = ShopifyClient()
            shopify_index = shopify.load_published_identities()
        except Exception as shopify_err:
            raise AutomationError(
                f"Strict Shopify verification failed to load catalog ({shopify_err}). "
                "Aborting to prevent inactive products from entering pipeline."
            ) from shopify_err

        active_candidates: list[ProductItem] = []
        excluded_shopify = 0
        for cand in candidates:
            if shopify_index.contains(cand.sku, cand.item_name):
                active_candidates.append(cand)
            else:
                try:
                    print(f"  [SHOPIFY DRAFT/INACTIVE SKIP] Item '{cand.item_name}' (SKU: {cand.sku}) is Enabled in Akeneo but Draft/Inactive in Shopify -> skipping", flush=True)
                except Exception:
                    print(f"  [SHOPIFY DRAFT/INACTIVE SKIP] SKU {cand.sku} is not active in Shopify -> skipping", flush=True)
                excluded_shopify += 1

        print(
            f"[INFO] Shopify cross-check: {len(active_candidates)} active on Shopify, "
            f"{excluded_shopify} excluded (Draft/Inactive in Shopify).",
            flush=True,
        )

        if not active_candidates:
            raise AutomationError(
                f"No active/published Shopify products found among eligible Akeneo candidates "
                f"({len(candidates)} candidates checked, but all {excluded_shopify} are Draft/Inactive on Shopify)."
            )

        item = random.choice(active_candidates)
        full_name = format_item_name_with_product_type(
            item.item_name,
            item.product_type,
            category_code=self.definition.category_code,
        )

        print(f"[OK] Selected non-duplicate product: {item.sku} ('{full_name}') from {len(candidates)} eligible candidate(s).", flush=True)
        record_id = self.airtable.create_record(
            {"SKU": item.sku, "Item Name": full_name, "Status": "Standby"}
        )
        download = None
        try:
            download = self.akeneo.download_media(item.media_code)
            self.airtable.upload_attachment(
                record_id,
                "Furniture Item",
                download,
                Path(item.media_code).name or f"{item.sku}.jpg",
            )
            if self.definition.layout_field and self.definition.layout_asset:
                layout_path = AssetCatalog(self.settings.workspace).path(self.definition.layout_asset)
                if not layout_path.is_file():
                    raise AssetValidationError(f"Missing layout asset: {layout_path}")
                self.airtable.upload_attachment(
                    record_id,
                    self.definition.layout_field,
                    layout_path,
                    layout_path.name,
                )
            if self.definition.outro_field and self.definition.outro_asset:
                outro_path = AssetCatalog(self.settings.workspace).path(self.definition.outro_asset)
                if not outro_path.is_file():
                    raise AssetValidationError(f"Missing outro asset: {outro_path}")
                self.airtable.upload_attachment(
                    record_id,
                    self.definition.outro_field,
                    outro_path,
                    outro_path.name,
                )
        except Exception:
            self._update_status(record_id, "Phase 1 - Failed")
            raise
        finally:
            if download:
                download.cleanup()
        self._update_status(record_id, "Standby")
        self.logger.event(
            "phase_completed",
            phase=1,
            record_id=record_id,
            sku=item.sku,
            item_name=full_name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": item.sku,
                "item_name": full_name,
                "category": self.definition.category_code,
                "style": self.settings.style_code,
                "media_code": item.media_code,
                "status": "Standby",
            },
            self.audit_log_dir / f"{self.definition.key}_akeneo_logs.json",
        )
        return self.airtable.get_record(record_id)

    def _record(self, record_id: str) -> dict[str, Any]:
        return self.airtable.get_record(record_id)

    def _resolve_logo_path(self, fields: dict[str, Any] | None = None) -> Path | None:
        """Resolve the HomeCartel logo asset path from Airtable 'Logo' field or local fallback."""
        if fields:
            logo_attachments = fields.get("Logo") or []
            if isinstance(logo_attachments, list) and logo_attachments and isinstance(logo_attachments[0], dict):
                logo_url = str(logo_attachments[0].get("url") or "").strip()
                if logo_url:
                    try:
                        cached_logo = self.settings.workspace / "output" / "cache" / "airtable_logo.png"
                        cached_logo.parent.mkdir(parents=True, exist_ok=True)
                        if not cached_logo.is_file() or cached_logo.stat().st_size == 0:
                            resp = requests.get(logo_url, timeout=30)
                            if resp.ok:
                                cached_logo.write_bytes(resp.content)
                        if cached_logo.is_file() and cached_logo.stat().st_size > 0:
                            return cached_logo
                    except Exception:
                        pass

        # Local fallbacks
        workspace = self.settings.workspace or Path(".")
        candidates = [
            workspace / "assets" / "homecartel_logo.png",
            workspace / "assets" / "Logo.png",
            workspace / "assets" / "logo.png",
            workspace / "JSON Prompts" / "homecartel_logo.png",
            Path("assets/homecartel_logo.png"),
            Path("assets/Logo.png"),
        ]
        for cand in candidates:
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
        return None

    @staticmethod
    def _attachment_url(fields: dict[str, Any], field_name: str) -> str:
        attachments = fields.get(field_name) or []
        if isinstance(attachments, list) and attachments and isinstance(attachments[0], dict):
            url = str(attachments[0].get("url") or "").strip()
            if url:
                return url
        raise AssetValidationError(f"Missing accessible attachment: {field_name}")

    @staticmethod
    def _validate_dimensions(path: Path, dimensions: tuple[int, int], label: str) -> None:
        try:
            with Image.open(path) as image:
                actual = image.size
        except (OSError, UnidentifiedImageError) as error:
            raise AssetValidationError(f"Unreadable {label}: {path}") from error
        if actual != dimensions:
            raise AssetValidationError(
                f"{label} must be {dimensions[0]}x{dimensions[1]}, found {actual[0]}x{actual[1]}"
            )

    @staticmethod
    def _validate_9_16(path: Path, label: str) -> None:
        try:
            with Image.open(path) as image:
                width, height = image.size
        except (OSError, UnidentifiedImageError) as error:
            raise AssetValidationError(f"Unreadable {label}: {path}") from error
        if not width or abs((width / height) - (9 / 16)) > 0.01:
            raise AssetValidationError(f"{label} must have a 9:16 aspect ratio, found {width}x{height}")

    @staticmethod
    def _download(url: str, destination: Path) -> Path:
        response = requests.get(url, stream=True, timeout=180)
        if not response.ok:
            raise ProviderError(f"Download generated media failed ({response.status_code})")
        temporary = destination.with_suffix(destination.suffix + ".part")
        with temporary.open("wb") as stream:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    stream.write(chunk)
        temporary.replace(destination)
        return destination

    def _phase_2(self, record_id: str) -> None:
        # Honor explicitly configured/overridden interior prompt
        if self.definition.interior_prompt and self.definition.interior_prompt.strip():
            prompt = self.definition.interior_prompt.strip()
        else:
            available_prompts = load_tips_edu_json_prompts(
                self.settings.workspace,
                self.definition.category_code,
                self.definition.interior_prompts or (self.definition.interior_prompt,),
            )
            prompt = random.choice(available_prompts)

        # Honor explicitly configured/overridden moodboard ID
        if self.definition.moodboard_id and self.definition.moodboard_id.strip():
            moodboard_id = self.definition.moodboard_id.strip()
        else:
            moodboard_id = resolve_krea_moodboard_id(
                self.definition.category_code,
                self.definition.moodboard_id,
                workspace=self.settings.workspace,
            )

        print(
            f"[INFO] [Phase 2/{self.definition.phase_count}] Krea AI Interior Generation | "
            f"Moodboard: {moodboard_id} | Prompt: \"{prompt}\"",
            flush=True,
        )

        url = self.krea.generate(
            prompt,
            aspect_ratio=KREA_ASPECT_RATIO,
            resolution="1K",
            moodboard_id=moodboard_id,
        )
        downloaded = self.krea.download_image(url)
        try:
            self._validate_9_16(Path(downloaded.path), "Krea interior")
            self.airtable.upload_attachment(
                record_id,
                self.definition.interior_field,
                downloaded,
                f"interior_{record_id}.jpg",
            )
        finally:
            downloaded.cleanup()
        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=2,
            provider="krea",
            model=KREA_MODEL_LABEL,
            moodboard_id=moodboard_id,
        )
        fields = self._record(record_id).get("fields", {})
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": "Phase 2: Krea AI Interior Generation",
                "api_provider": "Krea AI",
                "raw_request": {
                    "prompt": prompt,
                    "aspect_ratio": KREA_ASPECT_RATIO,
                    "resolution": "1K",
                    "moodboard_id": moodboard_id,
                    "model": KREA_MODEL_LABEL,
                },
                "raw_response": {

                    "output_image_url": url,
                    "target_field": self.definition.interior_field,
                    "status": "completed",
                },
            },
            self.audit_log_dir / f"{self.definition.key}_krea_logs.json",
        )

    def _phase_3(self, record_id: str) -> None:
        fields = self._record(record_id).get("fields", {})
        interior_url = self._attachment_url(fields, self.definition.interior_field)
        product_url = self._attachment_url(fields, "Furniture Item")
        item_name = str(fields.get("Item Name") or fields.get("SKU") or "Lighting Product").strip()

        ratio = getattr(self.definition, "aspect_ratio", None) or "9:16"
        instruction = build_vision_blending_instruction(
            interior_label=f"Room Interior ('{self.definition.interior_field}')",
            item_name=item_name,
            aspect_ratio=ratio,
        )
        print(f"  Requesting vision blending prompt from Claude Sonnet 5 ({FAL_VISION_MODEL})...", flush=True)
        raw_prompt = self.fal.generate_vision_prompt(
            [interior_url, product_url],
            instruction,
            model=FAL_VISION_MODEL,
        )
        clean_prompt = raw_prompt.strip().strip('"').strip("'")
        self.airtable.update_records([(record_id, {"Prompt for Blending": clean_prompt})])
        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=3,
            provider="fal",
            model=FAL_VISION_MODEL,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": item_name,
                "phase": "Phase 3: Claude Sonnet 5 Prompt Analysis (via Fal AI)",
                "api_provider": "Fal AI (OpenRouter Vision)",
                "api_model": FAL_VISION_MODEL,
                "raw_request": {
                    "model": FAL_VISION_MODEL,
                    "input_interior_url": interior_url,
                    "input_furniture_url": product_url,
                    "instruction": instruction,
                },
                "raw_response": {
                    "generated_prompt": clean_prompt,
                    "target_field": "Prompt for Blending",
                },
            },
            self.audit_log_dir / f"{self.definition.key}_claude_logs.json",
        )

    def _phase_4(self, record_id: str) -> None:
        fields = self._record(record_id).get("fields", {})
        prompt = str(fields.get("Prompt for Blending") or "").strip()
        if not prompt:
            raise AssetValidationError("Prompt for Blending is empty")
        try:
            parsed = json.loads(prompt)
            if isinstance(parsed, dict) and "final_blending_prompt" in parsed:
                prompt = str(parsed["final_blending_prompt"]).strip()
        except Exception:
            pass

        image_urls = [
            self._attachment_url(fields, self.definition.interior_field),
            self._attachment_url(fields, "Furniture Item"),
        ]

        filename = "day_and_night_blended.jpg" if self.is_day_night else "tips_edu_blended.jpg"
        print(f"  Sending image blending request to Fal AI Nano Banana Pro ({FAL_NANO_BANANA_MODEL}) at 9:16...", flush=True)
        result_url = self.fal.generate(
            prompt,
            image_urls,
            aspect_ratio="9:16",
            resolution="1K",
            model=FAL_NANO_BANANA_MODEL,
        )
        destination = self._artifact_path(record_id, filename)
        self._download(result_url, destination)
        self._validate_9_16(destination, "Nano Banana Pro blended image")

        if not self.is_day_night:
            self.airtable.upload_attachment(record_id, self.definition.blended_field, destination, destination.name)
            if self.definition.key.startswith("tips_edu_story"):
                try:
                    raw_item_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
                    item_title, product_type = split_item_name(
                        raw_item_name, fallback_product_type=str(fields.get("Product Type") or "")
                    )
                    print(
                        f"\n [ITEM TAGGING] Stamping item name ('{item_title}') onto 9:16 Blended Image -> '{TARGET_BLENDED_FIELD}'...",
                        flush=True,
                    )
                    tag_and_upload_blended_image(
                        airtable=self.airtable,
                        record_id=record_id,
                        blended_source=destination,
                        item_name=item_title,
                        product_type=product_type,
                        category=self.definition.category_code,
                        target_field=TARGET_BLENDED_FIELD,
                        output_filename_prefix=f"{self.definition.key}_tagged",
                    )
                except Exception as tag_err:
                    print(
                        f"  [WARN] Failed auto-tagging item name onto Tips & Edu Story blended image: {tag_err}",
                        flush=True,
                    )

        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=4,
            provider="fal",
            model=FAL_NANO_BANANA_MODEL,
            aspect_ratio="9:16",
            attachment_filename=destination.name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": f"Phase 4: Fal AI Nano Banana Pro Blending ({filename})",
                "api_provider": "Fal AI (Nano Banana Pro)",
                "api_model": FAL_NANO_BANANA_MODEL,
                "raw_request": {
                    "model": FAL_NANO_BANANA_MODEL,
                    "aspect_ratio": "9:16",
                    "resolution": "1K",
                    "input_images": image_urls,
                    "prompt": prompt,
                },
                "raw_response": {
                    "output_image_url": result_url,
                    "local_artifact_path": str(destination),
                },
            },
            self.audit_log_dir / f"{self.definition.key}_fal_nano_logs.json",
        )

    def _phase_5(self, record_id: str) -> None:
        fields = self._record(record_id).get("fields", {})
        if self.is_day_night:
            source = self._artifact_path(record_id, "day_and_night_blended.jpg")
            if not source.is_file():
                raise AssetValidationError("Phase 4 blend artifact is missing; rerun Phase 4")
            self._validate_9_16(source, "Day and Night blend")
            self.airtable.upload_attachment(record_id, self.definition.blended_field, source, source.name)

            # Auto-tag furniture item name onto Day & Night Reel Blended Image using YOLO-World
            try:
                raw_item_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
                item_title, product_type = split_item_name(
                    raw_item_name, fallback_product_type=str(fields.get("Product Type") or "")
                )
                print(
                    f"\n [ITEM TAGGING] Stamping item name ('{item_title}') onto Day & Night Reel Blended Image -> '{TARGET_BLENDED_FIELD}'...",
                    flush=True,
                )
                tag_and_upload_blended_image(
                    airtable=self.airtable,
                    record_id=record_id,
                    blended_source=source,
                    item_name=item_title,
                    product_type=product_type,
                    category=self.definition.category_code,
                    target_field=TARGET_BLENDED_FIELD,
                    output_filename_prefix=f"{self.definition.key}_tagged",
                    fallback_if_undetected=True,
                )
            except Exception as tag_err:
                print(f"  [WARN] Failed auto-tagging item name onto Day & Night Reel: {tag_err}", flush=True)

            return

        if self.definition.key.startswith("tips_edu_story"):
            if not self._has_attachment(fields, TARGET_BLENDED_FIELD):
                if self._has_attachment(fields, self.definition.blended_field):
                    raw_blended_url = self._attachment_url(fields, self.definition.blended_field)
                    raw_item_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
                    item_title, product_type = split_item_name(
                        raw_item_name, fallback_product_type=str(fields.get("Product Type") or "")
                    )
                    print(
                        f"\n  [ON-THE-FLY TAGGING] '{TARGET_BLENDED_FIELD}' missing on record {record_id}. "
                        f"Auto-tagging '{item_title}' from '{self.definition.blended_field}'...",
                        flush=True,
                    )
                    tag_and_upload_blended_image(
                        airtable=self.airtable,
                        record_id=record_id,
                        blended_source=raw_blended_url,
                        item_name=item_title,
                        product_type=product_type,
                        category=self.definition.category_code,
                        target_field=TARGET_BLENDED_FIELD,
                        output_filename_prefix=f"{self.definition.key}_tagged",
                        fallback_if_undetected=True,
                    )
                    fields = self._record(record_id).get("fields", {})

            target_blended_field = TARGET_BLENDED_FIELD if self._has_attachment(fields, TARGET_BLENDED_FIELD) else self.definition.blended_field
            print(f"  [1/3] Reading '{target_blended_field}' and '{self.definition.layout_field}' attachments from Airtable...", flush=True)
            blended_url = self._attachment_url(fields, target_blended_field)
        else:
            print(f"  [1/3] Reading '{self.definition.blended_field}' and '{self.definition.layout_field}' attachments from Airtable...", flush=True)
            blended_url = self._attachment_url(fields, self.definition.blended_field)

        if not self._has_attachment(fields, self.definition.layout_field) and self.definition.layout_asset:
            layout_path = AssetCatalog(self.settings.workspace).path(self.definition.layout_asset)
            if layout_path.is_file():
                self.airtable.upload_attachment(
                    record_id,
                    self.definition.layout_field,
                    layout_path,
                    layout_path.name,
                )
                fields = self._record(record_id).get("fields", {})
        layout_url = self._attachment_url(fields, self.definition.layout_field)
        prompt = AssetCatalog(self.settings.workspace).read_prompt(self.definition.final_prompt_asset)
        if self.definition.key.startswith("tips_edu_story"):
            try:
                raw_item_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
                item_title, product_type = split_item_name(
                    raw_item_name, fallback_product_type=str(fields.get("Product Type") or "")
                )
                prompt_data = json.loads(prompt)
                prompt_data["specific_fixture_preservation"] = {
                    "product_name": item_title,
                    "product_type": product_type,
                    "category": self.definition.category_code,
                    "instruction": (
                        f"The product advertised in Image 1 is '{item_title}' ({product_type}). "
                        f"Image 1 shows the exact '{item_title}' installed in the room WITH its floating white name tag beside it. "
                        f"You MUST preserve this exact '{item_title}' fixture and its floating white text tag with 100% precision. "
                        f"DO NOT replace, redesign, or alter the chandelier/lighting fixture, and DO NOT erase the floating white text."
                    ),
                }
                prompt = json.dumps(prompt_data)
            except Exception as inject_err:
                print(f"  [WARN] Dynamic prompt injection note: {inject_err}", flush=True)

        print(f"  [2/3] Sending layout conversion request to Fal AI Nano Banana Pro ({FAL_NANO_BANANA_MODEL}) at 9:16...", flush=True)
        result_url = self.fal.generate(
            prompt,
            [blended_url, layout_url],
            aspect_ratio="9:16",
            resolution="1K",
            model=FAL_NANO_BANANA_MODEL,
        )
        filename = "tips_edu_story_converted.jpg"
        destination = self._artifact_path(record_id, filename)
        self._download(result_url, destination)
        self._validate_9_16(destination, "Nano Banana Pro story converted image")

        if self.definition.key.startswith("tips_edu_story"):
            # Ensure the floating item name text is 100% sharp and visible on the final story conversion
            try:
                raw_item_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
                item_title, product_type = split_item_name(
                    raw_item_name, fallback_product_type=str(fields.get("Product Type") or "")
                )
                tagged_conv, _ = tag_blended_image(
                    image_input=destination,
                    item_name=item_title,
                    product_type=product_type,
                    category=self.definition.category_code,
                    destination=destination,
                )
                if tagged_conv is not None:
                    print(f"  [OK] Guaranteed sharp floating item name text tag stamped onto final story conversion ({destination.name}).", flush=True)
            except Exception as stamp_err:
                print(f"  [WARN] Story conversion text tag guarantee note: {stamp_err}", flush=True)

            # Local PIL Brand Logo Stamping (Story Top-Right: X=781.7, Y=108.0 | 190.3 x 63.5 px)
            try:
                logo_path = self._resolve_logo_path(fields)
                if logo_path and logo_path.is_file():
                    stamp_logo(
                        base_path=destination,
                        logo_path=logo_path,
                        destination=destination,
                        box=HOMECARTEL_STORY_LOGO_BOX,
                    )
                    print(
                        f"  [OK] Stamped HomeCartel Story logo onto final story conversion "
                        f"(Top-Right: X=781.7, Y=108.0 | 190.3 x 63.5 px) -> {destination.name}",
                        flush=True,
                    )
                else:
                    print("  [WARN] No brand logo asset found to stamp onto story conversion.", flush=True)
            except Exception as logo_err:
                print(f"  [WARN] Story conversion logo stamping note: {logo_err}", flush=True)

        print(f"  [3/3] Uploading converted story to '{self.definition.final_field}' on record {record_id}...", flush=True)
        self.airtable.upload_attachment(record_id, self.definition.final_field, destination, destination.name)
        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=5,
            provider="fal",
            model=FAL_NANO_BANANA_MODEL,
            aspect_ratio="9:16",
            attachment_filename=destination.name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": f"Phase 5: Fal AI Nano Banana Pro Layout Conversion ({filename})",
                "api_provider": "Fal AI (Nano Banana Pro)",
                "api_model": FAL_NANO_BANANA_MODEL,
                "raw_request": {
                    "model": FAL_NANO_BANANA_MODEL,
                    "aspect_ratio": "9:16",
                    "resolution": "1K",
                    "input_images": [blended_url, layout_url],
                    "prompt": prompt,
                },
                "raw_response": {
                    "output_image_url": result_url,
                    "local_artifact_path": str(destination),
                },
            },
            self.audit_log_dir / f"{self.definition.key}_fal_nano_layout_logs.json",
        )

    def _phase_6(self, record_id: str) -> None:
        if not self.is_day_night:
            raise AutomationError("Tips & Edu Story has no phase 6")
        fields = self._record(record_id).get("fields", {})
        if self._has_attachment(fields, TARGET_BLENDED_FIELD):
            source_url = self._attachment_url(fields, TARGET_BLENDED_FIELD)
        else:
            source_url = self._attachment_url(fields, self.definition.blended_field)
        local_source = self._artifact_path(record_id, "fal_day_and_night_source.jpg")
        print(f"  [1/4] Downloading blended source image from Airtable...", flush=True)
        self._download(source_url, local_source)
        self._validate_9_16(local_source, "Day and Night blend")
        print(f"  [2/4] Uploading source image to Fal AI CDN...", flush=True)
        fal_source_url = self.fal.upload_file(local_source)
        print(f"  [3/4] Requesting Grok Imagine Video 1.5 15s timelapse from Fal AI ({FAL_GROK_VIDEO_MODEL}) at {DAY_NIGHT_VIDEO_RESOLUTION}...", flush=True)
        video_url = self.fal.generate_grok_video(
            DAY_NIGHT_TIMELAPSE_PROMPT,
            fal_source_url,
            duration=int(DAY_NIGHT_VIDEO_DURATION),
            resolution=DAY_NIGHT_VIDEO_RESOLUTION,
            model=FAL_GROK_VIDEO_MODEL,
        )
        target_video_field = self.definition.video_field or "REEL - Day & Night"
        print(f"  [4/4] Video generated! Downloading & uploading to Airtable '{target_video_field}'...", flush=True)
        video_path = self._artifact_path(record_id, "day_and_night_reel.mp4")
        self._download(video_url, video_path)
        self.airtable.upload_attachment(record_id, target_video_field, video_path, video_path.name)
        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=6,
            provider="fal",
            model=FAL_GROK_VIDEO_MODEL,
            duration_seconds=int(DAY_NIGHT_VIDEO_DURATION),
            resolution=DAY_NIGHT_VIDEO_RESOLUTION,
            attachment_filename=video_path.name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": "Phase 6: xAI Grok Imagine Video 1.5 Timelapse",
                "api_provider": "Fal AI (xAI Grok Imagine Video 1.5)",
                "api_model": FAL_GROK_VIDEO_MODEL,
                "raw_request": {
                    "model": FAL_GROK_VIDEO_MODEL,
                    "prompt": DAY_NIGHT_TIMELAPSE_PROMPT,
                    "airtable_source_url": source_url,
                    "fal_source_url": fal_source_url,
                    "duration_seconds": int(DAY_NIGHT_VIDEO_DURATION),
                    "resolution": DAY_NIGHT_VIDEO_RESOLUTION,
                },
                "raw_response": {
                    "video_url": video_url,
                    "local_video_path": str(video_path),
                    "target_field": target_video_field,
                },
            },
            self.audit_log_dir / f"{self.definition.key}_fal_grok_logs.json",
        )

    def _phase_7(self, record_id: str) -> None:
        if not self.is_day_night:
            raise AutomationError("Tips & Edu Story has no phase 7")
        if not ENABLE_DAY_NIGHT_MUSIC:
            print("  [INFO] Music generation is currently disabled (ENABLE_DAY_NIGHT_MUSIC=False). Skipping Phase 7.", flush=True)
            return
        fields = self._record(record_id).get("fields", {})
        blended_url = self._attachment_url(fields, self.definition.blended_field)
        print(f"  [1/3] Analyzing Day and Night Blended photo with Claude Sonnet 5 ({FAL_VISION_MODEL}) for smooth jazz music prompt...", flush=True)
        music_instruction = (
            "Analyze this interior lighting room photo and describe a smooth, relaxing lounge jazz background music track "
            "with instrumentation (e.g. warm piano, mellow saxophone, gentle acoustic bass/drums, warm ambient tone) "
            "that perfectly matches the mood and atmosphere of this room. "
            "Output ONLY the short prompt description (under 25 words), with no quotes, preamble, or markdown."
        )
        jazz_prompt = ""
        try:
            jazz_prompt = self.fal.generate_vision_prompt(
                [blended_url],
                music_instruction,
                model=FAL_VISION_MODEL,
            ).strip().strip('"').strip("'")
        except Exception as vision_err:
            print(f"  [WARN] Vision music prompt failed ({vision_err}), using default jazz prompt...", flush=True)

        if not jazz_prompt or len(jazz_prompt) < 5:
            jazz_prompt = "Smooth relaxing lounge jazz with warm piano, subtle saxophone, and gentle acoustic rhythm"

        print(f"  [2/3] Generating 18s background jazz music via Fal AI ElevenLabs Music (Prompt: '{jazz_prompt}')...", flush=True)
        audio_url = self.fal.generate_elevenlabs_music(
            jazz_prompt,
            duration=int(DAY_NIGHT_MUSIC_DURATION),
            model=FAL_ELEVENLABS_MUSIC_MODEL,
        )
        target_music_field = self.definition.music_field or "Music Generated"
        print(f"  [3/3] Audio generated! Downloading & uploading to Airtable '{target_music_field}'...", flush=True)
        music_path = self._artifact_path(record_id, "day_and_night_music.mp3")
        self._download(audio_url, music_path)
        self.airtable.upload_attachment(record_id, target_music_field, music_path, music_path.name)
        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=7,
            provider="fal",
            model=FAL_ELEVENLABS_MUSIC_MODEL,
            duration_seconds=int(DAY_NIGHT_MUSIC_DURATION),
            music_prompt=jazz_prompt,
            attachment_filename=music_path.name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": "Phase 7: Fal AI ElevenLabs Jazz Music (Claude Sonnet 5 Prompt)",
                "api_provider": "Fal AI (ElevenLabs Music + Claude Sonnet 5)",
                "api_model": f"{FAL_ELEVENLABS_MUSIC_MODEL} + {FAL_VISION_MODEL}",
                "raw_request": {
                    "vision_model": FAL_VISION_MODEL,
                    "audio_model": FAL_ELEVENLABS_MUSIC_MODEL,
                    "prompt": jazz_prompt,
                    "duration_seconds": int(DAY_NIGHT_MUSIC_DURATION),
                },
                "raw_response": {
                    "audio_url": audio_url,
                    "local_audio_path": str(music_path),
                    "target_field": target_music_field,
                },
            },
            self.audit_log_dir / f"{self.definition.key}_elevenlabs_logs.json",
        )

    def _phase_8(self, record_id: str) -> None:
        if not self.is_day_night:
            raise AutomationError("Tips & Edu Story has no phase 8")
        fields = self._record(record_id).get("fields", {})

        # 1. Download Kling Video
        video_field = self.definition.video_field or "REEL - Day & Night"
        video_url = self._attachment_url(fields, video_field)
        local_video = self._artifact_path(record_id, "day_and_night_reel.mp4")
        print(f"  [1/4] Downloading '{video_field}' from Airtable...", flush=True)
        self._download(video_url, local_video)

        # 2. Download Music Generated (if present)
        music_field = self.definition.music_field or "Music Generated"
        local_music: Path | None = None
        if self._has_attachment(fields, music_field):
            music_url = self._attachment_url(fields, music_field)
            local_music = self._artifact_path(record_id, "day_and_night_music.mp3")
            print(f"  [2/4] Downloading '{music_field}' from Airtable...", flush=True)
            self._download(music_url, local_music)
        else:
            print(f"  [2/4] No '{music_field}' attachment found, proceeding without background audio...", flush=True)

        # 3. Locate / Download Outro image
        outro_field = self.definition.outro_field or "Outro"
        local_outro = self._artifact_path(record_id, "outro.jpg")
        if self._has_attachment(fields, outro_field):
            print(f"  [3/4] Downloading '{outro_field}' attachment from record...", flush=True)
            outro_url = self._attachment_url(fields, outro_field)
            self._download(outro_url, local_outro)
        else:
            outro_source: Path | None = None
            if self.definition.outro_asset:
                candidate = AssetCatalog(self.settings.workspace).path(self.definition.outro_asset)
                if candidate.is_file():
                    outro_source = candidate
            if not outro_source:
                workspace_outro = self.settings.workspace / "Outro for All Reels/Outro.jpg"
                if workspace_outro.is_file():
                    outro_source = workspace_outro
            if outro_source:
                print(f"  [3/4] Auto-attaching Outro image ({outro_source.name}) to Airtable '{outro_field}'...", flush=True)
                import shutil
                local_outro.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(outro_source, local_outro)
                try:
                    self.airtable.upload_attachment(
                        record_id,
                        outro_field,
                        local_outro,
                        outro_source.name,
                    )
                    print(f"  [OK] Outro attached to record {record_id} in Airtable.", flush=True)
                except Exception as upload_err:
                    print(f"  [WARN] Failed to upload Outro to Airtable ({upload_err}), proceeding with local file.", flush=True)
            else:
                local_outro = None

        # 4. Merge Video + Outro + Audio
        audio_desc = " + ElevenLabs Jazz Music" if local_music else " (Video Only)"
        print(f"  [4/4] Merging 15s Grok video + 3s Outro{audio_desc} into 18s vertical reel...", flush=True)
        from .video import merge_video_with_outro_and_audio
        final_video_path = self._artifact_path(record_id, "day_and_night_reel_with_music_and_outro.mp4")
        merge_video_with_outro_and_audio(
            video_path=local_video,
            outro_image_path=local_outro,
            audio_path=local_music,
            output_path=final_video_path,
            video_duration=DAY_NIGHT_VIDEO_DURATION,
            outro_duration=DAY_NIGHT_OUTRO_DURATION,
            fade_duration=1.0,
            audio_fade_duration=3.0,
            width=1080,
            height=1920,
            fps=30,
        )

        # 5. Upload to Final Field
        print(f"  [OK] Video merged! Uploading to Airtable field '{self.definition.final_field}'...", flush=True)
        self.airtable.upload_attachment(
            record_id,
            self.definition.final_field,
            final_video_path,
            final_video_path.name,
        )
        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=8,
            provider="ffmpeg",
            duration_seconds=DAY_NIGHT_VIDEO_DURATION + DAY_NIGHT_OUTRO_DURATION,
            attachment_filename=final_video_path.name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": "Phase 8: Video + Outro + Jazz Music Merging",
                "api_provider": "FFmpeg (local)",
                "raw_request": {
                    "video_field": video_field,
                    "music_field": music_field if local_music else None,
                    "outro_field": outro_field,
                },
                "raw_response": {
                    "local_final_video_path": str(final_video_path),
                    "target_field": self.definition.final_field,
                },
            },
            self.audit_log_dir / f"{self.definition.key}_final_reel_logs.json",
        )
