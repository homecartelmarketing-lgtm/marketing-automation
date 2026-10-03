"""Promo banner (1080x1920, 9:16): local Pillow layout, calendar captions, tagline cleaning and the fal steps (mocked)."""

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

import generate_promo_banner_pipeline as promo  # noqa: E402
from content_automation import overlay  # noqa: E402
from content_automation import promo_calendar  # noqa: E402
from content_automation.errors import AutomationError  # noqa: E402
from content_automation.prompts import PROMO_OUTPAINT_PROMPT, build_promo_tagline_instruction  # noqa: E402

BACKGROUND = (60, 45, 35)
CAPTION_10 = "On all items from curated monthly collection on September 1–30, 2026"


def _solid_logo(directory: Path) -> Path:
    """A fully white 943x138 stand-in for the logo asset, so its pasted size can be measured exactly."""
    path = directory / "logo.png"
    Image.new("RGBA", (943, 138), (255, 255, 255, 255)).save(path)
    return path


def _bands(mask: np.ndarray, top: int, bottom: int, gap: int = 3):
    """Row bands of white pixels between two rows: [(top, bottom, left, right)]."""
    sub = mask[top:bottom]
    rows = np.where(sub.any(axis=1))[0]
    bands, start, prev = [], None, None
    for r in rows:
        if start is None:
            start = prev = r
        elif r <= prev + gap:
            prev = r
        else:
            bands.append((start, prev))
            start = prev = r
    if start is not None:
        bands.append((start, prev))
    out = []
    for a, b in bands:
        cols = np.where(sub[a:b + 1].any(axis=0))[0]
        out.append((top + int(a), top + int(b), int(cols.min()), int(cols.max())))
    return out


class PromoLayoutTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.logo = _solid_logo(self.tmp)

    def _render(self, discount=10, tagline="Festive Glow, Festive Finds", caption=CAPTION_10, bg=None):
        background = bg or Image.new("RGB", (900, 1600), BACKGROUND)
        return overlay.draw_promo_banner(
            background, discount=discount, tagline=tagline, date_caption=caption, logo_path=self.logo
        )

    @staticmethod
    def _white(img):
        arr = np.array(img.convert("RGB")).astype(int)
        return (arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235)

    def test_canvas_is_1080_by_1920_whatever_the_background_size(self):
        for size in ((900, 1600), (2000, 848), (1080, 1920)):
            self.assertEqual(self._render(bg=Image.new("RGB", size, BACKGROUND)).size, (1080, 1920))

    def test_logo_is_890_wide_with_its_height_following_the_asset_ratio(self):
        white = self._white(self._render())
        rows = np.where(white[:, 90:100].any(axis=1))[0]  # the logo is the only white thing at x 93-99 in these rows
        logo_rows = [r for r in rows if 1000 < r < 1230]
        top, bottom = min(logo_rows), max(logo_rows)
        self.assertAlmostEqual(top, 1091, delta=2)
        self.assertEqual(bottom - top + 1, 130)  # 943x138 -> 890x130, not stretched to 890x160
        cols = np.where(white[1150])[0]
        cols = cols[cols < 1000]
        self.assertAlmostEqual(int(cols.max()) - int(cols.min()) + 1, 890, delta=2)
        self.assertAlmostEqual(int(cols.min()), 93, delta=2)  # Canva x 92.6

    def test_real_logo_asset_is_resized_to_890_wide(self):
        asset = overlay._resolve_asset_file("homecartel_logo.png")
        self.assertIsNotNone(asset)
        with Image.open(asset) as logo:
            self.assertEqual(round(logo.height * overlay.PROMO_LOGO_WIDTH / logo.width), 130)

    def test_text_blocks_stack_without_overlapping_and_stay_on_the_page(self):
        white = self._white(self._render())
        bands = _bands(white, 1225, 1920)
        # tagline, "10%OFF" and the date block (its two lines, 0.91 em apart, touch each other's ink rows)
        self.assertEqual(len(bands), 3)
        tagline, big, date = bands
        self.assertLess(tagline[1], big[0])  # the tagline ends before the big text starts
        self.assertLess(big[1], date[0])  # the big text ends before the date starts
        self.assertAlmostEqual((tagline[2] + tagline[3]) / 2, 540, delta=8)  # tagline is centred
        self.assertAlmostEqual((date[2] + date[3]) / 2, 540, delta=8)  # date lines are centred
        self.assertGreaterEqual(big[2], 30)  # "10%OFF" starts near Canva x 41.9...
        self.assertLessEqual(big[3], 1078)  # ...and stays inside the 1080 page
        self.assertLess(date[1], 1900)

    def test_big_text_is_tilted_only_for_percent_and_off(self):
        self.assertEqual(overlay.PROMO_BIG_ROTATION_DEG, -1.1)
        flat = self._white(self._render())
        with patch.object(overlay, "PROMO_BIG_ROTATION_DEG", 0.0):
            straight = self._white(self._render())
        # the "10" is drawn straight in both renders, "%OFF" differs by the tilt
        self.assertTrue(np.array_equal(flat[1300:1600, 40:300], straight[1300:1600, 40:300]))
        self.assertFalse(np.array_equal(flat[1300:1600, 500:1080], straight[1300:1600, 500:1080]))

    def test_discount_15_draws_a_different_number(self):
        a, b = self._white(self._render(discount=10)), self._white(self._render(discount=15))
        self.assertFalse(np.array_equal(a[1300:1600, 40:300], b[1300:1600, 40:300]))

    def test_text_uses_the_canva_font_tracking_and_line_spacing(self):
        self.assertEqual(overlay.PROMO_DATE_FONT, "Poppins-Medium.ttf")  # Canva's B toggle renders Medium
        self.assertEqual(overlay.PROMO_TRACKING_EM, -0.13)  # Canva letter spacing -130
        self.assertEqual(overlay.PROMO_DATE_LINE_SPACING_EM, 0.91)
        self.assertEqual(overlay.PROMO_BIG_FONT, "Poppins-Regular.ttf")

    def test_date_lines_match_the_canva_widths_and_line_pitch(self):
        # Canva screenshot: the two date lines are ~676 and ~693 px wide and their baselines ~46.4 px apart.
        font = overlay._promo_font(overlay.PROMO_DATE_FONT, overlay.PROMO_DATE_SIZE)
        px = overlay.PROMO_DATE_SIZE * overlay.PROMO_FONT_PX
        tracking = overlay.PROMO_TRACKING_EM * px
        line1, line2 = overlay.promo_wrap_date(CAPTION_10, font, tracking)
        self.assertEqual(line1, "On all items from curated monthly")
        self.assertEqual(line2, "collection on September 1–30, 2026")
        self.assertAlmostEqual(overlay._tracked_width(line1, font, tracking), 682, delta=8)
        self.assertAlmostEqual(overlay._tracked_width(line2, font, tracking), 698, delta=8)
        self.assertAlmostEqual(overlay.PROMO_DATE_LINE_SPACING_EM * px, 46.9, delta=1.5)

        # rendered: the date block is 2 lines of 0.91 em pitch (first ink row to last ink row of the block)
        white = self._white(self._render())
        date_rows = np.where(white[1600:1760].any(axis=1))[0]
        self.assertAlmostEqual(int(date_rows.max() - date_rows.min()) + 1, 100, delta=6)

    def test_tagline_and_big_text_are_as_wide_as_in_canva(self):
        white = self._white(self._render())
        tagline = _bands(white, 1225, 1300)[0]
        self.assertAlmostEqual(tagline[3] - tagline[2] + 1, 565, delta=15)  # Canva ~557
        big = _bands(white, 1300, 1600)[0]
        self.assertAlmostEqual(big[3], 1035, delta=12)  # right edge of "OFF" in Canva ~1033

    def test_date_wraps_to_two_balanced_lines_and_short_text_stays_on_one(self):
        font = overlay._promo_font(overlay.PROMO_DATE_FONT, overlay.PROMO_DATE_SIZE)
        tracking = overlay.PROMO_TRACKING_EM * overlay.PROMO_DATE_SIZE * overlay.PROMO_FONT_PX
        lines = overlay.promo_wrap_date(CAPTION_10, font, tracking)
        self.assertEqual(len(lines), 2)
        self.assertEqual(" ".join(lines), CAPTION_10)
        for line in lines:
            self.assertLessEqual(overlay._tracked_width(line, font, tracking), overlay.PROMO_DATE_MAX_WIDTH)
        self.assertEqual(overlay.promo_wrap_date("September 1–30, 2026", font, tracking), ["September 1–30, 2026"])
        self.assertEqual(overlay.promo_wrap_date("", font, tracking), [])

    def test_a_long_tagline_shrinks_instead_of_leaving_the_page(self):
        white = self._white(self._render(tagline="A Very Long Festive Promotion Tagline That Keeps Going On"))
        tagline = _bands(white, 1225, 1300)[0]
        self.assertGreaterEqual(tagline[2], 60)
        self.assertLessEqual(tagline[3], 1020)

    def test_writes_a_png_when_given_a_destination(self):
        out = overlay.draw_promo_banner(
            Image.new("RGB", (500, 900), BACKGROUND), discount=10, tagline="T", date_caption=CAPTION_10,
            destination=self.tmp / "sub" / "p.png", logo_path=self.logo,
        )
        with Image.open(out) as saved:
            self.assertEqual((saved.format, saved.size), ("PNG", (1080, 1920)))


