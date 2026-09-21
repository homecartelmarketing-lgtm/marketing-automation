"""Run Full End-to-End Moodboard #2 Feed Automation.

Usage:
    python "Moodboard Feed/2_Run_Full_Moodboard_2_Feed.py"
    python "Moodboard Feed/2_Run_Full_Moodboard_2_Feed.py" --category pendant_lights
    python "Moodboard Feed/2_Run_Full_Moodboard_2_Feed.py" --max-items 3
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add workspace root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_full_moodboard_2_feed import main as runner_main


def main():
    sys.exit(runner_main())


if __name__ == "__main__":
    main()
