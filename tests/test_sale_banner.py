"""Tests for the Sale banner: calendar captions, layout renderer, shared helpers and pipeline phases."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation import banner_common as common
from content_automation import overlay
from content_automation import promo_calendar as promo
from content_automation.errors import AutomationError, ProviderError
from content_automation.prompts import build_banner_multi_fixture_instruction
import generate_sale_banner_pipeline as pipeline


class PromoCalendarTests(unittest.TestCase):
    def test_default_month_is_this_month_until_day_24_then_next(self):
        self.assertEqual(promo.campaign_month(date(2026, 10, 10)), (10, 2026))
        self.assertEqual(promo.campaign_month(date(2026, 10, 23)), (10, 2026))
        self.assertEqual(promo.campaign_month(date(2026, 9, 30)), (10, 2026))
        self.assertEqual(promo.campaign_month(date(2026, 12, 24)), (1, 2027))

    def test_explicit_month_and_year_win(self):
        self.assertEqual(promo.campaign_month(date(2026, 9, 30), month=11, year=2026), (11, 2026))
        self.assertEqual(promo.campaign_month(date(2026, 9, 30), month=3), (3, 2026))
        with self.assertRaises(AutomationError):
            promo.campaign_month(month=13)

    def test_whole_month_captions_from_the_real_calendar(self):
        captions = promo.build_sale_captions(today=date(2026, 9, 30))
        self.assertEqual([c.percent for c in captions], [10, 15])
        self.assertEqual(captions[0].caption, "On all items from curated monthly collection on October 1-31, 2026")
        self.assertEqual(captions[1].caption, "On all items from a curated collection on October 1-31, 2026")
        self.assertEqual(captions[0].date_text, "October 1-31, 2026")

    def test_window_formats_include_the_year(self):
        self.assertEqual(promo.format_window(date(2026, 10, 1), date(2026, 10, 31)), "October 1-31, 2026")
        self.assertEqual(promo.format_window(date(2026, 10, 25), date(2026, 11, 30)), "October 25 - November 30, 2026")
        self.assertEqual(promo.format_window(date(2026, 12, 12), date(2026, 12, 12)), "December 12, 2026")
        self.assertEqual(
            promo.format_window(date(2026, 12, 25), date(2027, 1, 5)), "December 25, 2026 - January 5, 2027"
        )

    def test_next_year_captions_use_the_next_year(self):
        captions = promo.build_sale_captions(month=1, year=2027)
        self.assertTrue(captions[0].caption.endswith("on January 1-31, 2027"))

    def test_event_windows(self):
        whole = {"key": "x", "whole_month": True}
        self.assertEqual(promo.event_window(whole, 2, 2028), (date(2028, 2, 1), date(2028, 2, 29)))
        ranged = {"key": "y", "start_md": "10-25", "end_md": "11-30"}
        self.assertEqual(promo.event_window(ranged, 10, 2026), (date(2026, 10, 25), date(2026, 11, 30)))
        new_year = {"key": "z", "start_md": "12-20", "end_md": "01-05"}
        self.assertEqual(promo.event_window(new_year, 12, 2026), (date(2026, 12, 20), date(2027, 1, 5)))
        with self.assertRaises(AutomationError):
            promo.event_window({"key": "bad"}, 1, 2026)

    def test_percent_and_event_lookup_errors(self):
        self.assertEqual(promo.percent_of_event({"name": "15% OFF (Ceiling)"}), 15)
        with self.assertRaises(AutomationError):
            promo.percent_of_event({"name": "Monthly Promotion"})
        with self.assertRaises(AutomationError):
            promo.find_event({"events": []}, "ten_off_monthly")

    def test_calendar_is_read_from_a_custom_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cal.json"
            path.write_text(
                '{"events": [{"key": "ten_off_monthly", "name": "10% OFF", "whole_month": true},'
                ' {"key": "fifteen_off_monthly", "name": "20% OFF", "start_md": "11-01", "end_md": "11-05"}]}',
                encoding="utf-8",
            )
            captions = promo.build_sale_captions(promo.load_calendar(path), month=11, year=2026)
        self.assertEqual([c.percent for c in captions], [10, 20])
        self.assertEqual(captions[1].date_text, "November 1-5, 2026")
        with self.assertRaises(AutomationError):
            promo.load_calendar(Path(tmp) / "missing.json")


class SaleOverlayTests(unittest.TestCase):
    """Reference geometry measured on the Canva sample (1800x600)."""

    @staticmethod
    def _photo(colour):
        return Image.new("RGB", (483, 600), colour)

    @staticmethod
    def _white(image):
        return (np.array(image.convert("RGB")).astype(int) > 245).all(axis=2)

    @staticmethod
    def _bbox(mask, rows, cols):
        sub = mask[rows[0]:rows[1], cols[0]:cols[1]]
        xs = np.where(sub.any(axis=0))[0]
        ys = np.where(sub.any(axis=1))[0]
        return cols[0] + xs.min(), cols[0] + xs.max(), rows[0] + ys.min(), rows[0] + ys.max()

    def _render(self, **kwargs):
        return overlay.draw_sale_banner(self._photo((10, 160, 10)), self._photo((230, 200, 20)), **kwargs)

    # The text sizes the reference sample was fitted with (px); the current design uses the Canva pt values.
    SAMPLE_STYLES = {
        "SALE_HEADLINE_STYLE": overlay.SaleTextStyle("Poppins-Medium.ttf", 80.86),
        "SALE_WORD_STYLE": overlay.SaleTextStyle("Poppins-Medium.ttf", 221.18),
        "SALE_NUMBER_STYLE": overlay.SaleTextStyle("Poppins-Medium.ttf", 148.86, -0.17),  # X glyphs overlap
        "SALE_UPTO_STYLE": overlay.SaleTextStyle("Poppins-Regular.ttf", 35.0),
        "SALE_PERCENT_STYLE": overlay.SaleTextStyle("Poppins-Regular.ttf", 66.33),
        "SALE_OFF_STYLE": overlay.SaleTextStyle("Poppins-Regular.ttf", 67.14),
    }

    def test_canvas_slots_and_panel(self):
        image = self._render()
        self.assertEqual(image.size, (1800, 600))
        arr = np.array(image)
        self.assertEqual(tuple(arr[300, 100]), (10, 160, 10))  # left photo
        self.assertEqual(tuple(arr[300, 1700]), (230, 200, 20))  # right photo
        self.assertEqual(tuple(arr[5, 700]), (255, 49, 49))  # red panel, clear of text
        self.assertEqual(tuple(arr[595, 1200]), (255, 49, 49))
        # the two panel edge columns are a 50% mix of panel and photo, like the sample
        self.assertEqual(tuple(arr[300, 482]), ((10 + 255) // 2, (160 + 49) // 2, (10 + 49) // 2))
        self.assertEqual(tuple(arr[300, 1317])[0], (230 + 255) // 2)

    def test_headline_and_sale_word_match_the_sample(self):
        with patch.multiple(overlay, **self.SAMPLE_STYLES):
            white = self._white(self._render(percent_left="XX", percent_right="XX"))
        h_left, h_right, h_top, h_bottom = self._bbox(white, (48, 126), (575, 1245))
        self.assertAlmostEqual(h_left, 589, delta=3)
        self.assertAlmostEqual(h_right, 1230, delta=4)
        self.assertAlmostEqual(h_bottom, 117, delta=2)
        s_left, s_right, s_top, s_bottom = self._bbox(white, (135, 310), (685, 1115))
        self.assertAlmostEqual(s_left, 693, delta=3)
        self.assertAlmostEqual(s_right, 1108, delta=4)
        self.assertAlmostEqual(s_top, 144, delta=3)
        self.assertAlmostEqual(s_bottom, 301, delta=3)

    def test_left_percent_block_matches_the_sample_with_xx(self):
        # The sample's "XX" was fitted at -0.17 em (the X glyphs overlap); real digits use the shared -0.09.
        with patch.multiple(overlay, **self.SAMPLE_STYLES):
            white = self._white(self._render(percent_left="XX", percent_right="XX"))
        left, right, top, bottom = self._bbox(white, (318, 500), (555, 870))
        self.assertAlmostEqual(left, 565, delta=3)  # UP TO
        self.assertAlmostEqual(right, 855, delta=3)  # OFF
        self.assertAlmostEqual(top, 326, delta=3)
        self.assertAlmostEqual(bottom, 492, delta=2)  # the number's baseline

    def test_font_sizes_are_the_canva_point_values(self):
        px = 4.0 / 3.0
        self.assertAlmostEqual(overlay.SALE_HEADLINE_STYLE.size, 60.9 * px)
        self.assertAlmostEqual(overlay.SALE_WORD_STYLE.size, 168 * px)
        self.assertAlmostEqual(overlay.SALE_NUMBER_STYLE.size, 141 * px)
        self.assertAlmostEqual(overlay.SALE_UPTO_STYLE.size, 26.7 * px)
        self.assertAlmostEqual(overlay.SALE_PERCENT_STYLE.size, 50.5 * px)
        self.assertAlmostEqual(overlay.SALE_OFF_STYLE.size, 51.3 * px)
        self.assertEqual(overlay.SALE_PERCENT_STYLE.font_file, "Poppins-Regular.ttf")
        self.assertEqual(overlay.SALE_OFF_STYLE.font_file, "Poppins-Regular.ttf")
        self.assertEqual(overlay.SALE_HEADLINE_STYLE.font_file, "Poppins-Medium.ttf")
        self.assertEqual(overlay.SALE_UPTO_STYLE.font_file, "Poppins-Regular.ttf")

    def test_headline_and_sale_word_keep_their_ink_centres_at_the_canva_sizes(self):
        white = self._white(self._render(percent_left=10, percent_right=15))
        h_left, h_right, _, h_bottom = self._bbox(white, (40, 126), (560, 1260))
        self.assertAlmostEqual((h_left + h_right) / 2, overlay.SALE_HEADLINE_INK_CENTER, delta=3)
        self.assertAlmostEqual(h_bottom, overlay.SALE_HEADLINE_BASELINE, delta=2)
        s_left, s_right, s_top, s_bottom = self._bbox(white, (128, 310), (660, 1140))
        self.assertAlmostEqual((s_left + s_right) / 2, overlay.SALE_WORD_INK_CENTER, delta=3)
        self.assertAlmostEqual(s_bottom, overlay.SALE_WORD_BASELINE + 2, delta=3)
        # SALE is 168 pt = 224 px: cap height about 0.7 em
        self.assertAlmostEqual(s_bottom - s_top, 0.7 * 224, delta=8)
        # ink widths scale with the size versus the sample fit (641 px headline, 415 px SALE)
        self.assertAlmostEqual(h_right - h_left, 641 * (60.9 * 4 / 3) / 80.86, delta=6)
        self.assertAlmostEqual(s_right - s_left, 415 * 224 / 221.18, delta=6)

    def test_big_number_is_141_pt_and_blocks_stay_inside_the_panel(self):
        for left_value, right_value in ((10, 15), (88, 88)):
            white = self._white(self._render(percent_left=left_value, percent_right=right_value))
            l_left, l_right, _, _ = self._bbox(white, (318, 500), (500, 895))
            r_left, r_right, _, _ = self._bbox(white, (318, 500), (905, 1310))
            self.assertGreater(l_left, overlay.SALE_PANEL_X[0] + 20)
            self.assertLess(r_right, overlay.SALE_PANEL_X[1] - 20)
            self.assertGreater(r_left - l_right, 30)  # the two blocks never touch
        # the number's cap height is about 0.7 em of 188 px
        number = self._bbox(self._white(self._render(percent_left=10, percent_right=15)), (330, 500), (610, 735))
        self.assertAlmostEqual(number[3] - number[2], 0.7 * 141 * 4 / 3, delta=8)
        self.assertAlmostEqual(number[3], overlay.SALE_NUMBER_BASELINE - 1, delta=3)

    def test_two_digit_numbers_stay_centred_on_their_slots(self):
        white = self._white(self._render(percent_left=10, percent_right=15))
        l_left, l_right, *_ = self._bbox(white, (318, 500), (540, 890))
        r_left, r_right, *_ = self._bbox(white, (318, 500), (920, 1275))
        self.assertAlmostEqual((l_left + l_right) / 2, overlay.SALE_BLOCK_CENTERS[0], delta=4)
        self.assertAlmostEqual((r_left + r_right) / 2, overlay.SALE_BLOCK_CENTERS[1], delta=4)
        # both blocks share one geometry, so the right block is the left one shifted sideways
        self.assertAlmostEqual(
            (r_right - r_left), (l_right - l_left), delta=8
        )

    def test_captions_wrap_like_the_sample_and_sit_under_their_blocks(self):
        self.assertEqual(
            overlay.wrap_sale_caption("On all items from curated monthly collection on October 1-31, 2026"),
            ["On all items from curated monthly", "collection on October 1-31, 2026"],
        )
        self.assertEqual(
            overlay.wrap_sale_caption("On all items from a curated collection on October 1-31, 2026"),
            ["On all items from a curated collection", "on October 1-31, 2026"],
        )
        white = self._white(self._render(
            caption_left="On all items from curated monthly collection on October 1-31, 2026",
            caption_right="On all items from a curated collection on October 1-31, 2026",
        ))
        # tiny thin text: use any ink above 200 in the raw image instead of the strict-white mask
        arr = np.array(self._render(
            caption_left="On all items from curated monthly collection on October 1-31, 2026",
            caption_right="On all items from a curated collection on October 1-31, 2026",
        )).astype(int)
        ink = arr[:, :, 1] > 120
        l = np.where(ink[518:566, 560:850].any(axis=0))[0]
        r = np.where(ink[518:566, 930:1245].any(axis=0))[0]
        self.assertAlmostEqual(560 + (l.min() + l.max()) / 2, overlay.SALE_CAPTION_CENTERS[0], delta=8)
        self.assertAlmostEqual(930 + (r.min() + r.max()) / 2, overlay.SALE_CAPTION_CENTERS[1], delta=8)
        self.assertIsNotNone(white)

    def test_panel_colour_is_configurable_and_defaults_to_the_sample_red(self):
        for given, expected in (((11, 61, 46), (11, 61, 46)), ("#0B3D2E", (11, 61, 46)), (None, (255, 49, 49)),
                                ("not a colour", (255, 49, 49))):
            arr = np.array(self._render(panel_color=given))
            self.assertEqual(tuple(arr[5, 700]), expected, given)
            self.assertEqual(tuple(arr[595, 1200]), expected, given)
            # edge columns are still a 50% mix of the panel and the photo
            mixed = (np.array(expected) + np.array((10, 160, 10))) / 2.0
            self.assertTrue((np.abs(arr[300, 482].astype(float) - mixed) <= 1.0).all(), given)
            self.assertEqual(tuple(arr[300, 100]), (10, 160, 10))

    def test_long_caption_wraps_to_at_most_three_lines(self):
        lines = overlay.wrap_sale_caption("On all items from curated monthly collection on October 25 - November 30 " * 3)
        self.assertLessEqual(len(lines), 3)

    def test_writes_a_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "nested" / "sale.jpg"
            result = self._render(destination=dest)
            self.assertEqual(result, dest)
            with Image.open(dest) as written:
                self.assertEqual(written.size, (1800, 600))


class PanelColourHelperTests(unittest.TestCase):
    def test_parse_hex_color(self):
        self.assertEqual(overlay.parse_hex_color("#B3122A"), (179, 18, 42))
        self.assertEqual(overlay.parse_hex_color("#b3122a"), (179, 18, 42))
        self.assertEqual(overlay.parse_hex_color("#F0A"), (255, 0, 170))
        self.assertEqual(overlay.parse_hex_color("B3122A"), (179, 18, 42))
        self.assertEqual(overlay.parse_hex_color("Use #0B3D2E, a deep green (not #FFFFFF)."), (11, 61, 46))
        for bad in ("", None, "red", "#GG0000", "#12345", "decade of light", "#1234567"):
            self.assertIsNone(overlay.parse_hex_color(bad), bad)

    def test_format_hex_color(self):
        self.assertEqual(overlay.format_hex_color((179, 18, 42)), "#B3122A")

    def test_contrast_with_white(self):
        self.assertAlmostEqual(overlay.contrast_with_white((255, 255, 255)), 1.0, places=2)
        self.assertAlmostEqual(overlay.contrast_with_white((0, 0, 0)), 21.0, places=1)
        self.assertLess(overlay.contrast_with_white(overlay.SALE_PANEL_COLOR), 4.5)  # the sample red is lighter

    def test_ensure_white_text_contrast_darkens_only_when_needed(self):
        good = (11, 61, 46)
        self.assertEqual(overlay.ensure_white_text_contrast(good), good)
        light = (245, 245, 245)
        fixed = overlay.ensure_white_text_contrast(light)
        self.assertGreaterEqual(overlay.contrast_with_white(fixed), overlay.SALE_PANEL_MIN_CONTRAST)
        self.assertTrue(all(f <= l for f, l in zip(fixed, light)))
        # hue is kept: a light red stays red-dominant
        red = overlay.ensure_white_text_contrast((255, 120, 120))
        self.assertGreaterEqual(overlay.contrast_with_white(red), overlay.SALE_PANEL_MIN_CONTRAST)
        self.assertGreater(red[0], red[1])


class SharedHelperTests(unittest.TestCase):
    def test_phases_to_run(self):
        self.assertEqual(common.phases_to_run(has_record=False), [2, 3, 4, 5, 6])
        self.assertEqual(common.phases_to_run(from_phase=4, has_record=True), [4, 5, 6])
        self.assertEqual(common.phases_to_run(text_only=True, has_record=True), [5, 6])
        self.assertEqual(common.phases_to_run(only_phase=4, has_record=True), [4])

    def test_phases_to_run_rejects_bad_combinations(self):
        for kwargs in (
            {"from_phase": 3, "has_record": False},
            {"text_only": True, "has_record": False},
            {"only_phase": 4, "has_record": False},
            {"only_phase": 4, "text_only": True, "has_record": True},
            {"only_phase": 4, "from_phase": 3, "has_record": True},
            {"only_phase": 9, "has_record": True},
            {"from_phase": 9, "has_record": True},
        ):
            with self.assertRaises(AutomationError, msg=str(kwargs)):
                common.phases_to_run(**kwargs)

    def test_fixtures_from_record_orders_by_slot_and_reads_notes(self):
        defs = [
            {"code": "PE", "label": "Pendant Light"},
            {"code": "TA", "label": "Table Lamp"},
            {"code": "TB", "label": "Table Lamp"},
        ]
        fields = {
            "Item Name": "PE: Allein\nTA: Yareli\nTB: Yarelo",
            "Item Details": "TA: W 25cm x H 48cm",
            "Furniture Item": [
                {"filename": "TB_s3_m.png", "url": "u-tb"},
                {"filename": "PE_s1_m.png", "url": "u-pe"},
                {"filename": "CH_s9_m.png", "url": "u-ch"},
                {"filename": "TA_s2_m.png", "url": "u-ta"},
            ],
        }
        items = common.fixtures_from_record(fields, defs)
        self.assertEqual([i["code"] for i in items], ["PE", "TA", "TB"])
        self.assertEqual([i["name"] for i in items], ["Allein", "Yareli", "Yarelo"])
        self.assertEqual(items[1]["notes"], "W 25cm x H 48cm")
        self.assertEqual(items[0]["notes"], "")

    def test_validate_blend_prompt_accepts_a_shorter_minimum(self):
        text = "Image 2 and Image 3 " * 45  # 900 characters
        self.assertFalse(common.validate_blend_prompt(text, 2)[0])
        self.assertTrue(common.validate_blend_prompt(text, 2, min_chars=700)[0])

    def test_krea_helper_retries_non_moodboard_errors_only(self):
        clients = MagicMock()
        clients.krea.generate.side_effect = [ProviderError("failed (422): invalid aspect_ratio"), "https://x/y.jpg"]
        url = common.krea_generate_room(
            clients, prompt="p", moodboard_id="mb-1", aspect_ratio="4:5", fallback_aspect_ratio="3:4"
        )
        self.assertEqual(url, "https://x/y.jpg")
        self.assertEqual([c.kwargs["aspect_ratio"] for c in clients.krea.generate.call_args_list], ["4:5", "3:4"])
        clients = MagicMock()
        clients.krea.generate.side_effect = ProviderError("Moodboard Not Found: Krea moodboard 'mb-1' was not found")
        with self.assertRaises(ProviderError):
            common.krea_generate_room(clients, prompt="p", moodboard_id="mb-1", aspect_ratio="4:5")
        self.assertEqual(clients.krea.generate.call_count, 1)


def _fields_with_rooms():
    return {
        "Item Name": "PE: Allein\nTA: Yareli\nTB: Yarelo",
        pipeline.FIELD_FURNITURE: [
            {"filename": "PE_s1_m.png", "url": "u-pe"},
            {"filename": "TA_s2_m.png", "url": "u-ta"},
            {"filename": "TB_s3_m.png", "url": "u-tb"},
        ],
        pipeline.FIELD_DINING_INTERIOR: [{"url": "u-dining", "filename": "d.jpg"}],
        pipeline.FIELD_BEDROOM_INTERIOR: [{"url": "u-bedroom", "filename": "b.jpg"}],
        pipeline.FIELD_DINING_PROMPT: "dining prompt",
        pipeline.FIELD_BEDROOM_PROMPT: "bedroom prompt",
    }


class SalePipelinePhaseTests(unittest.TestCase):
    def test_slots_are_one_pendant_and_two_table_lamps(self):
        self.assertEqual([s["code"] for s in pipeline.SLOTS], ["PE", "TA", "TB"])
        self.assertEqual([s["category"] for s in pipeline.SLOTS], ["pendant_lights", "table_lamps", "table_lamps"])
        self.assertEqual(pipeline.ROOM_ASPECT_RATIO, "4:5")

    def test_table_defaults_to_the_shared_banner_table(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in pipeline.TABLE_ENV_KEYS:
                os.environ.pop(key, None)
            self.assertEqual(pipeline.resolve_table_id(None), "tblgNk1Tp6qKUcduw")
        with patch.dict(os.environ, {"AIRTABLE_TABLE_ID_CHRISTMAS_BANNER": "tblChristmas"}):
            os.environ.pop("AIRTABLE_TABLE_ID_SALE_BANNER", None)
            self.assertEqual(pipeline.resolve_table_id(None), "tblChristmas")
        with patch.dict(os.environ, {"AIRTABLE_TABLE_ID_SALE_BANNER": "tblSale"}):
            self.assertEqual(pipeline.resolve_table_id(None), "tblSale")
        self.assertEqual(pipeline.resolve_table_id("tblX"), "tblX")

    def test_required_fields_cover_every_field_written(self):
        for name in (pipeline.FIELD_STATUS, pipeline.FIELD_FK_ID, pipeline.FIELD_DATE_GENERATED,
                     pipeline.FIELD_DINING_BLENDED, pipeline.FIELD_BEDROOM_BLENDED, pipeline.FIELD_SALE_BANNER,
                     pipeline.FIELD_CAPTION_LEFT, pipeline.FIELD_PERCENT_RIGHT, pipeline.FIELD_PANEL_COLOR):
            self.assertIn(name, pipeline.REQUIRED_FIELDS)
        self.assertNotIn("ID", pipeline.REQUIRED_FIELDS)

    def test_phase1_picks_three_distinct_items_and_creates_one_sale_row(self):
        clients = MagicMock()
        clients.airtable.create_record.return_value = "recSALE"
        picks = iter(range(3))

        def fake_pick(_clients, slot, _style, base_skus, base_names, _shopify):
            n = next(picks)
            return {"code": slot["code"], "sku": f"SKU{n}", "clean_name": f"Name{n}", "media_code": "m.png",
                    "cutout": Path("c.png"), "notes": "W 25cm" if slot["code"] == "TA" else ""}

        with patch.object(pipeline, "load_scrape_context", return_value=(set(), set(), None)), \
                patch.object(pipeline, "pick_fixture", side_effect=fake_pick):
            record_id = pipeline.run_phase_1_scrape(clients)
        self.assertEqual(record_id, "recSALE")
        fields = clients.airtable.create_record.call_args.args[0]
        self.assertEqual(fields["Category"], "Sale Banner")
        self.assertEqual(fields["SKU"], "PE: SKU0\nTA: SKU1\nTB: SKU2")
        self.assertEqual(fields["Item Details"], "TA: W 25cm")
        self.assertNotIn("ID", fields)
        self.assertNotIn("Foreign Key ID", fields)
        self.assertEqual(clients.airtable.upload_attachment.call_count, 3)

    def test_phase1_stops_before_writing_when_an_item_is_missing(self):
        clients = MagicMock()
        with patch.object(pipeline, "load_scrape_context", return_value=(set(), set(), None)), \
                patch.object(pipeline, "pick_fixture", return_value=None):
            with self.assertRaises(AutomationError):
                pipeline.run_phase_1_scrape(clients)
        clients.airtable.create_record.assert_not_called()

    def test_phase1_second_lamp_is_not_the_first(self):
        clients = MagicMock()
        clients.airtable.create_record.return_value = "recSALE"
        seen: list[set] = []

        def fake_pick(_clients, slot, _style, base_skus, base_names, _shopify):
            seen.append(set(base_skus))
            n = len(seen)
            return {"code": slot["code"], "sku": f"SKU{n}", "clean_name": f"Name{n}", "media_code": "m.png",
                    "cutout": Path("c.png"), "notes": ""}

        with patch.object(pipeline, "load_scrape_context", return_value=(set(), set(), None)), \
                patch.object(pipeline, "pick_fixture", side_effect=fake_pick):
            pipeline.run_phase_1_scrape(clients)
        self.assertEqual(seen[1], {"sku1"})
        self.assertEqual(seen[2], {"sku1", "sku2"})

    def test_phase2_generates_both_rooms_at_4_5(self):
        clients = MagicMock()
        clients.krea.download_image.return_value = MagicMock(path="x.jpg")
        with patch.object(pipeline, "krea_generate_room", return_value="https://k/room.jpg") as krea:
            pipeline.run_phase_2_interiors(clients, "recX")
        self.assertEqual(krea.call_count, 2)
        ratios = {c.kwargs["aspect_ratio"] for c in krea.call_args_list}
        self.assertEqual(ratios, {"4:5"})
        moodboards = [c.kwargs["moodboard_id"] for c in krea.call_args_list]
        self.assertEqual(moodboards[0], pipeline.ROOMS[0]["moodboard_default"])
        self.assertEqual(moodboards[1], pipeline.ROOMS[1]["moodboard_default"])
        prompts = [c.kwargs["prompt"] for c in krea.call_args_list]
        self.assertIn("dining room", prompts[0])
        self.assertIn("bedroom", prompts[1])
        for prompt in prompts:
            self.assertIn("Christmas", prompt)
        saved = clients.airtable.update_record.call_args.args[1]
        self.assertEqual(saved[pipeline.FIELD_STATUS], "Interiors Generated")

    def test_phase2_uses_cli_overrides(self):
        clients = MagicMock()
        clients.krea.download_image.return_value = MagicMock(path="x.jpg")
        overrides = {"dining": {"moodboard": "mb-d", "prompt": "custom dining"}, "bedroom": {"moodboard": "", "prompt": ""}}
        with patch.object(pipeline, "krea_generate_room", return_value="https://k/room.jpg") as krea:
            pipeline.run_phase_2_interiors(clients, "recX", overrides=overrides)
        self.assertEqual(krea.call_args_list[0].kwargs["moodboard_id"], "mb-d")
        self.assertEqual(krea.call_args_list[0].kwargs["prompt"], "custom dining")

    def test_phase3_asks_claude_once_per_room_with_that_rooms_images(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": _fields_with_rooms()}
        good = "Image 2 Image 3 " * 60
        clients.fal.generate_claude_vision.side_effect = [good, good]
        prompts = pipeline.run_phase_3_claude(clients, "recX")
        self.assertEqual(set(prompts), {"dining", "bedroom"})
        calls = clients.fal.generate_claude_vision.call_args_list
        self.assertEqual(calls[0].kwargs["image_urls"], ["u-dining", "u-pe"])
        self.assertEqual(calls[1].kwargs["image_urls"], ["u-bedroom", "u-ta", "u-tb"])
        self.assertIn("dining room", calls[0].kwargs["prompt"])
        self.assertIn("bedroom", calls[1].kwargs["prompt"])
        self.assertIn("bedside tables", calls[1].kwargs["prompt"])
        for call in calls:
            self.assertNotIn("Composition reserve", call.kwargs["prompt"])  # nothing is drawn over the rooms
            self.assertIn("4:5", call.kwargs["prompt"])
        saved = clients.airtable.update_record.call_args.args[1]
        self.assertEqual(saved[pipeline.FIELD_DINING_PROMPT], good.strip())

    def test_phase3_falls_back_per_room_when_claude_fails(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": _fields_with_rooms()}
        clients.fal.generate_claude_vision.side_effect = RuntimeError("boom")
        prompts = pipeline.run_phase_3_claude(clients, "recX")
        self.assertIn("Pendant Light \"Allein\" (Image 2)", prompts["dining"])
        self.assertIn("(Image 3)", prompts["bedroom"])

    def test_phase3_needs_interiors_and_items(self):
        clients = MagicMock()
        fields = _fields_with_rooms()
        del fields[pipeline.FIELD_BEDROOM_INTERIOR]
        clients.airtable.get_record.return_value = {"fields": fields}
        with self.assertRaises(AutomationError):
            pipeline.run_phase_3_claude(clients, "recX")

    def test_phase4_blends_each_room_with_its_prompt_and_images(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": _fields_with_rooms()}
        with tempfile.TemporaryDirectory() as tmp, patch.object(pipeline, "OUTPUT_DIR", Path(tmp)):
            src = Path(tmp) / "src.jpg"
            Image.new("RGB", (40, 50), (1, 2, 3)).save(src)
            with patch.object(pipeline, "nano_banana_blend", return_value="https://f/blend.jpg") as blend, \
                    patch.object(pipeline, "download_url_to_temp_file", return_value=MagicMock(path=str(src))):
                saved = pipeline.run_phase_4_blend(clients, "recX")
            self.assertEqual([p.name for p in saved], ["dining_blend_recX.jpg", "bedroom_blend_recX.jpg"])
        calls = blend.call_args_list
        self.assertEqual(calls[0].kwargs["image_urls"], ["u-dining", "u-pe"])
        self.assertEqual(calls[1].kwargs["image_urls"], ["u-bedroom", "u-ta", "u-tb"])
        self.assertEqual([c.kwargs["prompt"] for c in calls], ["dining prompt", "bedroom prompt"])
        self.assertEqual({c.kwargs["aspect_ratio"] for c in calls}, {"4:5"})

    @staticmethod
    def _phase5_clients(reply="#B3122A", *, blends=True):
        clients = MagicMock()
        fields = {}
        if blends:
            fields = {pipeline.FIELD_DINING_BLENDED: [{"url": "u-dining-blend"}],
                      pipeline.FIELD_BEDROOM_BLENDED: [{"url": "u-bedroom-blend"}]}
        clients.airtable.get_record.return_value = {"fields": fields}
        if isinstance(reply, Exception):
            clients.fal.generate_claude_vision.side_effect = reply
        elif isinstance(reply, list):
            clients.fal.generate_claude_vision.side_effect = reply
        else:
            clients.fal.generate_claude_vision.return_value = reply
        return clients

    def test_phase5_writes_percents_captions_with_year_and_claudes_colour(self):
        clients = self._phase5_clients("#B3122A")
        captions = pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026)
        self.assertEqual(captions[0], "On all items from curated monthly collection on November 1-30, 2026")
        saved = clients.airtable.update_record.call_args.args[1]
        self.assertEqual(saved[pipeline.FIELD_PERCENT_LEFT], "10")
        self.assertEqual(saved[pipeline.FIELD_PERCENT_RIGHT], "15")
        self.assertEqual(saved[pipeline.FIELD_CAPTION_RIGHT],
                         "On all items from a curated collection on November 1-30, 2026")
        self.assertEqual(saved[pipeline.FIELD_PANEL_COLOR], "#B3122A")
        call = clients.fal.generate_claude_vision.call_args.kwargs
        self.assertEqual(call["image_urls"], ["u-dining-blend", "u-bedroom-blend"])
        self.assertIn("#RRGGBB", call["prompt"])

    def test_phase5_darkens_a_colour_too_light_for_white_text(self):
        clients = self._phase5_clients("#F5F5F5")
        pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026)
        saved_hex = clients.airtable.update_record.call_args.args[1][pipeline.FIELD_PANEL_COLOR]
        rgb = overlay.parse_hex_color(saved_hex)
        self.assertGreaterEqual(overlay.contrast_with_white(rgb), overlay.SALE_PANEL_MIN_CONTRAST)
        self.assertNotEqual(saved_hex, "#F5F5F5")

    def test_phase5_retries_once_then_falls_back_to_the_sample_red(self):
        clients = self._phase5_clients(["no idea", "still words"])
        pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026)
        self.assertEqual(clients.fal.generate_claude_vision.call_count, 2)
        self.assertEqual(clients.airtable.update_record.call_args.args[1][pipeline.FIELD_PANEL_COLOR], "#FF3131")
        clients = self._phase5_clients(["no idea", "#0B3D2E"])
        pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026)
        self.assertEqual(clients.airtable.update_record.call_args.args[1][pipeline.FIELD_PANEL_COLOR], "#0B3D2E")

    def test_phase5_api_errors_and_missing_blends_never_fail_the_run(self):
        clients = self._phase5_clients(ProviderError("down"))
        pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026)
        self.assertEqual(clients.airtable.update_record.call_args.args[1][pipeline.FIELD_PANEL_COLOR], "#FF3131")
        clients = self._phase5_clients(blends=False)
        pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026)
        clients.fal.generate_claude_vision.assert_not_called()
        self.assertEqual(clients.airtable.update_record.call_args.args[1][pipeline.FIELD_PANEL_COLOR], "#FF3131")

    def test_phase5_panel_color_override_skips_claude(self):
        clients = self._phase5_clients()
        pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026, panel_color="0b3d2e")
        clients.fal.generate_claude_vision.assert_not_called()
        clients.airtable.get_record.assert_not_called()
        self.assertEqual(clients.airtable.update_record.call_args.args[1][pipeline.FIELD_PANEL_COLOR], "#0B3D2E")
        with self.assertRaises(AutomationError):
            pipeline.run_phase_5_captions(clients, "recX", month=11, year=2026, panel_color="green")

    def test_phase6_composes_the_banner_from_the_row(self):
        clients = MagicMock()
        fields = {
            pipeline.FIELD_DINING_BLENDED: [{"url": "u-d"}],
            pipeline.FIELD_BEDROOM_BLENDED: [{"url": "u-b"}],
            pipeline.FIELD_PERCENT_LEFT: "10",
            pipeline.FIELD_PERCENT_RIGHT: "15",
            pipeline.FIELD_CAPTION_LEFT: "On all items from curated monthly collection on October 1-31, 2026",
            pipeline.FIELD_CAPTION_RIGHT: "On all items from a curated collection on October 1-31, 2026",
        }
        clients.airtable.get_record.return_value = {"fields": fields}
        with tempfile.TemporaryDirectory() as tmp, patch.object(pipeline, "OUTPUT_DIR", Path(tmp)):
            src = Path(tmp) / "room.jpg"
            Image.new("RGB", (400, 500), (40, 90, 40)).save(src)
            with patch.object(pipeline, "download_url_to_temp_file", return_value=MagicMock(path=str(src))):
                path = pipeline.run_phase_6_composite(clients, "recX")
            self.assertEqual(path.name, "sale_banner_recX.jpg")
            with Image.open(path) as banner:
                self.assertEqual(banner.size, (1800, 600))
        done = clients.airtable.update_record.call_args.args[1]
        self.assertEqual(done[pipeline.FIELD_STATUS], "Done")
        self.assertIn(pipeline.FIELD_DATE_GENERATED, done)

    def test_phase6_paints_the_panel_with_the_stored_colour(self):
        for stored, expected in (("#0B3D2E", (11, 61, 46)), ("", (255, 49, 49)), ("garbage", (255, 49, 49))):
            clients = MagicMock()
            clients.airtable.get_record.return_value = {"fields": {
                pipeline.FIELD_DINING_BLENDED: [{"url": "u-d"}],
                pipeline.FIELD_BEDROOM_BLENDED: [{"url": "u-b"}],
                pipeline.FIELD_PERCENT_LEFT: "10", pipeline.FIELD_PERCENT_RIGHT: "15",
                pipeline.FIELD_CAPTION_LEFT: "On all items from curated monthly collection on October 1-31, 2026",
                pipeline.FIELD_CAPTION_RIGHT: "On all items from a curated collection on October 1-31, 2026",
                pipeline.FIELD_PANEL_COLOR: stored,
            }}
            with tempfile.TemporaryDirectory() as tmp, patch.object(pipeline, "OUTPUT_DIR", Path(tmp)):
                src = Path(tmp) / "room.jpg"
                Image.new("RGB", (400, 500), (40, 90, 40)).save(src)
                with patch.object(pipeline, "download_url_to_temp_file", return_value=MagicMock(path=str(src))):
                    path = pipeline.run_phase_6_composite(clients, "recX")
                with Image.open(path) as banner:
                    pixel = banner.convert("RGB").getpixel((700, 5))
            self.assertTrue(all(abs(a - b) <= 6 for a, b in zip(pixel, expected)), (stored, pixel))  # JPEG drift

    def test_phase6_needs_captions_first(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": {
            pipeline.FIELD_DINING_BLENDED: [{"url": "u-d"}], pipeline.FIELD_BEDROOM_BLENDED: [{"url": "u-b"}]}}
        with patch.object(pipeline, "download_url_to_temp_file", return_value=MagicMock(path="x")):
            with self.assertRaises(AutomationError):
                pipeline.run_phase_6_composite(clients, "recX")


class SaleRunPipelineTests(unittest.TestCase):
    def _run(self, **kwargs):
        names = ("run_phase_1_scrape", "run_phase_2_interiors", "run_phase_3_claude",
                 "run_phase_4_blend", "run_phase_5_captions", "run_phase_6_composite")
        mocks = {n: MagicMock(return_value="recNEW" if n == "run_phase_1_scrape" else None) for n in names}
        with patch.object(pipeline, "PipelineClients"), patch.multiple(pipeline, **mocks):
            pipeline.run_pipeline(**kwargs)
        return {n: m.called for n, m in mocks.items()}

    def test_default_runs_everything(self):
        self.assertTrue(all(self._run().values()))

    def test_only_phase_runs_one_phase(self):
        called = self._run(record_id="recX", only_phase=4)
        self.assertEqual([n for n, v in called.items() if v], ["run_phase_4_blend"])

    def test_from_phase_and_text_only(self):
        called = self._run(record_id="recX", from_phase=3)
        self.assertEqual([n for n, v in called.items() if v][:1], ["run_phase_3_claude"])
        self.assertFalse(called["run_phase_2_interiors"])
        called = self._run(record_id="recX", text_only=True)
        self.assertEqual([n for n, v in called.items() if v], ["run_phase_5_captions", "run_phase_6_composite"])

    def test_invalid_combinations_raise(self):
        with self.assertRaises(AutomationError):
            pipeline.run_pipeline(only_phase=4)
        with self.assertRaises(AutomationError):
            pipeline.run_pipeline(record_id="recX", only_phase=4, from_phase=3)

    def test_month_is_passed_to_the_caption_phase(self):
        clients_cls = MagicMock()
        with patch.object(pipeline, "PipelineClients", clients_cls), \
                patch.object(pipeline, "run_phase_5_captions") as captions, \
                patch.object(pipeline, "run_phase_6_composite", return_value=None):
            pipeline.run_pipeline(record_id="recX", from_phase=5, month=11, year=2026)
        self.assertEqual(captions.call_args.kwargs, {"month": 11, "year": 2026, "panel_color": None})

    def test_panel_color_is_passed_to_the_caption_phase(self):
        with patch.object(pipeline, "PipelineClients", MagicMock()), \
                patch.object(pipeline, "run_phase_5_captions") as captions, \
                patch.object(pipeline, "run_phase_6_composite", return_value=None):
            pipeline.run_pipeline(record_id="recX", from_phase=5, panel_color="#0B3D2E")
        self.assertEqual(captions.call_args.kwargs["panel_color"], "#0B3D2E")

    def test_failure_marks_the_row_for_manual(self):
        clients = MagicMock()
        with patch.object(pipeline, "PipelineClients", return_value=clients), \
                patch.object(pipeline, "run_phase_4_blend", side_effect=AutomationError("boom")):
            with self.assertRaises(AutomationError):
                pipeline.run_pipeline(record_id="recX", only_phase=4)
        self.assertEqual(clients.airtable.update_record.call_args.args[1], {pipeline.FIELD_STATUS: "For Manual"})


class PanelColourInstructionTests(unittest.TestCase):
    def test_instruction_asks_for_one_hex_that_suits_both_rooms_and_white_text(self):
        from content_automation.prompts import build_sale_panel_color_instruction

        text = build_sale_panel_color_instruction()
        self.assertIn("#RRGGBB", text)
        self.assertIn("Image 1", text)
        self.assertIn("Image 2", text)
        self.assertIn("4.5:1", text)
        self.assertIn("white", text.lower())


class InstructionVariantTests(unittest.TestCase):
    FIXTURE = [{"code": "PE", "label": "Pendant Light", "name": "Allein", "notes": ""}]

    def test_text_zone_none_drops_the_reserve_rule_and_extra_rules_are_numbered(self):
        text = build_banner_multi_fixture_instruction(
            self.FIXTURE, aspect_ratio="4:5", theme="modern Christmas dining room", text_zone=None,
            extra_rules="Hang it above the table.", length_hint="about 1,800 to 3,200 characters",
        )
        self.assertNotIn("Composition reserve", text)
        self.assertIn("\n7. Extra requirements: Hang it above the table.", text)
        self.assertIn("modern Christmas dining room", text)
        self.assertIn("about 1,800 to 3,200 characters", text)

    def test_default_keeps_the_reserve_rule(self):
        text = build_banner_multi_fixture_instruction(self.FIXTURE)
        self.assertIn("\n7. Composition reserve:", text)
        self.assertNotIn("Extra requirements", text)


class StatusCountByCategoryTests(unittest.TestCase):
    @staticmethod
    def _response():
        response = MagicMock()
        response.ok = True
        response.json.return_value = {"records": [
            {"fields": {"Status": "Done", "Category": "Sale Banner"}},
            {"fields": {"Status": "Done", "Category": "Christmas Banner"}},
            {"fields": {"Status": "In progress", "Category": "sale banner"}},
            {"fields": {"Status": "For Manual", "Category": "Christmas Banner"}},
            {"fields": {"Status": "Done"}},
        ]}
        return response

    def test_category_filter_counts_only_that_categorys_rows(self):
        from content_automation.airtable_client import fetch_status_breakdown

        with patch("content_automation.airtable_client.requests.get", return_value=self._response()) as get:
            counts = fetch_status_breakdown("pat", "app", "tblX", category="Sale Banner")
        self.assertEqual(counts, {"P": 1, "S": 0, "C": 1, "D": 0, "FM": 0})
        sent = get.call_args.kwargs["params"]
        self.assertIn(("fields[]", "Category"), sent)
        self.assertIn(("fields[]", "Status"), sent)

    def test_without_category_every_row_counts(self):
        from content_automation.airtable_client import fetch_status_breakdown

        with patch("content_automation.airtable_client.requests.get", return_value=self._response()) as get:
            counts = fetch_status_breakdown("pat", "app", "tblX")
        self.assertEqual(counts, {"P": 1, "S": 0, "C": 3, "D": 0, "FM": 1})
        self.assertNotIn(("fields[]", "Category"), get.call_args.kwargs["params"])


class SaleBannerRouteTests(unittest.TestCase):
    def setUp(self):
        import importlib

        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        routes_dir = REPO_ROOT / "UI Control"
        if str(routes_dir) not in sys.path:
            sys.path.insert(0, str(routes_dir))
        self.common = importlib.import_module("routes.common")
        self.patches = [
            patch.object(self.common, "MARKETING_DIR", self.workspace),
            patch.object(self.common, "OVERRIDES_FILE", self.workspace / "output" / "config_overrides.json"),
        ]
        for p in self.patches:
            p.start()
        (self.workspace / ".env").write_text("", encoding="utf-8")
        from flask import Flask

        self.sale = importlib.import_module("routes.sale_banner")
        self.christmas = importlib.import_module("routes.christmas_banner")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.sale.sale_banner_bp)
        self.app.register_blueprint(self.christmas.christmas_banner_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def test_fixture_defaults_to_the_shared_table_and_has_no_pencils(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in self.sale.TABLE_ENV_KEYS:
                os.environ.pop(key, None)
            fixture = self.client.get("/api/sale-banner/fixtures").get_json()["fixtures"][0]
        self.assertEqual(fixture["id"], "sale_banner")
        self.assertEqual(fixture["table_id"], "tblgNk1Tp6qKUcduw")
        self.assertNotIn("moodboard_id", fixture)
        self.assertEqual(self.client.post("/api/sale-banner/moodboard", json={}).status_code, 404)

    def test_six_phases_and_its_own_script(self):
        self.assertEqual(self.sale.TOTAL_PHASES, 6)
        self.assertEqual(sorted(self.sale.PHASE_LABELS), [1, 2, 3, 4, 5, 6])
        self.assertEqual(self.sale.SCRIPT_NAME, "generate_sale_banner_pipeline.py")
        self.assertTrue((REPO_ROOT / self.sale.SCRIPT_NAME).is_file())

    def test_each_banner_counts_only_its_own_rows(self):
        with patch("content_automation.airtable_client.fetch_status_breakdown",
                   return_value={"P": 0, "S": 0, "C": 2, "D": 0, "FM": 0}) as counts:
            sale = self.client.get("/api/sale-banner/counts?refresh=true").get_json()["counts"]["sale_banner"]
            xmas = self.client.get("/api/christmas-banner/counts?refresh=true").get_json()["counts"]["christmas_banner"]
        self.assertEqual(sale["completed"], 2)
        self.assertEqual(xmas["completed"], 2)
        categories = [c.kwargs.get("category") for c in counts.call_args_list]
        self.assertEqual(categories, ["Sale Banner", "Christmas Banner"])

    def test_stop_without_a_running_pipeline_is_400(self):
        with patch.object(self.sale, "is_authorized", return_value=True):
            self.assertEqual(self.client.post("/api/sale-banner/stop").status_code, 400)


if __name__ == "__main__":
    unittest.main()
