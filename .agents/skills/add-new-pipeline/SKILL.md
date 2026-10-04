---
name: add-new-pipeline
description: Use when adding a new pipeline, Studio subtab, Airtable table, or fixture (including Ad Cover fixtures) to this repo. Walks every layer that must be wired so nothing ends up half-registered.
---

# Add a New Pipeline, Subtab, Table or Fixture

A pipeline in this repo touches four layers: the generator monolith, the Flask blueprint, the React Studio config, and the docs. Missing one rarely crashes loudly. It shows up later as a card that never runs, a Studio route that spawns the wrong script (see `docs/memory/incidents/2026-09-30-sketch-to-real-studio-ran-stale-script-copy.md`), or a white screen from a prop mismatch. So work through every step below, even when the change feels small.

## 1. Generator (`generate_<name>_pipeline.py` in the repo root)

Copy the shape of the closest existing monolith instead of inventing a new one:

- Phase 1 scrapes **fresh** products into a **brand-new Airtable row**. Follow the `fresh-row-scrape` skill: Shopify Active & Published check, base-wide dedup, FK ID stamping.
- Declare `STATUS_*` constants near the top and update the row's `Status` after each phase.
- Print explicit `[PHASE n/N]` markers. The Studio route's `detect_phase()` reads them to drive the progress UI.
- All text, logo and watermark layout is local Pillow (see the `pillow-layout` skill). No image API calls for typography.
- Only the last phase writes `Complete`/`Done`. `current_pht_timestamp()` is stamped automatically when Status goes to Complete/Done.
- Accept the usual flags (`--table-id`, `--max-items`/`--max-rows`, `--record-id`, `--mode`/`--dry-run`). Do not add `--execute` to a monolith, because that flag belongs to the `run_*` orchestrators.
- Optionally add a thin `run_<name>.py` alias that calls the monolith's `main()`.

## 2. Register the table ID

- `content_automation/foreign_key.py`: add the table ID to `TABLE_PREFIX_MAP` as `<IDEA>-<FORMAT>-<FIXTURE>` (see AGENTS.md §4A for the abbreviations).
- `.env.example`: add the env key for the table ID.

## 3. Verify the Airtable schema

The table needs `Foreign Key ID` (singleLineText), `ID` (number), `Date and Time Generated` (dateTime) and `Status` (singleSelect), plus whatever attachment and text fields the phases write. The `scratch/ensure_ad_cover_fields.py` script shows an idempotent way to provision fields.

## 4. Flask blueprint (`UI Control/routes/<name>.py`)

- Implement `GET /counts`, `GET /status`, `POST /run`, `POST /stop`, `POST /moodboard`, `POST /prompt`.
- `/run` spawns the **tracked root generator** with `subprocess.Popen([sys.executable, "-u", "<root generator>.py", ...])`. Never point it at an untracked or sibling-folder copy.
- Use `fetch_status_breakdown(table_id)` for counts.
- Never save `None`/`null` overrides as a moodboard or prompt (see `2026-10-01-studio-run-saved-none-as-moodboard-and-prompt.md`).
- Register the blueprint in `UI Control/api_server.py` with `app.register_blueprint(bp)`.

## 5. Studio frontend (`UI Control/src/app/`, data-driven, no `App.tsx` edits)

- `constants/fixtures.ts`: add the `*_FIXTURES` array (`id`, `name`, `tableId`, `moodboardId`, `prompt`) and return it from the subtab switch.
- `constants/pipelines.ts`: add a `PipelineConfig` (`type`, `format`, `subtabIndex`, `subTabLabel`, run/status/stop/counts/moodboard/prompt endpoints, `totalPhases`, `phaseSummary`, `hasMoodboard`, `hasPrompt`).
- `types/index.ts`: add the id to the `PipelineType` union.
- `hooks/usePipelineData.ts`: seed default moodboard/prompt overrides if the pipeline has pencils.
- Run `npm run build` in `UI Control/` and make sure it exits 0. `dist/` is tracked and Railway serves it as-is.

## 6. Verify

```bash
python -m py_compile generate_<name>_pipeline.py "UI Control/routes/<name>.py"
python -m unittest discover tests        # includes the import smoke test for root runners
cd "UI Control" && npm run build && cd ..
python "UI Control/api_server.py"        # then hit /api/<prefix>/counts and /api/health
```

`/api/health` lists registered modules, so the new pipeline should appear there.

## 7. Docs (same commit)

Apply the "Docs to update when you change X" table in AGENTS.md §8. For a new pipeline that means its own `docs/<format>/<NAME>.md`, AGENTS.md §2 tree + §7 + §9, `docs/README.md`, `README.md`, `UI Control/README.md` and `docs/UI_CONTROL_CONFIG.md`. If you made a non-obvious design choice, add a short note under `docs/memory/decisions/`.

Shipping the change is a separate step. Use the `ship-to-railway` skill, and only when the user asks.
