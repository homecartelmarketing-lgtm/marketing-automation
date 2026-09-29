# Ad Cover Automation Pipeline (1:1 + 9:16 Story)

The **Ad Cover Automation Pipeline** generates branded **1:1 square ad creatives (1080 x 1080 px)** plus a matching **9:16 Story twin (1080 x 1920 px)** for HomeCartel lighting collections and promotional campaigns. It scrapes the **active fixture** (or candidates from promotional inventory CSVs for sale/stock/new campaigns), generates a photorealistic 1:1 room interior with Krea AI, blends the product into the room with **Nano Banana Pro**, and then composites the pre-designed transparent 1:1 collection overlay (`assets/chand-collection.png` for Chandelier, `assets/trending.png` for Floor Lamp, `assets/table-lamps-collection.png` for Table Lamp, `assets/clsuter-collec.png` for Cluster Chandelier, `assets/pendant-light-collec.png` for Pendant Light, `assets/wall-collec.png` for Wall Light, `assets/new-collection.png` for New Collection, `assets/on-sale.png` for On Sale Designs, and `assets/on-stock-feed.png` for On Stock Designs, which already carry the collection banner and the HomeCartel® brand mark) **100% locally via Python Pillow** — zero API cost for typography. Phases 6-7 then re-extend that same blend to 9:16 and composite it over `assets/ad-cover-<fixture>-story.png` or dedicated campaign story overlays.

Unlike Story/Feed/Reel, Ad Covers is a **standalone 4th top-level Studio tab** rather than a sub-tab family: each fixture is its own card with live status badges, Row Inspector, and run button, producing **both** 1:1 and 9:16 formats.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1080 px` (Aspect Ratio `1:1`) and `1080 x 1920 px` (Aspect Ratio `9:16`, Story)
- **Format**: Single-Card Square Ad Cover + vertical Story card (`.jpg` / `.png`)
- **Color Profile**: sRGB, 8-bit truecolor
- **Card Composition**:
  - Full-bleed photorealistic room interior with the illuminated fixture blended in.
  - Transparent overlay layer carrying the HomeCartel® brand mark and the collection banner, alpha-composited on top.
- **Compositing rule**: the base room photo is **centre-cropped** to the target canvas before the overlay is applied, so the output is always a clean square / vertical frame regardless of the source geometry. This is why Phase 6 must return a genuine 9:16 image — if it returned a square, Phase 7 would chop off the left and right thirds of the room.

---

## 2. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scraper** | Akeneo PIM API + Inventory CSVs | `enabled=true` + strict Shopify "active & published" check + base-wide cross-table dedup<br>**Highest price within newest 50 candidates** (or randomized CSV campaign pool) | Akeneo Catalog / CSV exports | `Furniture Item`, `SKU`, `Item Name`, `Item Price` -> Status: `Standby` |
| **Phase 2** | **Krea Room Interior** | Krea AI | 1:1 interior (per-fixture moodboard) | Standby record + room prompt | `Ad Cover Interior` -> Status: `Ad Cover Interior Generated` |
| **Phase 3** | **Claude Vision Prompting** | Fal AI | `anthropic/claude-sonnet-5` | `Ad Cover Interior` + `Furniture Item` | `Prompt` -> Status: `Blending Prompt Generated` |
| **Phase 4** | **Nano Banana Pro Blending** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `1:1` | `Ad Cover Interior` + `Furniture Item` + `Prompt` | `Ad Cover Blended Image` -> Status: `Ad Cover Blended Image Generated` |
| **Phase 5** | **Local Ad Cover Composite (1:1)** | **Local Python Pillow** | **Zero-API Local Script**<br>`overlay.py::overlay_ad_cover_layout` | `Ad Cover Blended Image` + fixture 1:1 collection overlay (`assets/chand-collection.png`, `trending.png`, etc.) | `Ad Cover Converted Image` -> Status: `Ad Cover Converted Image Generated` |
| **Phase 6** | **Nano Banana Pro 9:16 Extension** | Fal AI | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K`<br>Model override: `FAL_STORY_MODEL` | `Ad Cover Blended Image` + dedicated outpaint prompt `FAL_STORY_CONVERSION_PROMPT` | `Ad Cover Blended Image Story` -> Status: `Ad Cover Blended Image Story Generated` |
| **Phase 7** | **Local Story Composite (9:16)** | **Local Python Pillow** | **Zero-API Local Script**<br>`overlay_ad_cover_layout(..., asset_name, canvas_size)` | `Ad Cover Blended Image Story` + Story overlay (`assets/ad-cover-<fixture>-story.png`) | `Ad Cover Converted Image Story` -> Status: `Complete` (`C`) + PHT timestamp |

