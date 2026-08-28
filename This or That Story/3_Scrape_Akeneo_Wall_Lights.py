"""Scrape Wall Lights from Akeneo into This or That Story Table.

Table ID: tblZw6jvSa27oZDiN
Category: Wall Lights (Modern)
Row Capacity: 2 Products per Row + This or That Layout Watermark

Usage:
    # Scrape 1 pair (1 row = 2 products):
    python "This or That Story/3_Scrape_Akeneo_Wall_Lights.py"

    # Scrape N pairs (N rows):
    python "This or That Story/3_Scrape_Akeneo_Wall_Lights.py" --rows 3

    # Override Style or Table ID:
    python "This or That Story/3_Scrape_Akeneo_Wall_Lights.py" --style modern --table-id tblZw6jvSa27oZDiN
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
    ScrapeAirtableClient,
    ScrapeRunner,
    load_scrape_settings,
)

CATEGORY_CODE = "wall_lights_this_or_that"
LABEL = "Wall Lights This or That"
DEFAULT_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT", "").strip() or "tblZw6jvSa27oZDiN"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=f"Scrape {LABEL} from Akeneo into Airtable (2 products per row with layout)."
    )
    parser.add_argument(
        "--rows",
        "-n",
        "--count",
        type=int,
        default=1,
        help="Number of rows (pairs) to scrape (default: 1)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum individual products to scrape (overrides --rows if set)",
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


def scrape_wall_lights(
    rows: int = 1,
    max_items: int | None = None,
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

    total_items = max_items if max_items is not None else rows * 2

    print("\n" + "=" * 64)
    print(f" HomeCartel - Scraper: {LABEL}")
    print(f" Target Table ID: {scrape_settings.airtable_table_id}")
    print(f" Style: {style} | Rows Target: {rows} (Up to {total_items} items)")
    print(f" Auto-Layout: thisorthatlayout.jpg -> 'This or That Layout'")
    print("=" * 64)

    runner = ScrapeRunner(
        akeneo,
        airtable,
        category_code=CATEGORY_CODE,
        style_code=style,
        items_per_row=2,
        max_items=total_items,
    )
    return runner.run()


def main(argv=None) -> int:
    args = parse_args(argv)
    ok = scrape_wall_lights(
        rows=args.rows,
        max_items=args.max_items,
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
