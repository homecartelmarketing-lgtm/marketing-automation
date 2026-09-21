"""End-to-end 2-step automation for Product Closeup w/ Description Story:
1. Scrape item from Akeneo into Airtable (Furniture Item + Layout) with comprehensive deduplication.
2. Generate blended closeup story card via Fal AI API and save output to Airtable ('Product Closeup Description Converted').

Usage::

    python run_full_product_description_story.py
    python run_full_product_description_story.py --target chandelier --count 1
    python run_full_product_description_story.py --target pendant_light --count 1
    python run_full_product_description_story.py --target floor_lamp --count 1
    python run_full_product_description_story.py --target all
    python run_full_product_description_story.py --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

from scrape_product_description_story import main as run_scraper
from generate_product_description_story_pipeline import main as run_pipeline


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run end-to-end 2-step automation: Scrape -> Generate Story Card via Fal AI."
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
        default="chandelier",
        help="Target lighting category (default: chandelier)",
    )
    parser.add_argument(
        "--count",
        "-n",
        "--limit",
        "--max-items",
        type=int,
        default=1,
        help="Number of items to scrape & process in this run (default: 1)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default="modern",
        help="Akeneo Style2 filter (default: modern)",
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
        help="Fal AI image model name (default: fal-ai/nano-banana-pro/edit)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    print("\n" + "=" * 80)
    print(f"🚀 STARTING END-TO-END AUTOMATION FOR '{args.target.upper()}' (Count: {args.count})")
    print("Workflow: Scrape -> Fal AI Story Card Generation -> 'Product Closeup Description Converted'")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 1: Scrape Item from Akeneo into Airtable (with comprehensive deduplication)
    # -------------------------------------------------------------------------
    if not args.record_id:
        print(f"\n📥 [STEP 1/2] Scraping {args.count} modern product item(s) from Akeneo into Airtable...")
        scrape_argv = ["--target", args.target, "--max-items", str(args.count), "--style", args.style]
        if args.table_id:
            scrape_argv.extend(["--table-id", args.table_id])
        scrape_exit_code = run_scraper(scrape_argv)
        if scrape_exit_code != 0:
            print(f"❌ [ERROR] Scraping failed with exit code {scrape_exit_code}.")
            return scrape_exit_code
        print("✅ [STEP 1/2 COMPLETE] Scraped item into Airtable.")
    else:
        print(f"\n⏩ [STEP 1/2 SKIPPED] Targeted specific Record ID: {args.record_id}")

    # -------------------------------------------------------------------------
    # STEP 2: Fal AI Image Generation -> Airtable Output Attachment
    # -------------------------------------------------------------------------
    print(f"\n🎨 [STEP 2/2] Generating Fal AI Image ({args.model}) & attaching output to Airtable...")
    pipeline_argv = ["--target", args.target, "--limit", str(args.count), "--model", args.model]
    if args.record_id:
        pipeline_argv.extend(["--record-id", args.record_id])
    if args.table_id:
        pipeline_argv.extend(["--table-id", args.table_id])
    pipeline_exit_code = run_pipeline(pipeline_argv)
    if pipeline_exit_code != 0:
        print(f"❌ [ERROR] Image generation pipeline failed with exit code {pipeline_exit_code}.")
        return pipeline_exit_code
    print("✅ [STEP 2/2 COMPLETE] Generated Closeup image card.")

    print("\n" + "=" * 80)
    print("🎉 [END-TO-END COMPLETE] Processed item(s) -> Generated Story Card -> Saved to Airtable!")
    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())


