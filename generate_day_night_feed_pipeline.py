"""Chandelier Day & Night Feed (4:5 Ratio) AI Generation & Blending Pipeline.

This pipeline is DEDICATED SOLELY to Day & Night FEEDS (4:5 Ratio) and is completely
independent and separated from Day & Night Story scripts.

Target Table:
    Table ID:   tblSceuLVvLMQ6wWp ("Day and Night Feed Chandelier")
    Category:   chandeliers (Modern Chandeliers)
    Ratio:      4:5 (Standard Feed Ratio)
    Moodboard:  b5ffdcbb-192e-4528-8d86-d1a4cf496887

Phases (Sequential, Row-by-Row):
    0. Akeneo Product Scraping (1 chandelier per row)      -> Status: 'Standby'
    1. Krea AI Interior Photo Generation (4:5 Ratio)       -> 'Interior Generated Photo', Status: 'Processing Interior Generated Photo'
    2. Claude Sonnet 5 Prompt Analysis (via Fal AI Vision) -> 'Blending Prompt', Status: 'Processing Blending Prompt'
    3. Fal AI Nano Banana Pro 4:5 Daytime Blending         -> 'Day Image', Status: 'Processing Day Image'
    4. Fal AI Nano Banana Pro 4:5 Night Transformation     -> 'Night Image', Status: 'Complete'

Usage::

    # Interactive Menu
    python generate_day_night_feed_pipeline.py --mode menu

    # Process 1 Feed row end-to-end:
    python generate_day_night_feed_pipeline.py --max-items 1

    # Process 3 Feed rows sequentially:
    python generate_day_night_feed_pipeline.py --max-items 3

    # Process a specific Airtable Record ID:
    python generate_day_night_feed_pipeline.py --record-id recXXXXXXXXXXXXXX

    # Scrape only:
    python generate_day_night_feed_pipeline.py --mode scrape --max-items 3

    # Dry run (test configuration without API calls):
    python generate_day_night_feed_pipeline.py --dry-run
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import re
import shutil
import sys
import tempfile
import time
from typing import Any
import requests

from PIL import Image

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename, download_to_temp_file
from content_automation.qwen_client import QwenClient
from content_automation.scraping import ScrapeAirtableClient, load_scrape_settings
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    akeneo_category_code,
    moodboard_id_for_category,
)
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner
from content_automation.scraping.products import (
    existing_product_identities,
    select_new_products,
)

# ── Table & Feed Configurations ───────────────────────────────────────────────

DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_DAY_AND_NIGHT_4_5", "").strip()
    or "tblSceuLVvLMQ6wWp"
)
DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
    or "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
)
DEFAULT_CATEGORY = "chandeliers"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
ASPECT_RATIO_4_5 = "4:5"

DEFAULT_INTERIOR_PROMPT = (
    "Generate me a modern living room the ceiling and plain and hanging chandelier"
)

NIGHT_PROMPT = """
Transform this exact completed daytime interior photograph into a realistic
night version. Preserve the product design, position, scale, room geometry,
camera angle, composition, and all objects. Change only the time-of-day,
exterior light, ambience, and illumination. Keep the featured lighting or
furniture product visibly switched on and attractive. Do not add text.
""".strip()

# ── Field Names for Feed Table ───────────────────────────────────────────────

FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "Processing Interior Generated Photo"
STATUS_GENERATING_PROMPT = "Processing Blending Prompt"
STATUS_BLENDED_DAY = "Processing Day Image"
STATUS_BLENDED_NIGHT = "Processing Night Image"
STATUS_COMPLETE = "Complete"

INTERIOR_FIELD = "Interior Generated Photo"
INTERIOR_FIELD_FALLBACKS = ["Interior Generated Photo", "Interior Generated", "Interior"]

PROMPT_FIELD = "Blending Prompt"
PROMPT_FIELD_FALLBACKS = ["Blending Prompt", "Prompt for Blending", "Prompt"]

DAY_IMAGE_FIELD = "Day Image"
DAY_IMAGE_FALLBACKS = ["Day Image", "Day Photo", "Blended Image"]

NIGHT_IMAGE_FIELD = "Night Image"
NIGHT_IMAGE_FALLBACKS = ["Night Image", "Night Photo"]

STORY_FINAL_FIELD = "STORY - Day & Night (2)"

FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_BLENDING_MODEL = os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"

AUDIT_LOG_DIR = Path("output") / "logs"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "day_night_feed_logs.json"


def append_audit_log(entry: dict[str, Any], log_path: Path = AUDIT_LOG_FILE) -> None:
    """Append execution log record to audit JSON file."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logs: list[dict[str, Any]] = []
        if log_path.exists():
            try:
                logs = json.loads(log_path.read_text(encoding="utf-8"))
                if not isinstance(logs, list):
                    logs = []
            except Exception:
                logs = []
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        logs.append(entry)
        log_path.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    except Exception as error:
        print(f"[WARN] Failed to write audit log: {error}")


