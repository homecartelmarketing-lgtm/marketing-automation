# CTA Story Automation Pipeline

The **CTA Story Automation** is an end-to-end marketing automation workflow that generates branded **9:16 vertical Instagram Stories (1080 x 1920 px)** for HomeCartel lighting collections.

It combines a photorealistic AI room interior, seamless lighting fixture blending, an AI-analyzed luxury headline saved in **`Word Generated`**, and an automated local Python Pillow stamping of the **HomeCartel brand logo** and **Canva CTA text watermark layout**.

---

## 🏗️ Architecture & Model Stack

| Phase | Phase Name | Provider / Tool | Model / Engine | Input Field | Output Field |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape + Layout** | Akeneo PIM API | Akeneo Scrape Client | Akeneo Catalog | `Furniture Item`, `CTA Blended Image Watermark Layout` |
| **Phase 2** | **Krea AI Room Interiors** | Krea AI | `krea-2-medium` (9:16) | Krea Moodboard | `CTA Interior` |
| **Phase 3** | **Claude Sonnet 5 Prompting** | Fal AI | `anthropic/claude-sonnet-5` | Interior + Product Photos | `Blending Prompt` |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit` (9:16) | `CTA Interior` + `Furniture Item` + `Blending Prompt` | `CTA Blended Image` |
| **Phase 5** | **Claude Headline Analysis** | Fal AI | `anthropic/claude-sonnet-5` | `CTA Blended Image` | **`Word Generated`** |
| **Phase 6** | **Local Logo & CTA Stamping** | **Local Python (PIL)** | **Zero API / Local Python Pillow** | `CTA Blended Image` + `Word Generated` + `Logo` | **`CTA Converted Image`** (Status -> **`Complete`**) |

---

## 📐 9:16 Story Canvas & Design Specifications

### 1. Canvas Dimensions (9:16)
- **Total Resolution**: `1080 x 1920 px` (Aspect Ratio `9:16 = 0.5625`)
- **Cropping & Quality**: Automatic high-quality RGB composite (`LANCZOS`, JPEG quality 95).

### 2. Canva Brand Logo Placement
- **Source**: Retrieved directly from Airtable attachment field **`Logo`** (with table-wide and local asset fallback).
- **Width**: `190.3 px`
- **Height**: `63.5 px`
- **X Position**: `781.7 px` (Top-right corner, exact 108 px margin from the right edge)
- **Y Position**: `108.0 px` (Exact 108 px margin from the top edge)
- **Smart Background Removal**: Automatically detects and trims black canvas (`Stories Sandbox.jpg`), white, or transparent backgrounds.

### 3. Canva CTA Text Watermark Layout Box
- **Box Dimensions**:
  - **Width**: `820.8 px`
  - **Height**: `304.6 px`
  - **X Position**: `151.2 px`
  - **Y Position**: `1521.8 px`
  - **Right Margin Edge**: `X = 972.0 px` (Exact 108 px margin from the canvas right edge)
- **Alignment**: **Right-aligned** to `X = 972.0 px`.

### 4. Typography & Font Specifications
- **Headline / Title**:
  - **Source**: Read from **`Word Generated`** (Claude Vision headline analysis of `CTA Blended Image`).
  - **Font**: `Poppins-Bold.ttf` (Google Fonts / Canva font)
  - **Font Size**: **`48 px`**
  - **Auto-fit Protection**: Automatically scales font size down to 24px if the product title exceeds box width.
- **Follow Call-to-Action**:
  - **Font**: `Poppins-Bold.ttf`
  - **Font Size**: **`28 px`**
  - **Text**:
    ```text
    Follow @HomeCartel for
    more home inspiration.
    ```
- **Contact Details**:
  - **Font**: `Poppins-Regular.ttf`
  - **Font Size**: **`28 px`**
  - **Text**:
    ```text
    0977 825 5588 (or send us a DM)
    (02) 8248 8071 | Dial 1
    sales@homecartel.com
    ```
- **Legibility**: Multi-directional soft drop shadow `(0, 0, 0, 180)` ensures crisp contrast over light, medium, and dark room backgrounds.

---

## 🎯 Supported Airtable Tables & IDs

| # | Airtable Table Name | Category Code (`--category`) | Table ID (`table_id`) | Moodboard Default |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **CTA Story Chandelier** | `chandelier_cta_story` *(default)* | `tblYHdVq14FjMWg5o` | Chandeliers (`fda7090c-787b-4116-94cd-3feef613eaaa`) |
| **2** | **CTA Story Cluster Chandelier** | `cluster_chandelier_cta_story` | `tblviGpe0rrOwgUul` | Cluster Chandelier |
| **3** | **CTA Story Pendant Light** | `pendant_lights_cta_story` | `tblSpGJLO3faYfIDY` | Pendant Lights |
| **4** | **CTA Story Table Lamp** | `table_lamps_cta_story` | `tblKJeCCp4zQ6g7Em` | Table Lamps |
| **5** | **CTA Story Floor Lamp** | `floor_lamp_cta_story` | `tblylO54F3NR5RQD1` | Floor Lamps |
| **6** | **CTA Story Wall Light** | `wall_lights_cta_story` | `tblsllKrNcffItIua` | Wall Sconce |

---

## 🚀 Quick Usage Commands

```bash
# 1. Full End-to-End Pipeline (Row-by-Row: Scrape -> Krea -> Claude Prompt -> Blend -> Claude Headline -> Python Stamping)
python generate_cta_story_pipeline.py

# 2. Process Multiple Rows in Sequence (e.g. 5 items)
python generate_cta_story_pipeline.py --max-items 5

# 3. Target a Specific CTA Story Table Category
python generate_cta_story_pipeline.py --category cluster_chandelier_cta_story
python generate_cta_story_pipeline.py --category pendant_lights_cta_story
python generate_cta_story_pipeline.py --category table_lamps_cta_story
python generate_cta_story_pipeline.py --category floor_lamp_cta_story
python generate_cta_story_pipeline.py --category wall_lights_cta_story

# 4. Custom Prompt Override for Krea Interior
python generate_cta_story_pipeline.py --category table_lamps_cta_story --prompt "Generate me a modern bedroom with a table lamp side by side"

# 5. Custom Table ID Override
python generate_cta_story_pipeline.py --table-id tblviGpe0rrOwgUul

# 6. Interactive Menu (Select Phase 1 to 8)
python generate_cta_story_pipeline.py --mode menu

# 7. Run Phase 5 Only (Claude Vision Headline Analysis -> 'Word Generated')
python generate_cta_story_pipeline.py --mode words

# 8. Run Phase 6 Only (Local Python Pillow Stamping Logo + CTA Layout -> 'CTA Converted Image')
python generate_cta_story_pipeline.py --mode conversion
```

---

## 🔍 Resumability & Smart Skip Logic

- **Row-by-Row Auto Complete**: The script inspects the row's existing fields on Airtable:
  - If **`CTA Blended Image`** exists and **`Word Generated`** is filled: Directly executes **Phase 6** (Logo + CTA Text Stamping) and marks row **`Complete`**.
  - If **`CTA Blended Image`** exists but **`Word Generated`** is empty: Executes **Phase 5** (Claude Vision) then **Phase 6**.
  - If **`Blending Prompt`** exists: Starts at **Phase 4** (Nano Banana Pro Blending).
  - If **`CTA Interior`** exists: Starts at **Phase 3** (Claude Prompting).
  - If blank/standby: Starts at **Phase 1 & 2**.
- **Zero API Cost for Conversion**: Phase 6 executes 100% locally via Python Pillow (`PIL`), eliminating Fal AI API charges for the layout conversion phase.
