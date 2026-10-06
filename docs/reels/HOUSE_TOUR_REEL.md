# House Tour Reel Automation Pipeline

The **House Tour Reel Automation Pipeline** generates a premium **9:16 vertical video reel (1080 x 1920 px)** touring 11 rooms of one home — Living Room Lounge Corner, Primary Bedroom, Dining Room Table, Kitchen Counter, Living Room Central, Dining Credenza Wall, Living Room Media Console, Primary Bedroom Dressing, Entryway Foyer, Guest Bedroom Bed, and Guest Bedroom Dresser — in an organic-modern / Japandi style.

Room interiors are generated fresh by Krea using 11 ultra-detailed reusable prompts derived frame-by-frame from `assets/house_tour_reference.mp4` paired with a unified Japandi moodboard ID (`fda7090c-787b-4116-94cd-3feef613eaaa`). Each generated room interior is dynamically analyzed by Claude 3.5 Sonnet Vision to guide fixture blending and extract a chic lowercase editorial room title. Fixtures are blended into the rooms, animated into 3-second motion clips with Fal Kling V3 Turbo Pro, scored with ElevenLabs background music, and assembled locally via FFmpeg with fast beat-matched snap cuts, dynamic upper-third room titles, and fluid lower-third animated product reveals in Poppins font.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Structure & Pacing**:
  - **Pacing**: 22.0-second total runtime with exactly **2.0 seconds per room** across all 11 rooms (`[2.0s] * 11`). Trims each 3.0s Kling clip from `0.5s` to `2.5s` for smooth constant camera velocity. Optional relaxed 24.5s pacing available via `--pacing relaxed`.
  - **Cut Style**: Default `snap` (clean beat cuts); optional `dissolve` (crossfades).
  - **Upper-Third Room Title**: Poppins-Medium 44px, solid white with subtle shadow (`y = 480`, centered), dynamically identified from Claude 3.5 Sonnet Vision analysis (`5. ROOM TITLE: ...`).
    - **Strict Zero Fallback Policy**: If Claude Vision fails, times out, or produces no room title, upper-third text is **completely omitted** (`""` — no text filter is generated). No hardcoded default room styles will ever be stamped.
  - **Lower-Third Animated Product Reveal**: Poppins-Medium 32px, solid white with subtle shadow (`y = 1600`, centered). Displays normalized **Item Name + Product Type** (e.g., `kansa table lamp`, `indus wall light`). Slides upward by 20px and fades in opacity from 0 to 1 between `t = 0.25s` and `t = 0.55s` after each shot cut (holds steady for ~1.45s).
  - **Font Policy**: Strictly Poppins typography (`content_automation/fonts/Poppins-Medium.ttf`). Zero external or serif fonts.
  - **Outro**: Seamless loop (`--outro none`, default for reference pacing) or optional branded HomeCartel outro (`assets/outro_layout.jpg`, 24.5s total).
- **Audio Profile**: Stereo AAC @ 192 kbps Fal ElevenLabs background music (~24s warm organic-modern acoustic instrumental).
- **Caption**: none — the pipeline writes no caption or hashtag text.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo 11-Fixture Scrape** | Akeneo PIM API | Active ingestion (`enabled=true`) + Shopify Published check + base-wide dedup | Akeneo catalog (11 room categories) | `Furniture Item1..11`, `Item Name1..11`, `SKU1..11` -> Status: `Standby` (`P`) |
| **Phase 2** | **Krea Room Interiors** | Krea AI | `krea-2-medium` (9:16, 1K)<br>11 reference-derived detailed prompts + unified moodboard | `Interior Prompt1..11` (Studio override > built-in detailed prompt) | `Interior1..11` (+ `Interior Prompt`, `Moodboard ID`) -> Status: `Interior Generated` (`P`) |
| **Phase 2.5** | **Claude Vision Room Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` (vision mode) | `Interior1..11` | `Interior Analysis1..11` (placement instruction + `5. ROOM TITLE: ...`) -> Status: `Interior Analyzed` (`P`) |
| **Phase 3** | **Claude Blend Prompts** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `InteriorN` + `Furniture ItemN` + `Interior AnalysisN` | `Generated Prompt1..11` -> Status: `Prompt Generated` (`P`) |
| **Phase 4** | **Nano Banana Pro Blending + YOLO Tags** | Fal AI + local YOLO-World | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Interior` + `Product` + `Prompt` | `Blended Image1..11` (clean, feeds Kling) + `Blended Image with Name text` (tagged archive) -> Status: `Blended Image Generated` (`P`) |
| **Phase 5** | **Kling Motion Clips** | Fal AI | `fal-ai/kling-video/v3/turbo/pro/image-to-video`<br>Duration: `3` (s) per clip | `Blended ImageN` (fal-staged) + pan-pattern motion prompt (odd left, even right) | `Kling Video1..11` -> Status: `Kling Video Generated` (`P`), or `Generation Failed Via Kling` on failure (row stops) |
| **Phase 6/7** | **ElevenLabs Music** | Fal AI | `fal-ai/elevenlabs/music` (~24s organic modern instrumental) | — | `Music Generated` -> Status: `Music Generated` (`P`) |
| **Phase 8** | **FFmpeg Video Reel Assembly** | Local FFmpeg | Zero-API video engine: 22.0s (2.0s per room), upper-third dynamic room titles, lower-third animated product reveals | 11 Kling clips + item names + analysis + outro + audio | `Final Video` -> Status: `Done` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