def get_first_field_value(fields: dict[str, Any], field_names: list[str]) -> Any:
    """Return the first populated value among candidate field names."""
    for name in field_names:
        if name in fields and fields[name]:
            return fields[name]
    return None


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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0: Akeneo Scraping for Feed Table
# ─────────────────────────────────────────────────────────────────────────────

def scrape_feed_products(
    settings: Any,
    airtable: ScrapeAirtableClient,
    count: int = 1,
    style: str = DEFAULT_STYLE,
) -> bool:
    """Scrape unique chandelier products from Akeneo into Feed table tblSceuLVvLMQ6wWp."""
    print(f"\n[PHASE 0: SCRAPE] Scraping {count} new chandelier item(s) from Akeneo (style={style})...")
    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
    )
    runner = FurnitureItemScrapeRunner(
        akeneo,
        airtable,
        category_code=DEFAULT_CATEGORY,
        style_code=style,
        field_name=FIELD_NAME,
        item_name_field=ITEM_NAME_FIELD,
        sku_field=SKU_FIELD,
        status_field=STATUS_FIELD,
        default_status=STATUS_STANDBY,
        include_product_type_in_name=True,
        max_items=count,
    )
    return runner.run()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Krea AI Interior Generation (4:5 Ratio)
# ─────────────────────────────────────────────────────────────────────────────

