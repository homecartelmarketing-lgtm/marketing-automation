# CTA fixture catalog + Studio-only saves (2026-10-05)

**Decision.** Per-pipeline fixture wiring (table ID, FK prefix, moodboard /
prompt env keys + defaults) now lives in `content_automation/fixture_catalog.py`
(pilot: CTA Story, 5 active + 1 parked wall-light), enforced by
`tests/test_cta_catalog_consistency.py` (routes = `fixtures.ts` = docs = FK map).

**Why.** Table IDs + moodboard IDs + prompts were scattered across 5 disagreeing
layers (route dicts, `fixtures.ts`, `config.py TABLES`, generator inline
`getenv` chains, `.env`/`.env.example`). CTA table-lamp had a 3-way UUID split
(route `351d992d` vs docs/generator `257569e1` vs `.env.example` `fb2487fb`);
winner per user: `257569e1`.

**Studio saves no longer touch `.env`.** `save_config_override` writes
`output/config_overrides.json` + `os.environ` only; standalone CLI reads the
same file via `fixture_catalog.load_studio_overrides()`. Toasts/tooltips now
say "Studio setting".

**Hang-forever guard.** All 29 route `Popen` spawns use `stdin=DEVNULL`, and
the queue worker fails jobs past `MAX_JOB_RUNTIME_SECONDS` (default 3h,
`QUEUE_MAX_JOB_RUNTIME_SECONDS` override) so the FIFO advances.

**Rollout pattern.** Same catalog shape for the next pipeline; extend the
consistency test per pipeline.
