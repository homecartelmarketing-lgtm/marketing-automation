---
date: 2026-10-13
pipeline: Control UI & Queue Manager
status: resolved
---

# Studio Queue: Stuck at "Starting Generation... Step 0/5" & Stop Endpoint Failure

## Symptom

When starting a pipeline run (e.g. `day-night-feed > chandelier`) from the Studio UI:
1. The Run Center displayed `"Starting generation... Step 0/5"`.
2. The timer continued incrementing past several minutes (e.g. `02:40`, `05:41`).
3. The Live Log remained frozen with only `[XX:XX:XX] Direct Start: chandelier` and `[XX:XX:XX] Successfully dispatched: Pipeline started successfully`.
4. Clicking "Stop" triggered a toast notification: `"Stop request sent to chandelier: No stop_endpoint specified"`, while the queue remained running and additional queued jobs stayed pending.

## Root Cause

1. **Deny-by-Default Gate Blocked Internal Status Checks**:
   Commit `422a6b4` introduced `require_api_auth` in `UI Control/api_server.py`. While `_dispatch_job_run` sent internal loopback headers (`X-Internal-Token`), `_fetch_job_status` in `UI Control/routes/queue_manager.py` did not pass `internal_auth_headers()`. Every status query to `http://127.0.0.1:5200/api/<pipeline>/status` returned HTTP 401 Unauthorized, caught as an exception and returned as `{"status": "running"}` with no logs or phase information.
2. **Missing `stop_endpoint` in Content Calendar Imports**:
   Calendar-imported jobs lacked `stop_endpoint` in `calendar_pipeline_map.json`, `calendar_import.py`, and `routes/calendar.py`. When Stop was clicked, `_dispatch_job_stop` found no endpoint and returned `"No stop_endpoint specified"`.
3. **Queue Worker Depended on Status Route to Clear Stopped Jobs**:
   `stop_current_job` did not clear `_ACTIVE_JOB`, relying on `_fetch_job_status` to report `"stopped"`. Because `_fetch_job_status` was returning 401 `"running"`, the active job was never archived.
4. **Eager Mounting Fetches in React**:
   `fetchLiveCounts()` and `useQueue` in `App.tsx` fired before authentication was verified, returning 401s in the browser DevTools console on initial page load.

## Resolution

1. **Internal Auth**: Added `internal_auth_headers()` to `_fetch_job_status` in `queue_manager.py`.
2. **Stop Endpoint Auto-Derivation**: Added fallback in `_dispatch_job_stop` to derive `/stop` from `run_endpoint` (replacing `/run` with `/stop`) if missing.
3. **Immediate Archive on Stop**: Updated `stop_current_job` to immediately archive `_ACTIVE_JOB` into `_JOB_HISTORY` and clear `_ACTIVE_JOB = None`.
4. **Calendar Mappings**: Added `stop_endpoint` across `calendar_pipeline_map.json`, `calendar_import.py`, and `routes/calendar.py`.
5. **Frontend Auth Gating**: Gated `fetchLiveCounts` and `useQueue` polling in `App.tsx` and `useQueue.ts` on `isAuthenticated`.
6. **Rebuilt Frontend & Tests**: Ran `npm run build` and added unit regression tests in `tests/test_api_hardening.py` and `tests/test_studio_config_overrides.py`.
