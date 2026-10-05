# Content Calendar XLSX Import → Control UI Auto-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the monthly Content Calendar `.xlsx` so only slots marked `TO DO` auto-run in the Studio; everything already Posted/Scheduled is never re-run.

**Architecture:** A parser turns the month-sheet grid into slot records, a JSON map translates (Format, Idea) to Studio `pipeline_type` + route endpoints, a round-robin pointer picks fixtures, and an importer CLI enqueues `TO DO` jobs via the existing `POST /api/queue/enqueue` FIFO (the queue is the only serializer, workers stay at 1).

**Tech Stack:** Python stdlib + `openpyxl` (already used for xlsx), existing Flask queue (`UI Control/routes/queue_manager.py`), `unittest` (stdlib, `python -m unittest discover tests`).

**Spec:** User decisions 2026-10-05: (1) runnable = status `TO DO` only (case-insensitive); Posted / Scheduled (via UI) / Scheduled (Manual Edit) / NONE / N/A / blank = skip; (2) fixture = round-robin per pipeline; (3) timing = enqueue all at import, queue runs them serially. Source file layout verified from `Content Calendar.xlsx`: sheets July/August/September/October/Caption are weekly grids (4 cols/day: SUN A–D, MON E–H, TUE I–L, WED M–P, THU Q–T, FRI U–X, SAT Y–AB), each slot = 4 cells `[Format, Idea, Time, Status]`; `Auto Compute` is costing (ignore). **Heads-up: the file currently contains zero `TO DO` cells** — importing today enqueues nothing until slots are marked.

## Global Constraints

- Brand-new Airtable row every run still holds; the importer never touches existing rows, it only enqueues Studio runs.
- Never stage `.env`; new files only: parser, mapping JSON, importer CLI, state JSON (gitignored), tests + fixture xlsx.
- Queue payload must match what each route's `/run` expects; read the route before adding its endpoint to the map.
- Keep `--workers 1`; no new concurrency mechanisms.
- All tests stdlib `unittest`, run `python -m unittest discover tests` green before commit.

---

### Task 1: Calendar grid parser

**Files:**
- Create: `content_automation/calendar_import.py`
- Test: `tests/test_calendar_import.py`
- Create: `tests/fixtures/mini_calendar.xlsx` (2 weeks, 3 TO DO / 2 Posted / 1 NONE / 1 blank)

**Interfaces:**
- Consumes: `.xlsx` month sheet with the 4-cols-per-day grid.
- Produces: `parse_month_slots(path: str, month: str) -> list[CalendarSlot]` where `CalendarSlot = dict(date=ISO, format, idea, time, status, cell)`; `status` normalized (`TO DO` uppercased stripped, `Scheduled (via UI)` kept verbatim for logs).

- [ ] **Step 1: Write the failing test**

```python
def test_parse_month_slots_todo_only(self):
    from content_automation.calendar_import import parse_month_slots
    slots = parse_month_slots("tests/fixtures/mini_calendar.xlsx", "October")
    todos = [s for s in slots if s["status"] == "TO DO"]
    self.assertEqual(len(todos), 3)
    self.assertEqual(todos[0]["format"], "Feeds")
    self.assertTrue(todos[0]["date"].startswith("2026-10-"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p test_calendar_import.py`
Expected: FAIL/ERROR (`calendar_import` not defined).

- [ ] **Step 3: Write minimal implementation**

```python
"""Parse Content Calendar month sheets into slot records."""
from __future__ import annotations
import datetime
import openpyxl

DAY_COLS = {"SUN": 1, "MON": 5, "TUE": 9, "WED": 13, "THU": 17, "FRI": 21, "SAT": 25}
VALID_FORMATS = {"Feeds", "Reels", "Stories"}

def _norm_status(v) -> str:
    s = str(v or "").strip()
    return "TO DO" if s.upper() == "TO DO" else s

def parse_month_slots(path: str, month: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[month.capitalize()]
    year = 2026
    month_no = {"october": 10}[month.lower()]
    slots: list[dict] = []
    # Date rows: numeric day in a day-start column; slot rows follow until next date row.
    current: dict[str, int] = {}
    for row in ws.iter_rows():
        starts = {}
        for day, col in DAY_COLS.items():
            v = row[col - 1].value
            if isinstance(v, (int, float)) and 1 <= int(v) <= 31:
                starts[day] = int(v)
        if starts:
            current = {d: datetime.date(year, month_no, n).isoformat() for d, n in starts.items()}
            continue
        if not current:
            continue
        for day, col in DAY_COLS.items():
            if day not in current:
                continue
            cells = [c.value for c in row[col - 1:col + 3]]
            fmt = str(cells[0] or "").strip()
            if fmt not in VALID_FORMATS:
                continue
            slots.append({
                "date": current[day], "format": fmt,
                "idea": str(cells[1] or "").strip(),
                "time": str(cells[2] or "").strip(),
                "status": _norm_status(cells[3]),
                "cell": row[col - 1].coordinate,
            })
    return slots
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p test_calendar_import.py`
Expected: PASS (create `mini_calendar.xlsx` in the test setup if the assertion needs exact rows — build it with openpyxl mirroring the real grid: date row + slot rows).

