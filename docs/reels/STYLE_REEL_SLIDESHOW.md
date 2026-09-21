# Style Reel Slideshow Automation Pipeline

The **Style Reel Slideshow Automation Pipeline** generates an architectural **11-second 9:16 vertical video slideshow reel (1080 x 1920 px)** for table `tblFFEvkHb3jLKrcv`. It seamlessly chains 5 coherent interior living spaces featuring 4 distinct blended lighting fixture categories (Chandelier, Floor Lamp, Table Lamp, Linear Chandelier, and Pendant Light) into a single cohesive home tour video.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Slideshow Timeline (Total 11.0 Seconds)**:
  - **Slide 1 (Slot 1 Interior1)**: 3.0 seconds duration (Living Room architectural cover shot).
  - **Slide 2 (Slot 2 Blended Image2)**: 2.0 seconds duration (Master Bedroom with Floor Lamp).
  - **Slide 3 (Slot 3 Blended Image3)**: 2.0 seconds duration (Living Room sofa end table with Table Lamp).
  - **Slide 4 (Slot 4 Blended Image4)**: 2.0 seconds duration (Modern Kitchen with Linear Chandelier).
  - **Slide 5 (Slot 5 Blended Image5)**: 2.0 seconds duration (Dining Room with Pendant Light).

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Multi-Category Akeneo Scrape**| Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (4 categories) | `Furniture Item[2-5]`, `Item Name[2-5]` -> Status: `Pending` (`P`) |
| **Phase 2** | **Sequential Krea Generation** | Krea AI | `krea-2-medium` (9:16, 1K) with cumulative style referencing | Dedicated moodboard per room slot | `Interior[1-5]` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Claude Vision Prompting** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `Interior[2-5]` + `Furniture Item[2-5]` | `Blending Prompt[2-5]` -> Status: `Drafting` (`D`) |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Interior[2-5]` + `Furniture[2-5]` + `Prompt[2-5]` | `Blended Image[2-5]` -> Status: `Drafting` (`D`) |
| **Phase 5** | **FFmpeg Slideshow Video** | Local FFmpeg | Zero-API Local Video Engine | 5 photos in sequence | `Style Reel Slideshow` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{SRS\text{-}REEL\text{-}SET\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `SRS` (Style Reel Slideshow)
- **Content Format**: `REEL`
- **Set Identifier**: `SET` (5-Room Interior Tour)

### Real-World Examples:
- `SRS-REEL-SET-1` (Row 1 of Style Reel Slideshow)
- `SRS-REEL-SET-4` (Row 4 of Style Reel Slideshow)
- `SRS-REEL-SET-10` (Row 10 of Style Reel Slideshow)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Scope | Airtable Table ID | Foreign Key Prefix | Slot Sequence & Moodboard IDs | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **5-Room Style Tour** | `tblFFEvkHb3jLKrcv` | `SRS-REEL-SET` | 1. Living Room: `b5ffdcbb-192e-4528-8d86-d1a4cf496887`<br>2. Bedroom: `b1641228-beec-4823-8d01-1de3eec8410d`<br>3. End Table: `fb2487fb-2895-4d2c-9758-805aaf1bac69`<br>4. Kitchen: `994a703c-4c6b-498a-bb27-7609615a74bd`<br>5. Dining: `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | `AIRTABLE_TABLE_ID_STYLE_REEL_SLIDESHOW` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped 4-product bundle awaiting interior generation.
- **`Scheduled` (`S`)**: Queued for batch video generation.
- **`Drafting` (`D`)**: Processing through sequential Krea rooms, Claude prompts, or Fal blending.
- **`For Modification` (`FM`)**: Flagged for room style re-alignment.
- **`Completed` (`C`)**: `Style Reel Slideshow` MP4 video attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local FFmpeg Slideshow Specifications

- **Slide Timing & Transitions**:
  ```bash
  # Assembled with exact duration per slot (3.0s cover, 2.0s per blend)
  ffmpeg -f concat -safe 0 -i slides.txt -c:v libx264 -r 30 -pix_fmt yuv420p output.mp4
  ```
- **Zero API Video Rendering**: The stitching and MP4 encoding run 100% locally via FFmpeg.

---

## 7. CLI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive menu
python run_style_reel_slideshow.py --menu

# Run full pipeline for all rows
python run_style_reel_slideshow.py --phase all --execute

# Run Phase 1 (Akeneo Scrape) for 1 row
python run_style_reel_slideshow.py --phase 1 --max-rows 1 --execute

# Run Phase 5 (FFmpeg video compilation) only
python run_style_reel_slideshow.py --phase 5 --execute
```
