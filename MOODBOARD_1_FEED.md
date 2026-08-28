# Moodboard #1 Feed Automation Pipeline

The **Moodboard #1 Feed Automation** is an end-to-end marketing automation workflow that generates branded **4:5 vertical Instagram Feed / Carousel posts (1080 x 1350 px)** for HomeCartel lighting and furniture products on Airtable (`tbl9u5vjgx8kuE44R`).

Each processed product generates a complete **4-slide Feed carousel**:
1. **Slide 1**: `Moodboard V1 Blended` — Photorealistic luxury room interior with the product naturally integrated.
2. **Slide 2**: `Moodboard Added Watermark` — Blended room photo with the official HomeCartel® brand mark stamped at exact Canva coordinates.
3. **Slide 3**: `Moodboard Converted` — Minimalist luxury 3-swatch editorial material moodboard derived from the room's materials.
4. **Slide 4**: `Closeup Photo` — High-end commercial macro product photograph highlighting micro textures, craftsmanship, and metallic details.

---

## 🏗️ Architecture & Model Stack

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields | Output Field / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Akeneo Catalog Ingestion | Akeneo Catalog | `Furniture Item`, `Item Name`, `SKU`, `Status` -> **`Standby`** |
| **Phase 1** | **Krea Room Interior** | Krea AI | `krea-2-medium` (4:5)<br>Preset ID: `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | Standby record + Room Prompt | `Interior Generated`<br>(Status -> **`Interior Generated`**) |
| **Phase 2** | **Claude Sonnet 5 Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Generated` + `Furniture Item` | `Prompt for Blending`<br>(Status -> **`Generating Prompt for Blending`**) |
| **Phase 3** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1k` | `Interior Generated` + `Furniture Item` + `Prompt for Blending` | `Moodboard V1 Blended`<br>(Status -> **`Blended Image Generated`**) |
| **Phase 4** | **Local PIL Logo Overlay** | **Local Python (PIL)** | **Zero API / Local Python Script**<br>Box: $190.3 \times 63.5\text{ px}$ @ $(108, 1178.5)$ | `Moodboard V1 Blended` + `Watermark Layout` / `Logo` | **`Moodboard Added Watermark`**<br>(Status -> **`Added Watermark Layout`**) |
| **Phase 5** | **Material Moodboard Conversion** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1k` | `Moodboard V1 Blended` + `Moodboard Layout` | **`Moodboard Converted`**<br>(Status -> **`Moodboard Converted`**) |
| **Phase 6** | **Macro Close-up Photo** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1k` | `Furniture Item` + `Closeup Photo Layout` | **`Closeup Photo`**<br>(Status -> **`Complete`**) |

---

## 📐 4:5 Feed Canvas & Canva Brand Mark Specifications

### 1. Canvas Dimensions (4:5)
- **Total Resolution**: `1080 x 1350 px` (Aspect Ratio `4:5 = 0.8`)
- **Format**: High-resolution vertical Instagram Feed carousel slides.

### 2. Canva Brand Logo Placement (`HOMECARTEL_LOGO_BOX`)
- **Width**: `190.3 px`
- **Height**: `63.5 px`
- **X Coordinate (Left)**: `108.0 px` (Exact 108 px margin from left edge)
- **Y Coordinate (Top)**: `1178.5 px` (Exact 108 px margin from bottom edge: $1350 - 1178.5 - 63.5 = 108.0\text{ px}$)
- **Rotation**: `0°`
- **Engine**: Local Python Pillow (`stamp_logo`) with auto background removal and visible boundary trimming. Zero API cost and zero distortion.

---

## 🎯 Supported Tables & Settings

| Setting | Value / Details |
| :--- | :--- |
| **Airtable Table ID** | `tbl9u5vjgx8kuE44R` |
| **Table Name** | `Moodboard #1 Feed` |
| **Krea Moodboard ID** | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` |
| **Default Category** | `chandeliers` (Akeneo PIM) |
| **Default Style** | `modern` |
| **Claude Vision Model** | `anthropic/claude-sonnet-5` |
| **Nano Banana Model** | `fal-ai/nano-banana-pro/edit` (4:5, 1k) |

---

## 🚀 Usage Commands

### 1. Scrape Products from Akeneo to Airtable
```powershell
# Scrape chandeliers (default style: modern) into tbl9u5vjgx8kuE44R
python scrape_moodboard_1_feed.py

# Scrape at most 5 products
python scrape_moodboard_1_feed.py --max-items 5

# Scrape custom category
python scrape_moodboard_1_feed.py --category pendant_lights --style modern
```

### 2. Run Full AI Generation & Local Overlay Pipeline
```powershell
# Run the complete pipeline for all Standby/unprocessed records
python generate_moodboard_1_feed.py

# Run for at most 5 records
python generate_moodboard_1_feed.py --max-items 5

# Override destination table or Krea moodboard
python generate_moodboard_1_feed.py --table-id tbl9u5vjgx8kuE44R --moodboard-id b5ffdcbb-192e-4528-8d86-d1a4cf496887
```

---

## 🔍 Resumability & Skip Guards

- **Smart Skip**: If a record already has `Interior Generated`, `Prompt for Blending`, `Moodboard V1 Blended`, `Moodboard Added Watermark`, `Moodboard Converted`, or `Closeup Photo`, the pipeline automatically skips completed steps.
- **Auto-Finalization**: Any record that has `Closeup Photo` attached is automatically marked with Status **`Complete`**.
- **Audit Logs**: Structured JSON audit logs for Claude prompt analysis and Fal image generation are recorded in `output/logs/moodboard_1_feed_claude_logs.json` and `output/logs/moodboard_1_feed_fal_logs.json`.
