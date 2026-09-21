# Moodboard Reel Automation Pipeline

The **Moodboard Reel Automation Pipeline** generates high-end **9:16 vertical video reels (1080 x 1920 px)** showcasing 4 lighting products per row in designer room interiors, transitioning smoothly between editorial moodboard layouts, lifestyle vignettes, and an official brand outro set to 20-second ambient audio.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Duration**: ~20.0 seconds
  - **4 Product Vignettes**: Individual lifestyle room blends showcasing each of the 4 products.
  - **Moodboard Conversion Slides**: Editorial aesthetic flat-lay sequence.
  - **Branded Outro**: Final call-to-action slide.
- **Audio Profile**: 20.0 seconds Stereo AAC @ 192 kbps background music.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo 4-Product Scrape** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog | `Furniture Item1..4`, `Item Name1..4` -> Status: `Standby` |
| **Phase 2** | **Krea Room Interiors** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Moodboard: `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | 4 Room Prompts | `Interior1..4` -> Status: `Already attached a room Interior` |
| **Phase 2.5** | **Claude Vision Prompting + Unique Materials** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | 4 Furniture Products (1 row-level call) + 4 Interiors + 4 Products | `Texture1..12` (12 globally-unique material words, never repeating) + `Prompt1..4` (materials conveyed visually in the blend prompt) -> Status: `Processing` |
| **Phase 3** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | Interiors + Products + Prompts | `Moodboard Blended` (4 images) + YOLO item-name tags on blends -> `Blended Image with Name text` |
| **Phase 4** | **3-Panel Moodboard Conversion**| Fal AI | `fal-ai/nano-banana-pro/edit`<br>Blended + Reference Template | 4 Blends + Reference Photo + Prompt | `Converted Moodboard` (4 raw 3-panel images) |
| **Phase 4.5** | **Music Generation** (Optional)| Fal AI ElevenLabs | `fal-ai/elevenlabs/music`<br>120 BPM luxury lounge house music | Music Prompt | `Music Generated` (20s audio) |
| **Phase 5** | **Reel Video Assembly** | Local FFmpeg | 2x2 collage + 8 slides + Outro + Audio mix | Converted Moodboards + Name-tagged Blends + Audio | `REEL - Moodboard Reel` -> Status: `Complete` |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{MB\text{-}REEL\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `MB` (Moodboard)
- **Content Format**: `REEL`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `CL` (Cluster Chandelier), `LC` (Linear Chandelier), `FL` (Floor Lamp), `WS` (Wall Sconce), `TL` (Table Lamp)

### Real-World Examples:
- `MB-REEL-CH-1` (Row 1 of Chandelier Modern Moodboard Reel)
- `MB-REEL-PE-4` (Row 4 of Pendant Lights Moodboard Reel)
- `MB-REEL-FL-9` (Row 9 of Floor Lamp Moodboard Reel)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- |
| **Chandelier Modern** | `CH` | `tbl026zbECJJ9FRfj` | `AIRTABLE_TABLE_ID_CHANDELIER_MODERN_MOODBOARDREEL` |
| **Pendant Lights** | `PE` | `tblpjRudEy6fobIrP` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARDREEL` |
| **Cluster Chandeliers** | `CL` | `tblJX6rd5nhhEuWbL` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_MOODBOARDREEL` |
| **Linear Chandeliers** | `LC` | `tblj4DVzllYa8pliK` | `AIRTABLE_TABLE_ID_LINEAR_CHANDELIER_MOODBOARDREEL` |
| **Floor Lamps** | `FL` | `tblF3ot4fdHN2VCQn` | `AIRTABLE_TABLE_ID_FLOOR_LAMP_MOODBOARDREEL` |
| **Wall Sconces** | `WS` | `tbli7nuOEhR8inzva` | `AIRTABLE_TABLE_ID_WALL_SCONCE_MOODBOARDREEL` |
| **Table Lamps** | `TL` | `tblr0uAYkDWDQZinl` | `AIRTABLE_TABLE_ID_TABLE_LAMP_MOODBOARDREEL` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped 4-product row awaiting generation.
- **`Scheduled` (`S`)**: Queued for batch video generation.
- **`Drafting` (`D`)**: Processing through Krea, Fal Nano, or FFmpeg video compilation.
- **`For Modification` (`FM`)**: Flagged for moodboard palette refinement.
- **`Completed` (`C`)**: Final MP4 video reel attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Video & Audio Specs

- **FFmpeg Concat Architecture**: Generates smooth crossfade transitions between the 4 product blends, moodboard flat-lay, and branded outro.
- **Audio Synchronization**: Audio track is normalized to $-16\text{ LUFS}$ to match standard social media broadcast levels.

---

## 7. CLI Execution Commands

### CLI Execution via PowerShell

```powershell
# Run full 5-phase pipeline for Chandelier Modern
python run_moodboard_reel.py --category chandelier_modern

# Run for Pendant Lights
python run_moodboard_reel.py --category pendant_lights_reel

# Run specific phase (e.g. video compilation only)
python run_moodboard_reel.py --phase reel --limit 1

# Process single row
python run_moodboard_reel.py --limit 1
```
