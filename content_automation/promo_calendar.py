"""Sale percentages and caption dates for the Sale banner, read from the promotions calendar.

The HomeCartel promotions calendar PDF ("HC Monthly Promotions Calendar.pdf") is a single flattened
page, so its structured form, ``calendar_config.json`` (hand-transcribed from the PDF and used by
the monthly sale automation), is the runtime source. Two events matter here:

- ``ten_off_monthly``     "10% OFF (Chandelier + Pendant Light)"  (whole month)
- ``fifteen_off_monthly`` "15% OFF (Ceiling, Chandelier, Pendant, Table, Floor)"  (whole month)

The percent is parsed from each event name and the date window comes from the event
(``whole_month`` or ``start_md`` / ``end_md``), so the captions follow the calendar.
"""

from __future__ import annotations

import calendar as _calendar
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .errors import AutomationError

PHT = timezone(timedelta(hours=8))  # the calendar is in Asia/Manila
REPO_ROOT = Path(__file__).resolve().parents[1]

CALENDAR_ENV_KEY = "PROMO_CALENDAR_PATH"
TEN_EVENT_KEY = "ten_off_monthly"
FIFTEEN_EVENT_KEY = "fifteen_off_monthly"

# Caption wording matches the Canva sample; only the date is generated.
CAPTION_TEMPLATES = {
    TEN_EVENT_KEY: "On all items from curated monthly collection on {date}",
    FIFTEEN_EVENT_KEY: "On all items from a curated collection on {date}",
}

# run_monthly_sale.py plans the next month once the current one is nearly over.
NEXT_MONTH_FROM_DAY = 24


def calendar_candidates() -> list[Path]:
    """Where to look for calendar_config.json, in order."""
    candidates: list[Path] = []
    env = os.getenv(CALENDAR_ENV_KEY, "").strip()
    if env:
        candidates.append(Path(env))
    candidates.append(REPO_ROOT / "assets" / "calendar_config.json")
    candidates.append(REPO_ROOT.parent / "Auto Export Inventory" / "calendar_config.json")
    return candidates


def load_calendar(path: Path | str | None = None) -> dict[str, Any]:
    paths = [Path(path)] if path else calendar_candidates()
    for candidate in paths:
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data.get("events"), list):
                raise AutomationError(f"{candidate} has no 'events' list.")
            return data
    raise AutomationError(
        "calendar_config.json not found. Copy it to assets/ or set "
        f"{CALENDAR_ENV_KEY}. Looked in: " + ", ".join(str(p) for p in paths)
    )


def today_manila(as_of: date | None = None) -> date:
    return as_of or datetime.now(PHT).date()


def campaign_month(today: date | None = None, month: int | None = None, year: int | None = None) -> tuple[int, int]:
    """(month, year) the banner is for: explicit values win; otherwise this month, or next from day 24."""
    now = today_manila(today)
    if month is not None:
        if not 1 <= int(month) <= 12:
            raise AutomationError(f"--month must be 1-12 (got {month}).")
        return int(month), int(year or now.year)
    m, y = now.month, now.year
    if now.day >= NEXT_MONTH_FROM_DAY:
        m, y = (1, y + 1) if m == 12 else (m + 1, y)
    return m, int(year or y)


def find_event(cal: dict[str, Any], key: str) -> dict[str, Any]:
    for event in cal.get("events", []):
        if event.get("key") == key:
            return event
    raise AutomationError(f"Calendar event '{key}' not found in calendar_config.json.")


def percent_of_event(event: dict[str, Any]) -> int:
    match = re.search(r"(\d+)\s*%", str(event.get("name") or ""))
    if not match:
        raise AutomationError(f"Cannot read a discount percent from event name {event.get('name')!r}.")
    return int(match.group(1))


def _md(value: str, year: int) -> date:
    month, day = (int(part) for part in str(value).split("-"))
    return date(year, month, day)


def event_window(event: dict[str, Any], month: int, year: int) -> tuple[date, date]:
    """First and last day the event runs for the target month/year."""
    if event.get("whole_month"):
        return date(year, month, 1), date(year, month, _calendar.monthrange(year, month)[1])
    if event.get("start_md") and event.get("end_md"):
        start = _md(event["start_md"], year)
        end = _md(event["end_md"], year)
        if end < start:  # window crosses New Year
            end = _md(event["end_md"], year + 1)
        return start, end
    raise AutomationError(f"Event {event.get('key')!r} has neither whole_month nor start_md/end_md.")


def format_window(start: date, end: date) -> str:
    """Window text with the year: 'October 1-31, 2026', 'October 25 - November 30, 2026',
    'December 25, 2026 - January 5, 2027' (crosses New Year), 'December 12, 2026' (single day)."""
    if start == end:
        return f"{start:%B} {start.day}, {start.year}"
    if start.year != end.year:
        return f"{start:%B} {start.day}, {start.year} - {end:%B} {end.day}, {end.year}"
    if start.month == end.month:
        return f"{start:%B} {start.day}-{end.day}, {end.year}"
    return f"{start:%B} {start.day} - {end:%B} {end.day}, {end.year}"


@dataclass(frozen=True)
class SaleCaption:
    key: str
    percent: int
    date_text: str
    caption: str


def build_sale_captions(
    cal: dict[str, Any] | None = None,
    *,
    month: int | None = None,
    year: int | None = None,
    today: date | None = None,
) -> list[SaleCaption]:
    """The two sale captions (10% then 15%) for the target month, in banner order (left, right)."""
    cal = cal or load_calendar()
    target_month, target_year = campaign_month(today, month, year)
    out: list[SaleCaption] = []
    for key in (TEN_EVENT_KEY, FIFTEEN_EVENT_KEY):
        event = find_event(cal, key)
        start, end = event_window(event, target_month, target_year)
        date_text = format_window(start, end)
        out.append(SaleCaption(
            key=key,
            percent=percent_of_event(event),
            date_text=date_text,
            caption=CAPTION_TEMPLATES[key].format(date=date_text),
        ))
    return out
