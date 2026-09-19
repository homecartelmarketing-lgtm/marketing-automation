# AGENTS.md — HomeCartel Marketing AI Automation Master Guide

> **Welcome AI Agents & Vibe Coders!**  
> This file is the primary single source of truth for understanding, running, modifying, and extending the HomeCartel Marketing AI Content Automation system. Read this document before making any changes.

---

## 1. Executive System Overview

The **HomeCartel Marketing Automation** repository is an enterprise-grade social media content automation platform. It ingests lighting and furniture products from **Akeneo PIM**, generates photorealistic lifestyle room interiors using **Krea AI**, writes design prompts and luxury headlines using **Anthropic Claude Sonnet 5**, blends products into rooms using **Fal AI Nano Banana Pro**, stamps brand logos, watermarks, and typography locally using **Python Pillow (`PIL`)**, syncs everything to **Airtable**, and provides a full-stack **React + Flask Web Studio** running on port `5200`.

### Core Operating Tenets

1. **Zero API Cost for Layouts**:
   Never call external image APIs for text rendering, logo stamping, watermarks, color pill stamping, or layout composition. All layout assembly is executed **100% locally via Python Pillow (`PIL`)** using exact sub-pixel Canva coordinate mathematics.

2. **Always Generate Brand-New Rows (Scrape Fresh & Process End-to-End)**:
   Every pipeline execution (whether triggered from the Control UI or default CLI) MUST scrape fresh active products into a **brand-new Airtable row** (e.g. 4 fresh active products for Product Closeup Reel / 4-product slots, fresh active products for Collection Category Feed, etc.) and process that new row **end-to-end**. **AI agents must NEVER search for, pick up, re-run, or loop over existing/remaining/unprocessed/incomplete rows in Airtable.**

3. **Strict Shopify "Active & Published" Ingestion**:
   Having `enabled=True` in Akeneo PIM is NOT sufficient. Every product candidate scraped from Akeneo MUST be strictly cross-verified against live published Shopify catalog data (`homecartel.net/products.json`). Any product that is Draft, Inactive, Archived, or Unlisted on Shopify MUST be immediately rejected and skipped.

---

## 2. Directory Structure & Key Entrypoints

