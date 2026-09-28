"""Scrape four Modern lighting categories into category-locked Airtable rows."""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.style_this import StyleThisRunner


DEFAULT_STYLE_THIS_TABLE_ID = "tblvSAzXasTVI85r9"
STYLE_THIS_TABLE_ENV = "AIRTABLE_TABLE_ID_STYLE_THIS"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Pack Modern Floor Lamp, Table Lamp, Pendant Light and Chandelier "
            "products horizontally into Style This Airtable rows."
        )
    )
    parser.add_argument(
        "--style",
        default=None,
        help="Akeneo Style2 code (default: AKENEO_STYLE, normally modern)",
    )
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N complete/repairable Airtable rows",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override the Style This Airtable table ID for this run",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write rows and attachments; without this flag the run is read-only",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_pairs is not None and args.max_pairs < 1:
        raise SystemExit("--max-pairs must be at least 1")

    settings = load_settings()
    settings.require({"airtable", "akeneo"})
    style = (args.style or os.getenv("AKENEO_STYLE") or "modern").strip()
    table_id = (
        (args.table_id or "").strip()
        or (os.getenv(STYLE_THIS_TABLE_ENV) or "").strip()
        or DEFAULT_STYLE_THIS_TABLE_ID
    )
    channel = (os.getenv("CHANNEL_NAME") or "").strip()
    if not channel:
        raise AutomationError("Missing CHANNEL_NAME in .env")

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"[{mode}] Style This table={table_id}; style={style}")
    runner = StyleThisRunner(
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
        max_pairs=args.max_pairs,
    )
    return 0 if runner.run(execute=args.execute) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
