"""Unit tests for This Mood Every Night Reel pipeline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.config import Settings
import generate_this_mood_every_night_reel_pipeline as pipeline


class ThisMoodEveryNightPipelineTests(unittest.TestCase):
    def setUp(self):
        self.mock_airtable = MagicMock()
        self.mock_settings = Settings(
            workspace=pipeline.REPO_ROOT,
            airtable_token="fake_airtable_token",
            airtable_base_id="appFakeBaseId",
            krea_token="fake_krea_token",
            krea_base_url="https://api.krea.ai",
            kie_api_key="",
            kie_api_base="",
            kie_upload_base="",
            qwen_api_key="",
            qwen_base_url="",
            qwen_model="",
            zoho_client_id="",
            zoho_client_secret="",
            zoho_refresh_token="",
            zoho_output_folder_id="",
            fal_key="fake_fal_key",
            callback_url="",
            output_dir=pipeline.REPO_ROOT / "output",
            akeneo_host="https://akeneo.example.com",
            akeneo_client_id="fake_client_id",
            akeneo_secret="fake_secret",
            akeneo_username="fake_user",
            akeneo_password="fake_pass",
        )

    def test_clients_initialization_no_missing_positional_arguments(self):
        clients = pipeline.Clients(self.mock_airtable, self.mock_settings)

        # akeneo() should successfully create an AkeneoClient without TypeError
        akeneo = clients.akeneo()
        self.assertIsNotNone(akeneo)
        self.assertEqual(akeneo.host, "https://akeneo.example.com")
        self.assertEqual(akeneo.client_id, "fake_client_id")
        self.assertEqual(akeneo.username, "fake_user")

        # krea() should create a KreaClient without missing token error
        krea = clients.krea()
        self.assertIsNotNone(krea)
        self.assertEqual(krea.token, "fake_krea_token")

        # fal() should create a FalClient with api_key
        fal = clients.fal()
        self.assertIsNotNone(fal)
        self.assertEqual(fal.api_key, "fake_fal_key")

        # shopify() should create a ShopifyClient
        shopify = clients.shopify()
        self.assertIsNotNone(shopify)

    def test_upload_attachment_url_on_airtable_client(self):
        clients = pipeline.Clients(self.mock_airtable, self.mock_settings)
        clients.airtable.upload_attachment_url("rec123", "Interior1", "https://example.com/interior.jpg", "interior.jpg")

        self.mock_airtable.upload_attachment_url.assert_called_once_with(
            "rec123", "Interior1", "https://example.com/interior.jpg", "interior.jpg"
        )

    def test_phase3_analyze_calls_analyze_image(self):
        clients = pipeline.Clients(self.mock_airtable, self.mock_settings)
        mock_fal = MagicMock()
        mock_fal.analyze_image.return_value = "Mount chandelier in center of living room."
        clients._fal = mock_fal

        fields = {
            pipeline.INTERIOR_FIELDS[1]: [{"url": "https://example.com/interior_1.jpg"}],
        }
        res = pipeline.phase3_analyze(clients, "rec123", fields)
        self.assertTrue(res)
        mock_fal.analyze_image.assert_called_once()
        self.assertIn("Mount chandelier", fields[pipeline.INTERIOR_ANALYSIS_FIELDS[1]])

    def test_phase5_blend_calls_fal_generate(self):
        clients = pipeline.Clients(self.mock_airtable, self.mock_settings)
        mock_fal = MagicMock()
        mock_fal.generate.return_value = "https://example.com/blended_1.jpg"
        clients._fal = mock_fal

        fields = {
            pipeline.INTERIOR_FIELDS[1]: [{"url": "https://example.com/interior_1.jpg"}],
            pipeline.FURNITURE_FIELDS[1]: [{"url": "https://example.com/fixture_1.jpg"}],
            pipeline.GENERATED_PROMPT_FIELDS[1]: "Seamlessly inpaint lighting fixture",
        }
        res = pipeline.phase5_blend(clients, "rec123", fields)
        self.assertTrue(res)
        mock_fal.generate.assert_called_once_with(
            prompt="Seamlessly inpaint lighting fixture",
            image_urls=["https://example.com/interior_1.jpg", "https://example.com/fixture_1.jpg"],
            aspect_ratio="9:16",
            resolution="1K",
            model="fal-ai/nano-banana-pro/edit",
            output_format="jpeg",
        )

    def test_phase6_motion_calls_generate_kling_video(self):
        clients = pipeline.Clients(self.mock_airtable, self.mock_settings)
        mock_fal = MagicMock()
        mock_fal.generate_kling_video.return_value = "https://example.com/kling_1.mp4"
        clients._fal = mock_fal

        fields = {
            pipeline.BLENDED_FIELDS[1]: [{"url": "https://example.com/blended_1.jpg"}],
        }
        res = pipeline.phase6_motion(clients, "rec123", fields, use_kling=True)
        self.assertTrue(res)
        mock_fal.generate_kling_video.assert_called_once()

    def test_resolve_outro_file_finds_asset(self):
        outro = pipeline.resolve_outro_file()
        self.assertIsNotNone(outro)
        self.assertTrue(outro.is_file())

    def test_tag_reel_position_bounds(self):
        x, y_title, y_sub = pipeline.tag_reel_position("Mina 7", "Chandelier")
        self.assertGreater(x, 0)
        self.assertLess(x, 1080)
        self.assertGreater(y_title, 0)
        self.assertLess(y_title, 1920)
        self.assertGreater(y_sub, y_title)

    def test_ffmpeg_escape_drawtext(self):
        raw = "Mina's, Luxury: 100% Cotton \\ Test"
        escaped = pipeline._ffmpeg_escape_drawtext(raw)
        self.assertIn("\\'", escaped)
        self.assertIn("\\,", escaped)
        self.assertIn("\\:", escaped)
        self.assertIn("\\%", escaped)

    @patch("subprocess.run")
    def test_phase8_assemble_creates_outro_and_drawtext(self, mock_subproc):
        mock_subproc.return_value = MagicMock(returncode=0)
        clients = pipeline.Clients(self.mock_airtable, self.mock_settings)

        fields = {
            "Item Name1": "Mina 7",
            "Item Name2": "Landon",
            "Item Name3": "Riley",
            "Item Name4": "Landulf",
            "Item Name5": "Alondra",
            "Item Name6": "Hugi",
            "Item Name7": "Gulla",
        }
        for slot in pipeline.SLOTS:
            fields[pipeline.KLING_FIELDS[slot]] = [{"url": f"https://example.com/kling_{slot}.mp4"}]
        fields["Music Generated"] = [{"url": "https://example.com/music.mp3"}]

        self.mock_airtable.record.return_value = {"id": "rec123", "fields": fields}

        with patch("generate_this_mood_every_night_reel_pipeline._download_file"):
            res = pipeline.phase8_assemble(clients, "rec123", fields)

        self.assertTrue(res)
        # Verify airtable uploads for Outro and Final Video
        upload_calls = self.mock_airtable.upload_attachment.call_args_list
        fields_uploaded = [c[0][1] for c in upload_calls]
        self.assertIn("Outro", fields_uploaded)
        self.assertIn("Final Video", fields_uploaded)

        # Inspect subprocess calls to verify drawtext commands
        drawtext_commands = [
            c[0][0] for c in mock_subproc.call_args_list
            if any("-vf" in arg or any("drawtext=" in a for a in arg) for arg in c[0])
        ]
        self.assertTrue(len(drawtext_commands) > 0)
        vf_args = [cmd[cmd.index("-vf") + 1] for cmd in drawtext_commands if "-vf" in cmd]
        combined_vf = " ".join(vf_args)
        self.assertIn("this mood every night", combined_vf)
        self.assertIn("between(t,0,9.45)", combined_vf)
        self.assertIn("Mina 7 Chandelier", combined_vf)
        self.assertIn("alpha=", combined_vf)

    def test_format_item_display_name(self):
        cases = [
            ("Mina 7", "Chandelier", "Mina 7 Chandelier"),
            ("Landon", "Pendant Light", "Landon Pendant Light"),
            ("Aria Pendant Light", "Pendant Light", "Aria Pendant Light"),
            ("Riley", "Table Lamp", "Riley Table Lamp"),
            ("Hugi", "Modern Floor Lamp", "Hugi Floor Lamp"),
        ]
        for title, ptype, expected in cases:
            with self.subTest(title=title, ptype=ptype):
                res = pipeline.format_item_display_name(title, ptype)
                self.assertEqual(res, expected)


if __name__ == "__main__":
    unittest.main()


