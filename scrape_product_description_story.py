"""Scrape products from Akeneo into Airtable for Product Closeup w/ Description tables.

Destination tables:
- Chandelier: ``tblDcT6jovdAbKnfw``
- Pendant Light: ``tblDD2w4v0Idb4jAZ``
- Floor Lamp: ``tblPvHyKGByWJCMtY``

Writable fields: ``Furniture Item`` (Attachment), ``Item Name`` (Text), ``SKU``, ``Status`` ("Standby")

Usage::

    python scrape_product_description_story.py
    python scrape_product_description_story.py --target pendant_lights --max-items 5
    python scrape_product_description_story.py --target floor_lamps --style modern
"""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import TABLES
from content_automation.errors import AutomationError
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import SCRAPE_CATEGORIES

PRODUCT_DESCRIPTION_TABLES: dict[str, dict[str, str]] = {
    "chandelier": {
        "category_code": "chandelier_product_description_story",
        "label": "Chandelier Product Closeup w/ Description",
        "default_table_id": "tblDcT6jovdAbKnfw",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION",
        "akeneo_category": "chandeliers",
    },
    "chandeliers": {
        "category_code": "chandelier_product_description_story",
        "label": "Chandelier Product Closeup w/ Description",
        "default_table_id": "tblDcT6jovdAbKnfw",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION",
        "akeneo_category": "chandeliers",
    },
    "pendant_light": {
        "category_code": "pendant_lights_product_description_story",
        "label": "Pendant Light Product Closeup w/ Description",
        "default_table_id": "tblDD2w4v0Idb4jAZ",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION",
        "akeneo_category": "pendant_lights",
    },
    "pendant_lights": {
        "category_code": "pendant_lights_product_description_story",
        "label": "Pendant Light Product Closeup w/ Description",
        "default_table_id": "tblDD2w4v0Idb4jAZ",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION",
        "akeneo_category": "pendant_lights",
    },
    "floor_lamp": {
        "category_code": "floor_lamp_product_description_story",
        "label": "Floor Lamp Product Closeup w/ Description",
        "default_table_id": "tblPvHyKGByWJCMtY",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION",
        "akeneo_category": "floor_lamps",
    },
    "floor_lamps": {
        "category_code": "floor_lamp_product_description_story",
        "label": "Floor Lamp Product Closeup w/ Description",
        "default_table_id": "tblPvHyKGByWJCMtY",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION",
        "akeneo_category": "floor_lamps",
    },
    "cluster_chandelier": {
        "category_code": "cluster_chandelier_product_description_story",
        "label": "Cluster Chandelier Product Closeup w/ Description",
        "default_table_id": "tblnIOQVywHcTgAtv",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION",
        "akeneo_category": "cluster_chandeliers",
    },
    "cluster_chandeliers": {
        "category_code": "cluster_chandelier_product_description_story",
        "label": "Cluster Chandelier Product Closeup w/ Description",
        "default_table_id": "tblnIOQVywHcTgAtv",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION",
        "akeneo_category": "cluster_chandeliers",
    },
    "table_lamp": {
        "category_code": "table_lamps_product_description_story",
        "label": "Table Lamps Product Closeup w/ Description",
        "default_table_id": "tbl5S9JEHSrjrLwxA",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION",
        "akeneo_category": "table_lamps",
    },
    "table_lamps": {
        "category_code": "table_lamps_product_description_story",
        "label": "Table Lamps Product Closeup w/ Description",
        "default_table_id": "tbl5S9JEHSrjrLwxA",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION",
        "akeneo_category": "table_lamps",
    },
    "wall_light": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
        "akeneo_category": "wall_lights",
    },
    "wall_lights": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
        "akeneo_category": "wall_lights",
    },
    "wall_sconces": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
        "akeneo_category": "wall_lights",
    },
}

DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"
STATUS_FIELD = "Status"
SELECT_STATUS = "Standby"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Scrape Akeneo products into Product Closeup w/ Description Airtable tables."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[
            "chandelier", "chandeliers",
            "pendant_light", "pendant_lights",
            "floor_lamp", "floor_lamps",
            "cluster_chandelier", "cluster_chandeliers",
            "table_lamp", "table_lamps",
            "wall_light", "wall_lights", "wall_sconces",
            "all",
        ],
        default="all",
        help="Target lighting product category to scrape (default: all)",
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
        type=int,
        default=None,
        metavar="N",
        help="Upload at most N new products per category",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    return parser.parse_args(argv)


def resolve_target_configs(target: str) -> list[dict[str, str]]:
    if target in ("all", None):
        return [
            PRODUCT_DESCRIPTION_TABLES["chandelier"],
            PRODUCT_DESCRIPTION_TABLES["pendant_lights"],
            PRODUCT_DESCRIPTION_TABLES["floor_lamps"],
            PRODUCT_DESCRIPTION_TABLES["cluster_chandeliers"],
            PRODUCT_DESCRIPTION_TABLES["table_lamps"],
            PRODUCT_DESCRIPTION_TABLES["wall_lights"],
        ]
    cfg = PRODUCT_DESCRIPTION_TABLES.get(target.lower())
    if not cfg:
        raise AutomationError(
            f"Unknown target '{target}'. Choose chandelier, pendant_lights, floor_lamps, cluster_chandeliers, table_lamps, or wall_lights."
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

        settings = load_scrape_settings(
            category_code=category_code,
            style_code=args.style,
            table_id_override=table_id,
        )

        print("=" * 64)
        print(f"Product Closeup w/ Description Scraper ({cfg['label']})")
        print(f"Destination: {settings.airtable_base_id} / {settings.airtable_table_id}")
        print(f"Akeneo Source Category: {cfg['akeneo_category']} | Style filter: {args.style}")
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
            settings.airtable_table_id,
        )

        runner = FurnitureItemScrapeRunner(
            akeneo,
            airtable,
            category_code=category_code,
            style_code=args.style,
            field_name=FIELD_NAME,
            item_name_field=ITEM_NAME_FIELD,
            sku_field=SKU_FIELD,
            status_field=STATUS_FIELD,
            default_status=SELECT_STATUS,
            include_product_type_in_name=True,
            max_items=args.max_items,
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