$$\text{Format: } \mathbf{HTR\text{-}REEL\text{-}SET\text{-}\langle ROW\_ID\rangle}$$
- **Idea Abbreviation**: `HTR` (House Tour Reel)
- **Content Format**: `REEL`
- **Set Identifier**: `SET` (11-room home tour)

### Real-World Examples:
- `HTR-REEL-SET-1` (Row 1 of House Tour Reel)
- `HTR-REEL-SET-9` (Row 9 of House Tour Reel)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Scope | Airtable Table ID | Foreign Key Prefix | Slot Sequence & Default Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **11-Room House Tour** | `tblqXkdDw4O7hxJS4` | `HTR-REEL-SET` | **Unified Moodboard**: `fda7090c-787b-4116-94cd-3feef613eaaa`<br>1. Living Room Lounge / Chandelier<br>2. Primary Bedroom / Table Lamp<br>3. Dining Room Table / Pendant Light<br>4. Kitchen Counter / Pendant Light<br>5. Living Room Central / Floor Lamp<br>6. Dining Credenza Wall / Wall Light<br>7. Living Room Media Console / Table Lamp<br>8. Primary Bedroom Dressing / Wall Light<br>9. Entryway Foyer / Chandelier<br>10. Guest Bedroom Bed / Ceiling Light<br>11. Guest Bedroom Dresser / Pendant Light | `AIRTABLE_TABLE_ID_HOUSE_TOUR_REEL` |

Studio pencil keys: per-room `KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM1..11` / `PROMPT_HOUSE_TOUR_REEL_ROOM1..11`, edited through 11 labeled fields in the single card's moodboard/prompt modals (defaults to unified moodboard `fda7090c-787b-4116-94cd-3feef613eaaa` and the 11 reference-matching prompts).

Full schema: `Foreign Key ID`, `ID`, `Date and Time Generated`, `Status`, `Furniture Item1..11`, `Item Name1..11`, `SKU1..11`, `Interior1..11`, `Interior Prompt1..11`, `Interior Analysis1..11`, `Generated Prompt1..11`, `Blended Image1..11`, `Blended Image with Name text`, `Kling Video1..11`, `Music Generated`, `Outro`, `Final Video`.

---

## 5. 5-Status Lifecycle & PHT Timestamps

| Badge | Color | Lifecycle State | Airtable Status Value | Operational Meaning |
| :---: | :--- | :--- | :--- | :--- |
| **P** | Sky Blue | **Posted / Processing** | Posted, Processing, Pending, In Progress, Standby, intermediate phase statuses | Record is actively queued or being processed. |
| **S** | Purple | **Scheduled** | Scheduled, Schedule | Approved and scheduled for publishing. |
| **C** | Emerald | **Complete / Done** | Complete, Completed, Done | All phases complete; deliverables attached. |
| **D** | Rose | **Discarded** | Discard, Discarded | Archived or rejected candidate. |
| **FM** | Amber | **For Manual / Revision** | For Manual, Minor revision, FM | Flagged for manual review or adjustment. |

