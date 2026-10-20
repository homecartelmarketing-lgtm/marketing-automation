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
├── GIT_PUSH_AND_DEPLOY.md               # How the AI commits, pushes, and deploys to Railway (step by step)
├── SKILLS_GUIDE.md                      # What each agent skill is for and when to load it
├── SECURITY_AUDIT.md                    # Studio security audit + 2026-10-12 hardening addendum
├── REDFLAG_REPORT.md                    # Consolidated audit of wrong-data / config-drift risks (verified 2026-10-05)
├── WORKSPACE_AUDIT.md                   # 2026-10-03 workspace organization audit
├── REMAINING_WORK.md                    # Post-audit follow-up checklist
├── HOUSE_TOUR_REEL_RUN_FIX_REPORT.md    # 2026-10-09 House Tour Reel fix & verification report
├── plans/                               # Implemented implementation plans (e.g. 2026-10-05-calendar-import.md)
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
├── reels/                               # 12 Reel Pipelines (9:16 video, 1080 x 1920 px)
│   ├── DAY_NIGHT_REEL.md
│   ├── PRODUCT_CLOSEUP_REEL.md
│   ├── BEFORE_AND_AFTER_REEL.md
│   ├── MOODBOARD_REEL.md
│   ├── STYLE_REEL_SLIDESHOW.md
│   ├── ONE_PRODUCT_THREE_STYLES_REEL.md
│   ├── ONE_AT_A_TIME_LIGHTS_REEL.md
│   ├── SKETCH_TO_REAL_REEL.md
│   ├── ROOM_BUILD_UP_REEL.md
│   ├── HOUSE_TOUR_REEL.md
│   ├── THIS_MOOD_EVERY_NIGHT_REEL.md
│   └── VIRTUAL_STAGING_REEL.md
│
├── ads/                                 # Ad Cover Pipeline (1:1 1080 x 1080 + 9:16 Story 1080 x 1920)
│   └── AD_COVER.md
│
├── banners/                             # Christmas Banner Pipeline (21:9, 5 fixtures in one Krea Christmas living room)
│   ├── BANNER_SET.md                    # ONE run/row = Christmas + Sale + third banner (what the Studio runs)
│   ├── THIRD_BANNER.md                  # 3rd banner: Sale-colour panel (951 px) + Krea Christmas bedroom (849 px)
│   ├── PROMO_BANNER.md                  # 9:16 "Your Story" promo from the main banner (standalone CLI)
│   ├── CHRISTMAS_BANNER.md
│   └── SALE_BANNER.md
│
├── icm/                                 # Vendored ICM reference library (feeds the icm-architect skill; not a pipeline spec)
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
| **1** | [`TIPS_AND_EDU_STORY.md`](stories/TIPS_AND_EDU_STORY.md) | `tblwnFN5a8fLzKuP4` (Pendant) | `TNE-STORY-<FIXTURE>-<ID>` | Zero-cost YOLO name tag + local-Pillow "Style Tip of the Day" layout (Claude-written tip). |
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
| [`BEFORE_AND_AFTER_REEL.md`](reels/BEFORE_AND_AFTER_REEL.md) | `tbloMhCOngGDWFS2y` (Chandelier) | ~15.0s | Room transformation reel (Before room $\rightarrow$ Nano Banana blend $\rightarrow$ YOLO tagging $\rightarrow$ FFmpeg video). (Pendant table live; Floor Lamp table removed from base.) |
| [`MOODBOARD_REEL.md`](reels/MOODBOARD_REEL.md) | `tbl026zbECJJ9FRfj` (Chandelier) | 20.0s | 4-product moodboard video + 20s ElevenLabs audio. |
| [`ONE_PRODUCT_THREE_STYLES_REEL.md`](reels/ONE_PRODUCT_THREE_STYLES_REEL.md) | `tbl6ls4AWcEcynBpZ` (Chandelier) | 18.0s | Three blended photos at 5s, 4s, 4s plus 5s outro. |
| [`STYLE_REEL_SLIDESHOW.md`](reels/STYLE_REEL_SLIDESHOW.md) | `tblFFEvkHb3jLKrcv` (5-Room Set) | 11.0s | 5-room whole-home slideshow tour. |
| [`ONE_AT_A_TIME_LIGHTS_REEL.md`](reels/ONE_AT_A_TIME_LIGHTS_REEL.md) | `tblJpEtBudQZda319` (One at a time Lights) | ~11.0s | Bedroom where 3 lights (table lamp, ceiling mounted, pendant) turn on one at a time via progressive Nano Banana Pro lighting blends, local FFmpeg crossfades, silent audio + brand outro. |
| [`SKETCH_TO_REAL_REEL.md`](reels/SKETCH_TO_REAL_REEL.md) | `tblUFR6OvFQaHnG1V` (Chandelier), `tblSALsUd5MXXnkp6` (Pendant) | ~11.0s | Hand-drawn outline of the room animating line by line into the photorealistic lit interior + Instagram cover + Fal AI ElevenLabs luxury background music + outro. Studio subtab 7 "Sketch to Real" (Chandelier and Pendant runnable). |
| [`HOUSE_TOUR_REEL.md`](reels/HOUSE_TOUR_REEL.md) | `tblqXkdDw4O7hxJS4` (House Tour Set) | 22.0s | 11-room organic-modern/Japandi home tour (2.0s per room): Krea interiors + Claude Vision room analysis + Kling 3s clips + animated Poppins typography + ElevenLabs music + optional outro. Studio subtab 9 "House Tour". |
| [`ROOM_BUILD_UP_REEL.md`](reels/ROOM_BUILD_UP_REEL.md) | `tblhq1rz9CVCD7yiR` (Room Build-Up Set) | ~4.8s | Stop-motion hard-cut reel: 2 rooms (Pendant Light, Chandelier) each go empty → furnished in 4 steps. Built in reverse with chained Nano Banana Pro removals, then local FFmpeg + ElevenLabs pop/whoosh sounds. Studio subtab 8 "Room Build-Up". |
| [`THIS_MOOD_EVERY_NIGHT_REEL.md`](reels/THIS_MOOD_EVERY_NIGHT_REEL.md) | `tblDa5UOTUTlU1Xxy` (This Mood Every Night Set) | ~12.0s | 7 night-interior snap cuts (~1.35s) + centered `this mood every night` title + animated product tags + lo-fi music + 2.5s outro. Studio subtab 10 "This Mood Every Night". |
| [`VIRTUAL_STAGING_REEL.md`](reels/VIRTUAL_STAGING_REEL.md) | `tblPYG5Ed4XURecu6` (Chandelier) | ~12.5s | Empty-to-furnished assembly sequence via Fal Kling 3.0 Pro start-to-end frame transition, Pillow branding pill tag, and branded outro. Studio subtab 11 "Virtual Staging". |

