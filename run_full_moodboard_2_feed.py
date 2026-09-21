"""Run Full End-to-End Moodboard #2 Feed Automation.

Workflow:
1. Ingests 1 (or N) product(s) from Akeneo into the target Airtable Moodboard #2 table:
   - Populates: Furniture Item, Item Name, Moodboard #2 Layout (referencephoto_moodboard.png),
     Moodboard Converstion Fixed Prompt (second_moodboard.json), Status = 'Standby'.
2. Runs the complete AI Generation & Flat-Lay Conversion Pipeline:
   - Phase 1: Krea AI Room Interior Generation (4:5) -> 'Interior Photo'
   - Phase 2: Claude Sonnet 5 Vision Prompt Generation -> 'Blending Prompt'
   - Phase 3: Fal AI Nano Banana Pro Image Blending (4:5 1k) -> 'Blended Image'
   - Phase 4: Auto-attaches Layout reference photo & fixed prompt if missing
   - Phase 5: Fal AI Nano Banana Pro Editorial Flat-Lay Conversion (4:5 1k) -> 'Moodboard #2 Converted'
   - Phase 6: Finalize Status -> 'Done'

Usage:
    # 1. Run interactive category menu (when in terminal):
    python run_full_moodboard_2_feed.py

    # 2. Run for specific category:
    python run_full_moodboard_2_feed.py --category chandeliers
    python run_full_moodboard_2_feed.py --category pendant_lights
    python run_full_moodboard_2_feed.py --category floor_lamps
    python run_full_moodboard_2_feed.py --category wall_lights

    # 3. Process N items (e.g. 3 products):
    python run_full_moodboard_2_feed.py --category chandeliers --max-items 3

    # 4. Only process existing records without scraping new ones:
    python run_full_moodboard_2_feed.py --skip-scrape
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from scrape_moodboard_2_feed import (
    MOODBOARD_2_FEED_PRESETS,
    main as run_scraper,
    resolve_preset,
)
from generate_moodboard_2_feed import main as run_pipeline


def prompt_category_choice() -> str:
    """Prompt user to select category from an interactive terminal menu."""
    presets = list(MOODBOARD_2_FEED_PRESETS.values())
    print("\n" + "=" * 64)
    print("Select Moodboard #2 Feed Category Table:")
    print("=" * 64)
    for idx, p in enumerate(presets, start=1):
        t_id = os.getenv(p["env_table_key"], "").strip() or p["default_table_id"]
        mb_id = os.getenv(p.get("env_moodboard_key", ""), "").strip() or p.get("default_moodboard_id", "")
        prompt = p.get("default_prompt", "")
        print(f"  [{idx}] {p['label']} ({p['category_code']})")
        print(f"      * Table ID        : {t_id}")
        print(f"      * Krea Moodboard  : {mb_id}")
        print(f"      * Interior Prompt : \"{prompt}\"\n")
    print("=" * 64)

    try:
        choice = input(f"Enter choice [1-{len(presets)}] (default: 1): ").strip().lower()
        if choice:
            try:
                num = int(choice)
                if 1 <= num <= len(presets):
                    return presets[num - 1]["category_code"]
            except ValueError:
                pass
            for p in presets:
                if choice in p["aliases"] or choice == p["category_code"]:
                    return p["category_code"]
    except (EOFError, KeyboardInterrupt):
        pass

    return presets[0]["category_code"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Full End-to-End Moodboard #2 Feed Automation: Scrape -> Generate -> Converted Moodboard."
    )
    parser.add_argument(
        "--category",
        "-c",
        default=None,
        help="Category to process (chandeliers, pendant_lights, floor_lamps, wall_lights)",
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
        help="Number of items to scrape & process (default: 1)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override Airtable destination table ID",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Krea Moodboard ID override",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Krea Interior Prompt override",
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
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    category = args.category
    # If no category provided and running interactively, prompt user
    if not category:
        if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            category = prompt_category_choice()
        else:
            category = "chandeliers"

    preset = resolve_preset(category)
    table_id = (
        args.table_id
        or os.getenv(preset["env_table_key"], "").strip()
        or preset["default_table_id"]
    )

    print("\n" + "=" * 64)
    print("🚀 MOODBOARD #2 FEED | FULL END-TO-END AUTOMATION")
    print(f"Target Category : {preset['label']} ({preset['category_code']})")
    print(f"Airtable Table  : {table_id}")
    print(f"Style Filter    : {args.style}")
    print(f"Item Count      : {args.max_items} product(s)")
    print("=" * 64 + "\n")

    # Step 1: Scrape from Akeneo into Airtable (if not skipped)
    if not args.skip_scrape:
        print("[STEP 1/2] Ingesting product(s) from Akeneo into Airtable...")
        scraper_argv = [
            "--category", preset["category_code"],
            "--style", args.style,
            "--max-items", str(args.max_items),
            "--table-id", table_id,
        ]
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

    # Step 2: Run Full AI Generation Pipeline
    print("\n[STEP 2/2] Running AI Generation & Editorial Flat-Lay Pipeline...")
    pipeline_argv = [
        "--category", preset["category_code"],
        "--table-id", table_id,
        "--max-items", str(args.max_items),
        "--no-scrape",
    ]
    if args.moodboard_id:
        pipeline_argv.extend(["--moodboard-id", args.moodboard_id])
    if args.prompt:
        pipeline_argv.extend(["--prompt", args.prompt])

    pipeline_code = run_pipeline(pipeline_argv)
    if pipeline_code != 0:
        print(f"[ERROR] Pipeline step failed with exit code {pipeline_code}")
        return pipeline_code

    print("\n" + "=" * 64)
    print("✨ MOODBOARD #2 FEED END-TO-END RUN COMPLETE!")
    print(f"Check your Airtable table ({table_id}) to inspect the generated slides:")
    print("  1. Blended Image (Product integrated into luxury interior)")
    print("  2. Moodboard #2 Converted (Curated editorial flat-lay moodboard)")
    print("  -> Status: Done")
    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
