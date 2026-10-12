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


if __name__ == "__main__":
    unittest.main()
