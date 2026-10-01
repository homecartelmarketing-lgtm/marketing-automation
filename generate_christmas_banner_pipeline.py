#!/usr/bin/env python3
"""Christmas Banner Automation Pipeline (21:9 ultra-wide).

Blends ONE fresh Akeneo fixture of every type (chandelier, pendant light, floor lamp,
table lamp, wall light) into a single Krea-generated modern Christmas living room and
outputs a 21:9 Nano Banana Pro banner, then stamps a Claude-written title + subtitle on it
(local Pillow, Poppins only, white text with a soft shadow).

Phases
------
    Phase 1  Akeneo scrape: 1 fresh active fixture per type (5 total) + strict Shopify catalog
             check + base-wide dedup -> ONE brand-new Airtable row (Status: "In progress").
             The 5 cutouts are attached to "Furniture Item" (order: CH, PE, FL, TL, WL).
    Phase 2  Krea interior (2.35:1, the widest ratio krea-2 accepts; moodboard b5ffdcbb-...,
             modern Christmas living room) -> "Room Interior". Retries at 16:9 on a non-moodboard error.
    Phase 3  Claude Sonnet 5 vision over [interior + 5 cutouts] -> "Blending Prompt".
    Phase 4  Fal Nano Banana Pro blend, 21:9 -> "Blended Banner" (text-free)
    Phase 5  Claude Sonnet 5 vision over the blended banner -> "Banner Title" + "Banner Subtitle".
    Phase 6  Local Pillow overlay: white title Poppins Medium 81.8 pt and subtitle Poppins
             Regular 46.3 pt (Canva points = 4/3 px), tight tracking, soft shadow, on the 1800x600
             design-canvas boxes -> "Banner with Text"
             -> Status: "Done" + "Date and Time Generated".

Usage:
    python generate_christmas_banner_pipeline.py
    python generate_christmas_banner_pipeline.py --record-id recXXXXXXXXXXXXXX   # re-run phases 2-6
    python generate_christmas_banner_pipeline.py --record-id recXXXXXXXXXXXXXX --from-phase 3   # Claude prompt + blend + text
    python generate_christmas_banner_pipeline.py --record-id recXXXXXXXXXXXXXX --text-only   # phases 5-6 only
    python generate_christmas_banner_pipeline.py --record-id recXXXXXXXXXXXXXX --only-phase 4   # banner blend ONLY
    python generate_christmas_banner_pipeline.py --moodboard-id <id> --interior-prompt "<prompt>"
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import requests
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.airtable_client import current_pht_timestamp
from content_automation.banner_common import (
    NOTES_MAX_CHARS,
    PipelineClients,
    attachment_code,
    clean_blend_prompt,
    clean_item_notes,
    coded_map,
    krea_generate_room,
    nano_banana_blend,
    parse_coded_lines,
    phases_to_run,
    pick_fixture,
    product_notes,
    request_blend_prompt,
    stale_output_note,
    validate_blend_prompt,
)
from content_automation.errors import AutomationError, ProviderError  # noqa: F401  (ProviderError: re-exported for tests)
from content_automation.media import download_url_to_temp_file
from content_automation.overlay import BANNER_SHADOW_INTENSITY, overlay_banner_title_subtitle
from content_automation.prompts import build_banner_copy_instruction, build_banner_multi_fixture_instruction
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
from content_automation.shopify_client import ShopifyClient

# --------------------------------------------------------------------------
# Constants & Defaults
# --------------------------------------------------------------------------

TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_CHRISTMAS_BANNER"
DEFAULT_TABLE_ID = "tblgNk1Tp6qKUcduw"
ASPECT_RATIO = "21:9"  # final banner (Nano Banana Pro)
KREA_ASPECT_RATIO = "2.35:1"  # krea-2 does not accept 21:9; 2.35:1 is its widest documented ratio
KREA_FALLBACK_ASPECT_RATIO = "16:9"
OUTPUT_DIR = REPO_ROOT / "output" / "christmas_banner"

DEFAULT_MOODBOARD_ID = "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
DEFAULT_INTERIOR_PROMPT = (
    "Generate me a photo of a modern luxury living room with a Christmas vibe: a decorated Christmas tree, "
    "warm festive styling with garlands and soft fairy lights, a sofa and armchair seating area, a side table "
    "and console, high ceilings, clean architecture, warm cozy evening light, wide cinematic panoramic composition, "
    "with empty ceiling, wall and floor spaces for lighting fixtures"
)

# Order matters: it is the attachment order and the Image 2..6 order given to Claude / Nano Banana.
FIXTURES: list[dict[str, str]] = [
    {"code": "CH", "category": "chandeliers", "label": "Chandelier"},
    {"code": "PE", "category": "pendant_lights", "label": "Pendant Light"},
    {"code": "FL", "category": "floor_lamps", "label": "Floor Lamp"},
    {"code": "TL", "category": "table_lamps", "label": "Table Lamp"},
    {"code": "WL", "category": "wall_lights", "label": "Wall Light"},
]
FIXTURE_ORDER = {fx["code"]: idx for idx, fx in enumerate(FIXTURES)}

# Airtable field names
FIELD_FK_ID = "Foreign Key ID"
FIELD_ID = "ID"
FIELD_DATE_GENERATED = "Date and Time Generated"
FIELD_STATUS = "Status"
FIELD_FURNITURE = "Furniture Item"
FIELD_SKU = "SKU"
FIELD_ITEM_NAME = "Item Name"
FIELD_ITEM_DETAILS = "Item Details"
FIELD_CATEGORY = "Category"
FIELD_INTERIOR = "Room Interior"
FIELD_INTERIOR_PROMPT = "Interior Prompt"
FIELD_BLEND_PROMPT = "Blending Prompt"
FIELD_BANNER = "Blended Banner"
FIELD_TITLE = "Banner Title"
FIELD_SUBTITLE = "Banner Subtitle"
FIELD_BANNER_TEXT = "Banner with Text"

REQUIRED_FIELDS = {
    FIELD_SKU: "multilineText",
    FIELD_ITEM_NAME: "multilineText",
    FIELD_ITEM_DETAILS: "multilineText",
    FIELD_CATEGORY: "singleLineText",
    FIELD_FURNITURE: "multipleAttachments",
    FIELD_INTERIOR: "multipleAttachments",
    FIELD_INTERIOR_PROMPT: "multilineText",
    FIELD_BLEND_PROMPT: "multilineText",
    FIELD_BANNER: "multipleAttachments",
    # Standard columns. "ID" is deliberately absent: it is an autoNumber on this table, which
    # Airtable computes and refuses writes to. create_record() patches Foreign Key ID from it.
    FIELD_FK_ID: "singleLineText",
    FIELD_DATE_GENERATED: "dateTime",
    FIELD_STATUS: "singleSelect",
    FIELD_TITLE: "multilineText",
    FIELD_SUBTITLE: "multilineText",
    FIELD_BANNER_TEXT: "multipleAttachments",
}

STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"
STATUS_FOR_MANUAL = "For Manual"


# Generic helpers live in content_automation/banner_common.py (shared with the Sale banner);
# the underscore names below keep this module's historical API.
_parse_coded_lines = parse_coded_lines
_attachment_code = attachment_code
_coded_map = coded_map
_product_notes = product_notes
_pick_fixture = pick_fixture
_clean_blend_prompt = clean_blend_prompt


def resolve_table_id(table_id: str | None) -> str:
    return (table_id or os.getenv(TABLE_ENV_KEY) or DEFAULT_TABLE_ID).strip()


def _banner_fixtures_from_record(fields: dict[str, Any]) -> list[dict[str, str]]:
    """Ordered fixture dicts (code/label/name/notes/url) built from the row's cutout attachments."""
    names_by_code = _coded_map(fields.get(FIELD_ITEM_NAME))
    notes_by_code = _coded_map(fields.get(FIELD_ITEM_DETAILS))
    labels = {fx["code"]: fx["label"] for fx in FIXTURES}

    items: list[dict[str, str]] = []
    for att in fields.get(FIELD_FURNITURE) or []:
        code = _attachment_code(att)
        if code in FIXTURE_ORDER and att.get("url"):
            items.append({
                "code": code,
                "label": labels[code],
                "name": names_by_code.get(code, labels[code]),
                "notes": notes_by_code.get(code, ""),
                "url": att["url"],
            })
    items.sort(key=lambda it: FIXTURE_ORDER[it["code"]])
    return items


