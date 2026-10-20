"""Tips & Edu Feed attach-to-photo + item-name formatting regressions."""
import unittest
import run_tips_and_edu_feed as feed

def make_att(filename, idx):
    return {"url": f"https://example.invalid/{filename}", "filename": filename, "id": f"att{idx}"}

class AttachFormatTests(unittest.TestCase):
    def test_space_variant_item_name_fields_resolve(self):
        from run_tips_and_edu_feed import get_slot_item_name_val, SLOTS
        fields = {"Item Name 2": "Zygadlo | Luxury Modern Chandelier"}
        self.assertEqual(get_slot_item_name_val(fields, SLOTS[1]), "Zygadlo | Luxury Modern Chandelier")
    def test_empty_name_never_returns_record_id(self):
        from run_tips_and_edu_feed import get_slot_item_name_val, SLOTS
        self.assertEqual(get_slot_item_name_val({"SKU2": "HC-1", "Item Name2": ""}, SLOTS[1]), "")
    def test_thumbnail_filtered_from_tagged_carousel(self):
        from run_tips_and_edu_feed import select_tagged_blends_for_layout
        atts = [make_att("temp_thumb_recT.jpg", 0), make_att("tips_edu_feed_tagged_2_recT.jpg", 2),
                make_att("tips_edu_feed_tagged_1_recT.jpg", 1), make_att("tips_edu_feed_tagged_3_recT.jpg", 3)]
        got = select_tagged_blends_for_layout(atts)
        self.assertEqual([a["filename"] for a in got],
            ["tips_edu_feed_tagged_1_recT.jpg", "tips_edu_feed_tagged_2_recT.jpg", "tips_edu_feed_tagged_3_recT.jpg"])
    def test_record_id_substring_does_not_fake_a_slot(self):
        from run_tips_and_edu_feed import select_tagged_blends_for_layout, _slot_of
        atts = [make_att("tips_edu_feed_tagged_1_rec01ABC.jpg", 1),
                make_att("tips_edu_feed_tagged_2_rec01ABC.jpg", 2), make_att("temp_thumb_rec01ABC.jpg", 0)]
        # The rec01ABC digits must not fake slots: only real tagged_1/_2 resolve.
        self.assertEqual([_slot_of(a) for a in atts], [1, 2, None])
        # Fewer than 3 tagged photos -> [] so Phase 6 routes to For Manual.
        self.assertEqual(select_tagged_blends_for_layout(atts), [])
    def test_name_normalization_strips_pipe_and_variant_suffix(self):
        from run_tips_and_edu_feed import normalize_tips_edu_tag
        self.assertEqual(normalize_tips_edu_tag("Keyes I | Modern LED Floor Lamp", "Modern LED Floor Lamp", "Chandelier"),
                         ("Keyes", "Modern LED Floor Lamp"))
        t2, s2 = normalize_tips_edu_tag("Zerrie Linear Brass Island Chandelier", "", "Chandelier")
        self.assertEqual(t2, "Zerrie")
        self.assertTrue(s2)

    def test_phase5_clears_tagged_field_and_uses_thumbnail_with_text(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        runner = feed.TipsAndEduFeedRunner.__new__(feed.TipsAndEduFeedRunner)
        runner.category_code = "chandeliers"
        runner.fixture_label = "Chandelier"
        runner.force_layouts = False
        runner.airtable = mock.Mock()
        runner.airtable.get_record.return_value = {"fields": {
            feed.BLENDED_FIELD: [
                {"url": "https://example.invalid/b1.jpg", "filename": "tips_and_edu_blended_1_recT.jpg"},
                {"url": "https://example.invalid/b2.jpg", "filename": "tips_and_edu_blended_2_recT.jpg"},
                {"url": "https://example.invalid/b3.jpg", "filename": "tips_and_edu_blended_3_recT.jpg"}],
            "Item Name": "Zygadlo | Luxury Modern Chandelier",
            "Item Name2": "Keyes | Modern Floor Lamp",
            "Item Name3": "Dorvalira D | Contemporary Floor Lamp",
            "Product Type": "Chandelier", "Product Type2": "Floor Lamp", "Product Type3": "Floor Lamp",
            feed.THUMBNAIL_WITH_TEXT_FIELD: [{"url": "https://example.invalid/thumb.jpg", "filename": "thumb_text.jpg"}]}}
        tmp = Path(tempfile.mkdtemp())
        runner._artifact_path = lambda rec, name: tmp / name
        runner._download = mock.Mock()
        cleared = {}
        runner.airtable.clear_attachment_field = lambda rec, field: cleared.setdefault(field, True)
        runner._update_status = mock.Mock()
        with mock.patch("content_automation.item_tagger.tag_blended_image", return_value=(mock.Mock(save=mock.Mock()), {"x": 1})), \
             mock.patch.object(feed, "append_error_log"):
            runner.phase_5("recT", execute=True)
        self.assertTrue(cleared.get(feed.TAGGED_BLENDED_FIELD), "must clear tagged carousel before re-upload")
        first_thumb_call = [c for c in runner._download.call_args_list]
        self.assertTrue(first_thumb_call, "thumbnail must be downloaded for prepend")
