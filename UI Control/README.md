# HomeCartel Marketing Automation — UI Control Dashboard

The **UI Control Dashboard** is a unified visual command center and operations hub for the HomeCartel marketing automation system. It bridges Airtable bases, Akeneo PIM product catalogs, AI vision models (Krea, Claude Sonnet 5, Fal Nano Banana Pro, Fal Kling Video), and local Pillow/FFmpeg processing engines into a clean, real-time web dashboard.

---

## 🏗️ Architecture Overview

The system consists of two tightly integrated components:

1. **Backend API Server (`api_server.py`)**:
   - Built on Flask + Python 3.12.
   - Listens on `http://localhost:5200`.
   - Dispatches automation workflows asynchronously and streams live logs.
   - Provides REST endpoints for Airtable inventory scanning, status aggregation, and batch triggering.
   - Enforces PIN-based session authentication when `DASHBOARD_PIN` is configured.

2. **Frontend Single Page Application (`UI Control/`)**:
   - Built with React 18, TypeScript, Tailwind CSS, and Lucide React icons.
   - Bundled and served via Vite / Flask static files.
   - Source layout (`src/app/`): `App.tsx` is a thin shell; `constants/fixtures.ts` + `constants/pipelines.ts` hold every fixture and per-pipeline config; `hooks/` (`usePipelineData`, `usePipelineRunner`, `useQueue`) hold state and polling (`useQueue` is the **only** run-status poller; `usePipelineRunner` just starts/stops runs); `types/index.ts` defines `PipelineType`; `components/planning/` and `components/modals/` hold the UI. Adding a subtab means editing the constants, types and hooks, not `App.tsx` (see `AGENTS.md` §8).
    - Organized into **Story** (10 subtabs), **Feed** (7 subtabs), **Reel** (9 subtabs), **Ad Covers** (standalone top-level tab), and **Banner** (standalone top-level tab with one sub-tab, "Banner Set" at `/api/christmas-banner/*`: one Run is the Banner Set, 15 phases, and makes the Christmas, Sale and third banners on ONE Airtable row via `generate_banner_set_pipeline.py`; `/api/sale-banner/*` remains for API/CLI use only).

---

## 🌗 Light / Dark Theme

The header has a theme button (Light / Dark / System). The choice is stored in the browser (`localStorage` key `hc-studio-theme`, default Light) and handled by `next-themes` (`src/main.tsx`), which toggles the `dark` class on `<html>`. Components keep their normal Tailwind classes; `src/styles/dark-palette.css` remaps the gray/slate scales and the tint/text shades of the colour families under `.dark`, and `bg-card` replaces `bg-white` so surfaces follow the theme. Anything that must stay dark in both themes (the log terminal in `LogStream.tsx`) uses fixed hex colours.

---

## 🔐 Security & Access Control

Editable settings and run actions use the dashboard PIN when one is configured:
- **Environment Key**: `DASHBOARD_PIN` in `.env`
- **Session**: Retained in browser session storage for seamless tab navigation.

---

## 📑 Dashboard Navigation & Supported Tabs

### 1. Story Workspace (9:16 vertical, 1080 x 1920 px)
- **CTA Story**: 5 categories (Chandelier, Pendant, Cluster, Table Lamp, Floor Lamp).
- **Tips & Educational Story**: 6 categories (Pendant, Floor Lamp, Chandelier, Ceiling Mounted, Table Lamp, Cluster).
- **Collection Category Story**: 5 categories (Pendant, Wall Light, Chandelier, Floor Lamp, Cluster).
- **Day & Night Story**: 5 categories (Chandelier, Pendant, Floor Lamp, Table Lamp, Cluster).
- **Moodboard Story**: 3 categories (Chandelier, Pendant, Floor Lamp).
- **Product Closeup Specs Story**: Technical specifications card for Chandeliers.
- **Style This Story**: 2 categories (Chandelier, Floor Lamp) with interactive voting cards and color reaction pills.
- **Myth & Fact Story**: 3 categories (Chandelier, Floor Lamp, Pendant) with debunking sequences.
- **Product Closeup Description Story**: 6 categories with narrative copy.
- **This or That Story**: 6 categories with dual-product voting cards.

