"""Resumable, isolated phase runners for high-value content automations."""

from __future__ import annotations

import json
import os
import random
import re
import uuid

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PHT = timezone(timedelta(hours=8))  # Philippine Standard Time (UTC+8)


def pht_timestamp() -> str:
    """Return formatted Philippine Standard Time (e.g. 2026-08-14 09:18:04 AM PHT)."""
    return datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")

import requests
from PIL import Image, UnidentifiedImageError

from .akeneo_client import AkeneoClient
from .assets import AssetCatalog
from .errors import AssetValidationError, AutomationError, ProviderError
from .fal_client import FalClient
from .isolated_config import IsolatedAutomationSettings
from .krea_client import KreaClient
from .qwen_client import QwenClient
from .scraping.airtable import ScrapeAirtableClient
from .scraping.categories import akeneo_category_code
from .scraping.furniture_item import (
    fetch_all_base_existing_identities,
    format_item_name_with_product_type,
)
from .scraping.products import (
    existing_product_identities,
    select_new_products,
)


QWEN_PROMPT_MODEL = "qwen3.7-flash"
QWEN_IMAGE_MODEL = "qwen-image-3.0-pro"
QWEN_IMAGE_SIZE = "1536*2688"
QWEN_IMAGE_DIMENSIONS = (1536, 2688)
KREA_ASPECT_RATIO = "9:16"
KREA_MODEL_LABEL = "krea-2-medium"
FAL_KLING_MODEL = "fal-ai/kling-video/v3/turbo/pro/image-to-video"
FAL_STABLE_AUDIO_MODEL = "fal-ai/stable-audio-3/small/music/base/text-to-audio"
FAL_VISION_MODEL = "anthropic/claude-sonnet-5"
FAL_NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"

DAY_NIGHT_MUSIC_DURATION = 18.0
DAY_NIGHT_VIDEO_DURATION = 15.0
DAY_NIGHT_OUTRO_DURATION = 3.0
DAY_NIGHT_TIMELAPSE_PROMPT = (
    'Generate a timelapse of this "day" photo. Start from 7am and timelapse '
    "to 9pm. Consider appropriate lighting, shadows, and natural light coming "
    "from the lighting fixture and outside the interior. Do not change the "
    "angle of the camera and do not change the lighting fixture."
)

    
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


DAY_NIGHT_REEL_CHANDELIER = PipelineDefinition(
    key="day_night_reel_chandeliers",
    table_id="tbl35JySlNuWh61tL",
    category_code="chandeliers",
    moodboard_id="b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    interior_field="Interior",
    blended_field="Day and Night Blended",
    video_field="REEL - Day & Night",
    music_field="Music Generated",
    outro_field="Outro",
    final_field="Day and Night Reel with Music and Outro",
    phase_count=8,
    interior_prompt="Generate me a modern living room with hanging chandelier from the ceiling",
)

DAY_NIGHT_REEL_PENDANT = PipelineDefinition(
    key="day_night_reel_pendant_lights",
    table_id="tblkTuM627s2f0FTN",
    category_code="pendant_lights",
    moodboard_id="de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    interior_field="Interior",
    blended_field="Day and Night Blended",
    video_field="REEL - Day & Night",
    music_field="Music Generated",
    outro_field="Outro",
    final_field="Day and Night Reel with Music and Outro",
    phase_count=8,
    interior_prompt="Generate me a modern dining room hanging chandelier",
)

