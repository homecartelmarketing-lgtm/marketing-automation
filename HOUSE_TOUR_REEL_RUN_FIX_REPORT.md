# House Tour Reel Pipeline Fix & Verification Report

**Target:** House Tour Reel (`generate_house_tour_reel_pipeline.py`)  
**Target Table:** `tblqXkdDw4O7hxJS4` ("House Tour Reel")  
**Control UI:** `https://marketing-automation-control-ui.up.railway.app/`  
**Date:** 2026-10-09  

---

## 1. Executive Summary

When triggering a **House Tour Reel** run from the Control UI at `https://marketing-automation-control-ui.up.railway.app/`, the execution aborted during **Phase 1: Krea 11-Room Interior Generation** with the error:

```
Run failed: Process exited with non-zero code 1
```

By querying the Railway deployment runtime logs and reproducing the call directly, two underlying root causes were uncovered:

1. **Depleted Krea API Balance (HTTP 402):** Krea's API rejected room generation requests with HTTP 402:
   ```json
   {"message": "Your API balance is separate from your workspace compute balance. Please top up your API balance to continue using the API."}
   ```
2. **Generic Error Masking in `extract_clean_error()`:** In `UI Control/routes/common.py`, the error parser checked for specific exceptions (like `AttributeError`, `TypeError`) and Airtable/Shopify errors, but did not catch `ProviderError`, `AutomationError`, or Krea 402/balance errors. It therefore fell through to the default fallback: `"Process exited with non-zero code 1"`.
3. **No Fallback in Phase 1:** `generate_house_tour_reel_pipeline.py` strictly relied on Krea without a fallback for room interiors, causing the thread pool to raise an uncaught exception in `process_row()` and immediately crash the runner process.

---

## 2. Technical Root Cause Breakdown

### A. Krea Account Balance Depletion (HTTP 402)
Krea separates web workspace compute credits from developer API balance (`api.krea.ai`). When an API key runs out of developer credits, Krea responds with HTTP 402.

In `generate_house_tour_reel_pipeline.py`:
```python
url = clients.krea.generate_image(
    prompt=interior_prompt,
    moodboard_id=moodboard_id,
    aspect_ratio=INTERIOR_ASPECT_RATIO,
    resolution=INTERIOR_RESOLUTION,
)
```
When Krea returned 402, `KreaClient` raised:
```
content_automation.errors.ProviderError: Krea image generation failed (402): {'message': 'Your API balance is separate from your workspace compute balance. Please top up your API balance to continue using the API.'}
```

### B. Masked Error in Studio UI
In `UI Control/routes/common.py`, `extract_clean_error()` scanned stdout/stderr lines for known patterns. Because `ProviderError` and the 402 message were not in the match list, the function returned:
```python
code = default_code if default_code is not None else 1
return f"Process exited with non-zero code {code}"
```
This hid the exact reason from the user and UI operator.

### C. Unhandled Exception in `process_row()`
`process_row()` executed Phase 1 without an outer `try/except` guard. When the thread pool re-raised `ProviderError`, the process terminated with code 1, leaving the created Airtable record permanently stuck in `Status: In Progress`.

---

## 3. Implemented Fixes

### Fix 1: Automatic Fal AI Flux Fallback for Room Interiors
In `generate_house_tour_reel_pipeline.py::phase1_interiors`:
- When Krea image generation fails (due to HTTP 402 balance depletion, 401 auth failure, or temporary provider outage), the pipeline now logs a warning:
  ```
  [WARN] Krea generation failed for slot {slot}: {error}
  -> Falling back to Fal AI (Flux Schnell) for slot {slot} ({SLOT_ROOMS[slot]})...
  ```
- It calls Fal AI's high-speed photorealistic model (`fal-ai/flux/schnell`, 9:16 portrait) with the rich room interior prompt.
- Verified: Fal AI produces a 9:16 interior in **0.93 seconds**, which is directly compatible with Claude Sonnet 5 Vision analysis in Phase 2.

