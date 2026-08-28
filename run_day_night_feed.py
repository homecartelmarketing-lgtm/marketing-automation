"""End-to-End CLI Runner for Day & Night FEED Pipeline (4:5 Ratio).

This runner is DEDICATED SOLELY to Day & Night Feed (4:5 Ratio) targeting
table tblSceuLVvLMQ6wWp ("Day and Night Feed Chandelier"), completely separate
from Day & Night Story (9:16).

Workflow:
  1. Auto-Scrape (if needed): Scrapes new unique chandelier product(s) from Akeneo -> tblSceuLVvLMQ6wWp (Status: 'Standby')
  2. [Phase 1/4] Krea AI Interior Generation (4:5) -> 'Interior Generated Photo'
  3. [Phase 2/4] Claude Sonnet 5 Prompt Generation -> 'Blending Prompt'
  4. [Phase 3/4] Fal AI Nano Banana Pro Daytime Blending (4:5) -> 'Day Image'
  5. [Phase 4/4] Fal AI Nano Banana Pro Night Transformation (4:5) -> 'Night Image'
  6. [Upload & Complete] Sets Status to 'Complete'.

Usage::

    # Run 1 Feed row end-to-end (Scrape 1 item if needed -> Generate 4:5 Feed -> Complete):
    python run_day_night_feed.py

    # Run specific number of Feed rows sequentially:
    python run_day_night_feed.py --limit 3

    # Run on a specific Airtable Record ID:
    python run_day_night_feed.py --record-id recXXXXXXXXXXXXXX

    # Dry run (test only, no API calls or Airtable writes):
    python run_day_night_feed.py --dry-run

    # Scrape only:
    python run_day_night_feed.py --scrape-only --limit 1
"""

from __future__ import annotations

import sys
from generate_day_night_feed_pipeline import main as pipeline_main


def main(argv=None) -> int:
    return pipeline_main(argv)


if __name__ == "__main__":
    sys.exit(main())
