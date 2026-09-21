# Product Closeup Reel Automation Pipeline

The **Product Closeup Reel Automation Pipeline** generates premium **9:16 vertical video reels (1080 x 1920 px)** highlighting 4 distinct lighting products per row (e.g. Table Lamps) in high-resolution residential vignettes, complete with Poppins title typography, smooth slideshow transitions, background audio, and brand outro.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Structure**:
  - **4 Lifestyle Vignettes**: 2.5 seconds per product (10.0 seconds total).
  - **Product Typography**: Poppins Regular 28pt product title overlays per slide.
  - **Branded Outro**: 3.0 seconds (`assets/outro_layout.jpg`).
- **Audio Profile**: Stereo AAC @ 192 kbps background music.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo 4-Product Scrape** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`table_lamps`) | `Furniture Item1..4`, `Item Name1..4` -> Status: `Pending` (`P`) |
| **Phase 2** | **Krea Bedroom Interiors** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Moodboard: `fb2487fb-2895-4d2c-9758-805aaf1bac69` | Room prompt ("Modern bedroom nightstand") | `Interior1..4` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Claude Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior1..4` + `Furniture Item1..4` | `Generated Prompt1..4` -> Status: `Drafting` (`D`) |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Interior` + `Product` + `Prompt` | 4 local blended stills -> Status: `Drafting` (`D`) |
| **Phase 4.5** | **Outro Attachment** | Local Storage | Zero-API Local Outro Sync | `assets/outro_layout.jpg` | `Outro` |
| **Phase 5** | **FFmpeg Video Reel Assembly** | Local FFmpeg | Zero-API Video Engine + Poppins Typography | 4 stills + Item Names + Outro | `Final Video` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{PCR\text{-}REEL\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `PCR` (Product Closeup Reel)
- **Content Format**: `REEL`
- **Fixture Codes**: `TL` (Table Lamp)

### Real-World Examples:
- `PCR-REEL-TL-1` (Row 1 of Table Lamps Product Closeup Reel)
- `PCR-REEL-TL-3` (Row 3 of Table Lamps Product Closeup Reel)
- `PCR-REEL-TL-7` (Row 7 of Table Lamps Product Closeup Reel)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Table Lamps** | `TL` | `tblqBZ946hVdOpmDV` | `fb2487fb-2895-4d2c-9758-805aaf1bac69` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_CLOSEUP_REEL` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped 4-lamp pack awaiting interior generation.
- **`Scheduled` (`S`)**: Queued for batch video generation.
- **`Drafting` (`D`)**: Processing through Krea, Fal Nano, or FFmpeg compilation.
- **`For Modification` (`FM`)**: Flagged for vignette re-rendering.
- **`Completed` (`C`)**: `Final Video` attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Typography & Video Specs

- **Item Name Overlay**: Clean white Poppins Regular 28pt stamped onto the bottom portion of each product slide.
- **Local Outro Sync**: Automatically verifies and attaches `assets/outro_layout.jpg` to the row.
- **FFmpeg Zero-API Assembly**: Slideshow video rendering runs 100% locally via FFmpeg.

---

## 7. Mandatory Generation & Scraping Rules

> [!CAUTION]
> ### Always Generate Brand-New Rows (Never Rerun Remaining Old Rows)
> - Every run of this pipeline (from Web Studio UI or CLI default) MUST scrape 4 fresh active products into a **brand-new Airtable row** and process that row end-to-end (Phases 1 through 5).
> - **DO NOT search for, iterate over, or rerun remaining, old, or incomplete rows in the table.**
> - The ONLY exception is if a developer explicitly supplies `--record-id <rec_id>` via CLI to re-render a specific record.

> [!IMPORTANT]
> ### Strict Shopify Active Verification & Base-Wide Deduplication
> - Every table lamp candidate scraped from Akeneo MUST be strictly verified against published products on Shopify (`homecartel.net`). Any item that is Draft, Inactive, Archived, or Unlisted on Shopify is immediately skipped.
> - Before adding lamps to the new row, cross-check against all 60+ tables across the entire base to ensure zero duplicate appearances across Stories, Feeds, or Reels.

---

## 8. CLI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run the complete Product Closeup Reel pipeline
python run_product_closeup_reel.py

# Enable background music
python run_product_closeup_reel.py --with-music

# Process 3 rows in batch
python run_product_closeup_reel.py --max-rows 3

# Scrape only (creates new 4-lamp rows)
python run_product_closeup_reel.py --phase scrape --max-rows 1

# Process a specific Record ID
python run_product_closeup_reel.py --record-id recXXXXXXXXXXXXXX
```
