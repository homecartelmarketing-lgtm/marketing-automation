#!/usr/bin/env python3
"""Sale Banner Automation Pipeline (1800x600).

A wide sale banner: a red centre panel with the sale text (drawn locally to match the Canva
reference) between two Krea-generated modern Christmas interiors with scraped fixtures blended in:
the LEFT side is a dining room with one pendant light, the RIGHT side a kitchen with two pendant
lights over the island. The two percentages and captions come from the promotions calendar.

Phases
------
    Phase 1  Akeneo scrape: 3 pendant lights (DP dining room; KA + KB kitchen), Shopify-active, unused
             -> ONE brand-new row (Category "Sale Banner"); cutouts in "Furniture Item".
    Phase 2  Krea x2 at 4:5: modern Christmas dining room + kitchen
             -> "Dining Interior" / "Kitchen Interior".
    Phase 3  Claude Sonnet 5 vision per room over [interior + that room's items]
             -> "Dining Blending Prompt" / "Kitchen Blending Prompt".
    Phase 4  Nano Banana Pro x2 (4:5): [dining interior, pendant] and [kitchen interior, pendant, pendant]
             -> "Dining Blended" / "Kitchen Blended".
    Phase 5  Percentages and captions from the calendar (dates with the year), plus the panel colour:
             Claude Sonnet 5 looks at both blends and suggests a hex colour (white text stays readable)
             -> "Sale Percent Left/Right", "Sale Caption Left/Right", "Sale Panel Color".
    Phase 6  Local Pillow composite (interiors + coloured panel + Poppins text) -> "Sale Banner"
             -> Status: "Done" + "Date and Time Generated".

Usage:
    python generate_sale_banner_pipeline.py
    python generate_sale_banner_pipeline.py --month 11 --year 2026                      # other month's captions
    python generate_sale_banner_pipeline.py --record-id recXXXX --from-phase 3          # new prompts + blends + banner
    python generate_sale_banner_pipeline.py --record-id recXXXX --only-phase 4          # room blends only
    python generate_sale_banner_pipeline.py --record-id recXXXX --text-only             # captions + colour + composite
    python generate_sale_banner_pipeline.py --record-id recXXXX --from-phase 5 --panel-color "#0B3D2E"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
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
    PipelineClients,
    fixtures_from_record,
    krea_generate_room,
    load_scrape_context,
    nano_banana_blend,
    phases_to_run,
    pick_fixture,
    request_blend_prompt,
    stale_output_note,
)
from content_automation.errors import AutomationError
from content_automation.media import download_url_to_temp_file
from content_automation.overlay import (
    SALE_PANEL_COLOR,
    SALE_PANEL_MIN_CONTRAST,
    contrast_with_white,
    draw_sale_banner,
    ensure_white_text_contrast,
    format_hex_color,
    parse_hex_color,
)
from content_automation.promo_calendar import build_sale_captions
from content_automation.prompts import build_banner_multi_fixture_instruction, build_sale_panel_color_instruction

# --------------------------------------------------------------------------
# Constants & Defaults
# --------------------------------------------------------------------------

# The sale banner shares the Christmas banner's Airtable table; rows are told apart by Category.
TABLE_ENV_KEYS = ("AIRTABLE_TABLE_ID_SALE_BANNER", "AIRTABLE_TABLE_ID_CHRISTMAS_BANNER")
DEFAULT_TABLE_ID = "tblgNk1Tp6qKUcduw"
CATEGORY_LABEL = "Sale Banner"
ROOM_ASPECT_RATIO = "4:5"  # each side slot is 483x600 (0.805)
KREA_FALLBACK_ASPECT_RATIO = "3:4"
OUTPUT_DIR = REPO_ROOT / "output" / "sale_banner"
BLEND_MIN_CHARS = 700  # one or two fixtures need shorter prompts than the five-fixture banner
BLEND_LENGTH_HINT = "about 1,800 to 3,200 characters (never more than 4,500)"

# Short defaults on purpose: the Krea moodboard carries the look, the prompt only names the room. Override with
# SALE_BANNER_DINING_PROMPT / SALE_BANNER_KITCHEN_PROMPT or the CLI flags.
DINING_PROMPT = "Generate me a modern luxury dining room with a Christmas theme"
KITCHEN_PROMPT = "Generate me a modern luxury kitchen with a Christmas theme"

# Slot code -> Akeneo category. DP hangs over the dining table; KA and KB are two different pendant lights for the
# kitchen island. None of them is "PE" so they never collide with the Christmas banner's pendant when both banners
# share one Airtable row.
PENDANT_SLOT = {"code": "DP", "category": "pendant_lights", "label": "Pendant Light"}
KITCHEN_SLOTS = [
    {"code": "KA", "category": "pendant_lights", "label": "Pendant Light"},
    {"code": "KB", "category": "pendant_lights", "label": "Pendant Light"},
]
SLOTS = [PENDANT_SLOT, *KITCHEN_SLOTS]

# Airtable field names. Reused from the Christmas banner: the standard columns and the item columns.
FIELD_FK_ID = "Foreign Key ID"
FIELD_DATE_GENERATED = "Date and Time Generated"
FIELD_STATUS = "Status"
FIELD_CATEGORY = "Category"
FIELD_FURNITURE = "Furniture Item"
FIELD_SKU = "SKU"
FIELD_ITEM_NAME = "Item Name"
FIELD_ITEM_DETAILS = "Item Details"
# Sale-banner specific.
FIELD_DINING_INTERIOR = "Dining Interior"
FIELD_KITCHEN_INTERIOR = "Kitchen Interior"
FIELD_DINING_INTERIOR_PROMPT = "Dining Interior Prompt"
FIELD_KITCHEN_INTERIOR_PROMPT = "Kitchen Interior Prompt"
FIELD_DINING_PROMPT = "Dining Blending Prompt"
FIELD_KITCHEN_PROMPT = "Kitchen Blending Prompt"
FIELD_DINING_BLENDED = "Dining Blended"
FIELD_KITCHEN_BLENDED = "Kitchen Blended"
FIELD_PERCENT_LEFT = "Sale Percent Left"
FIELD_PERCENT_RIGHT = "Sale Percent Right"
FIELD_CAPTION_LEFT = "Sale Caption Left"
FIELD_CAPTION_RIGHT = "Sale Caption Right"
FIELD_PANEL_COLOR = "Sale Panel Color"
FIELD_SALE_BANNER = "Sale Banner"
DEFAULT_PANEL_HEX = format_hex_color(SALE_PANEL_COLOR)  # the sample's red, used when Claude gives no usable colour

REQUIRED_FIELDS = {
    FIELD_SKU: "multilineText",
    FIELD_ITEM_NAME: "multilineText",
    FIELD_ITEM_DETAILS: "multilineText",
    FIELD_CATEGORY: "singleLineText",
    FIELD_FURNITURE: "multipleAttachments",
    # Standard columns ("ID" is an autoNumber on this table and is never written).
    FIELD_FK_ID: "singleLineText",
    FIELD_DATE_GENERATED: "dateTime",
    FIELD_STATUS: "singleSelect",
    FIELD_DINING_INTERIOR: "multipleAttachments",
    FIELD_KITCHEN_INTERIOR: "multipleAttachments",
    FIELD_DINING_INTERIOR_PROMPT: "multilineText",
    FIELD_KITCHEN_INTERIOR_PROMPT: "multilineText",
    FIELD_DINING_PROMPT: "multilineText",
    FIELD_KITCHEN_PROMPT: "multilineText",
    FIELD_DINING_BLENDED: "multipleAttachments",
    FIELD_KITCHEN_BLENDED: "multipleAttachments",
    FIELD_PERCENT_LEFT: "singleLineText",
    FIELD_PERCENT_RIGHT: "singleLineText",
    FIELD_CAPTION_LEFT: "multilineText",
    FIELD_CAPTION_RIGHT: "multilineText",
    FIELD_PANEL_COLOR: "singleLineText",
    FIELD_SALE_BANNER: "multipleAttachments",
}

ROOMS: list[dict[str, Any]] = [
    {
        "key": "dining",
        "label": "Dining Room",
        "theme": "modern Christmas dining room",
        "slots": [PENDANT_SLOT],
        "interior_field": FIELD_DINING_INTERIOR,
        "krea_prompt_field": FIELD_DINING_INTERIOR_PROMPT,
        "prompt_field": FIELD_DINING_PROMPT,
        "blended_field": FIELD_DINING_BLENDED,
        "moodboard_env": "KREA_MOODBOARD_ID_SALE_BANNER_DINING",
        "moodboard_default": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
        "prompt_env": "SALE_BANNER_DINING_PROMPT",
        "prompt_default": DINING_PROMPT,
        "extra_rules": (
            "Hang the pendant light centred above the dining table so it reads as the focal point, its lowest point "
            "roughly 70 to 80 cm above the tabletop. If the ceiling is not visible in Image 1, extend the scene "
            "upward so the ceiling canopy and the cord or rod are visible."
        ),
    },
    {
        "key": "kitchen",
        "label": "Kitchen",
        "theme": "modern Christmas kitchen",
        "slots": KITCHEN_SLOTS,
        "interior_field": FIELD_KITCHEN_INTERIOR,
        "krea_prompt_field": FIELD_KITCHEN_INTERIOR_PROMPT,
        "prompt_field": FIELD_KITCHEN_PROMPT,
        "blended_field": FIELD_KITCHEN_BLENDED,
        "moodboard_env": "KREA_MOODBOARD_ID_SALE_BANNER_KITCHEN",
        # No kitchen moodboard yet: reuse the dining room's modern Christmas look until one is set in .env.
        "moodboard_default": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
        "prompt_env": "SALE_BANNER_KITCHEN_PROMPT",
        "prompt_default": KITCHEN_PROMPT,
        "extra_rules": (
            "Hang the two pendant lights side by side above the kitchen island, evenly spaced and centred on it, each "
            "lowest point roughly 70 to 80 cm above the countertop, so they read as a pair. The two pendants may be "
            "different models: keep each exactly as its own cutout. If the ceiling is not visible in Image 1, extend "
            "the scene upward so the ceiling canopies and the cords or rods are visible."
        ),
    },
]

STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"
STATUS_SALE_DONE = "Sale Banner Done"  # Banner Set only: the third banner is still to be made on this row
STATUS_FOR_MANUAL = "For Manual"


def resolve_table_id(table_id: str | None) -> str:
    if table_id:
        return table_id.strip()
    for key in TABLE_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return DEFAULT_TABLE_ID


def _room_fixtures(fields: dict[str, Any], room: dict[str, Any]) -> list[dict[str, str]]:
    return fixtures_from_record(
        fields,
        room["slots"],
        furniture_field=FIELD_FURNITURE,
        name_field=FIELD_ITEM_NAME,
        details_field=FIELD_ITEM_DETAILS,
    )


def _first_url(fields: dict[str, Any], field: str) -> str:
    atts = fields.get(field) or []
    return str(atts[0].get("url") or "") if atts else ""


# --------------------------------------------------------------------------
# PHASE 1: scrape 3 pendant lights into ONE brand-new row
# --------------------------------------------------------------------------

def run_phase_1_scrape(clients: PipelineClients, style: str = "modern") -> str:
    print("\n[PHASE 1] Scraping 3 pendant lights (1 for the dining room, 2 for the kitchen)...")
    base_skus, base_names, shopify_index = load_scrape_context(clients)

    picked: list[dict[str, Any]] = []
    for slot in SLOTS:
        chosen = pick_fixture(clients, slot, style, base_skus, base_names, shopify_index)
        if chosen is None:
            raise AutomationError(
                f"No new eligible {slot['label']} found in Akeneo category '{slot['category']}'. "
                "The sale banner needs three pendant lights; nothing was written to Airtable."
            )
        picked.append(chosen)
        # Recording each pick right away keeps the three pendant lights from being the same item.
        base_skus.add(chosen["sku"].lower())
        base_names.add(chosen["clean_name"].lower())

    clients.airtable.ensure_fields(REQUIRED_FIELDS)

    # No ID / Foreign Key ID here: ID is an autoNumber and create_record() fills Foreign Key ID from it.
    record_id = clients.airtable.create_record({
        FIELD_STATUS: STATUS_IN_PROGRESS,
        FIELD_CATEGORY: CATEGORY_LABEL,
        FIELD_SKU: "\n".join(f"{p['code']}: {p['sku']}" for p in picked),
        FIELD_ITEM_NAME: "\n".join(f"{p['code']}: {p['clean_name']}" for p in picked),
        FIELD_ITEM_DETAILS: "\n".join(f"{p['code']}: {p['notes']}" for p in picked if p.get("notes")),
    })
    for p in picked:  # sequential upload keeps the DP, KA, KB order
        clients.airtable.upload_attachment(
            record_id, FIELD_FURNITURE, p["cutout"], f"{p['code']}_{p['sku']}_{p['media_code']}.png"
        )
    print(f"  [OK] Created brand-new row {record_id} with {len(picked)} cutouts.")
    return record_id


# --------------------------------------------------------------------------
# PHASE 2: Krea dining room + kitchen (4:5)
# --------------------------------------------------------------------------

def run_phase_2_interiors(
    clients: PipelineClients,
    record_id: str,
    overrides: dict[str, dict[str, str]] | None = None,
) -> None:
    print(f"\n[PHASE 2] Generating Krea Christmas dining room and kitchen ({ROOM_ASPECT_RATIO}) for record {record_id}...")
    updates: dict[str, Any] = {}
    for room in ROOMS:
        override = (overrides or {}).get(room["key"], {})
        moodboard_id = (override.get("moodboard") or os.getenv(room["moodboard_env"], "") or room["moodboard_default"]).strip()
        prompt = (override.get("prompt") or os.getenv(room["prompt_env"], "") or room["prompt_default"]).strip()
        print(f"  [{room['label']}] moodboard {moodboard_id}")
        print(f"  [{room['label']}] prompt: \"{prompt}\"")
        krea_url = krea_generate_room(
            clients,
            prompt=prompt,
            moodboard_id=moodboard_id,
            aspect_ratio=ROOM_ASPECT_RATIO,
            fallback_aspect_ratio=KREA_FALLBACK_ASPECT_RATIO,
        )
        print(f"  [OK] {room['label']} interior: {krea_url[:70]}...")
        downloaded = clients.krea.download_image(krea_url)
        clients.airtable.clear_attachment_field(record_id, room["interior_field"])
        clients.airtable.upload_attachment(
            record_id, room["interior_field"], downloaded, f"krea_{room['key']}_{record_id}.jpg"
        )
        updates[room["krea_prompt_field"]] = prompt
    updates[FIELD_STATUS] = "Interiors Generated"
    clients.airtable.update_record(record_id, updates)


# --------------------------------------------------------------------------
# PHASE 3: Claude blending prompt per room
# --------------------------------------------------------------------------

def _fallback_room_prompt(room: dict[str, Any], fixtures: list[dict[str, str]]) -> str:
    if room["key"] == "dining":
        name = fixtures[0]["name"] if fixtures else "pendant light"
        return (
            f"Using Image 1 as the base {room['theme']}, hang the Pendant Light \"{name}\" (Image 2) from the ceiling "
            "centred above the dining table, reproduced faithfully from its cutout and switched on with a warm 2700K glow "
            "that lights the table. Keep the room and its Christmas styling unchanged. No text, logos or people."
        )
    names = [f["name"] for f in fixtures] + ["pendant light"] * 2
    return (
        f"Using Image 1 as the base {room['theme']}, hang the Pendant Light \"{names[0]}\" (Image 2) and the Pendant "
        f"Light \"{names[1]}\" (Image 3) side by side from the ceiling above the kitchen island, each reproduced "
        "faithfully from its own cutout and switched on with a warm 2700K glow that lights the island. Keep the room "
        "and its Christmas styling unchanged. No text, logos or people."
    )


def run_phase_3_claude(clients: PipelineClients, record_id: str) -> dict[str, str]:
    print(f"\n[PHASE 3] Claude Sonnet 5 vision analysis (dining room and kitchen) for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})

    prompts: dict[str, str] = {}
    updates: dict[str, Any] = {}
    for room in ROOMS:
        interior_url = _first_url(fields, room["interior_field"])
        fixtures = _room_fixtures(fields, room)
        if not interior_url or len(fixtures) != len(room["slots"]):
            raise AutomationError(
                f"Record {record_id} needs the {room['label']} interior and {len(room['slots'])} item cutout(s) "
                f"(found {len(fixtures)})."
            )
        print(f"  [{room['label']}] {len(fixtures)} item(s): {', '.join(f['name'] for f in fixtures)}")
        prompt = request_blend_prompt(
            clients,
            instruction=build_banner_multi_fixture_instruction(
                fixtures,
                aspect_ratio=ROOM_ASPECT_RATIO,
                theme=room["theme"],
                text_zone=None,
                extra_rules=room["extra_rules"],
                length_hint=BLEND_LENGTH_HINT,
            ),
            image_urls=[interior_url, *[fx["url"] for fx in fixtures]],
            fixture_count=len(fixtures),
            fallback=_fallback_room_prompt(room, fixtures),
            min_chars=BLEND_MIN_CHARS,
        )
        prompts[room["key"]] = prompt
        updates[room["prompt_field"]] = prompt
        print(f"  [OK] {room['label']} blending prompt ({len(prompt)} characters).")
    updates[FIELD_STATUS] = "Prompts Generated"
    clients.airtable.update_record(record_id, updates)
    return prompts


# --------------------------------------------------------------------------
# PHASE 4: Nano Banana Pro blend per room (4:5)
# --------------------------------------------------------------------------

def run_phase_4_blend(clients: PipelineClients, record_id: str) -> list[Path]:
    print(f"\n[PHASE 4] Nano Banana Pro {ROOM_ASPECT_RATIO} room blends for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})
    resolution = os.getenv("SALE_BANNER_RESOLUTION", "2K")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for room in ROOMS:
        interior_url = _first_url(fields, room["interior_field"])
        fixtures = _room_fixtures(fields, room)
        prompt = str(fields.get(room["prompt_field"]) or "").strip()
        if not interior_url or len(fixtures) != len(room["slots"]) or not prompt:
            raise AutomationError(f"Record {record_id} is missing inputs for the {room['label']} blend.")

        blended_url = nano_banana_blend(
            clients,
            prompt=prompt,
            image_urls=[interior_url, *[fx["url"] for fx in fixtures]],
            aspect_ratio=ROOM_ASPECT_RATIO,
            resolution=resolution,
        )
        print(f"  [OK] {room['label']} blend: {blended_url[:70]}...")
        downloaded = download_url_to_temp_file(
            requests.Session(),
            blended_url,
            prefix=f"sale_{room['key']}_",
            suffix=".jpg",
            context=f"Download Nano Banana Pro {room['label']} blend from {blended_url}",
        )
        local_path = OUTPUT_DIR / f"{room['key']}_blend_{record_id}.jpg"
        local_path.write_bytes(Path(downloaded.path).read_bytes())
        clients.airtable.clear_attachment_field(record_id, room["blended_field"])
        clients.airtable.upload_attachment(record_id, room["blended_field"], downloaded, local_path.name)
        saved.append(local_path)
    clients.airtable.update_record(record_id, {FIELD_STATUS: "Rooms Blended"})
    return saved


# --------------------------------------------------------------------------
# PHASE 5: percentages, captions (calendar) and the panel colour (Claude)
# --------------------------------------------------------------------------

def suggest_panel_color(clients: PipelineClients, fields: dict[str, Any]) -> str:
    """Ask Claude Sonnet 5 (vision, both room blends) for the panel's hex colour.

    The answer is darkened just enough for white text to stay readable. Any problem (missing blend,
    API error, no hex code twice in a row) falls back to the sample's red, so this never fails the run.
    """
    urls = [_first_url(fields, FIELD_DINING_BLENDED), _first_url(fields, FIELD_KITCHEN_BLENDED)]
    if not all(urls):
        print(f"  [WARN] Both room blends are needed to suggest a colour; using {DEFAULT_PANEL_HEX}.")
        return DEFAULT_PANEL_HEX
    for attempt in (1, 2):
        try:
            reply = clients.fal.generate_claude_vision(
                prompt=build_sale_panel_color_instruction(),
                image_urls=urls,
                system_instruction="You are a senior retail art director for HomeCartel.",
            )
        except Exception as exc:  # noqa: BLE001 - the colour is optional, keep the run going
            print(f"  [WARN] Claude panel colour attempt {attempt} failed: {exc}")
            continue
        suggested = parse_hex_color(reply)
        if suggested:
            final = ensure_white_text_contrast(suggested)
            note = "" if final == suggested else f" (darkened from {format_hex_color(suggested)} for white text)"
            print(f"  [OK] Claude panel colour {format_hex_color(final)}{note}")
            return format_hex_color(final)
        print(f"  [WARN] Claude panel colour attempt {attempt} had no hex code: {str(reply)[:80]!r}")
    print(f"  [WARN] No usable colour from Claude; using {DEFAULT_PANEL_HEX}.")
    return DEFAULT_PANEL_HEX


def run_phase_5_captions(
    clients: PipelineClients,
    record_id: str,
    month: int | None = None,
    year: int | None = None,
    panel_color: str | None = None,
) -> list[str]:
    print(f"\n[PHASE 5] Sale captions and panel colour for record {record_id}...")
    left, right = build_sale_captions(month=month, year=year)

    if panel_color:
        chosen = parse_hex_color(panel_color)
        if not chosen:
            raise AutomationError(f"--panel-color {panel_color!r} is not a hex colour like #B3122A.")
        ratio = contrast_with_white(chosen)
        if ratio < SALE_PANEL_MIN_CONTRAST:
            print(f"  [WARN] {format_hex_color(chosen)} gives white text only {ratio:.1f}:1 contrast.")
        color_hex = format_hex_color(chosen)
        print(f"  [OK] panel colour {color_hex} (override)")
    else:
        fields = clients.airtable.get_record(record_id).get("fields", {})
        color_hex = suggest_panel_color(clients, fields)

    clients.airtable.update_record(record_id, {
        FIELD_PERCENT_LEFT: str(left.percent),
        FIELD_PERCENT_RIGHT: str(right.percent),
        FIELD_CAPTION_LEFT: left.caption,
        FIELD_CAPTION_RIGHT: right.caption,
        FIELD_PANEL_COLOR: color_hex,
        FIELD_STATUS: "Captions Generated",
    })
    for side, cap in (("left", left), ("right", right)):
        print(f"  [OK] {side}: {cap.percent}% | {cap.caption}")
    return [left.caption, right.caption]


# --------------------------------------------------------------------------
# PHASE 6: local composite (interiors + red panel + Poppins text)
# --------------------------------------------------------------------------

def run_phase_6_composite(clients: PipelineClients, record_id: str, final: bool = True) -> Path:
    print(f"\n[PHASE 6] Composing the 1800x600 sale banner for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})

    def download(field: str, label: str) -> Any:
        url = _first_url(fields, field)
        if not url:
            raise AutomationError(f"Record {record_id} has no '{field}' image ({label}); run phase 4 first.")
        return download_url_to_temp_file(
            requests.Session(), url, prefix="sale_base_", suffix=".jpg", context=f"Download {label} from {url}"
        )

    dining = download(FIELD_DINING_BLENDED, "dining blend")
    kitchen = download(FIELD_KITCHEN_BLENDED, "kitchen blend")
    percent_left = str(fields.get(FIELD_PERCENT_LEFT) or "").strip()
    percent_right = str(fields.get(FIELD_PERCENT_RIGHT) or "").strip()
    caption_left = str(fields.get(FIELD_CAPTION_LEFT) or "").strip()
    caption_right = str(fields.get(FIELD_CAPTION_RIGHT) or "").strip()
    if not (percent_left and percent_right and caption_left and caption_right):
        raise AutomationError(f"Record {record_id} has no sale percentages/captions; run phase 5 first.")

    panel_rgb = parse_hex_color(fields.get(FIELD_PANEL_COLOR)) or SALE_PANEL_COLOR
    print(f"  Panel colour {format_hex_color(panel_rgb)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / f"sale_banner_{record_id}.jpg"
    draw_sale_banner(
        dining.path,
        kitchen.path,
        percent_left=percent_left,
        percent_right=percent_right,
        caption_left=caption_left,
        caption_right=caption_right,
        destination=local_path,
        panel_color=panel_rgb,
    )

    clients.airtable.clear_attachment_field(record_id, FIELD_SALE_BANNER)
    clients.airtable.upload_attachment(record_id, FIELD_SALE_BANNER, local_path, local_path.name)
    if final:
        clients.airtable.update_record(record_id, {
            FIELD_STATUS: STATUS_DONE,
            FIELD_DATE_GENERATED: current_pht_timestamp(),
        })
        print(f"  [SUCCESS] Record {record_id} Done. Saved {local_path}")
    else:
        # The Banner Set makes the third banner on this same row next; only its last phase writes Done.
        clients.airtable.update_record(record_id, {FIELD_STATUS: STATUS_SALE_DONE})
        print(f"  [OK] Sale banner composed for record {record_id}. Saved {local_path}")
    return local_path


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

STALE_NOTES = {
    2: "The blending prompts, room blends and banner are now out of date; run --from-phase 3 to refresh them.",
    3: "The room blends and banner are now out of date; run --from-phase 4 to refresh them.",
    4: "'Sale Banner' still shows the previous room blends; run --only-phase 6 to rebuild it.",
    5: "'Sale Banner' still shows the previous captions and panel colour; run --only-phase 6 to rebuild it.",
}


def run_pipeline(
    table_id: str | None = None,
    record_id: str | None = None,
    style: str = "modern",
    text_only: bool = False,
    from_phase: int = 2,
    only_phase: int | None = None,
    month: int | None = None,
    year: int | None = None,
    overrides: dict[str, dict[str, str]] | None = None,
    panel_color: str | None = None,
) -> Path | None:
    phases = phases_to_run(from_phase, text_only, only_phase, has_record=bool(record_id))
    resolved_table_id = resolve_table_id(table_id)

    print("=" * 70)
    print("HOMECARTEL MARKETING AI -- SALE BANNER PIPELINE (1800x600)")
    print("=" * 70)
    print(f"Table ID: {resolved_table_id}")
    print("Left: dining room + 1 pendant light | Right: kitchen + 2 pendant lights")
    print(f"Phases:   {', '.join(str(p) for p in phases)}")
    print("=" * 70)

    clients = PipelineClients(table_id=resolved_table_id)
    rec_id = record_id or run_phase_1_scrape(clients, style=style)
    if record_id:
        print(f"[TARGET] Re-processing explicitly targeted record: {record_id}")
        clients.airtable.ensure_fields(REQUIRED_FIELDS)

    steps = {
        2: lambda: run_phase_2_interiors(clients, rec_id, overrides=overrides),
        3: lambda: run_phase_3_claude(clients, rec_id),
        4: lambda: run_phase_4_blend(clients, rec_id),
        5: lambda: run_phase_5_captions(clients, rec_id, month=month, year=year, panel_color=panel_color),
        6: lambda: run_phase_6_composite(clients, rec_id),
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
    parser = argparse.ArgumentParser(description="HomeCartel Sale Banner Pipeline (1800x600)")
    parser.add_argument("--table-id", default="", help="Airtable Table ID override (default: the Christmas banner table)")
    parser.add_argument("--record-id", default=None, help="Explicit record ID to re-process (skips scrape)")
    parser.add_argument("--style", default="modern", help="Akeneo Style2 filter ('all' disables it)")
    parser.add_argument("--month", type=int, default=None, help="Month (1-12) for the caption dates (default: this month, or next from day 24)")
    parser.add_argument("--year", type=int, default=None, help="Year for the caption dates")
    parser.add_argument("--dining-moodboard-id", default="", help="Krea moodboard ID for the dining room")
    parser.add_argument("--kitchen-moodboard-id", default="", help="Krea moodboard ID for the kitchen")
    parser.add_argument("--dining-prompt", default="", help="Krea prompt override for the dining room")
    parser.add_argument("--kitchen-prompt", default="", help="Krea prompt override for the kitchen")
    parser.add_argument("--panel-color", default="", help="Panel hex colour like #B3122A (default: Claude suggests one from the two rooms)")
    parser.add_argument("--text-only", action="store_true", help="Alias for --from-phase 5 (captions + panel colour + composite; one Claude call, no image generation)")
    parser.add_argument(
        "--from-phase", type=int, choices=[2, 3, 4, 5, 6], default=2,
        help="Re-run from this phase on --record-id, re-using earlier images "
             "(2 Krea, 3 Claude prompts, 4 blends, 5 captions + panel colour, 6 composite)",
    )
    parser.add_argument(
        "--only-phase", type=int, choices=[2, 3, 4, 5, 6], default=None,
        help="Run just this one phase on --record-id and stop (for example 4 = room blends only)",
    )
    args = parser.parse_args()
    if args.text_only and args.from_phase not in (2, 5):
        parser.error("--text-only is --from-phase 5; do not combine it with another --from-phase")
    if args.only_phase is not None and (args.text_only or args.from_phase != 2):
        parser.error("--only-phase cannot be combined with --text-only or --from-phase")

    if args.panel_color and not parse_hex_color(args.panel_color):
        parser.error("--panel-color must be a hex colour such as #B3122A")
    overrides = {
        "dining": {"moodboard": args.dining_moodboard_id, "prompt": args.dining_prompt},
        "kitchen": {"moodboard": args.kitchen_moodboard_id, "prompt": args.kitchen_prompt},
    }
    run_pipeline(
        table_id=args.table_id or None,
        record_id=args.record_id,
        style=args.style,
        text_only=args.text_only,
        from_phase=args.from_phase,
        only_phase=args.only_phase,
        month=args.month,
        year=args.year,
        overrides=overrides,
        panel_color=args.panel_color or None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