- [ ] **Step 5: Commit**

```bash
git add content_automation/calendar_import.py tests/test_calendar_import.py tests/fixtures/mini_calendar.xlsx
git commit -m "feat(calendar): parse month-sheet grid into slot records"
```

### Task 2: Idea → pipeline endpoint map (JSON, editable without code)

**Files:**
- Create: `assets/calendar_pipeline_map.json`
- Test: extend `tests/test_calendar_import.py` with `test_every_mapped_idea_has_route`

**Interfaces:**
- Consumes: `CalendarSlot` idea strings.
- Produces: `resolve_job(idea, format) -> dict(pipeline_type, run_endpoint, status_endpoint) | None` (None = skip with reason: `Caption`, `NONE`, `House Tour`, unknown).

- [ ] **Step 1: Write the failing test**

```python
def test_known_ideas_resolve(self):
    from content_automation.calendar_import import resolve_job
    job = resolve_job("Feeds", "Product Showcase")
    self.assertEqual(job["pipeline_type"], "product-showcase-feed")
    self.assertTrue(job["run_endpoint"].startswith("/api/"))
    self.assertIsNone(resolve_job("Feeds", "Caption"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p test_calendar_import.py`
Expected: FAIL (`resolve_job` not defined).

- [ ] **Step 3: Write minimal implementation**

```python
import json
from pathlib import Path

_MAP_PATH = Path(__file__).resolve().parent.parent / "assets" / "calendar_pipeline_map.json"

def _load_map() -> dict:
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))

def resolve_job(format: str, idea: str) -> dict | None:
    entry = _load_map().get(f"{format} :: {idea.strip()}")
    if entry is None or entry.get("skip"):
        return None
    return dict(entry)
```

