#!/usr/bin/env python3
"""Third banner (1800x600): a coloured panel (951 px) with text on the left, a Krea bedroom (849 px) on the right.

This is the third banner of the Banner Set (generate_banner_set_pipeline.py): it runs after the Christmas banner
and the Sale banner, on the SAME Airtable row, and its panel uses the colour the Sale banner used
(`Sale Panel Color`, chosen by Claude via fal.ai). It never creates a row of its own; its CLI needs the
`--record-id` of a row the Banner Set made (the Set also scrapes its 2 table lamps, codes BA and BB).

Phases (the numbers match the "[PHASE n]" lines the Studio reads; the Set shows them as 12-15)
------
    Phase 2  Krea 3:2: modern bedroom with a Christmas vibe, always (moodboard-driven, short prompt)
             -> "Bedroom Interior", "Bedroom Interior Prompt".
    Phase 3  Claude Sonnet 5 vision over [bedroom + 2 table lamps] -> "Bedroom Blending Prompt".
    Phase 4  Nano Banana Pro 3:2: [bedroom, lamp A, lamp B] -> "Bedroom Blended".
    Phase 5  Local Pillow composite (panel in the Sale colour, "New Collection" / "Free Delivery and Installation"
             + arrow, bedroom on the right) -> "Third Banner", Status "Done" + "Date and Time Generated".

Usage (on a row made by the Banner Set):
    python generate_third_banner_pipeline.py --record-id recXXXX --from-phase 4
    python generate_third_banner_pipeline.py --record-id recXXXX --only-phase 5 --title "Holiday Collection"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
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

from content_automation.airtable_client import current_pht_timestamp  # noqa: E402
from content_automation.banner_common import (  # noqa: E402
    PipelineClients,
    fixtures_from_record,
    krea_generate_room,
    nano_banana_blend,
    request_blend_prompt,
)
from content_automation.errors import AutomationError  # noqa: E402
from content_automation.media import download_url_to_temp_file  # noqa: E402
from content_automation.overlay import (  # noqa: E402
    SALE_PANEL_COLOR,
    THIRD_SUBTITLE_TEXT,
    THIRD_TITLE_TEXT,
    draw_third_banner,
    format_hex_color,
    parse_hex_color,
)
from content_automation.prompts import build_banner_multi_fixture_instruction  # noqa: E402

# --------------------------------------------------------------------------
# Constants & defaults
# --------------------------------------------------------------------------

TABLE_ENV_KEYS = ("AIRTABLE_TABLE_ID_SALE_BANNER", "AIRTABLE_TABLE_ID_CHRISTMAS_BANNER")
DEFAULT_TABLE_ID = "tblgNk1Tp6qKUcduw"
ROOM_ASPECT_RATIO = "3:2"  # the right-hand photo slot is 849x600 (1.415)
KREA_FALLBACK_ASPECT_RATIO = "4:3"
OUTPUT_DIR = REPO_ROOT / "output" / "third_banner"
BLEND_MIN_CHARS = 700
BLEND_LENGTH_HINT = "about 1,800 to 3,200 characters (never more than 4,500)"

# Short on purpose: the Krea moodboard carries the look. Always a modern bedroom with a Christmas vibe.
BEDROOM_PROMPT = "Generate me a modern bedroom with a Christmas vibe"
# No dedicated moodboard yet: reuse the bedroom moodboard the Sale banner used, until KREA_MOODBOARD_ID_THIRD_BANNER is set.
BEDROOM_MOODBOARD_DEFAULT = "fb2487fb-2895-4d2c-9758-805aaf1bac69"
MOODBOARD_ENV = "KREA_MOODBOARD_ID_THIRD_BANNER"
PROMPT_ENV = "THIRD_BANNER_PROMPT"
TITLE_ENV = "THIRD_BANNER_TITLE"
SUBTITLE_ENV = "THIRD_BANNER_SUBTITLE"

# Slot code -> Akeneo category. BA and BB are two different table lamps for the two bedside tables.
THIRD_SLOTS = [
    {"code": "BA", "category": "table_lamps", "label": "Table Lamp"},
    {"code": "BB", "category": "table_lamps", "label": "Table Lamp"},
]

EXTRA_RULES = (
    "Place one table lamp on each of the two bedside tables flanking the bed, at natural heights, so they read as a "
    "pair, both switched on with a warm glow. The two lamps may be different models: keep each exactly as its own "
    "cutout. If only one bedside table is visible, use it for one lamp and the nearest surface for the other. Keep "
    "the wide composition and the Christmas styling of Image 1."
)

FIELD_STATUS = "Status"
FIELD_DATE_GENERATED = "Date and Time Generated"
FIELD_FURNITURE = "Furniture Item"
FIELD_ITEM_NAME = "Item Name"
FIELD_ITEM_DETAILS = "Item Details"
FIELD_BEDROOM_INTERIOR = "Bedroom Interior"
FIELD_BEDROOM_INTERIOR_PROMPT = "Bedroom Interior Prompt"
FIELD_BEDROOM_PROMPT = "Bedroom Blending Prompt"
FIELD_BEDROOM_BLENDED = "Bedroom Blended"
FIELD_PANEL_COLOR = "Sale Panel Color"
FIELD_THIRD_BANNER = "Third Banner"

REQUIRED_FIELDS = {
    FIELD_BEDROOM_INTERIOR: "multipleAttachments",
    FIELD_BEDROOM_INTERIOR_PROMPT: "multilineText",
    FIELD_BEDROOM_PROMPT: "multilineText",
    FIELD_BEDROOM_BLENDED: "multipleAttachments",
    FIELD_PANEL_COLOR: "singleLineText",
    FIELD_THIRD_BANNER: "multipleAttachments",
}

THEME = "modern Christmas bedroom"
STATUS_DONE = "Done"
STATUS_FOR_MANUAL = "For Manual"
PHASES = (2, 3, 4, 5)


def resolve_table_id(table_id: str | None) -> str:
    if table_id:
        return table_id.strip()
    for key in TABLE_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return DEFAULT_TABLE_ID


def phases_to_run(from_phase: int = 2, only_phase: int | None = None) -> list[int]:
    """Phases 2-5: ``only_phase=N`` runs just N; otherwise ``from_phase`` to 5."""
    if only_phase is not None:
        if only_phase not in PHASES:
            raise AutomationError(f"--only-phase must be one of {PHASES} (got {only_phase}).")
        if from_phase != 2:
            raise AutomationError("--only-phase cannot be combined with --from-phase.")
        return [only_phase]
    if from_phase not in PHASES:
        raise AutomationError(f"--from-phase must be one of {PHASES} (got {from_phase}).")
    return [p for p in PHASES if p >= from_phase]


def _first_url(fields: dict[str, Any], field: str) -> str:
    atts = fields.get(field) or []
    return str(atts[0].get("url") or "") if atts else ""


def _lamps(fields: dict[str, Any]) -> list[dict[str, str]]:
    return fixtures_from_record(
        fields,
        THIRD_SLOTS,
        furniture_field=FIELD_FURNITURE,
        name_field=FIELD_ITEM_NAME,
        details_field=FIELD_ITEM_DETAILS,
    )


# --------------------------------------------------------------------------
# PHASE 2: Krea modern bedroom, Christmas vibe
# --------------------------------------------------------------------------

def run_phase_2_interior(
    clients: PipelineClients,
    record_id: str,
    custom_moodboard: str = "",
    custom_prompt: str = "",
) -> str:
    moodboard_id = (custom_moodboard or os.getenv(MOODBOARD_ENV, "") or BEDROOM_MOODBOARD_DEFAULT).strip()
    prompt = (custom_prompt or os.getenv(PROMPT_ENV, "") or BEDROOM_PROMPT).strip()
    print(f"\n[PHASE 2] Generating Krea modern Christmas bedroom ({ROOM_ASPECT_RATIO}) for record {record_id}...")
    print(f"  Prompt: \"{prompt}\"")
    print(f"  Moodboard ID: {moodboard_id}")
    krea_url = krea_generate_room(
        clients,
        prompt=prompt,
        moodboard_id=moodboard_id,
        aspect_ratio=ROOM_ASPECT_RATIO,
        fallback_aspect_ratio=KREA_FALLBACK_ASPECT_RATIO,
    )
    print(f"  [OK] Bedroom interior: {krea_url[:70]}...")
    downloaded = clients.krea.download_image(krea_url)
    clients.airtable.clear_attachment_field(record_id, FIELD_BEDROOM_INTERIOR)
    clients.airtable.upload_attachment(record_id, FIELD_BEDROOM_INTERIOR, downloaded, f"krea_bedroom_{record_id}.jpg")
    clients.airtable.update_record(record_id, {
        FIELD_BEDROOM_INTERIOR_PROMPT: prompt,
        FIELD_STATUS: "Bedroom Interior Generated",
    })
    return krea_url


# --------------------------------------------------------------------------
# PHASE 3: Claude blending prompt (two table lamps)
# --------------------------------------------------------------------------

def _fallback_prompt(fixtures: list[dict[str, str]]) -> str:
    names = [f["name"] for f in fixtures] + ["table lamp"] * 2
    return (
        f"Using Image 1 as the base {THEME}, place the Table Lamp \"{names[0]}\" (Image 2) on the left bedside table "
        f"and the Table Lamp \"{names[1]}\" (Image 3) on the right bedside table, each reproduced faithfully from its "
        "own cutout and switched on with a warm 2700K glow. Keep the room and its Christmas styling unchanged. "
        "No text, logos or people."
    )


def run_phase_3_claude(clients: PipelineClients, record_id: str) -> str:
    print(f"\n[PHASE 3] Claude Sonnet 5 vision analysis (bedroom) for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})
    interior_url = _first_url(fields, FIELD_BEDROOM_INTERIOR)
    fixtures = _lamps(fields)
    if not interior_url or len(fixtures) != len(THIRD_SLOTS):
        raise AutomationError(
            f"Record {record_id} needs the Bedroom Interior and {len(THIRD_SLOTS)} table lamp cutouts "
            f"(found {len(fixtures)})."
        )
    print(f"  {len(fixtures)} item(s): {', '.join(f['name'] for f in fixtures)}")
    prompt = request_blend_prompt(
        clients,
        instruction=build_banner_multi_fixture_instruction(
            fixtures,
            aspect_ratio=ROOM_ASPECT_RATIO,
            theme=THEME,
            text_zone=None,
            extra_rules=EXTRA_RULES,
            length_hint=BLEND_LENGTH_HINT,
        ),
        image_urls=[interior_url, *[fx["url"] for fx in fixtures]],
        fixture_count=len(fixtures),
        fallback=_fallback_prompt(fixtures),
        min_chars=BLEND_MIN_CHARS,
    )
    clients.airtable.update_record(record_id, {FIELD_BEDROOM_PROMPT: prompt, FIELD_STATUS: "Bedroom Prompt Generated"})
    print(f"  [OK] Bedroom blending prompt ({len(prompt)} characters).")
    return prompt


# --------------------------------------------------------------------------
# PHASE 4: Nano Banana Pro blend (3:2)
# --------------------------------------------------------------------------

def run_phase_4_blend(clients: PipelineClients, record_id: str) -> Path:
    print(f"\n[PHASE 4] Nano Banana Pro {ROOM_ASPECT_RATIO} bedroom blend for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})
    interior_url = _first_url(fields, FIELD_BEDROOM_INTERIOR)
    fixtures = _lamps(fields)
    prompt = str(fields.get(FIELD_BEDROOM_PROMPT) or "").strip()
    if not interior_url or len(fixtures) != len(THIRD_SLOTS) or not prompt:
        raise AutomationError(f"Record {record_id} is missing inputs for the bedroom blend.")

    blended_url = nano_banana_blend(
        clients,
        prompt=prompt,
        image_urls=[interior_url, *[fx["url"] for fx in fixtures]],
        aspect_ratio=ROOM_ASPECT_RATIO,
        resolution=os.getenv("THIRD_BANNER_RESOLUTION", "2K"),
    )
    print(f"  [OK] Bedroom blend: {blended_url[:70]}...")
    downloaded = download_url_to_temp_file(
        requests.Session(),
        blended_url,
        prefix="third_bedroom_",
        suffix=".jpg",
        context=f"Download Nano Banana Pro bedroom blend from {blended_url}",
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / f"bedroom_blend_{record_id}.jpg"
    local_path.write_bytes(Path(downloaded.path).read_bytes())
    clients.airtable.clear_attachment_field(record_id, FIELD_BEDROOM_BLENDED)
    clients.airtable.upload_attachment(record_id, FIELD_BEDROOM_BLENDED, downloaded, local_path.name)
    clients.airtable.update_record(record_id, {FIELD_STATUS: "Bedroom Blended"})
    return local_path


# --------------------------------------------------------------------------
# PHASE 5: local composite (Sale colour panel + text + arrow + bedroom)
# --------------------------------------------------------------------------

def run_phase_5_composite(
    clients: PipelineClients,
    record_id: str,
    title: str = "",
    subtitle: str = "",
) -> Path:
    print(f"\n[PHASE 5] Composing the third banner for record {record_id}...")
    fields = clients.airtable.get_record(record_id).get("fields", {})
    blend_url = _first_url(fields, FIELD_BEDROOM_BLENDED)
    if not blend_url:
        raise AutomationError(f"Record {record_id} has no '{FIELD_BEDROOM_BLENDED}' image; run phase 4 first.")

    panel_rgb = parse_hex_color(fields.get(FIELD_PANEL_COLOR))
    if panel_rgb is None:
        print(f"  [WARN] Record {record_id} has no usable '{FIELD_PANEL_COLOR}'; using the sample red.")
        panel_rgb = SALE_PANEL_COLOR
    print(f"  Panel colour {format_hex_color(panel_rgb)} (the Sale banner's colour)")

    title_text = (title or os.getenv(TITLE_ENV, "") or THIRD_TITLE_TEXT).strip()
    subtitle_text = (subtitle or os.getenv(SUBTITLE_ENV, "") or THIRD_SUBTITLE_TEXT).strip()

    downloaded = download_url_to_temp_file(
        requests.Session(), blend_url, prefix="third_base_", suffix=".jpg",
        context=f"Download bedroom blend from {blend_url}",
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / f"third_banner_{record_id}.jpg"
    draw_third_banner(
        downloaded.path,
        title=title_text,
        subtitle=subtitle_text,
        panel_color=panel_rgb,
        destination=local_path,
    )
    clients.airtable.clear_attachment_field(record_id, FIELD_THIRD_BANNER)
    clients.airtable.upload_attachment(record_id, FIELD_THIRD_BANNER, local_path, local_path.name)
    clients.airtable.update_record(record_id, {
        FIELD_STATUS: STATUS_DONE,
        FIELD_DATE_GENERATED: current_pht_timestamp(),
    })
    print(f"  [SUCCESS] Record {record_id} Done. Saved {local_path}")
    return local_path


# --------------------------------------------------------------------------
# Orchestration (a row made by the Banner Set)
# --------------------------------------------------------------------------

def run_pipeline(
    record_id: str,
    *,
    table_id: str | None = None,
    from_phase: int = 2,
    only_phase: int | None = None,
    moodboard_id: str = "",
    prompt: str = "",
    title: str = "",
    subtitle: str = "",
) -> Path | None:
    if not record_id:
        raise AutomationError(
            "The third banner never creates a row of its own: pass the --record-id of a row made by "
            "generate_banner_set_pipeline.py (or run that script to make all three banners)."
        )
    phases = phases_to_run(from_phase, only_phase)
    clients = PipelineClients(table_id=resolve_table_id(table_id))
    print("=" * 70)
    print("HOMECARTEL MARKETING AI -- THIRD BANNER (1800x600, panel 951 + Krea bedroom 849)")
    print("=" * 70)
    print(f"Record:   {record_id}")
    print(f"Phases:   {', '.join(str(p) for p in phases)}")
    print("=" * 70)
    clients.airtable.ensure_fields(REQUIRED_FIELDS)

    steps = {
        2: lambda: run_phase_2_interior(clients, record_id, custom_moodboard=moodboard_id, custom_prompt=prompt),
        3: lambda: run_phase_3_claude(clients, record_id),
        4: lambda: run_phase_4_blend(clients, record_id),
        5: lambda: run_phase_5_composite(clients, record_id, title=title, subtitle=subtitle),
    }
    banner_path: Path | None = None
    try:
        for phase in phases:
            result = steps[phase]()
            if isinstance(result, Path) and phase == 5:
                banner_path = result
    except Exception as e:
        print(f"\n[ERROR] Third banner failed on record {record_id}: {e}")
        try:
            clients.airtable.update_record(record_id, {FIELD_STATUS: STATUS_FOR_MANUAL})
        except Exception:
            pass
        raise
    print(f"\n>>> COMPLETED RECORD {record_id} SUCCESSFULLY! <<<")
    if banner_path:
        print(f"Banner: {banner_path}")
    return banner_path


def main() -> int:
    parser = argparse.ArgumentParser(description="HomeCartel third banner (re-run on a Banner Set row)")
    parser.add_argument("--record-id", default=None, help="Row made by generate_banner_set_pipeline.py (required)")
    parser.add_argument("--table-id", default="", help="Airtable Table ID override (default: the banner table)")
    parser.add_argument("--moodboard-id", default="", help="Krea moodboard ID for the bedroom")
    parser.add_argument("--prompt", default="", help="Krea prompt override for the bedroom")
    parser.add_argument("--title", default="", help=f"Panel title (default: ${TITLE_ENV} or '{THIRD_TITLE_TEXT}')")
    parser.add_argument("--subtitle", default="", help=f"Panel subtitle (default: ${SUBTITLE_ENV} or '{THIRD_SUBTITLE_TEXT}')")
    parser.add_argument("--from-phase", type=int, choices=list(PHASES), default=2,
                        help="Re-run from this phase (2 Krea, 3 Claude prompt, 4 blend, 5 composite)")
    parser.add_argument("--only-phase", type=int, choices=list(PHASES), default=None,
                        help="Run just this one phase and stop")
    args = parser.parse_args()
    if not args.record_id:
        parser.error(
            "--record-id is required: the third banner never makes its own row. "
            "Run `python generate_banner_set_pipeline.py` to make all three banners on one row."
        )
    if args.only_phase is not None and args.from_phase != 2:
        parser.error("--only-phase cannot be combined with --from-phase")
    run_pipeline(
        args.record_id,
        table_id=args.table_id or None,
        from_phase=args.from_phase,
        only_phase=args.only_phase,
        moodboard_id=args.moodboard_id,
        prompt=args.prompt,
        title=args.title,
        subtitle=args.subtitle,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
