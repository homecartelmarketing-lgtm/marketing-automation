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


if __name__ == "__main__":
    unittest.main()
