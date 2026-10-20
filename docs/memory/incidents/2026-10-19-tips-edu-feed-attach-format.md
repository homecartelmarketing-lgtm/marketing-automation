---
date: 2026-10-19
pipeline: Tips & Educational Feed
status: resolved
---

# Tips & Edu Feed: tips attached to wrong photo + raw item-name stamping

## Symptom
Phase 6 tips/numerals landed on the wrong slot photo (thumbnail included in slicing, `[-3:]` order-dependent, silent fallback to untagged blends); YOLO tags stamped raw `A | B` pipe strings, variant suffixes (`Keyes I`), or `rec…` IDs when name fields were empty.

## Fix
Slot-config field resolution with space variants; fail-closed on empty names; `normalize_tips_edu_tag`; tagged carousel cleared + branded thumbnail prepended; `select_tagged_blends_for_layout` with thumbnail exclusion; hardened slot-sort regex; Phase 6 refuses untagged fallback (FM).

## Verification
`python -m unittest discover tests -p test_tips_edu_feed_attach_format.py` (6 tests) + `test_tips_edu_feed_failure_status.py` (9 tests) green; full `python -m unittest discover tests` green.
