"""Import Content Calendar TO DO slots into the Studio generation queue.

Parses one month sheet from the Content Calendar workbook, builds queue jobs
for the TO DO slots, and POSTs them to /api/queue/enqueue.

Usage::

    python scripts/ops/import_content_calendar.py --file calendar.xlsx
    python scripts/ops/import_content_calendar.py --file calendar.xlsx --dry-run
    python scripts/ops/import_content_calendar.py --file calendar.xlsx --pin 1234
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_automation.calendar_import import (  # noqa: E402
    build_jobs,
    parse_month_slots,
)

STATE_PATH = ROOT / "output" / "calendar_fixture_state.json"


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def enqueue_job(queue_url: str, job: dict, pin: str | None = None) -> dict:
    """POST one job to /api/queue/enqueue. Raises on HTTP/network errors."""
    body = dict(job)
    if pin:
        body["pin"] = pin
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        queue_url.rstrip("/") + "/api/queue/enqueue",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if pin:
        req.add_header("Authorization", f"Bearer {pin}")
        req.add_header("X-Dashboard-PIN", pin)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
            msg = detail.get("error") or detail.get("message") or str(exc)
        except Exception:
            msg = str(exc)
        raise RuntimeError(f"enqueue failed (HTTP {exc.code}): {msg}") from exc
    except OSError as exc:
        raise RuntimeError(f"enqueue connection error: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import Content Calendar TO DO slots into the Studio queue."
    )
    parser.add_argument("--file", required=True, help="Content Calendar .xlsx path")
    parser.add_argument("--month", default="October", help="Month sheet name")
    parser.add_argument("--queue-url", default="http://127.0.0.1:5200",
                        help="Studio base URL")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the job table and exit 0 without POSTing")
    parser.add_argument("--pin", default=None,
                        help="Studio PIN, forwarded as pin when set")
    args = parser.parse_args(argv)

    try:
        slots = parse_month_slots(args.file, args.month)
    except KeyError:
        print(f"error: month sheet {args.month!r} is not supported "
              f"(only the October sheet exists in the current map)",
              file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot read workbook: {exc}", file=sys.stderr)
        return 2

    state = load_state()
    jobs, skipped = build_jobs(slots, state)

    for job in jobs:
        print(f"{job['date']}  {job['pipeline_type']}  {job['fixture_id']}")

    if args.dry_run:
        print(f"dry-run: {len(jobs)} job(s), {len(skipped)} skipped; no POSTs sent")
        return 0

    enqueued = 0
    for job in jobs:
        try:
            enqueue_job(args.queue_url, job, args.pin)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        enqueued += 1

    save_state(state)

    print(f"enqueued: {enqueued}")
    for reason, count in sorted(Counter(s["reason"] for s in skipped).items()):
        print(f"skipped [{reason}]: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
