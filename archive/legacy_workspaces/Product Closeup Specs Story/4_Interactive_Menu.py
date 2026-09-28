"""Interactive Terminal Menu for Product Closeup w/ Specs Story Automation.

Run this script to launch a console menu to scrape or generate Product Closeup w/ Specs.

Usage:
    python "Product Closeup Specs Story/4_Interactive_Menu.py"
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def print_banner():
    print("\n" + "=" * 70)
    print(" 💡  HomeCartel - Product Closeup w/ Specs Story Automation Menu")
    print("=" * 70)


def run_interactive_menu():
    folder = Path(__file__).resolve().parent

    while True:
        print_banner()
        print(" [1] 🚀 Run Full Automation (Scrape 1 Product -> Nano Banana Pro -> PCS Story)")
        print(" [2] 🎨 Generate PCS Story Cards Only (Process Pending Records via Fal AI)")
        print(" [3] 📥 Scrape Chandeliers from Akeneo (1 Product -> Airtable)")
        print(" [4] 🔢 Scrape Custom Count (Specify how many products)")
        print(" [5] 🔍 Dry Run Scrape (Preview deduplication & layout attachment)")
        print(" [0] 🚪 Exit")
        print("-" * 70)

        choice = input(" Piliin ang nais mong gawin [0-5]: ").strip()

        if choice == "0":
            print("\n👋 Babay! Maraming salamat!\n")
            break

        elif choice == "1":
            script = folder / "1_Run_Full_Story_Automation.py"
            subprocess.run([sys.executable, str(script), "--count", "1"])
            input("\nPress Enter para bumalik sa menu...")

        elif choice == "2":
            script = folder / "2_Generate_Pending_Stories.py"
            subprocess.run([sys.executable, str(script)])
            input("\nPress Enter para bumalik sa menu...")

        elif choice == "3":
            script = folder / "3_Scrape_Akeneo_Chandeliers.py"
            subprocess.run([sys.executable, str(script), "--count", "1"])
            input("\nPress Enter para bumalik sa menu...")

        elif choice == "4":
            count_str = input(" Ilang products ang nais mong i-scrape? (e.g. 3): ").strip()
            count = int(count_str) if count_str.isdigit() else 1
            script = folder / "3_Scrape_Akeneo_Chandeliers.py"
            subprocess.run([sys.executable, str(script), "--count", str(count)])
            input("\nPress Enter para bumalik sa menu...")

        elif choice == "5":
            script = folder / "3_Scrape_Akeneo_Chandeliers.py"
            subprocess.run([sys.executable, str(script), "--count", "1", "--dry-run"])
            input("\nPress Enter para bumalik sa menu...")

        else:
            print("⚠️ Hindi wastong pagpipilian. Subukan muli.")


if __name__ == "__main__":
    try:
        run_interactive_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Naantala ng user. Paalam!\n")
