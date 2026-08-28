"""Interactive Terminal Menu for Before & After Reel Automation.

Run this script to launch a user-friendly console menu where you can choose
any action with a simple keypress (1 to 5).

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


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print("\n" + "=" * 65)
    print(" 🎬 HomeCartel - Before & After Reel Automation Menu")
    print("=" * 65)


def run_interactive_menu():
    folder = Path(__file__).resolve().parent

    while True:
        print_banner()
        print(" [1] 🚀 Run Full Automation (Floor Lamps - Default)")
        print(" [2] 🚀 Run Full Automation (Pendant Lights)")
        print(" [3] 🚀 Run Full Automation (Chandeliers)")
        print(" [4] 🎬 Generate Videos Only (Compile from existing images)")
        print(" [5] 🔍 Scrape 1 New Floor Lamp from Akeneo")
        print(" [6] 🔍 Scrape 1 New Pendant Light from Akeneo")
        print(" [7] 🔍 Scrape 1 New Chandelier from Akeneo")
        print(" [0] 🚪 Exit")
        print("-" * 65)

        choice = input(" Piliin ang nais mong gawin [0-7]: ").strip()

        if choice == "0":
            print("\n[INFO] Exited Before & After Reel Menu. Salamat!\n")
            break
        elif choice == "1":
            cmd = [sys.executable, str(folder / "1_Run_Full_Reel_Automation.py"), "--target", "floor_lamps"]
            subprocess.run(cmd)
        elif choice == "2":
            cmd = [sys.executable, str(folder / "1_Run_Full_Reel_Automation.py"), "--target", "pendant_lights"]
            subprocess.run(cmd)
        elif choice == "3":
            cmd = [sys.executable, str(folder / "1_Run_Full_Reel_Automation.py"), "--target", "chandeliers"]
            subprocess.run(cmd)
        elif choice == "4":
            print("\nPiliin ang target category:")
            print(" [1] Floor Lamps")
            print(" [2] Pendant Lights")
            print(" [3] Chandeliers")
            sub = input("Target [1-3]: ").strip()
            cat = "floor_lamps" if sub == "1" else ("pendant_lights" if sub == "2" else "chandeliers")
            cmd = [sys.executable, str(folder / "2_Generate_Videos_Only.py"), "--target", cat]
            subprocess.run(cmd)
        elif choice == "5":
            cmd = [sys.executable, str(folder / "3_Scrape_Akeneo_Floor_Lamps.py"), "--execute"]
            subprocess.run(cmd)
        elif choice == "6":
            cmd = [sys.executable, str(folder / "3_Scrape_Akeneo_Pendant_Lights.py"), "--execute"]
            subprocess.run(cmd)
        elif choice == "7":
            cmd = [sys.executable, str(folder / "3_Scrape_Akeneo_Chandeliers.py"), "--execute"]
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
