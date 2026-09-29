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
| **Phase 1** | **Krea Day Interior** | Krea AI | `krea-2-medium` (4:5, 1K)<br>Moodboard: `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | Room prompt ("Generate me a modern bright sunlit living room") | `Interior Generated Photo` -> Status: `In Progress` (`P`) |
| **Phase 2** | **Claude Day & Night Vision Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Generated Photo` + `Furniture Item` | `Blending Prompt` -> Status: `In Progress` (`P`) |
| **Phase 3** | **Nano Banana Pro Day Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Interior Generated Photo` + `Furniture Item` + `Blending Prompt` | `Day Image` -> Status: `Processing Day Image` |
| **Phase 4** | **Nano Banana Pro Night Transformation** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Day Image` | `Night Image` -> Status: `In Progress` (`P`) |
| **Phase 5** | **Feed Logo Stamping & Local YOLO-World Tagging** | **Local Python (Pillow + YOLO-World)** | **Zero-API Local Overlay Engines** (`content_automation/overlay.py` + `content_automation/item_tagger.py`) | `Day Image` + `Night Image` + `Item Name`/`SKU` | `Day Image`, `STORY - Day & Night (2)`, `Blended Image with Name text` -> Status: `Completed` (`C`) |

> 🏷️ **Logo & Item-Name Watermark**: Slide 1 (`Day Mode`) receives the floating open-vocabulary YOLO-World item-name tag (`Item Name` + `Product Type`), followed by the HomeCartel brand logo stamped at the standard Canva 4:5 bottom-left position (`HOMECARTEL_LOGO_BOX`: `X=108.0, Y=1178.5, W=190.3, H=63.5`). This stamped and tagged Day photo is uploaded over `Day Image` and paired with the clean `Night Image` into the deliverable multi-attachment field `STORY - Day & Night (2)`. Both are also mirrored to `Blended Image with Name text`.

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

The Airtable single-select Status field tracks records across 5 lifecycle stages:

| Badge | Color | Lifecycle State | Airtable Status Value | Operational Meaning |
| :---: | :---: | :--- | :--- | :--- |
| **P** | Sky Blue | **Posted / Processing** | Posted, Processing, Pending, In Progress, intermediate phase statuses | Record is actively queued or being processed. |
| **S** | Purple | **Scheduled** | Scheduled, Schedule | Approved and scheduled for publishing. |
| **C** | Emerald | **Complete / Done** | Complete, Completed, Done | All phases complete; deliverables attached. |
| **D** | Rose | **Discarded** | Discard, Discarded | Archived or rejected candidate. |
| **FM** | Amber | **For Manual / Revision** | For Manual, Minor revision, FM | Flagged for manual review or adjustment. |

### Execution Timestamp
When a row reaches Complete (C), the pipeline automatically writes the Philippine Standard Time timestamp (UTC+8, ISO 8601) into the **Date and Time Generated** field:
`
2026-09-07T13:12:00+08:00
`

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
1. Open http://localhost:5200 in your web browser.
2. Enter the Studio PIN if DASHBOARD_PIN is configured.
3. Click the **Feed** tab in the main navigation.
4. Select the **Day & Night Feeds** subtab.
5. Pick an active fixture category.
6. Click the **Run** button on the fixture card, confirm the batch count (default 1) in the confirmation modal, and the pipeline will scrape a fresh active product and process it end-to-end.