When a row reaches `Done`, the pipeline stamps Philippine Standard Time (UTC+8, ISO 8601) into **Date and Time Generated** (e.g. `2026-10-06T13:30:00+08:00`).

---

## 6. Local Typography, Tagging & Video Specs

- **Zero-Cost Layout & Animation**:
  All typography, motion overlays, and video assembly execute 100% locally via FFmpeg. Zero external image/video API cost for composition.
- **Strict Poppins Font**:
  Typography uses `content_automation/fonts/Poppins-Medium.ttf`. No external or serif fonts.
- **Upper-Third Dynamic Room Titles**:
  - Font: `Poppins-Medium.ttf`, 44px, solid white with subtle shadow (`y = 480`, centered).
  - Text: Extracted directly from Claude 3.5 Sonnet Vision analysis (`5. ROOM TITLE: ...`).
  - **Zero Default Fallback**: If Claude Vision fails, is missing, or does not identify a room title, upper-third text is completely omitted (`""`). No hardcoded default titles are stamped.
- **Lower-Third Animated Product Name Reveal**:
  - Font: `Poppins-Medium.ttf`, 32px, solid white with subtle shadow (`y = 1600`, centered).
  - Format: Normalized **Item Name + Product Type** (e.g., `kansa table lamp`, `indus wall light`).
  - Animation: Slides upward by 20px and fades in opacity from 0 to 1 between `t = start + 0.25s` and `t = start + 0.55s` into each shot cut via dynamic FFmpeg expressions:
    ```
    y_expr = 1600 + if(lt(t, start + 0.25), 20, if(lt(t, start + 0.55), (1 - (t - (start + 0.25)) / 0.30) * 20, 0))
    alpha_expr = if(lt(t, start + 0.25), 0, if(lt(t, start + 0.55), (t - (start + 0.25)) / 0.30, 1))
    ```
- **YOLO-World Poppins Tags**:
  - Stamped onto `Blended Image with Name text` for archiving.
- **Kling Motion Prompts**:
  - Deterministic per-slot template with alternating pans (odd slots pan left, even slots pan right).

---

## 7. Mandatory Generation & Scraping Rules

> [!CAUTION]
> ### Always Generate Brand-New Rows (Never Rerun Remaining Old Rows)
> - Every run of this pipeline (from Web Studio UI or CLI default) MUST scrape 11 fresh active fixtures (one per room slot) into a **brand-new Airtable row** and process that row end-to-end (Phases 1 through 8).
> - **DO NOT search for, iterate over, or rerun remaining, old, or incomplete rows in the table.**
> - The ONLY exception is if a developer explicitly supplies `--record-id <rec_id>` via CLI to re-render a specific record.

> [!IMPORTANT]
> ### Strict Shopify Active Verification & Base-Wide Deduplication
> - Every candidate scraped from Akeneo MUST be strictly verified against published products on Shopify (`homecartel.net`). Any item that is Draft, Inactive, Archived, or Unlisted on Shopify is immediately skipped.
> - Before adding fixtures to the new row, cross-check against all 60+ tables across the entire base to ensure zero duplicate appearances across Stories, Feeds, or Reels.

---

## 8. CLI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run the complete House Tour Reel pipeline (1 brand-new 11-fixture row, end to end)
python run_house_tour_reel.py

# Process 3 rows in batch
python run_house_tour_reel.py --max-rows 3

# Scrape only (creates new 11-fixture rows, no video)
python run_house_tour_reel.py --phase scrape --max-rows 1

# Silent reel (no ElevenLabs music)
python run_house_tour_reel.py --no-music

# Process a specific Record ID
python run_house_tour_reel.py --record-id recXXXXXXXXXXXXXX

# Assemble with branded outro (default is seamless loop)
python run_house_tour_reel.py --record-id recXXXXXXXXXXXXXX --outro branded
```

### Web UI Dashboard Execution
1. Open http://localhost:5200 in your web browser.
2. Enter the Studio PIN if DASHBOARD_PIN is configured.
3. Click the **Reel** tab in the main navigation.
4. Select the **House Tour** subtab.
5. Select the single **House Tour** card (table `tblqXkdDw4O7hxJS4`).
6. Optionally review the moodboard/prompt settings, then click **Run**, confirm the batch count (default 1).
7. The pipeline scrapes 11 fresh active fixtures into a **brand-new row** and executes Phases 1 through 8 end-to-end.
