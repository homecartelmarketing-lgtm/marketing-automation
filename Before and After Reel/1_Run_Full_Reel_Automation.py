"""Run Full End-to-End Before & After Reel Automation.

Workflow:
1. Auto-scrapes 1 new active product from Akeneo (Floor Lamp, Pendant Light, or Chandelier) if needed.
2. Generates a 9:16 interior room photograph with Krea AI ('Interior Generated Photo' - Before).
3. Analyzes the room scene with Claude Sonnet 5 Vision to craft the blending prompt ('Blending Prompt').
4. Blends the product into the room scene with Fal AI Nano Banana Pro ('Blended Image' - After, 9:16).
5. Generates 4 alternative camera angles with Fal AI Qwen ('Multiple Angle Blended Image', 9:16).
6. Compiles a 9:16 Slideshow Video Reel with on-beat jazz music, typography title, and branded outro.
7. Automatically exports and syncs to Google Drive ('G:/My Drive/Before & After Reels') and Airtable.

Usage:
    # 1. Run Floor Lamps (Default):
    python "Before and After Reel/1_Run_Full_Reel_Automation.py"

    # 2. Run Pendant Lights:
    python "Before and After Reel/1_Run_Full_Reel_Automation.py" --target pendant_lights

    # 3. Run Chandeliers:
    python "Before and After Reel/1_Run_Full_Reel_Automation.py" --target chandeliers

    # 4. Process N products:
    python "Before and After Reel/1_Run_Full_Reel_Automation.py" --max-items 3
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_before_after_reel import main as run_main


def main():
    sys.exit(run_main())


if __name__ == "__main__":
    main()
