"""Collection Category Feed (5 Products, 5 Interiors) Complete Automation Pipeline.

Target Table: Collection Category Feed (tbl5o1j3XvUaUqmjs)

Phases:
1. Akeneo Multi-Category Scrape (Newest to Oldest):
   Packs 5 distinct lighting product categories into 1 Airtable row:
   - Slot 1: Chandelier (chandeliers) -> Furniture Item1, Item Name1
   - Slot 2: Floor Lamp (floor_lamps) -> Furniture Item2, Item Name2
   - Slot 3: Table Lamp (table_lamps) -> Furniture item3 / Furniture Item3, Item Name3
   - Slot 4: Pendant Light (pendant_lights) -> Furniture Item4, Item Name4
   - Slot 5: Linear Chandelier (linear_chandeliers) -> Furniture Item5, Item Name5
   Sets Status -> 'Standby'.

2. Krea AI Sequential Interior Generation (4:5 Ratio):
   Uses moodboard ID b5ffdcbb-192e-4528-8d86-d1a4cf496887 with cumulative style referencing:
   - Interior1: Living room (no style ref) -> Interior1
   - Interior2: Bedroom (Ref: Interior1, strength 1.0) -> Interior2
   - Interior3: Dining room (Refs: Interior1, Interior2, strength 1.0 each) -> Interior3
   - Interior4: Kitchen (Refs: Interior1, Interior2, Interior3, strength 1.0 each) -> Interior4
   - Interior5: Luxury Open Living/Dining (Refs: Interior1..4, strength 1.0 each) -> Interior5
   Sets Status -> 'Processing'.

3. Fal AI Claude Sonnet Vision Prompt Analysis:
   Generates 5 tailored JSON blending prompts for each (Interior[i], Furniture Item[i]) pair
   into Blending Prompt1, Blending Prompt2, Blending Prompt3, Blending Prompt4, Blending Prompt5.

4. Fal AI Nano Banana Pro Blending (4:5 Ratio):
   Blends the 5 products into their respective interiors at 1728x2368 (4:5)
   and uploads them to Blended Image1 through Blended Image5.
   Sets Status -> 'Done'.

Usage:
    python run_collection_category_feed.py
    python run_collection_category_feed.py --phase all --execute
    python run_collection_category_feed.py --phase 1 --max-rows 1 --execute
    python run_collection_category_feed.py --phase 2 --execute
    python run_collection_category_feed.py --phase 3 --execute
    python run_collection_category_feed.py --phase 4 --execute
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import functools
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import requests

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AssetValidationError, AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename, download_to_temp_file
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
    os.getenv("AIRTABLE_TABLE_ID_COLLECTION_CATEGORY_FEED", "").strip()
    or "tbl5o1j3XvUaUqmjs"
)
DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_COLLECTION_CATEGORY_FEED", "").strip()
    or "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
)

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_PROCESSING = "Processing"
STATUS_DONE = "Done"

KREA_ASPECT_RATIO = "4:5"
KREA_RESOLUTION = "1K"
KREA_MOODBOARD_STRENGTH = 0.23
KREA_STYLE_REF_STRENGTH = 0.5

# ── Fal AI Models (Nano Banana Pro + Claude Sonnet vision) ───────────────
FAL_VISION_MODEL = (
    os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
)
FAL_BLENDING_MODEL = (
    os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
)
FAL_BLEND_ASPECT_RATIO = "4:5"
FAL_BLEND_RESOLUTION = "1K"

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
        interior_prompt="Generate me a bedroom",
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
        interior_prompt="Generate me a dining room",
    ),
    SlotConfig(
        slot_index=4,
        label="Pendant Light",
        akeneo_category="pendant_lights",
        keyword_filter=None,
        exclude_keywords=(),
        furniture_field_candidates=("Furniture Item4", "Furniture Item 4"),
        item_name_field="Item Name4",
        interior_field_candidates=("Interior4", "Interior 4"),
        blending_prompt_field="Blending Prompt4",
        blended_image_field_candidates=("Blended Image4", "Blended Image 4"),
        interior_prompt="Generate me a kitchen room interior",
    ),
    SlotConfig(
        slot_index=5,
        label="Linear Chandelier",
        akeneo_category="chandeliers",
        keyword_filter="linear",
        exclude_keywords=(),
        furniture_field_candidates=("Furniture Item5", "Furniture Item 5"),
        item_name_field="Item Name5",
        interior_field_candidates=("Interior5", "Interior 5"),
        blending_prompt_field="Blending Prompt5",
        blended_image_field_candidates=("Blended Image5", "Blended Image 5"),
        interior_prompt="Generate me an open concept luxury living and dining room with a long dining table",
    ),
]


# ── Audit Logging ────────────────────────────────────────────────────────

AUDIT_LOG_DIR = Path("output") / "logs"
AUDIT_LOG_AKENEO = AUDIT_LOG_DIR / "collection_category_feed_akeneo_logs.json"
AUDIT_LOG_KREA = AUDIT_LOG_DIR / "collection_category_feed_krea_logs.json"
AUDIT_LOG_QWEN_FLASH = AUDIT_LOG_DIR / "collection_category_feed_qwen_flash_logs.json"
AUDIT_LOG_QWEN_IMAGE = AUDIT_LOG_DIR / "collection_category_feed_qwen_image_logs.json"


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
# PHASE 1: Akeneo Multi-Category Scraper (Newest to Oldest)
# ══════════════════════════════════════════════════════════════════════════

def scrape_single_new_row(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    *,
    style: str = "modern",
    execute: bool = True,
) -> str | None:
    """Scrape 1 new row (5 products across 5 categories, newest to oldest) into Airtable."""
    records = airtable.list_records()
    existing_identities = collect_existing_identities(records)
    known_fields = airtable.table_fields()

    slot_picked: dict[int, ProductItem] = {}

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

        picked: ProductItem | None = None
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

            picked = item
            break

        if not picked:
            print(f"  [WARN] No eligible new product found for Slot {slot.slot_index}: {slot.label}")
            return None

        slot_picked[slot.slot_index] = picked

    row_fields: dict[str, Any] = {STATUS_FIELD: STATUS_STANDBY}
    log_items: list[dict[str, Any]] = []

    print("\n--- Selected New Products for Row ---")
    for slot in SLOTS:
        item = slot_picked[slot.slot_index]
        clean_name = item.item_name.split("|")[0].strip() if "|" in item.item_name else item.item_name
        row_fields[slot.item_name_field] = clean_name
        log_items.append({
            "slot": slot.slot_index,
            "label": slot.label,
            "sku": item.sku,
            "name": clean_name,
            "media_code": item.media_code,
        })
        print(f"  Slot {slot.slot_index} ({slot.label}): [{item.sku}] {clean_name}")

    if not execute:
        print(f"  [DRY RUN] Would create Airtable record with fields: {list(row_fields.keys())}")
        return "dry_run_record_id"

    created_res = airtable.create_record(row_fields)
    record_id = created_res["id"] if isinstance(created_res, dict) else str(created_res)
    print(f"  [OK] Created Airtable record {record_id} with Status '{STATUS_STANDBY}'")

    for slot in SLOTS:
        item = slot_picked[slot.slot_index]
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
            "phase": "Phase 1: Akeneo Multi-Category Scrape (Newest to Oldest)",
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
    """Scrape 5 products (one per slot) newest to oldest into Airtable rows."""
    print("\n" + "=" * 70)
    print("PHASE 1: Akeneo Multi-Category Scrape (Newest to Oldest)")
    print(f"Target Table: {airtable.table_id} | Style: {style}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    # 1. Inspect existing Airtable records for deduplication
    print("[INFO] Fetching existing Airtable records for deduplication...")
    records = airtable.list_records()
    existing_identities = collect_existing_identities(records)
    print(f"[OK] Found {len(records)} existing record(s) with {len(existing_identities.names)} Name(s) / {len(existing_identities.photos)} Photo(s).")

    # 2. Fetch candidates for each category sorted by newest to oldest
    slot_candidates: dict[int, list[ProductItem]] = {}
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

        valid_items: list[ProductItem] = []
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

            valid_items.append(item)

        print(f"  Eligible new products available: {len(valid_items)}")
        slot_candidates[slot.slot_index] = valid_items

    max_possible_rows = min(len(slot_candidates[slot.slot_index]) for slot in SLOTS)
    if max_possible_rows == 0:
        print("\n[WARN] Not enough unique new products across all 5 categories to assemble a full row.")
        return True

    rows_to_create = max_possible_rows if max_rows is None else min(max_possible_rows, max_rows)
    print(f"\n[INFO] Assembling {rows_to_create} new row(s) (5 products per row)...")

    known_fields = airtable.table_fields()
    created_count = 0

    for row_idx in range(rows_to_create):
        print(f"\n--- Assembling Row {row_idx + 1}/{rows_to_create} ---")
        row_fields: dict[str, Any] = {STATUS_FIELD: STATUS_STANDBY}
        log_items: list[dict[str, Any]] = []

        for slot in SLOTS:
            item = slot_candidates[slot.slot_index][row_idx]
            furniture_field_name = resolve_field_name(known_fields, slot.furniture_field_candidates)
            item_name_field_name = slot.item_name_field

            clean_name = item.item_name.split("|")[0].strip() if "|" in item.item_name else item.item_name

            row_fields[item_name_field_name] = clean_name
            log_items.append({
                "slot": slot.slot_index,
                "label": slot.label,
                "sku": item.sku,
                "name": clean_name,
                "media_code": item.media_code,
            })
            print(f"  Slot {slot.slot_index} ({slot.label}): [{item.sku}] {clean_name}")

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
            item = slot_candidates[slot.slot_index][row_idx]
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
                "phase": "Phase 1: Akeneo Multi-Category Scrape (Newest to Oldest)",
                "items": log_items,
                "status": STATUS_STANDBY,
            },
            AUDIT_LOG_AKENEO,
        )
        created_count += 1

    print(f"\n[OK] Phase 1 completed: {created_count} row(s) successfully created on Airtable.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2: Krea AI Sequential Interior Generation (4:5 Ratio)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_2_for_record(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    execute: bool = True,
) -> bool:
    """Generate 5 sequential interior photos with cumulative style referencing for a specific record."""
    print(f"\n[PHASE 2] Krea AI Sequential Interiors (4:5) for Record: {record_id}")
    print(f"Moodboard ID: {moodboard_id} (str={KREA_MOODBOARD_STRENGTH}) | Style Ref Str: {KREA_STYLE_REF_STRENGTH} | Aspect Ratio: {KREA_ASPECT_RATIO}")

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
        print(f"    Prompt: \"{slot.interior_prompt}\"")
        print(f"    Cumulative Style References: {len(style_refs)} image(s)")
        for s_idx, ref in enumerate(style_refs, 1):
            print(f"      Ref {s_idx}: {ref['url'][:60]}... (str={ref['strength']})")

        if not execute:
            print(f"    [DRY RUN] Would generate Krea interior for {interior_field_name}")
            continue

        print(f"    Generating image via Krea AI (medium, 4:5)...")
        image_url = krea.generate(
            slot.interior_prompt,
            aspect_ratio=KREA_ASPECT_RATIO,
            resolution=KREA_RESOLUTION,
            moodboard_id=moodboard_id,
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
                "phase": "Phase 2: Krea AI Sequential Interior Generation (4:5 Ratio)",
                "moodboard_id": moodboard_id,
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
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Generate 5 sequential interior photos with cumulative style referencing across records."""
    print("\n" + "=" * 70)
    print("PHASE 2: Krea AI Sequential Interior Generation (4:5 Ratio)")
    print(f"Moodboard ID: {moodboard_id} | Aspect Ratio: {KREA_ASPECT_RATIO}")
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
        run_phase_2_for_record(krea, airtable, record_id, moodboard_id=moodboard_id, execute=execute)

    print("\n[OK] Phase 2 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3: Fal AI (Claude Sonnet Vision) Prompt Analysis
# ══════════════════════════════════════════════════════════════════════════

def run_phase_3_for_record(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Analyze Interior and Furniture Item pairs and generate 5 blending prompts for a specific record."""
    print(f"\n[PHASE 3] Fal AI Claude Sonnet Vision Prompts for Record: {record_id}")
    record = airtable.get_record(record_id)
    fields = record.get("fields", {})

    prompt_updates: dict[str, str] = {}
    log_updates: dict[str, str] = {}

    for slot in SLOTS:
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

        print(f"  Generating prompt for Slot {slot.slot_index} ({slot.label} - '{item_name}')...")

        if not execute:
            print(f"    [DRY RUN] Would generate prompt for {slot.blending_prompt_field}")
            continue

        instruction = (
            f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the interior room "
            f"photo from 'Interior{slot.slot_index}' and Image 2 as the product photo for '{item_name}' "
            f"from '{slot.label}'.\n"
            f"Generate a detailed, highly specific, photorealistic image-blending prompt for Nano Banana Pro "
            f"(4:5 portrait aspect ratio). The prompt must describe naturally and elegantly integrating the "
            f"lighting fixture from Image 2 into the room interior from Image 1.\n"
            f"CRITICAL PRODUCT ISOLATION RULES:\n"
            f"1. The product shown in Image 2 MUST BE THE ONLY LIGHTING FIXTURE / LAMP of its kind in the final scene.\n"
            f"2. If Image 1 contains ANY pre-existing competing light fixtures or lamps, explicitly instruct to remove and replace them so that ONLY the product from Image 2 is installed.\n"
            f"3. Strictly exclude unnecessary, extra, competing furniture items, duplicate fixtures, or clutter.\n"
            f"4. Ensure realistic lighting direction, soft cast shadows, reflections on surfaces, and architectural harmony.\n\n"
            f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
        )

        generated_prompt = fal.generate_vision_prompt(
            image_urls=[interior_url, furniture_url],
            prompt=instruction,
            model=FAL_VISION_MODEL,
        ).strip().strip('"').strip("'")

        prompt_updates[slot.blending_prompt_field] = generated_prompt
        log_updates[slot.blending_prompt_field] = generated_prompt
        print(f"    [OK] Prompt generated successfully ({len(generated_prompt)} chars).")

    if execute and prompt_updates:
        airtable.update_records([(record_id, prompt_updates)])
        print(f"  [OK] Saved {len(prompt_updates)} prompt(s) to Airtable record {record_id}")
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 3: Fal AI Claude Sonnet Vision Prompt Analysis",
                "model": FAL_VISION_MODEL,
                "updates": log_updates,
            },
            AUDIT_LOG_QWEN_FLASH,
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
    """Analyze Interior and Furniture Item pairs and generate 5 blending prompts across records."""
    print("\n" + "=" * 70)
    print("PHASE 3: Fal AI Claude Sonnet Vision Blending Prompt Analysis")
    print(f"Model: {FAL_VISION_MODEL}")
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

        has_all_prompts = all(
            bool(fields.get(slot.blending_prompt_field)) for slot in SLOTS
        )
        if not has_all_prompts:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing blending prompts.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Blending Prompt1..5.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Record {record_id} ---")
        run_phase_3_for_record(fal, airtable, record_id, execute=execute)

    print("\n[OK] Phase 3 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4: Fal AI Nano Banana Pro Blending (4:5 Ratio)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_4_for_record(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Blend products into interior scenes using Fal AI Nano Banana Pro at 4:5 ratio for a specific record."""
    print(f"\n[PHASE 4] Fal AI Nano Banana Pro Blending (4:5) for Record: {record_id}")

    if execute:
        required_fields = {
            "Blended Image1": "multipleAttachments",
            "Blended Image2": "multipleAttachments",
            "Blended Image3": "multipleAttachments",
            "Blended Image4": "multipleAttachments",
            "Blended Image5": "multipleAttachments",
        }
        airtable.ensure_fields(required_fields)

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})
    known_fields = airtable.table_fields()

    blended_log_entries: list[dict[str, Any]] = []
    all_slots_succeeded = True

    for slot in SLOTS:
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
        print(f"\n  [Slot {slot.slot_index}: {slot.label} - '{item_name}']")
        print(f"    Target Field: {blended_field_name}")

        if not execute:
            print(f"    [DRY RUN] Would blend image using {FAL_BLENDING_MODEL} at {FAL_BLEND_ASPECT_RATIO}")
            continue

        try:
            print(f"    Sending image blending request to Fal AI Nano Banana Pro...")
            blend_prompt_text = (
                f"STRICT INSTRUCTION: Replace and remove any competing light fixtures from the interior room photo. "
                f"Place ONLY the target {slot.label} product ('{item_name}') into the room naturally.\n\n"
                f"{blending_prompt}"
            )
            blended_url = fal.generate(
                prompt=blend_prompt_text,
                image_urls=[interior_url, furniture_url],
                aspect_ratio=FAL_BLEND_ASPECT_RATIO,
                resolution=FAL_BLEND_RESOLUTION,
                model=FAL_BLENDING_MODEL,
            )
            print(f"    [OK] Blended image generated: {blended_url}")

            resp = requests.get(blended_url, timeout=60, stream=True)
            downloaded = download_to_temp_file(
                resp,
                prefix=f"blended_{slot.slot_index}_",
                suffix=".jpg",
                context="Download blended image",
            )

            print(f"    Uploading to Airtable field '{blended_field_name}'...")
            airtable.upload_attachment(
                record_id,
                blended_field_name,
                downloaded.path,
                filename=f"Blended_Image{slot.slot_index}_{record_id}.jpg",
            )
            downloaded.cleanup()

            blended_log_entries.append({
                "slot": slot.slot_index,
                "label": slot.label,
                "target_field": blended_field_name,
                "image_url": blended_url,
                "aspect_ratio": FAL_BLEND_ASPECT_RATIO,
            })
        except Exception as err:
            print(f"    [ERROR] Failed blending Slot {slot.slot_index}: {err}")
            all_slots_succeeded = False

    if execute and blended_log_entries:
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 4: Fal AI Nano Banana Pro Blending (4:5 Ratio)",
                "model": FAL_BLENDING_MODEL,
                "aspect_ratio": FAL_BLEND_ASPECT_RATIO,
                "slots": blended_log_entries,
            },
            AUDIT_LOG_QWEN_IMAGE,
        )

    if execute and all_slots_succeeded:
        update_record_status(airtable, record_id, STATUS_DONE)
        print(f"  [OK] All 5 slots blended. Updated record {record_id} Status -> '{STATUS_DONE}'")

    print(f"[OK] Phase 4 completed for {record_id}.")
    return True


