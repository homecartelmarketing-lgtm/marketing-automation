# Auto Post Scheduler

> Publishes finished Stories, Feeds, and Reels to Instagram at their scheduled Philippine Time (PHT).

- **Script**: [`run_auto_post_scheduler.py`](../run_auto_post_scheduler.py)
- **Not covered elsewhere**: this worker isn't part of the Story/Feed/Reel generation pipelines documented under `docs/stories/`, `docs/feeds/`, `docs/reels/` — it runs *after* content is generated, as a separate always-on process.

## What it does

Every 60 seconds (or once, with `--once`), it sends an authenticated `GET` to a scheduling API and prints what happened:

```python
API_URL = "http://localhost:3000/api/schedules/runner"
headers = {"Authorization": f"Bearer {CRON_SECRET}"}
```

The response tells it which scheduled items were just published, which are still pending, and which errored — the worker itself contains no publishing logic; it's a thin poller.

## ⚠️ External dependency — not in this repository

`http://localhost:3000/api/schedules/runner` is **not implemented anywhere in this repo** (confirmed: no route, no handler, no reference to `schedules/runner` exists outside `run_auto_post_scheduler.py` itself). Port `3000` is a different service from the `UI Control` Studio dashboard (which runs on port `5200`).

This means the actual scheduling logic — deciding *what* is due to post and *how* it posts to Instagram — lives in a **separate application** (almost certainly the Next.js "Content Planning Dashboard" the team also uses), not in this Python codebase. If you're debugging why nothing is posting:

1. Confirm the port-3000 app is actually running (`run_auto_post_scheduler.py` itself prints `"Waiting for UI server on http://localhost:3000 to be online..."` when it can't connect — that's expected if the other app is down, not a bug here).
2. The fix, the schema of scheduled items, and the actual Instagram publish call all live in that other codebase. This repo only owns the polling loop and the `CRON_SECRET`.

See [`docs/memory/architecture/system-overview.md`](memory/architecture/system-overview.md) for how this fits into the rest of the system.

## Configuration

| Env var | Purpose |
| :--- | :--- |
| `CRON_SECRET` | Sent as `Authorization: Bearer <CRON_SECRET>` on every poll. Must match what the port-3000 app expects. Added in commit `e1a6e52` (2026-09-11) — before that fix, the header wasn't sent and authenticated runners would reject the request. |

Timezone is hardcoded to Philippine Time (UTC+8); all "published"/"pending" timing is reported in PHT regardless of server locale.

## Running it

```bash
# Run continuously, polling every 60s
python run_auto_post_scheduler.py

# Run a single check-and-exit tick (useful for cron/Task Scheduler instead of a long-lived loop)
python run_auto_post_scheduler.py --once
```