---

## 🖼️ 4. Ad Covers (`docs/ads/`, 1:1 Square + 9:16 Story)

| Fixture | Pipeline Documentation | Primary Airtable Table ID | Foreign Key Prefix | Output Description |
| :--- | :--- | :--- | :--- | :--- |
| **Chandelier** | [`AD_COVER.md`](ads/AD_COVER.md) | `tblwIsDGZBPuYJV2Z` (Chandelier) | `ADC-ADS-CH-<ID>` | Highest-priced newest chandelier blended into a Krea 1:1 living room + local Pillow ad-cover overlay, then extended to a 9:16 Story twin (`Ad Cover Converted Image Story`). |
| **Floor Lamp** | [`AD_COVER.md`](ads/AD_COVER.md) | `tbl27FKuDUD4FdJUR` (Floor Lamp) | `ADC-ADS-FL-<ID>` | Highest-priced newest floor lamp blended into a Krea 1:1 living room + local Pillow ad-cover overlay, then extended to a 9:16 Story twin. |
| **Table Lamp** | [`AD_COVER.md`](ads/AD_COVER.md) | `tblk3RfFqawHZ5Wrk` (Table Lamp) | `ADC-ADS-TL-<ID>` | Highest-priced newest table lamp blended into a Krea 1:1 bedroom + local Pillow ad-cover overlay, then extended to a 9:16 Story twin. |
| **Cluster Chandelier** | [`AD_COVER.md`](ads/AD_COVER.md) | `tbltouegkjgQwdr1u` (Cluster Chandelier) | `ADC-ADS-CL-<ID>` | Highest-priced newest cluster chandelier blended into a high-ceiling Krea 1:1 room + local Pillow ad-cover overlay, then extended to a 9:16 Story twin. |
| **Pendant Light** | [`AD_COVER.md`](ads/AD_COVER.md) | `tbl99Cwda2Xn93giT` (Pendant Light) | `ADC-ADS-PE-<ID>` | Highest-priced newest pendant light blended into a dining room Krea 1:1 room + local Pillow ad-cover overlay, then extended to a 9:16 Story twin. |
| **Wall Light** | [`AD_COVER.md`](ads/AD_COVER.md) | `tblUO5nybG9fIkhTT` (Wall Light) | `ADC-ADS-WL-<ID>` | Highest-priced newest wall light blended into a modern living room Krea 1:1 room + local Pillow ad-cover overlay, then extended to a 9:16 Story twin. |
| **New Collection** | [`AD_COVER.md`](ads/AD_COVER.md) | `tbluMexgzcWE1pDZJ` (New Collection) | `ADC-ADS-NEW-<ID>` | Highest-priced newest chandelier blended into a Krea 1:1 living room + local Pillow "New Collection" overlay, then extended to a 9:16 Story twin. |
| **On Sale Designs** | [`AD_COVER.md`](ads/AD_COVER.md) | `tbleQIVBooVazAyk3` (On Sale Designs) | `ADC-ADS-SALE-<ID>` | Highest-priced newest chandelier blended into a Krea 1:1 living room + local Pillow "On Sale" overlay, then extended to a 9:16 Story twin. |
| **On Stock Designs** | [`AD_COVER.md`](ads/AD_COVER.md) | `tblX7tpTJhfH0UXmm` (On Stock Designs) | `ADC-ADS-STOCK-<ID>` | Highest-priced newest chandelier blended into a Krea 1:1 interior + local Pillow "On Stock" overlay, then extended to a 9:16 Story twin. |

