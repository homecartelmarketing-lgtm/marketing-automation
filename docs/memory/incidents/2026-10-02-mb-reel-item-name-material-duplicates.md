---
date: 2026-10-02
pipeline: Moodboard Reel
status: resolved
---

# MB Reel: no item name + duplicate material names (2026-10-02)

**Incident.** Moodboard Reel runs shipped with no (real) item name on the
blended slides and the same material word repeating across slots.

**Root causes in `generate_moodboard_reel_pipeline.py`:**

1. Phase 3 looked up names as `Item Name{slot}` / `SKU{slot}` with a
   0-based slot. That matches neither Airtable scheme (`Item Name`,
   `Item Name2`.. nor `Item Name1`..`Item Name4`): slot 0 fell back to the
   placeholder "Furniture Item 0", and later slots were shifted onto the
   previous product's name. YOLO category was also hard-coded to
   `chandeliers` for every fixture.
2. `generate_unique_material_words()` compared raw Claude words, so
   `BRASS,` and `Brass` passed as different words and were saved as
   duplicates. Its result was also keyed 0..n-1 while the caller indexed
   by actual slot, and words already saved for other slots of the row
   were not considered on a partial re-run.
3. Rebuilding a reel with `--phase 5` loaded only `Moodboard Blended`,
   never `Blended Image with Name text`, so the reel lost the name tags
   even on rows that had them. Re-runs also accumulated stale tagged
   attachments because that field was never cleared.

**Fix.** Added `get_item_name_for_slot()` (both naming schemes, then
Furniture Item attachment filename, then SKU; never a placeholder) and
used it in Phases 2.5 and 3, passing the real category to the tagger.
Material words are normalized before the uniqueness check, seeded with
existing `Texture1..12` words for slots not being regenerated, and
returned keyed by actual slot. Phase 5 standalone now loads the tagged
blends, tagged filenames are `blended_tagged_mb<slot+1>.jpg`, and the
tagged field is cleared before re-upload. Same changes mirrored to the
`python-content-script/` copy of the pipeline.

**Tests.** `tests/test_moodboard_reel_names.py` covers both item-name
schemes, placeholder avoidance, tagged-filename parsing, punctuation /
partial-rerun material duplicates, and a mocked Phase 3 run asserting
each slot is tagged with its own name. Verification was static
(`py_compile` + mocked unit tests); first live proof is the next Studio
MB Reel run. Pre-fix rows were not re-run or re-stamped.
