"""Style Reel Slideshow (5 Interiors, 4 Blended Lighting Products, 9:16 Video Reel) Complete Automation Pipeline.

Target Table: Style Reel Slideshow (tblFFEvkHb3jLKrcv)

Phases:
1. Akeneo Multi-Category Scrape (Newest to Oldest, Randomized Pool Selection):
   Packs distinct lighting product categories into 1 Airtable row with random selection from newest inventory:
   - Slot 1: Living Room Chandelier (Interior Only, No Blending)
   - Slot 2: Floor Lamp (floor_lamps) -> Furniture Item2, Item Name2
   - Slot 3: Table Lamp (table_lamps) -> Furniture item3 / Furniture Item3, Item Name3
   - Slot 4: Linear Chandelier (chandeliers with 'linear') -> Furniture Item4, Item Name4
   - Slot 5: Pendant Light (pendant_lights) -> Furniture Item5, Item Name5
   Sets Status -> 'Standby'.

2. Krea AI Sequential Interior Generation (9:16 Ratio) with Dedicated Moodboards:
   Generates 5 coherent rooms with slot-specific moodboards & cumulative style referencing (9:16 ratio):
   - Slot 1 (Living Room): Chandelier living room (Moodboard: b5ffdcbb-192e-4528-8d86-d1a4cf496887, base) -> Interior1
   - Slot 2 (Bedroom): Bedroom with floor lamp (Moodboard: b1641228-beec-4823-8d01-1de3eec8410d, Ref: Interior1) -> Interior2
   - Slot 3 (Living Room Sofa End Table): "Put a lamp on an end table next to the sofa." (Moodboard: fb2487fb-2895-4d2c-9758-805aaf1bac69, Refs: Interior1, Interior2) -> Interior3
   - Slot 4 (Kitchen): Kitchen with hanging linear chandelier (Moodboard: 994a703c-4c6b-498a-bb27-7609615a74bd, Refs: Interior1, Interior2, Interior3) -> Interior4
   - Slot 5 (Dining Room): Dining room with hanging pendant light (Moodboard: de5f4ff8-518c-4d6b-b606-ce1d5dac51f3, Refs: Interior1..4) -> Interior5
   Sets Status -> 'Processing'.

3. Claude Sonnet 5 Prompt Analysis (via Fal AI, Slots 2 to 5):
   Uses anthropic/claude-sonnet-5 via Fal AI openrouter/router/vision to analyze each (Interior[i], Furniture Item[i]) pair
   for Slots 2 to 5 and writes tailored blending prompts to Blending Prompt2 through Blending Prompt5.
   (Slot 1 is skipped as it is an unblended pure interior photo).

4. Fal AI Nano Banana Pro Blending (9:16 Ratio, 1K Quality, Slots 2 to 5):
   Blends products 2 to 5 into their respective interiors using fal-ai/nano-banana-pro/edit at 9:16 ratio (1K)
   and uploads them to Blended Image2 through Blended Image5.
   Sets Status -> 'Processing'.

5. Style Reel Slideshow MP4 Video Generation (9:16 Video):
   Stitches the 5 photos in sequence into an 11-second vertical H.264 MP4 slideshow video:
   - Slide 1 (Slot 1 Interior1): 3.0 seconds duration
   - Slide 2 (Slot 2 Blended Image2): 2.0 seconds duration
   - Slide 3 (Slot 3 Blended Image3): 2.0 seconds duration
   - Slide 4 (Slot 4 Blended Image4): 2.0 seconds duration
   - Slide 5 (Slot 5 Blended Image5): 2.0 seconds duration
   Uploads the video to Airtable field 'Style Reel Slideshow'.
   Sets Status -> 'Done'.

Usage:
    python run_style_reel_slideshow.py
    python run_style_reel_slideshow.py --phase all --execute
    python run_style_reel_slideshow.py --phase 1 --max-rows 1 --execute
    python run_style_reel_slideshow.py --phase 2 --execute
    python run_style_reel_slideshow.py --phase 3 --execute
    python run_style_reel_slideshow.py --phase 4 --execute
    python run_style_reel_slideshow.py --phase 5 --execute
    python run_style_reel_slideshow.py --menu
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import functools
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
import requests

from content_automation.akeneo_client import AkeneoClient, first_attribute
from content_automation.config import load_settings
from content_automation.errors import AssetValidationError, AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename, download_to_temp_file
from content_automation.models import LocalImage
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    product_item,
)

print = functools.partial(print, flush=True)

# ── Timezone & Configuration ─────────────────────────────────────────────

PHT = timezone(timedelta(hours=8))  # Philippine Standard Time (UTC+8)


def pht_timestamp() -> str:
    return datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")


DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_STYLE_REEL_SLIDESHOW", "").strip()
    or "tblFFEvkHb3jLKrcv"
)
DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_STYLE_REEL_SLIDESHOW", "").strip()
    or "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
)

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_PROCESSING = "Processing"
STATUS_DONE = "Done"

# Ratios & Models (9:16 for Krea & Fal Blending)
KREA_ASPECT_RATIO = "9:16"
KREA_RESOLUTION = "1K"
KREA_MOODBOARD_STRENGTH = 0.23
KREA_STYLE_REF_STRENGTH = 0.5

# Phase 3: Claude Sonnet 5 via Fal AI
FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"

# Phase 4: Fal AI Nano Banana Pro (9:16 Ratio, 1K Quality)
FAL_BLENDING_MODEL = os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
BLENDING_ASPECT_RATIO = "9:16"
BLENDING_RESOLUTION = "1K"

# Phase 5: Style Reel Slideshow Settings
SLIDESHOW_FIELD = "Style Reel Slideshow"
SLIDESHOW_FIELD_CANDIDATES = ("Style Reel Slideshow", "Style Reel Slide Show", "Slideshow")
OUTRO_FIELD = "Outro"
OUTRO_FIELD_CANDIDATES = ("Outro", "Outro Photo", "Outro Image", "Outro Thumbnail")
TITLE_FIELD_CANDIDATES = ("Reel Title", "Title", "Hook", "Thumbnail Title", "Word Generated", "Style Reel Title")
THUMBNAIL_FIELD_CANDIDATES = (
    "Thumbnail with Generated Text",
    "Thumbnail",
    "Slide 1 with Text",
    "Interior 1 with Text",
    "Cover Photo",
)
POPPINS_FONT_STYLE = "bold"
DIM_BRIGHTNESS_FACTOR = 0.65
SLIDE_1_DURATION = 3.0  # 3.0s for first photo (Slot 1 Interior with Poppins Text)
SLIDE_NEXT_DURATION = 2.0  # 2.0s each for subsequent photos (Slots 2..5)
OUTRO_DURATION = 3.0  # 3.0s for Outro slide (with 1.0s fade to black transition)
FADE_DURATION = 1.0  # 1.0s fade to black before Outro
SLIDESHOW_WIDTH = 1080
SLIDESHOW_HEIGHT = 1920
SLIDESHOW_FPS = 30

# ── Slot Definitions ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class SlotConfig:
    slot_index: int  # 1 to 5
    label: str
    akeneo_category: str
    keyword_filter: str | None
    exclude_keywords: tuple[str, ...]
    furniture_field_candidates: tuple[str, ...]
    item_name_field: str
    interior_field_candidates: tuple[str, ...]
    blending_prompt_field: str
    blended_image_field_candidates: tuple[str, ...]
    interior_prompt: str
    moodboard_id: str
    skip_blending: bool = False  # Slot 1 is pure generated interior, no blending


SLOTS: list[SlotConfig] = [
    SlotConfig(
        slot_index=1,
        label="Chandelier",
        akeneo_category="chandeliers",
        keyword_filter=None,
        exclude_keywords=("linear", "cluster"),
        furniture_field_candidates=("Furniture Item1", "Furniture Item 1"),
        item_name_field="Item Name1",
        interior_field_candidates=("Interior1", "Interior 1", "Interior"),
        blending_prompt_field="Blending Prompt1",
        blended_image_field_candidates=("Blended Image1", "Blended Image 1"),
        interior_prompt="Generate me a modern living room hanging chandelier make the ceiling plain",
        moodboard_id="b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        skip_blending=True,  # Slot 1: pure generated interior, no blending
    ),
    SlotConfig(
        slot_index=2,
        label="Floor Lamp",
        akeneo_category="floor_lamps",
        keyword_filter=None,
        exclude_keywords=(),
        furniture_field_candidates=("Furniture Item2", "Furniture Item 2"),
        item_name_field="Item Name2",
        interior_field_candidates=("Interior2", "Interior 2"),
        blending_prompt_field="Blending Prompt2",
        blended_image_field_candidates=("Blended Image2", "Blended Image 2"),
        interior_prompt="Generate me a modern bedroom with a floor lamp standing beside the bed",
        moodboard_id="b1641228-beec-4823-8d01-1de3eec8410d",
        skip_blending=False,
    ),
    SlotConfig(
        slot_index=3,
        label="Table Lamp",
        akeneo_category="table_lamps",
        keyword_filter=None,
        exclude_keywords=(),
        # Note: Airtable schema has 'Furniture item3' (lowercase 'item')
        furniture_field_candidates=("Furniture item3", "Furniture Item3", "Furniture Item 3"),
        item_name_field="Item Name3",
        interior_field_candidates=("Interior3", "Interior 3"),
        blending_prompt_field="Blending Prompt3",
        blended_image_field_candidates=("Blended Image3", "Blended Image 3"),
        interior_prompt="Put a lamp on an end table next to the sofa.",
        moodboard_id="fb2487fb-2895-4d2c-9758-805aaf1bac69",
        skip_blending=False,
    ),
    SlotConfig(
        slot_index=4,
        label="Linear Chandelier",
        akeneo_category="chandeliers",
        keyword_filter="linear",
        exclude_keywords=(),
        furniture_field_candidates=("Furniture Item4", "Furniture Item 4"),
        item_name_field="Item Name4",
        interior_field_candidates=("Interior4", "Interior 4"),
        blending_prompt_field="Blending Prompt4",
        blended_image_field_candidates=("Blended Image4", "Blended Image 4"),
        interior_prompt="Generate me a modern room interior kitchen with a linear chandelier hanging from the ceiling",
        moodboard_id="994a703c-4c6b-498a-bb27-7609615a74bd",
        skip_blending=False,
    ),
    SlotConfig(
        slot_index=5,
        label="Pendant Light",
        akeneo_category="pendant_lights",
        keyword_filter=None,
        exclude_keywords=(),
        furniture_field_candidates=("Furniture Item5", "Furniture Item 5"),
        item_name_field="Item Name5",
        interior_field_candidates=("Interior5", "Interior 5"),
        blending_prompt_field="Blending Prompt5",
        blended_image_field_candidates=("Blended Image5", "Blended Image 5"),
        interior_prompt="Generate me a dining room with a pendant light hanging from the ceiling",
        moodboard_id="de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
        skip_blending=False,
    ),
]


# ── Audit & Error Logging ────────────────────────────────────────────────

AUDIT_LOG_DIR = Path("output") / "logs"
AUDIT_LOG_AKENEO = AUDIT_LOG_DIR / "style_reel_slideshow_akeneo_logs.json"
AUDIT_LOG_KREA = AUDIT_LOG_DIR / "style_reel_slideshow_krea_logs.json"
AUDIT_LOG_CLAUDE = AUDIT_LOG_DIR / "style_reel_slideshow_claude_logs.json"
AUDIT_LOG_FAL = AUDIT_LOG_DIR / "style_reel_slideshow_fal_logs.json"
AUDIT_LOG_SLIDESHOW = AUDIT_LOG_DIR / "style_reel_slideshow_video_logs.json"


def append_audit_log(log_entry: dict[str, Any], log_path: Path) -> None:
    """Append an audit record to the specified JSON log file."""
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
    log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [AUDIT LOG] Appended log entry to {log_path}")


# ── Helper Functions ─────────────────────────────────────────────────────

def extract_attachment_url(attachments: Any) -> str:
    """Extract accessible HTTP URL from an Airtable attachment field."""
    if not attachments:
        return ""
    if isinstance(attachments, list) and len(attachments) > 0:
        first = attachments[0]
        if isinstance(first, dict):
            return str(first.get("url") or "").strip()
    if isinstance(attachments, dict):
        return str(attachments.get("url") or "").strip()
    return ""


def get_field_val(fields: dict[str, Any], candidates: tuple[str, ...] | list[str] | str) -> Any:
    """Find first matching populated field value."""
    if isinstance(candidates, str):
        candidates = [candidates]
    for name in candidates:
        if name in fields and fields[name]:
            return fields[name]
    return None


def resolve_field_name(existing_fields: dict[str, Any] | list[str] | set[str], candidates: tuple[str, ...]) -> str:
    """Return the exact field name existing on Airtable matching candidates."""
    existing_set = set(existing_fields) if not isinstance(existing_fields, set) else existing_fields
    for candidate in candidates:
        if candidate in existing_set:
            return candidate
    return candidates[0]


def update_record_status(airtable: ScrapeAirtableClient, record_id: str, desired_status: str) -> None:
    """Update Status safely matching table's singleSelect options."""
    try:
        fields_map = airtable.table_fields()
        status_entry = fields_map.get(STATUS_FIELD, {})
        choices = status_entry.get("choices", []) if isinstance(status_entry, dict) else []

        if not choices:
            airtable.update_records([(record_id, {STATUS_FIELD: desired_status})])
            return

        matched = next((c for c in choices if c.casefold() == desired_status.casefold()), None)
        if matched:
            airtable.update_records([(record_id, {STATUS_FIELD: matched})])
            return

        # Fallback to closest match
        sub_match = next((c for c in choices if desired_status.casefold() in c.casefold()), None)
        if sub_match:
            airtable.update_records([(record_id, {STATUS_FIELD: sub_match})])
            return

        airtable.update_records([(record_id, {STATUS_FIELD: choices[0]})])
    except Exception as err:
        print(f"  [WARN] Failed updating status for record {record_id}: {err}")


