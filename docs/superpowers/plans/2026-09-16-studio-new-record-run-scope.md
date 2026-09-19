# Studio New-Record Run Scope Implementation Plan

> [!WARNING]
> **STATUS (as of 2026-09-19): NOT IMPLEMENTED.** The modules this plan creates (`content_automation/studio_run_scope.py`, `UI Control/routes/studio_runs.py`, `tests/test_studio_*`) do not exist in the repository. Treat this as a historical design draft only.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Control UI launch create fresh Airtable rows and process only those rows end-to-end, with truthful outcomes and no implicit repair of older records.

**Architecture:** A shared `StudioRunScope` persists an exact-ID manifest and protects same-table creation with a cross-process lock. Each runner opts into `--new-only --studio-run-id`, returns the IDs created by its scrape step, and passes only those IDs through generation; shared Control UI helpers create the launch arguments and map the manifest to terminal UI state.

**Tech Stack:** Python 3, dataclasses, JSON, `filelock`, pytest/unittest mocks, Flask, React 18, TypeScript, Vite

**Spec:** `docs/superpowers/specs/2026-09-16-studio-new-record-run-scope-design.md`

## Global Constraints

- Control UI runs must never modify a row that existed before the run began.
- An explicit empty target-ID collection must never mean “process all pending rows.”
- Existing CLI behavior stays compatible unless the caller explicitly passes `--new-only`.
- No test or verification step may call Akeneo, Airtable, Krea, Fal, Claude, Google Drive, or any other paid/external generation service.
- Airtable status badge mappings and completed-count semantics remain unchanged.
- Manifests contain identifiers and concise errors only; never credentials, images, or complete private API payloads.
- Preserve all unrelated staged, unstaged, and untracked workspace changes.

---

## File Structure

### New shared files

- `content_automation/studio_run_scope.py` — run IDs, state transitions, atomic manifests, exact target IDs, CLI argument helpers, and cross-process table locks.
- `UI Control/routes/studio_runs.py` — pure helpers for Studio command construction and manifest-to-API terminal result mapping.
- `tests/test_studio_run_scope.py` — shared scope, manifest, lock, and fail-closed tests.
- `tests/test_studio_route_contract.py` — command/result helpers and all-route argument contract audit.
- `tests/test_studio_before_after_new_only.py` — regression tests for the reported Before & After Reel defect.
- `tests/test_studio_reel_new_only.py` — remaining Reel runner contracts.
- `tests/test_studio_feed_new_only.py` — Feed runner contracts.
- `tests/test_studio_story_new_only.py` — Story runner contracts.
- `UI Control/src/app/studioRunState.ts` — typed terminal-state normalization and toast copy.
- `UI Control/src/app/studioRunState.test.ts` — frontend state tests.

### Shared files to modify

- `requirements.txt` — declare `filelock` directly.
- `.gitignore` — ignore `output/studio-runs/` runtime manifests and locks.
- `content_automation/scraping/runner.py` — add new-record-only scraping and created-ID tracking.
- `UI Control/routes/common.py` — re-export or consume Studio launch/result helpers without duplicating lifecycle logic.
- `UI Control/src/app/App.tsx` — accept `no_new_content`, use structured terminal results, and prevent false success toasts.
- `docs/UI_CONTROL_CONFIG.md` — document new-only Studio behavior and terminal outcomes.

### Runner and route files

The plan modifies the 23 runner/route pairs listed in Tasks 4–10. Each runner owns pipeline-specific scraping and generation; each route owns only launch/status plumbing.

---

### Task 1: Shared Studio Run Scope and Manifest

**Files:**
- Create: `content_automation/studio_run_scope.py`
- Create: `tests/test_studio_run_scope.py`
- Modify: `requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `add_studio_run_arguments(parser: argparse.ArgumentParser) -> None`
- Produces: `scope_from_args(args, *, pipeline: str, fixture: str, table_id: str, requested_items: int) -> StudioRunScope | None`
- Produces: `StudioRunScope.record_created(record_ids: Iterable[str]) -> tuple[str, ...]`
- Produces: `StudioRunScope.target_ids -> tuple[str, ...]`
- Produces: `StudioRunScope.creation_lock(timeout: float = 60.0) -> ContextManager[None]`
- Produces: `load_run_manifest(run_id: str, manifest_dir: Path | None = None) -> dict[str, Any]`

- [ ] **Step 1: Write failing lifecycle and fail-closed tests**

```python
def test_scope_persists_exact_ids_and_completes(tmp_path):
    scope = StudioRunScope.start(
        run_id="11111111-1111-4111-8111-111111111111",
        pipeline="before-after-reel",
        fixture="pendant",
        table_id="tbleUP86Kw36G8Hdw",
        requested_items=2,
        manifest_dir=tmp_path,
    )
    scope.mark_scraping()
    assert scope.record_created(["recA", "recB", "recA"]) == ("recA", "recB")
    scope.mark_generating()
    scope.mark_completed()
    manifest = load_run_manifest(scope.run_id, tmp_path)
    assert manifest["state"] == "completed"
    assert manifest["created_record_ids"] == ["recA", "recB"]


