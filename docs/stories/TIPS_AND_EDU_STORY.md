# Tips & Educational Story Automation Pipeline

The **Tips & Educational Story Automation Pipeline** generates branded **9:16 vertical Instagram and Facebook Stories (1080 x 1920 px)** for HomeCartel lighting collections across 6 fixture categories. It pairs a photorealistic AI room interior with a lighting product, tags product details, and converts it into an infographic-style educational story card.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Vertical Story (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - The blended room photo fills the canvas; a soft bottom gradient, the title **"Style Tip of the Day"**, a 2 px underline, a Claude-written styling tip and the HomeCartel logo are drawn on top locally.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape + Layout** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, etc.) | `Furniture Item`, `Tips and Edu Story Layout` -> Status: `Pending` (`P`) |
| **Phase 2** | **Krea Room Interior** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Category Moodboard ID | Standby record + Room Prompt | `Interior Photo Generated` -> Status: `In Progress` (`P`) |
| **Phase 3** | **Claude Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | Interior + Product Photos | `Prompt` -> Status: `In Progress` (`P`) |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI + Local YOLO | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | Interior + Product + Prompt | `Blended Image` & `Multiple Angle Blended Image` -> Status: `In Progress` (`P`) |
| **Phase 5** | **Story Layout (local Pillow)** | Fal AI (Claude tip only) + local Pillow | `anthropic/claude-sonnet-5` writes the tip; layout built by `overlay.py::create_tips_edu_story_image` (zero image-API cost) | `Blended Image` (the room photo is the background) | `Tips and Edu Story Converted` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{TNE\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `TNE` (Tips & Educational)
- **Content Format**: `STORY`
- **Fixture Codes**: `PE` (Pendant Light), `FL` (Floor Lamp), `CH` (Chandelier), `CM` (Ceiling Mounted), `TL` (Table Lamp), `CL` (Cluster Chandelier)

### Real-World Examples:
- `TNE-STORY-PE-1` (Row 1 of Pendant Lights Tips & Edu Story)
- `TNE-STORY-FL-5` (Row 5 of Floor Lamps Tips & Edu Story)
- `TNE-STORY-CH-8` (Row 8 of Chandeliers Tips & Edu Story)
- `TNE-STORY-CM-2` (Row 2 of Ceiling Mounted Tips & Edu Story)
- `TNE-STORY-TL-6` (Row 6 of Table Lamps Tips & Edu Story)
- `TNE-STORY-CL-3` (Row 3 of Cluster Chandeliers Tips & Edu Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pendant Lights** | `PE` | `tblwnFN5a8fLzKuP4` | `TNE-STORY-PE` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDU_STORY` |
| **Floor Lamps** | `FL` | `tblJxWwZexgBHl26B` | `TNE-STORY-FL` | `b1641228-beec-4823-8d01-1de3eec8410d` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_TIPS_EDU_STORY` |
| **Chandeliers** | `CH` | `tblpFiaNn1Ym9fTTk` | `TNE-STORY-CH` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CHANDELIERS_TIPS_EDU_STORY` |
| **Ceiling Mounted** | `CM` | `tblGlRibUZXB9R3Gt` | `TNE-STORY-CM` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CEILING_MOUNTED_TIPS_EDU_STORY` |
| **Table Lamps** | `TL` | `tblZtENqILDAekLv2` | `TNE-STORY-TL` | `257569e1-7be8-4412-a90f-acbc347e4646` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_TIPS_EDU_STORY` |
| **Cluster Chandeliers** | `CL` | `tbllzkE2prSyj9BaD` | `TNE-STORY-CL` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIERS_TIPS_EDU_STORY` |

---

### Provider credentials (isolated loader)
`run_tips_and_edu_story.py` loads credentials through `IsolatedAutomationSettings` in this order: `.env.tips-edu-story`, then the shared `.env`, then (hosted deployments such as Railway, which have no dotenv files) the **process environment variables**. Required: `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`, `AKENEO_HOST`, `AKENEO_CLIENT_ID`, `AKENEO_SECRET`, `AKENEO_USERNAME`, `AKENEO_PASSWORD`, `CHANNEL_NAME`, `KREA_API_TOKEN`, `FAL_KEY` (`AKENEO_STYLE` defaults to `modern`). The error names any that are missing.

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

## 6. Local Pillow & YOLO Detection Specs

- **Zero-Cost YOLO-World**: Local zero-API object detection tags bounding boxes around the lighting fixture to coordinate layout positioning without third-party API expense.
- **Brand Logo Coordinates (`HOMECARTEL_STORY_LOGO_BOX`)**:
  - Sourced from Airtable `Logo` attachment field (or local fallback `assets/homecartel_logo.png`).
  - Target Placement: Top-right corner of 9:16 vertical canvas (`1080 x 1920 px`).
  - Coordinate Box: $X = 781.7\text{ px}, Y = 108.0\text{ px}$ (exact 108 px top & right margins).
  - Box Size: $\text{Width} = 190.3\text{ px}, \text{Height} = 63.5\text{ px}$.
  - Stamped 100% locally via Python Pillow (`PIL`) with Lanczos antialiasing and alpha-mask blending for zero API cost and razor-sharp brand rendering on final story conversions.
- **Phase 5 Layout (`overlay.py::overlay_tips_edu_story_layout`)**: Nano Banana Pro is **not** used for the layout (it redrew the room, doubled the logo and printed prompt text). Measured from the Canva layout `JSON Prompts/Tips and Edu Story/stories (33).jpg`:
  - Title: Poppins **ExtraBold** (`content_automation/fonts/Poppins-ExtraBold.ttf`), 40 pt = 53.33 px (`CANVA_PT_TO_PX = 4/3`), ink at x=121, y=1369; 2 px underline at x=113-632, y=1437.
  - Tip: Poppins **Regular**, 28 pt = 37.33 px, origin x=113, y=1541, wrapped to 854 px, max 4 lines (shrinks only beyond that).
  - Legibility gradient: `TIPS_EDU_STORY_GRADIENT_START_Y` / `TIPS_EDU_STORY_GRADIENT_MAX_ALPHA` in `overlay.py` (set alpha to 0 to remove it).
  - Tip text: `content_automation/story_tip.py` asks Claude Sonnet 5 (via `fal_client.generate_claude_vision`, looking at the blended image) for one 12-20 word sentence; unusable replies or API errors fall back to a neutral per-category tip so the run still completes (`tip_used_fallback` is logged).
  - The layout image and `tips-and-edu.json` are no longer used for this story (the layout is still attached to the row for reference).
  - Tests: `tests/test_tips_edu_story_layout.py`.
- **Typography & Bounding Box Rules**: Other local text compositing renders titles with `Poppins-Bold.ttf` with soft Gaussian blur drop shadows for high legibility across diverse room tones.
- **Active Product Enforcement**: Ingestion strictly filters `enabled=true` products from Akeneo and verifies against all existing Story and Feed tables.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive category menu
python run_tips_and_edu_story.py

# Run all phases for Pendant Lights
python run_tips_and_edu_story.py --target pendant_lights --phase all

# Run all phases for Floor Lamps
python run_tips_and_edu_story.py --target floor_lamps --phase all

# Run all phases for Chandeliers
python run_tips_and_edu_story.py --target chandeliers --phase all

# Run specific phase (e.g. Phase 2 Krea generation)
python run_tips_and_edu_story.py --target pendant --phase 2
```

### Web UI Dashboard Execution
1. Open http://localhost:5200 in your web browser.
2. Enter the Studio PIN if DASHBOARD_PIN is configured.
3. Click the **Story** tab in the main navigation.
4. Select the **Tips & Educational Story** subtab.
5. Pick an active fixture category.
6. Click the **Run** button on the fixture card, confirm the batch count (default 1) in the confirmation modal, and the pipeline will scrape a fresh active product and process it end-to-end.
