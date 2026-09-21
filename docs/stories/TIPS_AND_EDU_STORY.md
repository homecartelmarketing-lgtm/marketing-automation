# Tips & Educational Story Automation Pipeline

The **Tips & Educational Story Automation Pipeline** generates branded **9:16 vertical Instagram and Facebook Stories (1080 x 1920 px)** for HomeCartel lighting collections across 6 fixture categories. It pairs a photorealistic AI room interior with a lighting product, tags product details, and converts it into an infographic-style educational story card.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Vertical Story (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - Educational Infographic card combining room interior, lighting installation context, and design recommendations in a clean editorial Canva template format.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape + Layout** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, etc.) | `Furniture Item`, `Tips and Edu Story Layout` -> Status: `Pending` (`P`) |
| **Phase 2** | **Krea Room Interior** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Category Moodboard ID | Standby record + Room Prompt | `Interior Photo Generated` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Claude Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | Interior + Product Photos | `Prompt` -> Status: `Drafting` (`D`) |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI + Local YOLO | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | Interior + Product + Prompt | `Blended Image` & `Multiple Angle Blended Image` -> Status: `Drafting` (`D`) |
| **Phase 5** | **Story Layout Conversion** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Blended Image` + `Tips and Edu Story Layout` | `Tips and Edu Story Converted` -> Status: `Completed` (`C`) |

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
| **Pendant Lights** | `PE` | `tblwnFN5a8fLzKuP4` | `TNE-STORY-PE` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | `AIRTABLE_TABLE_ID_TNE_STORY_PENDANT` |
| **Floor Lamps** | `FL` | `tblJxWwZexgBHl26B` | `TNE-STORY-FL` | `b1641228-beec-4823-8d01-1de3eec8410d` | `AIRTABLE_TABLE_ID_TNE_STORY_FLOOR_LAMP` |
| **Chandeliers** | `CH` | `tblpFiaNn1Ym9fTTk` | `TNE-STORY-CH` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_TNE_STORY_CHANDELIER` |
| **Ceiling Mounted** | `CM` | `tblGlRibUZXB9R3Gt` | `TNE-STORY-CM` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_TNE_STORY_CEILING_MOUNTED` |
| **Table Lamps** | `TL` | `tblZtENqILDAekLv2` | `TNE-STORY-TL` | `257569e1-7be8-4412-a90f-acbc347e4646` | `AIRTABLE_TABLE_ID_TNE_STORY_TABLE_LAMP` |
| **Cluster Chandeliers** | `CL` | `tbllzkE2prSyj9BaD` | `TNE-STORY-CL` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_TNE_STORY_CLUSTER` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped Akeneo product awaiting generation.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Krea room generation, Claude prompt analysis, or Fal blending.
- **`For Modification` (`FM`)**: Flagged for layout adjustment or prompt tweaking.
- **`Completed` (`C`)**: Story graphic converted and verified in Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow & YOLO Detection Specs

- **Zero-Cost YOLO-World**: Local zero-API object detection tags bounding boxes around the lighting fixture to coordinate layout positioning without third-party API expense.
- **Brand Logo Coordinates (`HOMECARTEL_STORY_LOGO_BOX`)**:
  - Sourced from Airtable `Logo` attachment field (or local fallback `assets/homecartel_logo.png`).
  - Target Placement: Top-right corner of 9:16 vertical canvas (`1080 x 1920 px`).
  - Coordinate Box: $X = 781.7\text{ px}, Y = 108.0\text{ px}$ (exact 108 px top & right margins).
  - Box Size: $\text{Width} = 190.3\text{ px}, \text{Height} = 63.5\text{ px}$.
  - Stamped 100% locally via Python Pillow (`PIL`) with Lanczos antialiasing and alpha-mask blending for zero API cost and razor-sharp brand rendering on final story conversions.
- **Typography & Bounding Box Rules**: When local text compositing is active, titles render using `Poppins-Bold.ttf` with soft Gaussian blur drop shadows for high legibility across diverse room tones.
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
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Tips & Edu Stories**.
5. Pick fixture category (**Pendant**, **Floor Lamp**, **Chandelier**, **Ceiling Mounted**, **Table Lamp**, or **Cluster**).
6. Select rows and trigger generation.