```
marketing-automation/
├── AGENTS.md                                # This file (AI Master Rulebook)
├── README.md                                # Workspace overview & documentation index
├── .env                                     # Environment variables (API tokens, Table IDs, Moodboards)
├── .env.example                             # Environment template with all 60+ table keys
│
├── generate_*_pipeline.py                   # Self-contained pipeline MONOLITHS (real generators).
│                                            #   e.g. generate_cta_story_pipeline.py,
│                                            #   generate_product_showcase_feed_pipeline.py.
│                                            #   Flask routes spawn these via subprocess (see §3).
├── run_*.py                                 # CLI runners: thin aliases delegating to a monolith's
│                                            #   main(), OR orchestrators calling run_content_automation.py
├── run_content_automation.py                # Registry-driven runner (content_automation/workflows/)
├── scrape_*.py / backfill_*.py / preview_*.py / standalone_*.py  # Ops & one-off utility scripts
├── launch_studio_cloudflare.py / .bat       # Studio + free Cloudflare quick-tunnel launcher
│
├── docs/                                    # Centralized documentation hub
│   ├── README.md                            # Documentation index & navigation map
│   ├── stories/                             # 10 Story pipeline specs (9:16 vertical)
│   ├── feeds/                               # 7 Feed pipeline specs (4:5 vertical)
│   ├── reels/                               # 6 Reel pipeline specs (9:16 video)
│   ├── AUTO_POST_SCHEDULER.md               # Instagram auto-publish worker (external, cross-repo dependency)
│   ├── OPERATIONS_AND_UTILITIES.md          # Airtable maintenance / tagging / diagnostic scripts
│   ├── UI_CONTROL_CONFIG.md                 # Studio moodboard/prompt overrides & config keys
│   ├── CLOUDFLARE_TUNNEL_GUIDE.md           # Tunnel guide
│   ├── superpowers/                         # Planned-but-NOT-implemented designs (see index note)
│   └── memory/                              # incidents/, decisions/, architecture/ (Obsidian vault)
│
├── content_automation/                      # Core automation package
│   ├── config.py                            # .env -> Settings (load_settings), TABLES, WORKFLOWS maps
│   ├── isolated_config.py                   # Per-pipeline isolated .env settings loader
│   ├── airtable_client.py                   # Airtable REST client, fetch_status_breakdown, current_pht_timestamp
│   ├── foreign_key.py                       # TABLE_PREFIX_MAP & generate_foreign_key (FK IDs)
│   ├── akeneo_client.py                     # Akeneo PIM API client (product scraping, split_item_name)
│   ├── shopify_client.py                    # Strict Shopify live-catalog verification (products.json, 12h cache)
│   ├── krea_client.py                       # Krea AI client (room interior generation)
│   ├── fal_client.py                        # Fal AI client (Claude Sonnet 5, Nano Banana Pro, ElevenLabs, Grok)
│   ├── kie_client.py                        # Kie AI client (video & other models)
│   ├── overlay.py                           # LOCAL Python Pillow rendering engine (logos, watermarks, typography)
│   ├── item_tagger.py                       # YOLO-World furniture tagging on blended images
│   ├── media.py / video.py / audio.py       # Temp downloads; imageio-ffmpeg video & audio muxing
│   ├── assets.py                            # AssetCatalog: workspace, assets/, JSON Prompts/ lookups
│   ├── phased_content.py                    # PhasedContentRunner: resumable per-record phase engine (JSONL logs)
│   ├── state.py                             # StateManager: row select/reserve/mark_running/mark_complete
│   ├── models.py / fields.py / errors.py / http.py   # Shared dataclasses, Airtable field names, HTTP helpers
│   ├── cleanup.py / cta_conversion.py / google_form_audit.py / zoho_client.py
│   ├── fonts/                               # Poppins TTF fonts (Bold/Regular/Light) used by overlay.py
│   ├── prompts/                             # Claude prompt templates
│   ├── scraping/                            # Scrape layer: airtable.py (ScrapeAirtableClient row insertion +
│   │                                        #   FK/timestamp stamping), runner.py, products.py, categories.py,
│   │                                        #   furniture_item.py, interiors.py, tips_and_edu.py,
│   │                                        #   style_this.py, settings.py
│   └── workflows/                           # OPTIONAL class-based workflow system used ONLY by
│       ├── registry.py                      #   run_content_automation.py: WORKFLOW_CLASSES + create_workflow()
│       ├── base.py                          #   BaseWorkflow + WorkflowContext (krea_image, nano_image,
│       └── <one per format>.py              #   claude_blend_prompt, stamp_logo, update_field, ...)
│
├── UI Control/                              # Full-stack Web Dashboard ("Studio")
│   ├── api_server.py                        # THE Flask backend server (port 5200). NOTE: there is NO
│   │                                        #   root-level api_server.py.
│   ├── routes/                              # 25 pipeline blueprints + infrastructure:
│   │   ├── cta_story.py                     # Story: /api/cta/*          tips_edu_story.py  /api/tips-edu/*
│   │   ├── collection_story.py              # /api/collection-story/*    day_night_story.py  /api/day-night-story/*
│   │   ├── moodboard_story.py               # /api/moodboard-story/*     product_specs_story.py /api/product-specs/*
│   │   ├── style_this_story.py              # /api/style-this/*          myth_fact_story.py  /api/myth-fact-story/*
│   │   ├── product_description_story.py     # /api/product-description-story/*  this_or_that_story.py /api/this-or-that/*
│   │   ├── tips_edu_feed.py                 # Feed: /api/tips-edu-feed/* collection_feed.py /api/collection-feed/*
│   │   ├── moodboard_1_feed.py              # /api/moodboard-1-feed/*    moodboard_2_feed.py /api/moodboard-2-feed/*
│   │   ├── one_product_three_styles_feed.py # /api/one-product-3-styles/* day_night_feed.py /api/day-night-feed/*
│   │   ├── product_showcase_feed.py         # /api/product-showcase-feed/*
│   │   ├── day_night_reel.py                # Reel: /api/day-night-reel/* product_closeup_reel.py
│   │   ├── before_after_reel.py             # /api/before-after-reel/*    moodboard_reel.py
│   │   ├── style_reel_slideshow.py          # /api/style-reel-slideshow/* one_product_three_styles_reel.py
│   │   ├── queue_manager.py                 # In-memory FIFO job queue (/api/queue/*) — see §3
│   │   ├── rows.py                          # Row Inspector & Airtable deep links (/api/rows)
│   │   └── common.py                        # PIN verification, config overrides, helpers
│   ├── src/                                 # React + TypeScript Vite frontend
│   │   ├── app/App.tsx                      # Primary dashboard controller & state manager
│   │   └── app/components/planning/         # FixtureCard, RowInspectorModal, RunConfirmModal
│   └── dist/                                # Compiled production assets served by Flask
│
├── assets/                                  # homecartel_logo.png, *_layout.jpg watermark templates, emojis
├── JSON Prompts/                            # Per-format layout JSON + moodboard templates (Canva exports)
├── output/                                  # Generated local image composites & exports
└── scratch/                                 # Temporary test scripts & verification utilities
```

