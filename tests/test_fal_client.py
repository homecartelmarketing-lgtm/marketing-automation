"""Unit tests for FalClient.generate_seedance_video."""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from content_automation.errors import ProviderTimeout
from content_automation.fal_client import FalClient


def _client() -> FalClient:
    return FalClient(
        api_key="test-key",
        api_base="https://fal.run",
        queue_base="https://queue.fal.run",
        poll_interval=0.01,
        max_wait=1.0,
    )


class SeedanceVideoTests(unittest.TestCase):
    def test_duration_must_be_5_or_10(self):
        for bad in (3, 4, 6, 9, 11, 15, "12"):
            with self.subTest(duration=bad):
                with self.assertRaises(ValueError):
                    _client().generate_seedance_video("lights on", "http://img", duration=bad)

    def test_sdk_path_returns_video_url(self):
        client = _client()
        fake_sdk = MagicMock()
        fake_sdk.subscribe.return_value = {"video": {"url": "https://fal.media/v.mp4"}}
        with patch.dict(sys.modules, {"fal_client": fake_sdk}):
            url = client.generate_seedance_video("lights on", "http://img")
        self.assertEqual(url, "https://fal.media/v.mp4")
        args, kwargs = fake_sdk.subscribe.call_args
        self.assertEqual(args[0], "bytedance/seedance-2.0/reference-to-video")
        self.assertEqual(kwargs["arguments"]["image_urls"], ["http://img"])
        self.assertEqual(kwargs["arguments"]["duration"], "10")
        self.assertEqual(kwargs["arguments"]["aspect_ratio"], "9:16")

    def test_queue_rest_fallback_path(self):
        client = _client()
        client.poll_queue = MagicMock(return_value="https://fal.media/fallback.mp4")
        fake_response = SimpleNamespace(
            ok=True,
            json=lambda: {"request_id": "req-123"},
        )
        with patch.dict(sys.modules, {"fal_client": None}):
            with patch(
                "content_automation.fal_client.request_with_retry",
                return_value=fake_response,
            ) as post_mock:
                url = client.generate_seedance_video("lights on", "http://img", duration=5)
        self.assertEqual(url, "https://fal.media/fallback.mp4")
        post_mock.assert_called_once()
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["image_urls"], ["http://img"])
        self.assertEqual(payload["duration"], "5")
        self.assertEqual(payload["aspect_ratio"], "9:16")
        client.poll_queue.assert_called_once_with(
            "bytedance/seedance-2.0/reference-to-video", "req-123"
        )

    def test_requires_api_key(self):
        with self.assertRaises(Exception):
            FalClient(api_key="").generate_seedance_video("lights on", "http://img")


class ElevenLabsSoundEffectTests(unittest.TestCase):
    def test_queue_timeout_skips_the_long_synchronous_call(self):
        client = _client()
        queued = SimpleNamespace(ok=True, json=lambda: {"request_id": "req-9"})
        with patch(
            "content_automation.fal_client.request_with_retry", return_value=queued
        ) as request_mock, patch.object(
            client, "poll_queue_raw", side_effect=ProviderTimeout("stuck in queue")
        ) as poll_mock:
            with self.assertRaises(ProviderTimeout):
                client.generate_elevenlabs_sound_effect("soft pop", max_wait=45.0)

        poll_mock.assert_called_once_with(
            "fal-ai/elevenlabs/sound-effects/v2", "req-9", max_wait=45.0
        )
        self.assertEqual(request_mock.call_count, 1)  # queue POST only, no sync fallback

    def test_poll_queue_raw_uses_the_call_budget(self):
        client = _client()
        client.poll_interval = 0.01
        status = SimpleNamespace(
            ok=True, json=lambda: {"status": "IN_QUEUE"}
        )
        with patch("content_automation.fal_client.request_with_retry", return_value=status):
            with self.assertRaises(ProviderTimeout) as error:
                client.poll_queue_raw("fal-ai/elevenlabs/sound-effects/v2", "req-1", max_wait=0.2)
        self.assertIn("0.2s", str(error.exception))


if __name__ == "__main__":
    unittest.main()