DAY_NIGHT_REEL_FLOOR_LAMP = PipelineDefinition(
    key="day_night_reel_floor_lamps",
    table_id="tbl2VoWOt7sSut4E2",
    category_code="floor_lamps",
    moodboard_id="b1641228-beec-4823-8d01-1de3eec8410d",
    interior_field="Interior",
    blended_field="Day and Night Blended",
    video_field="REEL - Day & Night",
    music_field="Music Generated",
    outro_field="Outro",
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
    "tblkTuM627s2f0FTN": DAY_NIGHT_REEL_PENDANT,
    "tbl35JySlNuWh61tL": DAY_NIGHT_REEL_PENDANT,
    "tblODnfaNVP6SXn0A": DAY_NIGHT_REEL_CHANDELIER,
    "tbloMhCOngGDWFS2y": DAY_NIGHT_REEL_CHANDELIER,
    "tbl2VoWOt7sSut4E2": DAY_NIGHT_REEL_FLOOR_LAMP,
}



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
    interior_prompt=PENDANT_TIPS_EDU_PROMPTS[0],
    interior_prompts=PENDANT_TIPS_EDU_PROMPTS,
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
    "Generate a premium modern living room interior in a vertical 9:16 composition with a plain, empty ceiling and clear central focal point for a hanging chandelier above the seating area. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern dining room interior in a vertical 9:16 composition featuring a luxury dining table under a plain, clean ceiling with a clear central focal point for a hanging chandelier. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern grand foyer and entryway in a vertical 9:16 composition with high ceilings and a prominent central ceiling focal point for a grand hanging chandelier. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern lounge and conversation area in a vertical 9:16 composition with luxurious seating and a plain ceiling ready for a central chandelier. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern master bedroom interior in a vertical 9:16 composition with an elegant bed and a plain ceiling centered for a luxury hanging chandelier. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    "Generate a premium modern open-concept great room in a vertical 9:16 composition with expansive windows and a clean ceiling focal point for a hanging chandelier. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
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

