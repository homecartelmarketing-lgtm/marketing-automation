"""Generate PCS Story Images for Pending Records in Airtable via Fal AI Nano Banana Pro.

Reads records where 'Furniture item' and 'Product Closeup w/ Specs Layout' exist
and blends them using 'JSON Prompts/Product Closeup with Specs/product_closeup_specs.json'
into 'PCS Story'.

Usage:
    # Process all pending records:
    python "Product Closeup Specs Story/2_Generate_Pending_Stories.py"

    # Process up to N records:
    python "Product Closeup Specs Story/2_Generate_Pending_Stories.py" --limit 3

    # Process a single record ID:
    python "Product Closeup Specs Story/2_Generate_Pending_Stories.py" --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_product_specs_story_pipeline import main as pipeline_main


def main():
    sys.exit(pipeline_main())


if __name__ == "__main__":
    main()