> [!IMPORTANT]
> The root folder contains ~70 `.py` scripts. The naming pattern matters:
> - `generate_*_pipeline.py` — self-contained monoliths that actually run Phases 1..N. **Flask routes spawn these directly as subprocesses.**
> - `run_*.py` — CLI entrypoints: either *thin aliases* that call a monolith's `main()`, or *orchestrators* that scrape and then invoke `run_content_automation.py`.
> - There is **no** `content_automation/text_overlays/` and **no** root `api_server.py` — Pillow rendering lives in `content_automation/overlay.py` and the server lives in `UI Control/api_server.py`.

---

## 3. How a Pipeline Run Actually Works (End-to-End Workflow)

Three execution patterns coexist. **Web Studio always uses Pattern A.**

### Pattern A — Studio run: Flask route → subprocess monolith (the primary path)

Tracing CTA Story end-to-end (every Story/Feed/Reel route follows this same shape):

1. Frontend `POST`s to `/api/cta/run` (`UI Control/routes/cta_story.py`). The optional Studio PIN (`DASHBOARD_PIN`) is verified first.
2. The route spawns the generator as a **subprocess**:
   `subprocess.Popen([sys.executable, "-u", "generate_cta_story_pipeline.py", "--table-id", T, "--max-items", N, "--mode", "all", "--moodboard-id", M, "--prompt", P])`
3. Child-process stdout streams into the route's in-memory `STATE["logs"]` (capped at 1000 lines); `detect_phase()` maps log lines to the current phase for the UI progress display.
4. The frontend polls `GET /api/cta/status` until the process exits; `POST /api/cta/stop` kills it.
5. Inside the monolith, `run_pipeline()` executes the phases in order, updating the Airtable row's `Status` after each phase (intermediate statuses are pipeline-specific; see the `STATUS_*` constants near the top of each monolith).

**CTA Story phases** (`generate_cta_story_pipeline.py`):

| # | Step | Engine | Airtable writes | Status after |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Scrape | `content_automation/scraping/*` + `akeneo_client` + strict `shopify_client` live check + base-wide dedup | **brand-new row**, FK ID stamped | `Standby` |
| 2 | Room interior | `krea_client` (9:16) | `CTA Interior` attachment | `CTA Interior Generated` |
| 3 | Blending prompt | `fal_client` (`anthropic/claude-sonnet-5`) | `Blending Prompt` field | `Blending Prompt Generated` |
| 4 | Product→room blend | Fal **Nano Banana Pro**, then `item_tagger.tag_and_upload_blended_image` (YOLO-World name tags) | `CTA Blended Image` + tagged variant | `CTA Blended Image Generated` |
| 5 | Headline | Claude via `fal_client` | `Word Generated` | — |
| 6 | Final layout | **local Pillow** (`content_automation/overlay.py`: `overlay_cta_story_layout`, `stamp_logo`) — zero API cost | `CTA Converted Image` | `Complete` + PHT timestamp |

Feed/Reel monoliths follow the same scrape → Krea → Claude → blend → local-layout chain, with per-format phases (e.g. Product Showcase Feed: `Phase 0` scrape + Phases 1–4 slide generation; Reels add `video.py`/`audio.py`/`kie_client` steps).

### Pattern B — Registry workflows (`run_content_automation.py`)

- Orchestrator runners (`run_day_night_story.py`, `run_moodboard_story.py`, `run_myth_and_fact_story.py`) scrape first, then invoke
  `python run_content_automation.py --phase stories --assignment <table_code> --batch-size N [--execute] [--record-id ...]`.
- `content_automation/workflows/registry.py::create_workflow` instantiates the matching `BaseWorkflow` subclass (one file per format under `content_automation/workflows/`); `WorkflowContext` in `base.py` provides the shared steps (`krea_image`, `nano_image`, `fal_image`, `image_to_video`, `claude_blend_prompt`, `stamp_logo`, `attach_exact`, `update_field`).
- **Flag vocabularies differ per script.** `--execute` exists only on `run_*` runners (`run_content_automation.py`, `run_collection_category_feed.py`, `run_tips_and_edu_feed.py`, ...); the `generate_*_pipeline.py` monoliths and their thin `run_*` aliases don't accept it (they use `--dry-run`, `--mode`, `--max-items`/`--max-rows`, `--record-id`). Always check the target script's `argparse` block before documenting a command.

