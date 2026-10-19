---
date: 2026-10-15
pipeline: Tips & Educational Feed
status: resolved
---

# Tips & Educational Feed: Phase 5 & 6 Stale Banners, Audit Log Labels & Partial-Failure Status

## Context & Symptoms

Following the resolution of the Phase 5 `split_item_name` parameter issue, code inspection revealed two stale phase label discrepancies in [`run_tips_and_edu_feed.py`](../../run_tips_and_edu_feed.py):

1. **Stale Header Banner at Line 1957**:
   Directly above `def phase_5`, the comment banner read:
   `# PHASE 5: PROGRAMMATIC PIL LAYOUT COMPOSITING -> TIPS AND EDU FEEDS`
   However, `phase_5` actually executes YOLO-World item name tagging and thumbnail prepending into `Tips and Edu Blended Attach Item Name`.
2. **Orphaned Divider Rule at Line 2044**:
   Above `def phase_6`, a lone `# ════...` divider rule was left behind from a previous refactoring, lacking a phase title or closing rule.
3. **Mis-labeled Audit Log Entry at Line 2164**:
   Inside `def phase_6` (which attaches the 3 completed layout feed images with numerals and tips to `Tips and Edu Feeds`), the audit record logged:
   `"phase": "Phase 5: Programmatic PIL Layout Compositing"`
   This wrote `"Phase 5"` into `AUDIT_LOG_LAYOUT` instead of `"Phase 6"`.
4. **Mis-labeled Failure Log at Line 2183**:
   When `phase_6` partially failed, it printed:
   `[WARN] Phase 5 partially failed for record {record_id}.`
5. **Partial Failure Status Ambiguity (Line 2182)**:
   On partial failure, `phase_6` set the record status to `STATUS_INTERIOR_ATTACHED` ("Already attached a room Interior"), which is the exact status set by a successful `phase_5` run. This made a partially-failed Phase 6 indistinguishable from a completed Phase 5 by status alone.

## Root Cause

When YOLO-World Item Tagging was inserted as a standalone step, it became Phase 5, and the Programmatic PIL Layout Compositing was bumped to Phase 6. While runtime execution (`phase_5` then `phase_6`) executed in the correct order, the comment banners, orphaned dividers, and audit string literals inside the newly bumped `phase_6` were not updated.

## Resolution

1. **Phase 5 Banner**:
   Updated Line 1957 banner to:
   ```python
   # ══════════════════════════════════════════════════════════════════════════
   # PHASE 5: YOLO ITEM NAME TAGGING & CAROUSEL ASSEMBLY
   # ══════════════════════════════════════════════════════════════════════════
   ```
2. **Phase 6 Banner (Avoiding Doubled Rule)**:
   Replaced the orphaned divider line at Line 2044 directly with the complete 3-line banner for Phase 6, avoiding a stacked/doubled rule:
   ```python
   # ══════════════════════════════════════════════════════════════════════════
   # PHASE 6: PROGRAMMATIC PIL LAYOUT COMPOSITING -> TIPS AND EDU FEEDS
   # ══════════════════════════════════════════════════════════════════════════
   ```
3. **Audit Log Phase String**:
   Updated Line 2164 in `AUDIT_LOG_LAYOUT` to write:
   `"phase": "Phase 6: Programmatic PIL Layout Compositing"`
4. **Warning Output**:
   Updated Line 2183 warning output to:
   `print(f"[WARN] Phase 6 partially failed for record {record_id}.")`
5. **Typography Validation**:
   Confirmed that `Poppins-Regular` (196px) for the large numerals ("1", "2", "3") and `Poppins-Bold` (32px) for educational tips text is intentional per the Canva coordinate design.
6. **Status Routing on Partial Failures (FM Badge)**:
   Updated Phase 6 failure handling (`line 2184`) to set `STATUS_FOR_MANUAL = "For Manual"` instead of `STATUS_INTERIOR_ATTACHED`. This maps directly to the amber `FM` badge in the Studio UI, eliminating the blind spot where partially failed layout jobs masqueraded as Phase 5 successes.

## Verification

- `python -m py_compile run_tips_and_edu_feed.py` passed with exit code 0.
- `python -m unittest discover tests` passed all 469 test cases cleanly in ~29s.

## Follow-up

Partial failures in Phase 6 already went to `FM`, but a phase that **crashed** still left the row on `Processing`. That gap is closed in [[2026-10-15-tips-edu-feed-crash-leaves-row-processing]].
