"""End-to-End Moodboard Reel Automation Pipeline (5-Phase Architecture).

Row-by-Row Execution Flow:
  1. Phase 1 (Auto Scrape): Scrapes 1 row (4 products) from Akeneo (Newest to Oldest, Modern style) -> Airtable (Status: 'Standby')
  2. Phase 2 (Interior Generation): Generates 4 room interiors via Krea AI (9:16, moodboard de6ad512-870d-4ab7-a48c-3f3ca85faf24) -> (Status: 'Already attached a room Interior')
  3. Phase 2.5 (Vision Prompting): Generates 4 detailed prompts via Claude Sonnet 5 on Fal AI OpenRouter -> (Status: 'Processing')
  4. Phase 3 (Image Blending): Blends 4 pairs via Fal AI nano-banana-pro/edit -> Moodboard Blended
  5. Phase 4 (Moodboard Conversion): Re-blends against template via Fal AI nano-banana-pro/edit -> Converted Moodboard
  6. Phase 4.5 (Music Generation): Generates 20s 120 BPM luxury lounge background music via Fal AI ElevenLabs -> Music Generated
  7. Phase 5 (Reel Assembly): FFmpeg 2x2 Collage + 8 Slide Sequence + Outro + Audio Mix -> REEL - Moodboard Reel -> (Status: 'Complete')

Usage::
    python run_moodboard_reel.py --dry-run
    python run_moodboard_reel.py --category chandelier_modern
    python run_moodboard_reel.py --category pendant_lights_reel --limit 1
    python run_moodboard_reel.py --phase music --limit 1
    python generate_moodboard_reel_pipeline.py --phase music --execute
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from content_automation.akeneo_client import AkeneoClient
from content_automation.airtable_client import inject_generated_timestamp
from content_automation.assets import MAX_PROMPT_LENGTH, AssetCatalog
from content_automation.config import (
    MOODBOARD_REEL_CATEGORIES,
    TABLES,
    load_settings,
)
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.prompts import build_vision_blending_instruction
from content_automation.fields import (
    furniture_field,
    interior_field,
    item_name_field,
    sku_field,
)
from content_automation.foreign_key import generate_foreign_key
from content_automation.http import request_with_retry, response_error
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename
from content_automation.models import LocalImage
from content_automation.item_tagger import TARGET_BLENDED_FIELD, tag_blended_image
from content_automation.shopify_client import ShopifyCatalogIndex, ShopifyClient
from content_automation.scraping import (
    ScrapeAirtableClient,
    categories,
    load_scrape_settings,
)
from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    identity_key,
    select_new_products,
)

DEFAULT_TABLE_CODE = "chandelier_modern"
DEFAULT_MOODBOARD_ID = "de6ad512-870d-4ab7-a48c-3f3ca85faf24"
SLOT_COUNT = 4

# Exact status options matching Airtable single select field:
STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_ATTACHED_INTERIOR = "Already attached a room Interior"
STATUS_PROCESSING = "Processing"
STATUS_COMPLETE = "Complete"

BLENDED_FIELD = "Moodboard Blended"
CONVERTED_FIELD = "Converted Moodboard"
TEXTURE_FIELDS = [f"Texture{i}" for i in range(1, 13)]
REFERENCE_FIELD = "Moodboard Reference Photo"
MOODBOARD_PROMPT_FIELD = "Moodboard Prompt"
REEL_FIELD = "REEL - Moodboard Reel"
MUSIC_FIELD = "Music Generated"
OUTRO_FIELD = "Outro"

COLLAGE_FILENAME = "collage_mb.jpg"
REEL_FILENAME = "moodboard_reel.mp4"
COLLAGE_COLS, COLLAGE_ROWS = 2, 2
COLLAGE_CELLS = COLLAGE_COLS * COLLAGE_ROWS

class BlendedSlotMap(dict):
    """Mapping of slot indices to LocalImages, with a tagged_map attribute for YOLO tagged blends."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tagged_map: dict[int, LocalImage] = {}

VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920
VIDEO_FPS = 30
SLIDE_SECONDS = 2
OUTRO_SECONDS = 3
FADE_SECONDS = 1
AUDIO_BITRATE = "192k"
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024

BLENDING_MODEL = "fal-ai/nano-banana-pro/edit"
CLAUDE_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "anthropic/claude-sonnet-5").strip()
PROMPT_ASSET = "converted_moodboard.json"

API_BASE = "https://api.airtable.com/v0"
CONTENT_BASE = "https://content.airtable.com/v0"


def prompt_field_candidates(slot: int) -> list[str]:
    """Candidates for prompt field name in Airtable: Prompt1, Prompt2, Prompt3, Prompt4."""
    return [f"Prompt{slot + 1}"]


def get_prompt_value(fields: dict[str, Any], slot: int) -> str:
    """Get prompt text for a slot checking both naming styles."""
    for name in prompt_field_candidates(slot):
        val = str(fields.get(name) or "").strip()
        if val:
            return val
    return ""


def get_attachment_field(fields: dict[str, Any], base_name: str, slot: int) -> list[dict[str, Any]]:
    """Retrieve attachments handling either 'Field', 'Field2' or 'Field 2' casing."""
    candidates = []
    if slot == 0:
        candidates = [base_name, f"{base_name} 1", f"{base_name}1"]
    else:
        candidates = [f"{base_name}{slot + 1}", f"{base_name} {slot + 1}"]

    for cand in candidates:
        val = fields.get(cand)
        if val and isinstance(val, list):
            return val
    return []


# ---------------------------------------------------------------------------
# Airtable HTTP helpers
# ---------------------------------------------------------------------------

def _airtable_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _list_records(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    fields: list[str] | None = None,
    *,
    formula: str = "",
) -> list[dict[str, Any]]:
    url = f"{API_BASE}/{base_id}/{table_id}"
    records: list[dict[str, Any]] = []
    offset = ""
    while True:
        params: list[tuple[str, str]] = [("pageSize", "100")]
        if formula:
            params.append(("filterByFormula", formula))
        if offset:
            params.append(("offset", offset))
        resp = request_with_retry(
            session, "GET", url, headers=_airtable_headers(token), params=params
        )
        if not resp.ok:
            raise response_error(resp, "List Airtable records")
        payload = resp.json()
        records.extend(payload.get("records", []))
        offset = str(payload.get("offset") or "")
        if not offset:
            return records


def _get_record(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    record_id: str,
) -> dict[str, Any]:
    url = f"{API_BASE}/{base_id}/{table_id}/{record_id}"
    resp = request_with_retry(session, "GET", url, headers=_airtable_headers(token))
    if not resp.ok:
        raise response_error(resp, f"Get record {record_id}")
    return resp.json()


def _ensure_field(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    field_name: str,
    field_type: str,
) -> None:
    schema_url = f"{API_BASE}/meta/bases/{base_id}/tables"
    resp = request_with_retry(
        session, "GET", schema_url, headers=_airtable_headers(token)
    )
    if not resp.ok:
        return
    for table in resp.json().get("tables", []):
        if table.get("id") == table_id:
            existing = {f["name"] for f in table.get("fields", [])}
            if field_name in existing:
                return
            break
    else:
        return

    create_url = f"{API_BASE}/meta/bases/{base_id}/tables/{table_id}/fields"
    resp = request_with_retry(
        session,
        "POST",
        create_url,
        headers=_airtable_headers(token),
        json={"name": field_name, "type": field_type},
    )
    if resp.ok:
        print(f"  [OK] Created Airtable field '{field_name}'")


def _update_record_fields(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    record_id: str,
    patch_fields: dict[str, Any],
) -> dict[str, Any]:
    url = f"{API_BASE}/{base_id}/{table_id}/{record_id}"
    req_fields = inject_generated_timestamp(patch_fields)
    resp = request_with_retry(
        session,
        "PATCH",
        url,
        headers=_airtable_headers(token),
        json={"fields": req_fields},
    )
    if not resp.ok and ("Date and Time Generated" in resp.text or "Date and Time" in resp.text):
        fallback_fields = dict(req_fields)
        if "Date and Time Generated" in fallback_fields:
            fallback_fields["Date and Time"] = fallback_fields.pop("Date and Time Generated")
            resp = request_with_retry(
                session, "PATCH", url, headers=_airtable_headers(token), json={"fields": fallback_fields}
            )
        if not resp.ok and ("Date and Time Generated" in resp.text or "Date and Time" in resp.text):
            clean_fields = {k: v for k, v in req_fields.items() if k not in ("Date and Time Generated", "Date and Time")}
            resp = request_with_retry(
                session, "PATCH", url, headers=_airtable_headers(token), json={"fields": clean_fields}
            )
    if not resp.ok:
        raise response_error(resp, f"Update record {record_id}")

    ret = resp.json()
    try:
        f = ret.get("fields", {})
        if not f.get("Foreign Key ID") and f.get("ID") is not None:
            fk = generate_foreign_key(table_id, f["ID"])
            request_with_retry(
                session, "PATCH", url, headers=_airtable_headers(token), json={"fields": {"Foreign Key ID": fk}}
            )
    except Exception:
        pass
    return ret


