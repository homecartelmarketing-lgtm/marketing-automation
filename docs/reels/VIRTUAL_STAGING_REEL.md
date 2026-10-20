# Virtual Staging Reel Automation Pipeline

The **Virtual Staging Reel Automation Pipeline** generates a photorealistic, high-engagement **9:16 vertical video reel (1080 x 1920 px, 12.5 seconds)** that captures an empty luxury room being progressively staged with furniture, rugs, tables, accessories, and a statement HomeCartel lighting fixture falling smoothly into place with realistic gravity and settle.

> **Reference Video:** [`6-Virtual-Staging.mp4`](file:///c:/Users/User/Desktop/marketing-automation/6-Virtual-Staging.mp4) (seamless falling physics and settle, upbeat chillhop rhythmic beat).

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Total Duration**: `12.5 seconds`
  - `10.0 seconds`: AI keyframe-guided staging video (Empty Room $\to$ Full Staged Room animated with Kling 3.0 Pro).
  - `2.5 seconds`: Standard HomeCartel Outro card ([`assets/outro_layout.jpg`](file:///c:/Users/User/Desktop/marketing-automation/assets/outro_layout.jpg)) with 0.5s fade-in transition and 1.0s audio fade-out.
- **Audio Profile**:
  - Upbeat modern rhythmic lounge/chillhop soundtrack extracted directly from [`6-Virtual-Staging.mp4`](file:///c:/Users/User/Desktop/marketing-automation/6-Virtual-Staging.mp4) saved to `assets/virtual_staging_track.mp3` (zero API cost, guaranteed sync with drops).
- **On-Screen Brand Typography**:
  - Lower corner luxury product pill (e.g. `HomeCartel — Mina 7 Chandelier`) stamped locally via Python Pillow (`content_automation/fonts/Poppins-Bold.ttf`, 28px white with ambient drop shadow). Zero layout API cost.

---

## 2. Operating Modes: Auto vs. Upload

The pipeline supports two execution modes switched via `--source {auto,upload}` (default `auto`):

1. **Auto Mode (`source="auto"`)**:
   - Synthesizes a luxury furnished room interior via **Krea AI** using Krea moodboard and prompt overrides.
   - Blends the HomeCartel chandelier into the room using **Nano Banana Pro**.
   - Strips furniture in Phase 5 with Claude Vision analysis and Nano Banana inpainting to create the bare start frame.
   - Animates Empty Room $\to$ Blended Room via Kling 3.0 Pro.

2. **Upload Mode (`source="upload"`)**:
   - The user/team uploads an **empty room photo** in the Studio (or supplies `--empty-room-url`).
   - The photo is validated, center-cropped to 9:16 (1080x1920) via `content_automation/media.crop_to_reel`, and uploaded to Fal CDN storage.
   - **Phase 2 Ingest**: Bypasses Krea, attaches the uploaded room to both `Empty Room Interior` and `Room Interior`, sets `Status` to `Empty Room Uploaded`, and stamps `Source Mode = "Upload"`.
   - **Phase 3 Staging Prompt**: Claude Sonnet 5 Vision analyzes the empty room and writes a prompt tailored to furnish that exact architectural layout (sofa, rug, coffee table, shelving cabinet, wall art, plant, pillows, throw, small decor) and mount the HomeCartel fixture.
   - **Phase 4 Staged End Frame**: Nano Banana Pro blends the chandelier and staging elements into the empty room as the target end frame.
   - **Phase 5 Skip**: Stripping is skipped (`[PHASE 5/7] Empty-room stripping SKIPPED (source=upload)`).
   - **Phase 6 Kling Queue**: Submits the locked request to Fal Queue with resume polling support.
   - **Phase 7 Assembly**: Pillow branding pill, Outro card, audio muxing, and Instagram caption.

---

## 3. Phase Map Comparison

Both modes preserve **7 phase markers** (`[PHASE n/7]`) so the Studio progress bar, log stream, and queue poller remain consistent.

| Phase | Auto Mode | Upload Mode (`source=upload`) | Output Field(s) | Status After |
| :---: | :--- | :--- | :--- | :--- |
| **1/7** | Scrape Akeneo + Shopify verification | Scrape Akeneo + Shopify verification | `Furniture Item`, `Item Name`, `SKU`, `Category` | `Standby` |
| **2/7** | Krea 9:16 Furnished Room | **Ingest Uploaded Empty Room** | `Empty Room Interior`, `Room Interior` | `Interior Generated` (Auto) / `Empty Room Uploaded` (Upload) |
| **3/7** | Claude Sonnet 5 Blend Prompt | **Claude Sonnet 5 Staging Prompt** | `Blending Prompt` | `Prompt Generated` |
| **4/7** | Nano Banana Pro Fixture Blend | **Nano Banana Pro Staged End Frame** | `Fully Staged Room` | `Blended Image Generated` |
| **5/7** | Claude + Nano Banana Room Stripping | **SKIPPED** (prints skip marker) | `Emptying Prompt`, `Empty Room Interior` | `Empty Room Generated` (Auto) / unchanged (Upload) |
| **6/7** | Kling 3.0 Pro (Queue submit & poll) | **Kling 3.0 Pro (Locked Request, Queue)** | `Video Prompt`, `Kling Queue Request`, `Raw Video` | `Video Generated` |
| **7/7** | Pillow Pill + Outro + Audio Mux | Pillow Pill + Outro + Audio Mux | `Outro`, `Final Video`, `Caption Generated` | `Done` + PHT Timestamp |

---

## 4. Locked Kling 3.0 Pro Request (Fal Queue)

Both modes execute Kling 3.0 Pro through the Fal Queue API (`https://queue.fal.run/fal-ai/kling-video/v3/pro/image-to-video`):

```json
{
  "start_image_url": "<Empty Room Interior: fal storage URL>",
  "end_image_url": "<Fully Staged Room: fal storage URL>",
  "prompt": "Photorealistic interior, vertical video, one continuous shot. Slow, steady camera push-in throughout. The empty room holds still for a moment. First, the main sofa flies in from the left and lands softly with a slight bounce. Then the rug unrolls across the floor and the coffee table drops onto it. Next, the shelving cabinet slides in against the right wall and the chandelier lowers from the ceiling. Then wall art pops onto the wall, the plant rises into place, and pillows and a throw drop onto the sofa. Finally, small decor appears on the shelves and table, and everything settles. Each object moves quickly with motion blur and lands exactly in its final position. Walls, windows, floor and lighting never change. No people",
  "duration": "10",
  "generate_audio": false,
  "negative_prompt": "blur, distort, low quality, shaky camera, cartoon, anime, text, watermark, deformed face, extra limbs"
}
```

### Key Technical Rules:
1. **Fal Storage URLs Only**: Airtable signed attachment URLs expire after ~2 hours. Both `start_image_url` and `end_image_url` are checked with `FalClient.ensure_fal_url()` to guarantee Kling receives permanent CDN URLs.
2. **Audio Billing Fix (`generate_audio: false`)**: Kling defaults to synthetic audio billing ($0.168/s = $1.68). Setting `generate_audio: false` reduces video billing to $0.112/s = **$1.12** per 10s reel, and Phase 7 muxes the branded audio locally.
3. **Queue Resumption**: If a process is interrupted or restarted, Phase 6 inspects `Kling Queue Request`. If `status_url` and `response_url` are present and `Raw Video` has not yet been saved, it resumes polling directly without double-billing.

---

## 5. Web Studio Walkthrough (Upload Mode)

1. Open Web Studio on port 5200 (`http://localhost:5200`).
2. Navigate to **Reel** tab $\to$ **Subtab 11: "Virtual Staging"**.
3. Click **Run** on the Virtual Staging fixture card.
4. In the modal:
   - Click the **Upload empty room** segmented toggle.
   - Drop or browse an empty room image (JPEG, PNG, WebP $\le$ 15 MB).
   - Review the 9:16 crop preview.
   - (Optional) Edit the Kling motion prompt in the prompt editor.
   - Batch size is locked to 1 ("1 upload = 1 reel").
5. Click **Upload & Run**.
   - The Studio crops and uploads the photo to Fal CDN storage.
   - If edited, the Kling motion prompt is persisted.
   - The job is enqueued in the FIFO generation queue and runs Phases 1–7 end-to-end.

---

## 6. Supported Airtable Schema & Environment Variables

### Airtable Table & Keys

| Setting | Environment Variable | Default Value |
| :--- | :--- | :--- |
| **Table ID** | `AIRTABLE_TABLE_ID_VIRTUAL_STAGING_REEL` | `tblPYG5Ed4XURecu6` |
| **Krea Moodboard ID** | `KREA_MOODBOARD_ID_VIRTUAL_STAGING_REEL` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` |
| **Krea Interior Prompt** | `PROMPT_VIRTUAL_STAGING_REEL` | `Generate me a photo of a modern luxury living room with high ceilings...` |
| **Kling Motion Prompt** | `KLING_PROMPT_VIRTUAL_STAGING_REEL` | (Locked drop motion prompt) |
| **Kling Negative Prompt** | `KLING_NEGATIVE_PROMPT_VIRTUAL_STAGING_REEL` | `blur, distort, low quality, shaky camera...` |

### Airtable Field Definitions

The generator auto-provisions schema via `_ensure_schema()`:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `Foreign Key ID` | `singleLineText` | Format: `VST-REEL-SET-<ROW_ID>` |
| `ID` | `number` | Unique numeric row identifier |
| `Status` | `singleSelect` | `Standby`, `In progress`, `Empty Room Uploaded`, `Done`, etc. |
| `Source Mode` | `singleLineText` | `"Auto"` or `"Upload"` |
| `Furniture Item` | `multipleAttachments` | Scraped chandelier cutout from Akeneo |
| `Item Name` | `singleLineText` | Chandelier name (e.g. `Mina 7 Chandelier`) |
| `SKU` | `singleLineText` | Akeneo SKU |
| `Category` | `singleLineText` | `chandeliers` |
| `Room Interior` | `multipleAttachments` | Krea generated room (Auto) or Uploaded empty room (Upload) |
| `Blending Prompt` | `multilineText` | Claude Sonnet 5 vision blending prompt |
| `Fully Staged Room` | `multipleAttachments` | Nano Banana Pro blend (end frame) |
| `Empty Room Interior` | `multipleAttachments` | Nano Banana stripped room (Auto) or Uploaded room (Upload) |
| `Video Prompt` | `multilineText` | Kling 3.0 Pro motion prompt |
| `Kling Queue Request` | `multilineText` | JSON holding request_id, status_url, response_url |
| `Raw Video` | `multipleAttachments` | 10s silent video from Kling |
| `Outro` | `multipleAttachments` | 2.5s HomeCartel Outro card |
| `Final Video` | `multipleAttachments` | 12.5s vertical video reel with branding and audio |
| `Caption Generated` | `multilineText` | Claude Sonnet 5 Instagram caption |
| `Date and Time Generated` | `dateTime` | Automatic PHT timestamp on completion |

---

## 7. CLI Usage

```bash
# Auto mode: scrape fresh chandelier, generate Krea room, strip, Kling video, assemble
python generate_virtual_staging_reel_pipeline.py --source auto --max-items 1

# Upload mode: supply an already hosted Fal storage URL
python generate_virtual_staging_reel_pipeline.py --source upload \
  --empty-room-url "https://v3b.fal.media/files/sample/empty_room.jpg" --max-items 1

# Reprocess a specific record by ID
python generate_virtual_staging_reel_pipeline.py --record-id recXXXXXXXXXXXXXX

# Thin runner alias
python run_virtual_staging_reel.py --max-rows 1
```
