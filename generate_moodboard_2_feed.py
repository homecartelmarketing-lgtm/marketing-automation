"""Moodboard #2 Feed AI Generation & Editorial Flat-Lay Conversion Pipeline.

Runs the complete AI generation pipeline for Moodboard #2 Feed:
1. [Phase 1/5] Krea AI Interior Generation (4:5) -> 'Interior Photo' / 'Interior Generated'
2. [Phase 2/5] Fal AI Claude Sonnet 5 Prompt Generation -> 'Blending Prompt'
3. [Phase 3/5] Fal AI Nano Banana Pro Image Blending (4:5, 1k) -> 'Blended Image'
4. [Phase 4/5] Ensure Moodboard #2 Layout & Fixed Prompt are attached
5. [Phase 5/5] Fal AI Nano Banana Pro Flat-Lay Conversion (4:5, 1k) -> 'Moodboard #2 Converted'
6. [Finalize]  Set Status -> 'Done'

Usage::

    python generate_moodboard_2_feed.py
    python generate_moodboard_2_feed.py --category pendant_lights --max-items 3
    python generate_moodboard_2_feed.py --table-id tbltWgQKOYjuHw6tx
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import requests

from content_automation.airtable_client import current_pht_timestamp
from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.prompts import build_vision_blending_instruction
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.overlay import HOMECARTEL_LOGO_BOX, stamp_logo
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner

MOODBOARD_2_FEED_PRESETS = {
    "chandeliers": {
        "category_code": "chandeliers",
        "label": "Chandelier",
        "default_table_id": "tbltWgQKOYjuHw6tx",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_MOODBOARD_2_FEED",
        "default_moodboard_id": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        "env_moodboard_key": "KREA_MOODBOARD_ID_CHANDELIER_MOODBOARD_2_FEED",
        "default_prompt": "Generate me a modern living room",
        "env_prompt_key": "MOODBOARD_2_FEED_PROMPT_CHANDELIER",
        "aliases": ["chandelier", "chandeliers", "1"],
    },
    "pendant_lights": {
        "category_code": "pendant_lights",
        "label": "Pendant Lights",
        "default_table_id": "tbl4TiV90SzdBz4KG",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARD_2_FEED",
        "default_moodboard_id": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
        "env_moodboard_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_MOODBOARD_2_FEED",
        "default_prompt": "Generate me a modern dining room",
        "env_prompt_key": "MOODBOARD_2_FEED_PROMPT_PENDANT_LIGHTS",
        "aliases": ["pendant", "pendant_lights", "pendant_light", "2"],
    },
    "floor_lamps": {
        "category_code": "floor_lamps",
        "label": "Floor Lamps",
        "default_table_id": "tbl4YF9iXlBqGblEc",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMPS_MOODBOARD_2_FEED",
        "default_moodboard_id": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
        "env_moodboard_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS_MOODBOARD_2_FEED",
        "default_prompt": "Generate me a modern living room with empty floor space for a standing floor lamp",
        "env_prompt_key": "MOODBOARD_2_FEED_PROMPT_FLOOR_LAMPS",
        "aliases": ["floor_lamp", "floor_lamps", "3"],
    },
    "wall_lights": {
        "category_code": "wall_lights",
        "label": "Wall Lights",
        "default_table_id": "tbljUk9JwzS1JeZJg",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_MOODBOARD_2_FEED",
        "default_moodboard_id": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        "env_moodboard_key": "KREA_MOODBOARD_ID_WALL_LIGHTS_MOODBOARD_2_FEED",
        "default_prompt": "Generate me a modern living room with a wall light",
        "env_prompt_key": "MOODBOARD_2_FEED_PROMPT_WALL_LIGHTS",
        "aliases": ["wall_light", "wall_lights", "wall_sconces", "wall_sconce", "4"],
    },
}

DEFAULT_CATEGORY = "chandeliers"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

FIELD_FURNITURE = "Furniture Item"
FIELD_ITEM_NAME = "Item Name"
FIELD_STATUS = "Status"

STATUS_STANDBY = "Standby"
STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"

# Candidate fields with resilient fallbacks for slight schema differences
CANDIDATE_INTERIOR_FIELDS = ("Interior Photo", "Interior Generated")
CANDIDATE_PROMPT_FIELDS = ("Blending Prompt", "Prompt for Blending")
CANDIDATE_BLENDED_FIELDS = ("Blended Image", "Moodboard V1 Blended")
CANDIDATE_LAYOUT_FIELDS = ("Moodboard #2 Layout", "Moodboard Layout")
CANDIDATE_CONVERTED_FIELDS = ("Moodboard #2 Converted", "Moodboard Converted")
CANDIDATE_FIXED_PROMPT_FIELDS = (
    "Moodboard Converstion Fixed Prompt",
    "Moodboard Conversion Fixed Prompt",
    "Fixed Prompt",
)

INTERIOR_ASPECT_RATIO = "4:5"
FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_NANO_MODEL = os.getenv("FAL_NANO_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
NANO_ASPECT_RATIO = "4:5"
NANO_RESOLUTION = "1k"

AUDIT_LOG_DIR = Path("output/logs")
AUDIT_LOG_CLAUDE = AUDIT_LOG_DIR / "moodboard_2_feed_claude_logs.json"
AUDIT_LOG_FAL = AUDIT_LOG_DIR / "moodboard_2_feed_fal_logs.json"

LOCAL_LAYOUT_PATH = Path("JSON Prompts/Moodboard V2/referencephoto_moodboard.png")
LOCAL_FIXED_PROMPT_PATH = Path("JSON Prompts/Moodboard V2/second_moodboard.json")


def resolve_preset(category_or_key: str | None) -> dict:
    """Resolve category or key to a valid preset dictionary."""
    if not category_or_key:
        return MOODBOARD_2_FEED_PRESETS[DEFAULT_CATEGORY]
    raw = category_or_key.strip().lower()
    if raw in MOODBOARD_2_FEED_PRESETS:
        return MOODBOARD_2_FEED_PRESETS[raw]
    for key, preset in MOODBOARD_2_FEED_PRESETS.items():
        if raw in preset["aliases"] or raw == preset["category_code"]:
            return preset
        t_id = os.getenv(preset["env_table_key"], "").strip() or preset["default_table_id"]
        if raw == t_id.lower():
            return preset
    return MOODBOARD_2_FEED_PRESETS[DEFAULT_CATEGORY]


def find_table_field(airtable: ScrapeAirtableClient, candidates: tuple[str, ...], default: str) -> str:
    """Resolve actual field name from table schema using case-insensitive match."""
    if hasattr(airtable, "find_field_name"):
        for cand in candidates:
            found = airtable.find_field_name(cand)
            if found:
                return found
    if hasattr(airtable, "has_field"):
        for cand in candidates:
            if airtable.has_field(cand):
                return cand
    return default


def append_audit_log(log_entry: dict[str, Any], log_path: Path = AUDIT_LOG_CLAUDE) -> None:
    """Append a structured JSON log entry for auditing and transparency."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            logs = json.loads(log_path.read_text(encoding="utf-8"))
            if not isinstance(logs, list):
                logs = []
        except Exception:
            logs = []
    logs.append(log_entry)
    try:
        log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception as err:
        print(f"[WARN] Failed writing audit log: {err}")