# ── Poppins Text Overlay Helpers ─────────────────────────────────────────

def resolve_poppins_font(style: str = "bold", size: int = 54) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Resolve Poppins font path from local font assets."""
    font_file_map = {
        "bold": "Poppins-Bold.ttf",
        "regular": "Poppins-Regular.ttf",
        "light": "Poppins-Light.ttf",
    }
    filename = font_file_map.get(style.lower(), "Poppins-Bold.ttf")
    base_fonts = Path(__file__).parent / "content_automation" / "fonts"
    candidates = [
        base_fonts / filename,
        Path("content_automation/fonts") / filename,
        Path("fonts") / filename,
        Path(filename),
    ]
    for c in candidates:
        if c.is_file():
            try:
                return ImageFont.truetype(str(c), size)
            except Exception:
                pass
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def overlay_centered_poppins_text(
    pil_img: Image.Image,
    text: str,
    *,
    font_style: str = POPPINS_FONT_STYLE,
    font_size: int | None = None,
    text_color: str = "#FFFFFF",
    dim_factor: float = DIM_BRIGHTNESS_FACTOR,
    wrap_width: int = 22,
) -> Image.Image:
    """Overlay text centered on image using Poppins font with clean wrapping, soft drop shadow, and background dimming."""
    import textwrap

    if not text or not text.strip():
        return pil_img.copy()

    img = pil_img.copy().convert("RGB")
    if dim_factor < 1.0:
        img = ImageEnhance.Brightness(img).enhance(dim_factor)

    width, height = img.size
    draw = ImageDraw.Draw(img)

    target_size = font_size or max(46, int(height * 0.038))
    font = resolve_poppins_font(style=font_style, size=target_size)

    clean_text = text.strip()
    wrapped_lines = textwrap.wrap(clean_text, width=wrap_width) or [clean_text]

    line_bboxes = [draw.textbbox((0, 0), line, font=font) for line in wrapped_lines]
    line_widths = [b[2] - b[0] for b in line_bboxes]
    line_heights = [b[3] - b[1] for b in line_bboxes]

    line_spacing = int(target_size * 0.3)
    total_height = sum(line_heights) + (len(wrapped_lines) - 1) * line_spacing
    start_y = (height - total_height) // 2

    current_y = start_y
    for i, line in enumerate(wrapped_lines):
        line_w = line_widths[i]
        line_h = line_heights[i]
        x = (width - line_w) // 2

        # Draw subtle drop shadow for crisp readability
        shadow_offset = max(2, int(target_size * 0.04))
        draw.text((x + shadow_offset, current_y + shadow_offset), line, font=font, fill="#000000")
        draw.text((x, current_y), line, font=font, fill=text_color)
        current_y += line_h + line_spacing

    return img


def generate_slideshow_title_prompt(
    fal: FalClient,
    interior1_url: str,
    item_names: list[str] | None = None,
    model: str = FAL_VISION_MODEL,
) -> str:
    """Generate a catchy, aesthetic 2-5 word title for the Style Reel Slideshow using Claude Sonnet 5."""
    items_desc = f" Products featured in subsequent slides include: {', '.join(item_names)}." if item_names else ""
    instruction = (
        "You are an expert interior design branding specialist and social media director. "
        "Analyze this modern living room interior photo."
        f"{items_desc}\n\n"
        "Generate a short, punchy, elegant 2 to 5 word interior styling title/hook for a luxury Instagram reel "
        "(e.g. '5 Modern Lighting Essentials', 'Curated Lighting For Modern Homes', 'Elevate Your Living Space', 'Modern Lighting Inspiration').\n"
        "Do NOT use ALL CAPS. Use Title Case. Return ONLY the 2-5 word title with no quotes or preamble."
    )
    raw_title = fal.generate_vision_prompt([interior1_url], instruction, model=model)
    return raw_title.strip().strip('"').strip("'")


@dataclass
class ExistingIdentities:
    skus: set[str]
    names: set[str]
    photos: set[str]


def collect_existing_identities(records: list[dict[str, Any]]) -> ExistingIdentities:
    """Extract known names, SKUs, and attachment filenames from Airtable records."""
    skus: set[str] = set()
    names: set[str] = set()
    photos: set[str] = set()

    for record in records:
        fields = record.get("fields", {})
        for slot in SLOTS:
            # Check Item Name
            name_val = str(fields.get(slot.item_name_field) or "").strip()
            if name_val:
                names.add(name_val.casefold())

            # Check Furniture Item attachment
            furniture_val = get_field_val(fields, slot.furniture_field_candidates)
            if isinstance(furniture_val, list):
                for att in furniture_val:
                    if isinstance(att, dict):
                        fn = str(att.get("filename") or "").strip().casefold()
                        if fn:
                            photos.add(fn)
                            # Extract leading SKU if filename is formatted like SKU_filename
                            if "_" in fn:
                                skus.add(fn.split("_")[0].strip())

    return ExistingIdentities(skus=skus, names=names, photos=photos)


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1: Akeneo Multi-Category Scraper (Newest to Oldest, Randomized Pool)
# ══════════════════════════════════════════════════════════════════════════

def scrape_single_new_row(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    *,
    style: str = "modern",
    execute: bool = True,
) -> str | None:
    """Scrape 1 new row across categories (newest with random variety) into Airtable."""
    records = airtable.list_records()
    existing_identities = collect_existing_identities(records)
    known_fields = airtable.table_fields()

    slot_picked: dict[int, tuple[dict[str, Any], ProductItem]] = {}

    for slot in SLOTS:
        query = {
            "categories": [{"operator": "IN", "value": [slot.akeneo_category]}],
            "Style2": [{"operator": "IN", "value": [style]}],
        }
        raw_items = akeneo.fetch_products(query)
        raw_items.sort(
            key=lambda x: str(x.get("updated") or x.get("created") or ""),
            reverse=True,
        )

        valid_items: list[tuple[dict[str, Any], ProductItem]] = []
        for raw in raw_items:
            item = product_item(raw)
            if not item:
                continue

            raw_name = str((raw.get("values", {}).get("name", [{}])[0].get("data")) or "").lower()
            combined_text = f"{item.item_name} {item.product_type} {item.sku} {raw_name}".lower()

            if slot.keyword_filter and slot.keyword_filter not in combined_text:
                continue
            if any(ex in combined_text for ex in slot.exclude_keywords):
                continue
            if item.sku in existing_identities.skus:
                continue
            if item.item_name.casefold() in existing_identities.names:
                continue
            if item.media_code.casefold() in existing_identities.photos:
                continue

            valid_items.append((raw, item))

        if not valid_items:
            if slot.skip_blending:
                continue
            print(f"  [WARN] No eligible new product found for Slot {slot.slot_index}: {slot.label}")
            return None

        # Sample randomly from top newest pool (up to top 20 items) for variety
        top_pool_size = min(20, len(valid_items))
        picked = random.choice(valid_items[:top_pool_size])
        slot_picked[slot.slot_index] = picked

    row_fields: dict[str, Any] = {STATUS_FIELD: STATUS_STANDBY}
    log_items: list[dict[str, Any]] = []

    print("\n--- Selected New Products for Row (Randomized from Newest Pool) ---")
    for slot in SLOTS:
        if slot.slot_index not in slot_picked:
            continue
        raw_item, item = slot_picked[slot.slot_index]
        full_name = str(first_attribute(raw_item, "name") or item.item_name).strip()
        row_fields[slot.item_name_field] = full_name
        log_items.append({
            "slot": slot.slot_index,
            "label": slot.label,
            "sku": item.sku,
            "name": full_name,
            "media_code": item.media_code,
        })
        print(f"  Slot {slot.slot_index} ({slot.label}): [{item.sku}] {full_name}")

    if not execute:
        print(f"  [DRY RUN] Would create Airtable record with fields: {list(row_fields.keys())}")
        return "dry_run_record_id"

    created_res = airtable.create_record(row_fields)
    record_id = created_res["id"] if isinstance(created_res, dict) else str(created_res)
    print(f"  [OK] Created Airtable record {record_id} with Status '{STATUS_STANDBY}'")

    for slot in SLOTS:
        if slot.slot_index not in slot_picked:
            continue
        raw_item, item = slot_picked[slot.slot_index]
        furniture_field_name = resolve_field_name(known_fields, slot.furniture_field_candidates)
        print(f"  Uploading {slot.label} photo for Slot {slot.slot_index}...")
        media_download = akeneo.download_media(item.media_code)
        airtable.upload_attachment(
            record_id,
            furniture_field_name,
            media_download.path,
            filename=f"{item.sku}_{Path(media_download.path).name}",
        )
        if hasattr(media_download, "cleanup"):
            media_download.cleanup()
        elif Path(media_download.path).exists():
            Path(media_download.path).unlink(missing_ok=True)

    append_audit_log(
        {
            "timestamp": pht_timestamp(),
            "record_id": record_id,
            "phase": "Phase 1: Akeneo Multi-Category Scrape (Newest to Oldest, Randomized)",
            "items": log_items,
            "status": STATUS_STANDBY,
        },
        AUDIT_LOG_AKENEO,
    )
    return record_id


def run_phase_1_scrape(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    *,
    style: str = "modern",
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Scrape products newest to oldest with random pool diversity into Airtable rows."""
    print("\n" + "=" * 70)
    print("PHASE 1: Akeneo Multi-Category Scrape (Newest to Oldest, Randomized Pool)")
    print(f"Target Table: {airtable.table_id} | Style: {style}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    # 1. Inspect existing Airtable records for deduplication
    print("[INFO] Fetching existing Airtable records for deduplication...")
    records = airtable.list_records()
    existing_identities = collect_existing_identities(records)
    print(f"[OK] Found {len(records)} existing record(s) with {len(existing_identities.names)} Name(s) / {len(existing_identities.photos)} Photo(s).")

    # 2. Fetch candidates for each category sorted by newest to oldest
    slot_candidates: dict[int, list[tuple[dict[str, Any], ProductItem]]] = {}
    for slot in SLOTS:
        print(f"\n[INFO] Fetching candidates for Slot {slot.slot_index}: {slot.label} ({slot.akeneo_category})...")
        query = {
            "categories": [{"operator": "IN", "value": [slot.akeneo_category]}],
            "Style2": [{"operator": "IN", "value": [style]}],
        }
        raw_items = akeneo.fetch_products(query)
        print(f"  Total raw products found in Akeneo: {len(raw_items)}")

        raw_items.sort(
            key=lambda x: str(x.get("updated") or x.get("created") or ""),
            reverse=True,
        )

        valid_items: list[tuple[dict[str, Any], ProductItem]] = []
        for raw in raw_items:
            item = product_item(raw)
            if not item:
                continue

            raw_name = str((raw.get("values", {}).get("name", [{}])[0].get("data")) or "").lower()
            combined_text = f"{item.item_name} {item.product_type} {item.sku} {raw_name}".lower()

            if slot.keyword_filter and slot.keyword_filter not in combined_text:
                continue
            if any(ex in combined_text for ex in slot.exclude_keywords):
                continue
            if item.sku in existing_identities.skus:
                continue
            if item.item_name.casefold() in existing_identities.names:
                continue
            if item.media_code.casefold() in existing_identities.photos:
                continue

            valid_items.append((raw, item))

        print(f"  Eligible new products available: {len(valid_items)}")
        slot_candidates[slot.slot_index] = valid_items

    # Eligible counts
    required_slots = [slot for slot in SLOTS if not slot.skip_blending]
    max_possible_rows = min(len(slot_candidates[slot.slot_index]) for slot in required_slots)
    if max_possible_rows == 0:
        print("\n[WARN] Not enough unique new products across all required categories to assemble a full row.")
        return True

    rows_to_create = max_possible_rows if max_rows is None else min(max_possible_rows, max_rows)
    print(f"\n[INFO] Assembling {rows_to_create} new row(s) (randomized newest pool)...")

    # Randomly shuffle candidates within the top newest pool for each slot
    for slot in SLOTS:
        if slot.slot_index not in slot_candidates or not slot_candidates[slot.slot_index]:
            continue
        pool_size = max(25, rows_to_create * 3)
        available = slot_candidates[slot.slot_index]
        top_pool = available[:min(pool_size, len(available))]
        rest = available[len(top_pool):]
        random.shuffle(top_pool)
        slot_candidates[slot.slot_index] = top_pool + rest

    known_fields = airtable.table_fields()
    created_count = 0

    for row_idx in range(rows_to_create):
        print(f"\n--- Assembling Row {row_idx + 1}/{rows_to_create} ---")
        row_fields: dict[str, Any] = {STATUS_FIELD: STATUS_STANDBY}
        log_items: list[dict[str, Any]] = []

        for slot in SLOTS:
            if slot.slot_index not in slot_candidates or len(slot_candidates[slot.slot_index]) <= row_idx:
                continue
            raw_item, item = slot_candidates[slot.slot_index][row_idx]
            furniture_field_name = resolve_field_name(known_fields, slot.furniture_field_candidates)
            item_name_field_name = slot.item_name_field

            full_name = str(first_attribute(raw_item, "name") or item.item_name).strip()

            row_fields[item_name_field_name] = full_name
            log_items.append({
                "slot": slot.slot_index,
                "label": slot.label,
                "sku": item.sku,
                "name": full_name,
                "media_code": item.media_code,
            })
            print(f"  Slot {slot.slot_index} ({slot.label}): [{item.sku}] {full_name}")

            existing_identities.skus.add(item.sku)
            existing_identities.names.add(item.item_name.casefold())
            existing_identities.photos.add(item.media_code.casefold())

        if not execute:
            print(f"  [DRY RUN] Would create Airtable record with fields: {list(row_fields.keys())}")
            continue

        created_res = airtable.create_record(row_fields)
        record_id = created_res["id"] if isinstance(created_res, dict) else str(created_res)
        print(f"  [OK] Created Airtable record {record_id} with Status '{STATUS_STANDBY}'")

        for slot in SLOTS:
            if slot.slot_index not in slot_candidates or len(slot_candidates[slot.slot_index]) <= row_idx:
                continue
            raw_item, item = slot_candidates[slot.slot_index][row_idx]
            furniture_field_name = resolve_field_name(known_fields, slot.furniture_field_candidates)

            print(f"  Uploading {slot.label} photo for Slot {slot.slot_index}...")
            media_download = akeneo.download_media(item.media_code)
            airtable.upload_attachment(
                record_id,
                furniture_field_name,
                media_download.path,
                filename=f"{item.sku}_{Path(media_download.path).name}",
            )
            if hasattr(media_download, "cleanup"):
                media_download.cleanup()
            elif Path(media_download.path).exists():
                Path(media_download.path).unlink(missing_ok=True)

        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 1: Akeneo Multi-Category Scrape (Newest to Oldest, Randomized)",
                "items": log_items,
                "status": STATUS_STANDBY,
            },
            AUDIT_LOG_AKENEO,
        )
        created_count += 1

    print(f"\n[OK] Phase 1 completed: {created_count} row(s) successfully created on Airtable.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2: Krea AI Sequential Interior Generation (9:16 Ratio)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_2_for_record(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Generate 5 sequential interior photos with dedicated moodboards & cumulative style referencing (9:16)."""
    print(f"\n[PHASE 2] Krea AI Sequential Interiors ({KREA_ASPECT_RATIO}) for Record: {record_id}")
    print(f"Aspect Ratio: {KREA_ASPECT_RATIO} | Style Ref Str: {KREA_STYLE_REF_STRENGTH}")

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})
    known_fields = airtable.table_fields()

    if execute:
        update_record_status(airtable, record_id, STATUS_PROCESSING)

    generated_urls: dict[int, str] = {}
    log_slots: list[dict[str, Any]] = []

    for slot in SLOTS:
        interior_field_name = resolve_field_name(known_fields, slot.interior_field_candidates)
        existing_interior = get_field_val(fields, slot.interior_field_candidates)

        if existing_interior:
            extracted = extract_attachment_url(existing_interior)
            if extracted:
                generated_urls[slot.slot_index] = extracted
                print(f"  Slot {slot.slot_index} ({slot.label}): Interior already present.")
                continue

        # Build cumulative style references list from previous slots (1 to slot.slot_index - 1)
        style_refs: list[dict[str, Any]] = []
        for prev_idx in range(1, slot.slot_index):
            if prev_idx in generated_urls:
                style_refs.append({
                    "url": generated_urls[prev_idx],
                    "strength": KREA_STYLE_REF_STRENGTH,
                })

        print(f"\n  [Slot {slot.slot_index}: {slot.label}]")
        print(f"    Moodboard ID: {slot.moodboard_id}")
        print(f"    Prompt: \"{slot.interior_prompt}\"")
        print(f"    Cumulative Style References: {len(style_refs)} image(s)")
        for s_idx, ref in enumerate(style_refs, 1):
            print(f"      Ref {s_idx}: {ref['url'][:60]}... (str={ref['strength']})")

        if not execute:
            print(f"    [DRY RUN] Would generate Krea interior for {interior_field_name} (9:16)")
            continue

        print(f"    Generating image via Krea AI (9:16)...")
        image_url = krea.generate(
            slot.interior_prompt,
            aspect_ratio=KREA_ASPECT_RATIO,
            resolution=KREA_RESOLUTION,
            moodboard_id=slot.moodboard_id,
            moodboard_strength=KREA_MOODBOARD_STRENGTH,
            style_references=style_refs,
        )
        print(f"    [OK] Generated image URL: {image_url}")
        generated_urls[slot.slot_index] = image_url

        print(f"    Uploading to Airtable field '{interior_field_name}'...")
        downloaded = krea.download_image(image_url)
        airtable.upload_attachment(
            record_id,
            interior_field_name,
            downloaded.path,
            filename=f"Interior{slot.slot_index}_{record_id}.jpg",
        )
        if hasattr(downloaded, "cleanup"):
            downloaded.cleanup()
        elif Path(downloaded.path).exists():
            Path(downloaded.path).unlink(missing_ok=True)

        log_slots.append({
            "slot": slot.slot_index,
            "label": slot.label,
            "moodboard_id": slot.moodboard_id,
            "prompt": slot.interior_prompt,
            "style_references_count": len(style_refs),
            "image_url": image_url,
            "target_field": interior_field_name,
        })

    if execute and log_slots:
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 2: Krea AI Sequential Interior Generation (9:16 Ratio)",
                "aspect_ratio": KREA_ASPECT_RATIO,
                "slots": log_slots,
            },
            AUDIT_LOG_KREA,
        )

    print(f"[OK] Phase 2 completed for {record_id}.")
    return True


