"""End-to-End CLI Runner for Myth & Fact Story Pipeline.

Workflow:
  1. Auto-Scrape (if needed): Scrapes new unique product(s) from Akeneo -> Airtable (Status: 'Standby')
  2. [Slide 1] Fal AI Debunk Cover Slide -> 'debunk_layout.jpg'
  3. [Slide 2] Fal AI Nano Banana Pro Myth Slide -> 'myth_blended.jpg' & 'myth1.jpg'
  4. [Slide 3] Fal AI Nano Banana Pro Fact Slide -> 'fact_blended.jpg' & 'fact1.jpg'
  5. [Slide 4] Fal AI Outro Slide -> 'outro.jpg'
  6. [Upload & Complete] Uploads all 4 slides to 'STORY - Myth & Fact (4)' & sets Status to 'Complete'.

Usage::

    # Run 1 row end-to-end (Auto-scrapes from Akeneo if no Standby row exists):
    python run_myth_and_fact_story.py

    # Run specific number of rows:
    python run_myth_and_fact_story.py --batch-size 3

    # Run on a specific Airtable Record ID:
    python run_myth_and_fact_story.py --record-id recBOCgsmJGNOxlhu

    # Dry run (test only, no API calls or Airtable writes):
    python run_myth_and_fact_story.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.airtable_client import AirtableClient
from content_automation.config import (
    TABLES,
    load_settings,
)
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner
from run_content_automation import main as automation_main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Myth & Fact Story: End-to-end automated scraping & generation pipeline."
    )
    parser.add_argument(
        "--category",
        "-c",
        default="chandelier_myth_and_fact_story",
        help="Target table code (default: chandelier_myth_and_fact_story)",
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=1,
        help="Number of records to process (default: 1)",
    )
    parser.add_argument(
        "--record-id",
        "-r",
        action="append",
        default=[],
        help="Target specific Airtable record ID(s). Repeatable.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without calling paid APIs or mutating Airtable.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even if already completed or state is locked.",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip auto-scraping even if there are 0 Standby records.",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape Akeneo products into Airtable, do not generate.",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=None,
        help="Override Akeneo style filter (e.g., modern, japandi, minimalist)",
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

    table_code = args.category.lower().strip()
    if table_code not in TABLES:
        # Try finding match
        for code in TABLES:
            if table_code in code and "myth" in code:
                table_code = code
                break
    table_def = TABLES.get(table_code, TABLES["chandelier_myth_and_fact_story"])
    table_id = table_def.table_id
    cat_code = "chandeliers"
    akeneo_cat = akeneo_category_code(cat_code)
    style_filter = (args.style or os.getenv("AKENEO_STYLE") or "modern").strip()

    print("\n" + "=" * 64)
    print(" [HOMECARTEL] MYTH & FACT STORY AUTOMATION PIPELINE")
    print(f" Table   : {table_def.label}")
    print(f" Category: {cat_code} (Style: {style_filter})")
    print(f" Mode    : {'DRY RUN (Simulation)' if args.dry_run else 'LIVE EXECUTION'}")
    print(f" Rows    : {args.batch_size} row(s)")
    if args.record_id:
        print(f" Target  : {', '.join(args.record_id)}")
    print("=" * 64)

    # 1. Check if we need to scrape new products from Akeneo
    if not args.dry_run and not args.record_id and not args.no_scrape:
        standby_count = get_standby_record_count(settings, table_def)
        if standby_count < args.batch_size:
            needed = args.batch_size - standby_count
            print(f"\n[STEP 1/2] Checking rows: Found {standby_count} Standby row(s). Auto-scraping {needed} new product(s) from Akeneo...")
            success = scrape_new_products(settings, table_id, akeneo_cat, needed, style_filter)
            if not success:
                print("[WARN] No new products found or scrape returned no items.")
        else:
            print(f"\n[STEP 1/2] Found {standby_count} Standby row(s) ready in Airtable.")

    if args.scrape_only:
        print("\n[OK] Scrape complete. Exiting (--scrape-only).")
        return 0

    # 2. Run the Generation Pipeline via content_automation generic runner
    forward_args = [
        "--phase", "stories",
        "--assignment", "myth_and_fact_story",
        "--category", table_code,
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
