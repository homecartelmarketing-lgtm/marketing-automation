# Decision: Studio email + password login on top of the existing auth plumbing (2026-10-12)

The Studio's only gate was the shared `DASHBOARD_PIN`. It is now an email + password login with a Flask cookie session (`UI Control/routes/studio_auth.py`), with a split-layout screen in `LoginScreen.tsx`.

## Choices and why

- **A session is one more way to pass `is_authorized`, not a rewrite.** ~40 route files and ~15 frontend call sites already pass a PIN. `is_authorized(request)` keeps its signature and `common.DASHBOARD_PIN` stays patchable because many tests rely on both. In account mode the browser sends no PIN at all; same-origin fetches carry the cookie.
- **Per-process `X-Internal-Token` for loopback calls.** The queue worker and calendar import POST to `/run` on 127.0.0.1 and used to forward the user's PIN. They now send `INTERNAL_TOKEN` (random per start), so queued jobs keep working with no PIN in the browser. This only works while the app runs as one process (`--workers 1`, see AGENTS.md section 3).
- **Accounts are admin-managed.** Users live in `output/studio_users.json` (hashed with Werkzeug). "Sign Up" and "Forgot Password" send people to the admin by email. `STUDIO_ADMIN_EMAIL`/`STUDIO_ADMIN_PASSWORD` seed one in-memory admin because Railway's disk can be wiped.
- **Open mode now means no PIN and no accounts.** Removing the last account would silently open the Studio, so `manage_studio_users.py remove` refuses without `--force`.
- **PIN mode kept.** With only `DASHBOARD_PIN` set the login screen shows one PIN field, so the existing deployment keeps working until the first account is created.

## Not done at the time (see `docs/SECURITY_AUDIT.md` addendum 2026-10-12 for status)

No per-account rate limit (still per IP, shared with the PIN limiter), no roles enforcement (the `role` field is stored but not checked), no audit log. UPDATE 2026-10-12 (same day, uncommitted on `fix/house-tour-moodboard-errors`): the block-by-default hook now EXISTS — `require_api_auth` in `UI Control/api_server.py:146` 401s every `/api/*` except `/api/health`, `/api/auth/*` and OPTIONS. The other gaps in this paragraph (per-account limiter, roles, audit log) are still open.
