"""Unit tests for the Visual QA & Self-Healing Feed Engine."""

import json
import unittest
from unittest.mock import MagicMock, patch

from content_automation.feed_qa import (
    QASlotTarget,
    QASlotVerdict,
    STATUS_DONE,
    STATUS_FOR_REVIEW,
    inspect_single_slot,
    load_qa_skills,
    parse_claude_qa_json,
    run_self_healing_feed_qa,
)


class TestFeedBlendQA(unittest.TestCase):
    """Test suite for feed_qa module."""

    def test_load_qa_skills(self):
        """Verify skills load correctly with and without chandelier rules."""
        skill_generic = load_qa_skills(is_chandelier=False)
        self.assertIn("Visual QA", skill_generic)
        self.assertIn("canopy", skill_generic.lower())

        skill_chand = load_qa_skills(is_chandelier=True)
        self.assertIn("CHANDELIER", skill_chand.upper())
        self.assertGreater(len(skill_chand), len(skill_generic))

    def test_parse_claude_qa_json_markdown_wrapped(self):
        """Verify parsing of markdown fenced JSON responses."""
        raw = """```json
{
  "verdict": "PASS",
  "defects_detected": [],
  "reason": "Flush canopy and realistic scale.",
  "correction_instruction": ""
}
```"""
        parsed = parse_claude_qa_json(raw)
        self.assertEqual(parsed["verdict"], "PASS")
        self.assertEqual(parsed["defects_detected"], [])
        self.assertEqual(parsed["reason"], "Flush canopy and realistic scale.")

    def test_parse_claude_qa_json_failure(self):
        """Verify parsing of defect reports."""
        raw = """{
  "verdict": "FAIL",
  "defects_detected": ["LIVING_ROOM_OVERSIZING", "CEILING_CANOPY_MOUNT"],
  "reason": "Chandelier canopy is floating and fixture is oversized.",
  "correction_instruction": "Scale down by 25% and mount flush to ceiling."
}"""
        parsed = parse_claude_qa_json(raw)
        self.assertEqual(parsed["verdict"], "FAIL")
        self.assertIn("LIVING_ROOM_OVERSIZING", parsed["defects_detected"])
        self.assertEqual(parsed["correction_instruction"], "Scale down by 25% and mount flush to ceiling.")

    def test_run_self_healing_feed_qa_all_pass(self):
        """Test case where all slots pass in Round 1 with zero retries."""
        mock_fal = MagicMock()
        mock_fal.analyze_image.return_value = json.dumps({
            "verdict": "PASS",
            "defects_detected": [],
            "reason": "Realistic blend.",
            "correction_instruction": ""
        })

        mock_airtable = MagicMock()
        mock_reblend = MagicMock()

        slots = [
            QASlotTarget(
                slot_index=2,
                slot_label="Modern Bedroom",
                item_name="Pendant Light",
                category="pendant_lights",
                room_type="modern bedroom",
                image_url="https://example.com/blend2.jpg",
                attachment_field="Blended Image2",
            ),
            QASlotTarget(
                slot_index=5,
                slot_label="Modern Living Room",
                item_name="Zygadlo Chandelier",
                category="chandeliers",
                room_type="modern living room",
                image_url="https://example.com/blend5.jpg",
                attachment_field="Blended Image5",
            ),
        ]

        result = run_self_healing_feed_qa(
            mock_fal,
            mock_airtable,
            "recTEST123",
            slots,
            reblend_fn=mock_reblend,
            execute=True,
            status_done_val="Done",
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.final_status, "Done")
        self.assertEqual(len(result.retried_slots), 0)
        mock_reblend.assert_not_called()
        mock_airtable.update_record.assert_called_once_with(
            "recTEST123",
            {"Status": "Done", "Blend Review Notes": result.review_notes}
        )

    def test_run_self_healing_feed_qa_slot_healed_on_retry(self):
        """Test case where Slot 5 fails Round 1, reblends, and passes Round 2."""
        mock_fal = MagicMock()
        # Call 1: Slot 2 passes
        # Call 2: Slot 5 fails
        # Call 3: Slot 5 passes on re-inspection
        mock_fal.analyze_image.side_effect = [
            json.dumps({"verdict": "PASS", "defects_detected": [], "reason": "Good bedroom pendant."}),
            json.dumps({
                "verdict": "FAIL",
                "defects_detected": ["LIVING_ROOM_OVERSIZING"],
                "reason": "Chandelier too large for living room.",
                "correction_instruction": "Scale down by 25%."
            }),
            json.dumps({"verdict": "PASS", "defects_detected": [], "reason": "Perfect scale and mount on retry."}),
        ]

        mock_airtable = MagicMock()
        mock_reblend = MagicMock(return_value="https://example.com/blend5_retry.jpg")

        slots = [
            QASlotTarget(
                slot_index=2,
                slot_label="Modern Bedroom",
                item_name="Pendant Light",
                category="pendant_lights",
                room_type="modern bedroom",
                image_url="https://example.com/blend2.jpg",
                attachment_field="Blended Image2",
            ),
            QASlotTarget(
                slot_index=5,
                slot_label="Modern Living Room",
                item_name="Zygadlo Chandelier",
                category="chandeliers",
                room_type="modern living room",
                image_url="https://example.com/blend5.jpg",
                attachment_field="Blended Image5",
            ),
        ]

        result = run_self_healing_feed_qa(
            mock_fal,
            mock_airtable,
            "recTEST456",
            slots,
            reblend_fn=mock_reblend,
            execute=True,
            status_done_val="Done",
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.final_status, "Done")
        self.assertEqual(result.retried_slots, [5])
        mock_reblend.assert_called_once()
        self.assertIn("healed on retry", result.review_notes)
        mock_airtable.update_record.assert_called_once_with(
            "recTEST456",
            {"Status": "Done", "Blend Review Notes": result.review_notes}
        )

    def test_run_self_healing_feed_qa_persists_failure_after_retry(self):
        """Test case where Slot 5 fails Round 1 AND fails Round 2 -> status becomes 'For Review'."""
        mock_fal = MagicMock()
        mock_fal.analyze_image.side_effect = [
            json.dumps({"verdict": "PASS", "defects_detected": [], "reason": "Pass."}),
            json.dumps({
                "verdict": "FAIL",
                "defects_detected": ["CEILING_CANOPY_MOUNT"],
                "reason": "Severed wire.",
                "correction_instruction": "Connect canopy."
            }),
            json.dumps({
                "verdict": "FAIL",
                "defects_detected": ["CEILING_CANOPY_MOUNT"],
                "reason": "Still severed after retry."
            }),
        ]

        mock_airtable = MagicMock()
        mock_reblend = MagicMock(return_value="https://example.com/blend5_retry2.jpg")

        slots = [
            QASlotTarget(
                slot_index=2,
                slot_label="Modern Bedroom",
                item_name="Pendant Light",
                category="pendant_lights",
                room_type="modern bedroom",
                image_url="https://example.com/blend2.jpg",
                attachment_field="Blended Image2",
            ),
            QASlotTarget(
                slot_index=5,
                slot_label="Modern Living Room",
                item_name="Zygadlo Chandelier",
                category="chandeliers",
                room_type="modern living room",
                image_url="https://example.com/blend5.jpg",
                attachment_field="Blended Image5",
            ),
        ]

        result = run_self_healing_feed_qa(
            mock_fal,
            mock_airtable,
            "recTEST789",
            slots,
            reblend_fn=mock_reblend,
            execute=True,
            status_done_val="Done",
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.final_status, STATUS_FOR_REVIEW)
        self.assertEqual(result.retried_slots, [5])
        self.assertIn("failed after 1 retry", result.review_notes)
        mock_airtable.update_record.assert_called_once_with(
            "recTEST789",
            {"Status": STATUS_FOR_REVIEW, "Blend Review Notes": result.review_notes}
        )


    def test_run_self_healing_feed_qa_tips_and_edu_chandelier_three_slots(self):
        """Test Tips & Edu Feed 3-slot chandelier workflow with self-healing retry."""
        mock_fal = MagicMock()
        mock_fal.analyze_image.side_effect = [
            # Slot 1: Pass
            json.dumps({"verdict": "PASS", "defects_detected": [], "reason": "Good chandelier mount.", "correction_instruction": ""}),
            # Slot 2: Fail (Canopy disconnected)
            json.dumps({
                "verdict": "FAIL",
                "defects_detected": ["CEILING_CANOPY_MOUNT"],
                "reason": "Chandelier canopy is severed from ceiling.",
                "correction_instruction": "Mount canopy flush to ceiling with visible suspension wire."
            }),
            # Slot 3: Pass
            json.dumps({"verdict": "PASS", "defects_detected": [], "reason": "Proper scale and mount.", "correction_instruction": ""}),
            # Slot 2 (Retry): Pass!
            json.dumps({"verdict": "PASS", "defects_detected": [], "reason": "Canopy is now flush and anchored.", "correction_instruction": ""}),
        ]

        mock_airtable = MagicMock()
        mock_reblend = MagicMock(return_value="https://example.com/tne_blend2_fixed.jpg")

        slots = [
            QASlotTarget(
                slot_index=1,
                slot_label="Chandelier 1",
                item_name="Nordic Minimalist Chandelier",
                category="chandeliers",
                room_type="modern interior",
                image_url="https://example.com/tne_blend1.jpg",
                attachment_field="Tips and Edu Blended",
                blending_prompt="Modern chandelier hanging in dining room",
            ),
            QASlotTarget(
                slot_index=2,
                slot_label="Chandelier 2",
                item_name="Sputnik Brass Chandelier",
                category="chandeliers",
                room_type="modern interior",
                image_url="https://example.com/tne_blend2.jpg",
                attachment_field="Tips and Edu Blended",
                blending_prompt="Brass sputnik chandelier in living room",
            ),
            QASlotTarget(
                slot_index=3,
                slot_label="Chandelier 3",
                item_name="Linear Glass Chandelier",
                category="chandeliers",
                room_type="modern interior",
                image_url="https://example.com/tne_blend3.jpg",
                attachment_field="Tips and Edu Blended",
                blending_prompt="Linear glass chandelier above kitchen island",
            ),
        ]

        status_interior_attached = "Already attached a room Interior"

        result = run_self_healing_feed_qa(
            mock_fal,
            mock_airtable,
            "recTNE999",
            slots,
            reblend_fn=mock_reblend,
            execute=True,
            status_done_val=status_interior_attached,
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.final_status, status_interior_attached)
        self.assertEqual(result.retried_slots, [2])
        mock_reblend.assert_called_once()
        self.assertIn("Slot 2", result.review_notes)
        self.assertIn("healed on retry", result.review_notes)
        mock_airtable.update_record.assert_called_once_with(
            "recTNE999",
            {"Status": status_interior_attached, "Blend Review Notes": result.review_notes}
        )


if __name__ == "__main__":
    unittest.main()
