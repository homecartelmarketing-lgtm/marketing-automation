"""Generate Local Visual Previews for Style This Story Cards.

Renders high-resolution previews for:
- Slide 1: 'How would you style this? ft. [Item Name]' (Top-right Logo + Centered Headline, no shadow)
- Slide 2: 'Double tap if you choose:' (Heart Icon + Headline @ X=346.6, Y=212.0 + Dynamic Pill Shape @ Y=296.3, no shadow)

Output directory:
    output/style_this_preview/

Usage:
    # 1. Quick local preview using test assets:
    python "Style This Story/4_Preview_Story_Cards_Locally.py"

    # 2. Preview directly from an Airtable Record ID:
    python "Style This Story/4_Preview_Story_Cards_Locally.py" --record-id recXXXXXXXXXXXXXX

    # 3. Preview with custom text and custom HEX color:
    python "Style This Story/4_Preview_Story_Cards_Locally.py" --text "Terracotta Warmth" --color "#c17c5f"
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preview_style_this_overlay import main as preview_main


def main():
    sys.exit(preview_main())


if __name__ == "__main__":
    main()
