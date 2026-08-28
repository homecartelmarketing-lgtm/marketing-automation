"""Scrape Pendant Lights from Akeneo into Product Closeup w/ Description Table.

Table ID: tblDD2w4v0Idb4jAZ
Category: Pendant Lights (Modern)
Row Capacity: 1 Product per Row + Product Closeup Description Layout Watermark

Usage:
    # Scrape 1 product (1 row):
    python "Product Closeup Description Story/3_Scrape_Akeneo_Pendant_Lights.py"

    # Scrape N products (N rows):
    python "Product Closeup Description Story/3_Scrape_Akeneo_Pendant_Lights.py" --count 3

    # Override Style or Table ID:
    python "Product Closeup Description Story/3_Scrape_Akeneo_Pendant_Lights.py" --style modern --table-id tblDD2w4v0Idb4jAZ
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)

CATEGORY_CODE = "pendant_lights_product_description_story"
LABEL = "Pendant Lights Product Closeup w/ Description"
DEFAULT_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION", "").strip() or "tblDD2w4v0Idb4jAZ"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"
STATUS_FIELD = "Status"
SELECT_STATUS = "Standby"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=f"Scrape {LABEL} from Akeneo into Airtable."
    )
    parser.add_argument(
        "--count",
        "-n",
        "--max-items",
        type=int,
        default=1,
        help="Number of products to scrape (default: 1)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Akeneo Style filter (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--table-id",
        default=DEFAULT_TABLE_ID,
        help=f"Target Airtable Table ID (default: {DEFAULT_TABLE_ID})",
    )
    return parser.parse_args(argv)


def scrape_pendant_lights(
    count: int = 1,
    style: str = DEFAULT_STYLE,
    table_id: str = DEFAULT_TABLE_ID,
) -> bool:
    settings = load_settings()
    scrape_settings = load_scrape_settings(
        category_code=CATEGORY_CODE,
        style_code=style,
        table_id_override=table_id,
        settings=settings,
    )
    airtable = ScrapeAirtableClient(
        scrape_settings.airtable_token,
        scrape_settings.airtable_base_id,
        scrape_settings.airtable_table_id,
    )
    akeneo = AkeneoClient(
        scrape_settings.akeneo_host,
        scrape_settings.akeneo_client_id,
        scrape_settings.akeneo_secret,
        scrape_settings.akeneo_username,
        scrape_settings.akeneo_password,
        channel_name=scrape_settings.channel_name,
    )

    print("\n" + "=" * 64)
    print(f" HomeCartel - Scraper: {LABEL}")
    print(f" Target Table ID: {scrape_settings.airtable_table_id}")
    print(f" Style: {style} | Products Target: {count}")
    print(" Auto-Layout: layout_product_v2.jpg -> 'Product Closeup Description Layout'")
    print("=" * 64)

    runner = FurnitureItemScrapeRunner(
        akeneo,
        airtable,
        category_code=CATEGORY_CODE,
        style_code=style,
        field_name=FIELD_NAME,
        item_name_field=ITEM_NAME_FIELD,
        sku_field=SKU_FIELD,
        status_field=STATUS_FIELD,
        default_status=SELECT_STATUS,
        include_product_type_in_name=True,
        max_items=count,
    )
    return runner.run()


def main(argv=None) -> int:
    args = parse_args(argv)
    ok = scrape_pendant_lights(
        count=args.count,
        style=args.style,
        table_id=args.table_id,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AutomationError as err:
        print(f"[FATAL] {err}", file=sys.stderr)
        sys.exit(2)