### Pattern C — Resumable phase engine (`content_automation/phased_content.py`)

- `PipelineDefinition` + `PhasedContentRunner`: `preflight()` auto-creates missing fields and the `Phase N - Processing / Ready / Failed` status options; `run(phase, resume, max_items)` processes one phase per pass with JSONL run logging (`JsonlRunLogger`); `TERMINAL_AND_PROTECTED_STATUSES` shields Posted/Scheduled rows.
- Used only by `run_day_night_reel.py`, `run_tips_and_edu_story.py`, and `content_automation/cta_conversion.py`.

### Queue & concurrency (`UI Control/routes/queue_manager.py`)

- One **in-memory FIFO** serializes all Studio runs: `_ACTIVE_JOB`, `_PENDING_QUEUE`, `_JOB_HISTORY` (last 30), guarded by `_QUEUE_LOCK`.
- A daemon thread (`_queue_worker_loop`) pops the queue head, dispatches by POSTing to the job's own `run_endpoint` over local HTTP, then polls its `status_endpoint` every 1.5s (copying phase + logs into the queue view). On `completed/error/stopped` it moves to history with a 2s cool-off.
- REST: `/api/queue/status | enqueue | cancel | clear | stop-current`. `enqueue` requires `pipeline_type`, `fixture_id`, `run_endpoint`, `status_endpoint`; duplicate pipeline+fixture is deduped; worker lazy-starts.
- **Gotcha:** `routes/common.py::is_any_pipeline_running` is hard-coded to return `False` — the queue is the ONLY serialization mechanism. Never rely on that helper.

### Server & frontend

- There is **no root `api_server.py`**. The only Flask app is `UI Control/api_server.py` (registers 25 blueprints + rows/queue infra), serving the SPA from `UI Control/dist`.
- Dev: `python "UI Control/api_server.py"` — port resolution `X_ZOHO_CATALYST_LISTEN_PORT` → `PORT` → `5200`. Production (Dockerfile): `gunicorn --bind 0.0.0.0:${PORT:-5200} --workers 2 --threads 4 --timeout 600 api_server:app` from `UI Control/`.
- Rebuild the frontend with `npm run build` (or `pnpm run build`) inside `UI Control/`.

---

## 4. Airtable Database Conventions & Schema Standards

All pipelines connect to Airtable Base **`appDM0jUDsaiThtR3`**. Every table in this base adheres to the following mandatory standards:

### A. Standardized Foreign Key ID
Every record in every Story and Feed table must have a unique, human-readable Foreign Key ID generated by [foreign_key.py](content_automation/foreign_key.py):

$$\text{Foreign Key ID} = \langle\text{Idea Abbr}\rangle\text{-}\langle\text{Format}\rangle\text{-}\langle\text{Fixture Code}\rangle\text{-}\langle\text{Row ID}\rangle$$

- **Idea Abbr**: `CTA`, `TNE`, `CC`, `DN`, `MB`, `MB1`, `MB2`, `PCS`, `PCD`, `ST`, `MNF`, `TOT`, `OP3S`, `PS`, `PCR`, `BA`, `SRS`
- **Format**: `STORY` (9:16), `FEEDS` (4:5), or `REEL` (9:16 video)
- **Fixture Code**: `CH` (Chandelier), `PE` (Pendant), `FL` (Floor Lamp), `TL` (Table Lamp), `CL` (Cluster Chandelier), `WL` (Wall Light), `CM` (Ceiling Mounted), `SET` (Multi-room / Carousel), plus `LC` (Linear Chandelier) and `WS` (Wall Sconce) which appear only in `MB-REEL` table entries
- **Examples**: `CTA-STORY-CH-24`, `TNE-FEEDS-FL-1`, `CC-FEEDS-SET-22`, `OP3S-FEEDS-PE-4`, `PCR-REEL-TL-1`

### B. Timestamp Stamping (PHT, UTC+8)
When a pipeline finishes generation or marks a row Complete/Done, it stamps the current Philippine Time into the **`Date and Time Generated`** field (`dateTime` type) in ISO 8601 format:
```python
from content_automation.airtable_client import current_pht_timestamp
record_fields["Date and Time Generated"] = current_pht_timestamp()  # e.g., "2026-09-09T12:30:00+08:00"
```
*(Handled automatically by `AirtableClient.update_records` and `ScrapeAirtableClient.update_records` whenever `Status` is set to Complete/Done).*

