"""Before & After Reel: runner imports, fresh-row-only flow, protected rows and Studio phase parsing."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import tempfile

from PIL import Image

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


def _solid_jpg(path: Path, color) -> Path:
    Image.new("RGB", (216, 384), color).save(path, "JPEG")
    return path


def _frame_count(video: Path) -> int:
    import cv2

    cap = cv2.VideoCapture(str(video))
    try:
        return int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()


class SlideshowAfterSlideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def _build(self, name, after=None):
        out = self.tmp / f"{name}.mp4"
        pipeline.build_before_after_slideshow_video(
            first_slide_image_path=_solid_jpg(self.tmp / "first.jpg", (200, 50, 50)),
            angle_image_paths=[_solid_jpg(self.tmp / "a1.jpg", (50, 200, 50)), _solid_jpg(self.tmp / "a2.jpg", (50, 50, 200))],
            output_mp4_path=out,
            after_image_path=after,
            outro_image_path=_solid_jpg(self.tmp / "outro.jpg", (20, 20, 20)),
            width=108, height=192, fps=10,
        )
        return out

    def test_after_slide_adds_its_duration_to_the_reel(self):
        without = _frame_count(self._build("plain"))
        with_after = _frame_count(self._build("with_after", after=_solid_jpg(self.tmp / "after.jpg", (240, 240, 240))))
        self.assertEqual(with_after - without, 30)  # 3.0 s at 10 fps

    def test_missing_after_image_is_ignored(self):
        plain = _frame_count(self._build("plain2"))
        missing = _frame_count(self._build("missing", after=self.tmp / "nope.jpg"))
        self.assertEqual(plain, missing)


class SlideshowPipelineNameTagTests(unittest.TestCase):
    def _run(self, fields):
        """Run the slideshow phase with every network/video step mocked; return (built kwargs, tagger mock)."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        built = {}

        class Downloaded:
            def __init__(self, path):
                self.path = path

            def cleanup(self):
                pass

        counter = {"n": 0}

        def fake_download(session, url, **kwargs):
            counter["n"] += 1
            return Downloaded(_solid_jpg(tmp / f"dl_{counter['n']}.jpg", (120, 120, 120)))

        def fake_build(**kwargs):
            built.update(kwargs)
            kwargs["output_mp4_path"].write_bytes(b"video")
            return kwargs["output_mp4_path"]

        airtable = mock.Mock()
        airtable.list_records.return_value = [{"id": "recX", "fields": fields}]
        airtable.table_fields.return_value = {}
        fal = mock.Mock()
        with mock.patch.object(pipeline, "download_url_to_temp_file", side_effect=fake_download),              mock.patch.object(pipeline, "build_before_after_slideshow_video", side_effect=fake_build),              mock.patch.object(pipeline, "export_reel_artifacts", return_value=Path("unused")),              mock.patch.object(pipeline, "append_audit_log", return_value=None),              mock.patch("content_automation.item_tagger.tag_blended_image", return_value=(object(), None)) as tagger:
            ok = pipeline.generate_slideshow_reels_pipeline(fal, airtable, record_ids=["recX"])
        return ok, built, tagger

    BASE = {
        "Status": "Multiple Angle Blended Image Generating",
        "Item Name": "Tia | Brass and Frosted Glass Pendant Light",
        "Interior Generated": [{"url": "https://x/interior.jpg"}],
        "Blended Image": [{"url": "https://x/blended.jpg"}],
        "Thumbnail with Generated Text": [{"url": "https://x/thumb.jpg"}],
        "Multiple Angle Blended Image": [{"url": "https://x/a1.jpg"}, {"url": "https://x/a2.jpg"}],
    }

    def test_untagged_row_gets_the_name_stamped_locally_for_the_after_slide(self):
        ok, built, tagger = self._run(dict(self.BASE))
        self.assertTrue(ok)
        tagger.assert_called_once()
        self.assertEqual(tagger.call_args.kwargs["item_name"], "Tia")
        self.assertEqual(tagger.call_args.kwargs["product_type"], "Brass and Frosted Glass Pendant Light")
        self.assertEqual(tagger.call_args.kwargs["category"], "pendant_lights")
        self.assertIsNotNone(built["after_image_path"])

    def test_row_with_a_tagged_image_is_used_as_is(self):
        fields = dict(self.BASE)
        fields["Blended Image with Name text"] = [{"url": "https://x/tagged.jpg"}]
        ok, built, tagger = self._run(fields)
        self.assertTrue(ok)
        tagger.assert_not_called()
        self.assertIsNotNone(built["after_image_path"])


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
