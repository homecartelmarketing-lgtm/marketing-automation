"""Scrape Modern lighting products into Tips and Edu Feeds Airtable rows (4 items per row)."""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.tips_and_edu import TipsAndEduRunner

DEFAULT_TABLE_ID = "tblEy5batpOObnZ4J"
TABLE_PRESETS: dict[str, str] = {
    "chandeliers": "tblEy5batpOObnZ4J",
    "pendant_lights": "tblIhCP3Gjg09QFCK",
}
TABLE_ENV_CHANDELIER = "AIRTABLE_TABLE_ID_TIPS_EDUCATIONAL_FEED"
TABLE_ENV_PENDANT = "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDUCATIONAL_FEED"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Pack Modern lighting products into Tips & Edu Feeds Airtable rows "
            "(4 items per row: Furniture Item 1..4, Item Name 1..4)."
        )
    )
    parser.add_argument(
        "--category",
        "-c",
        default="chandeliers",
        choices=("chandeliers", "pendant_lights"),
        help="Akeneo category code (default: chandeliers)",
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=("chandeliers", "pendant_lights", "1", "2"),
        default=None,
        help="Target category preset (1: chandeliers, 2: pendant_lights)",
    )
    parser.add_argument(
        "--style",
        default=None,
        help="Akeneo Style2 code (default: AKENEO_STYLE, normally modern)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N complete Airtable rows",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override the Tips & Edu Airtable table ID for this run",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for product shuffling",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write rows and attachments; without this flag the run is read-only",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_rows is not None and args.max_rows < 1:
        raise SystemExit("--max-rows must be at least 1")

    category = args.category
    if args.target:
        if args.target in ("2", "pendant_lights"):
            category = "pendant_lights"
        elif args.target in ("1", "chandeliers"):
            category = "chandeliers"

    settings = load_settings()
    settings.require({"airtable", "akeneo"})
    style = (args.style or os.getenv("AKENEO_STYLE") or "modern").strip()
    
    if args.table_id:
        table_id = args.table_id.strip()
    elif category == "pendant_lights":
        table_id = (os.getenv(TABLE_ENV_PENDANT) or "").strip() or TABLE_PRESETS["pendant_lights"]
    else:
        table_id = (os.getenv(TABLE_ENV_CHANDELIER) or "").strip() or TABLE_PRESETS["chandeliers"]

    channel = (os.getenv("CHANNEL_NAME") or "").strip()
    if not channel:
        raise AutomationError("Missing CHANNEL_NAME in .env")

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(
        f"[{mode}] Tips & Edu Feeds table={table_id}; "
        f"category={category}; style={style}"
    )
    runner = TipsAndEduRunner(
        AkeneoClient(
            settings.akeneo_host,
            settings.akeneo_client_id,
            settings.akeneo_secret,
            settings.akeneo_username,
            settings.akeneo_password,
            channel_name=channel,
        ),
        ScrapeAirtableClient(
            settings.airtable_token,
            settings.airtable_base_id,
            table_id,
        ),
        style_code=style,
        max_rows=args.max_rows,
        seed=args.seed,
        categories_list=(category,),
    )

    return 0 if runner.run(execute=args.execute) else 1



if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
