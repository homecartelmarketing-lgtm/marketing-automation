"""Central Visual QA & Self-Healing Engine for Feed Blended Images.

Uses Claude Sonnet 5 Vision via Fal AI (openrouter/router/vision) to evaluate
blended lifestyle room interiors against real-world production QA standards
defined in `.agents/skills/feed-blended-qa/SKILL.md` and
`.agents/skills/chandelier-blend-qa/SKILL.md`.

Supports a 1-time context-aware self-healing retry:
If a slot fails Round 1 inspection, Claude provides an explicit correction directive
(e.g., 'mount canopy flush to ceiling, reduce diameter by 25%'). The engine triggers
a 1-time corrective re-blend of ONLY that slot, re-stamps tags and logos, and re-evaluates.
If it passes, the row sets to 'Done' (preserving all photos). If it still fails,
it sets to 'For Review' and saves the critique to 'Blend Review Notes'.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from content_automation.fal_client import FalClient
from content_automation.scraping.airtable import ScrapeAirtableClient

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FEED_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "feed-blended-qa" / "SKILL.md"
CHANDELIER_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "chandelier-blend-qa" / "SKILL.md"

STATUS_DONE = "Done"
STATUS_FOR_REVIEW = "For Review"
STATUS_COMPLETE = "Complete"
FIELD_STATUS = "Status"
FIELD_REVIEW_NOTES = "Blend Review Notes"


@dataclass
class QASlotTarget:
    """Represents a single blended image slot to be inspected."""
    slot_index: int
    slot_label: str
    item_name: str
    category: str
    room_type: str
    image_url: str
    attachment_field: str
    blending_prompt: str = ""
    # Optional metadata for re-blending
    interior_url: str = ""
    product_url: str = ""
    measurement: str = ""
    aspect_ratio: str = "4:5"


@dataclass
class QASlotVerdict:
    """Result of inspecting a single slot."""
    slot_index: int
    slot_label: str
    item_name: str
    verdict: str  # "PASS" | "FAIL"
    defects_detected: list[str] = field(default_factory=list)
    reason: str = ""
    correction_instruction: str = ""
    attempt: int = 1
    image_url_inspected: str = ""


@dataclass
class OverallQAResult:
    """Aggregate result across all inspected slots in a record."""
    record_id: str
    passed: bool
    final_status: str  # "Done" | "For Review"
    slot_verdicts: list[QASlotVerdict] = field(default_factory=list)
    retried_slots: list[int] = field(default_factory=list)
    review_notes: str = ""


def load_qa_skills(is_chandelier: bool = False) -> str:
    """Load the markdown QA rules from disk.

    Combines feed-blended-qa rules with chandelier-specific deep-dive rules if relevant.
    """
    rules: list[str] = []
    if FEED_SKILL_PATH.is_file():
        rules.append(FEED_SKILL_PATH.read_text(encoding="utf-8"))
    else:
        logger.warning(f"Feed QA skill not found at {FEED_SKILL_PATH}")

    if is_chandelier and CHANDELIER_SKILL_PATH.is_file():
        rules.append("\n---\n# SPECIFIC CHANDELIER INSPECTION RULES\n")
        rules.append(CHANDELIER_SKILL_PATH.read_text(encoding="utf-8"))

    return "\n\n".join(rules)


def parse_claude_qa_json(raw_text: str) -> dict[str, Any]:
    """Parse JSON response from Claude Sonnet 5, stripping markdown codeblocks."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Try regex match for outermost JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    # Fallback structure
    return {
        "verdict": "FAIL" if "fail" in cleaned.lower() else "PASS",
        "defects_detected": ["PARSE_ERROR"],
        "reason": cleaned[:300],
        "correction_instruction": "Ensure fixture is mounted flush and proportioned realistically to the room."
    }


