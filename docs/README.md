# HomeCartel Marketing Automation — Documentation Hub

Welcome to the centralized documentation hub for the HomeCartel Marketing AI Content Automation platform.

> 📘 **Master Agent Protocol**: For core operating rules, zero-API Pillow layout rules, active scraping deduplication, and developer guides, consult the master rulebook at [`../AGENTS.md`](../AGENTS.md).  
> 🌐 **Workspace Overview**: For high-level system architecture and dashboard setup, see [`../README.md`](../README.md).
> 🛠️ **Studio Configuration**: For every editable UI pipeline, saved prompt/moodboard behavior, and live completed counts, see [`UI_CONTROL_CONFIG.md`](UI_CONTROL_CONFIG.md).
> ⚡ **Universal Execution & Scraping Rules**:  
> - **Always Generate Brand-New Rows**: Every run scrapes fresh active products into a brand-new Airtable row and processes it end-to-end. Never re-run remaining old rows.  
> - **Strict Shopify Ingestion**: Only scrape items confirmed Active and Published on Shopify (`homecartel.net`). Draft/archived items are skipped.  
> - **Base-Wide Cross-Table Deduplication**: Check all 60+ tables in the base to ensure zero duplicate products.

---

## 📑 Directory Navigation

```
docs/
├── README.md                            # This documentation index
├── UI_CONTROL_CONFIG.md                 # Studio overrides, config keys, counts behavior
├── AUTO_POST_SCHEDULER.md               # Instagram auto-publish worker
├── OPERATIONS_AND_UTILITIES.md          # Maintenance / tagging / diagnostic scripts
├── CLOUDFLARE_TUNNEL_GUIDE.md           # Quick Tunnel sharing guide
│
├── stories/                             # 10 Story Pipelines (9:16 vertical, 1080 x 1920 px)
│   ├── CTA_STORY.md
│   ├── TIPS_AND_EDU_STORY.md
│   ├── COLLECTION_CATEGORY_STORY.md
│   ├── DAY_NIGHT_STORY.md
│   ├── MOODBOARD_STORY.md
│   ├── PRODUCT_CLOSEUP_SPECS_STORY.md
│   ├── STYLE_THIS_STORY.md
│   ├── MYTH_FACT_STORY.md
│   ├── PRODUCT_CLOSEUP_DESCRIPTION_STORY.md
│   └── THIS_OR_THAT_STORY.md
│
├── feeds/                               # 7 Feed Pipelines (4:5 vertical, 1080 x 1350 px)
│   ├── TIPS_AND_EDU_FEED.md
│   ├── COLLECTION_CATEGORY_FEED.md
│   ├── MOODBOARD_1_FEED.md
│   ├── MOODBOARD_2_FEED.md
│   ├── ONE_PRODUCT_THREE_STYLES_FEED.md
│   ├── DAY_NIGHT_FEED.md
│   └── PRODUCT_SHOWCASE_FEED.md
│
├── reels/                               # 6 Reel Pipelines (9:16 video, 1080 x 1920 px)
│   ├── DAY_NIGHT_REEL.md
│   ├── PRODUCT_CLOSEUP_REEL.md
│   ├── BEFORE_AND_AFTER_REEL.md
│   ├── MOODBOARD_REEL.md
│   ├── STYLE_REEL_SLIDESHOW.md
│   └── ONE_PRODUCT_THREE_STYLES_REEL.md
│
├── superpowers/                         # Planned-but-NOT-implemented designs (reference only)
│   ├── plans/2026-09-16-studio-new-record-run-scope.md
│   └── specs/2026-09-16-studio-new-record-run-scope-design.md
│
└── memory/                              # Incidents, decisions, architecture notes (Obsidian vault)
    ├── incidents/
    │   ├── 2026-09-17-floor-lamp-shopify-draft-inactive.md
    │   ├── 2026-09-19-control-ui-infinite-running-status.md
    │   ├── 2026-09-19-one-product-3-styles-tagging-nameerror.md
    │   └── 2026-09-19-shopify-catalog-truncation-429.md
    ├── decisions/
    │   ├── strict-shopify-verification-policy.md
    │   ├── moodboard-1-feed-yolo-tagging.md
    │   └── 2026-09-19-foreign-key-map-purge.md
    └── architecture/
        └── system-overview.md
```

