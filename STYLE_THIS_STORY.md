# Style This Story Automation (9:16 Ratio)

End-to-end automated generation pipeline for **Style This Story** (1080 x 1920 px vertical Instagram Story).

---

## 🚀 Pipeline Workflow

| Phase | Action | Engine | Target Airtable Field | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 0** | Auto-Scrape Akeneo Floor Lamps | `AkeneoClient` | `Furniture Item`, `Item Name`, `SKU` | `Standby` |
| **Phase 1** | 9:16 Room Interiors (4 slots) | `KreaClient` | `Interior`, `Interior2`, `Interior3`, `Interior4` | `Processing Interior Generated Photo` |
| **Phase 2** | Vision Prompt Analysis | `FalClient` (Claude Sonnet 5) | `Prompt`, `Prompt2`, `Prompt3`, `Prompt4` | `Processing Blending Prompt` |
| **Phase 3** | 9:16 Image Blending (4 slots) | `FalClient` (Nano Banana Pro) | `Style This Blended` (`style_this01.jpg` .. `04.jpg`) | `Processing Day Image` |
| **Phase 4** | Story Cards Layout Stamping | **Local Python Pillow (Zero Nano Banana API Cost)** | `Double Tap Converted` (3 cards) & `STORY - Style This? (4)` (4 cards) | `Complete` |

---

## 📋 Style This Category Table IDs, Moodboards & Prompts

| Category | Airtable Table ID | Krea Moodboard ID | Krea Interior Prompt | Scraping Rules |
| :--- | :--- | :--- | :--- | :--- |
| **Floor Lamps** | `tblvSAzXasTVI85r9` | `b1641228-beec-4823-8d01-1de3eec8410d` | `"Generate me a modern bedroom that have beside a floor lamp"` | Active only, Newest $\rightarrow$ Oldest, Cross-table dedup |
| **Pendant Lights** | `tblWdz71nULR0TZx7` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `"Generate me a modern dining room"` | Active only, Newest $\rightarrow$ Oldest, Cross-table dedup |
| **Chandelier** | `tblp6AMYb13NPqkuT` | `fda7090c-787b-4116-94cd-3feef613eaaa` | `"Generate me a modern bedroom"` | **Skip Linear & Cluster Chandeliers**, Active only, Cross-table dedup |
| **Wall Lights** | `tblXJrvSBkJNhRHLa` | *(Default: Floor Lamp)* | `"Generate me a modern living room with a wall light"` | Active only, Newest $\rightarrow$ Oldest, Cross-table dedup |

---

## ➕ Add a New Table (No Code Changes — `.env` Only)

Each Style This table has its **own** Airtable Table ID, Krea Moodboard ID, and room-interior prompt. To register a **brand-new table**, just add a numbered block to your `.env` (N = 1, 2, 3, ...) — the pipeline auto-detects it on startup:

```dotenv
STYLE_THIS_CUSTOM_1_NAME=Table Lamps
STYLE_THIS_CUSTOM_1_TABLE_ID=tblXXXXXXXXXXXXXX
STYLE_THIS_CUSTOM_1_MOODBOARD_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
STYLE_THIS_CUSTOM_1_PROMPT=Generate me a modern living room with a table lamp
STYLE_THIS_CUSTOM_1_AKENEO_CATEGORY=table_lamps   # optional (scrape source; default floor_lamps)
```

| Field | Required? | Purpose |
| :--- | :--- | :--- |
| `..._NAME` | Recommended | Label shown in the menu; also becomes the `--category` slug (`Table Lamps` → `table_lamps`) |
| `..._TABLE_ID` | **Yes** | Airtable Table ID (`tbl...`) |
| `..._MOODBOARD_ID` | Optional | Krea Moodboard ID (defaults to the floor-lamp board) |
| `..._PROMPT` | Optional | Krea room-interior prompt for this table |
| `..._AKENEO_CATEGORY` | Optional | Which products to scrape (`floor_lamps`, `wall_lights`, `pendant_lights`, `chandeliers`, `table_lamps`, ...). Default: `floor_lamps` |
| `..._KEY` | Optional | Explicit `--category` slug override |

Then run it exactly like the built-in categories:

```bash
python run_style_this_story.py --category table_lamps
# or pick it from the numbered list:
python generate_style_this_story_pipeline.py --mode menu
# or bypass categories entirely with a raw table id:
python run_style_this_story.py --table-id tblXXXXXXXXXXXXXX
```

Add as many blocks as you need (`STYLE_THIS_CUSTOM_2_*`, `STYLE_THIS_CUSTOM_3_*`, ...). No Python edits required.

---

## 🎨 Exact Layout & Typography Specifications (1080 x 1920 Canvas)

