"""Run Full End-to-End Product Closeup w/ Description Story Automation.

Workflow:
1. Scrapes active modern lighting products from Akeneo into Airtable.
2. Automatically attaches 'layout_product_v2.jpg' into 'Product Closeup Description Layout'.
3. Formats prompt with item names using 'JSON Prompts/Product Closeup V2/product_desc.json'.
4. Blends product with description layout via Fal AI Nano Banana Pro (9:16 vertical 1080x1920).
5. Appends log to 'output/logs/fal_nano_product_description_logs.json'.
6. Uploads resulting story card directly to Airtable:
   - Field: 'Product Closeup Description Converted'
   - Sets Status = 'Complete'

Usage:
    # Run 1 item for Chandeliers (default):
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py"

    # Run for specific lighting category:
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target chandeliers
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target pendant_lights
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target floor_lamps
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target cluster_chandeliers
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target table_lamps
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target wall_lights

    # Run 1 item for ALL 6 categories:
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target all

    # Process N items (e.g. 3 products):
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target chandeliers --count 3

    # Target a specific Airtable Record ID:
    python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target chandeliers --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_full_product_description_story import main as runner_main


def main():
    sys.exit(runner_main())


if __name__ == "__main__":
    main()
