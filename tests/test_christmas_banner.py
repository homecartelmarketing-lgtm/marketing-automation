"""Unit tests for the Christmas Banner pipeline helpers and Studio blueprint."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from PIL import Image

from content_automation import overlay as overlay_module
from content_automation.overlay import BANNER_SUBTITLE_BOX, BANNER_TITLE_BOX, overlay_banner_title_subtitle
from content_automation.prompts import build_banner_copy_instruction, build_banner_multi_fixture_instruction
import generate_christmas_banner_pipeline as pipeline


class BannerPipelineHelperTests(unittest.TestCase):
    def test_fixture_order_is_ch_pe_fl_tl_wl(self):
        self.assertEqual([f["code"] for f in pipeline.FIXTURES], ["CH", "PE", "FL", "TL", "WL"])
        self.assertEqual([f["category"] for f in pipeline.FIXTURES][-1], "wall_lights")

    def test_banner_is_21_9_and_krea_uses_its_widest_supported_ratio(self):
        self.assertEqual(pipeline.ASPECT_RATIO, "21:9")
        self.assertEqual(pipeline.KREA_ASPECT_RATIO, "2.35:1")

    def test_phase2_retries_non_moodboard_errors_but_not_moodboard_errors(self):
        from unittest.mock import MagicMock

        clients = MagicMock()
        clients.krea.generate.side_effect = [
            pipeline.ProviderError("Krea image generation failed (422): invalid aspect_ratio"),
            "https://example.com/room.jpg",
        ]
        with patch.object(pipeline, "FIELD_INTERIOR", "Room Interior"):
            pipeline.run_phase_2_interior(clients, "recX")
        ratios = [c.kwargs["aspect_ratio"] for c in clients.krea.generate.call_args_list]
        self.assertEqual(ratios, ["2.35:1", "16:9"])

        clients = MagicMock()
        clients.krea.generate.side_effect = pipeline.ProviderError(
            f"Moodboard Not Found: Krea moodboard '{pipeline.DEFAULT_MOODBOARD_ID}' was not found"
        )
        with self.assertRaises(pipeline.ProviderError):
            pipeline.run_phase_2_interior(clients, "recX")
        self.assertEqual(clients.krea.generate.call_count, 1)

    def test_fixtures_from_record_sorted_and_named(self):
        fields = {
            pipeline.FIELD_ITEM_NAME: "CH: Aarhus\nPE: Nova\nWL: Sconce",
            pipeline.FIELD_FURNITURE: [
                {"filename": "WL_s3_m.png", "url": "u-wl"},
                {"filename": "CH_s1_m.png", "url": "u-ch"},
                {"filename": "PE_s2_m.png", "url": "u-pe"},
                {"filename": "unrelated.png", "url": "u-x"},
            ],
        }
        items = pipeline._banner_fixtures_from_record(fields)
        self.assertEqual([i["code"] for i in items], ["CH", "PE", "WL"])
        self.assertEqual(items[0]["name"], "Aarhus")
        self.assertEqual(items[2]["url"], "u-wl")

    def test_parse_coded_lines_strips_prefix(self):
        self.assertEqual(pipeline._parse_coded_lines("CH: SKU-1\nPE: sku-2\n"), ["sku-1", "sku-2"])

    def test_multi_fixture_instruction_mentions_every_image_and_ratio(self):
        fixtures = [{"code": f["code"], "label": f["label"], "name": "X"} for f in pipeline.FIXTURES]
        text = build_banner_multi_fixture_instruction(fixtures, aspect_ratio="21:9")
        self.assertIn("Images 2 to 6", text)
        self.assertIn("21:9", text)
        for idx in range(2, 7):
            self.assertIn(f"Image {idx}:", text)

    def test_fallback_prompt_lists_all_fixtures(self):
        fixtures = [{"code": f["code"], "label": f["label"], "name": f["label"]} for f in pipeline.FIXTURES]
        text = pipeline._fallback_blend_prompt(fixtures)
        for fx in pipeline.FIXTURES:
            self.assertIn(fx["label"], text)

    def test_resolve_table_id_defaults_to_banner_table(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(pipeline.TABLE_ENV_KEY, None)
            self.assertEqual(pipeline.resolve_table_id(None), "tblgNk1Tp6qKUcduw")
            self.assertEqual(pipeline.resolve_table_id("tblABC"), "tblABC")
        with patch.dict(os.environ, {pipeline.TABLE_ENV_KEY: "tblFromEnv"}):
            self.assertEqual(pipeline.resolve_table_id(None), "tblFromEnv")

    def test_banner_table_has_foreign_key_prefix(self):
        from content_automation.foreign_key import generate_foreign_key
        self.assertEqual(generate_foreign_key("tblgNk1Tp6qKUcduw", 3), "XMS-BANNER-ALL-3")

    def test_text_only_requires_record_id(self):
        with self.assertRaises(pipeline.AutomationError):
            pipeline.run_pipeline(text_only=True)


class BannerCopyTests(unittest.TestCase):
    def test_parse_fenced_json(self):
        reply = '```json\n{"title": "Light Up Your Christmas", "subtitle": "Warm glow for festive homes."}\n```'
        self.assertEqual(
            pipeline.parse_banner_copy(reply),
            ("Light Up Your Christmas", "Warm glow for festive homes"),
        )

    def test_parse_regex_fallback_for_broken_json(self):
        title, subtitle = pipeline.parse_banner_copy(
            'here: {"title": "Make Every Room Glow Brighter", "subtitle": "With statement lighting this Christmas" ...'
        )
        self.assertEqual(title, "Make Every Room Glow Brighter")
        self.assertEqual(subtitle, "With statement lighting this Christmas")

    def test_subtitle_first_letter_is_capitalised(self):
        _, subtitle = pipeline.parse_banner_copy(
            '{"title": "Make Every Room Glow Brighter", "subtitle": "with fixtures crafted for elegance"}'
        )
        self.assertEqual(subtitle, "With fixtures crafted for elegance")

    def test_title_and_subtitle_must_be_four_or_five_words(self):
        good_title, good_subtitle = "Make Every Room Glow", "Lights that set the mood"
        cases = (
            ("Festive Glow", good_subtitle, pipeline.FALLBACK_TITLE, good_subtitle),  # title 2 words
            ("Make Every Room Glow Brighter Today", good_subtitle, pipeline.FALLBACK_TITLE, good_subtitle),  # 6 words
            (good_title, "Warm light", good_title, pipeline.FALLBACK_SUBTITLE),  # subtitle 2 words
            (good_title, "With statement lighting for festive corners", good_title, pipeline.FALLBACK_SUBTITLE),  # 6
        )
        for title, subtitle, expected_title, expected_subtitle in cases:
            parsed = pipeline.parse_banner_copy('{"title": "%s", "subtitle": "%s"}' % (title, subtitle))
            self.assertEqual(parsed, (expected_title, expected_subtitle), (title, subtitle))

    def test_copy_problems_names_the_word_count(self):
        good = '{"title": "Let Your Home Glow Golden", "subtitle": "With fixtures crafted for seasons"}'
        self.assertEqual(pipeline.copy_problems(good), [])
        bad = '{"title": "Let Your Home Glow Golden", "subtitle": "with fixtures crafted for the season"}'
        problems = pipeline.copy_problems(bad)
        self.assertEqual(len(problems), 1)
        self.assertIn("subtitle", problems[0])
        self.assertIn("6 words", problems[0])

    def _phase5_clients(self, replies):
        from unittest.mock import MagicMock

        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": {
            pipeline.FIELD_BANNER: [{"url": "https://example.test/banner.jpg"}],
            pipeline.FIELD_ITEM_NAME: "CH: Aegnor | Chandelier",
        }}
        clients.fal.generate_claude_vision.side_effect = replies
        return clients

    def test_phase5_retries_claude_with_the_reason_instead_of_using_the_fallback(self):
        bad = '{"title": "Let Your Home Glow Golden", "subtitle": "with fixtures crafted for the season"}'
        good = '{"title": "Let Your Home Glow Golden", "subtitle": "With fixtures crafted for seasons"}'
        clients = self._phase5_clients([bad, good])
        title, subtitle = pipeline.run_phase_5_copy(clients, "recX")
        self.assertEqual((title, subtitle), ("Let Your Home Glow Golden", "With fixtures crafted for seasons"))
        self.assertEqual(clients.fal.generate_claude_vision.call_count, 2)
        retry_prompt = clients.fal.generate_claude_vision.call_args_list[1].kwargs["prompt"]
        self.assertIn("rejected because", retry_prompt)
        self.assertIn("6 words", retry_prompt)

    def test_phase5_uses_defaults_after_every_attempt_fails(self):
        bad = '{"title": "Festive Glow", "subtitle": "Warm light"}'
        clients = self._phase5_clients([bad] * pipeline.COPY_ATTEMPTS)
        title, subtitle = pipeline.run_phase_5_copy(clients, "recX")
        self.assertEqual((title, subtitle), (pipeline.FALLBACK_TITLE, pipeline.FALLBACK_SUBTITLE))
        self.assertEqual(clients.fal.generate_claude_vision.call_count, pipeline.COPY_ATTEMPTS)

    def test_fallbacks_are_four_to_five_words(self):
        self.assertIn(len(pipeline.FALLBACK_TITLE.split()), pipeline.TITLE_WORDS)
        self.assertIn(len(pipeline.FALLBACK_SUBTITLE.split()), pipeline.SUBTITLE_WORDS)

    def test_garbage_and_overlong_use_defaults(self):
        self.assertEqual(
            pipeline.parse_banner_copy("no json at all"),
            (pipeline.FALLBACK_TITLE, pipeline.FALLBACK_SUBTITLE),
        )
        title, _ = pipeline.parse_banner_copy('{"title": "%s", "subtitle": "ok"}' % ("word " * 20))
        self.assertEqual(title, pipeline.FALLBACK_TITLE)

    def test_copy_instruction_states_limits(self):
        text = build_banner_copy_instruction(["Aarhus | Chandelier"], title_max_chars=30, subtitle_max_chars=40)
        self.assertIn("30", text)
        self.assertIn("40", text)
        self.assertEqual(text.count("4 to 5 words"), 2)
        self.assertIn("continues or completes the thought of that title", text)
        self.assertIn('"title"', text)
        self.assertIn("Aarhus", text)

    def test_shadow_defaults_and_standard_fields_are_provisioned(self):
        self.assertEqual(overlay_module.BANNER_SHADOW_COLOR, (0, 0, 0))
        self.assertEqual(overlay_module.BANNER_SHADOW_INTENSITY, 100)
        self.assertEqual(overlay_module.BANNER_TITLE_FONT_FILE, "Poppins-Medium.ttf")
        self.assertEqual(overlay_module.BANNER_SUBTITLE_FONT_FILE, "Poppins-Regular.ttf")
        self.assertEqual(overlay_module.BANNER_TITLE_FONT_SIZE, 81.8)
        self.assertEqual(overlay_module.BANNER_SUBTITLE_FONT_SIZE, 46.3)
        # wide enough for a 4-5 word title at the full Canva size
        self.assertEqual(overlay_module.BANNER_TITLE_BOX.width, 1680)
        self.assertEqual(overlay_module.BANNER_SUBTITLE_BOX.width, 1680)
        self.assertTrue((REPO_ROOT / "content_automation" / "fonts" / "Poppins-Medium.ttf").is_file())
        for name in ("Status", "Foreign Key ID", "Date and Time Generated"):
            self.assertIn(name, pipeline.REQUIRED_FIELDS)
        self.assertNotIn("ID", pipeline.REQUIRED_FIELDS)

    def test_phase1_creates_row_without_autonumber_or_foreign_key(self):
        from unittest.mock import MagicMock

        clients = MagicMock()
        clients.airtable.list_records.return_value = []
        clients.airtable.create_record.return_value = "recNEW"

        def fake_pick(_clients, fx, *_args):
            return {
                "code": fx["code"], "sku": f"SKU-{fx['code']}", "clean_name": f"Name {fx['code']}",
                "media_code": "m.png", "cutout": Path("cutout.png"),
            }

        with patch.object(pipeline, "fetch_all_base_existing_identities", return_value=(set(), set(), set())), \
                patch.object(pipeline, "ShopifyClient") as shopify, \
                patch.object(pipeline, "_pick_fixture", side_effect=fake_pick):
            shopify.return_value.load_published_identities.return_value = None
            record_id = pipeline.run_phase_1_scrape(clients)

        self.assertEqual(record_id, "recNEW")
        clients.airtable.ensure_fields.assert_called_once_with(pipeline.REQUIRED_FIELDS)
        fields = clients.airtable.create_record.call_args.args[0]
        self.assertNotIn("ID", fields)
        self.assertNotIn("Foreign Key ID", fields)
        self.assertEqual(fields["Status"], "In progress")
        self.assertEqual(fields["SKU"].splitlines()[0], "CH: SKU-CH")
        self.assertEqual(clients.airtable.upload_attachment.call_count, 5)

    def test_phase5_copy_prompt_lists_only_the_christmas_fixtures_of_a_banner_set_row(self):
        clients = self._phase5_clients(['{"title": "Make Every Room Glow", "subtitle": "With fixtures crafted for radiance"}'])
        fields = clients.airtable.get_record.return_value["fields"]
        fields[pipeline.FIELD_ITEM_NAME] = (
            "CH: Aegnor\nPE: Hedda\nFL: Azazel\nTL: Siriana\nWL: Joakimm\nDP: Faramir\nKA: Yarpen Une\nKB: Ellowen"
        )
        pipeline.run_phase_5_copy(clients, "recX")
        prompt = clients.fal.generate_claude_vision.call_args.kwargs["prompt"]
        for name in ("Aegnor", "Hedda", "Azazel", "Siriana", "Joakimm"):
            self.assertIn(name, prompt)
        for name in ("Faramir", "Yarpen Une", "Ellowen"):  # the Sale banner's pendants
            self.assertNotIn(name, prompt)

    def _phase6(self, **kwargs):
        from unittest.mock import MagicMock
        import tempfile

        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": {
            pipeline.FIELD_BANNER: [{"url": "https://example.test/banner.jpg"}],
            pipeline.FIELD_TITLE: "Make Every Room Glow Brighter",
            pipeline.FIELD_SUBTITLE: "With fixtures crafted for radiance",
        }}
        with tempfile.TemporaryDirectory() as tmp, patch.object(pipeline, "OUTPUT_DIR", Path(tmp)), \
                patch.object(pipeline, "download_url_to_temp_file", return_value=MagicMock(path="base.jpg")), \
                patch.object(pipeline, "overlay_banner_title_subtitle"):
            pipeline.run_phase_6_overlay(clients, "recX", **kwargs)
        return clients.airtable.update_record.call_args.args[1]

    def test_phase6_writes_done_and_the_timestamp_when_it_is_the_last_phase(self):
        saved = self._phase6()
        self.assertEqual(saved[pipeline.FIELD_STATUS], "Done")
        self.assertIn(pipeline.FIELD_DATE_GENERATED, saved)

    def test_phase6_in_a_banner_set_does_not_mark_the_row_done_before_the_sale_banner(self):
        saved = self._phase6(final=False)
        self.assertEqual(saved, {pipeline.FIELD_STATUS: pipeline.STATUS_CHRISTMAS_DONE})
        self.assertNotEqual(saved[pipeline.FIELD_STATUS], "Done")


class BannerOverlayTests(unittest.TestCase):
    """Geometry values come from the Canva reference sample (1800x600, orange background)."""

    W, H = 1800, 600
    BG = (255, 145, 77)

    def _base(self, w=None, h=None):
        return Image.new("RGB", (w or self.W, h or self.H), self.BG)

    @staticmethod
    def _white(image):
        arr = np.array(image.convert("RGB")).astype(int)
        return (arr > 245).all(axis=2)

    @staticmethod
    def _bbox(mask, rows):
        sub = mask[rows[0]:rows[1] + 1]
        cols = np.where(sub.any(axis=0))[0]
        ys = np.where(sub.any(axis=1))[0]
        return cols.min(), cols.max(), rows[0] + ys.max()

    def test_matches_reference_sample_geometry(self):
        out = overlay_banner_title_subtitle(self._base(), "Auto Generated Title", "Auto Generated Subtitle")
        white = self._white(out)
        t_left, t_right, t_base = self._bbox(white, (350, 447))
        s_left, s_right, s_base = self._bbox(white, (466, 530))
        # reference: title x 65-988, baseline 443; subtitle x 63-666, baseline 515
        self.assertAlmostEqual(t_left, 65, delta=4)
        self.assertAlmostEqual(t_right, 988, delta=14)
        self.assertAlmostEqual(t_base, 443, delta=3)
        self.assertAlmostEqual(s_left, 63, delta=4)
        self.assertAlmostEqual(s_right, 666, delta=14)
        self.assertAlmostEqual(s_base, 515, delta=3)

    def test_title_uses_medium_weight_not_bold(self):
        out = overlay_banner_title_subtitle(self._base(), "Auto Generated Title", "", shadow_intensity=0)
        row = self._white(out)[415]
        runs, count = [], 0
        for value in row:
            if value:
                count += 1
            elif count:
                runs.append(count)
                count = 0
        # reference stems are 11-12 px; Poppins Bold would be 18-19 px
        self.assertLessEqual(int(np.median(runs)), 14)

    def test_shadow_darkens_pixels_below_text_for_title_and_subtitle(self):
        base = self._base()
        with_shadow = np.array(overlay_banner_title_subtitle(base, "Auto Generated Title", "Auto Generated Subtitle")).astype(int)
        flat = np.array(overlay_banner_title_subtitle(
            base, "Auto Generated Title", "Auto Generated Subtitle", shadow_intensity=0)).astype(int)
        for rows in ((446, 466), (517, 530)):  # just below the title / subtitle baselines
            shadowed = with_shadow[rows[0]:rows[1], 100:600, 0].mean()
            plain = flat[rows[0]:rows[1], 100:600, 0].mean()
            self.assertLess(shadowed, plain - 3)

    def test_flat_render_is_white_on_background_only(self):
        out = np.array(overlay_banner_title_subtitle(
            self._base(), "Auto Generated Title", "Auto Generated Subtitle", shadow_intensity=0)).astype(int)
        # nothing darker than the background appears without a shadow
        self.assertGreaterEqual(int(out[:, :, 1].min()), self.BG[1] - 2)
        self.assertGreaterEqual(int(out[:, :, 2].min()), self.BG[2] - 2)

    def test_21_9_banner_keeps_size_and_scales_position(self):
        base = self._base(2400, 1029)
        out = overlay_banner_title_subtitle(base, "Light Up Your Christmas", "Statement lighting", shadow_intensity=0)
        self.assertEqual(out.size, base.size)
        white = self._white(out)
        cols = np.where(white.any(axis=0))[0]
        # x scales by 2400/1800: the 65 px reference left edge lands near 87 px
        self.assertAlmostEqual(cols.min(), 65 * 2400 / 1800, delta=8)
        rows = np.where(white.any(axis=1))[0]
        # y scales by 1029/600: text sits around 57%-88% of the height
        self.assertGreater(rows.min(), 0.55 * 1029)
        self.assertLess(rows.max(), 0.90 * 1029)

    def test_long_title_shrinks_to_fit_box(self):
        base = self._base()
        out = overlay_banner_title_subtitle(base, "An Extremely Long Christmas Title Here", "", shadow_intensity=0)
        right = BANNER_TITLE_BOX.x + BANNER_TITLE_BOX.width
        cols = np.where(self._white(out).any(axis=0))[0]
        self.assertLessEqual(cols.max(), right + 4)

    def test_writes_jpeg_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "nested" / "out.jpg"
            result = overlay_banner_title_subtitle(self._base(), "Title", "Sub", dest)
            self.assertEqual(result, dest)
            self.assertTrue(dest.is_file())
            with Image.open(dest) as written:
                self.assertEqual(written.size, (self.W, self.H))


class BannerPromptInstructionTests(unittest.TestCase):
    FIXTURES = [
        {"code": "CH", "label": "Chandelier", "name": "Aegnor", "notes": "W120*L120*H300cm"},
        {"code": "PE", "label": "Pendant Light", "name": "Allein", "notes": ""},
        {"code": "FL", "label": "Floor Lamp", "name": "Azazel", "notes": ""},
        {"code": "TL", "label": "Table Lamp", "name": "Yareli", "notes": "W 25cm x H 48cm"},
        {"code": "WL", "label": "Wall Light", "name": "Joakimm", "notes": ""},
    ]

    def test_instruction_has_three_stages_and_seven_requirements(self):
        text = build_banner_multi_fixture_instruction(self.FIXTURES)
        for stage in ("STAGE A", "STAGE B", "STAGE C"):
            self.assertIn(stage, text)
        for number in range(1, 8):
            self.assertIn(f"\n{number}. ", text)
        self.assertIn("lower-left 60% of the width", text)
        self.assertIn("one paragraph per item", text.lower())

    def test_notes_appear_only_for_items_that_have_them(self):
        text = build_banner_multi_fixture_instruction(self.FIXTURES)
        self.assertIn("W120*L120*H300cm", text)
        self.assertIn("W 25cm x H 48cm", text)
        self.assertEqual(text.count("Supplier notes"), 2)

    def test_mount_hints_are_facts_not_locations(self):
        from content_automation.prompts import BANNER_MOUNT_HINTS

        self.assertEqual(set(BANNER_MOUNT_HINTS), {"CH", "PE", "FL", "TL", "WL", "DP", "KA", "KB", "BA", "BB"})
        for code in ("DP", "KA", "KB"):  # the Sale banner's pendants hang like the Christmas banner's PE
            self.assertEqual(BANNER_MOUNT_HINTS[code], BANNER_MOUNT_HINTS["PE"])
        for code in ("BA", "BB"):  # the third banner's bedside lamps sit like the Christmas banner's table lamp
            self.assertEqual(BANNER_MOUNT_HINTS[code], BANNER_MOUNT_HINTS["TL"])
        for hint in BANNER_MOUNT_HINTS.values():
            self.assertNotIn("sofa", hint)
            self.assertNotIn("coffee table", hint)


class BannerItemNotesTests(unittest.TestCase):
    def test_clean_item_notes_strips_html_and_keeps_dimensions(self):
        raw = "<ul><li>Measurement: W 25cm x H 48cm</li><li>Wattage: 4W &amp; dimmable</li></ul>"
        notes = pipeline.clean_item_notes(raw)
        self.assertNotIn("<", notes)
        self.assertIn("W 25cm x H 48cm", notes)
        self.assertIn("4W & dimmable", notes)

    def test_clean_item_notes_caps_length_on_a_word_boundary(self):
        notes = pipeline.clean_item_notes("<p>" + "word " * 200 + "</p>")
        self.assertLessEqual(len(notes), pipeline.NOTES_MAX_CHARS + 3)
        self.assertTrue(notes.endswith("..."))

    def test_product_notes_uses_first_non_empty_description(self):
        product = {"values": {"description": [{"data": "<p> </p>"}, {"data": "<p>Material: Fabric</p>"}]}}
        self.assertEqual(pipeline._product_notes(product), "Material: Fabric")
        self.assertEqual(pipeline._product_notes({"values": {}}), "")

    def test_fixtures_from_record_carry_notes(self):
        fields = {
            pipeline.FIELD_ITEM_NAME: "CH: Aarhus\nTL: Yareli",
            pipeline.FIELD_ITEM_DETAILS: "TL: W 25cm x H 48cm",
            pipeline.FIELD_FURNITURE: [
                {"filename": "CH_s1_m.png", "url": "u-ch"},
                {"filename": "TL_s4_m.png", "url": "u-tl"},
            ],
        }
        items = {i["code"]: i for i in pipeline._banner_fixtures_from_record(fields)}
        self.assertEqual(items["CH"]["notes"], "")
        self.assertEqual(items["TL"]["notes"], "W 25cm x H 48cm")

    def test_item_details_column_is_provisioned(self):
        self.assertIn("Item Details", pipeline.REQUIRED_FIELDS)


class BlendPromptValidationTests(unittest.TestCase):
    GOOD = "Image 2 Image 3 Image 4 Image 5 Image 6 " * 40

    def test_accepts_a_long_prompt_naming_every_image(self):
        self.assertEqual(pipeline.validate_blend_prompt(self.GOOD, 5), (True, ""))

    def test_rejects_short_missing_image_fenced_and_preamble(self):
        ok, reason = pipeline.validate_blend_prompt("Image 2 Image 3", 5)
        self.assertFalse(ok)
        self.assertIn("characters", reason)
        ok, reason = pipeline.validate_blend_prompt(("Image 2 Image 3 Image 4 Image 5 " * 60), 5)
        self.assertFalse(ok)
        self.assertIn("Image 6", reason)
        self.assertFalse(pipeline.validate_blend_prompt("```\n" + self.GOOD + "\n```", 5)[0])
        self.assertFalse(pipeline.validate_blend_prompt("Here is the prompt: " + self.GOOD, 5)[0])

    def _clients(self):
        from unittest.mock import MagicMock

        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": {
            pipeline.FIELD_INTERIOR: [{"url": "u-room", "filename": "room.jpg"}],
            pipeline.FIELD_ITEM_NAME: "CH: A\nPE: B\nFL: C\nTL: D\nWL: E",
            pipeline.FIELD_FURNITURE: [
                {"filename": f"{code}_s_m.png", "url": f"u-{code}"} for code in ("CH", "PE", "FL", "TL", "WL")
            ],
        }}
        return clients

    def test_phase3_retries_once_with_the_reason_then_saves_the_good_prompt(self):
        clients = self._clients()
        clients.fal.generate_claude_vision.side_effect = ["too short", self.GOOD]
        saved = pipeline.run_phase_3_claude(clients, "recX")
        self.assertEqual(saved, self.GOOD.strip())
        self.assertEqual(clients.fal.generate_claude_vision.call_count, 2)
        second_prompt = clients.fal.generate_claude_vision.call_args_list[1].kwargs["prompt"]
        self.assertIn("previous answer was rejected", second_prompt)
        sent = clients.fal.generate_claude_vision.call_args_list[0].kwargs["image_urls"]
        self.assertEqual(sent, ["u-room", "u-CH", "u-PE", "u-FL", "u-TL", "u-WL"])
        fields = clients.airtable.update_record.call_args.args[1]
        self.assertEqual(fields[pipeline.FIELD_BLEND_PROMPT], self.GOOD.strip())

    def test_phase3_falls_back_after_two_bad_answers(self):
        clients = self._clients()
        clients.fal.generate_claude_vision.side_effect = ["nope", "still nope"]
        saved = pipeline.run_phase_3_claude(clients, "recX")
        self.assertTrue(saved.startswith("Install all 5 lighting fixtures"))


class FromPhaseTests(unittest.TestCase):
    def _run(self, **kwargs):
        from unittest.mock import MagicMock

        names = ("run_phase_1_scrape", "run_phase_2_interior", "run_phase_3_claude",
                 "run_phase_4_blend", "run_phase_5_copy", "run_phase_6_overlay")
        mocks = {n: MagicMock(return_value="recNEW" if n == "run_phase_1_scrape" else None) for n in names}
        with patch.object(pipeline, "PipelineClients"), \
                patch.multiple(pipeline, **mocks):
            pipeline.run_pipeline(**kwargs)
        return {n: m.called for n, m in mocks.items()}

    def test_default_runs_scrape_and_all_phases(self):
        called = self._run()
        self.assertTrue(all(called.values()))

    def test_from_phase_3_skips_scrape_and_krea(self):
        called = self._run(record_id="recX", from_phase=3)
        self.assertFalse(called["run_phase_1_scrape"])
        self.assertFalse(called["run_phase_2_interior"])
        for name in ("run_phase_3_claude", "run_phase_4_blend", "run_phase_5_copy", "run_phase_6_overlay"):
            self.assertTrue(called[name], name)

    def test_text_only_is_from_phase_5(self):
        called = self._run(record_id="recX", text_only=True)
        self.assertEqual([n for n, v in called.items() if v], ["run_phase_5_copy", "run_phase_6_overlay"])

    def test_only_phase_4_runs_just_the_banner_blend(self):
        called = self._run(record_id="recX", only_phase=4)
        self.assertEqual([n for n, v in called.items() if v], ["run_phase_4_blend"])

    def test_only_phase_6_runs_just_the_overlay(self):
        called = self._run(record_id="recX", only_phase=6)
        self.assertEqual([n for n, v in called.items() if v], ["run_phase_6_overlay"])

    def test_only_phase_needs_a_record_and_cannot_be_mixed(self):
        with self.assertRaises(pipeline.AutomationError):
            pipeline.run_pipeline(only_phase=4)
        with self.assertRaises(pipeline.AutomationError):
            pipeline.run_pipeline(record_id="recX", only_phase=4, text_only=True)
        with self.assertRaises(pipeline.AutomationError):
            pipeline.run_pipeline(record_id="recX", only_phase=4, from_phase=3)
        with self.assertRaises(pipeline.AutomationError):
            pipeline.run_pipeline(record_id="recX", only_phase=1)

    def test_from_phase_needs_a_record_and_a_valid_number(self):
        with self.assertRaises(pipeline.AutomationError):
            pipeline.run_pipeline(from_phase=3)
        with self.assertRaises(pipeline.AutomationError):
            pipeline.run_pipeline(record_id="recX", from_phase=9)


class ChristmasBannerRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        routes_dir = REPO_ROOT / "UI Control"
        if str(routes_dir) not in sys.path:
            sys.path.insert(0, str(routes_dir))
        self.common = importlib.import_module("routes.common")
        self.marketing_patch = patch.object(self.common, "MARKETING_DIR", self.workspace)
        self.overrides_patch = patch.object(
            self.common, "OVERRIDES_FILE", self.workspace / "output" / "config_overrides.json"
        )
        self.marketing_patch.start()
        self.overrides_patch.start()
        (self.workspace / ".env").write_text("", encoding="utf-8")

        self.module = importlib.import_module("routes.christmas_banner")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.christmas_banner_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()

    def test_fixtures_lists_single_banner_fixture_with_default_moodboard(self):
        response = self.client.get("/api/christmas-banner/fixtures")
        self.assertEqual(response.status_code, 200)
        fixtures = response.get_json()["fixtures"]
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["id"], "christmas_banner")
        self.assertEqual(fixtures[0]["moodboard_id"], "b5ffdcbb-192e-4528-8d86-d1a4cf496887")
        self.assertIn("Christmas", fixtures[0]["prompt"])

    def test_counts_reports_status_breakdown(self):
        with patch.dict(os.environ, {self.module.TABLE_ENV_KEY: "tblBanner"}), patch(
            "content_automation.airtable_client.fetch_status_breakdown",
            return_value={"P": 1, "S": 0, "C": 5, "D": 0, "FM": 0},
        ):
            response = self.client.get("/api/christmas-banner/counts?refresh=true")
        data = response.get_json()["counts"]["christmas_banner"]
        self.assertEqual(data["completed"], 5)
        self.assertEqual(data["table_id"], "tblBanner")

    def test_fixture_defaults_to_banner_table_and_fifteen_phases(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(self.module.TABLE_ENV_KEY, None)
            fixture = self.client.get("/api/christmas-banner/fixtures").get_json()["fixtures"][0]
        self.assertEqual(fixture["table_id"], "tblgNk1Tp6qKUcduw")
        # One Studio run = the Banner Set: 1 scrape + 5 Christmas + 5 Sale + 4 third-banner phases
        self.assertEqual(self.module.TOTAL_PHASES, 15)
        self.assertEqual(sorted(self.module.PHASE_LABELS), list(range(1, 16)))

    def test_stop_without_active_run_is_400(self):
        with patch.object(self.module, "is_authorized", return_value=True):
            response = self.client.post("/api/christmas-banner/stop")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
