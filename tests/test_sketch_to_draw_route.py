"""Unit test for Sketch to Draw Reel Studio Blueprint."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask


class SketchToDrawRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        routes_dir = Path(__file__).resolve().parents[1] / "UI Control"
        if str(routes_dir) not in sys.path:
            sys.path.insert(0, str(routes_dir))
        self.common = importlib.import_module("routes.common")
        self.marketing_patch = patch.object(self.common, "MARKETING_DIR", self.workspace)
        self.overrides_patch = patch.object(
            self.common, "OVERRIDES_FILE", self.workspace / "output" / "config_overrides.json"
        )
        self.marketing_patch.start()
        self.overrides_patch.start()
        (self.workspace / ".env").write_text("", encoding="utf-8")

        self.module = importlib.import_module("routes.sketch_to_draw_reel")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.sketch_to_draw_reel_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()

    def test_fixtures_lists_all_five_categories(self):
        response = self.client.get("/api/sketch-to-draw-reel/fixtures")
        self.assertEqual(response.status_code, 200)
        fixtures = response.get_json()["fixtures"]
        self.assertEqual(len(fixtures), 5)
        fixture_ids = [f["id"] for f in fixtures]
        self.assertIn("chandeliers", fixture_ids)
        self.assertIn("pendant", fixture_ids)
        self.assertIn("floor_lamp", fixture_ids)
        self.assertIn("table_lamp", fixture_ids)
        self.assertIn("ceiling_mounted", fixture_ids)

    def test_counts_reports_status_breakdown(self):
        with patch.object(
            self.module, "is_authorized", return_value=True
        ), patch(
            "content_automation.airtable_client.fetch_status_breakdown",
            return_value={"P": 1, "S": 0, "C": 5, "D": 0, "FM": 0},
        ):
            response = self.client.get("/api/sketch-to-draw-reel/counts?refresh=true")
        self.assertEqual(response.status_code, 200)
        counts = response.get_json()["counts"]
        self.assertEqual(counts["chandeliers"]["completed"], 5)

    def test_moodboard_update(self):
        saved = []
        with patch.object(self.module, "is_authorized", return_value=True), patch.object(
            self.module, "save_config_override", side_effect=lambda key, val: saved.append((key, val))
        ):
            response = self.client.post(
                "/api/sketch-to-draw-reel/moodboard",
                json={"fixture_id": "chandeliers", "moodboard_id": "mb-test-id-123"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved, [("KREA_MOODBOARD_ID_SKETCH_TO_REAL_CHANDELIERS", "mb-test-id-123")])

    def test_prompt_update(self):
        saved = []
        with patch.object(self.module, "is_authorized", return_value=True), patch.object(
            self.module, "save_config_override", side_effect=lambda key, val: saved.append((key, val))
        ):
            response = self.client.post(
                "/api/sketch-to-draw-reel/prompt",
                json={"fixture_id": "pendant", "prompt": "Luxury modern dining room with pendant light"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved, [("PROMPT_SKETCH_TO_REAL_REEL_PENDANT", "Luxury modern dining room with pendant light")])


if __name__ == "__main__":
    unittest.main()
