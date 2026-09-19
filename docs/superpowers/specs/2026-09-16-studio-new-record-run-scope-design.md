# Studio New-Record Run Scope Design

> [!WARNING]
> **STATUS (as of 2026-09-19): NOT IMPLEMENTED.** This spec describes a run-scope feature that was never built (`studio_run_scope.py` / `routes/studio_runs.py` do not exist). See the matching plan in `../plans/`.

**Date:** 2026-09-16  
**Status:** Approved design, pending implementation plan  
**Scope:** All 23 Story, Feed, and Reel pipelines launched from Control UI

## Problem

Several pipeline runners discover existing Airtable rows before scraping. A Studio run can therefore resume unrelated old rows, treat terminal rows such as `Posted` or `Scheduled` as incomplete, skip the requested Akeneo scrape, and still exit successfully even though it created no content. The Before & After Reel failure is one confirmed example:

1. The runner counted `Posted` and `Scheduled` rows as backlog.
2. No generation phase considered those rows actionable.
3. The runner skipped Akeneo scraping because backlog existed.
4. It exited with code 0, so Control UI displayed a false success toast.

The behavior also makes simultaneous runs unsafe because a runner may select records that belong to another run.

## User-Approved Behavior

Every run started from Control UI must:

1. Scrape the requested number of new, eligible Akeneo products.
2. Create new Airtable rows for those products.
3. Capture the exact Airtable record IDs created by that run.
4. Execute every generation phase only for those captured IDs.
5. Finish those new rows end-to-end when all external services succeed.
6. Leave all pre-existing Airtable rows untouched, regardless of whether their status is incomplete, processing, posted, scheduled, complete, discarded, or manual/revision.
7. Report an explicit no-new-content outcome when deduplication or eligibility rules produce no new rows.

CLI workflows may retain explicit resume/repair behavior. Resume must never be an implicit fallback for a Control UI run.

## Considered Approaches

### 1. Shared run scope with exact record IDs — selected

Introduce a small shared run-scope abstraction. A Studio run receives a unique run ID, its scraper returns newly created Airtable IDs, and downstream phases receive only those IDs. A local manifest persists the scope for diagnostics and crash recovery.

This is the safest option because record identity is explicit, works across all status values, does not depend on timestamps, and isolates simultaneous runs.

### 2. Modify each runner independently

Remove backlog handling and add local ID filtering separately in each of the 23 pipelines. This has lower initial abstraction cost but would produce inconsistent flags, error handling, logs, and tests. Future pipelines could easily reintroduce the same defect.

### 3. Select rows by creation timestamp

Record a launch time and process rows created after it. This requires less plumbing but is unsafe when two runs overlap or when Airtable responses are delayed. One run could process another run's rows.

## Architecture

### `StudioRunScope`

A shared Python module will own the run contract. Its responsibilities are:

- Generate or validate a unique run ID.
- Record the pipeline, fixture, Airtable table ID, requested item count, and start time.
- Accept newly created Airtable record IDs from the scraper.
- Reject empty, duplicate, or malformed IDs where appropriate.
- Expose an immutable target-ID list to generation phases.
- Persist state transitions and the final outcome to a local JSON manifest.

The module will not call Akeneo, Airtable, Krea, Fal, or Claude. It is a small coordination and validation boundary that can be tested without network access.

### Manifest storage

Manifests will be stored under a dedicated ignored runtime directory, for example:

`output/studio-runs/<run-id>.json`

A manifest contains no API tokens or image payloads. Its minimum fields are:

- `run_id`
- `pipeline`
- `fixture`
- `table_id`
- `requested_items`
- `created_record_ids`
- `state`: `starting`, `scraping`, `generating`, `completed`, `no_new_content`, `failed`, or `stopped`
- `started_at` and `finished_at` in ISO 8601 format
- a concise failure message when applicable

Atomic replacement will be used when updating a manifest so a process interruption cannot leave partially written JSON.

### Runner contract

Every Control UI runner must support a Studio-only new-record mode, using a consistent argument such as:

```text
--studio-run-id <uuid> --new-only
```

In this mode the runner must follow this contract:

```text
scrape new products
    -> return exact created Airtable IDs
    -> if empty: stop with NO_NEW_CONTENT
    -> pass IDs to phase 1
    -> pass the same IDs to every later phase
    -> complete only those IDs
```

No generation function may interpret an empty target list as “process every pending row.” An explicit empty Studio scope must fail closed and perform no generation work.

Existing CLI defaults will not be silently changed unless a runner already represents only the Studio workflow. CLI resume behavior will require an explicit existing flag or a new `--resume-existing` option.

### Control UI contract

Each `/run` route will:

1. Generate a run ID.
2. Include `--studio-run-id` and `--new-only` in the subprocess command.
3. Store the run ID in that route's state for status responses and logs.
4. Read the structured final result from the manifest after the process exits.
5. Return a truthful terminal state to the frontend.

The frontend will distinguish:

- **Completed:** new rows were created and completed end-to-end.
- **No new eligible products:** the scraper created no rows; this is informative, not a pipeline success and not an external-service failure.
- **Failed:** the run created rows but one or more required phases failed, or the runner violated the run-scope contract.
- **Stopped:** the user stopped the run.

