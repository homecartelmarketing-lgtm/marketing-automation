# HomeCartel Marketing Automation — UI Control Dashboard

The **UI Control Dashboard** is a unified visual command center and operations hub for the HomeCartel marketing automation system. It bridges Airtable bases, Akeneo PIM product catalogs, AI vision models (Krea, Claude Sonnet 5, Fal Nano Banana Pro, Grok Video), and local Pillow/FFmpeg processing engines into a clean, real-time web dashboard.

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
   - Organized into **Story** (10 subtabs), **Feed** (7 subtabs), and **Reel** (6 subtabs).

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