def inspect_single_slot(
    fal: FalClient,
    target: QASlotTarget,
    *,
    attempt: int = 1,
) -> QASlotVerdict:
    """Inspect a single blended slot using Claude Sonnet 5 Vision."""
    is_chand = "chandelier" in target.category.lower() or "chandelier" in target.item_name.lower()
    skill_content = load_qa_skills(is_chandelier=is_chand)

    prompt = f"""{skill_content}

---
CRITICAL QA INSPECTION TASK:
You are inspecting a blended product image for HomeCartel marketing content.
Slot: {target.slot_label} (Slot #{target.slot_index})
Room Type: {target.room_type}
Product Item Name: '{target.item_name}'
Category: '{target.category}'
Attempt Number: {attempt}

Carefully evaluate the image at the provided URL against the inspection rules.
- If Chandelier: verify ceiling canopy mount (no floating or severed cords) and check room scale.
- If Pendant/Linear: verify centered alignment and realistic suspension.
- If Floor/Table Lamp: verify ground contact shadows on floor or furniture.
- If Wall Light: verify flush wall mounting.
- Verify product identity: does the blended fixture match the product type and name?

Respond ONLY in valid JSON format:
{{
  "verdict": "PASS" or "FAIL",
  "defects_detected": ["DEFECT_CODE_1", "DEFECT_CODE_2"],
  "reason": "Concise 1-2 sentence explanation of why it passes or what is defective",
  "correction_instruction": "Actionable, precise design directive on how to fix this defect in a re-blend (or empty string if PASS)"
}}
"""
    try:
        raw_response = fal.analyze_image(
            prompt=prompt,
            image_urls=[target.image_url],
            model="anthropic/claude-sonnet-5",
            endpoint="openrouter/router/vision",
        )
        parsed = parse_claude_qa_json(raw_response)
        verdict = str(parsed.get("verdict") or "FAIL").strip().upper()
        if verdict not in ("PASS", "FAIL"):
            verdict = "FAIL"

        defects = parsed.get("defects_detected") or []
        if isinstance(defects, str):
            defects = [defects]

        reason = str(parsed.get("reason") or "").strip()
        correction = str(parsed.get("correction_instruction") or "").strip()

        return QASlotVerdict(
            slot_index=target.slot_index,
            slot_label=target.slot_label,
            item_name=target.item_name,
            verdict=verdict,
            defects_detected=list(defects),
            reason=reason,
            correction_instruction=correction,
            attempt=attempt,
            image_url_inspected=target.image_url,
        )
    except Exception as err:
        logger.error(f"Error inspecting slot {target.slot_index}: {err}")
        return QASlotVerdict(
            slot_index=target.slot_index,
            slot_label=target.slot_label,
            item_name=target.item_name,
            verdict="FAIL",
            defects_detected=["AI_API_ERROR"],
            reason=f"Inspection failed with error: {str(err)[:200]}",
            correction_instruction="Verify canopy mount and scale.",
            attempt=attempt,
            image_url_inspected=target.image_url,
        )


def ensure_qa_airtable_fields(airtable: ScrapeAirtableClient) -> None:
    """Ensure Status and Blend Review Notes exist in target table."""
    try:
        airtable.ensure_fields({
            FIELD_STATUS: "singleSelect",
            FIELD_REVIEW_NOTES: "multilineText",
        })
    except Exception as err:
        logger.warning(f"Could not ensure QA fields in Airtable: {err}")