# --------------------------------------------------------------------------
# PHASE 1: Akeneo scrape (1 fresh item per fixture type) into ONE brand-new row
# --------------------------------------------------------------------------

def run_phase_1_scrape(clients: PipelineClients, style: str = "modern") -> str:
    print("\n[PHASE 1] Scraping one fresh item per fixture type (5 total)...")

    base_filenames: set[str] = set()
    base_names: set[str] = set()
    base_skus: set[str] = set()
    try:
        base_filenames, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
        print(f"  [OK] Base-wide dedup: {len(base_skus)} SKU(s), {len(base_names)} title(s) registered.")
    except Exception as e:
        print(f"  [WARN] Base-wide dedup notice: {e}")

    try:
        for r in clients.airtable.list_records([FIELD_SKU, FIELD_ITEM_NAME]):
            f = r.get("fields", {})
            # SKU / Item Name hold one 'CODE: value' line per fixture in this table.
            base_skus.update(_parse_coded_lines(f.get(FIELD_SKU)))
            base_names.update(_parse_coded_lines(f.get(FIELD_ITEM_NAME)))
    except Exception:
        pass

    shopify_index = None
    try:
        print("  [INFO] Verifying live published catalog from Shopify (homecartel.net)...")
        shopify_index = ShopifyClient().load_published_identities()
        print(f"  [OK] Shopify Index loaded: {len(shopify_index.skus)} active published SKU(s).")
    except Exception as e:
        print(f"  [WARN] Shopify index skipped: {e}")

    picked: list[dict[str, Any]] = []
    for fx in FIXTURES:
        chosen = _pick_fixture(clients, fx, style, base_skus, base_names, shopify_index)
        if chosen is None:
            raise AutomationError(
                f"No new eligible {fx['label']} found in Akeneo category '{fx['category']}'. "
                "The banner needs all 5 fixture types; nothing was written to Airtable."
            )
        picked.append(chosen)
        base_skus.add(chosen["sku"].lower())
        base_names.add(chosen["clean_name"].lower())

    clients.airtable.ensure_fields(REQUIRED_FIELDS)

    # No ID / Foreign Key ID here: ID is an autoNumber and create_record() fills Foreign Key ID from it.
    record_id = clients.airtable.create_record({
        FIELD_STATUS: STATUS_IN_PROGRESS,
        FIELD_CATEGORY: "Christmas Banner",
        FIELD_SKU: "\n".join(f"{p['code']}: {p['sku']}" for p in picked),
        FIELD_ITEM_NAME: "\n".join(f"{p['code']}: {p['clean_name']}" for p in picked),
        FIELD_ITEM_DETAILS: "\n".join(f"{p['code']}: {p['notes']}" for p in picked if p.get("notes")),
    })
    for p in picked:  # sequential upload keeps the CH, PE, FL, TL, WL order
        clients.airtable.upload_attachment(
            record_id, FIELD_FURNITURE, p["cutout"], f"{p['code']}_{p['sku']}_{p['media_code']}.png"
        )
    print(f"  [OK] Created brand-new row {record_id} with {len(picked)} cutouts.")
    return record_id


