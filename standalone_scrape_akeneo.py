"""CLI: scrape Akeneo products into packed Airtable product rows.

Up to ten products are stored per standard Airtable row. The implementation lives in
``content_automation.scraping``; this file is only the command line.
"""

from __future__ import annotations

import argparse
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.errors import AutomationError
from content_automation.scraping import (
    ScrapeAirtableClient,
    ScrapeRunner,
    load_scrape_settings,
)
from content_automation.scraping.categories import SCRAPE_CATEGORIES
from content_automation.scraping.categories import items_per_row


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Akeneo Auto Scraper for Airtable")
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
        "--items-per-row",
        type=int,
        choices=range(1, 11),
        default=None,
        metavar="1-10",
        help="Override row packing (use 1 for the original one-item mode)",
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


def run_category_scrape(
    category_code: str,
    style_code: str | None = None,
    items_per_row_override: int | None = None,
    max_items: int | None = None,
    table_id_override: str | None = None,
) -> bool:
    """Scrape one category. True when nothing failed."""
    settings = load_scrape_settings(
        category_code=category_code,
        style_code=style_code,
        table_id_override=table_id_override,
    )
    label = settings.category_label.title()
    style_label = settings.style_code.title()

    print("=" * 64)
    per_row = items_per_row_override or items_per_row(settings.category_code)
    print(
        f"{style_label} {label} Mass Scraper | "
        f"up to {per_row} products per Airtable row"
    )
    print(
        f"Airtable destination ({settings.category_code}): "
        f"{settings.airtable_base_id} / {settings.airtable_table_id}"
    )
    print("=" * 64)

    runner = ScrapeRunner(
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
        category_code=settings.category_code,
        style_code=settings.style_code,
        items_per_row=items_per_row_override,
        max_items=max_items,
    )
    return runner.run()


def run_categories(
    categories: list[str],
    style_code: str | None = None,
    items_per_row_override: int | None = None,
    max_items: int | None = None,
    table_id_override: str | None = None,
) -> int:
    """Scrape each category in turn, returning a process exit code."""
    failures = 0
    for category in categories:
        try:
            if not run_category_scrape(
                category,
                style_code=style_code,
                items_per_row_override=items_per_row_override,
                max_items=max_items,
                table_id_override=table_id_override,
            ):
                failures += 1
        except KeyboardInterrupt:
            print("\n[WARN] Scrape cancelled by user")
            return 130
        except Exception as error:
            print(f"[ERROR] Fatal error scraping {category}: {error}")
            failures += 1
    return 1 if failures else 0


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
        items_per_row_override=args.items_per_row,
        max_items=args.max_items,
        table_id_override=args.table_id,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
