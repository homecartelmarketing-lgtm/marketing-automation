"""Regression coverage for retrying transient provider media downloads."""

from __future__ import annotations

from pathlib import Path
import importlib
import sys
import tempfile
import unittest
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_automation import media
from content_automation.errors import ProviderError


class FakeImageResponse:
    ok = True
    status_code = 200
    headers = {"Content-Type": "image/png"}

    def iter_content(self, chunk_size: int = 8192):
        del chunk_size
        yield b"fake-image-bytes"


class FlakySession:
    def __init__(self, failures: int):
        self.failures = failures
        self.attempts = 0

    def request(self, method: str, url: str, **kwargs):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise requests.ConnectionError("temporary DNS resolution failure")
        return FakeImageResponse()


class SelectiveFailureSession:
    def __init__(self, failing_url: str):
        self.failing_url = failing_url
        self.attempts_by_url = {}

    def request(self, method: str, url: str, **kwargs):
        del method, kwargs
        self.attempts_by_url[url] = self.attempts_by_url.get(url, 0) + 1
        if url == self.failing_url:
            raise requests.ConnectionError("temporary DNS resolution failure")
        return FakeImageResponse()


class FakeFalClient:
    def __init__(self, failures: int):
        self.session = FlakySession(failures)
        self.generate_calls = 0

    def generate(self, **kwargs):
        self.generate_calls += 1
        return "https://v3b.fal.media/files/result.png"


class FakeSlideshowFal:
    def __init__(self, failing_url: str):
        self.session = SelectiveFailureSession(failing_url)


class FakeAirtableClient:
    def __init__(self):
        self.uploads = []
        self.updates = []

    def list_records(self):
        return [{
            "id": "recFutureRun",
            "fields": {
                "Status": "Generating Prompt for Blending",
                "Item Name": "Future Pendant",
                "SKU": "FUTURE-001",
                "Blending Prompt": "Blend this pendant into the room",
                "Interior Generated Photo": [{"url": "https://airtable.test/interior.jpg"}],
                "Furniture Item": [{"url": "https://airtable.test/product.jpg"}],
            },
        }]

    def table_fields(self):
        return {
            "Blended Image": {},
            "Status": {"choices": ["Processing Day Image"]},
        }

    def upload_attachment(self, record_id, field_name, local_image, filename):
        self.uploads.append({
            "record_id": record_id,
            "field_name": field_name,
            "filename": filename,
            "content": Path(local_image.path).read_bytes(),
        })

    def update_records(self, updates):
        self.updates.extend(updates)


class FakeSlideshowAirtable(FakeAirtableClient):
    def __init__(self, fields):
        super().__init__()
        self.fields = fields

    def list_records(self):
        return [{"id": "recFutureRun", "fields": self.fields}]

    def table_fields(self):
        return {
            "Multiple Angle Blended Image": {},
            "Thumbnail with Generated Text": {},
            "Slide Show Before and After Reel": {},
            "Status": {
                "choices": [
                    "Multiple Angle Blended Image Generating",
                    "Slide Show Before and After Reel Generating",
                    "Complete",
                ],
            },
        }


class MediaDownloadRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_tempdir = tempfile.tempdir
        tempfile.tempdir = self.temp.name

    def tearDown(self):
        tempfile.tempdir = self.previous_tempdir
        self.temp.cleanup()

    def downloader(self):
        downloader = getattr(media, "download_url_to_temp_file", None)
        self.assertIsNotNone(
            downloader,
            "download_url_to_temp_file must retry URL downloads before creating a temp file",
        )
        return downloader

    def test_transient_dns_failures_retry_the_same_url_then_write_one_file(self):
        session = FlakySession(failures=2)

        with patch("content_automation.http.time.sleep", return_value=None):
            downloaded = self.downloader()(
                session,
                "https://v3b.fal.media/files/result.png",
                prefix="fal_result_",
                suffix=".png",
                context="Download Fal result",
            )

        self.assertEqual(session.attempts, 3)
        self.assertEqual(Path(downloaded.path).read_bytes(), b"fake-image-bytes")
        self.assertEqual(downloaded.content_type, "image/png")
        self.assertEqual(len(list(Path(self.temp.name).iterdir())), 1)
        downloaded.cleanup()

    def test_exhausted_dns_retries_raise_without_creating_a_partial_file(self):
        session = FlakySession(failures=5)

        with patch("content_automation.http.time.sleep", return_value=None):
            with self.assertRaisesRegex(ProviderError, "temporary DNS resolution failure"):
                self.downloader()(
                    session,
                    "https://v3b.fal.media/files/result.png",
                    prefix="fal_result_",
                    suffix=".png",
                    context="Download Fal result",
                )

        self.assertEqual(session.attempts, 5)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_before_after_blend_retries_download_without_regenerating(self):
        pipeline = importlib.import_module("generate_before_after_reel_pipeline")
        fal = FakeFalClient(failures=2)
        airtable = FakeAirtableClient()

        with patch("content_automation.http.time.sleep", return_value=None), patch.object(
            pipeline, "append_audit_log", return_value=None
        ), patch(
            "requests.get",
            side_effect=requests.ConnectionError("raw requests.get bypassed retry protection"),
        ), patch(
            "content_automation.item_tagger.tag_and_upload_blended_image",
            return_value=None,
        ):
            result = pipeline.generate_nano_banana_pro_blends(
                fal,
                airtable,
                record_ids=["recFutureRun"],
            )

        self.assertTrue(result)
        self.assertEqual(fal.generate_calls, 1)
        self.assertEqual(fal.session.attempts, 3)
        self.assertEqual(len(airtable.uploads), 1)
        self.assertEqual(airtable.uploads[0]["content"], b"fake-image-bytes")
        self.assertEqual(len(airtable.updates), 1)

    def test_multiple_angle_download_exhaustion_does_not_advance_record(self):
        pipeline = importlib.import_module("generate_before_after_reel_pipeline")
        angle_url = "https://v3b.fal.media/files/angle.png"

        class FakeAngleFal(FakeSlideshowFal):
            def generate_multiple_angles(self, *args, **kwargs):
                del args, kwargs
                return [angle_url]

        fal = FakeAngleFal(angle_url)
        airtable = FakeSlideshowAirtable({
            "Status": "Processing Day Image",
            "Item Name": "Future Pendant",
            "Blended Image": [{"url": "https://airtable.test/blended.jpg"}],
        })

        with patch("content_automation.http.time.sleep", return_value=None), patch.object(
            pipeline, "append_audit_log", return_value=None
        ):
            result = pipeline.generate_multiple_angles_pipeline(
                fal,
                airtable,
                record_ids=["recFutureRun"],
            )

        self.assertFalse(result)
        self.assertEqual(fal.session.attempts_by_url[angle_url], 5)
        self.assertEqual(airtable.uploads, [])
        self.assertNotIn(
            "Complete",
            [fields.get("Status") for _, fields in airtable.updates],
        )

    def test_slideshow_angle_download_exhaustion_does_not_upload_or_complete(self):
        pipeline = importlib.import_module("generate_before_after_reel_pipeline")
        angle_url = "https://v3b.fal.media/files/angle.png"
        fal = FakeSlideshowFal(angle_url)
        airtable = FakeSlideshowAirtable({
            "Status": "Multiple Angle Blended Image Generating",
            "Item Name": "Future Pendant",
            "Interior Generated Photo": [{"url": "https://airtable.test/interior.jpg"}],
            "Thumbnail with Generated Text": [{"url": "https://airtable.test/thumbnail.jpg"}],
            "Multiple Angle Blended Image": [{"url": angle_url}],
        })

        def fake_build(*args, **kwargs):
            output_path = kwargs["output_mp4_path"]
            output_path.write_bytes(b"fake-video")
            return output_path

        with patch("content_automation.http.time.sleep", return_value=None), patch.object(
            pipeline, "build_before_after_slideshow_video", side_effect=fake_build
        ), patch.object(pipeline, "export_reel_artifacts", return_value=Path("unused")):
            result = pipeline.generate_slideshow_reels_pipeline(
                fal,
                airtable,
                record_ids=["recFutureRun"],
            )

        self.assertFalse(result)
        self.assertEqual(fal.session.attempts_by_url[angle_url], 5)
        self.assertEqual(airtable.uploads, [])
        self.assertNotIn(
            "Complete",
            [fields.get("Status") for _, fields in airtable.updates],
        )

    def test_export_blend_download_exhaustion_happens_before_upload_and_complete(self):
        pipeline = importlib.import_module("generate_before_after_reel_pipeline")
        blended_url = "https://v3b.fal.media/files/blended-export.png"
        fal = FakeSlideshowFal(blended_url)
        airtable = FakeSlideshowAirtable({
            "Status": "Multiple Angle Blended Image Generating",
            "Item Name": "Future Pendant",
            "Interior Generated Photo": [{"url": "https://airtable.test/interior.jpg"}],
            "Thumbnail with Generated Text": [{"url": "https://airtable.test/thumbnail.jpg"}],
            "Multiple Angle Blended Image": [{"url": "https://airtable.test/angle.jpg"}],
            "Blended Image with Name text": [{"url": blended_url}],
        })

        def fake_build(*args, **kwargs):
            output_path = kwargs["output_mp4_path"]
            output_path.write_bytes(b"fake-video")
            return output_path

        with patch("content_automation.http.time.sleep", return_value=None), patch.object(
            pipeline, "build_before_after_slideshow_video", side_effect=fake_build
        ), patch.object(pipeline, "export_reel_artifacts", return_value=Path("unused")):
            result = pipeline.generate_slideshow_reels_pipeline(
                fal,
                airtable,
                record_ids=["recFutureRun"],
            )

        self.assertFalse(result)
        self.assertEqual(fal.session.attempts_by_url[blended_url], 5)
        self.assertEqual(airtable.uploads, [])
        self.assertNotIn(
            "Complete",
            [fields.get("Status") for _, fields in airtable.updates],
        )


if __name__ == "__main__":
    unittest.main()