def test_empty_scope_cannot_start_generation(tmp_path):
    scope = make_scope(tmp_path)
    scope.mark_scraping()
    scope.record_created([])
    with pytest.raises(StudioRunStateError, match="no created record IDs"):
        scope.mark_generating()
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python -m pytest tests/test_studio_run_scope.py -q`  
Expected: collection/import failure because `content_automation.studio_run_scope` does not exist.

- [ ] **Step 3: Implement the state model, atomic persistence, argument validation, and lock**

```python
@dataclass
class StudioRunScope:
    run_id: str
    pipeline: str
    fixture: str
    table_id: str
    requested_items: int
    manifest_dir: Path = DEFAULT_MANIFEST_DIR
    state: str = "starting"
    created_record_ids: tuple[str, ...] = ()
    error: str | None = None

    def record_created(self, record_ids: Iterable[str]) -> tuple[str, ...]:
        unique = tuple(dict.fromkeys(str(value).strip() for value in record_ids if str(value).strip()))
        if any(not RECORD_ID_PATTERN.fullmatch(value) for value in unique):
            raise ValueError("Invalid Airtable record ID")
        self.created_record_ids = unique
        self._persist()
        return unique

    @property
    def target_ids(self) -> tuple[str, ...]:
        if not self.created_record_ids:
            raise StudioRunStateError("Studio run has no created record IDs")
        return self.created_record_ids

    def creation_lock(self, timeout: float = 60.0):
        lock_path = self.manifest_dir / "locks" / f"{safe_name(self.table_id)}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(str(lock_path), timeout=timeout)
```

Use `tempfile.NamedTemporaryFile(delete=False, dir=manifest_dir)` followed by `os.replace()` for every manifest write. Validate the run ID with `uuid.UUID`, require positive `requested_items`, enforce legal state transitions, and mark `finished_at` for every terminal state.

- [ ] **Step 4: Add tests for malformed IDs, invalid transitions, missing manifests, atomic replacement, lock contention, and argument pairing**

```python
def test_new_only_requires_run_id():
    parser = argparse.ArgumentParser()
    add_studio_run_arguments(parser)
    args = parser.parse_args(["--new-only"])
    with pytest.raises(SystemExit, match="studio-run-id"):
        scope_from_args(args, pipeline="p", fixture="f", table_id="tbl1", requested_items=1)
```

- [ ] **Step 5: Run scope tests and compile the module**

Run: `python -m pytest tests/test_studio_run_scope.py -q`  
Expected: all tests pass.  
Run: `python -m py_compile content_automation/studio_run_scope.py`  
Expected: exit code 0.

- [ ] **Step 6: Commit this task without including pre-existing staged changes**

Run: `git commit --only -m "feat: add Studio run scope manifests" -- content_automation/studio_run_scope.py tests/test_studio_run_scope.py requirements.txt .gitignore`

---

### Task 2: New-Record-Only Scraper Primitive

**Files:**
- Modify: `content_automation/scraping/runner.py`
- Modify: `tests/test_studio_run_scope.py`

**Interfaces:**
- Consumes: `StudioRunScope.creation_lock()` from Task 1.
- Produces: `FurnitureItemScrapeRunner(..., new_records_only: bool = False)`
- Produces: `FurnitureItemScrapeRunner.created_record_ids: list[str]`

- [ ] **Step 1: Add a regression test proving old rows are untouched**

```python
def test_new_records_only_skips_repairs_and_existing_slots(fake_runner):
    fake_runner.new_records_only = True
    fake_runner.run()
    fake_runner.airtable.available_product_slots.assert_not_called()
    fake_runner.repair_incomplete_slots.assert_not_called()
    fake_runner.repair_missing_layouts.assert_not_called()
    assert fake_runner.created_record_ids == ["recNew"]
```

Also test that `new_records_only=False` preserves existing CLI repair behavior.

- [ ] **Step 2: Run the regression test and confirm the old implementation fails**

Run: `python -m pytest tests/test_studio_run_scope.py -k new_records_only -q`  
Expected: FAIL because the constructor has no `new_records_only` argument and the runner repairs/fills old rows.

- [ ] **Step 3: Implement created-ID tracking and bypass all old-row repair paths**

```python
self.new_records_only = new_records_only
self.created_record_ids: list[str] = []

existing_skus, discovered_incomplete = self.airtable.load_inventory()
if self.new_records_only:
    incomplete = []
    available = []
else:
    incomplete = discovered_incomplete
    available = self.airtable.available_product_slots(per_row)

record_id = self.airtable.create_product_record(items)
self.created_record_ids.append(record_id)
```

Inventory used for deduplication must still be loaded; only mutation of old rows is bypassed. Split inventory lookup from incomplete-slot selection if the current `load_inventory()` return shape requires it.

- [ ] **Step 4: Verify both Studio and legacy modes**

Run: `python -m pytest tests/test_studio_run_scope.py -k "new_records_only or legacy_scrape" -q`  
Expected: all selected tests pass.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "feat: track newly scraped Airtable records" -- content_automation/scraping/runner.py tests/test_studio_run_scope.py`

