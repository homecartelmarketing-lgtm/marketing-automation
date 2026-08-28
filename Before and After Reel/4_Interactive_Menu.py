"""Interactive Terminal Menu for Before & After Reel Automation.

Run this script to launch a user-friendly console menu that dynamically reads all
built-in and custom tables defined in .env.

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


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print("\n" + "=" * 68)
    print(" 🎬 HomeCartel - Before & After Reel Automation Menu (.env Driven)")
    print("=" * 68)


def run_interactive_menu():
    folder = Path(__file__).resolve().parent
    parent_dir = folder.parent

    while True:
        tables = get_reel_tables()
        table_keys = list(tables.keys())

        print_banner()
        print(" [A] 🚀 RUN FULL AUTOMATION (Scrape -> Krea -> Claude -> Nano Banana -> Video)")
        for idx, key in enumerate(table_keys, start=1):
            info = tables[key]
            t_id = os.getenv(info.get("env_table_key", ""), "").strip() or info.get("default_table_id", "")
            cat = info.get("akeneo_category") or info.get("category_code", "")
            custom_tag = " (Custom .env)" if info.get("is_custom") else ""
            print(f"     [{idx}] {info['label']}{custom_tag} [Table: {t_id} | Scrape: {cat}]")

        print("\n [B] 🎬 GENERATE VIDEOS ONLY (Compile existing Airtable photos into Reels)")
        print(" [C] 🔍 SCRAPE NEW PRODUCTS ONLY (Akeneo -> Airtable)")
        print(" [0] 🚪 Exit")
        print("-" * 68)

        choice = input(f" Piliin ang numero o aksyon [1-{len(table_keys)}, B, C, 0]: ").strip().lower()

        if choice in ("0", "exit", "q"):
            print("\n[INFO] Exited Before & After Reel Menu. Salamat!\n")
            break

        # Direct number selection for Full Automation
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(table_keys):
                selected_key = table_keys[num - 1]
                cmd = [sys.executable, str(parent_dir / "run_before_after_reel.py"), "--target", selected_key]
                subprocess.run(cmd)
            else:
                print("\n[WARNING] Hindi wastong numero.")
        elif choice == "a":
            print("\nPiliin ang target table para sa Full Automation:")
            for idx, key in enumerate(table_keys, start=1):
                print(f" [{idx}] {tables[key]['label']}")
            sub = input(f"Piliin [1-{len(table_keys)}]: ").strip()
            if sub.isdigit() and 1 <= int(sub) <= len(table_keys):
                selected_key = table_keys[int(sub) - 1]
                cmd = [sys.executable, str(parent_dir / "run_before_after_reel.py"), "--target", selected_key]
                subprocess.run(cmd)
        elif choice == "b":
            print("\nPiliin ang target table para sa Video Compilation:")
            for idx, key in enumerate(table_keys, start=1):
                print(f" [{idx}] {tables[key]['label']}")
            sub = input(f"Piliin [1-{len(table_keys)}]: ").strip()
            if sub.isdigit() and 1 <= int(sub) <= len(table_keys):
                selected_key = table_keys[int(sub) - 1]
                cmd = [sys.executable, str(folder / "2_Generate_Videos_Only.py"), "--target", selected_key]
                subprocess.run(cmd)
        elif choice == "c":
            print("\nPiliin ang target table para mag-scrape ng bagong items:")
            for idx, key in enumerate(table_keys, start=1):
                print(f" [{idx}] {tables[key]['label']} (Category: {tables[key].get('akeneo_category', '')})")
            sub = input(f"Piliin [1-{len(table_keys)}]: ").strip()
            if sub.isdigit() and 1 <= int(sub) <= len(table_keys):
                selected_key = table_keys[int(sub) - 1]
                cmd = [sys.executable, str(parent_dir / "run_before_after_reel.py"), "--target", selected_key, "--max-items", "1"]
                subprocess.run(cmd)
        else:
            print("\n[WARNING] Hindi wastong pagpipilian. Subukan muli.")

        input("\nPress ENTER para bumalik sa menu...")


def main():
    try:
        run_interactive_menu()
    except KeyboardInterrupt:
        print("\n[INFO] Exited Before & After Reel Menu.")


if __name__ == "__main__":
    main()
