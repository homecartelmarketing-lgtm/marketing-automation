# Ad Cover Automation Pipeline (1:1)

The **Ad Cover Automation Pipeline** generates branded **1:1 square ad creatives (1080 x 1080 px)** for HomeCartel lighting collections. It scrapes the **highest-priced active fixture** out of the newest Akeneo candidates, generates a photorealistic 1:1 room interior with Krea AI, blends the product into the room with **Nano Banana Pro**, and then composites the pre-designed transparent ad-cover overlay (`assets/ad-covers-chandelier.png`, which already carries the tagline *"Illuminate your elegance."* and the HomeCartel® brand mark) **100% locally via Python Pillow** — zero API cost for typography.

Unlike Story/Feed/Reel, Ad Covers is a **standalone 4th top-level Studio tab** rather than a sub-tab family: each fixture is its own run button.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1080 px` (Aspect Ratio `1:1`)
- **Format**: Single-Card Square Ad Cover (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Card Composition**:
  - Full-bleed photorealistic room interior with the illuminated fixture blended in.
  - Transparent overlay layer carrying the HomeCartel® brand mark and the tagline, alpha-composited on top.
- **Compositing rule**: the base room photo is **centre-cropped** to `1080 x 1080` before the overlay is applied, so the output is always a clean square regardless of the Krea source geometry.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scraper** | Akeneo PIM API | `enabled=true` + strict Shopify "active & published" check + base-wide cross-table dedup<br>**Highest price within the newest 50 candidates** | Akeneo Catalog (`chandeliers`) | `Furniture Item`, `SKU`, `Item Name`, `Item Price` -> Status: `Standby` |
| **Phase 2** | **Krea Room Interior** | Krea AI | 1:1 interior, moodboard `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | Standby record + room prompt | `Ad Cover Interior` -> Status: `Ad Cover Interior Generated` |
| **Phase 3** | **Claude Vision Prompting** | Fal AI | `anthropic/claude-sonnet-5` | `Ad Cover Interior` + `Furniture Item` | `Prompt` -> Status: `Blending Prompt Generated` |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `1:1` | `Ad Cover Interior` + `Furniture Item` + `Prompt` | `Ad Cover Blended Image` -> Status: `Ad Cover Blended Image Generated` |
| **Phase 5** | **Local Ad Cover Composite** | **Local Python Pillow** | **Zero-API Local Script**<br>`overlay.py::overlay_ad_cover_layout` | `Ad Cover Blended Image` + `assets/ad-covers-chandelier.png` | `Ad Cover Converted Image` -> Status: `Complete` (`C`) + PHT timestamp |