def generate_krea_interior_for_feed(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_INTERIOR_PROMPT,
    aspect_ratio: str = ASPECT_RATIO_4_5,
    dry_run: bool = False,
) -> str:
    """Generate 4:5 ratio Krea AI Room Interior and attach to 'Interior Generated Photo'."""
    existing = get_first_field_value(fields, INTERIOR_FIELD_FALLBACKS)
    if existing:
        url = extract_attachment_url(existing)
        if url:
            print(f"  [SKIP] Record {record_id} already has interior photo attached.")
            return url

    print(f"  [PHASE 1/4] Generating 4:5 Interior Photo with Krea AI (Moodboard: {moodboard_id})...")
    if dry_run:
        print("  [DRY-RUN] Would generate 4:5 interior photo with Krea AI.")
        return "https://dry-run.placeholder/interior.jpg"

    downloaded = None
    try:
        image_url = krea.generate(
            prompt,
            aspect_ratio=aspect_ratio,
            moodboard_id=moodboard_id,
        )
        downloaded = krea.download_image(image_url)
        filename = f"interior_{record_id}.jpg"
        target_field = INTERIOR_FIELD
        airtable.upload_attachment(record_id, target_field, downloaded, filename)
        airtable.update_records([(record_id, {STATUS_FIELD: STATUS_INTERIOR_GENERATED})])
        print(f"  [OK] Attached 4:5 interior photo to '{target_field}' and updated Status to '{STATUS_INTERIOR_GENERATED}'")

        fresh = airtable.get_record(record_id)
        fresh_url = extract_attachment_url(get_first_field_value(fresh.get("fields", {}), INTERIOR_FIELD_FALLBACKS))
        return fresh_url or image_url
    finally:
        if downloaded:
            try:
                downloaded.cleanup()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Claude Sonnet 5 Vision Blending Prompt Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_blending_prompt_for_feed(
    fal: FalClient,
    qwen: QwenClient | None,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    interior_url: str,
    furniture_url: str,
    *,
    dry_run: bool = False,
) -> str:
    """Analyze interior and product images to generate a 4:5 ratio Nano Banana Pro blending prompt."""
    existing_prompt = str(get_first_field_value(fields, PROMPT_FIELD_FALLBACKS) or "").strip()
    if existing_prompt:
        print("  [SKIP] Record already has Blending Prompt generated.")
        return existing_prompt

    item_name = str(fields.get(ITEM_NAME_FIELD) or "Chandelier").strip()
    print(f"  [PHASE 2/4] Analyzing Scene & Writing Blending Prompt (Claude Sonnet 5 Vision)...")

    if dry_run:
        print("  [DRY-RUN] Would generate Claude Sonnet 5 vision blending prompt.")
        return f"A modern living room featuring the {item_name} chandelier mounted at ceiling center with warm ambient glow."

    instruction = (
        f"You are an expert interior design photographer and image blending director.\n"
        f"Treat Image 1 as the background room interior ('Interior Generated Photo') "
        f"and Image 2 as the product photo for '{item_name}' ('Furniture Item').\n"
        f"Generate a detailed, highly specific image-blending prompt for Nano Banana Pro (4:5 aspect ratio). "
        f"The prompt must describe naturally integrating and mounting the {item_name} from Image 2 into the room interior from Image 1.\n"
        f"CRITICAL ISOLATION & MOUNTING RULES:\n"
        f"1. The {item_name} shown in Image 2 MUST BE THE ONLY CEILING/MAIN LIGHTING FIXTURE in the entire final blended scene.\n"
        f"2. If Image 1 contains ANY pre-existing lighting fixtures, explicitly instruct to remove and replace them with the exact {item_name} from Image 2.\n"
        f"3. Strictly exclude unnecessary, competing furniture items, duplicate fixtures, or clutter.\n"
        f"4. Ensure natural hanging/placement height, realistic chain/rod/cord mounting, ceiling canopy, realistic daylight illumination, soft ambient glow, natural contact shadows on surrounding walls/floors, and authentic materials.\n\n"
        f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
    )

    prompt_text = ""
    try:
        prompt_text = fal.generate_vision_prompt(
            image_urls=[interior_url, furniture_url],
            prompt=instruction,
            model=FAL_VISION_MODEL,
        )
    except Exception as fal_err:
        print(f"  [WARN] Fal AI Claude vision error ({fal_err}), falling back to Qwen...")
        if qwen:
            try:
                prompt_text = qwen.generate_blending_json_prompt(
                    interior_url,
                    furniture_url,
                    model="qwen3.7-flash",
                )
            except Exception as qwen_err:
                raise AutomationError(f"Both Claude and Qwen prompt generation failed: {fal_err} | {qwen_err}")
        else:
            raise

    prompt_text = prompt_text.strip().strip('"').strip("'")
    target_prompt_field = PROMPT_FIELD
    airtable.update_records([(record_id, {target_prompt_field: prompt_text, STATUS_FIELD: STATUS_GENERATING_PROMPT})])
    print(f"  [OK] Saved Blending Prompt ({len(prompt_text)} chars) and updated Status to '{STATUS_GENERATING_PROMPT}'")
    return prompt_text


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Fal AI Nano Banana Pro Daytime Blending (4:5)
# ─────────────────────────────────────────────────────────────────────────────

