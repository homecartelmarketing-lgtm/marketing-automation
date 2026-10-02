import unittest

import generate_moodboard_reel_pipeline as mb


class FakeFal:
    def __init__(self, raw):
        self.raw = raw

    def generate_vision_prompt(self, urls, instruction, model=None):
        return self.raw


class ItemNameSlotTests(unittest.TestCase):
    def test_canonical_scheme_slot0_is_bare_name(self):
        fields = {
            "Item Name": "Halvor | Floor Lamp",
            "Item Name2": "Yareli | Table Lamp",
            "Item Name3": "Nord | Pendant",
            "Item Name4": "Alto | Chandelier",
        }
        self.assertEqual(mb.get_item_name_for_slot(fields, 0), "Halvor | Floor Lamp")
        self.assertEqual(mb.get_item_name_for_slot(fields, 1), "Yareli | Table Lamp")
        self.assertEqual(mb.get_item_name_for_slot(fields, 2), "Nord | Pendant")
        self.assertEqual(mb.get_item_name_for_slot(fields, 3), "Alto | Chandelier")

    def test_one_based_scheme_is_not_shifted(self):
        fields = {
            "Item Name1": "A1",
            "Item Name2": "B2",
            "Item Name3": "C3",
            "Item Name4": "D4",
        }
        self.assertEqual([mb.get_item_name_for_slot(fields, s) for s in range(4)], ["A1", "B2", "C3", "D4"])

    def test_no_placeholder_when_name_missing(self):
        fields = {"Furniture Item": [{"filename": "Halvor Lamp.jpg", "url": "https://x/y"}]}
        self.assertEqual(mb.get_item_name_for_slot(fields, 0), "Halvor Lamp")
        self.assertEqual(mb.get_item_name_for_slot({}, 0), "")

    def test_slot_from_tagged_filename(self):
        self.assertEqual(mb._slot_from_filename("blended_tagged_mb3.jpg", "blended_tagged_mb", 0), 2)
        self.assertEqual(mb._slot_from_filename("blended_tagged_slot0.jpg", "blended_tagged_mb", 99), 0)
        self.assertEqual(mb._slot_from_filename("tagged_slot2.jpg", "blended_tagged_mb", 99), 2)


class MaterialWordTests(unittest.TestCase):
    def test_punctuation_and_case_duplicates_are_replaced(self):
        fal = FakeFal(
            '{"slots":[{"top":"BRASS","middle":"MARBLE","bottom":"VELVET"},'
            '{"top":"BRASS,","middle":"Brass","bottom":"OAK"}]}'
        )
        result = mb.generate_unique_material_words(fal, ["u1", "u2"], ["A", "B"])
        words = [w for slot in result.values() for w in slot.values()]
        self.assertEqual(len(words), len(set(words)))
        self.assertEqual(result[0]["top"], "BRASS")

    def test_partial_rerun_keys_by_actual_slot_and_avoids_existing(self):
        fal = FakeFal('{"slots":[{"top":"BRASS","middle":"MARBLE","bottom":"VELVET"}]}')
        result = mb.generate_unique_material_words(
            fal,
            ["u3"],
            ["C"],
            slot_indices=[2],
            existing_words=["BRASS", "OAK", "LINEN"],
        )
        self.assertIn(2, result)
        words = [w for w in result[2].values()]
        self.assertNotIn("BRASS", words)
        self.assertEqual(len(words), len(set(words)))

    def test_fallback_when_claude_fails_is_unique(self):
        fal = FakeFal("not json")
        result = mb.generate_unique_material_words(fal, ["u1", "u2", "u3", "u4"], ["A", "B", "C", "D"])
        words = [w for slot in result.values() for w in slot.values()]
        self.assertEqual(len(words), 12)
        self.assertEqual(len(words), len(set(words)))


if __name__ == "__main__":
    unittest.main()


class Phase3TaggingTests(unittest.TestCase):
    def test_phase3_tags_each_slot_with_its_own_item_name(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        fields = {
            "Item Name": "Halvor | Floor Lamp",
            "Item Name2": "Yareli | Table Lamp",
            "Item Name3": "Nord | Pendant Light",
            "Item Name4": "Alto | Chandelier",
        }
        for slot in range(4):
            fields[f"Prompt{slot + 1}"] = "blend prompt"
            fields[mb.furniture_field(slot) if slot == 0 else f"Furniture Item{slot + 1}"] = [{"url": "https://x/f"}]
            fields[mb.interior_field(slot) if slot == 0 else f"Interior{slot + 1}"] = [{"url": "https://x/i"}]
        # get_attachment_field expects canonical keys above; ensure slot0 keys exist
        fields["Furniture Item"] = [{"url": "https://x/f"}]
        fields["Interior"] = [{"url": "https://x/i"}]

        record = {"id": "recTEST", "fields": fields}
        tag_calls = []

        def fake_tag(**kwargs):
            tag_calls.append(kwargs)
            Path(kwargs["destination"]).parent.mkdir(parents=True, exist_ok=True)
            Path(kwargs["destination"]).write_bytes(b"x")
            return object(), None

        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            fake_img = workdir / "blend.jpg"
            fake_img.write_bytes(b"x")
            with mock.patch.object(mb, "blend_slot", return_value=mb.LocalImage(fake_img, "blend.jpg")), \
                mock.patch.object(mb, "_clear_attachment_field", return_value=None), \
                mock.patch.object(mb, "_ensure_field", return_value=None), \
                mock.patch.object(mb, "_upload_attachment", return_value=None), \
                mock.patch.object(mb, "tag_blended_image", side_effect=fake_tag):
                result = mb.run_phase_3_blend(
                    record, category_code="floor_lamps_reel", fal=object(), session=object(),
                    token="t", base_id="b", table_id="tbl", workdir=workdir, execute=True, skip_existing=True,
                )
        self.assertIsNotNone(result)
        self.assertEqual([c["item_name"] for c in tag_calls], ["Halvor", "Yareli", "Nord", "Alto"])
        self.assertTrue(all(c["category"] == "floor_lamps_reel" for c in tag_calls))
        self.assertEqual(sorted(result.tagged_map), [0, 1, 2, 3])
        self.assertEqual(result.tagged_map[0].filename, "blended_tagged_mb1.jpg")