def run_phase_4_blend(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Blend products into interior scenes across records using Fal AI Nano Banana Pro at 4:5 ratio."""
    print("\n" + "=" * 70)
    print("PHASE 4: Fal AI Nano Banana Pro Blending (4:5 Ratio)")
    print(f"Model: {FAL_BLENDING_MODEL} | Aspect Ratio: {FAL_BLEND_ASPECT_RATIO}")
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

        has_all_blended = all(
            get_field_val(fields, slot.blended_image_field_candidates) for slot in SLOTS
        )
        if not has_all_blended:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing image blending.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Blended Image1..5.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Blending Record {record_id} ---")
        run_phase_4_for_record(fal, airtable, record_id, execute=execute)

    print("\n[OK] Phase 4 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# CONTINUOUS ROW-BY-ROW PIPELINE (Phase 1 -> 2 -> 3 -> 4 -> Next Row)
# ══════════════════════════════════════════════════════════════════════════

def run_continuous_row_pipeline(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    krea: KreaClient,
    fal: FalClient,
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    style: str = "modern",
    max_rows: int | None = None,
    execute: bool = True,
) -> bool:
    """Execute complete end-to-end pipeline (Phases 1 to 4) row by row continuously."""
    print("\n" + "=" * 70)
    print(" CONTINUOUS COLLECTION CATEGORY FEED PIPELINE (ROW-BY-ROW)")
    print(f" Target Table: {airtable.table_id} | Moodboard: {moodboard_id}")
    print(f" Mode: {'EXECUTE' if execute else 'DRY RUN'}")
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

            # Phase 2: Krea Interiors
            run_phase_2_for_record(krea, airtable, rec_id, moodboard_id=moodboard_id, execute=execute)

            # Phase 3: Fal AI Vision Prompts
            run_phase_3_for_record(fal, airtable, rec_id, execute=execute)

            # Phase 4: Fal AI Nano Banana Pro Blending (Blends all 5 slots -> sets Status = 'Done')
            run_phase_4_for_record(fal, airtable, rec_id, execute=execute)

            processed_rows += 1
            print(f"\n[DONE] Row {processed_rows} ({rec_id}) is completely finished and marked 'Done'!")
            print("Resetting and proceeding to next row...\n")
            continue

        # Step 2: If no unfinished row exists, scrape 1 new row from Akeneo (Newest -> Oldest)
        print(f"\n{'=' * 70}")
        print(f"[ROW {processed_rows + 1}] Scraping 1 new row from Akeneo across 5 categories...")
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
        run_phase_2_for_record(krea, airtable, new_rec_id, moodboard_id=moodboard_id, execute=execute)

        # Step 4: Phase 3 for this new row
        run_phase_3_for_record(fal, airtable, new_rec_id, execute=execute)

        # Step 5: Phase 4 for this new row
        run_phase_4_for_record(fal, airtable, new_rec_id, execute=execute)

        processed_rows += 1
        print(f"\n[DONE] Row {processed_rows} ({new_rec_id}) is completely finished and marked 'Done'!")
        print("Resetting and proceeding to next row...\n")

    return True


# ══════════════════════════════════════════════════════════════════════════
# Master Runner & CLI
# ══════════════════════════════════════════════════════════════════════════

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Collection Category Feed (5 Products, 5 Interiors) Complete Automation Pipeline"
    )
    parser.add_argument(
        "--phase",
        "-p",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Phase to execute (1: Scrape, 2: Krea, 3: Fal Vision Prompts, 4: Fal Blend, all: Continuous Row-by-Row Pipeline). Default: all",
    )
    parser.add_argument(
        "--table-id",
        default=DEFAULT_TABLE_ID,
        help=f"Airtable destination table ID (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--moodboard-id",
        default=DEFAULT_MOODBOARD_ID,
        help=f"Krea AI moodboard ID (default: {DEFAULT_MOODBOARD_ID})",
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
    print(" COLLECTION CATEGORY FEED AUTOMATION PIPELINE (tbl5o1j3XvUaUqmjs)")
    print("=" * 70)
    print("Select a phase to run:")
    print("  [1] Phase 1: Akeneo Multi-Category Scrape (Newest to Oldest)")
    print("  [2] Phase 2: Krea AI Sequential Interior Generation (4:5)")
    print("  [3] Phase 3: Fal AI Claude Sonnet Vision Blending Prompt Analysis")
    print("  [4] Phase 4: Fal AI Nano Banana Pro Blending (4:5)")
    print("  [5] Run Complete Continuous Row Pipeline (Phase 1 -> 2 -> 3 -> 4 -> Next Row)")
    print("  [Q] Quit")
    print("-" * 70)

    choice = input("Enter choice (1-5 or Q) [default: 5]: ").strip().upper()
    if choice in ("Q", "QUIT", "EXIT"):
        sys.exit(0)

    phase_map = {
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
        "5": "all",
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
    moodboard_id = args.moodboard_id or DEFAULT_MOODBOARD_ID

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
    fal = FalClient(api_key=settings.fal_key)

    print(f"\n[START] Collection Category Feed Pipeline | Phase: {phase.upper()} | Execute: {execute}")

    # Continuous row-by-row pipeline
    if phase == "all":
        run_continuous_row_pipeline(
            akeneo,
            airtable,
            krea,
            fal,
            moodboard_id=moodboard_id,
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
            moodboard_id=moodboard_id,
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