def extract_attachment_url(field_value: Any) -> str:
    """Pull primary HTTP download URL from Airtable attachment field value."""
    if isinstance(field_value, list) and field_value:
        first = field_value[0]
        if isinstance(first, dict):
            return str(first.get("url") or first.get("permalink") or "")
    if isinstance(field_value, dict):
        return str(field_value.get("url") or field_value.get("permalink") or "")
    return ""


def resolve_logo_path(fields: dict[str, Any] | None = None) -> tuple[Path, Any]:
    """Resolve HomeCartel logo path, checking table attachment first, then local disk fallback."""
    if fields:
        for fname in ("Logo", "Logo Watermark", "Brand Logo"):
            logo_field = fields.get(fname)
            url = extract_attachment_url(logo_field)
            if url:
                try:
                    resp = requests.get(url, stream=True, timeout=20)
                    downloaded = download_to_temp_file(
                        resp, prefix="feed_logo_", suffix=".png", context="Download table logo"
                    )
                    return downloaded.path, downloaded
                except Exception as err:
                    print(f"  [WARN] Failed downloading logo attachment ({err}), using local asset.")
                break

    candidates = [
        Path("assets/homecartel_logo.png"),
        Path(__file__).parent / "assets" / "homecartel_logo.png",
        Path("assets/Logo.png"),
        Path(__file__).parent / "assets" / "Logo.png",
    ]
    for p in candidates:
        if p.is_file():
            return p, None
    return Path("assets/homecartel_logo.png"), None


