"""Generate This or That Stories for Pending Records in Airtable.

This script processes existing rows in Airtable that already have scraped products
('Furniture Item' & 'Furniture Item2') and layout attached, but do not yet have a
generated story card in 'Story This or That (1)'.

It does NOT scrape new products from Akeneo.

Usage:
    # Generate stories for 1 pending row in Wall Lights:
    python "This or That Story/2_Generate_Pending_Stories.py"

    # Generate stories for specific lighting category:
    python "This or That Story/2_Generate_Pending_Stories.py" --target wall_lights
    python "This or That Story/2_Generate_Pending_Stories.py" --target table_lamps
    python "This or That Story/2_Generate_Pending_Stories.py" --target cluster_chandelier
    python "This or That Story/2_Generate_Pending_Stories.py" --target floor_lamp
    python "This or That Story/2_Generate_Pending_Stories.py" --target chandeliers
    python "This or That Story/2_Generate_Pending_Stories.py" --target pendant_lights
    python "This or That Story/2_Generate_Pending_Stories.py" --target all

    # Generate up to N pending records:
    python "This or That Story/2_Generate_Pending_Stories.py" --target wall_lights --count 5

    # Generate a specific record ID:
    python "This or That Story/2_Generate_Pending_Stories.py" --target wall_lights --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_this_or_that_pipeline import (
    THIS_OR_THAT_TABLES,
    run_row_by_row_pipeline,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate This or That Stories for existing pending records in Airtable."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[*THIS_OR_THAT_TABLES.keys(), "all"],
        default="wall_lights",
        help="Target lighting category (default: wall_lights)",
    )
    parser.add_argument(
        "--count",
        "-n",
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
        "--model",
        default="fal-ai/nano-banana-pro/edit",
        help="Fal AI model endpoint (default: fal-ai/nano-banana-pro/edit)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    canonical_targets = [
        "chandeliers",
        "pendant_lights",
        "floor_lamp",
        "cluster_chandelier",
        "table_lamps",
        "wall_lights",
    ]
    targets = canonical_targets if args.target == "all" else [args.target]
    all_ok = True
    for target in targets:
        ok = run_row_by_row_pipeline(
            target_key=target,
            count=args.count,
            mode="generate",
            record_id=args.record_id,
            table_id_override=args.table_id,
            model=args.model,
        )
        if not ok:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
