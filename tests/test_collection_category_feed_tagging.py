import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

import run_collection_category_feed as feed


def _slot(index: int):
    return next(s for s in feed.SLOTS if s.slot_index == index)


class ParseSuggestedCategoryTests(unittest.TestCase):
    def test_parses_category_token(self):
        text = "[CATEGORY: table_lamps] Table Lamp: A pair of sculptural table lamps"
        self.assertEqual(feed.parse_suggested_category(text), "table_lamps")

    def test_normalises_spaces_and_case(self):
        self.assertEqual(feed.parse_suggested_category("[category: Pendant Lights] x"), "pendant_lights")

    def test_missing_token_uses_fallback(self):
        self.assertEqual(feed.parse_suggested_category("Table Lamp: nice", fallback="Table Lamp"), "Table Lamp")
        self.assertEqual(feed.parse_suggested_category(None), "")


class StampItemNameTagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.image = self.tmp / "slot.jpg"
        Image.new("RGB", (928, 1152), (120, 110, 100)).save(self.image)
        self.fields = {"Suggest Furniture Item2": "[CATEGORY: table_lamps] Table Lamp: A pair of lamps"}

    def test_slot_config_has_no_stale_attribute(self):
        # Regression: Phase 5 used `slot.suggest_furniture_field`, which does not exist.
        self.assertFalse(hasattr(_slot(2), "suggest_furniture_field"))

    def test_calls_tagger_with_parsed_category_and_product_type(self):
        with mock.patch("content_automation.item_tagger.tag_blended_image", return_value=(object(), (1, 2, 3, 4))) as tagger:
            ok = feed.stamp_item_name_tag(self.image, "Yareli", _slot(2), self.fields)
        self.assertTrue(ok)
        kwargs = tagger.call_args.kwargs
        self.assertEqual(kwargs["category"], "table_lamps")
        self.assertEqual(kwargs["item_name"], "Yareli")
        self.assertEqual(kwargs["product_type"], "Table Lamp")  # not the room label
        self.assertEqual(kwargs["destination"], self.image)

    def test_pipe_item_name_keeps_its_own_product_type(self):
        with mock.patch("content_automation.item_tagger.tag_blended_image", return_value=(object(), None)) as tagger:
            feed.stamp_item_name_tag(self.image, "Halvor | Modern Floor Lamp", _slot(2), self.fields)
        self.assertEqual(tagger.call_args.kwargs["item_name"], "Halvor")
        self.assertEqual(tagger.call_args.kwargs["product_type"], "Modern Floor Lamp")

    def test_returns_false_when_tagger_raises_or_draws_nothing(self):
        with mock.patch("content_automation.item_tagger.tag_blended_image", side_effect=RuntimeError("boom")):
            self.assertFalse(feed.stamp_item_name_tag(self.image, "Yareli", _slot(2), self.fields))
        with mock.patch("content_automation.item_tagger.tag_blended_image", return_value=(None, None)):
            self.assertFalse(feed.stamp_item_name_tag(self.image, "Yareli", _slot(2), self.fields))

    def test_real_tagger_changes_the_image(self):
        before = self.image.read_bytes()
        with mock.patch("content_automation.item_tagger.detect_item_bbox", return_value=None):
            ok = feed.stamp_item_name_tag(self.image, "Yareli", _slot(2), self.fields)
        self.assertTrue(ok)
        self.assertNotEqual(before, self.image.read_bytes())


if __name__ == "__main__":
    unittest.main()