`assets/calendar_pipeline_map.json` keys (exact idea spellings from the file; endpoints copied from `UI Control/src/app/constants/pipelines.ts` + each route's `/run` + `/status` — executor must open those two files and copy verbatim):

```json
{
  "Feeds :: Product Showcase": {"pipeline_type": "product-showcase-feed", "run_endpoint": "/api/product-showcase-feed/run", "status_endpoint": "/api/product-showcase-feed/status"},
  "Feeds :: Collection Category": {"pipeline_type": "collection-feed", "run_endpoint": "/api/collection-feed/run", "status_endpoint": "/api/collection-feed/status"},
  "Feeds :: Tips & Educational": {"pipeline_type": "tips-edu-feed", "run_endpoint": "/api/tips-edu-feed/run", "status_endpoint": "/api/tips-edu-feed/status"},
  "Stories :: CTA": {"pipeline_type": "cta-story", "run_endpoint": "/api/cta/run", "status_endpoint": "/api/cta/status"},
  "Stories :: Tips & Educational": {"pipeline_type": "tips-edu-story", "run_endpoint": "/api/tips-edu/run", "status_endpoint": "/api/tips-edu/status"},
  "Reels :: Sketch to Real": {"pipeline_type": "sketch-to-real-reel", "run_endpoint": "/api/sketch-to-draw-reel/run", "status_endpoint": "/api/sketch-to-draw-reel/status"},
  "Reels :: Moodboard Reel": {"pipeline_type": "moodboard-reel", "run_endpoint": "/api/moodboard-reel/run", "status_endpoint": "/api/moodboard-reel/status"},
  "Feeds :: Caption": {"skip": true, "reason": "captions are not generatable"},
  "Reels :: NONE": {"skip": true, "reason": "no content that day"}
}
```

Full key list must also cover: `1 Product, 3 Styles`, `Day & Night` (feed), `Moodboard #1`, `Moodboard #2`, `Day (D&N)`, `Night (D&N)` (collapse same-date Day+Night pair into ONE `day-night-story` job), `Moodboard Styled Photo`, `Product Closeup w/ specifications`, `Product Closeup w/ description`, `Style This?`, `Myth & Fact`, `This or That`, `Collection Category` (story), `Before & After`, `One Light at a Time`, `House Tour` (skip: no pipeline — report it), Ad Cover ideas, banner ideas if present.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p test_calendar_import.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assets/calendar_pipeline_map.json content_automation/calendar_import.py tests/test_calendar_import.py
git commit -m "feat(calendar): map calendar ideas to Studio pipeline endpoints"
```

### Task 3: Round-robin fixture pointer (persisted, per pipeline)

**Files:**
- Modify: `content_automation/calendar_import.py` (add `pick_fixture`)
- Test: extend `tests/test_calendar_import.py`

**Interfaces:**
- Consumes: `pipeline_type`; fixture list per pipeline (copied from each route's `get_*_fixtures()`, e.g. moodboard `chandelier/pendant/floor-lamp` + table_ids).
- Produces: `pick_fixture(pipeline_type, state: dict) -> fixture_id`; state persisted to `output/calendar_fixture_state.json` (gitignored via `output/`).

- [ ] **Step 1: Write the failing test**

```python
def test_round_robin_cycles(self):
    from content_automation.calendar_import import pick_fixture
    state = {}
    got = [pick_fixture("moodboard-story", state, ["chandelier", "pendant", "floor-lamp"]) for _ in range(4)]
    self.assertEqual(got, ["chandelier", "pendant", "floor-lamp", "chandelier"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p test_calendar_import.py`
Expected: FAIL (`pick_fixture` not defined).

- [ ] **Step 3: Write minimal implementation**

```python
def pick_fixture(pipeline_type: str, state: dict, fixtures: list[str]) -> str:
    idx = int(state.get(pipeline_type, 0)) % len(fixtures)
    state[pipeline_type] = idx + 1
    return fixtures[idx]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p test_calendar_import.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add content_automation/calendar_import.py tests/test_calendar_import.py
git commit -m "feat(calendar): round-robin fixture picker with persisted state"
```

### Task 4: Importer CLI (dry-run + enqueue)

**Files:**
- Create: `scripts/ops/import_content_calendar.py`
- Test: `tests/test_calendar_import_cli.py` (mock `urllib` POST to queue, assert payload + skip counts)

**Interfaces:**
- Consumes: `--file`, `--month`, slots + map + fixtures + state file.
- Produces: `POST http://127.0.0.1:5200/api/queue/enqueue` per TO DO job: `{pipeline_type, fixture_id, run_endpoint, status_endpoint, payload: {fixture_id, max_items: 1}}`. Read `UI Control/routes/queue_manager.py:334-380` for the exact required fields before coding the POST body. `--dry-run` prints the job table and exits 0 without POSTs.

- [ ] **Step 1: Write the failing test** (mocked HTTP, sample slots incl. Posted/Scheduled/NONE/blank/unknown idea)

```python
def test_cli_skips_non_todo(self):
    jobs, skipped = build_jobs([{"status": "Posted"}, {"status": "TO DO", "format": "Feeds", "idea": "Product Showcase", "date": "2026-10-05"}], state={})
    self.assertEqual(len(jobs), 1)
    self.assertEqual(len(skipped), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p test_calendar_import_cli.py`
Expected: FAIL (`build_jobs` not defined).

- [ ] **Step 3: Write minimal implementation** (`build_jobs` in `calendar_import.py` + argparse CLI that loads state, calls it, POSTs or prints).

- [ ] **Step 4: Run tests**

Run: `python -m unittest discover tests`
Expected: all PASS (full suite, ~325 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/ops/import_content_calendar.py content_automation/calendar_import.py tests/test_calendar_import_cli.py
git commit -m "feat(calendar): CLI imports TO DO slots into the Studio queue"
```

### Task 5: Docs + Studio visibility

**Files:**
- Modify: `docs/OPERATIONS_AND_UTILITIES.md` (add importer row: command, `--dry-run`, state file, map JSON)
- Modify: `UI Control/src` + rebuild `dist/` ONLY if adding the Import button; otherwise skip UI and note CLI-only in docs.

- [ ] **Step 1: Update docs table** with `scripts/ops/import_content_calendar.py --file "Content Calendar.xlsx" --month October --dry-run` example.
- [ ] **Step 2: If UI button added**, rebuild via `npm run build` in `UI Control/` and stage `dist/`.
- [ ] **Step 3: Commit**

```bash
git add docs/OPERATIONS_AND_UTILITIES.md
git commit -m "docs(calendar): document XLSX import workflow"
```

## Self-Review

- Spec coverage: TO DO-only runs ✓ (Task 4 filter), no re-run of Posted/Scheduled ✓ (skip + queue dedupes pipeline+fixture), round-robin fixtures ✓ (Task 3), auto-run via Control UI ✓ (queue worker POSTs each job's own run_endpoint, Tasks 4–5).
- Gap to confirm during Task 2: exact `run_endpoint`/`status_endpoint` strings and per-route POST payloads — executor must copy from `pipelines.ts` + route files, not invent them.
- Placeholder scan: all code blocks concrete; Day+Night collapse rule explicit; unknown-idea behavior explicit (skip + report).
- Type consistency: `CalendarSlot` dict shape fixed in Task 1 and reused in Tasks 2–4.
