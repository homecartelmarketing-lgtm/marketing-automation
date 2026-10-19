# Tips & Educational Feed Automation Pipeline

The **Tips & Educational Feed Automation Pipeline** is an end-to-end multi-slide Instagram carousel generation engine producing high-converting educational lighting design content. Each row combines 3 distinct room interiors, 1 editorial cover thumbnail, 3 product blends, and 3 templated layout feeds sized for vertical social media.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1350 px` (Aspect Ratio `4:5`)
- **Format**: Multi-slide Instagram Carousel & Static Feed Posts
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 0 (Cover Thumbnail)**: Krea exterior architecture stamped with HomeCartel® logo and Claude-generated 5-word headline in Poppins-Bold.
  - **Slide 1**: Product 1 blended into Interior 1 + Tips & Edu Layout 1.
  - **Slide 2**: Product 2 blended into Interior 2 + Tips & Edu Layout 2.
  - **Slide 3**: Product 3 blended into Interior 3 + Tips & Edu Layout 3.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scraper** | Akeneo PIM REST API | Active Catalog Ingestion (`enabled=true`) + Shopify published catalog check | Akeneo Catalog (`chandeliers`, `pendant_lights`, etc.) | Populates 4 product slots (`Furniture Item[1-4]`, `SKU[1-4]`, `Item Name[1-4]`) -> Status: `Standby` |
| **Phase 2** | **Krea Room & Thumbnail Gen** | Krea AI | `krea-2-medium` (4:5, 1K resolution)<br>Thumb Moodboard: `ec860c16-10e4-429e-bba6-ff068bcb80b1` | Category room prompts + Preset Moodboard ID | `Interior1`, `Interior2`, `Interior3`, `Thumbnail` -> Status: `Already attached a room Interior` |
| **Phase 3** | **Claude Sonnet 5 Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior[1-3]` + `Furniture Item[1-3]` | Populates `Prompt1`, `Prompt2`, `Prompt3` |
| **Phase 4** | **Nano Banana Pro Blending & Tips Gen** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K`<br>Claude Vision for Tips | `Interior[1-3]` + `Furniture Item[1-3]` + `Prompt[1-3]` | Uploads 3 blended images to `Tips and Edu Blended`, generates `Thumbnail with Text`, and saves educational tips to `Tips 1..3` (dual-written to `Tip1..3`) |
| **Phase 5** | **YOLO Item Name Tagging** | YOLO-World (Local CPU) | Open-vocabulary tagging (Line 1: Item Name, Line 2: Product Type) | `Tips and Edu Blended` + `Item Name[1-3]` + `Product Type[1-3]` | Stamps two-line floating tag and uploads carousel to `Tips and Edu Blended Attach Item Name` |
| **Phase 6** | **Programmatic PIL Layout Compositing** | Local Python Pillow | Zero-API Local Compositor (Canva coordinates) | `Tips and Edu Blended Attach Item Name` + `Tips 1..3` | Overlays Numeral (196px) + Tip Text (32px) and uploads 3 feed photos to `Tips and Edu Feeds` -> Status: `Complete` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record generated or processed by this pipeline is assigned a permanent, human-readable Foreign Key ID in the `Foreign Key ID` field:

$$\text{Format: } \mathbf{\langle IDEA\rangle\text{-}\langle FORMAT\rangle\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `TNE` (Tips & Educational)
- **Content Format**: `FEEDS`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp), `CL` (Cluster Chandelier)

### Real-World Examples:
- `TNE-FEEDS-CH-1` (Row 1 of Chandelier Tips & Edu Feed)
- `TNE-FEEDS-PE-14` (Row 14 of Pendant Lights Tips & Edu Feed)
- `TNE-FEEDS-FL-8` (Row 8 of Floor Lamp Tips & Edu Feed)
- `TNE-FEEDS-CL-3` (Row 3 of Cluster Chandelier Tips & Edu Feed)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblQ65S51Dmauwx4c` | `TNE-FEEDS-CH` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CHANDELIER_TIPS_EDU_FEED` |
| **Pendant Lights** | `PE` | `tblIhCP3Gjg09QFCK` | `TNE-FEEDS-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDU_FEED` |
| **Floor Lamps** | `FL` | `tblQuhvktqYB59Ofw` | `TNE-FEEDS-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_FLOOR_LAMPS_TIPS_EDU_FEED` |
| **Cluster Chandeliers** | `CL` | `tblwY6eGQCD5bJeF1` | `TNE-FEEDS-CL` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIERS_TIPS_EDU_FEED` |

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

### Failure Handling
Each phase sets `Processing` when it starts. If a phase crashes, or Phase 6 fails any slot, the row is moved to `For Manual` (amber `FM` badge) instead of staying on `Processing`. Retry it with `python run_tips_and_edu_feed.py --target <target> --phase all --record-id <rec_id> --execute`. Finished work (interiors, blends, feed slides) is skipped, and un-targeted runs never pick the row up again. See [`2026-10-15-tips-edu-feed-crash-leaves-row-processing`](../memory/incidents/2026-10-15-tips-edu-feed-crash-leaves-row-processing.md).

