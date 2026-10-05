---
date: 2026-10-05
pipeline: Moodboard Story, Tips & Edu Story
status: resolved
---

# Tag Line-2 fallback + Floor Lamp registry KeyError (2026-10-05)

**Incident.** Moodboard Story rows with an empty `Product Type` field rendered
the YOLO name pill with Line 1 only (e.g. `Trude Une` lost `Modern Floor Lamp`).
Separately, `run_moodboard_story.py --target floor_lamps` crashed with
`KeyError: 'floor_lamps_moodboard_story'` in
`provider_requirements()`.

**Diagnosis — two distinct root causes, one symptom family:**

1. **Bare-name handoff.** `AirtableClient.product_from_record` splits
   `"Trude Une | Modern Floor Lamp"` into bare `anchor.item_name` +
   `anchor.product_type`. Both story workflows re-split the bare name with only
   `fields["Product Type"]` (usually empty) as fallback, so Line 2 was lost.
2. **Missing registry entry.** `content_automation/config.py::WORKFLOWS` had the
   `floor_lamps_moodboard_story` key but `workflows/registry.py::WORKFLOW_CLASSES`
   did not, so `create_workflow()` raised. Docs already listed Floor Lamps
   (`tblBaNeiSZeYrUawW`, `MB-STORY-FL`) as supported.

**Resolution (2026-10-05):**

- New shared `content_automation/item_tagger.py::resolve_tag_names`: the anchor's
  own `product_type` heads the fallback chain, then `fields["Product Type"]`.
  `workflows/moodboard_story.py::resolve_item_tag_names` is a thin wrapper kept
  for existing imports; `tips_educational_story.py` calls the shared helper
  directly.
- Added `"floor_lamps_moodboard_story": MoodboardStoryWorkflow` to
  `WORKFLOW_CLASSES`.

**Tests:** `tests/test_moodboard_story_tag_names.py` (Trude Une bare-name case +
pipe-name case), `tests/test_workflow_registry_coverage.py` (every `WORKFLOWS`
key resolves; floor-lamp entry creates a workflow). No network calls.