def _clear_attachment_field(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    record_id: str,
    field_name: str,
) -> None:
    _update_record_fields(session, token, base_id, table_id, record_id, {field_name: []})


def _upload_attachment(
    session: requests.Session,
    token: str,
    base_id: str,
    record_id: str,
    field_name: str,
    image: LocalImage,
) -> None:
    url = (
        f"{CONTENT_BASE}/{base_id}/{record_id}/"
        f"{quote(field_name, safe='')}/uploadAttachment"
    )
    payload = {
        "contentType": image.content_type or "image/jpeg",
        "file": base64.b64encode(image.path.read_bytes()).decode("ascii"),
        "filename": image.filename,
    }
    resp = request_with_retry(
        session, "POST", url, headers=_airtable_headers(token), json=payload
    )
    if not resp.ok:
        raise response_error(resp, f"Upload {image.filename} to {field_name}")


def _download_attachment_url(
    session: requests.Session,
    url: str,
    destination: Path,
) -> LocalImage:
    resp = request_with_retry(session, "GET", url)
    if not resp.ok:
        raise response_error(resp, "Download attachment from Airtable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(resp.content)
    ct = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0]
    return LocalImage(destination, destination.name, ct)


def _slot_from_filename(filename: str, prefix: str, fallback: int) -> int:
    """Map 'blended_mb3.jpg' with prefix 'blended_mb' -> slot 2."""
    match = re.search(rf"{re.escape(prefix)}(\d+)", filename or "", re.IGNORECASE)
    if match:
        return int(match.group(1)) - 1
    return fallback


def images_from_field(
    attachments: list[dict[str, Any]],
    session: requests.Session,
    workdir: Path,
    prefix: str,
) -> dict[int, LocalImage]:
    """Download an attachment field to disk, keyed by slot index."""
    images: dict[int, LocalImage] = {}
    for position, attachment in enumerate(attachments):
        url = str(attachment.get("url") or "")
        if not url:
            continue
        filename = str(attachment.get("filename") or "")
        slot = _slot_from_filename(filename, prefix, position)
        destination = workdir / f"{prefix}{slot + 1}.jpg"
        images[slot] = _download_attachment_url(session, url, destination)
    return images


# ---------------------------------------------------------------------------
# Dynamic Prompts for Krea & Claude Vision
# ---------------------------------------------------------------------------

def krea_interior_prompt(category_code: str, override_prompt: str = "") -> str:
    """Resolve interior prompt for Krea room generation."""
    if override_prompt.strip():
        return override_prompt.strip()

    cat = category_code.lower()
    # Check environment variable overrides
    env_prompt = (
        os.getenv(f"MOODBOARD_REEL_PROMPT_{cat.upper()}", "").strip()
        or os.getenv(f"KREA_INTERIOR_PROMPT_{cat.upper()}", "").strip()
        or (os.getenv("MOODBOARD_REEL_PROMPT_CHANDELIER", "").strip() if "chandelier" in cat else "")
    )
    if env_prompt:
        return env_prompt

    if "chandelier" in cat:
        return "Generate me a modern living room"
    elif "pendant" in cat:
        return "Generate me a modern dining room"
    elif "floor" in cat:
        return "Generate me a modern living room with empty floor space for a standing floor lamp"
    elif "wall" in cat or "sconce" in cat:
        return "Generate me a modern living room with a wall light"
    elif "table" in cat:
        return "Generate me a modern bedroom with a bedside table for a table lamp"
    else:
        return "Generate me a modern living room"


def claude_vision_instruction(
    category_code: str,
    item_name: str = "",
    materials: dict[str, str] | None = None,
) -> str:
    item_desc = item_name.strip() or "lighting fixture"
    material_line = ""
    if materials:
        words = ", ".join(
            w for w in (
                materials.get("top", "").lower(),
                materials.get("middle", "").lower(),
                materials.get("bottom", "").lower(),
            ) if w
        )
        if words:
            material_line = (
                f"The fixture's three signature materials are {words}: convey them purely visually with clearly "
                f"readable texture, reflectivity and finish on the product in the blended scene. "
                f"Never render words, labels or typography anywhere in the image."
            )

    return build_vision_blending_instruction(
        interior_label="Room Interior",
        item_name=item_desc,
        aspect_ratio="9:16",
        extra_instructions=material_line,
    )


# ---------------------------------------------------------------------------
# Phase 1: Auto Scrape (1 Row = 4 Items)
# ---------------------------------------------------------------------------

