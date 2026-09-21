"""Collection Category Feed (5 Products, 5 Interiors) Complete Automation Pipeline.

Target Table: Collection Category Feed (tbl5o1j3XvUaUqmjs)

Workflow Architecture:
1. Sequential Krea AI Room Interiors (4:5 Ratio):
   Generates 5 distinct photos using dedicated per-slot moodboard IDs and cumulative style references:
   - Interior1: Modern exterior photo (Moodboard: ec860c16-10e4-429e-bba6-ff068bcb80b1, no ref)
   - Interior2: Modern bedroom (Moodboard: 06fcc401-2e66-4638-b581-45220a8b497e, no ref)
   - Interior3: Modern dining room (Moodboard: 0844ad92-c34a-4dc8-9d70-d09498dc098c, Ref: Interior2)
   - Interior4: Modern kitchen (Moodboard: 994a703c-4c6b-498a-bb27-7609615a74bd, Refs: Interior2, Interior3)
   - Interior5: Modern living room (Moodboard: de6ad512-870d-4ab7-a48c-3f3ca85faf24, Refs: Interior2..4)
   Sets Status -> 'Processing'.

2. Claude Sonnet 5 Vision Analysis (Room Matching & Non-Duplicate Suggestion):
   Analyzes Interior2, Interior3, Interior4, Interior5 simultaneously via Fal AI.
   Strict 1-to-1 non-duplicate assignment across 4 lighting categories:
   - 'chandeliers' (Chandelier)
   - 'pendant_lights' (Pendant Light)
   - 'floor_lamps' (Floor Lamp)
   - 'table_lamps' (Table Lamp)
   Populates multiline fields:
   - Suggest Furniture Item2
   - Suggest Furniture Item3
   - Suggested Furniture Item4 (Airtable schema has 'Suggested')
   - Suggest Furniture Item5

3. Targeted Akeneo Catalog Scraper:
   Parses the assigned category from each Suggest field and queries Akeneo for the
   newest available 'modern' product, deduplicated against all existing table items.
   Populates:
   - Furniture Item2 + Item Name2
   - Furniture item3 + Item Name3 (Airtable schema has 'Furniture item3')
   - Furniture Item4 + Item Name4
   - Furniture Item5 + Item Name5
   (Slot 1 is left blank as Interior1 serves as exterior cover).

4. Claude Sonnet 5 Blending Prompt Engineering:
   Generates tailored commercial lighting blending prompts for Slots 2 to 5 into:
   - Blending Prompt2, Blending Prompt3, Blending Prompt4, Blending Prompt5
   (Blending Prompt1 is left blank).

5. Fal AI Nano Banana Pro Image Blending (4:5 Ratio):
   - Slot 1: Copies Interior1 directly to Blended Image1 (clean cover slide).
   - Slots 2 to 5: Blends (Interior[i], Furniture Item[i]) using Blending Prompt[i]
     via Fal AI Nano Banana Pro (fal-ai/nano-banana-pro/edit) at 4:5 aspect ratio
     into Blended Image2, Blended Image3, Blended Image4, Blended Image5.
   Sets Status -> 'Done'.

Usage:
    python run_collection_category_feed.py
    python run_collection_category_feed.py --phase all --execute
    python run_collection_category_feed.py --target-record recG4x8RgQXO5kWEs --phase all --execute
    python run_collection_category_feed.py --phase 1 --execute
    python run_collection_category_feed.py --phase 2 --execute
    python run_collection_category_feed.py --phase 3 --execute
    python run_collection_category_feed.py --phase 4 --execute
    python run_collection_category_feed.py --phase 5 --execute
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
from content_automation.prompts import build_vision_blending_instruction
from content_automation.krea_client import KreaClient
from content_automation.media import DownloadedMedia, attachment_filename, download_to_temp_file
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    product_item,
)
from content_automation.shopify_client import ShopifyCatalogIndex, ShopifyClient

print = functools.partial(print, flush=True)

# ── Timezone & Configuration ─────────────────────────────────────────────

PHT = timezone(timedelta(hours=8))  # Philippine Standard Time (UTC+8)


def pht_timestamp() -> str:
    return datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")


DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_COLLECTION_CATEGORY_FEED", "").strip()
    or "tbl5o1j3XvUaUqmjs"
)

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_PROCESSING = "Processing"
STATUS_DONE = "Done"

TERMINAL_AND_PROTECTED_STATUSES = {
    "complete", "completed", "done", "finished",
    "posted", "scheduled", "schedule",
    "discard", "discarded",
    "for manual", "minor revision", "minor revisions", "fm",
}

KREA_ASPECT_RATIO = "4:5"
KREA_RESOLUTION = "1K"
KREA_MOODBOARD_STRENGTH = 0.23
KREA_STYLE_REF_STRENGTH = 0.5

FAL_BLENDING_MODEL = "fal-ai/nano-banana-pro/edit"
FAL_ASPECT_RATIO = "4:5"
CLAUDE_VISION_MODEL = "anthropic/claude-sonnet-5"

# ── Slot Definitions ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class SlotConfig:
    slot_index: int  # 1 to 5
    label: str
    room_type: str
    moodboard_id: str
    interior_prompt: str
    style_ref_slots: tuple[int, ...]  # Slots (by slot_index) used as style references
    interior_field_candidates: tuple[str, ...]
    suggest_field_candidates: tuple[str, ...]  # Applicable for Slots 2..5
    furniture_field_candidates: tuple[str, ...]  # Applicable for Slots 2..5
    item_name_field_candidates: tuple[str, ...]  # Applicable for Slots 2..5
    blending_prompt_field: str  # Applicable for Slots 2..5
    blended_image_field_candidates: tuple[str, ...]


SLOTS: list[SlotConfig] = [
    SlotConfig(
        slot_index=1,
        label="Modern Exterior",
        room_type="modern exterior photo",
        moodboard_id="ec860c16-10e4-429e-bba6-ff068bcb80b1",
        interior_prompt="generate me a modern exterior photo",
        style_ref_slots=(),
        interior_field_candidates=("Interior1", "Interior 1", "Interior"),
        suggest_field_candidates=(),
        furniture_field_candidates=("Furniture Item1", "Furniture Item 1"),
        item_name_field_candidates=("Item Name1", "Item Name 1"),
        blending_prompt_field="Blending Prompt1",
        blended_image_field_candidates=("Blended Image1", "Blended Image 1"),
    ),
    SlotConfig(
        slot_index=2,
        label="Modern Bedroom",
        room_type="modern bedroom",
        moodboard_id="06fcc401-2e66-4638-b581-45220a8b497e",
        interior_prompt="generate me a modern bedroom",
        style_ref_slots=(),
        interior_field_candidates=("Interior2", "Interior 2"),
        suggest_field_candidates=("Suggest Furniture Item2", "Suggest Furniture Item 2"),
        furniture_field_candidates=("Furniture Item2", "Furniture Item 2"),
        item_name_field_candidates=("Item Name2", "Item Name 2"),
        blending_prompt_field="Blending Prompt2",
        blended_image_field_candidates=("Blended Image2", "Blended Image 2"),
    ),
    SlotConfig(
        slot_index=3,
        label="Modern Dining Room",
        room_type="modern dining room",
        moodboard_id="0844ad92-c34a-4dc8-9d70-d09498dc098c",
        interior_prompt="generate me a modern dining room",
        style_ref_slots=(2,),
        interior_field_candidates=("Interior3", "Interior 3"),
        suggest_field_candidates=("Suggest Furniture Item3", "Suggest Furniture Item 3"),
        # Note: Airtable schema has 'Furniture item3' (lowercase 'item')
        furniture_field_candidates=("Furniture item3", "Furniture Item3", "Furniture Item 3"),
        item_name_field_candidates=("Item Name3", "Item Name 3"),
        blending_prompt_field="Blending Prompt3",
        blended_image_field_candidates=("Blended Image3", "Blended Image 3"),
    ),
    SlotConfig(
        slot_index=4,
        label="Modern Kitchen",
        room_type="modern kitchen",
        moodboard_id="994a703c-4c6b-498a-bb27-7609615a74bd",
        interior_prompt="generate me a modern kitchen",
        style_ref_slots=(2, 3),
        interior_field_candidates=("Interior4", "Interior 4"),
        # Note: Airtable schema has 'Suggested Furniture Item4' (with 'ed')
        suggest_field_candidates=("Suggested Furniture Item4", "Suggest Furniture Item4", "Suggest Furniture Item 4"),
        furniture_field_candidates=("Furniture Item4", "Furniture Item 4"),
        item_name_field_candidates=("Item Name4", "Item Name 4"),
        blending_prompt_field="Blending Prompt4",
        blended_image_field_candidates=("Blended Image4", "Blended Image 4"),
    ),
    SlotConfig(
        slot_index=5,
        label="Modern Living Room",
        room_type="modern living room",
        moodboard_id="de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        interior_prompt="generate me a modern living room",
        style_ref_slots=(2, 3, 4),
        interior_field_candidates=("Interior5", "Interior 5"),
        suggest_field_candidates=("Suggest Furniture Item5", "Suggest Furniture Item 5"),
        furniture_field_candidates=("Furniture Item5", "Furniture Item 5"),
        item_name_field_candidates=("Item Name5", "Item Name 5"),
        blending_prompt_field="Blending Prompt5",
        blended_image_field_candidates=("Blended Image5", "Blended Image 5"),
    ),
]

# 4 Lighting Categories for Claude analysis & Akeneo scraping
CATEGORY_MAPPINGS = {
    "chandeliers": {
        "label": "Chandelier",
        "keywords": ("chandelier", "chandeliers"),
    },
    "pendant_lights": {
        "label": "Pendant Light",
        "keywords": ("pendant", "pendant light", "pendant lights"),
    },
    "floor_lamps": {
        "label": "Floor Lamp",
        "keywords": ("floor lamp", "floor lamps"),
    },
    "table_lamps": {
        "label": "Table Lamp",
        "keywords": ("table lamp", "table lamps", "desk lamp"),
    },
}

# ── Audit Logging ────────────────────────────────────────────────────────

AUDIT_LOG_DIR = Path("output") / "logs"
AUDIT_LOG_KREA = AUDIT_LOG_DIR / "collection_category_feed_krea_logs.json"
AUDIT_LOG_CLAUDE = AUDIT_LOG_DIR / "collection_category_feed_claude_logs.json"
AUDIT_LOG_AKENEO = AUDIT_LOG_DIR / "collection_category_feed_akeneo_logs.json"
AUDIT_LOG_FAL = AUDIT_LOG_DIR / "collection_category_feed_fal_logs.json"


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

        sub_match = next((c for c in choices if desired_status.casefold() in c.casefold()), None)
        if sub_match:
            airtable.update_records([(record_id, {STATUS_FIELD: sub_match})])
            return

        airtable.update_records([(record_id, {STATUS_FIELD: choices[0]})])
    except Exception as err:
        print(f"  [WARN] Failed updating status for record {record_id}: {err}")


def download_image_url(url: str, prefix: str = "download_") -> DownloadedMedia:
    """Download an image from a URL into a local temporary file."""
    resp = requests.get(url, stream=True, timeout=90)
    resp.raise_for_status()
    return download_to_temp_file(resp, prefix=prefix, suffix=".jpg", context=f"Download {url}")


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
            name_val = str(get_field_val(fields, slot.item_name_field_candidates) or "").strip()
            if name_val:
                names.add(name_val.casefold())

            furniture_val = get_field_val(fields, slot.furniture_field_candidates)
            if isinstance(furniture_val, list):
                for att in furniture_val:
                    if isinstance(att, dict):
                        fn = str(att.get("filename") or "").strip().casefold()
                        if fn:
                            photos.add(fn)
                            if "_" in fn:
                                skus.add(fn.split("_")[0].strip().casefold())

    return ExistingIdentities(skus=skus, names=names, photos=photos)


def parse_category_from_suggestion(text: str) -> str:
    """Extract the Akeneo category key from Claude's suggestion text."""
    if not text:
        return "chandeliers"

    # 1. Look for explicit [CATEGORY: ...] tag
    match = re.search(r"\[CATEGORY:\s*([a-z_]+)\]", text, re.IGNORECASE)
    if match:
        cat = match.group(1).lower().strip()
        if cat in CATEGORY_MAPPINGS:
            return cat

    # 2. Check keywords in order of specificity
    lower = text.lower()
    if "table lamp" in lower or "desk lamp" in lower:
        return "table_lamps"
    if "floor lamp" in lower:
        return "floor_lamps"
    if "pendant" in lower:
        return "pendant_lights"
    if "chandelier" in lower:
        return "chandeliers"

    return "chandeliers"


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1: Krea AI Sequential Interior Generation (4:5 Ratio)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_1_for_record(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Generate 5 sequential interior photos for a record using dedicated moodboard IDs and cumulative references."""
    print(f"\n[PHASE 1] Krea AI Interior Generation (4:5 Ratio) for Record: {record_id}")

    if execute:
        required_fields = {
            "Interior1": "multipleAttachments",
            "Interior2": "multipleAttachments",
            "Interior3": "multipleAttachments",
            "Interior4": "multipleAttachments",
            "Interior5": "multipleAttachments",
            "Status": "singleSelect",
        }
        airtable.ensure_fields(required_fields)

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})
    known_fields = airtable.table_fields()

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

        # Build style references list according to slot configuration
        style_refs: list[dict[str, Any]] = []
        for ref_slot_idx in slot.style_ref_slots:
            if ref_slot_idx in generated_urls:
                style_refs.append({
                    "url": generated_urls[ref_slot_idx],
                    "strength": KREA_STYLE_REF_STRENGTH,
                })

        print(f"\n  [Slot {slot.slot_index}: {slot.label}]")
        print(f"    Moodboard ID: {slot.moodboard_id}")
        print(f"    Prompt: \"{slot.interior_prompt}\"")
        print(f"    Style References: {len(style_refs)} image(s)")
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
                "phase": "Phase 1: Krea AI Sequential Interior Generation (4:5 Ratio)",
                "slots": log_slots,
            },
            AUDIT_LOG_KREA,
        )
        update_record_status(airtable, record_id, STATUS_PROCESSING)

    print(f"[OK] Phase 1 completed for {record_id}.")
    return True


def run_phase_1_krea(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    target_record: str | None = None,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Generate 5 sequential interior photos across records needing interiors."""
    print("\n" + "=" * 70)
    print("PHASE 1: Krea AI Sequential Interior Generation (4:5 Ratio)")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    if target_record:
        print(f"[INFO] Targeting single record: {target_record}")
        return run_phase_1_for_record(krea, airtable, target_record, execute=execute)

    records = airtable.list_records()
    targets = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in TERMINAL_AND_PROTECTED_STATUSES:
            continue

        has_all_interiors = all(
            get_field_val(fields, slot.interior_field_candidates) for slot in SLOTS
        )
        if not has_all_interiors:
            targets.append(record)

    # If no records exist needing interiors, create 1 new record
    if not targets:
        if execute:
            print("[INFO] No existing standby records found. Creating 1 new row in Airtable...")
            created = airtable.create_record({STATUS_FIELD: STATUS_PROCESSING})
            new_id = created if isinstance(created, str) else created.get("id")
            print(f"[OK] Created new record: {new_id}")
            targets.append({"id": new_id, "fields": {STATUS_FIELD: STATUS_PROCESSING}})
        else:
            print("[OK] No records found needing interior generation.")
            return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Interior1..5 generation.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Record {record_id} ---")
        run_phase_1_for_record(krea, airtable, record_id, execute=execute)

    print("\n[OK] Phase 1 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2: Claude Sonnet 5 Vision Analysis (Room Matching & Suggestion)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_2_for_record(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Analyze Interior 2, 3, 4, 5 simultaneously with Claude Sonnet 5 to assign distinct lighting categories."""
    print(f"\n[PHASE 2] Claude Sonnet 5 Vision Analysis for Record: {record_id}")

    if execute:
        required_fields = {
            "Suggest Furniture Item2": "multilineText",
            "Suggest Furniture Item3": "multilineText",
            "Suggested Furniture Item4": "multilineText",
            "Suggest Furniture Item5": "multilineText",
        }
        airtable.ensure_fields(required_fields)

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})
    known_fields = airtable.table_fields()

    # Check if all 4 suggestions already exist
    room_slots = [s for s in SLOTS if s.slot_index in (2, 3, 4, 5)]
    all_suggestions_exist = all(
        get_field_val(fields, s.suggest_field_candidates) for s in room_slots
    )
    if all_suggestions_exist:
        print(f"  [OK] All suggestions already populated for record {record_id}.")
        return True

    # Gather the 4 interior image URLs
    room_urls: dict[int, str] = {}
    for slot in room_slots:
        val = get_field_val(fields, slot.interior_field_candidates)
        url = extract_attachment_url(val)
        if not url:
            print(f"  [ERROR] Slot {slot.slot_index} ({slot.label}) is missing an interior photo. Run Phase 1 first.")
            return False
        room_urls[slot.slot_index] = url

    print(f"  Analyzing 4 room interiors simultaneously (Slots 2, 3, 4, 5)...")
    print(f"    Interior 2: Bedroom ({room_urls[2][:60]}...)")
    print(f"    Interior 3: Dining Room ({room_urls[3][:60]}...)")
    print(f"    Interior 4: Kitchen ({room_urls[4][:60]}...)")
    print(f"    Interior 5: Living Room ({room_urls[5][:60]}...)")

    if not execute:
        print("    [DRY RUN] Would call Claude Sonnet 5 Vision analysis and populate Suggest Furniture Item2..5")
        return True

    instruction = (
        "You are an expert luxury interior designer and commercial lighting curator for Home Cartel.\n"
        "Analyze the 4 room interior photos provided:\n"
        "- Image 1: Modern Bedroom (Interior2)\n"
        "- Image 2: Modern Dining Room (Interior3)\n"
        "- Image 3: Modern Kitchen (Interior4)\n"
        "- Image 4: Modern Living Room (Interior5)\n\n"
        "TASK:\n"
        "You must assign EXACTLY ONE distinct lighting category to each of the 4 rooms with ZERO DUPLICATES.\n"
        "This is a strict 1-to-1 bijective mapping where all 4 of these categories must be used exactly once:\n"
        "1. 'chandeliers' (Chandelier)\n"
        "2. 'pendant_lights' (Pendant Light)\n"
        "3. 'floor_lamps' (Floor Lamp)\n"
        "4. 'table_lamps' (Table Lamp)\n\n"
        "CURATION GUIDELINES:\n"
        "- Dining rooms and luxury living rooms are prime candidates for a striking chandelier or statement pendant light, or living lounge for a sculptural floor lamp.\n"
        "- Kitchens frequently benefit from pendant lights over islands or dining spaces.\n"
        "- Bedrooms excel with ambient table lamps on nightstands/dressers or a slender floor lamp in a cozy corner.\n"
        "Evaluate the architectural layout, ceiling heights, and furniture arrangements in each room to make the most stunning, commercially effective pairing.\n\n"
        "CRITICAL: Return valid JSON ONLY with no extra commentary, following this exact schema:\n"
        "{\n"
        "  \"interior2\": {\n"
        "    \"category\": \"floor_lamps\" | \"table_lamps\" | \"chandeliers\" | \"pendant_lights\",\n"
        "    \"category_label\": \"Floor Lamp\" | \"Table Lamp\" | \"Chandelier\" | \"Pendant Light\",\n"
        "    \"suggested_description\": \"Specific recommendation of the ideal lighting fixture design, finish, silhouette, and placement for this bedroom.\",\n"
        "    \"reasoning\": \"Why this fixture category best elevates this bedroom.\"\n"
        "  },\n"
        "  \"interior3\": {\n"
        "    \"category\": \"floor_lamps\" | \"table_lamps\" | \"chandeliers\" | \"pendant_lights\",\n"
        "    \"category_label\": \"...\",\n"
        "    \"suggested_description\": \"...\",\n"
        "    \"reasoning\": \"...\"\n"
        "  },\n"
        "  \"interior4\": {\n"
        "    \"category\": \"floor_lamps\" | \"table_lamps\" | \"chandeliers\" | \"pendant_lights\",\n"
        "    \"category_label\": \"...\",\n"
        "    \"suggested_description\": \"...\",\n"
        "    \"reasoning\": \"...\"\n"
        "  },\n"
        "  \"interior5\": {\n"
        "    \"category\": \"floor_lamps\" | \"table_lamps\" | \"chandeliers\" | \"pendant_lights\",\n"
        "    \"category_label\": \"...\",\n"
        "    \"suggested_description\": \"...\",\n"
        "    \"reasoning\": \"...\"\n"
        "  }\n"
        "}\n\n"
        "Remember: Each of the 4 categories ('chandeliers', 'pendant_lights', 'floor_lamps', 'table_lamps') must be chosen EXACTLY ONCE."
    )

    image_urls = [room_urls[2], room_urls[3], room_urls[4], room_urls[5]]
    raw_response = fal.generate_vision_prompt(
        image_urls,
        instruction,
        model=CLAUDE_VISION_MODEL,
    )

    # Parse JSON output from Claude
    parsed: dict[str, Any] = {}
    try:
        clean_text = raw_response.strip()
        if "```" in clean_text:
            # Extract content inside markdown code fence
            fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
            if fence_match:
                clean_text = fence_match.group(1).strip()
        json_match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
    except Exception as err:
        print(f"  [WARN] Failed direct JSON parse from Claude response: {err}")

    # Fallback default assignment if parse failed or was incomplete
    available_cats = {"chandeliers", "pendant_lights", "floor_lamps", "table_lamps"}
    assigned_cats: dict[int, str] = {}

    for slot_idx, key in [(2, "interior2"), (3, "interior3"), (4, "interior4"), (5, "interior5")]:
        entry = parsed.get(key, {})
        cat = str(entry.get("category") or "").strip().lower()
        if cat in available_cats:
            assigned_cats[slot_idx] = cat
            available_cats.remove(cat)

    # Reconcile any missing or duplicate categories to ensure strict 1-to-1 mapping
    for slot_idx in (2, 3, 4, 5):
        if slot_idx not in assigned_cats:
            fallback_cat = next(iter(available_cats))
            assigned_cats[slot_idx] = fallback_cat
            available_cats.remove(fallback_cat)

    updates: dict[str, str] = {}
    log_updates: dict[str, Any] = {}

    for slot in room_slots:
        suggest_field_name = resolve_field_name(known_fields, slot.suggest_field_candidates)
        key = f"interior{slot.slot_index}"
        entry = parsed.get(key, {})

        cat = assigned_cats[slot.slot_index]
        cat_info = CATEGORY_MAPPINGS.get(cat, {"label": cat.replace("_", " ").title()})
        label = entry.get("category_label") or cat_info["label"]
        desc = entry.get("suggested_description") or f"Modern {label.lower()} with clean architectural lines."
        reason = entry.get("reasoning") or f"Provides ideal ambient and functional illumination for this {slot.room_type}."

        formatted_suggestion = (
            f"[CATEGORY: {cat}] {label}: {desc}\n\n"
            f"Placement Reasoning: {reason}"
        )

        updates[suggest_field_name] = formatted_suggestion
        log_updates[suggest_field_name] = {
            "category": cat,
            "category_label": label,
            "description": desc,
            "reasoning": reason,
        }
        print(f"  Slot {slot.slot_index} ({slot.label}) -> Assigned: {label} ({cat})")

    airtable.update_records([(record_id, updates)])
    print(f"  [OK] Saved 4 furniture recommendations to record {record_id}")

    append_audit_log(
        {
            "timestamp": pht_timestamp(),
            "record_id": record_id,
            "phase": "Phase 2: Claude Sonnet 5 Vision Analysis (Room Matching)",
            "model": CLAUDE_VISION_MODEL,
            "assignments": log_updates,
        },
        AUDIT_LOG_CLAUDE,
    )

    print(f"[OK] Phase 2 completed for {record_id}.")
    return True


