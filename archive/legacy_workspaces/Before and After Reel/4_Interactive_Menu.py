"""Interactive Terminal Menu for Before & After Reel Automation.

Usage:
    python "Before and After Reel/4_Interactive_Menu.py"
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

# Add parent directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from content_automation.config import get_reel_tables


def print_banner():
    print("\n" + "=" * 64)
    print("  HomeCartel - Before & After Reel Automation")
    print("=" * 64)


def run_interactive_menu():
    folder = Path(__file__).resolve().parent
    parent_dir = folder.parent

    while True:
        print_banner()
        print("  [1] Run Full Pipeline: Chandeliers (tbloMhCOngGDWFS2y)")
        print("  [2] Run Full Pipeline: Pendant Lights (tbleUP86Kw36G8Hdw)")
        print("  [3] Generate Videos Only (Compile existing Airtable photos)")
        print("  [4] Scrape 1 New Product from Akeneo (Standby row)")
        print("  [0] Exit")
        print("-" * 64)

        choice = input("Select an option [0-4]: ").strip().lower()

        if choice in ("0", "exit", "q"):
            print("\n[INFO] Exited menu. Goodbye!\n")
            break
        elif choice == "1":
            cmd = [sys.executable, str(parent_dir / "run_before_after_reel.py"), "--target", "chandeliers"]
            subprocess.run(cmd)
        elif choice == "2":
            cmd = [sys.executable, str(parent_dir / "run_before_after_reel.py"), "--target", "pendant_lights"]
            subprocess.run(cmd)
        elif choice == "3":
            print("\nSelect target category for video compilation:")
            print("  [1] Chandeliers (Default)")
            print("  [2] Pendant Lights")
            print("  [0] Cancel")
            sub = input("Select [0-2]: ").strip()
            if sub == "1":
                cmd = [sys.executable, str(folder / "2_Generate_Videos_Only.py"), "--target", "chandeliers"]
                subprocess.run(cmd)
            elif sub == "2":
                cmd = [sys.executable, str(folder / "2_Generate_Videos_Only.py"), "--target", "pendant_lights"]
                subprocess.run(cmd)
        elif choice == "4":
            print("\nSelect category to scrape from Akeneo:")
            print("  [1] Chandeliers (tbloMhCOngGDWFS2y)")
            print("  [2] Pendant Lights (tbleUP86Kw36G8Hdw)")
            print("  [0] Cancel")
            sub = input("Select [0-2]: ").strip()
            if sub == "1":
                cmd = [sys.executable, str(parent_dir / "run_before_after_reel.py"), "--target", "chandeliers", "--max-items", "1"]
                subprocess.run(cmd)
            elif sub == "2":
                cmd = [sys.executable, str(parent_dir / "run_before_after_reel.py"), "--target", "pendant_lights", "--max-items", "1"]
                subprocess.run(cmd)
        else:
            print("\n[WARNING] Invalid choice. Please try again.")

        input("\nPress ENTER to continue...")


def main():
    try:
        run_interactive_menu()
    except KeyboardInterrupt:
        print("\n[INFO] Exited menu.")


if __name__ == "__main__":
    main()
