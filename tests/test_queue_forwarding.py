import json
from pathlib import Path
import sys
import unittest
from unittest import mock

# Ensure UI Control is on sys.path
UI_DIR = str(Path(__file__).resolve().parent.parent / "UI Control")
if UI_DIR not in sys.path:
    sys.path.insert(0, UI_DIR)

from routes import queue_manager as q


class QueueForwardingTests(unittest.TestCase):
    def test_dispatch_forwards_upload_fields(self):
        captured = {}

        def fake_urlopen(req, timeout=20):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            m = mock.MagicMock()
            m.__enter__.return_value.status = 200
            m.__enter__.return_value.read.return_value = b'{"status":"started"}'
            return m

        with mock.patch.object(q.urllib.request, "urlopen", fake_urlopen):
            q._dispatch_job_run({
                "run_endpoint": "/api/virtual-staging-reel/run",
                "fixture_id": "virtual-staging",
                "source": "upload",
                "empty_room_url": "https://v3b.fal.media/a.jpg",
            })

        self.assertEqual(captured["body"].get("source"), "upload")
        self.assertEqual(captured["body"].get("empty_room_url"), "https://v3b.fal.media/a.jpg")

    def test_enqueue_upload_dedup(self):
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(q.queue_bp)

        with mock.patch.object(q, "is_authorized", return_value=True), \
             mock.patch.object(q, "ensure_worker_started"):
            # Clear pending queue and active job
            with q._QUEUE_LOCK:
                q._PENDING_QUEUE.clear()
                q._ACTIVE_JOB = {"id": "dummy_active"}  # simulate busy worker

            client = app.test_client()

            # First upload job
            r1 = client.post("/api/queue/enqueue", json={
                "pipeline_type": "virtual-staging-reel",
                "fixture_id": "virtual-staging",
                "run_endpoint": "/api/virtual-staging-reel/run",
                "status_endpoint": "/api/virtual-staging-reel/status",
                "source": "upload",
                "empty_room_url": "https://v3b.fal.media/photo1.jpg",
            })
            self.assertEqual(r1.status_code, 201)

            # Second upload job with DIFFERENT URL should succeed
            r2 = client.post("/api/queue/enqueue", json={
                "pipeline_type": "virtual-staging-reel",
                "fixture_id": "virtual-staging",
                "run_endpoint": "/api/virtual-staging-reel/run",
                "status_endpoint": "/api/virtual-staging-reel/status",
                "source": "upload",
                "empty_room_url": "https://v3b.fal.media/photo2.jpg",
            })
            self.assertEqual(r2.status_code, 201)

            # Third upload job with SAME URL as photo1 should be rejected as already_queued
            r3 = client.post("/api/queue/enqueue", json={
                "pipeline_type": "virtual-staging-reel",
                "fixture_id": "virtual-staging",
                "run_endpoint": "/api/virtual-staging-reel/run",
                "status_endpoint": "/api/virtual-staging-reel/status",
                "source": "upload",
                "empty_room_url": "https://v3b.fal.media/photo1.jpg",
            })
            self.assertEqual(r3.status_code, 200)
            self.assertEqual(r3.get_json()["status"], "already_queued")


if __name__ == "__main__":
    unittest.main()