def run_phase_2_claude(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    target_record: str | None = None,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Run Phase 2 Claude Vision Analysis across records needing room suggestions."""
    print("\n" + "=" * 70)
    print("PHASE 2: Claude Sonnet 5 Vision Analysis (Room Matching)")
    print(f"Model: {CLAUDE_VISION_MODEL}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    if target_record:
        print(f"[INFO] Targeting single record: {target_record}")
        return run_phase_2_for_record(fal, airtable, target_record, execute=execute)

    records = airtable.list_records()
    targets = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in TERMINAL_AND_PROTECTED_STATUSES:
            continue

        # Must have Interior2..5
        has_interiors = all(
            get_field_val(fields, s.interior_field_candidates)
            for s in SLOTS if s.slot_index in (2, 3, 4, 5)
        )
        if not has_interiors:
            continue

        # Check if missing any suggestion
        has_all_suggestions = all(
            get_field_val(fields, s.suggest_field_candidates)
            for s in SLOTS if s.slot_index in (2, 3, 4, 5)
        )
        if not has_all_suggestions:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing Claude room suggestions.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Claude room suggestions.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Record {record_id} ---")
        run_phase_2_for_record(fal, airtable, record_id, execute=execute)

    print("\n[OK] Phase 2 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3: Targeted Akeneo Catalog Scraper (Based on Claude Suggestions)
# ══════════════════════════════════════════════════════════════════════════

def run_phase_3_for_record(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    style: str = "modern",
    shopify_client: ShopifyClient | None = None,
    shopify_index: ShopifyCatalogIndex | None = None,
    shopify_cross_check: bool = True,
    execute: bool = True,
) -> bool:
    """Scrape newest available products from Akeneo matching the assigned categories in Suggest fields, with Shopify publication verification."""
    print(f"\n[PHASE 3] Targeted Akeneo Product Scraping for Record: {record_id}")
    if shopify_cross_check:
        print(f"  Shopify Catalog Cross-Check: ENABLED (verifies published on homecartel.net)")
    else:
        print(f"  Shopify Catalog Cross-Check: DISABLED")

    if execute:
        required_fields = {
            "Furniture Item2": "multipleAttachments",
            "Furniture item3": "multipleAttachments",
            "Furniture Item4": "multipleAttachments",
            "Furniture Item5": "multipleAttachments",
            "Item Name2": "singleLineText",
            "Item Name3": "singleLineText",
            "Item Name4": "singleLineText",
            "Item Name5": "singleLineText",
        }
        airtable.ensure_fields(required_fields)

    # Initialize Shopify catalog index if cross-checking is enabled
    if shopify_cross_check and shopify_index is None and execute:
        try:
            client = shopify_client or ShopifyClient()
            shopify_index = client.load_published_identities()
        except Exception as s_err:
            print(f"  [WARN] Shopify catalog index initialization note: {s_err}")

    all_records = airtable.list_records()
    existing_identities = collect_existing_identities(all_records)
    try:
        from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
        base_identities = fetch_all_base_existing_identities(airtable.base_id)
        existing_identities.skus.update(base_identities.skus)
        existing_identities.names.update(base_identities.names)
        existing_identities.photos.update(base_identities.photos)
        print(f"  [BASE-WIDE DEDUP] Loaded {len(existing_identities.skus)} SKUs across all base tables.")
    except Exception as base_dedup_err:
        print(f"  [WARN] Base-wide dedup note: {base_dedup_err}")
    known_fields = airtable.table_fields()

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})

    room_slots = [s for s in SLOTS if s.slot_index in (2, 3, 4, 5)]
    updates: dict[str, Any] = {}
    log_slots: list[dict[str, Any]] = []

    for slot in room_slots:
        furniture_field_name = resolve_field_name(known_fields, slot.furniture_field_candidates)
        item_name_field_name = resolve_field_name(known_fields, slot.item_name_field_candidates)

        existing_furniture = get_field_val(fields, slot.furniture_field_candidates)
        existing_name = get_field_val(fields, slot.item_name_field_candidates)

        if existing_furniture and existing_name:
            print(f"  Slot {slot.slot_index} ({slot.label}): Product already populated ('{existing_name}').")
            continue

        suggest_text = str(get_field_val(fields, slot.suggest_field_candidates) or "").strip()
        if not suggest_text:
            print(f"  [WARN] Slot {slot.slot_index} ({slot.label}): Missing Suggestion text. Run Phase 2 first.")
            continue

        cat_code = parse_category_from_suggestion(suggest_text)
        cat_label = CATEGORY_MAPPINGS.get(cat_code, {}).get("label", cat_code)

        print(f"\n  [Slot {slot.slot_index}: {slot.label}]")
        print(f"    Target Category: '{cat_code}' ({cat_label}) | Style: '{style}'")

        if not execute:
            print(f"    [DRY RUN] Would query Akeneo for newest '{cat_code}' and upload to {furniture_field_name}")
            continue

        query = {
            "categories": [{"operator": "IN", "value": [cat_code]}],
            "Style2": [{"operator": "IN", "value": [style]}],
            "enabled": [{"operator": "=", "value": True}],
        }
        raw_items = akeneo.fetch_products(query)
        raw_items.sort(
            key=lambda x: str(x.get("updated") or x.get("created") or ""),
            reverse=True,
        )

        picked: ProductItem | None = None
        skipped_shopify = 0
        for raw in raw_items:
            item = product_item(raw)
            if not item:
                continue

            # Deduplication against existing table records and currently picked items
            sku_norm = item.sku.strip().casefold()
            name_norm = item.item_name.strip().casefold()
            media_norm = item.media_code.strip().casefold()

            if sku_norm in existing_identities.skus:
                continue
            if name_norm in existing_identities.names:
                continue
            if any(media_norm in p for p in existing_identities.photos):
                continue

            # Shopify published catalog cross-check
            if shopify_cross_check and shopify_index:
                if not shopify_index.contains(item.sku, item.item_name):
                    skipped_shopify += 1
                    continue

            picked = item
            break

        if not picked:
            shopify_note = f" ({skipped_shopify} candidates skipped: not published on Shopify)" if skipped_shopify else ""
            print(f"    [WARN] No eligible unused modern product found in Akeneo for '{cat_code}'{shopify_note}.")
            continue

        verified_tag = " [Shopify Verified]" if (shopify_cross_check and shopify_index) else ""
        print(f"    Selected Product: '{picked.item_name}' (SKU: {picked.sku}){verified_tag}")
        existing_identities.skus.add(picked.sku.strip().casefold())
        existing_identities.names.add(picked.item_name.strip().casefold())
        existing_identities.photos.add(picked.media_code.strip().casefold())

        # Download media from Akeneo
        downloaded = akeneo.download_media(picked.media_code)
        filename = attachment_filename(picked.item_name, picked.media_code)

        print(f"    Uploading to Airtable '{furniture_field_name}'...")
        airtable.upload_attachment(
            record_id,
            furniture_field_name,
            downloaded.path,
            filename=filename,
        )
        if hasattr(downloaded, "cleanup"):
            downloaded.cleanup()
        elif Path(downloaded.path).exists():
            Path(downloaded.path).unlink(missing_ok=True)

        updates[item_name_field_name] = picked.item_name

        log_slots.append({
            "slot": slot.slot_index,
            "room": slot.label,
            "assigned_category": cat_code,
            "sku": picked.sku,
            "name": picked.item_name,
            "shopify_verified": bool(shopify_cross_check and shopify_index),
            "target_furniture_field": furniture_field_name,
        })

    if execute and updates:
        airtable.update_records([(record_id, updates)])
        print(f"  [OK] Updated product item names on record {record_id}")

    if execute and log_slots:
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 3: Targeted Akeneo Catalog Scraper",
                "scraped_items": log_slots,
            },
            AUDIT_LOG_AKENEO,
        )

    print(f"[OK] Phase 3 completed for {record_id}.")
    return True


def run_phase_3_scrape(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    *,
    style: str = "modern",
    target_record: str | None = None,
    max_rows: int | None = None,
    shopify_cross_check: bool = True,
    execute: bool = False,
) -> bool:
    """Scrape products matching Claude suggestions across records needing products."""
    print("\n" + "=" * 70)
    print("PHASE 3: Targeted Akeneo Catalog Scraper (with Shopify Cross-Check)")
    print(f"Style: {style} | Shopify Check: {'ENABLED' if shopify_cross_check else 'DISABLED'} | Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    shopify_index: ShopifyCatalogIndex | None = None
    if shopify_cross_check and execute:
        try:
            shopify = ShopifyClient()
            shopify_index = shopify.load_published_identities()
        except Exception as s_err:
            print(f"[WARN] Shopify catalog index initialization note: {s_err}")

    if target_record:
        print(f"[INFO] Targeting single record: {target_record}")
        return run_phase_3_for_record(
            akeneo,
            airtable,
            target_record,
            style=style,
            shopify_index=shopify_index,
            shopify_cross_check=shopify_cross_check,
            execute=execute,
        )

    records = airtable.list_records()
    targets = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in TERMINAL_AND_PROTECTED_STATUSES:
            continue

        # Must have suggestions
        has_suggestions = all(
            get_field_val(fields, s.suggest_field_candidates)
            for s in SLOTS if s.slot_index in (2, 3, 4, 5)
        )
        if not has_suggestions:
            continue

        # Check if missing products
        has_all_furniture = all(
            get_field_val(fields, s.furniture_field_candidates)
            for s in SLOTS if s.slot_index in (2, 3, 4, 5)
        )
        if not has_all_furniture:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing product scraping.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Akeneo scraping.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Record {record_id} ---")
        run_phase_3_for_record(
            akeneo,
            airtable,
            record_id,
            style=style,
            shopify_index=shopify_index,
            shopify_cross_check=shopify_cross_check,
            execute=execute,
        )

    print("\n[OK] Phase 3 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4: Claude Sonnet 5 Blending Prompt Engineering
# ══════════════════════════════════════════════════════════════════════════

def run_phase_4_for_record(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Generate commercial lighting blending prompts for Slots 2 to 5 using Claude Sonnet 5 via Fal AI."""
    print(f"\n[PHASE 4] Claude Sonnet 5 Blending Prompts for Record: {record_id}")

    if execute:
        required_fields = {
            "Blending Prompt2": "multilineText",
            "Blending Prompt3": "multilineText",
            "Blending Prompt4": "multilineText",
            "Blending Prompt5": "multilineText",
        }
        airtable.ensure_fields(required_fields)

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})

    room_slots = [s for s in SLOTS if s.slot_index in (2, 3, 4, 5)]
    prompt_updates: dict[str, str] = {}
    log_updates: dict[str, str] = {}

    for slot in room_slots:
        existing_prompt = fields.get(slot.blending_prompt_field)
        if existing_prompt:
            print(f"  Slot {slot.slot_index} ({slot.label}): Prompt already populated.")
            continue

        interior_val = get_field_val(fields, slot.interior_field_candidates)
        interior_url = extract_attachment_url(interior_val)

        furniture_val = get_field_val(fields, slot.furniture_field_candidates)
        furniture_url = extract_attachment_url(furniture_val)

        item_name = str(get_field_val(fields, slot.item_name_field_candidates) or slot.label).strip()

        if not interior_url or not furniture_url:
            print(f"  [WARN] Slot {slot.slot_index} ({slot.label}): Missing interior or furniture image. Skipping slot.")
            continue

        print(f"  Generating prompt for Slot {slot.slot_index} ({slot.label} - '{item_name}')...")

        if not execute:
            print(f"    [DRY RUN] Would generate prompt for {slot.blending_prompt_field}")
            continue

        instruction = build_vision_blending_instruction(
            interior_label=f"Room Interior ('{slot.label}')",
            item_name=item_name,
            aspect_ratio="4:5",
        )

        raw_result = fal.generate_vision_prompt(
            [interior_url, furniture_url],
            instruction,
            model=CLAUDE_VISION_MODEL,
        )

        prompt_str = raw_result.strip()
        # Clean markdown code block if present
        if "```" in prompt_str:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", prompt_str, re.DOTALL)
            if match:
                prompt_str = match.group(1).strip()

        prompt_updates[slot.blending_prompt_field] = prompt_str
        log_updates[slot.blending_prompt_field] = prompt_str
        print(f"    [OK] Prompt generated successfully ({len(prompt_str)} chars).")

    if execute and prompt_updates:
        airtable.update_records([(record_id, prompt_updates)])
        print(f"  [OK] Saved {len(prompt_updates)} prompt(s) to Airtable record {record_id}")
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 4: Claude Sonnet 5 Blending Prompt Engineering",
                "model": CLAUDE_VISION_MODEL,
                "prompts": log_updates,
            },
            AUDIT_LOG_CLAUDE,
        )

    print(f"[OK] Phase 4 completed for {record_id}.")
    return True