---

## 📖 1. Story Pipelines (`docs/stories/`, 9:16 Vertical)

| Subtab | Pipeline Documentation | Primary Airtable Table ID | Foreign Key Prefix | Output Description |
| :---: | :--- | :--- | :--- | :--- |
| **0** | [`CTA_STORY.md`](stories/CTA_STORY.md) | `tblYHdVq14FjMWg5o` (Chandelier) | `CTA-STORY-<FIXTURE>-<ID>` | Blended lifestyle room + Claude luxury headline + local Pillow CTA watermark layout. |
| **1** | [`TIPS_AND_EDU_STORY.md`](stories/TIPS_AND_EDU_STORY.md) | `tblwnFN5a8fLzKuP4` (Pendant) | `TNE-STORY-<FIXTURE>-<ID>` | Zero-cost YOLO object detection + Canva infographic story template. |
| **2** | [`COLLECTION_CATEGORY_STORY.md`](stories/COLLECTION_CATEGORY_STORY.md) | `tblSSVJnubFk2yBm3` (Pendant) | `CC-STORY-<FIXTURE>-<ID>` | 3-row vertical product grid collage (`1080 x 640 px` slots) + Poppins Bold titles. |
| **3** | [`DAY_NIGHT_STORY.md`](stories/DAY_NIGHT_STORY.md) | `tblKkCf88UVQ3Yu07` (Chandelier) | `DN-STORY-<FIXTURE>-<ID>` | 2-card sequence contrasting daytime natural light and warm night illumination. |
| **4** | [`MOODBOARD_STORY.md`](stories/MOODBOARD_STORY.md) | `tblHQrci8d1K9ws2M` (Chandelier) | `MB-STORY-<FIXTURE>-<ID>` | Lifestyle blend + editorial swatch moodboard card. |
| **5** | [`PRODUCT_CLOSEUP_SPECS_STORY.md`](stories/PRODUCT_CLOSEUP_SPECS_STORY.md) | `tblEGTB6BodRVDqBV` (Chandelier) | `PCS-STORY-CH-<ID>` | Commercial specification card detailing dimensions, finishes, and specs. |
| **6** | [`STYLE_THIS_STORY.md`](stories/STYLE_THIS_STORY.md) | `tblYge5R7LwTJkEHC` (Chandelier) | `ST-STORY-<FIXTURE>-<ID>` | 4-card interactive sequence with Claude room vibe color pills and double-tap voting. |
| **7** | [`MYTH_FACT_STORY.md`](stories/MYTH_FACT_STORY.md) | `tbl3OI7crWvN2Q7u6` (Chandelier) | `MNF-STORY-<FIXTURE>-<ID>` | 4-slide sequence debunking common interior lighting myths. |
| **8** | [`PRODUCT_CLOSEUP_DESCRIPTION_STORY.md`](stories/PRODUCT_CLOSEUP_DESCRIPTION_STORY.md) | `tblDcT6jovdAbKnfw` (Chandelier) | `PCD-STORY-<FIXTURE>-<ID>` | Macro product photography + editorial narrative layout across 6 categories. |
| **9** | [`THIS_OR_THAT_STORY.md`](stories/THIS_OR_THAT_STORY.md) | `tblo42IkuhYLIQBzk` (Chandelier) | `TOT-STORY-<FIXTURE>-<ID>` | Dual-product voting comparison story card across 6 categories. |

---

## 📱 2. Feed Pipelines (`docs/feeds/`, 4:5 Vertical)