The UI must not infer business success from process exit code 0 alone.

## Pipeline Migration

The contract applies to all Control UI pipelines:

### Story

1. CTA Story
2. Tips & Educational Story
3. Collection Category Story
4. Day & Night Story
5. Moodboard Story
6. Product Closeup with Specifications Story
7. Style This Story
8. Myth & Fact Story
9. Product Closeup with Description Story
10. This or That Story

### Feed

1. Tips & Educational Feed
2. Collection Category Feed
3. Moodboard #1 Feed
4. Moodboard #2 Feed
5. 1 Product, 3 Styles Feed
6. Day & Night Feed
7. Product Showcase Feed

### Reel

1. Day & Night Reel
2. Product Closeup Reel
3. Before & After Reel
4. Moodboard Reel
5. Style Reel Slideshow
6. 1 Product, 3 Styles Reel

Migration will use adapters around existing scraper and phase functions where possible. Existing functions that already accept `record_ids` will be reused. Runners that currently locate “the next incomplete row” will be changed so Studio mode uses only the IDs returned by their scrape step.

Activation will be fail-closed: a route will not enable `--new-only` until its runner passes the shared contract tests. The complete Studio release will be built only after all 23 routes and runners are compliant.

## Simultaneous-Run Safety

Exact target IDs isolate generation work between concurrent runs. To prevent two scrapers for the same Airtable table from selecting the same Akeneo item before either write becomes visible, the creation step will use a short cross-process lock keyed by Airtable table ID. The lock covers eligibility selection and Airtable row creation only; it is released before expensive AI generation begins. The implementation must work across the child Python processes launched by Flask, not only across threads in the Flask process.

This design is compatible with a future configurable worker queue, but implementing that queue is outside this change. Existing route-level restrictions remain until the separate queue feature is implemented.

## Error Handling

- A scraper exception produces `failed`; no generation phase starts.
- Zero created rows produces `no_new_content`; no generation phase starts.
- If Akeneo contains fewer eligible products than requested, the run proceeds with every row Airtable successfully creates and reports the actual count.
- If Airtable returns an error during a create batch, the run records any confirmed IDs for diagnostics, stops before paid generation, and reports `failed`. It never guesses IDs or processes a partially confirmed batch.
- A generation failure records the failed phase and leaves the newly created rows available for an explicit repair action.
- A missing manifest or a mismatch between requested and reported run IDs is a contract failure, never success.
- User stop updates the manifest to `stopped` after terminating the child process.
- Logs include the run ID and number of scoped records, but no credentials or full private API payloads.

## Status Semantics

The existing five Airtable badge groups remain unchanged. `Posted` and `Scheduled` continue to count under their documented UI badges and are never treated as reasons to resume a row during a new Studio run. Completed totals continue to use only the `C` badge group.

## Testing Strategy

Implementation will follow test-driven development and will not call paid APIs.

### Shared unit tests

- A run scope accepts and persists newly created IDs.
- Duplicate IDs are normalized or rejected consistently.
- An explicit empty scope never expands to all pending Airtable rows.
- Manifest writes are atomic and contain no secrets.
- Invalid state transitions fail clearly.

### Runner contract tests

For every Studio runner, mocked Akeneo and Airtable clients will verify:

- scraping occurs before generation;
- only IDs returned by the current scrape are passed to every phase;
- old incomplete and terminal rows are not read as targets;
- zero newly created rows prevents all paid generation calls;
- a phase failure cannot be reported as completed.

### Route tests

For all 23 `/run` routes:

- the subprocess receives a unique `--studio-run-id` and `--new-only`;
- status exposes the same run ID;
- completed, no-new-content, failed, and stopped manifests map to the correct API state;
- process exit code 0 without a valid completed manifest is not reported as success.

### Regression verification

- Run the Python unit and contract suites.
- Compile all active Python entrypoints used by Control UI.
- Audit every route-to-CLI argument contract using each runner's `--help` output.
- Build the React frontend with `npm run build`.
- Perform one mocked end-to-end Studio run per pipeline family: Story, Feed, and Reel.

## Rollout Order

1. Add the shared run-scope module and its tests.
2. Add shared route helpers for run ID creation and manifest-result parsing.
3. Fix Before & After Reel first as the confirmed reproducer.
4. Migrate remaining Reel runners.
5. Migrate Feed runners.
6. Migrate Story runners.
7. Update frontend terminal messages.
8. Run the full contract audit and production build.

## Success Criteria

The change is complete when:

- Every Control UI run either creates fresh rows and processes only those rows, or reports that no new eligible products were found.
- No Control UI run automatically resumes or modifies any row that existed before that run began.
- Two overlapping runs cannot process each other's Airtable rows.
- A green completed message is impossible without a valid manifest containing at least one newly created record ID and a completed terminal state.
- All 23 route/runner contracts pass without making paid API calls.

## Out of Scope

- The configurable multi-worker queue discussed separately.
- A Resume/Repair user interface for old rows.
- Airtable schema changes.
- Unrelated legacy standalone-script syntax errors.
- Refactoring image generation, layouts, prompts, or Airtable badge definitions.
