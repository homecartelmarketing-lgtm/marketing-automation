"""Unified Product Closeup Video Reel Automation Script.

Exclusively targets Airtable Table: tblqBZ946hVdOpmDV ("Product Closeup Table Lamps").

Workflow:
1. Scrapes Table Lamps from Akeneo (4 products per row) with cross-table & Shopify deduplication.
2. Generates 4 modern bedroom interiors with Krea AI.
3. Generates 4 blend prompts with Fal Claude Sonnet.
4. Blends 4 lamps into interiors with Fal Nano Banana Pro.
5. Appends HomeCartel outro ('assets/outro_layout.jpg').
6. Synthesizes Fal ElevenLabs background music and compiles 9:16 vertical reel with photo_video_maker.py.
7. Uploads to Airtable 'Final Video' and marks Status = 'Done'.

Usage::

    # Run ONE row end-to-end:
    python run_product_closeup_reel.py

    # Process multiple rows:
    python run_product_closeup_reel.py --max-rows 3

    # Scrape only (no video generation):
    python run_product_closeup_reel.py --phase scrape

    # Generate videos for existing pending rows (no scraping):
    python run_product_closeup_reel.py --phase generate

    # Target specific record:
    python run_product_closeup_reel.py --record-id recXXXXXXXX
"""

from __future__ import annotations

import sys
from generate_product_closeup_reel_pipeline import main as pipeline_main

if __name__ == "__main__":
    sys.exit(pipeline_main())