---

### Task 3: Shared Control UI Launch and Terminal Result Helpers

**Files:**
- Create: `UI Control/routes/studio_runs.py`
- Create: `tests/test_studio_route_contract.py`
- Modify: `UI Control/routes/common.py`

**Interfaces:**
- Consumes: `load_run_manifest()` from Task 1.
- Produces: `prepare_studio_command(command: list[str], *, pipeline: str, fixture: str, table_id: str, requested_items: int) -> StudioLaunch`
- Produces: `resolve_studio_terminal(run_id: str, return_code: int) -> StudioTerminalResult`
- Produces: `apply_studio_terminal(state: dict[str, Any], result: StudioTerminalResult) -> None`

- [ ] **Step 1: Write failing pure-helper tests**

```python
def test_prepare_command_adds_new_only_and_unique_run_id():
    launch = prepare_studio_command(
        [sys.executable, "runner.py"],
        pipeline="cta-story",
        fixture="pendant",
        table_id="tbl123",
        requested_items=3,
    )
    assert launch.command[-3:] == ["--new-only", "--studio-run-id", launch.run_id]


def test_exit_zero_without_completed_manifest_is_error(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_runs, "DEFAULT_MANIFEST_DIR", tmp_path)
    result = resolve_studio_terminal("11111111-1111-4111-8111-111111111111", 0)
    assert result.status == "error"
    assert "manifest" in result.message.lower()
```

- [ ] **Step 2: Run the tests and confirm import failure**

Run: `python -m pytest tests/test_studio_route_contract.py -q`  
Expected: FAIL because `routes.studio_runs` is missing.

- [ ] **Step 3: Implement immutable launch/result dataclasses and fail-closed mapping**

```python
@dataclass(frozen=True)
class StudioTerminalResult:
    status: Literal["completed", "no_new_content", "error", "stopped"]
    message: str
    run_id: str
    created_record_ids: tuple[str, ...]

def resolve_studio_terminal(run_id: str, return_code: int) -> StudioTerminalResult:
    try:
        manifest = load_run_manifest(run_id)
    except (FileNotFoundError, ValueError) as exc:
        return StudioTerminalResult("error", f"Studio result manifest error: {exc}", run_id, ())
    # Map only a valid `completed` manifest with at least one ID to completed.
```

- [ ] **Step 4: Test all terminal states and mismatched run IDs**

Run: `python -m pytest tests/test_studio_route_contract.py -q`  
Expected: all tests pass.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "feat: add Studio launch result contract" -- "UI Control/routes/studio_runs.py" "UI Control/routes/common.py" tests/test_studio_route_contract.py`

---

### Task 4: Fix Before & After Reel End-to-End

**Files:**
- Modify: `run_before_after_reel.py`
- Modify: `generate_before_after_reel_pipeline.py`
- Modify: `UI Control/routes/before_after_reel.py`
- Create: `tests/test_studio_before_after_new_only.py`
- Preserve: `tests/test_studio_config_overrides.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `run_pipeline_for_table(..., record_ids: Sequence[str]) -> bool` with mandatory non-empty IDs in Studio mode.

- [ ] **Step 1: Write the exact reported-bug regression test**

```python
def test_studio_run_ignores_posted_and_scheduled_rows(monkeypatch):
    old_rows = [{"id": "recPosted", "fields": {"Status": "Posted"}},
                {"id": "recScheduled", "fields": {"Status": "Scheduled"}}]
    created = ["recFresh"]
    calls = install_before_after_fakes(monkeypatch, old_rows=old_rows, created_ids=created)
    rc = runner.main([
        "--target", "pendant_lights", "--max-items", "1", "--new-only",
        "--studio-run-id", "11111111-1111-4111-8111-111111111111",
    ])
    assert rc == 0
    assert calls.phase_record_ids == [created] * 5
    assert "recPosted" not in calls.mutated_ids
    assert "recScheduled" not in calls.mutated_ids
```

- [ ] **Step 2: Run the new and existing override tests and confirm the new test fails**

Run: `python -m pytest tests/test_studio_before_after_new_only.py tests/test_studio_config_overrides.py -q`  
Expected: new-only test fails because the runner processes backlog and the phase wrapper does not accept record IDs.

- [ ] **Step 3: Add Studio arguments, delete the Studio backlog branch, and scope every phase**

```python
add_studio_run_arguments(parser)
scope = scope_from_args(args, pipeline="before-after-reel", fixture=args.target or table_id,
                        table_id=table_id, requested_items=args.max_items)

with scope.creation_lock():
    scope.mark_scraping()
    runner = FurnitureItemScrapeRunner(..., new_records_only=True)
    scrape_ok = runner.run()
    created_ids = scope.record_created(runner.created_record_ids)

if not scrape_ok:
    scope.mark_failed("Airtable row creation or attachment upload failed")
    return 1
if not created_ids:
    scope.mark_no_new_content()
    return 0

scope.mark_generating()
success = run_pipeline_for_table(..., record_ids=created_ids)
```

Pass `record_ids` into all five functions in `generate_before_after_reel_pipeline.py`. Treat a missing or empty ID collection as no work, never as an unrestricted table query.