Ad Covers is a **standalone 4th top-level Studio tab** (not a sub-tab family): each of the 9 fixtures has its own run button, and one run produces both the 1:1 cover and its 9:16 Story twin. See [`AD_COVER.md`](ads/AD_COVER.md) for the 7-phase flow, status vocabulary, and CLI flags.

## 🎄 5. Christmas Banner (`docs/banners/`, 21:9)

Standalone **Banner** tab with one card. One run blends a fresh chandelier, pendant light, floor lamp, table lamp and wall light into a single Krea modern Christmas living room (moodboard `b5ffdcbb-192e-4528-8d86-d1a4cf496887`) using Nano Banana Pro at 21:9. Claude then writes a title + subtitle that a local Pillow phase stamps on (white Poppins with a soft shadow). Table: `tblgNk1Tp6qKUcduw` (`AIRTABLE_TABLE_ID_CHRISTMAS_BANNER`), prefix `XMS-BANNER-ALL-<ID>`. See [`CHRISTMAS_BANNER.md`](banners/CHRISTMAS_BANNER.md).

## 🏷️ 6. Sale Banner (`docs/banners/`, 1800x600)

Second sub-tab of the **Banner** tab. A red sale panel with `10%` and `15%` blocks between two Krea Christmas interiors: a dining room with one scraped pendant light (left) and a kitchen with two scraped pendant lights over the island (right), each blended by Nano Banana Pro from a prompt Claude writes for that room. Captions (dates with the year) and percentages come from `calendar_config.json` (the promotions calendar); Claude also suggests the panel's hex colour from the two blended rooms (`--panel-color` overrides it). Shares table `tblgNk1Tp6qKUcduw` with the Christmas banner (rows told apart by `Category`). See [`SALE_BANNER.md`](banners/SALE_BANNER.md).