def run_self_healing_feed_qa(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    slots: list[QASlotTarget],
    *,
    reblend_fn: Callable[[QASlotTarget, str], str] | None = None,
    execute: bool = True,
    status_done_val: str = STATUS_DONE,
) -> OverallQAResult:
    """Execute complete Visual QA with 1-time context-aware self-healing retry.

    Parameters:
    - fal: FalClient instance
    - airtable: ScrapeAirtableClient instance
    - record_id: Airtable record ID
    - slots: List of slots to inspect (e.g. Slots 2, 3, 4, 5)
    - reblend_fn: Callable that accepts (target, correction_directive) and returns new blended image URL
    - execute: Whether to write changes to Airtable
    - status_done_val: Status string on pass (e.g. "Done" or "Complete")
    """
    if execute:
        ensure_qa_airtable_fields(airtable)

    print(f"\n[PHASE 6: VISUAL QA] Claude Sonnet 5 Inspection for Record: {record_id}")
    print(f"Inspecting {len(slots)} blended slot(s)...")

    # Round 1: Inspect all slots
    round_1_verdicts: list[QASlotVerdict] = []
    failed_slots: list[QASlotTarget] = []

    for target in slots:
        print(f"  [QA REVIEW] Inspecting Slot {target.slot_index} ({target.slot_label} - {target.item_name})...")
        verdict = inspect_single_slot(fal, target, attempt=1)
        round_1_verdicts.append(verdict)
        if verdict.verdict == "PASS":
            print(f"    -> [PASS] Slot {target.slot_index}: {verdict.reason}")
        else:
            print(f"    -> [FAIL] Slot {target.slot_index}: {verdict.defects_detected} - {verdict.reason}")
            failed_slots.append(target)

    retried_slot_indices: list[int] = []
    final_verdicts: dict[int, QASlotVerdict] = {v.slot_index: v for v in round_1_verdicts}

    # Self-Healing Retry Loop (1-Time Max for each failed slot)
    if failed_slots and reblend_fn is not None:
        print(f"\n[PHASE 6: AUTO-HEALING] Detected {len(failed_slots)} defective slot(s). Attempting 1-time corrective re-blend...")
        for failed_target in failed_slots:
            idx = failed_target.slot_index
            v1 = final_verdicts[idx]
            correction = v1.correction_instruction or "Ensure fixture is mounted flush and realistic to room scale."
            print(f"\n  [QA HEAL] Re-blending Slot {idx} ({failed_target.slot_label})...")
            print(f"    Directive: {correction}")

            try:
                # Invoke callback to re-blend and re-upload to Airtable
                new_image_url = reblend_fn(failed_target, correction)
                retried_slot_indices.append(idx)

                # Re-inspect new image URL
                retried_target = QASlotTarget(
                    slot_index=failed_target.slot_index,
                    slot_label=failed_target.slot_label,
                    item_name=failed_target.item_name,
                    category=failed_target.category,
                    room_type=failed_target.room_type,
                    image_url=new_image_url,
                    attachment_field=failed_target.attachment_field,
                    blending_prompt=failed_target.blending_prompt,
                )
                print(f"    [QA RE-CHECK] Inspecting retried Slot {idx}...")
                v2 = inspect_single_slot(fal, retried_target, attempt=2)
                final_verdicts[idx] = v2

                if v2.verdict == "PASS":
                    print(f"    -> [HEALED] Slot {idx} passed Round 2! Reason: {v2.reason}")
                else:
                    print(f"    -> [STILL FAILED] Slot {idx} failed Round 2: {v2.defects_detected} - {v2.reason}")
            except Exception as retry_err:
                logger.error(f"Error during re-blend of slot {idx}: {retry_err}")
                print(f"    -> [RETRY ERROR] Slot {idx}: {retry_err}")

    # Determine overall status
    all_passed = all(v.verdict == "PASS" for v in final_verdicts.values())
    final_status = status_done_val if all_passed else STATUS_FOR_REVIEW

    # Build review notes
    notes_lines: list[str] = []
    for idx, v in sorted(final_verdicts.items()):
        status_tag = "PASS" if v.verdict == "PASS" else "FAIL"
        retry_tag = " (healed on retry)" if (idx in retried_slot_indices and v.verdict == "PASS") else (
            " (failed after 1 retry)" if idx in retried_slot_indices else ""
        )
        defects_str = f" [{', '.join(v.defects_detected)}]" if v.defects_detected else ""
        notes_lines.append(f"Slot {idx} ({v.slot_label} - {v.item_name}): {status_tag}{retry_tag}{defects_str} - {v.reason}")

    review_notes = "\n".join(notes_lines)

    print(f"\n[QA VERDICT] Record {record_id} Overall Result: {'ALL SLOTS PASSED' if all_passed else 'DEFECTS DETECTED'}")
    print(f"  Target Status: '{final_status}'")
    if not all_passed:
        print(f"  Blend Review Notes:\n{review_notes}")

    if execute:
        update_payload: dict[str, Any] = {
            FIELD_STATUS: final_status,
            FIELD_REVIEW_NOTES: review_notes,
        }
        try:
            airtable.update_record(record_id, update_payload)
            print(f"  [OK] Airtable Record {record_id} updated with Status -> '{final_status}'")
        except Exception as upd_err:
            logger.error(f"Failed updating Airtable record {record_id}: {upd_err}")
            print(f"  [WARN] Could not update Airtable fields: {upd_err}")

    return OverallQAResult(
        record_id=record_id,
        passed=all_passed,
        final_status=final_status,
        slot_verdicts=list(final_verdicts.values()),
        retried_slots=retried_slot_indices,
        review_notes=review_notes,
    )
