#!/usr/bin/env python3
"""Banner Set Pipeline: the Christmas banner (21:9), the Sale banner (1800x600) AND the third banner (1800x600)
from ONE Airtable row.

One run scrapes fresh products once, creates ONE brand-new row, then makes all three banners on that same row:

    Phase 1       Akeneo scrape (Shopify-active, base-wide dedup): 10 different products in one new row
                  - Christmas banner: chandelier CH, pendant PE, floor lamp FL, table lamp TL, wall light WL
                  - Sale banner:      3 pendant lights, DP over the dining table, KA and KB over the kitchen island
                  - Third banner:     2 table lamps, BA and BB, for the two bedside tables
    Phases 2-6    Christmas banner (docs/banners/CHRISTMAS_BANNER.md) -> "Banner with Text"
    Phases 7-11   Sale banner (docs/banners/SALE_BANNER.md), its phases 2-6 -> "Sale Banner"
                  (Krea dining room + kitchen, Claude prompts, Nano Banana Pro blends,
                  calendar captions + Claude panel colour, local Pillow composite)
    Phases 12-15  Third banner (docs/banners/THIRD_BANNER.md), its phases 2-5 -> "Third Banner"
                  (Krea modern Christmas bedroom, Claude prompt, Nano Banana Pro blend, local Pillow composite
                  with a panel in the Sale banner's colour)

The row is `Done` (with the PHT timestamp) only when the third banner is finished. Each banner can still be
re-made on a row this script made, with its own script and `--record-id` (generate_christmas_banner_pipeline.py,
generate_sale_banner_pipeline.py or generate_third_banner_pipeline.py, `--from-phase` / `--only-phase`).

Usage:
    python generate_banner_set_pipeline.py
    python generate_banner_set_pipeline.py --month 11 --year 2026 --panel-color "#0B3D2E"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import generate_christmas_banner_pipeline as christmas  # noqa: E402
import generate_sale_banner_pipeline as sale  # noqa: E402
import generate_third_banner_pipeline as third  # noqa: E402
from content_automation.banner_common import PipelineClients, load_scrape_context, pick_fixture  # noqa: E402
from content_automation.errors import AutomationError  # noqa: E402
from content_automation.overlay import parse_hex_color  # noqa: E402

# Same Category as the Christmas banner rows, so the Studio's banner count carries on across both.
CATEGORY_LABEL = "Christmas Banner"
# Christmas fixtures first (their order is the Image 2..6 order), then the Sale banner's three pendants, then the
# third banner's two table lamps. Every code is different so one row can hold all ten cutouts.
SLOTS: list[dict[str, str]] = [*christmas.FIXTURES, *sale.SLOTS, *third.THIRD_SLOTS]
REQUIRED_FIELDS = {**christmas.REQUIRED_FIELDS, **sale.REQUIRED_FIELDS, **third.REQUIRED_FIELDS}
TOTAL_PHASES = 15  # 1 scrape + 5 Christmas + 5 Sale + 4 Third


def run_phase_1_scrape_set(clients: PipelineClients, style: str = "modern") -> str:
    codes = ", ".join(slot["code"] for slot in SLOTS)
    print(f"\n[PHASE 1] Scraping {len(SLOTS)} fresh products ({codes}) into one new row...")
    base_skus, base_names, shopify_index = load_scrape_context(clients)

    picked: list[dict[str, Any]] = []
    for slot in SLOTS:
        chosen = pick_fixture(clients, slot, style, base_skus, base_names, shopify_index)
        if chosen is None:
            raise AutomationError(
                f"No new eligible {slot['label']} found in Akeneo category '{slot['category']}'. "
                "The banner set needs all of its products; nothing was written to Airtable."
            )
        picked.append(chosen)
        # Recording each pick right away keeps every slot (even two of the same category) on a different item.
        base_skus.add(chosen["sku"].lower())
        base_names.add(chosen["clean_name"].lower())

    clients.airtable.ensure_fields(REQUIRED_FIELDS)

    # No ID / Foreign Key ID here: ID is an autoNumber and create_record() fills Foreign Key ID from it.
    record_id = clients.airtable.create_record({
        christmas.FIELD_STATUS: christmas.STATUS_IN_PROGRESS,
        christmas.FIELD_CATEGORY: CATEGORY_LABEL,
        christmas.FIELD_SKU: "\n".join(f"{p['code']}: {p['sku']}" for p in picked),
        christmas.FIELD_ITEM_NAME: "\n".join(f"{p['code']}: {p['clean_name']}" for p in picked),
        christmas.FIELD_ITEM_DETAILS: "\n".join(f"{p['code']}: {p['notes']}" for p in picked if p.get("notes")),
    })
    for p in picked:  # sequential upload keeps the slot order
        clients.airtable.upload_attachment(
            record_id, christmas.FIELD_FURNITURE, p["cutout"], f"{p['code']}_{p['sku']}_{p['media_code']}.png"
        )
    print(f"  [OK] Created brand-new row {record_id} with {len(picked)} cutouts (one row for all three banners).")
    return record_id


def run_pipeline(
    table_id: str | None = None,
    *,
    style: str = "modern",
    moodboard_id: str = "",
    interior_prompt: str = "",
    month: int | None = None,
    year: int | None = None,
    overrides: dict[str, dict[str, str]] | None = None,
    panel_color: str | None = None,
    third_moodboard_id: str = "",
    third_prompt: str = "",
    third_title: str = "",
    third_subtitle: str = "",
) -> tuple[Path | None, Path | None, Path | None]:
    resolved_table_id = christmas.resolve_table_id(table_id)

    print("=" * 70)
    print("HOMECARTEL MARKETING AI -- BANNER SET (Christmas 21:9 + Sale 1800x600 + Third 1800x600, one row)")
    print("=" * 70)
    print(f"Table ID: {resolved_table_id}")
    print(f"Products: {', '.join(slot['code'] for slot in SLOTS)}")
    print("Phases:   1 scrape, 2-6 Christmas banner, then the Sale banner (its phases 2-6, printed as "
          "[PHASE 2] to [PHASE 6] again), then the third banner (its phases 2-5, printed as [PHASE 2] to [PHASE 5] again)")
    print("=" * 70)

    clients = PipelineClients(table_id=resolved_table_id)
    rec_id = run_phase_1_scrape_set(clients, style=style)

    christmas_path: Path | None = None
    sale_path: Path | None = None
    third_path: Path | None = None
    try:
        christmas.run_phase_2_interior(clients, rec_id, custom_moodboard=moodboard_id, custom_prompt=interior_prompt)
        christmas.run_phase_3_claude(clients, rec_id)
        christmas.run_phase_4_blend(clients, rec_id)
        christmas.run_phase_5_copy(clients, rec_id)
        christmas_path = christmas.run_phase_6_overlay(clients, rec_id, final=False)

        sale.run_phase_2_interiors(clients, rec_id, overrides=overrides)
        sale.run_phase_3_claude(clients, rec_id)
        sale.run_phase_4_blend(clients, rec_id)
        sale.run_phase_5_captions(clients, rec_id, month=month, year=year, panel_color=panel_color)
        sale_path = sale.run_phase_6_composite(clients, rec_id, final=False)

        third.run_phase_2_interior(clients, rec_id, custom_moodboard=third_moodboard_id, custom_prompt=third_prompt)
        third.run_phase_3_claude(clients, rec_id)
        third.run_phase_4_blend(clients, rec_id)
        third_path = third.run_phase_5_composite(
            clients, rec_id, title=third_title, subtitle=third_subtitle
        )  # writes Done + the PHT timestamp
    except Exception as e:
        print(f"\n[ERROR] Banner Set failed on record {rec_id}: {e}")
        try:
            clients.airtable.update_record(rec_id, {christmas.FIELD_STATUS: christmas.STATUS_FOR_MANUAL})
        except Exception:
            pass
        raise

    print(f"\n>>> COMPLETED RECORD {rec_id} SUCCESSFULLY! All three banners are on this one row. <<<")
    print(f"Christmas banner: {christmas_path}")
    print(f"Sale banner:      {sale_path}")
    print(f"Third banner:     {third_path}")
    return christmas_path, sale_path, third_path


def main() -> int:
    parser = argparse.ArgumentParser(description="HomeCartel Banner Set: Christmas, Sale and third banner on one row")
    parser.add_argument("--table-id", default="", help="Airtable Table ID override (default: the Christmas banner table)")
    parser.add_argument("--style", default="modern", help="Akeneo Style2 filter ('all' disables it)")
    parser.add_argument("--moodboard-id", default="", help="Krea moodboard ID for the Christmas living room")
    parser.add_argument("--interior-prompt", default="", help="Krea prompt override for the Christmas living room")
    parser.add_argument("--month", type=int, default=None, help="Month (1-12) for the Sale caption dates (default: this month, or next from day 24)")
    parser.add_argument("--year", type=int, default=None, help="Year for the Sale caption dates")
    parser.add_argument("--dining-moodboard-id", default="", help="Krea moodboard ID for the Sale dining room")
    parser.add_argument("--kitchen-moodboard-id", default="", help="Krea moodboard ID for the Sale kitchen")
    parser.add_argument("--dining-prompt", default="", help="Krea prompt override for the Sale dining room")
    parser.add_argument("--kitchen-prompt", default="", help="Krea prompt override for the Sale kitchen")
    parser.add_argument("--panel-color", default="", help="Sale panel hex colour like #0B3D2E (default: Claude picks one from the two rooms); the third banner uses the same colour")
    parser.add_argument("--third-moodboard-id", default="", help="Krea moodboard ID for the third banner's bedroom")
    parser.add_argument("--third-prompt", default="", help="Krea prompt override for the third banner's bedroom")
    parser.add_argument("--third-title", default="", help="Third banner panel title (default: 'New Collection')")
    parser.add_argument("--third-subtitle", default="", help="Third banner panel subtitle (default: 'Free Delivery and Installation')")
    args = parser.parse_args()

    if args.panel_color and not parse_hex_color(args.panel_color):
        parser.error("--panel-color must be a hex colour such as #0B3D2E")
    run_pipeline(
        table_id=args.table_id or None,
        style=args.style,
        moodboard_id=args.moodboard_id,
        interior_prompt=args.interior_prompt,
        month=args.month,
        year=args.year,
        overrides={
            "dining": {"moodboard": args.dining_moodboard_id, "prompt": args.dining_prompt},
            "kitchen": {"moodboard": args.kitchen_moodboard_id, "prompt": args.kitchen_prompt},
        },
        panel_color=args.panel_color or None,
        third_moodboard_id=args.third_moodboard_id,
        third_prompt=args.third_prompt,
        third_title=args.third_title,
        third_subtitle=args.third_subtitle,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
