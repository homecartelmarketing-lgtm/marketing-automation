import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from content_automation import overlay, phased_content, story_tip

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "homecartel_logo.png"


def _bright_box(image: Image.Image, box: tuple[int, int, int, int], threshold: int = 235):
    """Bounding box of near-white pixels inside ``box`` (x0, y0, x1, y1)."""
    crop = image.crop(box).convert("L").point(lambda v: 255 if v >= threshold else 0)
    found = crop.getbbox()
    if not found:
        return None
    return (found[0] + box[0], found[1] + box[1], found[2] + box[0], found[3] + box[1])


class TipsEduStoryLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # A plain mid-grey 4:5-ish photo so only drawn text can be near-white.
        self.photo = Image.new("RGB", (1080, 1350), (60, 60, 60))

    def test_output_is_1080x1920_and_photo_is_untouched_above_the_gradient(self):
        result = overlay.overlay_tips_edu_story_layout(self.photo, "Layer warm light with natural textures for a calm room.")
        self.assertEqual(result.size, (1080, 1920))
        # Top of the canvas (above the gradient and logo area) keeps the fitted photo colour.
        self.assertEqual(result.getpixel((20, 20)), (60, 60, 60))

    def test_title_and_underline_land_in_the_measured_boxes(self):
        result = overlay.overlay_tips_edu_story_layout(self.photo, "")
        title = _bright_box(result, (100, 1340, 1000, 1432))
        self.assertIsNotNone(title)
        # Measured on the layout: ink x 121-639, y 1369-1425 (allow 3 px).
        self.assertLessEqual(abs(title[0] - 121), 3)
        self.assertLessEqual(abs(title[2] - 640), 4)
        self.assertLessEqual(abs(title[1] - 1369), 3)
        self.assertLessEqual(abs(title[3] - 1426), 3)

        underline = _bright_box(result, (100, 1434, 1000, 1445))
        self.assertEqual(underline, (113, 1437, 633, 1439))

    def test_tip_is_drawn_below_underline_inside_margins(self):
        tip = "Hang a pendant light low over the dining table so the glow feels warm and welcoming."
        result = overlay.overlay_tips_edu_story_layout(self.photo, tip)
        ink = _bright_box(result, (0, 1500, 1080, 1920))
        self.assertIsNotNone(ink)
        self.assertGreaterEqual(ink[0], 113)
        self.assertLessEqual(ink[2], 1080 - 113 + 2)
        self.assertGreaterEqual(ink[1], 1541)

    def test_long_tip_never_exceeds_four_lines(self):
        tip = " ".join(["luminous"] * 28)
        result = overlay.overlay_tips_edu_story_layout(self.photo, tip)
        ink = _bright_box(result, (0, 1500, 1080, 1920))
        self.assertIsNotNone(ink)
        self.assertLess(ink[3], 1920)

    def test_create_image_saves_jpeg_and_stamps_single_logo(self):
        if not LOGO.is_file():
            self.skipTest("brand logo asset missing")
        destination = self.tmp / "story.jpg"
        out = overlay.create_tips_edu_story_image(
            self.photo, "Layer warm light with natural textures for a calm room.", destination, logo_path=LOGO
        )
        self.assertEqual(out, destination)
        with Image.open(destination) as image:
            self.assertEqual(image.size, (1080, 1920))
            # Logo sits in the story logo box (top-right); the left of the same band stays photo colour.
            logo_ink = _bright_box(image, (700, 100, 1080, 200), threshold=200)
            self.assertIsNotNone(logo_ink)
            self.assertGreaterEqual(logo_ink[0], 770)
            self.assertIsNone(_bright_box(image, (0, 100, 700, 200), threshold=200))


