# Moodboard #2 Feed Automation Pipeline

The **Moodboard #2 Feed Automation Pipeline** generates luxury **4:5 vertical Instagram Feed / Carousel posts (1080 x 1350 px)** for HomeCartel lighting and furniture products across 4 dedicated category tables. Each processed product yields a 2-slide carousel: an in-situ luxury room interior and an editorial architectural flat-lay moodboard.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1350 px` (Aspect Ratio `4:5`)
- **Format**: 2-Slide Instagram Carousel / Feed Post
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 1 (`Blended Image`)**: Photorealistic luxury room interior with the Akeneo lighting fixture mounted and illuminated.
  - **Slide 2 (`Moodboard #2 Converted`)**: Minimalist luxury vertical editorial flat-lay moodboard composed of two white-bordered interior photographs, 7–12 physical material swatches extracted from the room, and isolated design details arranged over an architectural background surface.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + layout auto-fill & cross-table dedup | Akeneo Catalog (`chandeliers`, `pendant_lights`, `floor_lamps`, `wall_lights`) | `Furniture Item`, `SKU`, `Item Name`, `Moodboard #2 Layout`, `Moodboard Converstion Fixed Prompt` -> Status: `Pending` (`P`) |
| **Phase 1** | **Krea Room Interior** | Krea AI | `krea-2-medium` (4:5, 1K)<br>Preset category Moodboard ID | Standby record + Category Room Prompt | `Interior Photo` -> Status: `Drafting` (`D`) |
| **Phase 2** | **Claude Vision Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Photo` + `Furniture Item` | `Blending Prompt` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Nano Banana Pro Blending & Brand Stamping** | Fal AI + **Local Python Pillow** | `fal-ai/nano-banana-pro/edit` + `HOMECARTEL_LOGO_BOX` ($190.3 \times 63.5\text{ px}$ @ $(108.0, 1178.5)$) | `Interior Photo` + `Furniture Item` + `Blending Prompt` | `Blended Image` (Watermarked) & `Blended Image with Name text` (YOLO-World tagged) -> Status: `In progress` |
| **Phase 4** | **Layout Verification** | Local Storage | Zero-API Local Template Ingestion | Local assets: `referencephoto_moodboard.png` & `second_moodboard.json` | Verifies attachment integrity |
| **Phase 5** | **Flat-Lay Conversion** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Moodboard #2 Layout` + `Blended Image` | `Moodboard #2 Converted` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{MB2\text{-}FEEDS\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `MB2` (Moodboard #2)
- **Content Format**: `FEEDS`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp), `WL` (Wall Light)

### Real-World Examples:
- `MB2-FEEDS-CH-1` (Row 1 of Chandelier Moodboard #2 Feed)
- `MB2-FEEDS-PE-6` (Row 6 of Pendant Lights Moodboard #2 Feed)
- `MB2-FEEDS-FL-3` (Row 3 of Floor Lamp Moodboard #2 Feed)
- `MB2-FEEDS-WL-8` (Row 8 of Wall Lights Moodboard #2 Feed)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tbltWgQKOYjuHw6tx` | `MB2-FEEDS-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_CHANDELIER_MOODBOARD_2_FEED` |
| **Pendant Lights** | `PE` | `tbl4TiV90SzdBz4KG` | `MB2-FEEDS-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARD_2_FEED` |
| **Floor Lamps** | `FL` | `tbl4YF9iXlBqGblEc` | `MB2-FEEDS-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_MOODBOARD_2_FEED` |
| **Wall Lights** | `WL` | `tbljUk9JwzS1JeZJg` | `MB2-FEEDS-WL` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_WALL_LIGHTS_MOODBOARD_2_FEED` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Freshly scraped record awaiting generation.
- **`Scheduled` (`S`)**: Queued for batch runner execution.
- **`Drafting` (`D`)**: Under active processing through Krea, Claude, or Fal.
- **`For Modification` (`FM`)**: Flagged for aesthetic adjustments.
- **`Completed` (`C`)**: Both `Blended Image` and `Moodboard #2 Converted` generated and attached.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Template Assets, Logo Stamping & Validation Rules

- **Editorial Reference Image**: Automatically attaches `JSON Prompts/Moodboard V2/referencephoto_moodboard.png` into `Moodboard #2 Layout` during ingestion.
- **Fixed Composition Prompt**: Automatically attaches `JSON Prompts/Moodboard V2/second_moodboard.json` into `Moodboard Converstion Fixed Prompt`.
- **Active SKU Enforcement**: Scraper strictly enforces `enabled=true` from Akeneo PIM and checks all existing tables to prevent duplicate records.
- **HomeCartel Feed Logo Stamping (`HOMECARTEL_LOGO_BOX`)**:
  - Automatically stamped locally onto `Blended Image` during Phase 3 before Airtable attachment.
  - Placement: $X=108.0\text{ px}$, $Y=1178.5\text{ px}$, Width: $190.3\text{ px}$, Height: $63.5\text{ px}$ on $1080 \times 1350\text{ px}$ canvas.
  - Sourcing: Resolves from Airtable `Logo` / `Logo Watermark` field or falls back to local `assets/homecartel_logo.png`.
- **YOLO-World Item Name Tagging**:
  - Automatically detects the mounted lighting fixture in the blended image.
  - Renders luxury typography badge with item name and product type into `Blended Image with Name text`.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive category selection menu
python run_full_moodboard_2_feed.py

# Run for chandeliers (tbltWgQKOYjuHw6tx)
python run_full_moodboard_2_feed.py --category chandeliers

# Run for pendant lights (tbl4TiV90SzdBz4KG)
python run_full_moodboard_2_feed.py --category pendant_lights

# Run for floor lamps (tbl4YF9iXlBqGblEc)
python run_full_moodboard_2_feed.py --category floor_lamps

# Run for wall lights (tbljUk9JwzS1JeZJg)
python run_full_moodboard_2_feed.py --category wall_lights

# Process multiple products (e.g. 3 items)
python run_full_moodboard_2_feed.py --category chandeliers --max-items 3
# Also available as: python "Moodboard Feed/2_Run_Full_Moodboard_2_Feed.py"

# Scrape new products only, without generating (e.g. 3 wall lights)
python scrape_moodboard_2_feed.py --category wall_lights --max-items 3
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter security PIN: `1234`
3. Click the **Feed** tab.
4. Select **Moodboard #2 Feeds**.
5. Select fixture category from dropdown (**Chandelier**, **Pendant**, **Floor Lamp**, or **Wall Light**).
6. Review rows and trigger batch runs.
