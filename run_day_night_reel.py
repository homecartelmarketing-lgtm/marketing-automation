"""Run the isolated, resumable Day & Night Reel automation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from content_automation.errors import AutomationError
from content_automation.isolated_config import IsolatedAutomationSettings
import dataclasses
from content_automation.phased_content import (
    DAY_NIGHT_REEL,
    DAY_NIGHT_REEL_CHANDELIER,
    DAY_NIGHT_REEL_FLOOR_LAMP,
    DAY_NIGHT_REEL_PENDANT,
    DAY_NIGHT_REEL_PIPELINES,
    PipelineDefinition,
    PhasedContentRunner,
)


def resolve_day_night_pipeline(
    target_arg: str | None = None,
    table_id_arg: str | None = None,
    prompt_if_interactive: bool = True,
) -> PipelineDefinition:
    """Resolve which Day & Night Reel destination table/category to run."""
    # 1. Check table_id_arg first
    if table_id_arg:
        tid = table_id_arg.strip()
        if tid in DAY_NIGHT_REEL_PIPELINES:
            return DAY_NIGHT_REEL_PIPELINES[tid]
        return dataclasses.replace(DAY_NIGHT_REEL_PENDANT, table_id=tid)

    # 2. Check target_arg
    if target_arg:
        raw = target_arg.strip().lower()
        if raw in ("1", "pendant_lights", "pendant_light", "pendant", "tblktum627s2f0ftn", "tbl35jyslnuwh61tl"):
            return DAY_NIGHT_REEL_PENDANT
        if raw in ("2", "chandeliers", "chandelier", "tblodnfanvp6sxn0a"):
            return DAY_NIGHT_REEL_CHANDELIER
        if raw in ("3", "floor_lamps", "floor_lamp", "floor", "tbl2vowot7ssut4e2"):
            return DAY_NIGHT_REEL_FLOOR_LAMP
        if raw in DAY_NIGHT_REEL_PIPELINES:
            return DAY_NIGHT_REEL_PIPELINES[raw]

    # 3. Interactive prompt
    if prompt_if_interactive:
        print("\n" + "=" * 64)
        print("Select Day & Night Reel Destination Table:")
        print("=" * 64)
        print("  [1] Pendant Light Day & Night Reel")
        print("      Table ID: tblkTuM627s2f0FTN | Category: pendant_lights")
        print("      Moodboard: de5f4ff8-518c-4d6b-b606-ce1d5dac51f3")
        print("  [2] Chandelier Day & Night Reel")
        print("      Table ID: tblODnfaNVP6SXn0A | Category: chandeliers")
        print("      Moodboard: b5ffdcbb-192e-4528-8d86-d1a4cf496887")
        print("  [3] Floor Lamp Day & Night Reel")
        print("      Table ID: tbl2VoWOt7sSut4E2 | Category: floor_lamps")
        print("      Moodboard: b1641228-beec-4823-8d01-1de3eec8410d")
        print("=" * 64)
        try:
            choice = input("Enter choice [1, 2, or 3] (default: 1): ").strip().lower()
            if choice in ("2", "chandelier", "chandeliers", "tblodnfanvp6sxn0a"):
                return DAY_NIGHT_REEL_CHANDELIER
            if choice in ("3", "floor", "floor_lamp", "floor_lamps", "tbl2vowot7ssut4e2"):
                return DAY_NIGHT_REEL_FLOOR_LAMP
            return DAY_NIGHT_REEL_PENDANT
        except (EOFError, KeyboardInterrupt):
            pass

    return DAY_NIGHT_REEL_PENDANT


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Day & Night Reel: phases 1-8 or resumable full run."
    )
    parser.add_argument(
        "--phase",
        choices=("1", "2", "3", "4", "5", "6", "7", "8", "all"),
        default="all",
        help="Run one phase, or resume all remaining phases (default: all).",
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=(
            "pendant_lights",
            "chandeliers",
            "floor_lamps",
            "pendant",
            "chandelier",
            "floor",
            "1",
            "2",
            "3",
        ),
        default=None,
        help="Target category / table for Day & Night Reel.",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override.",
    )
    parser.add_argument(
        "--env",
        type=Path,
        help="Optional path to the isolated Day & Night environment file.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = IsolatedAutomationSettings.load("day_night_reel", env_path=args.env)
    pipeline = resolve_day_night_pipeline(
        target_arg=args.target,
        table_id_arg=args.table_id,
        prompt_if_interactive=True,
    )
    print("=" * 64)
    print(f"Starting Day & Night Reel: {pipeline.category_code}")
    print(f"Destination Table: {settings.airtable_base_id} / {pipeline.table_id}")
    print(f"Krea Moodboard ID: {pipeline.moodboard_id}")
    print(f"Interior Prompt: {pipeline.interior_prompt}")
    print("=" * 64)
    PhasedContentRunner(pipeline, settings).run(args.phase)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
