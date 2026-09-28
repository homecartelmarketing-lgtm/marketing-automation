"""Scrape Chandeliers from Akeneo into Product Closeup w/ Specification Table.

Table ID: tblEGTB6BodRVDqBV
Table Name: Product Closeup w/ Specification Chandelier
Category: Chandeliers (Modern)
Row Capacity: 1 Product per Row + Product Closeup w/ Specs Layout (product_specs_layout.png)

Features:
- Shopify Catalog cross-check: verifies published on homecartel.net, skips drafts/inactive.
- Cross-table Airtable base deduplication: skips any item already existing across the Airtable base.
- Automatic Layout Attachment: attaches 'product_specs_layout.png' to 'Product Closeup w/ Specs Layout'.

Usage:
    # Scrape 1 product (1 row):
    python "Product Closeup Specs Story/3_Scrape_Akeneo_Chandeliers.py"

    # Scrape N products (N rows):
    python "Product Closeup Specs Story/3_Scrape_Akeneo_Chandeliers.py" --count 3

    # Dry run preview (no changes to Airtable):
    python "Product Closeup Specs Story/3_Scrape_Akeneo_Chandeliers.py" --dry-run
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

CATEGORY_CODE = "chandelier_product_specs_story"
LABEL = "Chandeliers Product Closeup w/ Specs"
DEFAULT_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_SPECS", "").strip() or "tblEGTB6BodRVDqBV"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
FIELD_NAME = "Furniture item"
ITEM_NAME_FIELD = "Item Name"
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
    parser.add_argument(
        "--no-shopify-check",
        action="store_true",
        help="Disable Shopify published catalog verification",
    )
    parser.add_argument(
        "--no-cross-dedup",
        action="store_true",
        help="Disable base-wide cross-table deduplication",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate scraping and deduplication without modifying Airtable",
    )
    return parser.parse_args(argv)


def scrape_chandeliers(
    count: int = 1,
    style: str = DEFAULT_STYLE,
    table_id: str = DEFAULT_TABLE_ID,
    shopify_cross_check: bool = True,
    cross_table_dedup: bool = True,
    execute: bool = True,
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

    print("\n" + "=" * 68)
    print(f" HomeCartel - Scraper: {LABEL}")
    print(f" Target Table ID: {scrape_settings.airtable_table_id}")
    print(f" Style: {style} | Products Target: {count}")
    print(f" Shopify Cross-Check : {'Enabled' if shopify_cross_check else 'Disabled'}")
    print(f" Cross-Table Dedup   : {'Enabled' if cross_table_dedup else 'Disabled'}")
    print(" Auto-Layout: product_specs_layout.png -> 'Product Closeup w/ Specs Layout'")
    print("=" * 68)

    sku_field = "SKU" if airtable.has_field("SKU") else None

    runner = FurnitureItemScrapeRunner(
        akeneo,
        airtable,
        category_code=CATEGORY_CODE,
        style_code=style,
        field_name=FIELD_NAME,
        item_name_field=ITEM_NAME_FIELD,
        sku_field=sku_field,
        status_field=STATUS_FIELD,
        default_status=SELECT_STATUS,
        include_product_type_in_name=True,
        max_items=count,
        cross_table_dedup=cross_table_dedup,
        shopify_cross_check=shopify_cross_check,
    )
    return runner.run(execute=execute)


def main(argv=None) -> int:
    args = parse_args(argv)
    ok = scrape_chandeliers(
        count=args.count,
        style=args.style,
        table_id=args.table_id,
        shopify_cross_check=not args.no_shopify_check,
        cross_table_dedup=not args.no_cross_dedup,
        execute=not args.dry_run,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AutomationError as err:
        print(f"[FATAL] {err}", file=sys.stderr)
        sys.exit(2)
