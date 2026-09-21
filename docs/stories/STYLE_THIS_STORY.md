# Style This Story Automation Pipeline

The **Style This Story Automation Pipeline** generates high-engagement interactive **9:16 vertical Instagram Stories (1080 x 1920 px)** for HomeCartel lighting collections. Each product generates a complete 4-card voting sequence: Card 1 invites users ("How would you style this? ft. [Item Name]"), while Cards 2 to 4 present distinct luxury interior stylings with dynamic color-coded reaction pills ("Double tap if you choose: [Vibe Name]").

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: 4-Card Story Sequence (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Card Composition**:
  - **Card 1 (`style_this01.jpg` / `how_would_you_style_this.jpg`)**: Blended room interior + Top-right logo + Centered headline `"How would you style this?"` & `"ft. [Item Name]"`.
  - **Cards 2–4 (`style_this02..04.jpg` / `double_tap_blended01..03.jpg`)**: 3 alternate interior styles + Top-right logo + Heart Emoji + Centered `"Double tap if you choose:"` + Dynamic color-matched capsule pill containing Claude-analyzed interior vibe name.

---

## 2. Model Stack Phase Table

| Phase       | Phase Name                                | Provider / Engine       | Model / Settings                                                                                                                                                                                                                           | Input Fields / Triggers                       | Output Fields / Status                                                                                            |
| :---------- | :---------------------------------------- | :---------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------- | :---------------------------------------------------------------------------------------------------------------- |
| **Phase 0** | **Akeneo Scraper (always brand-new row)** | Akeneo PIM API          | Active Ingestion (`enabled=true`) + strict Shopify-active check + cross-table dedup. Every run scrapes fresh products into a brand-new row; existing/pending rows are never re-processed (only an explicit `--record-id` may target a row) | Akeneo Catalog (`chandeliers`, `floor_lamps`) | `Furniture Item`, `Item Name`, `SKU` -> Status: `Pending` (`P`)                                                   |
| **Phase 1** | **Krea 4-Slot Interiors**                 | Krea AI                 | `krea-2-medium` (9:16, 1K)<br>Preset category Moodboard                                                                                                                                                                                    | 4 Category Room Prompts                       | `Interior`, `Interior2`, `Interior3`, `Interior4` -> Status: `Drafting` (`D`)                                     |
| **Phase 2** | **Claude Prompt Analysis**                | Fal AI / OpenRouter     | `anthropic/claude-sonnet-5`                                                                                                                                                                                                                | 4 Interiors + `Furniture Item`                | `Prompt`, `Prompt2`, `Prompt3`, `Prompt4` -> Status: `Drafting` (`D`)                                             |
| **Phase 3** | **Nano Banana Pro Blending**              | Fal AI                  | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K`                                                                                                                                                                    | 4 Interiors + `Furniture Item` + Prompts      | `Style This Blended` (4 images) -> Status: `Drafting` (`D`)                                                       |
| **Phase 4** | **Claude Vibe & Color Vision**            | Fal AI / OpenRouter     | `anthropic/claude-sonnet-5`                                                                                                                                                                                                                | `style_this02.jpg`, `03.jpg`, `04.jpg`        | Populates `Style This Text Generated[1-3]` & `Style This Auto Generated Color[1-3]`                               |
| **Phase 5** | **Local PIL Typography Engine**           | **Local Python Pillow** | **Zero-API Local Python Script**<br>Dynamic Pill & Typography                                                                                                                                                                              | `Style This Blended` + Vibe Fields + `Logo`   | Uploads 3 cards to `Double Tap Converted` & all 4 cards to `STORY - Style This? (4)` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{ST\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `ST` (Style This)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier), `FL` (Floor Lamp)

### Real-World Examples:
- `ST-STORY-CH-1` (Row 1 of Chandelier Style This Story)
- `ST-STORY-FL-6` (Row 6 of Floor Lamp Style This Story)
- `ST-STORY-CH-14` (Row 14 of Chandelier Style This Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblYge5R7LwTJkEHC` | `ST-STORY-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_STYLE_THIS_CHANDELIER` |
| **Floor Lamps** | `FL` | `tblvSAzXasTVI85r9` | `ST-STORY-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_STYLE_THIS_FLOOR_LAMPS` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting interior generation.
- **`Scheduled` (`S`)**: Queued for batch execution.
- **`Drafting` (`D`)**: Processing through Krea, Claude, or Fal.
- **`For Modification` (`FM`)**: Flagged for vibe color or typography re-rendering.
- **`Completed` (`C`)**: All 4 story cards stamped and attached to Airtable.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow Layout Specs

Phase 5 executes **Zero-API Local Python Pillow** typography & card composition (saving 100% of Nano Banana API costs for layout conversion):
- **Brand Logo Coordinates (`HOMECARTEL_STORY_LOGO_BOX`)**:
  - Width: `190.3 px`, Height: `63.5 px`
  - Position: `X=781.7 px`, `Y=108.0 px` (Stamped on all 4 slides)
- **Slide 1 Headline**:
  - Box: `X=87.7 px`, `Y=850.7 px`, `Width=904.7 px`, `Height=152.3 px`
  - Font: `Poppins-Light.ttf` (`44 px`, auto-scaling down to 24 px for long names)
  - Color: `#FFFFFF` with **NO shadow or outline**.
- **Slides 2–4 "Double Tap" Layout**:
  - Heart Emoji: `assets/Heaart Emoji.jpg` (`77.8 x 69.3 px`)
  - Headline: `Poppins-Bold.ttf` (`44 px`), centered horizontally with Heart Emoji.
  - Dynamic Capsule Pill:
    - Position: `Y=296.3 px` (below headline), centered horizontally.
    - Capsule radius: `89 px`, padding: `44 px`.
    - Background: Dynamic HEX color from `Style This Auto Generated Color[1-3]`.
    - Pill Text: `Poppins-Bold.ttf` (`44 px`), `#FFFFFF`, text from `Style This Text Generated[1-3]`.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive console menu
python "Style This Story/5_Interactive_Menu.py"
# or
python generate_style_this_story_pipeline.py --mode menu

# Run full pipeline for Floor Lamps (default tblvSAzXasTVI85r9)
python generate_style_this_story_pipeline.py --mode all

# Target Chandeliers table
python run_style_this_story.py --category chandeliers

# Run Phase 4 local Pillow assembly only
python generate_style_this_story_pipeline.py --mode conversion
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab.
4. Select **Style This Stories**.
5. Pick fixture category (**Floor Lamp** or **Chandelier**).
6. Select rows and trigger generation.
