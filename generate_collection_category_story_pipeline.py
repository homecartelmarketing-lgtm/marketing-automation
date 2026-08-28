"""Collection Category Story AI Generation & Blending Pipeline.

Runs the complete 5-Step sequential Row-by-Row AI pipeline for Collection Category Story on Airtable
(default: tblSSVJnubFk2yBm3 – Pendant Lights Collection Category Story):

0. Akeneo Product Scraping (3 products per row) + 'Collection Category Layout' Attachment -> Status: 'Standby'
1. Krea AI Interior Photo Generation (16:9 Ratio, 3 photos) -> 'Interior1', 'Interior2', 'Interior3'
2. Claude Sonnet 5 Prompt Analysis (via Fal AI)             -> 'Prompt1', 'Prompt2', 'Prompt3'
3. Fal AI Nano Banana Pro 16:9 Blending                    -> 'Collection Category Blended Image1/2/3'
4. 9:16 Auto-Grid & Logo Overlay (Local PIL, No Fal API)    -> 'Collection Category Converted' / 'STORY - Collection Category (1)'
-> When row is 'Complete', proceeds to the NEXT row!

Usage::

    python generate_collection_category_story_pipeline.py
    python generate_collection_category_story_pipeline.py --mode menu
    python generate_collection_category_story_pipeline.py --mode scrape --max-items 1
    python generate_collection_category_story_pipeline.py --mode all --max-items 3
    python generate_collection_category_story_pipeline.py --table-id tblSSVJnubFk2yBm3
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

import random
import requests

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename, download_to_temp_file
from content_automation.overlay import (
    HOMECARTEL_STORY_LOGO_BOX,
    create_three_image_story_grid,
)
from content_automation.scraping import ScrapeAirtableClient, load_scrape_settings
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    akeneo_category_code,
    moodboard_id_for_category,
)
from content_automation.scraping.products import (
    existing_product_identities,
    select_new_products,
)
from standalone_scrape_akeneo import run_category_scrape

# ── Table & Moodboard Configurations ────────────────────────────────────

COLLECTION_STORY_TABLES: dict[str, dict[str, str]] = {
    "tblJMJQlrnlDb1GtN": {
        "category_code": "chandelier_collec_story",
        "label": "Chandelier Collec Story",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "default_prompt": "Generate me a modern living room hanging chandelier",
    },
    "tblSSVJnubFk2yBm3": {
        "category_code": "pendant_lights_collec_story",
        "label": "Pendant Lights Collec Story",
        "default_moodboard_id": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
        "default_prompt": "Generate me a modern dining room hanging pendant light not too oversize item",
    },
    "tblsXXcoZZD4q6WWt": {
        "category_code": "cluster_chandeliers_collec_story",
        "label": "Cluster Chandelier Collec Story",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "default_prompt": "Generate me a modern living room with cluster chandelier hanging from the ceiling",
    },
    "tblGxqbSpQF21TLX8": {
        "category_code": "linear_chandeliers_collec_story",
        "label": "Linear Chandelier Collec Story",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "default_prompt": "Generate me a modern dining room with linear chandelier hanging over a long dining table",
    },
    "tblloZLRSKwOCg247": {
        "category_code": "floor_lamps_collec_story",
        "label": "Floor Lamp Collec Story",
        "default_moodboard_id": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
        "default_prompt": "Generate me a modern bedroom that have beside a floor lamp",
    },
    "tblIzL0gItIgoUZFw": {
        "category_code": "table_lamps_collec_story",
        "label": "Table Lamp Collec Story",
        "default_moodboard_id": "b1641228-beec-4823-8d01-1de3eec8410d",
        "default_prompt": "Generate me a modern bedside table with an elegant table lamp",
    },
    "tbl98UU0h4uFyFIlL": {
        "category_code": "wall_sconces_collec_story",
        "label": "Wall Sconce Collec Story",
        "default_moodboard_id": "20c3beaf-0995-44bf-a7a3-ac790fe8f315",
        "default_prompt": "Generate me a modern living room with wall sconce mounted on the wall",
    },
    "tbl0R6o61lGJmt44n": {
        "category_code": "chandelier_collec_story",
        "label": "Chandelier Collec Story (Legacy)",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "default_prompt": "Generate me a modern living room hanging chandelier",
    },
}

DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_COLLEC_STORY", "").strip()
    or "tblSSVJnubFk2yBm3"
)
DEFAULT_CATEGORY = "pendant_lights_collec_story"
DEFAULT_MOODBOARD_ID = "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3"
DEFAULT_PROMPT = "Generate me a modern dining room hanging pendant light not too oversize item"

# ── Field Names ─────────────────────────────────────────────────────────

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "Processing Interior Generated Photo"
STATUS_GENERATING_PROMPT = "Processing Blending Prompt"
STATUS_BLENDED = "Processing Blended Image"
STATUS_COMPLETE = "Complete"

ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"

# Interior attachment fields (slots 1-3)
INTERIOR_FIELDS = ["Interior1", "Interior2", "Interior3"]
INTERIOR_FALLBACKS = {
    "Interior1": ["Interior1", "Interior"],
    "Interior2": ["Interior2"],
    "Interior3": ["Interior3", "Interiro3"],
}

# Furniture item attachment fields (slots 1-3)
FURNITURE_FIELDS_MAP = {
    1: ["Furniture Item1", "Furniture Item copy", "Furniture Item"],
    2: ["Furniture Item2", "Furniture Item copy2"],
    3: ["Furniture Item3", "Furniture Item copy3"],
}

# Prompt text fields (slots 1-3)
PROMPT_FIELDS = ["Prompt1", "Prompt2", "Prompt3"]

# Blended image attachment fields (slots 1-3)
BLENDED_IMAGE_FIELDS = [
    "Collection Category Blended Image1",
    "Collection Category Blended Image2",
    "Collection Category Blended Image3",
]
BLENDED_ARRAY_FIELDS = [
    "Collection Category Blended",
    "Story Collection Categ Blended",
]

# Layout reference attachment fields
LAYOUT_FIELD = "Collection Category Layout"
LAYOUT_FIELDS = [
    "Collection Category Layout",
    "Collection Categ Story Layout",
    "Layout",
    "Story Layout",
    "Watermark Layout",
]

# Logo attachment fields
LOGO_FIELD = "Logo"
LOGO_FIELDS = [
    "Logo",
    "Brand Logo",
    "Watermark",
    "Logo Image",
]

# Final converted story attachment fields
FINAL_CONVERTED_FIELDS = [
    "Collection Category Converted",
    "STORY - Collection Category (1)",
    "Collection Category Final",
]

# ── Models & Aspect Ratios ──────────────────────────────────────────────

INTERIOR_ASPECT_RATIO = "16:9"
BLENDED_ASPECT_RATIO = "16:9"
STORY_ASPECT_RATIO = "9:16"

FAL_VISION_MODEL = (
    os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
)
FAL_BLENDING_MODEL = (
    os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
)
FAL_ASSEMBLY_MODEL = (
    os.getenv("COLLECTION_STORY_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
)

# ── Audit Logging ───────────────────────────────────────────────────────

AUDIT_LOG_DIR = Path("output") / "logs"
AUDIT_LOG_KREA = AUDIT_LOG_DIR / "collec_story_krea_logs.json"
AUDIT_LOG_CLAUDE = AUDIT_LOG_DIR / "collec_story_claude_logs.json"
AUDIT_LOG_NANO_BLEND = AUDIT_LOG_DIR / "collec_story_nano_blend_logs.json"
AUDIT_LOG_FINAL = AUDIT_LOG_DIR / "collec_story_final_assembly_logs.json"


def append_audit_log(log_entry: dict[str, Any], log_path: Path) -> None:
    """Append an API call audit record to the specified JSON log file."""
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
    try:
        log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"[AUDIT LOG] Appended log entry to {log_path}")
    except Exception as err:
        print(f"[WARN] Failed writing audit log: {err}")


# ── Helpers ─────────────────────────────────────────────────────────────

def sort_records_by_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort Airtable records deterministically by ID or row number."""
    return sorted(records, key=lambda r: str(r.get("id") or ""))


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


