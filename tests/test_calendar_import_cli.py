"""Tests for the Content Calendar importer CLI (Task 4): build_jobs + queue POST.

Mocked HTTP only -- never hit a real server in tests.
"""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

CLI_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts" / "ops" / "import_content_calendar.py"
)


def load_cli_module():
    spec = importlib.util.spec_from_file_location(
        "import_content_calendar", CLI_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBuildJobs(unittest.TestCase):
    def test_cli_skips_non_todo(self):
        from content_automation.calendar_import import build_jobs
        jobs, skipped = build_jobs([{"status": "Posted"}, {"status": "TO DO", "format": "Feeds", "idea": "Product Showcase", "date": "2026-10-05"}], state={})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(skipped), 1)

    def test_day_night_collapse_yields_one_job(self):
        from content_automation.calendar_import import build_jobs
        slots = [
            {"date": "2026-10-06", "format": "Stories", "idea": "Day (D&N)",
             "time": "", "status": "TO DO", "cell": "A1"},
            {"date": "2026-10-06", "format": "Stories", "idea": "Night (D&N)",
             "time": "", "status": "TO DO", "cell": "A2"},
        ]
        jobs, skipped = build_jobs(slots, state={})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(skipped), 0)
        self.assertEqual(jobs[0]["pipeline_type"], "day-night-story")
        self.assertEqual(jobs[0]["max_items"], 1)

    def test_unknown_idea_skipped_with_reason(self):
        from content_automation.calendar_import import build_jobs
        slots = [
            {"date": "2026-10-07", "format": "Feeds", "idea": "No Such Idea",
             "time": "", "status": "TO DO", "cell": "A1"},
            {"date": "2026-10-07", "format": "Reels", "idea": "House Tour",
             "time": "", "status": "TO DO", "cell": "A2"},
        ]
        jobs, skipped = build_jobs(slots, state={})
        self.assertEqual(len(jobs), 0)
        self.assertEqual(len(skipped), 2)
        reasons = {s["reason"] for s in skipped}
        self.assertIn("unknown-idea", reasons)
        self.assertIn("no Studio pipeline exists for house tours", reasons)

    def test_duplicate_date_pipeline_fixture_skipped(self):
        from content_automation.calendar_import import build_jobs
        slot = {"date": "2026-10-05", "format": "Feeds",
                "idea": "Product Showcase", "time": "",
                "status": "TO DO", "cell": "A1"}
        jobs, skipped = build_jobs([dict(slot), dict(slot)], state={})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["reason"], "duplicate")

    def test_job_shape_has_queue_required_fields(self):
        from content_automation.calendar_import import build_jobs
        jobs, _ = build_jobs(
            [{"date": "2026-10-05", "format": "Feeds",
              "idea": "Product Showcase", "time": "",
              "status": "TO DO", "cell": "A1"}],
            state={},
        )
        self.assertEqual(len(jobs), 1)
        for key in ("pipeline_type", "fixture_id", "run_endpoint",
                    "status_endpoint", "max_items", "date", "pipeline_name"):
            self.assertIn(key, jobs[0])
        self.assertTrue(jobs[0]["run_endpoint"].startswith("/api/"))
        self.assertTrue(jobs[0]["status_endpoint"].startswith("/api/"))


class TestEnqueuePost(unittest.TestCase):
    def test_post_helper_sends_required_fields(self):
        cli = load_cli_module()
        job = {"date": "2026-10-05", "pipeline_type": "cta",
               "pipeline_name": "cta", "fixture_id": "chandelier",
               "run_endpoint": "/api/cta/run",
               "status_endpoint": "/api/cta/status", "max_items": 1}
        captured = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"status": "queued"}).encode("utf-8")

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return FakeResp()

        with mock.patch.object(cli.urllib.request, "urlopen", fake_urlopen):
            cli.enqueue_job("http://127.0.0.1:5200", job)
        self.assertTrue(
            captured["url"].endswith("/api/queue/enqueue"))
        for key in ("pipeline_type", "fixture_id", "run_endpoint",
                    "status_endpoint"):
            self.assertIn(key, captured["body"])
        self.assertEqual(captured["body"]["fixture_id"], "chandelier")


if __name__ == "__main__":
    unittest.main()
