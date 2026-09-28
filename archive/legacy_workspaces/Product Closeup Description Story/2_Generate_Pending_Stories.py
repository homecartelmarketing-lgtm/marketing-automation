"""Generate Product Closeup w/ Description Stories for Pending Records in Airtable.

This script processes existing rows in Airtable that already have scraped products
('Furniture Item' & 'Product Closeup Description Layout' attached), but do not yet
have a generated story card in 'Product Closeup Description Converted'.

It does NOT scrape new products from Akeneo.

Usage:
    # Generate stories for 1 pending row in Chandeliers:
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py"

    # Generate stories for specific lighting category:
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target chandeliers
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target pendant_lights
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target floor_lamps
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target cluster_chandeliers
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target table_lamps
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target wall_lights
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target all

    # Generate up to N pending records:
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target chandeliers --count 5

    # Generate a specific record ID:
    python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target chandeliers --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_product_description_story_pipeline import (
    PRODUCT_DESCRIPTION_PIPELINE_TABLES,
    main as pipeline_main,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate Product Closeup w/ Description Stories for existing pending records in Airtable."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[*PRODUCT_DESCRIPTION_PIPELINE_TABLES.keys(), "all"],
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
    pipeline_argv = [
        "--target", args.target,
        "--limit", str(args.count),
        "--model", args.model,
    ]
    if args.record_id:
        pipeline_argv.extend(["--record-id", args.record_id])
    if args.table_id:
        pipeline_argv.extend(["--table-id", args.table_id])
    return pipeline_main(pipeline_argv)


if __name__ == "__main__":
    sys.exit(main())
