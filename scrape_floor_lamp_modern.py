"""Scrape Modern Floor Lamp images and names into Airtable.

Destination: ``tblvSAzXasTVI85r9``
Writable fields: ``Furniture Item`` and ``Item Name``

Each Akeneo product gets its own Airtable record. ``Item Name`` contains the
Akeneo item name and product type; no SKU, Interior, or numbered Furniture Item
fields are written.

Usage::

    python scrape_floor_lamp_modern.py
    python scrape_floor_lamp_modern.py --max-items 5
"""

from __future__ import annotations

import argparse
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.errors import AutomationError
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)


DEFAULT_TABLE_ID = "tblvSAzXasTVI85r9"
CATEGORY = "floor_lamps"
STYLE = "modern"
FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Scrape Modern Floor Lamp images and item name/product type "
            "from Akeneo into Airtable."
        )
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Upload at most N new product images",
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

    settings = load_scrape_settings(
        category_code=CATEGORY,
        style_code=STYLE,
        table_id_override=args.table_id,
    )
    print("=" * 64)
    print("Modern Floor Lamp Akeneo Scraper | Furniture Item + Item Name")
    print(
        f"Airtable destination: "
        f"{settings.airtable_base_id} / {settings.airtable_table_id}"
    )
    print("=" * 64)

    runner = FurnitureItemScrapeRunner(
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
        category_code=CATEGORY,
        style_code=STYLE,
        field_name=FIELD_NAME,
        item_name_field=ITEM_NAME_FIELD,
        max_items=args.max_items,
    )
    return 0 if runner.run() else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
