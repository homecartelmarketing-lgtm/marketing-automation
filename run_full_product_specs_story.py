"""End-to-end 2-step automation for Product Closeup w/ Specs Story:
1. Scrape item from Akeneo into Airtable (Furniture item + Product Closeup w/ Specs Layout) with comprehensive deduplication.
2. Generate blended story card via Fal AI Nano Banana Pro (using product_closeup_specs.json) -> 'PCS Story' field, Status -> 'Done'.

Usage::

    python run_full_product_specs_story.py
    python run_full_product_specs_story.py --count 1
    python run_full_product_specs_story.py --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

from scrape_product_specs_story import main as run_scraper
from generate_product_specs_story_pipeline import main as run_pipeline


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run end-to-end 2-step automation: Scrape -> Generate PCS Story via Fal AI Nano Banana Pro."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["chandelier", "chandeliers", "all"],
        default="chandeliers",
        help="Target lighting category (default: chandeliers)",
    )
    parser.add_argument(
        "--count",
        "-n",
        "--limit",
        "--max-items",
        type=int,
        default=1,
        help="Number of items to scrape & process (default: 1)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default="modern",
        help="Akeneo Style filter (default: modern)",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Process a specific Airtable record ID (skips scrape step)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override destination Airtable Table ID",
    )
    parser.add_argument(
        "--model",
        default="fal-ai/nano-banana-pro/edit",
        help="Fal AI model code (default: fal-ai/nano-banana-pro/edit)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    print("\n" + "=" * 80)
    print(f"🚀 STARTING END-TO-END AUTOMATION FOR '{args.target.upper()}' (Count: {args.count})")
    print(f"Workflow: Scrape -> Nano Banana Pro Blending -> 'PCS Story' (Status: Done)")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 1: Scrape Item from Akeneo into Airtable (with comprehensive deduplication)
    # -------------------------------------------------------------------------
    if not args.record_id:
        print(f"\n📥 [STEP 1/2] Scraping {args.count} product item(s) from Akeneo into Airtable...")
        scrape_argv = ["--target", args.target, "--max-items", str(args.count), "--style", args.style]
        if args.table_id:
            scrape_argv.extend(["--table-id", args.table_id])
        scrape_exit_code = run_scraper(scrape_argv)
        if scrape_exit_code != 0:
            print(f"❌ [ERROR] Scraping failed with exit code {scrape_exit_code}.")
            return scrape_exit_code
        print("✅ [STEP 1/2 COMPLETE] Scraped product item + layout into Airtable.")
    else:
        print(f"\n⏩ [STEP 1/2 SKIPPED] Targeted specific Record ID: {args.record_id}")

    # -------------------------------------------------------------------------
    # STEP 2: Fal AI Nano Banana Pro Blending -> 'PCS Story'
    # -------------------------------------------------------------------------
    print(f"\n🎨 [STEP 2/2] Blending images via Fal AI Nano Banana Pro ({args.model}) -> 'PCS Story'...")
    pipeline_argv = ["--target", args.target, "--limit", str(args.count), "--model", args.model]
    if args.record_id:
        pipeline_argv.extend(["--record-id", args.record_id])
    if args.table_id:
        pipeline_argv.extend(["--table-id", args.table_id])
    pipeline_exit_code = run_pipeline(pipeline_argv)
    if pipeline_exit_code != 0:
        print(f"❌ [ERROR] Image generation pipeline failed with exit code {pipeline_exit_code}.")
        return pipeline_exit_code
    print("✅ [STEP 2/2 COMPLETE] Generated PCS Story card and saved to Airtable.")

    print("\n" + "=" * 80)
    print("🎉 [END-TO-END COMPLETE] Scraped Product -> Generated 'PCS Story' -> Saved to Airtable!")
    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
