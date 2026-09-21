# 1 Product, 3 Styles Feed Automation Pipeline

The **1 Product, 3 Styles Feed Automation Pipeline** takes a single HomeCartel lighting product and seamlessly blends it into **3 distinct luxury architectural interior styles** at **4:5 vertical Instagram Feed format (1080 x 1350 px)**, applying the official HomeCartel® brand mark onto the first slide using local Pillow compositing.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1350 px` (Aspect Ratio `4:5`)
- **Format**: 3-Slide Instagram Carousel / Feed Post
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 1 (`1_product_3_styles_blended1_watermarked.jpg`)**: Luxury Style 1 (e.g., Grand Living Room) with HomeCartel® logo stamped at exact Canva coordinates.
  - **Slide 2 (`1_product_3_styles_blended2.jpg`)**: Luxury Style 2 (e.g., Formal Dining Room / Kitchen Island).
  - **Slide 3 (`1_product_3_styles_blended3.jpg`)**: Luxury Style 3 (e.g., High-Ceiling Foyer / Reading Nook).
- **Dual Airtable Output Attachments** (both carry the same stamped slides):
  - **`1 Product 3 Style Blended`**: 3 lifestyle room blends — every slide stamped with the floating YOLO-detected item-name tag (e.g., "Tally" + "Pendant Light"); Slide 1 additionally carries the official brand logo.
  - **`Blended Image with Name text`**: mirror of the same 3 name-stamped slides for the tagging/audit column.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Ingestion** | Akeneo PIM API | Active Ingestion (`enabled=true`) with cross-table deduplication | Akeneo Catalog (`chandeliers`, `pendant_lights`, `floor_lamps`) | `Furniture Item`, `SKU`, `Item Name` -> Status: `Pending` (`P`) |
| **Phase 2** | **Krea 3-Style Interiors** | Krea AI | `krea-2-medium` (4:5, 1K)<br>Preset category Moodboards | 3 Category Room Prompts | `Interior1`, `Interior2`, `Interior3` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Claude Vision Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Furniture Item` + 3 Room Interiors | `Prompt1`, `Prompt2`, `Prompt3` -> Status: `Drafting` (`D`) |
| **Phase 4** | **Nano Banana Pro Blending, YOLO Name Tagging & Logo Stamping** | Fal AI + Local YOLO-World + Local PIL | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K`<br>In-place YOLO item-name tags on all 3 slides, then local Pillow logo on Slide 1 | `Furniture Item` + Interiors + Prompts + `Logo` | Uploads 3 stamped slides to `1 Product 3 Style Blended` |
| **Phase 5** | **Tag Column Mirror** | Local (zero cost) | Copies the same stamped slides into the tagging column | 3 stamped slides + `Item Name` | Uploads 3 stamped slides to `Blended Image with Name text` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{OP3S\text{-}FEEDS\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `OP3S` (1 Product, 3 Styles)
- **Content Format**: `FEEDS`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp)

### Real-World Examples:
- `OP3S-FEEDS-CH-1` (Row 1 of Chandelier 1 Product 3 Styles Feed)
- `OP3S-FEEDS-PE-5` (Row 5 of Pendant Lights 1 Product 3 Styles Feed)
- `OP3S-FEEDS-FL-11` (Row 11 of Floor Lamp 1 Product 3 Styles Feed)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Default Style 1 Krea Prompt | Primary Environment Variables |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblrlfqBGe5EjS5PI` | `OP3S-FEEDS-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `Generate me a luxury modern grand living room with hanging chandelier` | `AIRTABLE_TABLE_ID_CHANDELIER_1_PRODUCT_3_STYLES`<br>`ONE_PRODUCT_3_STYLES_PROMPT_CHANDELIER` |
| **Pendant Lights** | `PE` | `tblRy52kCasisCWzd` | `OP3S-FEEDS-PE` | `2a4a62bf-c6eb-49f8-8808-2543200634a0` | `Generate me a luxury modern dining room with hanging pendant light` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_1_PRODUCT_3_STYLES`<br>`ONE_PRODUCT_3_STYLES_PROMPT_PENDANT` |
| **Floor Lamps** | `FL` | `tbl9GIq2QeYCwMhWU` | `OP3S-FEEDS-FL` | `b1641228-beec-4823-8d01-1de3eec8410d` | `Generate me a luxury modern living room lounge with standing floor lamp` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_1_PRODUCT_3_STYLES`<br>`ONE_PRODUCT_3_STYLES_PROMPT_FLOOR_LAMP` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Freshly scraped product awaiting interior generation.
- **`Scheduled` (`S`)**: Queued for batch generation.
- **`Drafting` (`D`)**: Processing through Krea 3-style generation, Claude prompt analysis, or Fal blending.
- **`For Modification` (`FM`)**: Flagged for aesthetic review or room re-rendering.
- **`Completed` (`C`)**: All 3 slides generated, watermarked, and attached.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow & Item Tagging Layout Specs

### A. Slide 1 Brand Logo (`HOMECARTEL_LOGO_BOX`)
The Slide 1 watermark uses **Zero-API Local Python Pillow** execution:
- **Placement Coordinates**:
  - Width: `190.3 px`, Height: `63.5 px`
  - X Coordinate (Left): `108.0 px`
  - Y Coordinate (Top): `1178.5 px`
  - Rotation: `0°`
- **Quality Control**: Alpha composite trimming and aspect-ratio preservation ensures crisp brand marks on dark and bright textures without cloud API costs.

### B. YOLO-World Item Detection & Name Tagging (baked into posted slides + mirrored to `Blended Image with Name text`)
All 3 blended room images are automatically processed through local zero-cost vision tagging BEFORE uploading:
- **Vision Model**: Open-Vocabulary YOLO-World detects the lighting fixture bounding box within each architectural room.
- **Dynamic Tag Placement**: Computes an optimal floating badge adjacent to the light fixture, ensuring zero overlap with the primary product geometry.
- **Typography Engine**:
  - Line 1 (Product Name): `Poppins-Bold.ttf` (White text with soft Gaussian drop shadow).
  - Line 2 (Category): `Poppins-Light.ttf` (e.g. "Chandelier", "Pendant Light", "Floor Lamp").
- **Airtable Destination**: The stamped slides are uploaded to **`1 Product 3 Style Blended`** (the posted carousel) and mirrored to **`Blended Image with Name text`** on completion.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive category menu
python run_1_product_3_styles_feed.py

# Run all 4 phases for Chandeliers with custom Style 1 prompt
python run_1_product_3_styles_feed.py --target chandeliers --phase all --prompt "Generate me a luxury modern grand living room with hanging chandelier"

# Run all 4 phases for Pendant Lights
python run_1_product_3_styles_feed.py --target pendant_lights --phase all

# Run all 4 phases for Floor Lamps
python run_1_product_3_styles_feed.py --target floor_lamps --phase all

# Mass scrape only
python run_1_product_3_styles_feed.py --target chandeliers --phase 1 --max-rows 3
```

### Web UI Dashboard Execution
1. Navigate to `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Feed** tab.
4. Select **1 Product 3 Styles Feeds** (Subtab 4).
5. View or click **`PR: <prompt>`** on any fixture card to edit the Style 1 Krea interior prompt (persisted to `.env`).
6. Click **`MB: <id>`** to edit the Krea Moodboard ID.
7. Click **Run** to execute the 4-phase generation pipeline.

