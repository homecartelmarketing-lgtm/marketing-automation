"""Compatibility CLI for the original one-product-per-Airtable-row scraper.

This intentionally remains separate from the default ten-item scraper so the
old behavior can be restored with a clear, stable command whenever needed.
"""

from __future__ import annotations

import argparse
import sys

from content_automation.errors import AutomationError
from content_automation.scraping.categories import SCRAPE_CATEGORIES
from standalone_scrape_akeneo import run_categories


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Akeneo scraper compatibility mode: one product per row"
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=[*SCRAPE_CATEGORIES, "all"],
        default="all",
        help="Category to scrape (default: all)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=None,
        help="Style code filter in Akeneo (default: AKENEO_STYLE from .env)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Upload at most N new products in the entire run",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override the Airtable destination table ID for this run",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")
    categories = (
        list(SCRAPE_CATEGORIES) if args.category == "all" else [args.category]
    )
    return run_categories(
        categories,
        style_code=args.style,
        items_per_row_override=1,
        max_items=args.max_items,
        table_id_override=args.table_id,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
