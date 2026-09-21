"""Run the isolated, resumable Tips & Edu Story automation."""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from pathlib import Path

from content_automation.airtable_client import fetch_multiple_tables_status_breakdown
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
    apply_tips_edu_story_settings,
)

TIPS_EDU_STORY_PRESETS: list[tuple[str, PipelineDefinition]] = [
    ("Pendant Light Tips & Edu Story", TIPS_EDU_STORY_PENDANT),
    ("Floor Lamp Tips & Edu Story", TIPS_EDU_STORY_FLOOR_LAMP),
    ("Chandelier Tips & Edu Story", TIPS_EDU_STORY_CHANDELIER),
    ("Ceiling Mounted Tips & Edu Story", TIPS_EDU_STORY_CEILING_MOUNTED),
    ("Table Lamp Tips & Edu Story", TIPS_EDU_STORY_TABLE_LAMP),
    ("Cluster Chandelier Tips & Edu Story", TIPS_EDU_STORY_CLUSTER_CHANDELIER),
]


def get_tips_edu_story_presets(workspace: Path | None = None) -> list[tuple[str, PipelineDefinition]]:
    """Return active presets with any overrides from settings.json applied."""
    return [
        (label, apply_tips_edu_story_settings(defn, workspace=workspace))
        for label, defn in TIPS_EDU_STORY_PRESETS
    ]


def resolve_tips_edu_story_pipeline(
    target_arg: str | None = None,
    table_id_arg: str | None = None,
    prompt_if_interactive: bool = True,
    workspace: Path | None = None,
) -> PipelineDefinition:
    """Resolve which Tips & Edu Story destination table/category to run."""
    presets = get_tips_edu_story_presets(workspace)

    # 1. Check table_id_arg first
    if table_id_arg:
        tid = table_id_arg.strip()
        for _, defn in presets:
            if defn.table_id.lower() == tid.lower():
                return defn
        if tid in TIPS_EDU_STORY_PIPELINES:
            return apply_tips_edu_story_settings(TIPS_EDU_STORY_PIPELINES[tid], workspace)
        return apply_tips_edu_story_settings(dataclasses.replace(TIPS_EDU_STORY_PENDANT, table_id=tid), workspace)

    # 2. Check target_arg
    if target_arg:
        raw = target_arg.strip().lower()
        if raw in ("1", "pendant_lights", "pendant_light", "pendant") or (presets[0][1].table_id.lower() == raw):
            return presets[0][1]
        if raw in ("2", "floor_lamps", "floor_lamp", "floor") or (presets[1][1].table_id.lower() == raw):
            return presets[1][1]
        if raw in ("3", "chandeliers", "chandelier") or (presets[2][1].table_id.lower() == raw):
            return presets[2][1]
        if raw in ("4", "ceiling_mounted", "ceiling", "ceiling_light", "ceiling_lights") or (presets[3][1].table_id.lower() == raw):
            return presets[3][1]
        if raw in ("5", "table_lamps", "table_lamp", "table") or (presets[4][1].table_id.lower() == raw):
            return presets[4][1]
        if raw in ("6", "cluster_chandeliers", "cluster_chandelier", "cluster") or (presets[5][1].table_id.lower() == raw):
            return presets[5][1]
        for _, defn in presets:
            if defn.category_code.lower() == raw or defn.table_id.lower() == raw:
                return defn
        if raw in TIPS_EDU_STORY_PIPELINES:
            return apply_tips_edu_story_settings(TIPS_EDU_STORY_PIPELINES[raw], workspace)

    # 3. Interactive prompt
    if prompt_if_interactive:
        token = os.getenv("AIRTABLE_TOKEN") or ""
        base_id = os.getenv("AIRTABLE_BASE_ID") or ""
        if not (token and base_id):
            try:
                settings_temp = IsolatedAutomationSettings.load("tips_edu_story", workspace=workspace)
                token = settings_temp.airtable_token or token
                base_id = settings_temp.airtable_base_id or base_id
            except Exception:
                pass

        table_ids = [defn.table_id for _, defn in presets if defn.table_id]
        status_map: dict[str, dict[str, int]] = {}
        if token and base_id and table_ids:
            try:
                status_map = fetch_multiple_tables_status_breakdown(token, base_id, table_ids, max_workers=6)
            except Exception:
                pass

        print("\n" + "=" * 68)
        print("          SELECT TIPS & EDU STORY DESTINATION TABLE")
        print("=" * 68)
        for idx, (label, defn) in enumerate(presets, start=1):
            prompt_str = defn.interior_prompt or (defn.interior_prompts[0] if defn.interior_prompts else "N/A")
            st = status_map.get(defn.table_id)
            if st:
                status_line = f"P: {st['P']} | C: {st['C']} | D: {st['D']} | FM: {st['FM']} (Completed: {st['P'] + st['C']})"
            else:
                status_line = "P: - | C: - | D: - | FM: -"

            print(f"  [{idx}] {label}")
            print(f"      Table ID:  {defn.table_id}")
            print(f"      Category:  {defn.category_code}")
            print(f"      Moodboard: {defn.moodboard_id}")
            print(f"      Prompt:    \"{prompt_str}\"")
            print(f"      Status:    {status_line}\n")
        print("=" * 68)
        try:
            choice = input(f"Enter choice [1-{len(presets)}] (default: 1): ").strip().lower()
            if choice:
                if choice in ("1", "pendant_lights", "pendant_light", "pendant") or (presets[0][1].table_id.lower() == choice):
                    return presets[0][1]
                if choice in ("2", "floor", "floor_lamp", "floor_lamps") or (presets[1][1].table_id.lower() == choice):
                    return presets[1][1]
                if choice in ("3", "chandelier", "chandeliers") or (presets[2][1].table_id.lower() == choice):
                    return presets[2][1]
                if choice in ("4", "ceiling", "ceiling_mounted", "ceiling_light", "ceiling_lights") or (presets[3][1].table_id.lower() == choice):
                    return presets[3][1]
                if choice in ("5", "table", "table_lamp", "table_lamps") or (presets[4][1].table_id.lower() == choice):
                    return presets[4][1]
                if choice in ("6", "cluster", "cluster_chandelier", "cluster_chandeliers") or (presets[5][1].table_id.lower() == choice):
                    return presets[5][1]
                for _, defn in presets:
                    if defn.category_code.lower() == choice or defn.table_id.lower() == choice:
                        return defn
                if choice in TIPS_EDU_STORY_PIPELINES:
                    return apply_tips_edu_story_settings(TIPS_EDU_STORY_PIPELINES[choice], workspace)
            return presets[0][1]
        except (EOFError, KeyboardInterrupt):
            pass

    return presets[0][1]


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
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Optional custom Krea Moodboard ID override.",
    )
    parser.add_argument(
        "--prompt",
        "-p",
        default=None,
        help="Optional custom Krea interior generation prompt override.",
    )
    return parser.parse_args(argv)



def main(argv=None) -> int:
    args = parse_args(argv)
    settings = IsolatedAutomationSettings.load("tips_edu_story", env_path=args.env)
    pipeline = resolve_tips_edu_story_pipeline(
        target_arg=args.target,
        table_id_arg=args.table_id,
        prompt_if_interactive=True,
        workspace=settings.workspace,
    )
    if args.moodboard_id and args.moodboard_id.strip():
        pipeline = dataclasses.replace(pipeline, moodboard_id=args.moodboard_id.strip())
    if args.prompt and args.prompt.strip():
        pipeline = dataclasses.replace(pipeline, interior_prompt=args.prompt.strip())
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
