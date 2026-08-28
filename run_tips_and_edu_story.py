"""Run the isolated, resumable Tips & Edu Story automation."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from content_automation.errors import AutomationError
from content_automation.isolated_config import IsolatedAutomationSettings
from content_automation.phased_content import (
    PhasedContentRunner,
    PipelineDefinition,
    TIPS_EDU_STORY,
    TIPS_EDU_STORY_CEILING_MOUNTED,
    TIPS_EDU_STORY_CHANDELIER,
    TIPS_EDU_STORY_CLUSTER_CHANDELIER,
    TIPS_EDU_STORY_FLOOR_LAMP,
    TIPS_EDU_STORY_PENDANT,
    TIPS_EDU_STORY_TABLE_LAMP,
    TIPS_EDU_STORY_PIPELINES,
)

TIPS_EDU_STORY_PRESETS: list[tuple[str, PipelineDefinition]] = [
    ("Pendant Light Tips & Edu Story", TIPS_EDU_STORY_PENDANT),
    ("Floor Lamp Tips & Edu Story", TIPS_EDU_STORY_FLOOR_LAMP),
    ("Chandelier Tips & Edu Story", TIPS_EDU_STORY_CHANDELIER),
    ("Ceiling Mounted Tips & Edu Story", TIPS_EDU_STORY_CEILING_MOUNTED),
    ("Table Lamp Tips & Edu Story", TIPS_EDU_STORY_TABLE_LAMP),
    ("Cluster Chandelier Tips & Edu Story", TIPS_EDU_STORY_CLUSTER_CHANDELIER),
]


def resolve_tips_edu_story_pipeline(
    target_arg: str | None = None,
    table_id_arg: str | None = None,
    prompt_if_interactive: bool = True,
) -> PipelineDefinition:
    """Resolve which Tips & Edu Story destination table/category to run."""
    # 1. Check table_id_arg first
    if table_id_arg:
        tid = table_id_arg.strip()
        if tid in TIPS_EDU_STORY_PIPELINES:
            return TIPS_EDU_STORY_PIPELINES[tid]
        return dataclasses.replace(TIPS_EDU_STORY_PENDANT, table_id=tid)

    # 2. Check target_arg
    if target_arg:
        raw = target_arg.strip().lower()
        if raw in ("1", "pendant_lights", "pendant_light", "pendant", "tblwnfn5a8flzkup4"):
            return TIPS_EDU_STORY_PENDANT
        if raw in ("2", "floor_lamps", "floor_lamp", "floor", "tbljxwzexgbhl26b"):
            return TIPS_EDU_STORY_FLOOR_LAMP
        if raw in ("3", "chandeliers", "chandelier", "tblpfiann1ym9fttk"):
            return TIPS_EDU_STORY_CHANDELIER
        if raw in ("4", "ceiling_mounted", "ceiling", "ceiling_light", "ceiling_lights", "tblglribuzxb9r3gt"):
            return TIPS_EDU_STORY_CEILING_MOUNTED
        if raw in ("5", "table_lamps", "table_lamp", "table", "tblztenqildaeklv2"):
            return TIPS_EDU_STORY_TABLE_LAMP
        if raw in ("6", "cluster_chandeliers", "cluster_chandelier", "cluster", "tbllzke2prsyj9bad"):
            return TIPS_EDU_STORY_CLUSTER_CHANDELIER
        if raw in TIPS_EDU_STORY_PIPELINES:
            return TIPS_EDU_STORY_PIPELINES[raw]

    # 3. Interactive prompt
    if prompt_if_interactive:
        print("\n" + "=" * 64)
        print("Select Tips & Edu Story Destination Table:")
        print("=" * 64)
        for idx, (label, defn) in enumerate(TIPS_EDU_STORY_PRESETS, start=1):
            print(f"  [{idx}] {label}")
            print(f"      Table ID: {defn.table_id} | Category: {defn.category_code}")
            print(f"      Moodboard: {defn.moodboard_id}")
        print("=" * 64)
        try:
            choice = input(f"Enter choice [1-{len(TIPS_EDU_STORY_PRESETS)}] (default: 1): ").strip().lower()
            if choice:
                if choice in ("1", "pendant_lights", "pendant_light", "pendant", "tblwnfn5a8flzkup4"):
                    return TIPS_EDU_STORY_PENDANT
                if choice in ("2", "floor", "floor_lamp", "floor_lamps", "tbljxwzexgbhl26b"):
                    return TIPS_EDU_STORY_FLOOR_LAMP
                if choice in ("3", "chandelier", "chandeliers", "tblpfiann1ym9fttk"):
                    return TIPS_EDU_STORY_CHANDELIER
                if choice in ("4", "ceiling", "ceiling_mounted", "ceiling_light", "ceiling_lights", "tblglribuzxb9r3gt"):
                    return TIPS_EDU_STORY_CEILING_MOUNTED
                if choice in ("5", "table", "table_lamp", "table_lamps", "tblztenqildaeklv2"):
                    return TIPS_EDU_STORY_TABLE_LAMP
                if choice in ("6", "cluster", "cluster_chandelier", "cluster_chandeliers", "tbllzke2prsyj9bad"):
                    return TIPS_EDU_STORY_CLUSTER_CHANDELIER
                if choice in TIPS_EDU_STORY_PIPELINES:
                    return TIPS_EDU_STORY_PIPELINES[choice]
            return TIPS_EDU_STORY_PENDANT
        except (EOFError, KeyboardInterrupt):
            pass

    return TIPS_EDU_STORY_PENDANT


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Tips & Edu Story: phases 1-5 or resumable full run."
    )
    parser.add_argument(
        "--phase",
        choices=("1", "2", "3", "4", "5", "all"),
        default="all",
        help="Run one phase, or resume all remaining phases (default: all).",
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=(
            "pendant_lights",
            "floor_lamps",
            "chandeliers",
            "ceiling_mounted",
            "table_lamps",
            "cluster_chandeliers",
            "pendant",
            "floor",
            "chandelier",
            "ceiling",
            "table",
            "cluster",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        ),
        default=None,
        help="Target category / table for Tips & Edu Story.",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override.",
    )
    parser.add_argument(
        "--env",
        type=Path,
        help="Optional path to the isolated Tips & Edu environment file.",
    )
    return parser.parse_args(argv)



def main(argv=None) -> int:
    args = parse_args(argv)
    settings = IsolatedAutomationSettings.load("tips_edu_story", env_path=args.env)
    pipeline = resolve_tips_edu_story_pipeline(
        target_arg=args.target,
        table_id_arg=args.table_id,
        prompt_if_interactive=True,
    )
    print("=" * 64)
    print(f"Starting Tips & Edu Story: {pipeline.category_code}")
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