def generate_day_image_for_feed(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    interior_url: str,
    furniture_url: str,
    blend_prompt: str,
    *,
    aspect_ratio: str = ASPECT_RATIO_4_5,
    dry_run: bool = False,
) -> str:
    """Generate 4:5 Daytime blended photo using Fal AI Nano Banana Pro."""
    existing_day = get_first_field_value(fields, DAY_IMAGE_FALLBACKS)
    if existing_day:
        url = extract_attachment_url(existing_day)
        if url:
            print("  [SKIP] Record already has Day Image generated.")
            return url

    print(f"  [PHASE 3/4] Blending Day Photo at {aspect_ratio} (Fal AI Nano Banana Pro)...")
    if dry_run:
        print("  [DRY-RUN] Would generate 4:5 Day Image via Fal AI.")
        return "https://dry-run.placeholder/day_photo.jpg"

    downloaded = None
    try:
        result_url = fal.generate(
            prompt=blend_prompt,
            image_urls=[interior_url, furniture_url],
            aspect_ratio=aspect_ratio,
            model=FAL_BLENDING_MODEL,
        )
        response = requests.get(result_url, stream=True)
        downloaded = download_to_temp_file(
            response,
            prefix=f"day_{record_id}_",
            suffix=".jpg",
            context=f"Download day image from {result_url}",
        )
        filename = f"day_photo_{record_id}.jpg"
        target_day_field = DAY_IMAGE_FIELD
        airtable.upload_attachment(record_id, target_day_field, downloaded, filename)
        airtable.update_records([(record_id, {STATUS_FIELD: STATUS_BLENDED_DAY})])
        print(f"  [OK] Attached 4:5 Day Image to '{target_day_field}' and updated Status to '{STATUS_BLENDED_DAY}'")

        fresh = airtable.get_record(record_id)
        fresh_url = extract_attachment_url(get_first_field_value(fresh.get("fields", {}), DAY_IMAGE_FALLBACKS))
        return fresh_url or result_url
    finally:
        if downloaded:
            try:
                downloaded.cleanup()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Fal AI Nano Banana Pro Night Transformation (4:5)
# ─────────────────────────────────────────────────────────────────────────────

def generate_night_image_for_feed(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    day_image_url: str,
    *,
    aspect_ratio: str = ASPECT_RATIO_4_5,
    dry_run: bool = False,
) -> str:
    """Generate 4:5 Nighttime transformed photo using Fal AI Nano Banana Pro."""
    existing_night = get_first_field_value(fields, NIGHT_IMAGE_FALLBACKS)
    if existing_night:
        url = extract_attachment_url(existing_night)
        if url:
            print("  [SKIP] Record already has Night Image generated.")
            return url

    print(f"  [PHASE 4/4] Creating Night Ambiance Version at {aspect_ratio} (Fal AI Nano Banana Pro)...")
    if dry_run:
        print("  [DRY-RUN] Would generate 4:5 Night Image via Fal AI.")
        return "https://dry-run.placeholder/night_photo.jpg"

    downloaded = None
    try:
        result_url = fal.generate(
            prompt=NIGHT_PROMPT,
            image_urls=[day_image_url],
            aspect_ratio=aspect_ratio,
            model=FAL_BLENDING_MODEL,
        )
        response = requests.get(result_url, stream=True)
        downloaded = download_to_temp_file(
            response,
            prefix=f"night_{record_id}_",
            suffix=".jpg",
            context=f"Download night image from {result_url}",
        )
        filename = f"night_photo_{record_id}.jpg"
        target_night_field = NIGHT_IMAGE_FIELD
        airtable.upload_attachment(record_id, target_night_field, downloaded, filename)
        print(f"  [OK] Attached 4:5 Night Image to '{target_night_field}'")

        fresh = airtable.get_record(record_id)
        fresh_url = extract_attachment_url(get_first_field_value(fresh.get("fields", {}), NIGHT_IMAGE_FALLBACKS))
        return fresh_url or result_url
    finally:
        if downloaded:
            try:
                downloaded.cleanup()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Completion: Upload Both Images & Mark Row Complete
# ─────────────────────────────────────────────────────────────────────────────