### C. 5-Badge Status Lifecycle
Airtable single-select field **`Status`** maps to 5 badges across every UI card:
| Badge | Color | Name | Status Values in Airtable |
| :---: | :---: | :--- | :--- |
| **`P`** | Sky Blue | **Posted / Processing** | `Posted`, `Processing`, `Pending`, `In Progress` |
| **`S`** | Purple | **Scheduled** | `Scheduled`, `Schedule` |
| **`C`** | Emerald | **Complete / Done** | `Complete`, `Completed`, `Done`, `Already attached a room Interior` |
| **`D`** | Rose | **Discarded** | `Discard`, `Discarded` |
| **`FM`** | Amber | **For Manual / Revision** | `For Manual`, `Minor revision`, `Minor revisions`, `FM` |

### D. Direct Airtable Deep Links
The Row Inspector modal queries `/api/rows?table_id=<table_id>` and constructs direct deep links:
`https://airtable.com/{base_id}/{table_id}/{record_id}`

---

## 5. Scraping & Deduplication Rules

> [!CAUTION]
> ### CRITICAL RULE: Always Generate Brand-New Rows (Scrape Fresh & Process End-to-End)
> **AI agents frequently make the mistake of scanning Airtable for leftover, pending, or incomplete rows and attempting to re-process them. THIS IS STRICTLY PROHIBITED.**
> - **Every single pipeline run** (whether triggered via Web Studio UI or CLI default `--phase all` / without `--record-id`) MUST:
>   1. Scrape fresh active products directly from Akeneo.
>   2. Cross-verify every product against Shopify to ensure it is **Active and Published**.
>   3. Run base-wide deduplication across all 60+ tables to guarantee it has never been featured anywhere in the base.
>   4. Create a **brand-new Airtable row** (e.g. 4 fresh active Table Lamps for Product Closeup Reel; 4 fresh active fixtures for Collection Category Feed; 1 fresh active fixture for Single-slide Story/Feed).
>   5. Process that brand-new row **end-to-end (every phase, 1 through N)** until it reaches `Complete`/`Done` (`C`).
> - **NEVER iterate over, query, or rerun remaining, old, or incomplete rows in the table.**
> - Existing rows in the table must remain 100% untouched. The ONLY exception is if a developer explicitly passes an exact `--record-id <rec_id>` via CLI to re-render a specific record.

> [!IMPORTANT]
> ### CRITICAL RULE: Strict Shopify "Active & Published" Cross-Deduplication
> - **Having `enabled=True` in Akeneo PIM is NOT enough.** Akeneo contains discontinued, draft, or out-of-stock items that have not yet been disabled in PIM.
> - **Every single candidate product scraped from Akeneo MUST be strictly verified against Shopify (`homecartel.net/products.json`).**
> - If an item is **Draft, Inactive, Archived, or Not Published on Shopify**, it MUST be skipped immediately:
>   `[SHOPIFY DRAFT/INACTIVE SKIP] Item '<name>' (SKU: <sku>) is not active on Shopify -> skipping`
> - **Strict Matching Only**: Matching against Shopify MUST use exact normalized SKU equality or exact Title equality (or pre-pipe title). Substring matching (e.g. `s in clean_sku`, which mistakenly matches short tokens like `'dl'`) is strictly banned.
> - **Catalog Cache Refresh**: The Shopify catalog index cache must auto-refresh every 12 hours from `https://homecartel.net/products.json` so newly unpublished or out-of-stock items are never ingested.

### 3. Base-Wide Cross-Table Deduplication
- Before inserting any product into ANY Story, Feed, or Reel table, cross-check its SKU and Item Name against ALL 60+ tables across the entire Airtable base using `fetch_all_base_existing_identities`.
- Products already featured in any Story, Feed, or Reel table must be excluded to prevent repetitive content across the brand's social feeds.

### 4. Category-Specific Inclusions / Exclusions
- In standard Chandelier categories, skip linear chandeliers and cluster chandeliers (route them to their dedicated cluster tables).
- Always verify slot room compatibility (e.g. Table Lamps for bedside nightstands; Chandeliers for high-ceiling living/dining spaces).

---

## 6. Local Pillow Rendering Guidelines (Zero API Cost)

All local layout rendering lives in **`content_automation/overlay.py`** (plus `item_tagger.py` for YOLO name tags). There is no `text_overlays/` package.

