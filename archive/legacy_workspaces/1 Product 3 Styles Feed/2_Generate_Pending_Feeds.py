"""Generate 1 Product, 3 Styles Feeds for Existing Pending Records in Airtable.

This script processes existing rows in Airtable that already have scraped products
('Furniture Item' attached), and runs Phase 2 (Krea Interiors), Phase 3 (Claude Prompt Analysis),
and Phase 4 (Nano Banana Pro Multi-Blending + Slide 1 Logo Stamping).

Usage:
    # 1. Generate for 1 pending row in Chandeliers:
    python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target chandeliers

    # 2. Generate for Pendant Lights:
    python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target pendant_lights

    # 3. Generate for Floor Lamps:
    python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target floor_lamps

    # 4. Generate up to N pending records:
    python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target chandeliers --max-rows 5

    # 5. Generate a specific record ID:
    python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target chandeliers --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_1_product_3_styles_feed import (
    PRESETS,
    OneProductThreeStylesRunner,
    resolve_preset,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate 1 Product, 3 Styles Feeds for existing pending records in Airtable."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=(
            "chandeliers",
            "chandelier",
            "pendant_lights",
            "pendant_light",
            "pendant",
            "floor_lamps",
            "floor_lamp",
            "floor",
            "1",
            "2",
            "3",
        ),
        default="chandeliers",
        help="Target lighting category preset (default: chandeliers)",
    )
    parser.add_argument(
        "--max-rows",
        "-n",
        "--count",
        type=int,
        default=1,
        help="Number of pending records to process (default: 1)",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Target a specific record ID in Airtable",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override destination Airtable Table ID",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Override Krea Moodboard ID",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    preset = resolve_preset(args.target)
    runner = OneProductThreeStylesRunner(
        preset=preset,
        table_id_override=args.table_id,
        moodboard_id_override=args.moodboard_id,
    )

    print("=" * 68)
    print(f" 1 Product, 3 Styles Feed Generator (Pending Rows) | {preset.name}")
    print(f" Destination Table: {runner.table_id}")
    print(f" Krea Moodboard ID: {runner.moodboard_id}")
    print(f" Max Pending Rows : {args.max_rows}")
    print("=" * 68)

    runner.run(
        phase="all",
        target_record_id=args.record_id,
        max_rows=args.max_rows,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