---

## 🌐 5. Operations, Scheduling & Team Sharing

| Guide | Description |
| :--- | :--- |
| [`CLOUDFLARE_TUNNEL_GUIDE.md`](CLOUDFLARE_TUNNEL_GUIDE.md) | 100% free, zero-config Cloudflare Quick Tunnel guide to share the live studio with coworkers. |
| [`AUTO_POST_SCHEDULER.md`](AUTO_POST_SCHEDULER.md) | The Instagram auto-publish worker — what it does, its `CRON_SECRET` auth, and its dependency on a separate scheduling app outside this repo. |
| [`OPERATIONS_AND_UTILITIES.md`](OPERATIONS_AND_UTILITIES.md) | Catalog of the Airtable data-maintenance, item-tagging, and diagnostic scripts that aren't Story/Feed/Reel/Ad Cover pipelines — including the `scratch/` Ad Cover schema and geometry verifiers. |
| [`GIT_PUSH_AND_DEPLOY.md`](GIT_PUSH_AND_DEPLOY.md) | Detailed, step-by-step guide to how an AI agent commits, pushes `marketing-automation`, fast-forwards `main`, and triggers the Railway deploy — what it checks, what it will never do, and what to do when a step fails. |

## 🧠 6. Project Memory

| Guide | Description |
| :--- | :--- |
| [`memory/README.md`](memory/README.md) | Incidents, design decisions, and architecture notes — durable knowledge that isn't obvious from the code alone. Meant to be browsed as an Obsidian vault rooted at `docs/`. |
| [`memory/architecture/system-overview.md`](memory/architecture/system-overview.md) | How the pipeline subsystems (scraping, generation, Airtable sync, Studio UI) fit together end to end. |
| [`memory/decisions/strict-shopify-verification-policy.md`](memory/decisions/strict-shopify-verification-policy.md) | Why every scraped product is cross-verified against Shopify before ingestion, not just Akeneo's `enabled` flag. |
| [`memory/decisions/moodboard-1-feed-yolo-tagging.md`](memory/decisions/moodboard-1-feed-yolo-tagging.md) | Design decision behind YOLO item tagging in the Moodboard #1 Feed. |
| [`memory/decisions/2026-09-19-foreign-key-map-purge.md`](memory/decisions/2026-09-19-foreign-key-map-purge.md) | Why 7 dead table IDs were removed from `TABLE_PREFIX_MAP`, and the missing Before & After Floor Lamp table follow-up. |
| [`memory/decisions/ad-cover-complete-status-belongs-to-phase-7.md`](memory/decisions/ad-cover-complete-status-belongs-to-phase-7.md) | Why `Complete` moved off Phase 5 onto Phase 7 (Airtable `singleSelect` overwrites), why a story-branch failure still leaves the row `Complete`, and why Phase 6 needs its own outpaint prompt. |
| [`memory/incidents/2026-09-17-floor-lamp-shopify-draft-inactive.md`](memory/incidents/2026-09-17-floor-lamp-shopify-draft-inactive.md) | Root cause of a Floor Lamp Shopify draft/inactive scraping incident and how it was diagnosed. |
| [`memory/incidents/2026-09-19-control-ui-infinite-running-status.md`](memory/incidents/2026-09-19-control-ui-infinite-running-status.md) | Why the Control UI can show a pipeline as running forever, and how it was fixed. |
| [`memory/incidents/2026-09-29-edit-modal-prop-mismatch-white-screen.md`](memory/incidents/2026-09-29-edit-modal-prop-mismatch-white-screen.md) | White screen when clicking the prompt/moodboard edit pencil: `App.tsx` passed stale prop names to the refactored modals (no type-check to catch it). |
| [`memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md`](memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md) | NameError incident in the 1 Product 3 Styles tagging step. |
| [`memory/incidents/2026-09-19-shopify-catalog-truncation-429.md`](memory/incidents/2026-09-19-shopify-catalog-truncation-429.md) | Shopify catalog truncation / HTTP 429 incident and mitigation. |
| [`memory/incidents/2026-09-21-shopify-429-partial-cache.md`](memory/incidents/2026-09-21-shopify-429-partial-cache.md) | Follow-up to the 429 incident: throttling from page 27 onward made the crawler save a truncated catalog over the 12-hour disk cache, wrongly rejecting live products. Fix adds `Retry-After` parsing, staggered workers, and a partial-crawl guard that refuses to overwrite a good cache. |
| [`memory/incidents/2026-09-21-day-night-feed-stamp-lost-in-refactor.md`](memory/incidents/2026-09-21-day-night-feed-stamp-lost-in-refactor.md) | Why Day & Night Feed rows shipped with an un-watermarked Day image and an empty `STORY - Day & Night (2)` field: the stamped temp file was consumed by YOLO tagging then deleted, and a refactor dropped the final slide upload. |
| [`memory/incidents/2026-09-21-item-name-stamp-inconsistencies.md`](memory/incidents/2026-09-21-item-name-stamp-inconsistencies.md) | One symptom family — missing item-name stamps — across 1 Product 3 Styles Feed, Collection Category Feed, Moodboard Reel and Style This Story, with three distinct root causes. |
| [`memory/incidents/2026-10-02-mb-reel-item-name-material-duplicates.md`](memory/incidents/2026-10-02-mb-reel-item-name-material-duplicates.md) | MB Reel regression: Phase 3's 0-based `Item Name{slot}` lookup stamped placeholders/shifted names, and un-normalized material words (`BRASS,` vs `Brass`) duplicated across slots. |
| [`memory/incidents/2026-10-05-tag-line2-anchor-fallback.md`](memory/incidents/2026-10-05-tag-line2-anchor-fallback.md) | Tag Line-2 lost when Product Type field empty (anchor handoff) + Floor Lamp Moodboard Story registry `KeyError`; fixed by shared `resolve_tag_names`. |
| [`memory/incidents/2026-10-19-tips-edu-feed-attach-format.md`](memory/incidents/2026-10-19-tips-edu-feed-attach-format.md) | Tips & Edu Feed carousel attachment order (thumbnail prepended at index 0) and fail-closed slot name resolution. |
| [`memory/decisions/2026-10-15-graphify-icm-vendored-skills.md`](memory/decisions/2026-10-15-graphify-icm-vendored-skills.md) | Why `graphify` and `icm-architect` are vendored by hand (absent from `skills-lock.json`), what each is for, why `docs/icm/` is reference material rather than a pipeline spec, and why the graphify `.gitignore` patterns must stay anchored. |
| [`memory/incidents/2026-10-15-tips-edu-feed-phase-5-6-labels-and-audit-sync.md`](memory/incidents/2026-10-15-tips-edu-feed-phase-5-6-labels-and-audit-sync.md) | Tips & Educational Feed Phase 5 & 6 stale comment banners, audit log labels, warning output, and partial-failure status analysis. |
| [`memory/incidents/2026-10-15-tips-edu-feed-phase-5-attributeerror-and-tips-stamping.md`](memory/incidents/2026-10-15-tips-edu-feed-phase-5-attributeerror-and-tips-stamping.md) | Tips & Educational Feed stopped after Phase 4: Phase 5 read a non-existent `category_label` attribute, so Phase 6 never ran and the final slides and tips stamping were missing. |
| [`memory/incidents/2026-10-15-tips-edu-feed-crash-leaves-row-processing.md`](memory/incidents/2026-10-15-tips-edu-feed-crash-leaves-row-processing.md) | A crashed Tips & Educational Feed phase left the row on `Processing` forever (`PE-16`); crashes now set `For Manual` (FM), and Phase 6 downloads fail per slot. Includes how to retry an FM row with `--record-id`. |
| [`memory/incidents/2026-10-13-studio-queue-stuck-step-0-and-stop-endpoint.md`](memory/incidents/2026-10-13-studio-queue-stuck-step-0-and-stop-endpoint.md) | Studio run stuck at "Starting Generation... Step 0/5" (queue polling hit a loopback 401) and a stop-endpoint failure; fixed with a stop fallback. |
| [`memory/incidents/2026-10-12-this-mood-every-night-client-init-typeerror.md`](memory/incidents/2026-10-12-this-mood-every-night-client-init-typeerror.md) | This Mood Every Night Reel failed because `AkeneoClient()` was created without `Settings` (missing `host`, `client_id`, ... arguments). |
| [`memory/incidents/2026-10-09-house-tour-krea-402-balance-error.md`](memory/incidents/2026-10-09-house-tour-krea-402-balance-error.md) | House Tour run died in Phase 1 with a generic "non-zero code 1": the Krea API balance was depleted (HTTP 402). |
| [`memory/incidents/2026-10-06-house-tour-kling-empty-blend-url.md`](memory/incidents/2026-10-06-house-tour-kling-empty-blend-url.md) | House Tour Phase 5 failed with "slot 2 has no blended image" even though the Phase 4 blends and YOLO tags had succeeded. |
| [`memory/incidents/2026-10-02-before-after-reel-runner-import-error.md`](memory/incidents/2026-10-02-before-after-reel-runner-import-error.md) | Every Before & After Reel Studio run died at startup: `run_before_after_reel.py` imported a constant its generator no longer defined (plus follow-up bugs behind it). |
| [`memory/incidents/2026-10-01-tips-edu-story-nano-banana-layout-redrew-room.md`](memory/incidents/2026-10-01-tips-edu-story-nano-banana-layout-redrew-room.md) | Tips & Edu Story's Nano Banana layout step repainted the room, doubled the logo and printed prompt text; fixed by moving the layout to local Pillow. |
| [`memory/incidents/2026-10-01-collection-feed-name-tag-attribute-error.md`](memory/incidents/2026-10-01-collection-feed-name-tag-attribute-error.md) | Collection Category Feed rows had no YOLO item-name tags: a swallowed `AttributeError` on a non-existent slot attribute. |
| [`memory/incidents/2026-10-01-studio-run-saved-none-as-moodboard-and-prompt.md`](memory/incidents/2026-10-01-studio-run-saved-none-as-moodboard-and-prompt.md) | A Studio run sent the literal prompt `"None"` to Krea: the queue posted JSON `null` overrides that routes turned into the string `"None"`. |
| [`memory/incidents/2026-10-01-railway-two-gunicorn-workers-split-queue.md`](memory/incidents/2026-10-01-railway-two-gunicorn-workers-split-queue.md) | On Railway a run showed "Initializing" while the queue was idle: two gunicorn workers each held their own in-memory queue. Rule: keep `--workers 1`. |
| [`memory/incidents/2026-10-01-railway-missing-isolated-env-file.md`](memory/incidents/2026-10-01-railway-missing-isolated-env-file.md) | "Missing isolated configuration" on Railway: the isolated loader only read dotenv files that are absent from the image; it now falls back to environment variables. |
| [`memory/incidents/2026-09-30-studio-run-flicker-two-pollers.md`](memory/incidents/2026-09-30-studio-run-flicker-two-pollers.md) | Studio log/status flicker during runs: two pollers wrote the same state. The queue is now the only status driver. |
| [`memory/incidents/2026-09-30-sketch-to-real-studio-ran-stale-script-copy.md`](memory/incidents/2026-09-30-sketch-to-real-studio-ran-stale-script-copy.md) | Sketch to Real worked from the CLI but failed in the Studio: the route preferred an untracked stale script copy over the root generator. |
| [`memory/incidents/2026-09-28-shopify-cloudflare-429-bot-challenge.md`](memory/incidents/2026-09-28-shopify-cloudflare-429-bot-challenge.md) | Phase 1 scrapes stalled around page 32 of the Shopify catalog on HTTP 429 and a Cloudflare bot challenge; mitigation notes. |
| [`memory/decisions/2026-10-12-api-hardening-pass.md`](memory/decisions/2026-10-12-api-hardening-pass.md) | Deny-by-default `/api/*` gate, `?pin=` rejection, single `MAX_RUN_ITEMS = 10` ceiling, SSRF guard on queue endpoints, and what is still open. See also [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md). |
| [`memory/decisions/2026-10-12-studio-email-password-login.md`](memory/decisions/2026-10-12-studio-email-password-login.md) | Why the Studio moved from the shared `DASHBOARD_PIN` to email + password login with a cookie session. |
| [`memory/decisions/2026-10-06-house-tour-reel-dynamic-vision-and-animation.md`](memory/decisions/2026-10-06-house-tour-reel-dynamic-vision-and-animation.md) | House Tour Reel: reference pacing, dynamic Claude Vision room analysis, animated Poppins reveal, and the zero-fallback title policy. |
| [`memory/decisions/2026-10-05-cta-fixture-catalog.md`](memory/decisions/2026-10-05-cta-fixture-catalog.md) | Why per-pipeline fixture wiring lives in `content_automation/fixture_catalog.py` (CTA Story pilot) and Studio saves go through it. |