def resolve_krea_moodboard_id(category_code: str, fallback: str = "") -> str:
    """Resolve category or table-specific Krea moodboard ID from environment."""
    category = category_code.lower()
    candidate_keys = []
    if "pendant" in category:
        candidate_keys = [
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ]
    elif "floor" in category:
        candidate_keys = [
            "KREA_MOODBOARD_ID_FLOOR_LAMP_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ]
    elif "table" in category:
        candidate_keys = [
            "KREA_MOODBOARD_ID_TABLE_LAMP_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ]
    elif "cluster" in category:
        candidate_keys = [
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ]
    elif "ceiling" in category:
        candidate_keys = [
            "KREA_MOODBOARD_ID_CEILING_MOUNTED_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_WALL_SCONCE",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ]
    elif "chand" in category:
        candidate_keys = [
            "KREA_MOODBOARD_ID_CHANDELIER_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ]
    for key in candidate_keys:
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return fallback


def load_tips_edu_json_prompts(
    workspace: Path,
    category_code: str,
    fallback_prompts: tuple[str, ...] | list[str],
) -> list[str]:
    """Load customized interior prompts from JSON Prompts/Tips and Edu Story/interior_prompts.json if available."""
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
        qwen: QwenClient | None = None,
        fal: FalClient | None = None,
        logger: JsonlRunLogger | None = None,
    ) -> None:
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
        self.qwen = qwen or QwenClient(settings.qwen_api_key, settings.qwen_base_url)
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
        self.logger.event("preflight_completed", table_id=self.definition.table_id)

    def run(self, phase: int | str = "all") -> None:
        self.preflight()
        if phase == "all":
            record, start_phase = self._next_incomplete()
            if record is None:
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
        if status.casefold() in ("error", "skip", "skipped", "ignore", "disabled") or "error" in status.casefold():
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
            if not self._has_attachment(fields, self.definition.music_field or "Music Generated"):
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
        for record in self._records():
            if self._phase_for_record(record) == phase:
                return record
        return None

    def _update_status(self, record_id: str, status: str) -> None:
        self.airtable.update_records([(record_id, {"Status": status})])
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

        products = self.akeneo.fetch_products(
            {
                "categories": [
                    {"operator": "IN", "value": [akeneo_category_code(self.definition.category_code)]}
                ],
                "Style2": [{"operator": "IN", "value": [self.settings.style_code]}],
            }
        )
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

        item = random.choice(candidates)
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
        available_prompts = load_tips_edu_json_prompts(
            self.settings.workspace,
            self.definition.category_code,
            self.definition.interior_prompts or (self.definition.interior_prompt,),
        )
        prompt = random.choice(available_prompts)
        moodboard_id = resolve_krea_moodboard_id(
            self.definition.category_code,
            self.definition.moodboard_id,
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

        if "floor" in self.definition.category_code:
            instruction = (
                f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
                f"and Image 2 as the product photo for '{item_name}'.\n"
                f"Generate a detailed, clean, photorealistic image blending prompt that will place and stand this {item_name} floor lamp naturally on the floor in this room interior.\n"
                f"CRITICAL ISOLATION & FLOOR LAMP PLACEMENT RULES:\n"
                f"1. The floor lamp shown in Image 2 MUST BE THE ONLY STANDING FLOOR LAMP in the entire final blended scene.\n"
                f"2. If Image 1 contains ANY pre-existing floor lamps, secondary lamps, or competing light fixtures, "
                f"EXPLICITLY INSTRUCT TO REMOVE AND REPLACE THEM so that ONLY the exact {item_name} floor lamp from Image 2 stands in the room.\n"
                f"3. Strictly place the floor lamp standing on the floor in full view (e.g. beside the armchair, at the end of the sofa, in the reading corner, beside the lounge chair, in the bedroom corner, or beside the console table).\n"
                f"4. Ensure natural standing height, realistic sturdy base resting flat on the floor/rug, natural contact shadows on the floor and adjacent walls, realistic warm illumination and soft ambient glow, and authentic product materials.\n"
                f"5. Strictly exclude duplicate lamps, extra competing lighting fixtures, or unwanted clutter.\n\n"
                f"Output ONLY the prompt text, with no preamble or markdown quotes."
            )
        elif "table" in self.definition.category_code:
            instruction = (
                f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
                f"and Image 2 as the product photo for '{item_name}'.\n"
                f"Generate a detailed, clean, photorealistic image blending prompt that will place this {item_name} table lamp on a tabletop, nightstand, or console in this room interior.\n"
                f"CRITICAL ISOLATION & TABLE LAMP PLACEMENT RULES:\n"
                f"1. The table lamp shown in Image 2 MUST BE THE ONLY TABLE LAMP in the entire final blended scene.\n"
                f"2. If Image 1 contains ANY pre-existing table lamps or competing light fixtures, "
                f"EXPLICITLY INSTRUCT TO REMOVE AND REPLACE THEM so that ONLY the exact table lamp from Image 2 rests on the table.\n"
                f"3. Ensure realistic contact shadows on the tabletop, authentic lamp materials, natural scale, and soft warm ambient lighting.\n\n"
                f"Output ONLY the prompt text, with no preamble or markdown quotes."
            )
        elif "wall" in self.definition.category_code:
            instruction = (
                f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
                f"and Image 2 as the product photo for '{item_name}'.\n"
                f"Generate a detailed, clean, photorealistic image blending prompt that will mount this {item_name} wall light securely on the wall in this room interior.\n"
                f"CRITICAL ISOLATION & WALL MOUNT RULES:\n"
                f"1. The wall light shown in Image 2 MUST BE THE ONLY WALL LIGHT in the entire final blended scene.\n"
                f"2. If Image 1 contains ANY pre-existing wall sconces or competing light fixtures, "
                f"EXPLICITLY INSTRUCT TO REMOVE AND REPLACE THEM so that ONLY the exact wall light from Image 2 is mounted on the wall.\n"
                f"3. Ensure natural mounting height, realistic wall junction, authentic materials, and soft warm ambient illumination casting on the wall.\n\n"
                f"Output ONLY the prompt text, with no preamble or markdown quotes."
            )
        elif "ceiling" in self.definition.category_code:
            instruction = (
                f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
                f"and Image 2 as the product photo for '{item_name}'.\n"
                f"Generate a detailed, clean, photorealistic image blending prompt that will mount this {item_name} ceiling light directly onto the ceiling in this room interior.\n"
                f"CRITICAL ISOLATION & CEILING MOUNT RULES:\n"
                f"1. The ceiling light shown in Image 2 MUST BE THE ONLY CEILING LIGHTING FIXTURE in the entire final blended scene.\n"
                f"2. If Image 1 contains ANY pre-existing lighting fixtures, ceiling lamps, or secondary light fixtures, "
                f"EXPLICITLY INSTRUCT TO REMOVE AND REPLACE THEM so that ONLY the exact ceiling-mounted light from Image 2 is installed on the ceiling.\n"
                f"3. Ensure seamless flush/semi-flush ceiling mounting, realistic ceiling canopy/junction, authentic materials, and soft warm ambient downward illumination.\n\n"
                f"Output ONLY the prompt text, with no preamble or markdown quotes."
            )
        else:
            if "cluster" in self.definition.category_code:
                fixture_type = "cluster chandelier"
            elif "pendant" in self.definition.category_code:
                fixture_type = "pendant light"
            else:
                fixture_type = "chandelier"
            instruction = (
                f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
                f"and Image 2 as the product photo for '{item_name}'.\n"
                f"Generate a detailed, clean, photorealistic image blending prompt that will mount and hang this {item_name} {fixture_type} from the ceiling in this room interior.\n"
                f"CRITICAL ISOLATION & CEILING MOUNT RULES:\n"
                f"1. The {fixture_type} shown in Image 2 MUST BE THE ONLY CEILING LIGHTING FIXTURE in the entire final blended scene.\n"
                f"2. If Image 1 contains ANY pre-existing lighting fixtures, ceiling lamps, or secondary light fixtures, "
                f"EXPLICITLY INSTRUCT TO REMOVE AND REPLACE THEM so that ONLY the exact {fixture_type} from Image 2 hangs from the ceiling.\n"
                f"3. Strictly exclude unnecessary, extra, competing furniture items, duplicate fixtures, or clutter.\n"
                f"4. Ensure natural hanging height, realistic chain/rod/cord mounting, ceiling junction canopy, realistic warm illumination, "
                f"soft downward & ambient glow, natural contact shadows on surrounding walls/floors, and authentic materials.\n\n"
                f"Output ONLY the prompt text, with no preamble or markdown quotes."
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
        if self.is_day_night:
            source = self._artifact_path(record_id, "day_and_night_blended.jpg")
            if not source.is_file():
                raise AssetValidationError("Phase 4 blend artifact is missing; rerun Phase 4")
            self._validate_9_16(source, "Day and Night blend")
            self.airtable.upload_attachment(record_id, self.definition.blended_field, source, source.name)
            return

        fields = self._record(record_id).get("fields", {})
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
        source_url = self._attachment_url(fields, self.definition.blended_field)
        local_source = self._artifact_path(record_id, "fal_day_and_night_source.jpg")
        print(f"  [1/4] Downloading blended source image from Airtable...", flush=True)
        self._download(source_url, local_source)
        self._validate_9_16(local_source, "Day and Night blend")
        print(f"  [2/4] Uploading source image to Fal AI CDN...", flush=True)
        fal_source_url = self.fal.upload_file(local_source)
        print(f"  [3/4] Requesting Kling 15s timelapse video from Fal AI ({FAL_KLING_MODEL})...", flush=True)
        video_url = self.fal.generate_kling_video(
            DAY_NIGHT_TIMELAPSE_PROMPT,
            fal_source_url,
            duration=15,
            model=FAL_KLING_MODEL,
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
            model=FAL_KLING_MODEL,
            duration_seconds=15,
            attachment_filename=video_path.name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": "Phase 6: Fal AI Kling Video Timelapse",
                "api_provider": "Fal AI (Kling Video v3 Pro)",
                "api_model": FAL_KLING_MODEL,
                "raw_request": {
                    "model": FAL_KLING_MODEL,
                    "prompt": DAY_NIGHT_TIMELAPSE_PROMPT,
                    "airtable_source_url": source_url,
                    "fal_source_url": fal_source_url,
                    "duration_seconds": 15,
                },
                "raw_response": {
                    "video_url": video_url,
                    "local_video_path": str(video_path),
                    "target_field": target_video_field,
                },
            },
            self.audit_log_dir / f"{self.definition.key}_fal_kling_logs.json",
        )

    def _phase_7(self, record_id: str) -> None:
        if not self.is_day_night:
            raise AutomationError("Tips & Edu Story has no phase 7")
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

        print(f"  [2/3] Generating 18s background jazz music via Fal AI Stable Audio 3 (Prompt: '{jazz_prompt}')...", flush=True)
        audio_url = self.fal.generate_stable_audio_music(
            jazz_prompt,
            duration=DAY_NIGHT_MUSIC_DURATION,
            model=FAL_STABLE_AUDIO_MODEL,
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
            model=FAL_STABLE_AUDIO_MODEL,
            duration_seconds=DAY_NIGHT_MUSIC_DURATION,
            music_prompt=jazz_prompt,
            attachment_filename=music_path.name,
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get("SKU") or ""),
                "item_label": fields.get("Item Name") or fields.get("SKU") or record_id,
                "phase": "Phase 7: Fal AI Stable Audio 3 Jazz Music (Claude Sonnet 5 Prompt)",
                "api_provider": "Fal AI (Stable Audio 3 + Claude Sonnet 5)",
                "api_model": f"{FAL_STABLE_AUDIO_MODEL} + {FAL_VISION_MODEL}",
                "raw_request": {
                    "vision_model": FAL_VISION_MODEL,
                    "audio_model": FAL_STABLE_AUDIO_MODEL,
                    "prompt": jazz_prompt,
                    "duration_seconds": DAY_NIGHT_MUSIC_DURATION,
                },
                "raw_response": {
                    "audio_url": audio_url,
                    "local_audio_path": str(music_path),
                    "target_field": target_music_field,
                },
            },
            self.audit_log_dir / f"{self.definition.key}_stable_audio_logs.json",
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

        # 2. Download Music Generated
        music_field = self.definition.music_field or "Music Generated"
        music_url = self._attachment_url(fields, music_field)
        local_music = self._artifact_path(record_id, "day_and_night_music.mp3")
        print(f"  [2/4] Downloading '{music_field}' from Airtable...", flush=True)
        self._download(music_url, local_music)

        # 3. Locate / Download Outro image
        outro_field = self.definition.outro_field or "Outro"
        local_outro = self._artifact_path(record_id, "outro.jpg")
        if self._has_attachment(fields, outro_field):
            print(f"  [3/4] Downloading '{outro_field}' attachment from record...", flush=True)
            outro_url = self._attachment_url(fields, outro_field)
            self._download(outro_url, local_outro)
        else:
            workspace_outro = self.settings.workspace / "Outro for All Reels/Outro.jpg"
            if workspace_outro.is_file():
                print(f"  [3/4] Using workspace Outro image: {workspace_outro}...", flush=True)
                import shutil
                local_outro.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(workspace_outro, local_outro)
            else:
                local_outro = None

        # 4. Merge Video + Outro + Audio
        print(f"  [4/4] Merging 15s Kling video + 3s Outro + Jazz Music into 18s vertical reel...", flush=True)
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
                    "music_field": music_field,
                    "outro_field": outro_field,
                },
                "raw_response": {
                    "local_final_video_path": str(final_video_path),
                    "target_field": self.definition.final_field,
                },
            },
            self.audit_log_dir / f"{self.definition.key}_final_reel_logs.json",
        )
