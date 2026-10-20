# Decision: Virtual Staging Reel Upload Mode & Kling 3.0 Pro Queue (2026-10-20)

## Context

The Virtual Staging Reel pipeline generates a 12.5s vertical video reel capturing an empty room being progressively furnished with furniture, rugs, decor, and a HomeCartel lighting fixture. Originally, the pipeline was synthetic-only (Krea interior generation followed by Claude Vision stripping + Nano Banana Pro empty room generation). The marketing team requested an **Upload Mode** in the Studio to allow uploading actual empty property photos for custom staging.

---

## What Changed

1. **Upload Source Mode (`--source upload`)**:
   - Added support for `--source {auto,upload}` and `--empty-room-url URL` to `generate_virtual_staging_reel_pipeline.py`.
   - In Upload mode, Phase 2 ingests the user-uploaded empty room photo (center-cropped to 9:16 and uploaded to Fal storage) instead of calling Krea.
   - Phase 3 generates a staging prompt tailored to furnishing the specific architecture of the uploaded room.
   - Phase 4 blends the HomeCartel chandelier plus staged furniture into the empty room using Fal Nano Banana Pro, cropped to 9:16 to guarantee framing matches the start frame.
   - Phase 5 (AI emptying/stripping) is skipped (`[PHASE 5/7] Empty-room stripping SKIPPED (source=upload)`).
   - Phase 6 generates a 10s video animation from empty room (start) to fully staged room (end) using Kling 3.0 Pro via Fal Queue.

2. **Fal Queue Integration with Resume**:
   - Fal client gained `submit_queue`, `poll_queue_urls`, and `ensure_fal_url`.
   - Kling video generation in Phase 6 records `{"request_id", "status_url", "response_url"}` in Airtable field `Kling Queue Request`.
   - Resuming an incomplete record polls the existing queue request without re-submitting, preventing duplicate billing.

3. **Audio-Off Cost Optimization**:
   - Explicitly passed `generate_audio: false` to Kling 3.0 Pro in both Auto and Upload modes, reducing billing from $0.168/s ($1.68) to $0.112/s ($1.12 per 10s video).

4. **Studio Control UI & Queue**:
   - Added `POST /api/virtual-staging-reel/upload-empty-room` to validate, 9:16 center-crop, and upload images to Fal storage.
   - Added `POST /api/virtual-staging-reel/kling-prompt` for customizing the Kling animation prompt.
   - Updated `POST /api/virtual-staging-reel/run` and queue dispatcher to validate and forward `source` and `empty_room_url`.
   - Queue manager updated to factor `empty_room_url` into dedup logic so multiple uploads can be queued.
   - Studio `RunConfirmModal` enhanced with source mode toggle (Auto vs Upload), drag-and-drop file upload with 9:16 preview, locked batch size 1 ("1 upload = 1 reel"), and Kling prompt editor.

---

## Files Touched

| Layer | File | Description |
| :--- | :--- | :--- |
| Fal Client | `content_automation/fal_client.py` | `submit_queue`, `poll_queue_urls`, `ensure_fal_url` (with uuid temp and cleanup), and `generate_kling_video(generate_audio=...)` |
| Image Helper | `content_automation/media.py` | `crop_to_reel` 9:16 center-crop and resize helper with EXIF handling |
| Generator | `generate_virtual_staging_reel_pipeline.py` | `--source`, `--empty-room-url`, upload Phase 2, upload Phase 3 prompt, Phase 4 blend + 9:16 crop, Phase 5 skip, Phase 6 locked Kling queue + resume |
| Route | `UI Control/routes/virtual_staging_reel.py` | `upload-empty-room`, `kling-prompt`, updated `run` endpoint, mode-specific phase labels |
| Queue | `UI Control/routes/queue_manager.py` | Store and forward `source` and `empty_room_url`; skip fixture dedup when `empty_room_url` is provided |
| Studio Config | `UI Control/src/app/constants/pipelines.ts` | `supportsEmptyRoomUpload`, `klingPromptEndpoint`, `phaseSummaryUpload` |
| Studio UI | `UI Control/src/app/components/planning/RunConfirmModal.tsx` | Mode toggle, file drop zone, 9:16 preview, Kling prompt pencil, batch size 1 lock |
| Studio Hooks | `UI Control/src/app/hooks/usePipelineRunner.ts` | Forward `source` and `empty_room_url` to `/api/queue/enqueue` |
| Studio Bundle | `UI Control/dist/*` | Rebuilt production assets |
| Tests | `tests/test_virtual_staging_upload.py`, `tests/test_queue_forwarding.py` | 16 new automated unit tests |
| Docs & Env | `docs/reels/VIRTUAL_STAGING_REEL.md`, `docs/UI_CONTROL_CONFIG.md`, `AGENTS.md`, `UI Control/README.md`, `.env.example`, `docs/plans/virtual-staging-upload-mode.md` | Comprehensive documentation updates |

---

## New Airtable Fields & Status

- **`Source Mode`** (`singleLineText`): Records `"Auto"` or `"Upload"`.
- **`Kling Queue Request`** (`multilineText`): Stores Fal queue metadata (`request_id`, `status_url`, `response_url`, `submitted_at`) for idempotent resume.
- **`Empty Room Uploaded`** (`Status` single-select choice): Set after Phase 2 in upload mode. Automatically seeded into table schema.

---

## The 4 "Why" Points

1. **Why a source switch (`auto` | `upload`) instead of a new pipeline:**
   - Both modes produce the identical final asset: a 12.5s 9:16 vertical reel (10s Kling animation from empty room to staged room + 2.5s branded HomeCartel outro card with Pillow product pill and luxury soundtrack).
   - Both share the same Airtable table (`tblPYG5Ed4XURecu6`), Akeneo PIM product scraping with strict Shopify verification, Nano Banana Pro blending, and Pillow/FFmpeg final layout assembly.
   - Creating a separate pipeline would duplicate table infrastructure, routes, background runners, and frontend subtabs.

2. **Why strictly preserve all 7 phase markers in both modes:**
   - The Studio progress indicator, log stream phase detector, and queue status polling rely on `[PHASE n/7]` markers matching the registered pipeline configuration.
   - In Upload mode, Phase 2 ingests the uploaded photo (`Status` $\to$ `Empty Room Uploaded`), Phase 4 creates the staged end frame, and Phase 5 logs `[PHASE 5/7] Empty-room stripping SKIPPED (source=upload)` rather than shifting the numbering or dropping a marker.

3. **Why only Fal CDN storage URLs are passed to Kling:**
   - Airtable attachment URLs are signed AWS S3 links with short lifespans (~2 hours).
   - Passing signed URLs to asynchronous video generation queues risks 403 Forbidden errors if queue or processing delays occur.
   - `FalClient.ensure_fal_url()` guarantees that start and end frame URLs passed to Kling are hosted on `*.fal.media` storage, automatically downloading and uploading any external URLs first.

4. **Why `generate_audio: false` across both modes:**
   - Fal Kling 3.0 Pro defaults `generate_audio` to `true`, which bills at $0.168/s ($1.68 per 10s generation).
   - Phase 7 of the Virtual Staging pipeline always replaces the audio track with the official HomeCartel soundtrack (`assets/virtual_staging_track.mp3`), discarding any AI-generated audio.
   - Passing `generate_audio: false` reduces Kling billing to $0.112/s (**$1.12 per clip**), saving $0.56 on every reel generated in both Auto and Upload modes.
