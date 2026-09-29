# 1 Product, 3 Styles Reel Automation Pipeline

The **1 Product, 3 Styles Reel Automation Pipeline** generates high-engagement **18-second 9:16 vertical video reels (1080 x 1920 px)** for social media (Instagram Reels, TikTok, YouTube Shorts). It demonstrates a single lighting product (chandeliers) blended into 3 distinct luxury room interior styles, tagged with local YOLO-World item name labels, and compiled into a silent video sequence with custom holds and branded outro.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, silent video
- **Reel Duration**: Total ~18.0 seconds
  - **Room Style 1**: 5.0 seconds
  - **Room Style 2**: 4.0 seconds
  - **Room Style 3**: 4.0 seconds
  - **Branded Outro**: 5.0 seconds (`assets/outro_layout.jpg`) with 0.5s fade out
- **Item Tagging**: Editorial YOLO-World 2-line floating tag (`Line 1`: Item Name in Poppins Bold, `Line 2`: Category in Poppins Regular) anchored to the detected product.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo 1-Product Scrape** | Akeneo PIM API & Shopify | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`) | `Furniture Item`, `SKU`, `Item Name` -> Status: `Standby` (`P`) |
| **Phase 2** | **Krea AI 3 Room Interiors** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Chandelier Moodboard | 3 distinct room style prompts | `Interior1`, `Interior2`, `Interior3` -> Status: `Phase 2 - Ready` (`P`) |
| **Phase 3** | **Claude Sonnet 5 Prompt Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | 3 Interiors + Product photo | `Prompt1`, `Prompt2`, `Prompt3` -> Status: `Phase 3 - Ready` (`P`) |
| **Phase 4** | **Nano Banana Pro Multi-Blend** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Interior[1-3]` + `Furniture` + `Prompt[1-3]` | `1 Product 3 Style Blended` (3 images) -> Status: `Phase 4 - Ready` (`P`) |
| **Phase 5** | **YOLO Tagging & Silent Reel Video** | Local Pillow + YOLO-World + FFmpeg | Zero-API Local Compositor | 3 Blended Stills + Outro Layout | `Blended Image with Name text`, `Converted Reel` -> Status: `Complete` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{OP3S\text{-}REEL\text{-}CH\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `OP3S` (One Product Three Styles)
- **Content Format**: `REEL`
- **Fixture Code**: `CH` (Chandelier)

### Real-World Examples:
- `OP3S-REEL-CH-1` (Row 1 of Chandelier 1 Product 3 Styles Reel)
- `OP3S-REEL-CH-4` (Row 4 of Chandelier 1 Product 3 Styles Reel)
- `OP3S-REEL-CH-12` (Row 12 of Chandelier 1 Product 3 Styles Reel)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tbl6ls4AWcEcynBpZ` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL` |

> [!NOTE]
> The Studio fixture is Chandelier only. Floor Lamp and other lighting categories are not part of this Reel.
> Moodboard and prompt settings are configured via `KREA_MOODBOARD_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL` and `PROMPT_ONE_PRODUCT_THREE_STYLES_REEL_CHANDELIER`.

---

## 5. 5-Status Lifecycle & PHT Timestamps

The Airtable single-select `Status` field tracks records across 5 lifecycle stages:

| Badge | Color | Lifecycle State | Airtable Status Value | Operational Meaning |
| :---: | :---: | :--- | :--- | :--- |
| **`P`** | Sky Blue | **Posted / Processing** | `Posted`, `Processing`, `Pending`, `In Progress`, intermediate phase statuses | Record is actively queued or being processed. |
| **`S`** | Purple | **Scheduled** | `Scheduled`, `Schedule` | Approved and scheduled for publishing. |
| **`C`** | Emerald | **Complete / Done** | `Complete`, `Completed`, `Done` | All phases complete; deliverables attached. |
| **`D`** | Rose | **Discarded** | `Discard`, `Discarded` | Archived or rejected candidate. |
| **`FM`** | Amber | **For Manual / Revision** | `For Manual`, `Minor revision`, `FM` | Flagged for manual review or adjustment. |

### Execution Timestamp
When a row reaches `Complete` (`C`), the pipeline automatically writes the Philippine Standard Time timestamp (UTC+8, ISO 8601) into the **`Date and Time Generated`** field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Typography, Tagging & Video Specs

- **YOLO-World Floating Tags**: Detects chandelier positioning in all 3 blended slides, stamping product title in Poppins Bold and category in Poppins Regular.
- **Local Outro Sync**: Attaches `assets/outro_layout.jpg` to the video timeline with a 0.5s fade out transition.
- **Zero-API Video Compositor**: FFmpeg stitches the tagged slides into a silent 9:16 vertical MP4 (5s, 4s, 4s photo holds + 5s outro) locally without external video API costs.

---

## 7. Mandatory Generation & Scraping Rules

> [!CAUTION]
> ### Always Generate Brand-New Rows (Never Rerun Remaining Old Rows)
> - Every run of this pipeline (from Web Studio UI or CLI default) MUST scrape a fresh active product into a **brand-new Airtable row** and process that row end-to-end (Phases 1 through 5).
> - **DO NOT search for, iterate over, or rerun remaining, old, or incomplete rows in the table.**
> - The ONLY exception is if a developer explicitly supplies `--record-id <rec_id>` via CLI to re-render a specific record.

> [!IMPORTANT]
> ### Strict Shopify Active Verification & Base-Wide Deduplication
> - Every product candidate scraped from Akeneo MUST be strictly verified against published products on Shopify (`homecartel.net`). Any item that is Draft, Inactive, Archived, or Unlisted on Shopify is immediately skipped.
> - Before adding the product to the new row, cross-check against all 60+ tables across the entire base to ensure zero duplicate appearances across Stories, Feeds, or Reels.

---

## 8. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run the complete 5-phase pipeline end-to-end (1 item)
python run_one_product_three_styles_reel.py --phase all --max-rows 1

# Process a specific record ID
python run_one_product_three_styles_reel.py --record-id recXXXXXXXXXXXXXX

# Override moodboard or prompt via CLI
python run_one_product_three_styles_reel.py --phase all --moodboard-id de6ad512-870d-4ab7-a48c-3f3ca85faf24 --prompt "Luxury high-ceiling living room"
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200` in your web browser.
2. Enter the Studio PIN if `DASHBOARD_PIN` is configured.
3. Click the **Reel** tab in the main navigation.
4. Select the **1 Product 3 Styles Reel** subtab.
5. Select the **Chandelier** fixture card.
6. Click the **Run** button on the fixture card, confirm the batch count (default 1) in the confirmation modal, and the pipeline will scrape a fresh active chandelier and process the 3-style video end-to-end.
