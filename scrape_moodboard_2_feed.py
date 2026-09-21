"""Scrape products from Akeneo into Airtable for Moodboard #2 Feed.

Supported destination tables:
- Chandelier:      ``tbltWgQKOYjuHw6tx`` (default)
- Pendant Lights:  ``tbl4TiV90SzdBz4KG``
- Floor Lamp:      ``tbl4YF9iXlBqGblEc``
- Wall Lights:     ``tbljUk9JwzS1JeZJg``

Writable fields:
- ``Furniture Item``: single high-resolution product cut-out image
- ``Item Name``: combined product title and type (e.g. "Ulzanveris Deux | Pendant Light")
- ``Moodboard #2 Layout``: auto-attached reference photo (referencephoto_moodboard.png)
- ``Moodboard Converstion Fixed Prompt``: editorial flat-lay prompt JSON (second_moodboard.json)
- ``Status``: set to "Standby"

Usage::

    # 1. Scrape chandeliers (default):
    python scrape_moodboard_2_feed.py

    # 2. Scrape at most 3 pendant lights:
    python scrape_moodboard_2_feed.py --category pendant_lights --max-items 3

    # 3. Scrape floor lamps with custom table override:
    python scrape_moodboard_2_feed.py --category floor_lamps --table-id tbl4YF9iXlBqGblEc
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from content_automation.akeneo_client import AkeneoClient
from content_automation.errors import AutomationError
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)

MOODBOARD_2_FEED_PRESETS = {
    "chandeliers": {
        "category_code": "chandeliers",
        "label": "Chandelier",
        "default_table_id": "tbltWgQKOYjuHw6tx",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_MOODBOARD_2_FEED",
        "aliases": ["chandelier", "chandeliers", "1"],
    },
    "pendant_lights": {
        "category_code": "pendant_lights",
        "label": "Pendant Lights",
        "default_table_id": "tbl4TiV90SzdBz4KG",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARD_2_FEED",
        "aliases": ["pendant", "pendant_lights", "pendant_light", "2"],
    },
    "floor_lamps": {
        "category_code": "floor_lamps",
        "label": "Floor Lamps",
        "default_table_id": "tbl4YF9iXlBqGblEc",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMPS_MOODBOARD_2_FEED",
        "aliases": ["floor_lamp", "floor_lamps", "3"],
    },
    "wall_lights": {
        "category_code": "wall_lights",
        "label": "Wall Lights",
        "default_table_id": "tbljUk9JwzS1JeZJg",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_MOODBOARD_2_FEED",
        "aliases": ["wall_light", "wall_lights", "wall_sconces", "wall_sconce", "4"],
    },
}

DEFAULT_CATEGORY = "chandeliers"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
STATUS_FIELD = "Status"
SELECT_STATUS = "Standby"
MOODBOARD_LAYOUT_FIELD = "Moodboard #2 Layout"

DEFAULT_LAYOUT_FIELDS = {
    MOODBOARD_LAYOUT_FIELD: "multipleAttachments",
}


def resolve_preset(category_or_key: str | None) -> dict:
    """Resolve category or key to a valid preset dictionary."""
    if not category_or_key:
        return MOODBOARD_2_FEED_PRESETS[DEFAULT_CATEGORY]
    raw = category_or_key.strip().lower()
    if raw in MOODBOARD_2_FEED_PRESETS:
        return MOODBOARD_2_FEED_PRESETS[raw]
    for key, preset in MOODBOARD_2_FEED_PRESETS.items():
        if raw in preset["aliases"] or raw == preset["category_code"]:
            return preset
        t_id = os.getenv(preset["env_table_key"], "").strip() or preset["default_table_id"]
        if raw == t_id.lower():
            return preset
    return MOODBOARD_2_FEED_PRESETS[DEFAULT_CATEGORY]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Scrape Akeneo product images and names into Airtable for Moodboard #2 Feed, "
            "auto-fill Moodboard #2 Layout, and set Status to Standby."
        )
    )
    parser.add_argument(
        "--category",
        "-c",
        default=DEFAULT_CATEGORY,
        help="Category to scrape (chandeliers, pendant_lights, floor_lamps, wall_lights, or 'all')",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Style code filter in Akeneo (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--max-items",
        "-n",
        type=int,
        default=None,
        metavar="N",
        help="Upload at most N new product images in total",
    )
    parser.add_argument(
        "--starting-letter",
        default=None,
        help="Starting letter for A-Z sorting cycle",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="Skip backfilling missing layout attachments on existing records",
    )
    parser.add_argument(
        "--no-shopify-check",
        action="store_true",
        help="Skip Shopify published status cross-check",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    if args.category == "all":
        categories = list(MOODBOARD_2_FEED_PRESETS.keys())
    else:
        preset = resolve_preset(args.category)
        categories = [preset["category_code"]]

    overall_success = True
    items_remaining = args.max_items

    for category_code in categories:
        cat_preset = resolve_preset(category_code)
        table_id = (
            args.table_id
            or os.getenv(cat_preset["env_table_key"], "").strip()
            or cat_preset["default_table_id"]
        )

        settings = load_scrape_settings(
            category_code=cat_preset["category_code"],
            style_code=args.style,
            table_id_override=table_id,
        )

        print("\n" + "=" * 64)
        print("Moodboard #2 Feed Akeneo Scraper")
        print(f"Target Category     : {cat_preset['label']} ({cat_preset['category_code']})")
        print(f"Airtable Table ID   : {table_id}")
        print(f"Style filter        : {args.style}")
        print(f"Layout auto-backfill: {'Enabled' if not args.no_backfill else 'Disabled'}")
        print(f"Shopify cross-check : {'Enabled' if not args.no_shopify_check else 'Disabled'}")
        print("=" * 64)

        akeneo = AkeneoClient(
            settings.akeneo_host,
            settings.akeneo_client_id,
            settings.akeneo_secret,
            settings.akeneo_username,
            settings.akeneo_password,
            channel_name=settings.channel_name,
        )
        airtable = ScrapeAirtableClient(
            settings.airtable_token,
            settings.airtable_base_id,
            table_id,
        )

        runner = FurnitureItemScrapeRunner(
            akeneo,
            airtable,
            category_code=cat_preset["category_code"],
            style_code=args.style,
            field_name=FIELD_NAME,
            item_name_field=ITEM_NAME_FIELD,
            sku_field=None,
            status_field=STATUS_FIELD,
            default_status=SELECT_STATUS,
            layout_fields=DEFAULT_LAYOUT_FIELDS,
            backfill_layouts=not args.no_backfill,
            shopify_cross_check=not args.no_shopify_check,
            include_product_type_in_name=True,
            max_items=items_remaining,
        )
        if not runner.run():
            overall_success = False

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