### 2. Feed Workspace (4:5 vertical, 1080 x 1350 px)
- **Tips & Educational Feed**: 4 categories (Chandelier, Pendant, Floor Lamp, Cluster).
- **Collection Category Feed**: 5-Room whole-home coordinated collection set.
- **Moodboard #1 Feed**: 4-slide editorial carousel (Blended, Watermark, Swatches, Macro).
- **Moodboard #2 Feed**: 2-slide architectural flat-lay carousel across 4 categories.
- **1 Product 3 Styles Feed**: 3 room styles per product across 3 categories.
- **Day & Night Feed**: Comparative daylight and night illumination contrast.
- **Product Showcase Feed**: Luxury commercial studio table lamp showcases.

### 3. Reel Workspace (9:16 vertical video, 1080 x 1920 px)
- **Day & Night Reel**: 3 categories (Chandelier, Pendant, Floor Lamp) with 15s Fal Kling timelapse, jazz audio, and branded outro.
- **Product Closeup Reel**: 4-product Table Lamp slideshow with Poppins titles, Ken Burns animation, and branded outro.
- **Before & After Reel**: 2 categories (Chandelier, Pendant) showcasing raw room to styled interior transformation.
- **Moodboard Reel**: 7 categories cycling between 4 blended room views, texture swatches, and lighting details with luxury audio.
- **Style Reel Slideshow**: 5-room whole-home lifestyle slideshow tour across 4 fixture categories.
- **1 Product 3 Styles Reel**: Single chandelier blended into 3 distinct interior styles (5s, 4s, 4s holds + 5s outro).
- **One at a time Lights Reel**: ~11s silent bedroom reel; 3 fixtures (Table Lamp, Ceiling Mounted, Pendant) are lit one at a time via progressive Nano Banana Pro variations, then all together, joined by local FFmpeg crossfades and a branded outro.
- **Sketch to Real Reel**: 2 runnable categories (Chandelier, Pendant); a hand-drawn outline of the Krea room animates line by line into the photorealistic lit interior (local Auto Draw + FFmpeg), with cover, Fal AI ElevenLabs luxury background music, and branded outro. Served by `/api/sketch-to-draw-reel/*`, which always runs `generate_sketch_to_real_reel_pipeline.py`.
- **House Tour Reel**: 11-room organic-modern/Japandi home tour guided by reference-video clips (Claude JSON → Krea); Nano Banana Pro blends with YOLO-World Poppins tags, Fal Kling 3s pan clips, Fal AI ElevenLabs music, and branded outro assembled with local FFmpeg crossfades. Served by `/api/house-tour-reel/*`, which runs `generate_house_tour_reel_pipeline.py`.

### 4. Ad Covers Workspace (1:1 1080 x 1080 px + 9:16 Story 1080 x 1920 px)
- **Standalone 4th Top-Level Tab**: Dedicated paid-creative generator producing twin deliverables per run.
- **9 Fully Runnable Fixture Categories**: Chandelier, Floor Lamp, Table Lamp, Cluster Chandelier, Pendant Light, Wall Light, New Collection, On Sale Designs, and On Stock Designs each have a dedicated Airtable table, live 5-badge status pills, and interactive prompt/moodboard editor pencils.
- **7-Phase Flow**: Blends the highest-priced active fixture from Akeneo into a Krea room interior, composites the local 1:1 ad cover overlay, then extends to 9:16 Story ratio via Fal Nano Banana Pro and composites the matching story twin (zero API typography cost).

---

## 🏷️ 5-Status Single-Character Badges

The UI visualizes the 5 lifecycle states using distinctive single-character status badges:

| Badge | Full Status Name | Visual Pill Color | Operational Meaning |
| :---: | :--- | :--- | :--- |
| **`P`** | **Posted / Processing** | Sky blue | Posted, pending, processing, or in progress. |
| **`S`** | **Scheduled** | Purple | Scheduled or Schedule. |
| **`D`** | **Discarded** | Rose | Discard or Discarded. |
| **`FM`**| **For Manual / Revision**| Amber | Manual review or minor revision. |
| **`C`** | **Complete / Done** | Emerald | Complete, Completed, Done, or already attached a room interior. |

---

## 🚀 Running & Developing Locally