- **Canvas Dimensions**:
  - **Story (9:16)**: `1080 x 1920 px`
  - **Feed (4:5)**: `1080 x 1350 px`
- **Typography Engine**:
  - Fonts are resolved by `overlay.py::_resolve_font_path` from **`content_automation/fonts/Poppins-Bold.ttf`, `Poppins-Regular.ttf`, `Poppins-Light.ttf`** (not `assets/fonts/`).
  - Always implement auto-scaling font protection (e.g. scale font down from 48px to 24px if text width exceeds bounding box).
- **Brand Logo**:
  - Local fallback asset is **`assets/homecartel_logo.png`** (not `assets/Logo.png`); resolution via `overlay.py::find_homecartel_logo_path` / `content_automation/assets.py::AssetCatalog`.
  - Logo bounding boxes: `HOMECARTEL_LOGO_BOX` (4:5 feeds) and `HOMECARTEL_STORY_LOGO_BOX` (9:16 stories) in `overlay.py`.
  - Story reference placement: `Width = 190.3 px`, `Height = 63.5 px`, top-right `X = 781.7 px`, `Y = 108.0 px` (108px margin from top and right).
- **Layout Templates**:
  - Watermark/layout images in `assets/*_layout.jpg` (`find_cta_layout_path` / `_resolve_asset_file`), per-format layout coordinates in `JSON Prompts/<Format>/*.json`.
- **Watermarks & Drop Shadows**:
  - Apply soft multi-directional shadow `(0, 0, 0, 180)` for legibility across any room background.

---

## 7. Complete Subtab & Pipeline Inventory

### Story Pipelines (10 Subtabs, 9:16 Ratio)
1. **CTA Story** ([`docs/stories/CTA_STORY.md`](docs/stories/CTA_STORY.md), prefix: `CTA-STORY`) — 5 tables (Chandelier, Pendant, Cluster, Table Lamp, Floor Lamp). Single slide + headline + CTA watermark.
2. **Tips & Educational Story** ([`docs/stories/TIPS_AND_EDU_STORY.md`](docs/stories/TIPS_AND_EDU_STORY.md), prefix: `TNE-STORY`) — 6 tables. Single slide + YOLO item tagging + educational infographic card.
3. **Collection Category Story** ([`docs/stories/COLLECTION_CATEGORY_STORY.md`](docs/stories/COLLECTION_CATEGORY_STORY.md), prefix: `CC-STORY`) — 5 tables. 3-product collage grid + brand header.
4. **Day & Night Story** ([`docs/stories/DAY_NIGHT_STORY.md`](docs/stories/DAY_NIGHT_STORY.md), prefix: `DN-STORY`) — 7 tables. Daytime room blend + night transformation.
5. **Moodboard Story** ([`docs/stories/MOODBOARD_STORY.md`](docs/stories/MOODBOARD_STORY.md), prefix: `MB-STORY`) — 3 tables. Lifestyle blend + moodboard swatch card.
6. **Product Closeup w/ Specs Story** ([`docs/stories/PRODUCT_CLOSEUP_SPECS_STORY.md`](docs/stories/PRODUCT_CLOSEUP_SPECS_STORY.md), prefix: `PCS-STORY`) — 1 table. Technical specification card.
7. **Style This? Story** ([`docs/stories/STYLE_THIS_STORY.md`](docs/stories/STYLE_THIS_STORY.md), prefix: `ST-STORY`) — 2 tables. 4-slide carousel + double-tap interaction + Claude room vibe pill.
8. **Myth & Fact Story** ([`docs/stories/MYTH_FACT_STORY.md`](docs/stories/MYTH_FACT_STORY.md), prefix: `MNF-STORY`) — 3 tables. 4-slide myth busting story sequence.
9. **Product Closeup w/ Description Story** ([`docs/stories/PRODUCT_CLOSEUP_DESCRIPTION_STORY.md`](docs/stories/PRODUCT_CLOSEUP_DESCRIPTION_STORY.md), prefix: `PCD-STORY`) — 6 tables. Story description card.
10. **This or That Story** ([`docs/stories/THIS_OR_THAT_STORY.md`](docs/stories/THIS_OR_THAT_STORY.md), prefix: `TOT-STORY`) — 6 tables. 2-product comparison card.

