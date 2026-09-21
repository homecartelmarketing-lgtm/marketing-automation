"""Run Full End-to-End Moodboard #1 Feed Automation.

Workflow:
1. Scrapes 1 (or N) new product(s) from Akeneo into Airtable (tbl9u5vjgx8kuE44R).
   - Populates: Furniture Item, Item Name, SKU, Moodboard Layout, Closeup Photo Layout, Logo.
   - Sets Status = 'Standby'.
2. Runs the full 6-phase AI & Local Composite Generation:
   - Phase 1: Krea AI Room Interior Generation (4:5) -> 'Interior Generated'
   - Phase 2: Claude Sonnet 5 Prompt Generation -> 'Prompt for Blending'
   - Phase 3: Fal AI Nano Banana Pro Blending (4:5 1k) -> 'Moodboard V1 Blended'
   - Phase 4: Local PIL Logo Stamping (Canva Box 190.3x63.5 @ 108, 1178.5) -> 'Moodboard Added Watermark'
   - Phase 5: Fal AI Nano Banana Pro 3-Swatch Moodboard Conversion (4:5 1k) -> 'Moodboard Converted'
   - Phase 6: Fal AI Nano Banana Pro Macro Close-up Photo (4:5 1k) -> 'Closeup Photo', Status -> 'Complete'

Usage:
    # 1. Run 1 item end-to-end (default: modern chandeliers):
    python run_full_moodboard_1_feed.py

    # 2. Run 1 item for specific lighting category:
    python run_full_moodboard_1_feed.py --category pendant_lights
    python run_full_moodboard_1_feed.py --category floor_lamps
    python run_full_moodboard_1_feed.py --category table_lamps
    python run_full_moodboard_1_feed.py --category wall_lights

    # 3. Process N items (e.g. 3 products):
    python run_full_moodboard_1_feed.py --max-items 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scrape_moodboard_1_feed import main as run_scraper
from generate_moodboard_1_feed import main as run_pipeline


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Full End-to-End Moodboard #1 Feed Automation: Scrape 1 item -> Generate all 4 slides -> Complete."
    )
    parser.add_argument(
        "--category",
        "-c",
        default="chandeliers",
        help="Category to scrape (default: chandeliers)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default="modern",
        help="Style filter in Akeneo (default: modern)",
    )
    parser.add_argument(
        "--max-items",
        "-n",
        "--count",
        type=int,
        default=1,
        help="Number of items to scrape & process in this run (default: 1)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override Airtable destination table ID",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping new products and only process existing Standby records",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="Skip backfilling missing layouts on existing records",
    )
    parser.add_argument(
        "--no-shopify-check",
        action="store_true",
        help="Skip Shopify published status cross-check",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Override Krea AI moodboard ID",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Override Krea AI interior generation prompt",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    print("\n" + "=" * 64)
    print("🚀 MOODBOARD #1 FEED | FULL END-TO-END AUTOMATION")
    print(f"Target Category : {args.category}")
    print(f"Style Filter    : {args.style}")
    print(f"Item Count      : {args.max_items} product(s)")
    if args.moodboard_id:
        print(f"Moodboard ID    : {args.moodboard_id}")
    if args.prompt:
        print(f"Custom Prompt   : {args.prompt}")
    print("=" * 64 + "\n")

    # Step 1: Scrape from Akeneo into Airtable (if not skipped)
    if not args.skip_scrape:
        print("[STEP 1/2] Ingesting product(s) from Akeneo into Airtable...")
        scraper_argv = [
            "--category", args.category,
            "--style", args.style,
            "--max-items", str(args.max_items),
        ]
        if args.table_id:
            scraper_argv.extend(["--table-id", args.table_id])
        if args.no_backfill:
            scraper_argv.append("--no-backfill")
        if args.no_shopify_check:
            scraper_argv.append("--no-shopify-check")

        scrape_code = run_scraper(scraper_argv)
        if scrape_code != 0:
            print(f"[ERROR] Scrape step failed with exit code {scrape_code}")
            return scrape_code
    else:
        print("[STEP 1/2] Skipping scrape step as requested (--skip-scrape).")

    # Step 2: Run Full 6-Phase AI Generation Pipeline
    print("\n[STEP 2/2] Running 6-Phase AI Generation & Blending Pipeline...")
    pipeline_argv = [
        "--max-items", str(args.max_items),
    ]
    if args.table_id:
        pipeline_argv.extend(["--table-id", args.table_id])
    if args.moodboard_id:
        pipeline_argv.extend(["--moodboard-id", args.moodboard_id])
    if args.prompt:
        pipeline_argv.extend(["--prompt", args.prompt])

    pipeline_code = run_pipeline(pipeline_argv)
    if pipeline_code != 0:
        print(f"[ERROR] Pipeline step failed with exit code {pipeline_code}")
        return pipeline_code

    print("\n" + "=" * 64)
    print("✨ END-TO-END RUN COMPLETE!")
    print("Check your Airtable table (tbl9u5vjgx8kuE44R) to inspect all 4 generated slides:")
    print("  1. Moodboard V1 Blended")
    print("  2. Moodboard Added Watermark")
    print("  3. Moodboard Converted")
    print("  4. Closeup Photo -> Status: Complete")
    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
