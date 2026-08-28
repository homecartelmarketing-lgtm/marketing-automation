"""Generate / Recompile Videos Only for Before & After Reel.

Use this when:
- Images (Interior, Blended, 4 Angles) are ALREADY generated in Airtable.
- You want to compile / re-compile the final 9:16 MP4 Video Reel with on-beat music, typography, and outro.
- Zero AI image cost (only video compilation & upload).

Usage:
    # 1. Generate videos for Floor Lamps (Default):
    python "Before and After Reel/2_Generate_Videos_Only.py"

    # 2. Generate videos for Pendant Lights:
    python "Before and After Reel/2_Generate_Videos_Only.py" --target pendant_lights

    # 3. Generate videos for Chandeliers:
    python "Before and After Reel/2_Generate_Videos_Only.py" --target chandeliers

    # 4. Limit to N records:
    python "Before and After Reel/2_Generate_Videos_Only.py" --limit 2
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_automation.config import REEL_TABLES, load_settings, resolve_reel_table
from content_automation.fal_client import FalClient
from content_automation.scraping import ScrapeAirtableClient
from generate_before_after_reel_pipeline import generate_slideshow_reels_pipeline


def parse_args(argv=None):
    preset_keys = list(REEL_TABLES.keys())
    parser = argparse.ArgumentParser(
        description="Compile 9:16 Slideshow Videos for existing Before & After Reel records in Airtable"
    )
    parser.add_argument(
        "--target",
        "-t",
        default=None,
        help=f"Target category ({', '.join(preset_keys)}) or table ID",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        metavar="N",
        help="Maximum records to process (default: all pending)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Direct Airtable table ID override",
    )
    return parser.parse_args(argv)


def main():
    args = parse_args()
    settings = load_settings()
    settings.require({"airtable", "fal"})

    resolved = resolve_reel_table(args.target, prompt_if_interactive=False)
    table_id = args.table_id or resolved.get("table_id") or resolved.get("default_table_id")

    print("\n" + "=" * 64)
    print(" HomeCartel - Before & After Reel (Video Compilation Only)")
    print(f" Target: {resolved.get('label', table_id)} ({table_id})")
    print(f" Limit: {args.limit if args.limit is not None else 'All Pending'}")
    print("=" * 64)

    fal = FalClient(settings.fal_key)
    airtable = ScrapeAirtableClient(settings.airtable_token, settings.airtable_base_id, table_id)

    success = generate_slideshow_reels_pipeline(fal, airtable, limit_records=args.limit)
    if success:
        print("\n[SUCCESS] Video compilation finished successfully!")
        sys.exit(0)
    else:
        print("\n[WARNING] Video compilation finished with some errors/warnings.")
        sys.exit(1)


if __name__ == "__main__":
    main()