### Execution Timestamp
When a row reaches Complete (C), the pipeline automatically writes the Philippine Standard Time timestamp (UTC+8, ISO 8601) into the **Date and Time Generated** field:
`
2026-09-07T13:12:00+08:00
`

---

## 6. Local Pillow Layout Specs

Both the cover thumbnail and the 3 final feed slides use **Zero-API Local Python Pillow** execution (`content_automation/overlay.py`) to render typography and brand assets without external cloud costs:

### A. Cover Thumbnail (`Thumbnail with Text`)
- **Brand Logo Coordinates**:
  - Width: `190.3 px`, Height: `63.5 px`
  - Position: `X=108.0 px`, `Y=108.0 px` (top-left margin) or bottom watermark placement.
- **Typography Engine**:
  - Font: `Poppins-Bold.ttf`
  - Headline Font Size: `52 px`, auto-wrapped within `900 px` bounding box.
  - Text Shadow: Subtle Gaussian blur drop shadow ($R=8\text{ px}$, opacity $0.45$) for legibility over bright architectural backgrounds.

### B. 3 Final Feed Slides (`Tips and Edu Feeds`)
- **Numeral Box (`TIPS_EDU_FEED_NUMERAL_BOX`)**:
  - Font: `Poppins-Regular.ttf`, font size `196 px`
  - Canva Position: `X=147.8 px`, `Y=942.2 px`, `Width=82 px`, `Height=312.7 px`
- **Tip Text Box (`TIPS_EDU_FEED_TEXT_BOX`)**:
  - Font: `Poppins-Bold.ttf`, font size `32 px`
  - Canva Position: `X=229.8 px`, `Y=1007.3 px`, `Width=755.3 px`, `Height=176.5 px`
  - Formatting: Top-anchor flow, Canva line spacing `1.0`, letter spacing `0`
  - Collision Avoidance: Dynamic offset `t_box_x = max(text_box.x, num_glyph_right + min_gap)` prevents wide numerals ("2", "3") from overlapping the tip text.

### C. Airtable Field Synchronization & Tagging Protocol
- **Dual-Write for Educational Tips**: Tips text generated in Phase 4 is dual-written to both the primary pipeline fields (`Tips 1`, `Tips 2 `, `Tips 3`) and legacy/alternative schema fields (`Tip1`, `Tip2`, `Tip3`) if present in the table. This guarantees all Airtable views and UI components display tips without blank columns.
- **Strict Item Name & Product Type Extraction (No Surrogate Fallbacks)**: YOLO product tagging in Phase 5 reads directly from `Item Name[1-3]` and `Product Type[1-3]` (handling whitespace variations like `Item Name 1` or `Item Name1`). The pipeline strictly passes `product_type_val` directly to `split_item_name(raw_name, fallback_product_type=product_type_val)` without creating synthetic fallback properties (such as `category_label` or `fallback_category_label`). This ensures Phase 5 completes smoothly and Phase 6 (Pillow layout stamping with Numerals and Tips) executes end-to-end.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run full pipeline for Chandeliers (default tblQ65S51Dmauwx4c)
python run_tips_and_edu_feed.py --phase all --execute

# Run specific phase for 1 test row
python run_tips_and_edu_feed.py --phase 1 --max-rows 1 --execute

# Target Pendant Lights table
python run_tips_and_edu_feed.py --target pendant_lights --phase all --execute

# Re-run only the layout phase (6) for one existing row (explicit developer exception, never loop old rows)
python run_tips_and_edu_feed.py --target chandeliers --phase 6 --record-id recXXXXXXXXXXXXXX --execute
```

`--phase` accepts `1`..`6`, `thumbnail_text` and `all` (default). Phase 5 = YOLO tagging, Phase 6 = Pillow layout. Preflight creates every field above, including `Tips and Edu Blended Attach Item Name`, on the first run against a table.

```powershell
# Scrape new active products from Akeneo (moved to scripts/scrapers/ — run from repo root)
PYTHONPATH=. python scripts/scrapers/scrape_tips_and_edu_feed.py --category chandeliers --max-rows 4 --execute
```

### Web UI Dashboard Execution
1. Open http://localhost:5200 in your web browser.
2. Enter the Studio PIN if DASHBOARD_PIN is configured.
3. Click the **Feed** tab in the main navigation.
4. Select the **Tips & Educational Feeds** subtab.
5. Pick an active fixture category.
6. Click the **Run** button on the fixture card, confirm the batch count (default 1) in the confirmation modal, and the pipeline will scrape a fresh active product and process it end-to-end.
