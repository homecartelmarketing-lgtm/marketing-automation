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
| **Phase 1** | **Debunk Hook Cover** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16` | Debunk layout template + product | `debunk_layout.jpg` -> Status: `Drafting` (`D`) |
| **Phase 2** | **Myth Generation** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16` | `myth_slide.json` prompt + product | `myth_blended.jpg` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Fact Generation** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16` | Fact lighting prompt + product | `fact_blended.jpg` -> Status: `Drafting` (`D`) |
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
| **Chandeliers** | `CH` | `tbl3OI7crWvN2Q7u6` | `MNF-STORY-CH` | `AIRTABLE_TABLE_ID_MNF_STORY_CHANDELIER` |
| **Floor Lamps** | `FL` | `tblf5Yaki4ktwiLtx` | `MNF-STORY-FL` | `AIRTABLE_TABLE_ID_MNF_STORY_FLOOR_LAMP` |
| **Pendant Lights** | `PE` | `tblwBnWYRGcV6as45` | `MNF-STORY-PE` | `AIRTABLE_TABLE_ID_MNF_STORY_PENDANT` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting slide generation.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Fal AI generation.
- **`For Modification` (`FM`)**: Flagged for copy or visual adjustment.
- **`Completed` (`C`)**: All 4 slides generated and attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

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
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Myth & Fact Stories**.
5. Pick fixture category (**Chandelier**, **Floor Lamp**, or **Pendant**).
6. Select rows and trigger generation.
