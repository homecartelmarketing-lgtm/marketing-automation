"""Pure-function tests for the One at a time Lights Reel pipeline (no network, no Airtable)."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class OneAtATimeLightsPipelineTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("generate_one_at_a_time_lights_reel_pipeline")


class MultiFixtureInstructionTests(OneAtATimeLightsPipelineTests):
    def test_build_multi_fixture_blending_instruction(self):
        prompt = self.mod.build_multi_fixture_blending_instruction(
            table_lamp_name="Lumen Nightstand Lamp",
            ceiling_light_name="Halo Flush Mount",
            pendant_light_name="Aura Mini Pendant",
            interior_label="Modern Luxury Bedroom Interior",
            aspect_ratio="9:16",
        )
        self.assertIn("Lumen Nightstand Lamp", prompt)
        self.assertIn("Halo Flush Mount", prompt)
        self.assertIn("Aura Mini Pendant", prompt)
        self.assertIn("9:16", prompt)
        self.assertIn("bedside nightstand", prompt)
        self.assertIn("ceiling", prompt)
        self.assertIn("suspended", prompt)

    def test_clean_claude_prompt_strips_fences_and_quotes(self):
        raw = "```text\n\"A photorealistic modern bedroom with all three lights placed.\"\n```"
        cleaned = self.mod.clean_claude_prompt(raw)
        self.assertEqual(cleaned, "A photorealistic modern bedroom with all three lights placed.")

    def test_clean_claude_prompt_handles_plain_string(self):
        raw = "Seamless blend of all three lamps."
        self.assertEqual(self.mod.clean_claude_prompt(raw), raw)

    def test_clean_claude_prompt_empty(self):
        self.assertEqual(self.mod.clean_claude_prompt(""), "")


class SchemaAndConfigTests(OneAtATimeLightsPipelineTests):
    def test_slots_and_categories(self):
        self.assertEqual(self.mod.SLOTS, (1, 2, 3))
        self.assertEqual(self.mod.SLOT_CATEGORIES[1], "table_lamps")
        self.assertEqual(self.mod.SLOT_CATEGORIES[2], "ceiling_lights")
        self.assertEqual(self.mod.SLOT_CATEGORIES[3], "pendant_lights")

    def test_required_fields_include_converted_images(self):
        fields = self.mod.REQUIRED_FIELDS
        self.assertIn("Converted Image1", fields)
        self.assertIn("Converted Image2", fields)
        self.assertIn("Converted Image3", fields)
        self.assertIn("Blended Image", fields)
        self.assertIn("Scraped Item 1", fields)
        self.assertIn("Scraped Item 2", fields)
        self.assertIn("Scraped Item 3", fields)
        self.assertNotIn("Scraped Item 4", fields)

    def test_variation_config_prompts(self):
        cfg = self.mod.VARIATION_CONFIG
        self.assertEqual(len(cfg), 3)

        # Variation 1: only table lamp on
        self.assertIn("table lamp", cfg[1]["prompt"])
        self.assertIn("turn off the ceiling mounted light and pendant light", cfg[1]["prompt"])
        self.assertEqual(cfg[1]["field"], "Converted Image1")

        # Variation 2: only ceiling mounted on
        self.assertIn("ceiling mounted", cfg[2]["prompt"])
        self.assertIn("turn off the pendant light and table lamp", cfg[2]["prompt"])
        self.assertEqual(cfg[2]["field"], "Converted Image2")

        # Variation 3: only pendant light on
        self.assertIn("pendant light", cfg[3]["prompt"])
        self.assertIn("turn off the ceiling mounted light and table lamp", cfg[3]["prompt"])
        self.assertEqual(cfg[3]["field"], "Converted Image3")


class ItemNameExtractionTests(OneAtATimeLightsPipelineTests):
    def test_extract_slot_item_names(self):
        fields = {
            "Scraped Items": (
                "Slot 1 (Table Lamp) | Aurora Table Lamp | SKU TL-01 | table_lamps\n"
                "Slot 2 (Ceiling Mounted Light) | Sol Flush Ceiling Mount | SKU CL-02 | ceiling_lights\n"
                "Slot 3 (Pendant Light) | Luna Glass Pendant | SKU PE-03 | pendant_lights"
            )
        }
        names = self.mod._extract_slot_item_names(fields)
        self.assertEqual(names[1], "Aurora Table Lamp")
        self.assertEqual(names[2], "Sol Flush Ceiling Mount")
        self.assertEqual(names[3], "Luna Glass Pendant")


class InPlaceCrossfadeAssemblyTests(OneAtATimeLightsPipelineTests):
    def test_crossfade_assembly_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            images = []
            for i, color in enumerate(["#221100", "#112200", "#001122", "#332211"]):
                p = td / f"img_{i}.jpg"
                Image.new("RGB", (720, 1280), color=color).save(p)
                images.append(p)

            outro_path = td / "outro.jpg"
            Image.new("RGB", (720, 1280), color="#111111").save(outro_path)

            output_path = td / "final_reel.mp4"
            result = self.mod.assemble_in_place_crossfade_video(
                image_paths=images,
                output_path=output_path,
                hold_duration=0.5,
                crossfade_duration=0.2,
                outro_path=outro_path,
                outro_duration=0.5,
                width=720,
                height=1280,
                fps=24,
            )
            self.assertTrue(result.is_file())
            self.assertGreater(result.stat().st_size, 1000)


class YoloVariationTaggingTests(OneAtATimeLightsPipelineTests):
    def test_tag_variation_image_stamps_successfully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "oatl_lamp_on.jpg"
            Image.new("RGB", (720, 1280), color="#1a1a1a").save(img_path)

            tagged = self.mod._tag_variation_image(
                image_path=img_path,
                raw_item_name="Nordic Table Lamp",
                default_product_type="Table Lamp",
                category="table_lamps",
            )
            self.assertTrue(tagged.is_file())
            self.assertGreater(tagged.stat().st_size, 500)

    def test_tag_variation_image_parses_names_and_stamps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "test_tag.jpg"
            Image.new("RGB", (720, 1280), color="#000000").save(img_path)

            with patch.object(self.mod, "tag_blended_image") as mock_tag:
                # 1. Pipe-separated item name
                self.mod._tag_variation_image(
                    image_path=img_path,
                    raw_item_name="Lumen Nightstand Lamp | Bedside Lamp",
                    default_product_type="Table Lamp",
                    category="table_lamps",
                )
                mock_tag.assert_called_once_with(
                    image_input=img_path,
                    item_name="Lumen Nightstand Lamp",
                    product_type="Bedside Lamp",
                    category="table_lamps",
                    destination=img_path,
                    fallback_if_undetected=True,
                )

            with patch.object(self.mod, "tag_blended_image") as mock_tag:
                # 2. Plain item name without pipe (uses default_product_type fallback)
                self.mod._tag_variation_image(
                    image_path=img_path,
                    raw_item_name="Sol Flush Mount",
                    default_product_type="Ceiling Mounted Light",
                    category="ceiling_lights",
                )
                mock_tag.assert_called_once_with(
                    image_input=img_path,
                    item_name="Sol Flush Mount",
                    product_type="Ceiling Mounted Light",
                    category="ceiling_lights",
                    destination=img_path,
                    fallback_if_undetected=True,
                )

    def test_tags_applied_to_converted_images_1_2_3(self):
        """Verify that Converted Image 1 (Table Lamp), 2 (Ceiling Light), and 3 (Pendant Light) receive tags."""
        slots_data = [
            (1, "oatl_lamp_on.jpg", "Aura Nightstand Lamp", "Table Lamp", "table_lamps"),
            (2, "oatl_ceiling_on.jpg", "Halo Flush Ceiling Mount", "Ceiling Mounted Light", "ceiling_lights"),
            (3, "oatl_pendant_on.jpg", "Luna Glass Drop Pendant", "Pendant Light", "pendant_lights"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            tagged_paths = {}

            for slot, filename, name, ptype, cat in slots_data:
                img_path = td / filename
                # Create a uniform dark image
                Image.new("RGB", (720, 1280), color=(10, 10, 10)).save(img_path)

                tagged = self.mod._tag_variation_image(
                    image_path=img_path,
                    raw_item_name=f"{name} | {ptype}",
                    default_product_type=ptype,
                    category=cat,
                )
                self.assertTrue(tagged.is_file())
                self.assertEqual(tagged, img_path)
                tagged_paths[slot] = tagged

                # Verify image was modified and contains white text pixels (#ffffff)
                with Image.open(tagged) as img:
                    w, h = img.size
                    px = img.load()
                    white_pixels = sum(
                        1
                        for x in range(0, w, 4)
                        for y in range(0, h, 4)
                        if px[x, y][0] > 240 and px[x, y][1] > 240 and px[x, y][2] > 240
                    )
                    self.assertGreater(
                        white_pixels,
                        0,
                        f"Converted Image {slot} ({filename}) should contain stamped white text pixels.",
                    )

            self.assertEqual(len(tagged_paths), 3)

    def test_phase5_applies_tags_to_all_three_variations(self):
        """Simulate Phase 5 execution and verify YOLO tagging is applied to all 3 variations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)

            # Mock Clients
            mock_clients = MagicMock()
            mock_clients.fal.generate.return_value = "https://fal.media/files/test.jpg"

            # Create dummy downloaded files when _download_url is called
            def fake_download(url, dest, timeout=120):
                Image.new("RGB", (720, 1280), color="#111111").save(dest)
                return dest

            fields = {
                "Blended Image": [{"url": "https://fal.media/files/blended.jpg"}],
                "Scraped Items": (
                    "Slot 1 (Table Lamp) | Nordic Bedside Lamp | SKU TL-01 | table_lamps\n"
                    "Slot 2 (Ceiling Mounted Light) | Sol Flush Ceiling Mount | SKU CL-02 | ceiling_lights\n"
                    "Slot 3 (Pendant Light) | Luna Glass Pendant | SKU PE-03 | pendant_lights"
                ),
            }

            with patch.object(self.mod, "_download_url", side_effect=fake_download), \
                 patch.object(self.mod, "_tag_variation_image", wraps=self.mod._tag_variation_image) as spy_tag:
                results = self.mod.phase5_variations(
                    clients=mock_clients,
                    fields=fields,
                    workdir=workdir,
                    record_id="recTestRow123",
                )

                # Verify all 3 slots processed
                self.assertEqual(set(results.keys()), {1, 2, 3})
                self.assertEqual(spy_tag.call_count, 3)

                # Verify Airtable uploads for Converted Image 1, 2, 3
                uploaded_fields = [call.args[1] for call in mock_clients.airtable.upload_attachment.call_args_list]
                self.assertIn("Converted Image1", uploaded_fields)
                self.assertIn("Converted Image2", uploaded_fields)
                self.assertIn("Converted Image3", uploaded_fields)

    def test_blended_image_remains_clean_without_tags(self):
        """Verify that Phase 4 initial room blend is saved directly without _tag_variation_image being called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            mock_clients = MagicMock()
            mock_clients.fal.generate.return_value = "https://fal.media/files/blended.jpg"

            def fake_download(url, dest, timeout=120):
                Image.new("RGB", (720, 1280), color="#222222").save(dest)
                return dest

            fields = {
                "Living Room Interior": [{"url": "https://fal.media/files/interior.jpg"}],
                "Blending Prompt": "Seamless blend of all three lamps.",
                "Scraped Item 1": [{"url": "https://fal.media/files/lamp.jpg"}],
                "Scraped Item 2": [{"url": "https://fal.media/files/ceiling.jpg"}],
                "Scraped Item 3": [{"url": "https://fal.media/files/pendant.jpg"}],
            }

            with patch.object(self.mod, "_download_url", side_effect=fake_download), \
                 patch.object(self.mod, "_tag_variation_image") as mock_tag:
                dest = self.mod.phase4_blend(
                    clients=mock_clients,
                    fields=fields,
                    workdir=workdir,
                    record_id="recTestRow123",
                )
                self.assertTrue(dest.is_file())
                # Tagging must NEVER be called on the clean blended image
                mock_tag.assert_not_called()


if __name__ == "__main__":
    unittest.main()