def run_phase_1_scrape_one_row(
    category_code: str,
    *,
    style_code: str = "modern",
    execute: bool = True,
) -> str | None:
    """Scrape 4 fresh active products from Akeneo into 1 brand-new Airtable row (Status: 'Standby').

    Enforces:
      1. Cross-table deduplication across all 60+ tables in Airtable base.
      2. Strict Shopify Active & Published cross-check (draft/archived skipped).
      3. Creating a brand-new Airtable record (Status: Standby, Foreign Key ID).
      4. Attaching the 4 product photos into Furniture Item 1..4 slots.

    Returns the newly created record ID (or 'dry_run_record_id' if dry run).
    """
    print("\n" + "=" * 64)
    print(f"[PHASE 1] Auto Scrape (1 Row / 4 Items: Akeneo PIM -> Airtable)")
    print(f"  Category: {category_code} | Style: {style_code} | Items: 4")
    print("=" * 64)

    settings = load_scrape_settings(
        category_code=category_code,
        style_code=style_code,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        settings.airtable_table_id,
    )
    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=settings.channel_name,
    )

    # 1. Stored identities in current table
    stored_names: set[str] = set()
    stored_filenames: set[str] = set()
    stored_skus: set[str] = set()
    try:
        current_records = airtable.inventory_records()
        for r in current_records:
            fields = r.get("fields", {})
            for slot in range(SLOT_COUNT):
                n_val = str(fields.get(airtable.resolve_slot_field("Item Name", slot)) or fields.get(f"Item Name{slot+1}") or "").strip()
                if n_val:
                    stored_names.add(n_val.lower())
                s_val = str(fields.get(airtable.resolve_slot_field("SKU", slot)) or fields.get(f"SKU{slot+1}") or "").strip()
                if s_val:
                    stored_skus.add(s_val)
                att_list = fields.get(airtable.resolve_slot_field("Furniture Item", slot)) or fields.get(f"Furniture Item{slot+1}")
                if isinstance(att_list, list):
                    for a in att_list:
                        if isinstance(a, dict) and a.get("filename"):
                            stored_filenames.add(identity_key(a["filename"]))
    except Exception as err:
        print(f"[WARN] Stored table identities lookup notice: {err}")

    # 2. Base-wide cross-table deduplication across all 60+ tables
    base_filenames: set[str] = set()
    base_names: set[str] = set()
    base_skus: set[str] = set()
    try:
        base_filenames, base_names, base_skus = fetch_all_base_existing_identities(airtable)
        print(
            f"[INFO] Cross-table deduplication active: Found {len(base_skus)} existing SKU(s), "
            f"{len(base_names)} item name(s), and {len(base_filenames)} attachment filename(s) across all base tables."
        )
    except Exception as e:
        print(f"[WARN] Base deduplication fetch notice: {e}")

    all_existing_filenames = stored_filenames | base_filenames
    all_existing_names = stored_names | base_names
    all_existing_skus = stored_skus | base_skus

    # 3. Shopify published catalog cross-check
    shopify_index = None
    try:
        print("[INFO] Fetching published catalog from Shopify (homecartel.net)...")
        shopify = ShopifyClient()
        prods = shopify.fetch_all_products()
        shopify_index = ShopifyCatalogIndex.build(prods)
        print(f"[OK] Shopify Index Ready: {shopify_index.product_count} published products indexed.")
    except Exception as s_err:
        print(f"[WARN] Shopify index check notice: {s_err}")

    # 4. Fetch candidates from Akeneo
    akeneo.authenticate()
    akeneo_cat = categories.akeneo_category_code(category_code)
    query: dict[str, Any] = {
        "categories": [{"operator": "IN", "value": [akeneo_cat]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    if style_code and style_code.lower() != "all":
        query["Style2"] = [{"operator": "IN", "value": [style_code]}]

    print(f"[INFO] Fetching active {style_code} {category_code} products from Akeneo...")
    products = akeneo.fetch_products(query)

    existing_names_query, existing_media_query = existing_product_identities(products, all_existing_skus)
    combined_names = all_existing_names | existing_names_query

    selected, stats = select_new_products(
        products,
        all_existing_skus,
        existing_item_names=combined_names,
        existing_media_codes=existing_media_query,
        category_code=category_code,
    )

    filtered_candidates: list[ProductItem] = []
    for item in selected:
        fn = attachment_filename(item.item_name, item.media_code)
        if identity_key(fn) in all_existing_filenames:
            print(f"[DEDUP SKIP] Existing photo: '{item.item_name}' (SKU: {item.sku}) already exists in Airtable")
            continue
        if item.sku and item.sku.strip() in all_existing_skus:
            print(f"[DEDUP SKIP] Existing SKU: '{item.item_name}' (SKU: {item.sku}) already exists in Airtable")
            continue
        if (item.item_name or "").strip().lower() in all_existing_names:
            print(f"[DEDUP SKIP] Existing Name: '{item.item_name}' already exists in Airtable")
            continue
        if shopify_index and not shopify_index.contains(item.sku, item.item_name):
            print(
                f"[SHOPIFY DRAFT/INACTIVE SKIP] Item '{item.item_name}' (SKU: {item.sku}) is Enabled in Akeneo "
                "but Draft/Inactive in Shopify -> skipping"
            )
            continue

        print(f"[DEDUP PASS] New unique product selected: '{item.item_name}' (SKU: {item.sku})")
        filtered_candidates.append(item)

    print(f"[PLAN] {len(filtered_candidates)} new unique candidate(s) passed deduplication.")

    if len(filtered_candidates) < SLOT_COUNT:
        print(f"[WARN] Needed {SLOT_COUNT} products for a new Moodboard Reel row, but only found {len(filtered_candidates)}.")
        return None

    chunk = filtered_candidates[:SLOT_COUNT]
    skus_str = ", ".join(it.sku for it in chunk)
    print(f"[INFO] Selected 4 products for brand-new row: {skus_str}")

    if not execute:
        print(f"  [DRY RUN] Would create brand-new Airtable row with {skus_str} (Status: 'Standby').")
        return "dry_run_record_id"

    # Create brand-new record
    airtable.ensure_product_fields(items_per_row=SLOT_COUNT)
    record_id = airtable.create_product_record(chunk)
    print(f"[OK] Created brand-new row {record_id} with Status: 'Standby'")

    # Upload product attachments
    for slot, item in enumerate(chunk):
        f_field = airtable.resolve_slot_field("Furniture Item", slot)
        downloaded = None
        try:
            downloaded = akeneo.download_media(item.media_code)
            fn = attachment_filename(item.item_name, item.media_code)
            airtable.upload_attachment(record_id, f_field, downloaded, fn)
            print(f"  [OK] Uploaded slot {slot + 1} ({item.sku}) -> '{f_field}'")
        except Exception as up_err:
            print(f"  [ERROR] Upload slot {slot + 1} ({item.sku}) failed: {up_err}")
        finally:
            if downloaded:
                downloaded.cleanup()

    return record_id


# ---------------------------------------------------------------------------
# Phase 2: Krea Room Interior Generation
# ---------------------------------------------------------------------------

def resolve_moodboard_id(category_code: str, override_id: str = "") -> str:
    """Resolve Krea moodboard ID from CLI override, env var, or defaults."""
    if override_id.strip():
        return override_id.strip()
    table = TABLES.get(category_code)
    env_key = table.moodboard_env if table else "KREA_MOODBOARD_ID_CHANDELIER_MODERN"
    env_val = os.getenv(env_key, "").strip() if env_key else ""
    return env_val or DEFAULT_MOODBOARD_ID


def run_phase_2_interior(
    record: dict[str, Any],
    category_code: str,
    *,
    krea: KreaClient,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir: Path,
    moodboard_id: str = "",
    interior_prompt: str = "",
    force: bool = False,
    execute: bool = True,
) -> int:
    """Generate room interiors for empty slots using Krea AI."""
    record_id = record["id"]
    fields = record.get("fields", {})
    prompt = krea_interior_prompt(category_code, override_prompt=interior_prompt)
    effective_moodboard_id = resolve_moodboard_id(category_code, moodboard_id)

    generated_count = 0
    for slot in range(SLOT_COUNT):
        fur_attachments = get_attachment_field(fields, "Furniture Item", slot)
        if not fur_attachments:
            continue
        int_attachments = get_attachment_field(fields, "Interior", slot)
        if int_attachments and not force:
            continue  # Already has interior

        target_field = "Interior" if slot == 0 else f"Interior{slot + 1}"
        print(f"  [PHASE 2] Record {record_id} Slot {slot + 1}: Generating Krea interior for '{target_field}' (Moodboard: {effective_moodboard_id})...")

        if not execute:
            print(f"    [DRY] Prompt: {prompt[:70]}...")
            print(f"    [DRY] Moodboard ID: {effective_moodboard_id}")
            generated_count += 1
            continue

        try:
            image_url = krea.generate(
                prompt,
                aspect_ratio="9:16",
                resolution="1K",
                moodboard_id=effective_moodboard_id,
            )
            download_dest = workdir / f"krea_interior_{slot + 1}_{record_id}.jpg"
            resp = request_with_retry(session, "GET", image_url)
            if not resp.ok:
                raise response_error(resp, f"Download Krea interior {image_url}")
            download_dest.write_bytes(resp.content)

            local_img = LocalImage(download_dest, download_dest.name, "image/jpeg")
            _upload_attachment(session, token, base_id, record_id, target_field, local_img)
            print(f"    [OK] Uploaded Krea interior -> '{target_field}'")
            generated_count += 1
        except Exception as err:
            print(f"    [ERROR] Krea interior generation failed for slot {slot + 1}: {err}")

    if execute and generated_count > 0:
        try:
            _update_record_fields(
                session, token, base_id, table_id, record_id,
                {STATUS_FIELD: STATUS_ATTACHED_INTERIOR}
            )
            print(f"  [STATUS] Record {record_id} -> '{STATUS_ATTACHED_INTERIOR}'")
        except Exception as err:
            print(f"  [WARN] Could not update status: {err}")

    return generated_count


# ---------------------------------------------------------------------------
# Phase 2.5: Claude Vision Prompting
# ---------------------------------------------------------------------------

def run_phase_2_5_vision(
    record: dict[str, Any],
    category_code: str,
    *,
    fal: FalClient,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    vision_model: str = CLAUDE_VISION_MODEL,
    execute: bool = True,
) -> int:
    """Generate detailed blending prompts (with unique per-slot materials) using Claude Vision on Fal AI OpenRouter."""
    record_id = record["id"]
    fields = record.get("fields", {})

    slot_targets: dict[int, tuple[str, str, str]] = {}
    for slot in range(SLOT_COUNT):
        existing_prompt = get_prompt_value(fields, slot)
        if existing_prompt:
            continue

        fur_attachments = get_attachment_field(fields, "Furniture Item", slot)
        int_attachments = get_attachment_field(fields, "Interior", slot)
        if not fur_attachments or not int_attachments:
            continue

        fur_url = str(fur_attachments[0].get("url") or "")
        int_url = str(int_attachments[0].get("url") or "")
        if not fur_url or not int_url:
            continue

        item_name = str(fields.get(item_name_field(slot)) or "").strip()
        slot_targets[slot] = (fur_url, int_url, item_name)

    if not slot_targets:
        return 0

    prompt_count = 0
    updates: dict[str, Any] = {}

    ordered_slots = sorted(slot_targets)
    material_words: dict[int, dict[str, str]] = {}
    if execute:
        print(f"  [PHASE 2.5] Record {record_id}: Generating {len(ordered_slots) * 3} unique material words via {vision_model}...")
        material_words = generate_unique_material_words(
            fal,
            [slot_targets[s][0] for s in ordered_slots],
            [slot_targets[s][2] or f"Slot {s + 1}" for s in ordered_slots],
            model=vision_model,
        )
        for slot in ordered_slots:
            words = material_words[slot]
            updates[f"Texture{slot * 3 + 1}"] = words["top"]
            updates[f"Texture{slot * 3 + 2}"] = words["middle"]
            updates[f"Texture{slot * 3 + 3}"] = words["bottom"]
            print(f"    [OK] Slot {slot + 1} unique materials: {words['top']}, {words['middle']}, {words['bottom']}")
    else:
        for slot in ordered_slots:
            print(f"    [DRY] Slot {slot + 1}: would generate unique material words -> Texture{slot * 3 + 1}..{slot * 3 + 3}, then vision prompt -> Prompt{slot + 1}")

    for slot in ordered_slots:
        fur_url, int_url, item_name = slot_targets[slot]
        instruction = claude_vision_instruction(category_code, item_name, material_words.get(slot))
        target_prompt_field = f"Prompt{slot + 1}"

        print(f"  [PHASE 2.5] Record {record_id} Slot {slot + 1}: Crafting vision prompt via {vision_model}...")

        if not execute:
            print(f"    [DRY] Send Interior ({int_url[:30]}...) + Furniture ({fur_url[:30]}...) -> {vision_model}")
            prompt_count += 1
            continue

        try:
            generated_prompt = fal.generate_vision_prompt(
                image_urls=[int_url, fur_url],
                prompt=instruction,
                model=vision_model,
            )
            clean_prompt = generated_prompt.strip().strip('"').strip("'")
            updates[target_prompt_field] = clean_prompt
            print(f"    [OK] Generated prompt for {target_prompt_field} ({len(clean_prompt)} chars): {clean_prompt[:60]}...")
            prompt_count += 1
        except Exception as err:
            print(f"    [ERROR] Claude vision prompt failed for slot {slot + 1}: {err}")

    if updates and execute:
        try:
            updates[STATUS_FIELD] = STATUS_PROCESSING
            _update_record_fields(session, token, base_id, table_id, record_id, updates)
            print(f"    [OK] Saved {len([k for k in updates if k != STATUS_FIELD])} field(s) to Airtable ({', '.join(k for k in updates if k != STATUS_FIELD)}), Status -> '{STATUS_PROCESSING}'")
        except Exception as err:
            print(f"    [ERROR] Could not save prompts to Airtable: {err}")

    return prompt_count


# ---------------------------------------------------------------------------
# Phase 3: Image Blending (Fal AI Nano Banana Pro)
# ---------------------------------------------------------------------------

@dataclass
class SlotPair:
    slot: int
    interior_url: str
    furniture_url: str
    prompt: str
    output_filename: str


def extract_slot_pairs(fields: dict[str, Any]) -> list[SlotPair]:
    pairs: list[SlotPair] = []
    for slot in range(SLOT_COUNT):
        int_attachments = get_attachment_field(fields, "Interior", slot)
        fur_attachments = get_attachment_field(fields, "Furniture Item", slot)
        prompt_text = get_prompt_value(fields, slot)

        if not int_attachments or not fur_attachments or not prompt_text:
            continue
        int_url = str(int_attachments[0].get("url") or "")
        fur_url = str(fur_attachments[0].get("url") or "")
        if not int_url or not fur_url:
            continue

        pairs.append(
            SlotPair(
                slot=slot,
                interior_url=int_url,
                furniture_url=fur_url,
                prompt=prompt_text,
                output_filename=f"blended_mb{slot + 1}.jpg",
            )
        )
    return pairs


def blend_slot(pair: SlotPair, fal: FalClient, workdir: Path) -> LocalImage:
    result_url = fal.generate(
        pair.prompt,
        [pair.interior_url, pair.furniture_url],
        aspect_ratio="9:16",
        model=BLENDING_MODEL,
    )
    destination = workdir / pair.output_filename
    return fal.download_jpeg(result_url, destination)


def run_phase_3_blend(
    record: dict[str, Any],
    *,
    fal: FalClient,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir: Path,
    execute: bool = True,
    skip_existing: bool = True,
) -> dict[int, LocalImage] | None:
    """Blend Interior + Furniture pairs via Fal AI Nano Banana Pro."""
    record_id = record["id"]
    fields = record.get("fields", {})

    existing_blended = fields.get(BLENDED_FIELD) or []
    if skip_existing and isinstance(existing_blended, list) and len(existing_blended) >= SLOT_COUNT:
        print(f"\n  [PHASE 3] Record {record_id}: Found {len(existing_blended)} existing '{BLENDED_FIELD}' image(s) in Airtable.")
        if not execute:
            return BlendedSlotMap({s: LocalImage(workdir / f"blended_mb{s + 1}.jpg", f"blended_mb{s + 1}.jpg", "image/jpeg") for s in range(len(existing_blended))})
        cached = images_from_field(existing_blended, session, workdir, "blended_mb")
        if cached and len(cached) >= SLOT_COUNT:
            print(f"    [OK] Reusing {len(cached)} existing blended image(s) from Airtable (Skipped Fal AI Blending).")
            res = BlendedSlotMap(cached)
            existing_tagged = fields.get(TARGET_BLENDED_FIELD) or []
            if existing_tagged and isinstance(existing_tagged, list):
                cached_tagged = images_from_field(existing_tagged, session, workdir, "blended_tagged_mb")
                if cached_tagged:
                    res.tagged_map = cached_tagged
            return res

    pairs = extract_slot_pairs(fields)

    if not pairs:
        print(f"  [SKIP] Record {record_id}: No complete Interior + Furniture + Prompt pairs to blend.")
        return None

    print(f"\n  [PHASE 3] Record {record_id}: Blending {len(pairs)} slot pair(s) via Fal AI Nano Banana Pro...")
    if not execute:
        for p in pairs:
            print(f"    [DRY] Slot {p.slot + 1}: Interior + Furniture + Prompt -> {p.output_filename}")
        return BlendedSlotMap({p.slot: LocalImage(workdir / p.output_filename, p.output_filename, "image/jpeg") for p in pairs})

    results = BlendedSlotMap()
    with ThreadPoolExecutor(max_workers=SLOT_COUNT) as pool:
        futures = {pool.submit(blend_slot, p, fal, workdir): p for p in pairs}
        for future in as_completed(futures):
            p = futures[future]
            try:
                img = future.result()
                results[p.slot] = img
                print(f"    [OK] Blended slot {p.slot + 1} -> {p.output_filename}")
            except Exception as err:
                print(f"    [ERROR] Blending slot {p.slot + 1} failed: {err}")

    if not results:
        return None

    try:
        _clear_attachment_field(session, token, base_id, table_id, record_id, BLENDED_FIELD)
    except Exception:
        pass

    try:
        _ensure_field(session, token, base_id, table_id, TARGET_BLENDED_FIELD, "multipleAttachments")
    except Exception:
        pass

    for slot in sorted(results):
        _upload_attachment(session, token, base_id, record_id, BLENDED_FIELD, results[slot])
        print(f"    [OK] Uploaded {results[slot].filename} -> '{BLENDED_FIELD}'")

        # Auto-tag furniture item name onto Moodboard Reel blended photo using YOLO-World
        try:
            from content_automation.akeneo_client import split_item_name
            raw_name = str(fields.get(f"Item Name{slot}") or fields.get(f"SKU{slot}") or f"Furniture Item {slot}").strip()
            item_title, product_type = split_item_name(raw_name, fallback_product_type="Lighting")
            tagged_dir = workdir / "tagged_blends"
            tagged_dir.mkdir(parents=True, exist_ok=True)
            tagged_path = tagged_dir / f"tagged_slot{slot}.jpg"
            tag_blended_image(
                image_input=results[slot].path,
                item_name=item_title,
                product_type=product_type,
                category="chandeliers",
                destination=tagged_path,
                fallback_if_undetected=True,
            )
            tagged_img = LocalImage(tagged_path, f"blended_tagged_slot{slot}.jpg")
            results.tagged_map[slot] = tagged_img
            # Upload to Airtable TARGET_BLENDED_FIELD
            try:
                _upload_attachment(session, token, base_id, record_id, TARGET_BLENDED_FIELD, tagged_img)
                print(f"    [ITEM TAGGING] Uploaded tagged blend -> '{TARGET_BLENDED_FIELD}'")
            except Exception as up_err:
                print(f"    [WARN] Failed uploading tagged blend: {up_err}")
        except Exception as tag_err:
            print(f"    [WARN] YOLO tagging notice on slot {slot}: {tag_err}")

    return results


# ---------------------------------------------------------------------------
# Phase 4: Convert Phase (Blended + Reference Template)
# ---------------------------------------------------------------------------

def resolve_moodboard_prompt(fields: dict[str, Any], assets: AssetCatalog) -> str:
    prompt = str(fields.get(MOODBOARD_PROMPT_FIELD) or "").strip()
    if not prompt:
        return assets.read_prompt(PROMPT_ASSET)
    try:
        prompt = json.dumps(json.loads(prompt), ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    return prompt[:MAX_PROMPT_LENGTH]


def convert_slot(
    slot: int,
    blended_url: str,
    reference_url: str,
    prompt: str,
    fal: FalClient,
    workdir: Path,
) -> LocalImage:
    result_url = fal.generate(
        prompt,
        [reference_url, blended_url],
        aspect_ratio="9:16",
        model=BLENDING_MODEL,
    )
    destination = workdir / f"converted_mb{slot + 1}.jpg"
    return fal.download_jpeg(result_url, destination)


def resolve_reference_photo(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    record: dict[str, Any],
) -> str:
    """Find reference photo URL from current record or fallback to any table record."""
    fields = record.get("fields", {})
    for k in (REFERENCE_FIELD, "Moodboard Reference", "Reference Photo", "Template"):
        att = fields.get(k) or []
        if att and isinstance(att, list) and att[0].get("url"):
            return str(att[0]["url"])

    try:
        all_recs = _list_records(session, token, base_id, table_id)
        for r in all_recs:
            rf = r.get("fields", {})
            for k in (REFERENCE_FIELD, "Moodboard Reference", "Reference Photo", "Template"):
                att = rf.get(k) or []
                if att and isinstance(att, list) and att[0].get("url"):
                    return str(att[0]["url"])
    except Exception:
        pass
    return ""


def run_phase_4_convert(
    record: dict[str, Any],
    blended_images: dict[int, LocalImage],
    *,
    fal: FalClient,
    assets: AssetCatalog,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir: Path,
    execute: bool = True,
    skip_existing: bool = True,
) -> dict[int, LocalImage] | None:
    """Convert blended images against the moodboard reference template."""
    record_id = record["id"]
    fields = record.get("fields", {})

    existing_converted = fields.get(CONVERTED_FIELD) or []
    if skip_existing and isinstance(existing_converted, list) and len(existing_converted) >= len(blended_images) and len(existing_converted) > 0:
        print(f"\n  [PHASE 4] Record {record_id}: Found {len(existing_converted)} existing '{CONVERTED_FIELD}' image(s) in Airtable.")
        if not execute:
            return {s: LocalImage(workdir / f"converted_mb{s + 1}.jpg", f"converted_mb{s + 1}.jpg", "image/jpeg") for s in range(len(existing_converted))}
        cached = images_from_field(existing_converted, session, workdir, "converted_mb")
        if cached and len(cached) >= len(blended_images):
            print(f"    [OK] Reusing {len(cached)} existing converted image(s) from Airtable (Skipped Fal AI Conversion).")
            return cached

    ref_url = resolve_reference_photo(session, token, base_id, table_id, record)
    if not ref_url:
        print(f"  [SKIP] Record {record_id}: Missing '{REFERENCE_FIELD}' attachment in record or table.")
        return None

    prompt = resolve_moodboard_prompt(fields, assets)
    print(f"\n  [PHASE 4] Record {record_id}: Converting {len(blended_images)} blended image(s) against template...")

    if not execute:
        for slot in sorted(blended_images):
            print(f"    [DRY] blended_mb{slot + 1}.jpg + Reference -> converted_mb{slot + 1}.jpg")
        return {s: LocalImage(workdir / f"converted_mb{s + 1}.jpg", f"converted_mb{s + 1}.jpg", "image/jpeg") for s in blended_images}

    blended_urls: dict[int, str] = {}
    fresh_blended = fields.get(BLENDED_FIELD) or []
    for idx, att in enumerate(fresh_blended):
        if idx < len(blended_images) and att.get("url"):
            slot_key = sorted(blended_images)[idx]
            blended_urls[slot_key] = str(att["url"])

    for slot, img in blended_images.items():
        if not blended_urls.get(slot):
            try:
                blended_urls[slot] = fal.upload_file(img.path)
            except Exception:
                blended_urls[slot] = ""

    results: dict[int, LocalImage] = {}
    with ThreadPoolExecutor(max_workers=SLOT_COUNT) as pool:
        futures = {}
        for slot, img in blended_images.items():
            b_url = blended_urls.get(slot) or ""
            if not b_url:
                continue
            futures[pool.submit(convert_slot, slot, b_url, ref_url, prompt, fal, workdir)] = slot

        for future in as_completed(futures):
            slot = futures[future]
            try:
                img = future.result()
                results[slot] = img
                print(f"    [OK] Converted slot {slot + 1} -> {img.filename}")
            except Exception as err:
                print(f"    [ERROR] Convert slot {slot + 1} failed: {err}")

    if not results:
        print(f"  [ERROR] Record {record_id}: Phase 4 conversion produced no images.")
        return None

    try:
        _clear_attachment_field(session, token, base_id, table_id, record_id, CONVERTED_FIELD)
    except Exception:
        pass

    for slot in sorted(results):
        _upload_attachment(session, token, base_id, record_id, CONVERTED_FIELD, results[slot])
        print(f"    [OK] Uploaded {results[slot].filename} -> '{CONVERTED_FIELD}'")

    return results


# ---------------------------------------------------------------------------
# Row-level Unique Material Words (Claude Sonnet 5) — injected into blend prompts
# ---------------------------------------------------------------------------

MATERIAL_FALLBACK_POOL = [
    "BRASS", "MARBLE", "BOUCLE", "VELVET", "OAK", "LINEN",
    "TRAVERTINE", "CERAMIC", "CHROME", "STONE", "GLASS", "PLASTER",
]


def generate_unique_material_words(
    fal: FalClient,
    furniture_urls: list[str],
    item_names: list[str],
    *,
    model: str = CLAUDE_VISION_MODEL,
) -> dict[int, dict[str, str]]:
    """One Claude Vision call per row: 3 single uppercase material words per slot.

    Words are guaranteed globally unique across the row so the same material
    (e.g. BRASS) never repeats in two slots."""
    instruction = (
        "You are an expert luxury interior designer. You will receive one furniture product image per slot "
        f"({len(furniture_urls)} images total: {', '.join(item_names)}).\n"
        "For EACH image, identify the 3 primary materials/textures/finishes visible on that product.\n"
        "STRICT REQUIREMENTS:\n"
        "- Every word MUST be a SINGLE UPPERCASE word (e.g. BRASS, GLASS, VELVET, MARBLE, OAK, LINEN, BOUCLE, CHROME, TRAVERTINE, LEATHER, WOOD, CERAMIC, METAL, STONE, FABRIC, PLASTER).\n"
        "- All words across ALL images must be GLOBALLY UNIQUE: no word may repeat anywhere in your output.\n"
        '- Return ONLY a valid JSON object with no extra text or markdown formatting: '
        '{"slots": [{"top": "WORD", "middle": "WORD", "bottom": "WORD"}, ...]} '
        "with exactly one object per image, in the same order as the images."
    )

    raw_slots: list[Any] = []
    try:
        raw = fal.generate_vision_prompt(furniture_urls, instruction, model=model)
        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = re.sub(r"```(?:json)?", "", cleaned).strip()
        raw_slots = list(json.loads(cleaned).get("slots") or [])
    except Exception as err:
        print(f"    [WARN] Row material word generation failed: {err}. Using unique fallback words.")

    results: dict[int, dict[str, str]] = {}
    seen: set[str] = set()
    pool_index = 0
    for slot in range(len(furniture_urls)):
        entry = raw_slots[slot] if slot < len(raw_slots) and isinstance(raw_slots[slot], dict) else {}
        words: dict[str, str] = {}
        for key in ("top", "middle", "bottom"):
            raw_word = str(entry.get(key) or "").strip().upper()
            word = raw_word.split()[0] if raw_word else ""
            if not word or word in seen:
                while pool_index < len(MATERIAL_FALLBACK_POOL) and MATERIAL_FALLBACK_POOL[pool_index] in seen:
                    pool_index += 1
                word = (
                    MATERIAL_FALLBACK_POOL[pool_index]
                    if pool_index < len(MATERIAL_FALLBACK_POOL)
                    else f"MATERIAL{len(seen) + 1}"
                )
                pool_index += 1
            seen.add(word)
            words[key] = word
        results[slot] = words
    return results


# ---------------------------------------------------------------------------
# Phase 5: Reel Video Assembly & Upload (FFmpeg)
# ---------------------------------------------------------------------------

def _fit_cover(source_path: Path, width: int, height: int):
    from PIL import Image
    with Image.open(source_path) as source:
        image = source.convert("RGB")
        scale = max(width / image.width, height / image.height)
        resized = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.LANCZOS,
        )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def build_collage(converted: dict[int, LocalImage], workdir: Path) -> LocalImage | None:
    from PIL import Image
    slots = sorted(converted)
    if len(slots) != COLLAGE_CELLS:
        return None

    cell_w = VIDEO_WIDTH // COLLAGE_COLS
    cell_h = VIDEO_HEIGHT // COLLAGE_ROWS
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))

    for index, slot in enumerate(slots):
        cell = _fit_cover(converted[slot].path, cell_w, cell_h)
        col, row = index % COLLAGE_COLS, index // COLLAGE_COLS
        canvas.paste(cell, (col * cell_w, row * cell_h))

    destination = workdir / COLLAGE_FILENAME
    canvas.save(destination, format="JPEG", quality=95, optimize=True)
    return LocalImage(destination, COLLAGE_FILENAME, "image/jpeg")


def build_reel_mp4(
    sequence: list[LocalImage],
    workdir: Path,
    outro: LocalImage | None = None,
    music: LocalImage | None = None,
) -> LocalImage:
    import imageio_ffmpeg

    frames = sequence + ([outro] if outro else [])
    paths: list[Path] = []
    for index, image in enumerate(frames, start=1):
        dest = workdir / f"slide_{index:02d}.jpg"
        _fit_cover(image.path, VIDEO_WIDTH, VIDEO_HEIGHT).save(dest, format="JPEG", quality=95, optimize=True)
        paths.append(dest)

    slideshow_seconds = len(sequence) * SLIDE_SECONDS
    slides = [(path, SLIDE_SECONDS) for path in paths[: len(sequence)]]
    if outro:
        slides.append((paths[-1], OUTRO_SECONDS))
    total_seconds = slideshow_seconds + (OUTRO_SECONDS if outro else 0)

    concat_path = workdir / "reel_concat.txt"
    lines = []
    for path, seconds in slides:
        lines.append(f"file '{path.name}'")
        lines.append(f"duration {seconds}")
    lines.append(f"file '{slides[-1][0].name}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    destination = workdir / REEL_FILENAME
    video_filter = f"fps={VIDEO_FPS},format=yuv420p"
    if outro:
        fade_out_at = slideshow_seconds - FADE_SECONDS
        fade_in_at = slideshow_seconds
        fade_in_end = slideshow_seconds + FADE_SECONDS
        video_filter += (
            f",fade=t=out:st={fade_out_at}:d={FADE_SECONDS}"
            f":enable=between(t\\,{fade_out_at}\\,{fade_in_at})"
            f",fade=t=in:st={fade_in_at}:d={FADE_SECONDS}"
            f":enable=between(t\\,{fade_in_at}\\,{fade_in_end})"
        )

    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_path.name,
    ]
    if music:
        command += ["-stream_loop", "-1", "-i", music.path.name]

    command += ["-vf", video_filter]
    if music:
        fade_start = slideshow_seconds if outro else total_seconds - FADE_SECONDS
        fade_length = OUTRO_SECONDS if outro else FADE_SECONDS
        command += [
            "-af", f"afade=t=out:st={fade_start}:d={fade_length}",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
            "-map", "0:v:0",
            "-map", "1:a:0",
        ]

    command += [
        "-t", str(total_seconds),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        destination.name,
    ]
    result = subprocess.run(command, cwd=workdir, capture_output=True, text=True)
    if result.returncode != 0 or not destination.is_file():
        raise AutomationError(f"FFmpeg failed: {result.stderr.strip() or result.returncode}")

    return LocalImage(destination, REEL_FILENAME, "video/mp4")


FAL_ELEVENLABS_MUSIC_MODEL = "fal-ai/elevenlabs/music"
DEFAULT_ELEVENLABS_MUSIC_PROMPT = (
    "Modern luxury fashion lounge house music, 120 BPM, rhythmic upbeat kick drum, "
    "crisp percussion on the beat, warm deep synth chords, elegant sophisticated mood, "
    "seamless 4/4 loop timing, clean professional studio mix"
)
MUSIC_DURATION = 20  # seconds (covers 16s slideshow + 3s outro + 1s fade)


def generate_jazz_prompt_via_claude(
    fal: FalClient,
    image_url: str = "",
    *,
    vision_model: str = CLAUDE_VISION_MODEL,
) -> str:
    """Prompt Claude Sonnet 5 to generate a random upbeat luxury jazz prompt."""
    instruction = (
        "You are an expert music curator and AI prompt engineer for high-end luxury interior design reels. "
        "Create a vivid, atmospheric, single-paragraph text-to-audio music prompt for a modern upbeat jazz track. "
        "Requirements: (1) Warm acoustic jazz instruments like Rhodes electric piano, walking upright bass, gentle saxophone/muted trumpet, and crisp brushed drum kit. "
        "(2) Must have a steady rhythmic beat in 4/4 time at 120 BPM for seamless video editing. "
        "(3) Sophisticated, elegant, aesthetic atmosphere. "
        "Return ONLY the prompt string with no quotes or preamble."
    )
    image_urls = [image_url] if image_url else []
    try:
        raw = fal.generate_vision_prompt(
            image_urls=image_urls,
            prompt=instruction,
            model=vision_model,
        )
        cleaned = raw.strip().strip('"').strip("'")
        if cleaned:
            if "120 BPM" not in cleaned and "120 bpm" not in cleaned:
                cleaned += ", 120 BPM, steady 4/4 rhythm"
            return cleaned
    except Exception as err:
        print(f"    [WARN] Claude jazz prompt generation failed: {err}")

    return DEFAULT_ELEVENLABS_MUSIC_PROMPT


def run_phase_music(
    record: dict[str, Any],
    category_code: str,
    *,
    fal: FalClient,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir: Path,
    music_prompt: str = "",
    force: bool = False,
    execute: bool = True,
) -> LocalImage | None:
    """Generate 20s 120 BPM luxury background music via Fal AI ElevenLabs Music."""
    record_id = record["id"]
    fields = record.get("fields", {})

    music_att = fields.get(MUSIC_FIELD) or []
    if music_att and not force:
        music_url = str(music_att[0].get("url") or "")
        if music_url:
            print(f"  [PHASE 4.5] Record {record_id}: Using existing '{MUSIC_FIELD}' audio...")
            if not execute:
                return LocalImage(workdir / "music.mp3", "music.mp3", "audio/mpeg")
            try:
                return _download_attachment_url(session, music_url, workdir / "music.mp3")
            except Exception as err:
                print(f"    [WARN] Could not download existing music: {err}")

    prompt = (music_prompt or "").strip() or DEFAULT_ELEVENLABS_MUSIC_PROMPT

    if not execute:
        print(f"\n  [PHASE 4.5] Record {record_id}: [DRY RUN] Fal AI ElevenLabs Music ({MUSIC_DURATION}s) -> '{MUSIC_FIELD}'")
        print(f"    [PROMPT] {prompt}")
        return LocalImage(workdir / "music.mp3", "music.mp3", "audio/mpeg")

    try:
        print(f"\n  [PHASE 4.5] Record {record_id}: Generating {MUSIC_DURATION}s luxury music via Fal AI ElevenLabs ({FAL_ELEVENLABS_MUSIC_MODEL})...")
        print(f"    [PROMPT] {prompt}")
        audio_url = fal.generate_elevenlabs_music(
            prompt=prompt,
            duration=MUSIC_DURATION,
            model=FAL_ELEVENLABS_MUSIC_MODEL,
        )
        if not audio_url:
            raise AutomationError("Fal AI ElevenLabs music returned empty audio URL")

        music_dest = workdir / "music.mp3"
        resp = request_with_retry(session, "GET", audio_url)
        if not resp.ok:
            raise response_error(resp, f"Download audio from {audio_url}")
        music_dest.write_bytes(resp.content)
        local_music = LocalImage(music_dest, "music.mp3", "audio/mpeg")

        _upload_attachment(session, token, base_id, record_id, MUSIC_FIELD, local_music)
        print(f"    [OK] Generated and uploaded ElevenLabs music -> '{MUSIC_FIELD}'")
        return local_music
    except Exception as err:
        print(f"    [ERROR] ElevenLabs music generation failed: {err}")
        return None


def run_phase_outro(
    record: dict[str, Any],
    workspace: Path,
    *,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir: Path,
    execute: bool = True,
) -> LocalImage | None:
    """Ensure Outro image is present on the record, using workspace Outro as template."""
    record_id = record["id"]
    fields = record.get("fields", {})

    outro_att = fields.get(OUTRO_FIELD) or []
    if outro_att:
        outro_url = str(outro_att[0].get("url") or "")
        if outro_url:
            if not execute:
                return LocalImage(workdir / "outro.jpg", "outro.jpg", "image/jpeg")
            try:
                return _download_attachment_url(session, outro_url, workdir / "outro.jpg")
            except Exception:
                pass

    workspace_outro = workspace / "Outro for All Reels" / "Outro.jpg"
    if workspace_outro.is_file():
        local_outro_path = workdir / "outro.jpg"
        import shutil
        local_outro_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace_outro, local_outro_path)
        local_outro = LocalImage(local_outro_path, "outro.jpg", "image/jpeg")
        print(f"  [OUTRO] Using workspace Outro image: {workspace_outro}")
        if execute:
            try:
                _upload_attachment(session, token, base_id, record_id, OUTRO_FIELD, local_outro)
                print(f"    [OK] Uploaded workspace outro -> '{OUTRO_FIELD}'")
            except Exception as err:
                print(f"    [WARN] Could not upload outro to Airtable: {err}")
        return local_outro

    return None


