"""Guaranteed 2-line tags: Line 2 is never empty and never invented.

Covers the Day & Night Story, Moodboard #1 Feed, and Collection Category
Feed migrations to ``resolve_tag_names`` + fixture-type final fallback, the
deterministic lower-right fallback per format, and the YOLO retry ladder.

Pure assertions, no network calls (detection is mocked).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


def make_anchor(item_name="", product_type="", fields=None, sku="SKU-1"):
    return SimpleNamespace(
        item_name=item_name,
        product_type=product_type,
        fields=dict(fields or {}),
        sku=sku,
        record_id="recTEST",
    )


class ResolveTagNamesGuaranteeTests(unittest.TestCase):
    def test_bare_name_empty_everywhere_uses_hint(self):
        from content_automation.item_tagger import resolve_tag_names

        anchor = make_anchor(item_name="Trude Une")
        self.assertEqual(
            resolve_tag_names("Trude Une", anchor, type_hint="Floor Lamp"),
            ("Trude Une", "Floor Lamp"),
        )

    def test_real_field_beats_hint(self):
        from content_automation.item_tagger import resolve_tag_names

        anchor = make_anchor(item_name="Trude Une", fields={"Product Type": "Modern Floor Lamp"})
        self.assertEqual(
            resolve_tag_names("Trude Une", anchor, type_hint="Pendant Light"),
            ("Trude Une", "Modern Floor Lamp"),
        )

    def test_anchor_product_type_beats_hint(self):
        from content_automation.item_tagger import resolve_tag_names

        anchor = make_anchor(item_name="Trude Une", product_type="Modern Floor Lamp")
        self.assertEqual(
            resolve_tag_names("Trude Une", anchor, type_hint="Pendant Light"),
            ("Trude Une", "Modern Floor Lamp"),
        )

    def test_pipe_name_still_splits(self):
        from content_automation.item_tagger import resolve_tag_names

        anchor = make_anchor()
        self.assertEqual(
            resolve_tag_names("Halvor | Modern Floor Lamp", anchor, type_hint="Pendant Light"),
            ("Halvor", "Modern Floor Lamp"),
        )

    def test_banned_words_never_appear(self):
        from content_automation.item_tagger import resolve_tag_names

        anchor = make_anchor(item_name="Trude Une")
        title, prod = resolve_tag_names("Trude Une", anchor, type_hint="Floor Lamp")
        self.assertTrue(title and prod)
        for banned in ("Lighting", "recTEST", "N/A", ""):
            if banned:
                self.assertNotEqual(prod, banned)


class FixtureDisplayTypeTests(unittest.TestCase):
    def test_known_codes(self):
        from content_automation.item_tagger import fixture_display_type

        self.assertEqual(fixture_display_type("floor_lamps_moodboard_story"), "Floor Lamp")
        self.assertEqual(fixture_display_type("tblOvvYdgsNTXh2zK"), "")
        self.assertEqual(fixture_display_type("pendant_lights"), "Pendant Light")
        self.assertEqual(fixture_display_type("chandelier_day_night_story"), "Chandelier")
        self.assertEqual(fixture_display_type("cluster_chandelier_cta_story"), "Cluster Chandelier")

    def test_unknown_is_empty_never_invented(self):
        from content_automation.item_tagger import fixture_display_type

        self.assertEqual(fixture_display_type(""), "")
        self.assertEqual(fixture_display_type("some_random_code"), "")


class LowerRightFallbackTests(unittest.TestCase):
    def test_feed_quadrant(self):
        from content_automation.item_tagger import lower_right_fallback_position

        x, y = lower_right_fallback_position((1080, 1350), "Trude Une", "Floor Lamp", "feed")
        self.assertGreater(x, 1080 / 2)
        self.assertGreater(y, 1350 / 2)

    def test_story_quadrant_clears_reply_bar(self):
        from content_automation.item_tagger import lower_right_fallback_position, measure_tag_pill

        x, y = lower_right_fallback_position((1080, 1920), "Trude Une", "Floor Lamp", "story")
        pill_w, pill_h = measure_tag_pill("Trude Une", "Floor Lamp")
        self.assertGreater(x, 1080 / 2)
        self.assertLessEqual(x + pill_w, 1080 - 60 + 1)
        self.assertLessEqual(y + pill_h, 1920 - 320 + 1)

    def test_reel_clears_action_rail(self):
        from content_automation.item_tagger import lower_right_fallback_position, measure_tag_pill

        x, y = lower_right_fallback_position((1080, 1920), "Trude Une", "Floor Lamp", "reel")
        pill_w, pill_h = measure_tag_pill("Trude Une", "Floor Lamp")
        self.assertLessEqual(x + pill_w, 1080 - 180 + 1)
        self.assertLessEqual(y + pill_h, 1920 - 320 + 1)

    def test_long_name_stays_inside_canvas(self):
        from content_automation.item_tagger import lower_right_fallback_position, measure_tag_pill

        name = "A Very Long Chandelier Name That Keeps Going"
        for fmt, (w, h) in (("feed", (1080, 1350)), ("story", (1080, 1920)), ("reel", (1080, 1920))):
            with self.subTest(fmt=fmt):
                x, y = lower_right_fallback_position((w, h), name, "Chandelier", fmt)
                pill_w, pill_h = measure_tag_pill(name, "Chandelier")
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + pill_w, w + 1)
                self.assertLessEqual(y + pill_h, h + 1)

    def test_normalize_variants(self):
        from content_automation.item_tagger import normalize_output_format

        self.assertEqual(normalize_output_format("feed"), "feed")
        self.assertEqual(normalize_output_format("FEED"), "feed")
        self.assertEqual(normalize_output_format("reel"), "reel")
        self.assertEqual(normalize_output_format("story"), "story")
        self.assertEqual(normalize_output_format(""), "story")
        self.assertEqual(normalize_output_format(None), "story")


class RetryLadderTests(unittest.TestCase):
    def test_ladder_retries_then_hits(self):
        from content_automation import item_tagger

        hit = (10, 10, 100, 100)
        with patch.object(item_tagger, "detect_item_bbox", side_effect=[None, hit]) as m:
            with patch.object(item_tagger, "brightest_region_center", return_value=(55, 55)):
                from PIL import Image

                img = Image.new("RGB", (200, 200), (10, 10, 10))
                self.assertEqual(
                    item_tagger.detect_with_retry_ladder(img, category="chandeliers"),
                    hit,
                )
                self.assertEqual(m.call_count, 2)

    def test_ladder_returns_none_when_model_missing(self):
        from content_automation import item_tagger
        from PIL import Image

        img = Image.new("RGB", (200, 200), (10, 10, 10))
        with patch.object(item_tagger, "detect_item_bbox", side_effect=ImportError("no ultralytics")):
            self.assertIsNone(item_tagger.detect_with_retry_ladder(img, category="chandeliers"))

    def test_saliency_rejects_far_bbox(self):
        from content_automation import item_tagger
        from PIL import Image

        far = (900, 1700, 950, 1750)
        img = Image.new("RGB", (1080, 1920), (10, 10, 10))
        with patch.object(item_tagger, "detect_item_bbox", return_value=far):
            with patch.object(item_tagger, "brightest_region_center", return_value=(100, 100)):
                self.assertIsNone(
                    item_tagger.detect_with_retry_ladder(
                        img, category="chandeliers", generic_queries=[]
                    )
                )


if __name__ == "__main__":
    unittest.main()
