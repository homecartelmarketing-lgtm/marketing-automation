---
tags: [architecture, overview]
---

# System overview: how the pieces fit together

A short map of the real data flow, for orientation before diving into a specific pipeline doc under [`docs/stories/`](../../stories/), [`docs/feeds/`](../../feeds/), or [`docs/reels/`](../../reels/).

## 1. Content generation (per fixture, per pipeline)

```
Akeneo PIM (product source, enabled=True)
    │
    ▼
content_automation/scraping/products.py — select_new_products()
    dedup against: existing Airtable rows (this table) + base-wide (60+ tables)
    │
    ▼
content_automation/shopify_client.py — ShopifyCatalogIndex.contains()
    strict cross-check: candidate must be LIVE + PUBLISHED on Shopify
    see [[../decisions/strict-shopify-verification-policy]] for why this is strict
    │  (if zero candidates survive → AutomationError, pipeline stops)
    ▼
Airtable row created (Status: Standby)
    │
    ▼
Phased generation (content_automation/phased_content.py, PhasedContentRunner)
    Phase 1: scrape + create row        (Akeneo + Shopify, above)
    Phase 2+: Krea (room interiors) → Claude Sonnet 5 (prompts/headlines)
              → Fal AI Nano Banana Pro (photorealistic blending)
              → local Pillow (typography/logo/watermark, zero API cost)
    │
    ▼
Airtable row updated (Status: Complete/Done), stamped with PHT timestamp
```

Every pipeline (Story/Feed/Reel) is a variation on this shape — see `AGENTS.md` §6 for the full subtab inventory and `docs/README.md` for per-pipeline detail.

## 2. Dashboard (observing & triggering the above)

`UI Control/api_server.py` — Flask app on **port 5200** — registers one Blueprint per pipeline under `UI Control/routes/`. The React frontend (`UI Control/src/app/App.tsx`) polls each pipeline's `/status` endpoint, which returns live stdout (`pipelineState.logs`) and current phase/status. This is where [[../incidents/2026-09-17-floor-lamp-shopify-draft-inactive]] was actually diagnosed — the `/status` endpoint's in-memory log buffer had the detail the UI wasn't (at the time) rendering after a failure.

`launch_studio_cloudflare.py` can tunnel this same port-5200 dashboard to a public `*.trycloudflare.com` URL for sharing without deploying anywhere (see [`docs/CLOUDFLARE_TUNNEL_GUIDE.md`](../../CLOUDFLARE_TUNNEL_GUIDE.md)).

## 3. Publishing (after content is generated) — ⚠️ crosses outside this repo

`run_auto_post_scheduler.py` polls `http://localhost:3000/api/schedules/runner` every 60s and publishes due items to Instagram. **Port 3000 is a separate application, not present in this repository** — grepping the whole codebase for `schedules/runner` turns up only the one poller script. See [`docs/AUTO_POST_SCHEDULER.md`](../../AUTO_POST_SCHEDULER.md) for what's known and what to check if publishing stalls.

This is a real architectural seam worth remembering: **this repo owns product sourcing → content generation → Airtable state.** A *different* app (likely the team's Next.js "Content Planning Dashboard") owns the actual scheduling/publishing decision. If you're debugging "why didn't this post," the answer may not be in this codebase at all.

## 4. Data maintenance (keeps the above healthy, runs ad hoc not continuously)

Airtable schema migrations, tagging, and Zoho asset folder upkeep — see [`docs/OPERATIONS_AND_UTILITIES.md`](../../OPERATIONS_AND_UTILITIES.md) for the full catalog of these scripts.