| Subtab | Pipeline Documentation | Primary Airtable Table ID | Foreign Key Prefix | Output Description |
| :---: | :--- | :--- | :--- | :--- |
| **0** | [`TIPS_AND_EDU_FEED.md`](feeds/TIPS_AND_EDU_FEED.md) | `tblQ65S51Dmauwx4c` (Chandelier) | `TNE-FEEDS-<FIXTURE>-<ID>` | 4-slide carousel: 1 exterior thumbnail cover + 3 interior product blend layouts. |
| **1** | [`COLLECTION_CATEGORY_FEED.md`](feeds/COLLECTION_CATEGORY_FEED.md) | `tbl5o1j3XvUaUqmjs` (5-Room Set) | `CC-FEEDS-SET-<ID>` | 5-room coordinated whole-home collection carousel (Exterior, Bed, Dining, Kitchen, Living). |
| **2** | [`MOODBOARD_1_FEED.md`](feeds/MOODBOARD_1_FEED.md) | `tbl9u5vjgx8kuE44R` (Chandelier) | `MB1-FEEDS-<FIXTURE>-<ID>` | 4-slide carousel: Blended room, brand watermark, 3-swatch moodboard, macro closeup. |
| **3** | [`MOODBOARD_2_FEED.md`](feeds/MOODBOARD_2_FEED.md) | `tbltWgQKOYjuHw6tx` (Chandelier) | `MB2-FEEDS-<FIXTURE>-<ID>` | 2-slide carousel: In-situ room blend + architectural flat-lay moodboard. |
| **4** | [`ONE_PRODUCT_THREE_STYLES_FEED.md`](feeds/ONE_PRODUCT_THREE_STYLES_FEED.md) | `tblrlfqBGe5EjS5PI` (Chandelier) | `OP3S-FEEDS-<FIXTURE>-<ID>` | 3-slide carousel showing 1 product in 3 distinct luxury room styles. |
| **5** | [`DAY_NIGHT_FEED.md`](feeds/DAY_NIGHT_FEED.md) | `tblSceuLVvLMQ6wWp` (4 Tables) | `DN-FEEDS-<FIXTURE>-<ID>` | Comparative day and night illumination feed post (Chandelier, Pendant, Floor Lamp, Table Lamp). |
| **6** | [`PRODUCT_SHOWCASE_FEED.md`](feeds/PRODUCT_SHOWCASE_FEED.md) | `tbln0MNBaVVrZ0wrF` (Table Lamp) | `PS-FEEDS-TL-<ID>` | Luxury commercial studio vignette feed post. |

---

## 🎬 3. Reel Pipelines (`docs/reels/`, 9:16 Video)

| Pipeline Documentation | Primary Airtable Table ID | Duration | Video Description |
| :--- | :--- | :--- | :--- |
| [`DAY_NIGHT_REEL.md`](reels/DAY_NIGHT_REEL.md) | `tbl35JySlNuWh61tL` (Chandelier) | 18.0s | Day-to-night video timelapse + jazz music + brand outro. |
| [`PRODUCT_CLOSEUP_REEL.md`](reels/PRODUCT_CLOSEUP_REEL.md) | `tblqBZ946hVdOpmDV` (Table Lamp) | ~13.0s | 4-product slideshow + Poppins titles + brand outro. |
| [`BEFORE_AND_AFTER_REEL.md`](reels/BEFORE_AND_AFTER_REEL.md) | `tbloMhCOngGDWFS2y` (Chandelier) | ~15.0s | Room transformation reel across multiple angles. (Pendant table live; Floor Lamp table removed from base.) |
| [`MOODBOARD_REEL.md`](reels/MOODBOARD_REEL.md) | `tbl026zbECJJ9FRfj` (Chandelier) | 20.0s | 4-product moodboard video + 20s ElevenLabs audio. |
| [`ONE_PRODUCT_THREE_STYLES_REEL.md`](reels/ONE_PRODUCT_THREE_STYLES_REEL.md) | `tbl6ls4AWcEcynBpZ` (Chandelier) | 18.0s | Three blended photos at 5s, 4s, 4s plus 5s outro. |
| [`STYLE_REEL_SLIDESHOW.md`](reels/STYLE_REEL_SLIDESHOW.md) | `tblFFEvkHb3jLKrcv` (5-Room Set) | 11.0s | 5-room whole-home slideshow tour. |

---

## 🌐 4. Operations, Scheduling & Team Sharing