### Feed Pipelines (7 Subtabs, 4:5 Ratio)
1. **Tips & Educational Feed** ([`docs/feeds/TIPS_AND_EDU_FEED.md`](docs/feeds/TIPS_AND_EDU_FEED.md), prefix: `TNE-FEEDS`) — 4 tables (Chandelier, Pendant, Floor Lamp, Cluster). Cover thumbnail + 3 product slides.
2. **Collection Category Feed** ([`docs/feeds/COLLECTION_CATEGORY_FEED.md`](docs/feeds/COLLECTION_CATEGORY_FEED.md), prefix: `CC-FEEDS`) — 1 table (5-Room Collection). 5-room carousel post.
3. **Moodboard #1 Feed** ([`docs/feeds/MOODBOARD_1_FEED.md`](docs/feeds/MOODBOARD_1_FEED.md), prefix: `MB1-FEEDS`) — 3 tables. 4-slide moodboard carousel.
4. **Moodboard #2 Feed** ([`docs/feeds/MOODBOARD_2_FEED.md`](docs/feeds/MOODBOARD_2_FEED.md), prefix: `MB2-FEEDS`) — 4 tables. 2-slide carousel (interior blend + editorial flat-lay moodboard).
5. **1 Product, 3 Styles Feed** ([`docs/feeds/ONE_PRODUCT_THREE_STYLES_FEED.md`](docs/feeds/ONE_PRODUCT_THREE_STYLES_FEED.md), prefix: `OP3S-FEEDS`) — 3 tables. 3-slide room styling carousel.
6. **Day & Night Feed** ([`docs/feeds/DAY_NIGHT_FEED.md`](docs/feeds/DAY_NIGHT_FEED.md), prefix: `DN-FEEDS`) — 4 tables (Chandelier, Pendant, Floor Lamp, Table Lamp). Day + Night 4:5 carousel slides.
7. **Product Showcase Feed** ([`docs/feeds/PRODUCT_SHOWCASE_FEED.md`](docs/feeds/PRODUCT_SHOWCASE_FEED.md), prefix: `PS-FEEDS`) — 1 table. 3-podium group slide + 3 solo showcase slides (4 slides).

### Reel Pipelines (6 Pipelines, 9:16 Video)
1. **Day & Night Reel** ([`docs/reels/DAY_NIGHT_REEL.md`](docs/reels/DAY_NIGHT_REEL.md)) — 18-second day-to-night timelapse video with AI jazz audio.
2. **Product Closeup Reel** ([`docs/reels/PRODUCT_CLOSEUP_REEL.md`](docs/reels/PRODUCT_CLOSEUP_REEL.md)) — 15-second product inspection reel.
3. **Before & After Reel** ([`docs/reels/BEFORE_AND_AFTER_REEL.md`](docs/reels/BEFORE_AND_AFTER_REEL.md)) — 15-second transformation reel.
4. **Moodboard Reel** ([`docs/reels/MOODBOARD_REEL.md`](docs/reels/MOODBOARD_REEL.md)) — 15-second swatch and texture video reel.
5. **Style Reel Slideshow** ([`docs/reels/STYLE_REEL_SLIDESHOW.md`](docs/reels/STYLE_REEL_SLIDESHOW.md)) — Fast-paced lifestyle video slideshow.
6. **1 Product, 3 Styles Reel** ([`docs/reels/ONE_PRODUCT_THREE_STYLES_REEL.md`](docs/reels/ONE_PRODUCT_THREE_STYLES_REEL.md)) — Chandelier-only blended photo Reel with 5s, 4s, 4s holds and 5s outro.

Studio moodboard/prompt pencils, persistent config keys, and completed count behavior are mapped in [`docs/UI_CONTROL_CONFIG.md`](docs/UI_CONTROL_CONFIG.md). Use the `C` badge alone for completed totals; `P` includes posted, pending, and processing rows. The optional Studio PIN is `DASHBOARD_PIN`.

---

## 8. Step-by-Step: How to Add a New Table or Subtab

When adding a new table or subtab, follow this strict checklist to prevent regressions:

1. **Add Table ID to `content_automation/foreign_key.py`**:
   - Register the table ID in `TABLE_PREFIX_MAP` with the standard `<IDEA>-<FORMAT>-<FIXTURE>` prefix.
2. **Verify Airtable Schema**:
   - Ensure table has `"Foreign Key ID"` (`singleLineText`), `"ID"` (`number`), `"Date and Time Generated"` (`dateTime`), and `"Status"` (`singleSelect`).
3. **Create/Update Blueprint in `UI Control/routes/`**:
   - Implement `GET /counts`, `GET /status`, `POST /run`, `POST /stop`, `POST /moodboard`, `POST /prompt`.
   - Use `fetch_status_breakdown(table_id)` from `content_automation.airtable_client`.
