from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

# Ensure UI Control is in path for route imports
UI_CONTROL_DIR = Path(__file__).resolve().parents[1] / "UI Control"
if str(UI_CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(UI_CONTROL_DIR))

import generate_moodboard_1_feed as mb1
from routes.moodboard_1_feed import (
    build_generation_command,
    get_fixtures,
    resolve_moodboard_id,
    resolve_prompt,
)


class Moodboard1RouteTests(unittest.TestCase):
    def test_fixtures_configured_correctly(self):
        fixtures = get_fixtures()
        self.assertIn("chandelier", fixtures)
        self.assertIn("pendant", fixtures)
        self.assertIn("floor-lamp", fixtures)
        self.assertEqual(fixtures["chandelier"]["category"], "chandeliers")
        self.assertEqual(fixtures["pendant"]["category"], "pendant_lights")
        self.assertEqual(fixtures["floor-lamp"]["category"], "floor_lamps")

    def test_build_generation_command_clamps_items(self):
        cmd = build_generation_command("tblTest", "chandeliers", 25, "mb-id", "Test Prompt")
        self.assertIn("--table-id", cmd)
        self.assertIn("tblTest", cmd)
        self.assertIn("--category", cmd)
        self.assertIn("chandeliers", cmd)
        self.assertIn("--max-items", cmd)
        # Should be clamped to 10 max
        max_idx = cmd.index("--max-items") + 1
        self.assertEqual(cmd[max_idx], "10")
        self.assertIn("--moodboard-id", cmd)
        self.assertIn("mb-id", cmd)
        self.assertIn("--prompt", cmd)
        self.assertIn("Test Prompt", cmd)


class Moodboard1GeneratorTests(unittest.TestCase):
    def test_constants_defined(self):
        self.assertEqual(mb1.STATUS_FOR_REVIEW, "For Review")
        self.assertEqual(mb1.STATUS_BLENDED_IMAGE, "Blended Image Generated")
        self.assertEqual(mb1.STATUS_COMPLETE, "Complete")
        self.assertEqual(mb1.BLENDED_FIELD, "Moodboard V1 Blended")
        self.assertEqual(mb1.WATERMARK_ADDED_FIELD, "Moodboard Added Watermark")

    @mock.patch("generate_moodboard_1_feed.write_scale_fields")
    @mock.patch("generate_moodboard_1_feed.tag_and_upload_blended_image")
    @mock.patch("generate_moodboard_1_feed.run_self_healing_feed_qa")
    @mock.patch("generate_moodboard_1_feed.download_to_temp_file")
    @mock.patch("generate_moodboard_1_feed.requests.get")
    @mock.patch("generate_moodboard_1_feed.blend_with_scale_guard")
    def test_phase_3_halts_when_qa_fails(
        self, mock_scale, mock_get, mock_dl, mock_qa, mock_tag, mock_scale_write
    ):
        mock_scale.return_value = mock.MagicMock(image_url="https://images.example/blend.jpg")
        mock_dl.return_value = mock.MagicMock(path=Path("dummy.jpg"), cleanup=mock.MagicMock())
        mock_qa.return_value = mock.MagicMock(passed=False)

        mock_airtable = mock.MagicMock()
        mock_airtable.table_id = "tblTest"
        mock_airtable.list_records.return_value = [
            {
                "id": "recTEST",
                "fields": {
                    "Item Name": "Nordora Chandelier",
                    "Prompt for Blending": "Place chandelier in center",
                    "Interior Generated": [{"url": "https://images.example/interior.jpg"}],
                    "Furniture Item": [{"url": "https://images.example/product.jpg"}],
                },
            }
        ]
        mock_airtable.get_record.return_value = {
            "id": "recTEST",
            "fields": {
                "Moodboard V1 Blended": [{"url": "https://images.example/blended.jpg"}],
            },
        }

        mock_fal = mock.MagicMock()

        success = mb1.generate_moodboard_v1_blends(
            mock_fal,
            mock_airtable,
            limit_records=1,
        )
        # Should return False because the record failed QA
        self.assertFalse(success)
        self.assertTrue(mock_qa.called)

    @mock.patch("generate_moodboard_1_feed.write_scale_fields")
    @mock.patch("generate_moodboard_1_feed.tag_and_upload_blended_image")
    @mock.patch("generate_moodboard_1_feed.run_self_healing_feed_qa")
    @mock.patch("generate_moodboard_1_feed.download_to_temp_file")
    @mock.patch("generate_moodboard_1_feed.requests.get")
    @mock.patch("generate_moodboard_1_feed.blend_with_scale_guard")
    def test_phase_3_succeeds_when_qa_passes(
        self, mock_scale, mock_get, mock_dl, mock_qa, mock_tag, mock_scale_write
    ):
        mock_scale.return_value = mock.MagicMock(image_url="https://images.example/blend.jpg")
        mock_dl.return_value = mock.MagicMock(path=Path("dummy.jpg"), cleanup=mock.MagicMock())
        mock_qa.return_value = mock.MagicMock(passed=True)

        mock_airtable = mock.MagicMock()
        mock_airtable.table_id = "tblTest"
        mock_airtable.list_records.return_value = [
            {
                "id": "recTEST",
                "fields": {
                    "Item Name": "Nordora Chandelier",
                    "Prompt for Blending": "Place chandelier in center",
                    "Interior Generated": [{"url": "https://images.example/interior.jpg"}],
                    "Furniture Item": [{"url": "https://images.example/product.jpg"}],
                },
            }
        ]
        mock_airtable.get_record.return_value = {
            "id": "recTEST",
            "fields": {
                "Moodboard V1 Blended": [{"url": "https://images.example/blended.jpg"}],
            },
        }

        mock_fal = mock.MagicMock()

        success = mb1.generate_moodboard_v1_blends(
            mock_fal,
            mock_airtable,
            limit_records=1,
        )
        self.assertTrue(success)
        self.assertTrue(mock_qa.called)


if __name__ == "__main__":
    unittest.main()
