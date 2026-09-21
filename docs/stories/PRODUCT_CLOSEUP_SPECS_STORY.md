# Product Closeup w/ Specs Story Automation Pipeline

The **Product Closeup w/ Specs Story Automation Pipeline** generates detailed commercial specification cards at **9:16 vertical Instagram Story format (1080 x 1920 px)**. It combines high-resolution product photography with an editorial Canva layout detailing dimensions, materials, and lighting specifications.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Vertical Story (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Hero Card (`PCS Story`)**: Macro product image cleanly embedded within an architectural specification layout showing technical dimensions, finish details, and brand identity.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + layout auto-fill & cross-table dedup | Akeneo Catalog (`chandeliers`) | `Furniture item`, `Item Name`, `Product Closeup w/ Specs Layout` -> Status: `Pending` (`P`) |
| **Phase 1** | **Specs Blending & Layout** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Furniture item` + `Product Closeup w/ Specs Layout` + `product_closeup_specs.json` | `PCS Story` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{PCS\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `PCS` (Product Closeup Specs)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier)

### Real-World Examples:
- `PCS-STORY-CH-1` (Row 1 of Chandelier Product Specs Story)
- `PCS-STORY-CH-4` (Row 4 of Chandelier Product Specs Story)
- `PCS-STORY-CH-12` (Row 12 of Chandelier Product Specs Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Template Asset & Prompt | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblEGTB6BodRVDqBV` | `PCS-STORY-CH` | Layout: `product_specs_layout.png`<br>Prompt: `product_closeup_specs.json` | `AIRTABLE_TABLE_ID_PCS_STORY_CHANDELIER` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting layout blending.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Fal AI Nano Banana Pro.
- **`For Modification` (`FM`)**: Flagged for spec adjustment or image repositioning.
- **`Completed` (`C`)**: `PCS Story` graphic uploaded and attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Template Assets & Validation Rules

- **Layout Template**: Automatically attaches local asset `templates/product_specs_layout.png` into `Product Closeup w/ Specs Layout`.
- **JSON Prompt**: Uses `templates/product_closeup_specs.json` for precise visual instruction formatting.
- **Active Filtering**: Scraper strictly enforces `enabled=true` from Akeneo PIM and checks all existing tables to prevent duplicate records.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive terminal menu
python "Product Closeup Specs Story/4_Interactive_Menu.py"

# Run full pipeline end-to-end (1 item)
python "Product Closeup Specs Story/1_Run_Full_Story_Automation.py"

# Generate pending records only
python "Product Closeup Specs Story/2_Generate_Pending_Stories.py"

# Scrape 1 new chandelier from Akeneo
python "Product Closeup Specs Story/3_Scrape_Akeneo_Chandeliers.py" --count 1

# Equivalent root-level scraper (supports --dry-run)
python scrape_product_specs_story.py --target chandeliers --max-items 1
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Product Closeup Specs Stories** (`tblEGTB6BodRVDqBV`).
5. Select target rows and click **Run Selected**.
