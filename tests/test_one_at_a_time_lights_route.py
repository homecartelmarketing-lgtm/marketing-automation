"""One at a time Lights Reel blueprint must expose fixtures, counts, and persistent moodboard edits."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask


class OneAtATimeLightsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        routes_dir = Path(__file__).resolve().parents[1] / "UI Control"
        sys.path.insert(0, str(routes_dir))
        self.common = importlib.import_module("routes.common")
        self.marketing_patch = patch.object(self.common, "MARKETING_DIR", self.workspace)
        self.overrides_patch = patch.object(
            self.common, "OVERRIDES_FILE", self.workspace / "output" / "config_overrides.json"
        )
        self.marketing_patch.start()
        self.overrides_patch.start()
        (self.workspace / ".env").write_text("", encoding="utf-8")
        os.environ.pop("AIRTABLE_TABLE_ID_ONE_AT_A_TIME_LIGHTS", None)
        os.environ.pop("KREA_MOODBOARD_ID_ONE_AT_A_TIME_LIGHTS", None)

        self.module = importlib.import_module("routes.one_at_a_time_lights_reel")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.one_at_a_time_lights_reel_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()
        os.environ.pop("AIRTABLE_TABLE_ID_ONE_AT_A_TIME_LIGHTS", None)
        os.environ.pop("KREA_MOODBOARD_ID_ONE_AT_A_TIME_LIGHTS", None)

    def test_fixtures_reports_living_room(self):
        response = self.client.get("/api/one-at-a-time-lights-reel/fixtures")
        self.assertEqual(response.status_code, 200)
        fixtures = response.get_json()["fixtures"]
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["id"], "living-room")
        self.assertEqual(fixtures[0]["table_id"], "tblJpEtBudQZda319")

    def test_counts_reports_completed_field(self):
        with patch.object(
            self.module,
            "is_authorized",
            return_value=True,
        ), patch(
            "content_automation.airtable_client.fetch_status_breakdown",
            return_value={"P": 1, "S": 0, "C": 2, "D": 0, "FM": 0},
        ):
            response = self.client.get("/api/one-at-a-time-lights-reel/counts?refresh=true")
        self.assertEqual(response.status_code, 200)
        counts = response.get_json()["counts"]
        self.assertEqual(counts["living-room"]["completed"], 2)

    def test_moodboard_edit_persists_env_key(self):
        saved = []
        with patch.object(self.module, "is_authorized", return_value=True), patch.object(
            self.module, "save_config_override", side_effect=lambda key, value: saved.append((key, value))
        ):
            response = self.client.post(
                "/api/one-at-a-time-lights-reel/moodboard",
                json={"fixture_id": "living-room", "moodboard_id": "abc-123-moodboard"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            saved,
            [("KREA_MOODBOARD_ID_ONE_AT_A_TIME_LIGHTS", "abc-123-moodboard")],
        )


if __name__ == "__main__":
    unittest.main()
