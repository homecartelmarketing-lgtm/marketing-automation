---
name: debug-pipeline-run
description: Use when a Studio or CLI pipeline run fails, hangs, flickers, skips a phase, or produces wrong output (missing name tag, bad layout, rejected products). Checks past incidents first, then reproduces, fixes, and records.
---

# Debug a Pipeline Run

Most failures in this repo have happened before. `docs/memory/incidents/` holds the root causes, and reading the right note is usually faster than re-investigating. The second most common trap is a broad `try/except` that swallows the real error and lets the run "succeed" with missing output.

## 1. Locate the failure

- **Which pipeline and phase?** Use the Studio Run Center log (`[PHASE n/N]` markers), the CLI output, or the Airtable row's `Status`, which shows the last phase that finished.
- **Where did it run?** Locally, on Railway, or through the GitHub Action. Env loading, Python version (3.12 locally vs 3.11 on Railway) and worker count all differ between them.
- **Did Studio run the same script as the CLI?** Check the route's `subprocess.Popen` path. It must be the tracked root `generate_*_pipeline.py`.

## 2. Check known incident families first

Search `docs/memory/incidents/` by pipeline name and by error text. These patterns keep coming back:

| Symptom | Usual cause | Where to look |
| :--- | :--- | :--- |
| Products rejected as draft/inactive, or the catalog looks tiny | Shopify 429 / Cloudflare bot challenge, partial cache | `python -m content_automation.shopify_client --status` / `--refresh`; the shopify-429 and cloudflare incidents |
| Studio stuck on "Initializing", flickering status, queue idle | More than one gunicorn worker, or two status pollers | Keep `--workers 1`; the queue is the only serializer (`is_any_pipeline_running` always returns False) |
| Studio output differs from the CLI | Route spawns a stale or untracked script copy | The route's subprocess path |
| Item name tag missing from the final image | Tagging raised inside a broad `except` (AttributeError/NameError), wrong category passed to YOLO | `item_tagger.py`, the phase's `stamp_item_name_tag` call |
| "Missing isolated configuration" on Railway | Loader expected a dotenv file, but Railway only has env vars | `content_automation/isolated_config.py` |
| "None" saved as moodboard/prompt | Null override persisted | `routes/common.py::save_config_override` |
| Runner dies at startup | Import error in a `run_*.py` | `tests/` import smoke test |
| Layout redrawn, doubled logo, prompt text in the image | Layout was sent to an image model instead of Pillow | Use the `pillow-layout` skill |

## 3. Reproduce narrowly

- Re-run only the broken record with `--record-id <rec_id>`. This is the **only** allowed way to touch an existing row. Never loop over leftover rows to "catch up".
- Use `--dry-run`, `--only-phase` or `--from-phase` when the script supports them. Check its `argparse` block first, because flags differ per script.
- Don't start a fresh full run just to debug. Every run creates a new row and spends Krea/Fal credits.

## 4. Fix properly

- Fix the root cause, not the symptom. If you find a broad `except` that hid the bug, narrow it or make it report and fail the record, so the next failure is loud.
- Add a regression test in `tests/` (stdlib `unittest`, mocking Akeneo/Fal/Krea/Airtable). The `python-testing-patterns` skill covers this.
- Run `python -m py_compile` on the changed files and `python -m unittest discover tests`.

## 5. Record it

If it took real investigation, add `docs/memory/incidents/YYYY-MM-DD-<pipeline>-<short-slug>.md` with a few sentences each on **Symptom**, **Root cause**, **How it was diagnosed** and **Fix**. Link related notes with `[[wikilinks]]`. This is what makes step 2 work next time.

Ship the fix with the `ship-to-railway` skill when the user asks.