def run_phase_5_reel(
    record: dict[str, Any],
    blended: dict[int, LocalImage],
    converted: dict[int, LocalImage],
    *,
    music: LocalImage | None,
    outro: LocalImage | None,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir: Path,
    execute: bool = True,
) -> bool:
    """Build MP4 vertical on-beat reel and upload to REEL - Moodboard Reel field."""
    record_id = record["id"]

    audio_desc = "with 120 BPM audio" if music else "silent (no audio)"
    if not execute:
        seq_count = (1 if len(converted) == COLLAGE_CELLS else 0) + len(set(blended) & set(converted)) * 2
        print(f"\n  [PHASE 5] Record {record_id}: Assembling MP4 Slideshow ({seq_count} slides + Outro, {audio_desc})...")
        print(f"    [DRY] FFmpeg -> {REEL_FILENAME} (1080x1920 @ 30fps, {audio_desc}) -> '{REEL_FIELD}' (Status: '{STATUS_COMPLETE}')")
        return True

    collage = build_collage(converted, workdir) if len(converted) == COLLAGE_CELLS else None
    sequence = [collage] if collage else []
    tagged_map = getattr(blended, "tagged_map", {}) or {}
    for slot in sorted(set(blended) & set(converted)):
        sequence.append(converted[slot])
        slide_blend = tagged_map.get(slot) or blended[slot]
        sequence.append(slide_blend)

    if not sequence:
        print(f"  [ERROR] Record {record_id}: No valid image sequence for reel.")
        return False

    print(f"\n  [PHASE 5] Record {record_id}: Assembling MP4 Slideshow ({len(sequence)} slides + Outro, {audio_desc})...")

    reel = build_reel_mp4(sequence, workdir, outro=outro, music=music)
    size_mb = reel.path.stat().st_size / (1024 * 1024)
    print(f"    [OK] Built {audio_desc} {reel.filename} ({size_mb:.2f} MB)")

    try:
        _clear_attachment_field(session, token, base_id, table_id, record_id, REEL_FIELD)
    except Exception:
        pass

    _upload_attachment(session, token, base_id, record_id, REEL_FIELD, reel)

    _update_record_fields(session, token, base_id, table_id, record_id, {STATUS_FIELD: STATUS_COMPLETE})
    print(f"    [OK] Uploaded {reel.filename} -> '{REEL_FIELD}', Status -> '{STATUS_COMPLETE}'")
    return True