- [ ] **Step 4: Route the subprocess through `prepare_studio_command` and `resolve_studio_terminal`**

Replace `p.returncode == 0` success inference. Save `run_id` in `_EXEC_STATE`, expose it from `/status`, and set the final state from the manifest result.

- [ ] **Step 5: Test completed, no-new-content, failed-phase, stopped, and missing-manifest behavior**

Run: `python -m pytest tests/test_studio_before_after_new_only.py tests/test_studio_config_overrides.py -q`  
Expected: all tests pass.

- [ ] **Step 6: Commit this task**

Run: `git commit --only -m "fix: isolate Before After Studio runs" -- run_before_after_reel.py generate_before_after_reel_pipeline.py "UI Control/routes/before_after_reel.py" tests/test_studio_before_after_new_only.py tests/test_studio_config_overrides.py`

---

### Task 5: Migrate the Other Five Reel Runners

**Files:**
- Modify: `run_day_night_reel.py`
- Modify: `scrape_day_night_reel.py`
- Modify: `run_product_closeup_reel.py`
- Modify: `generate_product_closeup_reel_pipeline.py`
- Modify: `run_moodboard_reel.py`
- Modify: `generate_moodboard_reel.py`
- Modify: `generate_moodboard_reel_pipeline.py`
- Modify: `run_style_reel_slideshow.py`
- Modify: `run_one_product_three_styles_reel.py`
- Create: `tests/test_studio_reel_new_only.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: all six Reel entrypoints accept `--new-only --studio-run-id` and use exact created IDs.

- [ ] **Step 1: Add parser and behavioral contract tests for every Reel entrypoint**

```python
REEL_ENTRYPOINTS = [
    "run_day_night_reel.py",
    "run_product_closeup_reel.py",
    "run_before_after_reel.py",
    "run_moodboard_reel.py",
    "run_style_reel_slideshow.py",
    "run_one_product_three_styles_reel.py",
]

@pytest.mark.parametrize("script", REEL_ENTRYPOINTS)
def test_reel_help_exposes_studio_scope(script):
    result = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--new-only" in result.stdout
    assert "--studio-run-id" in result.stdout
```

Add one mocked `main()` test per runner proving `created_ids == phase_ids` and proving old pending rows are not selected.

- [ ] **Step 2: Run the Reel contract tests and record the failing runners**

Run: `python -m pytest tests/test_studio_reel_new_only.py -q`  
Expected: all remaining Reel cases fail before migration.

- [ ] **Step 3: Adapt each runner's existing phase model**

For `run_day_night_reel.py`, force `resume=False` in Studio mode and pass only the scrape result IDs into `PhasedContentRunner`. For Product Closeup and Moodboard, replace pending-record discovery with newly created IDs. For Style Slideshow and 1 Product 3 Styles, reuse their existing `record_id`/`processed_record_ids` filters and reject an empty Studio list.

```python
if scope is not None:
    scrape_ok, created_ids = scrape_new_records_only(...)
    scope.record_created(created_ids)
    if not scrape_ok:
        scope.mark_failed("Airtable row creation or attachment upload failed")
        return 1
    if not created_ids:
        scope.mark_no_new_content()
        return 0
    scope.mark_generating()
    ok = run_phases(record_ids=scope.target_ids)
```

- [ ] **Step 4: Run Reel tests and compile all Reel entrypoints**

Run: `python -m pytest tests/test_studio_reel_new_only.py -q`  
Expected: all tests pass.  
Run: `python -m py_compile run_day_night_reel.py run_product_closeup_reel.py run_before_after_reel.py run_moodboard_reel.py run_style_reel_slideshow.py run_one_product_three_styles_reel.py`  
Expected: exit code 0.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "feat: isolate Reel Studio record scopes" -- run_day_night_reel.py scrape_day_night_reel.py run_product_closeup_reel.py generate_product_closeup_reel_pipeline.py run_moodboard_reel.py generate_moodboard_reel.py generate_moodboard_reel_pipeline.py run_style_reel_slideshow.py run_one_product_three_styles_reel.py tests/test_studio_reel_new_only.py`

---

### Task 6: Migrate ID-Aware Feed Runners

**Files:**
- Modify: `generate_moodboard_1_feed.py`
- Modify: `generate_moodboard_2_feed.py`
- Modify: `generate_day_night_feed_pipeline.py`
- Modify: `generate_product_showcase_feed_pipeline.py`
- Create: `tests/test_studio_feed_new_only.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: four Feed entrypoints use created IDs rather than pending-row fallbacks.

- [ ] **Step 1: Write tests for the existing ID-aware generation functions**

```python
@pytest.mark.parametrize("module_name", [
    "generate_moodboard_1_feed",
    "generate_moodboard_2_feed",
    "generate_day_night_feed_pipeline",
    "generate_product_showcase_feed_pipeline",
])
def test_id_aware_feed_uses_only_current_scrape(module_name, feed_harness):
    result = feed_harness.run(module_name, created_ids=["recFresh"], old_ids=["recOld"])
    assert result.generated_ids == ["recFresh"]
    assert "recOld" not in result.updated_ids
