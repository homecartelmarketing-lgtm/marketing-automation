# Collection Category Story Automation Pipeline

The **Collection Category Story Automation Pipeline** generates branded **9:16 vertical Instagram Story collages (1080 x 1920 px)** for HomeCartel lighting product collections across 5 fixture categories. It composites 3 blended lifestyle interior photos into a balanced 3-row grid with automated brand logo and Poppins Bold product title typography.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Vertical Story Collage (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Grid Composition (3 Horizontal Slots of 1080 x 640 px)**:
  - **Slot 1 (Top)**: `Collection Category Blended Image1` (Y: `0 - 640 px`) + Title overlay.
  - **Slot 2 (Middle)**: `Collection Category Blended Image2` (Y: `640 - 1280 px`) + Title overlay.
  - **Slot 3 (Bottom)**: `Collection Category Blended Image3` (Y: `1280 - 1920 px`) + Title overlay.
  - **Top-Right**: Brand logo (`190.3 x 63.5 px` at `X=781.7`, `Y=108.0`).

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Step 0** | **Akeneo Scrape + Layout** | Akeneo PIM API & Shopify | Active Ingestion (`enabled=true`) with cross-table dedup | Akeneo Catalog | `Furniture Item[1-3]`, `Collection Category Layout` -> Status: `Pending` (`P`) |
| **Phase 1** | **Krea AI Room Interiors** | Krea AI | `krea-2-medium` (16:9, 1K)<br>Preset category Moodboard | 3 Room Prompts | `Interior1`, `Interior2`, `Interior3` -> Status: `Drafting` (`D`) |
| **Phase 2** | **Claude Sonnet 5 Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | Interior + Product Photos | `Prompt1`, `Prompt2`, `Prompt3` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `16:9`, Resolution: `1K` | `Interior[1-3]` + `Furniture[1-3]` + `Prompt[1-3]` | `Collection Category Blended Image[1-3]` -> Status: `Drafting` (`D`) |
| **Phase 4** | **9:16 Auto-Grid & Overlays** | **Local Python Pillow** | **Zero-API Local Python Script**<br>3-Row Stacking + Typography | `Blended Image 1/2/3` + `Logo` + `Item Names` | `Collection Category Converted` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{CC\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `CC` (Collection Category)
- **Content Format**: `STORY`
- **Fixture Codes**: `PE` (Pendant Light), `WL` (Wall Light), `CH` (Chandelier), `FL` (Floor Lamp), `CL` (Cluster Chandelier)

### Real-World Examples:
- `CC-STORY-PE-1` (Row 1 of Pendant Lights Collection Category Story)
- `CC-STORY-WL-4` (Row 4 of Wall Lights Collection Category Story)
- `CC-STORY-CH-9` (Row 9 of Chandeliers Collection Category Story)
- `CC-STORY-FL-2` (Row 2 of Floor Lamps Collection Category Story)
- `CC-STORY-CL-7` (Row 7 of Cluster Chandeliers Collection Category Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pendant Lights** | `PE` | `tblSSVJnubFk2yBm3` | `CC-STORY-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `AIRTABLE_TABLE_ID_CC_STORY_PENDANT` |
| **Wall Lights** | `WL` | `tbl98UU0h4uFyFIlL` | `CC-STORY-WL` | `20c3beaf-0995-44bf-a7a3-ac790fe8f315` | `AIRTABLE_TABLE_ID_CC_STORY_WALL_LIGHT` |
| **Chandeliers** | `CH` | `tblJMJQlrnlDb1GtN` | `CC-STORY-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_CC_STORY_CHANDELIER` |
| **Floor Lamps** | `FL` | `tblloZLRSKwOCg247` | `CC-STORY-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_CC_STORY_FLOOR_LAMP` |
| **Cluster Chandeliers** | `CL` | `tblsXXcoZZD4q6WWt` | `CC-STORY-CL` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CC_STORY_CLUSTER` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped Akeneo product awaiting generation.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Krea 16:9 generation, Claude prompt analysis, or Fal blending.
- **`For Modification` (`FM`)**: Flagged for collage re-alignment or item substitution.
- **`Completed` (`C`)**: 3-row collage assembled, typography stamped, and attached.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow Layout Specs

Phase 4 executes **Zero-API Local Python Pillow** grid compositing:
- **Brand Logo Coordinates (`HOMECARTEL_LOGO_BOX`)**:
  - Width: `190.3 px`, Height: `63.5 px`
  - Position: `X=781.7 px`, `Y=108.0 px`
- **Product Title Coordinates (Poppins Bold, 30px)**:
  - Left Margin: `X=90.2 px`
  - Slot 1 (Top): `Y=548.9 px` (`Item Name` / `Item Name1`)
  - Slot 2 (Middle): `Y=1188.9 px` (`Item Name2`)
  - Slot 3 (Bottom): `Y=1828.9 px` (`Item Name3`)
  - Color: `#FFFFFF` with drop shadow `(0, 0, 0, 180)` for high contrast.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive menu (select category and phase)
python generate_collection_category_story_pipeline.py --mode menu

# Run full pipeline for Pendant Lights (tblSSVJnubFk2yBm3)
python generate_collection_category_story_pipeline.py --mode all

# Target Wall Lights table
python generate_collection_category_story_pipeline.py --table-id tbl98UU0h4uFyFIlL --mode all

# Run Phase 4 local Pillow assembly only
python generate_collection_category_story_pipeline.py --mode conversion
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Collection Category Stories**.
5. Select category (**Pendant**, **Wall Light**, **Chandelier**, **Floor Lamp**, or **Cluster**).
6. Select rows and trigger generation.
