"""Interactive CLI Menu for Style This Story Automation.

Run this script to launch a user-friendly console menu where you can choose
any action with a simple keypress (1 to 6).

Usage:
    python "Style This Story/5_Interactive_Menu.py"
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_style_this_story_pipeline import run_interactive_menu


def main():
    try:
        run_interactive_menu()
    except KeyboardInterrupt:
        print("\n[INFO] Exited Style This Story Menu.")


if __name__ == "__main__":
    main()
