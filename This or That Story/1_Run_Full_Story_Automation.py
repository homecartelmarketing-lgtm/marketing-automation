"""Run Full End-to-End This or That Story Automation.

Workflow:
1. Scrapes 2 active lighting products from Akeneo into 1 Airtable row.
2. Automatically attaches the 'This or That Layout' watermark template.
3. Formats prompt with item names and types using Fal AI Nano Banana Pro.
4. Generates 9:16 vertical Instagram Story comparing the two items.
5. Uploads resulting story card directly to Airtable:
   - 'Story This or That (1)' / 'This or That Converted'
   - Sets Status = 'Complete'

Usage:
    # Run 1 row for Wall Lights (default):
    python "This or That Story/1_Run_Full_Story_Automation.py"

    # Run for specific lighting category:
    python "This or That Story/1_Run_Full_Story_Automation.py" --target wall_lights
    python "This or That Story/1_Run_Full_Story_Automation.py" --target table_lamps
    python "This or That Story/1_Run_Full_Story_Automation.py" --target cluster_chandelier
    python "This or That Story/1_Run_Full_Story_Automation.py" --target floor_lamp
    python "This or That Story/1_Run_Full_Story_Automation.py" --target chandeliers
    python "This or That Story/1_Run_Full_Story_Automation.py" --target pendant_lights
    python "This or That Story/1_Run_Full_Story_Automation.py" --target all

    # Process N rows end-to-end (one by one):
    python "This or That Story/1_Run_Full_Story_Automation.py" --target wall_lights --count 3

    # Target a specific Airtable Record ID:
    python "This or That Story/1_Run_Full_Story_Automation.py" --target wall_lights --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_this_or_that_pipeline import main as pipeline_main


def main():
    sys.exit(pipeline_main())


if __name__ == "__main__":
    main()
