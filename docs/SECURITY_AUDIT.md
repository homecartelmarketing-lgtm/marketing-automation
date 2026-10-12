# Security Audit: HomeCartel Marketing Studio (marketing-automation)

## Addendum 2026-10-12 — hardening pass on `fix/house-tour-moodboard-errors` (UNCOMMITTED)

The findings below were reviewed at commit `5c91f78`. Since then the working
tree adds a hardening pass (not yet committed at time of writing). Status per
original item:

| # | Original finding | Status | Evidence |
|---|---|---|---|
| 1 | `/api/rows` open, unbounded `table_id`, cache grows | **Partial** — global `require_api_auth` gate now 401s `/api/rows` without a session/PIN/token (`api_server.py:146`), but `rows.py` has **no direct** `is_authorized` call (relies on the gate; `tests/test_rows_route.py` bypasses it), `CACHE` dict is still unbounded (10s TTL only), `table_id` still unvalidated, and `status` still interpolates into `filterByFormula` (`rows.py:81`) | `UI Control/api_server.py:146`, `UI Control/routes/rows.py:27-28,81` |
| 2 | `/api/auth/verify` brute-force, plain `==` | **Fixed** — `clamp_pin()` (256 chars) + `hmac.compare_digest` + per-IP 429 rate limit | `api_server.py:299-322`, `routes/common.py:163-170` |
| 3 | Shared-proxy-IP lockout | **Fixed (root cause)** — `ProxyFix(app.wsgi_app, x_for=1, ...)` so `remote_addr` is the real client, not the proxy | `api_server.py:83` |
| 4 | `/api/maintenance/cleanup` unauthenticated, `hours<=0` wipes | **Fixed** — POST-only + `is_authorized` + `hours = max(hours, 1.0)` (floor is 1h, not the 6h the roadmap suggested) | `api_server.py:342` |
| 5 | `max_items` uncapped on direct `/run` | **Fixed** — every `/run` parse clamped to 1..10 with 400-on-garbage; queue `/enqueue` too; single ceiling `MAX_RUN_ITEMS = 10` (`routes/common.py:70`) | ~31 sites, e.g. `cta_story.py:376`, `queue_manager.py:432` |
| 6 | Open `/status` logs + `/fixtures` | **Fixed for /api/** — the default-deny gate covers all `/status`, `/counts`, `/fixtures`, `/queue/status`; public allowlist is only `/api/health` + `/api/auth/*` + OPTIONS | `api_server.py:126-134,146` |
| DoS | 8 slow requests stall 1 worker | **Partial** — `MAX_CONTENT_LENGTH` 64 MiB (`api_server.py:142`) + per-route clamps bound cost, but no per-route concurrency limit; queue length uncapped (`queue_manager.py:484`) | open |
| DoS | `counts?refresh=1` Airtable loop | **Partial** — counts routes still honor `refresh` for any authed caller; requires login now but no admin/non-admin distinction | open |
| DoS | Calendar zip-bomb `.xlsx` | **Open** — `load_workbook(data_only=True)` without `read_only=True`, no row cap (`content_automation/calendar_import.py:17`); only the 64 MiB global body cap applies | open |
| SSRF | Queue `run/status/stop_endpoint` caller-controlled | **Fixed** — `_is_safe_local_endpoint()` allowlist (plain `/api/` paths only), 400 otherwise | `queue_manager.py:76,424` |
| Misc | CORS `*` when unset | **Fixed** — no `Access-Control-Allow-Origin` emitted unless `ALLOWED_ORIGINS` set | `api_server.py:224` |
| Misc | Clickjacking/MIME/referrer | **Fixed** — `X-Frame-Options: DENY`, `CSP frame-ancestors 'none'`, `nosniff`, `no-referrer`, `CORP: same-origin` | `api_server.py:182` |
| Misc | `?pin=` in URLs (logs/history leak) | **Fixed** — query PIN no longer read; presence raises (`_forbid_pin_in_query`) | `routes/common.py:109,231` |
| Misc | `studio_users.json` world-readable hashes | **Fixed** — `os.open(..., 0o600)` + chmod hardening | `routes/studio_auth.py` |
| Misc | CSRF on cookie session | **Fixed** — `is_same_origin()` rejects present-but-foreign `Origin` before credentials | `routes/common.py:73,196` |

Still open (not regressions — never addressed): queue has no length cap and no
`pipeline_type` allowlist; calendar XLSX has no `read_only`/row cap; cleanup
floor is 1h (roadmap said 6h); lockout is per-IP only (no per-account lockout);
`rows.py` hardening gaps listed in row 1 above. Open mode (no PIN + no
accounts) intentionally leaves `/api/*` open — same as the per-route behavior
before the gate; `tests/test_studio_auth.py::test_open_mode_when_no_pin_and_no_accounts`
pins this.

> **Original verdict — 2026-10-09, pre-hardening (superseded by the addendum above):**
> right now the Studio can be **read by anyone with the link**, **locked for the whole team by a stranger**, and **frozen by about 8 slow requests**. The paid AI runs are behind the PIN, but the PIN itself can be guessed with no limit. The new login only fixes this if it blocks _every_ /api route by default. Bolting a login page onto the current setup won't.

Reviewed commit `5c91f78` of [marketing-automation](https://github.com/homecartelmarketing-lgtm/marketing-automation) on 2026-10-09. That covers all 35 route files, the API server, the core `content_automation` library, the Dockerfile and deploy config, the frontend, the GitHub workflows and about 100 recent commits. This is a code review, not a live attack test.

* * *
## The 6 things to fix first
These are ranked by how easily someone could hurt you today. Items 1 to 4 are small patches you can ship this week, before the full login is ready.
1. **Lock** **`/api/rows`****. Anyone can dump your Airtable right now.** The file imports the PIN check but never calls it. Any caller can pass any `table_id` and get back every row, text field, thumbnail and attachment URL, with no page limit. Its cache also never clears old entries, so flooding it with random table IDs eats server memory. ( [rows.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/routes/rows.py))
2. **Rate-limit** **`/api/auth/verify`****. The PIN can be brute-forced.** It does a plain `if pin == DASHBOARD_PIN:` with no rate limit and no timing-safe compare, so a short PIN falls in minutes. ( [api\_server.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/api_server.py))
3. **Fix the lockout so one stranger can't kick out the whole team.** The lockout tracks `request.remote_addr`, and there's no ProxyFix. Behind Railway's proxy, many users probably share one IP, so 10 bad guesses can lock out everyone for 5 minutes, again and again. ( [common.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/routes/common.py))
4. **Lock** **`/api/maintenance/cleanup`****.** It needs no PIN and accepts any `hours` value. `?hours=0` or a negative number deletes every file in the temp, upload and preview folders while jobs are using them. ( [cleanup.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/content_automation/cleanup.py))
5. **Cap the size of paid runs.** Direct `/run` calls take `max_items` with no upper limit, and the cross-pipeline guard is hard-coded off (`return PipelineRunningResult(False, None)`). One House Tour row is about **56 paid provider jobs**, so anyone holding the PIN can rack up a big Krea/Fal bill. The queue's own limit of 10 doesn't apply to direct calls.
6. **Close the public logs and config endpoints.** Every pipeline's `/status` returns 150 to 300 log lines with no auth. Those logs include prompts, moodboard IDs, raw provider error bodies and signed download URLs. The `/fixtures` endpoints also expose table IDs and prompts.

* * *
## How someone could take it down (DoS)
The server runs as **1 Gunicorn worker with 8 threads and a 600-second timeout** ( [Dockerfile](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/Dockerfile)). It can't run more workers, because the queue and pipeline state live in memory. So **8 slow requests at once are enough to make the Studio stop responding**. Easy ways to get there with no login:

| Attack | Needs PIN? | Why it works | Fix |
| ---| ---| ---| --- |
| `/api/rows?table_id=…&refresh=1` in a loop | No | Fetches the whole table with no page limit, skips the cache, and fills memory | Require login, allow only known table IDs, cap pages, cap the cache |
| `/api/*/counts?refresh=1` in a loop | No | Each call starts several Airtable requests at once and skips the 10s cache. Airtable then throttles you | Require login, ignore `refresh` for non-admins |
| 10 wrong PINs | No | Shared proxy IP means everyone gets locked out | ProxyFix, plus a lockout per account instead of per IP |
| `/api/maintenance/cleanup?hours=-1` | No | Deletes files that running jobs still need | Admin only, POST only, enforce hours ≥ 6 |
| Huge or zip-bomb .xlsx sent to `/api/calendar/*` | Yes\* | There's no `MAX_CONTENT_LENGTH`, and openpyxl opens the full workbook without `read_only=True` | Set `MAX_CONTENT_LENGTH` to 5 MB, use `read_only=True`, cap the number of rows |
| Flood `/api/queue/enqueue` | Yes\* | The queue has no length limit, and the caller can make up any pipeline type or endpoint | Cap the queue at about 20, allow only known pipelines and endpoints |
| Fill the disk | Yes\* | Downloads have no size cap, and House Tour never deletes its 11 Akeneo temp files per row | Cap download bytes, call `downloaded.cleanup()` in a `finally` block |

\* "Yes" stops protecting you once the PIN leaks, and today it lives in browser localStorage and is printed in the tunnel console.

**Also do:** proxy your domain through **Cloudflare** (the free plan includes DDoS protection and one rate-limit rule) and set **spending caps** in the Krea and Fal dashboards. Your `/run` routes start a background thread and return right away, so the 600s Gunicorn timeout probably isn't needed. Try dropping it to 60s on the staging copy, so a slow client can't hold a thread for 10 minutes.

* * *
## What the login must do (or it's just a nicer PIN box)
- [ ] **Block by default.** Add one `@app.before_request` that rejects any `/api/*` request without a valid session. Only `/api/health`, `/api/auth/login` and `/api/auth/config` stay open, and that includes the `/status`, `/counts`, `/fixtures`, `/rows` and `/queue/status` routes. New routes are then protected automatically.
- [x] **One account per person,** with passwords hashed (Werkzeug `generate_password_hash`, scrypt, or bcrypt). Keep users in a small table, never in the frontend.
- [x] **Server-side session cookie** (done 2026-10-12: `HttpOnly`, `SameSite=Lax`, `Secure` via `STUDIO_COOKIE_SECURE=1`, `STUDIO_SECRET_KEY`; no rotation beyond `session.clear()` on login) set to `HttpOnly`, `Secure` and `SameSite=Lax`, with a strong `SECRET_KEY` from Railway variables. Expire it after 8 to 12 hours and rotate the session on login.
- [x] **Remove the PIN from the browser completely** (account mode only; PIN mode still keeps it in sessionStorage until the first account exists). No `localStorage`, no `?pin=` query parameter, no `X-Dashboard-PIN` header.
- [x] **Handle the queue's internal calls** (done: per-process `X-Internal-Token`). The queue and calendar call `/run` over HTTP on 127.0.0.1 with the PIN today. Change that to a separate `INTERNAL_TOKEN` env secret, or call the run functions directly, otherwise the queue breaks once the PIN goes away.
- [ ] **Rate-limit the login** with Flask-Limiter: about 5 attempts a minute per account and 20 per real IP, after adding `ProxyFix(x_for=1)`.
- [ ] **Two roles:** a _viewer_ who can browse, and a _runner_ who can run, stop and edit prompts. Only an _admin_ can use cleanup and settings.
- [ ] **Audit log:** record who ran what, when, and with which `max_items`. The shared PIN could never give you this.
- [ ] **Close CORS.** The frontend is already served from the same Flask app (there's no Vercel config in the repo and the API URL is relative `/api/...`), so the open `*` default can just go.
- [ ] **Generic error messages to the client.** Today the global handler returns `str(error)`, which leaks internal details.

* * *
## Everything else found
*   **High** (7)
    *   **Secrets can leak into public logs.** `response_error()` includes up to 1000 characters of provider response text, Krea logs raw error bodies without a limit, and image URLs appear in error context. No API key is printed directly, but signed URLs and error bodies end up in public `/status` output. ( [http.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/content_automation/http.py), [krea\_client.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/content_automation/krea_client.py), [fal\_client.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/content_automation/fal_client.py))
    *   **7 pipelines skip even the (disabled) concurrency check:** collection\_feed, moodboard\_story, myth\_fact\_story, product\_description\_story, product\_showcase\_feed, room\_build\_up\_reel and this\_or\_that\_story. With the PIN, someone can start all of them at once.
    *   **The GitHub workflow is open to shell injection.** In [product\_closeup\_reel.yml](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/.github/workflows/product_closeup_reel.yml), `${{ github.event.inputs.max_rows }}` goes straight into a shell command while the Airtable, Krea, Fal and Akeneo secrets are loaded. Pass the inputs through `env:` instead.
    *   **`main`** **isn't protected, but every push to it deploys to Railway.** ( [GIT\_PUSH\_AND\_DEPLOY.md](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/docs/GIT_PUSH_AND_DEPLOY.md)) Turn on branch protection with required reviews.
    *   **The Cloudflare quick tunnel exposes the whole API publicly and prints the PIN** to the console. ( [launch\_studio\_cloudflare.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/launch_studio_cloudflare.py)) Stop using it once the login ships, or switch to a named tunnel with Cloudflare Access.
    *   **The PIN sits in localStorage** (`hc_studio_pin`), so it survives browser restarts and any XSS or browser extension can read it. The README wrongly says it's kept in session storage. ( [App.tsx](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/src/app/App.tsx))
    *   **The queue trusts endpoints sent by the caller.** `run_endpoint`, `status_endpoint` and `stop_endpoint` come from the client and get called on 127.0.0.1. Allow only the known pipeline paths.
    

*   **Medium** (11)
    *   **The Airtable status filter is inserted straight into a formula** in [rows.py](http://rows.py) (`LOWER({Status}) = '{norm_status}'`). Only accept p, s, c, d or fm.
    *   **The container runs as root.** Add a non-root `USER`.
    *   **`.dockerignore`** **misses** **`.env.day-night-reel`** **and** **`.env.tips-edu-story`****.** Add `.env.*` and keep exceptions only for the `.example` files.
    *   **The Catalyst config (****`app-config.json`****) starts the Flask dev server** instead of Gunicorn.
    *   **Dependencies use version ranges, not exact pins,** and CLIP is installed from GitHub with no commit hash. Run `pip-audit` and lock versions.
    *   **`tests.yml`** **has no** **`permissions: contents: read`****,** and its actions aren't pinned to commit SHAs.
    *   **The tunnel launcher downloads** **`cloudflared.exe`** **without a checksum check.**
    *   **Fal can submit a paid job twice.** When the SDK call fails, it falls back to REST without checking whether the first job went through. Airtable POST and PATCH calls are also retried even though repeating them isn't safe.
    *   **Some HTTP calls have no timeout:** `requests.get(image_url, stream=True)` and `urlretrieve(audio_url)` in the CTA and House Tour pipelines.
    *   **Airtable and Akeneo pagination has no limit,** and every record is held in memory.
    *   **Config overrides accept any key and write it into** **`os.environ`****.** House Tour also changes global environment variables for each run, so settings can bleed between runs. Allow only the expected keys.
    

*   **Low / info**
    *   The frontend bundle hardcodes the Airtable base ID and fixture IDs. They aren't credentials, but they make it easier for someone to map your setup.
    *   `AssetCatalog.path()` builds file paths without checking they stay inside the allowed folders. No route passes user input into it today.
    *   `run_auto_post_scheduler.py` sends no auth header if `CRON_SECRET` is unset. Make sure the server-side runner rejects requests without it.
    

* * *
## How to test it safely
1. **Set up a staging copy on Railway** (a second service) with **separate test Airtable and provider keys** and low spending caps. Never test against production, because every run costs money.
2. **Run a no-login sweep:** `curl` every GET route from the inventory with no cookie and no PIN. Every one except health and login should return 401.
3. **Check the lockout:** send 10 bad logins from one machine, then confirm a different person can still log in.
4. **Scan it with OWASP ZAP** (free): a baseline scan against staging.
5. **Load test with k6 or Locust** against staging only: 50 users hitting `/api/health` and the logged-in `/status` pages. Confirm it stays responsive while one slow `/rows` request is running.
6. **Run the free supply-chain checks:** `pip-audit`, `npm audit` in UI Control, and **Gitleaks** over the full git history.

* * *
## Already in good shape
*   Every `/run`, `/stop`, `/moodboard` and `/prompt` route checks the PIN before doing anything.
*   No `shell=True`, `eval`, `pickle` or user-controlled file paths in the routes. Pipelines start with list arguments, so prompts can't inject shell commands.
*   `.env` is gitignored, the `.example` files only contain placeholder credentials, and no live key turned up in the recent commits checked.
*   Production uses Gunicorn, not the Flask dev server (except the Catalyst config).
## Couldn't verify
*   **The shared proxy IP** comes from how Railway usually works, not from your live setup. Test step 3 confirms it either way.
*   **Early git history** was only skimmed (the first commit is about 56k lines), so run Gitleaks.
*   **Other** **`content_automation`** **modules** (the scrapers and workflow helpers) were skimmed, not fully audited.
*   **Whether** **`DASHBOARD_PIN`** **is actually set on Railway right now.** If it's empty, every protected route is open too.

* * *
## Sources
*   [api\_server.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/api_server.py)
*   [routes/common.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/routes/common.py)
*   [routes/rows.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/routes/rows.py)
*   [routes/queue\_manager.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/routes/queue_manager.py)
*   [routes/calendar.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/routes/calendar.py)
*   [routes/cta\_story.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/routes/cta_story.py)
*   [content\_automation/cleanup.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/content_automation/cleanup.py)
*   [Dockerfile](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/Dockerfile)
*   [launch\_studio\_cloudflare.py](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/launch_studio_cloudflare.py)
*   [UI Control/src/app/App.tsx](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/UI%20Control/src/app/App.tsx)
*   [.github/workflows/product\_closeup\_reel.yml](https://github.com/homecartelmarketing-lgtm/marketing-automation/blob/5c91f780fe7fc8c68ee037b676ce2cc9981366aa/.github/workflows/product_closeup_reel.yml)