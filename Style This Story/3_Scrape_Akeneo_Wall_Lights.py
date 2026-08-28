"""Scrape Newest Active Wall Lights from Akeneo into Style This Story Table.

Table ID: tblXJrvSBkJNhRHLa
Category: Wall Lights (Modern)
Krea Prompt: "Generate me a modern living room with a wall light"

Features:
1. Cross-Table Deduplication: Scans ALL tables in the Airtable base to verify if a wall light already exists.
2. Active Products Only: Skips disabled/inactive products in Akeneo (enabled=True only).
3. Newest to Oldest: Sorts products so the newest additions are processed first.
4. Auto-populates 'Furniture Item', 'Item Name' (with Product Type), 'SKU', and Status='Standby'.

Usage:
    # 1. Scrape 1 new wall light (Dry Run / Read-Only):
    python "Style This Story/3_Scrape_Akeneo_Wall_Lights.py"

    # 2. Scrape 1 new wall light and save to Airtable (Execute):
    python "Style This Story/3_Scrape_Akeneo_Wall_Lights.py" --execute

    # 3. Scrape N new wall lights:
    python "Style This Story/3_Scrape_Akeneo_Wall_Lights.py" --execute --max-items 3
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

# Add parent directory to sys.path so modules import seamlessly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner


DEFAULT_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_WALL_LIGHTS", "").strip() or "tblXJrvSBkJNhRHLa"
DEFAULT_CATEGORY = "wall_lights"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Scrape active Wall Lights (newest to oldest, cross-table deduplicated) for Style This Story"
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
        help="Maximum number of new wall light products to scrape (default: 1)",
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


def scrape_wall_lights_for_style_this(
    table_id: str = DEFAULT_TABLE_ID,
    max_items: int = 1,
    style_code: str = DEFAULT_STYLE,
    execute: bool = False,
) -> bool:
    settings = load_settings()
    settings.require({"airtable", "akeneo"})

    channel = (os.getenv("CHANNEL_NAME") or "").strip()
    if not channel:
        raise AutomationError("Missing CHANNEL_NAME in .env")

    mode = "LIVE EXECUTE" if execute else "DRY RUN (Read-Only)"
    print("\n" + "=" * 64)
    print(" HomeCartel - Akeneo Wall Light Scraper for Style This Story")
    print(f" Target Table ID: {table_id}")
    print(f" Category: Wall Lights | Style: {style_code}")
    print(f" Mode: {mode}")
    print(f" Limit: {max_items} product(s)")
    print(" Filters: Active/Enabled Only | Cross-Table Dedup: ON | Order: Newest First")
    print("=" * 64)

    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=channel,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )

    runner = FurnitureItemScrapeRunner(
        akeneo,
        airtable,
        category_code=DEFAULT_CATEGORY,
        style_code=style_code,
        field_name="Furniture Item",
        item_name_field="Item Name",
        sku_field="SKU",
        status_field="Status",
        default_status="Standby",
        include_product_type_in_name=True,
        max_items=max_items,
        cross_table_dedup=True,
    )

    return runner.run(execute=execute)


def main(argv=None) -> int:
    args = parse_args(argv)
    success = scrape_wall_lights_for_style_this(
        table_id=args.table_id,
        max_items=args.max_items,
        style_code=args.style,
        execute=args.execute,
    )
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
