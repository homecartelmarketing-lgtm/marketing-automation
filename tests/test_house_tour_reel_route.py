"""House Tour Reel blueprint: single card, per-room pencils via rooms dicts."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

ROOM_KEYS = [
    "living-room", "bedroom", "dining-room", "kitchen", "lounge",
    "hallway", "office", "bathroom", "entryway", "sunroom", "kids-room",
]
ROOM_MB_KEYS = {
    key: f"KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM{i}"
    for i, key in enumerate(ROOM_KEYS, start=1)
}
ROOM_PROMPT_KEYS = {
    key: f"PROMPT_HOUSE_TOUR_REEL_ROOM{i}"
    for i, key in enumerate(ROOM_KEYS, start=1)
}


class HouseTourReelRouteTests(unittest.TestCase):
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
        os.environ.pop("AIRTABLE_TABLE_ID_HOUSE_TOUR_REEL", None)
        for key in (*ROOM_MB_KEYS.values(), *ROOM_PROMPT_KEYS.values()):
            os.environ.pop(key, None)

        sys.modules.pop("routes.house_tour_reel", None)
        self.module = importlib.import_module("routes.house_tour_reel")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.house_tour_reel_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()
        os.environ.pop("AIRTABLE_TABLE_ID_HOUSE_TOUR_REEL", None)
        for key in (*ROOM_MB_KEYS.values(), *ROOM_PROMPT_KEYS.values()):
            os.environ.pop(key, None)

    def test_fixtures_reports_single_card_with_eleven_rooms(self):
        response = self.client.get("/api/house-tour-reel/fixtures")
        self.assertEqual(response.status_code, 200)
        fixtures = response.get_json()["fixtures"]
        self.assertEqual(len(fixtures), 1)
        fix = fixtures[0]
        self.assertEqual(fix["id"], "house-tour")
        self.assertEqual(fix["table_id"], "tblqXkdDw4O7hxJS4")
        self.assertEqual([r["key"] for r in fix["rooms"]], ROOM_KEYS)
        # Each room carries its OWN board + prompt (no single shared value).
        self.assertEqual(len(fix["rooms"]), 11)
        for room in fix["rooms"]:
            self.assertTrue(room["moodboard_id"])
            self.assertTrue(room["prompt"])
        self.assertEqual(len({r["prompt"] for r in fix["rooms"]}), 11)

    def test_route_exposes_eight_phases(self):
        self.assertEqual(self.module.TOTAL_PHASES, 8)
        self.assertEqual(len(self.module.PHASE_LABELS), 8)
        self.assertIn("Interior Analysis", self.module.PHASE_LABELS[2])

    def test_counts_carries_rooms(self):
        with patch.object(
            self.module,
            "is_authorized",
            return_value=True,
        ), patch(
            "content_automation.airtable_client.fetch_status_breakdown",
            return_value={"P": 1, "S": 0, "C": 2, "D": 0, "FM": 0},
        ):
            response = self.client.get("/api/house-tour-reel/counts?refresh=true")
        self.assertEqual(response.status_code, 200)
        counts = response.get_json()["counts"]
        self.assertEqual(set(counts), {"house-tour"})
        self.assertEqual(counts["house-tour"]["completed"], 2)
        self.assertEqual(
            [r["key"] for r in counts["house-tour"]["rooms"]], ROOM_KEYS
        )

    def test_moodboard_rooms_dict_persists_per_room_keys(self):
        rooms = {key: f"board-for-{key}" for key in ROOM_KEYS}
        saved = []
        with patch.object(self.module, "is_authorized", return_value=True), patch.object(
            self.module, "save_config_override",
            side_effect=lambda key, value: saved.append((key, value)),
        ):
            response = self.client.post(
                "/api/house-tour-reel/moodboard",
                json={"fixture_id": "house-tour", "rooms": rooms},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            saved,
            [(ROOM_MB_KEYS[key], f"board-for-{key}") for key in ROOM_KEYS],
        )

    def test_prompt_rooms_dict_persists_per_room_keys(self):
        rooms = {key: f"Prompt for {key}" for key in ROOM_KEYS}
        saved = []
        with patch.object(self.module, "is_authorized", return_value=True), patch.object(
            self.module, "save_config_override",
            side_effect=lambda key, value: saved.append((key, value)),
        ):
            response = self.client.post(
                "/api/house-tour-reel/prompt",
                json={"fixture_id": "house-tour", "rooms": rooms},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            saved,
            [(ROOM_PROMPT_KEYS[key], f"Prompt for {key}") for key in ROOM_KEYS],
        )

    def test_incomplete_or_unknown_rooms_rejected(self):
        with patch.object(self.module, "is_authorized", return_value=True):
            missing_one = self.client.post(
                "/api/house-tour-reel/moodboard",
                json={"fixture_id": "house-tour",
                      "rooms": {k: "x" for k in ROOM_KEYS[:3]}},
            )
            unknown_room = self.client.post(
                "/api/house-tour-reel/prompt",
                json={"fixture_id": "house-tour",
                      "rooms": {**{k: "y" for k in ROOM_KEYS}, "attic": "z"}},
            )
            empty_value = self.client.post(
                "/api/house-tour-reel/moodboard",
                json={"fixture_id": "house-tour",
                      "rooms": {k: ("x" if k != "bedroom" else "  ") for k in ROOM_KEYS}},
            )
            legacy_single = self.client.post(
                "/api/house-tour-reel/moodboard",
                json={"fixture_id": "house-tour", "moodboard_id": "solo-board"},
            )
        self.assertEqual(missing_one.status_code, 400)
        self.assertEqual(unknown_room.status_code, 400)
        self.assertEqual(empty_value.status_code, 400)
        self.assertEqual(legacy_single.status_code, 400)


if __name__ == "__main__":
    unittest.main()