4. **Register Blueprint in `UI Control/api_server.py`**:
   - Import blueprint and register with `app.register_blueprint(bp)`.
5. **Update Frontend `UI Control/src/app/App.tsx`**:
   - Add fixture constants array (`id`, `name`, `tableId`, `moodboardId`, `prompt`).
   - Add status counts state and active subtab boolean.
   - Wire `fetchLiveCounts()`, `checkInitialRunning()`, `checkStatus()`, modal handlers, `baseFixtures`, `currentFixtures`, and header titles.
6. **Compile Frontend**:
   - Run `npm run build` in `UI Control/` (must exit with code 0).
7. **Restart Server**:
   - Kill previous server task, then run `python "UI Control/api_server.py"` as daemon (there is no root `api_server.py`).
8. **Document in Workspace**:
   - Create or update dedicated pipeline `.md` document and link it in `README.md`.

---

## 9. CLI Quickstart & Testing Cheatsheet

> Commands below are verified against each script's `argparse` block. Flags are NOT universal — see §3 Pattern B note on flag vocabularies, and check the script before reusing a command elsewhere.

```bash
# Start Web Dashboard (port 5200)
cd "UI Control" && python api_server.py

# Launch Studio with Free Public Cloudflare Quick Tunnel (Share with Coworkers)
python launch_studio_cloudflare.py
# Or double-click launch_studio_cloudflare.bat in Windows File Explorer

# Recompile Web Frontend
cd "UI Control" && npm run build

# Run CTA Story Pipeline monolith (modes: scrape|interior|prompt|blend|words|conversion|watermark|round_robin|all|menu)
python generate_cta_story_pipeline.py --mode all

# Run Collection Category Feed (orchestrator: supports --execute / --dry-run / --phase / --max-rows / --table-id / --target-record)
python run_collection_category_feed.py --execute

# Run Tips & Educational Feed (supports --target --phase --execute --dry-run --max-rows --record-id --category --moodboard-id --prompt)
python run_tips_and_edu_feed.py --target chandeliers --phase all --execute

# Run Day & Night Feed (thin alias into generate_day_night_feed_pipeline.main; NO --execute here)
python run_day_night_feed.py --limit 3 --dry-run

# Registry-driven run (the only script where --phase stories|feeds|reels + --assignment apply)
python run_content_automation.py --phase stories --assignment <table_code> --batch-size 2 --execute

# Run Style This Story Pipeline (CLI)
python run_style_this_story.py --category chandeliers

# Test API Endpoints & Airtable Counts
python scratch/test_feed_apis.py
python scratch/audit_all_feed_subtabs.py
```

---

## 10. Operations, Scheduling & Project Memory

### Publishing is a separate concern from generation
Content generation (all phases, §3) ends with an Airtable row at `Status: Complete/Done`. **Actually posting to Instagram is a separate, always-on worker**: [`run_auto_post_scheduler.py`](run_auto_post_scheduler.py), documented in [`docs/AUTO_POST_SCHEDULER.md`](docs/AUTO_POST_SCHEDULER.md). It polls `http://localhost:3000/api/schedules/runner` — **an API that does not exist anywhere in this repository**. That scheduling/publishing logic lives in a separate application (port 3000, not the port-5200 Studio). Do not go looking for scheduling logic in this codebase; look here only for the polling worker and its `CRON_SECRET`.

### Maintenance & diagnostic scripts
Root scripts that migrate/backfill Airtable data, tag furniture in room photos, manage Zoho asset folders, or sanity-check Akeneo credentials are catalogued in [`docs/OPERATIONS_AND_UTILITIES.md`](docs/OPERATIONS_AND_UTILITIES.md) — check there before assuming a `run_*` / `scrape_*` script you don't recognize is undocumented dead code.

### Project memory protocol
[`docs/memory/`](docs/memory/) holds incidents, design decisions, and architecture notes that aren't derivable from reading the code alone (see [`docs/memory/README.md`](docs/memory/README.md)). It's meant to be opened as an Obsidian vault rooted at `docs/`.

- **Before debugging a pipeline failure** (especially a Shopify/Akeneo cross-check failure or anything resembling a past incident), check `docs/memory/incidents/` first — it may already be root-caused.
- **After resolving anything non-trivial** — a failure that took real investigation, or a design decision made without an obvious paper trail — add a short note under `docs/memory/incidents/` or `docs/memory/decisions/`. A few sentences is enough. This applies to AI agents working in this repo, not just humans.
