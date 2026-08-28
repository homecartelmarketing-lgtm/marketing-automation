"""Interactive Terminal Menu for Product Closeup w/ Description Story Automation.

Run this script to launch a user-friendly console menu where you can choose
any action with a simple keypress.

Usage:
    python "Product Closeup Description Story/4_Interactive_Menu.py"
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
    ("1", "Chandeliers", "chandeliers", "3_Scrape_Akeneo_Chandeliers.py"),
    ("2", "Pendant Lights", "pendant_lights", "3_Scrape_Akeneo_Pendant_Lights.py"),
    ("3", "Floor Lamps", "floor_lamps", "3_Scrape_Akeneo_Floor_Lamps.py"),
    ("4", "Cluster Chandeliers", "cluster_chandeliers", "3_Scrape_Akeneo_Cluster_Chandeliers.py"),
    ("5", "Table Lamps", "table_lamps", "3_Scrape_Akeneo_Table_Lamps.py"),
    ("6", "Wall Lights", "wall_lights", "3_Scrape_Akeneo_Wall_Lights.py"),
]


def print_banner():
    print("\n" + "=" * 70)
    print(" 💡  HomeCartel - Product Closeup w/ Description Story Automation Menu")
    print("=" * 70)


def run_interactive_menu():
    folder = Path(__file__).resolve().parent

    while True:
        print_banner()
        print(" [1] 🚀 Run Full Automation (Scrape Item -> Generate Story Card)")
        print(" [2] 🎨 Generate Stories Only (Process Pending Records in Airtable)")
        print(" [3] 🔍 Scrape Products Only from Akeneo (Pick Category)")
        print(" [4] ⚡ Run 1 Item for All 6 Categories (End-to-End)")
        print(" [0] 🚪 Exit")
        print("-" * 70)

        choice = input(" Piliin ang nais mong gawin [0-4]: ").strip()

        if choice == "0":
            print("\n[INFO] Exited Product Closeup Description Story Menu. Salamat!\n")
            break

        elif choice == "1":
            print("\nPiliin ang target category:")
            for num, name, key, _ in CATEGORIES:
                print(f" [{num}] {name}")
            print(" [7] ALL Categories")
            cat_choice = input("Category [1-7] (default 1 - Chandeliers): ").strip() or "1"

            selected_cat = "chandeliers"
            if cat_choice == "7":
                selected_cat = "all"
            else:
                for num, name, key, _ in CATEGORIES:
                    if cat_choice == num:
                        selected_cat = key
                        break

            count_str = input("Ilang products ang ipo-process? (default: 1): ").strip() or "1"
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
            cat_choice = input("Category [1-7] (default 1 - Chandeliers): ").strip() or "1"

            selected_cat = "chandeliers"
            if cat_choice == "7":
                selected_cat = "all"
            else:
                for num, name, key, _ in CATEGORIES:
                    if cat_choice == num:
                        selected_cat = key
                        break

            count_str = input("Ilang pending records ang i-gegenerate? (default: 1): ").strip() or "1"
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
            print("\nPiliin ang lighting category na i-i-scrape:")
            for num, name, _, script in CATEGORIES:
                print(f" [{num}] {name}")
            print(" [7] ALL Categories (Scrape 1 from each)")
            cat_choice = input("Category [1-7] (default 1 - Chandeliers): ").strip() or "1"

            count_str = input("Ilang products bawat category? (default: 1): ").strip() or "1"
            try:
                count = max(1, int(count_str))
            except ValueError:
                count = 1

            if cat_choice == "7":
                for _, _, _, script in CATEGORIES:
                    cmd = [
                        sys.executable,
                        str(folder / script),
                        "--count",
                        str(count),
                    ]
                    subprocess.run(cmd)
            else:
                matched_script = "3_Scrape_Akeneo_Chandeliers.py"
                for num, _, _, script in CATEGORIES:
                    if cat_choice == num:
                        matched_script = script
                        break
                cmd = [
                    sys.executable,
                    str(folder / matched_script),
                    "--count",
                    str(count),
                ]
                subprocess.run(cmd)

        elif choice == "4":
            print("\n⚡ Running 1 item for ALL 6 categories end-to-end...")
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
            print("[WARN] Maling pagpipilian. Pumili lamang sa 0 hanggang 4.")


if __name__ == "__main__":
    run_interactive_menu()
