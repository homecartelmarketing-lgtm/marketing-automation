"""End-to-End Moodboard Reel Automation Pipeline (5-Phase Architecture).

Row-by-Row Execution Flow:
  1. Phase 1 (Auto Scrape): Scrapes 1 row (4 products) from Akeneo (Newest to Oldest, Modern style) -> Airtable (Status: 'Standby')
  2. Phase 2 (Interior Generation): Generates 4 room interiors via Krea AI (9:16, moodboard b5ffdcbb-192e-4528-8d86-d1a4cf496887) -> (Status: 'Already attached a room Interior')
  3. Phase 2.5 (Vision Prompting): Generates 4 detailed prompts via Claude Sonnet 5 on Fal AI OpenRouter -> (Status: 'Processing')
  4. Phase 3 (Image Blending): Blends 4 pairs via Fal AI nano-banana-pro/edit -> Moodboard Blended
  5. Phase 4 (Moodboard Conversion): Re-blends against template via Fal AI nano-banana-pro/edit -> Converted Moodboard
  6. Phase 5 (Reel Assembly): FFmpeg 2x2 Collage + 8 Slide Sequence + Outro + Audio Mix -> REEL - Moodboard Reel -> (Status: 'Complete')

Usage::
    python run_moodboard_reel.py --dry-run
    python run_moodboard_reel.py --category chandelier_modern
    python run_moodboard_reel.py --category pendant_lights_reel --limit 1
    python generate_moodboard_reel_pipeline.py --phase 2.5 --execute
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
from content_automation.assets import MAX_PROMPT_LENGTH, AssetCatalog
from content_automation.config import (
    MOODBOARD_REEL_CATEGORIES,
    TABLES,
    load_settings,
)
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.fields import (
    furniture_field,
    interior_field,
    item_name_field,
    sku_field,
)
from content_automation.http import request_with_retry, response_error
from content_automation.krea_client import KreaClient
from content_automation.models import LocalImage
from content_automation.scraping import (
    ScrapeAirtableClient,
    ScrapeRunner,
    load_scrape_settings,
)

DEFAULT_TABLE_CODE = "chandelier_modern"
DEFAULT_MOODBOARD_ID = "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
SLOT_COUNT = 4

# Exact status options matching Airtable single select field:
STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_ATTACHED_INTERIOR = "Already attached a room Interior"
STATUS_PROCESSING = "Processing"
STATUS_COMPLETE = "Complete"

BLENDED_FIELD = "Moodboard Blended"
CONVERTED_FIELD = "Converted Moodboard"
REFERENCE_FIELD = "Moodboard Reference Photo"
MOODBOARD_PROMPT_FIELD = "Moodboard Prompt"
REEL_FIELD = "REEL - Moodboard Reel"
MUSIC_FIELD = "Music Generated"
OUTRO_FIELD = "Outro"

COLLAGE_FILENAME = "collage_mb.jpg"
REEL_FILENAME = "moodboard_reel.mp4"
COLLAGE_COLS, COLLAGE_ROWS = 2, 2
COLLAGE_CELLS = COLLAGE_COLS * COLLAGE_ROWS

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
) -> None:
    url = f"{API_BASE}/{base_id}/{table_id}/{record_id}"
    resp = request_with_retry(
        session,
        "PATCH",
        url,
        headers=_airtable_headers(token),
        json={"fields": patch_fields},
    )
    if not resp.ok:
        raise response_error(resp, f"Update record {record_id}")


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

def krea_interior_prompt(category_code: str) -> str:
    cat = category_code.lower()
    if any(k in cat for k in ("chandelier", "pendant", "cluster", "linear")):
        focus = (
            "clean empty high ceiling with ample vertical headroom, "
            "NO pre-existing chandeliers, NO pendant lights, NO ceiling light fixtures, "
            "ready for lighting fixture hanging"
        )
    elif "floor" in cat:
        focus = (
            "clean empty open floor space in corner or beside seating, "
            "NO pre-existing floor lamps, NO standing lamps, ready for floor lamp placement"
        )
    elif "table" in cat:
        focus = (
            "clean empty side table, nightstand or credenza surface, "
            "NO pre-existing table lamps, ready for table lamp styling"
        )
    elif "wall" in cat or "sconce" in cat:
        focus = (
            "clean accent wall with open vertical wall space, "
            "NO pre-existing wall sconces, NO wall lamps, ready for wall sconce installation"
        )
    else:
        focus = "balanced empty space ready for product integration, NO competing fixtures"

    return (
        f"Modern luxury room interior, curvilinear contemporary furniture, warm neutral palette, "
        f"tactile boucle textures, organic minimalist architectural design, soft ambient natural daylight, "
        f"sculptural decor, clean uncluttered background, {focus}, photorealistic 8k"
    )


def claude_vision_instruction(category_code: str, item_name: str = "") -> str:
    cat = category_code.lower()
    item_desc = item_name.strip() or "lighting fixture"
    if any(k in cat for k in ("chandelier", "pendant", "cluster", "linear")):
        action = f"mount this {item_desc} from the ceiling"
    elif "floor" in cat:
        action = f"place this {item_desc} naturally standing on the floor"
    elif "table" in cat:
        action = f"place this {item_desc} on top of a table or credenza surface"
    elif "wall" in cat or "sconce" in cat:
        action = f"mount this {item_desc} naturally on the wall"
    else:
        action = f"seamlessly integrate this {item_desc} into the interior"

    return (
        f"You are an expert interior design AI prompt engineer. Analyze the provided Room Interior image and Furniture Item image.\n"
        f"Generate a detailed, concise image-to-image blending prompt that will {action} in this room interior.\n"
        f"Describe: (1) realistic position, scale, and angle, (2) realistic warm illumination and light casting onto surrounding surfaces, "
        f"(3) soft contact shadows, and (4) perfect architectural integration preserving the product's original shape, material, and color.\n"
        f"Output ONLY the prompt text, with no preamble or markdown quotes."
    )


# ---------------------------------------------------------------------------
# Phase 1: Auto Scrape (1 Row = 4 Items)
# ---------------------------------------------------------------------------

def run_phase_1_scrape_one_row(
    category_code: str,
    *,
    style_code: str = "modern",
    execute: bool = True,
) -> bool:
    """Scrape 1 row (4 items) from Akeneo into Airtable with Status: 'Standby'."""
    print("\n" + "=" * 64)
    print(f"[PHASE 1] Auto Scrape (1 Row / 4 Items: Akeneo PIM -> Airtable)")
    print(f"  Category: {category_code} | Style: {style_code} | Items: 4")
    print("=" * 64)

    if not execute:
        print("  [DRY RUN] Would scrape newest 4 modern products from Akeneo into 1 new Airtable row (Status: 'Standby').")
        return True

    settings = load_scrape_settings(
        category_code=category_code,
        style_code=style_code,
    )
    runner = ScrapeRunner(
        AkeneoClient(
            settings.akeneo_host,
            settings.akeneo_client_id,
            settings.akeneo_secret,
            settings.akeneo_username,
            settings.akeneo_password,
            channel_name=settings.channel_name,
        ),
        ScrapeAirtableClient(
            settings.airtable_token,
            settings.airtable_base_id,
            settings.airtable_table_id,
        ),
        category_code=settings.category_code,
        style_code=settings.style_code,
        items_per_row=4,
        max_items=4,
    )
    return runner.run()


# ---------------------------------------------------------------------------
# Phase 2: Krea Room Interior Generation
# ---------------------------------------------------------------------------

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
    execute: bool = True,
) -> int:
    """Generate room interiors for empty slots using Krea AI."""
    record_id = record["id"]
    fields = record.get("fields", {})
    prompt = krea_interior_prompt(category_code)

    generated_count = 0
    for slot in range(SLOT_COUNT):
        fur_attachments = get_attachment_field(fields, "Furniture Item", slot)
        if not fur_attachments:
            continue
        int_attachments = get_attachment_field(fields, "Interior", slot)
        if int_attachments:
            continue  # Already has interior

        target_field = "Interior" if slot == 0 else f"Interior{slot + 1}"
        print(f"  [PHASE 2] Record {record_id} Slot {slot + 1}: Generating Krea interior for '{target_field}'...")

        if not execute:
            print(f"    [DRY] Prompt: {prompt[:70]}...")
            generated_count += 1
            continue

        try:
            image_url = krea.generate(
                prompt,
                aspect_ratio="9:16",
                resolution="1K",
                moodboard_id=DEFAULT_MOODBOARD_ID,
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
    """Generate detailed blending prompts using Claude Vision on Fal AI OpenRouter."""
    record_id = record["id"]
    fields = record.get("fields", {})

    prompt_count = 0
    updates: dict[str, Any] = {}

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
        instruction = claude_vision_instruction(category_code, item_name)
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
            print(f"    [OK] Saved {len(updates) - 1} prompt field(s) to Airtable ({', '.join(k for k in updates if k != STATUS_FIELD)}), Status -> '{STATUS_PROCESSING}'")
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
            return {s: LocalImage(workdir / f"blended_mb{s + 1}.jpg", f"blended_mb{s + 1}.jpg", "image/jpeg") for s in range(len(existing_blended))}
        cached = images_from_field(existing_blended, session, workdir, "blended_mb")
        if cached and len(cached) >= SLOT_COUNT:
            print(f"    [OK] Reusing {len(cached)} existing blended image(s) from Airtable (Skipped Fal AI Blending).")
            return cached

    pairs = extract_slot_pairs(fields)

    if not pairs:
        print(f"  [SKIP] Record {record_id}: No complete Interior + Furniture + Prompt pairs to blend.")
        return None

    print(f"\n  [PHASE 3] Record {record_id}: Blending {len(pairs)} slot pair(s) via Fal AI Nano Banana Pro...")
    if not execute:
        for p in pairs:
            print(f"    [DRY] Slot {p.slot + 1}: Interior + Furniture + Prompt -> {p.output_filename}")
        return {p.slot: LocalImage(workdir / p.output_filename, p.output_filename, "image/jpeg") for p in pairs}

    results: dict[int, LocalImage] = {}
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

    for slot in sorted(results):
        _upload_attachment(session, token, base_id, record_id, BLENDED_FIELD, results[slot])
        print(f"    [OK] Uploaded {results[slot].filename} -> '{BLENDED_FIELD}'")

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


FAL_STABLE_AUDIO_MODEL = "fal-ai/stable-audio-3/small/music/base/text-to-audio"
MUSIC_PROMPT_120BPM = (
    "Modern luxury fashion lounge house music, 120 BPM, rhythmic upbeat kick drum, "
    "crisp percussion on the beat, warm deep synth chords, elegant sophisticated mood, "
    "seamless 4/4 loop timing, clean professional studio mix"
)


def generate_jazz_prompt_via_claude(
    fal: FalClient,
    image_url: str = "",
    *,
    vision_model: str = CLAUDE_VISION_MODEL,
) -> str:
    """Prompt Claude Sonnet 5 to generate a random upbeat luxury jazz prompt for Stable Audio 3."""
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

    return MUSIC_PROMPT_120BPM


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
    vision_model: str = CLAUDE_VISION_MODEL,
    execute: bool = True,
) -> LocalImage | None:
    """Generate Claude-prompted 120 BPM on-beat jazz music via Fal AI Stable Audio 3."""
    record_id = record["id"]
    fields = record.get("fields", {})

    music_att = fields.get(MUSIC_FIELD) or []
    if music_att:
        music_url = str(music_att[0].get("url") or "")
        if music_url:
            print(f"  [PHASE 4.5] Record {record_id}: Using existing '{MUSIC_FIELD}' audio...")
            if not execute:
                return LocalImage(workdir / "music.mp3", "music.mp3", "audio/mpeg")
            try:
                return _download_attachment_url(session, music_url, workdir / "music.mp3")
            except Exception as err:
                print(f"    [WARN] Could not download existing music: {err}")

    print(f"\n  [PHASE 4.5] Record {record_id}: Asking {vision_model} to craft random upbeat jazz prompt...")

    # Pick visual reference from blended or interior if available
    ref_image_url = ""
    for field_key in (BLENDED_FIELD, CONVERTED_FIELD, "Interior"):
        att = fields.get(field_key) or []
        if att and isinstance(att, list) and att[0].get("url"):
            ref_image_url = str(att[0]["url"])
            break

    if not execute:
        print(f"    [DRY] Prompt Claude Sonnet 5 for jazz prompt -> Fal AI Stable Audio 3 (21s) -> '{MUSIC_FIELD}'")
        return LocalImage(workdir / "music.mp3", "music.mp3", "audio/mpeg")

    jazz_prompt = generate_jazz_prompt_via_claude(fal, ref_image_url, vision_model=vision_model)
    print(f"    [OK] Claude Jazz Prompt ({len(jazz_prompt)} chars): {jazz_prompt[:75]}...")

    try:
        print(f"    [INFO] Generating 21s on-beat audio via Fal AI Stable Audio 3...")
        audio_url = fal.generate_stable_audio_music(
            jazz_prompt,
            duration=21.0,
            model=FAL_STABLE_AUDIO_MODEL,
        )
        music_dest = workdir / "music.mp3"
        resp = request_with_retry(session, "GET", audio_url)
        if not resp.ok:
            raise response_error(resp, f"Download audio from {audio_url}")
        music_dest.write_bytes(resp.content)
        local_music = LocalImage(music_dest, "music.mp3", "audio/mpeg")

        _upload_attachment(session, token, base_id, record_id, MUSIC_FIELD, local_music)
        print(f"    [OK] Generated and uploaded Claude-prompted jazz music -> '{MUSIC_FIELD}'")
        return local_music
    except Exception as err:
        print(f"    [ERROR] Music generation failed: {err}")
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

    collage = build_collage(converted, workdir) if len(converted) == COLLAGE_CELLS else None
    sequence = [collage] if collage else []
    for slot in sorted(set(blended) & set(converted)):
        sequence.append(converted[slot])
        sequence.append(blended[slot])

    if not sequence:
        print(f"  [ERROR] Record {record_id}: No valid image sequence for reel.")
        return False

    print(f"\n  [PHASE 5] Record {record_id}: Assembling On-Beat MP4 Slideshow (120 BPM, {len(sequence)} slides + Outro)...")
    if not execute:
        print(f"    [DRY] FFmpeg -> {REEL_FILENAME} (1080x1920 @ 30fps) with on-beat audio -> '{REEL_FIELD}' (Status: '{STATUS_COMPLETE}')")
        return True

    reel = build_reel_mp4(sequence, workdir, outro=outro, music=music)
    size_mb = reel.path.stat().st_size / (1024 * 1024)
    print(f"    [OK] Built on-beat {reel.filename} ({size_mb:.2f} MB)")

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
        workdir=workdir, execute=execute,
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

    # 4.5. Music Generation (Claude-prompted Fal AI Stable Audio 3 @ 120 BPM) & Outro
    music_img = run_phase_music(
        record, category_code, fal=fal, session=session,
        token=token, base_id=base_id, table_id=table_id,
        workdir=workdir, vision_model=vision_model, execute=execute,
    )
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
        choices=["all", "1", "2", "2.5", "3", "4", "5", "scrape", "interior", "vision", "blend", "convert", "reel"],
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
        for f in (BLENDED_FIELD, CONVERTED_FIELD, REEL_FIELD):
            _ensure_field(session, token, base_id, table_id, f, "multipleAttachments")
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
                run_phase_2_interior(record, args.category, krea=krea, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute)
            elif phase_target in ("2.5", "vision"):
                run_phase_2_5_vision(record, args.category, fal=fal, session=session, token=token, base_id=base_id, table_id=table_id, vision_model=args.vision_model, execute=args.execute)
            elif phase_target in ("3", "blend"):
                run_phase_3_blend(record, fal=fal, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute, skip_existing=args.skip_existing)
            elif phase_target in ("4", "convert"):
                blended_map = images_from_field(record.get("fields", {}).get(BLENDED_FIELD) or [], session, workdir, "blended_mb") if args.execute else {}
                if not blended_map:
                    blended_map = {s: LocalImage(workdir / f"blended_mb{s + 1}.jpg", f"blended_mb{s + 1}.jpg", "image/jpeg") for s in range(SLOT_COUNT) if (workdir / f"blended_mb{s + 1}.jpg").is_file()}
                run_phase_4_convert(record, blended_map, fal=fal, assets=assets, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute, skip_existing=args.skip_existing)
            elif phase_target in ("5", "reel"):
                blended_map = images_from_field(record.get("fields", {}).get(BLENDED_FIELD) or [], session, workdir, "blended_mb") if args.execute else {}
                if not blended_map:
                    blended_map = {s: LocalImage(workdir / f"blended_mb{s + 1}.jpg", f"blended_mb{s + 1}.jpg", "image/jpeg") for s in range(SLOT_COUNT) if (workdir / f"blended_mb{s + 1}.jpg").is_file()}
                converted_map = images_from_field(record.get("fields", {}).get(CONVERTED_FIELD) or [], session, workdir, "converted_mb") if args.execute else {}
                if not converted_map:
                    converted_map = {s: LocalImage(workdir / f"converted_mb{s + 1}.jpg", f"converted_mb{s + 1}.jpg", "image/jpeg") for s in range(SLOT_COUNT) if (workdir / f"converted_mb{s + 1}.jpg").is_file()}
                music_img = run_phase_music(record, args.category, fal=fal, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, vision_model=args.vision_model, execute=args.execute)
                outro_img = run_phase_outro(record, assets.workspace, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute)
                run_phase_5_reel(record, blended_map, converted_map, music=music_img, outro=outro_img, session=session, token=token, base_id=base_id, table_id=table_id, workdir=workdir, execute=args.execute)
        return 0

    # -----------------------------------------------------------------------
    # Case B: Full Row-by-Row Streaming Pipeline (--phase all)
    # -----------------------------------------------------------------------
    max_rows = args.limit or 1
    rows_completed = 0

    # 1. First, check if there are existing uncompleted rows in Airtable
    existing_records = _list_records(session, token, base_id, table_id)
    if args.record_id:
        req_set = set(args.record_id)
        incomplete_records = [r for r in existing_records if r["id"] in req_set]
    else:
        # Rows that are not yet Complete OR don't have REEL video
        incomplete_records = [
            r for r in existing_records
            if not r.get("fields", {}).get(REEL_FIELD)
            or str(r.get("fields", {}).get(STATUS_FIELD) or "") != STATUS_COMPLETE
        ]

    if incomplete_records:
        print(f"[INFO] Found {len(incomplete_records)} existing incomplete row(s) in Airtable. Finishing them first...")
        for record in incomplete_records:
            if rows_completed >= max_rows:
                break
            ok = process_one_record_end_to_end(
                record, args.category, fal=fal, krea=krea,
                assets=assets, session=session, token=token,
                base_id=base_id, table_id=table_id,
                workdir_root=workdir_root, vision_model=args.vision_model,
                execute=args.execute,
                skip_existing=args.skip_existing,
            )
            if ok or not args.execute:
                rows_completed += 1

    # 2. If we still need to process more rows, scrape 1 row from Akeneo and process it end-to-end
    while rows_completed < max_rows:
        print(f"\n[INFO] Starting Row {rows_completed + 1}/{max_rows}: Scraping 1 row (4 items) from Akeneo...")
        scraped_ok = run_phase_1_scrape_one_row(args.category, execute=args.execute)
        if not scraped_ok and args.execute:
            print("[INFO] No new items available to scrape from Akeneo.")
            break

        if not args.execute:
            print(f"  [DRY RUN] Finished row {rows_completed + 1}/{max_rows} simulation.")
            rows_completed += 1
            continue

        # Fetch the newly created record with Status: 'Standby'
        fresh_records = _list_records(session, token, base_id, table_id)
        standby_records = [
            r for r in fresh_records
            if str(r.get("fields", {}).get(STATUS_FIELD) or "") == STATUS_STANDBY
        ]

        if not standby_records:
            print("[INFO] No newly created Standby records found to process.")
            break

        new_record = standby_records[0]
        ok = process_one_record_end_to_end(
            new_record, args.category, fal=fal, krea=krea,
            assets=assets, session=session, token=token,
            base_id=base_id, table_id=table_id,
            workdir_root=workdir_root, vision_model=args.vision_model,
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
