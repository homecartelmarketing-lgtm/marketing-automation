---
date: 2026-09-19
pipeline: Control UI & Unified Generation Queue (1 Product 3 Styles Feed)
status: resolved
---

# Control UI: Infinite Running / Blinking Timer on Finished Pipelines

## Symptom

After a pipeline run for 1 Product 3 Styles Feed finished successfully (`[DONE] Pipeline execution completed successfully.`), the Control UI (`http://127.0.0.1:5200`):
- Kept displaying the top `BACKGROUND PROCESSING` banner indefinitely.
- Kept pulsing the sky-blue `● RUNNING` badge in the Live Execution Console with the elapsed timer continuing to increment past completion (e.g. `01:17`, `03:07`).
- Kept the floating `QueueDock` at the bottom active with the `Stop` button enabled.
- Never transitioned to the completed state or refreshed the completed count badge (`C`).

## How it was diagnosed

1. Checked `/api/one-product-3-styles/status` while the UI was stuck. It returned:
   ```json
   { "status": "success", "current_phase": "Complete", "exit_code": 0 }
   ```
2. Checked `/api/queue/status`. The `active_job` field was still populated:
   ```json
   { "active_job": { "pipeline_type": "one-product-3-styles", "status": "running", "elapsed_seconds": 187, ... } }
   ```
3. Traced `UI Control/routes/one_product_three_styles_feed.py` line 569:
   ```python
   if proc.returncode == 0:
       STATE["status"] = "success"  # Set to "success" instead of "completed"
   ```
4. Traced `UI Control/routes/queue_manager.py` line 223:
   ```python
   status_data = _fetch_job_status(curr_job)
   run_status = status_data.get("status", "running")
   if run_status in ("completed", "error", "stopped"):
       # Archive and clear _ACTIVE_JOB
   ```
   Because `run_status == "success"`, the condition evaluated to `False`. The queue worker kept looping, updating `_ACTIVE_JOB["elapsed_seconds"]`, and reporting `status: "running"`.
5. In `UI Control/src/app/App.tsx`, the queue polling hook continuously read `data.active_job` and forced `pipelineState.status = 'running'`, while `checkStatus` only checked `data.status === 'completed'`.

## Root Cause

Discrepancy in status string naming conventions: `one_product_three_styles_feed.py` used `"success"`, whereas all other 16 pipeline blueprints, the `queue_manager.py` worker, and the React frontend expected `"completed"`.

## Resolution

1. **Normalized Pipeline Status**: Updated [`UI Control/routes/one_product_three_styles_feed.py`](../../UI%20Control/routes/one_product_three_styles_feed.py) to set `STATE["status"] = "completed"`.
2. **Defensive Queue Manager**: Updated [`UI Control/routes/queue_manager.py`](../../UI%20Control/routes/queue_manager.py) to accept `"success"` and `"done"` alongside `"completed"`, normalizing them to `"completed"` in the job history.
3. **Frontend Synchronization**:
   - In [`UI Control/src/app/App.tsx`](../../UI%20Control/src/app/App.tsx), added support for `data.status === 'success'` in `checkStatus`.
   - Added `activeQueueJobRef` in `pollQueue` to detect when the queue finishes and immediately transition the UI to `status: 'completed'` and trigger `fetchLiveCounts()`.
   - In [`LiveLogViewer.tsx`](../../UI%20Control/src/app/components/planning/LiveLogViewer.tsx), added `case 'success':` to badge rendering.
4. **Rebuilt & Restarted**: Rebuilt frontend with `npm run build` and restarted `api_server.py`. Verified that `/api/queue/status` returns `active_job: null` and the UI cleanly resets to idle on completion.
