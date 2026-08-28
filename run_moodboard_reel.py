"""Unified Moodboard Reel Automation Script.

Runs the complete 5-Phase end-to-end workflow for Moodboard Reels:
1. Scrapes Akeneo modern products (sorted Newest to Oldest) packed 4 per row into Airtable
2. Generates Krea AI Room Interiors (9:16, moodboard b5ffdcbb-192e-4528-8d86-d1a4cf496887)
3. Generates Vision Blending Prompts via Claude 3.5 Sonnet (Fal AI OpenRouter)
4. Blends Interior + Furniture via Fal AI Nano Banana Pro (fal-ai/nano-banana-pro/edit)
5. Converts blended images against reference template & compiles final 9:16 MP4 reel

Usage::

    python run_moodboard_reel.py
    python run_moodboard_reel.py --category chandelier_modern
    python run_moodboard_reel.py --category pendant_lights_reel
    python run_moodboard_reel.py --limit 1
    python run_moodboard_reel.py --phase 2.5
"""

from __future__ import annotations

import argparse
import sys

from content_automation.config import MOODBOARD_REEL_CATEGORIES, TABLES
from generate_moodboard_reel_pipeline import main as pipeline_main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Unified Moodboard Reel 5-Phase Automation"
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=MOODBOARD_REEL_CATEGORIES,
        default="chandelier_modern",
        help="Moodboard reel category table (default: chandelier_modern)",
    )
    parser.add_argument(
        "--phase",
        "-p",
        choices=["all", "1", "2", "2.5", "3", "4", "5", "scrape", "interior", "vision", "blend", "convert", "reel"],
        default="all",
        help="Run all phases or a specific phase (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run without writing to Airtable or calling billable AI APIs",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of records to process",
    )
    parser.add_argument(
        "--record-id",
        action="append",
        default=[],
        help="Target a specific record ID",
    )
    parser.add_argument(
        "--vision-model",
        default="anthropic/claude-sonnet-5",
        help="Claude Vision model on Fal AI OpenRouter (default: anthropic/claude-sonnet-5)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-generation of all phases even if output fields are already populated",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    pipeline_args = [
        "--category", args.category,
        "--phase", args.phase,
        "--vision-model", args.vision_model,
    ]
    if not args.dry_run:
        pipeline_args.append("--execute")
    if args.force:
        pipeline_args.append("--force")
    if args.limit:
        pipeline_args.extend(["--limit", str(args.limit)])
    for rec in args.record_id:
        pipeline_args.extend(["--record-id", rec])

    return pipeline_main(pipeline_args)


if __name__ == "__main__":
    raise SystemExit(main())
