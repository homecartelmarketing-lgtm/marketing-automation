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
            self.assertIs(call_json["generate_audio"], False)


if __name__ == "__main__":
    unittest.main()
