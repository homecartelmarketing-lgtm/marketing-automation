# 1 Product, 3 Styles Feed Automation Pipeline

The **1 Product, 3 Styles Feed Automation** is an automated marketing pipeline designed to take **1 lighting/furniture product** and blend it into **3 distinct luxury room interior styles** (e.g., Dining Room, Kitchen Island, Living Room) at **4:5 vertical Instagram Feed format (1K Resolution)**, with the **official HomeCartel® logo stamped onto the first blended image**.

---

## 🏗️ Architecture & Model Stack

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Data | Output Field / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo 1-Item Ingestion** | **Akeneo PIM API** | Ingestion Script (`modern` style) | Akeneo Catalog | `Furniture Item`, `SKU`, `Item Name`<br>👉 Status -> **`Standby`** |
| **Phase 2** | **Krea Room Interiors (3 Styles)** | **Krea AI** | `krea-2-medium` (4:5, 1K)<br>Preset Moodboards | Standby row + 3 Room Prompts | `Interior1`, `Interior2`, `Interior3`<br>👉 Status -> **`Phase 2 - Ready`** |
| **Phase 3** | **Claude Sonnet 5 Prompt Analysis** | **Fal AI API** | `anthropic/claude-sonnet-5`<br>via `openrouter/router/vision` | `Furniture Item` + 3 Room Interiors | **`Prompt1`**, **`Prompt2`**, **`Prompt3`** (Long Text)<br>👉 Status -> **`Phase 3 - Ready`** |
| **Phase 4** | **Nano Banana Pro Multi-Blending + Logo Overlay** | **Fal AI API** + **Local PIL** | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1k`<br>Local Canva Logo Compositor | `Furniture Item` + Interiors + Prompts + `Logo` | **3 Blended Images** (Slide 1 Watermarked) in `1 Product 3 Style Blended`<br>👉 Status -> **`Complete`** |

---

## 📐 Image, Canvas & Canva Brand Logo Specifications

### 1. Canvas Dimensions (4:5)
- **Aspect Ratio**: `4:5` (Vertical Instagram Feed format)
- **Quality / Resolution**: `1K` High Definition

### 2. Canva Brand Logo Box Placement (`HOMECARTEL_LOGO_BOX` on Slide 1)
- **Width**: `190.3 px`
- **Height**: `63.5 px`
- **X Coordinate (Left)**: `108.0 px`
- **Y Coordinate (Top)**: `1178.5 px`
- **Rotation**: `0°`
- **Source Field**: `Logo` attachment field (Airtable)
- **Engine**: Local Python Pillow (`stamp_logo`) with automated background removal and boundary trimming.

### 3. Carousel Output Files in `1 Product 3 Style Blended`:
- **Slide 1**: `1_product_3_styles_blended1_watermarked.jpg` (Luxury Room Style 1 + **HomeCartel Logo stamped**)
- **Slide 2**: `1_product_3_styles_blended2.jpg` (Luxury Room Style 2)
- **Slide 3**: `1_product_3_styles_blended3.jpg` (Luxury Room Style 3)

---

## 🎯 Supported Category Presets

| Preset | Target Category | Airtable Table ID | Moodboard ID | Room Styles Generated |
| :--- | :--- | :--- | :--- | :--- |
| **`pendant_lights`** | Pendant Lights | `tblRy52kCasisCWzd` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | 1. Dining Room (`Interior1` / `Prompt1`)<br>2. Kitchen Island (`Interior2` / `Prompt2`)<br>3. Living Room Corner (`Interior3` / `Prompt3`) |
| **`table_lamps`** | Table Lamps | `tblCHrWkJ3KImcKoq` | `257569e1-7be8-4412-a90f-acbc347e4646` | 1. Bedroom Beside Table (`Interior1` / `Prompt1`)<br>2. Living Room Side Table (`Interior2` / `Prompt2`)<br>3. Study Desk (`Interior3` / `Prompt3`) |
| **`chandeliers`** | Chandeliers | `tblM1ODMxdP9sAfdS` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | 1. Grand Living Room (`Interior1` / `Prompt1`)<br>2. Luxury Dining Room (`Interior2` / `Prompt2`)<br>3. High Ceiling Foyer (`Interior3` / `Prompt3`) |

---

## 🚀 Execution Commands

```bash
# 1. Interactive Menu (Select category: Pendant Lights, Table Lamps, or Chandeliers)
python run_1_product_3_styles_feed.py

# 2. Run All 4 Phases directly for Pendant Lights
python run_1_product_3_styles_feed.py --target pendant_lights --phase all

# 3. Run All 4 Phases directly for Table Lamps
python run_1_product_3_styles_feed.py --target table_lamps --phase all

# 4. Ingest only (Phase 1: scrape 1 item)
python run_1_product_3_styles_feed.py --target table_lamps --phase 1

# 5. Process a specific Airtable row ID
python run_1_product_3_styles_feed.py --target table_lamps --record-id recXXXXXXXXXXXXXX
```

---

## 📝 Audit Logs

All API requests and responses are recorded in structured JSON format in:
- `output/logs/1_product_3_styles_{category}_akeneo_logs.json`
- `output/logs/1_product_3_styles_{category}_krea_logs.json`
- `output/logs/1_product_3_styles_{category}_claude_logs.json`
- `output/logs/1_product_3_styles_{category}_fal_banana_logs.json`
