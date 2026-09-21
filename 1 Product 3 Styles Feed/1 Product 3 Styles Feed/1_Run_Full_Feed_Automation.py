"""Run Full End-to-End 1 Product, 3 Styles Feed Automation Pipeline.

Workflow:
1. Phase 1 (Akeneo Scrape): Ingests 1 new active product (Floor Lamp, Pendant Light, or Chandelier) from Akeneo into Airtable (Status='Standby') with Cross-Table Deduplication.
2. Phase 2 (Krea AI Room Interiors): Generates 3 distinct room styles @ 4:5 vertical 1K using Krea AI (Interior1, Interior2, Interior3).
3. Phase 3 (Claude Sonnet 5 Prompt Analysis): Analyzes product + 3 room interiors with Fal Claude Sonnet 5 Vision to write Prompt1, Prompt2, Prompt3.
4. Phase 4 (Nano Banana Pro Multi-Blending + Logo Stamping): Blends product into 3 room styles (4:5 1K) with Fal AI Nano Banana Pro, stamps HomeCartel logo on Slide 1, and uploads to '1 Product 3 Style Blended'.

Usage:
    # 1. Run Chandeliers (tblrlfqBGe5EjS5PI):
    python "1 Product 3 Styles Feed/1_Run_Full_Feed_Automation.py" --target chandeliers

    # 2. Run Pendant Lights (tblRy52kCasisCWzd):
    python "1 Product 3 Styles Feed/1_Run_Full_Feed_Automation.py" --target pendant_lights

    # 3. Run Floor Lamps (tbl9GIq2QeYCwMhWU):
    python "1 Product 3 Styles Feed/1_Run_Full_Feed_Automation.py" --target floor_lamps

    # 4. Process N rows in batch:
    python "1 Product 3 Styles Feed/1_Run_Full_Feed_Automation.py" --target floor_lamps --max-rows 3
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_1_product_3_styles_feed import main as run_main


def main():
    sys.exit(run_main())


if __name__ == "__main__":
    main()