def finalize_feed_record(
    airtable: ScrapeAirtableClient,
    record_id: str,
    day_url: str,
    night_url: str,
    *,
    dry_run: bool = False,
) -> bool:
    """Upload both photos to multi-attachment field if present and set Status to Complete."""
    if dry_run:
        print(f"  [DRY-RUN] Would set Status='{STATUS_COMPLETE}' on record {record_id}")
        return True

    print(f"\n  [UPLOAD] Finalizing Day & Night Feed record {record_id}...")
    downloaded_day = None
    downloaded_night = None
    try:
        resp_day = requests.get(day_url, stream=True)
        downloaded_day = download_to_temp_file(resp_day, prefix="final_day_", suffix=".jpg")

        resp_night = requests.get(night_url, stream=True)
        downloaded_night = download_to_temp_file(resp_night, prefix="final_night_", suffix=".jpg")

        # Upload both images to the final multi-attachment field if present in schema
        try:
            airtable.upload_attachment(record_id, STORY_FINAL_FIELD, downloaded_day, "day_photo.jpg")
            airtable.upload_attachment(record_id, STORY_FINAL_FIELD, downloaded_night, "night_photo.jpg")
            print(f"  [OK] Uploaded [day_photo.jpg, night_photo.jpg] to '{STORY_FINAL_FIELD}'")
        except Exception:
            pass

        # Update status to Complete
        airtable.update_records([(record_id, {STATUS_FIELD: STATUS_COMPLETE})])
        print(f"  [OK] Updated Status to '{STATUS_COMPLETE}' on record {record_id}!")
        return True
    except Exception as error:
        print(f"  [WARN] Finalization notice: {error}")
        try:
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_COMPLETE})])
        except Exception:
            pass
        return True
    finally:
        if downloaded_day:
            try:
                downloaded_day.cleanup()
            except Exception:
                pass
        if downloaded_night:
            try:
                downloaded_night.cleanup()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Sequential Row Execution Engine
# ─────────────────────────────────────────────────────────────────────────────

def process_single_feed_row(
    krea: KreaClient,
    fal: FalClient,
    qwen: QwenClient | None,
    airtable: ScrapeAirtableClient,
    record: dict[str, Any],
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """Execute all 4 Feed AI generation phases for a single Airtable record end-to-end."""
    record_id = record["id"]
    fields = record.get("fields", {})
    item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
    status = str(fields.get(STATUS_FIELD) or "").strip()

    if status == STATUS_COMPLETE and not force:
        print(f"[SKIP] Record {record_id} ({item_label}) is already Complete.")
        return True

    furniture_url = extract_attachment_url(fields.get(FIELD_NAME))
    if not furniture_url:
        print(f"[ERROR] Record {record_id} ({item_label}) has no 'Furniture Item' attachment URL.")
        return False

    print("\n" + "=" * 64)
    print(f" [FEED ROW START] Processing Record: {record_id}")
    print(f" Item: {item_label}")
    print(f" Ratio: 4:5 (Feed) | Status: {status or 'Unset'}")
    print("=" * 64)

    start_time = time.time()

    # Step 1: Krea AI Interior Generation (4:5)
    interior_url = generate_krea_interior_for_feed(
        krea,
        airtable,
        record_id,
        fields,
        moodboard_id=moodboard_id,
        prompt=DEFAULT_INTERIOR_PROMPT,
        aspect_ratio=ASPECT_RATIO_4_5,
        dry_run=dry_run,
    )

    # Step 2: Claude Sonnet 5 Vision Blending Prompt
    blend_prompt = generate_blending_prompt_for_feed(
        fal,
        qwen,
        airtable,
        record_id,
        fields,
        interior_url,
        furniture_url,
        dry_run=dry_run,
    )

    # Step 3: Fal AI Nano Banana Pro Daytime Blending (4:5)
    day_image_url = generate_day_image_for_feed(
        fal,
        airtable,
        record_id,
        fields,
        interior_url,
        furniture_url,
        blend_prompt,
        aspect_ratio=ASPECT_RATIO_4_5,
        dry_run=dry_run,
    )

    # Step 4: Fal AI Nano Banana Pro Night Transformation (4:5)
    night_image_url = generate_night_image_for_feed(
        fal,
        airtable,
        record_id,
        fields,
        day_image_url,
        aspect_ratio=ASPECT_RATIO_4_5,
        dry_run=dry_run,
    )

    # Finalize: Update status to Complete
    success = finalize_feed_record(
        airtable,
        record_id,
        day_image_url,
        night_image_url,
        dry_run=dry_run,
    )

    elapsed = round(time.time() - start_time, 2)
    print(f"\n[FEED ROW COMPLETE] Record {record_id} finished in {elapsed}s")

    append_audit_log({
        "record_id": record_id,
        "item_label": str(item_label),
        "status": STATUS_COMPLETE if success else "Failed",
        "aspect_ratio": ASPECT_RATIO_4_5,
        "type": "feed",
        "elapsed_seconds": elapsed,
        "dry_run": dry_run,
    })

    return success


# ─────────────────────────────────────────────────────────────────────────────
# CLI Parser & Interactive Menu
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Chandelier Day & Night Feed (4:5 Ratio) AI Generation & Blending Pipeline."
    )
    parser.add_argument(
        "--mode",
        choices=["all", "menu", "scrape", "generate"],
        default="all",
        help="Execution mode (default: all)",
    )
    parser.add_argument(
        "--limit",
        "--max-items",
        "-n",
        dest="max_items",
        type=int,
        default=1,
        help="Number of Feed rows to process sequentially (default: 1)",
    )
    parser.add_argument(
        "--record-id",
        "-r",
        action="append",
        default=[],
        help="Specific Airtable Record ID(s) to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without paid API calls or Airtable writes",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip auto-scraping even if there are no pending Standby rows",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape products from Akeneo into Airtable without running generation",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if already completed",
    )
    parser.add_argument(
        "--table-id",
        default=DEFAULT_TABLE_ID,
        help=f"Airtable destination table ID (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--moodboard-id",
        default=DEFAULT_MOODBOARD_ID,
        help=f"Krea Moodboard ID override (default: {DEFAULT_MOODBOARD_ID})",
    )
    parser.add_argument(
        "--style",
        default=DEFAULT_STYLE,
        help=f"Akeneo style filter (default: {DEFAULT_STYLE})",
    )
    return parser.parse_args(argv)


