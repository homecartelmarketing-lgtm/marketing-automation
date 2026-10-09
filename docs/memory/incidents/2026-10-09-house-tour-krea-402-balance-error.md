# 2026-10-09 — House Tour failed: "Run failed: Process exited with non-zero code 1"

## Symptom

Triggering House Tour Reel from the Control UI at `https://marketing-automation-control-ui.up.railway.app/` failed during Phase 1 with the generic error:
`Run failed: Process exited with non-zero code 1`

## Root Cause

1. **Krea API Balance Depletion (HTTP 402)**:
   During Phase 1 (Krea 11-Room Interior Generation), `clients.krea.generate_image()` called Krea's `krea-2-medium` endpoint. Krea returned HTTP 402 with the payload:
   `{'message': 'Your API balance is separate from your workspace compute balance. Please top up your API balance to continue using the API.'}`
   `KreaClient` raised `ProviderError`, which crashed Phase 1 without an image generation fallback.

2. **Uncaught Exception in `process_row()`**:
   In `generate_house_tour_reel_pipeline.py`, `process_row()` had no outer `try/except` around the phase execution block. The exception escaped `main()`, printed a traceback to stderr, and exited with status code 1 while leaving the created Airtable record in `Status = In Progress`.

3. **Masked Error in `extract_clean_error()`**:
   In `UI Control/routes/common.py`, `extract_clean_error()` checked for several specific error strings and standard Python exceptions (AttributeError, TypeError, etc.), but did NOT catch `ProviderError`, `AutomationError`, or Krea HTTP 402 balance errors. As a result, it fell through to the default message: `Process exited with non-zero code 1`.

## Fix

1. **Graceful Fal AI Flux Fallback**:
   In `generate_house_tour_reel_pipeline.py::phase1_interiors`, if Krea image generation fails (due to HTTP 402 balance depletion, 401 auth, or provider outages), the pipeline automatically falls back to Fal AI's Flux model (`fal-ai/flux/schnell`, 9:16 portrait) to generate the room interior photorealistically from the detailed room prompt, allowing the pipeline to proceed seamlessly.

2. **Error Trapping & Row Status Update**:
   In `generate_house_tour_reel_pipeline.py::process_row`, wrapped the entire multi-phase execution in a `try/except Exception` block that logs a clean `[ERROR]` message and marks the Airtable row `Status = Failed` instead of crashing unhandled.

3. **Clear Error Extraction in UI Control**:
   In `UI Control/routes/common.py::extract_clean_error`:
   - Added explicit detection for Krea HTTP 402 balance depletion:
     `Krea API Error (402 Payment Required): Krea API balance is depleted. Please top up your API balance at krea.ai/api.`
   - Added explicit detection for Krea HTTP 401 auth error.
   - Expanded exception extraction to recognize `ProviderError:`, `AutomationError:`, `ConfigurationError:`, and general traceback exception lines.

4. **Regression Tests**:
   Added `tests/test_house_tour_fallback_and_error.py` covering Krea 402 error extraction, Krea 401 error extraction, and the Phase 1 Fal AI Flux fallback mechanism.
