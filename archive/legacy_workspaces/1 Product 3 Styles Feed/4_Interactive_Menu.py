"""Interactive Terminal Menu for 1 Product, 3 Styles Feed Automation.

Run this script to launch a user-friendly console menu where you can choose
any action with a simple keypress (0 to 7).

Usage:
    python "1 Product 3 Styles Feed/4_Interactive_Menu.py"
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

# Add parent directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print("\n" + "=" * 68)
    print(" ✨ HomeCartel - 1 Product, 3 Styles Feed Automation Menu")
    print("=" * 68)


def run_interactive_menu():
    folder = Path(__file__).resolve().parent

    while True:
        print_banner()
        print(" [1] 🚀 Run Full Automation (Chandeliers - tblrlfqBGe5EjS5PI)")
        print(" [2] 🚀 Run Full Automation (Pendant Lights - tblRy52kCasisCWzd)")
        print(" [3] 🚀 Run Full Automation (Floor Lamps - tbl9GIq2QeYCwMhWU)")
        print(" [4] 🎨 Generate Blends for Pending Rows (Phase 2-4 Only)")
        print(" [5] 🔍 Scrape Chandeliers from Akeneo (Cross-Table Dedup)")
        print(" [6] 🔍 Scrape Pendant Lights from Akeneo (Cross-Table Dedup)")
        print(" [7] 🔍 Scrape Floor Lamps from Akeneo (Cross-Table Dedup)")
        print(" [0] 🚪 Exit")
        print("-" * 68)

        choice = input(" Piliin ang nais mong gawin [0-7]: ").strip()

        if choice == "0":
            print("\n[INFO] Exited 1 Product, 3 Styles Feed Menu. Salamat!\n")
            break
        elif choice == "1":
            cmd = [sys.executable, str(folder / "1_Run_Full_Feed_Automation.py"), "--target", "chandeliers"]
            subprocess.run(cmd)
        elif choice == "2":
            cmd = [sys.executable, str(folder / "1_Run_Full_Feed_Automation.py"), "--target", "pendant_lights"]
            subprocess.run(cmd)
        elif choice == "3":
            cmd = [sys.executable, str(folder / "1_Run_Full_Feed_Automation.py"), "--target", "floor_lamps"]
            subprocess.run(cmd)
        elif choice == "4":
            print("\nPiliin ang target category:")
            print(" [1] Chandeliers")
            print(" [2] Pendant Lights")
            print(" [3] Floor Lamps")
            sub = input("Target [1-3]: ").strip()
            cat = "chandeliers" if sub == "1" else ("pendant_lights" if sub == "2" else "floor_lamps")
            count = input("Ilang rows ang ipoproseso? (default 1): ").strip() or "1"
            cmd = [sys.executable, str(folder / "2_Generate_Pending_Feeds.py"), "--target", cat, "--max-rows", count]
            subprocess.run(cmd)
        elif choice == "5":
            print("\n[Mode] Scrape Chandeliers (tblrlfqBGe5EjS5PI):")
            print(" [1] Live Execute (Isave agad sa Airtable)")
            print(" [2] Dry Run / Preview (Read-Only)")
            m = input("Piliin [1-2]: ").strip()
            count = input("Ilang items ang i-scrape? (default 1): ").strip() or "1"
            cmd = [sys.executable, str(folder / "3_Scrape_Akeneo_Chandeliers.py"), "--max-items", count]
            if m == "1":
                cmd.append("--execute")
            subprocess.run(cmd)
        elif choice == "6":
            print("\n[Mode] Scrape Pendant Lights (tblRy52kCasisCWzd):")
            print(" [1] Live Execute (Isave agad sa Airtable)")
            print(" [2] Dry Run / Preview (Read-Only)")
            m = input("Piliin [1-2]: ").strip()
            count = input("Ilang items ang i-scrape? (default 1): ").strip() or "1"
            cmd = [sys.executable, str(folder / "3_Scrape_Akeneo_Pendant_Lights.py"), "--max-items", count]
            if m == "1":
                cmd.append("--execute")
            subprocess.run(cmd)
        elif choice == "7":
            print("\n[Mode] Scrape Floor Lamps (tbl9GIq2QeYCwMhWU):")
            print(" [1] Live Execute (Isave agad sa Airtable)")
            print(" [2] Dry Run / Preview (Read-Only)")
            m = input("Piliin [1-2]: ").strip()
            count = input("Ilang items ang i-scrape? (default 1): ").strip() or "1"
            cmd = [sys.executable, str(folder / "3_Scrape_Akeneo_Floor_Lamps.py"), "--max-items", count]
            if m == "1":
                cmd.append("--execute")
            subprocess.run(cmd)
        else:
            print("\n[WARNING] Hindi wastong pagpipilian. Subukan muli.")

        input("\nPress ENTER para bumalik sa menu...")


def main():
    try:
        run_interactive_menu()
    except KeyboardInterrupt:
        print("\n[INFO] Exited 1 Product, 3 Styles Feed Menu.")


if __name__ == "__main__":
    main()