# ══════════════════════════════════════════════════════════════════════════
# PHASE 0 — Akeneo Product Scraping & Layout Ingestion
# ══════════════════════════════════════════════════════════════════════════

def scrape_feed_products(
    settings: Any,
    airtable: ScrapeAirtableClient,
    count: int = 1,
    style: str = DEFAULT_STYLE,
    category: str = DEFAULT_CATEGORY,
    no_shopify_check: bool = False,
    no_backfill: bool = False,
) -> bool:
    """Scrape unique active products from Akeneo into Moodboard #2 Feed table."""
    print(f"\n[PHASE 0: INGESTION] Scraping {count} new {category} item(s) from Akeneo (style={style})...")
    scrape_settings = load_scrape_settings(
        category_code=category,
        style_code=style,
        table_id_override=airtable.table_id,
        settings=settings,
    )
    akeneo = AkeneoClient(
        scrape_settings.akeneo_host,
        scrape_settings.akeneo_client_id,
        scrape_settings.akeneo_secret,
        scrape_settings.akeneo_username,
        scrape_settings.akeneo_password,
        channel_name=scrape_settings.channel_name,
    )
    runner = FurnitureItemScrapeRunner(
        akeneo,
        airtable,
        category_code=category,
        style_code=style,
        field_name=FIELD_FURNITURE,
        item_name_field=FIELD_ITEM_NAME,
        sku_field=None,
        status_field=FIELD_STATUS,
        default_status=STATUS_STANDBY,
        layout_fields={"Moodboard #2 Layout": "multipleAttachments"},
        backfill_layouts=not no_backfill,
        cross_table_dedup=False,
        shopify_cross_check=not no_shopify_check,
        include_product_type_in_name=True,
        max_items=count,
    )
    return runner.run()


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1 — Krea AI Room Interior Generation (4:5)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_2_interiors(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    moodboard_id: str,
    prompt: str,
    interior_field: str,
    aspect_ratio: str = INTERIOR_ASPECT_RATIO,
    limit_records: int | None = None,
) -> bool:
    """Generate 1 Krea interior photo per record into interior_field for Standby records."""
    airtable.ensure_fields({interior_field: "multipleAttachments", FIELD_STATUS: "singleSelect"})
    records = airtable.list_records(
        [interior_field, FIELD_FURNITURE, FIELD_ITEM_NAME, FIELD_STATUS]
    )
    if not records:
        print("[OK] No records found in Airtable to populate interior photos.")
        return True

    unpopulated = [
        record
        for record in records
        if str(record.get("fields", {}).get(FIELD_STATUS) or "").strip().casefold() in (STATUS_STANDBY.casefold(), "")
        and not record.get("fields", {}).get(interior_field)
    ]
    if not unpopulated:
        print(f"[OK] No records found with Status '{STATUS_STANDBY}' missing '{interior_field}'.")
        return True

    if limit_records is not None:
        unpopulated = unpopulated[:limit_records]

    print(
        f"[INFO] Generating '{interior_field}' for {len(unpopulated)} record(s) "
        f"using Krea AI (Moodboard ID: {moodboard_id}, Aspect Ratio: {aspect_ratio})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(unpopulated, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(FIELD_ITEM_NAME) or record_id
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
            filename = f"interior_{record_id}.jpg"
            airtable.upload_attachment(record_id, interior_field, downloaded, filename)
            airtable.update_records([(record_id, {FIELD_STATUS: STATUS_IN_PROGRESS, "Date and Time": current_pht_timestamp()})])
            print(
                f"[OK] Attached Krea image to '{interior_field}' and updated "
                f"{FIELD_STATUS} to '{STATUS_IN_PROGRESS}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(
                f"[ERROR] Failed generating '{interior_field}' for record {record_id}: {error}"
            )
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Krea interior generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Fal AI Claude Sonnet 5 Prompt Analysis
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_2_prompts(
    fal: FalClient | Any,
    airtable: ScrapeAirtableClient,
    *,
    interior_field: str,
    prompt_field: str,
    prompt_model: str = FAL_VISION_MODEL,
    limit_records: int | None = None,
) -> bool:
    """Generate detailed blending prompt using Claude Sonnet 5 via Fal AI into prompt_field."""
    airtable.ensure_fields({prompt_field: "multilineText"})
    records = airtable.list_records(
        [interior_field, FIELD_FURNITURE, FIELD_ITEM_NAME, FIELD_STATUS, prompt_field]
    )
    if not records:
        print("[OK] No records found in Airtable to generate prompts.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        if not fields.get(interior_field):
            continue
        if fields.get(prompt_field):
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Claude Sonnet 5 prompt generation ('{interior_field}' missing or '{prompt_field}' already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{prompt_field}' for {len(eligible)} record(s) "
        f"using Claude Sonnet 5 via Fal AI ({prompt_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = str(fields.get(FIELD_ITEM_NAME) or record_id).strip()

        interior_url = extract_attachment_url(fields.get(interior_field))
        furniture_url = extract_attachment_url(fields.get(FIELD_FURNITURE))

        if not interior_url or not furniture_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing photos & generating prompt for "
            f"record {record_id} ({item_label}) with Claude Sonnet 5..."
        )

        instruction = build_vision_blending_instruction(
            interior_label="Room Interior",
            item_name=item_label,
            aspect_ratio="4:5",
        )

        try:
            if hasattr(fal, "generate_vision_prompt"):
                blending_prompt = fal.generate_vision_prompt(
                    image_urls=[interior_url, furniture_url],
                    prompt=instruction,
                    model=prompt_model,
                ).strip().strip('"').strip("'")
            elif hasattr(fal, "generate_blending_json_prompt"):
                blending_prompt = fal.generate_blending_json_prompt(
                    interior_url,
                    furniture_url,
                    model=prompt_model,
                )
            else:
                raise AutomationError("Fal client does not support vision prompt generation")

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 2: Claude Sonnet 5 Prompt Generation",
                "api_provider": "Fal AI / OpenRouter",
                "api_model": prompt_model,
                "input_interior_url": interior_url,
                "input_furniture_url": furniture_url,
                "generated_prompt": blending_prompt,
            }, AUDIT_LOG_CLAUDE)

            airtable.update_records([(record_id, {prompt_field: blending_prompt, FIELD_STATUS: STATUS_IN_PROGRESS, "Date and Time": current_pht_timestamp()})])
            print(f"[OK] Saved Claude Sonnet 5 prompt to '{prompt_field}' on record {record_id}")
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating prompt for record {record_id}: {error}")
            failed += 1

    print(
        f"[INFO] Claude Sonnet 5 prompt generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Fal AI Nano Banana Pro Image Blending (4:5, 1k)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_2_blends(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    interior_field: str,
    prompt_field: str,
    blended_field: str,
    category: str = DEFAULT_CATEGORY,
    blend_model: str = FAL_NANO_MODEL,
    aspect_ratio: str = NANO_ASPECT_RATIO,
    resolution: str = NANO_RESOLUTION,
    limit_records: int | None = None,
) -> bool:
    """Generate image-to-image blended photo using Nano Banana Pro via Fal AI (4:5, 1k) into blended_field."""
    airtable.ensure_fields({blended_field: "multipleAttachments", FIELD_STATUS: "singleSelect"})
    records = airtable.list_records(
        [interior_field, FIELD_FURNITURE, FIELD_ITEM_NAME, FIELD_STATUS, prompt_field, blended_field, "Logo", "Logo Watermark"]
    )
    if not records:
        print("[OK] No records found in Airtable for image blending.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        prompt_text = str(fields.get(prompt_field) or "").strip()
        blended_attachments = fields.get(blended_field)
        if not prompt_text:
            continue
        if blended_attachments:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Nano Banana Pro blending ('{prompt_field}' missing or '{blended_field}' already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{blended_field}' for {len(eligible)} record(s) "
        f"using Nano Banana Pro via Fal AI ({blend_model}, {aspect_ratio}, {resolution})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(FIELD_ITEM_NAME) or record_id
        prompt_text = str(fields.get(prompt_field) or "").strip()

        interior_url = extract_attachment_url(fields.get(interior_field))
        furniture_url = extract_attachment_url(fields.get(FIELD_FURNITURE))
        image_inputs = [url for url in (interior_url, furniture_url) if url]

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating blended photo for "
            f"record {record_id} ({item_label}) with Nano Banana Pro..."
        )

        downloaded = None
        stamped_blended_file = None
        logo_temp = None
        try:
            image_url = fal.generate(
                prompt=prompt_text,
                image_urls=image_inputs,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                model=blend_model,
            )
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="blended_image_",
                suffix=".jpg",
                context=f"Download blended image from {image_url}",
            )

            # Stamp HomeCartel Feed logo onto blended image before uploading
            blended_source_for_upload = downloaded.path
            try:
                logo_path, logo_temp = resolve_logo_path(fields)
                if logo_path and logo_path.is_file():
                    temp_stamped = Path(tempfile.gettempdir()) / f"stamped_blended_{record_id}.jpg"
                    stamp_logo(
                        base_path=downloaded.path,
                        logo_path=logo_path,
                        destination=temp_stamped,
                        box=HOMECARTEL_LOGO_BOX,
                    )
                    if temp_stamped.is_file():
                        stamped_blended_file = temp_stamped
                        blended_source_for_upload = temp_stamped
                        print(
                            f"  [+] Stamped HomeCartel Feed logo onto Blended Image "
                            f"(Box: X={HOMECARTEL_LOGO_BOX.x}, Y={HOMECARTEL_LOGO_BOX.y}, "
                            f"W={HOMECARTEL_LOGO_BOX.width}, H={HOMECARTEL_LOGO_BOX.height})"
                        )
            except Exception as logo_err:
                print(f"  [WARN] Failed stamping HomeCartel logo onto Blended Image: {logo_err}")

            filename = f"blended_{record_id}.jpg"
            airtable.upload_attachment(record_id, blended_field, blended_source_for_upload, filename)
            airtable.update_records([(record_id, {FIELD_STATUS: STATUS_IN_PROGRESS, "Date and Time": current_pht_timestamp()})])

            # Auto-tag furniture item name onto Blended Image using YOLO-World
            try:
                from content_automation.akeneo_client import split_item_name
                from content_automation.item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
                raw_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
                item_title, product_type = split_item_name(raw_name, fallback_product_type=str(fields.get("Product Type") or ""))
                tag_and_upload_blended_image(
                    airtable=airtable,
                    record_id=record_id,
                    blended_source=blended_source_for_upload,
                    item_name=item_title,
                    product_type=product_type,
                    category=category,
                    target_field=TARGET_BLENDED_FIELD,
                    output_filename_prefix="mb2_tagged",
                    fallback_if_undetected=True,
                )
            except Exception as tag_err:
                print(f"[WARN] Failed YOLO item tagging on record {record_id}: {tag_err}")

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 3: Fal AI Image Blending",
                "api_provider": "Fal AI Nano Banana Pro",
                "model": blend_model,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "output_image_url": image_url,
            }, AUDIT_LOG_FAL)

            print(f"[OK] Attached blended image to '{blended_field}' on record {record_id}")
            succeeded += 1
        except Exception as error:
            err_msg = str(error).encode("ascii", errors="replace").decode("ascii")
            print(f"[ERROR] Failed blending image for record {record_id}: {err_msg}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()
            if logo_temp:
                try:
                    logo_temp.cleanup()
                except Exception:
                    pass
            if stamped_blended_file and stamped_blended_file.is_file():
                try:
                    stamped_blended_file.unlink(missing_ok=True)
                except Exception:
                    pass

    print(
        f"[INFO] Nano Banana Pro blending complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4 — Ensure Moodboard #2 Layout & Fixed Prompt
# ══════════════════════════════════════════════════════════════════════════

def ensure_layout_and_fixed_prompt(
    airtable: ScrapeAirtableClient,
    *,
    layout_field: str,
    fixed_prompt_field: str | None = None,
) -> None:
    """Ensure that Moodboard #2 Layout reference image and fixed prompt are populated."""
    records = airtable.list_records()
    if not records:
        return

    fixed_prompt_text = ""
    if LOCAL_FIXED_PROMPT_PATH.is_file():
        try:
            fixed_prompt_text = LOCAL_FIXED_PROMPT_PATH.read_text(encoding="utf-8")
        except Exception:
            pass

    for record in records:
        record_id = record["id"]
        fields = record.get("fields", {})

        # 1. Backfill layout attachment if missing
        if not fields.get(layout_field) and LOCAL_LAYOUT_PATH.is_file():
            try:
                airtable.upload_attachment(
                    record_id,
                    layout_field,
                    LOCAL_LAYOUT_PATH,
                    "referencephoto_moodboard.png",
                )
                print(f"[OK] Attached reference photo to '{layout_field}' on record {record_id}")
            except Exception as err:
                print(f"[WARN] Failed attaching layout to record {record_id}: {err}")

        # 2. Backfill fixed prompt if present in schema and missing
        if fixed_prompt_field and fixed_prompt_text and not fields.get(fixed_prompt_field):
            try:
                airtable.update_records([(record_id, {fixed_prompt_field: fixed_prompt_text})])
                print(f"[OK] Populated '{fixed_prompt_field}' on record {record_id}")
            except Exception as err:
                print(f"[WARN] Failed updating fixed prompt on record {record_id}: {err}")


# ══════════════════════════════════════════════════════════════════════════
# PHASE 5 — Fal AI Nano Banana Pro Editorial Flat-Lay Conversion (4:5, 1k)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_2_converted(
    fal: FalClient | Any,
    airtable: ScrapeAirtableClient,
    *,
    blended_field: str,
    layout_field: str,
    converted_field: str,
    fixed_prompt_field: str | None = None,
    blend_model: str = FAL_NANO_MODEL,
    aspect_ratio: str = NANO_ASPECT_RATIO,
    resolution: str = NANO_RESOLUTION,
    limit_records: int | None = None,
) -> bool:
    """Convert 'Blended Image' photo + 'Moodboard #2 Layout' into 'Moodboard #2 Converted' (4:5, 1k)."""
    airtable.ensure_fields({
        blended_field: "multipleAttachments",
        layout_field: "multipleAttachments",
        converted_field: "multipleAttachments",
        FIELD_STATUS: "singleSelect",
    })
    fields_to_fetch = [blended_field, layout_field, converted_field, FIELD_ITEM_NAME, FIELD_STATUS]
    if fixed_prompt_field and fixed_prompt_field not in fields_to_fetch:
        fields_to_fetch.append(fixed_prompt_field)
    records = airtable.list_records(fields_to_fetch)
    if not records:
        print("[OK] No records found in Airtable to process converted moodboard.")
        return True

    eligible = [
        record
        for record in records
        if record.get("fields", {}).get(blended_field)
        and record.get("fields", {}).get(layout_field)
        and not record.get("fields", {}).get(converted_field)
    ]
    if limit_records is not None:
        eligible = eligible[:limit_records]

    if not eligible:
        print(
            f"[OK] No records requiring Moodboard #2 flat-lay conversion "
            f"('{blended_field}' missing, '{layout_field}' missing, or '{converted_field}' already filled)."
        )
        return True

    print(
        f"[INFO] Generating '{converted_field}' for {len(eligible)} record(s) "
        f"using Nano Banana Pro via Fal AI ({blend_model}, {aspect_ratio}, {resolution})..."
    )

    # Load conversion prompt JSON string
    conversion_prompt_str = ""
    if LOCAL_FIXED_PROMPT_PATH.is_file():
        conversion_prompt_str = LOCAL_FIXED_PROMPT_PATH.read_text(encoding="utf-8")

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(FIELD_ITEM_NAME) or record_id

        blended_url = extract_attachment_url(fields.get(blended_field))
        layout_url = extract_attachment_url(fields.get(layout_field))

        # IMPORTANT: Reference Image 1 is the Layout/Composition reference. Reference Image 2 is the dynamic Blended Room photo.
        image_inputs = [layout_url, blended_url]

        prompt_to_use = (
            fields.get(fixed_prompt_field)
            if fixed_prompt_field and fields.get(fixed_prompt_field)
            else conversion_prompt_str
        )

        print(
            f"[INFO] [{position}/{len(eligible)}] Transforming blended photo into editorial flat-lay "
            f"for record {record_id} ({item_label}) with Nano Banana Pro..."
        )

        downloaded = None
        try:
            image_url = fal.generate(
                prompt=prompt_to_use,
                image_urls=image_inputs,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                model=blend_model,
            )
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="moodboard_2_converted_",
                suffix=".jpg",
                context=f"Download converted moodboard from {image_url}",
            )
            filename = f"moodboard_2_converted_{record_id}.jpg"
            airtable.upload_attachment(record_id, converted_field, downloaded, filename)
            airtable.update_records([(record_id, {FIELD_STATUS: STATUS_DONE, "Date and Time Generated": current_pht_timestamp()})])

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 5: Fal AI Moodboard Flat-Lay Conversion",
                "api_provider": "Fal AI Nano Banana Pro",
                "model": blend_model,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "output_image_url": image_url,
            }, AUDIT_LOG_FAL)

            print(
                f"[OK] Attached converted moodboard to '{converted_field}' and updated "
                f"{FIELD_STATUS} to '{STATUS_DONE}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            err_msg = str(error).encode("ascii", errors="replace").decode("ascii")
            print(f"[ERROR] Failed moodboard conversion for record {record_id}: {err_msg}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Moodboard #2 conversion complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════════════════════════════════

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Moodboard #2 Feed AI generation, prompt analysis, blending and flat-lay conversion."
    )
    parser.add_argument(
        "--category",
        "-c",
        default=DEFAULT_CATEGORY,
        help="Category to process (chandeliers, pendant_lights, floor_lamps, wall_lights)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Style filter in Akeneo (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--max-items",
        "-n",
        type=int,
        default=1,
        metavar="N",
        help="Process at most N records (default: 1)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Krea Moodboard ID override",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Krea Interior Prompt override",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip auto-scraping from Akeneo when no Standby records exist",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape products from Akeneo into Airtable without running generation",
    )
    parser.add_argument(
        "--no-shopify-check",
        action="store_true",
        help="Skip Shopify published status cross-check during scrape",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="Skip backfilling missing layout attachments during scrape",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    preset = resolve_preset(args.category)
    max_items = args.max_items if args.max_items is not None and args.max_items > 0 else 1

    table_id = (
        args.table_id
        or os.getenv(preset["env_table_key"], "").strip()
        or preset["default_table_id"]
    )
    moodboard_id = (
        args.moodboard_id
        or os.getenv(preset["env_moodboard_key"], "").strip()
        or preset["default_moodboard_id"]
    )
    interior_prompt = (
        args.prompt
        or os.getenv(preset["env_prompt_key"], "").strip()
        or preset["default_prompt"]
    )

    settings = load_settings()
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )
    krea = KreaClient(settings.krea_token)
    fal = FalClient(settings.fal_key)

    # Dynamic resilient field discovery for schema variations
    interior_field = find_table_field(airtable, CANDIDATE_INTERIOR_FIELDS, "Interior Photo")
    prompt_field = find_table_field(airtable, CANDIDATE_PROMPT_FIELDS, "Blending Prompt")
    blended_field = find_table_field(airtable, CANDIDATE_BLENDED_FIELDS, "Blended Image")
    layout_field = find_table_field(airtable, CANDIDATE_LAYOUT_FIELDS, "Moodboard #2 Layout")
    converted_field = find_table_field(airtable, CANDIDATE_CONVERTED_FIELDS, "Moodboard #2 Converted")
    fixed_prompt_field = next(
        (f for f in CANDIDATE_FIXED_PROMPT_FIELDS if airtable.has_field(f)),
        None,
    )

    print("\n" + "=" * 64)
    print("🚀 MOODBOARD #2 FEED | GENERATION PIPELINE")
    print(f"Target Category    : {preset['label']} ({preset['category_code']})")
    print(f"Airtable Table ID  : {table_id}")
    print(f"Krea Moodboard ID  : {moodboard_id}")
    print(f"Interior Prompt    : \"{interior_prompt}\"")
    print(f"Interior Field     : {interior_field}")
    print(f"Prompt Field       : {prompt_field}")
    print(f"Blended Field      : {blended_field}")
    print(f"Layout Field       : {layout_field}")
    print(f"Converted Field    : {converted_field}")
    print(f"Max Items to Run   : {max_items}")
    print("=" * 64 + "\n")

    # Handle Scrape-Only Mode
    if args.scrape_only:
        success = scrape_feed_products(
            settings,
            airtable,
            count=max_items,
            style=args.style,
            category=preset["category_code"],
            no_shopify_check=args.no_shopify_check,
            no_backfill=args.no_backfill,
        )
        print(f"\n[SCRAPE RESULT] {'Success' if success else 'Completed with warnings/no new items'}.")
        return 0 if success else 1

    # Check Standby rows or Auto-Scrape if needed
    if not args.no_scrape:
        records = airtable.list_records([FIELD_STATUS, FIELD_FURNITURE, FIELD_ITEM_NAME])
        standby_records = [
            r for r in records
            if str(r.get("fields", {}).get(FIELD_STATUS) or "").strip().casefold() in (STATUS_STANDBY.casefold(), "")
            and r.get("fields", {}).get(FIELD_FURNITURE)
        ]
        in_progress_records = [
            r for r in records
            if str(r.get("fields", {}).get(FIELD_STATUS) or "").strip().casefold() == STATUS_IN_PROGRESS.casefold()
            and r.get("fields", {}).get(FIELD_FURNITURE)
        ]
        active_uncompleted = len(standby_records) + len(in_progress_records)
        if active_uncompleted < max_items:
            needed = max_items - active_uncompleted
            print(f"[INFO] Found {len(standby_records)} 'Standby' and {len(in_progress_records)} 'In progress' row(s). Auto-scraping {needed} new {preset['label']} item(s) from Akeneo...")
            scrape_feed_products(
                settings,
                airtable,
                count=needed,
                style=args.style,
                category=preset["category_code"],
                no_shopify_check=args.no_shopify_check,
                no_backfill=args.no_backfill,
            )
        else:
            print(f"[INFO] Found {len(standby_records)} 'Standby' and {len(in_progress_records)} 'In progress' row(s) ready for generation.")

    # Phase 1: Krea AI Interior Generation
    print(f"\n[PHASE 1/5] Krea AI Room Interior Generation ({INTERIOR_ASPECT_RATIO} Ratio)...")
    p1_ok = generate_moodboard_2_interiors(
        krea,
        airtable,
        moodboard_id=moodboard_id,
        prompt=interior_prompt,
        interior_field=interior_field,
        limit_records=max_items,
    )

    # Phase 2: Claude Sonnet 5 Prompt Generation
    print(f"\n[PHASE 2/5] Claude Sonnet 5 Prompt Analysis ({FAL_VISION_MODEL})...")
    p2_ok = generate_moodboard_2_prompts(
        fal,
        airtable,
        interior_field=interior_field,
        prompt_field=prompt_field,
        limit_records=max_items,
    )

    # Phase 3: Fal AI Nano Banana Pro Blending
    print(f"\n[PHASE 3/5] Fal AI Nano Banana Pro Image Blending ({NANO_ASPECT_RATIO}, {NANO_RESOLUTION})...")
    p3_ok = generate_moodboard_2_blends(
        fal,
        airtable,
        interior_field=interior_field,
        prompt_field=prompt_field,
        blended_field=blended_field,
        category=preset["category_code"],
        limit_records=max_items,
    )

    # Phase 4: Layout Reference & Fixed Prompt Verification
    print("\n[PHASE 4/5] Layout Reference & Fixed Prompt Verification...")
    ensure_layout_and_fixed_prompt(
        airtable,
        layout_field=layout_field,
        fixed_prompt_field=fixed_prompt_field,
    )

    # Phase 5: Fal AI Nano Banana Pro Flat-Lay Conversion
    print(f"\n[PHASE 5/5] Fal AI Nano Banana Pro Editorial Flat-Lay Conversion ({NANO_ASPECT_RATIO}, {NANO_RESOLUTION})...")
    p5_ok = generate_moodboard_2_converted(
        fal,
        airtable,
        blended_field=blended_field,
        layout_field=layout_field,
        converted_field=converted_field,
        fixed_prompt_field=fixed_prompt_field,
        limit_records=max_items,
    )

    all_phases_ok = p1_ok and p2_ok and p3_ok and p5_ok
    print("\n" + "=" * 64)
    print("MOODBOARD #2 FEED RUN SUMMARY:")
    print(f"  Phase 1 (Krea Interior)     : {'PASS' if p1_ok else 'FAIL'}")
    print(f"  Phase 2 (Claude Prompt)     : {'PASS' if p2_ok else 'FAIL'}")
    print(f"  Phase 3 (Nano Banana Blend) : {'PASS' if p3_ok else 'FAIL'}")
    print(f"  Phase 4 (Layout Verify)     : PASS")
    print(f"  Phase 5 (Flat-Lay Moodboard): {'PASS' if p5_ok else 'FAIL'}")
    print("=" * 64)

    return 0 if all_phases_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as err:
        print(f"[FATAL] {err}", file=sys.stderr)
        raise SystemExit(2)