def run_phase_4_prompts(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    target_record: str | None = None,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Generate blending prompts across records needing prompts."""
    print("\n" + "=" * 70)
    print("PHASE 4: Claude Sonnet 5 Blending Prompt Engineering")
    print(f"Model: {CLAUDE_VISION_MODEL}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    if target_record:
        print(f"[INFO] Targeting single record: {target_record}")
        return run_phase_4_for_record(fal, airtable, target_record, execute=execute)

    records = airtable.list_records()
    targets = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in TERMINAL_AND_PROTECTED_STATUSES:
            continue

        has_products = all(
            get_field_val(fields, s.furniture_field_candidates)
            for s in SLOTS if s.slot_index in (2, 3, 4, 5)
        )
        if not has_products:
            continue

        has_all_prompts = all(
            bool(fields.get(s.blending_prompt_field))
            for s in SLOTS if s.slot_index in (2, 3, 4, 5)
        )
        if not has_all_prompts:
            targets.append(record)

    if not targets:
        print("[OK] No records found needing blending prompts.")
        return True

    if max_rows is not None:
        targets = targets[:max_rows]

    print(f"[INFO] Found {len(targets)} record(s) needing Blending Prompt2..5.")

    for idx, record in enumerate(targets, start=1):
        record_id = record["id"]
        print(f"\n--- [{idx}/{len(targets)}] Processing Record {record_id} ---")
        run_phase_4_for_record(fal, airtable, record_id, execute=execute)

    print("\n[OK] Phase 4 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# PHASE 5: Fal AI Nano Banana Pro Image Blending (4:5 Ratio)
# ══════════════════════════════════════════════════════════════════════════

def _resolve_feed_logo_path() -> Path:
    candidates = [
        Path("assets/homecartel_logo.png"),
        Path(__file__).parent / "assets" / "homecartel_logo.png",
        Path("assets/Logo.png"),
        Path(__file__).parent / "assets" / "Logo.png",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return Path("assets/homecartel_logo.png")


def run_phase_5_for_record(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    *,
    execute: bool = True,
) -> bool:
    """Blend products into interior scenes using Fal AI Nano Banana Pro at 4:5 ratio."""
    print(f"\n[PHASE 5] Fal AI Nano Banana Pro Blending (4:5 Ratio) for Record: {record_id}")

    if execute:
        required_fields = {
            "Blended Image1": "multipleAttachments",
            "Blended Image2": "multipleAttachments",
            "Blended Image3": "multipleAttachments",
            "Blended Image4": "multipleAttachments",
            "Blended Image5": "multipleAttachments",
            "Status": "singleSelect",
        }
        airtable.ensure_fields(required_fields)

    record = airtable.get_record(record_id)
    fields = record.get("fields", {})
    known_fields = airtable.table_fields()

    blended_log_entries: list[dict[str, Any]] = []
    all_slots_succeeded = True

    # Slot 1: Copy clean Interior1 (modern exterior) directly into Blended Image1 with HomeCartel Feed logo
    slot1 = SLOTS[0]
    blended_1_field = resolve_field_name(known_fields, slot1.blended_image_field_candidates)
    existing_blended_1 = get_field_val(fields, slot1.blended_image_field_candidates)

    if not existing_blended_1:
        interior_1_val = get_field_val(fields, slot1.interior_field_candidates)
        interior_1_url = extract_attachment_url(interior_1_val)
        if interior_1_url:
            print(f"\n  [Slot 1: {slot1.label}] (Cover Slide)")
            print(f"    Preparing Slide 1 cover with HomeCartel Feed logo -> '{blended_1_field}'...")
            if execute:
                try:
                    downloaded = download_image_url(interior_1_url, prefix="cover_slide_")
                    # Stamp HomeCartel Feed logo auto-layout (bottom-left x=108.0, y=1178.5)
                    try:
                        from content_automation.overlay import stamp_logo, HOMECARTEL_LOGO_BOX
                        logo_path = _resolve_feed_logo_path()
                        if logo_path.is_file():
                            stamp_logo(downloaded.path, logo_path, destination=downloaded.path, box=HOMECARTEL_LOGO_BOX)
                            print(f"    [LOGO] Stamped HomeCartel Feed logo onto Slide 1 cover")
                    except Exception as logo_err:
                        print(f"    [WARN] Logo stamping notice on Slot 1: {logo_err}")

                    airtable.upload_attachment(
                        record_id,
                        blended_1_field,
                        downloaded.path,
                        filename=f"Blended_Image1_Cover_{record_id}.jpg",
                    )
                    downloaded.cleanup()
                    print(f"    [OK] Uploaded branded cover slide to {blended_1_field}")
                    blended_log_entries.append({
                        "slot": 1,
                        "label": slot1.label,
                        "action": "copied_exterior_cover_with_logo",
                        "target_field": blended_1_field,
                    })
                except Exception as err:
                    print(f"    [ERROR] Failed copying Slot 1 cover slide: {err}")
                    all_slots_succeeded = False
        else:
            print(f"  [WARN] Slot 1: Interior1 is missing. Cannot populate Blended Image1.")
            all_slots_succeeded = False
    else:
        print(f"  Slot 1 ({slot1.label}): Blended Image1 cover slide already present.")

    # Slots 2 to 5: Blend product into room using Nano Banana Pro + YOLO Tag + HomeCartel Logo
    room_slots = [s for s in SLOTS if s.slot_index in (2, 3, 4, 5)]

    if execute:
        try:
            airtable.ensure_fields({"Blended Image with Name text": "multipleAttachments"})
            airtable.clear_attachment_field(record_id, "Blended Image with Name text")
        except Exception as clear_err:
            print(f"    [WARN] Could not reset 'Blended Image with Name text': {clear_err}")

    for slot in room_slots:
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

        item_name = str(get_field_val(fields, slot.item_name_field_candidates) or slot.label).strip()
        print(f"\n  [Slot {slot.slot_index}: {slot.label} - '{item_name}']")
        print(f"    Target Field: {blended_field_name}")

        if not execute:
            print(f"    [DRY RUN] Would blend image using {FAL_BLENDING_MODEL} at {FAL_ASPECT_RATIO}")
            continue

        try:
            print(f"    Sending image blending request to Fal AI ({FAL_BLENDING_MODEL}, 4:5)...")
            blended_url = fal.generate(
                prompt=blending_prompt,
                image_urls=[interior_url, furniture_url],
                aspect_ratio=FAL_ASPECT_RATIO,
                model=FAL_BLENDING_MODEL,
            )
            print(f"    [OK] Blended image generated: {blended_url}")

            downloaded = download_image_url(blended_url, prefix=f"blended_{slot.slot_index}_")

            # 1. Auto-tag furniture item name onto Blended Image using YOLO-World
            try:
                from content_automation.akeneo_client import split_item_name
                from content_automation.item_tagger import tag_blended_image
                item_title, product_type = split_item_name(item_name, fallback_product_type=slot.label)
                cat_query = str(fields.get(slot.suggest_furniture_field) or slot.label).strip()
                tag_blended_image(
                    image_input=downloaded.path,
                    item_name=item_title,
                    product_type=product_type,
                    category=cat_query,
                    destination=downloaded.path,
                    fallback_if_undetected=True,
                )
                print(f"    [ITEM TAGGING] Stamped '{item_title}' ({product_type}) onto Slot {slot.slot_index} with YOLO")
            except Exception as tag_err:
                print(f"    [WARN] YOLO tagging notice on Slot {slot.slot_index}: {tag_err}")

            # 2. Stamp HomeCartel Feed logo auto-layout (bottom-left x=108.0, y=1178.5)
            try:
                from content_automation.overlay import stamp_logo, HOMECARTEL_LOGO_BOX
                logo_path = _resolve_feed_logo_path()
                if logo_path.is_file():
                    stamp_logo(downloaded.path, logo_path, destination=downloaded.path, box=HOMECARTEL_LOGO_BOX)
                    print(f"    [LOGO] Stamped HomeCartel Feed logo onto Slot {slot.slot_index}")
            except Exception as logo_err:
                print(f"    [WARN] Logo stamping notice on Slot {slot.slot_index}: {logo_err}")

            print(f"    Uploading tagged & branded composite to Airtable field '{blended_field_name}'...")
            try:
                airtable.clear_attachment_field(record_id, blended_field_name)
            except Exception as clear_err:
                print(f"    [WARN] Could not clear '{blended_field_name}' before upload: {clear_err}")
            airtable.upload_attachment(
                record_id,
                blended_field_name,
                downloaded.path,
                filename=f"Blended_Image{slot.slot_index}_{record_id}.jpg",
            )
            try:
                airtable.upload_attachment(
                    record_id,
                    "Blended Image with Name text",
                    downloaded.path,
                    filename=f"Blended_Image{slot.slot_index}_{record_id}.jpg",
                )
            except Exception as mirror_err:
                print(f"    [WARN] Failed mirroring Slot {slot.slot_index} tagged image to 'Blended Image with Name text': {mirror_err}")

            downloaded.cleanup()

            blended_log_entries.append({
                "slot": slot.slot_index,
                "label": slot.label,
                "target_field": blended_field_name,
                "image_url": blended_url,
                "aspect_ratio": FAL_ASPECT_RATIO,
            })
        except Exception as err:
            print(f"    [ERROR] Failed blending Slot {slot.slot_index}: {err}")
            all_slots_succeeded = False

    if execute and blended_log_entries:
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "phase": "Phase 5: Fal AI Nano Banana Pro Image Blending (4:5 Ratio)",
                "model": FAL_BLENDING_MODEL,
                "aspect_ratio": FAL_ASPECT_RATIO,
                "slots": blended_log_entries,
            },
            AUDIT_LOG_FAL,
        )

    if execute and all_slots_succeeded:
        update_record_status(airtable, record_id, STATUS_DONE)
        print(f"  [OK] All 5 slots blended. Updated record {record_id} Status -> '{STATUS_DONE}'")

    print(f"[OK] Phase 5 completed for {record_id}.")
    return True


def run_phase_5_blend(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    target_record: str | None = None,
    max_rows: int | None = None,
    execute: bool = False,
) -> bool:
    """Blend products into interior scenes across records using Fal AI Nano Banana Pro at 4:5 ratio."""
    print("\n" + "=" * 70)
    print("PHASE 5: Fal AI Nano Banana Pro Image Blending (4:5 Ratio)")
    print(f"Model: {FAL_BLENDING_MODEL} | Aspect Ratio: {FAL_ASPECT_RATIO}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    if target_record:
        print(f"[INFO] Targeting single record: {target_record}")
        return run_phase_5_for_record(fal, airtable, target_record, execute=execute)

    records = airtable.list_records()
    targets = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in TERMINAL_AND_PROTECTED_STATUSES:
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
        run_phase_5_for_record(fal, airtable, record_id, execute=execute)

    print("\n[OK] Phase 5 batch completed successfully.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# CONTINUOUS ROW-BY-ROW PIPELINE (Phase 1 -> 2 -> 3 -> 4 -> 5 -> Next Row)
# ══════════════════════════════════════════════════════════════════════════

def run_continuous_row_pipeline(
    krea: KreaClient,
    fal: FalClient,
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    *,
    target_record: str | None = None,
    style: str = "modern",
    shopify_cross_check: bool = True,
    max_rows: int | None = None,
    execute: bool = True,
) -> bool:
    """Execute complete end-to-end pipeline (Phases 1 to 5) row by row continuously."""
    print("\n" + "=" * 70)
    print(" CONTINUOUS COLLECTION CATEGORY FEED PIPELINE (ROW-BY-ROW)")
    print(f" Target Table: {airtable.table_id} | Shopify Check: {'ENABLED' if shopify_cross_check else 'DISABLED'}")
    print(f" Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("=" * 70)

    shopify_index: ShopifyCatalogIndex | None = None
    if shopify_cross_check and execute:
        try:
            shopify = ShopifyClient()
            shopify_index = shopify.load_published_identities()
        except Exception as s_err:
            print(f"[WARN] Shopify catalog index initialization note: {s_err}")

    if target_record:
        print(f"[INFO] Running complete pipeline for targeted record: {target_record}")
        run_phase_1_for_record(krea, airtable, target_record, execute=execute)
        run_phase_2_for_record(fal, airtable, target_record, execute=execute)
        run_phase_3_for_record(
            akeneo,
            airtable,
            target_record,
            style=style,
            shopify_index=shopify_index,
            shopify_cross_check=shopify_cross_check,
            execute=execute,
        )
        run_phase_4_for_record(fal, airtable, target_record, execute=execute)
        run_phase_5_for_record(fal, airtable, target_record, execute=execute)
        print(f"\n[DONE] Record {target_record} is completely finished!")
        return True

    processed_rows = 0
    processed_record_ids: set[str] = set()

    while True:
        if max_rows is not None and processed_rows >= max_rows:
            print(f"\n[OK] Reached target limit of {max_rows} row(s). Pipeline completed.")
            break

        # Check for existing unfinished record
        records = airtable.list_records()
        unfinished_record = None
        for r in records:
            rid = r.get("id")
            if rid in processed_record_ids:
                continue
            st = str(r.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold()
            if st in ("done", "complete"):
                continue
            if st in (STATUS_STANDBY.casefold(), STATUS_PROCESSING.casefold(), ""):
                unfinished_record = r
                break

        if not unfinished_record:
            # Create 1 new record
            if not execute:
                print("[DRY RUN] Would create 1 new row in Airtable and execute Phases 1 to 5.")
                break
            print(f"\n{'=' * 70}")
            print(f"[ROW {processed_rows + 1}] Creating 1 new row in Airtable...")
            new_row = airtable.create_record({STATUS_FIELD: STATUS_PROCESSING})
            rec_id = new_row if isinstance(new_row, str) else new_row.get("id")
        else:
            rec_id = unfinished_record.get("id") if isinstance(unfinished_record, dict) else str(unfinished_record)

        processed_record_ids.add(rec_id)
        print(f"\n{'=' * 70}")
        print(f"[ROW {processed_rows + 1}] Processing record: {rec_id}")
        print(f"{'=' * 70}")

        # Phase 1: Sequential Krea Interiors
        run_phase_1_for_record(krea, airtable, rec_id, execute=execute)

        # Phase 2: Claude Sonnet 5 Vision Suggestions
        run_phase_2_for_record(fal, airtable, rec_id, execute=execute)

        # Phase 3: Targeted Akeneo Scraper
        run_phase_3_for_record(
            akeneo,
            airtable,
            rec_id,
            style=style,
            shopify_index=shopify_index,
            shopify_cross_check=shopify_cross_check,
            execute=execute,
        )

        # Phase 4: Claude Blending Prompts
        run_phase_4_for_record(fal, airtable, rec_id, execute=execute)

        # Phase 5: Fal Nano Banana Pro Blending
        run_phase_5_for_record(fal, airtable, rec_id, execute=execute)

        processed_rows += 1
        print(f"\n[DONE] Row {processed_rows} ({rec_id}) is completely finished and marked 'Done'!")
        print("Resetting and proceeding to next row...\n")

    return True


# ══════════════════════════════════════════════════════════════════════════
# Master Runner & CLI
# ══════════════════════════════════════════════════════════════════════════

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Collection Category Feed Complete Automation Pipeline"
    )
    parser.add_argument(
        "--phase",
        "-p",
        choices=["1", "2", "3", "4", "5", "all"],
        default="all",
        help="Phase to execute (1: Krea Interiors, 2: Claude Suggestions, 3: Akeneo Scrape, 4: Blending Prompts, 5: Nano Banana Pro Blending, all: Full Pipeline). Default: all",
    )
    parser.add_argument(
        "--target-record",
        default=None,
        help="Target a specific Airtable record ID (e.g. recG4x8RgQXO5kWEs)",
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
        "--no-shopify-check",
        action="store_true",
        default=False,
        help="Disable Shopify published products cross-check (default: enabled)",
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


def interactive_menu() -> tuple[str, bool, str | None, bool]:
    """Display CLI interactive menu when explicitly requested."""
    print("=" * 70)
    print(" COLLECTION CATEGORY FEED AUTOMATION PIPELINE (tbl5o1j3XvUaUqmjs)")
    print("=" * 70)
    print("Select a phase to run:")
    print("  [1] Phase 1: Sequential Krea AI Interior Generation (4:5)")
    print("  [2] Phase 2: Claude Sonnet 5 Vision Analysis (Room Matching & Suggestion)")
    print("  [3] Phase 3: Targeted Akeneo Catalog Scraper (with Shopify Cross-Check)")
    print("  [4] Phase 4: Claude Sonnet 5 Blending Prompt Engineering")
    print("  [5] Phase 5: Fal AI Nano Banana Pro Image Blending (4:5)")
    print("  [6] Run Complete Continuous Row Pipeline (Phase 1 -> 2 -> 3 -> 4 -> 5)")
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

    target_rec = input("Target specific Record ID (or press Enter for automatic batch): ").strip()
    target_record = target_rec if target_rec else None

    shopify_in = input("Enable Shopify published catalog cross-check? (Y/n) [default: Y]: ").strip().lower()
    shopify_cross_check = shopify_in not in ("n", "no", "false", "0")

    exec_input = input("Execute writes and API calls? (Y/n) [default: Y]: ").strip().lower()
    execute = exec_input not in ("n", "no", "false", "0")

    return selected_phase, execute, target_record, shopify_cross_check


def main(argv=None) -> int:
    args = parse_args(argv)

    target_record = args.target_record
    shopify_cross_check = not getattr(args, "no_shopify_check", False)

    if args.menu:
        phase, execute, target_record, shopify_cross_check = interactive_menu()
    else:
        phase = args.phase or "all"
        execute = False if args.dry_run else True

    settings = load_settings()

    channel_name = os.getenv("CHANNEL_NAME") or "home_cartel"
    table_id = args.table_id or DEFAULT_TABLE_ID
    fal_key = os.getenv("FAL_KEY", "").strip() or getattr(settings, "fal_key", "")

    # Initialize clients
    krea = KreaClient(
        token=settings.krea_token,
        base_url=settings.krea_base_url,
    )
    fal = FalClient(
        api_key=fal_key,
    )
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

    print(f"\n[START] Collection Category Feed Pipeline | Phase: {phase.upper()} | Execute: {execute} | Shopify Check: {'ENABLED' if shopify_cross_check else 'DISABLED'}")
    if target_record:
        print(f"[TARGET] Record ID: {target_record}")

    if phase == "all":
        run_continuous_row_pipeline(
            krea,
            fal,
            akeneo,
            airtable,
            target_record=target_record,
            style=args.style,
            shopify_cross_check=shopify_cross_check,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "1":
        run_phase_1_krea(
            krea,
            airtable,
            target_record=target_record,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "2":
        run_phase_2_claude(
            fal,
            airtable,
            target_record=target_record,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "3":
        run_phase_3_scrape(
            akeneo,
            airtable,
            style=args.style,
            target_record=target_record,
            max_rows=args.max_rows,
            shopify_cross_check=shopify_cross_check,
            execute=execute,
        )
    elif phase == "4":
        run_phase_4_prompts(
            fal,
            airtable,
            target_record=target_record,
            max_rows=args.max_rows,
            execute=execute,
        )
    elif phase == "5":
        run_phase_5_blend(
            fal,
            airtable,
            target_record=target_record,
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
