# Virtual Staging Reel Automation Pipeline

The **Virtual Staging Reel Automation Pipeline** generates a photorealistic, high-engagement **9:16 vertical video reel (1080 x 1920 px, ~10.5 seconds)** that captures an empty luxury room being progressively staged with furniture, rugs, tables, accessories, and a statement HomeCartel lighting fixture falling smoothly into place with realistic gravity and settle.

> **Reference Video:** [`6-Virtual-Staging.mp4`](file:///c:/Users/User/Desktop/marketing-automation/6-Virtual-Staging.mp4) (24 fps, 193 frames = 8.04 s, seamless falling physics and settle, upbeat chillhop rhythmic beat).

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Total Duration**: `~10.5 seconds`
  - `~8.0 seconds`: AI keyframe-guided staging video (Empty Room $\to$ Full Staged Room with falling furniture animation).
  - `~2.5 seconds`: Standard HomeCartel Outro card ([`assets/outro_layout.jpg`](file:///c:/Users/User/Desktop/marketing-automation/assets/outro_layout.jpg)) with 0.5s fade-in transition and 1.0s audio fade-out.
- **Audio Profile**:
  - Upbeat modern rhythmic lounge/chillhop soundtrack extracted directly from [`6-Virtual-Staging.mp4`](file:///c:/Users/User/Desktop/marketing-automation/6-Virtual-Staging.mp4) saved to `assets/virtual_staging_track.mp3` (zero API cost, guaranteed sync with drops).
- **On-Screen Brand Typography**:
  - Lower corner luxury product pill (e.g. `HomeCartel — Mina 7 Chandelier`) stamped locally via Python Pillow (`content_automation/fonts/Poppins-Bold.ttf`, 28px white with ambient drop shadow). Zero layout API cost.

---

## 2. Model Stack Phase Table (7 Phases)

The log prints `[PHASE n/7]` markers that the Web Studio reads for real-time progress tracking.

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape & Verification** | Akeneo PIM API + Shopify Live API | Active ingestion (`enabled=true`) + Shopify Live Published check + base-wide dedup | Akeneo `chandeliers` catalog strictly | Brand-new row, `Foreign Key ID`, `Furniture Item`, `Item Name`, `SKU` $\to$ Status: `Standby` |
| **Phase 2** | **Krea Furnished Room Interior** | Krea AI | `krea-2-medium` (9:16, 1K). Standard furnished room prompt + moodboard ID | Studio prompt override or default modern room prompt | `Room Interior` $\to$ Status: `Interior Generated` |
| **Phase 3** | **Claude Sonnet 5 Blending Prompt** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` (vision mode) | `Room Interior` + scraped fixture photo | `Blending Prompt` $\to$ Status: `Prompt Generated` |
| **Phase 4** | **Nano Banana Pro Fixture Blend** | Fal AI | `fal-ai/nano-banana-pro/edit`, 9:16, 1K | `Room Interior` + `Furniture Item` + `Blending Prompt` | `Fully Staged Room` $\to$ Status: `Blended Image Generated` |
| **Phase 5** | **Claude Empty-Room Conversion & Nano Banana Pro** | Fal AI (`anthropic/claude-sonnet-5` + `fal-ai/nano-banana-pro/edit`) | Vision removal prompt + inpainting removal of all furniture/fixtures/decor | `Fully Staged Room` | `Emptying Prompt`, `Empty Room Interior` $\to$ Status: `Empty Room Generated` |
| **Phase 6** | **Kling 3.0 Pro Virtual Staging Video** | Fal AI | `fal-ai/kling-video/v3/pro/image-to-video`<br>• `start_image_url`: Empty Room<br>• `end_image_url`: Fully Staged Room<br>• `prompt`: Single unified drop motion prompt<br>• `elements`: `@element1` fixture injection<br>• `shot_type`: `customize`<br>• `negative_prompt`: anti-warp & locked camera | `Empty Room Interior` + `Fully Staged Room` + `@element1` | `Raw Video` $\to$ Status: `Video Generated` |
| **Phase 7** | **Pillow Product Tag + Outro + Audio Mux + Caption** | Local Pillow + Local FFmpeg (`imageio-ffmpeg`) + Fal AI (`anthropic/claude-sonnet-5`) | Local Poppins typography overlay + reference audio mux + 2.5s Outro card crossfade + shared Instagram caption | `Raw Video` + `assets/virtual_staging_track.mp3` + `assets/outro_layout.jpg` | `Final Video`, `Caption Generated` $\to$ Status: `Done` + PHT Timestamp |

---

## 3. Kling 3.0 Pro Configuration & Setting Breakdown

The video generation in **Phase 6** runs on **`fal-ai/kling-video/v3/pro/image-to-video`**. Below is the exact payload and the purpose of every setting:

### Complete API Payload Structure

```json
{
  "start_image_url": "https://v3b.fal.media/files/.../empty_room.jpg",
  "end_image_url": "https://v3b.fal.media/files/.../fully_staged_room.jpg",
  "prompt": "Task: Turn the uploaded interior photo into a photorealistic empty-to-furnished room assembly animation.\n\nPrompt: Use the uploaded photo as the finished-room target. Begin with the same room empty of movable furniture and decorations, then animate ONLY the objects visible in the photo into their original positions. Adapt automatically to any room type, layout and furniture style. Preserve the architecture, flooring, walls, windows, doors, permanent built-ins, lighting and color palette. Reconstruct plausible surfaces temporarily exposed behind removed objects. Never redesign the room or invent furniture.\n\nAnimation: Create one continuous, satisfying self-furnishing sequence without people. Bring large furniture into place with short, smooth downward drops and subtle weighted settling. Keep furniture complete, including legs, upholstery, seat cushions and mattresses. Unfurl any rug before furniture resting on it lands. Slide or lower secondary furniture into its final positions in staggered beats. Reveal existing decorative lights and wall art at their correct mounting points. Drape loose blankets naturally, gently drop decorative pillows, then place plants and small accessories on their correct supporting surfaces. Skip categories absent from the photo. Animate distinct objects rather than crossfading the entire room.\n\nConsistency: Preserve each object's design, proportions, material, color, pattern and count. Match its final position, orientation, scale and overlap to the photo. Keep solid objects rigid; only loose fabric bends. Prevent collisions and movement through surfaces. Develop realistic contact shadows and reflections as objects settle. Keep illumination stable and preserve the photo's lamp states.\n\nCamera: Very gentle rightward drift with a subtle forward push, ending at the uploaded photo's viewpoint. Minimize movement if it would reveal unseen areas. Finish with a brief, steady view of the completed room matching the photo.\n\nOutput: Photorealistic interior advertisement; same aspect ratio as the uploaded image; no text or logos.",
  "duration": "10",
  "shot_type": "customize",
  "negative_prompt": "People, hands, pets, invented or duplicated objects, missing furnishings, incomplete upholstery, morphing, melting, warped architecture, changing colors, floating furniture, exaggerated bouncing, flicker, jump cuts, whole-room crossfades, camera shake, fast orbit, watermarks.",
  "generate_audio": false
}
```

### Detailed Setting Explanations

1. **`fal-ai/kling-video/v3/pro/image-to-video` (Model)**:
   - Kling’s flagship 3.0 Pro model hosted on Fal AI.
   - Enables dual keyframe interpolation (`start_image_url` $\to$ `end_image_url`), custom element injection (`elements`), and multi-shot storyboards (`multi_prompt`) with native 1080p photorealism.

2. **`multi_prompt` (Multi-Shot Progression)**:
   - Breaks the 10-second sequence into distinct timed stages.
   - Asking an AI model to animate 10 items dropping simultaneously causes visual chaos and hallucinated shapes. Dividing into two 5-second shots ensures:
     - **Shot 1 (0–5s)**: Foundation pieces (sofa, rug, table, bookcase) drop into the empty space.
     - **Shot 2 (5–10s)**: Statement lighting (`@element1`) drops from the ceiling and turns on, wall art slides in, and decor accents settle.

3. **`start_image_url` (Beginning Frame)**:
   - The starting frame at $t = 0.0\text{s}$.
   - We supply the Krea-generated **Empty Room**. Guarantees the video begins with bare architecture (clean hardwood floor, plain walls, empty ceiling).

4. **`end_image_url` (Destination Frame)**:
   - The destination frame at $t = 10.0\text{s}$.
   - **Crucial for accuracy**: We supply the **Fully Staged Room with the blended HomeCartel fixture**. Because the destination image is locked, Kling cannot invent random furniture or alter the room layout—it must interpolate toward this exact target scene.

5. **`elements` & `@element1` (Custom Entity Injection)**:
   - Registers custom objects using reference images.
   - We inject the scraped HomeCartel lighting fixture as `element1` with its `frontal_image_url`. In the prompt, referencing `@element1` instructs Kling to reproduce the exact brass finish, arm configuration, and shade geometry of the real product.

6. **`shot_type: "customize"` (Camera Lock)**:
   - Prevents cinematic camera panning, tilting, or zooming.
   - Virtual staging requires a locked eye-level camera so floor planks and ceiling planes remain stable while the furniture drops into place.

7. **`duration: "10"` (Total Runtime)**:
   - Set to 10 seconds (sum of `5 + 5` from `multi_prompt`).
   - Optimal pacing for social media reels: provides viewers ample time to appreciate the bare space, the drop transitions, and the final styled interior.

8. **`negative_prompt`**:
   - Strictly suppresses warping, moving cameras, jitter, blur, and cartoon styles:
     `"blur, distort, low quality, shaky camera, cartoon, anime, text, watermark, deformed face, extra limbs, moving camera, panning, warped walls, changing floor"`

9. **`generate_audio: false`**:
   - Disables Kling's native synthetic audio.
   - Our Phase 6 pipeline muxes the verified upbeat rhythmic audio track from [`6-Virtual-Staging.mp4`](file:///c:/Users/User/Desktop/marketing-automation/6-Virtual-Staging.mp4) (`assets/virtual_staging_track.mp3`) with precision beat alignment and smooth outro fade.

---

## 4. Foreign Key ID Convention & Examples

$$\text{Format: } \mathbf{VST\text{-}REEL\text{-}SET\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `VST` (Virtual Staging)
- **Content Format**: `REEL`
- **Fixture Code**: `SET` (Staged Set)

Examples: `VST-REEL-SET-1`, `VST-REEL-SET-2`.

---

## 5. Supported Airtable Table & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- |
| **Virtual Staging** | `SET` | Configurable | `AIRTABLE_TABLE_ID_VIRTUAL_STAGING_REEL` |

### Krea Settings & Defaults

| Setting | Environment Variable | Default Value |
| :--- | :--- | :--- |
| **Moodboard ID** | `KREA_MOODBOARD_ID_VIRTUAL_STAGING_REEL` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` |
| **Interior Prompt** | `PROMPT_VIRTUAL_STAGING_REEL` | `Generate me a photo of a modern luxury living room with high ceilings, large windows, architectural styling, natural daylight, warm aesthetic, high end furniture` |

### Airtable Schema Auto-Provisioning

The pipeline automatically checks for and provisions missing fields on the first execution:

| # | Field Name | Airtable Field Type | Source Phase / Description |
| :-: | :--- | :--- | :--- |
| **1** | `Foreign Key ID` | `singleLineText` | Standardized ID format: `VST-REEL-SET-<ROW_ID>` |
| **2** | `ID` | `number` | Unique numeric row identifier |
| **3** | `Status` | `singleSelect` | Lifecycle status: `Standby`, `In progress`, `Done`, `Scheduled`, `Posted`, `Discard`, `For Manual` |
| **4** | `Date and Time Generated` | `dateTime` | Automatic Asia/Manila (PHT) timestamp stamped when row completes |
| **5** | `Date and Time Scheduled` | `dateTime` | Scheduled publication date/time for Instagram auto-post scheduler |
| **6** | `Furniture Item` | `multipleAttachments` | **Phase 1**: High-res cutout product photo of scraped chandelier from Akeneo PIM |
| **7** | `Item Name` | `singleLineText` | **Phase 1**: Clean luxury product display name (e.g. `Mina 7 Chandelier`) |
| **8** | `SKU` | `singleLineText` | **Phase 1**: Unique Akeneo product SKU code |
| **9** | `Category` | `singleLineText` | **Phase 1**: Lighting catalog category (`chandeliers`) |
| **10** | `Room Interior` | `multipleAttachments` | **Phase 2**: Krea AI generated 9:16 luxury furnished room interior |
| **11** | `Interior Prompt` | `multilineText` | **Phase 2**: Text prompt used to generate the Krea room |
| **12** | `Moodboard ID` | `singleLineText` | **Phase 2**: Krea moodboard UUID used for the architectural aesthetic |
| **13** | `Blending Prompt` | `multilineText` | **Phase 3**: Claude Sonnet 5 vision blending prompt |
| **14** | `Fully Staged Room` | `multipleAttachments` | **Phase 4**: Nano Banana Pro blended room with HomeCartel chandelier installed on ceiling |
| **15** | `Emptying Prompt` | `multilineText` | **Phase 5**: Claude Sonnet 5 vision removal instructions to strip all furniture |
| **16** | `Empty Room Interior` | `multipleAttachments` | **Phase 5**: Nano Banana Pro inpainted empty room (Kling Start Image) |
| **17** | `Video Prompt` | `multilineText` | **Phase 6**: Complete Kling 3.0 Pro prompt string sent to Fal AI |
| **18** | `Raw Video` | `multipleAttachments` | **Phase 6**: 10-second generated video directly from Kling 3.0 Pro |
| **19** | `Outro` | `multipleAttachments` | **Phase 7**: Reference copy of the 2.5s HomeCartel Outro card (`assets/outro_layout.jpg`) |
| **20** | `Final Video` | `multipleAttachments` | **Phase 7**: Complete 9:16 vertical video reel with product name tag, synced audio, and Outro card |
| **21** | `Caption Generated` | `multilineText` | Luxury Instagram caption with curated hashtags generated by Claude Sonnet 5 |

---

## 6. Web Studio (UI Control) & CLI Runner

### Studio Placement
- **Location**: Reel tab, **Subtab 11: "Virtual Staging"** (`subtabIndex: 11`).
- **Card**: Single card (`id: 'virtual-staging'`) with live status counts (`Standby`, `In progress`, `Done`).
- **Primary Airtable Table ID**: `tblPYG5Ed4XURecu6` (configurable via `AIRTABLE_TABLE_ID_VIRTUAL_STAGING_REEL`).
- **Foreign Key Prefix**: `VST-REEL-SET-<ROW_ID>`.
- **Controls**: Editable moodboard ID and prompt pencils that persist overrides.
- **Flask Endpoints**: Mounted at `/api/virtual-staging-reel/*` (`run`, `status`, `stop`, `counts`, `moodboard`, `prompt`).
- **Calendar Automation**: Linked in `assets/calendar_pipeline_map.json` under `"Reels :: Virtual Staging"`.

### CLI Runner Usage

```bash
# Standard run: scrapes 1 fresh active fixture, creates a brand-new row, and runs end-to-end
python run_virtual_staging_reel.py --max-rows 1

# Explicit row re-render (skips scraping):
python run_virtual_staging_reel.py --record-id recXXXXXXXXXXXXXX

# Dry run / inspection:
python run_virtual_staging_reel.py --dry-run
```
