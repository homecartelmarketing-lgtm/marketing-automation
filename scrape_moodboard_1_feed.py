"""Scrape products from Akeneo into Airtable for Moodboard #1 Feed.

Destination: ``tbl9u5vjgx8kuE44R`` (or override via --table-id or env)
Writable fields: ``Furniture Item``, ``Item Name``, ``SKU``, ``Status`` ("Standby")

Each Akeneo product gets its own Airtable record:
- ``Furniture Item`` gets the single product image
- ``Item Name`` gets the item name combined with product type (e.g. Item Name | Product Type)
- ``SKU`` gets the Akeneo product SKU identifier
- ``Status`` gets set to "Standby" for AI pipeline processing

Usage::

    python scrape_moodboard_1_feed.py
    python scrape_moodboard_1_feed.py --max-items 5
    python scrape_moodboard_1_feed.py --category chandeliers --style modern
"""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.errors import AutomationError
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import SCRAPE_CATEGORIES

DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_MOODBOARD_1_FEED", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_MOODBOARD_FEED_1", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_REVISED_MOODBOARD_FEED", "").strip()
    or "tbl9u5vjgx8kuE44R"
)
DEFAULT_CATEGORY = "chandeliers"
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
            "and set Status to Standby for Moodboard #1 Feed (tbl9u5vjgx8kuE44R)."
        )
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=[*SCRAPE_CATEGORIES, "all"],
        default=DEFAULT_CATEGORY,
        help=f"Category to scrape (default: {DEFAULT_CATEGORY})",
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
        default=DEFAULT_TABLE_ID,
        help=f"Airtable destination table ID (default: {DEFAULT_TABLE_ID})",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    categories = (
        list(SCRAPE_CATEGORIES) if args.category == "all" else [args.category]
    )

    settings = load_scrape_settings(
        category_code=categories[0],
        style_code=args.style,
        table_id_override=args.table_id,
    )

    print("=" * 64)
    print("Moodboard #1 Feed Akeneo Scraper | Furniture Item + Item Name + SKU + Status")
    print(
        f"Airtable destination: "
        f"{settings.airtable_base_id} / {settings.airtable_table_id}"
    )
    print(f"Categories: {', '.join(categories)}")
    print(f"Style filter: {args.style}")
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
        )
        if not runner.run():
            overall_success = False

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
