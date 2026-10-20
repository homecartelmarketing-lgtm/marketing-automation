# Virtual Staging Reel: Upload Mode (Empty Room → Blended Room → Kling 3.0 Pro) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Also follow `.agents/skills/add-new-pipeline/SKILL.md` §4–§7 for the route, Studio and docs layers. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the team upload their own **empty room photo** in the Studio (Reel tab → Virtual Staging). The pipeline blends the HomeCartel fixture plus furniture into that exact room to make the **last frame**, then Kling 3.0 Pro animates the empty room into the blended room in a 10s, no-audio clip that ends in the standard branded reel.

**Architecture:** Add a `source` switch (`auto` | `upload`) to the existing 7-phase `generate_virtual_staging_reel_pipeline.py` instead of a new pipeline. Same Airtable table, same Studio card, same `[PHASE n/7]` markers. In upload mode, Phase 2 ingests the uploaded room instead of calling Krea, Phase 4 blends into it, Phase 5 is skipped, and Phase 6 calls Kling through the fal **queue** (submit → status → result) with the locked prompt below. The Studio uploads the photo to fal storage first, then queues the job with the returned URL.

**Tech Stack:** Python 3 + Flask (existing `UI Control/api_server.py`), Pillow, `requests`, existing `content_automation/fal_client.py`, React + Vite Studio (`UI Control/src/app`), stdlib `unittest` (`python -m unittest discover tests`).

**Spec (user decisions, 2026-10-20):**
1. Start frame = uploaded empty room. End frame = blended image (empty room + furniture + HomeCartel fixture).
2. Model `fal-ai/kling-video/v3/pro/image-to-video`, `duration: "10"`, `generate_audio: false`.
3. Prompt (verbatim):
   > Photorealistic interior, vertical video, one continuous shot. Slow, steady camera push-in throughout. The empty room holds still for a moment. First, the main sofa flies in from the left and lands softly with a slight bounce. Then the rug unrolls across the floor and the coffee table drops onto it. Next, the shelving cabinet slides in against the right wall and the chandelier lowers from the ceiling. Then wall art pops onto the wall, the plant rises into place, and pillows and a throw drop onto the sofa. Finally, small decor appears on the shelves and table, and everything settles. Each object moves quickly with motion blur and lands exactly in its final position. Walls, windows, floor and lighting never change. No people
