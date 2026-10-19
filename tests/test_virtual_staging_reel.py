"""Unit tests for Virtual Staging Reel pipeline, route, and layout."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

routes_dir = REPO_ROOT / "UI Control"
if str(routes_dir) not in sys.path:
    sys.path.insert(0, str(routes_dir))

from content_automation.foreign_key import generate_foreign_key, resolve_table_prefix
from generate_virtual_staging_reel_pipeline import (
    KLING_MODEL,
    REQUIRED_STANDARD_FIELDS,
    STATUS_CHOICES,
    render_branding_pill_overlay,
)
from routes.virtual_staging_reel import PHASE_LABELS, TOTAL_PHASES


class VirtualStagingReelUnitTests(unittest.TestCase):
    def test_foreign_key_prefix(self):
        prefix = resolve_table_prefix("tblPYG5Ed4XURecu6", "Virtual Staging Reel")
        self.assertEqual(prefix, "VST-REEL-SET")

        fk = generate_foreign_key("tblPYG5Ed4XURecu6", 42, "Virtual Staging Reel")
        self.assertEqual(fk, "VST-REEL-SET-42")

        # Also fallback alias
        self.assertEqual(resolve_table_prefix("tblVirtualStagingReel", "Virtual Staging Reel"), "VST-REEL-SET")

    def test_schema_constants_and_phases(self):
        self.assertEqual(TOTAL_PHASES, 7)
        self.assertEqual(len(PHASE_LABELS), 7)
        self.assertIn("Phase 1", PHASE_LABELS[1])
        self.assertIn("Phase 6", PHASE_LABELS[6])
        self.assertIn("Phase 7", PHASE_LABELS[7])

        self.assertIn("Foreign Key ID", REQUIRED_STANDARD_FIELDS)
        self.assertIn("Fully Staged Room", REQUIRED_STANDARD_FIELDS)
        self.assertIn("Empty Room Interior", REQUIRED_STANDARD_FIELDS)
        self.assertIn("Raw Video", REQUIRED_STANDARD_FIELDS)
        self.assertIn("Final Video", REQUIRED_STANDARD_FIELDS)
        self.assertIn("Standby", STATUS_CHOICES)
        self.assertIn("Done", STATUS_CHOICES)

    def test_branding_pill_overlay_rendering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_png = Path(tmpdir) / "pill.png"
            render_branding_pill_overlay("Mina Chandelier", out_png)
            self.assertTrue(out_png.is_file())
            with Image.open(out_png) as img:
                self.assertEqual(img.size, (1080, 1920))
                self.assertEqual(img.mode, "RGBA")

    def test_fal_client_kling_payload(self):
        import fal_client as official_fal_sdk
        from content_automation.fal_client import FalClient

        fal = FalClient(api_key="fake-test-key")
        with patch.object(
            official_fal_sdk,
            "subscribe",
            return_value={"video": {"url": "https://cdn.fal.media/output.mp4"}},
        ) as mock_subscribe:
            url = fal.generate_kling_video(
                prompt="test prompt",
                start_image_url="https://example.com/start.jpg",
                end_image_url="https://example.com/end.jpg",
                negative_prompt="anti warp",
                shot_type="customize",
                aspect_ratio="9:16",
                duration=10,
                model="fal-ai/kling-video/v3/pro/image-to-video",
            )
            self.assertEqual(url, "https://cdn.fal.media/output.mp4")

            # Check arguments sent to fal_client.subscribe
            mock_subscribe.assert_called_once()
            call_args, call_kwargs = mock_subscribe.call_args
            self.assertEqual(call_args[0], "fal-ai/kling-video/v3/pro/image-to-video")
            payload = call_kwargs["arguments"]
            self.assertEqual(payload["prompt"], "test prompt")
            self.assertEqual(payload["start_image_url"], "https://example.com/start.jpg")
            self.assertEqual(payload["end_image_url"], "https://example.com/end.jpg")
            self.assertEqual(payload["negative_prompt"], "anti warp")
            self.assertEqual(payload["shot_type"], "customize")
            self.assertEqual(payload["aspect_ratio"], "9:16")
            self.assertEqual(payload["duration"], "10")


class VirtualStagingReelRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.common = importlib.import_module("routes.common")
        self.marketing_patch = patch.object(self.common, "MARKETING_DIR", self.workspace)
        self.overrides_patch = patch.object(
            self.common, "OVERRIDES_FILE", self.workspace / "output" / "config_overrides.json"
        )
        self.marketing_patch.start()
        self.overrides_patch.start()

        sys.modules.pop("routes.virtual_staging_reel", None)
        self.module = importlib.import_module("routes.virtual_staging_reel")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.virtual_staging_reel_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()

    def test_fixtures_endpoint(self):
        response = self.client.get("/api/virtual-staging-reel/fixtures")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        fixtures = data["fixtures"]
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["id"], "virtual-staging")
        self.assertEqual(fixtures[0]["name"], "Virtual Staging")

    def test_counts_endpoint(self):
        with patch.object(self.module, "is_authorized", return_value=True), patch(
            "content_automation.airtable_client.fetch_status_breakdown",
            return_value={"P": 2, "C": 5, "D": 0, "FM": 0},
        ):
            response = self.client.get("/api/virtual-staging-reel/counts?refresh=true")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["status"], "success")
            counts = data["counts"]["virtual-staging"]
            self.assertEqual(counts["completed"], 5)

    def test_status_endpoint(self):
        response = self.client.get("/api/virtual-staging-reel/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "idle")
        self.assertEqual(data["total_phases"], 7)


if __name__ == "__main__":
    unittest.main()