# --------------------------------------------------------------------------
# PHASE 2: Krea modern Christmas living room (2.35:1, extended to 21:9 in Phase 4)
# --------------------------------------------------------------------------

def run_phase_2_interior(
    clients: PipelineClients,
    record_id: str,
    custom_moodboard: str = "",
    custom_prompt: str = "",
) -> str:
    moodboard_id = (
        custom_moodboard
        or os.getenv("KREA_MOODBOARD_ID_CHRISTMAS_BANNER", "")
        or DEFAULT_MOODBOARD_ID
    ).strip()
    prompt = (custom_prompt or os.getenv("CHRISTMAS_BANNER_PROMPT", "") or DEFAULT_INTERIOR_PROMPT).strip()

    print(f"\n[PHASE 2] Generating Krea Christmas living room ({KREA_ASPECT_RATIO}) for record {record_id}...")
    print(f"  Prompt: \"{prompt}\"")
    print(f"  Moodboard ID: {moodboard_id}")

    krea_url = krea_generate_room(
        clients,
        prompt=prompt,
        moodboard_id=moodboard_id,
        aspect_ratio=KREA_ASPECT_RATIO,
        fallback_aspect_ratio=KREA_FALLBACK_ASPECT_RATIO,
    )
    print(f"  [OK] Krea generated interior: {krea_url[:70]}...")

    downloaded = clients.krea.download_image(krea_url)
    clients.airtable.upload_attachment(record_id, FIELD_INTERIOR, downloaded, f"krea_interior_{record_id}.jpg")
    clients.airtable.update_record(record_id, {
        FIELD_INTERIOR_PROMPT: prompt,
        FIELD_STATUS: "Interior Generated",
    })
    return krea_url


# --------------------------------------------------------------------------
# PHASE 3: Claude vision -> multi-fixture blending prompt
# --------------------------------------------------------------------------

