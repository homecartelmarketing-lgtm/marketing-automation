"""CLI: scrape Akeneo products and/or generate Krea room-interior photos.

Run with no arguments in a terminal for the interactive menu. The
implementation lives in ``content_automation.scraping``.
"""

from __future__ import annotations

import argparse
import sys

from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.krea_client import KreaClient
from content_automation.scraping import (
    InteriorRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import items_per_row, moodboard_id_for_category
from standalone_scrape_akeneo import run_category_scrape

# Only these tables have interior moodboards configured.
INTERIOR_CATEGORIES = (
    "chandeliers",
    "pendant_lights",
    "floor_lamps",
    "linear_chandeliers",
)

MENU_CHOICES = {
    "1": "scrape",
    "2": "interior",
    "3": "all",
    "4": "exit",
}


def show_menu() -> str:
    print("\n" + "=" * 64)
    print("           HOME CARTEL AUTO SCRAPE & KREA AI MENU           ")
    print("=" * 64)
    print(" Select an action to perform:\n")
    print(" [1] Scrape Akeneo Products to Airtable")
    print(" [2] Generate Krea AI Room Interior Photos (Interior to Interior10)")
    print(" [3] Run Both (Scrape Akeneo + Generate Interior Photos)")
    print(" [4] Exit\n")

    while True:
        choice = input(" Enter choice [1-4]: ").strip()
        if choice in MENU_CHOICES:
            return MENU_CHOICES[choice]
        print("[WARN] Invalid option. Please enter 1, 2, 3, or 4.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Krea AI Room Interior Photo Generator & Menu Selector"
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["scrape", "interior", "all", "menu"],
        default=None,
        help="Mode of operation: scrape, interior, all, or menu",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=[*INTERIOR_CATEGORIES, "all"],
        default="all",
        help=f"Category to process: {', '.join(INTERIOR_CATEGORIES)}, or all",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=None,
        help="Style code filter in Akeneo (default: AKENEO_STYLE from .env)",
    )
    return parser.parse_args(argv)


def run_category_interior(category_code: str, style_code: str | None = None) -> bool:
    """Generate interior photos for one category. True when nothing failed."""
    base = load_settings()
    base.require({"krea"})
    settings = load_scrape_settings(
        category_code=category_code, style_code=style_code, settings=base
    )
    moodboard_id = moodboard_id_for_category(settings.category_code)

    print("=" * 64)
    print(f"Krea AI Interior Photo Generator | {settings.category_label.title()}")
    print(
        f"Airtable destination ({settings.category_code}): "
        f"{settings.airtable_base_id} / {settings.airtable_table_id}"
    )
    print(f"Krea Moodboard ID: {moodboard_id or '<none configured>'}")
    print("=" * 64)

    runner = InteriorRunner(
        krea=KreaClient(base.krea_token, base.krea_base_url),
        airtable=ScrapeAirtableClient(
            settings.airtable_token,
            settings.airtable_base_id,
            settings.airtable_table_id,
        ),
        moodboard_id=moodboard_id,
        slot_count=items_per_row(settings.category_code),
    )
    return runner.generate_for_records()


def _run_phase(banner: str, categories: list[str], run, style_code) -> tuple[int, bool]:
    """Run one phase over every category. Returns (failures, interrupted)."""
    print(banner)
    failures = 0
    for category in categories:
        try:
            if not run(category, style_code=style_code):
                failures += 1
        except KeyboardInterrupt:
            print("\n[WARN] Operation cancelled by user")
            return failures, True
        except Exception as error:
            print(f"[ERROR] Fatal error processing {category}: {error}")
            failures += 1
    return failures, False


def resolve_mode(mode: str | None) -> str:
    """Fall back to the menu when interactive, and to 'all' when piped."""
    if mode is not None:
        return mode
    return show_menu() if sys.stdin.isatty() else "all"


def main(argv=None) -> int:
    args = parse_args(argv)
    mode = resolve_mode(args.mode)
    if mode == "exit":
        print("[INFO] Exiting menu.")
        return 0

    categories = (
        list(INTERIOR_CATEGORIES) if args.category == "all" else [args.category]
    )

    failures = 0
    phases = []
    if mode in ("scrape", "all"):
        phases.append((">>> STARTING PRODUCT SCRAPING PHASE <<<", run_category_scrape))
    if mode in ("interior", "all"):
        phases.append(
            (
                "\n>>> STARTING KREA AI INTERIOR PHOTO GENERATION PHASE <<<",
                run_category_interior,
            )
        )

    for banner, run in phases:
        phase_failures, interrupted = _run_phase(
            banner, categories, run, args.style
        )
        failures += phase_failures
        if interrupted:
            return 130

    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