def run_phase_2_krea(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Generate 5 sequential interior photos with dedicated moodboards across records (9:16)."""
    print("\n" + "=" * 70)
    print("PHASE 2: Krea AI Sequential Interior Generation (9:16 Ratio)")
    print(f"Aspect Ratio: {KREA_ASPECT_RATIO}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    records = airtable.list_records()
    targets = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("done", "complete"):
            continue
        if status not in (STATUS_STANDBY.casefold(), STATUS_PROCESSING.casefold()):
            continue

        has_all_interiors = all(
            get_field_val(fields, slot.interior_field_candidates) for slot in SLOTS
        )
        if not has_all_interiors:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing interior generation.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Interior1..5 generation.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Record {record_id} ---")
        run_phase_2_for_record(krea, airtable, record_id, execute=execute)

    print("\n[OK] Phase 2 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3: Claude Sonnet 5 Prompt Analysis (via Fal AI, Slots 2..5)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_3_for_record(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Analyze Interior and Furniture Item pairs (Slots 2..5) and generate blending prompts using Claude Sonnet 5 via Fal AI."""
    print(f"\n[PHASE 3] Claude Sonnet 5 Prompt Analysis (via Fal AI) for Record: {record_id}")
    print(f"Model       : {FAL_VISION_MODEL}")
    print(f"Mode        : {'EXECUTE' if execute else 'DRY RUN'}")

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})

    if execute:
        update_record_status(airtable, record_id, STATUS_PROCESSING)

    phase_start = time.monotonic()
    prompt_updates: dict[str, str] = {}
    log_updates: dict[str, Any] = {}

    for slot in SLOTS:
        if slot.skip_blending:
            print(f"  Slot {slot.slot_index} ({slot.label}): Unblended pure interior photo, skipping prompt generation.")
            continue

        existing_prompt = fields.get(slot.blending_prompt_field)
        if existing_prompt:
            print(f"  Slot {slot.slot_index} ({slot.label}): Prompt already populated.")
            continue

        interior_val = get_field_val(fields, slot.interior_field_candidates)
        interior_url = extract_attachment_url(interior_val)

        furniture_val = get_field_val(fields, slot.furniture_field_candidates)
        furniture_url = extract_attachment_url(furniture_val)

        item_name = str(fields.get(slot.item_name_field) or slot.label).strip()

        if not interior_url or not furniture_url:
            print(f"  [WARN] Slot {slot.slot_index} ({slot.label}): Missing interior or furniture image. Skipping slot.")
            continue

        print(f"\n  [{slot.slot_index}/5] Analyzing Interior{slot.slot_index} + {slot.label} ('{item_name}') via {FAL_VISION_MODEL}...")

        if not execute:
            print(f"    [DRY RUN] Would generate prompt for {slot.blending_prompt_field}")
            continue

        instruction = (
            f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
            f"and Image 2 as the product photo for '{item_name}' ({slot.label}).\n\n"
            f"Create a highly detailed, clean, photorealistic image blending prompt that places, mounts, and seamlessly "
            f"integrates the exact {slot.label} '{item_name}' from Image 2 naturally into Image 1 in a vertical 9:16 composition.\n\n"
            f"CRITICAL PRODUCT ISOLATION & INTEGRATION RULES:\n"
            f"1. The product shown in Image 2 MUST BE THE ONLY LIGHTING FIXTURE of its type in the designated spot in the final scene.\n"
            f"2. If Image 1 contains ANY pre-existing competing light fixtures or placeholder lamps, "
            f"EXPLICITLY INSTRUCT TO REMOVE AND REPLACE THEM so that ONLY the product from Image 2 is installed.\n"
            f"3. Strictly exclude unnecessary, extra, competing furniture items, duplicate fixtures, or clutter.\n"
            f"4. Ensure realistic positioning, accurate mounting/standing height, authentic warm illumination, "
            f"soft downward/ambient glow, natural contact shadows, and architectural surface reflections.\n\n"
            f"Output ONLY the final image generation prompt text, with no preamble or markdown quotes."
        )

        slot_start = time.monotonic()
        try:
            raw_prompt = fal.generate_vision_prompt(
                [interior_url, furniture_url],
                instruction,
                model=FAL_VISION_MODEL,
            )
            clean_prompt = raw_prompt.strip().strip('"').strip("'")
            slot_duration = round(time.monotonic() - slot_start, 2)
            prompt_updates[slot.blending_prompt_field] = clean_prompt
            log_updates[slot.blending_prompt_field] = {
                "slot": slot.slot_index,
                "label": slot.label,
                "item_name": item_name,
                "prompt": clean_prompt,
                "model": FAL_VISION_MODEL,
                "duration_seconds": slot_duration,
            }
            print(f"    [OK] Prompt generated in {slot_duration}s ({len(clean_prompt)} chars): {clean_prompt[:60]}...")
        except Exception as err:
            print(f"    [ERROR] Claude vision prompt failed for Slot {slot.slot_index}: {err}")
            raise

    if execute and prompt_updates:
        total_duration = round(time.monotonic() - phase_start, 2)
        airtable.update_records([(record_id, prompt_updates)])
        print(f"  [OK] Saved {len(prompt_updates)} prompt(s) to Airtable record {record_id}")
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 3: Claude Sonnet 5 Prompt Analysis (via Fal AI)",
                "model": FAL_VISION_MODEL,
                "duration_seconds": total_duration,
                "prompts": log_updates,
            },
            AUDIT_LOG_CLAUDE,
        )

    print(f"[OK] Phase 3 completed for {record_id}.")
    return True


