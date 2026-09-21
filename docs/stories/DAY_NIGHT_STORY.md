# Day & Night Story Automation Pipeline

The **Day & Night Story Automation Pipeline** generates high-converting **9:16 vertical Instagram Stories (1080 x 1920 px)** contrasting day and night illumination for HomeCartel lighting collections across 5 fixture categories. Each row produces a 2-card sequence: daytime natural interior ambiance and dramatic illuminated night transformation.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: 2-Card Vertical Story Set (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Card 1 (`Day Mode`)**: Bright sunlit room interior with the fixture realistically mounted and official HomeCartel® logo stamped at top-right (`X=781.7`, `Y=108.0`).
  - **Card 2 (`Night Mode`)**: Warm, dramatic night ambiance showcasing the fixture illuminated with realistic light bloom and rich atmospheric shadows.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, etc.) | `Furniture Item`, `SKU`, `Item Name` -> Status: `Pending` (`P`) |
| **Phase 1** | **Krea Room Interior** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Preset category Moodboard | Standby record + Room Prompt | `Interior Generated Photo` -> Status: `Drafting` (`D`) |
| **Phase 2** | **Claude Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Generated Photo` + `Furniture Item` | `Blending Prompt` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Nano Banana Pro Day Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Interior Photo` + `Furniture Item` + `Blending Prompt` | `day_photo_raw.jpg` -> Status: `Drafting` (`D`) |
| **Phase 4** | **Nano Banana Pro Night Transform**| Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `day_photo_raw.jpg` + Night Transformation Prompt | `night_photo.jpg` -> Status: `Drafting` (`D`) |
| **Phase 5** | **Local PIL Logo Stamping** | **Local Python Pillow** | **Zero-API Local Python Script**<br>Top-right margin: $108\text{ px}$ | `day_photo_raw.jpg` + `Logo` | Uploads both cards to `STORY - Day & Night (2)` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{DN\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `DN` (Day & Night)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp), `TL` (Table Lamp), `CL` (Cluster Chandelier)

### Real-World Examples:
- `DN-STORY-CH-1` (Row 1 of Chandelier Day & Night Story)
- `DN-STORY-PE-4` (Row 4 of Pendant Lights Day & Night Story)
- `DN-STORY-FL-7` (Row 7 of Floor Lamp Day & Night Story)
- `DN-STORY-TL-3` (Row 3 of Table Lamp Day & Night Story)
- `DN-STORY-CL-8` (Row 8 of Cluster Chandelier Day & Night Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblKkCf88UVQ3Yu07` | `DN-STORY-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_DN_STORY_CHANDELIER` |
| **Pendant Lights** | `PE` | `tblaNyYZCR7E6TXtv` | `DN-STORY-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `AIRTABLE_TABLE_ID_DN_STORY_PENDANT` |
| **Floor Lamps** | `FL` | `tblr1hlsjGcs9QKCy` | `DN-STORY-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_DN_STORY_FLOOR_LAMP` |
| **Table Lamps** | `TL` | `tblhvM9Saq18YqONB` | `DN-STORY-TL` | `257569e1-7be8-4412-a90f-acbc347e4646` | `AIRTABLE_TABLE_ID_DN_STORY_TABLE_LAMP` |
| **Cluster Chandeliers** | `CL` | `tblgcvB4WFKOpSIQl` | `DN-STORY-CL` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_DN_STORY_CLUSTER` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting daytime interior generation.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Krea or Fal AI.
- **`For Modification` (`FM`)**: Flagged for lighting re-balancing or atmosphere adjustment.
- **`Completed` (`C`)**: Both daytime stamped card and night card attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow Layout Specs

Phase 5 executes **Zero-API Local Python Pillow** brand logo stamping:
- **Brand Logo Coordinates (`HOMECARTEL_STORY_LOGO_BOX`)**:
  - Width: `190.3 px`, Height: `63.5 px`
  - Position: `X=781.7 px`, `Y=108.0 px` (Exact 108 px top & right margins)
- **Zero API Rule**: Only the local Pillow engine is used to composite the logo, preserving cloud credits.
- **Alpha Protection**: Automatically removes black and white bounding canvases from logo attachments.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive category menu
python run_day_night_story.py

# Run for Chandeliers
python run_day_night_story.py --target chandeliers

# Run for Pendant Lights (process 3 records)
python run_day_night_story.py --target pendant_lights --limit 3

# Target specific Airtable Record ID
python run_day_night_story.py --record-id rechngJM56W0l7aKn

# Dry run test mode
python run_day_night_story.py --dry-run
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Day & Night Stories**.
5. Pick fixture category (**Chandelier**, **Pendant**, **Floor Lamp**, **Table Lamp**, or **Cluster**).
6. Select rows and trigger generation.
