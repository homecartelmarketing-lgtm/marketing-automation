# Sketch to Real Reel Automation Pipeline

The **Sketch to Real Reel Automation Pipeline** generates high-engagement **~11-to-12 second 9:16 vertical video reels (1080 x 1920 px)** for social media (Instagram Reels, TikTok, YouTube Shorts). It demonstrates an architectural transformation: beginning with a hand-drawn vector outline sketch of a room interior featuring a HomeCartel lighting fixture that animates in real-time, line-by-line, and blossoms into a photorealistic, warmly illuminated luxury room interior, complete with an Instagram thumbnail cover and branded outro.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Structure & Timing**: Total ~11.0 to 12.0 seconds
  - **Scene 1 (Auto Draw Reveal)**: 4.5s drawing + 1.8s ease transition + 2.0s hold — Real-time frame-by-frame vector stroke animation tracing the lighting fixture outlines onto the room, dissolving into the warm photorealistic scene.
  - **Scene 2 (Branded Outro)**: 2.5s hold — Branded HomeCartel closing card (`assets/outro_layout.jpg`) with smooth 0.5s fade-in.
- **Audio Profile**: Silent (`-an`) or optional local audio soundtrack (Zero ElevenLabs API calls).

---

## 2. Model Stack Phase Table (7 Phases)

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape & Catalog Verification** | Akeneo PIM API + Shopify Client | Active ingestion + strict Shopify catalog check + base-wide dedup | Fresh category product (Chandelier, Pendant, etc.) | `Furniture Item`, `SKU`, `Item Name`, `Category` -> Status: `In progress`<br>*(Strictly NO Price Field)* |
| **Phase 2** | **Krea Room Interior Generation** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Preset category Moodboard | Category Moodboard ID + Room Prompt | `Room Interior`, `Interior Prompt` -> Status: `Interior Generated` |
| **Phase 3** | **Claude Vision Prompting & Headline** | Fal AI | `anthropic/claude-sonnet-5` | Product Photo + Room Interior | `Blending Prompt`, `Reel Headline` -> Status: `Prompt Generated`<br>*(No Sketch Prompt, No Video Prompt, No Caption)* |
| **Phase 4** | **Nano Banana Pro Photorealistic Blend** | Fal AI + YOLO-World | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: 9:16, Resolution: 1K | Room Interior + Product + Blending Prompt | `Blended Image` + `Blended Image with Name text` -> Status: `Blended Image Generated` |
| **Phase 5** | **Auto Draw Outline & Cover Generation** | Local Auto Draw Engine + Pillow | Canny edge subtraction + Pillow Poppins Bold | Room Interior (BEFORE) + Blended Image (AFTER) + `Reel Headline` | `Sketch Image` + `Thumbnail with Generated Text` -> Status: `Sketch Generated` |
| **Phase 6** | **Auto Draw Vector Animation** | Local Auto Draw Engine via FFmpeg | Vector stroke path tracing directly to FFmpeg rawvideo pipe | Room Interior + Blended Image | `Raw Video` -> Status: `Video Generated` |
| **Phase 7** | **FFmpeg Outro & Completion** | Local FFmpeg (`imageio-ffmpeg`) | Zero-API Local Video Compositor (Zero ElevenLabs) | `Raw Video` + `assets/outro_layout.jpg` | `Final Video` + `Outro` -> Status: `Done` (C) + auto PHT timestamp |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{STR\text{-}REEL\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `STR` (Sketch To Real)
- **Content Format**: `REEL`
- **Fixture Codes**:
  - `CH`: Chandeliers
  - `PE`: Pendant Lights
  - `FL`: Floor Lamps
  - `TL`: Table Lamps
  - `CM`: Ceiling Mounted
  - `SET`: Multi-fixture / Unified Table

### Real-World Examples:
- `STR-REEL-CH-1` (Row 1 of Chandeliers Sketch to Real Reel)
- `STR-REEL-PE-4` (Row 4 of Pendant Lights Sketch to Real Reel)
- `STR-REEL-FL-2` (Row 2 of Floor Lamps Sketch to Real Reel)

---

## 4. Supported Categories & Environment Variables Map

| Category Name | Fixture Code | Primary Environment Variable | Default Table ID | Default Krea Moodboard ID | Studio |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Chandeliers** | `CH` | `AIRTABLE_TABLE_ID_CHANDELIERS_SKETCH_TO_REAL_REEL` | `tblUFR6OvFQaHnG1V` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | Runnable |
| **Pendant Lights** | `PE` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_SKETCH_TO_REAL_REEL` | `tblSALsUd5MXXnkp6` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | Runnable |
| **Floor Lamps** | `FL` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_SKETCH_TO_REAL_REEL` | *no Airtable table yet (placeholder `tblSketchToRealFloorLamps`)* | `b1641228-beec-4823-8d01-1de3eec8410d` | Not yet |
| **Table Lamps** | `TL` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_SKETCH_TO_REAL_REEL` | *no Airtable table yet (placeholder `tblSketchToRealTableLamps`)* | `fb2487fb-2895-4d2c-9758-805aaf1bac69` | Not yet |
| **Ceiling Mounted** | `CM` | `AIRTABLE_TABLE_ID_CEILING_MOUNTED_SKETCH_TO_REAL_REEL` | *no Airtable table yet (placeholder `tblSketchToRealCeilingMounted`)* | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | Not yet |
| **Unified Table** | `SET` | `AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL` | *unused* | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | n/a |

Rows marked "no Airtable table yet" cannot be run until a real table exists: create it, set the env key, and register its ID in `content_automation/foreign_key.py`, `UI Control/routes/sketch_to_draw_reel.py` and `UI Control/src/app/constants/fixtures.ts`.

--- | :---: | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `AIRTABLE_TABLE_ID_CHANDELIERS_SKETCH_TO_REAL_REEL` | `tblSketchToRealChandeliers` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` |
| **Pendant Lights** | `PE` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_SKETCH_TO_REAL_REEL` | `tblSALsUd5MXXnkp6` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` |
| **Floor Lamps** | `FL` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_SKETCH_TO_REAL_REEL` | `tblSketchToRealFloorLamps` | `b1641228-beec-4823-8d01-1de3eec8410d` |
| **Table Lamps** | `TL` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_SKETCH_TO_REAL_REEL` | `tblSketchToRealTableLamps` | `fb2487fb-2895-4d2c-9758-805aaf1bac69` |
| **Ceiling Mounted** | `CM` | `AIRTABLE_TABLE_ID_CEILING_MOUNTED_SKETCH_TO_REAL_REEL` | `tblSketchToRealCeilingMounted` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` |
| **Unified Table** | `SET` | `AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL` | `tblSketchToRealReel` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` |

---

## 5. Streamlined 19-Field Airtable Database Schema

| # | Field Name | Type | Operational Description |
| :-: | :--- | :--- | :--- |
| 1 | `Foreign Key ID` | `singleLineText` | Unique identifier (e.g. `STR-REEL-CH-1`) |
| 2 | `ID` | `number` / `autoNumber` | Row index counter |
| 3 | `Date and Time Generated` | `dateTime` (PHT) | Timestamp auto-injected when Status reaches Done |
| 4 | `Status` | `singleSelect` | `Standby`, `In progress`, `Scheduled`, `Done`, `Discarded`, `For Manual` |
| 5 | `Furniture Item` | `multipleAttachments` | Isolated cutout product photo from Akeneo PIM |
| 6 | `SKU` | `singleLineText` | Verified active SKU from Akeneo/Shopify |
| 7 | `Item Name` | `singleLineText` | Clean product title |
| 8 | `Category` | `singleLineText` / `singleSelect` | Lighting fixture category name |
| 9 | `Room Interior` | `multipleAttachments` | 9:16 luxury empty room interior from Krea AI (BEFORE scene) |
| 10 | `Interior Prompt` | `multilineText` | Prompt used to generate the interior |
| 11 | `Blending Prompt` | `multilineText` | Claude Sonnet 5 vision blend prompt |
| 12 | `Blended Image` | `multipleAttachments` | Photorealistic 9:16 room with lit fixture (AFTER scene) |
| 13 | `Blended Image with Name text` | `multipleAttachments` | YOLO-World tagged variant with floating luxury pill badge |
| 14 | `Sketch Image` | `multipleAttachments` | 9:16 outline preview generated via Auto Draw Canny subtraction |
| 15 | `Reel Headline` | `singleLineText` | Claude 3-5 word hook (e.g. "From Sketch to Real") |
| 16 | `Thumbnail with Generated Text` | `multipleAttachments` | 9:16 cover photo with dimmed outline and centered Poppins typography |
| 17 | `Raw Video` | `multipleAttachments` | Real-time line-drawing reveal video rendered via Auto Draw |
| 18 | `Outro` | `multipleAttachments` | Branded HomeCartel Outro (`assets/outro_layout.jpg`) |
| 19 | `Final Video` | `multipleAttachments` | Final 9:16 vertical video reel with Outro (Zero ElevenLabs) |

*(Note: Price, Caption Generated, Sketch Prompt, Video Prompt, and Music Generated fields are omitted per specifications).*

---

## 6. Execution Commands

CLI commands:
```bash
# Chandeliers
python run_sketch_to_real_reel.py --target chandeliers --max-items 1

# Pendant Lights
python run_sketch_to_real_reel.py --target pendant_lights --max-items 1

# Floor Lamps
python run_sketch_to_real_reel.py --target floor_lamps --max-items 1

# Table Lamps
python run_sketch_to_real_reel.py --target table_lamps --max-items 1

# Ceiling Mounted
python run_sketch_to_real_reel.py --target ceiling_mounted --max-items 1
```

### Web Studio Execution (Port 5200)

Studio **Reel** tab → subtab 7 **Sketch to Real** (`/api/sketch-to-draw-reel/*`; the URL prefix keeps its old name). Only **Chandeliers** and **Pendant Lights** are runnable today (the others have no Airtable table yet).

- The route always spawns the tracked root script `generate_sketch_to_real_reel_pipeline.py` (never a copy under `python-content-script/`); see [`../memory/incidents/2026-09-30-sketch-to-real-studio-ran-stale-script-copy.md`](../memory/incidents/2026-09-30-sketch-to-real-studio-ran-stale-script-copy.md).
- Phase progress comes from the `[PHASE N]` lines the script prints and never moves backwards; run status and logs reach the UI through the queue (`/api/queue/status`).
- Moodboard/prompt pencils save `KREA_MOODBOARD_ID_SKETCH_TO_REAL_*` / `PROMPT_SKETCH_TO_REAL_REEL_*` (see [`../UI_CONTROL_CONFIG.md`](../UI_CONTROL_CONFIG.md)).