```

- [ ] **Step 2: Confirm the tests fail on pending-row fallback behavior**

Run: `python -m pytest tests/test_studio_feed_new_only.py -k id_aware -q`  
Expected: failures show old/pending records are selected or Studio flags are missing.

- [ ] **Step 3: Add Studio scope orchestration and remove fallback only in Studio mode**

Keep legacy CLI mode intact. Product Showcase's current `pending_records[:max_items]` path must be bypassed; use only `scrape_active_table_lamps()` return IDs. Moodboard and Day/Night generation functions must receive the immutable `scope.target_ids`.

- [ ] **Step 4: Run focused Feed tests and compile entrypoints**

Run: `python -m pytest tests/test_studio_feed_new_only.py -k id_aware -q`  
Expected: all selected tests pass.  
Run: `python -m py_compile generate_moodboard_1_feed.py generate_moodboard_2_feed.py generate_day_night_feed_pipeline.py generate_product_showcase_feed_pipeline.py`  
Expected: exit code 0.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "feat: scope ID-aware Feed Studio runs" -- generate_moodboard_1_feed.py generate_moodboard_2_feed.py generate_day_night_feed_pipeline.py generate_product_showcase_feed_pipeline.py tests/test_studio_feed_new_only.py`

---

### Task 7: Migrate Backlog-Oriented Feed Runners

**Files:**
- Modify: `run_tips_and_edu_feed.py`
- Modify: `run_collection_category_feed.py`
- Modify: `run_1_product_3_styles_feed.py`
- Modify: `tests/test_studio_feed_new_only.py`

**Interfaces:**
- Consumes: Tasks 1–2 and the Feed test harness from Task 6.
- Produces: all seven Feed entrypoints satisfy the same new-only contract.

- [ ] **Step 1: Add failing tests for `_next_incomplete`, resume, and processed-set bypasses**

```python
@pytest.mark.parametrize("module_name", [
    "run_tips_and_edu_feed",
    "run_collection_category_feed",
    "run_1_product_3_styles_feed",
])
def test_backlog_feed_does_not_query_next_incomplete_in_studio_mode(module_name, feed_harness):
    result = feed_harness.run(module_name, created_ids=["recFresh"], old_ids=["recOld"])
    assert result.incomplete_selector_calls == 0
    assert result.generated_ids == ["recFresh"]
```

- [ ] **Step 2: Run the backlog Feed tests and confirm failures**

Run: `python -m pytest tests/test_studio_feed_new_only.py -k backlog -q`  
Expected: the runners query or process old incomplete records.

- [ ] **Step 3: Thread exact IDs through their phase loops**

Add a Studio branch at the orchestration boundary, not status-specific exclusions. `run_1_product_3_styles_feed.py` must not call `_next_incomplete()` in Studio mode. `run_tips_and_edu_feed.py` and `run_collection_category_feed.py` must iterate `scope.target_ids` and must not append discovered pending rows to that collection.

- [ ] **Step 4: Run all Feed contract tests**

Run: `python -m pytest tests/test_studio_feed_new_only.py -q`  
Expected: all seven Feed entrypoints pass created-ID, empty-scope, failure, and legacy-compatibility tests.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "feat: remove Feed Studio backlog fallback" -- run_tips_and_edu_feed.py run_collection_category_feed.py run_1_product_3_styles_feed.py tests/test_studio_feed_new_only.py`

---

### Task 8: Migrate Monolithic Story Runners

**Files:**
- Modify: `generate_cta_story_pipeline.py`
- Modify: `run_tips_and_edu_story.py`
- Modify: `generate_collection_category_story_pipeline.py`
- Modify: `generate_style_this_story_pipeline.py`
- Modify: `generate_this_or_that_pipeline.py`
- Create: `tests/test_studio_story_new_only.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: five Story entrypoints scrape first and process only current IDs.

- [ ] **Step 1: Write tests for known implicit-fallback functions**

```python
def test_cta_studio_run_never_calls_get_first_incomplete_record(story_harness):
    result = story_harness.run("generate_cta_story_pipeline", created_ids=["recFresh"])
    assert result.calls["get_first_incomplete_record"] == 0
    assert result.generated_ids == ["recFresh"]


def test_collection_story_studio_run_does_not_process_inventory_incomplete(story_harness):
    result = story_harness.run("generate_collection_category_story_pipeline",
                               created_ids=["recFresh"], inventory_incomplete=["recOld"])
    assert result.generated_ids == ["recFresh"]
```

Add equivalent created-ID tests for Tips & Educational, Style This, and This or That.

- [ ] **Step 2: Run the five Story tests and confirm failures**

Run: `python -m pytest tests/test_studio_story_new_only.py -k monolithic -q`  
Expected: tests fail on incomplete-row fallback or missing Studio arguments.

- [ ] **Step 3: Add Studio orchestration around existing phase functions**

CTA must bypass both calls to `get_first_incomplete_record()`. Collection Story must ignore the `incomplete` portion of `load_inventory()` for mutation while retaining existing identities for deduplication. Style This must pass `record_ids=scope.target_ids`; This or That and Tips must add equivalent explicit filters.

