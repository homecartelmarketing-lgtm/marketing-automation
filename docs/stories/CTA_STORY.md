# CTA Story Automation Pipeline

The **CTA Story Automation Pipeline** generates branded **9:16 vertical Instagram Stories (1080 x 1920 px)** for HomeCartel lighting collections. It combines a photorealistic AI room interior, seamless lighting fixture blending, Claude-analyzed luxury copy saved in `Word Generated`, and local Python Pillow stamping of the **HomeCartel brand logo** and **Canva CTA text layout**.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Format**: Single-Card Vertical Story (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Card Composition**:
  - Top-Right: Official HomeCartel® brand mark (`190.3 x 63.5 px` at `X=781.7`, `Y=108.0`).
  - Center: Photorealistic architectural living space featuring the illuminated lighting fixture.
  - Lower Third: Right-aligned typography card (`820.8 x 304.6 px` at `X=151.2`, `Y=1521.8`) with Claude-generated luxury headline, follow callout, and sales contact details.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scraper** | Akeneo PIM API | Active Ingestion (`enabled=true`) + cross-table dedup | Akeneo Catalog (`chandeliers`, `pendants`, etc.) | `Furniture Item`, `SKU`, `Item Name` -> Status: `Pending` (`P`) |
| **Phase 2** | **Krea Room Interior** | Krea AI | `krea-2-medium` (9:16, 1K)<br>Preset category Moodboard ID | Standby record + Room Prompt | `CTA Interior` -> Status: `Drafting` (`D`) |
| **Phase 3** | **Claude Vision Prompting** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `CTA Interior` + `Furniture Item` | `Blending Prompt` -> Status: `Drafting` (`D`) |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `CTA Interior` + `Furniture Item` + `Blending Prompt` | `CTA Blended Image` -> Status: `Drafting` (`D`) |
| **Phase 5** | **Claude Headline Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `CTA Blended Image` | `Word Generated` -> Status: `Drafting` (`D`) |
| **Phase 6** | **Local Logo & CTA Stamping** | **Local Python Pillow** | **Zero-API Local Python Script**<br>Canva Layout Box: $820.8 \times 304.6\text{ px}$ | `CTA Blended Image` + `Word Generated` + `Logo` | `CTA Converted Image` -> Status: `Completed` (`C`) |

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{CTA\text{-}STORY\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `CTA` (Call To Action)
- **Content Format**: `STORY`
- **Fixture Codes**: `CH` (Chandelier), `PE` (Pendant Light), `CL` (Cluster Chandelier), `TL` (Table Lamp), `FL` (Floor Lamp)

### Real-World Examples:
- `CTA-STORY-CH-1` (Row 1 of Chandelier CTA Story)
- `CTA-STORY-PE-3` (Row 3 of Pendant Lights CTA Story)
- `CTA-STORY-CL-7` (Row 7 of Cluster Chandelier CTA Story)
- `CTA-STORY-TL-2` (Row 2 of Table Lamp CTA Story)
- `CTA-STORY-FL-9` (Row 9 of Floor Lamp CTA Story)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Foreign Key Prefix | Default Krea Moodboard ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandeliers** | `CH` | `tblYHdVq14FjMWg5o` | `CTA-STORY-CH` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | `AIRTABLE_TABLE_ID_CHANDELIER_CTA` |
| **Pendant Lights** | `PE` | `tblfl7fqFZa2vUieB` | `CTA-STORY-PE` | `0844ad92-c34a-4dc8-9d70-d09498dc098c` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_CTA` |
| **Cluster Chandeliers** | `CL` | `tblSpGJLO3faYfIDY` | `CTA-STORY-CL` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_CTA` |
| **Table Lamps** | `TL` | `tblKJeCCp4zQ6g7Em` | `CTA-STORY-TL` | `257569e1-7be8-4412-a90f-acbc347e4646` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_CTA` |
| **Floor Lamps** | `FL` | `tblPKSYyjgbgMypE2` | `CTA-STORY-FL` | `c4c15a18-a92d-4465-924f-c85cfe1958bc` | `AIRTABLE_TABLE_ID_FLOOR_LAMP_CTA` |

---

## 5. 5-Status Lifecycle & PHT Timestamps

```
[ P ] Pending  ──►  [ S ] Scheduled  ──►  [ D ] Drafting  ──►  [ FM ] For Modification  ──►  [ C ] Completed
```

- **`Pending` (`P`)**: Scraped product awaiting interior generation.
- **`Scheduled` (`S`)**: Queued for batch generation.
- **`Drafting` (`D`)**: Processing through Krea, Claude, or Fal AI.
- **`For Modification` (`FM`)**: Flagged for headline revision or room re-rendering.
- **`Completed` (`C`)**: Blended image generated, copy analyzed, stamped, and attached.

### Execution Timestamp
Pipeline execution automatically writes the Philippine Standard Time timestamp (UTC+8) into the `Date & Time Run (PHT)` field:
```
2026-09-07T13:12:00+08:00
```

---

## 6. Local Pillow Layout Specs

Phase 6 executes **Zero-API Local Python Pillow** typography & logo composition:
- **Brand Logo Coordinates (`HOMECARTEL_LOGO_BOX`)**:
  - Width: `190.3 px`, Height: `63.5 px`
  - Position: `X=781.7 px`, `Y=108.0 px` (Exact 108 px top & right margins)
- **Canva CTA Text Watermark Box**:
  - Width: `820.8 px`, Height: `304.6 px`
  - Position: `X=151.2 px`, `Y=1521.8 px` (Right-aligned to `X=972.0 px`)
- **Typography**:
  - Headline: `Poppins-Bold.ttf` (`48 px`, auto-scaling down to 24 px if title overflows).
  - Follow Copy: `Poppins-Bold.ttf` (`28 px`):
    ```text
    Follow @HomeCartel for
    more home inspiration.
    ```
  - Contact Details: `Poppins-Regular.ttf` (`28 px`):
    ```text
    0977 825 5588 (or send us a DM)
    (02) 8248 8071 | Dial 1
    sales@homecartel.com
    ```
  - Drop Shadow: Soft Gaussian shadow `(0, 0, 0, 180)` for maximum legibility.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution via PowerShell

```powershell
# Interactive category menu
python generate_cta_story_pipeline.py --mode menu

# Run full pipeline for Chandeliers (default tblYHdVq14FjMWg5o)
python generate_cta_story_pipeline.py --mode all

# Target specific category
python generate_cta_story_pipeline.py --mode all --category pendant_lights_cta_story

# Multi-table round-robin runner
python run_cta_round_robin.py --menu
```

### Web UI Dashboard Execution
1. Open `http://localhost:5200`
2. Enter PIN: `1234`
3. Click the **Story** tab in the main navigation.
4. Select **CTA Stories**.
5. Pick fixture category (**Chandelier**, **Pendant**, **Cluster**, **Table Lamp**, or **Floor Lamp**).
6. Select rows and trigger generation.
