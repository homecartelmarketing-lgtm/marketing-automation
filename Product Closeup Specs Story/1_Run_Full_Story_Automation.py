"""Run Full End-to-End Product Closeup w/ Specs Story Automation.

Workflow:
1. Scrapes active modern lighting products from Akeneo into Airtable (with comprehensive deduplication).
2. Automatically attaches 'product_specs_layout.png' into 'Product Closeup w/ Specs Layout'.
3. Formats prompt with item names using 'JSON Prompts/Product Closeup with Specs/product_closeup_specs.json'.
4. Blends 'Furniture item' with 'Product Closeup w/ Specs Layout' via Fal AI Nano Banana Pro (9:16 vertical 1080x1920) -> 'PCS Story'.
5. Updates Status = 'Done'.

Usage:
    # Run 1 item for Chandeliers:
    python "Product Closeup Specs Story/1_Run_Full_Story_Automation.py"

    # Process N items (e.g. 3 products):
    python "Product Closeup Specs Story/1_Run_Full_Story_Automation.py" --count 3

    # Target a specific Airtable Record ID:
    python "Product Closeup Specs Story/1_Run_Full_Story_Automation.py" --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_full_product_specs_story import main as runner_main


def main():
    sys.exit(runner_main())


if __name__ == "__main__":
    main()