- [ ] **Step 4: Verify all five Story runners**

Run: `python -m pytest tests/test_studio_story_new_only.py -k monolithic -q`  
Expected: all selected tests pass.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "feat: isolate monolithic Story Studio runs" -- generate_cta_story_pipeline.py run_tips_and_edu_story.py generate_collection_category_story_pipeline.py generate_style_this_story_pipeline.py generate_this_or_that_pipeline.py tests/test_studio_story_new_only.py`

---

### Task 9: Migrate Wrapper-Based Story Runners

**Files:**
- Modify: `run_day_night_story.py`
- Modify: `run_moodboard_story.py`
- Modify: `run_full_product_specs_story.py`
- Modify: `run_myth_and_fact_story.py`
- Modify: `run_full_product_description_story.py`
- Modify: `run_content_automation.py`
- Modify: `generate_product_specs_story_pipeline.py`
- Modify: `generate_product_description_story_pipeline.py`
- Modify: `tests/test_studio_story_new_only.py`

**Interfaces:**
- Consumes: Tasks 1–2 and Story harness from Task 8.
- Produces: all ten Story entrypoints satisfy the same new-only contract.

- [ ] **Step 1: Add one failing exact-ID test per wrapper**

```python
@pytest.mark.parametrize("module_name", [
    "run_day_night_story",
    "run_moodboard_story",
    "run_full_product_specs_story",
    "run_myth_and_fact_story",
    "run_full_product_description_story",
])
def test_story_wrapper_passes_only_created_ids(module_name, story_harness):
    result = story_harness.run(module_name, created_ids=["recFresh"], old_ids=["recOld"])
    assert result.generated_ids == ["recFresh"]
    assert "recOld" not in result.updated_ids
```

- [ ] **Step 2: Run and confirm the missing filters**

Run: `python -m pytest tests/test_studio_story_new_only.py -k wrapper -q`  
Expected: failures identify wrappers or inner workflows that do not accept target IDs.

- [ ] **Step 3: Add the shared Studio arguments and exact-ID propagation**

Prefer adding `record_ids: Sequence[str] | None` to the smallest existing orchestration function. In Studio mode pass a non-empty tuple; in legacy mode keep `None`. Any inner function that currently treats `[]` and `None` identically must distinguish them:

```python
if record_ids is not None:
    if not record_ids:
        return True
    records = [record for record in records if record["id"] in set(record_ids)]
```

- [ ] **Step 4: Run the complete Story contract suite**

Run: `python -m pytest tests/test_studio_story_new_only.py -q`  
Expected: all ten Story entrypoints pass.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "feat: scope Story wrapper Studio runs" -- run_day_night_story.py run_moodboard_story.py run_full_product_specs_story.py run_myth_and_fact_story.py run_full_product_description_story.py run_content_automation.py generate_product_specs_story_pipeline.py generate_product_description_story_pipeline.py tests/test_studio_story_new_only.py`

---

### Task 10: Migrate All Remaining Control UI Routes

**Files:**
- Modify: `UI Control/routes/cta_story.py`
- Modify: `UI Control/routes/tips_edu_story.py`
- Modify: `UI Control/routes/collection_story.py`
- Modify: `UI Control/routes/day_night_story.py`
- Modify: `UI Control/routes/moodboard_story.py`
- Modify: `UI Control/routes/product_specs_story.py`
- Modify: `UI Control/routes/style_this_story.py`
- Modify: `UI Control/routes/myth_fact_story.py`
- Modify: `UI Control/routes/product_description_story.py`
- Modify: `UI Control/routes/this_or_that_story.py`
- Modify: `UI Control/routes/tips_edu_feed.py`
- Modify: `UI Control/routes/collection_feed.py`
- Modify: `UI Control/routes/moodboard_1_feed.py`
- Modify: `UI Control/routes/moodboard_2_feed.py`
- Modify: `UI Control/routes/one_product_three_styles_feed.py`
- Modify: `UI Control/routes/day_night_feed.py`
- Modify: `UI Control/routes/product_showcase_feed.py`
- Modify: `UI Control/routes/product_closeup_reel.py`
- Modify: `UI Control/routes/day_night_reel.py`
- Modify: `UI Control/routes/style_reel_slideshow.py`
- Modify: `UI Control/routes/moodboard_reel.py`
- Modify: `UI Control/routes/one_product_three_styles_reel.py`
- Modify: `tests/test_studio_route_contract.py`

**Interfaces:**
- Consumes: Task 3 helper and Tasks 4–9 runner arguments.
- Produces: every `/run` route launches with a unique scope and every `/status` route exposes truthful terminal state.

- [ ] **Step 1: Add a parameterized route-to-command contract covering all 23 routes**

