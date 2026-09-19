# Before & After Reel Automation Pipeline

The **Before & After Reel Automation Pipeline** generates captivating **9:16 vertical video transformation reels (1080 x 1920 px)**. It showcases an empty room interior transitioning into a fully styled architectural space featuring a HomeCartel lighting fixture across multiple angles, set to background music with centered typography.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Structure**:
  - **"Before" Scene**: Empty luxury room interior highlighting architectural potential.
  - **"After" Transformation**: Installed and illuminated lighting fixture in the room.
  - **Multiple Angle Details**: Close-up angles highlighting product textures.
  - **Branded Outro**: Call-to-action closing card.
- **Audio Profile**: Stereo AAC @ 192 kbps background music.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`floor_lamps`, `pendant_lights`, `chandeliers`) | `Furniture Item`, `Item Name`, `SKU` -> Status: `Pending` (`P`) |
| **Phase 2** | **Krea Room Interior** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Preset category Moodboard | Room Prompt | `Interior Generated Photo` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Claude Vision Prompting** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | Interior + Product Photos | `Blending Prompt` -> Status: `Drafting` (`D`) |
| **Phase 4** | **Nano Banana Pro Day Blend** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | Interior + Product + Prompt | `Blended Image` -> Status: `Drafting` (`D`) |
| **Phase 5** | **Multiple Angle Generation** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16` | `Blended Image` | `Multiple Angle Blended Image` -> Status: `Drafting` (`D`) |
| **Phase 6** | **FFmpeg Slideshow Reel Assembly**| Local FFmpeg | Zero-API Local Video Engine + Typography | All angles + Outro + Audio | `Slide Show Before and After Reel` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{BA\text{-}REEL\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `BA` (Before & After)
- **Content Format**: `REEL`
- **Fixture Codes**: `FL` (Floor Lamp), `PE` (Pendant Light), `CH` (Chandelier)

### Real-World Examples:
- `BA-REEL-FL-1` (Row 1 of Floor Lamp Before & After Reel)
- `BA-REEL-PE-4` (Row 4 of Pendant Lights Before & After Reel)
- `BA-REEL-CH-8` (Row 8 of Chandelier Before & After Reel)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Floor Lamps** | `FL` | `tbl2VoWOt7sSut4E2` ⚠️ *(table no longer exists in the live base as of 2026-09-19 — recreate it before running `--target floor_lamps`)* | `b1641228-beec-4823-8d01-1de3eec8410d` | `AIRTABLE_TABLE_ID_FLOORLAMP_BEFORE_AFTER_REEL` |
| **Pendant Lights** | `PE` | `tbleUP86Kw36G8Hdw` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_BEFORE_AFTER_REEL` |
| **Chandeliers** | `CH` | `tbloMhCOngGDWFS2y` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CHANDELIERS_BEFORE_AFTER_REEL` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting interior generation.
- **`Scheduled` (`S`)**: Queued for batch video generation.
- **`Drafting` (`D`)**: Processing through Krea, Fal Nano, or FFmpeg assembly.
- **`For Modification` (`FM`)**: Flagged for angle or timing adjustment.
- **`Completed` (`C`)**: `Slide Show Before and After Reel` attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Video & Typography Specs

- **Zero-API Video Compilation**: The multi-angle transitions, text overlay ("Before" / "After"), and outro concatenation execute locally via FFmpeg.
- **Google Drive Export**: Rendered reels are automatically mirrored to the local cache and Google Drive staging folder.

---

## 7. CLI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive runner
python run_before_after_reel.py

# Target Floor Lamps
python run_before_after_reel.py --target floor_lamps

# Target Pendant Lights
python run_before_after_reel.py --target pendant_lights

# Target Chandeliers
python run_before_after_reel.py --target chandeliers
```
