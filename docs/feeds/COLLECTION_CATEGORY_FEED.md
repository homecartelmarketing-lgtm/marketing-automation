# Collection Category Feed Automation Pipeline

The **Collection Category Feed Automation Pipeline** generates complete 5-room coordinated whole-home collections into branded Instagram Feed carousels (`1080 x 1350 px`). It pairs an exterior architectural cover shot with 4 interior living spaces (Bedroom, Dining Room, Kitchen, Living Room) featuring harmoniously matched lighting fixtures.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1350 px` (Aspect Ratio `4:5`)
- **Format**: 5-Slide Instagram Carousel Post
- **Color Profile**: sRGB, 8-bit truecolor
- **Slide Composition**:
  - **Slide 1 (`Blended Image1`)**: Clean modern luxury exterior architecture cover slide.
  - **Slide 2 (`Blended Image2`)**: Master Bedroom interior blended with matching lighting fixture.
  - **Slide 3 (`Blended Image3`)**: Contemporary Dining Room blended with coordinated lighting fixture.
  - **Slide 4 (`Blended Image4`)**: Open-concept Luxury Kitchen blended with coordinated lighting fixture.
  - **Slide 5 (`Blended Image5`)**: Coordinated Living Room interior blended with statement lighting fixture.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Sequential Krea Generation** | Krea AI | `krea-2-medium` (4:5, 1K) with sequential image chaining | Category room prompts + dedicated moodboard IDs per room | `Interior1` (Exterior), `Interior2` (Bedroom), `Interior3` (Dining), `Interior4` (Kitchen), `Interior5` (Living) -> Status: `Processing` |
| **Phase 2** | **Claude Sonnet 5 Matching** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior2..5` simultaneous vision analysis | Populates `Suggest Furniture Item[2-5]` with non-duplicate categories |
| **Phase 3** | **Akeneo Dynamic Scraping** | Akeneo PIM API | Active products (`enabled=true`) + cross-table deduplication | Categories suggested by Claude | Populates `Furniture Item[2-5]` and `Item Name[2-5]` |
| **Phase 4** | **Claude Prompt Engineering** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior[2-5]` + `Furniture Item[2-5]` | Generates `Blending Prompt2..5` |
| **Phase 5** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `4:5`, Resolution: `1K` | `Interior[2-5]` + `Furniture Item[2-5]` + `Blending Prompt[2-5]` | Generates `Blended Image2..5` (Slide 1 gets `Interior1`) -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record generated or processed in the Collection Category Feed table is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{CC\text{-}FEEDS\text{-}SET\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `CC` (Collection Category)
- **Content Format**: `FEEDS`
- **Set Identifier**: `SET` (5-Room Coordinated Collection)

### Real-World Examples:
- `CC-FEEDS-SET-1` (Row 1 of the 5-Room Collection Feed)
- `CC-FEEDS-SET-5` (Row 5 of the 5-Room Collection Feed)
- `CC-FEEDS-SET-12` (Row 12 of the 5-Room Collection Feed)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Collection Scope | Airtable Table ID | Foreign Key Prefix | Room Sequence & Moodboard IDs | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **5-Room Collection Set** | `tbl5o1j3XvUaUqmjs` | `CC-FEEDS-SET` | 1. Exterior: `ec860c16-10e4-429e-bba6-ff068bcb80b1`<br>2. Bedroom: `06fcc401-2e66-4638-b581-45220a8b497e`<br>3. Dining: `0844ad92-c34a-4dc8-9d70-d09498dc098c`<br>4. Kitchen: `994a703c-4c6b-498a-bb27-7609615a74bd`<br>5. Living: `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_COLLECTION_CATEGORY_FEED` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Initial placeholder record created in Airtable.
- **`Scheduled` (`S`)**: Queued for batch generation.
- **`Drafting` (`D`)**: Under active processing through Krea rooms, Claude matching, or Fal blending.
- **`For Modification` (`FM`)**: Set if image quality requires re-running a specific slot.
- **`Completed` (`C`)**: All 5 slides generated, validated, and attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Mandatory Generation, Scraping & Overlay Rules

> [!CAUTION]
> ### Always Generate Brand-New Rows (Never Rerun Remaining Old Rows)
> - Every run of this pipeline (from Web Studio UI or CLI default) MUST scrape fresh active products into a **brand-new Airtable row** and process that row end-to-end (Phases 1 through 5).
> - **DO NOT search for, iterate over, or rerun remaining, old, or incomplete rows in the table.**
> - The ONLY exception is if a developer explicitly supplies `--target-record <rec_id>` via CLI to re-render a specific record.

> [!IMPORTANT]
> ### Strict Shopify Active Verification & Base-Wide Deduplication
> - Every product candidate suggested by Claude and scraped from Akeneo MUST be strictly verified against published products on Shopify (`homecartel.net`). Any item that is Draft, Inactive, Archived, or Unlisted on Shopify is immediately skipped.
> - Before assigning products to Slots 2–5, cross-check against all 60+ tables across the entire base to guarantee zero duplicate appearances across Stories, Feeds, or Reels.

### YOLO Floating Tags & HomeCartel Feed Logo Auto-Layout (Zero API Cost)
- **Slide 1 (Exterior Cover)**: Stamped with the official HomeCartel Feed logo at bottom-left (`x=108.0, y=1178.5, width=190.3, height=63.5`) via Pillow.
- **Slides 2–5 (Lifestyle Interiors)**: Stamped with the floating YOLO 2-line item tag (`Line 1`: Item Name in Poppins Bold 19px, `Line 2`: Category in Poppins Regular 19px) anchored to the detected product, plus the HomeCartel Feed logo at bottom-left.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run the complete 5-phase pipeline for all unprocessed rows
python run_collection_category_feed.py --phase all --execute

# Run specific phase for a targeted record ID
python run_collection_category_feed.py --target-record recG4x8RgQXO5kWEs --phase all --execute

# Run only Phase 1 (Krea room generation)
python run_collection_category_feed.py --phase 1 --execute

# Run only Phase 2 (Claude vision room matching)
python run_collection_category_feed.py --phase 2 --execute

# Run only Phase 5 (Fal AI Nano Banana Pro blending)
python run_collection_category_feed.py --phase 5 --execute
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200` in your web browser.
2. Enter security PIN: `1234`
3. Click the **Feed** tab in the main header.
4. Select the **Collection Category Feeds** subtab (`tbl5o1j3XvUaUqmjs`).
5. Review the 5-room progress columns and execute batch runs.