### Fix 2: Enhanced Error Extraction in `extract_clean_error()`
In `UI Control/routes/common.py::extract_clean_error`:
- Added explicit detection for Krea HTTP 402:
  ```python
  if "api balance is separate from your workspace compute balance" in full_text or (
      "krea" in full_text and ("402" in full_text or "balance" in full_text)
  ):
      return (
          "Krea API Error (402 Payment Required): Krea API balance is depleted. "
          "Please top up your API balance at krea.ai/api."
      )
  ```
- Added explicit detection for Krea HTTP 401 auth errors.
- Expanded the traceback matcher to recognize `ProviderError:`, `AutomationError:`, `ConfigurationError:`, and any `*Error` or `*Exception` lines in stdout/stderr.

### Fix 3: Robust Exception Handling in `process_row()`
In `generate_house_tour_reel_pipeline.py::process_row`:
- Wrapped the entire execution inside a `try/except Exception` block.
- If an unrecoverable failure occurs in any phase, it logs `[ERROR] [ROW {record_id}] Processing failed: {error}` and updates the Airtable record `Status` to `"Failed"` instead of leaving it stranded in `"In Progress"`.

---

## 4. Verification & Testing

1. **Unit Testing (`tests/test_house_tour_fallback_and_error.py`):**
   - Verified that Krea HTTP 402 logs are correctly extracted as `"Krea API Error (402 Payment Required): Krea API balance is depleted..."`.
   - Verified that Krea HTTP 401 logs are correctly extracted as `"Krea Auth Error..."`.
   - Verified that `phase1_interiors` falls back to Fal AI Flux Schnell when Krea raises `ProviderError` and stamps the generated URL into Airtable updates.
   - Result: `Ran 4 tests in 0.001s - OK`.

2. **Route and Existing House Tour Tests:**
   - Ran `python -m unittest discover -s tests -p "test_house_tour*.py"`.
   - Result: `Ran 16 tests in 1.488s - OK`.

3. **Fal AI Generation & Vision Pipeline Verification:**
   - Tested direct text-to-image generation via `fal-ai/flux/schnell`: generated 9:16 interior in < 1s (`https://v3b.fal.media/files/b/0aada01b/2_wQGBYdCsj2XA60Z2L80.jpg`).
   - Tested Claude Sonnet 5 Vision analysis (`generate_vision_prompt`) on the resulting image: successfully analyzed mounting positions and lighting placement.

---

## 5. Deployment & Execution Instructions

To deploy the fix to the live Railway instance:

1. **Commit & Push to `main`**:
   Railway triggers automatic builds whenever `main` is updated:
   ```bash
   git add generate_house_tour_reel_pipeline.py "UI Control/routes/common.py" tests/test_house_tour_fallback_and_error.py docs/memory/incidents/2026-10-09-house-tour-krea-402-balance-error.md HOUSE_TOUR_REEL_RUN_FIX_REPORT.md docs/HOUSE_TOUR_REEL_RUN_FIX_REPORT.md
   git commit -m "fix(house-tour): add Fal Flux interior fallback and surface Krea 402 errors in Studio UI"
   git push origin main
   ```
2. **Trigger via API**:
   Once Railway rebuilds and reports `HEALTHCHECK` ok at `https://marketing-automation-control-ui.up.railway.app/api/health`, trigger the House Tour Reel via POST:
   ```bash
   curl -X POST https://marketing-automation-control-ui.up.railway.app/api/house-tour-reel/run \
        -H "Content-Type: application/json" \
        -d '{"fixture_id": "house-tour", "max_items": 1}'
   ```
3. **Poll Run Status**:
   ```bash
   curl https://marketing-automation-control-ui.up.railway.app/api/house-tour-reel/status
   ```
   The run will proceed through Phase 1 without crashing on depleted Krea credits, using Fal AI Flux Schnell when Krea returns 402.
