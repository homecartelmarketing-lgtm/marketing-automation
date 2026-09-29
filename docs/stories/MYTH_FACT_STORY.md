# Myth & Fact Story Automation Pipeline

The **Myth & Fact Story Automation Pipeline** produces an educational, high-engagement 4-slide sequence for **9:16 vertical Instagram/Facebook Stories (1080 x 1920 px)**. It debunks common home lighting misconceptions by contrasting a popular lighting "Myth" against an architectural lighting "Fact" using photorealistic product imagery.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: 4-Slide Story Sequence (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 1 (`Debunk Cover`)**: Editorial hook slide establishing the lighting dilemma (`debunk_myth_layout.jpg`).
  - **Slide 2 (`Myth Slide`)**: Visual illustration of the common myth (`myth_blended.jpg` / `myth1.jpg`).
  - **Slide 3 (`Fact Slide`)**: Correct luxury lighting application showcasing the HomeCartel product (`fact_blended.jpg` / `fact1.jpg`).
  - **Slide 4 (`Outro Slide`)**: Branded call-to-action outro (`assets/Outro-Myth-Fact.png`).

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`, `floor_lamps`, `pendants`) | `Furniture item`, `Item Name`, `SKU` -> Status: `Pending` (`P`) |
| **Phase 1** | **Debunk Hook Cover** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16` | Debunk layout template + product | `debunk_layout.jpg` -> Status: `In Progress` (`P`) |
| **Phase 2** | **Myth Generation** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16` | `myth_slide.json` prompt + product | `myth_blended.jpg` -> Status: `In Progress` (`P`) |
| **Phase 3** | **Fact Generation** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16` | Fact lighting prompt + product | `fact_blended.jpg` -> Status: `In Progress` (`P`) |
| **Phase 4** | **Branded Outro & Assembly** | Local Storage / Pillow | Zero-API Local Compositor | `assets/Outro-Myth-Fact.png` | Uploads all 4 slides to `STORY - Myth & Fact (4)` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{MNF\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `MNF` (Myth & Fact)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier), `FL` (Floor Lamp), `PE` (Pendant Light)

### Real-World Examples:
- `MNF-STORY-CH-1` (Row 1 of Chandelier Myth & Fact Story)
- `MNF-STORY-FL-5` (Row 5 of Floor Lamp Myth & Fact Story)
- `MNF-STORY-PE-3` (Row 3 of Pendant Lights Myth & Fact Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tbl3OI7crWvN2Q7u6` | `MNF-STORY-CH` | `AIRTABLE_TABLE_ID_CHANDELIER_MYTH_AND_FACT` |
| **Floor Lamps** | `FL` | `tblf5Yaki4ktwiLtx` | `MNF-STORY-FL` | `AIRTABLE_TABLE_ID_FLOOR_LAMP_MYTH_AND_FACT` |
| **Pendant Lights** | `PE` | `tblwBnWYRGcV6as45` | `MNF-STORY-PE` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MYTH_AND_FACT` |

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

## 6. Local Pillow & Template Asset Specs

- **Template Assets**:
  - Cover Hook: `JSON Prompts/Myth and Fact/debunk_myth_layout.jpg`
  - Myth Prompt: `JSON Prompts/Myth and Fact/myth_slide.json`
  - Branded Outro: `assets/Outro-Myth-Fact.png`
- **Zero API Outro Assembly**: The final outro card uses local file assets, eliminating cloud generation cost.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run 1 row end-to-end for Chandeliers
python run_myth_and_fact_story.py

# Process 3 rows in batch
python run_myth_and_fact_story.py --batch-size 3

# Target specific record ID
python run_myth_and_fact_story.py --record-id recBOCgsmJGNOxlhu

# Dry run test mode
python run_myth_and_fact_story.py --dry-run
```

### Web UI Dashboard Execution
1. Open http://localhost:5200 in your web browser.
2. Enter the Studio PIN if DASHBOARD_PIN is configured.
3. Click the **Story** tab in the main navigation.
4. Select the **Myth & Fact Story** subtab.
5. Pick an active fixture category.
6. Click the **Run** button on the fixture card, confirm the batch count (default 1) in the confirmation modal, and the pipeline will scrape a fresh active product and process it end-to-end.