class PromoCalendarTests(unittest.TestCase):
    def test_date_text_uses_an_en_dash_and_the_chosen_month(self):
        self.assertEqual(promo_calendar.promo_date_text(10, "SEP", 2026), "September 1–30, 2026")
        self.assertEqual(promo_calendar.promo_date_text(15, 9, 2026), "September 1–30, 2026")
        self.assertEqual(promo_calendar.promo_date_text(10, "February", 2028), "February 1–29, 2028")  # leap year

    def test_month_parsing(self):
        for value in (9, "9", "SEP", "sep", "September"):
            self.assertEqual(promo_calendar.month_number(value), 9)
        self.assertEqual(promo_calendar.month_abbr(9), "SEP")
        with self.assertRaises(AutomationError):
            promo_calendar.month_number("13")

    def test_captions_follow_the_canva_wording_for_each_discount(self):
        text = "September 1–30, 2026"
        self.assertEqual(promo_calendar.promo_caption(10, text), f"On all items from curated monthly collection on {text}")
        self.assertEqual(promo_calendar.promo_caption(15, text), f"On all items from a curated collection on {text}")
        with self.assertRaises(AutomationError):
            promo_calendar.promo_date_text(12, "SEP", 2026)


class PromoTaglineTests(unittest.TestCase):
    def test_banner_name_comes_from_the_file_name(self):
        self.assertEqual(promo.clean_banner_name("Festive Glow Banner.jpg"), "Festive Glow Banner")
        self.assertEqual(promo.clean_banner_name(Path("out/festive_glow-banner_2.png")), "festive glow banner 2")

    def test_clean_tagline_strips_quotes_markdown_emoji_and_extra_lines(self):
        self.assertEqual(promo.clean_tagline('"Festive Glow, Festive Finds"'), "Festive Glow, Festive Finds")
        self.assertEqual(promo.clean_tagline("**Title:** Festive Glow, Festive Finds.\nWhy: it rhymes"), "Festive Glow, Festive Finds")
        self.assertEqual(promo.clean_tagline("\n\n  Cosy Lights, Cosy Nights \U0001F384\n"), "Cosy Lights, Cosy Nights")
        self.assertEqual(promo.clean_tagline(""), "")

    def test_clean_tagline_limits_words_and_length(self):
        long = promo.clean_tagline("one two three four five six seven eight nine ten")
        self.assertLessEqual(len(long.split()), promo.TAGLINE_MAX_WORDS)
        self.assertLessEqual(len(promo.clean_tagline("Supercalifragilistic " * 6)), promo.TAGLINE_MAX_CHARS)

    def test_the_prompt_is_based_on_the_banner_name_and_the_outpaint_prompt_forbids_text(self):
        prompt = build_promo_tagline_instruction("Festive Glow Banner")
        self.assertIn("Festive Glow Banner", prompt)
        self.assertIn("MAIN source", prompt)
        self.assertIn("3 to 5 words", prompt)
        self.assertIn("NO text", PROMO_OUTPAINT_PROMPT)
        self.assertIn("9:16", PROMO_OUTPAINT_PROMPT)

    def test_override_wins_without_calling_claude(self):
        fal = MagicMock()
        self.assertEqual(promo.make_tagline(fal, "u", "Banner Name", "Cosy Nights, Warm Lights"), "Cosy Nights, Warm Lights")
        fal.generate_claude_vision.assert_not_called()

    def test_a_failed_or_empty_claude_call_falls_back_to_the_banner_name_and_never_raises(self):
        fal = MagicMock()
        fal.generate_claude_vision.side_effect = RuntimeError("boom")
        self.assertEqual(promo.make_tagline(fal, "u", "Festive Glow Banner"), "Festive Glow Banner")
        fal.generate_claude_vision.side_effect = None
        fal.generate_claude_vision.return_value = "   "
        self.assertEqual(promo.make_tagline(fal, "u", "Festive Glow Banner"), "Festive Glow Banner")
        self.assertEqual(promo.make_tagline(None, "", "Festive Glow Banner"), "Festive Glow Banner")  # dry run

    def test_a_good_claude_reply_is_cleaned_and_used(self):
        fal = MagicMock()
        fal.generate_claude_vision.return_value = '"Festive Glow, Festive Finds"\n'
        self.assertEqual(promo.make_tagline(fal, "https://fal/banner.jpg", "Festive Glow Banner"), "Festive Glow, Festive Finds")
        args, kwargs = fal.generate_claude_vision.call_args
        self.assertIn("Festive Glow Banner", args[0])
        self.assertEqual(args[1], ["https://fal/banner.jpg"])
        self.assertEqual(kwargs["model"], promo.CLAUDE_MODEL)


class PromoRunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.banner = self.tmp / "Festive Glow Banner.jpg"
        Image.new("RGB", (1600, 680), (90, 70, 50)).save(self.banner)

    def test_output_names(self):
        self.assertEqual(promo.output_stem(10, 9, 2026), "promo_SEP-2026-10OFF_9x16")
        self.assertEqual(promo.output_stem(15, 8, 2026), "promo_AUG-2026-15OFF_9x16")

    def test_dry_run_makes_the_png_and_background_without_touching_fal(self):
        with patch.object(promo, "make_fal_client", side_effect=AssertionError("fal must not be used in a dry run")):
            out = promo.run(self.banner, 10, "SEP", 2026, dry_run=True, output_dir=self.tmp / "out")
        # a dry run is saved under its own name so it can never overwrite a live promo or background
        self.assertEqual(out.name, "promo_SEP-2026-10OFF_9x16_dryrun.png")
        with Image.open(out) as img:
            self.assertEqual(img.size, (1080, 1920))
        with Image.open(self.tmp / "out" / "promo_SEP-2026-10OFF_9x16_dryrun_bg.png") as bg:
            self.assertEqual(bg.size, (1080, 1920))
        self.assertFalse((self.tmp / "out" / "promo_SEP-2026-10OFF_9x16.png").exists())

    def test_live_run_extends_to_9x16_with_nano_banana_pro_and_asks_claude_for_the_tagline(self):
        fal = MagicMock()
        fal.upload_file.return_value = "https://fal/banner.jpg"
        fal.generate.return_value = "https://fal/bg.png"
        fal.generate_claude_vision.return_value = "Festive Glow, Festive Finds"
        bg_file = self.tmp / "bg.png"
        Image.new("RGB", (768, 1376), (50, 40, 30)).save(bg_file)
        with patch.object(promo, "download_url_to_temp_file", return_value=MagicMock(path=str(bg_file))):
            out = promo.run(self.banner, 15, 8, 2026, resolution="2K", output_dir=self.tmp / "out", fal=fal)
        self.assertEqual(out.name, "promo_AUG-2026-15OFF_9x16.png")
        fal.upload_file.assert_called_once_with(self.banner)
        args, kwargs = fal.generate.call_args
        self.assertEqual(args[1], ["https://fal/banner.jpg"])
        self.assertEqual(
            {k: kwargs[k] for k in ("aspect_ratio", "resolution", "model", "output_format")},
            {"aspect_ratio": "9:16", "resolution": "2K", "model": "fal-ai/nano-banana-pro/edit", "output_format": "png"},
        )
        self.assertIn("NO text", args[0])
        with Image.open(out) as img:
            self.assertEqual(img.size, (1080, 1920))

    def test_a_failing_tagline_call_does_not_fail_the_run(self):
        fal = MagicMock()
        fal.upload_file.return_value = "u"
        fal.generate.return_value = "https://fal/bg.png"
        fal.generate_claude_vision.side_effect = RuntimeError("claude down")
        bg_file = self.tmp / "bg.png"
        Image.new("RGB", (768, 1376), (50, 40, 30)).save(bg_file)
        with patch.object(promo, "download_url_to_temp_file", return_value=MagicMock(path=str(bg_file))):
            out = promo.run(self.banner, 10, "SEP", 2026, output_dir=self.tmp / "out", fal=fal)
        self.assertTrue(out.is_file())

    def test_a_date_override_replaces_the_calendar_window(self):
        with patch.object(promo, "draw_promo_banner") as draw:
            draw.return_value = None
            promo.run(self.banner, 15, "AUG", 2026, dry_run=True, output_dir=self.tmp / "out",
                      date_text="August 20–31, 2026")
        self.assertEqual(
            draw.call_args.kwargs["date_caption"], "On all items from a curated collection on August 20–31, 2026"
        )

    def test_bad_inputs_are_refused_before_any_work(self):
        with self.assertRaises(AutomationError):
            promo.run(self.tmp / "missing.jpg", 10, "SEP", 2026, dry_run=True, output_dir=self.tmp / "out")
        with self.assertRaises(AutomationError):
            promo.run(self.banner, 12, "SEP", 2026, dry_run=True, output_dir=self.tmp / "out")
        with self.assertRaises(AutomationError):
            promo.run(self.banner, 10, "NOPE", 2026, dry_run=True, output_dir=self.tmp / "out")

    def test_live_mode_without_a_fal_key_explains_dry_run(self):
        with patch.dict("os.environ", {"FAL_KEY": "", "FAL_API_KEY": ""}):
            with self.assertRaises(AutomationError) as ctx:
                promo.make_fal_client()
        self.assertIn("--dry-run", str(ctx.exception))

    def test_cli_accepts_only_10_or_15(self):
        with patch.object(sys, "argv", ["x", "--banner", "b.jpg", "--discount", "12", "--month", "SEP", "--year", "2026"]):
            with self.assertRaises(SystemExit):
                promo.main()


if __name__ == "__main__":
    unittest.main()
