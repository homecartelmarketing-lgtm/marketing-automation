"""Unit tests for generate_cta_story_pipeline.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from generate_cta_story_pipeline import (
    CTA_STORY_TABLES,
    clean_headline_text,
    extract_attachment_url,
    find_cta_table_by_category,
    generate_claude_blending_prompts,
    generate_claude_word_generated,
    generate_cta_blended_images,
    generate_krea_interiors,
    generate_watermark_added_images,
    get_cta_tables,
    make_layout_transparent,
    overlay_watermark_layout,
    parse_args,
    prompt_for_category,
    resolve_cta_table_and_config,
    run_pipeline,
    show_menu,
    show_table_menu,
)
from content_automation.fal_client import FalClient


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

    def test_cta_story_tables_registry(self):
        expected_tables = {
            "tblYHdVq14FjMWg5o": "chandelier_cta_story",
            "tblfl7fqFZa2vUieB": "pendant_lights_cta_story",
            "tblSpGJLO3faYfIDY": "cluster_chandelier_cta_story",
            "tblKJeCCp4zQ6g7Em": "table_lamps_cta_story",
            "tblPKSYyjgbgMypE2": "floor_lamp_cta_story",
        }
        for tid, cat in expected_tables.items():
            self.assertIn(tid, CTA_STORY_TABLES)
            self.assertEqual(CTA_STORY_TABLES[tid]["category_code"], cat)
            self.assertTrue(bool(CTA_STORY_TABLES[tid]["label"]))
            self.assertTrue(bool(CTA_STORY_TABLES[tid]["default_moodboard_id"]))
            self.assertTrue(bool(CTA_STORY_TABLES[tid]["default_prompt"]))

    def test_show_table_menu_selection(self):
        with mock.patch("builtins.input", side_effect=["2"]):
            res = show_table_menu()
            self.assertEqual("tblfl7fqFZa2vUieB", res)

    def test_show_table_menu_round_robin(self):
        with mock.patch("builtins.input", side_effect=["6"]):
            res = show_table_menu()
            self.assertEqual("round_robin", res)

    def test_show_table_menu_custom_table_id(self):
        with mock.patch("builtins.input", side_effect=["7", "tblCustom123"]):
            res = show_table_menu()
            self.assertEqual("tblCustom123", res)

    def test_show_table_menu_exit(self):
        with mock.patch("builtins.input", side_effect=["8"]):
            res = show_table_menu()
            self.assertEqual("exit", res)

        with mock.patch("builtins.input", side_effect=["q"]):
            res = show_table_menu()
            self.assertEqual("exit", res)

    def test_show_menu_phases(self):
        with mock.patch("builtins.input", side_effect=["1"]):
            self.assertEqual("scrape", show_menu("tblYHdVq14FjMWg5o"))

        with mock.patch("builtins.input", side_effect=["4"]):
            self.assertEqual("blend", show_menu("tblYHdVq14FjMWg5o"))

        with mock.patch("builtins.input", side_effect=["6"]):
            self.assertEqual("conversion", show_menu("tblYHdVq14FjMWg5o"))

        with mock.patch("builtins.input", side_effect=["7"]):
            self.assertEqual("all", show_menu("tblYHdVq14FjMWg5o"))

        with mock.patch("builtins.input", side_effect=["8"]):
            self.assertEqual("round_robin", show_menu("tblYHdVq14FjMWg5o"))

        with mock.patch("builtins.input", side_effect=["9"]):
            self.assertEqual("switch_table", show_menu("tblYHdVq14FjMWg5o"))

        with mock.patch("builtins.input", side_effect=["10"]):
            self.assertEqual("exit", show_menu("tblYHdVq14FjMWg5o"))

        with mock.patch("builtins.input", side_effect=["exit"]):
            self.assertEqual("exit", show_menu("tblYHdVq14FjMWg5o"))

    def test_round_robin_menu_options(self):
        from run_cta_round_robin import show_round_robin_menu

        # Option 1: 1 round across all tables
        with mock.patch("builtins.input", side_effect=["1"]):
            cats, rounds, inf, delay, open_pipe = show_round_robin_menu()
            self.assertEqual(5, len(cats))
            self.assertEqual(1, rounds)
            self.assertFalse(inf)
            self.assertFalse(open_pipe)

        # Option 3: continuous infinite loop
        with mock.patch("builtins.input", side_effect=["3", "10"]):
            cats, rounds, inf, delay, open_pipe = show_round_robin_menu()
            self.assertTrue(inf)
            self.assertEqual(10, delay)

        # Option 5: launch pipeline menu
        with mock.patch("builtins.input", side_effect=["5"]):
            cats, rounds, inf, delay, open_pipe = show_round_robin_menu()
            self.assertTrue(open_pipe)

    def test_clean_headline_text(self):
        self.assertEqual("Warm Modern Sanctuary", clean_headline_text('"Warm Modern Sanctuary"'))
        self.assertEqual("Warm Modern Sanctuary", clean_headline_text('**Warm Modern Sanctuary**'))
        self.assertEqual("Warm Modern Sanctuary", clean_headline_text('Headline: Warm Modern Sanctuary.'))
        self.assertEqual("Warm Modern Sanctuary", clean_headline_text('# Hook: "Warm Modern Sanctuary"'))
        self.assertEqual("Warm Modern Sanctuary", clean_headline_text("Warm Modern Sanctuary\nHere is an explanation..."))
        self.assertEqual("", clean_headline_text(None))

    def test_generate_claude_word_generated_retries_on_duplicate_response(self):
        mock_fal = mock.MagicMock()
        mock_fal.analyze_image.side_effect = ["Warm Minimalist Living", "Sunken Lounge Serenity"]

        mock_airtable = mock.MagicMock()
        mock_airtable.list_records.return_value = [
            {
                "id": "rec1",
                "fields": {
                    "Status": "Complete",
                    "Item Name": "Prior Chandelier",
                    "CTA Blended Image": [{"url": "https://example.com/prior.jpg"}],
                    "Word Generated": "Warm Minimalist Living",
                },
            },
            {
                "id": "rec2",
                "fields": {
                    "Status": "CTA Blended Image Generated",
                    "Item Name": "Current Chandelier",
                    "CTA Blended Image": [{"url": "https://example.com/current.jpg"}],
                    "Word Generated": "",
                },
            },
        ]

        success = generate_claude_word_generated(mock_fal, mock_airtable)
        self.assertTrue(success)
        self.assertEqual(2, mock_fal.analyze_image.call_count)
        mock_airtable.update_records.assert_called_once_with([("rec2", {"Word Generated": "Sunken Lounge Serenity"})])

    def test_fal_client_analyze_image_delegates_to_generate_vision_prompt(self):
        fal = FalClient(api_key="test_key")
        with mock.patch.object(fal, "generate_vision_prompt", return_value="Unique Luxury Glow") as mock_gen:
            res = fal.analyze_image(prompt="Analyze this room", image_urls=["https://example.com/image.jpg"])
            self.assertEqual("Unique Luxury Glow", res)
            mock_gen.assert_called_once_with(["https://example.com/image.jpg"], "Analyze this room", model="anthropic/claude-sonnet-5", endpoint="openrouter/router/vision", on_task_created=None)

    def test_generate_claude_word_generated_refreshes_stale_modern_luxury_living(self):
        mock_fal = mock.MagicMock()
        mock_fal.analyze_image.return_value = "Sculptural Brass Illumination"

        mock_airtable = mock.MagicMock()
        mock_airtable.list_records.return_value = [
            {
                "id": "rec1",
                "fields": {
                    "Status": "CTA Blended Image Generated",
                    "Item Name": "Chandelier B",
                    "CTA Blended Image": [{"url": "https://example.com/blended.jpg"}],
                    "Word Generated": "Modern Luxury Living",
                },
            }
        ]

        success = generate_claude_word_generated(mock_fal, mock_airtable)
        self.assertTrue(success)
        mock_fal.analyze_image.assert_called_once()
        mock_airtable.update_records.assert_called_once_with([("rec1", {"Word Generated": "Sculptural Brass Illumination"})])

    def test_generate_claude_word_generated_deduplication_avoid_clause(self):
        mock_fal = mock.MagicMock()
        mock_fal.analyze_image.return_value = "Golden Hour Sanctuary"

        mock_airtable = mock.MagicMock()
        mock_airtable.list_records.return_value = [
            {
                "id": "rec1",
                "fields": {
                    "Status": "Complete",
                    "Item Name": "Chandelier Prior",
                    "CTA Blended Image": [{"url": "https://example.com/prior.jpg"}],
                    "Word Generated": "Warm Minimalist Living",
                },
            },
            {
                "id": "rec2",
                "fields": {
                    "Status": "CTA Blended Image Generated",
                    "Item Name": "Chandelier Current",
                    "CTA Blended Image": [{"url": "https://example.com/current.jpg"}],
                    "Word Generated": "",
                },
            },
        ]

        success = generate_claude_word_generated(mock_fal, mock_airtable)
        self.assertTrue(success)
        call_kwargs = mock_fal.analyze_image.call_args.kwargs
        self.assertIn("Warm Minimalist Living", call_kwargs["prompt"])
        self.assertIn("Do NOT reuse or repeat", call_kwargs["prompt"])
        mock_airtable.update_records.assert_called_once_with([("rec2", {"Word Generated": "Golden Hour Sanctuary"})])

    def test_dynamic_cta_tables_resolution_all_categories(self):
        expected = {
            "chandelier_cta_story": "tblYHdVq14FjMWg5o",
            "pendant_lights_cta_story": "tblfl7fqFZa2vUieB",
            "cluster_chandelier_cta_story": "tblSpGJLO3faYfIDY",
            "table_lamps_cta_story": "tblKJeCCp4zQ6g7Em",
            "floor_lamp_cta_story": "tblPKSYyjgbgMypE2",
        }
        for cat, expected_tid in expected.items():
            found = find_cta_table_by_category(cat)
            self.assertIsNotNone(found, f"Category {cat} must resolve to a table")
            tid, cfg = found
            self.assertEqual(expected_tid, tid)
            self.assertEqual(cat, cfg["category_code"])
            self.assertTrue(bool(cfg["default_moodboard_id"]))
            self.assertTrue(bool(cfg["default_prompt"]))

            # Test resolve_cta_table_and_config without target_table_id
            resolved_tid, resolved_cat, resolved_cfg = resolve_cta_table_and_config(None, cat)
            self.assertEqual(expected_tid, resolved_tid)
            self.assertEqual(cat, resolved_cat)
            self.assertEqual(cfg["default_moodboard_id"], resolved_cfg["default_moodboard_id"])
            self.assertEqual(cfg["default_prompt"], resolved_cfg["default_prompt"])

    def test_dynamic_cta_tables_env_override(self):
        import os
        custom_mb = "custom-test-moodboard-12345"
        custom_prompt = "Custom test dining prompt"
        with mock.patch.dict(os.environ, {
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS_CTA": custom_mb,
            "CTA_PROMPT_PENDANT_LIGHTS": custom_prompt,
        }):
            tables = get_cta_tables()
            pendant_cfg = tables.get("tblfl7fqFZa2vUieB")
            self.assertIsNotNone(pendant_cfg)
            self.assertEqual(custom_mb, pendant_cfg["default_moodboard_id"])
            self.assertEqual(custom_prompt, pendant_cfg["default_prompt"])


if __name__ == "__main__":
    unittest.main()