```python
ROUTE_CASES = [
    ("/api/cta/run", "generate_cta_story_pipeline.py"),
    ("/api/tips-edu/run", "run_tips_and_edu_story.py"),
    ("/api/collection-story/run", "generate_collection_category_story_pipeline.py"),
    ("/api/day-night-story/run", "run_day_night_story.py"),
    ("/api/moodboard-story/run", "run_moodboard_story.py"),
    ("/api/product-specs/run", "run_full_product_specs_story.py"),
    ("/api/style-this/run", "generate_style_this_story_pipeline.py"),
    ("/api/myth-fact-story/run", "run_myth_and_fact_story.py"),
    ("/api/product-description-story/run", "run_full_product_description_story.py"),
    ("/api/this-or-that/run", "generate_this_or_that_pipeline.py"),
    ("/api/tips-edu-feed/run", "run_tips_and_edu_feed.py"),
    ("/api/collection-feed/run", "run_collection_category_feed.py"),
    ("/api/moodboard-1-feed/run", "generate_moodboard_1_feed.py"),
    ("/api/moodboard-2-feed/run", "generate_moodboard_2_feed.py"),
    ("/api/one-product-3-styles/run", "run_1_product_3_styles_feed.py"),
    ("/api/day-night-feed/run", "generate_day_night_feed_pipeline.py"),
    ("/api/product-showcase-feed/run", "generate_product_showcase_feed_pipeline.py"),
    ("/api/product-closeup-reel/run", "run_product_closeup_reel.py"),
    ("/api/day-night-reel/run", "run_day_night_reel.py"),
    ("/api/before-after-reel/run", "run_before_after_reel.py"),
    ("/api/style-reel-slideshow/run", "run_style_reel_slideshow.py"),
    ("/api/moodboard-reel/run", "run_moodboard_reel.py"),
    ("/api/one-product-3-styles-reel/run", "run_one_product_three_styles_reel.py"),
]

@pytest.mark.parametrize(("endpoint", "script"), ROUTE_CASES)
def test_run_route_adds_studio_scope(client, popen_spy, endpoint, script):
    response = client.post(endpoint, json=valid_payload(endpoint), headers=authorized_headers())
    assert response.status_code in (200, 202)
    command = popen_spy.command_for(script)
    assert "--new-only" in command
    assert command[command.index("--studio-run-id") + 1]
```

The concrete `ROUTE_CASES` list must contain 23 entries; assert its length.

- [ ] **Step 2: Run the route suite and confirm only Before & After passes initially**

Run: `python -m pytest tests/test_studio_route_contract.py -q`  
Expected: remaining route cases fail because they do not use the shared helper.

- [ ] **Step 3: Replace exit-code success inference in every worker**

For each route, call `prepare_studio_command`, save `run_id`, then call `resolve_studio_terminal` after `wait()`. Use `apply_studio_terminal` under that route's state lock. Add `run_id`, `created_count`, and `result_message` to `/status` output.

```python
launch = prepare_studio_command(cmd, pipeline=PIPELINE_KEY, fixture=fixture_id,
                                table_id=table_id, requested_items=max_items)
state["run_id"] = launch.run_id
process = subprocess.Popen(launch.command, ...)
process.wait()
terminal = resolve_studio_terminal(launch.run_id, process.returncode)
apply_studio_terminal(state, terminal)
```

- [ ] **Step 4: Add stop-path tests and mark manifests stopped**

When a route terminates a child process, load the scope by run ID and mark it stopped if its manifest exists. A process that exits after stop must not overwrite `stopped` with `error`.

- [ ] **Step 5: Run all route and runner contracts**

Run: `python -m pytest tests/test_studio_route_contract.py tests/test_studio_before_after_new_only.py tests/test_studio_reel_new_only.py tests/test_studio_feed_new_only.py tests/test_studio_story_new_only.py -q`  
Expected: all tests pass.

- [ ] **Step 6: Commit this task**

Run: `git commit --only -m "feat: launch every Studio pipeline with run scope" -- "UI Control/routes" tests/test_studio_route_contract.py`

Review the staged diff before this directory-scoped commit to ensure it includes only route files changed by this task.

---

### Task 11: Frontend Terminal State and Truthful Toasts

**Files:**
- Create: `UI Control/src/app/studioRunState.ts`
- Create: `UI Control/src/app/studioRunState.test.ts`
- Modify: `UI Control/src/app/App.tsx`
- Modify: `UI Control/package.json`
- Modify: `UI Control/package-lock.json`

**Interfaces:**
- Consumes: route status values `completed`, `no_new_content`, `error`, and `stopped`.
- Produces: `normalizeStudioTerminal(statusPayload) -> StudioTerminalNotice | null`.

- [ ] **Step 1: Write frontend state tests**

```typescript
it('does not show success for no new content', () => {
  expect(normalizeStudioTerminal({
    status: 'no_new_content',
    result_message: 'No new eligible products found',
    created_count: 0,
  })).toEqual({ kind: 'info', message: 'No new eligible products found' });
});

it('requires at least one created row for completed', () => {
  expect(() => normalizeStudioTerminal({ status: 'completed', created_count: 0 }))
    .toThrow(/created row/i);
});
```

- [ ] **Step 2: Add Vitest and confirm the new test fails**

Run from `UI Control`: `npm install --save-dev vitest`  
Add `"test": "vitest"` under `scripts` in `package.json`.  
Run from `UI Control`: `npm test -- --run`  
Expected: test import fails because `studioRunState.ts` does not exist.

