# Day & Night Feed Automation Pipeline

The **Day & Night Feed Automation Pipeline** generates high-engagement 4:5 Instagram Feed posts (`1080 x 1350 px`) contrasting natural daytime luxury room illumination with dramatic warm evening lighting showcasing HomeCartel lighting fixtures.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1350 px` (Aspect Ratio `4:5`)
- **Format**: 2-Slide Instagram Carousel / Comparative Feed Post
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 1 (`Day Mode`)**: Bright, natural daylight illumination showing architectural details and unlit or softly lit fixture.
  - **Slide 2 (`Night Mode`)**: Moody, warm golden-hour or evening ambiance showcasing the fixture fully turned on with realistic light bloom and dramatic shadow interplay.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`) | `Furniture Item`, `SKU`, `Item Name` -> Status: `Pending` (`P`) |
| **Phase 1** | **Krea Day Interior** | Krea AI | `krea-2-medium` (4:5, 1K)<br>Moodboard: `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | Room prompt ("Generate me a modern bright sunlit living room") | `Interior Generated Photo` -> Status: `Drafting` (`D`) |
| **Phase 2** | **Claude Day & Night Vision Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Generated Photo` + `Furniture Item` | `Blending Prompt` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Nano Banana Pro Day Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Interior Generated Photo` + `Furniture Item` + `Blending Prompt` | `Day Image` -> Status: `Processing Day Image` |
| **Phase 4** | **Nano Banana Pro Night Transformation** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Day Image` | `Night Image` -> Status: `Drafting` (`D`) |
| **Phase 5** | **Feed Logo Stamping & Local YOLO-World Tagging** | **Local Python (Pillow + YOLO-World)** | **Zero-API Local Overlay Engines** (`content_automation/overlay.py` + `content_automation/item_tagger.py`) | `Day Image` + `Night Image` + `Item Name`/`SKU` | `Blended Image with Name text` -> Status: `Completed` (`C`) |

> 🏷️ **Logo & Item-Name Watermark**: Slide 1 (`Day Mode`) is stamped with the HomeCartel brand logo at the standard Canva 4:5 bottom-left position (`HOMECARTEL_LOGO_BOX`: `X=108.0, Y=1178.5, W=190.3, H=63.5`). Then, both Slide 1 (with logo) and Slide 2 (`Night Mode`) receive an open-vocabulary YOLO-World floating item-name tag (`Item Name` + `Product Type`) rendered in pure solid white Poppins typography beside the fixture. The finalized carousel pair is uploaded to `Blended Image with Name text`, keeping the base `Day Image` and `Night Image` fields unbranded.

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{DN\text{-}FEEDS\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `DN` (Day & Night)
- **Content Format**: `FEEDS`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp), `TL` (Table Lamp)

### Real-World Examples:
- `DN-FEEDS-CH-1` (Row 1 of Chandelier Day & Night Feed)
- `DN-FEEDS-PE-3` (Row 3 of Pendant Light Day & Night Feed)
- `DN-FEEDS-FL-5` (Row 5 of Floor Lamp Day & Night Feed)
- `DN-FEEDS-TL-2` (Row 2 of Table Lamp Day & Night Feed)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Default Room Prompt | Primary Environment Variables |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblSceuLVvLMQ6wWp` | `DN-FEEDS-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `Generate me a modern living room` | `AIRTABLE_TABLE_ID_CHANDELIER_DAY_AND_NIGHT_4_5`<br>`DAY_NIGHT_FEED_PROMPT_CHANDELIER` |
| **Pendant Lights** | `PE` | `tblIgRlTtO7Y2EGIo` | `DN-FEEDS-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `Generate me a modern dining room with plain ceiling for hanging pendant light` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_NIGHT_FEED`<br>`DAY_NIGHT_FEED_PROMPT_PENDANT` |
| **Floor Lamps** | `FL` | `tblcKHAVYgzIcmabT` | `DN-FEEDS-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `Generate me a modern living room with empty floor space for a standing floor lamp` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_DAY_NIGHT_FEED`<br>`DAY_NIGHT_FEED_PROMPT_FLOOR_LAMP` |
| **Table Lamps** | `TL` | `tbljsKOEhc0618qbM` | `DN-FEEDS-TL` | `257569e1-7be8-4412-a90f-acbc347e4646` | `Generate me a modern bedroom with a bedside table for a table lamp` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_DAY_NIGHT_FEED`<br>`DAY_NIGHT_FEED_PROMPT_TABLE_LAMP` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Freshly scraped product awaiting day interior generation.
- **`Scheduled` (`S`)**: Queued for batch generation.
- **`Drafting` (`D`)**: Under active generation through Krea or Fal AI.
- **`For Modification` (`FM`)**: Flagged for lighting re-balance or prompt adjustment.
- **`Completed` (`C`)**: Both Day and Night slides successfully generated and attached.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Feed Logo Stamping & Item-Name Tagging Specs

The final step is 100% local (Zero API Cost) combining **Pillow Brand Logo Stamping** and **YOLO-World Item Detection**:
1. **Slide 1 HomeCartel Logo Stamping**:
   - Stamped onto the Day image at Canva 4:5 bottom-left coordinates (`HOMECARTEL_LOGO_BOX`):
     - `Width = 190.3 px`, `Height = 63.5 px`, `X = 108.0 px`, `Y = 1178.5 px` (108px margin from bottom and left).
   - Sourced automatically from `assets/homecartel_logo.png` on local disk.
2. **Slide 1 & Slide 2 YOLO-World Tagging**:
   - Detects the lighting fixture bounding box in both the Day (with logo) and Night images using open-vocabulary YOLO-World.
   - Renders the item's name/type (`Item Name` + `Product Type`) as an editorial floating text label beside the detected fixture in Poppins-Bold and Poppins-Regular.
3. **Airtable Field Placement**:
   - Both finalized slides are uploaded to `Blended Image with Name text`.
   - The base `Day Image` and `Night Image` fields in Airtable remain clean unbranded Fal AI outputs for backup and night transformation.
4. **Zero API Cost**: Logo composition and YOLO detection run 100% locally on CPU without third-party API spend.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run the complete Day & Night Feed pipeline (thin alias into the generator; no --execute flag)
python run_day_night_feed.py

# Run generation for 1 test record
python generate_day_night_feed_pipeline.py --max-items 1

# Scrape new active chandeliers from Akeneo
python run_day_night_feed.py --scrape-only --max-items 3
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Feed** tab.
4. Select **Day & Night Feeds** (`tblSceuLVvLMQ6wWp`).
5. Inspect day/night thumbnail columns and execute generation.