4. Negative prompt (verbatim): `blur, distort, low quality, shaky camera, cartoon, anime, text, watermark, deformed face, extra limbs`
5. Transport: fal Queue API, per https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video/api (#queue-submit, #queue-status, #queue-result).
6. Files: uploaded room → fal storage upload (#files-upload). Blended image → hosted fal URL as-is (#files-from-url). Data URI (#files-data-uri) only as a fallback when upload fails.

**Cost per reel (Kling only):** 10s × $0.112 = **$1.12** (audio off). Today's pipeline never sends `generate_audio`, which fal defaults to `true`, so it is billed at $0.168/s ($1.68), and Phase 7 then throws that audio away. This plan fixes that for both modes.

## Global Constraints

- **Auto mode must keep working unchanged** (Krea → blend → strip → Kling). Every change branches on `source`; default is `auto`.
- Keep **7 phase markers** in both modes so `PHASE_LABELS`, the queue poller and the Studio progress bar stay aligned. Upload mode prints `[PHASE 5/7] ... SKIP` instead of dropping the marker.
- Phase 1 rules still hold: brand-new Airtable row, Shopify Active & Published check, base-wide dedup (`fresh-row-scrape` skill).
- **Kling only ever receives fal storage URLs.** Airtable attachment URLs are signed and expire (~2h), so they must never be passed to fal.
- Never save `None`/`null`/empty overrides (see `docs/memory/incidents/2026-10-01-studio-run-saved-none-as-moodboard-and-prompt.md`).
- `/run` spawns only the tracked root generator (see `2026-09-30-sketch-to-real-studio-ran-stale-script-copy.md`).
- Layout/typography stays local Pillow. No image API calls for text.
- Never stage `.env`. `UI Control/dist/` is tracked: rebuild and stage it.
- Full suite green before every commit: `python -m unittest discover tests`.

## Locked Kling Request

```json
{
  "start_image_url": "<Empty Room Interior: fal storage URL>",
  "end_image_url": "<Fully Staged Room: fal storage URL>",
  "prompt": "<Spec item 3, verbatim>",
  "duration": "10",
  "generate_audio": false,
  "negative_prompt": "blur, distort, low quality, shaky camera, cartoon, anime, text, watermark, deformed face, extra limbs"
}
```

Not sent, on purpose: `shot_type` (only meaningful with `multi_prompt`), `aspect_ratio` (Kling infers it from the start image, which is why Phase 2 crops to 9:16), `cfg_scale` (keep the 0.5 default), `elements` (the prompt doesn't reference `@Element1`; see Open Decisions).

## Phase Map (Upload Mode)

| Marker | Phase | Engine | Input | Output field(s) | Status after |
| :-: | :-- | :-- | :-- | :-- | :-- |
| 1/7 | Fixture scrape | Akeneo + Shopify (unchanged) | `chandeliers` category | Furniture Item, Item Name, SKU, Category, **Source Mode = Upload** | `Standby` |
| 2/7 | **Empty room ingest** | Local Pillow + fal storage | `--empty-room-url` (already uploaded by Studio) | Empty Room Interior, Room Interior (same image) | `Empty Room Uploaded` |
| 3/7 | Staging prompt | Claude Sonnet 5 vision via fal | Empty room + fixture cutout | Blending Prompt | `Prompt Generated` |
| 4/7 | **Blended end frame** | `fal-ai/nano-banana-pro/edit` | Empty room + cutout + prompt | Fully Staged Room | `Blended Image Generated` |
| 5/7 | Skipped | – | – | – | unchanged |
| 6/7 | **Kling 3.0 Pro (queue)** | fal queue submit/status/result | Locked request above | Video Prompt, Kling Queue Request, Raw Video | `Video Generated` |
| 7/7 | Assemble (unchanged) | Pillow pill + FFmpeg + outro + track | Raw Video | Outro, Final Video, Caption Generated | `Done` + PHT |

## Request Flow

```
Studio RunConfirmModal (upload mode)
  ├── POST /api/virtual-staging-reel/upload-empty-room   (multipart: file)
  │     → validate → Pillow crop 1080x1920 → fal.upload_file → {empty_room_url}
  ├── (optional) POST /api/virtual-staging-reel/kling-prompt   (only if edited)
  └── POST /api/queue/enqueue {…, source:"upload", empty_room_url}
        queue worker → POST /api/virtual-staging-reel/run {…, source, empty_room_url}
              → generate_virtual_staging_reel_pipeline.py --source upload --empty-room-url <url> --max-items 1
                    Phase 1 → 2 → 3 → 4 → (5 skip) → 6 [queue submit → status → result] → 7
```

## Files Touched

| Layer | File | Change |
| :-- | :-- | :-- |
| fal client | `content_automation/fal_client.py` | New `submit_queue`, `poll_queue_urls`, `ensure_fal_url`; `generate_kling_video` gains `generate_audio` |
| Generator | `generate_virtual_staging_reel_pipeline.py` | `--source`, `--empty-room-url`; `build_kling_payload()`; upload Phase 2; Phase 4 input switch; Phase 5 skip; Phase 6 queue + resume; new status/fields |
| Image helper | `content_automation/media.py` | `crop_to_reel(path) -> Path` (9:16, 1080×1920) |
| Route | `UI Control/routes/virtual_staging_reel.py` | `POST /upload-empty-room`, `POST /kling-prompt`; `/run` accepts `source` + `empty_room_url`; per-mode phase labels |
| Queue | `UI Control/routes/queue_manager.py` | Store + forward `source`, `empty_room_url`; skip dedup for uploads |
| Studio | `UI Control/src/app/constants/pipelines.ts` | `supportsEmptyRoomUpload`, `klingPromptEndpoint`, `phaseSummaryUpload` |
| Studio | `UI Control/src/app/components/planning/RunConfirmModal.tsx` | Source toggle, drop zone + preview, Kling prompt field, batch lock |
| Studio | `UI Control/src/app/hooks/usePipelineRunner.ts` | Send `source` + `empty_room_url` in enqueue body |
| Studio | `UI Control/src/app/App.tsx` (verify) | Pass the new 4th `onConfirm` arg through, only if it's wired inline |
| Env | `.env.example` | `KLING_PROMPT_VIRTUAL_STAGING_REEL`, `KLING_NEGATIVE_PROMPT_VIRTUAL_STAGING_REEL` |
| Tests | `tests/test_virtual_staging_upload.py`, `tests/test_queue_forwarding.py` | New |
| Docs | `docs/reels/VIRTUAL_STAGING_REEL.md`, `docs/UI_CONTROL_CONFIG.md`, `AGENTS.md`, `UI Control/README.md`, `docs/memory/decisions/2026-10-20-virtual-staging-upload-mode.md` | Update |

---

### Task 1: fal client — audio flag, queue with returned URLs, URL guard

**Files:**
- Modify: `content_automation/fal_client.py`
- Test: `tests/test_virtual_staging_upload.py`

**Interfaces:**
- `generate_kling_video(..., generate_audio: bool | None = None)`: when not `None`, send it. Existing callers are unchanged.
- `submit_queue(model_code: str, payload: dict) -> dict` returns `{"request_id", "status_url", "response_url"}` taken **from fal's submit response**, never rebuilt.
- `poll_queue_urls(status_url: str, response_url: str, *, interval=5.0, max_wait=1200.0, on_log=None) -> dict` returns the raw result JSON. Raises `ProviderError` on `FAILED`/`CANCELLED`, `ProviderTimeout` on timeout.
- `ensure_fal_url(url: str, *, filename: str) -> str` returns `url` unchanged if the host is `fal.media` / `*.fal.media`. Otherwise it downloads the file and re-uploads it with `upload_file`. If upload fails, it falls back to a `data:` URI only when the file is ≤ 8 MB, otherwise it raises.

- [ ] **Step 1: Write the failing tests**

```python
import unittest
from unittest import mock
from content_automation.fal_client import FalClient

class FalQueueTests(unittest.TestCase):
    def setUp(self):
        self.fal = FalClient(api_key="k")

    def test_submit_queue_uses_returned_urls(self):
        resp = mock.Mock(ok=True, status_code=200)
        resp.json.return_value = {
            "request_id": "abc",
            "status_url": "https://queue.fal.run/fal-ai/kling-video/requests/abc/status",
            "response_url": "https://queue.fal.run/fal-ai/kling-video/requests/abc",
        }
        with mock.patch("content_automation.fal_client.request_with_retry", return_value=resp) as rq:
            out = self.fal.submit_queue("fal-ai/kling-video/v3/pro/image-to-video", {"prompt": "x"})
        self.assertEqual(out["status_url"].rsplit("/", 1)[-1], "status")
        self.assertEqual(rq.call_args.args[2], "https://queue.fal.run/fal-ai/kling-video/v3/pro/image-to-video")

    def test_poll_raises_on_failed(self):
        st = mock.Mock(ok=True); st.json.return_value = {"status": "FAILED"}
        with mock.patch("content_automation.fal_client.request_with_retry", return_value=st):
            with self.assertRaises(Exception):
                self.fal.poll_queue_urls("https://s", "https://r", interval=0)

    def test_ensure_fal_url_passthrough(self):
        url = "https://v3b.fal.media/files/b/x/room.jpg"
        self.assertEqual(self.fal.ensure_fal_url(url, filename="room.jpg"), url)

    def test_ensure_fal_url_reuploads_airtable(self):
        with mock.patch.object(self.fal, "_download_to_temp", return_value="/tmp/r.jpg"), \
             mock.patch.object(self.fal, "upload_file", return_value="https://v3b.fal.media/files/new.jpg"):
            out = self.fal.ensure_fal_url("https://v5.airtableusercontent.com/abc", filename="r.jpg")
        self.assertTrue(out.startswith("https://v3b.fal.media/"))
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_virtual_staging_upload -v`
Expected: ERROR (`submit_queue` / `poll_queue_urls` / `ensure_fal_url` not defined).

- [ ] **Step 3: Implement**

In `generate_kling_video`, add `generate_audio: bool | None = None` and `if generate_audio is not None: payload["generate_audio"] = bool(generate_audio)`.

- [ ] **Step 4: Run tests** · `python -m unittest tests.test_virtual_staging_upload -v` · Expected: PASS
- [ ] **Step 5: Commit**

```bash
git add content_automation/fal_client.py tests/test_virtual_staging_upload.py
git commit -m "feat(fal): queue submit/poll via returned URLs, ensure_fal_url, Kling generate_audio flag"
```

### Task 2: 9:16 crop helper

**Files:**
- Modify: `content_automation/media.py`
- Test: extend `tests/test_virtual_staging_upload.py`

**Interfaces:** `crop_to_reel(src: Path, dest: Path, *, size=(1080, 1920), min_short_side=720) -> Path`. Applies EXIF orientation, converts to RGB, center-crops to 9:16, resizes with LANCZOS, saves JPEG q=95. Raises `ValueError` when the short side is under `min_short_side` (a too-small photo will look soft in Kling).

- [ ] **Step 1: Failing test**

```python
def test_crop_to_reel_landscape(self):
    from PIL import Image
    from content_automation.media import crop_to_reel
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    Image.new("RGB", (4000, 3000), "white").save(d / "in.jpg")
    out = crop_to_reel(d / "in.jpg", d / "out.jpg")
    self.assertEqual(Image.open(out).size, (1080, 1920))

def test_crop_rejects_tiny(self):
    from PIL import Image
    from content_automation.media import crop_to_reel
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    Image.new("RGB", (500, 400)).save(d / "s.jpg")
    with self.assertRaises(ValueError):
        crop_to_reel(d / "s.jpg", d / "o.jpg")
```

- [ ] **Step 2: Run, expect ERROR**
- [ ] **Step 3: Implement**
- [ ] **Step 4: PASS** · **Step 5: Commit** `feat(media): crop_to_reel 9:16 helper`

### Task 3: Generator — source switch, upload Phase 2, Phase 4 input, Phase 5 skip

**Files:**
- Modify: `generate_virtual_staging_reel_pipeline.py`
- Test: extend `tests/test_virtual_staging_upload.py`

**Interfaces:**
- CLI: `--source {auto,upload}` (default `auto`) and `--empty-room-url URL` (required when `--source upload`; `argparse` error otherwise). `--max-items` is forced to `1` in upload mode, with a `[WARN]` if a higher value was passed.
- New constants: `STATUS_EMPTY_ROOM_UPLOADED = "Empty Room Uploaded"` (add to `STATUS_CHOICES`), `FIELD_SOURCE_MODE = "Source Mode"` (singleLineText), `FIELD_KLING_QUEUE = "Kling Queue Request"` (multilineText). Add both fields to `REQUIRED_STANDARD_FIELDS`.
- `process_record(..., source="auto", empty_room_url="")`.
- `phase2_upload(clients, record_id, fields, empty_room_url) -> str` uses `clients.fal.ensure_fal_url`, attaches the image to **both** `Empty Room Interior` and `Room Interior` (Phase 3/4 read `Room Interior`), writes `Source Mode = "Upload"`, sets Status `Empty Room Uploaded`, and stores the **fal URL** in `fields` (not the Airtable URL).
- `phase3_blending_prompt` in upload mode uses a different instruction: furnish the empty room in its own style (sofa, rug, coffee table, shelving cabinet, wall art, plant, pillows, throw, small decor, matching the objects the Kling prompt animates) **and** mount the fixture. It must preserve the architecture, camera, windows, floor and lighting.
- `phase4_room_blend` is unchanged except it calls `ensure_fal_url` on both inputs.
- Phase 5 in upload mode: `print("[PHASE 5/7] Empty-room stripping SKIPPED (source=upload)")` and return the existing empty room URL.

- [ ] **Step 1: Failing tests**
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat(virtual-staging): upload source mode (phase 2 ingest, phase 5 skip)`

### Task 4: Generator — Phase 6 locked Kling request via queue + resume

**Files:**
- Modify: `generate_virtual_staging_reel_pipeline.py`
- Test: extend `tests/test_virtual_staging_upload.py`

**Interfaces:**
- `UPLOAD_KLING_PROMPT` = Spec item 3, verbatim. `UPLOAD_KLING_NEGATIVE` = Spec item 4, verbatim. Runtime overrides: `os.getenv("KLING_PROMPT_VIRTUAL_STAGING_REEL")` / `os.getenv("KLING_NEGATIVE_PROMPT_VIRTUAL_STAGING_REEL")`, ignoring empty / `none` / `null` / `undefined`.
- Pure `build_kling_payload(start_url, end_url, prompt, negative) -> dict` returns exactly the "Locked Kling Request" keys. **Plain strings, no `json.dumps` of dicts.**
- Phase 6 flow:
  1. `start = ensure_fal_url(empty_url)`, `end = ensure_fal_url(staged_url)`.
  2. **Resume:** if `Kling Queue Request` holds JSON with `status_url` + `response_url` and there's no `Raw Video` yet, skip the submit and go straight to polling (no second $1.12 charge).
  3. Otherwise `submit_queue(KLING_MODEL, payload)`, then immediately write `{"request_id","status_url","response_url","submitted_at"}` to `Kling Queue Request` and the prompt to `Video Prompt`.
  4. `poll_queue_urls(..., interval=5, max_wait=1200, on_log=...)` prints `[FAL AI] Kling status: IN_QUEUE|IN_PROGRESS (elapsed Ns)` every ~10s, which the Studio log stream shows.
  5. `video_url = result["video"]["url"]`, download it, attach Raw Video, Status `Video Generated`.
- **Auto mode:** also switch it to `build_kling_payload` with plain-text versions of its existing `KLING_PROMPT_PAYLOAD` / negative, and `generate_audio: false`. This fixes the JSON-as-prompt and audio-billing bugs for both modes.

- [ ] **Step 1: Failing tests**
- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: PASS**
- [ ] **Step 5: Manual CLI smoke (real spend ~$1.12 + image steps)** (Ask user before running)
- [ ] **Step 6: Commit** `feat(virtual-staging): locked Kling request via fal queue with resume; audio off`

### Task 5: Flask route — upload endpoint, Kling prompt pencil, `/run` source

**Files:**
- Modify: `UI Control/routes/virtual_staging_reel.py`
- Test: `tests/test_virtual_staging_upload.py` (Flask test client)

- [ ] **Step 1: Failing tests**
- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat(studio-api): virtual staging upload endpoint, kling prompt pencil, source on /run`

### Task 6: Queue — forward the upload, fix dedup

**Files:**
- Modify: `UI Control/routes/queue_manager.py`
- Test: `tests/test_queue_forwarding.py`

- [ ] **Step 1: Failing test**
- [ ] **Step 2: FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `fix(queue): forward source/empty_room_url; allow multiple upload jobs`

### Task 7: Studio UI — Reel tab → Virtual Staging card

**Files:**
- Modify: `UI Control/src/app/constants/pipelines.ts`
- Modify: `UI Control/src/app/components/planning/RunConfirmModal.tsx`
- Modify: `UI Control/src/app/hooks/usePipelineRunner.ts`
- Verify/modify: `UI Control/src/app/App.tsx`
- Rebuild: `UI Control/dist/`

- [ ] **Step 1:** Implement the config + modal + hook changes.
- [ ] **Step 2:** `cd "UI Control" && npm run build && cd ..` → exit 0.
- [ ] **Step 3: Manual check**
- [ ] **Step 4: Commit** `feat(studio): virtual staging upload mode in Reel tab`

### Task 8: Airtable schema

(Ask user before running: User will add "Empty Room Uploaded" status in Airtable by hand)

- [ ] Check schema fields `Source Mode` and `Kling Queue Request`.
- [ ] User adds `Empty Room Uploaded` choice to `Status` in Airtable.

### Task 9: Docs

- [ ] Update `docs/reels/VIRTUAL_STAGING_REEL.md`
- [ ] Update `docs/UI_CONTROL_CONFIG.md`
- [ ] Update `AGENTS.md`
- [ ] Update `UI Control/README.md`
- [ ] Update `.env.example`
- [ ] Write `docs/memory/decisions/2026-10-20-virtual-staging-upload-mode.md`
- [ ] Commit `docs(virtual-staging): upload mode, kling queue, fixes`
