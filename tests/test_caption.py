"""Unit tests for the shared universal caption module (Task 1)."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation import caption as C


def _long_body(item: str) -> str:
    return (
        f"Golden hour, sculpted in light for the {item}, where every evening "
        f"feels calm and warm and beautifully styled around the {item} glow."
    )


def _valid_raw(item: str = "Aurelia Chandelier") -> str:
    return (
        f"Golden hour, sculpted in light \u2728\n\n{item} | Chandelier\n\n"
        f"{_long_body(item)}\n\nReady to let the {item} steal the spotlight "
        "in your home?\n\n" + C.CONTACT_BLOCK + "\n\n" + C.HASHTAG_LINE
    )


class CaptionFormatTest(unittest.TestCase):
    def test_assemble_matches_user_format(self):
        out = C.assemble_caption(
            "Golden hour, sculpted in light \u2728",
            "Aurelia Chandelier",
            "Chandelier",
            "Its warm brass glow softens the living room.",
            "Ready to let the Aurelia Chandelier steal the spotlight in your home?",
        )
        self.assertIn("Aurelia Chandelier | Chandelier", out)
        self.assertIn("Inquire now!", out)
        self.assertIn("0977 825 5588", out)
        self.assertTrue(out.rstrip().endswith(C.HASHTAG_LINE))

    def test_assemble_block_order(self):
        out = C.assemble_caption(
            "Hook line \u2728", "Aurelia Chandelier", "Chandelier",
            "Value sentence here.", "CTA question here?",
        )
        blocks = out.split("\n\n")
        self.assertEqual(len(blocks), 6)
        self.assertIn("Hook line", blocks[0])
        self.assertEqual(blocks[1], "Aurelia Chandelier | Chandelier")
        self.assertEqual(blocks[2], "Value sentence here.")
        self.assertEqual(blocks[3], "CTA question here?")
        self.assertTrue(blocks[4].startswith("Inquire now!"))
        self.assertEqual(blocks[5], C.HASHTAG_LINE)

    def test_fallback_never_empty(self):
        for item, ptype in [("Aurelia Chandelier", "Chandelier"), ("", "")]:
            out = C.fallback_caption(item, ptype)
            self.assertTrue(out.strip())
            self.assertIn("Inquire now!", out)
            self.assertTrue(out.rstrip().endswith(C.HASHTAG_LINE))

    def test_contact_and_hashtag_constants_verbatim(self):
        self.assertEqual(
            C.CONTACT_BLOCK,
            "Inquire now!\n\U0001f4de 0977 825 5588 (or send us a DM)\n"
            "\U0001f4de (02) 8248 8071 | Dial 1\n"
            "\U0001f4e9 sales@homecartel.com",
        )
        self.assertEqual(C.CAPTION_FIELD, "Caption Generated")


class CaptionSanitizerTest(unittest.TestCase):
    def test_sanitize_appends_missing_blocks(self):
        raw = (
            "Golden hour, sculpted in light \u2728\n\n"
            "Aurelia Chandelier | Chandelier\n\n"
            f"{_long_body('Aurelia Chandelier')}\n\n"
            "Ready to let the Aurelia Chandelier steal the spotlight in your home?"
        )
        out = C.sanitize_caption(raw, "Aurelia Chandelier")
        self.assertIn("Inquire now!", out)
        self.assertTrue(out.rstrip().endswith(C.HASHTAG_LINE))

    def test_sanitize_rejects_missing_item_name(self):
        raw = (
            "Lovely glow for any room tonight.\n\nSome Lamp | Pendant\n\n"
            + _long_body("Some Lamp")
        )
        self.assertEqual(C.sanitize_caption(raw, "Aurelia Chandelier"), "")

    def test_sanitize_rejects_short_text(self):
        raw = "Aurelia Chandelier | Chandelier\n\nNice glow."
        out = C.sanitize_caption(raw, "Aurelia Chandelier")
        self.assertEqual(out, "")

    def test_sanitize_rejects_empty(self):
        self.assertEqual(C.sanitize_caption("", "Aurelia Chandelier"), "")
        self.assertEqual(C.sanitize_caption(None, "Aurelia Chandelier"), "")


class CaptionPromptTest(unittest.TestCase):
    def test_instruction_mentions_item_and_constants(self):
        instruction = C.build_caption_instruction(
            "Aurelia Chandelier", "Chandelier", "chandeliers",
        )
        self.assertIn("Aurelia Chandelier", instruction)
        self.assertIn("Chandelier", instruction)
        self.assertIn(C.CONTACT_BLOCK, instruction)
        self.assertIn(C.HASHTAG_LINE, instruction)


class GenerateCaptionTest(unittest.TestCase):
    def test_success_returns_cleaned_caption(self):
        fal = MagicMock()
        fal.generate_vision_prompt.return_value = _valid_raw()
        out, used_fallback = C.generate_caption(
            fal, "Aurelia Chandelier", "Chandelier",
            ["https://example.com/room.jpg"], "chandeliers",
        )
        self.assertFalse(used_fallback)
        self.assertIn("Aurelia Chandelier | Chandelier", out)
        fal.generate_vision_prompt.assert_called_once()

    def test_failure_returns_fallback_never_raises(self):
        fal = MagicMock()
        fal.generate_vision_prompt.side_effect = RuntimeError("boom")
        out, used_fallback = C.generate_caption(
            fal, "Aurelia Chandelier", "Chandelier",
            ["https://example.com/room.jpg"],
        )
        self.assertTrue(used_fallback)
        self.assertIn("Aurelia Chandelier | Chandelier", out)
        self.assertIn("Inquire now!", out)

    def test_unusable_reply_returns_fallback(self):
        fal = MagicMock()
        fal.generate_vision_prompt.return_value = "too short"
        out, used_fallback = C.generate_caption(
            fal, "Aurelia Chandelier", "Chandelier", [],
        )
        self.assertTrue(used_fallback)
        self.assertIn("Aurelia Chandelier", out)

    def test_none_client_returns_fallback(self):
        out, used_fallback = C.generate_caption(None, "Aurelia Chandelier")
        self.assertTrue(used_fallback)
        self.assertTrue(out.strip())


class PipelineWiringTest(unittest.TestCase):
    """VST wiring uses the shared helper. Captions are reels/feeds-only (2026-10-26)."""

    def test_vst_field_alias_and_shared_helper(self):
        import inspect

        import generate_virtual_staging_reel_pipeline as vst

        self.assertEqual(vst.FIELD_CAPTION, C.CAPTION_FIELD)
        self.assertEqual(vst.FIELD_CAPTION, "Caption Generated")
        src = inspect.getsource(vst.phase7_assemble_final_reel)
        self.assertIn("generate_caption", src)
        self.assertNotIn("cap_prompt", src)


if __name__ == "__main__":
    unittest.main()

