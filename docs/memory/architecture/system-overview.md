---
tags: [architecture, overview]
---

# System overview: how the pieces fit together

A short map of the real data flow, for orientation before diving into a specific pipeline doc under [`docs/stories/`](../../stories/), [`docs/feeds/`](../../feeds/), [`docs/reels/`](../../reels/), or [`docs/ads/`](../../ads/).

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

Every pipeline (Story/Feed/Reel/Ad Cover) is a variation on this shape — see `AGENTS.md` §7 for the full subtab inventory and `docs/README.md` for per-pipeline detail.

**Ad Cover is the one pipeline that deviates**, in four ways worth knowing before reading the generic shape above:

- It runs **7 phases, not 5–6**, and one run produces **two deliverables**: the 1:1 `Ad Cover Converted Image` and its 9:16 `Ad Cover Converted Image Story` twin.
- Its API cost profile is **1 Krea call + 2 Fal image calls** (the second Fal call is the Nano Banana Pro 9:16 extension of the already-blended square image, not a fresh blend).
- **`Complete` is written by Phase 7 only**, because Airtable `Status` is a `singleSelect` that overwrites — writing it earlier would make the story branch's failure invisible on the card. See [[../decisions/ad-cover-complete-status-belongs-to-phase-7]].
- Phase lines stream as `[Phase N/7]`, and `detect_phase()` parses the number first rather than matching keywords, since two phases here share vocabulary ("blend", "converted").

## 2. Dashboard (observing & triggering the above)

`UI Control/api_server.py` — Flask app on **port 5200** — registers one Blueprint per pipeline under `UI Control/routes/`; Ad Covers is one Blueprint covering nine fixture cards rather than one per subtab. The React frontend (`UI Control/src/app/`; per-pipeline config lives in `constants/pipelines.ts`, not in `App.tsx`) shows run status from a single poller, `hooks/useQueue.ts`, which reads `/api/queue/status`; the queue worker in `routes/queue_manager.py` copies each pipeline's `/status` payload (live stdout from `pipelineState.logs`, current phase) into that view. All of this state lives in process memory, so production must run one gunicorn worker (see [[../incidents/2026-10-01-railway-two-gunicorn-workers-split-queue]] and [[../incidents/2026-09-30-studio-run-flicker-two-pollers]]). This is where [[../incidents/2026-09-17-floor-lamp-shopify-draft-inactive]] was actually diagnosed — the `/status` endpoint's in-memory log buffer had the detail the UI wasn't (at the time) rendering after a failure.

`launch_studio_cloudflare.py` can tunnel this same port-5200 dashboard to a public `*.trycloudflare.com` URL for sharing without deploying anywhere (see [`docs/CLOUDFLARE_TUNNEL_GUIDE.md`](../../CLOUDFLARE_TUNNEL_GUIDE.md)).

## 3. Publishing (after content is generated) — ⚠️ crosses outside this repo

`run_auto_post_scheduler.py` polls `http://localhost:3000/api/schedules/runner` every 60s and publishes due items to Instagram. **Port 3000 is a separate application, not present in this repository** — grepping the whole codebase for `schedules/runner` turns up only the one poller script. See [`docs/AUTO_POST_SCHEDULER.md`](../../AUTO_POST_SCHEDULER.md) for what's known and what to check if publishing stalls.

This is a real architectural seam worth remembering: **this repo owns product sourcing → content generation → Airtable state.** A *different* app (likely the team's Next.js "Content Planning Dashboard") owns the actual scheduling/publishing decision. If you're debugging "why didn't this post," the answer may not be in this codebase at all.

## 4. Data maintenance (keeps the above healthy, runs ad hoc not continuously)

Airtable schema migrations, tagging, and Zoho asset folder upkeep — see [`docs/OPERATIONS_AND_UTILITIES.md`](../../OPERATIONS_AND_UTILITIES.md) for the full catalog of these scripts.