> [!NOTE]
> There is deliberately **no Claude headline phase**. The overlay asset already contains the tagline and logo, which keeps the flow to 5 phases and eliminates extra text-generation cost.

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{ADC\text{-}ADS\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `ADC` (Ad Cover)
- **Content Format**: `ADS` (Ad Cover / Ads)
- **Fixture Codes**: `CH` (Chandelier) — the only wired fixture today; `PE`, `FL`, `TL`, `CL`, `WL` are scaffolded for future rollout.

### Real-World Examples:
- `ADC-ADS-CH-1` (Row 1 of Chandelier Ad Covers)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Fixture | Fixture Code | Airtable Table ID | Foreign Key Prefix | Category Code | Environment Variables | Studio State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandelier** | `CH` | `tblwIsDGZBPuYJV2Z` | `ADC-ADS-CH` | `chandelier_ad_cover` | `AIRTABLE_TABLE_ID_CHANDELIER_AD_COVER`<br>`KREA_MOODBOARD_ID_CHANDELIER_AD_COVER`<br>`AD_COVER_PROMPT_CHANDELIER` | **Runnable** |
| Pendant Light | `PE` | — | `ADC-ADS-PE` (reserved) | — | — | Coming soon |
| Floor Lamp | `FL` | — | `ADC-ADS-FL` (reserved) | — | — | Coming soon |
| Table Lamp | `TL` | — | `ADC-ADS-TL` (reserved) | — | — | Coming soon |
| Cluster Chandelier | `CL` | — | `ADC-ADS-CL` (reserved) | — | — | Coming soon |
| Wall Light | `WL` | — | `ADC-ADS-WL` (reserved) | — | — | Coming soon |

Default env values (`.env` / `.env.example`):

```ini
AIRTABLE_TABLE_ID_CHANDELIER_AD_COVER=tblwIsDGZBPuYJV2Z
KREA_MOODBOARD_ID_CHANDELIER_AD_COVER=de6ad512-870d-4ab7-a48c-3f3ca85faf24
AD_COVER_PROMPT_CHANDELIER=Generate me a modern living room
```

**Scrape category behaviour** (`content_automation/scraping/categories.py`):

- `source: "chandeliers"`, `items_per_row: 1`
- Style filter defaults to `AKENEO_STYLE` (`modern`)
- `sort_by_price_in_newest_pool: True`, `price_pool_size: 50` — the pick is the **most expensive item within the newest 50 candidates**, not the global maximum, so the selection stays fresh
- Cluster and linear chandeliers remain excluded (`cluster_chandeliers`, `linear_chandeliers`)

**Provisioned Airtable fields** (auto-created by `ensure_ad_cover_fields`):

| Field | Type |
| :--- | :--- |
| `Foreign Key ID` | `singleLineText` |
| `Date and Time Generated` | `dateTime` |
| `Moodboard ID` | `singleLineText` |
| `Prompt` | `multilineText` |
| `Item Price` | `number` |
| `Ad Cover Interior` | `multipleAttachments` |
| `Ad Cover Blended Image` | `multipleAttachments` |
| `Ad Cover Converted Image` | `multipleAttachments` |
| `Furniture Item` / `SKU` / `Item Name` | product slot 1 (`items_per_row=1`) |
| `Status` | `singleSelect` (options below) |

---

## 5. Status Lifecycle & PHT Timestamps

Ad Covers uses a dedicated phase-progress vocabulary in addition to the standard 5-badge UI mapping:

```
[ Standby ] ──► [ Ad Cover Interior Generated ] ──► [ Blending Prompt Generated ]
    ──► [ Ad Cover Blended Image Generated ] ──► [ Ad Cover Converted Image Generated ]
    ──► [ Complete ]
```

- **`Standby`**: Brand-new scraped row awaiting interior generation.
- **`Ad Cover Interior Generated`**: 1:1 Krea interior attached.
- **`Blending Prompt Generated`**: Claude blending prompt written to `Prompt`.
- **`Ad Cover Blended Image Generated`**: Nano Banana Pro blend attached.
- **`Ad Cover Converted Image Generated`**: Local Pillow composite produced.
- **`Complete` (`C`)**: Final 1:1 ad cover attached and PHT-stamped.

### Execution Timestamp
On completion the pipeline writes Philippine Standard Time (UTC+8) into `Date and Time Generated`:

```
2026-09-09T12:30:00+08:00
```

---

## 6. Local Pillow Composite Specs

Phase 5 is **Zero-API Local Python Pillow** and lives in `content_automation/overlay.py`:

- **Asset registry**: `AD_COVER_FIXTURE_ASSETS = {"chandelier": "ad-covers-chandelier.png"}` (append future fixtures here).
- **Canvas**: `AD_COVER_CANVAS_SIZE = (1080, 1080)`.
- **Function**: `overlay_ad_cover_layout(base_image, fixture="chandelier", destination=None, *, asset_name=None, canvas_size=AD_COVER_CANVAS_SIZE)`.
  1. Resolves the overlay via the shared `_resolve_asset_file` lookup (searches the known asset directories).
  2. Centre-crops the base room photo to `canvas_size`.
  3. Alpha-composites the RGBA overlay on top and returns a `Path` (when `destination` is given) or an in-memory RGB `Image`.
- **No API call is ever made for Ad Cover typography** — the tagline *"Illuminate your elegance."* and the brand mark are baked into the overlay PNG.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution

```powershell
# Full 5-phase run for Chandelier (default table tblwIsDGZBPuYJV2Z)
python generate_ad_cover_pipeline.py --fixture chandelier --mode all --max-items 1

# Single phase
python generate_ad_cover_pipeline.py --fixture chandelier --mode scrape
python generate_ad_cover_pipeline.py --fixture chandelier --mode interior
python generate_ad_cover_pipeline.py --fixture chandelier --mode prompt
python generate_ad_cover_pipeline.py --fixture chandelier --mode blend
python generate_ad_cover_pipeline.py --fixture chandelier --mode conversion

# Explicit table / moodboard / prompt overrides
python generate_ad_cover_pipeline.py --fixture chandelier --mode all --max-items 1 `
  --table-id tblwIsDGZBPuYJV2Z `
  --moodboard-id de6ad512-870d-4ab7-a48c-3f3ca85faf24 `
  --prompt "Generate me a modern living room"

# Re-render one exact existing record (the only allowed non-fresh path)
python generate_ad_cover_pipeline.py --fixture chandelier --mode conversion --record-id recXXXXXXXXXXXXXX
```

| Flag | Description |
| :--- | :--- |
| `--fixture` | Ad Cover fixture (default `chandelier`) |
| `--mode` / `-m` | `scrape` \| `interior` \| `prompt` \| `blend` \| `conversion` \| `all` |
| `--table-id` | Override the Airtable destination table |
| `--max-items` | Number of brand-new rows to generate (default `1`) |
| `--moodboard-id` | Override the Krea moodboard ID |
| `--prompt` / `-p` | Override the Krea interior prompt |
| `--style` / `-s` | Akeneo style filter (default `AKENEO_STYLE` or `modern`) |
| `--record-id` | Re-render one exact Airtable record instead of scraping |

> [!IMPORTANT]
> Per the repository-wide scraping rule, every default run scrapes **fresh active products into a brand-new row** and processes it end-to-end. Existing/incomplete rows are never scanned or resumed — `--record-id` is the only explicit exception.

### Web UI Dashboard Execution

1. Open `http://localhost:5200` (or the Cloudflare tunnel URL).
2. Enter the Studio PIN if `DASHBOARD_PIN` is configured.
3. Click the **Ad Covers** tab (4th top-level tab, next to Feed / Story / Reel).
4. Click **Run** on the **Chandelier** card. The other 5 fixtures render as disabled **Coming soon** cards.
5. Use the MB / Prompt pencils on the card to override the Krea moodboard or interior prompt (persisted to `.env` via `output/config_overrides.json`); the 5 status pills (`P, S, C, D, FM`) and Rows count stay live.

### API Endpoints (`UI Control/routes/ad_cover.py`)

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/ad-cover/counts` | Live 5-badge breakdown per fixture (10s cache; `?refresh=true` bypasses) |
| `GET` | `/api/ad-cover/status` | Live phase, elapsed time, and streaming stdout logs |
| `POST` | `/api/ad-cover/run` | Spawn `generate_ad_cover_pipeline.py` for one fixture (PIN-guarded) |
| `POST` | `/api/ad-cover/stop` | Terminate the running subprocess (PIN-guarded) |
| `POST` | `/api/ad-cover/moodboard` | Persist a moodboard override (PIN-guarded) |
| `POST` | `/api/ad-cover/prompt` | Persist a prompt override (PIN-guarded) |

Studio runs are serialized through the shared FIFO queue (`/api/queue/*`), so an Ad Cover run will wait for any other active pipeline and vice versa.
