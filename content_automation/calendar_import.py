"""Parse Content Calendar month sheets into slot records."""
from __future__ import annotations
import datetime
import json
from pathlib import Path

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


MAP_PATH = Path(__file__).resolve().parent.parent / "assets" / "calendar_pipeline_map.json"


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def resolve_job(format: str, idea: str) -> dict | None:
    entry = _load_map().get(f"{format} :: {idea.strip()}")
    if entry is None or entry.get("skip"):
        return None
    return dict(entry)


def collapse_day_night(slots: list[dict]) -> list[dict]:
    """Collapse a same-date Day (D&N) + Night (D&N) pair into one Day & Night slot."""
    by_date: dict[str, list[int]] = {}
    for i, s in enumerate(slots):
        by_date.setdefault(s.get("date", ""), []).append(i)
    drop: set[int] = set()
    out = [dict(s) for s in slots]
    for idxs in by_date.values():
        day_i = next((i for i in idxs if out[i].get("idea", "").strip() == "Day (D&N)"), None)
        night_i = next((i for i in idxs if out[i].get("idea", "").strip() == "Night (D&N)"), None)
        if day_i is not None and night_i is not None:
            out[day_i]["idea"] = "Day & Night"
            drop.add(night_i)
    return [s for i, s in enumerate(out) if i not in drop]


def pick_fixture(pipeline_type: str, state: dict, fixtures: list[str]) -> str:
    idx = int(state.get(pipeline_type, 0)) % len(fixtures)
    state[pipeline_type] = int(state.get(pipeline_type, 0)) + 1
    return fixtures[idx]


# Fixture `id` values copied verbatim from each route's get_*_fixtures()
# (fixture ids for the config-driven reel routes are the TABLE_CONFIG keys,
# since get_fixtures() sets each fixture's "id" to its config key).
PIPELINE_FIXTURES: dict[str, list[str]] = {
    "product-showcase-feed": ["table-lamp"],
    "collection-feed": ["collection"],
    "tips-edu-feed": ["chandelier", "pendant", "floor-lamp", "cluster-chandelier"],
    "cta": ["chandelier", "pendant", "cluster-chandelier", "table-lamp", "floor-lamp"],
    "tips-edu": ["pendant", "floor-lamp", "chandelier", "ceiling-mounted",
                 "table-lamp", "cluster-chandelier"],
    "sketch-to-draw-reel": ["chandeliers", "pendant", "floor_lamp",
                             "table_lamp", "ceiling_mounted"],
    "moodboard-reel": ["chandelier", "pendant", "cluster-chandelier",
                       "linear-chandelier", "floor-lamp", "wall-sconce",
                       "table-lamp"],
    "one-product-3-styles": ["pendant", "floor-lamp", "chandelier"],
    "day-night-feed": ["chandelier", "pendant", "floor-lamp", "table-lamp"],
    "moodboard-1-feed": ["chandelier", "pendant", "floor-lamp"],
    "moodboard-2-feed": ["chandelier", "pendant", "floor-lamp", "wall-light"],
    "one-product-three-styles-reel": ["chandelier"],
    "before-after-reel": ["pendant", "chandelier"],
    "day-night-reel": ["pendant", "chandelier", "floor-lamp"],
    "one-at-a-time-lights-reel": ["living-room"],
    "product-closeup-reel": ["table-lamp"],
    "style-reel-slideshow": ["style-tour"],
    "collec-story": ["pendant", "wall-light", "chandelier", "floor-lamp",
                     "cluster-chandelier"],
    "day-night-story": ["chandelier", "pendant", "floor-lamp", "table-lamp",
                        "cluster-chandelier"],
    "moodboard-story": ["chandelier", "pendant", "floor-lamp"],
    "product-specs": ["chandelier"],
    "product-desc-story": ["chandelier", "pendant", "floor-lamp",
                           "cluster-chandelier", "table-lamp", "wall-light"],
    "style-this": ["chandelier", "floor-lamp"],
    "myth-fact-story": ["chandelier", "floor-lamp", "pendant"],
    "this-or-that-story": ["chandelier", "pendant", "floor-lamp",
                           "cluster-chandelier", "table-lamp", "wall-light"],
}


def build_jobs(slots: list[dict], state: dict) -> tuple[list[dict], list[dict]]:
    """Build queue jobs for the TO DO slots in one calendar import.

    Returns (jobs, skipped) where each job has {date, pipeline_type,
    pipeline_name, fixture_id, run_endpoint, status_endpoint, max_items: 1}
    and each skipped entry has {date, idea, status, reason}.
    """
    jobs: list[dict] = []
    skipped: list[dict] = []
    seen: set[tuple] = set()
    pipeline_map = _load_map()
    for s in collapse_day_night(slots):
        date = s.get("date")
        idea = s.get("idea")
        status = s.get("status", "")
        if status != "TO DO":
            skipped.append({"date": date, "idea": idea, "status": status,
                            "reason": f"not-todo:{status}"})
            continue
        entry = pipeline_map.get(f"{s.get('format', '')} :: {(idea or '').strip()}")
        job = resolve_job(s.get("format", ""), idea or "")
        if job is None:
            reason = (entry or {}).get("reason") or "unknown-idea"
            skipped.append({"date": date, "idea": idea, "status": status,
                            "reason": reason})
            continue
        pipeline_type = job["pipeline_type"]
        fixture_id = pick_fixture(
            pipeline_type, state, PIPELINE_FIXTURES[pipeline_type])
        key = (date, pipeline_type, fixture_id)
        if key in seen:
            skipped.append({"date": date, "idea": idea, "status": status,
                            "reason": "duplicate"})
            continue
        seen.add(key)
        jobs.append({
            "date": date,
            "pipeline_type": pipeline_type,
            "pipeline_name": pipeline_type,
            "fixture_id": fixture_id,
            "run_endpoint": job["run_endpoint"],
            "status_endpoint": job["status_endpoint"],
            "max_items": 1,
        })
    return jobs, skipped