## 🚧 7. Implementation plans (`docs/plans/`)

| Doc | Status |
| :--- | :--- |
| [`plans/2026-10-20-universal-caption-generation.md`](plans/2026-10-20-universal-caption-generation.md) | Universal Instagram auto-caption generation across all Story/Feed/Reel/Banner tables (`Caption Generated` field via Claude Sonnet 5). |
| [`plans/2026-10-19-tips-edu-feed-fix-tips-attach-item-name.md`](plans/2026-10-19-tips-edu-feed-fix-tips-attach-item-name.md) | Tips & Edu Feed: Carousel attachment ordering (thumbnail prepended at index 0) and item-name normalization. |
| [`plans/2026-10-05-calendar-import.md`](plans/2026-10-05-calendar-import.md) | Content Calendar XLSX → Studio queue import (implemented: `content_automation/calendar_import.py`, `UI Control/routes/calendar.py`, `scripts/ops/import_content_calendar.py`). |
| [`plans/2026-10-15-skills-registration-md-sync.md`](plans/2026-10-15-skills-registration-md-sync.md) | Register `graphify` + `icm-architect` in `AGENTS.md` §12 and `docs/SKILLS_GUIDE.md`, add `docs/icm/` to the docs navigation, fix the stale `skills-lock.json` row, and anchor the graphify `.gitignore` patterns. Docs-only. |

> `docs/superpowers/plans/` holds one tracked plan, `2026-10-13-skill-upgrades-md-protocol.md` (the skills upgrade and MD pre-read protocol work). New plans go in `docs/plans/`, which is the live list above.

## 📂 8. Legacy Per-Folder Notes

Each legacy manual-workspace folder (now preserved under `archive/legacy_workspaces/`) keeps its own README describing its step scripts (e.g. `archive/legacy_workspaces/CTA Story/README.md`, `archive/legacy_workspaces/Style This Story/README.md`, `archive/legacy_workspaces/Moodboard Feed/README.md`, `archive/legacy_workspaces/This or That Story/README.md`, `archive/legacy_workspaces/1 Product 3 Styles Feed/README.md`, `archive/legacy_workspaces/Before and After Reel/README.md`, `archive/legacy_workspaces/Product Closeup Description Story/README.md`, `archive/legacy_workspaces/Product Closeup Specs Story/README.md`, `UI Control/README.md`). These are **manual/legacy references** — the automated source of truth is the pipeline docs in sections 1–3 above plus [`../AGENTS.md`](../AGENTS.md).
