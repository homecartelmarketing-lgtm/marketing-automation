"""Unified House Tour Reel Automation Script.

Exclusively targets Airtable Table: tblqXkdDw4O7hxJS4 ("House Tour Reel").

Workflow:
1. Scrapes 11 fresh fixtures from Akeneo (one per room across the 11-room tour)
   with cross-table & Shopify deduplication and stamps pre-crafted Interior Prompt1..11.
2. Generates 11 organic-modern/Japandi room interiors with Krea AI.
3. Generates 11 blend prompts with Fal Claude Sonnet 5.
4. Blends fixtures into rooms with Fal Nano Banana Pro + YOLO Poppins tags.
5. Animates each blend into 3s motion clips with Fal Kling V3 Turbo Pro (alternating pans).
6. Synthesizes Fal ElevenLabs background music.
7. Local FFmpeg assembly with 1s dissolves, Poppins title cards, outro, and music.
   Uploads to Airtable 'Final Video' and marks Status = 'Done'.

Usage::

    # Run ONE row end-to-end:
    python run_house_tour_reel.py

    # Process multiple rows:
    python run_house_tour_reel.py --max-rows 3

    # Scrape only (no video generation):
    python run_house_tour_reel.py --phase scrape

    # Target specific record:
    python run_house_tour_reel.py --record-id recXXXXXXXX
"""

from __future__ import annotations

import sys
from generate_house_tour_reel_pipeline import main as pipeline_main

if __name__ == "__main__":
    sys.exit(pipeline_main())
