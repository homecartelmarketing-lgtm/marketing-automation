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
