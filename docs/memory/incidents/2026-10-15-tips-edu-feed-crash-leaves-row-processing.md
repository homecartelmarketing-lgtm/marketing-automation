---
date: 2026-10-15
pipeline: Tips & Educational Feed
status: resolved
---

# Tips & Educational Feed: a crashed phase left the row on `Processing` forever

## Symptom

A Tips & Edu Feed run "looked finished" but a row stayed on `Processing`, counted as `P` on the Studio card, and nothing flagged it as failed. Example: Pendant `TNE-FEEDS-PE-16` (`recPvY8pWpqjtjOO6`) had 4 scraped products and only `Interior1` (no `Interior2/3`, no thumbnail, no prompts, no blends) while its status read `Processing`.

## Root cause

Every phase (2, 3, 4 and 6) sets `Processing` when it starts. `_run_single_phase` caught an exception, wrote the error log and re-raised, but never moved the row to another status, so the process died and the row kept the in-flight status. `phase_6` also called `_download` outside its per-slot `try`, so one expired Airtable attachment URL crashed the whole phase after `Processing` had been set.

## How it was diagnosed

- Read-only Airtable scan of the four Tips & Edu Feed tables: `CH-10` was `Complete` with 3 feed slides, `PE-16` was `Processing` with 1 interior. The row was not "done generating"; it had crashed in Phase 2.
- Repro of Phases 5-6 on `CH-9` (`--record-id`, no API spend): the child process exits with code 0 about a second after the "100% COMPLETE" line, so a hung process was ruled out. A stub-child test showed the Studio route flips to `completed` correctly.
- Compared with other pipelines, which already set `For Manual` on any exception (`generate_room_build_up_reel_pipeline.py`, `generate_christmas_banner_pipeline.py`).

## Fix

- `run_tips_and_edu_feed.py::_mark_for_manual_after_crash` is called from the `except` block of `_run_single_phase`. It sets `For Manual` (amber `FM` badge), is skipped in dry-run, and never raises, so the original error always surfaces.
- `phase_6` now downloads each blended photo inside its per-slot `try`, so a bad download fails that slot and the phase ends in the existing `FM` branch. The slot error is now logged as Phase 6 (it was mislabelled 5).
- Regression tests: `tests/test_tips_edu_feed_failure_status.py`.

## Related stale-numbering bugs found while fixing this

- `--phase` only accepted `1..5` (written when the pipeline had 5 phases, commit `ff16305`; `phase_6` arrived in `fb756e5` without updating argparse), so Phase 6 could not be run alone. `6` is now accepted.
- `_phase_for_record` returned `5` for "feed slides missing", but Phase 5 is YOLO tagging. It now returns `5` while `Tips and Edu Blended Attach Item Name` has fewer than 3 images, and `6` once it has them.
- `Tips and Edu Blended Attach Item Name` was missing from `_schema_fields()`, so preflight never created it. Only the Chandelier table had it; a Pendant, Floor Lamp or Cluster run would fail in Phase 5 when uploading to the missing field (Airtable `uploadAttachment` does not create fields). It is now part of the schema, so preflight creates it. An earlier note in this session claimed preflight already did; that was wrong.

## Retrying an `FM` row

Use the explicit developer exception: `python run_tips_and_edu_feed.py --target <target> --phase all --record-id <rec_id> --execute`. `FM` is a protected status, so the runner restarts at Phase 2 and each phase skips work already done (populated interiors, 3 blends, 3 feed slides). Un-targeted runs never pick the row up again.

Related: [[2026-10-15-tips-edu-feed-phase-5-6-labels-and-audit-sync]], [[2026-10-15-tips-edu-feed-phase-5-attributeerror-and-tips-stamping]].
