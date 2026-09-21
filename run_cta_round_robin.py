"""Multi-Table Round-Robin CTA Story Orchestrator.

Processes 1 complete row (Phases 1-6) per table, then loops back
to the beginning of the table queue for subsequent rounds.

Usage:
    # Run 1 round across all 5 CTA tables (1 row each = 5 rows total):
    python run_cta_round_robin.py --rounds 1

    # Run 3 continuous rounds across all CTA tables (3 rows per table):
    python run_cta_round_robin.py --rounds 3 --delay 5

    # Run infinite continuous loop (stop with Ctrl+C):
    python run_cta_round_robin.py --infinite

    # Run only specific subset of tables:
    python run_cta_round_robin.py --categories table_lamps_cta_story chandelier_cta_story
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from typing import Sequence

from generate_cta_story_pipeline import find_cta_table_by_category, run_pipeline


# Verified CTA categories with their human-readable labels
DEFAULT_CTA_CATEGORIES = [
    ("chandelier_cta_story", "CTA Story Chandelier"),
    ("table_lamps_cta_story", "CTA Story Table Lamp"),
    ("cluster_chandelier_cta_story", "CTA Story Cluster Chandelier"),
    ("pendant_lights_cta_story", "CTA Story Pendant Light"),
    ("floor_lamp_cta_story", "CTA Story Floor Lamp"),
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CTA Story automation across multiple tables in round-robin order."
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of round-robin cycles to execute across all tables (default: 1).",
    )
    parser.add_argument(
        "--infinite",
        action="store_true",
        help="Run continuously in an infinite loop until interrupted (Ctrl+C).",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=[code for code, _ in DEFAULT_CTA_CATEGORIES],
        help="List of category codes to cycle through.",
    )
    parser.add_argument(
        "--style",
        type=str,
        default="modern",
        help="Akeneo style code to filter during scrape (default: modern).",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Delay in seconds between table switches (default: 5s).",
    )
    parser.add_argument(
        "--menu",
        action="store_true",
        help="Display interactive round-robin configuration menu.",
    )
    return parser.parse_args(argv)


def run_round_robin(
    categories: list[str],
    total_rounds: int,
    is_infinite: bool,
    style_code: str,
    delay_seconds: int,
) -> int:
    category_map = dict(DEFAULT_CTA_CATEGORIES)
    selected_targets = [
        (code, category_map.get(code, code))
        for code in categories
    ]

    total_tables = len(selected_targets)
    current_round = 1
    total_successes = 0
    total_failures = 0

    print("=" * 70)
    print("CTA STORY ROUND-ROBIN MULTI-TABLE RUNNER")
    print(f"Target Tables ({total_tables}):")
    for code, label in selected_targets:
        print(f"  - {label} (`{code}`)")
    mode_label = "INFINITE CONTINUOUS LOOP" if is_infinite else f"{total_rounds} ROUND(S)"
    print(f"Execution Mode: {mode_label}")
    print(f"Inter-table Delay: {delay_seconds}s")
    print("=" * 70)

    try:
        while True:
            round_header = f" ROUND {current_round}" + ("" if is_infinite else f" / {total_rounds}") + " "
            print(f"\n{round_header.center(70, '=')}")
            print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            round_successes = 0
            round_failures = 0

            for table_idx, (cat_code, cat_label) in enumerate(selected_targets, start=1):
                print("-" * 70)
                print(f"[ROUND {current_round} | TABLE {table_idx}/{total_tables}] -> {cat_label} ({cat_code})")
                print(f"Executing 1 complete row (Phases 1 -> 6)...")
                print("-" * 70)

                target_table_id = None
                found = find_cta_table_by_category(cat_code)
                if found:
                    target_table_id = found[0]

                try:
                    # Execute 1 single row end-to-end for this table
                    exit_code = run_pipeline(
                        mode="all",
                        category_code=cat_code,
                        table_id_override=target_table_id,
                        style_code=style_code,
                        max_items=1,
                    )

                    if exit_code == 0:
                        print(f"\n[OK] Successfully completed 1 row for {cat_label}.")
                        round_successes += 1
                        total_successes += 1
                    else:
                        print(f"\n[ERROR] Row execution failed for {cat_label} (Exit Code: {exit_code}).")
                        round_failures += 1
                        total_failures += 1

                except Exception as err:
                    print(f"\n[CRITICAL] Unhandled exception on table {cat_label}: {err}")
                    round_failures += 1
                    total_failures += 1

                # Cooldown before switching to next table
                if table_idx < total_tables or (not is_infinite and current_round < total_rounds):
                    time.sleep(max(1, delay_seconds))

            print("\n" + "-" * 70)
            print(
                f"ROUND {current_round} FINISHED: {round_successes}/{total_tables} tables succeeded, "
                f"{round_failures} failed."
            )
            print("-" * 70)

            if not is_infinite and current_round >= total_rounds:
                break

            current_round += 1
            if delay_seconds > 0:
                print(f"[INFO] Pausing for {delay_seconds}s before starting Round {current_round}...")
                time.sleep(delay_seconds)

    except KeyboardInterrupt:
        print("\n[INFO] User interrupted execution (Ctrl+C). Exiting safely.")

    print("\n" + "=" * 70)
    print("FINAL SUMMARY REPORT")
    print(f"Total Rounds Completed : {current_round if is_infinite else min(current_round, total_rounds)}")
    print(f"Total Successful Rows  : {total_successes}")
    print(f"Total Failed Rows      : {total_failures}")
    print("=" * 70)

    return 1 if total_failures > 0 else 0


def show_round_robin_menu() -> tuple[list[str], int, bool, int, bool]:
    """Display interactive console menu for CTA Story Round-Robin automation."""
    print("\n" + "=" * 68)
    print("      CTA STORY MULTI-TABLE ROUND-ROBIN ORCHESTRATOR MENU      ")
    print("=" * 68)
    print(" Target Tables available:")
    for idx, (cat_code, cat_name) in enumerate(DEFAULT_CTA_CATEGORIES, 1):
        print(f"  [{idx}] {cat_name} (`{cat_code}`)")
    print("=" * 68)
    print(" Select execution mode:\n")
    print(" [1] 1 Round across all 5 CTA Tables (1 complete row each)")
    print(" [2] Custom Number of Rounds across all tables")
    print(" [3] Continuous Infinite Loop (Ctrl+C to stop)")
    print(" [4] Select Specific Subset of Tables to cycle through")
    print(" [5] Launch Single-Table CTA Story Pipeline Menu")
    print(" [0] Exit\n")

    while True:
        choice = input(" Enter choice [0-5] (default: 1): ").strip()
        if not choice:
            choice = "1"

        if choice in ("0", "q", "exit", "quit"):
            print("[INFO] Exiting Round-Robin Menu. Goodbye!")
            sys.exit(0)

        elif choice == "1":
            return [c for c, _ in DEFAULT_CTA_CATEGORIES], 1, False, 5, False

        elif choice == "2":
            num_str = input(" Enter number of rounds to run [default: 2]: ").strip()
            rounds = int(num_str) if num_str.isdigit() and int(num_str) > 0 else 2
            delay_str = input(" Inter-table delay in seconds [default: 5]: ").strip()
            delay = int(delay_str) if delay_str.isdigit() else 5
            return [c for c, _ in DEFAULT_CTA_CATEGORIES], rounds, False, delay, False

        elif choice == "3":
            delay_str = input(" Inter-table delay in seconds [default: 5]: ").strip()
            delay = int(delay_str) if delay_str.isdigit() else 5
            return [c for c, _ in DEFAULT_CTA_CATEGORIES], 1, True, delay, False

        elif choice == "4":
            print("\n Select tables to include (comma-separated numbers, e.g. '1,3,4'):")
            for idx, (cat_code, cat_name) in enumerate(DEFAULT_CTA_CATEGORIES, 1):
                print(f"  [{idx}] {cat_name}")
            sub_choice = input(" Choice: ").strip()
            selected = []
            for part in sub_choice.split(","):
                part = part.strip()
                if part.isdigit():
                    idx = int(part)
                    if 1 <= idx <= len(DEFAULT_CTA_CATEGORIES):
                        selected.append(DEFAULT_CTA_CATEGORIES[idx - 1][0])
            if not selected:
                print("[WARN] No valid tables selected. Using all tables.")
                selected = [c for c, _ in DEFAULT_CTA_CATEGORIES]

            rounds_str = input(" Number of rounds (or 'inf' for infinite) [default: 1]: ").strip().lower()
            is_inf = rounds_str in ("inf", "infinite")
            rounds = 1 if is_inf else (int(rounds_str) if rounds_str.isdigit() and int(rounds_str) > 0 else 1)
            delay_str = input(" Inter-table delay in seconds [default: 5]: ").strip()
            delay = int(delay_str) if delay_str.isdigit() else 5
            return selected, rounds, is_inf, delay, False

        elif choice == "5":
            return [], 0, False, 0, True

        print("[WARN] Invalid option. Please enter 0 to 5.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.menu or (argv is None and len(sys.argv) == 1 and sys.stdin.isatty()):
        categories, rounds, infinite, delay, open_pipeline = show_round_robin_menu()
        if open_pipeline:
            from generate_cta_story_pipeline import run_pipeline
            return run_pipeline(mode="menu")
        return run_round_robin(
            categories=categories,
            total_rounds=rounds,
            is_infinite=infinite,
            style_code=args.style,
            delay_seconds=delay,
        )

    return run_round_robin(
        categories=args.categories,
        total_rounds=args.rounds,
        is_infinite=args.infinite,
        style_code=args.style,
        delay_seconds=args.delay,
    )


if __name__ == "__main__":
    raise SystemExit(main())
