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

#: Feed/Reel module -> flow key it passes to ``write_row_caption``.
CAPTION_PIPELINES = {
    "run_tips_and_edu_feed.py": "tips_edu_feed",
    "run_collection_category_feed.py": "collection_feed",
    "generate_moodboard_1_feed.py": "moodboard_1_feed",
    "generate_moodboard_2_feed.py": "moodboard_2_feed",
    "run_1_product_3_styles_feed.py": "op3s_feed",
    "generate_day_night_feed_pipeline.py": "day_night_feed",
    "generate_product_showcase_feed_pipeline.py": "product_showcase_feed",
    "content_automation/phased_content.py": "day_night_reel",
    "generate_product_closeup_reel_pipeline.py": "product_closeup_reel",
    "generate_before_after_reel_pipeline.py": "before_after_reel",
    "generate_moodboard_reel_pipeline.py": "moodboard_reel",
    "run_style_reel_slideshow.py": "style_reel_slideshow",
    "run_one_product_three_styles_reel.py": "op3s_reel",
    "generate_one_at_a_time_lights_reel_pipeline.py": "oatl_reel",
    "generate_sketch_to_real_reel_pipeline.py": "sketch_to_real_reel",
    "generate_house_tour_reel_pipeline.py": "house_tour_reel",
    "generate_room_build_up_reel_pipeline.py": "room_build_up_reel",
    "generate_this_mood_every_night_reel_pipeline.py": "tmen_reel",
    "generate_virtual_staging_reel_pipeline.py": "virtual_staging_reel",
    "generate_room_reveal_reel_pipeline.py": "room_reveal_reel",
}

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

    def test_every_feed_and_reel_writes_the_caption(self):
        for name, key in CAPTION_PIPELINES.items():
            with self.subTest(pipeline=name):
                source = (REPO_ROOT / name).read_text(encoding="utf-8")
                self.assertIn("write_row_caption", source)
                self.assertIn(f'"{key}"', source)

    def test_every_flow_key_is_defined(self):
        import sys

        sys.path.insert(0, str(REPO_ROOT))
        from content_automation.caption_flows import CAPTION_FLOWS

        for key in CAPTION_PIPELINES.values():
            with self.subTest(key=key):
                self.assertTrue(CAPTION_FLOWS.get(key, "").strip())
        self.assertEqual(set(CAPTION_FLOWS), set(CAPTION_PIPELINES.values()))

    def test_sale_banner_keeps_its_calendar_captions(self):
        source = (REPO_ROOT / "generate_sale_banner_pipeline.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Sale Caption Left", source)
        self.assertIn("Sale Caption Right", source)


if __name__ == "__main__":
    unittest.main()
