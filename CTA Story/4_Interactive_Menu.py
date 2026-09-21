"""Interactive CLI Menu for CTA Story Automation.

Run this script to launch a user-friendly console menu where you can choose
the CTA Story Airtable table and pipeline phases with simple numbered options.

Usage:
    python "CTA Story/4_Interactive_Menu.py"
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_cta_story_pipeline import run_pipeline


def main() -> int:
    try:
        return run_pipeline(mode="menu")
    except KeyboardInterrupt:
        print("\n[INFO] Exited CTA Story Menu.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
