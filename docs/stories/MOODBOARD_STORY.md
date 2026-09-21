# Moodboard Story Automation Pipeline

The **Moodboard Story Automation Pipeline** produces editorial **9:16 vertical Instagram Stories (1080 x 1920 px)** for HomeCartel lighting collections across 3 core fixture categories. It blends the lighting product into a photorealistic luxury room interior, stamps the official HomeCartel® brand mark locally, and converts the aesthetic into an editorial moodboard card.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Vertical Story (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Hero Card (`Moodboard Converted`)**: Luxury vertical editorial moodboard featuring the blended room photo, material texture swatches, and the official brand logo.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, `floor_lamps`) | `Furniture Item`, `SKU`, `Item Name` -> Status: `Pending` (`P`) |
| **Phase 1** | **Krea Room Interior** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Preset category Moodboard | Standby record + Room Prompt | `Interior Generated` -> Status: `Drafting` (`D`) |
| **Phase 2** | **Claude Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Generated` + `Furniture Item` | `Generated Prompt` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Nano Banana Pro Blending & Brand Stamping** | Fal AI + **Local Python Pillow** | `fal-ai/nano-banana-pro/edit` + `HOMECARTEL_STORY_LOGO_BOX`<br>Top-right: $X=781.7, Y=108.0$ ($190.3 \times 63.5\text{ px}$) | `Interior Generated` + `Furniture Item` + `Generated Prompt` | `Blended Image` (Watermarked), `Homecartel Logo Overlay`, and `Blended Image with Name text` (YOLO Tagged) -> Status: `Drafting` (`D`) |
| **Phase 4** | **Brand Overlay Verification** | Local Python Engine | Zero-API Local Verification | `Blended Image` + `Logo` | Verifies brand watermark & YOLO badge attachment |
| **Phase 5** | **Moodboard Card Conversion** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | Clean room blend + `Moodboard Layout` | `Moodboard Converted` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{MB\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `MB` (Moodboard)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `FL` (Floor Lamp)

### Real-World Examples:
- `MB-STORY-CH-1` (Row 1 of Chandelier Moodboard Story)
- `MB-STORY-PE-5` (Row 5 of Pendant Lights Moodboard Story)
- `MB-STORY-FL-8` (Row 8 of Floor Lamp Moodboard Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblHQrci8d1K9ws2M` | `MB-STORY-CH` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_MB_STORY_CHANDELIER` |
| **Pendant Lights** | `PE` | `tblkm119i48y0M1IQ` | `MB-STORY-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `AIRTABLE_TABLE_ID_MB_STORY_PENDANT` |
| **Floor Lamps** | `FL` | `tblBaNeiSZeYrUawW` | `MB-STORY-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_MB_STORY_FLOOR_LAMP` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped Akeneo product awaiting generation.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Krea, Claude, or Fal.
- **`For Modification` (`FM`)**: Flagged for moodboard palette refinement.
- **`Completed` (`C`)**: `Moodboard Converted` card generated and attached.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow Layout Specs & YOLO Item Tagging

The pipeline executes **Zero-API Local Python Pillow** logo stamping and YOLO-World item tagging:
- **Brand Logo Coordinates (`HOMECARTEL_STORY_LOGO_BOX`)**:
  - Canvas: `1080 x 1920 px` (9:16)
  - Width: `190.3 px`, Height: `63.5 px`
  - Position: `X=781.7 px`, `Y=108.0 px` (Exact 108 px top & right margins)
  - Target Fields: Stamped directly onto `Blended Image`, `Homecartel Logo Overlay`, and carried over to `Blended Image with Name text`.
- **YOLO-World Item Name Tagging & Safe Fallback**:
  - Automatically identifies the mounted fixture in the room interior and places the 2-line floating name pill relative to the detected bounding box.
  - **Global 9:16 Safe Fallback**: If YOLO detection is below confidence or undetected, the tag automatically positions at the **Mid-Left Safe Zone (`X=100, Y=800`)**, ensuring zero collision with Instagram Story top header or bottom reply bars.
  - Target Field: Uploaded to `Blended Image with Name text`.
- **Zero API Rule**: All text rendering, badge background drawing, and logo overlays execute 100% locally via PIL without cloud API calls.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive category menu
python run_moodboard_story.py

# Run for Pendant Lights
python run_moodboard_story.py --target pendant_lights

# Run for Chandeliers (batch size of 3)
python run_moodboard_story.py --target chandeliers --batch-size 3

# Target specific record ID
python run_moodboard_story.py --record-id recXXXXXXXXXXXXXX
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Moodboard Stories**.
5. Pick fixture category (**Chandelier**, **Pendant**, or **Floor Lamp**).
6. Select rows and trigger generation.
