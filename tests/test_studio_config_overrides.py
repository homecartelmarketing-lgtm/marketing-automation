"""Studio edit settings must survive a restart and reach child processes."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from dotenv import dotenv_values
from flask import Flask


class StudioConfigOverrideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        routes_dir = Path(__file__).resolve().parents[1] / "UI Control"
        sys.path.insert(0, str(routes_dir))
        self.common = importlib.import_module("routes.common")
        self.marketing_patch = patch.object(self.common, "MARKETING_DIR", self.workspace)
        self.overrides_patch = patch.object(
            self.common, "OVERRIDES_FILE", self.workspace / "output" / "config_overrides.json"
        )
        self.marketing_patch.start()
        self.overrides_patch.start()
        (self.workspace / ".env").write_text("", encoding="utf-8")

    def tearDown(self):
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()

    def test_prompt_edit_persists_special_characters(self):
        key = "TEST_STUDIO_INTERIOR_PROMPT"
        prompt = "A bright room # keep this note, with a chandelier\nand daylight"
        os.environ.pop(key, None)

        self.common.save_config_override(key, prompt)

        self.assertEqual(self.common.load_config_overrides()[key], prompt)
        self.assertEqual(dotenv_values(self.workspace / ".env")[key], prompt)
        self.assertEqual(os.environ[key], prompt)
        os.environ.pop(key, None)

    def test_failed_persistence_does_not_report_success(self):
        key = "TEST_STUDIO_FAILED_PROMPT"
        os.environ.pop(key, None)
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.common.save_config_override(key, "new room prompt")
        self.assertNotIn(key, os.environ)

    def test_feed_edit_routes_use_persistent_settings(self):
        for module_name, blueprint_name, config_name in (
            ("moodboard_1_feed", "moodboard_1_feed_bp", "MOODBOARD_1_FEED_PROMPT_CONFIG"),
            ("moodboard_2_feed", "moodboard_2_feed_bp", "MOODBOARD_2_FEED_PROMPT_CONFIG"),
            ("tips_edu_feed", "tips_edu_feed_bp", "TIPS_EDU_FEED_PROMPT_CONFIG"),
        ):
            with self.subTest(module=module_name):
                module = importlib.import_module(f"routes.{module_name}")
                fixture_id = next(iter(getattr(module, config_name)))
                app = Flask(__name__)
                blueprint = getattr(module, blueprint_name)
                app.register_blueprint(blueprint)
                saved = []
                with patch.object(module, "is_authorized", return_value=True), patch.object(
                    module, "save_config_override", side_effect=lambda key, value: saved.append((key, value)), create=True
                ):
                    response = app.test_client().post(
                        blueprint.url_prefix + "/prompt",
                        json={"fixture_id": fixture_id, "prompt": "Edited interior prompt"},
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(saved, [(getattr(module, config_name)[fixture_id]["env_key"], "Edited interior prompt")])

    def test_moodboard_one_command_uses_edited_interior_settings(self):
        module = importlib.import_module("routes.moodboard_1_feed")
        command = module.build_generation_command(
            "tbl9u5vjgx8kuE44R", 2, "new-moodboard-id", "Bright dining interior"
        )
        self.assertEqual(command[1], "generate_moodboard_1_feed.py")
        self.assertEqual(command[command.index("--moodboard-id") + 1], "new-moodboard-id")
        self.assertEqual(command[command.index("--prompt") + 1], "Bright dining interior")

    def test_tips_feed_command_uses_edited_interior_settings(self):
        module = importlib.import_module("routes.tips_edu_feed")
        command = module.build_generation_command(
            "chandeliers", 2, "new-moodboard-id", "Bright living interior"
        )
        self.assertEqual(command[command.index("--moodboard-id") + 1], "new-moodboard-id")
        self.assertEqual(command[command.index("--prompt") + 1], "Bright living interior")

    def test_cta_completed_count_excludes_pending(self):
        module = importlib.import_module("routes.cta_story")
        app = Flask(__name__)
        app.register_blueprint(module.cta_bp)
        fixture = {
            "chandelier": {
                "id": "chandelier", "name": "Chandelier", "table_id": "tblTest",
                "total": 100, "moodboard_id": "test", "prompt": "test",
            }
        }
        response_body = {
            "records": [
                {"fields": {"Status": "Pending"}},
                {"fields": {"Status": "Complete"}},
            ]
        }
        fake_response = SimpleNamespace(ok=True, json=lambda: response_body)
        with patch.object(module, "get_cta_fixtures", return_value=fixture), patch.object(
            module, "load_settings", return_value=SimpleNamespace(airtable_base_id="base", airtable_token="token")
        ), patch.object(module.requests, "get", return_value=fake_response):
            response = app.test_client().get(module.cta_bp.url_prefix + "/counts?refresh=true")
        self.assertEqual(response.status_code, 200)
        count = response.json["counts"]["chandelier"]
        self.assertEqual(count["status_counts"]["C"], 1)
        self.assertEqual(count["completed"], 1)

    def test_one_product_reel_reports_completed_field(self):
        module = importlib.import_module("routes.one_product_three_styles_reel")
        app = Flask(__name__)
        app.register_blueprint(module.one_product_three_styles_reel_bp)
        source = importlib.import_module("content_automation.airtable_client")
        with patch.object(source, "fetch_status_breakdown", return_value={"P": 2, "S": 0, "C": 1, "D": 0, "FM": 0}):
            response = app.test_client().get(module.one_product_three_styles_reel_bp.url_prefix + "/counts?refresh=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["counts"]["chandelier"]["completed"], 1)

    def test_product_closeup_reel_reads_editor_settings(self):
        with patch.dict(os.environ, {
            "KREA_MOODBOARD_ID_TABLE_LAMPS_PRODUCT_CLOSEUP_REEL": "edited-board",
            "PROMPT_PRODUCT_CLOSEUP_REEL_TABLE_LAMP": "Edited bedroom interior",
        }):
            module = importlib.import_module("generate_product_closeup_reel_pipeline")
            self.assertEqual(module.resolve_interior_settings(), ("edited-board", "Edited bedroom interior"))

    def test_style_reel_editor_applies_to_cover_slot(self):
        module = importlib.import_module("run_style_reel_slideshow")
        with patch.dict(os.environ, {
            "KREA_MOODBOARD_ID_STYLE_REEL_SLIDESHOW": "edited-cover-board",
            "PROMPT_STYLE_REEL_SLIDESHOW": "Edited cover interior",
        }):
            slots = module.resolve_slots()
        self.assertEqual(slots[0].moodboard_id, "edited-cover-board")
        self.assertEqual(slots[0].interior_prompt, "Edited cover interior")
        self.assertEqual(slots[1].moodboard_id, module.SLOTS[1].moodboard_id)

    def test_day_night_reel_accepts_editor_settings(self):
        module = importlib.import_module("run_day_night_reel")
        args = module.parse_args(["--target", "pendant", "--moodboard-id", "edited-board", "--interior-prompt", "Edited dining room"])
        pipeline = module.resolve_day_night_pipeline(args.target, prompt_if_interactive=False)
        self.assertEqual(module.apply_interior_overrides(pipeline, args).moodboard_id, "edited-board")
        self.assertEqual(module.apply_interior_overrides(pipeline, args).interior_prompt, "Edited dining room")

    def test_before_after_reel_accepts_editor_prompt(self):
        module = importlib.import_module("run_before_after_reel")
        args = module.parse_args(["--target", "pendant_lights", "--interior-prompt", "Edited dining room"])
        self.assertEqual(args.interior_prompt, "Edited dining room")

    def test_before_after_reel_uses_editor_prompt_instead_of_table_default(self):
        module = importlib.import_module("run_before_after_reel")
        args = module.parse_args(["--target", "pendant_lights", "--interior-prompt", "Edited dining room"])
        reel_config = {"interior_prompt": "Default dining room"}
        self.assertEqual(
            module.resolve_interior_prompt(reel_config, args.interior_prompt),
            "Edited dining room",
        )

    def test_airtable_count_failure_is_not_a_zero_count(self):
        source = importlib.import_module("content_automation.airtable_client")
        fake_response = SimpleNamespace(ok=False, status_code=503)
        with patch.object(source.requests, "get", return_value=fake_response):
            with self.assertRaisesRegex(RuntimeError, "503"):
                source.fetch_status_breakdown("token", "base", "tblTest")

    def test_three_blended_reel_photos_hold_for_five_four_four_seconds(self):
        video = importlib.import_module("content_automation.video")
        self.assertEqual(video.resolve_slide_intervals(3, per_slide_seconds=(5.0, 4.0, 4.0)), [5.0, 4.0, 4.0])

    def test_all_studio_count_tabs_report_c_badge_as_completed(self):
        server = importlib.import_module("api_server")
        source = importlib.import_module("content_automation.airtable_client")
        fake_response = SimpleNamespace(ok=True, json=lambda: {"records": [
            {"fields": {"Status": "Pending"}}, {"fields": {"Status": "Complete"}},
        ]})
        fake_breakdown = {"P": 1, "S": 0, "C": 1, "D": 0, "FM": 0}
        paths = sorted(rule.rule for rule in server.app.url_map.iter_rules() if rule.rule.endswith("/counts"))
        self.assertEqual(len(paths), 23)
        with patch.object(source.requests, "get", return_value=fake_response), patch.object(
            source, "fetch_status_breakdown", return_value=fake_breakdown
        ):
            for path in paths:
                with self.subTest(path=path):
                    response = server.app.test_client().get(path + "?refresh=true")
                    self.assertEqual(response.status_code, 200)
                    for fixture in response.json["counts"].values():
                        self.assertEqual(fixture["completed"], fixture["status_counts"]["C"])

    def test_three_styles_reel_uses_pipeline_specific_moodboard_key(self):
        route = importlib.import_module("routes.one_product_three_styles_reel")
        self.assertEqual(
            route.ONE_PRODUCT_THREE_STYLES_REEL_MOODBOARD_CONFIG["chandelier"]["env_key"],
            "KREA_MOODBOARD_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL",
        )

    def test_every_editable_pipeline_has_both_edit_endpoints(self):
        server = importlib.import_module("api_server")
        routes = {rule.rule for rule in server.app.url_map.iter_rules()}
        moodboard_prefixes = {path.removesuffix("/moodboard") for path in routes if path.endswith("/moodboard")}
        prompt_prefixes = {path.removesuffix("/prompt") for path in routes if path.endswith("/prompt")}
        self.assertEqual(len(moodboard_prefixes), 18)
        self.assertEqual(moodboard_prefixes, prompt_prefixes)


if __name__ == "__main__":
    unittest.main()
