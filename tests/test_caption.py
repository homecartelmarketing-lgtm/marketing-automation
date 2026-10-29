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

    def test_flow_text_is_in_the_prompt(self):
        instruction = C.build_caption_instruction(
            "Aurelia Chandelier", "Chandelier", "", "One locked camera reveal.",
        )
        self.assertIn("One locked camera reveal.", instruction)
        self.assertNotIn("About this post", C.build_caption_instruction("A", "B"))


class GenerateCaptionTest(unittest.TestCase):
    def test_success_returns_cleaned_caption(self):
        fal = MagicMock()
        fal.generate_vision_prompt.return_value = _valid_raw()
        out = C.generate_caption(
            fal, "Aurelia Chandelier", "Chandelier",
            ["https://example.com/room.jpg"], "chandeliers", "Day to night.",
        )
        self.assertIn("Aurelia Chandelier | Chandelier", out)
        fal.generate_vision_prompt.assert_called_once()
        prompt = fal.generate_vision_prompt.call_args.kwargs["prompt"]
        self.assertIn("Day to night.", prompt)

    def test_failure_returns_blank_never_raises(self):
        fal = MagicMock()
        fal.generate_vision_prompt.side_effect = RuntimeError("boom")
        out = C.generate_caption(
            fal, "Aurelia Chandelier", "Chandelier", ["https://example.com/room.jpg"],
        )
        self.assertEqual(out, "")
        self.assertEqual(fal.generate_vision_prompt.call_count, 2)  # one retry

    def test_unusable_reply_retries_once_then_blank(self):
        fal = MagicMock()
        fal.generate_vision_prompt.return_value = "too short"
        self.assertEqual(C.generate_caption(fal, "Aurelia Chandelier", "Chandelier", []), "")
        self.assertEqual(fal.generate_vision_prompt.call_count, 2)

    def test_retry_recovers_from_first_bad_reply(self):
        fal = MagicMock()
        fal.generate_vision_prompt.side_effect = ["too short", _valid_raw()]
        out = C.generate_caption(fal, "Aurelia Chandelier", "Chandelier", [])
        self.assertIn("Aurelia Chandelier", out)

    def test_none_client_or_no_item_returns_blank(self):
        self.assertEqual(C.generate_caption(None, "Aurelia Chandelier"), "")
        self.assertEqual(C.generate_caption(MagicMock(), ""), "")

    def test_no_fallback_helpers_remain(self):
        self.assertFalse(hasattr(C, "fallback_caption"))


class WriteRowCaptionTest(unittest.TestCase):
    def _fal(self):
        fal = MagicMock()
        fal.generate_vision_prompt.return_value = _valid_raw()
        return fal

    def test_writes_caption_using_row_images(self):
        airtable = MagicMock()
        fal = self._fal()
        fields = {
            "Item Name1": "Aurelia Chandelier | Chandelier",
            "Blended Image": [{"url": "https://example.com/a.jpg"}],
        }
        out = C.write_row_caption(
            airtable, "rec1", fields, fal, "room_reveal_reel",
            image_fields=("Blended Image",),
        )
        self.assertIn("Aurelia Chandelier | Chandelier", out)
        airtable.update_record.assert_called_once_with("rec1", {C.CAPTION_FIELD: out})
        self.assertEqual(
            fal.generate_vision_prompt.call_args.kwargs["image_urls"],
            ["https://example.com/a.jpg"],
        )

    def test_rereads_row_when_fields_is_none(self):
        airtable = MagicMock()
        airtable.get_record.return_value = {"fields": {"Item Name": "Aurelia Chandelier"}}
        out = C.write_row_caption(airtable, "rec1", None, self._fal(), "tmen_reel")
        airtable.get_record.assert_called_once_with("rec1")
        self.assertTrue(out)

    def test_existing_caption_is_not_overwritten(self):
        airtable = MagicMock()
        fal = self._fal()
        fields = {C.CAPTION_FIELD: "Hand written", "Item Name": "Aurelia Chandelier"}
        out = C.write_row_caption(airtable, "rec1", fields, fal, "tmen_reel")
        self.assertEqual(out, "Hand written")
        fal.generate_vision_prompt.assert_not_called()
        airtable.update_record.assert_not_called()

    def test_blank_result_writes_nothing_and_never_raises(self):
        airtable = MagicMock()
        fal = MagicMock()
        fal.generate_vision_prompt.side_effect = RuntimeError("down")
        out = C.write_row_caption(
            airtable, "rec1", {"Item Name": "Aurelia Chandelier"}, fal, "tmen_reel",
        )
        self.assertEqual(out, "")
        airtable.update_record.assert_not_called()

    def test_airtable_write_failure_is_swallowed(self):
        airtable = MagicMock()
        airtable.update_record.side_effect = RuntimeError("422")
        out = C.write_row_caption(
            airtable, "rec1", {"Item Name": "Aurelia Chandelier"}, self._fal(), "tmen_reel",
        )
        self.assertEqual(out, "")

    def test_update_fn_replaces_the_airtable_write(self):
        sink = []
        out = C.write_row_caption(
            None, "rec1", {"Item Name": "Aurelia Chandelier"}, self._fal(), "moodboard_reel",
            update_fn=sink.append,
        )
        self.assertEqual(sink, [{C.CAPTION_FIELD: out}])

    def test_collect_image_urls(self):
        fields = {"A": [{"url": "https://x/1.jpg"}, {"url": "https://x/2.jpg"}], "B": "https://x/3.jpg"}
        self.assertEqual(
            C.collect_image_urls(fields, ("A", "B"), limit=3),
            ["https://x/1.jpg", "https://x/2.jpg", "https://x/3.jpg"],
        )


class PipelineWiringTest(unittest.TestCase):
    """VST wiring uses the shared helper. Captions are reels/feeds-only (2026-10-26)."""

    def test_vst_field_alias_and_shared_helper(self):
        import inspect

        import generate_virtual_staging_reel_pipeline as vst

        self.assertEqual(vst.FIELD_CAPTION, C.CAPTION_FIELD)
        self.assertEqual(vst.FIELD_CAPTION, "Caption Generated")
        src = inspect.getsource(vst.phase7_assemble_final_reel)
        self.assertIn("write_row_caption", src)
        self.assertNotIn("cap_prompt", src)


if __name__ == "__main__":
    unittest.main()

