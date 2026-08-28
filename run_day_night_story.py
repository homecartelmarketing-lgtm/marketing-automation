"""End-to-End CLI Runner for Day & Night Story Pipeline.

Workflow:
  1. Auto-Scrape (if needed): Scrapes new unique product(s) from Akeneo -> Airtable (Status: 'Standby')
  2. [Phase 1/4] Krea AI Interior Generation -> 'Interior Generated Photo'
  3. [Phase 2/4] Fal AI Claude Sonnet 5 Prompt Generation -> 'Blending Prompt'
  4. [Phase 3/4] Fal AI Nano Banana Pro Daytime Blending -> 'day_photo_raw.jpg'
  5. [Phase 4/4] Fal AI Nano Banana Pro Night Transformation -> 'night_photo.jpg'
  6. [Logo Overlay] Stamping 'Logo' attachment at top-right (X=781.7, Y=108) -> 'day_photo.jpg'
  7. [Upload & Complete] Uploads both images to 'STORY - Day & Night (2)' & sets Status to 'Complete'.

Usage::

    # Interactive table selection:
    python run_day_night_story.py

    # Target specific lighting category:
    python run_day_night_story.py --target chandeliers
    python run_day_night_story.py --target pendant_lights
    python run_day_night_story.py --target table_lamps
    python run_day_night_story.py --target floor_lamps
    python run_day_night_story.py --target cluster_chandeliers

    # Run specific number of rows sequentially:
    python run_day_night_story.py --target chandeliers --limit 3

    # Run on a specific Airtable Record ID:
    python run_day_night_story.py --record-id rechngJM56W0l7aKn

    # Dry run (test only, no API calls or Airtable writes):
    python run_day_night_story.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.airtable_client import AirtableClient
from content_automation.config import (
    TABLES,
    DAY_NIGHT_STORY_TABLES,
    load_settings,
    resolve_day_night_story_table,
)
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner
from run_content_automation import main as automation_main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Day & Night Story: End-to-end automated scraping & generation pipeline."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[
            "1", "2", "3", "4", "5",
            "chandeliers", "chandelier",
            "pendant_lights", "pendant_light", "pendant",
            "table_lamps", "table_lamp", "table",
            "floor_lamps", "floor_lamp", "floor",
            "cluster_chandeliers", "cluster_chandelier", "cluster",
            "tblodnfanvp6sxn0a", "tblanyyzcr7e6txtv", "tblenvluwdfqwdj08",
            "tbldzp777tozevmvu", "tblfcavauxzyghat9",
        ],
        default=None,
        help="Target lighting category / table (default: interactive prompt or chandelier)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override destination Airtable Table ID",
    )
    parser.add_argument(
        "--limit",
        "--batch-size",
        "-n",
        dest="batch_size",
        type=int,
        default=1,
        help="Number of rows to process sequentially (default: 1)",
    )
    parser.add_argument(
        "--record-id",
        "-r",
        action="append",
        default=[],
        help="Specific Airtable Record ID to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a test run without paid API calls or Airtable writes",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip auto-scraping even if there are no pending rows in Airtable",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape products from Akeneo into Airtable without running generation",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if already completed",
    )
    parser.add_argument(
        "--style",
        default="modern",
        help="Akeneo style filter (default: modern)",
    )
    return parser.parse_args(argv)


def get_standby_record_count(settings, table_def) -> int:
    """Check how many records currently have Status == 'Standby'."""
    client = AirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_def,
    )
    records = client.list_records(
        fields=["Status"],
        formula="{Status}='Standby'",
    )
    return len(records)


def scrape_new_products(settings, table_id: str, akeneo_cat: str, count: int, style: str) -> bool:
    """Scrape unique products from Akeneo into Airtable with Status 'Standby'."""
    print(f"\n[PHASE 0: SCRAPE] Checking & scraping {count} new product(s) from Akeneo (category={akeneo_cat}, style={style})...")
    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )
    runner = FurnitureItemScrapeRunner(
        akeneo,
        airtable,
        category_code=akeneo_cat,
        style_code=style,
        field_name="Furniture Item",
        item_name_field="Item Name",
        sku_field="SKU",
        status_field="Status",
        default_status="Standby",
        include_product_type_in_name=True,
        max_items=count,
    )
    return runner.run()


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_settings()

    selected_preset = resolve_day_night_story_table(
        target_arg=args.target,
        prompt_if_interactive=not args.dry_run and not args.target and not args.table_id and not args.record_id,
    )
    table_code = selected_preset["table_code"]
    table_def = TABLES.get(table_code, TABLES["chandelier_day_night_story"])
    table_id = args.table_id or os.getenv(selected_preset.get("env_table_key", ""), "").strip() or table_def.table_id
    cat_code = selected_preset.get("category_code", "chandeliers")
    akeneo_cat = akeneo_category_code(cat_code)

    print("\n" + "=" * 64)
    print(" HomeCartel - Day & Night Story End-to-End Pipeline")
    print(f" Target Preset: {selected_preset['label']}")
    print(f" Target Table ID: {table_id}")
    print(f" Category: {cat_code} (Akeneo: {akeneo_cat})")
    print(f" Mode: {'DRY RUN (Simulation)' if args.dry_run else 'LIVE EXECUTION'}")
    print(f" Batch Size: {args.batch_size} row(s)")
    if args.record_id:
        print(f" Target Record(s): {', '.join(args.record_id)}")
    print("=" * 64)

    # 1. Check if we need to scrape new products from Akeneo
    if not args.dry_run and not args.record_id and not args.no_scrape:
        standby_count = get_standby_record_count(settings, table_def)
        if standby_count < args.batch_size:
            needed = args.batch_size - standby_count
            print(f"[INFO] Found {standby_count} 'Standby' row(s). Auto-scraping {needed} new item(s) from Akeneo...")
            success = scrape_new_products(settings, table_id, akeneo_cat, needed, args.style)
            if not success:
                print("[WARN] Akeneo scrape returned no new items or encountered an issue.")
        else:
            print(f"[INFO] Found {standby_count} existing 'Standby' row(s) ready for generation.")

    if args.scrape_only:
        print("\n[OK] Scrape complete. Exiting (--scrape-only).")
        return 0

    # 2. Run the Generation Pipeline via content_automation generic runner
    forward_args = [
        "--phase", "stories",
        "--assignment", table_code,
        "--batch-size", str(args.batch_size),
    ]
    if not args.dry_run:
        forward_args.append("--execute")
    if args.force:
        forward_args.append("--force")
    for rid in args.record_id:
        forward_args.extend(["--record-id", rid])

    return automation_main(forward_args)


if __name__ == "__main__":
    sys.exit(main())
