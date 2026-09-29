# One at a time Lights Reel Automation Pipeline

The **One at a time Lights Reel Automation Pipeline** generates high-engagement **~11-second 9:16 vertical video reels (1080 x 1920 px)** for social media (Instagram Reels, TikTok, YouTube Shorts). It produces a luxury **bedroom** interior at night where the lighting illuminates **one fixture at a time** — Table Lamp first, then Ceiling Mounted, then Pendant Light, and finally all lights on together — before transitioning into the brand outro.

The pipeline replaces video generative models with **precise, high-control progressive Nano Banana Pro blends** and **local FFmpeg in-place crossfade dissolves**, guaranteeing zero morphing artifacts and a stationary camera where only the lighting realistically changes.

> **Visual aesthetic:** Warm contemporary bedroom lighting design — stationary cinematic perspective, warm ambient illumination switching progressively from fixture to fixture without jumpy slideshow effects.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Reel Duration**: Total ~11.0 seconds
  - **State 1 (`Converted Image1`)**: 2.0s hold — Table Lamp ON only (ceiling & pendant OFF, dark corners)
  - **State 2 (`Converted Image2`)**: 2.0s hold — Ceiling Mounted Light ON only (table & pendant OFF, dark corners)
  - **State 3 (`Converted Image3`)**: 2.0s hold — Pendant Light ON only (table & ceiling OFF, dark corners)
  - **State 4 (`Blended Image`)**: 2.0s hold — All 3 fixtures ON together (fully lit climax)
  - **State 5 (`Outro`)**: 2.5s hold — Branded HomeCartel Outro (`assets/outro_layout.jpg`)
  - **Transitions**: 0.8s smooth in-place crossfade dissolve (`xfade=transition=fade`) between consecutive states (NO black fade-in at the start, NO sliding photo cards).
- **Audio Profile**: Silent for now (background music disabled).

---

## 2. Model Stack Phase Table (6 phases)

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape (3 fresh fixtures)** | Akeneo PIM API | Active ingestion + strict Shopify Active & Published verification + base-wide dedup | Akeneo catalog: 1 Table Lamp, 1 Ceiling Mounted, 1 Pendant Light | Brand-new row, `Foreign Key ID`, `Scraped Item 1..3` -> Status: `In progress` |
| **Phase 2** | **Krea Bedroom Interior** | Krea AI | Krea moodboard ID (9:16, 1K)<br>Preset category Moodboard | Moodboard ID + Bedroom prompt | `Living Room Interior` |
| **Phase 3** | **Claude Sonnet 5 Blending Prompt** | Fal AI | `anthropic/claude-sonnet-5` (standard multi-fixture vision prompt) | 3 scraped items + `Living Room Interior` | `Blending Prompt` |
| **Phase 4** | **Nano Banana Pro Initial Blend** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: 9:16, Resolution: 1K | Interior + 3 scraped items + `Blending Prompt` | `Blended Image` (all 3 lights installed & lit) |
| **Phase 5** | **Progressive Lighting Variations** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: 9:16, Resolution: 1K | `Blended Image` + variation prompts | `Converted Image1` (Table Lamp ON)<br>`Converted Image2` (Ceiling ON)<br>`Converted Image3` (Pendant ON) |
| **Phase 6** | **FFmpeg In-Place Crossfade Mux** | Local FFmpeg | `imageio-ffmpeg` in-place `xfade` (0 API cost) | 3 Converted Images + `Blended Image` + `Outro` | `Final Video` -> Status: `Done` (C) + PHT timestamp |

---

## 3. Phase 3 & 5 Details — Multi-Fixture Placement & Lighting Variations

### Phase 3: Claude Sonnet 5 Prompt Engineering
Claude Sonnet 5 is given the room interior and the 3 scraped product photos (Table Lamp, Ceiling Mounted Light, Pendant Light). It uses the standardized vision prompt architecture (`build_multi_fixture_blending_instruction`) to generate a single cohesive prompt for Nano Banana Pro:
- Table Lamp placed naturally on the bedside nightstand.
- Ceiling Light mounted flush on the ceiling.
- Pendant Light hung gracefully from the ceiling.
- Clean removal of any pre-existing competing fixtures in the interior.

### Phase 5: Progressive Lighting Variations via Nano Banana Pro
All variations take the initial `Blended Image` as the base input photo:
1. **`Converted Image1`**:
   *"In this exact room, turn off the ceiling mounted light and pendant light completely. Make sure all room corners and the photo are dark, with only the bedside table lamp turned on, casting a warm golden glow onto the nightstand and nearby wall."*
2. **`Converted Image2`**:
   *"In this exact room, turn off the pendant light and table lamp completely. Make sure all room corners and the photo are dark, with only the ceiling mounted light turned on, casting an architectural ambient glow downward across the ceiling and room."*
3. **`Converted Image3`**:
   *"In this exact room, turn off the ceiling mounted light and table lamp completely. Make sure all room corners and the photo are dark, with only the pendant light turned on, casting a focused warm pool of light downward."*

---

## 4. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{OATL\text{-}REEL\text{-}LR\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `OATL` (One At a Time Lights)
- **Content Format**: `REEL`
- **Fixture Code**: `LR` (Living Room / Bedroom)

### Real-World Examples:
- `OATL-REEL-LR-1` (Row 1 of One at a time Lights)
- `OATL-REEL-LR-2` (Row 2 of One at a time Lights)

---

## 5. Supported Airtable Table & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- |
| **One at a time Lights** | `LR` | `tblJpEtBudQZda319` | `AIRTABLE_TABLE_ID_ONE_AT_A_TIME_LIGHTS` |

| Krea Moodboard | Environment Variable |
| :--- | :--- |
| Bedroom moodboard ID: `fb2487fb-2895-4d2c-9758-805aaf1bac69` | `KREA_MOODBOARD_ID_ONE_AT_A_TIME_LIGHTS` |
| Bedroom interior prompt: "Generate me a modern bedroom" | `PROMPT_ONE_AT_A_TIME_LIGHTS_REEL_INTERIOR` |

### Airtable Schema (`tblJpEtBudQZda319`)

| Field | Type |
| :--- | :--- |
| `Foreign Key ID` | singleLineText |
| `ID` | number |
| `Date and Time Generated` | dateTime |
| `Status` | singleSelect (`In progress` / `Done`) |
| `Scraped Items` | multilineText |
| `Scraped Item 1` | attachment (Table Lamp) |
| `Scraped Item 2` | attachment (Ceiling Mounted Light) |
| `Scraped Item 3` | attachment (Pendant Light) |
| `Living Room Interior` | attachment |
| `Blending Prompt` | multilineText |
| `Blended Image` | attachment (All 3 fixtures lit) |
| `Converted Image1` | attachment (Table Lamp ON only) |
| `Converted Image2` | attachment (Ceiling Mounted ON only) |
| `Converted Image3` | attachment (Pendant Light ON only) |
| `Outro` | attachment |
| `Final Video` | attachment |