### Slide 1: `style_this01.jpg` -> `how_would_you_style_this.jpg`
1. **HomeCartel Logo (Top-Right)**:
   - Position: `X=781.7`, `Y=108.0`, `Width=190.3`, `Height=63.5`, `Rotation=0°` (Auto-stamped on all slides)
2. **Centered Two-Line Headline**:
   - Content:
     - **Line 1**: `How would you style this?`
     - **Line 2**: `ft. [Item Name]` (auto-sourced from Airtable `"Item Name"`)
   - Bounding Box: `X=87.7`, `Y=850.7`, `Width=904.7`, `Height=152.3`, `Rotation=0°` (Center `X = 540.05`)
   - Font: `Poppins-Light.ttf` (Font size: **44px** non-bold with auto-scaling down to 24px for long product names)
   - Color: Clean Solid White `(255, 255, 255)` with **NO text shadow or outline**.

---

### Slide 2 (and 3, 4): `style_this02.jpg` .. `04.jpg` -> `double_tap_blended01.jpg` .. `03.jpg`
1. **HomeCartel Logo (Top-Right)**:
   - Position: `X=781.7`, `Y=108.0`, `Width=190.3`, `Height=63.5`, `Rotation=0°` (Auto-stamped on all slides)
2. **Heart Emoji Asset**:
   - Source: `assets/Heaart Emoji.jpg` (auto-transparent)
   - Size: `Width=77.8`, `Height=69.3`, `Rotation=0°`
   - Rendered as part of a **horizontally-centered group** together with the headline text (placed immediately to the left of the headline), sitting directly above the pill.
3. **Headline Text**:
   - Content: `Double tap if you choose:`
   - **Centered horizontally** as a group with the heart emoji, positioned directly above the color pill (24px gap).
   - Font: `Poppins-Bold.ttf` (Font size: **44px** **bold**), Clean Solid White with **NO text shadow or outline**.
4. **Dynamic Claude Room Vibe & Color Fields in Airtable**:
   - **Source Photos**: Sourced directly from `"Style This Blended"` attachment field (`style_this02.jpg`, `style_this03.jpg`, `style_this04.jpg`).
   - **Airtable Target Fields**:
     - `style_this02.jpg` -> Text: `"Style This Text Generated1"`, Color: `"Style This Auto Generated Color1"` -> `double_tap_blended01.jpg`
     - `style_this03.jpg` -> Text: `"Style This Text Generated2"`, Color: `"Style This Auto Generated Color2"` -> `double_tap_blended02.jpg`
     - `style_this04.jpg` -> Text: `"Style This Text Generated3"`, Color: `"Style This Auto Generated Color3"` -> `double_tap_blended03.jpg`
   - **Claude Vision JSON Output**:
     ```json
     {"vibe_name": "Warm Olive", "hex_color": "#adb481"}
     ```
   - **Text Inside Pill**: Dynamic 1-3 word room color/vibe name sourced from the corresponding `"Style This Text Generated[1-3]"` field in **Font Size 44** `Poppins-Light.ttf` (non-bold, Solid White `#FFFFFF`, no shadow).
   - **Dynamic Pill Shape** (Claude-generated text):
     - Auto-hugs text width + `44px` horizontal spread padding on each side.
     - Shape spec: `Width=606.4`, `Height=70.3`, `X=236.8`, `Y=1488`, `Rotation=0°`.
     - Anchored at `Y = 1488` and **centered horizontally** (`X = 236.8` for the reference `606.4px` width); the headline group sits directly above it.
     - Background Color: The exact HEX color saved in `"Style This Auto Generated Color[1-3]"` for that room photo.
     - Roundness: `89` (Smooth rounded capsule ends), Opacity `100%`.

---

## 🛠️ How to Run & Try

### 1. Preview Layouts Locally
```bash
# Preview using local sample images
python preview_style_this_overlay.py

# Preview with custom text and custom HEX color
python preview_style_this_overlay.py --text "Terracotta Warmth" --color "#c17c5f"

# Preview a specific Airtable Record ID (outputs to output/style_this_preview/)
python preview_style_this_overlay.py --record-id recFxXwIFimDuVQs9
```

### 2. Convert Existing Blended Rows in Airtable
```bash
# Convert all blended rows to Story Cards and upload directly to Airtable
python generate_style_this_story_pipeline.py --mode conversion

# Convert a specific Record ID
python generate_style_this_story_pipeline.py --mode conversion --record-id recFxXwIFimDuVQs9
```

### 3. Full End-to-End Pipeline
```bash
# Run next pending row end-to-end (Scrape -> Krea -> Claude -> Fal Blend -> Pillow Layout -> Complete)
python run_style_this_story.py

# Interactive Menu
python generate_style_this_story_pipeline.py --mode menu
```