### 1. Launch the Backend API Server
From the project root:
```powershell
cd "UI Control"
python api_server.py
```
*The server starts on `http://localhost:5200`.*

### 2. Frontend Development Server (Optional)
If modifying React/TypeScript source files in `UI Control/src/`:
```powershell
cd "UI Control"
npm install
npm run dev
```

### 3. Production Build
To rebuild the frontend bundle served by Flask:
```powershell
cd "UI Control"
npm run build
```

---

## 🛠️ API and Editable Settings

Each pipeline has a blueprint under `routes/` with `GET /counts`, `GET /status`, `POST /run`, and `POST /stop`. Pipelines with moodboard and interior-prompt pencils also expose `POST /moodboard` and `POST /prompt`. The UI derives those edit URLs from the active pipeline's run URL, so every editable Story, Feed, and Reel uses the same request flow.

Saved edits are stored in `output/config_overrides.json` and `.env`, then made available to child runners. The submitted value takes precedence over the saved value for that run; otherwise the runner uses the saved fixture setting. Prompt values with `#`, quotes, or line breaks are quoted safely in `.env`. See [the configuration map](../docs/UI_CONTROL_CONFIG.md) for runner behavior and exact settings.

The format, subtab, header, and fixture counts all use live Airtable `C` status totals. `P` rows are shown separately and never counted as completed. A dash means the count has not loaded; a confirmed zero means Airtable returned zero completed rows. On a count request failure, the API reports an error instead of fabricating a zero.

---

## 🚦 Queue Manager & Row Inspector

### 1. In-Memory FIFO Job Queue (`routes/queue_manager.py`)
Studio manages concurrent job execution via a serialized in-memory FIFO queue guarded by thread locks:
- **Endpoints**:
  - `GET /api/queue/status`: Returns current queue state (`active_job`, `pending_queue`, and `history` of the last 30 completed jobs).
  - `POST /api/queue/enqueue`: Adds a new pipeline execution request to the pending queue.
  - `POST /api/queue/cancel`: Cancels a pending job from the queue.
  - `POST /api/queue/stop-current`: Aborts the currently executing active job.
  - `POST /api/queue/clear`: Empties all queued pending jobs.
- **Queue Worker Daemon**: Runs in a background thread, popping jobs in FIFO order, dispatching execution over local HTTP to the blueprint's `/run` endpoint (override values that are `null` are omitted so nothing is saved as the text "None"), and monitoring progress every 1.5s until completion. The phase shown never moves backwards.
- **Content Calendar import (`routes/calendar.py`)**: RunCenter **Calendar** button (`components/planning/CalendarImportModal.tsx`) uploads a Content Calendar workbook; `POST /api/calendar/preview` shows which `TO DO` slots would run (pointer copy, nothing consumed) and `POST /api/calendar/enqueue` enqueues them via `/api/queue/enqueue`. Fixture pointer persists in `output/calendar_fixture_state.json` (gitignored); idea→pipeline map is `assets/calendar_pipeline_map.json`.
- **Run Center (frontend)**: `components/planning/RunCenter.tsx` is a slim light-theme status bar fixed at the bottom of the page (it never covers the cards) that opens a right-hand panel with **Running** (phase steps from each pipeline's `phaseSummary`, progress, live log, Stop), **Queue** (upcoming jobs, remove/clear) and **History** tabs. It replaces the old floating queue dock, the "Background Processing" banner and the inline log console.
- **Frontend status**: the UI reads run status, phase and logs only from `/api/queue/status` (one poller in `hooks/useQueue.ts`), skips identical polls to avoid re-render flicker, and drops a run it still shows as running after ~4 consecutive empty polls (server restarted or lost it).
- **Deployment**: the queue and every pipeline route keep state in memory, so production must run a single gunicorn worker (`--workers 1`, see `AGENTS.md` §3 and the Dockerfile); two workers split the queue and runs look stuck.

### 2. Row Inspector & Airtable Deep Links (`routes/rows.py`)
- **Endpoint**: `GET /api/rows?table_id=<table_id>`
- Fetches recent records for the selected fixture card, parsing field values, image attachments, foreign keys, and statuses.
- Provides direct deep links into the Airtable web application:
  `https://airtable.com/{base_id}/{table_id}/{record_id}`

