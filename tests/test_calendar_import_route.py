"""Unit tests for the Calendar XLSX Import Studio Blueprint."""

from __future__ import annotations

import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask


class FakeQueueResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class CalendarRouteTests(unittest.TestCase):
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
        # routes.common reads DASHBOARD_PIN once at import from the real
        # repo .env (which sets a PIN); force open access for these tests.
        self.pin_patch = patch.object(self.common, "DASHBOARD_PIN", "")
        self.pin_patch.start()

        self.module = importlib.import_module("routes.calendar")
        self.state_patch = patch.object(
            self.module, "STATE_PATH", self.workspace / "output" / "calendar_fixture_state.json"
        )
        self.state_patch.start()
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.calendar_bp)
        self.client = self.app.test_client()
        repo_root = Path(__file__).resolve().parents[1]
        self.fixture_xlsx = repo_root / "tests" / "fixtures" / "mini_calendar.xlsx"

    def tearDown(self):
        self.pin_patch.stop()
        self.state_patch.stop()
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()

    def _upload(self, endpoint: str, month: str = "October", with_file: bool = True):
        data: dict = {"month": month}
        if with_file:
            data["file"] = (io.BytesIO(self.fixture_xlsx.read_bytes()), "calendar.xlsx")
        return self.client.post(endpoint, data=data, content_type="multipart/form-data")

    def test_preview_requires_file(self):
        response = self._upload("/api/calendar/preview", with_file=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_preview_lists_todo_jobs(self):
        response = self._upload("/api/calendar/preview")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["job_count"], 3)
        self.assertTrue(body["skipped_count"] >= 3)
        job = body["jobs"][0]
        for key in ("date", "pipeline_type", "fixture_id", "run_endpoint", "status_endpoint"):
            self.assertIn(key, job)

    def test_preview_rejects_unknown_month(self):
        response = self._upload("/api/calendar/preview", month="Nope")
        self.assertEqual(response.status_code, 400)

    def test_preview_requires_pin_when_set(self):
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            response = self._upload("/api/calendar/preview")
        self.assertEqual(response.status_code, 401)

    def test_enqueue_posts_jobs_to_queue(self):
        calls: list = []

        def fake_urlopen(req, timeout=None):
            calls.append(json.loads(req.data.decode("utf-8")))
            return FakeQueueResponse(b'{"status": "queued"}')

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            response = self._upload("/api/calendar/enqueue")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["enqueued"], 3)
        self.assertEqual(len(calls), 3)
        for payload in calls:
            for key in ("pipeline_type", "fixture_id", "run_endpoint", "status_endpoint"):
                self.assertIn(key, payload)
        state_path = self.workspace / "output" / "calendar_fixture_state.json"
        self.assertTrue(state_path.is_file())

    def test_enqueue_reports_queue_errors(self):
        import urllib.error

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 500, "busy", {}, io.BytesIO(b'{"error": "busy"}')
            )

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            response = self._upload("/api/calendar/enqueue")
        body = response.get_json()
        self.assertEqual(body["enqueued"], 0)
        self.assertTrue(all(r["error"] for r in body["results"]))


if __name__ == "__main__":
    unittest.main()