def get_field_value(fields: dict[str, Any], candidates: list[str]) -> Any:
    """Return the first populated value among candidate field names."""
    for name in candidates:
        if name in fields and fields[name]:
            return fields[name]
    return None


def get_slot_furniture_field(fields: dict[str, Any], slot: int) -> Any:
    """Get furniture attachment value for a slot (1-indexed)."""
    candidates = FURNITURE_FIELDS_MAP.get(slot, [f"Furniture Item{slot}"])
    return get_field_value(fields, candidates)


def get_slot_interior_field(fields: dict[str, Any], slot: int) -> Any:
    """Get interior attachment value for a slot (1-indexed)."""
    field_name = f"Interior{slot}"
    fallbacks = INTERIOR_FALLBACKS.get(field_name, [field_name])
    return get_field_value(fields, fallbacks)


def resolve_slot_interior_target(airtable: ScrapeAirtableClient, slot: int) -> str:
    """Find the exact matching Interior field name on Airtable (e.g. Interior3 or Interiro3)."""
    known = airtable.known_field_names()
    candidates = INTERIOR_FALLBACKS.get(f"Interior{slot}", [f"Interior{slot}"])
    for candidate in candidates:
        if candidate in known:
            return candidate
    return f"Interior{slot}"


def resolve_slot_blended_target(airtable: ScrapeAirtableClient, slot: int) -> str:
    """Find the exact matching Blended field name on Airtable."""
    known = airtable.known_field_names()
    specific_field = BLENDED_IMAGE_FIELDS[slot - 1]
    if specific_field in known:
        return specific_field
    for array_field in BLENDED_ARRAY_FIELDS:
        if array_field in known:
            return array_field
    return specific_field


def resolve_final_target(airtable: ScrapeAirtableClient) -> str:
    """Find the exact matching converted/story final field name on Airtable."""
    known = airtable.known_field_names()
    for field in FINAL_CONVERTED_FIELDS:
        if field in known:
            return field
    return FINAL_CONVERTED_FIELDS[0]


def resolve_layout_field(fields: dict[str, Any]) -> Any:
    """Get layout attachment value from candidate layout fields."""
    return get_field_value(fields, LAYOUT_FIELDS)


def resolve_logo_field(fields: dict[str, Any]) -> Any:
    """Get logo attachment value from candidate logo fields."""
    return get_field_value(fields, LOGO_FIELDS)


def update_status_if_valid(airtable: ScrapeAirtableClient, record_id: str, desired_status: str) -> None:
    """Update Status field safely matching table's allowed singleSelect options."""
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

        if "processing" in desired_status.casefold():
            proc_match = next((c for c in choices if "processing" in c.casefold()), None)
            if proc_match:
                airtable.update_records([(record_id, {STATUS_FIELD: proc_match})])
                return

        if "complete" in desired_status.casefold():
            comp_match = next((c for c in choices if "complete" in c.casefold()), None)
            if comp_match:
                airtable.update_records([(record_id, {STATUS_FIELD: comp_match})])
                return
    except Exception as err:
        print(f"  [WARN] Failed updating status for record {record_id}: {err}")


# ══════════════════════════════════════════════════════════════════════════
# LAYOUT ATTACHMENT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════

def find_collection_category_layout_path() -> Path | None:
    """Find local layout template file for Collection Category Story on disk."""
    for base in (
        Path("JSON Prompts") / "Collection Categ",
        Path("JSON Prompts") / "Collection Category",
        Path("JSON Prompts"),
        Path("."),
    ):
        if base.is_dir():
            for filename in (
                "stories (59).jpg",
                "collection_category_layout.jpg",
                "collec_layout.jpg",
                "layout.jpg",
                "layout.png",
            ):
                p = base / filename
                if p.is_file():
                    return p
            for match in base.glob("*story*layout*.jpg"):
                if match.is_file():
                    return match
    return None


def get_existing_layout_attachment_from_table(airtable: ScrapeAirtableClient) -> dict | None:
    """Find any existing record in the table that has a layout attached in 'Collection Category Layout'."""
    records = airtable.list_records()
    for record in records:
        fields = record.get("fields", {})
        layout_val = resolve_layout_field(fields)
        if layout_val:
            if isinstance(layout_val, list) and len(layout_val) > 0 and isinstance(layout_val[0], dict) and layout_val[0].get("url"):
                return layout_val[0]
            if isinstance(layout_val, dict) and layout_val.get("url"):
                return layout_val
    return None


