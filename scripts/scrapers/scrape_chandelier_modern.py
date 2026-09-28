"""CLI: scrape Akeneo 'chandelier modern' products into the Airtable
Chandelier Modern table (tbl026zbECJJ9FRfj).

Packs 4 products per row with Furniture Item, Furniture Item2..4 fields,
identical to how the table_lamps scraper works.  Reads from the shared
Akeneo 'chandeliers' category with the 'modern' style filter.

Usage::

    python scrape_chandelier_modern.py                # default style=modern
    python scrape_chandelier_modern.py --style modern  # explicit style
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


CATEGORY = "chandelier_modern"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Akeneo Chandelier Modern Scraper → Airtable (4 per row)"
    )
    parser.add_argument(
        "--style",
        "-s",
        default="modern",
        help="Style code filter in Akeneo (default: modern)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_scrape_settings(
        category_code=CATEGORY, style_code=args.style
    )
    label = settings.category_label.title()
    style_label = settings.style_code.title()

    print("=" * 64)
    print(f"{style_label} {label} Mass Scraper | 4 products per Airtable row")
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
    )
    success = runner.run()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
