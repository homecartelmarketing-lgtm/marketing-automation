"""Scrape products from Akeneo into Airtable for Product Closeup w/ Specs tables.

Destination tables:
- Chandelier: ``tblEGTB6BodRVDqBV`` (Product Closeup w/ Specification Chandelier)

Writable fields:
- ``Furniture item`` (Attachment)
- ``Item Name`` (Text)
- ``Product Closeup w/ Specs Layout`` (Attachment, layout image "product_specs_layout.png")
- ``Status`` (SingleSelect, "Standby")

Deduplication:
- Local table deduplication (filenames, item names, SKUs)
- Cross-table Airtable base deduplication (scans all tables across the base)
- Shopify Catalog cross-check (verifies published & active on homecartel.net, skipping drafts/inactive)

Usage::

    python scrape_product_specs_story.py
    python scrape_product_specs_story.py --target chandeliers --max-items 1
    python scrape_product_specs_story.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import SCRAPE_CATEGORIES

PRODUCT_SPECS_TABLES: dict[str, dict[str, str]] = {
    "chandelier": {
        "category_code": "chandelier_product_specs_story",
        "label": "Chandelier Product Closeup w/ Specs",
        "default_table_id": "tblEGTB6BodRVDqBV",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_SPECS",
        "akeneo_category": "chandeliers",
    },
    "chandeliers": {
        "category_code": "chandelier_product_specs_story",
        "label": "Chandelier Product Closeup w/ Specs",
        "default_table_id": "tblEGTB6BodRVDqBV",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_SPECS",
        "akeneo_category": "chandeliers",
    },
}

DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
FIELD_NAME = "Furniture item"
ITEM_NAME_FIELD = "Item Name"
STATUS_FIELD = "Status"
SELECT_STATUS = "Standby"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Scrape Akeneo products into Product Closeup w/ Specs Airtable tables."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[
            "chandelier", "chandeliers",
            "all",
        ],
        default="chandeliers",
        help="Target lighting product category to scrape (default: chandeliers)",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=[*SCRAPE_CATEGORIES, "all"],
        default=None,
        help="Akeneo category code override",
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
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Upload at most N new products per category",
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
        "--no-cross-dedup",
        action="store_true",
        help="Disable base-wide cross-table deduplication (check current table only)",
    )
    parser.add_argument(
        "--no-shopify-check",
        action="store_true",
        help="Disable Shopify published catalog verification",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate scraping and deduplication without modifying Airtable",
    )
    return parser.parse_args(argv)


def resolve_target_configs(target: str) -> list[dict[str, str]]:
    if target in ("all", None):
        return [
            PRODUCT_SPECS_TABLES["chandeliers"],
        ]
    cfg = PRODUCT_SPECS_TABLES.get(target.lower())
    if not cfg:
        raise AutomationError(
            f"Unknown target '{target}'. Choose chandelier or chandeliers."
        )
    return [cfg]


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    configs = resolve_target_configs(args.target)
    overall_success = True

    for cfg in configs:
        table_id = args.table_id or os.getenv(cfg["env_table_key"], "").strip() or cfg["default_table_id"]
        category_code = cfg["category_code"]

        settings = load_settings()
        scrape_settings = load_scrape_settings(
            category_code=category_code,
            style_code=args.style,
            table_id_override=table_id,
            settings=settings,
        )

        print("=" * 68)
        print(f"Product Closeup w/ Specs Scraper ({cfg['label']})")
        print(f"Destination Table: {scrape_settings.airtable_base_id} / {scrape_settings.airtable_table_id}")
        print(f"Akeneo Category: {cfg['akeneo_category']} | Style filter: {args.style}")
        print(f"Shopify Cross-Check : {'Enabled' if not args.no_shopify_check else 'Disabled'}")
        print(f"Cross-Table Dedup   : {'Enabled' if not args.no_cross_dedup else 'Disabled'}")
        print("Auto-Attachment     : 'product_specs_layout.png' -> 'Product Closeup w/ Specs Layout'")
        print("=" * 68)

        akeneo = AkeneoClient(
            scrape_settings.akeneo_host,
            scrape_settings.akeneo_client_id,
            scrape_settings.akeneo_secret,
            scrape_settings.akeneo_username,
            scrape_settings.akeneo_password,
            channel_name=scrape_settings.channel_name,
        )
        airtable = ScrapeAirtableClient(
            scrape_settings.airtable_token,
            scrape_settings.airtable_base_id,
            scrape_settings.airtable_table_id,
        )

        # Check if table already has a SKU field
        sku_field = "SKU" if airtable.has_field("SKU") else None

        runner = FurnitureItemScrapeRunner(
            akeneo,
            airtable,
            category_code=category_code,
            style_code=args.style,
            field_name=FIELD_NAME,
            item_name_field=ITEM_NAME_FIELD,
            sku_field=sku_field,
            status_field=STATUS_FIELD,
            default_status=SELECT_STATUS,
            include_product_type_in_name=True,
            max_items=args.max_items,
            cross_table_dedup=not args.no_cross_dedup,
            shopify_cross_check=not args.no_shopify_check,
        )

        if not runner.run(execute=not args.dry_run):
            overall_success = False

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
