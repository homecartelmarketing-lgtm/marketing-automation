"""Interactive Terminal Menu for This or That Story Automation.

Run this script to launch a user-friendly console menu where you can choose
any action with a simple keypress.

Usage:
    python "This or That Story/4_Interactive_Menu.py"
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

# Add workspace root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

CATEGORIES = [
    ("1", "Wall Lights", "wall_lights", "3_Scrape_Akeneo_Wall_Lights.py"),
    ("2", "Table Lamps", "table_lamps", "3_Scrape_Akeneo_Table_Lamps.py"),
    ("3", "Cluster Chandeliers", "cluster_chandelier", "3_Scrape_Akeneo_Cluster_Chandeliers.py"),
    ("4", "Floor Lamps", "floor_lamp", "3_Scrape_Akeneo_Floor_Lamps.py"),
    ("5", "Chandeliers", "chandeliers", "3_Scrape_Akeneo_Chandeliers.py"),
    ("6", "Pendant Lights", "pendant_lights", "3_Scrape_Akeneo_Pendant_Lights.py"),
]


def print_banner():
    print("\n" + "=" * 65)
    print(" ⚖️  HomeCartel - This or That Story Automation Menu")
    print("=" * 65)


def run_interactive_menu():
    folder = Path(__file__).resolve().parent

    while True:
        print_banner()
        print(" [1] 🚀 Run Full Automation (Scrape 2 Products -> Generate Story Card)")
        print(" [2] 🎨 Generate Stories Only (Process Pending Records in Airtable)")
        print(" [3] 🔍 Scrape Products Only from Akeneo (Pick Category)")
        print(" [4] ⚡ Run 1 Pair for All 6 Categories (End-to-End)")
        print(" [0] 🚪 Exit")
        print("-" * 65)

        choice = input(" Piliin ang nais mong gawin [0-4]: ").strip()

        if choice == "0":
            print("\n[INFO] Exited This or That Story Menu. Salamat!\n")
            break

        elif choice == "1":
            print("\nPiliin ang target category:")
            for num, name, key, _ in CATEGORIES:
                print(f" [{num}] {name}")
            print(" [7] ALL Categories")
            cat_choice = input("Category [1-7] (default 1 - Wall Lights): ").strip() or "1"
            
            selected_cat = "wall_lights"
            if cat_choice == "7":
                selected_cat = "all"
            else:
                for num, name, key, _ in CATEGORIES:
                    if cat_choice == num:
                        selected_cat = key
                        break

            count_str = input("Ilang rows ang ipo-process? (default: 1): ").strip() or "1"
            try:
                count = max(1, int(count_str))
            except ValueError:
                count = 1

            cmd = [
                sys.executable,
                str(folder / "1_Run_Full_Story_Automation.py"),
                "--target",
                selected_cat,
                "--count",
                str(count),
            ]
            subprocess.run(cmd)

        elif choice == "2":
            print("\nPiliin ang target category para sa Generate Only:")
            for num, name, key, _ in CATEGORIES:
                print(f" [{num}] {name}")
            print(" [7] ALL Categories")
            cat_choice = input("Category [1-7] (default 1 - Wall Lights): ").strip() or "1"
            
            selected_cat = "wall_lights"
            if cat_choice == "7":
                selected_cat = "all"
            else:
                for num, name, key, _ in CATEGORIES:
                    if cat_choice == num:
                        selected_cat = key
                        break

            count_str = input("Ilang pending records ang ipo-process? (default: 1): ").strip() or "1"
            try:
                count = max(1, int(count_str))
            except ValueError:
                count = 1

            cmd = [
                sys.executable,
                str(folder / "2_Generate_Pending_Stories.py"),
                "--target",
                selected_cat,
                "--count",
                str(count),
            ]
            subprocess.run(cmd)

        elif choice == "3":
            print("\nPiliin ang category na ise-scrape mula Akeneo:")
            for num, name, key, script_name in CATEGORIES:
                print(f" [{num}] {name}")
            cat_choice = input("Category [1-6] (default 1 - Wall Lights): ").strip() or "1"

            target_script = folder / "3_Scrape_Akeneo_Wall_Lights.py"
            for num, name, key, script_name in CATEGORIES:
                if cat_choice == num:
                    target_script = folder / script_name
                    break

            rows_str = input("Ilang pairs / rows ang ise-scrape? (default: 1): ").strip() or "1"
            try:
                rows = max(1, int(rows_str))
            except ValueError:
                rows = 1

            cmd = [sys.executable, str(target_script), "--rows", str(rows)]
            subprocess.run(cmd)

        elif choice == "4":
            print("\n[START] Running 1 pair end-to-end for all categories...")
            cmd = [
                sys.executable,
                str(folder / "1_Run_Full_Story_Automation.py"),
                "--target",
                "all",
                "--count",
                "1",
            ]
            subprocess.run(cmd)

        else:
            print("\n[WARNING] Hindi wastong pagpipilian. Subukan muli.")

        input("\nPress ENTER para bumalik sa menu...")


def main():
    try:
        run_interactive_menu()
    except KeyboardInterrupt:
        print("\n[INFO] Exited This or That Story Menu.")


if __name__ == "__main__":
    main()
