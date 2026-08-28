# Collection Category Story Automation Pipeline

The **Collection Category Story Automation** is an end-to-end marketing automation workflow that generates branded **9:16 vertical Instagram Story collages (1080 x 1920 px)** for HomeCartel lighting product collections.

It combines three (3) individual blended lifestyle interior photos into an equal 3-row grid collage with an automated brand logo and Poppins Bold product title overlays.

---

## 🏗️ Architecture & Model Stack

| Phase | Phase Name | Provider / Tool | Model / Engine | Input Field | Output Field |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Step 0** | **Akeneo Scrape + Layout** | Akeneo PIM API | Akeneo Client + Local Layout | Akeneo Catalog | `Furniture Item`, `Furniture Item2`, `Furniture Item3`, `Collection Category Layout` |
| **Phase 1** | **Krea AI Room Interiors** | Krea AI | `krea-2-medium` (16:9) | Krea Moodboard | `Interior1`, `Interior2`, `Interior3` |
| **Phase 2** | **Claude Sonnet 5 Analysis** | Fal AI | `anthropic/claude-sonnet-5` | Interior + Product Photos | `Prompt1`, `Prompt2`, `Prompt3` |
| **Phase 3** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit` (16:9) | `Interior` + `Furniture` + `Prompt` | `Collection Category Blended Image1`, `Collection Category Blended Image2`, `Collection Category Blended Image3` |
| **Phase 4** | **9:16 Auto-Grid & Overlays** | **Local Python (PIL)** | **Zero API / Local Python Script** | `Blended Image 1/2/3` + `Logo` + `Item Names` | **`Collection Category Converted`** (Status -> **`Complete`**) |

---

## 📐 9:16 Story Canvas & Design Specifications

### 1. Canvas & Grid Dimensions (9:16)
- **Total Resolution**: `1080 x 1920 px` (Aspect Ratio `9:16 = 0.5625`)
- **Row Slots**: 3 equal horizontal slots (`1080 x 640 px` each):
  - **Slot 1 (Top)**: `Collection Category Blended Image1` (Y: `0 - 640 px`)
  - **Slot 2 (Middle)**: `Collection Category Blended Image2` (Y: `640 - 1280 px`)
  - **Slot 3 (Bottom)**: `Collection Category Blended Image3` (Y: `1280 - 1920 px`)
- **Cropping**: Automatic cover crop (`ImageOps.fit` with `LANCZOS`) ensuring zero letterboxing or aspect distortion.

### 2. Canva Brand Logo Placement
- **Width**: `190.3 px`
- **Height**: `63.5 px`
- **X Position**: `781.7 px` (Exact 108 px margin from the right edge)
- **Y Position**: `108.0 px` (Exact 108 px margin from the top)
- **Rotation**: `0°`

### 3. Canva Item Names Text Overlay (Poppins Bold)
- **Font**: `Poppins-Bold.ttf` (Official Google Fonts / Canva font, size 30px)
- **Color**: Crisp White (`#FFFFFF`) with a soft drop shadow for readability across all room backgrounds.
- **Canva Position Coordinates**:
  - **Left Margin (X)**: `90.2 px`
  - **Slot 1 Y (Top)**: `548.9 px` (`Item Name` / `Item Name1`)
  - **Slot 2 Y (Middle)**: `1188.9 px` (`Item Name2`)
  - **Slot 3 Y (Bottom)**: `1828.9 px` (`Item Name3`)
- **100% Python Scripted**: Reads product names directly from Airtable fields and stamps them into exact canvas coordinates without manual Canva intervention.

### 4. Smart Background Removal Engine
- The script (`prepare_logo_image`) automatically samples corner pixels from the `"Logo"` attachment.
- **Black Canvas Support**: Strips pure black canvas exports (e.g., `Stories Sandbox.jpg`) leaving only the white wordmark logo.
- **White / Transparent Support**: Strips solid white backgrounds and trims excess transparent PNG margins.

---

## 🎯 Supported Tables & Settings

| Setting | Value / Details |
| :--- | :--- |
| **Default Table ID** | `tblSSVJnubFk2yBm3` (Pendant Lights Story) |
| **Custom Table Support** | `--table-id <TABLE_ID>` (e.g. `tbl98UU0h4uFyFIlL`) |
| **Krea Moodboard ID** | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` |
| **Default Category** | `pendant_lights_collec_story` |

---

## 🚀 Quick Usage Commands

```powershell
# 1. Interactive Menu (Select phase 1 through 6 via interactive terminal CLI)
python generate_collection_category_story_pipeline.py

# 2. Run Full End-to-End Pipeline (Row-by-Row: Scrape -> Krea -> Claude -> Blending -> 9:16 Grid)
python generate_collection_category_story_pipeline.py --mode all

# 3. Target Specific Table ID (e.g., tbl98UU0h4uFyFIlL)
python generate_collection_category_story_pipeline.py --table-id tbl98UU0h4uFyFIlL --mode all

# 4. Run Phase 4 Only (9:16 Auto-Grid + Logo + Poppins Text direct to 'Collection Category Converted')
python generate_collection_category_story_pipeline.py --mode conversion
python generate_collection_category_story_pipeline.py --table-id tbl98UU0h4uFyFIlL --mode conversion

# 5. Run Single Specific Record
python generate_collection_category_story_pipeline.py --target-record reczlyhz1hLszSr0X --mode conversion

# 6. Run via Content Automation Framework
python -m content_automation.cli run --workflow collection_category_story
```

---

## 🔍 Resumability & Skip Logic

- **Smart Skip**: When `Interior1/2/3`, `Prompt1/2/3`, or `Blended Image 1/2/3` are already populated, the pipeline skips earlier phases automatically to conserve processing time and API quota.
- **Zero API Cost for Final Conversion**: Phase 4 executes entirely locally using Python Pillow (PIL). It does not call the Fal AI Nano Banana API, providing instant and cost-free story generation.
- **Audit Logs**: Comprehensive JSON audit logs are recorded in `output/logs/collec_story_*.json` for monitoring and debugging.
