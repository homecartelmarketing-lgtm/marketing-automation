"""End-to-End CLI Runner for Style This Story Pipeline.

Workflow:
  1. Auto-Scrape (if needed): Scrapes new unique floor lamp product from Akeneo -> tblvSAzXasTVI85r9 (Status: 'Standby')
  2. [Phase 1/4] Krea AI 9:16 Interior Generation for 4 slots -> 'Interior', 'Interior2', 'Interior3', 'Interior4'
  3. [Phase 2/4] Fal AI Claude Sonnet 5 Prompt Generation -> 'Prompt', 'Prompt2', 'Prompt3', 'Prompt4'
  4. [Phase 3/4] Fal AI Nano Banana Pro 9:16 Blending -> 'Style This Blended' (4 photos)
  5. [Phase 4/4] Fal AI Nano Banana Pro Story Cards Layout Conversion -> 'Double Tap Converted' & 'STORY - Style This? (4)' & Status: 'Complete'

Usage::

    # Run 1 row end-to-end:
    python run_style_this_story.py

    # Run specific number of rows:
    python run_style_this_story.py --limit 3

    # Run on a specific Record ID:
    python run_style_this_story.py --record-id recXXXXXXXXXXXXXX

    # Dry run test:
    python run_style_this_story.py --dry-run
"""

from __future__ import annotations

import sys
from generate_style_this_story_pipeline import main as pipeline_main


def main(argv=None) -> int:
    return pipeline_main(argv)


if __name__ == "__main__":
    sys.exit(main())
