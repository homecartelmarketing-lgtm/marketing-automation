"""CTA Story AI Generation & Blending Pipeline.

Runs the complete 6-phase AI pipeline for CTA Story on Airtable:
1. Akeneo Product Scraping -> 'Furniture Item' + 'CTA Blended Image Watermark Layout' + 'Logo', Status -> 'Standby'
2. Krea AI Interior Photo Generation (9:16) -> 'CTA Interior', Status -> 'CTA Interior Generated'
3. Claude Sonnet 5 Prompt Analysis (via Fal AI) -> 'Blending Prompt', Status -> 'Blending Prompt Generated'
4. Fal AI Nano Banana Pro Blending (9:16) -> 'CTA Blended Image', Status -> 'CTA Blended Image Generated'
5. Claude Sonnet 5 Headline Analysis (via Fal AI) -> 'Word Generated'
6. Python Local CTA Layout & Logo Stamping (9:16) -> 'CTA Converted Image' / 'Watermark Added', Status -> 'Complete'

Usage::

    python generate_cta_story_pipeline.py
    python generate_cta_story_pipeline.py --max-items 5
    python generate_cta_story_pipeline.py --category chandelier_cta_story
    python generate_cta_story_pipeline.py --mode conversion --table-id tblYHdVq14FjMWg5o
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image

from content_automation.airtable_client import fetch_multiple_tables_status_breakdown
from content_automation.akeneo_client import split_item_name
from content_automation.config import TABLES, load_settings
from content_automation.cta_conversion import run_cta_conversion
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.item_tagger import TARGET_BLENDED_FIELD, tag_blended_image
from content_automation.prompts import build_vision_blending_instruction
from content_automation.kie_client import KieClient
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.overlay import (
    CTA_STORY_TEXT_BOX,
    HOMECARTEL_STORY_LOGO_BOX,
    overlay_cta_story_layout,
    stamp_cta_story_watermark_and_logo,
)
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    moodboard_id_for_category,
)
from standalone_scrape_akeneo import run_category_scrape

CTA_STORY_TABLES: dict[str, dict[str, str]] = {
    "tblYHdVq14FjMWg5o": {
        "category_code": "chandelier_cta_story",
        "label": "CTA Story Chandelier",
        "default_moodboard_id": (
            os.getenv("KREA_MOODBOARD_ID_CHANDELIER_CTA", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
            or "de6ad512-870d-4ab7-a48c-3f3ca85faf24"
        ),
        "default_prompt": (
            os.getenv("CTA_PROMPT_CHANDELIER", "").strip()
            or os.getenv("PROMPT_CHANDELIER", "").strip()
            or "Generate me a modern living room"
        ),
    },
    "tblfl7fqFZa2vUieB": {
        "category_code": "pendant_lights_cta_story",
        "label": "CTA Story Pendant Light",
        "default_moodboard_id": (
            os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS_CTA", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
            or "0844ad92-c34a-4dc8-9d70-d09498dc098c"
        ),
        "default_prompt": (
            os.getenv("CTA_PROMPT_PENDANT_LIGHTS", "").strip()
            or os.getenv("PROMPT_PENDANT_LIGHTS", "").strip()
            or "Generate me a modern dining room"
        ),
    },
    "tblSpGJLO3faYfIDY": {
        "category_code": "cluster_chandelier_cta_story",
        "label": "CTA Story Cluster Chandelier",
        "default_moodboard_id": (
            os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_CTA", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER", "").strip()
            or "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
        ),
        "default_prompt": (
            os.getenv("CTA_PROMPT_CLUSTER_CHANDELIER", "").strip()
            or os.getenv("PROMPT_CLUSTER_CHANDELIER", "").strip()
            or (
                "Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, "
                "clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait"
            )
        ),
    },
    "tblKJeCCp4zQ6g7Em": {
        "category_code": "table_lamps_cta_story",
        "label": "CTA Story Table Lamp",
        "default_moodboard_id": (
            os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS_CTA", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS_DAY_NIGHT_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS", "").strip()
            or "257569e1-7be8-4412-a90f-acbc347e4646"
        ),
        "default_prompt": (
            os.getenv("CTA_PROMPT_TABLE_LAMPS", "").strip()
            or os.getenv("PROMPT_TABLE_LAMPS", "").strip()
            or "Generate me a modern bedroom with a table lamp side by side"
        ),
    },
    "tblPKSYyjgbgMypE2": {
        "category_code": "floor_lamp_cta_story",
        "label": "CTA Story Floor Lamp",
        "default_moodboard_id": (
            os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMP_CTA", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
            or "c4c15a18-a92d-4465-924f-c85cfe1958bc"
        ),
        "default_prompt": (
            os.getenv("CTA_PROMPT_FLOOR_LAMPS", "").strip()
            or os.getenv("PROMPT_FLOOR_LAMPS", "").strip()
            or (
                "Modern living room interior, stylish lounge chair, warm ambient lighting, "
                "spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait"
            )
        ),
    },
}


def get_cta_tables() -> dict[str, dict[str, str]]:
    """Return dynamically refreshed CTA tables config from .env."""
    return {
        (os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_CTA", "").strip() or "tblYHdVq14FjMWg5o"): {
            "category_code": "chandelier_cta_story",
            "label": "CTA Story Chandelier",
            "default_moodboard_id": (
                os.getenv("KREA_MOODBOARD_ID_CHANDELIER_CTA", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
                or "de6ad512-870d-4ab7-a48c-3f3ca85faf24"
            ),
            "default_prompt": (
                os.getenv("CTA_PROMPT_CHANDELIER", "").strip()
                or os.getenv("PROMPT_CHANDELIER", "").strip()
                or "Generate me a modern living room"
            ),
        },
        (os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_CTA", "").strip() or "tblfl7fqFZa2vUieB"): {
            "category_code": "pendant_lights_cta_story",
            "label": "CTA Story Pendant Light",
            "default_moodboard_id": (
                os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS_CTA", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
                or "0844ad92-c34a-4dc8-9d70-d09498dc098c"
            ),
            "default_prompt": (
                os.getenv("CTA_PROMPT_PENDANT_LIGHTS", "").strip()
                or os.getenv("PROMPT_PENDANT_LIGHTS", "").strip()
                or "Generate me a modern dining room"
            ),
        },
        (os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_CTA", "").strip() or "tblSpGJLO3faYfIDY"): {
            "category_code": "cluster_chandelier_cta_story",
            "label": "CTA Story Cluster Chandelier",
            "default_moodboard_id": (
                os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_CTA", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER", "").strip()
                or "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
            ),
            "default_prompt": (
                os.getenv("CTA_PROMPT_CLUSTER_CHANDELIER", "").strip()
                or os.getenv("PROMPT_CLUSTER_CHANDELIER", "").strip()
                or (
                    "Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, "
                    "clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait"
                )
            ),
        },
        (os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMPS_CTA", "").strip() or "tblKJeCCp4zQ6g7Em"): {
            "category_code": "table_lamps_cta_story",
            "label": "CTA Story Table Lamp",
            "default_moodboard_id": (
                os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS_CTA", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS_DAY_NIGHT_STORY", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS", "").strip()
                or "257569e1-7be8-4412-a90f-acbc347e4646"
            ),
            "default_prompt": (
                os.getenv("CTA_PROMPT_TABLE_LAMPS", "").strip()
                or os.getenv("PROMPT_TABLE_LAMPS", "").strip()
                or "Generate me a modern bedroom with a table lamp side by side"
            ),
        },
        (os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_CTA", "").strip() or "tblPKSYyjgbgMypE2"): {
            "category_code": "floor_lamp_cta_story",
            "label": "CTA Story Floor Lamp",
            "default_moodboard_id": (
                os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMP_CTA", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
                or "c4c15a18-a92d-4465-924f-c85cfe1958bc"
            ),
            "default_prompt": (
                os.getenv("CTA_PROMPT_FLOOR_LAMPS", "").strip()
                or os.getenv("PROMPT_FLOOR_LAMPS", "").strip()
                or (
                    "Modern living room interior, stylish lounge chair, warm ambient lighting, "
                    "spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait"
                )
            ),
        },
    }


def find_cta_table_by_category(category_code: str) -> tuple[str, dict[str, str]] | None:
    """Find the Table ID and table configuration for a given category code."""
    tables = get_cta_tables()
    for tid, info in tables.items():
        if info.get("category_code") == category_code:
            return tid, info
    if category_code == "cta_story":
        for tid, info in tables.items():
            if info.get("category_code") == "chandelier_cta_story":
                return tid, info
    return None


def resolve_cta_table_and_config(
    target_table_id: str | None = None,
    category_code: str | None = None,
) -> tuple[str, str, dict[str, str]]:
    """Resolve (table_id, category_code, tbl_config) dynamically without Chandelier lock."""
    tables = get_cta_tables()

    # 1. If explicit recognized Table ID was provided, use it
    if target_table_id and target_table_id in tables:
        cfg = tables[target_table_id]
        cat = category_code or cfg.get("category_code", DEFAULT_CATEGORY)
        return target_table_id, cat, cfg

    # 2. If category_code was provided, find its dedicated Table ID
    if category_code:
        found = find_cta_table_by_category(category_code)
        if found:
            tid, cfg = found
            return tid, category_code, cfg

    # 3. If target_table_id is a custom/unrecognized ID
    if target_table_id:
        return target_table_id, (category_code or DEFAULT_CATEGORY), {}

    # 4. Default fallback to Chandelier
    default_tid = (
        os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_CTA", "").strip()
        or os.getenv("AIRTABLE_TABLE_ID_CTA_STORY", "").strip()
        or DEFAULT_TABLE_ID
    )
    default_cfg = tables.get(default_tid, {})
    return default_tid, default_cfg.get("category_code", DEFAULT_CATEGORY), default_cfg


DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_CTA", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_CTA_STORY", "").strip()
    or "tblYHdVq14FjMWg5o"
)
DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_CHANDELIER_CTA", "").strip()
    or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
    or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
    or "de6ad512-870d-4ab7-a48c-3f3ca85faf24"
)
DEFAULT_PROMPT = "Generate me a modern living room"

CTA_INTERIOR_PROMPTS: dict[str, str] = {
    "table_lamps_cta_story": "Generate me a modern bedroom with a table lamp side by side",
    "chandelier_cta_story": "Generate me a modern living room",
    "cta_story": "Generate me a modern living room",
    "cluster_chandelier_cta_story": (
        "Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, "
        "clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait"
    ),
    "pendant_lights_cta_story": "Generate me a modern dining room",
    "floor_lamp_cta_story": (
        "Modern living room interior, stylish lounge chair, warm ambient lighting, "
        "spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait"
    ),
    "wall_lights_cta_story": (
        "Modern living room or bedroom hallway, clean textured accent wall, soft ambient daylight, "
        "empty wall space ready for wall sconce lighting fixture, photorealistic 8k vertical portrait"
    ),
}


def prompt_for_category(category_code: str, custom_prompt: str | None = None) -> str:
    """Return the designated interior prompt for a category or custom override."""
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()
    for info in get_cta_tables().values():
        if info.get("category_code") == category_code and info.get("default_prompt"):
            return info["default_prompt"]
    return CTA_INTERIOR_PROMPTS.get(category_code, DEFAULT_PROMPT)


DEFAULT_CATEGORY = "chandelier_cta_story"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "CTA Interior Generated"
STATUS_GENERATING_PROMPT = "Blending Prompt Generated"
STATUS_BLENDED_IMAGE = "CTA Blended Image Generated"
STATUS_ADDED_WATERMARK = "Watermark Added Layout"
STATUS_COMPLETE = "Complete"

INTERIOR_FIELD = "CTA Interior"
INTERIOR_FIELD_FALLBACKS = ["CTA Interior", "CTA Interior Image", "Interior", "Interior Image"]
INTERIOR_ASPECT_RATIO = "9:16"

PROMPT_FIELD = "Blending Prompt"
PROMPT_FIELD_FALLBACKS = [
    "Blending Prompt",
    "CTA Prompt Blending",
    "Prompt",
    "Blend Prompt",
    "Blending Prompt Generated",
]

BLENDED_FIELD = "CTA Blended Image"
BLENDED_FIELD_FALLBACKS = [
    "CTA Blended Image",
    "CTA Blended",
    "Blended Image",
    "Blended Photo",
]
BLENDED_ASPECT_RATIO = "9:16"

LAYOUT_FIELD = "CTA Blended Image Watermark Layout"
LAYOUT_FIELD_FALLBACKS = [
    "CTA Blended Image Watermark Layout",
    "CTA Layout",
    "Watermark Layout",
    "Layout",
    "CTA Overlay Layout",
]

LOGO_FIELD = "Logo"
LOGO_FIELD_FALLBACKS = [
    "Logo",
    "HomeCartel Logo",
    "Brand Logo",
    "Watermark Logo",
]

WATERMARK_FIELD = "Watermark Added"
WATERMARK_FIELD_FALLBACKS = [
    "Watermark Added",
    "Watermark Added Layout",
    "Watermarked Image",
    "Watermark Added Image",
    "CTA Converted Image",
    "CTA Converted Blended",
]

CONVERTED_FIELD_FALLBACKS = [
    "CTA Converted Image",
    "CTA Converted Blended",
    "Watermark Added",
    "Watermark Added Layout",
    "Watermarked Image",
]

WORD_GENERATED_FIELD = "Word Generated"
WORD_GENERATED_FALLBACKS = [
    "Word Generated",
    "Word Generate",
    "Generated Words",
    "Words Generated",
    "CTA Headline",
    "Headline",
]

FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_BLENDING_MODEL = os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"


def base_has_key(client: Any) -> bool:
    return bool(getattr(client, "api_key", None))


def get_first_field_value(fields: dict[str, Any], field_names: list[str]) -> Any:
    """Return the first populated value among candidate field names."""
    for name in field_names:
        if name in fields and fields[name]:
            return fields[name]
    return None


def get_first_field_name(fields: dict[str, Any], field_names: list[str]) -> str:
    """Return the first matching field name that exists in fields dictionary."""
    for name in field_names:
        if name in fields:
            return name
    return field_names[0]


def extract_attachment_url(attachments: Any) -> str:
    """Extract accessible HTTP URL from Airtable attachment field."""
    if not attachments:
        return ""
    if isinstance(attachments, list) and len(attachments) > 0:
        first = attachments[0]
        if isinstance(first, dict):
            return str(first.get("url") or "").strip()
    if isinstance(attachments, dict):
        return str(attachments.get("url") or "").strip()
    return ""


def make_layout_transparent(img: Image.Image, threshold: int = 35) -> Image.Image:
    """Convert layout overlay image to RGBA and turn solid background transparent."""
    img = img.convert("RGBA")
    extrema = img.getextrema()
    if extrema[3][0] < 255:
        return img

    w, h = img.size
    corners = [
        img.getpixel((0, 0)),
        img.getpixel((w - 1, 0)),
        img.getpixel((0, h - 1)),
        img.getpixel((w - 1, h - 1)),
    ]
    avg_brightness = sum((c[0] + c[1] + c[2]) / 3.0 for c in corners) / 4.0
    is_dark_bg = avg_brightness < 128

    rgb_data = img.convert("RGB").tobytes()
    alpha_data = bytearray(w * h)

    for i in range(w * h):
        r_val = rgb_data[i * 3]
        g_val = rgb_data[i * 3 + 1]
        b_val = rgb_data[i * 3 + 2]
        if is_dark_bg:
            if not (r_val <= threshold and g_val <= threshold and b_val <= threshold):
                alpha_data[i] = 255
        else:
            if not (r_val >= (255 - threshold) and g_val >= (255 - threshold) and b_val >= (255 - threshold)):
                alpha_data[i] = 255

    new_alpha = Image.frombytes("L", (w, h), bytes(alpha_data))
    img.putalpha(new_alpha)
    return img


def overlay_watermark_layout(
    blended_path: str | Path,
    layout_path: str | Path,
    output_path: str | Path,
    threshold: int = 35,
) -> Path:
    """Overlay transparent layout photo on top of blended base photo, saving result."""
    base_img = Image.open(blended_path).convert("RGBA")
    layout_img = Image.open(layout_path)

    transparent_layout = make_layout_transparent(layout_img, threshold=threshold)
    if transparent_layout.size != base_img.size:
        transparent_layout = transparent_layout.resize(base_img.size, Image.Resampling.LANCZOS)

    composited = Image.alpha_composite(base_img, transparent_layout).convert("RGB")
    composited.save(output_path, "JPEG", quality=95)
    return Path(output_path)


def find_cta_layout_path() -> Path | None:
    """Locate local cta_layout.jpg file from project tree."""
    candidates = [
        Path(__file__).parent / "JSON Prompts" / "CTA" / "cta_layout.jpg",
        Path(__file__).parent / "JSON Prompts" / "cta_layout.jpg",
        Path(__file__).parent / "cta_layout.jpg",
        Path(__file__).parent / "assets" / "cta_layout.jpg",
        Path(__file__).parent / "assets" / "CTA" / "cta_layout.jpg",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def find_homecartel_logo_path() -> Path | None:
    """Locate local HomeCartel logo asset from project tree."""
    candidates = [
        Path(__file__).parent / "assets" / "homecartel_logo.png",
        Path(__file__).parent / "assets" / "logo.png",
        Path(__file__).parent / "logo.png",
        Path(__file__).parent / "homecartel_logo.png",
        Path(__file__).parent / "JSON Prompts" / "CTA" / "homecartel_logo.png",
        Path(__file__).parent / "JSON Prompts" / "homecartel_logo.png",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def get_existing_logo_attachment_from_table(airtable: ScrapeAirtableClient) -> dict[str, Any] | None:
    """Find an existing populated Logo attachment from any record in the table."""
    try:
        records = airtable.list_records(LOGO_FIELD_FALLBACKS)
        for record in records:
            logo_val = get_first_field_value(record.get("fields", {}), LOGO_FIELD_FALLBACKS)
            if logo_val:
                if isinstance(logo_val, list) and len(logo_val) > 0 and isinstance(logo_val[0], dict):
                    return logo_val[0]
                elif isinstance(logo_val, dict):
                    return logo_val
    except Exception as e:
        print(f"[DEBUG] Table logo scan skipped: {e}")
    return None


def ensure_cta_layout_uploaded(airtable: ScrapeAirtableClient, record_id: str, fields: dict[str, Any]) -> bool:
    """Ensure CTA layout asset is populated on the record."""
    target_field = (
        (getattr(airtable, "find_field_name", lambda n: None)("CTA Blended Image Watermark Layout") if hasattr(airtable, "find_field_name") else None)
        or get_first_field_name(fields, LAYOUT_FIELD_FALLBACKS)
        or "CTA Blended Image Watermark Layout"
    )
    if get_first_field_value(fields, LAYOUT_FIELD_FALLBACKS):
        return True

    layout_path = find_cta_layout_path()
    if not layout_path:
        print("[WARN] Local 'cta_layout.jpg' not found in project tree; skipping layout attachment upload.")
        return False

    try:
        airtable.upload_attachment(record_id, target_field, layout_path, "cta_layout.jpg")
        print(f"[OK] Uploaded layout 'cta_layout.jpg' to '{target_field}' on record {record_id}")
        return True
    except Exception as error:
        print(f"[ERROR] Failed uploading layout to record {record_id}: {error}")
        return False


def ensure_cta_logo_uploaded(airtable: ScrapeAirtableClient, record_id: str, fields: dict[str, Any]) -> bool:
    """Ensure HomeCartel brand logo asset is populated on the record."""
    target_field = (
        (getattr(airtable, "find_field_name", lambda n: None)("Logo") if hasattr(airtable, "find_field_name") else None)
        or get_first_field_name(fields, LOGO_FIELD_FALLBACKS)
        or "Logo"
    )
    if get_first_field_value(fields, LOGO_FIELD_FALLBACKS):
        return True

    logo_path = find_homecartel_logo_path()
    if logo_path and logo_path.exists():
        try:
            airtable.upload_attachment(record_id, target_field, logo_path, "homecartel_logo.png")
            print(f"[OK] Uploaded logo 'homecartel_logo.png' to '{target_field}' on record {record_id}")
            return True
        except Exception as error:
            print(f"[WARN] Local logo upload failed for record {record_id}: {error}")

    table_logo = get_existing_logo_attachment_from_table(airtable)
    if table_logo and table_logo.get("url"):
        import requests
        try:
            resp = requests.get(table_logo["url"], stream=True, timeout=30)
            if resp.status_code == 200:
                dl = download_to_temp_file(resp, prefix="logo_copy_", suffix=".png", context="Table logo copy")
                try:
                    airtable.upload_attachment(record_id, target_field, dl.path, "homecartel_logo.png")
                    print(f"[OK] Copied existing logo from Airtable to '{target_field}' on record {record_id}")
                    return True
                finally:
                    dl.cleanup()
        except Exception as error:
            print(f"[WARN] Failed copying logo from other Airtable records: {error}")

    return False


def safe_update_status(airtable: ScrapeAirtableClient, record_id: str, status_value: str) -> None:
    payload = {STATUS_FIELD: status_value}
    if status_value == STATUS_COMPLETE:
        try:
            from content_automation.airtable_client import current_pht_timestamp
            payload["Date and Time Generated"] = current_pht_timestamp()
        except Exception:
            pass
    try:
        airtable.update_records([(record_id, payload)])
    except Exception:
        try:
            airtable.update_records([(record_id, {STATUS_FIELD: status_value})])
        except Exception:
            pass



def backfill_missing_cta_assets(airtable: ScrapeAirtableClient) -> None:
    records = airtable.list_records(LAYOUT_FIELD_FALLBACKS + LOGO_FIELD_FALLBACKS + [FIELD_NAME, STATUS_FIELD])
    for rec in records:
        f = rec.get("fields", {})
        ensure_cta_layout_uploaded(airtable, rec["id"], f)
        ensure_cta_logo_uploaded(airtable, rec["id"], f)


def sort_records_by_id(records: list[dict]) -> list[dict]:
    def sort_key(record: dict):
        fields = record.get("fields", {})
        for key in ("ID", "Auto Number", "No", "Number", "Id", "id", "Row"):
            val = fields.get(key)
            if val is not None:
                try:
                    return (0, int(val))
                except (ValueError, TypeError):
                    return (0, str(val))
        return (1, record.get("createdTime", ""))

    return sorted(records, key=sort_key)


def generate_krea_interiors(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_PROMPT,
    aspect_ratio: str = INTERIOR_ASPECT_RATIO,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate Krea AI room interior photo into 'CTA Interior'."""
    airtable.ensure_fields({INTERIOR_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(INTERIOR_FIELD_FALLBACKS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"])
    if not records:
        print("[OK] No records found in Airtable to populate interior photos.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    unpopulated = [
        record
        for record in records
        if not get_first_field_value(record.get("fields", {}), INTERIOR_FIELD_FALLBACKS)
    ]
    if not unpopulated:
        print(f"[OK] No records found missing interior photo field ('{INTERIOR_FIELD}').")
        return True

    if limit_records is not None:
        unpopulated = unpopulated[:limit_records]

    print(
        f"[INFO] Generating '{INTERIOR_FIELD}' for {len(unpopulated)} record(s) "
        f"using Krea AI (Moodboard ID: {moodboard_id}, Aspect Ratio: {aspect_ratio})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(unpopulated, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
        print(
            f"[INFO] [{position}/{len(unpopulated)}] Generating photo for "
            f"record {record_id} ({item_label})..."
        )

        downloaded = None
        try:
            image_url = krea.generate(
                prompt,
                aspect_ratio=aspect_ratio,
                moodboard_id=moodboard_id,
            )
            downloaded = krea.download_image(image_url)
            filename = f"cta_interior_{record_id}.jpg"
            target_field = get_first_field_name(fields, INTERIOR_FIELD_FALLBACKS)
            airtable.upload_attachment(record_id, target_field, downloaded, filename)
            safe_update_status(airtable, record_id, STATUS_INTERIOR_GENERATED)
            print(
                f"[OK] Attached Krea image to '{target_field}' and updated "
                f"{STATUS_FIELD} on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(
                f"[ERROR] Failed generating interior photo for record {record_id}: {error}"
            )
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(f"[INFO] Krea CTA interior generation complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def generate_claude_blending_prompts(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    vision_model: str = FAL_VISION_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate detailed blending prompt using Claude Sonnet 5 via Fal AI into 'Blending Prompt'."""
    airtable.ensure_fields({PROMPT_FIELD: "multilineText"})
    records = airtable.list_records(
        INTERIOR_FIELD_FALLBACKS + PROMPT_FIELD_FALLBACKS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to generate prompts.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        interior_attachments = get_first_field_value(fields, INTERIOR_FIELD_FALLBACKS)
        prompt_val = get_first_field_value(fields, PROMPT_FIELD_FALLBACKS)
        if not interior_attachments:
            continue
        if prompt_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Claude Sonnet 5 prompt generation (CTA interior missing or blending prompt already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{PROMPT_FIELD}' for {len(eligible)} record(s) "
        f"using Claude Sonnet 5 via Fal AI ({vision_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Lighting Fixture").strip()
        item_label = f"{record_id} ({item_name})"

        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELD_FALLBACKS))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))

        if not interior_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible CTA Interior attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing photos & generating CTA blending prompt for "
            f"record {record_id} ({item_label}) with Claude Sonnet 5..."
        )

        image_urls = [url for url in [interior_url, furniture_url] if url]
        instruction = build_vision_blending_instruction(
            interior_label="Room Interior ('CTA Interior')",
            item_name=item_name,
            aspect_ratio="9:16",
        )

        try:
            generated_prompt = fal.generate_vision_prompt(
                image_urls=image_urls,
                prompt=instruction,
                model=vision_model,
            )

            target_field = get_first_field_name(fields, PROMPT_FIELD_FALLBACKS)
            airtable.update_records([(record_id, {target_field: generated_prompt.strip()})])
            safe_update_status(airtable, record_id, STATUS_GENERATING_PROMPT)
            print(
                f"[OK] Generated prompt ({len(generated_prompt.strip())} chars) for "
                f"record {record_id} and updated '{target_field}'"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating Claude prompt for record {record_id}: {error}")
            failed += 1

    print(f"[INFO] Claude Sonnet 5 prompt generation complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def generate_cta_blended_images(
    fal_or_blend_client: Any,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = FAL_BLENDING_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate 9:16 CTA Blended Image using Fal AI Nano Banana Pro into 'CTA Blended Image'."""
    airtable.ensure_fields({BLENDED_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        INTERIOR_FIELD_FALLBACKS + PROMPT_FIELD_FALLBACKS + BLENDED_FIELD_FALLBACKS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to generate blended images.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        prompt_val = get_first_field_value(fields, PROMPT_FIELD_FALLBACKS)
        blended_val = get_first_field_value(fields, BLENDED_FIELD_FALLBACKS)
        if not prompt_val:
            continue
        if blended_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Nano Banana Pro CTA blending (prompt missing or blended image already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{BLENDED_FIELD}' for {len(eligible)} record(s) "
        f"using Fal AI Nano Banana Pro ({blend_model}, Aspect Ratio: {BLENDED_ASPECT_RATIO})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        prompt_str = str(get_first_field_value(fields, PROMPT_FIELD_FALLBACKS)).strip()
        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELD_FALLBACKS))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))

        image_urls = [url for url in [interior_url, furniture_url] if url]
        if not image_urls:
            print(f"[SKIP] Record {record_id} ({item_label}) has no accessible source image URLs.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Blending CTA image for "
            f"record {record_id} ({item_label}) with Fal AI Nano Banana Pro..."
        )

        downloaded = None
        try:
            image_url = fal_or_blend_client.generate(
                prompt=prompt_str,
                image_urls=image_urls,
                aspect_ratio=BLENDED_ASPECT_RATIO,
                resolution="1K",
                model=blend_model,
            )
            import requests
            resp = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                resp,
                prefix="cta_blend_",
                suffix=".jpg",
                context=f"Download CTA blended image from {image_url}",
            )

            filename = f"cta_blended_{record_id}.jpg"
            target_field = get_first_field_name(fields, BLENDED_FIELD_FALLBACKS)
            airtable.upload_attachment(record_id, target_field, downloaded, filename)
            safe_update_status(airtable, record_id, STATUS_BLENDED_IMAGE)
            print(
                f"[OK] Attached CTA blended image to '{target_field}' and updated "
                f"{STATUS_FIELD} on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed blending CTA image for record {record_id}: {error}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(f"[INFO] Fal AI Nano Banana Pro CTA blending complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def clean_headline_text(text: str) -> str:
    """Clean generated headline to be concise 2-4 words, removing markdown and extra punctuation."""
    if not text:
        return ""
    s = str(text).strip()
    lines = [line.strip() for line in s.splitlines() if line.strip()]
    if lines:
        s = lines[0]
    for _ in range(3):
        s = s.strip().strip('"\'`*#_~').strip()
        for prefix in ("headline:", "hook:", "title:", "caption:", "words:"):
            if s.lower().startswith(prefix):
                s = s[len(prefix):].strip()
    return s.rstrip(".:,;!-").strip('"\'`*#_~ ').strip()


def generate_claude_word_generated(
    fal_or_vision: Any,
    airtable: ScrapeAirtableClient,
    *,
    vision_model: str = FAL_VISION_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
    force_refresh: bool = False,
    max_retries: int = 3,
) -> bool:
    """Generate luxury 2-4 word headline in 'Word Generated' strictly using Claude Sonnet 5 via Fal AI."""
    airtable.ensure_fields({WORD_GENERATED_FIELD: "singleLineText"})
    records = airtable.list_records(
        BLENDED_FIELD_FALLBACKS + WORD_GENERATED_FALLBACKS + [ITEM_NAME_FIELD, SKU_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to generate words.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    existing_headlines: set[str] = set()
    for r in records:
        w = get_first_field_value(r.get("fields", {}), WORD_GENERATED_FALLBACKS)
        if w and isinstance(w, str):
            clean_w = clean_headline_text(w)
            if clean_w and clean_w.lower() not in ("modern luxury living", "singkwenta dose"):
                existing_headlines.add(clean_w)

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        blended_val = get_first_field_value(fields, BLENDED_FIELD_FALLBACKS)
        word_val = get_first_field_value(fields, WORD_GENERATED_FALLBACKS)
        if not blended_val:
            continue

        is_repeating_default = False
        if word_val:
            clean_val = clean_headline_text(str(word_val))
            if clean_val.lower() in ("modern luxury living", "singkwenta dose"):
                is_repeating_default = True

        if word_val and not force_refresh and not is_repeating_default:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Claude Sonnet 5 word generation (blended image missing or word already filled with unique headline).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating unique '{WORD_GENERATED_FIELD}' for {len(eligible)} record(s) "
        f"strictly using Claude Sonnet 5 API ({vision_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Lighting Fixture").strip()
        item_label = f"{record_id} ({item_name})"

        blended_url = extract_attachment_url(get_first_field_value(fields, BLENDED_FIELD_FALLBACKS))
        if not blended_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible CTA Blended Image attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing CTA blended image for "
            f"record {record_id} ({item_label}) with Claude Sonnet 5..."
        )

        avoid_clause = ""
        if existing_headlines:
            sample_avoid = list(existing_headlines)[-20:]
            avoid_clause = (
                f" Do NOT reuse or repeat any of the following previously used headlines: "
                f"{json.dumps(sample_avoid)}. Make sure your headline is completely unique, creative, and distinct."
            )

        instruction = (
            "Analyze this luxury interior and lighting design image ('CTA Blended Image'). "
            "Generate an original, elegant, luxury 2 to 4 word headline or hook that captures the unique visual vibe, architectural aesthetic, lighting mood, and interior style shown in the room for an Instagram Story. "
            "Do NOT include or mention any product item names, brand names, catalog titles, or SKU codes. "
            "Base the words purely and dynamically on the visual composition, textures, colors, and lighting atmosphere in the image. "
            "Keep it concise, elegant, and punchy. Output ONLY the 2 to 4 words without quotation marks, commentary, explanations, or extra punctuation."
            f"{avoid_clause}"
        )

        cleaned_words = ""
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                raw_words = ""
                if hasattr(fal_or_vision, "analyze_image"):
                    raw_words = fal_or_vision.analyze_image(
                        prompt=instruction,
                        image_urls=[blended_url],
                        model=vision_model,
                    )
                elif hasattr(fal_or_vision, "generate_vision_prompt"):
                    raw_words = fal_or_vision.generate_vision_prompt(
                        image_urls=[blended_url],
                        prompt=instruction,
                        model=vision_model,
                    )
                else:
                    raise AutomationError("Vision client has neither 'analyze_image' nor 'generate_vision_prompt'.")

                candidate = clean_headline_text(raw_words)
                if not candidate:
                    raise ValueError(f"Claude Vision API returned an empty response (raw: {raw_words!r})")

                # If Claude returned a duplicate headline already in this table, prompt Claude again
                if candidate.lower() in {h.lower() for h in existing_headlines}:
                    if attempt < max_retries:
                        print(
                            f"[WARN] [Attempt {attempt}/{max_retries}] Claude returned duplicate headline '{candidate}'. "
                            f"Re-querying Claude Sonnet 5 for a completely distinct phrase..."
                        )
                        instruction += f" Note: You previously returned '{candidate}'. Do NOT use that; generate a completely different phrase."
                        time.sleep(1.0)
                        continue

                cleaned_words = candidate
                break

            except Exception as err:
                last_error = err
                print(
                    f"[WARN] [Attempt {attempt}/{max_retries}] Claude Vision API call error on record {record_id}: {err}"
                )
                if attempt < max_retries:
                    sleep_sec = attempt * 1.5
                    print(f"[INFO] Retrying Claude Sonnet 5 Vision in {sleep_sec:.1f}s...")
                    time.sleep(sleep_sec)

        if not cleaned_words:
            print(
                f"[ERROR] Failed generating Claude words for record {record_id} after {max_retries} API attempts: {last_error}"
            )
            failed += 1
            continue

        target_field = get_first_field_name(fields, WORD_GENERATED_FALLBACKS)
        airtable.update_records([(record_id, {target_field: cleaned_words})])
        existing_headlines.add(cleaned_words)
        print(
            f"[OK] Claude Sonnet 5 generated unique words '{cleaned_words}' for record {record_id} and updated '{target_field}'"
        )
        succeeded += 1

    print(f"[INFO] Claude word generation complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def generate_watermark_added_images(
    airtable: ScrapeAirtableClient,
    *,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Stamp Logo and Canva CTA text watermark layout using Python Pillow."""
    airtable.ensure_fields({WATERMARK_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        BLENDED_FIELD_FALLBACKS
        + WATERMARK_FIELD_FALLBACKS
        + LOGO_FIELD_FALLBACKS
        + WORD_GENERATED_FALLBACKS
        + [ITEM_NAME_FIELD, SKU_FIELD, STATUS_FIELD, "Product Type", "Category", TARGET_BLENDED_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to composite watermark layout.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        blended_val = get_first_field_value(fields, BLENDED_FIELD_FALLBACKS)
        watermark_val = get_first_field_value(fields, WATERMARK_FIELD_FALLBACKS)
        if not blended_val:
            continue
        if watermark_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring watermark layout compositing (blended missing or watermark already added).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Stamping HomeCartel logo & CTA text watermark layout (Python Pillow) for {len(eligible)} record(s) "
        f"into '{WATERMARK_FIELD}'..."
    )

    import requests
    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        raw_item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "HomeCartel Lighting").strip()
        item_title, product_type = split_item_name(
            raw_item_name, fallback_product_type=str(fields.get("Product Type") or "")
        )
        item_label = f"{record_id} ({item_title})"

        cat_code = str(fields.get("Category") or "").strip().lower().replace(" ", "_")
        if not cat_code:
            tbl_info = CTA_STORY_TABLES.get(table_id or "", {})
            cat_code = tbl_info.get("category_code", "chandelier").replace("_cta_story", "")

        blended_url = extract_attachment_url(get_first_field_value(fields, BLENDED_FIELD_FALLBACKS))
        if not blended_url:
            print(f"[SKIP] Record {record_id} ({item_label}) has no accessible CTA Blended Image.")
            continue

        logo_url = extract_attachment_url(get_first_field_value(fields, LOGO_FIELD_FALLBACKS))
        words_val = get_first_field_value(fields, WORD_GENERATED_FALLBACKS)
        display_headline = str(words_val).strip() if words_val else item_title

        print(
            f"[INFO] [{position}/{len(eligible)}] Stamping Logo & CTA layout for "
            f"record {record_id} ({item_label}) with local Python Pillow..."
        )

        dl_blended = None
        dl_logo = None
        out_path = None
        tagged_temp_path = None
        try:
            resp_b = requests.get(blended_url, stream=True, timeout=30)
            dl_blended = download_to_temp_file(resp_b, prefix="blend_in_", suffix=".jpg", context="Blended photo dl")

            # Auto-tag furniture item name onto blended scene using zero-cost local YOLO-World (with Upper/Mid-Left fallback)
            source_to_composite = dl_blended.path
            try:
                with tempfile.NamedTemporaryFile(suffix="_cta_tagged.jpg", delete=False) as tf_tag:
                    tagged_temp_path = tf_tag.name

                tagged_img, _ = tag_blended_image(
                    image_input=dl_blended.path,
                    item_name=item_title,
                    product_type=product_type,
                    category=cat_code,
                    destination=tagged_temp_path,
                    fallback_if_undetected=True,
                )
                if tagged_temp_path and Path(tagged_temp_path).is_file():
                    source_to_composite = tagged_temp_path
                    # Upload to 'Blended Image with Name text'
                    try:
                        airtable.ensure_fields({TARGET_BLENDED_FIELD: "multipleAttachments"})
                        airtable.upload_attachment(
                            record_id,
                            TARGET_BLENDED_FIELD,
                            tagged_temp_path,
                            f"cta_tagged_{record_id}.jpg",
                        )
                    except Exception:
                        pass
            except Exception as tag_err:
                print(f"[WARN] Failed auto-tagging item name on record {record_id}: {tag_err}")

            logo_source_path = None
            if logo_url:
                try:
                    resp_l = requests.get(logo_url, stream=True, timeout=30)
                    dl_logo = download_to_temp_file(resp_l, prefix="logo_in_", suffix=".png", context="Logo dl")
                    logo_source_path = dl_logo.path
                except Exception as e:
                    print(f"[WARN] Failed downloading logo attachment, falling back to local: {e}")

            if not logo_source_path:
                local_logo = find_homecartel_logo_path()
                if local_logo:
                    logo_source_path = local_logo

            with tempfile.NamedTemporaryFile(suffix="_cta_converted.jpg", delete=False) as tf:
                out_path = tf.name

            stamp_cta_story_watermark_and_logo(
                base_image_path=source_to_composite,
                logo_path=logo_source_path,
                output_path=out_path,
                item_name=display_headline,
            )

            filename = f"cta_converted_{record_id}.jpg"
            output_field_name = get_first_field_name(fields, WATERMARK_FIELD_FALLBACKS)
            airtable.upload_attachment(record_id, output_field_name, out_path, filename)
            safe_update_status(airtable, record_id, STATUS_COMPLETE)
            print(
                f"[OK] Attached composited photo to '{output_field_name}' and updated "
                f"{STATUS_FIELD} on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed compositing watermark layout for record {record_id}: {error}")
            failed += 1
        finally:
            if dl_blended:
                dl_blended.cleanup()
            if dl_logo:
                dl_logo.cleanup()
            if tagged_temp_path and Path(tagged_temp_path).exists():
                try:
                    Path(tagged_temp_path).unlink()
                except Exception:
                    pass
            if out_path and Path(out_path).exists():
                try:
                    Path(out_path).unlink()
                except Exception:
                    pass
    print(f"[INFO] Watermark layout compositing complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def get_first_incomplete_record(airtable: ScrapeAirtableClient) -> dict[str, Any] | None:
    records = airtable.list_records(
        INTERIOR_FIELD_FALLBACKS
        + PROMPT_FIELD_FALLBACKS
        + BLENDED_FIELD_FALLBACKS
        + WORD_GENERATED_FALLBACKS
        + CONVERTED_FIELD_FALLBACKS
        + [FIELD_NAME, ITEM_NAME_FIELD, SKU_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        return None
    records = sort_records_by_id(records)
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().lower()
        if status in {"complete", "completed"}:
            continue
        converted_val = get_first_field_value(fields, CONVERTED_FIELD_FALLBACKS)
        if converted_val:
            continue
        return record
    return None


def show_table_menu(current_table_id: str | None = None) -> str:
    """Interactive menu to select which CTA Story table to target."""
    tables = get_cta_tables()
    table_items = list(tables.items())

    # Fast parallel fetch of live P, C, D, FM status breakdown
    status_map: dict[str, dict[str, int]] = {}
    try:
        scrape_settings = load_scrape_settings()
        if scrape_settings.airtable_token and scrape_settings.airtable_base_id and table_items:
            table_ids = [tid for tid, _ in table_items]
            status_map = fetch_multiple_tables_status_breakdown(
                scrape_settings.airtable_token,
                scrape_settings.airtable_base_id,
                table_ids,
                max_workers=5,
            )
    except Exception:
        pass

    print("\n" + "=" * 68)
    print("              SELECT CTA STORY AIRTABLE TABLE")
    print("=" * 68)
    for idx, (tid, info) in enumerate(table_items, 1):
        is_current = " (CURRENT)" if tid == current_table_id else ""
        st = status_map.get(tid)
        if st:
            status_line = f"P: {st['P']} | C: {st['C']} | D: {st['D']} | FM: {st['FM']} (Completed: {st['P'] + st['C']})"
        else:
            status_line = "P: - | C: - | D: - | FM: -"

        print(f"  [{idx}] {info['label']}{is_current}")
        print(f"      Table ID:  {tid}")
        print(f"      Category:  {info['category_code']}")
        print(f"      Moodboard: {info['default_moodboard_id']}")
        print(f"      Prompt:    \"{info['default_prompt']}\"")
        print(f"      Status:    {status_line}\n")
    print(f"  [{len(table_items) + 1}] Multi-Table Round-Robin (All CTA Tables)")
    print(f"  [{len(table_items) + 2}] Enter Custom Airtable Table ID Manually")
    print(f"  [{len(table_items) + 3}] Exit\n")
    print("=" * 68)

    while True:
        choice = input(f" Select Table [1-{len(table_items) + 3}] (default: 1): ").strip()
        if not choice:
            choice = "1"
        if choice.lower() in {"0", "q", "exit", "quit"}:
            return "exit"
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(table_items):
                return table_items[idx - 1][0]
            if idx == len(table_items) + 1:
                return "round_robin"
            if idx == len(table_items) + 2:
                custom = input(" Enter Airtable Table ID (e.g., tblYHdVq14FjMWg5o): ").strip()
                if custom:
                    return custom
                print("[WARN] Table ID cannot be empty.")
                continue
            if idx == len(table_items) + 3:
                return "exit"
        elif choice in tables or choice in CTA_STORY_TABLES:
            return choice
        print(f"[WARN] Invalid option. Please enter 1 to {len(table_items) + 3}.")


def show_menu(active_table_id: str | None = None) -> str:
    tables = get_cta_tables()
    tbl_id = active_table_id or DEFAULT_TABLE_ID
    tbl_info = tables.get(tbl_id, {})
    tbl_name = tbl_info.get("label", tbl_id)

    print("\n" + "=" * 64)
    print("           CTA STORY AI GENERATION & BLENDING           ")
    print("=" * 64)
    print(f" Active Table: {tbl_name} ({tbl_id})")
    print(f" Category:     {tbl_info.get('category_code', 'Custom')}")
    print(f" Moodboard:    {tbl_info.get('default_moodboard_id', 'Default')}")
    print(f" Prompt:       \"{tbl_info.get('default_prompt', DEFAULT_PROMPT)}\"")
    print("=" * 64)
    print(" Select a phase to run:\n")
    print(" [1] Scrape Akeneo Products to Airtable (1 item)")
    print(" [2] Krea AI Interior Generation (9:16) -> 'CTA Interior'")
    print(" [3] Claude Sonnet 5 Prompt Generation (Fal AI) -> 'Blending Prompt'")
    print(" [4] Fal AI Nano Banana Pro Blending (9:16) -> 'CTA Blended Image'")
    print(" [5] Claude Sonnet 5 Headline Generation -> 'Word Generated' (Unique/Deduplicated)")
    print(" [6] Python Local CTA Layout & Logo Stamping (9:16) -> 'CTA Converted Image'")
    print(" [7] Run Full End-to-End Pipeline (Scrape Akeneo 1 item + Steps 2-6)")
    print(" [8] Multi-Table Round-Robin (All CTA Tables)")
    print(" [9] Switch Target Table ID")
    print(" [10] Exit\n")

    menu_choices = {
        "1": "scrape",
        "2": "interior",
        "3": "prompt",
        "4": "blend",
        "5": "words",
        "6": "conversion",
        "7": "all",
        "8": "round_robin",
        "9": "switch_table",
        "10": "exit",
    }
    while True:
        choice = input(" Enter choice [1-10]: ").strip()
        if choice.lower() in {"0", "q", "exit", "quit"}:
            return "exit"
        if choice in menu_choices:
            return menu_choices[choice]
        print("[WARN] Invalid option. Please enter 1, 2, 3, 4, 5, 6, 7, 8, 9, or 10.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="CTA Story AI Generation & Blending Pipeline"
    )
    default_mode = "menu" if (argv is None and len(sys.argv) == 1) else "all"
    parser.add_argument(
        "--mode",
        "-m",
        choices=["scrape", "interior", "prompt", "blend", "words", "conversion", "watermark", "round_robin", "all", "menu"],
        default=default_mode,
        help="Mode of operation: scrape, interior, prompt, blend, words, conversion, round_robin, all, or menu (default: menu if no flags)",
    )
    parser.add_argument(
        "--category",
        "-c",
        default=DEFAULT_CATEGORY,
        help=f"Target table category (default: {DEFAULT_CATEGORY})",
    )
    parser.add_argument(
        "--prompt",
        "-p",
        default=None,
        help="Optional custom prompt override for Krea interior generation",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Style code filter (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override Airtable destination table ID",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=1,
        metavar="N",
        help="Process at most N records in each phase (default: 1)",
    )
    parser.add_argument(
        "--force-words",
        "--refresh-words",
        action="store_true",
        dest="force_words",
        help="Force re-generation of 'Word Generated' headlines even if already filled (replaces repetitive defaults)",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Optional custom Krea Moodboard ID override",
    )
    return parser.parse_args(argv)


def run_pipeline(
    mode: str = "all",
    category_code: str = DEFAULT_CATEGORY,
    style_code: str = DEFAULT_STYLE,
    custom_prompt: str | None = None,
    table_id_override: str | None = None,
    max_items: int = 1,
    force_words: bool = False,
    custom_moodboard_id: str | None = None,
) -> int:
    target_table_id = table_id_override

    if mode == "menu":
        if not target_table_id:
            chosen = show_table_menu(current_table_id=DEFAULT_TABLE_ID)
            if chosen == "exit":
                print("[INFO] Exiting CTA Story Pipeline. Goodbye!")
                return 0
            if chosen == "round_robin":
                from run_cta_round_robin import run_round_robin, DEFAULT_CTA_CATEGORIES
                return run_round_robin(
                    categories=[c for c, _ in DEFAULT_CTA_CATEGORIES],
                    total_rounds=1,
                    is_infinite=False,
                    style_code=style_code,
                    delay_seconds=5,
                )
            target_table_id = chosen

        while True:
            choice = show_menu(target_table_id)
            if choice == "exit":
                print("[INFO] Exiting CTA Story Pipeline. Goodbye!")
                return 0
            if choice == "switch_table":
                chosen = show_table_menu(current_table_id=target_table_id)
                if chosen == "exit":
                    print("[INFO] Exiting CTA Story Pipeline. Goodbye!")
                    return 0
                if chosen == "round_robin":
                    from run_cta_round_robin import run_round_robin, DEFAULT_CTA_CATEGORIES
                    return run_round_robin(
                        categories=[c for c, _ in DEFAULT_CTA_CATEGORIES],
                        total_rounds=1,
                        is_infinite=False,
                        style_code=style_code,
                        delay_seconds=5,
                    )
                target_table_id = chosen
                continue
            if choice == "round_robin":
                from run_cta_round_robin import run_round_robin, DEFAULT_CTA_CATEGORIES
                return run_round_robin(
                    categories=[c for c, _ in DEFAULT_CTA_CATEGORIES],
                    total_rounds=1,
                    is_infinite=False,
                    style_code=style_code,
                    delay_seconds=5,
                )
            mode = choice
            break

    target_table_id, effective_category, tbl_cfg = resolve_cta_table_and_config(
        target_table_id=target_table_id,
        category_code=category_code if (category_code != DEFAULT_CATEGORY or not target_table_id) else None,
    )

    base_settings = load_settings()
    scrape_settings = load_scrape_settings(
        category_code=effective_category,
        style_code=style_code,
        table_id_override=target_table_id,
    )

    interior_prompt = (
        custom_prompt
        or tbl_cfg.get("default_prompt")
        or prompt_for_category(effective_category, custom_prompt)
    )

    moodboard_id = (
        custom_moodboard_id
        or tbl_cfg.get("default_moodboard_id")
        or moodboard_id_for_category(effective_category, DEFAULT_MOODBOARD_ID)
        or DEFAULT_MOODBOARD_ID
    )

    airtable = ScrapeAirtableClient(
        token=scrape_settings.airtable_token,
        base_id=scrape_settings.airtable_base_id,
        table_id=target_table_id,
    )

    tbl_label = tbl_cfg.get("label", effective_category)
    print("\n" + "=" * 70)
    print(f" [CTA RUNNER] Target Table:  {tbl_label} ({target_table_id})")
    print(f" [CTA RUNNER] Category Code: {effective_category}")
    print(f" [CTA RUNNER] Moodboard ID:  {moodboard_id}")
    print(f" [CTA RUNNER] Krea Prompt:   \"{interior_prompt}\"")
    print(f" [CTA RUNNER] Airtable Base: {scrape_settings.airtable_base_id}")
    print("=" * 70 + "\n")
    count = max_items or 1
    failures = 0

    if mode == "scrape":
        print(f"[INFO] Phase 1: Scraping {count} product item(s) from Akeneo to Airtable...")
        for i in range(count):
            try:
                if not run_category_scrape(
                    category_code=scrape_settings.category_code,
                    style_code=scrape_settings.style_code,
                    items_per_row_override=1,
                    max_items=1,
                    table_id_override=target_table_id,
                ):
                    failures += 1
                else:
                    newly_scraped = get_first_incomplete_record(airtable)
                    if newly_scraped:
                        ensure_cta_layout_uploaded(airtable, newly_scraped["id"], newly_scraped.get("fields", {}))
                        ensure_cta_logo_uploaded(airtable, newly_scraped["id"], newly_scraped.get("fields", {}))
            except Exception as error:
                print(f"[ERROR] Failed scraping Akeneo products: {error}")
                failures += 1
        backfill_missing_cta_assets(airtable)
        return 1 if failures else 0

    if mode == "interior":
        base_settings.require({"krea"})
        krea = KreaClient(base_settings.krea_token, base_url=base_settings.krea_base_url)
        return 0 if generate_krea_interiors(
            krea,
            airtable,
            moodboard_id=moodboard_id,
            prompt=interior_prompt,
            limit_records=count,
        ) else 1

    if mode == "prompt":
        base_settings.require({"fal"})
        fal_client = FalClient(base_settings.fal_key)
        return 0 if generate_claude_blending_prompts(
            fal_client,
            airtable,
            limit_records=count,
        ) else 1

    if mode == "blend":
        base_settings.require({"fal"})
        fal_client = FalClient(base_settings.fal_key)
        return 0 if generate_cta_blended_images(
            fal_client,
            airtable,
            limit_records=count,
        ) else 1

    if mode == "words":
        base_settings.require({"fal"})
        fal_client = FalClient(base_settings.fal_key)
        return 0 if generate_claude_word_generated(
            fal_client,
            airtable,
            limit_records=count,
            force_refresh=force_words,
        ) else 1

    if mode == "conversion":
        return 0 if run_cta_conversion(
            base_settings,
            table_id=target_table_id,
            max_items=count,
            use_local_pil=True,
        ) else 1

    # mode == 'all': Full 6-Phase Row-by-Row Pipeline Loop
    base_settings.require({"krea", "fal"})
    krea = KreaClient(base_settings.krea_token, base_url=base_settings.krea_base_url)
    fal_client = FalClient(base_settings.fal_key)

    for row_idx in range(1, count + 1):
        print(f"\n{'=' * 30} ROW {row_idx}/{count} {'=' * 30}")
        print(f"[INFO] [Phase 1/6] Scraping 1 new product item from Akeneo (cross-checked with Shopify) to Airtable...")
        existing_ids = {r["id"] for r in airtable.list_records(["Status"])}
        target_record_id = None

        try:
            if not run_category_scrape(
                category_code=scrape_settings.category_code,
                style_code=scrape_settings.style_code,
                items_per_row_override=1,
                max_items=1,
                table_id_override=target_table_id,
            ):
                print(f"[WARN] Akeneo scrape returned warnings on Row {row_idx}.")
        except Exception as error:
            print(f"[ERROR] Failed scraping Akeneo products on Row {row_idx}: {error}")
            failures += 1

        refreshed_records = airtable.list_records(
            INTERIOR_FIELD_FALLBACKS
            + PROMPT_FIELD_FALLBACKS
            + BLENDED_FIELD_FALLBACKS
            + WORD_GENERATED_FALLBACKS
            + CONVERTED_FIELD_FALLBACKS
            + [FIELD_NAME, ITEM_NAME_FIELD, SKU_FIELD, STATUS_FIELD]
        )
        newly_scraped_candidates = [r for r in refreshed_records if r["id"] not in existing_ids]

        if newly_scraped_candidates:
            target_record_id = newly_scraped_candidates[0]["id"]
            fields = newly_scraped_candidates[0].get("fields", {})
            label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or target_record_id
            print(f"[OK] Successfully scraped new product: Record {target_record_id} ({label})")
            ensure_cta_layout_uploaded(airtable, target_record_id, fields)
            ensure_cta_logo_uploaded(airtable, target_record_id, fields)
        else:
            incomplete_rec = get_first_incomplete_record(airtable)
            if incomplete_rec:
                target_record_id = incomplete_rec["id"]
                fields = incomplete_rec.get("fields", {})
                label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or target_record_id
                print(f"[INFO] No new Akeneo products scraped. Completing existing row: Record {target_record_id} ({label})...")
                ensure_cta_layout_uploaded(airtable, target_record_id, fields)
                ensure_cta_logo_uploaded(airtable, target_record_id, fields)
            else:
                print(f"[WARN] No new products scraped from Akeneo and no incomplete records in table.")
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}
        item_label = current_fields.get(ITEM_NAME_FIELD) or current_fields.get(SKU_FIELD) or target_record_id

        # Phase 2: Krea AI Interior Generation (9:16) -> 'CTA Interior'
        if not get_first_field_value(current_fields, INTERIOR_FIELD_FALLBACKS):
            print(f"[INFO] [Phase 2/6] Generating 9:16 Room Interior with Krea AI for Record {target_record_id}...")
            print(f"[INFO] [Phase 2/6] Active Moodboard: {moodboard_id} | Prompt: \"{interior_prompt}\"")
            ok_phase2 = generate_krea_interiors(
                krea,
                airtable,
                moodboard_id=moodboard_id,
                prompt=interior_prompt,
                target_record_id=target_record_id,
            )
            if not ok_phase2:
                print(f"[ERROR] Phase 2 Interior generation failed on Record {target_record_id}.")
                failures += 1
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 3: Claude Sonnet 5 Prompt Generation -> 'Blending Prompt'
        if not get_first_field_value(current_fields, PROMPT_FIELD_FALLBACKS):
            print(f"[INFO] [Phase 3/6] Analyzing Photos with Claude Sonnet 5 for Record {target_record_id}...")
            ok_phase3 = generate_claude_blending_prompts(
                fal_client,
                airtable,
                target_record_id=target_record_id,
            )
            if not ok_phase3:
                print(f"[ERROR] Phase 3 Claude Prompt generation failed on Record {target_record_id}.")
                failures += 1
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 4: Fal AI Nano Banana Pro Blending (9:16) -> 'CTA Blended Image'
        if not get_first_field_value(current_fields, BLENDED_FIELD_FALLBACKS):
            print(f"[INFO] [Phase 4/6] Blending Furniture + Interior with Fal AI Nano Banana Pro for Record {target_record_id}...")
            ok_phase4 = generate_cta_blended_images(
                fal_client,
                airtable,
                target_record_id=target_record_id,
            )
            if not ok_phase4:
                print(f"[ERROR] Phase 4 Nano Banana Pro blending failed on Record {target_record_id}.")
                failures += 1
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 5: Claude Sonnet 5 Headline Analysis -> 'Word Generated'
        word_val_now = get_first_field_value(current_fields, WORD_GENERATED_FALLBACKS)
        is_stale_default = (
            word_val_now
            and clean_headline_text(str(word_val_now)).lower() in ("modern luxury living", "singkwenta dose")
        )
        word_was_updated = False
        if not word_val_now or is_stale_default or force_words:
            print(f"[INFO] [Phase 5/6] Analyzing 'CTA Blended Image' with Claude Sonnet 5 for Record {target_record_id}...")
            ok_phase5 = generate_claude_word_generated(
                fal_client,
                airtable,
                target_record_id=target_record_id,
                force_refresh=force_words,
            )
            if not ok_phase5:
                print(f"[ERROR] Phase 5 Claude Headline Analysis failed on Record {target_record_id}.")
                failures += 1
                continue
            word_was_updated = True

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 6: Python Local CTA Layout & Logo Stamping (9:16) -> 'CTA Converted Image' / 'Watermark Added'
        has_converted = get_first_field_value(current_fields, CONVERTED_FIELD_FALLBACKS)
        if not has_converted or word_was_updated:
            ensure_cta_layout_uploaded(airtable, target_record_id, current_fields)
            ensure_cta_logo_uploaded(airtable, target_record_id, current_fields)
            print(f"[INFO] [Phase 6/6] Stamping Logo & CTA Layout (Python Pillow) for Record {target_record_id}...")
            ok_phase6 = run_cta_conversion(
                base_settings,
                table_id=target_table_id,
                target_record_id=target_record_id,
                use_local_pil=True,
            )
            if not ok_phase6:
                print(f"[ERROR] Phase 6 Local CTA conversion failed on Record {target_record_id}.")
                failures += 1
                continue

        print(f"[ROW {row_idx} COMPLETE] Record {target_record_id} is 100% COMPLETE! Status: Complete.")

    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_pipeline(
            mode=args.mode,
            category_code=args.category,
            style_code=args.style,
            custom_prompt=args.prompt,
            table_id_override=args.table_id,
            max_items=args.max_items,
            force_words=getattr(args, "force_words", False),
            custom_moodboard_id=getattr(args, "moodboard_id", None),
        )
    except KeyboardInterrupt:
        print("\n[INFO] Exited CTA Story Pipeline. Goodbye!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

    sys.exit(main())
