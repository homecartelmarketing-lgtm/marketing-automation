# Product Closeup w/ Description Story Automation Pipeline

The **Product Closeup w/ Description Story Automation Pipeline** generates editorial **9:16 vertical Instagram Stories (1080 x 1920 px)** combining macro product detail photography with an elegant narrative product description layout across 6 lighting categories.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Vertical Story (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Hero Card (`Product Closeup Description Converted`)**: Macro product image cleanly embedded within an editorial narrative layout highlighting materials, design philosophy, and dimensions.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + layout auto-fill & cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, etc.) | `Furniture Item`, `Item Name`, `SKU`, `Product Closeup Description Layout` -> Status: `Pending` (`P`) |
| **Phase 1** | **Story Card Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Furniture Item` + `Product Closeup Description Layout` | `Product Closeup Description Converted` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{PCD\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `PCD` (Product Closeup Description)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp), `CL` (Cluster Chandelier), `TL` (Table Lamp), `WL` (Wall Light)

### Real-World Examples:
- `PCD-STORY-CH-1` (Row 1 of Chandelier Product Description Story)
- `PCD-STORY-PE-3` (Row 3 of Pendant Lights Product Description Story)
- `PCD-STORY-FL-6` (Row 6 of Floor Lamp Product Description Story)
- `PCD-STORY-CL-2` (Row 2 of Cluster Chandelier Product Description Story)
- `PCD-STORY-TL-5` (Row 5 of Table Lamp Product Description Story)
- `PCD-STORY-WL-8` (Row 8 of Wall Lights Product Description Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblDcT6jovdAbKnfw` | `PCD-STORY-CH` | `AIRTABLE_TABLE_ID_PCD_STORY_CHANDELIER` |
| **Pendant Lights** | `PE` | `tblDD2w4v0Idb4jAZ` | `PCD-STORY-PE` | `AIRTABLE_TABLE_ID_PCD_STORY_PENDANT` |
| **Floor Lamps** | `FL` | `tblPvHyKGByWJCMtY` | `PCD-STORY-FL` | `AIRTABLE_TABLE_ID_PCD_STORY_FLOOR_LAMP` |
| **Cluster Chandeliers** | `CL` | `tblnIOQVywHcTgAtv` | `PCD-STORY-CL` | `AIRTABLE_TABLE_ID_PCD_STORY_CLUSTER` |
| **Table Lamps** | `TL` | `tbl5S9JEHSrjrLwxA` | `PCD-STORY-TL` | `AIRTABLE_TABLE_ID_PCD_STORY_TABLE_LAMP` |
| **Wall Lights** | `WL` | `tblYqudlgjYMNRROM` | `PCD-STORY-WL` | `AIRTABLE_TABLE_ID_PCD_STORY_WALL_LIGHT` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting layout blending.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Fal AI generation.
- **`For Modification` (`FM`)**: Flagged for layout or crop adjustment.
- **`Completed` (`C`)**: Story card generated and attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Template Assets & Validation Rules

- **Layout Template**: Automatically attaches local asset `templates/layout_product_v2.jpg` into `Product Closeup Description Layout`.
- **Active SKU Filtering**: Strictly queries `enabled=true` products from Akeneo PIM with cross-table deduplication across all 10 Story and 7 Feed tables.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive terminal menu
python "Product Closeup Description Story/4_Interactive_Menu.py"

# Run 1 item end-to-end for Chandeliers
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target chandeliers

# Run all 6 categories end-to-end
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target all

# Generate pending image cards only
python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target chandeliers
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Product Closeup Description Stories**.
5. Pick fixture category (**Chandelier**, **Pendant**, **Floor Lamp**, **Cluster**, **Table Lamp**, or **Wall Light**).
6. Select rows and trigger generation.
