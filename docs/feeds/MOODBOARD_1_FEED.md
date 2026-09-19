# Moodboard #1 Feed Automation Pipeline

The **Moodboard #1 Feed Automation Pipeline** generates high-end editorial 4-slide Instagram carousels (`1080 x 1350 px`) showcasing HomeCartel lighting fixtures inside photorealistic designer living spaces, paired with a brand watermark, material swatch conversion, and macro closeup photography.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1350 px` (Aspect Ratio `4:5`)
- **Format**: 4-Slide Instagram Feed Carousel
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 1 (`Moodboard V1 Blended`)**: Luxury contemporary room interior with lighting fixture seamlessly blended and tagged with product name via local YOLO-World.
  - **Slide 2 (`Moodboard Added Watermark`)**: Slide 1 stamped with official HomeCartel® logo at bottom-left Canva coordinates (includes both item name and brand logo).
  - **Slide 3 (`Moodboard Converted`)**: Minimalist 3-swatch editorial material moodboard derived from interior textures.
  - **Slide 4 (`Closeup Photo`)**: High-end commercial macro detail photograph highlighting metal craftsmanship and finish.
- **Dual Tagged Attachment Fields**:
  - `Moodboard V1 Blended` (Primary Slide 1 blend with floating product badge)
  - `Blended Image with Name text` (Mirrored tagged blend for base-wide schema consistency)

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Catalog Ingestion (`enabled=true`) with cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, `floor_lamps`) | `Furniture Item`, `SKU`, `Item Name`, layouts -> Status: `Standby` |
| **Phase 1** | **Krea Room Interior** | Krea AI | `krea-2-medium` (4:5, 1K)<br>Preset Moodboard ID: `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | Standby record + Room Prompt | `Interior Generated` -> Status: `Interior Generated` |
| **Phase 2** | **Claude Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Generated` + `Furniture Item` | `Prompt for Blending` -> Status: `Generating Prompt for Blending` |
| **Phase 3** | **Nano Banana Pro Blending + YOLO Tagging** | Fal AI + Local YOLO-World | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K`<br>Local Zero-Cost YOLO-World & Poppins Pill Tagging | `Interior Generated` + `Furniture Item` + `Prompt for Blending` | `Moodboard V1 Blended` & `Blended Image with Name text` -> Status: `Blended Image Generated` |
| **Phase 4** | **Local PIL Logo Watermark** | **Local Python Pillow** | **Zero API / Local Python Script**<br>Box: $190.3 \times 63.5\text{ px}$ @ $(108.0, 1178.5)$ | `Moodboard V1 Blended` (Tagged) + `Logo` | `Moodboard Added Watermark` (Tag + Logo) -> Status: `Added Watermark Layout` |
| **Phase 5** | **Material Moodboard Gen** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Moodboard V1 Blended` + `Moodboard Layout` | `Moodboard Converted` -> Status: `Moodboard Converted` |
| **Phase 6** | **Macro Detail Photo** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Furniture Item` + `Closeup Photo Layout` | `Closeup Photo` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record generated or processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{MB1\text{-}FEEDS\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `MB1` (Moodboard #1)
- **Content Format**: `FEEDS`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp)

### Real-World Examples:
- `MB1-FEEDS-CH-1` (Row 1 of Chandelier Moodboard #1 Feed)
- `MB1-FEEDS-PE-4` (Row 4 of Pendant Lights Moodboard #1 Feed)
- `MB1-FEEDS-FL-9` (Row 9 of Floor Lamp Moodboard #1 Feed)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tbl9u5vjgx8kuE44R` | `MB1-FEEDS-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_CHANDELIER_MB1_FEED` |
| **Pendant Lights** | `PE` | `tblOvvYdgsNTXh2zK` | `MB1-FEEDS-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MB1_FEED` |
| **Floor Lamps** | `FL` | `tbl6uTmwM23KK9ocO` | `MB1-FEEDS-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_MB1_FEED` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped Akeneo product awaiting initial interior generation.
- **`Scheduled` (`S`)**: Queued for batch generation.
- **`Drafting` (`D`)**: Processing through Krea generation, Claude vision prompt analysis, or Fal blending.
- **`For Modification` (`FM`)**: Flagged for visual review or prompt regeneration.
- **`Completed` (`C`)**: All 4 carousel slides generated, watermarked, converted, and attached.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow & Item Tagging Layout Specs

### A. YOLO-World Item Detection & Name Tagging (`Moodboard V1 Blended`)
Before Slide 1 is uploaded to Airtable, local zero-cost vision tagging is executed:
- **Vision Model**: Open-Vocabulary YOLO-World detects the lighting fixture bounding box in the 4:5 room interior.
- **Dynamic Tag Placement**: Computes an optimal non-overlapping floating badge adjacent to the light fixture.
- **Typography Engine**:
  - Line 1 (Product Name): `Poppins-Bold.ttf` (White text with soft Gaussian drop shadow).
  - Line 2 (Category): `Poppins-Light.ttf` (e.g. "Chandelier", "Pendant Light", "Floor Lamp").
- **Airtable Destinations**: Uploaded as the primary image into **`Moodboard V1 Blended`** and mirrored into **`Blended Image with Name text`**.

### B. Slide 2 Brand Logo Stamping (`Moodboard Added Watermark`)
Phase 4 executes **Zero-API Local Python Pillow** logo stamping on top of the tagged Slide 1:
- **Brand Logo Placement (`HOMECARTEL_LOGO_BOX`)**:
  - Width: `190.3 px`, Height: `63.5 px`
  - X Coordinate (Left): `108.0 px` (Exact 108 px margin from left edge)
  - Y Coordinate (Top): `1178.5 px` (Exact 108 px margin from bottom edge: $1350 - 1178.5 - 63.5 = 108.0\text{ px}$)
  - Rotation: `0°`
- **Dual Stamped Output**: Slide 2 features BOTH the product name badge (near fixture) and the official brand logo (bottom-left) without spatial conflict.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run the complete pipeline for Chandeliers (tbl9u5vjgx8kuE44R)
python generate_moodboard_1_feed.py

# Run for at most 5 records
python generate_moodboard_1_feed.py --max-items 5

# Override destination table or Krea moodboard
python generate_moodboard_1_feed.py --table-id tbl9u5vjgx8kuE44R --moodboard-id de6ad512-870d-4ab7-a48c-3f3ca85faf24

# Scrape new chandelier products from Akeneo
python scrape_moodboard_1_feed.py --category chandeliers --max-items 5

# One-shot: scrape N new products then run the full 6-phase pipeline end-to-end
python run_full_moodboard_1_feed.py --category pendant_lights --max-items 3
# Also available as: python "Moodboard Feed/1_Run_Full_Moodboard_Feed.py"
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter security PIN: `1234`
3. Click the **Feed** tab in the top navigation.
4. Select the **Moodboard #1 Feeds** subtab.
5. Filter by status (`P`, `S`, `D`, `FM`, `C`) and click **Run Selected**.
