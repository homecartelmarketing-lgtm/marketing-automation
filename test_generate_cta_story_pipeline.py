"""Unit tests for generate_cta_story_pipeline.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from generate_cta_story_pipeline import (
    extract_attachment_url,
    generate_claude_blending_prompts,
    generate_claude_word_generated,
    generate_cta_blended_images,
    generate_krea_interiors,
    generate_qwen_blending_prompts,
    generate_watermark_added_images,
    make_layout_transparent,
    overlay_watermark_layout,
    parse_args,
    prompt_for_category,
    run_pipeline,
)


class TestCtaStoryPipeline(unittest.TestCase):
    def test_parse_args_defaults(self):
        args = parse_args([])
        self.assertEqual("all", args.mode)
        self.assertEqual("chandelier_cta_story", args.category)

    def test_extract_attachment_url(self):
        self.assertEqual("", extract_attachment_url(None))
        self.assertEqual("", extract_attachment_url([]))
        self.assertEqual("https://example.com/img.jpg", extract_attachment_url([{"url": "https://example.com/img.jpg"}]))
        self.assertEqual("https://example.com/img.jpg", extract_attachment_url({"url": "https://example.com/img.jpg"}))

    def test_make_layout_transparent_black_background(self):
        img = Image.new("RGB", (50, 50), color=(0, 0, 0))
        for x in range(10, 20):
            for y in range(10, 20):
                img.putpixel((x, y), (255, 255, 255))

        transparent = make_layout_transparent(img, threshold=30)
        self.assertEqual(transparent.mode, "RGBA")
        self.assertEqual(transparent.getpixel((0, 0))[3], 0)
        self.assertEqual(transparent.getpixel((15, 15)), (255, 255, 255, 255))

    def test_make_layout_transparent_white_background(self):
        img = Image.new("RGB", (50, 50), color=(255, 255, 255))
        for x in range(10, 20):
            for y in range(10, 20):
                img.putpixel((x, y), (0, 0, 0))

        transparent = make_layout_transparent(img, threshold=30)
        self.assertEqual(transparent.mode, "RGBA")
        self.assertEqual(transparent.getpixel((0, 0))[3], 0)
        self.assertEqual(transparent.getpixel((15, 15)), (0, 0, 0, 255))

    def test_make_layout_transparent_preserves_existing_alpha(self):
        img = Image.new("RGBA", (20, 20), color=(100, 150, 200, 128))
        transparent = make_layout_transparent(img)
        self.assertEqual(transparent.getpixel((0, 0)), (100, 150, 200, 128))

    def test_overlay_watermark_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            base_file = tmp_path / "base.jpg"
            layout_file = tmp_path / "layout.png"
            out_file = tmp_path / "output.jpg"

            Image.new("RGB", (100, 200), color=(200, 100, 100)).save(base_file, "JPEG")
            Image.new("RGB", (100, 200), color=(0, 0, 0)).save(layout_file, "PNG")

            res_path = overlay_watermark_layout(base_file, layout_file, out_file)
            self.assertTrue(res_path.exists())

            with Image.open(res_path) as result_img:
                self.assertEqual(result_img.size, (100, 200))

    def test_generate_krea_interiors(self):
        mock_krea = mock.MagicMock()
        mock_krea.generate.return_value = "https://example.com/interior.jpg"
        mock_dl = mock.MagicMock()
        mock_krea.download_image.return_value = mock_dl

        mock_airtable = mock.MagicMock()
        mock_airtable.list_records.return_value = [
            {
                "id": "rec1",
                "fields": {"Status": "Standby", "Item Name": "Chandelier A"},
            }
        ]

        success = generate_krea_interiors(mock_krea, mock_airtable)
        self.assertTrue(success)
        mock_krea.generate.assert_called_once()
        mock_airtable.upload_attachment.assert_called_once()
        mock_airtable.update_records.assert_called_once_with([("rec1", {"Status": "CTA Interior Generated"})])

    def test_generate_claude_blending_prompts(self):
        mock_fal = mock.MagicMock()
        mock_fal.analyze_image.return_value = "Hang chandelier gracefully in living room."

        mock_airtable = mock.MagicMock()
        mock_airtable.list_records.return_value = [
            {
                "id": "rec1",
                "fields": {
                    "Status": "CTA Interior Generated",
                    "Item Name": "Chandelier A",
                    "CTA Interior": [{"url": "https://example.com/interior.jpg"}],
                    "Furniture Item": [{"url": "https://example.com/product.jpg"}],
                },
            }
        ]

        success = generate_claude_blending_prompts(mock_fal, mock_airtable)
        self.assertTrue(success)
        mock_fal.analyze_image.assert_called_once()
        mock_airtable.update_records.assert_has_calls([
            mock.call([("rec1", {"Blending Prompt": "Hang chandelier gracefully in living room."})]),
            mock.call([("rec1", {"Status": "Blending Prompt Generated"})]),
        ])

    def test_generate_cta_blended_images(self):
        mock_fal = mock.MagicMock()
        mock_fal.generate.return_value = "https://example.com/blended.jpg"

        mock_airtable = mock.MagicMock()
        mock_airtable.list_records.return_value = [
            {
                "id": "rec1",
                "fields": {
                    "Status": "Blending Prompt Generated",
                    "Item Name": "Chandelier A",
                    "CTA Interior": [{"url": "https://example.com/interior.jpg"}],
                    "Furniture Item": [{"url": "https://example.com/product.jpg"}],
                    "Blending Prompt": "Install chandelier in ceiling",
                },
            }
        ]

        with mock.patch("requests.get") as mock_get, mock.patch("generate_cta_story_pipeline.download_to_temp_file") as mock_dl:
            mock_resp = mock.MagicMock()
            mock_get.return_value = mock_resp
            mock_temp = mock.MagicMock()
            mock_dl.return_value = mock_temp

            success = generate_cta_blended_images(mock_fal, mock_airtable)
            self.assertTrue(success)
            mock_fal.generate.assert_called_once()
            mock_airtable.upload_attachment.assert_called_once()

    def test_generate_claude_word_generated_does_not_depend_on_item_name(self):
        mock_fal = mock.MagicMock()
        mock_fal.analyze_image.return_value = "Warm Minimalist Living"

        mock_airtable = mock.MagicMock()
        mock_airtable.list_records.return_value = [
            {
                "id": "rec1",
                "fields": {
                    "Status": "CTA Blended Image Generated",
                    "Item Name": "Nordora Chandelier",
                    "CTA Blended Image": [{"url": "https://example.com/blended.jpg"}],
                },
            }
        ]

        success = generate_claude_word_generated(mock_fal, mock_airtable)
        self.assertTrue(success)
        mock_fal.analyze_image.assert_called_once()
        call_kwargs = mock_fal.analyze_image.call_args.kwargs
        # Verify the instruction does not inject or require the item name
        self.assertNotIn("Nordora Chandelier", call_kwargs["prompt"])
        mock_airtable.update_records.assert_called_once_with([("rec1", {"Word Generated": "Warm Minimalist Living"})])

    def test_prompt_for_category(self):
        chandelier_prompt = prompt_for_category("chandelier_cta_story")
        self.assertEqual("Generate me a modern living room", chandelier_prompt)

        table_lamp_prompt = prompt_for_category("table_lamps_cta_story")
        self.assertEqual("Generate me a modern bedroom with a table lamp side by side", table_lamp_prompt)

        custom = prompt_for_category("chandelier_cta_story", "My custom prompt")
        self.assertEqual("My custom prompt", custom)

    def test_parse_args_with_prompt(self):
        args = parse_args(["--category", "chandelier_cta_story", "--prompt", "Generate me a modern living room"])
        self.assertEqual("chandelier_cta_story", args.category)
        self.assertEqual("Generate me a modern living room", args.prompt)


if __name__ == "__main__":
    unittest.main()
