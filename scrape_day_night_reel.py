"""Scrape products from Akeneo into Airtable for Chandelier Day & Night Reel (Before & After Reel).

Destination: ``tbl2VoWOt7sSut4E2`` (or override via --table-id or env)
Writable fields: ``Furniture Item``, ``Item Name``, ``SKU``, ``Status`` ("Standby")

Each Akeneo product gets its own Airtable record:
- ``Furniture Item`` gets the single product image
- ``Item Name`` gets the item name combined with product type (e.g. Item Name | Product Type)
- ``SKU`` gets the Akeneo product SKU identifier
- ``Status`` gets set to "Standby" for AI pipeline processing

Usage::

    python scrape_day_night_reel.py
    python scrape_day_night_reel.py --max-items 5
    python scrape_day_night_reel.py --category chandeliers --style modern
"""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings, resolve_reel_table
from content_automation.errors import AutomationError
from content_automation.krea_client import KreaClient
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    InteriorRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    moodboard_id_for_category,
)

DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"
STATUS_FIELD = "Status"
SELECT_STATUS = "Standby"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Scrape Akeneo product images, item names with product type, SKUs, "
            "and generate Krea AI room interiors for Before & After Reels."
        )
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["chandeliers", "floor_lamps", "pendant_lights"],
        default=None,
        help="Target table: chandeliers (tblODnfaNVP6SXn0A), floor_lamps (tbl2VoWOt7sSut4E2), or pendant_lights (tbleUP86Kw36G8Hdw)",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=[*SCRAPE_CATEGORIES, "all"],
        default=None,
        help="Akeneo category to scrape",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Style code filter in Akeneo (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Upload at most N new product images in total",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    parser.add_argument(
        "--no-cross-dedup",
        action="store_true",
        help="Disable base-wide cross-table deduplication (check current table only)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    reel_config = resolve_reel_table(args.target, args.category)
    table_id = args.table_id or os.getenv(reel_config["env_table_key"], "").strip() or reel_config["default_table_id"]
    category_code = reel_config["table_code"] if args.category is None else args.category
    categories = [category_code]

    settings = load_scrape_settings(
        category_code=category_code,
        style_code=args.style,
        table_id_override=table_id,
    )

    print("=" * 64)
    print(f"Before & After Reel Akeneo Scraper ({reel_config['label']})")
    print(f"Destination: {settings.airtable_base_id} / {settings.airtable_table_id}")
    print(f"Akeneo Category: {reel_config['category_code']} | Style filter: {args.style}")
    print("=" * 64)

    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=settings.channel_name,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        settings.airtable_table_id,
    )

    overall_success = True
    items_remaining = args.max_items

    for category_code in categories:
        runner = FurnitureItemScrapeRunner(
            akeneo,
            airtable,
            category_code=category_code,
            style_code=args.style,
            field_name=FIELD_NAME,
            item_name_field=ITEM_NAME_FIELD,
            sku_field=SKU_FIELD,
            status_field=STATUS_FIELD,
            default_status=SELECT_STATUS,
            include_product_type_in_name=True,
            max_items=items_remaining,
            cross_table_dedup=not args.no_cross_dedup,
        )
        if not runner.run():
            overall_success = False

    if args.generate_interior:
        print("\n" + "=" * 64)
        print(f"Generating Krea AI Room Interior Photos for {reel_config['label']}...")
        base = load_settings()
        base.require({"krea"})
        moodboard_id = moodboard_id_for_category(category_code) or reel_config.get("default_moodboard_id", "")
        print(f"Krea Moodboard ID: {moodboard_id or '<none configured>'}")
        print("=" * 64)

        interior_runner = InteriorRunner(
            krea=KreaClient(base.krea_token, base.krea_base_url),
            airtable=airtable,
            moodboard_id=moodboard_id,
            prompt=reel_config["interior_prompt"],
            slot_count=1,
        )
        if not interior_runner.generate_for_records():
            overall_success = False

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
