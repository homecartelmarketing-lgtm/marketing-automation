# AGENTS.md — HomeCartel Marketing AI Automation Master Guide

> **Welcome AI Agents & Vibe Coders!**  
> This file is the primary single source of truth for understanding, running, modifying, and extending the HomeCartel Marketing AI Content Automation system. Read this document before making any changes.
>
> Step-by-step procedures (adding a pipeline, shipping, debugging, layouts, scraping) live in **skills** under `.agents/skills/` (see §12). This file keeps the rules that always apply; load the matching skill when you start that kind of task.

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
├── .agents/skills/                          # Agent skills (procedures loaded on demand, see §12)
│
├── generate_*_pipeline.py                   # Self-contained pipeline MONOLITHS (real generators).
│                                            #   e.g. generate_cta_story_pipeline.py,
│                                            #   generate_product_showcase_feed_pipeline.py.
│                                            #   Flask routes spawn these via subprocess (see §3).
├── run_*.py                                 # CLI runners: thin aliases delegating to a monolith's
│                                            #   main(), OR orchestrators calling run_content_automation.py
├── run_content_automation.py                # Registry-driven runner (content_automation/workflows/)
├── tests/                                   # stdlib unittest suites (run: python -m unittest discover tests)
├── scripts/                                 # Organized ops, scrapers, and visual previewers
│   ├── ops/                                 # Maintenance, backfills, migrations, video tools
│   ├── scrapers/                            # Standalone Akeneo and category scrapers
│   └── previews/                            # Local Pillow layout and thumbnail previewers
├── archive/                                 # Preserved legacy workspace menus, runners & UI prototypes
│   ├── legacy_workspaces/                   # 9 archived interactive-menu folders (CTA Story, etc.)
│   ├── legacy_runners/                      # 6 archived dead stub/alias runners
│   └── legacy_ui/                           # Archived legacy HTML/JS prototype UI
├── launch_studio_cloudflare.py / .bat       # Studio + free Cloudflare quick-tunnel launcher
│
├── docs/                                    # Centralized documentation hub
│   ├── README.md                            # Documentation index & navigation map
│   ├── stories/                             # 10 Story pipeline specs (9:16 vertical)
│   ├── feeds/                               # 7 Feed pipeline specs (4:5 vertical)
│   ├── reels/                               # 8 Reel pipeline specs (9:16 video)
│   ├── ads/                                 # 1 Ad Cover pipeline spec (1:1 1080x1080 + 9:16 Story 1080x1920)
│   ├── AUTO_POST_SCHEDULER.md               # Instagram auto-publish worker (external, cross-repo dependency)
│   ├── OPERATIONS_AND_UTILITIES.md          # Airtable maintenance / tagging / diagnostic scripts
│   ├── GIT_PUSH_AND_DEPLOY.md               # Detailed AI commit/push/deploy walkthrough (expands §11)
│   ├── SKILLS_GUIDE.md                      # What each agent skill is for and when to load it
│   ├── UI_CONTROL_CONFIG.md                 # Studio moodboard/prompt overrides & config keys
│   ├── CLOUDFLARE_TUNNEL_GUIDE.md           # Tunnel guide
│   └── memory/                              # incidents/, decisions/, architecture/ (Obsidian vault)
│
├── content_automation/                      # Core automation package
│   ├── config.py                            # .env -> Settings (load_settings), TABLES, WORKFLOWS maps
│   ├── isolated_config.py                   # Per-pipeline isolated .env settings loader
│   ├── airtable_client.py                   # Airtable REST client, fetch_status_breakdown, current_pht_timestamp
│   ├── foreign_key.py                       # TABLE_PREFIX_MAP & generate_foreign_key (FK IDs)
│   ├── fixture_catalog.py                   # Single source of truth: per-pipeline fixture wiring
│   │                                        #   (table_id, FK prefix, moodboard/prompt env keys + defaults).
│   │                                        #   Pilot: CTA Story. Enforced by tests/test_cta_catalog_consistency.py
│   ├── akeneo_client.py                     # Akeneo PIM API client (product scraping, split_item_name)
│   ├── shopify_client.py                    # Strict Shopify live-catalog verification (products.json, 24h cache)
│   ├── krea_client.py                       # Krea AI client (room interior generation)
│   ├── fal_client.py                        # Fal AI client (Claude Sonnet 5, Nano Banana Pro, ElevenLabs, Grok)
│   ├── kie_client.py                        # Kie AI client (video & other models)
│   ├── overlay.py                           # LOCAL Python Pillow rendering engine (logos, watermarks, typography)
│   ├── story_tip.py                         # Tips & Edu Story: Claude "Style Tip of the Day" prompt, sanitizer, fallback tips
│   ├── banner_common.py / promo_calendar.py # Christmas/Sale Banner shared helpers; promotions calendar (assets/calendar_config.json)
│   ├── item_tagger.py                       # YOLO-World furniture tagging on blended images (resolve_tag_names: anchor.product_type-first fallback)
│   ├── calendar_import.py                   # Content Calendar XLSX parser (parse_month_slots, resolve_job, pick_fixture, build_jobs)
│   ├── media.py / video.py / audio.py       # Temp downloads; imageio-ffmpeg video & audio muxing
│   ├── assets.py                            # AssetCatalog: workspace, assets/, JSON Prompts/ lookups
│   ├── phased_content.py                    # PhasedContentRunner: resumable per-record phase engine (JSONL logs)
│   ├── state.py                             # StateManager: row select/reserve/mark_running/mark_complete
│   ├── models.py / fields.py / errors.py / http.py   # Shared dataclasses, Airtable field names, HTTP helpers
│   ├── cleanup.py / cta_conversion.py / google_form_audit.py / zoho_client.py
│   ├── fonts/                               # Poppins TTF fonts (ExtraBold/Bold/Medium/Regular/Light) used by overlay.py
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
│   ├── routes/                              # 27 pipeline blueprints + infrastructure:
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
│   │   ├── one_at_a_time_lights_reel.py     # /api/one-at-a-time-lights-reel/* (3-fixture progressive-lighting reel)
│   │   ├── sketch_to_draw_reel.py           # /api/sketch-to-draw-reel/* (Studio "Sketch to Real" subtab; always runs generate_sketch_to_real_reel_pipeline.py)
│   │   ├── ad_cover.py                      # Ad Cover: /api/ad-cover/* (1:1 + 9:16 Story, per-fixture run)
│   │   ├── christmas_banner.py              # Banner (Christmas + Sale + third, one run/row): /api/christmas-banner/*   sale_banner.py /api/sale-banner/* (API/CLI only)
│   │   ├── queue_manager.py                 # In-memory FIFO job queue (/api/queue/*) — see §3
│   │   ├── calendar.py                      # Content Calendar XLSX import (/api/calendar/preview|enqueue) — RunCenter button
│   │   ├── rows.py                          # Row Inspector & Airtable deep links (/api/rows)
│   │   └── common.py                        # PIN verification, config overrides, helpers
│   ├── src/                                 # React + TypeScript Vite frontend
│   │   ├── app/App.tsx                      # Dashboard shell (composes the hooks below; no per-pipeline wiring)
│   │   ├── app/constants/                   # fixtures.ts (*_FIXTURES + subtab switch), pipelines.ts (PipelineConfig per pipeline)
│   │   ├── app/hooks/                       # usePipelineData, usePipelineRunner, useQueue
│   │   ├── app/types/index.ts               # PipelineType union, FixtureData, status-count types
│   │   └── app/components/                  # planning/ (FixtureCard, RowInspectorModal, RunConfirmModal, RunCenter = bottom status bar + run panel + CalendarImportModal), modals/
│   └── dist/                                # Compiled production assets served by Flask
│
├── assets/                                  # homecartel_logo.png, *_layout.jpg watermark templates, emojis,
│   │                                        #   chand-collection.png, trending.png, etc. (1:1) + ad-cover-*-story.png (9:16)
│   │                                        #   calendar_pipeline_map.json (Content Calendar idea→pipeline map), calendar_config.json
│   └── models/                              # yolov8s-worldv2.pt (YOLO-World weights for item tagging)
├── JSON Prompts/                            # Per-format layout JSON + moodboard templates (Canva exports)
├── output/                                  # Generated local image composites & exports
└── scratch/                                 # Temporary test scripts & verification utilities
```

> [!IMPORTANT]
> The root folder contains the active generators and runners (~55 `.py` scripts). The naming pattern matters:
> - `generate_*` (e.g. `generate_*_pipeline.py`) — self-contained monoliths that actually run Phases 1..N. **Flask routes spawn these directly as subprocesses.**
> - `run_*.py` — CLI entrypoints: either *thin aliases* that call a monolith's `main()`, or *orchestrators* that scrape and then invoke `run_content_automation.py`.
> - Root utilities with internal pipeline callers (`standalone_scrape_akeneo.py` and category scrapers imported by runners) remain in root to guarantee zero breaking changes. Standalone tools with no callers were tidied away 2026-10-05: `scripts/ops/photo_video_maker.py`, `scripts/ops/standalone_item_tagger.py`, `scripts/scrapers/generate_krea_interiors.py`, and the legacy dashboard `archive/run_dashboard.py`.
> - One-off utility scripts, standalone test scrapers, and layout previews live organized under `scripts/ops/`, `scripts/scrapers/`, and `scripts/previews/`.
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

- There is **no root `api_server.py`**. The only Flask app is `UI Control/api_server.py` (registers 25 pipeline blueprints + rows/queue infra), serving the SPA from `UI Control/dist`.
- Dev: `python "UI Control/api_server.py"` — port resolution `X_ZOHO_CATALYST_LISTEN_PORT` → `PORT` → `5200`. Production (Dockerfile): `gunicorn --bind 0.0.0.0:${PORT:-5200} --workers 1 --threads 8 --timeout 600 api_server:app` from `UI Control/`. **Keep `--workers 1`**: the queue and every pipeline route keep their state in memory, so extra worker processes each hold a different copy and runs look stuck or flicker.
- Rebuild the frontend with `npm run build` (or `pnpm run build`) inside `UI Control/`.

---

## 4. Airtable Database Conventions & Schema Standards

All pipelines connect to Airtable Base **`appDM0jUDsaiThtR3`**. Every table in this base adheres to the following mandatory standards:

### A. Standardized Foreign Key ID
Every record in every Story and Feed table must have a unique, human-readable Foreign Key ID generated by [foreign_key.py](content_automation/foreign_key.py):

$$\text{Foreign Key ID} = \langle\text{Idea Abbr}\rangle\text{-}\langle\text{Format}\rangle\text{-}\langle\text{Fixture Code}\rangle\text{-}\langle\text{Row ID}\rangle$$

- **Idea Abbr**: `CTA`, `TNE`, `CC`, `DN`, `MB`, `MB1`, `MB2`, `PCS`, `PCD`, `ST`, `MNF`, `TOT`, `OP3S`, `PS`, `PCR`, `BA`, `SRS`, `ADC`, `OATL`, `STR` (Sketch to Real; `STD` table aliases map to `STR`), `XMS` (Christmas/Sale Banner)
- **Format**: `STORY` (9:16), `FEEDS` (4:5), `REEL` (9:16 video), `ADS` (Ad Cover row: carries the 1:1 cover and its 9:16 Story twin; the FK token stays `ADS`), or `BANNER` (Christmas/Sale Banner rows, `XMS-BANNER-ALL`)
- **Fixture Code**: `CH` (Chandelier), `PE` (Pendant), `FL` (Floor Lamp), `TL` (Table Lamp), `CL` (Cluster Chandelier), `WL` (Wall Light), `CM` (Ceiling Mounted), `SET` (Multi-room / Carousel), `LR` (Living Room / Bedroom, One at a time Lights Reel), `NEW` / `SALE` / `STOCK` (New Collection / On Sale Designs / On Stock Designs, Ad Cover only), plus `LC` (Linear Chandelier) and `WS` (Wall Sconce) which appear only in `MB-REEL` table entries
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
> These apply to every run. Agents break them often, so they stay in this always-loaded file.
> - **Brand-new row every run.** Scrape fresh from Akeneo, verify, dedup, insert a new row, and process it end-to-end until `Complete`/`Done`. **Never** query, loop over, or re-run existing, leftover, or incomplete rows. The only exception is an explicit `--record-id <rec_id>` passed by a developer.
> - **Shopify Active & Published, exact match only.** `enabled=True` in Akeneo is not enough. Skip anything that is Draft, Inactive, Archived, or Unlisted on `homecartel.net/products.json`. Match on exact normalized SKU or exact title (or pre-pipe title). Substring matching is banned.
> - **Base-wide dedup.** Check SKU and item name against all 60+ tables (`fetch_all_base_existing_identities`) before inserting.
> - **Category routing.** Linear and cluster chandeliers go to their own tables, not standard chandelier ones.

Full mechanics (skip-log format, Shopify cache/crawler behavior and the partial-cache guarantee, room-slot compatibility): **`.agents/skills/fresh-row-scrape/SKILL.md`**.

---

## 6. Local Pillow Rendering Guidelines (Zero API Cost)

All layout rendering is local Pillow in **`content_automation/overlay.py`** (plus `item_tagger.py` for YOLO name tags). There is no `text_overlays/` package. Canvases: Story `1080 x 1920`, Feed `1080 x 1350`, Ad Cover `1080 x 1080` (+ 9:16 twin). Fonts come from `content_automation/fonts/` (Poppins), the logo is `assets/homecartel_logo.png`, and coordinates come from `JSON Prompts/<Format>/*.json`.

Font sizes, logo boxes, watermark templates, shadows, auto-scaling and how to preview: **`.agents/skills/pillow-layout/SKILL.md`**.

---

## 7. Complete Subtab & Pipeline Inventory

### Story Pipelines (10 Subtabs, 9:16 Ratio)
1. **CTA Story** ([`docs/stories/CTA_STORY.md`](docs/stories/CTA_STORY.md), prefix: `CTA-STORY`) — 5 tables (Chandelier, Pendant, Cluster, Table Lamp, Floor Lamp). Single slide + headline + CTA watermark.
2. **Tips & Educational Story** ([`docs/stories/TIPS_AND_EDU_STORY.md`](docs/stories/TIPS_AND_EDU_STORY.md), prefix: `TNE-STORY`) — 6 tables. Single slide + YOLO item name tag + local-Pillow "Style Tip of the Day" card (Poppins ExtraBold title, Claude-written tip via Fal; Phase 5 does not use Nano Banana).
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

### Reel Pipelines (8 Pipelines, 9:16 Video)
1. **Day & Night Reel** ([`docs/reels/DAY_NIGHT_REEL.md`](docs/reels/DAY_NIGHT_REEL.md)) — 18-second day-to-night timelapse video with AI jazz audio.
2. **Product Closeup Reel** ([`docs/reels/PRODUCT_CLOSEUP_REEL.md`](docs/reels/PRODUCT_CLOSEUP_REEL.md)) — 15-second product inspection reel.
3. **Before & After Reel** ([`docs/reels/BEFORE_AND_AFTER_REEL.md`](docs/reels/BEFORE_AND_AFTER_REEL.md)) — 15-second transformation reel.
4. **Moodboard Reel** ([`docs/reels/MOODBOARD_REEL.md`](docs/reels/MOODBOARD_REEL.md)) — 15-second swatch and texture video reel.
5. **Style Reel Slideshow** ([`docs/reels/STYLE_REEL_SLIDESHOW.md`](docs/reels/STYLE_REEL_SLIDESHOW.md)) — Fast-paced lifestyle video slideshow.
6. **1 Product, 3 Styles Reel** ([`docs/reels/ONE_PRODUCT_THREE_STYLES_REEL.md`](docs/reels/ONE_PRODUCT_THREE_STYLES_REEL.md)) — Chandelier-only blended photo Reel with 5s, 4s, 4s holds and 5s outro.
7. **One at a time Lights Reel** ([`docs/reels/ONE_AT_A_TIME_LIGHTS_REEL.md`](docs/reels/ONE_AT_A_TIME_LIGHTS_REEL.md), prefix: `OATL-REEL`) — ~11-second silent bedroom reel: 3 fresh fixtures (Table Lamp, Ceiling Mounted, Pendant) blended into one Krea interior, three progressive "only this light is ON" Nano Banana Pro variations, then local FFmpeg crossfades + branded outro. Table `tblJpEtBudQZda319`.
8. **Sketch to Real Reel** ([`docs/reels/SKETCH_TO_REAL_REEL.md`](docs/reels/SKETCH_TO_REAL_REEL.md), prefix: `STR-REEL`) — ~11-second reel: hand-drawn outline of a Krea room animates line by line (local Auto Draw + FFmpeg) into the Nano Banana Pro blended interior, with cover and branded outro. Studio Reel subtab 7 "Sketch to Real" (route `/api/sketch-to-draw-reel/*`); Chandelier `tblUFR6OvFQaHnG1V` and Pendant `tblSALsUd5MXXnkp6` are runnable.

### Ad Cover Pipeline (1 Pipeline, 1:1 Square + 9:16 Story)
1. **Ad Cover** ([`docs/ads/AD_COVER.md`](docs/ads/AD_COVER.md), prefix: `ADC-ADS`) — Standalone 4th top-level Studio tab (not a sub-tab family): one run button per fixture. All 9 fixtures are fully runnable with dedicated Airtable tables (Chandelier: `tblwIsDGZBPuYJV2Z`, Floor Lamp: `tbl27FKuDUD4FdJUR`, Table Lamp: `tblk3RfFqawHZ5Wrk`, Cluster Chandelier: `tbltouegkjgQwdr1u`, Pendant Light: `tbl99Cwda2Xn93giT`, Wall Light: `tblUO5nybG9fIkhTT`, New Collection: `tbluMexgzcWE1pDZJ`, On Sale Designs: `tbleQIVBooVazAyk3`, On Stock Designs: `tblX7tpTJhfH0UXmm`). 7 phases: highest-priced newest Akeneo fixture → Krea 1:1 interior → Claude blending prompt → Nano Banana Pro blend → **local Pillow** composite of the transparent ad-cover overlay → Nano Banana Pro **9:16 extension** of that blend → **local Pillow** composite of the 9:16 story overlay (tagline + logo baked into PNG overlays, zero API cost for typography). One run produces **both** the 1:1 `Ad Cover Converted Image` and the 9:16 `Ad Cover Converted Image Story`; `Complete` is written by Phase 7 only.

### Banner Set (the Studio's Banner tab: Christmas + Sale + third banner on ONE row)
One Studio run (and `python generate_banner_set_pipeline.py`) scrapes 10 fresh products once (Christmas: CH, PE, FL, TL, WL; Sale: three pendants DP, KA, KB; third banner: two table lamps BA, BB), creates **one** brand-new Airtable row, and makes all three banners on it: the Christmas banner (phases 2-6, `Banner with Text`), the Sale banner (its phases 2-6, shown as 7-11 in the Studio, `Sale Banner`) and the third banner (1800x600: a 951 px panel in the Sale banner's colour + a Krea modern Christmas bedroom with 2 blended table lamps, its phases 2-5 shown as 12-15, `Third Banner`; doc [`docs/banners/THIRD_BANNER.md`](docs/banners/THIRD_BANNER.md)). `Done` is written only after the third banner. Neither the Sale nor the third banner adds a row of its own in this flow. Doc: [`docs/banners/BANNER_SET.md`](docs/banners/BANNER_SET.md). The sections below describe each banner's phases.

### Christmas Banner Pipeline (1 Pipeline, 21:9)
1. **Christmas Banner** ([`docs/banners/CHRISTMAS_BANNER.md`](docs/banners/CHRISTMAS_BANNER.md), prefix: `XMS-BANNER-ALL`, table via `AIRTABLE_TABLE_ID_CHRISTMAS_BANNER`) — Standalone 5th top-level Studio tab (`generate_christmas_banner_pipeline.py`, `UI Control/routes/christmas_banner.py`). 6 phases: 1 fresh Akeneo item per type (chandelier, pendant, floor lamp, table lamp, wall light) → Krea **2.35:1** (krea-2 has no 21:9) modern Christmas living room (moodboard `b5ffdcbb-192e-4528-8d86-d1a4cf496887`) → Claude multi-fixture blending prompt → Nano Banana Pro **21:9** blend of all 5 fixtures → Claude Sonnet 5 title + subtitle → **local Pillow** overlay (white Poppins Medium 81.8 pt title and Regular 46.3 pt subtitle, tight tracking, soft shadow) into `Banner with Text`. Table `tblgNk1Tp6qKUcduw`.

### Promo Banner (standalone CLI, 1080x1920 9:16)
**Promo Banner** ([`docs/banners/PROMO_BANNER.md`](docs/banners/PROMO_BANNER.md), `generate_promo_banner_pipeline.py`) — the monthly 9:16 "Your Story" promo that used to be rebuilt in Canva. Takes the main (wide) banner as a **local file** (`--banner`), has Nano Banana Pro extend it to a 9:16 background, has Claude Sonnet 5 (via fal) write a 3-5 word tagline from the banner's name (a failed call never fails the run), then **local Pillow** (`overlay.py::draw_promo_banner`) draws the 890 px logo, the tagline, a huge `10%OFF` / `15%OFF` and the date line (from the promotions calendar, with an en dash). Output `output/promo_banner/promo_<MON-YYYY-NNOFF>_9x16.png`. No Airtable row, no Studio card.

### Sale Banner Pipeline (1 Pipeline, 1800x600)
1. **Sale Banner** ([`docs/banners/SALE_BANNER.md`](docs/banners/SALE_BANNER.md), shares table `tblgNk1Tp6qKUcduw` with the Christmas banner, rows told apart by `Category = Sale Banner`) — second sub-tab of the Studio **Banner** tab (`generate_sale_banner_pipeline.py`, `UI Control/routes/sale_banner.py`). 6 phases: 3 pendant lights from Akeneo (1 for the dining room, 2 for the kitchen island) → Krea 4:5 modern Christmas dining room (left) and kitchen (right) → Claude blending prompt per room → Nano Banana Pro 4:5 blend per room → percentages and captions (dates with the year) from the promotions calendar (`content_automation/promo_calendar.py`, `assets/calendar_config.json`) plus a panel hex colour suggested by Claude from the two blends (`Sale Panel Color`) → **local Pillow** composite (interiors either side of the coloured panel, Poppins text fitted to the Canva sample). Shared helpers live in `content_automation/banner_common.py`.

Studio moodboard/prompt pencils, persistent config keys, and completed count behavior are mapped in [`docs/UI_CONTROL_CONFIG.md`](docs/UI_CONTROL_CONFIG.md). Use the `C` badge alone for completed totals; `P` includes posted, pending, and processing rows. The optional Studio PIN is `DASHBOARD_PIN`.

---

## 8. Adding a New Table, Subtab, Pipeline or Fixture

Follow **`.agents/skills/add-new-pipeline/SKILL.md`**. It covers the generator shape, `TABLE_PREFIX_MAP`, the required Airtable fields, the blueprint endpoints and `api_server.py` registration, the data-driven frontend wiring (`fixtures.ts`, `pipelines.ts`, `types/index.ts`, `usePipelineData.ts`), the build, and verification. Skipping a layer usually fails silently, so go through the whole checklist.

### Docs to update when you change X

Read this file (auto-loaded) plus only the doc for the pipeline you touch — do **not** read every `.md`. But when you change the following, update the matching docs so this file stays trustworthy:

| You changed… | Also update |
| :--- | :--- |
| A new Ad Cover fixture | `docs/ads/AD_COVER.md`, `docs/README.md` §4, this file §4A + §7, `docs/UI_CONTROL_CONFIG.md`, `README.md`, `UI Control/README.md`, `.env.example` |
| A new pipeline / subtab | its own `docs/<format>/*.md`, this file §2 tree + §7 + §9, `docs/README.md`, `README.md`, `UI Control/README.md`, `docs/UI_CONTROL_CONFIG.md` |
| A new env key or table ID | `.env.example`, `content_automation/foreign_key.py`, the pipeline doc's env table |
| The frontend layout | `UI Control/README.md` and this file's §2 tree |
| A design decision that isn't obvious from the diff | a note in `docs/memory/decisions/` (see §10) |
| The git / push / deploy workflow (branches, Dockerfile, CI, hooks) | `docs/GIT_PUSH_AND_DEPLOY.md`, `.agents/skills/ship-to-railway/SKILL.md`, and §11 of this file |
| An agent skill (added, removed, or repurposed) | this file §12 and `docs/SKILLS_GUIDE.md` |

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

# Run the Banner Set: Christmas + Sale + third banner on ONE new row (flags: --table-id --style --moodboard-id --interior-prompt --month --year --dining-moodboard-id --kitchen-moodboard-id --dining-prompt --kitchen-prompt --panel-color --third-moodboard-id --third-prompt --third-title --third-subtitle)
python generate_banner_set_pipeline.py

# Promo Banner (9:16, local file in/out, no Airtable; flags: --banner --discount 10|15 --month --year --banner-name --tagline --date-text --resolution --dry-run)
python generate_promo_banner_pipeline.py --banner banner.jpg --discount 10 --month SEP --year 2026 --dry-run

# Run Christmas Banner (21:9; flags: --table-id --record-id --moodboard-id --interior-prompt --style --text-only --from-phase --only-phase)
python generate_christmas_banner_pipeline.py

# Run Sale Banner (1800x600; flags: --table-id --record-id --style --month --year --dining-moodboard-id --kitchen-moodboard-id --dining-prompt --kitchen-prompt --panel-color --text-only --from-phase --only-phase)
python generate_sale_banner_pipeline.py

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

# Run the One at a time Lights Reel (thin alias; --phase all|scrape|generate, --max-rows N, --record-id, --force, --with-music)
python run_one_at_a_time_lights_reel.py --phase all --max-rows 1

# Run the Ad Cover pipeline — modes: scrape|interior|prompt|blend|conversion|story-blend|story-conversion|all
# One --mode all run produces BOTH the 1:1 cover and the 9:16 Story twin; see docs/ads/AD_COVER.md §7
python generate_ad_cover_pipeline.py --fixture chandelier --mode all --max-items 1

# Unit tests (stdlib unittest; live in tests/)
python -m unittest discover tests

# Test API Endpoints & Airtable Counts
python scratch/test_feed_apis.py
python scratch/audit_all_feed_subtabs.py

# Ad Cover schema provisioning (idempotent) + row/image verification (read-only)
python scratch/ensure_ad_cover_fields.py --table-id tblwIsDGZBPuYJV2Z
python scratch/_verify_ad_cover_row.py [record_id]
python scratch/_verify_ad_cover_image.py [record_id]
```

---

## 10. Operations, Scheduling & Project Memory

### Publishing is a separate concern from generation
Content generation (all phases, §3) ends with an Airtable row at `Status: Complete/Done`. **Actually posting to Instagram is a separate, always-on worker**: [`run_auto_post_scheduler.py`](run_auto_post_scheduler.py), documented in [`docs/AUTO_POST_SCHEDULER.md`](docs/AUTO_POST_SCHEDULER.md). It polls `http://localhost:3000/api/schedules/runner` — **an API that does not exist anywhere in this repository**. That scheduling/publishing logic lives in a separate application (port 3000, not the port-5200 Studio). Do not go looking for scheduling logic in this codebase; look here only for the polling worker and its `CRON_SECRET`.

### Maintenance & diagnostic scripts
Root scripts that migrate/backfill Airtable data, tag furniture in room photos, manage Zoho asset folders, or sanity-check Akeneo credentials are catalogued in [`docs/OPERATIONS_AND_UTILITIES.md`](docs/OPERATIONS_AND_UTILITIES.md) — check there before assuming a `run_*` / `scrape_*` script you don't recognize is undocumented dead code.

### Project memory protocol
[`docs/memory/`](docs/memory/) holds incidents, design decisions, and architecture notes that aren't derivable from reading the code alone (see [`docs/memory/README.md`](docs/memory/README.md)). It's meant to be opened as an Obsidian vault rooted at `docs/`.

- **Before debugging a pipeline failure** (especially a Shopify/Akeneo cross-check failure or anything resembling a past incident), check `docs/memory/incidents/` first — it may already be root-caused. The **`.agents/skills/debug-pipeline-run/SKILL.md`** skill maps the recurring symptoms to their known causes.
- **After resolving anything non-trivial** — a failure that took real investigation, or a design decision made without an obvious paper trail — add a short note under `docs/memory/incidents/` or `docs/memory/decisions/`. A few sentences is enough. This applies to AI agents working in this repo, not just humans.

---

## 11. Git, Deployment & Push Protocol for AI Agents

The always-on rules are below. The step-by-step sequence is in **`.agents/skills/ship-to-railway/SKILL.md`**, and the full walkthrough with failure handling is [`docs/GIT_PUSH_AND_DEPLOY.md`](docs/GIT_PUSH_AND_DEPLOY.md).

- **Commit/push only when the user asks.** Finishing a task is not a push request.
- **Right repo.** `git remote -v` must show `https://github.com/homecartelmarketing-lgtm/marketing-automation.git`. Never run git from sibling folders (e.g. `Downloads/Marketing Output UI`).
- **No secrets.** Never stage `.env`, `.env.*` (except `*.example`), keys, tokens, or customer data. Model weights, `node_modules/`, `output/`, and `tmp/` stay ignored. Stage named paths after reading `git status`.
- **Compile and test first.** Run `python -m py_compile <changed files>` and `python -m unittest discover tests`. Never push code that fails either.
- **Rebuild `UI Control/dist/`** whenever `UI Control/src/` changed. Railway serves the committed `dist/` as-is.
- **Conventional commits:** `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.
- **Two branches.** Develop and push on `marketing-automation`. `main` is the Railway production deploy, so tell the user before fast-forwarding and pushing it (`git merge --ff-only marketing-automation`), then switch back to `marketing-automation`.
- **Never** force-push, `reset --hard`, amend or rebase pushed commits, or use `--no-verify`. Undo a bad deploy with `git revert`.

---

## 12. Integrated Workspace Agent Skills (`.agents/skills/`)

The workspace includes 11 version-controlled agent skills in `.agents/skills/` (whitelisted in `.gitignore`). Load the matching skill when a task starts. Each one holds the detail this file only summarizes.

**Repo workflow skills (specific to this codebase):**

1. **`add-new-pipeline`** — Full wiring checklist for a new pipeline, subtab, table, or fixture: generator shape, FK map, schema, blueprint, frontend config, build, verification, docs.
2. **`ship-to-railway`** — Commit/push/deploy sequence: pre-flight, secret scan, compile + tests, `dist/` rebuild, `marketing-automation` push, confirmed fast-forward of `main`.
3. **`debug-pipeline-run`** — Triage for failed, stuck, or wrong-output runs: maps recurring symptoms to past incidents, narrow `--record-id` reproduction, regression tests, incident notes.
4. **`pillow-layout`** — Local Pillow rules: canvas sizes, Poppins fonts, logo boxes, watermarks, shadows, Canva coordinates, auto-scaling, previews.
5. **`fresh-row-scrape`** — Brand-new-row rule, strict Shopify Active & Published matching, cache/crawler behavior, base-wide dedup, category routing.

**General skills (installed from external sources):**

6. **`airtable-automation`** — Schema enforcement, batch updates (10-records-per-call max), and `update_record` convenience patterns across 60+ tables.
7. **`prompt-optimizer`** — Claude Sonnet 5 Vision JSON prompt templates, system instructions, and Krea diffusion prompt tuning.
8. **`python-testing-patterns`** — Unittest isolation, mocking external AI APIs (Akeneo, Fal, Krea), and pre-commit checks (`python -m unittest discover -s tests -p "test_*.py"`).
9. **`vercel-react-best-practices`** — React hook composition (`usePipelineData`, `usePipelineRunner`, `useQueue`), memoization, and Web Studio performance.
10. **`vite`** — Production Vite bundling (`UI Control/dist/`), asset hashing, and SPA routing integration with Flask.
11. **`git-guardrails-claude-code`** — Safety hooks blocking destructive git commands (`git push --force`, `git reset --hard`, accidental wipeouts).

See [`docs/SKILLS_GUIDE.md`](docs/SKILLS_GUIDE.md) for when to use each one.