class StoryTipTests(unittest.TestCase):
    def test_sanitize_strips_labels_quotes_and_extra_lines(self):
        raw = '"Style Tip: Pair a warm pendant glow with natural oak and linen for a calm evening mood"\nExtra note.'
        self.assertEqual(
            story_tip.sanitize_tip(raw),
            "Pair a warm pendant glow with natural oak and linen for a calm evening mood.",
        )

    def test_sanitize_rejects_too_short_or_too_long(self):
        self.assertEqual(story_tip.sanitize_tip("Too short."), "")
        self.assertEqual(story_tip.sanitize_tip(" ".join(["word"] * 40)), "")
        self.assertEqual(story_tip.sanitize_tip(""), "")
        self.assertEqual(story_tip.sanitize_tip(None), "")

    def test_resolve_tip_falls_back_per_category(self):
        tip, used = story_tip.resolve_tip("", "pendant_lights")
        self.assertTrue(used)
        self.assertEqual(tip, story_tip.FALLBACK_TIPS["pendant_lights"])
        tip, used = story_tip.resolve_tip("", "unknown")
        self.assertEqual(tip, story_tip.FALLBACK_TIPS["default"])

    def test_resolve_tip_keeps_good_claude_reply(self):
        reply = "Let a statement chandelier anchor the room and echo its brass finish in nearby decor."
        tip, used = story_tip.resolve_tip(reply, "chandeliers")
        self.assertFalse(used)
        self.assertEqual(tip, reply)

    def test_fallback_tips_are_valid_single_sentences(self):
        for category, tip in story_tip.FALLBACK_TIPS.items():
            self.assertEqual(story_tip.sanitize_tip(tip), tip, category)


class TipsEduStoryPhase5Tests(unittest.TestCase):
    def _runner(self, workspace: Path, fal_reply):
        runner = object.__new__(phased_content.PhasedContentRunner)
        runner.settings = SimpleNamespace(workspace=workspace, output_dir=workspace / "out")
        runner.definition = SimpleNamespace(
            key="tips_edu_story_pendant",
            category_code="pendant_lights",
            final_field="Tips and Edu Story Converted",
        )
        runner.fal = mock.Mock()
        if isinstance(fal_reply, Exception):
            runner.fal.generate_claude_vision.side_effect = fal_reply
        else:
            runner.fal.generate_claude_vision.return_value = fal_reply
        runner.airtable = mock.Mock()
        runner.logger = mock.Mock()
        runner._download = lambda url, destination: (
            Image.new("RGB", (1080, 1350), (90, 80, 70)).save(destination, "JPEG") or destination
        )
        runner._resolve_logo_path = lambda fields=None: LOGO if LOGO.is_file() else None
        return runner

    def _run(self, fal_reply):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        runner = self._runner(tmp, fal_reply)
        with mock.patch.object(phased_content, "split_item_name", return_value=("Aria", "Pendant Light")):
            runner._tips_edu_story_local_layout("recTEST", {"Item Name": "Aria | Pendant Light"}, "https://x/blended.jpg")
        return runner

    def test_uses_claude_tip_and_uploads_local_layout_without_nano_banana(self):
        reply = "Hang a pendant light low over the dining table so the glow feels warm and welcoming."
        runner = self._run(reply)
        runner.fal.generate.assert_not_called()
        runner.airtable.upload_attachment.assert_called_once()
        record_id, field, path, filename = runner.airtable.upload_attachment.call_args.args
        self.assertEqual((record_id, field, filename), ("recTEST", "Tips and Edu Story Converted", "tips_edu_story_converted.jpg"))
        with Image.open(path) as image:
            self.assertEqual(image.size, (1080, 1920))
        event = runner.logger.event.call_args
        self.assertEqual(event.args[0], "layout_completed")
        self.assertFalse(event.kwargs["tip_used_fallback"])

    def test_falls_back_when_claude_call_fails(self):
        runner = self._run(RuntimeError("fal down"))
        runner.airtable.upload_attachment.assert_called_once()
        self.assertTrue(runner.logger.event.call_args.kwargs["tip_used_fallback"])


if __name__ == "__main__":
    unittest.main()