def ensure_collection_category_layout_uploaded(
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any] | None = None,
) -> bool:
    """Ensure layout photo is uploaded into 'Collection Category Layout' field for the row."""
    target_field = LAYOUT_FIELD
    if fields is None:
        try:
            rec = airtable.get_record(record_id) if hasattr(airtable, "get_record") else None
            fields = rec.get("fields", {}) if rec else {}
        except Exception:
            fields = {}

    existing_layout = resolve_layout_field(fields)
    if existing_layout:
        return True

    # 1. Prefer local clean layout file on disk (which has NO red bounding box)
    local_path = find_collection_category_layout_path()
    if local_path and local_path.is_file():
        try:
            airtable.ensure_fields({target_field: "multipleAttachments"})
            airtable.upload_attachment(record_id, target_field, local_path, local_path.name)
            print(f"[OK] Uploaded clean local layout '{local_path.name}' to '{target_field}' on record {record_id}")
            return True
        except Exception as err:
            print(f"[WARN] Failed uploading local layout to record {record_id}: {err}")

    # 2. Fall back to existing Airtable row
    existing_att = get_existing_layout_attachment_from_table(airtable)
    if existing_att and existing_att.get("url"):
        layout_url = existing_att["url"]
        downloaded = None
        try:
            airtable.ensure_fields({target_field: "multipleAttachments"})
            resp = requests.get(layout_url, stream=True)
            downloaded = download_to_temp_file(
                resp,
                prefix="collec_layout_",
                suffix=".jpg",
                context=f"Download layout from {layout_url}",
            )
            airtable.upload_attachment(record_id, target_field, downloaded, "collection_category_layout.jpg")
            print(f"[OK] Copied existing layout from Airtable to '{target_field}' on record {record_id}")
            return True
        except Exception as err:
            print(f"[WARN] Failed copying layout from Airtable to record {record_id}: {err}")
        finally:
            if downloaded:
                downloaded.cleanup()

    print(f"[WARN] No layout photo found on disk or Airtable for record {record_id}")
    return False


# ══════════════════════════════════════════════════════════════════════════
# HOMECARTEL LOGO ATTACHMENT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════

def find_homecartel_logo_path() -> Path | None:
    """Find local clean transparent HomeCartel logo on disk."""
    for base in (
        Path("assets"),
        Path("JSON Prompts"),
        Path("scratch"),
        Path("tmp") / "logo_preview",
        Path("."),
    ):
        if base.is_dir():
            for filename in (
                "homecartel_logo.png",
                "logo.png",
                "refined_logo.png",
                "removed_bg_logo.png",
                "HomeCartel_Logo.png",
            ):
                p = base / filename
                if p.is_file():
                    return p
    return None


def get_existing_logo_attachment_from_table(airtable: ScrapeAirtableClient) -> dict | None:
    """Find any existing record in the table that has a logo attached in 'Logo'."""
    try:
        records = airtable.list_records()
    except Exception:
        return None
    for record in records:
        fields = record.get("fields", {})
        logo_val = resolve_logo_field(fields)
        if logo_val:
            if isinstance(logo_val, list) and len(logo_val) > 0 and isinstance(logo_val[0], dict) and logo_val[0].get("url"):
                return logo_val[0]
            if isinstance(logo_val, dict) and logo_val.get("url"):
                return logo_val
    return None


def ensure_homecartel_logo_uploaded(
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any] | None = None,
) -> bool:
    """Ensure transparent HomeCartel logo is uploaded into 'Logo' field for the row."""
    target_field = LOGO_FIELD
    if fields is None:
        try:
            rec = airtable.get_record(record_id) if hasattr(airtable, "get_record") else None
            fields = rec.get("fields", {}) if rec else {}
        except Exception:
            fields = {}

    existing_logo = resolve_logo_field(fields)
    if existing_logo:
        return True

    # 1. Prefer local clean transparent logo on disk
    local_path = find_homecartel_logo_path()
    if local_path and local_path.is_file():
        try:
            airtable.ensure_fields({target_field: "multipleAttachments"})
            airtable.upload_attachment(record_id, target_field, local_path, local_path.name)
            print(f"[OK] Uploaded HomeCartel logo '{local_path.name}' to '{target_field}' on record {record_id}")
            return True
        except Exception as err:
            print(f"[WARN] Failed uploading local logo to record {record_id}: {err}")

    # 2. Fall back to existing Airtable row
    existing_att = get_existing_logo_attachment_from_table(airtable)
    if existing_att and existing_att.get("url"):
        logo_url = existing_att["url"]
        downloaded = None
        try:
            airtable.ensure_fields({target_field: "multipleAttachments"})
            resp = requests.get(logo_url, stream=True)
            downloaded = download_to_temp_file(
                resp,
                prefix="collec_logo_",
                suffix=".png",
                context=f"Download logo from {logo_url}",
            )
            airtable.upload_attachment(record_id, target_field, downloaded, "homecartel_logo.png")
            print(f"[OK] Copied existing logo from Airtable to '{target_field}' on record {record_id}")
            return True
        except Exception as err:
            print(f"[WARN] Failed copying logo from Airtable to record {record_id}: {err}")
        finally:
            if downloaded:
                downloaded.cleanup()

    print(f"[WARN] No logo file found on disk or Airtable for record {record_id}")
    return False


def get_first_incomplete_record(airtable: ScrapeAirtableClient) -> dict[str, Any] | None:
    """Find the single lowest ID record in Airtable that is NOT yet Complete and missing any output field."""
    records = airtable.list_records()
    if not records:
        return None

    records = sort_records_by_id(records)
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()

        # If Status is already Complete, skip this row completely!
        if status == STATUS_COMPLETE.casefold():
            continue

        # Must have at least 1 furniture item to be an active product row
        if not get_slot_furniture_field(fields, 1):
            continue

        has_converted = bool(get_field_value(fields, FINAL_CONVERTED_FIELDS))
        if has_converted:
            # Row already has final converted story; mark Complete and skip!
            if status != STATUS_COMPLETE.casefold():
                update_status_if_valid(airtable, record["id"], STATUS_COMPLETE)
            continue

        has_3_interiors = all(get_slot_interior_field(fields, slot) for slot in (1, 2, 3))
        has_3_prompts = all(str(fields.get(f"Prompt{slot}") or "").strip() for slot in (1, 2, 3))
        has_3_blends = all(fields.get(BLENDED_IMAGE_FIELDS[slot - 1]) for slot in (1, 2, 3))
        if not has_3_blends:
            for array_field in BLENDED_ARRAY_FIELDS:
                att_list = fields.get(array_field) or []
                if isinstance(att_list, list) and len(att_list) >= 3:
                    has_3_blends = True
                    break
        has_layout = bool(resolve_layout_field(fields))

        if not (has_3_interiors and has_3_prompts and has_3_blends and has_layout and has_converted):
            return record

    return None


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1 — Krea AI Interior Photo Generation (16:9)
# ══════════════════════════════════════════════════════════════════════════

