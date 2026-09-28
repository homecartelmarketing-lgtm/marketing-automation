"""CLI: print how many products a category/style query matches, plus a sample.

A read-only sanity check for Akeneo credentials and category codes.
"""

from __future__ import annotations

import argparse
import json
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.errors import AutomationError
from content_automation.scraping import load_scrape_settings
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    akeneo_category_code,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Probe an Akeneo category query")
    parser.add_argument("--category", "-c", choices=SCRAPE_CATEGORIES, default=None)
    parser.add_argument("--style", "-s", default=None)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_scrape_settings(category_code=args.category, style_code=args.style)
    client = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=settings.channel_name,
    )
    client.authenticate()

    products = client.fetch_products(
        {
            "categories": [
                {
                    "operator": "IN",
                    "value": [akeneo_category_code(settings.category_code)],
                }
            ],
            "Style2": [{"operator": "IN", "value": [settings.style_code]}],
        }
    )
    print(f"Found {len(products)} matching products")
    if products:
        sample = products[0]
        print(
            json.dumps(
                {
                    "identifier": sample.get("identifier"),
                    "categories": sample.get("categories"),
                    "values": sample.get("values"),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
