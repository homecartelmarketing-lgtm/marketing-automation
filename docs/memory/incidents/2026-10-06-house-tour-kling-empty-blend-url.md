# 2026-10-06 — House Tour Phase 5 failed: "slot 2 has no blended image"

## Symptom

House Tour run failed at Phase 5 with
`Kling image-to-video failed: slot 2 has no blended image to animate with Kling`,
even though the live log showed all 4 Phase-4 blends + YOLO tags succeeding.
Row was stamped `Generation Failed Via Kling`.

## Root cause

`phase4_blends.blend_slot()` uploaded each clean blend to Airtable but never
wrote the URL back into the local `fields` dict, which `process_row()` had
fetched **before** Phase 4 ran. `phase5_kling()` reads blend URLs from that
same dict, so it saw zero blends for **every** slot; the thread pool just
surfaced slot 2's future first, making the message misleading.

Secondary contributor: Phase 5 passed expiring Airtable CDN URLs straight to
Kling as `image_url`. Per fal.ai files docs, some hosts block or rate-limit
bot-like fetching — fal-storage upload is the reliable path.

## Fix

- `blend_slot()` returns `(slot, still, blend_url)`; the main thread writes
  `fields[Blended ImageN] = [{"url": url}]` after the pool finishes.
- `phase5_kling()` merges a fresh record fetch for blend fields on entry
  (resume-after-crash safety).
- Phase 4 reuse is Airtable-attachment-only (the old tempdir-file check could
  never hit, so `--record-id` reruns needlessly re-blended).
- Phase 5 stages each blend via `FalClient.upload_file()` and hands Kling the
  fal URL, falling back to the Airtable URL if staging fails.
- Regression tests: Phase-4→5 handoff, resume merge, fal-URL assertion,
  upload-fallback assertion (`tests/test_house_tour_kling.py`).

## Recovery

Blends were safe in Airtable, so the failed row is salvageable without
re-scraping: `python run_house_tour_reel.py --record-id <rec_id>`
(explicit-record exception to the fresh-row rule).
