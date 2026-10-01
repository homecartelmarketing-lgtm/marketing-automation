# Sketch to Draw Reel Automation Pipeline

> [!NOTE]
> **Superseded by [Sketch to Real Reel](SKETCH_TO_REAL_REEL.md).** `generate_sketch_to_draw_reel_pipeline.py` is now a thin alias that calls the Sketch to Real pipeline's `main()`, and the Studio "Sketch to Real" subtab (`/api/sketch-to-draw-reel/*`) runs that pipeline. Rows get `STR-REEL-*` Foreign Key IDs (the `STD` table aliases in `foreign_key.py` map to `STR`). The design below (Nano Banana sketch, Kling/Grok video, caption, music) is the original spec and is **not** what the code does today; use the Sketch to Real doc for current behaviour, tables and commands.

The **Sketch to Draw Reel Automation Pipeline** generates high-engagement **~12-second 9:16 vertical video reels (1080 x 1920 px)** for social media (Instagram Reels, TikTok, YouTube Shorts). It demonstrates an architectural transformation: beginning with a hand-drawn pencil/blueprint sketch of a room interior featuring a HomeCartel lighting fixture that animates in real-time, line-by-line, and blossoms into a photorealistic, warmly illuminated luxury room interior, complete with an Instagram thumbnail cover, Claude copywriting, YOLO item tagging, and branded outro.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Structure & Timing**: Total ~12.0 seconds
  - **Scene 1 (Sketch & Title Hook)**: 2.0s hold — Architectural hand-drawn pencil sketch on drafting paper with centered luxury headline.
  - **Scene 2 (Drawing Timelapse Transition)**: 5.0s to 6.0s — Dynamic animation showing the pencil lines sketching, shadows shading in, textures materializing, and lighting blooming into realistic warmth.
  - **Scene 3 (Photorealistic Reveal)**: 2.5s hold — Photorealistic room interior with the fixture glowing, featuring a floating YOLO luxury product tag.
  - **Scene 4 (Branded Outro)**: 2.5s hold — Branded HomeCartel closing card (`assets/outro_layout.jpg`) with smooth 0.5s fade-in and audio fade-out.
- **Audio Profile**: Stereo AAC @ 192 kbps ambient luxury soundtrack with smooth outro fade.

---

