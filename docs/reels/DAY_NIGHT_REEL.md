# Day & Night Reel Automation Pipeline

The **Day & Night Reel Automation Pipeline** generates high-engagement **18-second 9:16 vertical video reels (1080 x 1920 px)** for social media (Instagram Reels, TikTok, YouTube Shorts). It demonstrates a lighting fixture (chandeliers, pendants, or floor lamps) in a luxury interior undergoing a seamless visual timelapse transition from daytime natural light to dramatic night illumination with warm light bloom, complete with jazz audio and brand outro.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Duration**: Total 18.0 seconds
  - **Timelapse Transition**: 15.0 seconds (Day illumination transitioning to warm evening light bloom).
  - **Branded Outro**: 3.0 seconds (`assets/outro_layout.jpg`).
- **Audio Profile**: 18.0 seconds Stereo AAC @ 192 kbps (automated ambient jazz soundtrack).

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape & Outro Sync**| Akeneo PIM API | Active Ingestion (enabled=true) + cross-table dedup | Akeneo Catalog (pendant_lights, chandeliers, loor_lamps) | Furniture Item, SKU, Item Name, Outro -> Status: Standby (P) |
| **Phase 2** | **Krea AI Room Interior** | Krea AI | krea-2-medium (9:16, 1K)<br>Preset category Moodboard | Standby record + Room Prompt | Interior -> Status: Phase 2 - Ready (P) |
| **Phase 3** | **Claude Vision Prompting** | Fal AI / OpenRouter | nthropic/claude-sonnet-5 | Interior + Furniture Item | Prompt for Blending -> Status: Phase 3 - Ready (P) |
| **Phase 4** | **Nano Banana Pro Day & Night Blending**| Fal AI | al-ai/nano-banana-pro/edit<br>Aspect Ratio: 9:16, Resolution: 1K | Interior + Furniture Item + Prompt for Blending | Day and Night Blended -> Status: Phase 4 - Ready (P) |
| **Phase 5** | **Airtable Blended Image Sync**| Local / Airtable REST | Attachment Sync to Airtable | Day and Night Blended | Airtable attachment fields -> Status: Phase 5 - Ready (P) |
| **Phase 6** | **Fal AI Kling Video Timelapse**| Fal AI | al-ai/kling-video/v3/turbo/pro/image-to-video<br>Duration: 15s, Resolution: 720p | Day and Night Blended | REEL - Day & Night -> Status: Phase 6 - Ready (P) |
| **Phase 7** | **Fal AI Stable Audio 3 / ElevenLabs Jazz**| Fal AI / ElevenLabs | al-ai/elevenlabs/music (18s luxury jazz) | Claude music prompt | Music Generated -> Status: Phase 7 - Ready (P) |
| **Phase 8** | **FFmpeg Concat & Outro Merge** | Local FFmpeg | Zero-API Local Video Compositor | 15s Kling video + 3s outro + 18s audio | Day and Night Reel with Music and Outro -> Status: Complete (C) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{DN\text{-}REEL\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `DN` (Day & Night)
- **Content Format**: `REEL`
- **Fixture Codes**: `PE` (Pendant Light), `CH` (Chandelier), `FL` (Floor Lamp)

### Real-World Examples:
- `DN-REEL-PE-1` (Row 1 of Pendant Lights Day & Night Reel)
- `DN-REEL-CH-5` (Row 5 of Chandelier Day & Night Reel)
- `DN-REEL-FL-3` (Row 3 of Floor Lamp Day & Night Reel)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Pendant Lights** | `PE` | `tblkTuM627s2f0FTN` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_NIGHT_REEL` |
| **Chandeliers** | `CH` | `tbl35JySlNuWh61tL` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CHANDELIERS_DAY_NIGHT_REEL` |
| **Floor Lamps** | `FL` | `tblVPgI4C6HEFcKW9` | `b1641228-beec-4823-8d01-1de3eec8410d` | `AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL` |

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

## 6. Local Outro & FFmpeg Merge Specifications

- **Branded Outro**: Automatically attaches and syncs `assets/outro_layout.jpg` to the `Outro` field.
- **FFmpeg Concat Filter**:
  ```bash
  ffmpeg -i 15s_timelapse.mp4 -loop 1 -t 3 -i outro.jpg -i jazz_music.mp3 -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]" -map "[v]" -map 2:a -c:v libx264 -pix_fmt yuv420p -shortest final_reel.mp4
  ```
- **Resumability**: Rows with completed final video attachments are permanently skipped to prevent duplicate API billing.

---

## 7. CLI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive runner menu
python run_day_night_reel.py

# Run for Pendant Lights
python run_day_night_reel.py --target pendant_lights

# Run for Chandeliers
python run_day_night_reel.py --target chandeliers

# Run for Floor Lamps
python run_day_night_reel.py --target floor_lamps

# Resume an interrupted row
python run_day_night_reel.py --target chandeliers --resume
```


### Web UI Dashboard Execution
1. Open http://localhost:5200 in your web browser.
2. Enter the Studio PIN if DASHBOARD_PIN is configured.
3. Click the **Reel** tab in the main navigation.
4. Select the **Day & Night Reel** subtab.
5. Pick an active fixture category (**Pendant Lights**, **Chandeliers**, or **Floor Lamps**).
6. Click the **Run** button on the fixture card, confirm the batch count (default 1) in the confirmation modal, and the pipeline will scrape a fresh active product and process it end-to-end.
