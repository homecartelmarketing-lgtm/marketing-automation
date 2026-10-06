"""Rows inspector must expose plain-text extras (e.g. Interior JSON) without attachments."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask


class RowsExtrasTests(unittest.TestCase):
    def setUp(self):
        routes_dir = Path(__file__).resolve().parents[1] / "UI Control"
        sys.path.insert(0, str(routes_dir))
        self.module = importlib.import_module("routes.rows")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.rows_bp)
        self.client = self.app.test_client()

    def _get(self, record):
        payload = {"records": [record]}
        fake = SimpleNamespace(ok=True, json=lambda: payload)
        with patch.object(self.module.requests, "get", return_value=fake):
            return self.client.get("/api/rows?table_id=tblTest&refresh=true")

    def test_extra_text_carries_generated_text_not_attachments(self):
        resp = self._get({
            "id": "rec1",
            "fields": {
                "ID": 7,
                "Foreign Key ID": "HTR-REEL-SET-7",
                "Status": "Done",
                "Interior JSON": '[{"room_type": "living room"}]',
                "Interior JSON3": '{"room_type": "dining room", "style": "Japandi"}',
                "Interior Prompt": "Slot 1: Generate me a living room",
                "Furniture Item1": [{"filename": "a.jpg", "url": "https://x/a.jpg"}],
                "Blended Image1": [{"filename": "b.jpg", "url": "https://x/b.jpg"}],
            },
        })
        self.assertEqual(resp.status_code, 200)
        row = resp.get_json()["rows"][0]
        extras = row["extra_text"]
        self.assertEqual(extras["Interior JSON"], '[{"room_type": "living room"}]')
        self.assertIn("dining room", extras["Interior JSON3"])
        self.assertTrue(extras["Interior Prompt"].startswith("Slot 1"))
        # Attachment blobs must not leak into the text payload.
        self.assertNotIn("Furniture Item1", extras)
        self.assertNotIn("Blended Image1", extras)

    def test_rows_without_generated_text_get_empty_extras(self):
        resp = self._get({
            "id": "rec2",
            "fields": {"ID": 1, "Status": "Standby"},
        })
        self.assertEqual(resp.status_code, 200)
        row = resp.get_json()["rows"][0]
        self.assertNotIn("Interior JSON", row["extra_text"])
        self.assertNotIn("Interior Prompt", row["extra_text"])
        # Legacy summary keys unchanged.
        self.assertTrue(row["foreign_key_id"])
        self.assertEqual(row["status"], "Standby")


if __name__ == "__main__":
    unittest.main()