## 2. Model Stack Phase Table (7 Phases)

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape & Catalog Verification** | Akeneo PIM API + Shopify Client | Active ingestion + strict Shopify catalog check + base-wide dedup | Fresh category product (Chandelier, Pendant, etc.) | `Furniture Item`, `SKU`, `Item Name`, `Price` -> Status: `In progress` |
| **Phase 2** | **Krea Room Interior Generation** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Preset category Moodboard | Category Moodboard ID + Room Prompt | `Room Interior`, `Interior Prompt` |
| **Phase 3** | **Claude Vision Prompting & Copywriting** | Fal AI | `anthropic/claude-sonnet-5` | Product Photo + Room Interior | `Blending Prompt`, `Sketch Prompt`, `Video Prompt`, `Reel Headline`, `Caption Generated` |
| **Phase 4** | **Nano Banana Pro Photorealistic Blend** | Fal AI + YOLO-World | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: 9:16, Resolution: 1K | Room Interior + Product + Blending Prompt | `Blended Image` + `Blended Image with Name text` |
| **Phase 5** | **Architectural Sketch & Cover Generation** | Fal AI + Local Pillow | `fal-ai/nano-banana-pro/edit` + Pillow Poppins Bold | `Blended Image` + Sketch Prompt + `Reel Headline` | `Sketch Image` + `Thumbnail with Generated Text` |
| **Phase 6** | **Drawing & Transition Animation** | Fal AI (Kling V3 Turbo Pro / Grok) or Local FFmpeg | Image-to-Video (5s, 9:16) or local crossfade dissolve | `Sketch Image` + `Blended Image` + Video Prompt | `Raw Video` |
| **Phase 7** | **FFmpeg Outro, Audio Mux & Completion** | Local FFmpeg (`imageio-ffmpeg`) | Zero-API Local Video Compositor | `Raw Video` + `assets/outro_layout.jpg` + Audio | `Final Video` + `Outro` -> Status: `Done` (C) + auto PHT timestamp |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{STD\text{-}REEL\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `STD` (Sketch To Draw)
- **Content Format**: `REEL`
- **Fixture Codes**:
  - `CH`: Chandeliers
  - `PE`: Pendant Lights
  - `FL`: Floor Lamps
  - `TL`: Table Lamps
  - `CM`: Ceiling Mounted
  - `SET`: Multi-fixture / Unified Table

### Real-World Examples:
- `STR-REEL-CH-1` (Row 1 of Chandeliers Sketch to Draw Reel)
- `STR-REEL-PE-4` (Row 4 of Pendant Lights Sketch to Draw Reel)
- `STR-REEL-FL-2` (Row 2 of Floor Lamps Sketch to Draw Reel)

---

## 4. Supported Categories & Environment Variables Map

| Category Name | Fixture Code | Primary Environment Variable | Fallback / Default Table ID | Default Krea Moodboard ID |
| :--- | :---: | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `AIRTABLE_TABLE_ID_CHANDELIERS_SKETCH_TO_DRAW_REEL` | `tblSketchToDrawChandeliers` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` |
| **Pendant Lights** | `PE` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_SKETCH_TO_DRAW_REEL` | `tblSketchToDrawPendants` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` |
| **Floor Lamps** | `FL` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_SKETCH_TO_DRAW_REEL` | `tblSketchToDrawFloorLamps` | `b1641228-beec-4823-8d01-1de3eec8410d` |
| **Table Lamps** | `TL` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_SKETCH_TO_DRAW_REEL` | `tblSketchToDrawTableLamps` | `fb2487fb-2895-4d2c-9758-805aaf1bac69` |
| **Ceiling Mounted** | `CM` | `AIRTABLE_TABLE_ID_CEILING_MOUNTED_SKETCH_TO_DRAW_REEL` | `tblSketchToDrawCeilingMounted` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` |
| **Unified Table** | `SET` | `AIRTABLE_TABLE_ID_SKETCH_TO_DRAW_REEL` | `tblSketchToDrawReel` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` |

---

## 5. Complete 24-Field Airtable Database Schema

| # | Field Name | Type | Operational Description |
| :-: | :--- | :--- | :--- |
| 1 | `Foreign Key ID` | `singleLineText` | Unique identifier (e.g. `STR-REEL-CH-1`) |
| 2 | `ID` | `number` / `autoNumber` | Row index counter |
| 3 | `Date and Time Generated` | `dateTime` (PHT) | Timestamp auto-injected when Status reaches Done |
| 4 | `Status` | `singleSelect` | `Standby`, `In progress`, `Scheduled`, `Done`, `Discarded`, `For Manual` |
| 5 | `Furniture Item` | `multipleAttachments` | Isolated cutout product photo from Akeneo PIM |
| 6 | `SKU` | `singleLineText` | Verified active SKU from Akeneo/Shopify |
| 7 | `Item Name` | `singleLineText` | Product title |
| 8 | `Category` | `singleLineText` / `singleSelect` | Lighting fixture category name |
| 9 | `Price` | `singleLineText` | Live retail price from Shopify catalog |
| 10 | `Room Interior` | `multipleAttachments` | 9:16 luxury room interior from Krea AI |
| 11 | `Interior Prompt` | `multilineText` | Prompt used to generate the interior |
| 12 | `Blending Prompt` | `multilineText` | Claude Sonnet 5 vision blend prompt |
| 13 | `Blended Image` | `multipleAttachments` | Photorealistic 9:16 room with installed and lit fixture |
| 14 | `Blended Image with Name text` | `multipleAttachments` | YOLO-World tagged variant with floating luxury pill badge |
| 15 | `Sketch Prompt` | `multilineText` | Architectural pencil sketch prompt |
| 16 | `Sketch Image` | `multipleAttachments` | 9:16 architectural graphite pencil blueprint on drafting paper |
| 17 | `Reel Headline` | `singleLineText` | Claude 3-5 word hook for cover and video |
| 18 | `Thumbnail with Generated Text` | `multipleAttachments` | 9:16 cover photo with dimmed sketch and centered Poppins typography |
| 19 | `Video Prompt` | `multilineText` | Drawing timelapse motion prompt for AI video engine |
| 20 | `Raw Video` | `multipleAttachments` | Generated drawing timelapse video clip |
| 21 | `Music Generated` | `multipleAttachments` | Background audio soundtrack |
| 22 | `Outro` | `multipleAttachments` | Branded HomeCartel Outro (`assets/outro_layout.jpg`) |
| 23 | `Final Video` | `multipleAttachments` | Final 9:16 vertical video reel with Outro and Audio |
| 24 | `Caption Generated` | `multilineText` | Ready-to-post Instagram caption with hashtags |

---

## 6. Execution Commands

### CLI Execution via PowerShell

```powershell
# Run for Chandeliers
python generate_sketch_to_draw_reel_pipeline.py --target chandeliers --max-items 1

# Run for Pendant Lights
python generate_sketch_to_draw_reel_pipeline.py --target pendant_lights --max-items 1

# Run with Zero-API local FFmpeg crossfade transition (no video API cost)
python generate_sketch_to_draw_reel_pipeline.py --target floor_lamps --video-engine ffmpeg

# Re-run a specific record
python generate_sketch_to_draw_reel_pipeline.py --record-id recXXXXXXXXXXXXXX
```

### Web Studio Execution (Port 5200)

1. Launch Studio: `python "UI Control/api_server.py"`
2. Open `http://localhost:5200` in your web browser.
3. Click the **Reel** tab in the main navigation.
4. Select the **Sketch to Real** subtab (Subtab 7; it runs the Sketch to Real pipeline, see the note at the top).
5. Pick an active fixture card (**Chandeliers** or **Pendant Lights**; the other fixtures have no Airtable table yet).
6. Click **Run**, confirm the batch count (default 1), and monitor real-time phase progress and streaming execution logs.
