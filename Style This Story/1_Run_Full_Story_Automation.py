"""Run Full End-to-End Style This Story Automation.

Workflow:
1. Auto-scrapes a new Floor Lamp from Akeneo if there are no pending rows.
2. Generates 4 9:16 interior room photographs with Krea AI.
3. Analyzes scenes with Claude Sonnet 5 Vision to craft blending prompts.
4. Blends the floor lamp into the 4 room scenes with Fal AI Nano Banana Pro.
5. Saves dynamic Claude vibe text to 'Style This Text Generated[1-3]' and HEX color to 'Style This Auto Generated Color[1-3]'.
6. Stamps HomeCartel logo, heart icon, and dynamic color pill badges via local Python Pillow.
7. Uploads story cards directly to Airtable:
   - 'Double Tap Converted' (3 cards)
   - 'STORY - Style This? (4)' (4 cards)
   - Sets Status = 'Complete'

Usage:
    # Process 1 pending row end-to-end:
    python "Style This Story/1_Run_Full_Story_Automation.py"

    # Process N rows:
    python "Style This Story/1_Run_Full_Story_Automation.py" --limit 3

    # Process a specific Airtable Record ID:
    python "Style This Story/1_Run_Full_Story_Automation.py" --record-id recXXXXXXXXXXXXXX

    # Dry-run test (simulation without calling paid APIs):
    python "Style This Story/1_Run_Full_Story_Automation.py" --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_style_this_story_pipeline import main as pipeline_main


def main():
    # Pass command line arguments directly to pipeline engine with default mode='all'
    sys.exit(pipeline_main())


if __name__ == "__main__":
    main()
