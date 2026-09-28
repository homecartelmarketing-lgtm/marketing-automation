"""Scrape Newest Active Pendant Lights from Akeneo into 1 Product, 3 Styles Feed Table.

Table ID: tblRy52kCasisCWzd
Category: Pendant Lights (Modern)
Krea Moodboard ID: 2a4a62bf-c6eb-49f8-8808-2543200634a0

Features:
1. Cross-Table Deduplication: Scans all tables in the Airtable base to prevent duplicate products across categories and feeds.
2. Active Products Only: Skips disabled/inactive products in Akeneo (enabled=True only) scoped to ecommerce/Shopify channel.
3. Newest to Oldest / Price Sorting: Highest value & newest additions prioritized.
4. Auto-populates 'Furniture Item', 'Item Name' (with Product Type), 'SKU', and Status='Standby'.

Usage:
    # 1. Preview / Dry Run (Read-Only):
    python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Pendant_Lights.py"

    # 2. Scrape 1 product and save to Airtable (Execute):
    python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Pendant_Lights.py" --execute

    # 3. Mass-scrape N products:
    python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Pendant_Lights.py" --execute --max-items 5
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner


DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_1_PRODUCT_3_STYLES", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_ONE_PRODUCT_THREE_STYLES", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_3_PRODUCT_1_STYLE", "").strip()
    or "tblRy52kCasisCWzd"
)
DEFAULT_CATEGORY = "pendant_lights"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Scrape active Pendant Lights for 1 Product, 3 Styles Feed (Newest First, Cross-Table Dedup)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write rows and image attachments to Airtable (without this, run is read-only dry run)",
    )
    parser.add_argument(
        "--max-items",
        "--limit",
        "-n",
        type=int,
        default=1,
        help="Maximum number of products to scrape (default: 1)
    parser.add_argument(
        "--starting-letter",
        default=None,
        help="Starting letter for A-Z sorting cycle",
    )",
    )
    parser.add_argument(
        "--table-id",
        default=DEFAULT_TABLE_ID,
        help=f"Target Airtable Table ID (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--style",
        default=DEFAULT_STYLE,
        help=f"Akeneo Style code (default: {DEFAULT_STYLE})",
    )
    return parser.parse_args(argv)


def main():
    args = parse_args()
    settings = load_settings()
    settings.require({"airtable", "akeneo"})

    channel = (os.getenv("CHANNEL_NAME") or "").strip()
    if not channel:
        raise AutomationError("Missing CHANNEL_NAME in .env")

    mode = "LIVE EXECUTE" if args.execute else "DRY RUN (Read-Only)"
    print("\n" + "=" * 68)
    print(" HomeCartel - Akeneo Pendant Light Scraper for 1 Product, 3 Styles Feed")
    print(f" Target Table ID: {args.table_id}")
    print(f" Category: Pendant Lights | Style: {args.style}")
    print(f" Mode: {mode}")
    print(f" Limit: {args.max_items} product(s)")
    print(" Filters: Active/Enabled Only | Cross-Table Dedup: ON | Order: Newest First")
    print("=" * 68)

    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=channel,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_api_key,
        settings.airtable_base_id,
        args.table_id,
    )

    runner = FurnitureItemScrapeRunner(
        akeneo=akeneo,
        airtable=airtable,
        category_code=DEFAULT_CATEGORY,
        style_code=args.style,
        field_name="Furniture Item",
        item_name_field="Item Name",
        sku_field="SKU",
        status_field="Status",
        default_status="Standby",
        include_product_type_in_name=True,
        max_items=args.max_items,
        cross_table_dedup=True,
        starting_letter=args.starting_letter,
        sort_by_price=True,
    )

    runner.run(execute=args.execute)
    if not args.execute:
        print("\n[NOTE] Dry run complete. To save to Airtable, add the `--execute` flag.")


if __name__ == "__main__":
    main()
