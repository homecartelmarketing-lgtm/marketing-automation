"""End-to-End CLI Runner for Moodboard Story Pipeline.

Workflow:
  1. Ingestion: Scrapes unique product(s) from Akeneo -> Airtable (Status: 'Standby')
  2. [Phase 1/5] Krea AI 9:16 Vertical Interior Generation -> 'Interior Generated'
  3. [Phase 2/5] Fal AI Claude Sonnet 5 Prompt Generation -> 'Generated Prompt'
  4. [Phase 3/5] Fal AI Nano Banana Pro 9:16 Daytime Blending -> 'Blended Image'
  5. [Phase 4/5] Local PIL Logo Overlay Stamping (top-right X=781.7, Y=108) -> 'Homecartel Logo Overlay'
  6. [Phase 5/5] Fal AI Nano Banana Pro Moodboard Card Conversion -> 'Moodboard Converted'
  7. [Upload & Complete] Sets Status to 'Complete'.

Usage::

    # Interactive table selection:
    python run_moodboard_story.py

    # Target Pendant Light table (auto-scrapes Akeneo pendant lights):
    python run_moodboard_story.py --target pendant_lights

    # Target Chandelier table:
    python run_moodboard_story.py --target chandeliers

    # Run specific number of rows:
    python run_moodboard_story.py --target pendant_lights --batch-size 3

    # Run on a specific Airtable Record ID:
    python run_moodboard_story.py --record-id recXXXXXXXXXXXXXX

    # Dry run (test only, no API calls or Airtable writes):
    python run_moodboard_story.py --target pendant_lights --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from content_automation.akeneo_client import AkeneoClient
from content_automation.airtable_client import AirtableClient
from content_automation.config import (
    TABLES,
    MOODBOARD_STORY_TABLES,
    load_settings,
    resolve_moodboard_story_table,
)
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner
from run_content_automation import main as automation_main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Moodboard Story: End-to-end automated scraping & generation pipeline."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[
            "1", "2",
            "chandeliers", "chandelier",
            "pendant_lights", "pendant_light", "pendant",
            "tblhqrci8d1k9ws2m", "tblkm119i48y0m1iq",
        ],
        default=None,
        help="Target lighting category / table (default: interactive prompt or pendant_lights)",
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
        "-b",
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
        "-s",
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
    print(f"\n+------------------------------------------------------------------------------+")
    print(f"| STEP 0: AKENEO PRODUCT INGESTION                                             |")
    print(f"+------------------------------------------------------------------------------+")
    print(f"  * Category:     {akeneo_cat} (Style: {style})")
    print(f"  * Destination:  Table ID {table_id}")
    print(f"  * Items Needed: {count} product(s)")
    print(f"  ... Querying Akeneo PIM catalog and deduplicating against Airtable base ...")
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

    selected_preset = resolve_moodboard_story_table(
        target_arg=args.target,
        prompt_if_interactive=not args.dry_run and not args.target and not args.table_id and not args.record_id,
    )
    table_code = selected_preset["table_code"]
    table_def = TABLES.get(table_code, TABLES["pendant_lights_moodboard_story"])
    table_id = args.table_id or os.getenv(selected_preset.get("env_table_key", ""), "").strip() or table_def.table_id
    cat_code = selected_preset.get("category_code", "pendant_lights")
    akeneo_cat = akeneo_category_code(cat_code)
    mb_id = os.getenv(selected_preset.get("moodboard_env_key", ""), "").strip() or selected_preset.get("default_moodboard_id", "")
    interior_prompt = selected_preset.get("interior_prompt", "")

    mode_label = "DRY RUN (Simulation - No API Costs)" if args.dry_run else "LIVE EXECUTION (Airtable & API Calls Active)"

    print("\n================================================================================")
    print("                 HOMECARTEL • MOODBOARD STORY AUTOMATION                        ")
    print("                       9:16 Vertical Instagram Story                            ")
    print("================================================================================")
    print(f"  [Preset]           {selected_preset['label']}")
    print(f"  [Category]         {cat_code} (Akeneo: {akeneo_cat})")
    print(f"  [Table ID]         {table_id}")
    print(f"  [Krea Moodboard]   {mb_id}")
    print(f"  [Interior Prompt]  \"{interior_prompt}\"")
    print(f"  [Execution Mode]   {mode_label}")
    print(f"  [Batch Size]       {args.batch_size} row(s)")
    if args.record_id:
        print(f"  [Target Record(s)] {', '.join(args.record_id)}")
    print("================================================================================")

    # 1. Check if we need to scrape new products from Akeneo
    if not args.dry_run and not args.record_id and not args.no_scrape:
        standby_count = get_standby_record_count(settings, table_def)
        if standby_count < args.batch_size:
            needed = args.batch_size - standby_count
            print(f"\n[INFO] Found {standby_count} 'Standby' row(s). Auto-scraping {needed} new item(s) from Akeneo...")
            success = scrape_new_products(settings, table_id, akeneo_cat, needed, args.style)
            if not success:
                print("[WARN] Akeneo scrape returned no new items or encountered an issue.")
        else:
            print(f"\n[INFO] Found {standby_count} existing 'Standby' row(s) ready in Airtable.")

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