def run_phase_3_prompts(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Analyze Interior and Furniture Item pairs (Slots 2..5) across records."""
    print("\n" + "=" * 70)
    print("PHASE 3: Claude Sonnet 5 Blending Prompt Analysis (via Fal AI)")
    print(f"Model: {FAL_VISION_MODEL}")
    print(f"Mode : {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    records = airtable.list_records()
    targets = []
    blended_slots = [s for s in SLOTS if not s.skip_blending]

    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("done", "complete"):
            continue
        if status not in (STATUS_STANDBY.casefold(), STATUS_PROCESSING.casefold()):
            continue

        has_all_prompts = all(
            bool(fields.get(slot.blending_prompt_field)) for slot in blended_slots
        )
        if not has_all_prompts:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing blending prompts.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Blending Prompts.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Record {record_id} ---")
        run_phase_3_for_record(fal, airtable, record_id, execute=execute)

    print("\n[OK] Phase 3 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4: Fal AI Nano Banana Pro Blending (9:16 Ratio, 1K Quality, Slots 2..5)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_4_for_record(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Blend products 2..5 into interior scenes using Fal AI Nano Banana Pro at 9:16 ratio (1K) for a specific record."""
    print(f"\n[PHASE 4] Fal AI Nano Banana Pro Blending ({BLENDING_ASPECT_RATIO}, {BLENDING_RESOLUTION}) for Record: {record_id}")
    print(f"Model       : {FAL_BLENDING_MODEL}")
    print(f"Mode        : {'EXECUTE' if execute else 'DRY RUN'}")

    if execute:
        required_fields = {
            "Blended Image1": "multipleAttachments",
            "Blended Image2": "multipleAttachments",
            "Blended Image3": "multipleAttachments",
            "Blended Image4": "multipleAttachments",
            "Blended Image5": "multipleAttachments",
        }
        airtable.ensure_fields(required_fields)
        update_record_status(airtable, record_id, STATUS_PROCESSING)

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})
    known_fields = airtable.table_fields()

    phase_start = time.monotonic()
    blended_log_entries: list[dict[str, Any]] = []
    all_slots_succeeded = True

    for slot in SLOTS:
        if slot.skip_blending:
            print(f"  Slot {slot.slot_index} ({slot.label}): Unblended pure interior photo, skipping blending phase.")
            continue

        blended_field_name = resolve_field_name(known_fields, slot.blended_image_field_candidates)
        existing_blended = get_field_val(fields, slot.blended_image_field_candidates)
        if existing_blended:
            print(f"  Slot {slot.slot_index} ({slot.label}): Already has blended image.")
            continue

        interior_val = get_field_val(fields, slot.interior_field_candidates)
        interior_url = extract_attachment_url(interior_val)

        furniture_val = get_field_val(fields, slot.furniture_field_candidates)
        furniture_url = extract_attachment_url(furniture_val)

        prompt_raw = str(fields.get(slot.blending_prompt_field) or "").strip()

        if not interior_url or not furniture_url or not prompt_raw:
            print(f"  [WARN] Slot {slot.slot_index} ({slot.label}): Missing interior, furniture, or prompt. Cannot blend.")
            all_slots_succeeded = False
            continue

        blending_prompt = prompt_raw
        try:
            parsed_json = json.loads(prompt_raw)
            if isinstance(parsed_json, dict) and "final_blending_prompt" in parsed_json:
                blending_prompt = parsed_json["final_blending_prompt"]
        except Exception:
            pass

        item_name = str(fields.get(slot.item_name_field) or slot.label).strip()
        print(f"\n  [{slot.slot_index}/5] Blending {slot.label} ('{item_name}') into Interior{slot.slot_index} via {FAL_BLENDING_MODEL} (9:16)...")
        print(f"    Target Field: {blended_field_name}")

        if not execute:
            print(f"    [DRY RUN] Would blend image using {FAL_BLENDING_MODEL} ({BLENDING_ASPECT_RATIO}, {BLENDING_RESOLUTION})")
            continue

        slot_start = time.monotonic()
        try:
            print(f"    Sending image blending request to Fal AI Nano Banana Pro...")
            blended_url = fal.generate(
                blending_prompt,
                [interior_url, furniture_url],
                aspect_ratio=BLENDING_ASPECT_RATIO,
                resolution=BLENDING_RESOLUTION,
                model=FAL_BLENDING_MODEL,
            )
            print(f"    [OK] Blended image generated: {blended_url}")

            # Download & convert to standard JPEG
            temp_dest = Path("output") / "temp" / f"blended_{slot.slot_index}_{record_id}.jpg"
            downloaded = fal.download_jpeg(blended_url, temp_dest)
            slot_duration = round(time.monotonic() - slot_start, 2)

            print(f"    Uploading to Airtable field '{blended_field_name}' in {slot_duration}s...")
            airtable.upload_attachment(
                record_id,
                blended_field_name,
                str(downloaded.path),
                filename=f"Blended_Image{slot.slot_index}_{record_id}.jpg",
            )
            if hasattr(downloaded, "cleanup"):
                downloaded.cleanup()
            elif Path(downloaded.path).exists():
                Path(downloaded.path).unlink(missing_ok=True)

            blended_log_entries.append({
                "slot": slot.slot_index,
                "label": slot.label,
                "target_field": blended_field_name,
                "image_url": blended_url,
                "aspect_ratio": BLENDING_ASPECT_RATIO,
                "resolution": BLENDING_RESOLUTION,
                "duration_seconds": slot_duration,
            })
        except Exception as err:
            print(f"    [ERROR] Failed blending Slot {slot.slot_index}: {err}")
            all_slots_succeeded = False

    if execute and blended_log_entries:
        total_duration = round(time.monotonic() - phase_start, 2)
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 4: Fal AI Nano Banana Pro Blending (9:16 Ratio, 1K Quality)",
                "model": FAL_BLENDING_MODEL,
                "aspect_ratio": BLENDING_ASPECT_RATIO,
                "resolution": BLENDING_RESOLUTION,
                "duration_seconds": total_duration,
                "slots": blended_log_entries,
            },
            AUDIT_LOG_FAL,
        )

    print(f"[OK] Phase 4 completed for {record_id}.")
    return all_slots_succeeded


