# This or That Story Automation Pipeline

The **This or That Story Automation Pipeline** generates high-engagement interactive voting **9:16 vertical Instagram Stories (1080 x 1920 px)** across 6 lighting categories. Each row pairs 2 complementary products from the same fixture family within a clean split-frame editorial voting template.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Interactive Vertical Story (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Voting Card (`Story This or That (1)` / `This or That Converted`)**: Dual-product comparison card pairing Option A (`Furniture Item`) and Option B (`Furniture Item2`) formatted for Instagram Story polling/slider stickers.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo 2-Product Scrape** | Akeneo PIM API | Active Ingestion (`enabled=true`) + pair layout auto-fill & cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, etc.) | `Furniture Item`, `Furniture Item2`, `Item Name`, `Item Name2`, `SKU`, `SKU2`, `This or That Layout` -> Status: `Pending` (`P`) |
| **Phase 2** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Furniture Item[1-2]` + `This or That Layout` | `Story This or That (1)` / `This or That Converted` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{TOT\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `TOT` (This or That)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp), `CL` (Cluster Chandelier), `TL` (Table Lamp), `WL` (Wall Light)

### Real-World Examples:
- `TOT-STORY-CH-1` (Row 1 of Chandelier This or That Story)
- `TOT-STORY-PE-4` (Row 4 of Pendant Lights This or That Story)
- `TOT-STORY-FL-2` (Row 2 of Floor Lamp This or That Story)
- `TOT-STORY-CL-5` (Row 5 of Cluster Chandelier This or That Story)
- `TOT-STORY-TL-3` (Row 3 of Table Lamp This or That Story)
- `TOT-STORY-WL-7` (Row 7 of Wall Lights This or That Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblo42IkuhYLIQBzk` | `TOT-STORY-CH` | `AIRTABLE_TABLE_ID_CHANDELIERS_THIS_OR_THAT` |
| **Pendant Lights** | `PE` | `tblS1VHp41RDfxztD` | `TOT-STORY-PE` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_THIS_OR_THAT` |
| **Floor Lamps** | `FL` | `tblaoqj8VPVHFmVQn` | `TOT-STORY-FL` | `AIRTABLE_TABLE_ID_FLOOR_LAMP_THIS_OR_THAT` |
| **Cluster Chandeliers** | `CL` | `tblYAhjKckXtjUayx` | `TOT-STORY-CL` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_THIS_OR_THAT` |
| **Table Lamps** | `TL` | `tblm1Ty2QkAlUcHJt` | `TOT-STORY-TL` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_THIS_OR_THAT` |
| **Wall Lights** | `WL` | `tblZw6jvSa27oZDiN` | `TOT-STORY-WL` | `AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped 2-product pair awaiting generation.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Fal AI Nano Banana Pro.
- **`For Modification` (`FM`)**: Flagged for layout or product pairing adjustment.
- **`Completed` (`C`)**: Story voting graphic generated and attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Template Assets & Validation Rules

- **Layout Template**: Automatically attaches local asset `assets/thisorthatlayout.jpg` into `This or That Layout`.
- **Product Pair Checking**: Scraper pairs two distinct active products from Akeneo, ensuring neither product has been previously used across other rows or tables.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive console menu
python "This or That Story/4_Interactive_Menu.py"

# Run 1 row end-to-end for Wall Lights
python "This or That Story/1_Run_Full_Story_Automation.py" --target wall_lights

# Run all 6 categories end-to-end
python "This or That Story/1_Run_Full_Story_Automation.py" --target all

# Generate pending records only
python "This or That Story/2_Generate_Pending_Stories.py" --target wall_lights

# Backfill layout watermark on pending records
python generate_this_or_that_pipeline.py --target all --mode backfill-layout
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **This or That Stories**.
5. Pick fixture category (**Chandelier**, **Pendant**, **Floor Lamp**, **Cluster**, **Table Lamp**, or **Wall Light**).
6. Select rows and trigger generation.
