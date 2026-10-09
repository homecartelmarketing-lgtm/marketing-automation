"""Unit tests for House Tour Reel Krea 402 balance fallback and extract_clean_error."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_CONTROL_DIR = REPO_ROOT / "UI Control"
if str(UI_CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(UI_CONTROL_DIR))

from routes.common import extract_clean_error
from content_automation.errors import ProviderError
import generate_house_tour_reel_pipeline as pipeline


class TestExtractCleanError(unittest.TestCase):
    def test_krea_402_balance_error(self):
        logs = [
            "[PHASE 1/8] Generating 11 room interiors...",
            "Traceback (most recent call last):",
            "content_automation.errors.ProviderError: Krea image generation failed (402): "
            "{'message': 'Your API balance is separate from your workspace compute balance. "
            "Please top up your API balance to continue using the API.'}",
        ]
        result = extract_clean_error(logs, 1)
        self.assertIn("402", result)
        self.assertIn("Krea API balance is depleted", result)
        self.assertNotIn("Process exited with non-zero code", result)

    def test_krea_401_auth_error(self):
        logs = [
            "[PHASE 1/8] Generating 11 room interiors...",
            "content_automation.errors.ProviderError: Krea image generation failed (401): unauthorized",
        ]
        result = extract_clean_error(logs, 1)
        self.assertIn("Krea Auth Error", result)
        self.assertNotIn("Process exited with non-zero code", result)

    def test_provider_error_traceback(self):
        logs = [
            "Traceback (most recent call last):",
            "  File 'something.py', line 10, in <module>",
            "content_automation.errors.ProviderError: Some unexpected error occurred",
        ]
        result = extract_clean_error(logs, 1)
        self.assertIn("Some unexpected error occurred", result)
        self.assertNotIn("Process exited with non-zero code", result)


class TestHouseTourFallback(unittest.TestCase):
    @patch("generate_house_tour_reel_pipeline.ThreadPoolExecutor")
    def test_phase1_falls_back_to_fal_flux_on_krea_failure(self, mock_executor):
        # Configure ThreadPoolExecutor to run synchronously
        class SyncExecutor:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def map(self, fn, items):
                return [fn(item) for item in items]

        mock_executor.return_value = SyncExecutor()

        clients = MagicMock()
        # Krea raises ProviderError (402)
        clients.krea.generate_image.side_effect = ProviderError("Krea image generation failed (402)")
        # Fal generates successfully
        clients.fal.generate.return_value = "https://fal.media/files/flux_interior.jpg"

        fields: dict = {}
        # Run phase1_interiors for a single test row
        with patch.object(pipeline, "SLOTS", [1]):
            pipeline.phase1_interiors(clients, "recTEST123", fields)

        # Verify Krea was attempted
        clients.krea.generate_image.assert_called_once()
        # Verify Fal AI Flux was called as fallback
        clients.fal.generate.assert_called_once()
        call_kwargs = clients.fal.generate.call_args.kwargs
        self.assertEqual(call_kwargs.get("model"), "fal-ai/flux/schnell")
        self.assertEqual(call_kwargs.get("image_size"), "portrait_16_9")

        # Verify attachment updates used the Fal URL
        clients.airtable.update_records.assert_called()
        first_call = clients.airtable.update_records.call_args_list[0]
        updates = first_call[0][0][0][1]
        self.assertEqual(updates[pipeline.INTERIOR_FIELDS[1]], [{"url": "https://fal.media/files/flux_interior.jpg"}])


if __name__ == "__main__":
    unittest.main()
