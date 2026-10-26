"""Guard the caption scope: feeds and reels only (2026-10-26 decision).

Stories, Ad Cover and both banners must not call the shared caption helper.
Sale Banner keeps its calendar captions baked into the image, which are a
different feature from the Instagram caption.
"""

from __future__ import annotations

from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]

NO_CAPTION_PIPELINES = (
    "generate_cta_story_pipeline.py",
    "generate_collection_category_story_pipeline.py",
    "generate_product_description_story_pipeline.py",
    "generate_product_specs_story_pipeline.py",
    "generate_style_this_story_pipeline.py",
    "generate_this_or_that_pipeline.py",
    "generate_ad_cover_pipeline.py",
    "generate_christmas_banner_pipeline.py",
    "generate_sale_banner_pipeline.py",
)

CAPTION_MARKERS = (
    "generate_caption",
    "CAPTION_GENERATED_FIELD",
    "from content_automation.caption",
    "from content_automation import caption",
)


class CaptionScopeTest(unittest.TestCase):
    def test_stories_ads_and_banners_do_not_generate_captions(self):
        for name in NO_CAPTION_PIPELINES:
            with self.subTest(pipeline=name):
                source = (REPO_ROOT / name).read_text(encoding="utf-8")
                for marker in CAPTION_MARKERS:
                    self.assertNotIn(marker, source)

    def test_virtual_staging_reel_still_generates_the_caption(self):
        source = (REPO_ROOT / "generate_virtual_staging_reel_pipeline.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("generate_caption", source)

    def test_sale_banner_keeps_its_calendar_captions(self):
        source = (REPO_ROOT / "generate_sale_banner_pipeline.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Sale Caption Left", source)
        self.assertIn("Sale Caption Right", source)


if __name__ == "__main__":
    unittest.main()
