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
        from run_tips_and_edu_feed import select_tagged_blends_for_layout
        atts = [make_att("tips_edu_feed_tagged_1_rec01ABC.jpg", 1),
                make_att("tips_edu_feed_tagged_2_rec01ABC.jpg", 2), make_att("temp_thumb_rec01ABC.jpg", 0)]
        self.assertEqual(len(select_tagged_blends_for_layout(atts)), 2)
    def test_name_normalization_strips_pipe_and_variant_suffix(self):
        from run_tips_and_edu_feed import normalize_tips_edu_tag
        self.assertEqual(normalize_tips_edu_tag("Keyes I | Modern LED Floor Lamp", "Modern LED Floor Lamp", "Chandelier"),
                         ("Keyes", "Modern LED Floor Lamp"))
        t2, s2 = normalize_tips_edu_tag("Zerrie Linear Brass Island Chandelier", "", "Chandelier")
        self.assertEqual(t2, "Zerrie")
        self.assertTrue(s2)