| Guide | Description |
| :--- | :--- |
| [`CLOUDFLARE_TUNNEL_GUIDE.md`](CLOUDFLARE_TUNNEL_GUIDE.md) | 100% free, zero-config Cloudflare Quick Tunnel guide to share the live studio with coworkers. |
| [`AUTO_POST_SCHEDULER.md`](AUTO_POST_SCHEDULER.md) | The Instagram auto-publish worker — what it does, its `CRON_SECRET` auth, and its dependency on a separate scheduling app outside this repo. |
| [`OPERATIONS_AND_UTILITIES.md`](OPERATIONS_AND_UTILITIES.md) | Catalog of the Airtable data-maintenance, item-tagging, and diagnostic scripts that aren't Story/Feed/Reel pipelines. |

## 🧠 5. Project Memory

| Guide | Description |
| :--- | :--- |
| [`memory/README.md`](memory/README.md) | Incidents, design decisions, and architecture notes — durable knowledge that isn't obvious from the code alone. Meant to be browsed as an Obsidian vault rooted at `docs/`. |
| [`memory/architecture/system-overview.md`](memory/architecture/system-overview.md) | How the pipeline subsystems (scraping, generation, Airtable sync, Studio UI) fit together end to end. |
| [`memory/decisions/strict-shopify-verification-policy.md`](memory/decisions/strict-shopify-verification-policy.md) | Why every scraped product is cross-verified against Shopify before ingestion, not just Akeneo's `enabled` flag. |
| [`memory/decisions/moodboard-1-feed-yolo-tagging.md`](memory/decisions/moodboard-1-feed-yolo-tagging.md) | Design decision behind YOLO item tagging in the Moodboard #1 Feed. |
| [`memory/decisions/2026-09-19-foreign-key-map-purge.md`](memory/decisions/2026-09-19-foreign-key-map-purge.md) | Why 7 dead table IDs were removed from `TABLE_PREFIX_MAP`, and the missing Before & After Floor Lamp table follow-up. |
| [`memory/incidents/2026-09-17-floor-lamp-shopify-draft-inactive.md`](memory/incidents/2026-09-17-floor-lamp-shopify-draft-inactive.md) | Root cause of a Floor Lamp Shopify draft/inactive scraping incident and how it was diagnosed. |
| [`memory/incidents/2026-09-19-control-ui-infinite-running-status.md`](memory/incidents/2026-09-19-control-ui-infinite-running-status.md) | Why the Control UI can show a pipeline as running forever, and how it was fixed. |
| [`memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md`](memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md) | NameError incident in the 1 Product 3 Styles tagging step. |
| [`memory/incidents/2026-09-19-shopify-catalog-truncation-429.md`](memory/incidents/2026-09-19-shopify-catalog-truncation-429.md) | Shopify catalog truncation / HTTP 429 incident and mitigation. |

## 🚧 6. Planned but NOT Implemented (`docs/superpowers/`)

| Doc | Status |
| :--- | :--- |
| [`superpowers/plans/2026-09-16-studio-new-record-run-scope.md`](superpowers/plans/2026-09-16-studio-new-record-run-scope.md) | Design/plan only. The modules it names (`content_automation/studio_run_scope.py`, `UI Control/routes/studio_runs.py`) do **not** exist in the codebase. |
| [`superpowers/specs/2026-09-16-studio-new-record-run-scope-design.md`](superpowers/specs/2026-09-16-studio-new-record-run-scope-design.md) | Same — spec for an unimplemented run-scope feature. Do not assume it is active behavior. |

## 📂 7. Legacy Per-Folder Notes

Each manual-workspace folder keeps its own README describing its step scripts (e.g. `CTA Story/README.md`, `Style This Story/README.md`, `Moodboard Feed/README.md`, `This or That Story/README.md`, `1 Product 3 Styles Feed/README.md`, `Before and After Reel/README.md`, `Product Closeup Description Story/README.md`, `Product Closeup Specs Story/README.md`, `Tips and Edu Feeds/README.md`, `UI Control/README.md`). These are **manual/legacy references** — the automated source of truth is the pipeline docs in sections 1–3 above plus [`../AGENTS.md`](../AGENTS.md).