def run_phase_4_blend(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Blend products 2..5 into interior scenes across records using Fal AI Nano Banana Pro at 9:16 ratio."""
    print("\n" + "=" * 70)
    print("PHASE 4: Fal AI Nano Banana Pro Blending (9:16 Ratio, 1K Quality)")
    print(f"Model: {FAL_BLENDING_MODEL} | Aspect Ratio: {BLENDING_ASPECT_RATIO} | Quality: {BLENDING_RESOLUTION}")
    print(f"Mode : {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    records = airtable.list_records()
    targets = []
    blended_slots = [s for s in SLOTS if not s.skip_blending]

    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("done", "complete"):
            continue
        if status not in (STATUS_STANDBY.casefold(), STATUS_PROCESSING.casefold()):
            continue

        has_all_blended = all(
            get_field_val(fields, slot.blended_image_field_candidates) for slot in blended_slots
        )
        if not has_all_blended:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing image blending.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Blended Images.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Blending Record {record_id} ---")
        run_phase_4_for_record(fal, airtable, record_id, execute=execute)

    print("\n[OK] Phase 4 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 5: Style Reel Slideshow MP4 Video Generation (3s Slide 1 + 2s Slides 2..5)
# ══════════════════════════════════════════════════════════════════════════

def build_style_reel_slideshow_video(
    slide_image_paths: list[Path | str],
    output_mp4_path: Path,
    *,
    outro_image_path: Path | str | None = None,
    first_slide_duration: float = SLIDE_1_DURATION,
    subsequent_slide_duration: float = SLIDE_NEXT_DURATION,
    outro_duration: float = OUTRO_DURATION,
    fade_duration: float = FADE_DURATION,
    width: int = SLIDESHOW_WIDTH,
    height: int = SLIDESHOW_HEIGHT,
    fps: int = SLIDESHOW_FPS,
) -> Path:
    """Build a 9:16 vertical H.264 MP4 slideshow video reel.

    Slide 1 (Slot 1 Interior1): 3.0s duration.
    Slides 2-5 (Slots 2..5 Blended Images): 2.0s duration each.
    Slide 6 ('Outro' if present): 3.0s duration, with a 1.0s Fade to Black transition before Outro.
    """
    output_mp4_path.parent.mkdir(parents=True, exist_ok=True)
    temp_raw = output_mp4_path.with_name(f"raw_{output_mp4_path.name}")

    has_outro = outro_image_path is not None and Path(outro_image_path).is_file()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_raw), fourcc, fps, (width, height))

    try:
        total_slides = len(slide_image_paths)
        for idx, img_path in enumerate(slide_image_paths, start=1):
            path_obj = Path(img_path)
            if not path_obj.is_file():
                raise FileNotFoundError(f"Slide image not found: {path_obj}")

            duration = first_slide_duration if idx == 1 else subsequent_slide_duration
            num_frames = int(duration * fps)

            with Image.open(path_obj) as pil_img:
                pil_img = pil_img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
                frame_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

                # Check if this is the last main slide before Outro (apply 1s Fade-to-Black)
                is_last_main = has_outro and (idx == total_slides)
                if is_last_main:
                    fade_frames = int(fade_duration * fps)
                    normal_frames = max(0, num_frames - fade_frames)
                    for _ in range(normal_frames):
                        writer.write(frame_bgr)
                    # Fade out to black over fade_frames
                    for i in range(fade_frames):
                        factor = 1.0 - (i / max(1, fade_frames))
                        faded = (frame_bgr.astype(np.float32) * factor).astype(np.uint8)
                        writer.write(faded)
                else:
                    for _ in range(num_frames):
                        writer.write(frame_bgr)

        # 2. Write Outro slide (3.0s duration) if present
        if has_outro:
            with Image.open(outro_image_path) as outro_pil:
                outro_pil = outro_pil.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
                outro_bgr = cv2.cvtColor(np.array(outro_pil), cv2.COLOR_RGB2BGR)

                outro_num_frames = int(outro_duration * fps)
                fade_in_frames = int(0.5 * fps)
                # Fade in from black for 0.5s
                for i in range(fade_in_frames):
                    factor = i / max(1, fade_in_frames)
                    faded_in = (outro_bgr.astype(np.float32) * factor).astype(np.uint8)
                    writer.write(faded_in)

                # Rest of outro duration
                for _ in range(max(0, outro_num_frames - fade_in_frames)):
                    writer.write(outro_bgr)
    finally:
        writer.release()

    # Re-encode to standard H.264 MP4 via FFmpeg with yuv420p for universal browser & device playback
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(temp_raw),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_mp4_path),
    ]

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if temp_raw.exists():
        try:
            temp_raw.unlink(missing_ok=True)
        except Exception:
            pass

    if completed.returncode != 0:
        raise AutomationError(f"FFmpeg slideshow encoding failed: {completed.stderr}")

    return output_mp4_path


def run_phase_5_for_record(
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    fal: FalClient | None = None,
    execute: bool = True,
) -> bool:
    """Download 5 photos (Interior 1 with Centered Poppins Text + Blended Images 2..5) + optional Outro, and assemble 9:16 slideshow video into 'Style Reel Slideshow'."""
    print(f"\n[PHASE 5] Style Reel Slideshow Video (9:16 MP4, 3s Slide 1 + 2s Slides 2..5 + Outro) for Record: {record_id}")

    if execute:
        airtable.ensure_fields({SLIDESHOW_FIELD: "multipleAttachments"})
        update_record_status(airtable, record_id, STATUS_PROCESSING)

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})
    known_fields = airtable.table_fields()
    slideshow_field_name = resolve_field_name(known_fields, SLIDESHOW_FIELD_CANDIDATES)

    existing_slideshow = get_field_val(fields, SLIDESHOW_FIELD_CANDIDATES)
    if existing_slideshow:
        print(f"  Record {record_id} already has a slideshow video attached in '{slideshow_field_name}'.")
        if execute:
            update_record_status(airtable, record_id, STATUS_DONE)
        return True

    # Gather the 5 slide image URLs:
    # Slide 1: Slot 1 Interior (Interior1)
    # Slides 2..5: Slots 2..5 Blended Images (Blended Image2..5)
    slide_urls: list[tuple[int, str, str]] = []

    # Slide 1 (Interior 1)
    slot1 = SLOTS[0]
    int1_val = get_field_val(fields, slot1.interior_field_candidates)
    int1_url = extract_attachment_url(int1_val)
    if not int1_url:
        print(f"  [ERROR] Missing Interior1 for Slide 1 on record {record_id}.")
        return False
    slide_urls.append((1, slot1.label, int1_url))

    # Slides 2..5 (Blended Images)
    for slot in SLOTS[1:]:
        blended_val = get_field_val(fields, slot.blended_image_field_candidates)
        blended_url = extract_attachment_url(blended_val)
        if not blended_url:
            print(f"  [ERROR] Missing Blended Image for Slot {slot.slot_index} ({slot.label}) on record {record_id}.")
            return False
        slide_urls.append((slot.slot_index, slot.label, blended_url))

    # Check for Outro image attachment
    outro_val = get_field_val(fields, OUTRO_FIELD_CANDIDATES)
    outro_url = extract_attachment_url(outro_val)

    # Determine Title Text for Centered Poppins Text Overlay on Slide 1
    title_text = str(get_field_val(fields, TITLE_FIELD_CANDIDATES) or "").strip()
    if not title_text and fal is not None:
        try:
            item_names = [str(fields.get(s.item_name_field) or "").strip() for s in SLOTS if fields.get(s.item_name_field)]
            title_text = generate_slideshow_title_prompt(fal, int1_url, item_names=item_names)
            print(f"  [OK] Generated Reel Title via Claude: '{title_text}'")
            if execute:
                title_field_name = resolve_field_name(known_fields, TITLE_FIELD_CANDIDATES)
                if title_field_name in known_fields:
                    airtable.update_records([(record_id, {title_field_name: title_text})])
        except Exception as t_err:
            print(f"  [WARN] Failed generating title via Claude: {t_err}")
    if not title_text:
        title_text = "5 Modern Lighting Styles"

    print(f"  Found all {len(slide_urls)} main slide images for slideshow assembly:")
    for idx, label, url in slide_urls:
        dur = SLIDE_1_DURATION if idx == 1 else SLIDE_NEXT_DURATION
        note = f" (Centered Poppins Text: '{title_text}')" if idx == 1 else ""
        print(f"    Slide {idx} ({label}){note}: {dur}s | {url[:60]}...")
    if outro_url:
        print(f"    Outro Slide: {OUTRO_DURATION}s (1.0s fade to black) | {outro_url[:60]}...")
    else:
        print("    Outro Slide: None attached (proceeding with 5 main slides only)")

    if not execute:
        print(f"  [DRY RUN] Would build and upload {SLIDESHOW_WIDTH}x{SLIDESHOW_HEIGHT} MP4 slideshow video to '{slideshow_field_name}'")
        return True

    phase_start = time.monotonic()
    temp_dir = Path("output") / "temp" / f"slideshow_{record_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing pre-rendered thumbnail with text
    existing_thumb_val = get_field_val(fields, THUMBNAIL_FIELD_CANDIDATES)
    existing_thumb_url = extract_attachment_url(existing_thumb_val)

    downloaded_slide_paths: list[Path] = []
    for idx, label, url in slide_urls:
        dest = temp_dir / f"slide_{idx}_{record_id}.jpg"
        if idx == 1:
            if existing_thumb_url:
                try:
                    resp = requests.get(existing_thumb_url, timeout=60, stream=True)
                    if resp.ok:
                        with open(dest, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=65536):
                                f.write(chunk)
                        downloaded_slide_paths.append(dest)
                        print(f"  [OK] Downloaded existing '{resolve_field_name(known_fields, THUMBNAIL_FIELD_CANDIDATES)}' for Slide 1")
                        continue
                except Exception as t_dl_err:
                    print(f"  [WARN] Failed downloading existing thumbnail, re-generating: {t_dl_err}")

            # Download raw Interior1, apply centered Poppins text & dimming
            resp = requests.get(url, timeout=60, stream=True)
            if not resp.ok:
                raise ProviderError(f"Failed downloading slide 1 image from {url}: status {resp.status_code}")
            raw_int1_dest = temp_dir / f"raw_int1_{record_id}.jpg"
            with open(raw_int1_dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)

            with Image.open(raw_int1_dest) as pil_int1:
                thumb_pil = overlay_centered_poppins_text(
                    pil_int1,
                    title_text,
                    font_style=POPPINS_FONT_STYLE,
                    dim_factor=DIM_BRIGHTNESS_FACTOR,
                )
                thumb_pil.save(dest, format="JPEG", quality=95)
                print(f"  [OK] Rendered Centered Poppins Text ('{title_text}') onto Slide 1")

            # Try uploading generated thumbnail to Airtable if thumbnail field exists
            thumb_field_name = resolve_field_name(known_fields, THUMBNAIL_FIELD_CANDIDATES)
            if thumb_field_name in known_fields:
                try:
                    airtable.upload_attachment(
                        record_id,
                        thumb_field_name,
                        str(dest),
                        filename=f"Thumbnail_{record_id}.jpg",
                    )
                    print(f"  [OK] Attached centered Poppins text thumbnail to '{thumb_field_name}' on Airtable")
                except Exception as up_err:
                    print(f"  [WARN] Could not upload thumbnail attachment to '{thumb_field_name}': {up_err}")

            if raw_int1_dest.exists():
                try:
                    raw_int1_dest.unlink(missing_ok=True)
                except Exception:
                    pass

            downloaded_slide_paths.append(dest)
        else:
            resp = requests.get(url, timeout=60, stream=True)
            if not resp.ok:
                raise ProviderError(f"Failed downloading slide {idx} image from {url}: status {resp.status_code}")
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            downloaded_slide_paths.append(dest)

    downloaded_outro_path: Path | None = None
    if outro_url:
        try:
            dest_outro = temp_dir / f"outro_{record_id}.jpg"
            outro_resp = requests.get(outro_url, timeout=60, stream=True)
            if outro_resp.ok:
                with open(dest_outro, "wb") as f:
                    for chunk in outro_resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                downloaded_outro_path = dest_outro
                print(f"  [OK] Downloaded Outro slide photo for record {record_id}")
            else:
                print(f"  [WARN] Failed downloading Outro photo (HTTP {outro_resp.status_code}), continuing without outro.")
        except Exception as outro_err:
            print(f"  [WARN] Outro download error for record {record_id}: {outro_err}")

    output_video_path = Path("output") / "videos" / f"style_reel_slideshow_{record_id}.mp4"
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    expected_dur = SLIDE_1_DURATION + (len(slide_urls) - 1) * SLIDE_NEXT_DURATION + (OUTRO_DURATION if downloaded_outro_path else 0.0)
    print(f"\n  Assembling 9:16 MP4 slideshow video ({expected_dur}s total)...")
    actual_video_path = build_style_reel_slideshow_video(
        downloaded_slide_paths,
        output_video_path,
        outro_image_path=downloaded_outro_path,
        first_slide_duration=SLIDE_1_DURATION,
        subsequent_slide_duration=SLIDE_NEXT_DURATION,
        outro_duration=OUTRO_DURATION,
        fade_duration=FADE_DURATION,
        width=SLIDESHOW_WIDTH,
        height=SLIDESHOW_HEIGHT,
        fps=SLIDESHOW_FPS,
    )
    video_size_mb = round(actual_video_path.stat().st_size / (1024 * 1024), 2)
    print(f"  [OK] Video generated successfully: {actual_video_path.name} ({video_size_mb} MB)")

    print(f"  Uploading video to Airtable field '{slideshow_field_name}'...")
    airtable.upload_attachment(
        record_id,
        slideshow_field_name,
        str(actual_video_path),
        filename=f"Style_Reel_Slideshow_{record_id}.mp4",
    )

    # Cleanup temp slide frames
    for p in downloaded_slide_paths:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
    if downloaded_outro_path:
        try:
            downloaded_outro_path.unlink(missing_ok=True)
        except Exception:
            pass

    total_duration = round(time.monotonic() - phase_start, 2)
    append_audit_log(
        {
            "timestamp": pht_timestamp(),
            "record_id": record_id,
            "phase": "Phase 5: Style Reel Slideshow MP4 Video Generation",
            "title_text": title_text,
            "video_path": str(actual_video_path),
            "video_size_mb": video_size_mb,
            "target_field": slideshow_field_name,
            "has_outro": downloaded_outro_path is not None,
            "slideshow_duration_seconds": expected_dur,
            "duration_seconds": total_duration,
        },
        AUDIT_LOG_SLIDESHOW,
    )

    update_record_status(airtable, record_id, STATUS_DONE)
    print(f"  [OK] Slideshow video attached. Updated record {record_id} Status -> '{STATUS_DONE}'")
    print(f"[OK] Phase 5 completed for {record_id}.")
    return True


def run_phase_5_slideshow(
    airtable: ScrapeAirtableClient,
    *,
    fal: FalClient | None = None,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Generate Style Reel Slideshow MP4 videos across records."""
    print("\n" + "=" * 70)
    print("PHASE 5: Style Reel Slideshow MP4 Video Generation (3s Slide 1 + 2s Slides 2..5)")
    print(f"Target Field: '{SLIDESHOW_FIELD}' (9:16 Video, {SLIDESHOW_WIDTH}x{SLIDESHOW_HEIGHT})")
    print(f"Mode        : {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    records = airtable.list_records()
    targets = []
    blended_slots = [s for s in SLOTS if not s.skip_blending]

    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("done", "complete"):
            continue

        existing_slideshow = get_field_val(fields, SLIDESHOW_FIELD_CANDIDATES)
        if existing_slideshow:
            continue

        has_interior1 = bool(get_field_val(fields, SLOTS[0].interior_field_candidates))
        has_all_blended = all(
            bool(get_field_val(fields, slot.blended_image_field_candidates)) for slot in blended_slots
        )

        if has_interior1 and has_all_blended:
            targets.append(record)

    if not targets:
        print("[OK] No records found ready for slideshow generation.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) ready for Style Reel Slideshow generation.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Slideshow for Record {record_id} ---")
        run_phase_5_for_record(airtable, record_id, fal=fal, execute=execute)

    print("\n[OK] Phase 5 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# CONTINUOUS ROW-BY-ROW PIPELINE (Phase 1 -> 2 -> 3 -> 4 -> 5 -> Next Row)
# ══════════════════════════════════════════════════════════════════════════

def run_continuous_row_pipeline(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    krea: KreaClient,
    fal: FalClient,
    *,
    style: str = "modern",
    max_rows: int | None = None,
    execute: bool = True,
) -> bool:
    """Execute complete end-to-end pipeline (Phases 1 to 5) row by row continuously."""
    print("\n" + "=" * 70)
    print(" CONTINUOUS STYLE REEL SLIDESHOW PIPELINE (ROW-BY-ROW)")
    print(f" Target Table   : {airtable.table_id}")
    print(f" Krea Ratio     : {KREA_ASPECT_RATIO} ({KREA_RESOLUTION})")
    print(f" Vision Model   : {FAL_VISION_MODEL} (via Fal AI)")
    print(f" Blend Model    : {FAL_BLENDING_MODEL} ({BLENDING_ASPECT_RATIO}, {BLENDING_RESOLUTION})")
    print(f" Slideshow Reel : 3s Slide 1 + 2s Slides 2..5 -> '{SLIDESHOW_FIELD}'")
    print(f" Mode           : {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    processed_rows = 0

    while True:
        if max_rows is not None and processed_rows >= max_rows:
            print(f"\n[OK] Reached target limit of {max_rows} row(s). Pipeline completed.")
            break

        # Step 1: Check for any existing unfinished row in Airtable (Status != 'Done')
        records = airtable.list_records()
        unfinished_record = None
        for r in records:
            st = str(r.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold()
            if st in ("done", "complete"):
                continue
            if st in (STATUS_STANDBY.casefold(), STATUS_PROCESSING.casefold(), ""):
                unfinished_record = r
                break

        if unfinished_record:
            rec_id = unfinished_record["id"]
            print(f"\n{'=' * 70}")
            print(f"[ROW {processed_rows + 1}] Resuming existing unfinished record: {rec_id}")
            print(f"{'=' * 70}")

            # Phase 2: Krea Interiors (9:16 dedicated moodboards & cumulative style refs)
            run_phase_2_for_record(krea, airtable, rec_id, execute=execute)

            # Phase 3: Claude Sonnet 5 Prompts via Fal AI (Slots 2..5)
            run_phase_3_for_record(fal, airtable, rec_id, execute=execute)

            # Phase 4: Fal AI Nano Banana Pro Blending (9:16 Ratio, 1K Quality, Slots 2..5)
            run_phase_4_for_record(fal, airtable, rec_id, execute=execute)

            # Phase 5: Style Reel Slideshow Video Generation (3s Slide 1 + 2s Slides 2..5 -> sets Status = 'Done')
            run_phase_5_for_record(airtable, rec_id, fal=fal, execute=execute)

            processed_rows += 1
            print(f"\n[DONE] Row {processed_rows} ({rec_id}) is completely finished and marked 'Done'!")
            print("Resetting and proceeding to next row...\n")
            continue

        # Step 2: If no unfinished row exists, scrape 1 new row from Akeneo (Newest with random pool selection)
        print(f"\n{'=' * 70}")
        print(f"[ROW {processed_rows + 1}] Scraping 1 new row from Akeneo across categories...")
        print(f"{'=' * 70}")

        new_rec_id = scrape_single_new_row(
            akeneo,
            airtable,
            style=style,
            execute=execute,
        )

        if not new_rec_id:
            print("\n[INFO] No more eligible unique products in Akeneo. Pipeline completed.")
            break

        if not execute:
            print(f"[DRY RUN] Finished row cycle simulation.")
            processed_rows += 1
            continue

        # Step 3: Phase 2 for this new row
        run_phase_2_for_record(krea, airtable, new_rec_id, execute=execute)

        # Step 4: Phase 3 for this new row
        run_phase_3_for_record(fal, airtable, new_rec_id, execute=execute)

        # Step 5: Phase 4 for this new row
        run_phase_4_for_record(fal, airtable, new_rec_id, execute=execute)

        # Step 6: Phase 5 for this new row
        run_phase_5_for_record(airtable, new_rec_id, fal=fal, execute=execute)

        processed_rows += 1
        print(f"\n[DONE] Row {processed_rows} ({new_rec_id}) is completely finished and marked 'Done'!")
        print("Resetting and proceeding to next row...\n")

    return True


# ══════════════════════════════════════════════════════════════════════════
# Master Runner & CLI
# ══════════════════════════════════════════════════════════════════════════

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Style Reel Slideshow (5 Interiors, 4 Blended Products, 9:16 Video Reel) Complete Automation Pipeline"
    )
    parser.add_argument(
        "--phase",
        "-p",
        choices=["1", "2", "3", "4", "5", "all"],
        default="all",
        help="Phase to execute (1: Scrape, 2: Krea 9:16, 3: Claude Prompts, 4: Fal Blend 9:16, 5: Slideshow Video, all: Continuous Row-by-Row Pipeline). Default: all",
    )
    parser.add_argument(
        "--table-id",
        default=DEFAULT_TABLE_ID,
        help=f"Airtable destination table ID (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--style",
        default="modern",
        help="Akeneo style filter (default: modern)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        metavar="N",
        help="Maximum rows to process (default: all available)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode without making live API generation or Airtable write calls",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=True,
        help="Execute write operations and API calls (default: True)",
    )
    parser.add_argument(
        "--menu",
        action="store_true",
        help="Display interactive phase selection menu",
    )
    return parser.parse_args(argv)


def interactive_menu() -> tuple[str, bool]:
    """Display CLI interactive menu when explicitly requested."""
    print("=" * 70)
    print(" STYLE REEL SLIDESHOW AUTOMATION PIPELINE (tblFFEvkHb3jLKrcv)")
    print("=" * 70)
    print("Select a phase to run:")
    print("  [1] Phase 1: Akeneo Multi-Category Scrape (Newest to Oldest, Randomized Pool)")
    print("  [2] Phase 2: Krea AI Sequential Interior Generation (9:16 Dedicated Moodboards)")
    print("  [3] Phase 3: Claude Sonnet 5 Blending Prompt Analysis (via Fal AI, Slots 2..5)")
    print("  [4] Phase 4: Fal AI Nano Banana Pro Blending (9:16 Ratio, 1K Quality, Slots 2..5)")
    print("  [5] Phase 5: Style Reel Slideshow MP4 Video (3s Slide 1 + 2s Slides 2..5)")
    print("  [6] Run Complete Continuous Row Pipeline (Phase 1 -> 2 -> 3 -> 4 -> 5 -> Next Row)")
    print("  [Q] Quit")
    print("-" * 70)

    choice = input("Enter choice (1-6 or Q) [default: 6]: ").strip().upper()
    if choice in ("Q", "QUIT", "EXIT"):
        sys.exit(0)

    phase_map = {
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
        "5": "5",
        "6": "all",
        "": "all",
    }
    selected_phase = phase_map.get(choice, "all")

    exec_input = input("Execute writes and API calls? (Y/n) [default: Y]: ").strip().lower()
    execute = exec_input not in ("n", "no", "false", "0")

    return selected_phase, execute


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.menu:
        phase, execute = interactive_menu()
    else:
        phase = args.phase or "all"
        execute = False if args.dry_run else True

    # Load project settings
    settings = load_settings()

    channel_name = os.getenv("CHANNEL_NAME") or "home_cartel"
    table_id = args.table_id or DEFAULT_TABLE_ID

    fal_key = settings.fal_key or os.getenv("FAL_KEY", "").strip() or os.getenv("FAL_API_KEY", "").strip()

    # Initialize clients
    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=channel_name,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )
    krea = KreaClient(
        token=settings.krea_token,
        base_url=settings.krea_base_url,
    )
    fal = FalClient(
        api_key=fal_key,
    )

    print(f"\n[START] Style Reel Slideshow Pipeline | Table: {table_id} | Phase: {phase.upper()} | Execute: {execute}")

    # Continuous row-by-row pipeline
    if phase == "all":
        run_continuous_row_pipeline(
            akeneo,
            airtable,
            krea,
            fal,
            style=args.style,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "1":
        run_phase_1_scrape(
            akeneo,
            airtable,
            style=args.style,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "2":
        run_phase_2_krea(
            krea,
            airtable,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "3":
        run_phase_3_prompts(
            fal,
            airtable,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "4":
        run_phase_4_blend(
            fal,
            airtable,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "5":
        run_phase_5_slideshow(
            airtable,
            fal=fal,
            max_rows=args.max_rows,
            execute=execute,
        )

    print("\n" + "=" * 70)
    print(" [DONE] Pipeline execution completed successfully!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AutomationError as error:
        print(f"\n[FATAL] {error}", file=sys.stderr)
        sys.exit(2)