# ---------------------------------------------------------------------------
# Complete End-to-End Single Record Processor
# ---------------------------------------------------------------------------

def process_one_record_end_to_end(
    record: dict[str, Any],
    category_code: str,
    *,
    fal: FalClient,
    krea: KreaClient,
    assets: AssetCatalog,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir_root: Path,
    vision_model: str,
    moodboard_id: str = "",
    interior_prompt: str = "",
    music_prompt: str = "",
    force_music: bool = False,
    enable_music: bool = False,
    execute: bool = True,
    skip_existing: bool = True,
) -> bool:
    """Run Phase 2 -> 2.5 -> 3 -> 4 -> 5 on a single record completely."""
    record_id = record["id"]
    workdir = workdir_root / record_id
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 64}")
    print(f"[ROW PIPELINE] Processing Record {record_id} End-to-End")
    print(f"{'=' * 64}")

    # 1. Phase 2: Krea Interior
    run_phase_2_interior(
        record, category_code, krea=krea, session=session,
        token=token, base_id=base_id, table_id=table_id,
        workdir=workdir, moodboard_id=moodboard_id,
        interior_prompt=interior_prompt,
        force=not skip_existing, execute=execute,
    )

    # Refresh record fields
    if execute:
        try:
            record = _get_record(session, token, base_id, table_id, record_id)
        except Exception:
            pass

    # 2. Phase 2.5: Vision Prompt
    run_phase_2_5_vision(
        record, category_code, fal=fal, session=session,
        token=token, base_id=base_id, table_id=table_id,
        vision_model=vision_model, execute=execute,
    )

    if execute:
        try:
            record = _get_record(session, token, base_id, table_id, record_id)
        except Exception:
            pass

    # 3. Phase 3: Blending
    blended_map = run_phase_3_blend(
        record, fal=fal, session=session, token=token,
        base_id=base_id, table_id=table_id, workdir=workdir,
        execute=execute, skip_existing=skip_existing,
    )
    if not blended_map:
        print(f"  [WARN] Record {record_id}: Blending did not produce images.")
        return False

    if execute:
        try:
            record = _get_record(session, token, base_id, table_id, record_id)
        except Exception:
            pass

    # 4. Phase 4: Conversion
    converted_map = run_phase_4_convert(
        record, blended_map, fal=fal, assets=assets,
        session=session, token=token, base_id=base_id,
        table_id=table_id, workdir=workdir, execute=execute,
        skip_existing=skip_existing,
    )
    if not converted_map:
        print(f"  [WARN] Record {record_id}: Conversion did not produce images.")
        return False

    if execute:
        try:
            record = _get_record(session, token, base_id, table_id, record_id)
        except Exception:
            pass

    # 4.5. Music Generation (Fal AI ElevenLabs Music @ 120 BPM, 20s) & Outro
    if enable_music:
        music_img = run_phase_music(
            record, category_code, fal=fal, session=session,
            token=token, base_id=base_id, table_id=table_id,
            workdir=workdir, music_prompt=music_prompt, force=force_music, execute=execute,
        )
    else:
        music_img = None
        print(f"  [PHASE 4.5] Record {record_id}: Music generation disabled by default (silent video). Pass --enable-music to enable.")

    outro_img = run_phase_outro(
        record, assets.workspace, session=session,
        token=token, base_id=base_id, table_id=table_id,
        workdir=workdir, execute=execute,
    )

    # 5. Phase 5: On-Beat Reel MP4 Assembly
    ok = run_phase_5_reel(
        record, blended_map, converted_map, music=music_img, outro=outro_img,
        session=session, token=token, base_id=base_id, table_id=table_id,
        workdir=workdir, execute=execute,
    )

    if ok:
        print(f"\n[DONE] Record {record_id} successfully completed entire pipeline!")
    return ok