def interactive_menu():
    """Display interactive CLI menu for user selection."""
    print("\n" + "=" * 64)
    print(" HomeCartel - Chandelier Day & Night Feed Pipeline (4:5 Ratio)")
    print(f" Target Table ID: {DEFAULT_TABLE_ID}")
    print("=" * 64)
    print(" [1] Run 1 Feed Row End-to-End (Scrape 1 -> Generate 4:5 Day & Night -> Complete)")
    print(" [2] Run 3 Feed Rows End-to-End")
    print(" [3] Run N Feed Rows End-to-End (Custom limit)")
    print(" [4] Scrape Akeneo Products Only (Status: Standby)")
    print(" [5] Generate Day & Night Feed Only (Skip Scraping)")
    print(" [6] Process Specific Record ID")
    print(" [7] Dry Run (Validate configuration without paid API calls)")
    print(" [8] Exit")
    print("=" * 64)

    choice = input("Select an option (1-8): ").strip()
    return choice


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.mode == "menu":
        choice = interactive_menu()
        if choice == "1":
            args.mode = "all"
            args.max_items = 1
        elif choice == "2":
            args.mode = "all"
            args.max_items = 3
        elif choice == "3":
            try:
                count = int(input("Enter number of rows to process: ").strip())
                args.max_items = max(1, count)
                args.mode = "all"
            except ValueError:
                print("[ERROR] Invalid number. Defaulting to 1.")
                args.max_items = 1
        elif choice == "4":
            args.mode = "scrape"
            try:
                count = int(input("Enter number of products to scrape: ").strip())
                args.max_items = max(1, count)
            except ValueError:
                args.max_items = 1
        elif choice == "5":
            args.mode = "generate"
            args.no_scrape = True
        elif choice == "6":
            rid = input("Enter Airtable Record ID: ").strip()
            if rid:
                args.record_id = [rid]
                args.mode = "all"
        elif choice == "7":
            args.dry_run = True
            args.mode = "all"
            args.max_items = 1
        else:
            print("Exiting.")
            return 0

    base_settings = load_settings()
    table_id = args.table_id or DEFAULT_TABLE_ID
    moodboard_id = args.moodboard_id or DEFAULT_MOODBOARD_ID

    print("\n" + "=" * 64)
    print(" HomeCartel - Day & Night Feed AI Pipeline (4:5 Ratio)")
    print(f" Target Table: {table_id} (Chandelier Feed)")
    print(f" Aspect Ratio: {ASPECT_RATIO_4_5} (Feed)")
    print(f" Krea Moodboard ID: {moodboard_id}")
    print(f" Mode: {'DRY RUN' if args.dry_run else 'LIVE EXECUTION'}")
    print(f" Batch Size: {args.max_items} row(s)")
    if args.record_id:
        print(f" Specific Record(s): {', '.join(args.record_id)}")
    print("=" * 64)

    airtable = ScrapeAirtableClient(
        base_settings.airtable_token,
        base_settings.airtable_base_id,
        table_id,
    )
    krea = KreaClient(base_settings.krea_token, base_settings.krea_base_url)
    fal = FalClient(base_settings.fal_key)
    qwen = QwenClient(base_settings.qwen_api_key, base_settings.qwen_base_url) if getattr(base_settings, "qwen_api_key", None) else None

    # Handle Scrape Mode
    if args.mode == "scrape" or args.scrape_only:
        success = scrape_feed_products(base_settings, airtable, count=args.max_items, style=args.style)
        print(f"\n[SCRAPE RESULT] {'Success' if success else 'Completed with warnings/no new items'}.")
        return 0 if success else 1

    # Check Standby rows or Auto-Scrape if needed
    if not args.dry_run and not args.record_id and not args.no_scrape:
        records = airtable.list_records([STATUS_FIELD, FIELD_NAME, SKU_FIELD])
        standby_records = [
            r for r in records
            if str(r.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold() == STATUS_STANDBY.casefold()
            and r.get("fields", {}).get(FIELD_NAME)
        ]
        if len(standby_records) < args.max_items:
            needed = args.max_items - len(standby_records)
            print(f"[INFO] Found {len(standby_records)} 'Standby' row(s). Auto-scraping {needed} new chandelier item(s) from Akeneo...")
            scrape_feed_products(base_settings, airtable, count=needed, style=args.style)
        else:
            print(f"[INFO] Found {len(standby_records)} existing 'Standby' row(s) ready for generation.")

    # Fetch rows to process
    records_to_process = []
    if args.record_id:
        for rid in args.record_id:
            try:
                rec = airtable.get_record(rid)
                if rec:
                    records_to_process.append(rec)
            except Exception as e:
                print(f"[ERROR] Could not fetch record {rid}: {e}")
    else:
        all_records = airtable.list_records()
        for r in all_records:
            fields = r.get("fields", {})
            st = str(fields.get(STATUS_FIELD) or "").strip()
            has_product = bool(fields.get(FIELD_NAME))
            if has_product and (st != STATUS_COMPLETE or args.force):
                records_to_process.append(r)
        if args.max_items:
            records_to_process = records_to_process[:args.max_items]

    if not records_to_process:
        print("\n[OK] No pending rows to process. Table is up to date!")
        return 0

    print(f"\n[INFO] Starting sequential row-by-row generation for {len(records_to_process)} Feed row(s)...\n")

    succeeded = 0
    failed = 0
    for idx, rec in enumerate(records_to_process, start=1):
        print(f"\n>>> [FEED ROW {idx}/{len(records_to_process)}] <<<")
        try:
            ok = process_single_feed_row(
                krea,
                fal,
                qwen,
                airtable,
                rec,
                moodboard_id=moodboard_id,
                dry_run=args.dry_run,
                force=args.force,
            )
            if ok:
                succeeded += 1
            else:
                failed += 1
        except Exception as error:
            print(f"[ERROR] Feed row processing failed for {rec.get('id')}: {error}")
            failed += 1

    print("\n" + "=" * 64)
    print(f" Feed Pipeline Finished: {succeeded} Succeeded, {failed} Failed.")
    print("=" * 64)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
        sys.exit(130)
    except AutomationError as error:
        print(f"\n[FATAL] {error}", file=sys.stderr)
        sys.exit(2)
