"""Unit tests for Sketch to Real Reel item name & product type tagging."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image

from content_automation.akeneo_client import split_item_name
from content_automation.auto_draw import render_auto_draw_video
import generate_sketch_to_real_reel_pipeline as pipeline


class SketchToRealItemTagTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_split_item_name_extracts_title_and_product_type(self):
        title, ptype = split_item_name("Aegnor | Chandelier", fallback_product_type="Chandelier")
        self.assertEqual(title, "Aegnor")
        self.assertEqual(ptype, "Chandelier")

        title2, ptype2 = split_item_name("Aurelia | Pendant Light", fallback_product_type="Pendant Light")
        self.assertEqual(title2, "Aurelia")
        self.assertEqual(ptype2, "Pendant Light")

        title3, ptype3 = split_item_name("Minimalist Lamp", fallback_product_type="Floor Lamp")
        self.assertEqual(title3, "Minimalist Lamp")
        self.assertEqual(ptype3, "Floor Lamp")

    def test_auto_draw_video_with_tagged_after_image(self):
        # Create small test before, after, and tagged images (270x480)
        before_file = self.temp_path / "before.png"
        after_file = self.temp_path / "after.png"
        tagged_file = self.temp_path / "tagged.png"
        out_video = self.temp_path / "output.mp4"

        img_b = Image.new("RGB", (270, 480), (240, 240, 240))
        img_b.save(before_file)

        img_a = Image.new("RGB", (270, 480), (240, 240, 240))
        for x in range(100, 170):
            for y in range(100, 170):
                img_a.putpixel((x, y), (20, 20, 20))
        img_a.save(after_file)

        img_tag = Image.new("RGB", (270, 480), (240, 240, 240))
        for x in range(100, 170):
            for y in range(100, 170):
                img_tag.putpixel((x, y), (20, 20, 20))
        for x in range(30, 80):
            for y in range(200, 220):
                img_tag.putpixel((x, y), (255, 0, 0))
        img_tag.save(tagged_file)

        res = render_auto_draw_video(
            before_path=before_file,
            after_path=after_file,
            output_path=out_video,
            draw_seconds=0.5,
            transition_seconds=0.5,
            end_hold=0.5,
            target_width=270,
            fps=10,
            after_tagged_path=tagged_file,
        )

        self.assertTrue(res.is_file())
        self.assertGreater(res.stat().st_size, 500)

    def test_run_phase_4_blend_returns_three_tuple_with_tagged_path(self):
        clients = mock.MagicMock()
        clients.airtable.get_record.return_value = {
            "fields": {
                "Room Interior": [{"url": "https://example.com/interior.jpg"}],
                "Furniture Item": [{"url": "https://example.com/fixture.png"}],
                "Blending Prompt": "Install chandelier in room",
                "Item Name": "Aegnor",
                "Product Type": "Chandelier",
                "Category": "Chandeliers",
            }
        }
        clients.fal.generate.return_value = "https://example.com/blended.jpg"

        dummy_img = self.temp_path / "dummy.jpg"
        Image.new("RGB", (100, 100), (255, 255, 255)).save(dummy_img)

        with mock.patch("generate_sketch_to_real_reel_pipeline.download_url_to_temp_file") as mock_dl, \
             mock.patch("generate_sketch_to_real_reel_pipeline.tag_and_upload_blended_image") as mock_tag:
            
            mock_dl.return_value = mock.MagicMock(path=str(dummy_img))
            
            def fake_tag(**kwargs):
                if kwargs.get("output_tagged_paths") is not None:
                    kwargs["output_tagged_paths"].append(dummy_img)
                return True

            mock_tag.side_effect = fake_tag

            blended_url, temp_blended, tagged_local = pipeline.run_phase_4_blend(clients, "rec123")

            self.assertEqual(blended_url, "https://example.com/blended.jpg")
            self.assertEqual(temp_blended, dummy_img)
            self.assertEqual(tagged_local, dummy_img)
            
            # Verify tag_and_upload_blended_image received both title and product type
            mock_tag.assert_called_once()
            call_kwargs = mock_tag.call_args[1]
            self.assertEqual(call_kwargs["item_name"], "Aegnor")
            self.assertEqual(call_kwargs["product_type"], "Chandelier")


if __name__ == "__main__":
    unittest.main()
