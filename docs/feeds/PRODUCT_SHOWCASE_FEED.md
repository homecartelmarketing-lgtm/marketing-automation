# Product Showcase Feed Automation Pipeline

The **Product Showcase Feed Automation Pipeline** generates premium commercial studio feed posts (`1080 x 1350 px`) highlighting individual lighting fixtures—such as luxury Table Lamps—in modern architectural settings with rich focus on texture, finish, and form.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1350 px` (Aspect Ratio `4:5`)
- **Format**: 4-Slide Instagram Feed Carousel Post
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 1 (Hero Group Post)**: Commercial group podium arrangement featuring 3 featured lighting fixtures styled harmoniously on cylindrical architectural pedestals, with the HomeCartel logo stamped at bottom-left (`HOMECARTEL_LOGO_BOX`).
  - **Slides 2, 3, 4 (Solo Spotlight Posts)**: Dedicated individual spotlight slides for each of the 3 featured products on its individual pedestal with ambient room lighting, each stamped with the HomeCartel logo at bottom-left (`HOMECARTEL_LOGO_BOX`).

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ingestion** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + Shopify cross-check & cross-table dedup | Akeneo Catalog (`table_lamps`) | `Furniture Item 1-3`, `SKU 1-3`, `Item Name 1-3` -> Status: `Standby` |
| **Phase 1** | **Krea Studio Interior** | Krea AI | `krea-2-medium` (4:5, 1K)<br>Moodboard: `257569e1-7be8-4412-a90f-acbc347e4646` | Minimalist group podium prompt | `Interior Photo` |
| **Phase 2** | **Claude Vision Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior Photo` + Product Catalogs | Blending & placement prompts |
| **Phase 3** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | Group blend + 3 individual solo blends | 4 blended images |
| **Phase 4** | **Local PIL Brand Watermark & Assembly** | **Local Python Pillow** | **Zero-API Local Python Script**<br>Box: $190.3 \times 63.5\text{ px}$ @ $(108.0, 1178.5)$ | Stamped across **all 4 slides** (Hero + 3 Solo) | Watermarked carousel attached to `FEED - Product Showcase Feed` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{PS\text{-}FEEDS\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `PS` (Product Showcase)
- **Content Format**: `FEEDS`
- **Fixture Codes**: `TL` (Table Lamp)

### Real-World Examples:
- `PS-FEEDS-TL-1` (Row 1 of Table Lamp Product Showcase Feed)
- `PS-FEEDS-TL-4` (Row 4 of Table Lamp Product Showcase Feed)
- `PS-FEEDS-TL-10` (Row 10 of Table Lamp Product Showcase Feed)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Table Lamps** | `TL` | `tbln0MNBaVVrZ0wrF` | `PS-FEEDS-TL` | `257569e1-7be8-4412-a90f-acbc347e4646` | `AIRTABLE_TABLE_ID_PRODUCT_SHOWCASE_FEED` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting interior generation.
- **`Scheduled` (`S`)**: Queued for batch generation.
- **`Drafting` (`D`)**: Processing through Krea or Fal AI.
- **`For Modification` (`FM`)**: Flagged for vignette re-styling.
- **`Completed` (`C`)**: Showcase image generated, watermarked, and attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow Layout Specs

The carousel post receives a **Zero-API Local Python Pillow** logo watermark across **all 4 slides** (Hero Slide 1 + Solo Slides 2, 3, 4):
- **Logo Placement Coordinates (`HOMECARTEL_LOGO_BOX`)**:
  - Canvas: `1080 x 1350 px`
  - Width: `190.3 px`
  - Height: `63.5 px`
  - X Coordinate (Left): `108.0 px`
  - Y Coordinate (Top): `1178.5 px`
  - Rotation: `0°`
- **Zero API Rule**: Watermark compositing is executed strictly locally via Pillow without cloud API calls.
- **Logo Sourcing & Fallback**: The pipeline checks the row's `Logo` / `Logo Watermark` field first; if empty or absent, it falls back to the high-resolution local disk asset `assets/homecartel_logo.png`.
- **Target Field**: All 4 watermarked slides are uploaded as a batch into `FEED - Product Showcase Feed`.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run the complete Product Showcase Feed pipeline
python generate_product_showcase_feed_pipeline.py --mode all

# Run for at most 3 items
python generate_product_showcase_feed_pipeline.py --mode all --max-items 3

# Dry run (no AI calls, no Airtable writes)
python generate_product_showcase_feed_pipeline.py --dry-run

# Re-render one specific record
python generate_product_showcase_feed_pipeline.py --mode all --record-id recXXXXXXXXXXXXXX
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Feed** tab.
4. Select **Product Showcase Feeds** (`tbln0MNBaVVrZ0wrF`).
5. Select target rows and click **Run Selected**.