def generate_krea_interiors_pipeline(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_PROMPT,
    aspect_ratio: str = INTERIOR_ASPECT_RATIO,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate 3 Krea AI room interior photos into Interior1/2/3 for Standby records."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable to populate interior photos.")
        return True

    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    unpopulated = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if not target_record_id and status == STATUS_COMPLETE.casefold():
            continue
        all_filled = all(
            get_slot_interior_field(fields, slot) for slot in (1, 2, 3)
        )
        if all_filled:
            continue
        unpopulated.append(record)

    if not unpopulated:
        print(f"[OK] No records found needing interior photos.")
        return True

    if limit_records is not None:
        unpopulated = unpopulated[:limit_records]

    print(
        f"[INFO] Generating Interior1/2/3 for {len(unpopulated)} record(s) "
        f"using Krea AI (Moodboard ID: {moodboard_id}, Aspect Ratio: {aspect_ratio})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(unpopulated, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        print(
            f"[INFO] [{position}/{len(unpopulated)}] Generating 3 interior photos for "
            f"record {record_id} ({item_label})..."
        )

        slot_success = 0
        for slot in (1, 2, 3):
            if get_slot_interior_field(fields, slot):
                print(f"  [SKIP] Interior{slot} already has attachment on record {record_id}")
                slot_success += 1
                continue

            downloaded = None
            try:
                image_url = krea.generate(
                    prompt,
                    aspect_ratio=aspect_ratio,
                    moodboard_id=moodboard_id,
                )
                downloaded = krea.download_image(image_url)
                filename = f"interior{slot}_{record_id}.jpg"
                target_field = resolve_slot_interior_target(airtable, slot)
                airtable.upload_attachment(record_id, target_field, downloaded, filename)
                fields[target_field] = [{"filename": filename, "url": image_url}]
                print(f"  [OK] Attached Krea image to '{target_field}' on record {record_id}")

                append_audit_log({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "record_id": record_id,
                    "item_label": item_label,
                    "phase": f"Phase 1: Krea AI Interior Generation - Slot {slot}",
                    "api_provider": "Krea AI",
                    "moodboard_id": moodboard_id,
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "output_image_url": image_url,
                    "target_field": target_field,
                }, AUDIT_LOG_KREA)

                slot_success += 1
            except Exception as error:
                print(
                    f"  [ERROR] Failed generating Interior{slot} for record {record_id}: {error}"
                )
            finally:
                if downloaded:
                    downloaded.cleanup()

        if slot_success == 3:
            update_status_if_valid(airtable, record_id, STATUS_INTERIOR_GENERATED)
            print(
                f"[OK] All 3 interiors generated. Updated {STATUS_FIELD} "
                f"on record {record_id}"
            )
            succeeded += 1
        else:
            print(f"[WARN] Only {slot_success}/3 interior slots filled for record {record_id}")
            failed += 1

    print(
        f"[INFO] Krea interior generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Claude Sonnet 5 Prompt Analysis (via Fal AI)
# ══════════════════════════════════════════════════════════════════════════

def generate_claude_blending_prompts(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    vision_model: str = FAL_VISION_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate blending prompts using Claude Sonnet 5 via Fal AI for each Interior + Furniture pair."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable to generate prompts.")
        return True

    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if not target_record_id and status == STATUS_COMPLETE.casefold():
            continue
        has_work = False
        for slot in (1, 2, 3):
            interior_val = get_slot_interior_field(fields, slot)
            furniture_val = get_slot_furniture_field(fields, slot)
            prompt_val = str(fields.get(f"Prompt{slot}") or "").strip()
            if interior_val and furniture_val and not prompt_val:
                has_work = True
                break
        if has_work:
            eligible.append(record)

    if not eligible:
        print("[OK] No records requiring Claude Sonnet 5 prompt generation.")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating Prompt1/2/3 for {len(eligible)} record(s) "
        f"using Claude Sonnet 5 via Fal AI ({vision_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating prompts for "
            f"record {record_id} ({item_label}) with Claude Sonnet 5..."
        )

        slot_success = 0
        for slot in (1, 2, 3):
            prompt_field = f"Prompt{slot}"
            existing_prompt = str(fields.get(prompt_field) or "").strip()
            if existing_prompt:
                print(f"  [SKIP] {prompt_field} already populated on record {record_id}")
                slot_success += 1
                continue

            interior_url = extract_attachment_url(get_slot_interior_field(fields, slot))
            furniture_url = extract_attachment_url(get_slot_furniture_field(fields, slot))

            if not interior_url or not furniture_url:
                print(
                    f"  [SKIP] Record {record_id} slot {slot} missing Interior or Furniture URL."
                )
                continue

            slot_item_name = (
                str(fields.get(f"Item Name{slot}") or "").strip()
                if slot > 1
                else str(fields.get("Item Name") or "").strip()
            ) or item_label

            instruction = (
                f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
                f"and Image 2 as the product photo for '{slot_item_name}' ('Furniture Item {slot}').\n"
                f"Generate a detailed, highly specific image-blending prompt for Nano Banana Pro (16:9 landscape aspect ratio). "
                f"The prompt must describe naturally integrating and mounting the {slot_item_name} from Image 2 into the room interior from Image 1.\n"
                f"CRITICAL ISOLATION & MOUNTING RULES:\n"
                f"1. The {slot_item_name} shown in Image 2 MUST BE THE ONLY CEILING/MAIN LIGHTING FIXTURE in the entire final blended scene.\n"
                f"2. If Image 1 contains ANY pre-existing lighting fixtures, pendant lights, or hanging lamps, explicitly instruct to remove and replace them with the exact {slot_item_name} from Image 2.\n"
                f"3. Strictly exclude unnecessary competing furniture items, duplicate fixtures, or clutter.\n"
                f"4. Ensure natural hanging/placement height, realistic chain/rod/cord mounting, ceiling canopy, realistic warm illumination, soft ambient glow, natural contact shadows on surrounding walls/floors, and authentic materials.\n\n"
                f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
            )

            try:
                generated_prompt = fal.generate_vision_prompt(
                    image_urls=[interior_url, furniture_url],
                    prompt=instruction,
                    model=vision_model,
                ).strip().strip('"').strip("'")

                append_audit_log({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "record_id": record_id,
                    "item_label": slot_item_name,
                    "phase": f"Phase 2: Claude Sonnet 5 Prompt Generation - Slot {slot}",
                    "api_provider": "Fal AI / OpenRouter",
                    "api_model": vision_model,
                    "input_interior_url": interior_url,
                    "input_furniture_url": furniture_url,
                    "generated_prompt": generated_prompt,
                }, AUDIT_LOG_CLAUDE)

                airtable.update_records([(record_id, {prompt_field: generated_prompt})])
                fields[prompt_field] = generated_prompt
                print(f"  [OK] Saved Claude Sonnet 5 prompt to '{prompt_field}' on record {record_id}")
                slot_success += 1
            except Exception as error:
                print(f"  [ERROR] Failed generating prompt for slot {slot} on record {record_id}: {error}")

        if slot_success > 0:
            update_status_if_valid(airtable, record_id, STATUS_GENERATING_PROMPT)
            print(
                f"[OK] {slot_success}/3 prompts generated. Updated {STATUS_FIELD} "
                f"on record {record_id}"
            )
            succeeded += 1
        else:
            print(f"[WARN] No prompts generated for record {record_id}")
            failed += 1

    print(
        f"[INFO] Claude Sonnet 5 prompt generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# Alias for backwards compatibility
generate_qwen_blending_prompts = generate_claude_blending_prompts


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Fal AI Nano Banana Pro 16:9 Blending
# ══════════════════════════════════════════════════════════════════════════

def generate_nano_banana_blends(
    fal_or_blend_client: Any,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = FAL_BLENDING_MODEL,
    aspect_ratio: str = BLENDED_ASPECT_RATIO,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate 16:9 blended photos using Fal AI Nano Banana Pro into Collection Category Blended Image 1/2/3."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable for image blending.")
        return True

    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if not target_record_id and status == STATUS_COMPLETE.casefold():
            continue
        has_work = False
        for slot in (1, 2, 3):
            prompt_text = str(fields.get(f"Prompt{slot}") or "").strip()
            interior_val = get_slot_interior_field(fields, slot)
            furniture_val = get_slot_furniture_field(fields, slot)
            blended_val = fields.get(BLENDED_IMAGE_FIELDS[slot - 1])
            if prompt_text and interior_val and furniture_val and not blended_val:
                has_work = True
                break
        if has_work:
            eligible.append(record)

    if not eligible:
        print("[OK] No records requiring Fal AI Nano Banana Pro blending.")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating Collection Category Blended Image1/2/3 for {len(eligible)} record(s) "
        f"using Fal AI Nano Banana Pro ({blend_model}, Aspect Ratio: {aspect_ratio})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating blended photos for "
            f"record {record_id} ({item_label})..."
        )

        slot_success = 0
        for slot in (1, 2, 3):
            blended_field = resolve_slot_blended_target(airtable, slot)

            if fields.get(BLENDED_IMAGE_FIELDS[slot - 1]):
                print(f"  [SKIP] {BLENDED_IMAGE_FIELDS[slot - 1]} already has attachment on record {record_id}")
                slot_success += 1
                continue

            prompt_text = str(fields.get(f"Prompt{slot}") or "").strip()
            interior_url = extract_attachment_url(get_slot_interior_field(fields, slot))
            furniture_url = extract_attachment_url(get_slot_furniture_field(fields, slot))

            if not prompt_text or not interior_url or not furniture_url:
                print(
                    f"  [SKIP] Record {record_id} slot {slot} missing prompt, interior, or furniture."
                )
                continue

            image_inputs = [url for url in (interior_url, furniture_url) if url]

            print(
                f"  [INFO] Blending slot {slot} for record {record_id} with Fal AI Nano Banana Pro..."
            )

            downloaded = None
            try:
                image_url = fal_or_blend_client.generate(
                    prompt=prompt_text,
                    image_urls=image_inputs,
                    aspect_ratio=aspect_ratio,
                    resolution="1K",
                    model=blend_model,
                )

                append_audit_log({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "record_id": record_id,
                    "item_label": item_label,
                    "phase": f"Phase 3: Fal AI Nano Banana Pro Blending - Slot {slot}",
                    "api_model": blend_model,
                    "input_prompt": prompt_text,
                    "input_image_urls": image_inputs,
                    "output_image_url": image_url,
                    "aspect_ratio": aspect_ratio,
                    "target_field": blended_field,
                }, AUDIT_LOG_NANO_BLEND)

                response = requests.get(image_url, stream=True)
                downloaded = download_to_temp_file(
                    response,
                    prefix=f"collec_blend_slot{slot}_",
                    suffix=".jpg",
                    context=f"Download blended image from {image_url}",
                )
                filename = f"blended_{slot}_{record_id}.jpg"
                airtable.upload_attachment(record_id, blended_field, downloaded, filename)
                fields[blended_field] = [{"filename": filename, "url": image_url}]
                print(f"  [OK] Attached blended image to '{blended_field}' on record {record_id}")
                slot_success += 1
            except Exception as error:
                print(
                    f"  [ERROR] Failed blending slot {slot} for record {record_id}: {error}"
                )
            finally:
                if downloaded:
                    downloaded.cleanup()

        if slot_success > 0:
            new_status = STATUS_COMPLETE if slot_success == 3 else STATUS_BLENDED
            update_status_if_valid(airtable, record_id, new_status)
            print(
                f"[OK] {slot_success}/3 blends generated. Updated {STATUS_FIELD} "
                f"on record {record_id}"
            )
            succeeded += 1
        else:
            print(f"[WARN] No blends generated for record {record_id}")
            failed += 1

    print(
        f"[INFO] Fal AI Nano Banana Pro blending complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# Alias for backwards compatibility
generate_qwen_image_blends = generate_nano_banana_blends


def build_story_metadata(fields: dict[str, Any]) -> list[dict[str, str]]:
    """Extract item names and product types for 3 slots from record fields."""
    metadata = []
    for slot in (1, 2, 3):
        suffix = "" if slot == 1 else str(slot)
        item_name = str(
            fields.get(f"Item Name{slot}")
            or fields.get(f"Item Name{suffix}")
            or fields.get(ITEM_NAME_FIELD)
            or f"Pendant Light {slot}"
        ).strip()
        prod_type = str(
            fields.get(f"Product Type{slot}")
            or fields.get(f"Product Type{suffix}")
            or fields.get("Product Type")
            or "Pendant Light"
        ).strip()
        metadata.append({"item_name": item_name, "product_type": prod_type})
    return metadata


def build_final_story_prompt(metadata: list[dict[str, str]]) -> str:
    """Build the final 9:16 story prompt template with substituted metadata."""
    prompt_path = Path("JSON Prompts") / "Collection Categ" / "collection-categ.json"
    if prompt_path.exists():
        prompt_text = prompt_path.read_text(encoding="utf-8")
    else:
        prompt_text = (
            "Generate one polished 9:16 HomeCartel Collection Category Story from four images: "
            "top section: [Item Name] ([Product Type]), middle section: [Item Name2] ([Product Type2]), "
            "bottom section: [Item Name3] ([Product Type3]), image 4: layout guide only."
        )

    replacements = {
        "[Item Name]": metadata[0]["item_name"],
        "[Product Type]": metadata[0]["product_type"],
        "[Item Name2]": metadata[1]["item_name"],
        "[Product Type2]": metadata[1]["product_type"],
        "[Item Name3]": metadata[2]["item_name"],
        "[Product Type3]": metadata[2]["product_type"],
    }
    for placeholder, value in replacements.items():
        prompt_text = prompt_text.replace(placeholder, value)

    runtime_text = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    return f"{prompt_text}\nRUNTIME_PRODUCT_TEXT={runtime_text}"


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4 — 9:16 Auto-Grid & Logo Overlay -> 'Collection Category Converted'
# (Local Python PIL script, No Fal API calls)
# ══════════════════════════════════════════════════════════════════════════

def generate_collection_category_story_final_assembly(
    fal_client: Any = None,
    airtable: ScrapeAirtableClient = None,
    *,
    assembly_model: str = FAL_ASSEMBLY_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate final 9:16 Story auto-grid composition combining Blended Image 1, 2, 3 + Logo overlay."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable for story final assembly.")
        return True

    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if not target_record_id and status == STATUS_COMPLETE.casefold():
            continue
        final_val = get_field_value(fields, FINAL_CONVERTED_FIELDS)
        if final_val and not target_record_id:
            continue

        has_3_blends = all(
            fields.get(f"Collection Category Blended Image{slot}") for slot in (1, 2, 3)
        )
        if not has_3_blends:
            for array_field in BLENDED_ARRAY_FIELDS:
                att_list = fields.get(array_field) or []
                if isinstance(att_list, list) and len(att_list) >= 3:
                    has_3_blends = True
                    break

        if has_3_blends and not final_val:
            eligible.append(record)

    if not eligible:
        print("[OK] No records requiring final story assembly (missing blended images or already converted).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    target_final_field = resolve_final_target(airtable)
    print(
        f"[INFO] Generating 9:16 Auto-Grid Story Conversion for {len(eligible)} record(s) "
        f"into '{target_final_field}' using local Python PIL script (No Fal API)..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        # Extract 3 blended images URLs
        blend_urls: list[str] = []
        for slot in (1, 2, 3):
            url = extract_attachment_url(fields.get(f"Collection Category Blended Image{slot}"))
            if url:
                blend_urls.append(url)

        if len(blend_urls) < 3:
            for array_field in BLENDED_ARRAY_FIELDS:
                att_list = fields.get(array_field) or []
                if isinstance(att_list, list):
                    for att in att_list:
                        u = extract_attachment_url(att)
                        if u and u not in blend_urls:
                            blend_urls.append(u)
                if len(blend_urls) >= 3:
                    break

        if len(blend_urls) < 3:
            print(f"[SKIP] Record {record_id} ({item_label}) has only {len(blend_urls)}/3 accessible blended images.")
            continue

        # Extract Logo URL or fallback to local transparent HomeCartel logo
        logo_url = extract_attachment_url(resolve_logo_field(fields))
        local_logo_path = None
        if not logo_url:
            local_logo_path = find_homecartel_logo_path()
            if local_logo_path and local_logo_path.is_file():
                print(f"  [INFO] Using local clean HomeCartel logo fallback '{local_logo_path.name}' for record {record_id}.")
            else:
                print(f"  [INFO] No logo found in 'Logo' field or local disk on record {record_id}; generating grid without logo overlay.")

        print(
            f"[INFO] [{position}/{len(eligible)}] Assembling 9:16 Auto-Grid Story (Blended 1/2/3 + Logo) for "
            f"record {record_id} ({item_label})..."
        )

        downloaded_temps = []
        final_temp_path = None
        try:
            # Download 3 blended images
            blended_paths = []
            for slot, url in enumerate(blend_urls[:3], start=1):
                resp = requests.get(url, stream=True)
                tmp_file = download_to_temp_file(
                    resp,
                    prefix=f"collec_story_blend{slot}_",
                    suffix=".jpg",
                    context=f"Download Blended Image {slot} from {url}",
                )
                downloaded_temps.append(tmp_file)
                blended_paths.append(tmp_file.path)

            # Download Logo or use local fallback
            logo_path = None
            if logo_url:
                resp_logo = requests.get(logo_url, stream=True)
                tmp_logo = download_to_temp_file(
                    resp_logo,
                    prefix="collec_story_logo_",
                    suffix=".png",
                    context=f"Download Logo from {logo_url}",
                )
                downloaded_temps.append(tmp_logo)
                logo_path = tmp_logo.path
            elif local_logo_path and local_logo_path.is_file():
                logo_path = local_logo_path

            out_dir = Path("tmp") / "collection_story"
            out_dir.mkdir(parents=True, exist_ok=True)
            final_temp_path = out_dir / f"collection_category_story_{record_id}.jpg"

            # Extract Item Names for the 3 slots
            item_names: list[str] = []
            for slot in (1, 2, 3):
                suffix = "" if slot == 1 else str(slot)
                name_val = str(
                    fields.get(f"Item Name{slot}")
                    or fields.get(f"Item Name{suffix}")
                    or fields.get(f"Item Name copy{slot}")
                    or (fields.get(ITEM_NAME_FIELD) if slot == 1 else "")
                    or ""
                ).strip()
                item_names.append(name_val)

            create_three_image_story_grid(
                blended_paths,
                destination=final_temp_path,
                logo_path=logo_path,
                logo_box=HOMECARTEL_STORY_LOGO_BOX,
                item_names=item_names,
            )

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 4: Python PIL 9:16 Auto-Grid Story Conversion",
                "engine": "local_pil",
                "input_blended_count": len(blended_paths),
                "has_logo": logo_path is not None,
                "aspect_ratio": STORY_ASPECT_RATIO,
                "target_field": target_final_field,
            }, AUDIT_LOG_FINAL)

            filename = f"collection_category_story_{record_id}.jpg"
            airtable.upload_attachment(record_id, target_final_field, final_temp_path, filename)
            fields[target_final_field] = [{"filename": filename, "url": f"file://{final_temp_path}"}]
            update_status_if_valid(airtable, record_id, STATUS_COMPLETE)
            print(
                f"[OK] Attached converted 9:16 Story to '{target_final_field}' and updated "
                f"{STATUS_FIELD} -> '{STATUS_COMPLETE}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed final story assembly for record {record_id}: {error}")
            failed += 1
        finally:
            for tmp in downloaded_temps:
                try:
                    tmp.cleanup()
                except Exception:
                    pass
            if final_temp_path and final_temp_path.is_file():
                try:
                    final_temp_path.unlink()
                except Exception:
                    pass

    print(
        f"[INFO] 9:16 Auto-Grid Story assembly complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# Interactive Menu & Execution
# ══════════════════════════════════════════════════════════════════════════

def show_menu() -> str:
    print("\n" + "=" * 64)
    print("      COLLECTION CATEGORY STORY AI GENERATION & BLENDING      ")
    print("=" * 64)
    print(" Select a phase to run:\n")
    print(" [1] Step 0: Scrape Akeneo Products to Airtable (3 items/row) + Layout")
    print(" [2] Phase 1: Krea AI Interior Generation (16:9) -> 'Interior1/2/3'")
    print(" [3] Phase 2: Claude Sonnet 5 Prompt Generation (Fal AI) -> 'Prompt1/2/3'")
    print(" [4] Phase 3: Fal AI Nano Banana Pro Blending (16:9) -> 'Blended Image 1/2/3'")
    print(" [5] Phase 4: 9:16 Auto-Grid & Logo Story Conversion (Blended 1/2/3 -> Converted)")
    print(" [6] Run Full End-to-End Row-by-Row Pipeline (Scrape -> Layout -> Phases 1 to 4 -> Next Row)")
    print(" [7] Exit\n")

    menu_choices = {
        "1": "scrape",
        "2": "interior",
        "3": "prompt",
        "4": "blend",
        "5": "assembly",
        "6": "all",
        "7": "exit",
    }
    while True:
        choice = input(" Enter choice [1-7]: ").strip()
        if choice in menu_choices:
            return menu_choices[choice]
        print("[WARN] Invalid option. Please enter 1, 2, 3, 4, 5, 6, or 7.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Collection Category Story AI Generation & Blending Pipeline"
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["scrape", "interior", "prompt", "blend", "assembly", "conversion", "all", "menu"],
        default="all",
        help="Mode of operation: scrape, interior, prompt, blend, assembly, all, or menu (default: all)",
    )
    parser.add_argument(
        "--category",
        "-c",
        default=None,
        help=f"Target category code (default: auto-detected from table ID, or {DEFAULT_CATEGORY})",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help=f"Airtable table ID override (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help=f"Krea Moodboard ID override (default: {DEFAULT_MOODBOARD_ID})",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N rows per phase / run",
    )
    parser.add_argument(
        "--record-id",
        "--target-record-id",
        dest="target_record_id",
        default=None,
        help="Process only a specific Airtable record ID",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help=f"Krea interior generation prompt override (default: '{DEFAULT_PROMPT}')",
    )
    return parser.parse_args(argv)


def scrape_random_collection_category_row(
    airtable: ScrapeAirtableClient,
    settings: Any,
    category_code: str,
    table_id: str,
    items_count: int = 3,
) -> str | None:
    """Scrape products from Akeneo (sorted newest to oldest) and randomly select 3 eligible items."""
    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=settings.channel_name,
    )
    akeneo.authenticate()

    airtable.ensure_product_fields(items_per_row=items_count)
    existing_skus, incomplete = airtable.load_inventory()

    akeneo_cat = akeneo_category_code(category_code)
    query = {
        "categories": [{"operator": "IN", "value": [akeneo_cat]}],
        "Style2": [{"operator": "IN", "value": [settings.style_code]}],
    }
    print(f"[INFO] Fetching {settings.style_code} {category_code} products from Akeneo (newest to oldest)...")
    products = akeneo.fetch_products(query)

    existing_names, existing_media = existing_product_identities(products, existing_skus)
    all_new_items, stats = select_new_products(
        products,
        existing_skus,
        existing_item_names=existing_names,
        existing_media_codes=existing_media,
        category_code=category_code,
    )

    if not all_new_items:
        print(f"[WARN] No new eligible products found in Akeneo for {category_code}.")
        return None

    if len(all_new_items) < items_count:
        print(f"[WARN] Only {len(all_new_items)} new products found in Akeneo (needed {items_count}). Using all available.")
        chosen_items = list(all_new_items)
    else:
        # Randomly select 3 products from the pool of newest-to-oldest candidates
        chosen_items = random.sample(all_new_items, items_count)

    skus_str = ", ".join(it.sku for it in chosen_items)
    print(f"[INFO] Randomly selected {len(chosen_items)} products ({skus_str}) from {len(all_new_items)} newest-to-oldest eligible items.")

    try:
        record_id = airtable.create_product_record(chosen_items)
        print(f"[OK] Created new Airtable record: {record_id}")
    except Exception as err:
        print(f"[ERROR] Failed creating product record in Airtable: {err}")
        return None

    # Upload product photos for each slot
    for slot, item in enumerate(chosen_items):
        field_name = airtable.resolve_slot_field("Furniture Item", slot)
        downloaded = None
        try:
            downloaded = akeneo.download_media(item.media_code)
            filename = attachment_filename(item.item_name, item.media_code)
            airtable.upload_attachment(record_id, field_name, downloaded, filename)
            print(f"  [OK] Uploaded {item.sku} photo -> '{field_name}'")
        except Exception as error:
            print(f"  [ERROR] Failed uploading photo for {item.sku} to {field_name}: {error}")
        finally:
            if downloaded:
                downloaded.cleanup()

    # Upload layout photo to 'Collection Category Layout'
    ensure_collection_category_layout_uploaded(airtable, record_id)

    # Upload transparent HomeCartel logo to 'Logo'
    ensure_homecartel_logo_uploaded(airtable, record_id)

    return record_id


def run_pipeline(
    mode: str = "all",
    category: str | None = None,
    table_id: str | None = None,
    moodboard_id: str | None = None,
    interior_prompt: str | None = None,
    max_items: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Execute the selected phases of the Collection Category Story pipeline."""
    if mode == "menu":
        mode = show_menu()
        if mode == "exit":
            print("[INFO] Exiting menu.")
            return True

    base = load_settings()
    target_table_id = table_id or DEFAULT_TABLE_ID
    tbl_cfg = COLLECTION_STORY_TABLES.get(target_table_id, {})

    category_code = category or tbl_cfg.get("category_code") or DEFAULT_CATEGORY
    if not category_code.endswith("_collec_story") and f"{category_code}_collec_story" in SCRAPE_CATEGORIES:
        category_code = f"{category_code}_collec_story"

    os.environ["AKENEO_CATEGORY"] = category_code

    settings = load_scrape_settings(category_code=category_code, table_id_override=target_table_id)
    target_table_id = table_id or settings.airtable_table_id or target_table_id
    target_moodboard = (
        moodboard_id
        or tbl_cfg.get("default_moodboard_id")
        or moodboard_id_for_category(category_code, DEFAULT_MOODBOARD_ID)
        or DEFAULT_MOODBOARD_ID
    )
    target_prompt = interior_prompt or tbl_cfg.get("default_prompt") or DEFAULT_PROMPT

    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        target_table_id,
    )

    count = max_items or 1
    failures = 0

    print("\n" + "=" * 64)
    print("  COLLECTION CATEGORY STORY AI PIPELINE")
    print("=" * 64)
    print(f"  Mode:         {mode.upper()}")
    print(f"  Category:     {category_code}")
    print(f"  Table ID:     {target_table_id}")
    print(f"  Moodboard ID: {target_moodboard}")
    print(f"  Rows Count:   {max_items or 'unlimited / 1 default'}")
    if target_record_id:
        print(f"  Target Record: {target_record_id}")
    print("=" * 64)


    # ── Single Step Modes ──

    if mode == "scrape":
        print(f"[INFO] Scraping {count} row(s) with randomized newest-to-oldest items from Akeneo...")
        for i in range(count):
            rec_id = scrape_random_collection_category_row(
                airtable, settings, category_code, target_table_id, items_count=3
            )
            if not rec_id:
                failures += 1
        return failures == 0

    if mode == "interior":
        base.require({"krea"})
        krea = KreaClient(base.krea_token, base.krea_base_url)
        return generate_krea_interiors_pipeline(
            krea,
            airtable,
            moodboard_id=target_moodboard,
            prompt=target_prompt,
            limit_records=max_items,
            target_record_id=target_record_id,
        )

    if mode == "prompt":
        base.require({"fal"})
        fal = FalClient(api_key=base.fal_key)
        return generate_claude_blending_prompts(
            fal,
            airtable,
            vision_model=FAL_VISION_MODEL,
            limit_records=max_items,
            target_record_id=target_record_id,
        )

    if mode == "blend":
        base.require({"fal"})
        fal = FalClient(api_key=base.fal_key)
        return generate_nano_banana_blends(
            fal,
            airtable,
            blend_model=FAL_BLENDING_MODEL,
            aspect_ratio=BLENDED_ASPECT_RATIO,
            limit_records=max_items,
            target_record_id=target_record_id,
        )

    if mode in ("assembly", "conversion"):
        return generate_collection_category_story_final_assembly(
            None,
            airtable,
            assembly_model=FAL_ASSEMBLY_MODEL,
            limit_records=max_items,
            target_record_id=target_record_id,
        )

    # ── mode == 'all': Full Row-by-Row Sequential Pipeline Loop ──
    # (Scrape 3 items + Upload Layout -> Phase 1 Interior -> Phase 2 Claude Prompt -> Phase 3 Nano Blend -> Phase 4 Story Conversion -> Next Row)

    base.require({"krea", "fal"})
    krea = KreaClient(base.krea_token, base.krea_base_url)
    fal = FalClient(api_key=base.fal_key)

    for row_idx in range(1, count + 1):
        print(f"\n{'=' * 30} ROW {row_idx}/{count} {'=' * 30}")
        if target_record_id:
            row_rec_id = target_record_id
            rec_data = airtable.get_record(row_rec_id) if hasattr(airtable, "get_record") else None
            fields = rec_data.get("fields", {}) if rec_data else {}
            label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or row_rec_id
            print(f"[INFO] Processing targeted record {row_rec_id} ({label})...")
        else:
            incomplete_rec = get_first_incomplete_record(airtable)
            if incomplete_rec:
                row_rec_id = incomplete_rec["id"]
                fields = incomplete_rec.get("fields", {})
                label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or row_rec_id
                print(f"[INFO] Found incomplete row: Record {row_rec_id} ({label}). Completing this row...")
            else:
                print(f"[INFO] [Step 0/4] Scraping 3 random product items (1 row) from newest-to-oldest Akeneo candidates...")
                row_rec_id = scrape_random_collection_category_row(
                    airtable, settings, category_code, target_table_id, items_count=3
                )
                if not row_rec_id:
                    print(f"[ERROR] Failed scraping Akeneo products on Row {row_idx}.")
                    failures += 1
                    continue

                rec_data = airtable.get_record(row_rec_id) if hasattr(airtable, "get_record") else None
                fields = rec_data.get("fields", {}) if rec_data else {}

        # Step 0b: Ensure Layout and Logo are attached
        ensure_collection_category_layout_uploaded(airtable, row_rec_id, fields)
        ensure_homecartel_logo_uploaded(airtable, row_rec_id, fields)

        # Phase 1: Krea AI Interior Generation (16:9)
        print(f"[INFO] [Phase 1/4] Generating 3 Krea AI 16:9 Interiors for Record {row_rec_id}...")
        if not generate_krea_interiors_pipeline(
            krea,
            airtable,
            moodboard_id=target_moodboard,
            prompt=target_prompt,
            limit_records=1,
            target_record_id=row_rec_id,
        ):
            print(f"[ERROR] Phase 1: Interior generation failed for record {row_rec_id}")
            failures += 1
            continue

        # Phase 2: Claude Sonnet 5 Prompt Generation (via Fal AI)
        print(f"[INFO] [Phase 2/4] Generating 3 Claude Sonnet 5 Prompts for Record {row_rec_id}...")
        if not generate_claude_blending_prompts(
            fal,
            airtable,
            vision_model=FAL_VISION_MODEL,
            limit_records=1,
            target_record_id=row_rec_id,
        ):
            print(f"[ERROR] Phase 2: Prompt generation failed for record {row_rec_id}")
            failures += 1
            continue

        # Phase 3: Fal AI Nano Banana Pro 16:9 Blending
        print(f"[INFO] [Phase 3/4] Blending 3 Slots with Fal AI Nano Banana Pro for Record {row_rec_id}...")
        if not generate_nano_banana_blends(
            fal,
            airtable,
            blend_model=FAL_BLENDING_MODEL,
            aspect_ratio=BLENDED_ASPECT_RATIO,
            limit_records=1,
            target_record_id=row_rec_id,
        ):
            print(f"[ERROR] Phase 3: Blending failed for record {row_rec_id}")
            failures += 1
            continue

        # Phase 4: 9:16 Auto-Grid Story Conversion (Interior1/2/3 + Logo)
        print(f"[INFO] [Phase 4/4] Generating 9:16 Auto-Grid Story Conversion for Record {row_rec_id}...")
        if not generate_collection_category_story_final_assembly(
            fal,
            airtable,
            assembly_model=FAL_ASSEMBLY_MODEL,
            limit_records=1,
            target_record_id=row_rec_id,
        ):
            print(f"[ERROR] Phase 4: Story conversion failed for record {row_rec_id}")
            failures += 1
            continue

        print(f"[ROW {row_idx} COMPLETE] Record {row_rec_id} is 100% COMPLETE! Status: Complete.\n")

        if target_record_id:
            break

    print("\n" + "=" * 64)
    if failures == 0:
        print("[OK] Collection Category Story pipeline executed successfully!")
    else:
        print(f"[WARN] Pipeline completed with {failures} row failure(s).")
    print("=" * 64)

    return failures == 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    success = run_pipeline(
        mode=args.mode,
        category=args.category,
        table_id=args.table_id,
        moodboard_id=args.moodboard_id,
        interior_prompt=args.prompt,
        max_items=args.max_items,
        target_record_id=args.target_record_id,
    )
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
