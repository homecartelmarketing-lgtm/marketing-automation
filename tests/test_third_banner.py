"""Third banner: 951 px panel in the Sale colour (title, subtitle, arrow) + a Krea bedroom 849 px wide, on one row."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import generate_third_banner_pipeline as third  # noqa: E402
from content_automation import overlay  # noqa: E402
from content_automation.errors import AutomationError  # noqa: E402
from content_automation.prompts import BANNER_MOUNT_HINTS  # noqa: E402


def _photo(color=(30, 60, 120), size=(1275, 900)):
    return Image.new("RGB", size, color)


class ThirdBannerLayoutTests(unittest.TestCase):
    PANEL = (61, 42, 36)  # the Sale banner's colour in a real run (#3D2A24)

    def _render(self, **kwargs):
        return np.array(overlay.draw_third_banner(_photo(), panel_color=self.PANEL, **kwargs)).astype(int)

    @staticmethod
    def _bands(white_cols):
        rows = np.where(white_cols.any(axis=1))[0]
        bands, start, prev = [], None, None
        for r in rows:
            if start is None:
                start = prev = r
            elif r <= prev + 3:
                prev = r
            else:
                bands.append((start, prev))
                start = prev = r
        bands.append((start, prev))
        out = []
        for top, bottom in bands:
            cols = np.where(white_cols[top:bottom + 1].any(axis=0))[0]
            out.append((int(cols.min()), int(cols.max()), int(top), int(bottom)))
        return out

    def test_canvas_panel_and_photo_slots(self):
        img = overlay.draw_third_banner(_photo((30, 60, 120)), panel_color=self.PANEL)
        self.assertEqual(img.size, (1800, 600))
        arr = np.array(img).astype(int)
        self.assertEqual(overlay.THIRD_PANEL_WIDTH, 951)
        self.assertEqual(overlay.THIRD_PHOTO_SIZE, (849, 600))
        self.assertEqual(tuple(arr[5, 5]), self.PANEL)
        self.assertEqual(tuple(arr[300, 940]), self.PANEL)  # still the panel just before x 951
        self.assertEqual(tuple(arr[300, 960]), (30, 60, 120))  # the photo starts at x 951
        self.assertEqual(tuple(arr[595, 1795]), (30, 60, 120))

    def test_text_and_arrow_match_the_canva_sample(self):
        arr = self._render()
        white = (arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235)
        title, subtitle, arrow = self._bands(white[:, :940])
        # Canva: title x 46.4-624.8, y 394.7-465.6 | subtitle x 46.4-423.5, y 483.9-515.7 | arrow x 43.9-203.8, y 547.5-560.9
        self.assertAlmostEqual(title[0], 46, delta=3)
        self.assertAlmostEqual(title[1], 624, delta=4)
        self.assertAlmostEqual(title[2], 395, delta=3)
        self.assertAlmostEqual(title[3], 465, delta=3)
        self.assertAlmostEqual(subtitle[0], 46, delta=3)
        self.assertAlmostEqual(subtitle[1], 428, delta=10)
        self.assertAlmostEqual(subtitle[2], 484, delta=3)
        self.assertAlmostEqual(subtitle[3], 515, delta=3)
        self.assertAlmostEqual(arrow[0], 44, delta=3)
        self.assertAlmostEqual(arrow[1], 203, delta=3)
        self.assertAlmostEqual(arrow[2], 548, delta=3)
        self.assertAlmostEqual(arrow[3], 560, delta=3)

    def test_fonts_are_the_canva_ones(self):
        self.assertEqual(overlay.THIRD_TITLE_STYLE.font_file, "Poppins-Medium.ttf")  # Canva's B renders Medium
        self.assertAlmostEqual(overlay.THIRD_TITLE_STYLE.size, 70 * 4 / 3)
        self.assertEqual(overlay.THIRD_SUBTITLE_STYLE.font_file, "Poppins-Regular.ttf")
        self.assertAlmostEqual(overlay.THIRD_SUBTITLE_STYLE.size, 24 * 4 / 3)
        self.assertEqual((overlay.THIRD_TITLE_TEXT, overlay.THIRD_SUBTITLE_TEXT),
                         ("New Collection", "Free Delivery and Installation"))

    def test_panel_takes_any_colour_hex_or_tuple_and_falls_back_to_the_sample_red(self):
        for given, expected in (("#0B3D2E", (11, 61, 46)), ((10, 20, 30), (10, 20, 30)),
                                ("garbage", (255, 49, 49)), (None, (255, 49, 49))):
            arr = np.array(overlay.draw_third_banner(_photo(), panel_color=given)).astype(int)
            self.assertEqual(tuple(arr[5, 5]), expected, given)

    def test_long_custom_text_shrinks_to_stay_inside_the_panel(self):
        arr = self._render(title="A Much Longer Collection Title For The Holidays", subtitle="")
        white = (arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235)
        cols = np.where(white[:, :940][380:470].any(axis=0))[0]
        self.assertLessEqual(int(cols.max()), int(overlay.THIRD_PANEL_WIDTH - overlay.THIRD_TEXT_INK_LEFT) + 2)

    def test_writes_a_jpeg_when_given_a_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = overlay.draw_third_banner(_photo(), panel_color=self.PANEL, destination=Path(tmp) / "x" / "t.jpg")
            self.assertTrue(Path(out).is_file())
            with Image.open(out) as saved:
                self.assertEqual(saved.size, (1800, 600))


class ThirdBannerPhaseTests(unittest.TestCase):
    @staticmethod
    def _fields():
        return {
            "Item Name": "BA: Yareli\nBB: Yarelo",
            third.FIELD_FURNITURE: [
                {"filename": "BA_s1_m.png", "url": "u-ba"},
                {"filename": "BB_s2_m.png", "url": "u-bb"},
                {"filename": "CH_s9_m.png", "url": "u-ch"},
            ],
            third.FIELD_BEDROOM_INTERIOR: [{"url": "u-bedroom", "filename": "b.jpg"}],
            third.FIELD_BEDROOM_PROMPT: "bedroom prompt",
            third.FIELD_BEDROOM_BLENDED: [{"url": "u-blend"}],
            third.FIELD_PANEL_COLOR: "#3D2A24",
        }

    def test_slots_and_defaults(self):
        self.assertEqual([s["code"] for s in third.THIRD_SLOTS], ["BA", "BB"])
        self.assertEqual({s["category"] for s in third.THIRD_SLOTS}, {"table_lamps"})
        self.assertEqual(third.BEDROOM_PROMPT, "Generate me a modern bedroom with a Christmas vibe")
        self.assertEqual(third.ROOM_ASPECT_RATIO, "3:2")
        self.assertEqual(BANNER_MOUNT_HINTS["BA"], BANNER_MOUNT_HINTS["TL"])
        self.assertEqual(BANNER_MOUNT_HINTS["BB"], BANNER_MOUNT_HINTS["TL"])

    def test_phase_selection(self):
        self.assertEqual(third.phases_to_run(), [2, 3, 4, 5])
        self.assertEqual(third.phases_to_run(4), [4, 5])
        self.assertEqual(third.phases_to_run(only_phase=5), [5])
        for kwargs in ({"from_phase": 6}, {"only_phase": 6}, {"only_phase": 3, "from_phase": 4}):
            with self.assertRaises(AutomationError):
                third.phases_to_run(**kwargs)

    def test_never_creates_a_row_of_its_own(self):
        with patch.object(third, "PipelineClients") as clients_cls:
            with self.assertRaises(AutomationError):
                third.run_pipeline("")
        clients_cls.assert_not_called()

    def test_phase2_generates_a_short_moodboard_driven_bedroom(self):
        clients = MagicMock()
        clients.krea.download_image.return_value = MagicMock(path="x.jpg")
        with patch.object(third, "krea_generate_room", return_value="https://k/room.jpg") as krea:
            third.run_phase_2_interior(clients, "recX")
        kwargs = krea.call_args.kwargs
        self.assertEqual(kwargs["prompt"], third.BEDROOM_PROMPT)
        self.assertEqual(kwargs["moodboard_id"], third.BEDROOM_MOODBOARD_DEFAULT)
        self.assertEqual((kwargs["aspect_ratio"], kwargs["fallback_aspect_ratio"]), ("3:2", "4:3"))
        saved = clients.airtable.update_record.call_args.args[1]
        self.assertEqual(saved[third.FIELD_BEDROOM_INTERIOR_PROMPT], third.BEDROOM_PROMPT)

    def test_phase2_overrides_win(self):
        clients = MagicMock()
        clients.krea.download_image.return_value = MagicMock(path="x.jpg")
        with patch.object(third, "krea_generate_room", return_value="https://k/room.jpg") as krea:
            third.run_phase_2_interior(clients, "recX", custom_moodboard="mb-3", custom_prompt="custom")
        self.assertEqual((krea.call_args.kwargs["moodboard_id"], krea.call_args.kwargs["prompt"]), ("mb-3", "custom"))

    def test_phase3_asks_claude_with_the_bedroom_and_the_two_lamps_only(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": self._fields()}
        good = "Image 2 Image 3 " * 60
        clients.fal.generate_claude_vision.return_value = good
        prompt = third.run_phase_3_claude(clients, "recX")
        self.assertEqual(prompt, good.strip())
        call_kwargs = clients.fal.generate_claude_vision.call_args.kwargs
        self.assertEqual(call_kwargs["image_urls"], ["u-bedroom", "u-ba", "u-bb"])  # not the CH cutout
        self.assertIn("modern Christmas bedroom", call_kwargs["prompt"])
        self.assertIn("bedside tables", call_kwargs["prompt"])
        self.assertIn("3:2", call_kwargs["prompt"])

    def test_phase3_falls_back_and_needs_its_inputs(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": self._fields()}
        clients.fal.generate_claude_vision.side_effect = RuntimeError("boom")
        prompt = third.run_phase_3_claude(clients, "recX")
        self.assertIn("(Image 3)", prompt)
        fields = self._fields()
        del fields[third.FIELD_BEDROOM_INTERIOR]
        clients.airtable.get_record.return_value = {"fields": fields}
        with self.assertRaises(AutomationError):
            third.run_phase_3_claude(clients, "recX")

    def test_phase4_blends_at_3_to_2_and_saves_the_blend(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": self._fields()}
        with tempfile.TemporaryDirectory() as tmp, patch.object(third, "OUTPUT_DIR", Path(tmp)):
            src = Path(tmp) / "src.jpg"
            Image.new("RGB", (40, 30), (1, 2, 3)).save(src)
            with patch.object(third, "nano_banana_blend", return_value="https://f/blend.jpg") as blend, \
                    patch.object(third, "download_url_to_temp_file", return_value=MagicMock(path=str(src))):
                saved = third.run_phase_4_blend(clients, "recX")
            self.assertEqual(saved.name, "bedroom_blend_recX.jpg")
        kwargs = blend.call_args.kwargs
        self.assertEqual(kwargs["image_urls"], ["u-bedroom", "u-ba", "u-bb"])
        self.assertEqual((kwargs["prompt"], kwargs["aspect_ratio"]), ("bedroom prompt", "3:2"))

    def test_phase5_composes_with_the_sale_colour_and_writes_done(self):
        clients = MagicMock()
        clients.airtable.get_record.return_value = {"fields": self._fields()}
        with tempfile.TemporaryDirectory() as tmp, patch.object(third, "OUTPUT_DIR", Path(tmp)):
            src = Path(tmp) / "bedroom.jpg"
            _photo((30, 60, 120), (600, 400)).save(src)
            with patch.object(third, "download_url_to_temp_file", return_value=MagicMock(path=str(src))):
                path = third.run_phase_5_composite(clients, "recX")
            self.assertEqual(path.name, "third_banner_recX.jpg")
            with Image.open(path) as banner:
                self.assertEqual(banner.size, (1800, 600))
                pixel = banner.convert("RGB").getpixel((10, 10))
        self.assertTrue(all(abs(a - b) <= 6 for a, b in zip(pixel, (61, 42, 36))), pixel)  # #3D2A24, JPEG drift
        done = clients.airtable.update_record.call_args.args[1]
        self.assertEqual(done[third.FIELD_STATUS], "Done")
        self.assertIn(third.FIELD_DATE_GENERATED, done)
        clients.airtable.upload_attachment.assert_called_once()
        self.assertEqual(clients.airtable.upload_attachment.call_args.args[1], third.FIELD_THIRD_BANNER)

    def test_phase5_without_a_sale_colour_uses_the_sample_red_and_needs_the_blend(self):
        clients = MagicMock()
        fields = self._fields()
        fields[third.FIELD_PANEL_COLOR] = ""
        clients.airtable.get_record.return_value = {"fields": fields}
        with tempfile.TemporaryDirectory() as tmp, patch.object(third, "OUTPUT_DIR", Path(tmp)):
            src = Path(tmp) / "bedroom.jpg"
            _photo((30, 60, 120), (600, 400)).save(src)
            with patch.object(third, "download_url_to_temp_file", return_value=MagicMock(path=str(src))):
                path = third.run_phase_5_composite(clients, "recX", title="Holiday Collection", subtitle="Order today")
            with Image.open(path) as banner:
                pixel = banner.convert("RGB").getpixel((10, 10))
        self.assertTrue(all(abs(a - b) <= 6 for a, b in zip(pixel, (255, 49, 49))), pixel)
        fields = self._fields()
        del fields[third.FIELD_BEDROOM_BLENDED]
        clients.airtable.get_record.return_value = {"fields": fields}
        with self.assertRaises(AutomationError):
            third.run_phase_5_composite(clients, "recX")

    def test_a_failure_marks_the_row_for_manual(self):
        clients = MagicMock()
        with patch.object(third, "PipelineClients", return_value=clients), \
                patch.object(third, "run_phase_4_blend", side_effect=AutomationError("boom")):
            with self.assertRaises(AutomationError):
                third.run_pipeline("recX", only_phase=4)
        self.assertEqual(clients.airtable.update_record.call_args.args[1], {third.FIELD_STATUS: "For Manual"})


if __name__ == "__main__":
    unittest.main()