def _fallback_blend_prompt(fixtures: list[dict[str, str]]) -> str:
    listing = "; ".join(f"Image {i} is the {fx['label']} '{fx['name']}'" for i, fx in enumerate(fixtures, start=2))
    return (
        f"Install all {len(fixtures)} lighting fixtures into the Christmas living room in Image 1. {listing}. "
        "Hang the chandelier and pendant light from the ceiling in separate spots, stand the floor lamp beside the sofa, "
        "place the table lamp on a side table, and mount the wall light on a wall. All fixtures are turned on with a warm "
        "2700K glow. Keep the room and Christmas styling unchanged, no text. Compose as a 21:9 ultra-wide banner, "
        "extending the room to the left and right if needed."
    )


def run_phase_3_claude(clients: PipelineClients, record_id: str) -> str:
    print(f"\n[PHASE 3] Claude Sonnet 5 vision analysis for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})

    interior_atts = fields.get(FIELD_INTERIOR) or []
    fixtures = _banner_fixtures_from_record(fields)
    if not interior_atts or len(fixtures) != len(FIXTURES):
        raise AutomationError(
            f"Record {record_id} needs a Room Interior and all {len(FIXTURES)} fixture cutouts (found {len(fixtures)})."
        )

    prompt = request_blend_prompt(
        clients,
        instruction=build_banner_multi_fixture_instruction(fixtures, aspect_ratio=ASPECT_RATIO),
        image_urls=[interior_atts[0]["url"], *[fx["url"] for fx in fixtures]],
        fixture_count=len(fixtures),
        fallback=_fallback_blend_prompt(fixtures),
    )

    clients.airtable.update_record(record_id, {FIELD_BLEND_PROMPT: prompt, FIELD_STATUS: "Prompt Generated"})
    print(f"  [OK] Saved Blending Prompt to Airtable ({len(prompt)} characters).")
    return prompt


# --------------------------------------------------------------------------
# PHASE 4: Nano Banana Pro blend (21:9)
# --------------------------------------------------------------------------

def run_phase_4_blend(clients: PipelineClients, record_id: str) -> Path:
    print(f"\n[PHASE 4] Nano Banana Pro {ASPECT_RATIO} banner blend for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})

    interior_atts = fields.get(FIELD_INTERIOR) or []
    fixtures = _banner_fixtures_from_record(fields)
    blend_prompt = str(fields.get(FIELD_BLEND_PROMPT) or "").strip()
    if not interior_atts or len(fixtures) != len(FIXTURES) or not blend_prompt:
        raise AutomationError(f"Record {record_id} is missing inputs for the banner blend.")

    blended_url = nano_banana_blend(
        clients,
        prompt=blend_prompt,
        image_urls=[interior_atts[0]["url"], *[fx["url"] for fx in fixtures]],
        aspect_ratio=ASPECT_RATIO,
        resolution=os.getenv("CHRISTMAS_BANNER_RESOLUTION", "2K"),
    )
    print(f"  [OK] Nano Banana Pro banner produced: {blended_url[:70]}...")

    downloaded = download_url_to_temp_file(
        requests.Session(),
        blended_url,
        prefix="christmas_banner_",
        suffix=".jpg",
        context=f"Download Nano Banana Pro banner from {blended_url}",
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / f"christmas_banner_{record_id}.jpg"
    local_path.write_bytes(Path(downloaded.path).read_bytes())

    clients.airtable.clear_attachment_field(record_id, FIELD_BANNER)
    clients.airtable.upload_attachment(record_id, FIELD_BANNER, downloaded, f"christmas_banner_{record_id}.jpg")
    clients.airtable.update_record(record_id, {FIELD_STATUS: "Blended Image Generated"})
    print(f"  [OK] Blended banner (no text) saved to '{FIELD_BANNER}' and {local_path}")
    return local_path


# --------------------------------------------------------------------------
# PHASE 5: Claude title + subtitle for the banner
# --------------------------------------------------------------------------

FALLBACK_TITLE = "Light Up Your Christmas"
FALLBACK_SUBTITLE = "Statement lighting for festive homes"
TITLE_MAX_CHARS = 22
SUBTITLE_MAX_CHARS = 36


def _clean_copy_text(value: Any, max_chars: int, fallback: str) -> str:
    """Strip labels/quotes/markdown; fall back when empty or far too long for its box."""
    text = re.sub(r"^\s*(title|subtitle)\s*:\s*", "", str(value or ""), flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" \"'`*_#").rstrip(".").strip()
    if not text or len(text) > max_chars + 8:
        return fallback
    return text


def parse_banner_copy(response: str) -> tuple[str, str]:
    """Parse Claude's reply into (title, subtitle): JSON first, then per-key regex, then defaults."""
    raw = re.sub(r"^```(?:json)?", "", str(response or "").strip(), flags=re.MULTILINE)
    raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()
    title: Any = ""
    subtitle: Any = ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            title, subtitle = data.get("title", ""), data.get("subtitle", "")
    except Exception:
        m_title = re.search(r'"title"\s*:\s*"([^"]+)"', raw)
        m_sub = re.search(r'"subtitle"\s*:\s*"([^"]+)"', raw)
        title = m_title.group(1) if m_title else ""
        subtitle = m_sub.group(1) if m_sub else ""
    return (
        _clean_copy_text(title, TITLE_MAX_CHARS, FALLBACK_TITLE),
        _clean_copy_text(subtitle, SUBTITLE_MAX_CHARS, FALLBACK_SUBTITLE),
    )


def run_phase_5_copy(clients: PipelineClients, record_id: str) -> tuple[str, str]:
    print(f"\n[PHASE 5] Claude Sonnet 5 banner title + subtitle for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})
    banner_atts = fields.get(FIELD_BANNER) or []
    if not banner_atts or not banner_atts[0].get("url"):
        raise AutomationError(f"Record {record_id} has no '{FIELD_BANNER}' image to write copy for.")

    names = [
        re.sub(r"^[A-Z]{2}:\s*", "", line.strip())
        for line in str(fields.get(FIELD_ITEM_NAME) or "").splitlines()
        if line.strip()
    ]
    title, subtitle = FALLBACK_TITLE, FALLBACK_SUBTITLE
    try:
        response = clients.fal.generate_claude_vision(
            prompt=build_banner_copy_instruction(names, title_max_chars=TITLE_MAX_CHARS, subtitle_max_chars=SUBTITLE_MAX_CHARS),
            image_urls=[banner_atts[0]["url"]],
            system_instruction="You are a luxury lighting copywriter for HomeCartel.",
            model=os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5",
        )
        title, subtitle = parse_banner_copy(response)
    except Exception as err:
        print(f"  [WARN] Claude copy failed ({err}); using the default title/subtitle.")

    clients.airtable.update_record(record_id, {
        FIELD_TITLE: title,
        FIELD_SUBTITLE: subtitle,
        FIELD_STATUS: "Copy Generated",
    })
    print(f"  [OK] Title: \"{title}\" | Subtitle: \"{subtitle}\"")
    return title, subtitle


# --------------------------------------------------------------------------
# PHASE 6: Local Pillow overlay (white Poppins, soft shadow)
# --------------------------------------------------------------------------

def run_phase_6_overlay(clients: PipelineClients, record_id: str) -> Path:
    print(f"\n[PHASE 6] Stamping title + subtitle on the banner for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})
    banner_atts = fields.get(FIELD_BANNER) or []
    title = str(fields.get(FIELD_TITLE) or "").strip()
    subtitle = str(fields.get(FIELD_SUBTITLE) or "").strip()
    if not banner_atts or not banner_atts[0].get("url"):
        raise AutomationError(f"Record {record_id} has no '{FIELD_BANNER}' image to stamp.")
    if not title:
        raise AutomationError(f"Record {record_id} has no '{FIELD_TITLE}'; run phase 5 first.")

    banner_url = banner_atts[0]["url"]
    downloaded = download_url_to_temp_file(
        requests.Session(),
        banner_url,
        prefix="christmas_banner_base_",
        suffix=".jpg",
        context=f"Download blended banner from {banner_url}",
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / f"christmas_banner_text_{record_id}.jpg"
    overlay_banner_title_subtitle(
        downloaded.path,
        title,
        subtitle,
        local_path,
        shadow_intensity=BANNER_SHADOW_INTENSITY,
    )

    clients.airtable.clear_attachment_field(record_id, FIELD_BANNER_TEXT)
    clients.airtable.upload_attachment(record_id, FIELD_BANNER_TEXT, local_path, local_path.name)
    clients.airtable.update_record(record_id, {
        FIELD_STATUS: STATUS_DONE,
        FIELD_DATE_GENERATED: current_pht_timestamp(),
    })
    print(f"  [SUCCESS] Record {record_id} Done. Saved {local_path}")
    return local_path


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

STALE_NOTES = {
    2: "The blending prompt, blend, title and overlay are now out of date; run --from-phase 3 to refresh them.",
    3: "The blend and overlay are now out of date; run --from-phase 4 to refresh them.",
    4: "'Banner with Text' still shows the previous blend; run --only-phase 6 to re-stamp it.",
    5: "'Banner with Text' still uses the previous title/subtitle; run --only-phase 6 to re-stamp it.",
}


def run_pipeline(
    table_id: str | None = None,
    record_id: str | None = None,
    moodboard_id: str = "",
    interior_prompt: str = "",
    style: str = "modern",
    text_only: bool = False,
    from_phase: int = 2,
    only_phase: int | None = None,
) -> Path | None:
    phases = phases_to_run(from_phase, text_only, only_phase, has_record=bool(record_id))
    resolved_table_id = resolve_table_id(table_id)

    print("=" * 70)
    print("HOMECARTEL MARKETING AI -- CHRISTMAS BANNER PIPELINE (21:9)")
    print("=" * 70)
    print(f"Table ID: {resolved_table_id}")
    print(f"Fixtures: {', '.join(fx['label'] for fx in FIXTURES)}")
    print(f"Phases:   {', '.join(str(p) for p in phases)}")
    print("=" * 70)

    clients = PipelineClients(table_id=resolved_table_id)
    rec_id = record_id or run_phase_1_scrape(clients, style=style)
    if record_id:
        print(f"[TARGET] Re-processing explicitly targeted record: {record_id}")
        clients.airtable.ensure_fields(REQUIRED_FIELDS)

    steps = {
        2: lambda: run_phase_2_interior(clients, rec_id, custom_moodboard=moodboard_id, custom_prompt=interior_prompt),
        3: lambda: run_phase_3_claude(clients, rec_id),
        4: lambda: run_phase_4_blend(clients, rec_id),
        5: lambda: run_phase_5_copy(clients, rec_id),
        6: lambda: run_phase_6_overlay(clients, rec_id),
    }
    banner_path: Path | None = None
    try:
        for phase in phases:
            result = steps[phase]()
            if isinstance(result, Path):
                banner_path = result
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed on record {rec_id}: {e}")
        try:
            clients.airtable.update_record(rec_id, {FIELD_STATUS: STATUS_FOR_MANUAL})
        except Exception:
            pass
        raise

    print(f"\n>>> COMPLETED RECORD {rec_id} SUCCESSFULLY! <<<")
    if banner_path:
        print(f"Banner: {banner_path}")
    note = stale_output_note(only_phase, STALE_NOTES)
    if note:
        print(f"[NOTE] {note}")
    return banner_path


def main() -> int:
    parser = argparse.ArgumentParser(description="HomeCartel Christmas Banner Pipeline (21:9)")
    parser.add_argument("--table-id", default="", help=f"Airtable Table ID override (default: ${TABLE_ENV_KEY})")
    parser.add_argument("--record-id", default=None, help="Explicit record ID to re-process (skips scrape)")
    parser.add_argument("--moodboard-id", default="", help="Custom Krea moodboard ID")
    parser.add_argument("--interior-prompt", default="", help="Custom Krea interior prompt override")
    parser.add_argument("--style", default="modern", help="Akeneo Style2 filter ('all' disables it)")
    parser.add_argument("--text-only", action="store_true", help="Alias for --from-phase 5 (title/subtitle + overlay only)")
    parser.add_argument(
        "--from-phase", type=int, choices=[2, 3, 4, 5, 6], default=2,
        help="Re-run from this phase on --record-id, re-using the earlier images "
             "(2 Krea, 3 Claude prompt, 4 blend, 5 title/subtitle, 6 overlay)",
    )
    parser.add_argument(
        "--only-phase", type=int, choices=[2, 3, 4, 5, 6], default=None,
        help="Run just this one phase on --record-id and stop (for example 4 = banner blend only)",
    )
    args = parser.parse_args()
    if args.text_only and args.from_phase not in (2, 5):
        parser.error("--text-only is --from-phase 5; do not combine it with another --from-phase")
    if args.only_phase is not None and (args.text_only or args.from_phase != 2):
        parser.error("--only-phase cannot be combined with --text-only or --from-phase")

    run_pipeline(
        table_id=args.table_id or None,
        record_id=args.record_id,
        moodboard_id=args.moodboard_id,
        interior_prompt=args.interior_prompt,
        style=args.style,
        text_only=args.text_only,
        from_phase=args.from_phase,
        only_phase=args.only_phase,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
