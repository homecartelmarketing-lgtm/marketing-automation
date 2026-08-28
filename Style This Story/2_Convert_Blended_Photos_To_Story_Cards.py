"""Convert Existing Blended Photos in Airtable into Final Story Cards.

Use this script when you already have rows with 'Style This Blended' images in Airtable
and you want to quickly generate the Story Cards (Slide 1: How Would You + Slides 2-4: Double Tap)
without paying for image generation or blending APIs.

Workflow:
1. Downloads 'style_this01.jpg', '02.jpg', '03.jpg', '04.jpg' from 'Style This Blended'.
2. Slide 1: Stamped top-right logo + centered headline 'How would you style this? ft. [Item Name]' (Clean solid white, no shadow).
3. Slides 2-4:
   - Claude Vision analyzes 'style_this02..04' to identify room vibe and matching HEX color.
   - Automatically saves vibe text to 'Style This Text Generated[1-3]' and HEX color to 'Style This Auto Generated Color[1-3]' in Airtable.
   - Renders 'Double tap if you choose:' with heart icon at X=346.6, Y=212.0 (no shadow) and dynamic color pill at Y=296.3.
4. Uploads 3 Double Tap cards to 'Double Tap Converted' and all 4 cards to 'STORY - Style This? (4)' and sets Status='Complete'.

Usage:
    # Convert all pending blended rows (processes 1 row):
    python "Style This Story/2_Convert_Blended_Photos_To_Story_Cards.py"

    # Convert N blended rows:
    python "Style This Story/2_Convert_Blended_Photos_To_Story_Cards.py" --limit 5

    # Convert a specific Record ID:
    python "Style This Story/2_Convert_Blended_Photos_To_Story_Cards.py" --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_style_this_story_pipeline import main as pipeline_main


def main():
    # Force conversion mode if not explicitly provided
    args = list(sys.argv[1:])
    if "--mode" not in args:
        args = ["--mode", "conversion"] + args
    sys.exit(pipeline_main(args))


if __name__ == "__main__":
    main()
