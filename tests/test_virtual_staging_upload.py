import unittest
from unittest import mock
from content_automation.fal_client import FalClient


class FalQueueTests(unittest.TestCase):
    def setUp(self):
        self.fal = FalClient(api_key="k")

    def test_submit_queue_uses_returned_urls(self):
        resp = mock.Mock(ok=True, status_code=200)
        resp.json.return_value = {
            "request_id": "abc",
            "status_url": "https://queue.fal.run/fal-ai/kling-video/requests/abc/status",
            "response_url": "https://queue.fal.run/fal-ai/kling-video/requests/abc",
        }
        with mock.patch("content_automation.fal_client.request_with_retry", return_value=resp) as rq:
            out = self.fal.submit_queue("fal-ai/kling-video/v3/pro/image-to-video", {"prompt": "x"})
        self.assertEqual(out["status_url"].rsplit("/", 1)[-1], "status")
        self.assertEqual(rq.call_args.args[2], "https://queue.fal.run/fal-ai/kling-video/v3/pro/image-to-video")

    def test_poll_raises_on_failed(self):
        st = mock.Mock(ok=True)
        st.json.return_value = {"status": "FAILED"}
        with mock.patch("content_automation.fal_client.request_with_retry", return_value=st):
            with self.assertRaises(Exception):
                self.fal.poll_queue_urls("https://s", "https://r", interval=0)

    def test_ensure_fal_url_passthrough(self):
        url = "https://v3b.fal.media/files/b/x/room.jpg"
        self.assertEqual(self.fal.ensure_fal_url(url, filename="room.jpg"), url)

    def test_ensure_fal_url_reuploads_airtable(self):
        with mock.patch.object(self.fal, "_download_to_temp", return_value="/tmp/r.jpg"), \
             mock.patch.object(self.fal, "upload_file", return_value="https://v3b.fal.media/files/new.jpg"):
            out = self.fal.ensure_fal_url("https://v5.airtableusercontent.com/abc", filename="r.jpg")
        self.assertTrue(out.startswith("https://v3b.fal.media/"))

    def test_ensure_fal_url_deletes_temp_file(self):
        import tempfile, pathlib
        tmp = pathlib.Path(tempfile.gettempdir()) / "test_room.jpg"
        tmp.write_bytes(b"test")
        with mock.patch.object(self.fal, "_download_to_temp", return_value=str(tmp)), \
             mock.patch.object(self.fal, "upload_file", return_value="https://v3b.fal.media/files/new.jpg"):
            out = self.fal.ensure_fal_url("https://v5.airtableusercontent.com/abc", filename="r.jpg")
        self.assertTrue(out.startswith("https://v3b.fal.media/"))
        self.assertFalse(tmp.exists())

    def test_generate_kling_video_generate_audio(self):
        resp = mock.Mock(ok=True, status_code=200)
        resp.json.return_value = {"request_id": "req-1"}
        with mock.patch("content_automation.fal_client.request_with_retry", return_value=resp) as rq, \
             mock.patch.object(self.fal, "poll_queue", return_value="https://v3b.fal.media/vid.mp4"):
            res = self.fal.generate_kling_video(
                prompt="test",
                start_image_url="https://v3b.fal.media/a.jpg",
                end_image_url="https://v3b.fal.media/b.jpg",
                generate_audio=False,
            )
            self.assertEqual(res, "https://v3b.fal.media/vid.mp4")
            call_json = rq.call_args.kwargs["json"]
            self.assertIn("generate_audio", call_json)
    def test_crop_to_reel_landscape(self):
        from PIL import Image
        from content_automation.media import crop_to_reel
        import tempfile, pathlib
        d = pathlib.Path(tempfile.mkdtemp())
        Image.new("RGB", (4000, 3000), "white").save(d / "in.jpg")
        out = crop_to_reel(d / "in.jpg", d / "out.jpg")
        with Image.open(out) as im:
            self.assertEqual(im.size, (1080, 1920))

    def test_crop_rejects_tiny(self):
        from PIL import Image
        from content_automation.media import crop_to_reel
        import tempfile, pathlib
        d = pathlib.Path(tempfile.mkdtemp())
        Image.new("RGB", (500, 400)).save(d / "s.jpg")
        with self.assertRaises(ValueError):
            crop_to_reel(d / "s.jpg", d / "o.jpg")

    def test_upload_mode_skips_krea_and_strip(self):
        import generate_virtual_staging_reel_pipeline as g
        c = mock.MagicMock()
        c.airtable.get_record.return_value = {
            "fields": {
                "Status": "Standby",
                "Furniture Item": [{"url": "https://v3b.fal.media/cut.png"}],
                "Item Name": "Mina 7",
            }
        }
        c.fal.ensure_fal_url.side_effect = lambda u, filename: u
        with mock.patch.object(g, "phase2_interior") as krea, \
             mock.patch.object(g, "phase5_empty_room_conversion") as strip, \
             mock.patch.object(g, "phase3_blending_prompt"), \
             mock.patch.object(g, "phase4_room_blend"), \
             mock.patch.object(g, "phase6_kling_video"), \
             mock.patch.object(g, "phase7_assemble_final_reel"), \
             mock.patch.object(g, "download_attachment"):
            g.process_record(c, "rec1", source="upload", empty_room_url="https://v3b.fal.media/room.jpg")
        krea.assert_not_called()
        strip.assert_not_called()

    def test_upload_requires_url(self):
        import generate_virtual_staging_reel_pipeline as g
        with self.assertRaises(SystemExit):
            g.main(["--source", "upload", "--dry-run"])

    def test_build_kling_payload_exact(self):
        import generate_virtual_staging_reel_pipeline as g
        p = g.build_kling_payload(
            "https://v3b.fal.media/a.jpg",
            "https://v3b.fal.media/b.jpg",
            g.UPLOAD_KLING_PROMPT,
            g.UPLOAD_KLING_NEGATIVE,
        )
        self.assertEqual(
            set(p),
            {"start_image_url", "end_image_url", "prompt", "duration", "generate_audio", "negative_prompt"},
        )
        self.assertEqual(p["duration"], "10")
        self.assertIs(p["generate_audio"], False)
        self.assertTrue(p["prompt"].startswith("Photorealistic interior, vertical video"))
        self.assertNotIn("{", p["prompt"])
        self.assertEqual(
            p["negative_prompt"],
            "blur, distort, low quality, shaky camera, cartoon, anime, text, watermark, deformed face, extra limbs",
        )

    def test_phase6_resumes_without_resubmit(self):
        import generate_virtual_staging_reel_pipeline as g
        import json
        c = mock.MagicMock()
        c.fal.ensure_fal_url.side_effect = lambda u, filename: u
        c.fal.poll_queue_urls.return_value = {"video": {"url": "https://v3b.fal.media/out.mp4"}}
        fields = {
            "Empty Room Interior": [{"url": "https://v3b.fal.media/a.jpg"}],
            "Fully Staged Room": [{"url": "https://v3b.fal.media/b.jpg"}],
            "Source Mode": "Upload",
            "Kling Queue Request": json.dumps({"request_id": "r", "status_url": "s", "response_url": "u"}),
        }
        with mock.patch.object(g, "download_attachment"), mock.patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 1234
            g.phase6_kling_video(c, "rec1", fields)
        c.fal.submit_queue.assert_not_called()


    def test_run_rejects_non_fal_url(self):
        import sys
        from pathlib import Path
        from flask import Flask
        ui_dir = str(Path(__file__).resolve().parent.parent / "UI Control")
        if ui_dir not in sys.path:
            sys.path.insert(0, ui_dir)
        import routes.virtual_staging_reel as vsr
        app = Flask(__name__)
        app.register_blueprint(vsr.virtual_staging_reel_bp)
        with mock.patch.object(vsr, "is_authorized", return_value=True):
            client = app.test_client()
            r = client.post(
                "/api/virtual-staging-reel/run",
                json={"source": "upload", "empty_room_url": "https://evil.example/x.jpg"},
            )
            self.assertEqual(r.status_code, 400)
            self.assertIn("must be a fal.media URL", r.get_json()["error"])

    def test_upload_requires_auth(self):
        import sys
        from pathlib import Path
        from flask import Flask
        ui_dir = str(Path(__file__).resolve().parent.parent / "UI Control")
        if ui_dir not in sys.path:
            sys.path.insert(0, ui_dir)
        import routes.virtual_staging_reel as vsr
        app = Flask(__name__)
        app.register_blueprint(vsr.virtual_staging_reel_bp)
        with mock.patch.object(vsr, "is_authorized", return_value=False):
            client = app.test_client()
            r = client.post("/api/virtual-staging-reel/upload-empty-room", data={})
            self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
