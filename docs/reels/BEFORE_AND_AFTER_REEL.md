# Before & After Reel Automation Pipeline

The **Before & After Reel Automation Pipeline** generates captivating **9:16 vertical video transformation reels (1080 x 1920 px)**. It showcases an empty room interior transitioning into a fully styled architectural space featuring a HomeCartel lighting fixture across multiple angles, set to background music with centered typography.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Structure**:
  - **"Before" Scene**: Empty luxury room interior highlighting architectural potential.
  - **"After" Transformation (3 s)**: Installed and illuminated lighting fixture in the room, with the floating item-name tag (name + product type, YOLO placement) from `Blended Image with Name text`. If a row only has the plain `Blended Image`, the tag is stamped locally while the reel is built, so the name is always shown.
  - **Multiple Angle Details (2 s each)**: Close-up angles highlighting product textures (generated from the untagged blend; the name appears once, on the After slide).
  - **Branded Outro**: Call-to-action closing card.
- **Audio Profile**: Stereo AAC @ 192 kbps background music.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (enabled=true) + cross-table dedup | Akeneo Catalog (pendant_lights, chandeliers) | Furniture Item, Item Name, SKU -> Status: Standby (P) |
| **Phase 2** | **Krea Room Interior** | Krea AI | krea-2-medium (9:16, 1K)<br>Preset category Moodboard | Room Prompt | Interior Generated Photo -> Status: Processing (P) |
| **Phase 3** | **Claude Vision Prompting** | Fal AI / OpenRouter | nthropic/claude-sonnet-5 | Interior + Product Photos | Blending Prompt -> Status: Processing (P) |
| **Phase 4** | **Nano Banana Pro Day Blend** | Fal AI | al-ai/nano-banana-pro/edit<br>Aspect Ratio: 9:16, Resolution: 1K | Interior + Product + Prompt | Blended Image -> Status: Processing (P) |
| **Phase 5** | **FFmpeg Slideshow Reel Assembly**| Local FFmpeg | Zero-API Local Video Engine + ElevenLabs Audio | Blended Stills + Outro + Audio | Slide Show Before and After Reel -> Status: Complete (C) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{BA\text{-}REEL\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `BA` (Before & After)
- **Content Format**: `REEL`
- **Fixture Codes**: `FL` (Floor Lamp), `PE` (Pendant Light), `CH` (Chandelier)

### Real-World Examples:
- `BA-REEL-FL-1` (Row 1 of Floor Lamp Before & After Reel)
- `BA-REEL-PE-4` (Row 4 of Pendant Lights Before & After Reel)
- `BA-REEL-CH-8` (Row 8 of Chandelier Before & After Reel)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Floor Lamps** | `FL` | `tbl2VoWOt7sSut4E2` ⚠️ *(table no longer exists in the live base as of 2026-09-19 — recreate it before running `--target floor_lamps`)* | `b1641228-beec-4823-8d01-1de3eec8410d` | `AIRTABLE_TABLE_ID_BEFORE_AFTER_FLOOR_LAMPS` *(defined only in `.env.example`; not exposed in Studio — CLI `--target floor_lamps` only, which falls back to `AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL`)* |
| **Pendant Lights** | `PE` | `tbleUP86Kw36G8Hdw` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_BEFORE_AFTER_REEL` |
| **Chandeliers** | `CH` | `tbloMhCOngGDWFS2y` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CHANDELIERS_BEFORE_AFTER_REEL` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

The Airtable single-select Status field tracks records across 5 lifecycle stages:

| Badge | Color | Lifecycle State | Airtable Status Value | Operational Meaning |
| :---: | :---: | :--- | :--- | :--- |
| **P** | Sky Blue | **Posted / Processing** | Posted, Processing, Pending, In Progress, intermediate phase statuses | Record is actively queued or being processed. |
| **S** | Purple | **Scheduled** | Scheduled, Schedule | Approved and scheduled for publishing. |
| **C** | Emerald | **Complete / Done** | Complete, Completed, Done | All phases complete; deliverables attached. |
| **D** | Rose | **Discarded** | Discard, Discarded | Archived or rejected candidate. |
| **FM** | Amber | **For Manual / Revision** | For Manual, Minor revision, FM | Flagged for manual review or adjustment. |

### Execution Timestamp
When a row reaches Complete (C), the pipeline automatically writes the Philippine Standard Time timestamp (UTC+8, ISO 8601) into the **Date and Time Generated** field:
`
2026-09-07T13:12:00+08:00
`

---

## 6. Local Video & Typography Specs

- **Zero-API Video Compilation**: The multi-angle transitions, text overlay ("Before" / "After"), and outro concatenation execute locally via FFmpeg.
- **Google Drive Export**: Rendered reels are automatically mirrored to the local cache and Google Drive staging folder.

---

## 7. CLI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive runner
python run_before_after_reel.py

# Target Floor Lamps
python run_before_after_reel.py --target floor_lamps

# Target Pendant Lights
python run_before_after_reel.py --target pendant_lights

# Target Chandeliers
python run_before_after_reel.py --target chandeliers

# Explicit re-render of ONE existing row (the only case that touches an existing row)
python run_before_after_reel.py --target pendant_lights --record-id recXXXXXXXXXXXXXX
```

**Always a fresh row:** every run (CLI or Studio) scrapes a brand-new row from Akeneo and processes only that row; it never picks up old, remaining or incomplete rows (AGENTS.md §5). If the scraper creates no new row, the run exits with code 1 ("no new eligible product"). Generic phase runs skip Posted / Scheduled / Complete / For Manual rows.

**Phase markers:** the runner prints `[PHASE n/6]` lines (1 Akeneo scrape, 2 Krea interior, 3 Claude prompt, 4 Banana blend, 5 multiple angles, 6 slideshow) which the Studio route uses to show progress. Media downloads (blend, angles, slideshow assets) are retried; if an angle or the blended image cannot be fetched the row fails instead of producing a partial reel marked Complete. The blend phase stamps the item-name tag with YOLO into `Blended Image with Name text`, with the fixture category derived from the target or the item name.


### Web UI Dashboard Execution
1. Open http://localhost:5200 in your web browser.
2. Enter the Studio PIN if DASHBOARD_PIN is configured.
3. Click the **Reel** tab in the main navigation.
4. Select the **Before & After Reel** subtab.
5. Pick an active fixture category (**Pendant Lights** or **Chandeliers**).
6. Click the **Run** button on the fixture card, confirm the batch count (default 1) in the confirmation modal, and the pipeline will scrape a fresh active product and process it end-to-end.