- [ ] **Step 3: Implement typed normalization and update `PipelineState`**

```typescript
export type StudioPipelineStatus =
  | 'idle' | 'running' | 'completed' | 'no_new_content' | 'error' | 'stopped';

export function normalizeStudioTerminal(payload: StudioStatusPayload): StudioTerminalNotice | null {
  if (payload.status === 'no_new_content') {
    return { kind: 'info', message: payload.result_message || 'No new eligible products found' };
  }
  if (payload.status === 'completed' && (payload.created_count ?? 0) > 0) {
    return { kind: 'success', message: payload.result_message || 'New content completed' };
  }
  // Map error and stopped explicitly; reject invalid completed payloads.
}
```

In `App.tsx`, replace the `running -> completed` hard-coded success branch with the normalized notice. Refresh Airtable counts only after a valid completion, not after no-new-content or failure.

- [ ] **Step 4: Run tests and production build**

Run from `UI Control`: `npm test -- --run`  
Expected: all frontend tests pass.  
Run from `UI Control`: `npm run build`  
Expected: TypeScript and Vite build exit with code 0.

- [ ] **Step 5: Commit this task**

Run: `git commit --only -m "fix: show truthful Studio terminal results" -- "UI Control/src/app/studioRunState.ts" "UI Control/src/app/studioRunState.test.ts" "UI Control/src/app/App.tsx" "UI Control/package.json" "UI Control/package-lock.json"`

---

### Task 12: Full Contract Audit, Documentation, and Release Verification

**Files:**
- Modify: `docs/UI_CONTROL_CONFIG.md`
- Modify: `tests/test_studio_route_contract.py`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified route/CLI compatibility and operator documentation.

- [ ] **Step 1: Add an audit test that runs `--help` for all 23 route-linked scripts**

```python
def test_all_route_linked_scripts_accept_shared_studio_arguments():
    assert len(ROUTE_CASES) == 23
    for _, script in ROUTE_CASES:
        result = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
        assert result.returncode == 0, (script, result.stdout, result.stderr)
        assert "--new-only" in result.stdout
        assert "--studio-run-id" in result.stdout
```

- [ ] **Step 2: Run the complete Python test set relevant to Studio**

Run: `python -m pytest tests/test_studio_run_scope.py tests/test_studio_route_contract.py tests/test_studio_before_after_new_only.py tests/test_studio_reel_new_only.py tests/test_studio_feed_new_only.py tests/test_studio_story_new_only.py tests/test_studio_config_overrides.py -q`  
Expected: all tests pass with no network calls.

- [ ] **Step 3: Compile only active Control UI entrypoints**

Run: `python -m py_compile content_automation/studio_run_scope.py "UI Control/routes/studio_runs.py" "UI Control/routes/common.py" run_before_after_reel.py run_day_night_reel.py run_product_closeup_reel.py run_moodboard_reel.py run_style_reel_slideshow.py run_one_product_three_styles_reel.py run_tips_and_edu_feed.py run_collection_category_feed.py generate_moodboard_1_feed.py generate_moodboard_2_feed.py run_1_product_3_styles_feed.py generate_day_night_feed_pipeline.py generate_product_showcase_feed_pipeline.py generate_cta_story_pipeline.py run_tips_and_edu_story.py generate_collection_category_story_pipeline.py run_day_night_story.py run_moodboard_story.py run_full_product_specs_story.py generate_style_this_story_pipeline.py run_myth_and_fact_story.py run_full_product_description_story.py generate_this_or_that_pipeline.py`  
Expected: exit code 0.

- [ ] **Step 4: Build the frontend**

Run from `UI Control`: `npm run build`  
Expected: Vite build succeeds.

- [ ] **Step 5: Document operator-visible behavior**

Add these exact rules to `docs/UI_CONTROL_CONFIG.md`:

```markdown
## Studio run scope

Every Run action creates new Airtable rows and processes only the rows created by that action. Existing rows are never resumed automatically. If deduplication finds no eligible product, Studio reports “No new eligible products found” and does not call paid generation services. Repairing an older row requires an explicit CLI resume/repair workflow.
```

- [ ] **Step 6: Inspect the final diff for scope and secrets**

Run: `git diff --check`  
Expected: no new whitespace errors in files changed by this plan.  
Run: `git diff --name-only 6a35396..HEAD`  
Expected: only this plan and the exact files listed in its tasks.  
Run: `rg -n "api[_-]?key|token|secret|password" output/studio-runs tests -g '*.json' -g '*.py'`  
Expected: no generated manifest contains credential values; test fixtures contain only field names or redacted dummy strings.

- [ ] **Step 7: Commit documentation and any audit correction**

Run: `git commit --only -m "docs: explain new-only Studio runs" -- docs/UI_CONTROL_CONFIG.md tests/test_studio_route_contract.py`

- [ ] **Step 8: Record verification evidence**

Save the exact passing command summaries in the final handoff. Do not report the feature complete if any route lacks the shared arguments, any runner test selects an old record, the frontend build fails, or a completed result can be produced without at least one created record ID.
