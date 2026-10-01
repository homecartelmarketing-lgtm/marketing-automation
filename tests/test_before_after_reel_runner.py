"""Before & After Reel: runner imports, fresh-row-only flow, protected rows and Studio phase parsing."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import generate_before_after_reel_pipeline as pipeline
import run_before_after_reel as runner_module


def _route_module():
    routes_dir = Path(__file__).resolve().parents[1] / "UI Control"
    if str(routes_dir) not in sys.path:
        sys.path.insert(0, str(routes_dir))
    return importlib.import_module("routes.before_after_reel")


class PipelineHelpersTests(unittest.TestCase):
    def test_protected_statuses_are_defined(self):
        for status in ("posted", "scheduled", "complete", "done", "for manual", "discarded"):
            self.assertIn(status, pipeline.TERMINAL_AND_PROTECTED_STATUSES)

    def test_every_phase_function_accepts_record_ids(self):
        for name in (
            "generate_krea_interiors_pipeline",
            "generate_claude_blending_prompts",
            "generate_nano_banana_pro_blends",
            "generate_multiple_angles_pipeline",
            "generate_slideshow_reels_pipeline",
        ):
            params = inspect.signature(getattr(pipeline, name)).parameters
            self.assertIn("record_ids", params, name)

    def test_restrict_records_without_ids_skips_protected_rows(self):
        records = [
            {"id": "recA", "fields": {"Status": "Standby"}},
            {"id": "recB", "fields": {"Status": "Posted"}},
            {"id": "recC", "fields": {"Status": "Scheduled"}},
            {"id": "recD", "fields": {"Status": "Processing Day Image"}},
            {"id": "recE", "fields": {}},
        ]
        kept = [r["id"] for r in pipeline.restrict_records(records)]
        self.assertEqual(kept, ["recA", "recD", "recE"])

    def test_restrict_records_with_ids_only_returns_those_rows(self):
        records = [{"id": "recA", "fields": {}}, {"id": "recB", "fields": {"Status": "Posted"}}]
        self.assertEqual([r["id"] for r in pipeline.restrict_records(records, ["recB"])], ["recB"])


class TaggingCategoryTests(unittest.TestCase):
    def test_infer_fixture_category(self):
        self.assertEqual(pipeline.infer_fixture_category("Brass and Frosted Glass Pendant Light"), "pendant_lights")
        self.assertEqual(pipeline.infer_fixture_category("Modern Chandelier"), "chandeliers")
        self.assertEqual(pipeline.infer_fixture_category("Arc Floor Lamp"), "floor_lamps")
        self.assertEqual(pipeline.infer_fixture_category("Sofa"), "")

    def test_blend_phase_tags_the_item_with_a_category(self):
        # Regression: the tagging block referenced an undefined name `category`, so no name tag was ever stamped.
        from test_media_download_retry import FakeAirtableClient, FakeFalClient

        fal = FakeFalClient(failures=0)
        airtable = FakeAirtableClient()
        with mock.patch("content_automation.http.time.sleep", return_value=None),              mock.patch.object(pipeline, "append_audit_log", return_value=None),              mock.patch("content_automation.item_tagger.tag_and_upload_blended_image") as tagger:
            ok = pipeline.generate_nano_banana_pro_blends(fal, airtable, record_ids=["recFutureRun"])
        self.assertTrue(ok)
        tagger.assert_called_once()
        self.assertEqual(tagger.call_args.kwargs["category"], "pendant_lights")
        self.assertEqual(tagger.call_args.kwargs["item_name"], "Future Pendant")


class RunnerMainTests(unittest.TestCase):
    def _run_main(self, argv, created_ids):
        base = SimpleNamespace(krea_token="k", krea_base_url="u", fal_key="f", require=lambda providers: None)
        settings = SimpleNamespace(
            airtable_token="t", airtable_base_id="b", akeneo_host="h", akeneo_client_id="c",
            akeneo_secret="s", akeneo_username="u", akeneo_password="p", channel_name="ch",
        )
        scrape_runner = mock.Mock()
        scrape_runner.run.return_value = bool(created_ids)
        scrape_runner.created_record_ids = created_ids
        with mock.patch.object(runner_module, "load_settings", return_value=base), \
             mock.patch.object(runner_module, "load_scrape_settings", return_value=settings), \
             mock.patch.object(runner_module, "AkeneoClient"), \
             mock.patch.object(runner_module, "ScrapeAirtableClient"), \
             mock.patch.object(runner_module, "KreaClient"), \
             mock.patch.object(runner_module, "FalClient"), \
             mock.patch.object(runner_module, "FurnitureItemScrapeRunner", return_value=scrape_runner) as scraper_cls, \
             mock.patch.object(runner_module, "run_pipeline_for_table", return_value=True) as run_phases:
            code = runner_module.main(argv)
        return code, scraper_cls, run_phases

    def test_module_imports(self):
        self.assertTrue(callable(runner_module.main))
        self.assertFalse(hasattr(runner_module, "count_incomplete_records"))

    def test_always_scrapes_a_fresh_row_and_processes_only_it(self):
        code, scraper_cls, run_phases = self._run_main(
            ["--target", "pendant_lights", "--max-items", "1"], ["recNEW"]
        )
        self.assertEqual(code, 0)
        scraper_cls.assert_called_once()
        self.assertEqual(run_phases.call_args.kwargs["record_ids"], ["recNEW"])

    def test_no_new_product_returns_error_and_runs_no_phase(self):
        code, _, run_phases = self._run_main(["--target", "pendant_lights"], [])
        self.assertEqual(code, 1)
        run_phases.assert_not_called()

    def test_explicit_record_id_skips_scraping(self):
        code, scraper_cls, run_phases = self._run_main(
            ["--target", "pendant_lights", "--record-id", "recOLD"], []
        )
        self.assertEqual(code, 0)
        scraper_cls.assert_not_called()
        self.assertEqual(run_phases.call_args.kwargs["record_ids"], ["recOLD"])


class StudioPhaseParsingTests(unittest.TestCase):
    def test_phase_markers_advance_and_never_go_back(self):
        route = _route_module()
        state = {"current_phase": "", "current_phase_index": 0}
        route.update_phase_from_log(state, "[PHASE 1/6] Akeneo scrape: 1 new item(s)...")
        self.assertEqual(state["current_phase_index"], 1)
        route.update_phase_from_log(state, "[PHASE 4/6] Fal AI Nano Banana Pro Image Blending (After Image)...")
        self.assertEqual(state["current_phase_index"], 4)
        self.assertEqual(state["current_phase"], route.PHASE_LABELS[4])
        # Mentioning Krea / interior / akeneo later must not move the phase.
        route.update_phase_from_log(state, "[INFO] Krea interior image downloaded, akeneo item ready")
        route.update_phase_from_log(state, "[PHASE 2/6] stale line")
        self.assertEqual(state["current_phase_index"], 4)
        route.update_phase_from_log(state, "[PHASE 6/6] Slideshow Reel Video Generation")
        self.assertEqual(state["current_phase_index"], 6)


if __name__ == "__main__":
    unittest.main()