> [!NOTE]
> There is deliberately **no Claude headline phase**. Both overlay assets already contain the tagline and logo, which keeps the flow to 7 phases and eliminates extra text-generation cost.

> [!IMPORTANT]
> **`Complete` is written by Phase 7 only.** `Status` is a `singleSelect`, so any later write overwrites the earlier one. If Phase 5 stamped `Complete`, Phase 6 would immediately replace it with `Ad Cover Blended Image Story Generated` and the row would drop out of the `C` badge mid-run — permanently, if the story branch then failed. A Phase 6/7 failure therefore re-asserts `Complete` (the 1:1 deliverable is already done) while the run still exits non-zero; retry with `--mode story-blend --record-id ...`.

---

## 3. Foreign Key ID Convention & Examples

Every Airtable record processed by this pipeline is assigned a permanent Foreign Key ID:

$$\text{Format: } \mathbf{ADC\text{-}ADS\text{-}\langle FIXTURE\rangle\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `ADC` (Ad Cover)
- **Content Format**: `ADS` (Ad Cover / Ads)
- **Fixture Codes**: `CH` (Chandelier), `FL` (Floor Lamp), `TL` (Table Lamp), `CL` (Cluster Chandelier), `PE` (Pendant Light), `WL` (Wall Light), `NEW` (New Collection), `SALE` (On Sale Designs), `STOCK` (On Stock Designs).

### Real-World Examples:
- `ADC-ADS-CH-1` (Row 1 of Chandelier Ad Covers)
- `ADC-ADS-FL-1` (Row 1 of Floor Lamp Ad Covers)
- `ADC-ADS-TL-1` (Row 1 of Table Lamp Ad Covers)
- `ADC-ADS-CL-1` (Row 1 of Cluster Chandelier Ad Covers)
- `ADC-ADS-PE-1` (Row 1 of Pendant Light Ad Covers)
- `ADC-ADS-WL-1` (Row 1 of Wall Light Ad Covers)
- `ADC-ADS-NEW-1` (Row 1 of New Collection Ad Covers)
- `ADC-ADS-SALE-1` (Row 1 of On Sale Designs Ad Covers)
- `ADC-ADS-STOCK-1` (Row 1 of On Stock Designs Ad Covers)

---

## 4. Supported Airtable Tables, Categories & Env Vars Map

| Fixture | Fixture Code | Airtable Table ID | Foreign Key Prefix | 1:1 Collection Overlay Asset | 9:16 Story Overlay Asset | Category Code | Environment Variables | Studio State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandelier** | `CH` | `tblwIsDGZBPuYJV2Z` | `ADC-ADS-CH` | `chand-collection.png` | `ad-cover-chandelier-story.png` | `chandelier_ad_cover` | `AIRTABLE_TABLE_ID_CHANDELIER_AD_COVER`<br>`KREA_MOODBOARD_ID_CHANDELIER_AD_COVER`<br>`AD_COVER_PROMPT_CHANDELIER` | **Runnable** |
| **Trending Lights** | `FL` | `tbl27FKuDUD4FdJUR` | `ADC-ADS-FL` | `trending.png` *(or `floor-lamp-collection.png`)* | `trending-lights-collection-story.png` | `floor_lamp_ad_cover` | `AIRTABLE_TABLE_ID_FLOOR_LAMP_AD_COVER`<br>`KREA_MOODBOARD_ID_FLOOR_LAMP_AD_COVER`<br>`AD_COVER_PROMPT_FLOOR_LAMP` | **Runnable** |
| **Table Lamp** | `TL` | `tblk3RfFqawHZ5Wrk` | `ADC-ADS-TL` | `table-lamps-collection.png` | `table-lamps-collection.story.png` | `table_lamp_ad_cover` | `AIRTABLE_TABLE_ID_TABLE_LAMP_AD_COVER`<br>`KREA_MOODBOARD_ID_TABLE_LAMP_AD_COVER`<br>`AD_COVER_PROMPT_TABLE_LAMP` | **Runnable** |
| **Cluster Chandelier** | `CL` | `tbltouegkjgQwdr1u` | `ADC-ADS-CL` | `clsuter-collec.png` | `cluster-chandelier-collection-story.png` | `cluster_chandelier_ad_cover` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_AD_COVER`<br>`KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_AD_COVER`<br>`AD_COVER_PROMPT_CLUSTER_CHANDELIER` | **Runnable** |
| **Pendant Light** | `PE` | `tbl99Cwda2Xn93giT` | `ADC-ADS-PE` | `pendant-light-collec.png` | `pendant-light-collect-story.png` | `pendant_ad_cover` | `AIRTABLE_TABLE_ID_PENDANT_AD_COVER`<br>`KREA_MOODBOARD_ID_PENDANT_AD_COVER`<br>`AD_COVER_PROMPT_PENDANT` | **Runnable** |
| **Wall Light** | `WL` | `tblUO5nybG9fIkhTT` | `ADC-ADS-WL` | `wall-collec.png` | *(fallback)* | `wall_light_ad_cover` | `AIRTABLE_TABLE_ID_WALL_LIGHT_AD_COVER`<br>`KREA_MOODBOARD_ID_WALL_LIGHT_AD_COVER`<br>`AD_COVER_PROMPT_WALL_LIGHT` | **Runnable** |
| **New Collection** | `NEW` | `tbluMexgzcWE1pDZJ` | `ADC-ADS-NEW` | `new-collection.png` | `new-collection-story.png` | `new_collection_ad_cover` | `AIRTABLE_TABLE_ID_NEW_COLLECTION_AD_COVER`<br>`KREA_MOODBOARD_ID_NEW_COLLECTION_AD_COVER`<br>`AD_COVER_PROMPT_NEW_COLLECTION` | **Runnable** |
| **On Sale Designs** | `SALE` | `tbleQIVBooVazAyk3` | `ADC-ADS-SALE` | `on-sale.png` | `on-sale-story-collection.png` | `on_sale_ad_cover` | `AIRTABLE_TABLE_ID_ON_SALE_AD_COVER`<br>`KREA_MOODBOARD_ID_ON_SALE_AD_COVER`<br>`AD_COVER_PROMPT_ON_SALE` | **Runnable** |
| **On Stock Designs** | `STOCK` | `tblX7tpTJhfH0UXmm` | `ADC-ADS-STOCK` | `on-stock-feed.png` | `on-stock-collection-story.png` | `on_stock_ad_cover` | `AIRTABLE_TABLE_ID_ON_STOCK_AD_COVER`<br>`KREA_MOODBOARD_ID_ON_STOCK_AD_COVER`<br>`AD_COVER_PROMPT_ON_STOCK` | **Runnable** |

Default env values (`.env` / `.env.example`):

```ini
# Chandelier
AIRTABLE_TABLE_ID_CHANDELIER_AD_COVER=tblwIsDGZBPuYJV2Z
KREA_MOODBOARD_ID_CHANDELIER_AD_COVER=de6ad512-870d-4ab7-a48c-3f3ca85faf24
AD_COVER_PROMPT_CHANDELIER=Generate me a modern living room

# Floor Lamp
AIRTABLE_TABLE_ID_FLOOR_LAMP_AD_COVER=tbl27FKuDUD4FdJUR
KREA_MOODBOARD_ID_FLOOR_LAMP_AD_COVER=c4c15a18-a92d-4465-924f-c85cfe1958bc
AD_COVER_PROMPT_FLOOR_LAMP=Generate me a modern living room with a standing floor lamp beside a sofa or lounge chair

# Table Lamp
AIRTABLE_TABLE_ID_TABLE_LAMP_AD_COVER=tblk3RfFqawHZ5Wrk
KREA_MOODBOARD_ID_TABLE_LAMP_AD_COVER=257569e1-7be8-4412-a90f-acbc347e4646
AD_COVER_PROMPT_TABLE_LAMP=Generate me a modern luxury bedroom bedside table or console with a table lamp

# Cluster Chandelier
AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_AD_COVER=tbltouegkjgQwdr1u
KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_AD_COVER=b5ffdcbb-192e-4528-8d86-d1a4cf496887
AD_COVER_PROMPT_CLUSTER_CHANDELIER=Generate me a luxury modern room with high ceiling featuring a cluster chandelier

# Pendant Light
AIRTABLE_TABLE_ID_PENDANT_AD_COVER=tbl99Cwda2Xn93giT
KREA_MOODBOARD_ID_PENDANT_AD_COVER=0844ad92-c34a-4dc8-9d70-d09498dc098c
AD_COVER_PROMPT_PENDANT=Generate me a modern luxury dining room with hanging pendant light

# Wall Light
AIRTABLE_TABLE_ID_WALL_LIGHT_AD_COVER=tblUO5nybG9fIkhTT
KREA_MOODBOARD_ID_WALL_LIGHT_AD_COVER=20c3beaf-0995-44bf-a7a3-ac790fe8f315
AD_COVER_PROMPT_WALL_LIGHT=Generate me a modern luxury living room with wall sconce mounted on the wall

# New Collection
AIRTABLE_TABLE_ID_NEW_COLLECTION_AD_COVER=tbluMexgzcWE1pDZJ
KREA_MOODBOARD_ID_NEW_COLLECTION_AD_COVER=de6ad512-870d-4ab7-a48c-3f3ca85faf24
AD_COVER_PROMPT_NEW_COLLECTION=Generate me a modern luxury living room

# On Sale Designs
AIRTABLE_TABLE_ID_ON_SALE_AD_COVER=tbleQIVBooVazAyk3
KREA_MOODBOARD_ID_ON_SALE_AD_COVER=de6ad512-870d-4ab7-a48c-3f3ca85faf24
AD_COVER_PROMPT_ON_SALE=Generate me a modern luxury living room with chandelier

# On Stock Designs
AIRTABLE_TABLE_ID_ON_STOCK_AD_COVER=tblX7tpTJhfH0UXmm
KREA_MOODBOARD_ID_ON_STOCK_AD_COVER=de6ad512-870d-4ab7-a48c-3f3ca85faf24
AD_COVER_PROMPT_ON_STOCK=Generate me a modern interior with ambient lighting
```
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
| `Ad Cover Blended Image Story` | `multipleAttachments` (Phase 6, 9:16) |
| `Ad Cover Converted Image Story` | `multipleAttachments` (Phase 7, 9:16 final deliverable) |
| `Furniture Item` / `SKU` / `Item Name` | product slot 1 (`items_per_row=1`) |
| `Status` | `singleSelect` (options below) |

Run `python scratch/ensure_ad_cover_fields.py --table-id tblwIsDGZBPuYJV2Z` to provision the two story columns and the 8 `Status` choices idempotently; the helper and the two read-only verifiers are catalogued in [`../OPERATIONS_AND_UTILITIES.md`](../OPERATIONS_AND_UTILITIES.md). Provisioning must precede the first story-branch run — Phase 6 cannot upload into a column that does not exist.

> [!NOTE]
> The Zoho asset-folder interceptor in `content_automation/scraping/airtable.py` files any field whose name contains "converted" as a **final deliverable** and skips "blended"/"interior" fields. `Ad Cover Converted Image Story` therefore mirrors to Zoho like the square cover; `Ad Cover Blended Image Story` stays Airtable-only.

---

## 5. Status Lifecycle & PHT Timestamps

Ad Covers uses a dedicated phase-progress vocabulary in addition to the standard 5-badge UI mapping:

```
[ Standby ] ──► [ Ad Cover Interior Generated ] ──► [ Blending Prompt Generated ]
    ──► [ Ad Cover Blended Image Generated ] ──► [ Ad Cover Converted Image Generated ]
    ──► [ Ad Cover Blended Image Story Generated ] ──► [ Ad Cover Converted Image Story Generated ]
    ──► [ Complete ]
```

- **`Standby`**: Brand-new scraped row awaiting interior generation.
- **`Ad Cover Interior Generated`**: 1:1 Krea interior attached.
- **`Blending Prompt Generated`**: Claude blending prompt written to `Prompt`.
- **`Ad Cover Blended Image Generated`**: Nano Banana Pro 1:1 blend attached.
- **`Ad Cover Converted Image Generated`**: Local Pillow 1:1 composite produced.
- **`Ad Cover Blended Image Story Generated`**: Nano Banana Pro 9:16 extension attached.
- **`Ad Cover Converted Image Story Generated`**: Local Pillow 9:16 composite produced.
- **`Complete` (`C`)**: Both deliverables attached — written **only** by Phase 7 (or re-asserted by the failure fallback when the story branch fails after the 1:1 cover is done).

### Execution Timestamp
On completion the pipeline writes Philippine Standard Time (UTC+8) into `Date and Time Generated`:

```
2026-09-09T12:30:00+08:00
```

---

## 6. Local Pillow Composite Specs

Phase 5 (1:1) and Phase 7 (9:16 Story) are both **Zero-API Local Python Pillow** and live in `content_automation/overlay.py`:

- **Square asset registry**: `AD_COVER_FIXTURE_ASSETS` maps each fixture to its 1:1 collection overlay PNG:
  - `chandelier`: `chand-collection.png`
  - `floor-lamp`: `trending.png` *(dynamically falls back to `floor-lamp-collection.png` if uploaded to `assets/`)*
  - `table-lamp`: `table-lamps-collection.png`
  - `cluster-chandelier`: `clsuter-collec.png`
  - `pendant`: `pendant-light-collec.png`
  - `wall-light`: `wall-collec.png`
- **Story asset registry**: `AD_COVER_STORY_ASSETS = {"chandelier": "ad-cover-chandelier-story.png", ...}` — deliberately a *separate* dict so a fixture without a story PNG can never fall back onto the square overlay and get stretched across a 1080x1920 canvas. The pipeline reads it as `cfg["story_asset"]`; when that key is empty Phases 6-7 print a `[WARN] ... skipping` and the run continues (a skip is not a failure).
- **Canvas**: `AD_COVER_CANVAS_SIZE = (1080, 1080)` and `AD_COVER_STORY_CANVAS_SIZE = (1080, 1920)`.
- **Function**: `overlay_ad_cover_layout(base_image, fixture="chandelier", destination=None, *, asset_name=None, canvas_size=AD_COVER_CANVAS_SIZE)`.
  1. Resolves the overlay via the shared `_resolve_asset_file` lookup (searches the known asset directories).
  2. Centre-crops the base room photo to `canvas_size` (`ImageOps.fit(..., centering=(0.5, 0.5))`).
  3. Alpha-composites the RGBA overlay on top and returns a `Path` (when `destination` is given) or an in-memory RGB `Image`.
  - The Story phase passes both kwargs explicitly: `asset_name=cfg["story_asset"], canvas_size=cfg["story_canvas_size"]`.
- **No API call is ever made for Ad Cover typography** — the collection banner and the brand mark are baked into the overlay PNGs.

---

## 7. CLI & Web UI Execution Commands

### CLI Execution

```powershell
# Full 7-phase run for Chandelier — produces the 1:1 cover AND the 9:16 Story twin
python generate_ad_cover_pipeline.py --fixture chandelier --mode all --max-items 1

# Single phase
python generate_ad_cover_pipeline.py --fixture chandelier --mode scrape
python generate_ad_cover_pipeline.py --fixture chandelier --mode interior
python generate_ad_cover_pipeline.py --fixture chandelier --mode prompt
python generate_ad_cover_pipeline.py --fixture chandelier --mode blend
python generate_ad_cover_pipeline.py --fixture chandelier --mode conversion
python generate_ad_cover_pipeline.py --fixture chandelier --mode story-blend
python generate_ad_cover_pipeline.py --fixture chandelier --mode story-conversion

# Explicit table / moodboard / prompt overrides
python generate_ad_cover_pipeline.py --fixture chandelier --mode all --max-items 1 `
  --table-id tblwIsDGZBPuYJV2Z `
  --moodboard-id de6ad512-870d-4ab7-a48c-3f3ca85faf24 `
  --prompt "Generate me a modern living room"

# Re-render one exact existing record (the only allowed non-fresh path)
python generate_ad_cover_pipeline.py --fixture chandelier --mode conversion --record-id recXXXXXXXXXXXXXX

# Cheapest recovery after a story-branch failure: re-run only the 9:16 phases on that row
python generate_ad_cover_pipeline.py --fixture chandelier --mode story-blend --record-id recXXXXXXXXXXXXXX
python generate_ad_cover_pipeline.py --fixture chandelier --mode story-conversion --record-id recXXXXXXXXXXXXXX
```

| Flag | Description |
| :--- | :--- |
| `--fixture` | Ad Cover fixture (default `chandelier`) |
| `--mode` / `-m` | `scrape` \| `interior` \| `prompt` \| `blend` \| `conversion` \| `story-blend` \| `story-conversion` \| `all` |
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
4. Click **Run** on any of the 9 fixture cards (**Chandelier**, **Floor Lamp** (shown as *Trending Lights*), **Table Lamp**, **Cluster Chandelier**, **Pendant Light**, **Wall Light**, **New Collection**, **On Sale Designs**, **On Stock Designs**). Each card has its own dedicated Airtable table, live 5-badge status pills, and interactive prompt/moodboard editor pencils. The progress bar runs to **7/7** and the run consumes 1 Krea call + 2 Fal calls (Phase 4 blend, Phase 6 story extension); the local composites are free.
5. Use the MB / Prompt pencils on the card to override the Krea moodboard or interior prompt (persisted to `.env` via `output/config_overrides.json`); the 5 status pills (`P, S, C, D, FM`) and Rows count stay live. Those pencils reach Phases 1–2 only — the Phase 6 9:16 extension prompt is environment-only (`AD_COVER_STORY_CONVERSION_PROMPT`), as mapped in [`../UI_CONTROL_CONFIG.md`](../UI_CONTROL_CONFIG.md).

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
