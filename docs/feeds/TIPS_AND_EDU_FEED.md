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
| **Phase 0** | **Akeneo Ingestion** | Akeneo PIM REST API | Active Catalog Ingestion (`enabled=true`) with cross-table dedup | Akeneo Catalog (`chandeliers`, `pendant_lights`, etc.) | Populates 4 product slots (`Furniture Item[1-4]`, `SKU[1-4]`, `Item Name[1-4]`) -> Status: `Standby` |
| **Phase 1** | **Krea Room & Thumbnail Gen** | Krea AI | `krea-2-medium` (4:5, 1K resolution)<br>Thumb Moodboard: `ec860c16-10e4-429e-bba6-ff068bcb80b1` | Category room prompts + Preset Moodboard ID | `Interior1`, `Interior2`, `Interior3`, `Thumbnail` -> Status: `Already attached a room Interior` |
| **Phase 2** | **Claude Sonnet 5 Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior[1-3]` + `Furniture Item[1-3]` + Exterior | `Prompt1`, `Prompt2`, `Prompt3`, `5-Word Tips Title` |
| **Phase 3** | **Nano Banana Pro Product Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Interior[1-3]` + `Furniture Item[1-3]` + `Prompt[1-3]` | Uploads 3 blended images to `Tips and Edu Blended` |
| **Phase 4** | **Nano Banana Pro Layout Blending** | Fal AI | `fal-ai/nano-banana-pro/edit` + `tipsedufeeds1..3.json` | `Tips and Edu Layout[1-3]` + `Tips and Edu Blended[1-3]` | Uploads 3 completed graphics to `Tips and Edu Feeds` |
| **Phase 5** | **Local PIL Stamp & Finalization** | Local Python Pillow | Zero-API Local Compositor | `Thumbnail` + `Logo` | Stamps brand watermark & headline -> Status: `Completed` (`C`) |

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

All records adhere to the 5 standard single-select lifecycle statuses, visualized as single-character badges in the Web UI:

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

1. **`Pending` (`P`)**: Raw product slots scraped from Akeneo, waiting for interior generation.
2. **`Scheduled` (`S`)**: Queued for execution in batch automation runners.
3. **`Drafting` (`D`)**: Processing through Krea generation, Claude prompt analysis, or Fal blending.
4. **`For Modification` (`FM`)**: Flagged by marketing team for regeneration or manual prompt tweaking.
5. **`Completed` (`C`)**: All 3 carousel slides and thumbnail successfully generated, validated, and stamped.

### Timestamp Tracking
Every pipeline run writes the exact execution timestamp in Philippine Time (UTC+8) into the `Date & Time Run (PHT)` field in ISO 8601 format:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow Layout Specs

The cover thumbnail uses **Zero-API Local Python Pillow** execution to render typography and brand assets without external cloud costs:
- **Brand Logo Coordinates**:
  - Width: `190.3 px`, Height: `63.5 px`
  - Position: `X=108.0 px`, `Y=108.0 px` (top-left margin) or bottom watermark placement.
- **Typography Engine**:
  - Font: `Poppins-Bold.ttf`
  - Headline Font Size: `52 px`, auto-wrapped within `900 px` bounding box.
  - Text Shadow: Subtle Gaussian blur drop shadow ($R=8\text{ px}$, opacity $0.45$) for legibility over bright architectural backgrounds.
- **Deduplication Guard**: Cross-table checking against all existing Story and Feed tables prevents duplicate Akeneo SKUs from being scraped or processed.

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

# Scrape new active products from Akeneo
python scrape_tips_and_edu_feed.py --category chandeliers --max-rows 4 --execute
```

### Web UI Dashboard Execution
1. Navigate to `http://localhost:5200`
2. Enter security PIN: `1234`
3. Select the **Feed** tab from the top navigation bar.
4. Click on **Tips & Edu Feeds** subtab.
5. Choose your target category (**Chandelier**, **Pendant**, **Floor Lamp**, or **Cluster**).
6. Select rows and click **Run Selected** or **Run All Pending**.