# ---------------------------------------------------------------------------
# CLI & Main Orchestration
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="5-Phase Moodboard Reel Pipeline")
    parser.add_argument(
        "--category",
        "-c",
        choices=MOODBOARD_REEL_CATEGORIES,
        default=DEFAULT_TABLE_CODE,
        help=f"Moodboard reel table category (default: {DEFAULT_TABLE_CODE})",
    )
    parser.add_argument(
        "--phase",
        "-p",
        choices=["all", "1", "2", "2.5", "3", "4", "4.5", "5", "scrape", "interior", "vision", "blend", "convert", "music", "audio", "reel"],
        default="all",
        help="Specific phase to execute, or 'all' for row-by-row full pipeline (default: all)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Live execution (makes API calls & writes to Airtable)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of rows to process end-to-end (default: 1)",
    )
    parser.add_argument(
        "--record-id",
        action="append",
        default=[],
        help="Target specific record ID",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip phases/records that already have output generated (default: true)",
    )
    parser.add_argument(
        "--force",
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="Force re-generation of all phases even if output fields are populated",
    )
    parser.add_argument(
        "--moodboard-id",
        default="",
        help=f"Krea AI moodboard ID override (default: {DEFAULT_MOODBOARD_ID})",
    )
    parser.add_argument(
        "--interior-prompt",
        default="",
        help="Custom prompt for Krea room interior generation (default: 'Generate me a modern living room' for chandeliers)",
    )
    parser.add_argument(
        "--music-prompt",
        default="",
        help="Custom prompt for Fal AI ElevenLabs music (default: luxury lounge house music)",
    )
    parser.add_argument(
        "--force-music",
        action="store_true",
        help="Force re-generation of background music even if 'Music Generated' is already populated",
    )
    enable_music_env = os.getenv("MOODBOARD_REEL_ENABLE_MUSIC", "false").strip().lower() in ("true", "1", "yes")
    parser.add_argument(
        "--enable-music",
        action="store_true",
        default=enable_music_env,
        help="Enable background music generation via Fal AI ElevenLabs and mix audio into reel (default: False)",
    )
    parser.add_argument(
        "--vision-model",
        default=CLAUDE_VISION_MODEL,
        help=f"Claude Vision model on Fal AI OpenRouter (default: {CLAUDE_VISION_MODEL})",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    settings.require({"airtable"})

    table = TABLES[args.category]
    base_id = settings.airtable_base_id
    table_id = table.table_id
    token = settings.airtable_token

    mode = "EXECUTE (LIVE)" if args.execute else "DRY RUN"
    print("=" * 64)
    print(f"[{mode}] 5-Phase Moodboard Reel Pipeline | {table.label}")
    print(f"  Table ID: {table_id}")
    print(f"  Phase Target: {args.phase.upper()} | Limit: {args.limit} row(s)")
    print(f"  Vision Model: {args.vision_model}")
    print("=" * 64)

    session = requests.Session()
    fal = FalClient(api_key=settings.fal_key, session=session)
    krea = KreaClient(token=settings.krea_token, base_url=settings.krea_base_url, session=session)
    assets = AssetCatalog(settings.workspace)

    if args.execute:
        for f in (BLENDED_FIELD, CONVERTED_FIELD, REEL_FIELD, MUSIC_FIELD, TARGET_BLENDED_FIELD):
            _ensure_field(session, token, base_id, table_id, f, "multipleAttachments")
        for tf in TEXTURE_FIELDS:
            _ensure_field(session, token, base_id, table_id, tf, "multilineText")
        for slot in range(SLOT_COUNT):
            _ensure_field(session, token, base_id, table_id, f"Prompt{slot + 1}", "multilineText")
            _ensure_field(session, token, base_id, table_id, f"Interior{slot + 1}" if slot > 0 else "Interior", "multipleAttachments")

    phase_target = args.phase.lower()
    workdir_root = settings.output_dir / "moodboard_reel" / args.category
    workdir_root.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Case A: User selected a specific individual phase (e.g. --phase 2.5)
    # -----------------------------------------------------------------------
    if phase_target not in ("all",):
        if phase_target in ("1", "scrape"):
            run_phase_1_scrape_one_row(args.category, execute=args.execute)
            return 0

        records = _list_records(session, token, base_id, table_id)
        if args.record_id:
            req_set = set(args.record_id)
            records = [r for r in records if r["id"] in req_set]
        if args.limit:
            records = records[: args.limit]

        for record in records:
            record_id = record["id"]
            workdir = workdir_root / record_id
            workdir.mkdir(parents=True, exist_ok=True)

            if phase_target in ("2", "interior"):
                run_phase_2_interior(
                    record, args.category, krea=krea, session=session,
                    token=token, base_id=base_id, table_id=table_id,
                    workdir=workdir, moodboard_id=args.moodboard_id,
                    interior_prompt=args.interior_prompt,
                    force=not args.skip_existing, execute=args.execute,
                )
            elif phase_target in ("2.5", "vision"):
                run_phase_2_5_vision(record, args.category, fal=fal, session=session, token=token, base_id=base_id, table_id=table_id, vision_model=args.vision_model, execute=args.execute)
            elif phase_target in ("3", "blend"):
                run_phase_3_blend(record, fal=fal, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute, skip_existing=args.skip_existing)
            elif phase_target in ("4", "convert"):
                blended_map = images_from_field(record.get("fields", {}).get(BLENDED_FIELD) or [], session, workdir, "blended_mb") if args.execute else {}
                if not blended_map:
                    blended_map = {s: LocalImage(workdir / f"blended_mb{s + 1}.jpg", f"blended_mb{s + 1}.jpg", "image/jpeg") for s in range(SLOT_COUNT) if (workdir / f"blended_mb{s + 1}.jpg").is_file()}
                run_phase_4_convert(record, blended_map, fal=fal, assets=assets, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute, skip_existing=args.skip_existing)
            elif phase_target in ("4.5", "music", "audio"):
                run_phase_music(
                    record, args.category, fal=fal, session=session,
                    token=token, base_id=base_id, table_id=table_id,
                    workdir=workdir, music_prompt=args.music_prompt,
                    force=args.force_music, execute=args.execute,
                )
            elif phase_target in ("5", "reel"):
                blended_map = images_from_field(record.get("fields", {}).get(BLENDED_FIELD) or [], session, workdir, "blended_mb") if args.execute else {}
                if not blended_map:
                    blended_map = {s: LocalImage(workdir / f"blended_mb{s + 1}.jpg", f"blended_mb{s + 1}.jpg", "image/jpeg") for s in range(SLOT_COUNT) if (workdir / f"blended_mb{s + 1}.jpg").is_file()}
                converted_map = images_from_field(record.get("fields", {}).get(CONVERTED_FIELD) or [], session, workdir, "converted_mb") if args.execute else {}
                if not converted_map:
                    converted_map = {s: LocalImage(workdir / f"converted_mb{s + 1}.jpg", f"converted_mb{s + 1}.jpg", "image/jpeg") for s in range(SLOT_COUNT) if (workdir / f"converted_mb{s + 1}.jpg").is_file()}
                if args.enable_music:
                    music_img = run_phase_music(
                        record, args.category, fal=fal, session=session,
                        token=token, base_id=base_id, table_id=table_id,
                        workdir=workdir, music_prompt=args.music_prompt,
                        force=args.force_music, execute=args.execute,
                    )
                else:
                    music_img = None
                    print(f"  [PHASE 4.5] Record {record_id}: Music generation disabled for reel (silent video). Pass --enable-music to enable.")
                outro_img = run_phase_outro(record, assets.workspace, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute)
                run_phase_5_reel(record, blended_map, converted_map, music=music_img, outro=outro_img, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute)
        return 0

    # -----------------------------------------------------------------------
    # Case B: Full Row-by-Row Streaming Pipeline (--phase all)
    # -----------------------------------------------------------------------
    max_rows = args.limit or 1
    rows_completed = 0

    # If developer explicitly passed --record-id, process only those specified records
    if args.record_id:
        req_set = set(args.record_id)
        existing_records = _list_records(session, token, base_id, table_id)
        target_records = [r for r in existing_records if r["id"] in req_set]
        print(f"[INFO] Targeted {len(target_records)} specific record(s) via --record-id...")
        for record in target_records:
            if rows_completed >= max_rows:
                break
            ok = process_one_record_end_to_end(
                record, args.category, fal=fal, krea=krea,
                assets=assets, session=session, token=token,
                base_id=base_id, table_id=table_id,
                workdir_root=workdir_root, vision_model=args.vision_model,
                moodboard_id=args.moodboard_id,
                interior_prompt=args.interior_prompt,
                music_prompt=args.music_prompt,
                force_music=args.force_music,
                enable_music=args.enable_music,
                execute=args.execute,
                skip_existing=args.skip_existing,
            )
            if ok or not args.execute:
                rows_completed += 1
        return 0

    # Default Execution: ALWAYS scrape 4 fresh active Shopify products into a brand-new row and process end-to-end
    while rows_completed < max_rows:
        print(f"\n[INFO] Starting Row {rows_completed + 1}/{max_rows}: Scraping 4 fresh active products into brand-new Airtable row...")
        new_record_id = run_phase_1_scrape_one_row(
            args.category,
            execute=args.execute,
        )
        if not new_record_id and args.execute:
            print("[INFO] No new items available to scrape from Akeneo/Shopify.")
            break

        if not args.execute:
            print(f"  [DRY RUN] Finished row {rows_completed + 1}/{max_rows} simulation.")
            rows_completed += 1
            continue

        # Fetch the exact newly created record by its ID
        new_record = _get_record(session, token, base_id, table_id, new_record_id)
        ok = process_one_record_end_to_end(
            new_record, args.category, fal=fal, krea=krea,
            assets=assets, session=session, token=token,
            base_id=base_id, table_id=table_id,
            workdir_root=workdir_root, vision_model=args.vision_model,
            moodboard_id=args.moodboard_id,
            interior_prompt=args.interior_prompt,
            music_prompt=args.music_prompt,
            force_music=args.force_music,
            enable_music=args.enable_music,
            execute=args.execute,
            skip_existing=args.skip_existing,
        )
        if ok:
            rows_completed += 1
        else:
            print(f"[WARN] Row {rows_completed + 1} pipeline encountered an issue.")
            break

    print("\n" + "=" * 64)
    print(f"[SUMMARY] Total Rows Completed: {rows_completed}/{max_rows}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
