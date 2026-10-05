"""Content Calendar XLSX Import API (/api/calendar/*).

Upload a Content Calendar workbook, preview which slots would run, and
enqueue them into the generation queue. Only slots with status ``TO DO``
are ever enqueued; Posted / Scheduled / NONE / N/A / blank slots are
reported as skipped. Enqueued jobs run through the normal queue worker,
so the Control UI runs them automatically.
"""

from __future__ import annotations

import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

from .common import MARKETING_DIR, is_authorized
from .queue_manager import get_server_port

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")

STATE_PATH = MARKETING_DIR / "output" / "calendar_fixture_state.json"


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _parse_upload(month: str) -> tuple[list[dict[str, Any]], str | None]:
    """Save the uploaded workbook to temp and parse its month slots."""
    from content_automation.calendar_import import parse_month_slots

    upload = request.files.get("file")
    if upload is None or not (upload.filename or "").strip():
        return [], "No .xlsx file uploaded (form field 'file')"
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in (".xlsx", ".xlsm"):
        return [], f"Unsupported file type '{suffix}': upload an .xlsx calendar"
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        upload.save(tmp.name)
        tmp.close()
        try:
            slots = parse_month_slots(tmp.name, month)
        except KeyError:
            return [], f"Month sheet '{month}' not found in workbook"
        except Exception as exc:
            return [], f"Could not parse calendar: {exc}"
        return slots, None
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except Exception:
            pass


def _build_preview_jobs(
    slots: list[dict[str, Any]], state: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from content_automation.calendar_import import build_jobs

    return build_jobs(slots, state)


@calendar_bp.route("/preview", methods=["POST"])
def preview_import():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    month = (request.form.get("month") or "October").strip() or "October"
    slots, err = _parse_upload(month)
    if err:
        return jsonify({"status": "error", "error": err}), 400
    # Preview with a COPY of the persisted pointer: no fixture turns consumed.
    jobs, skipped = _build_preview_jobs(slots, dict(_load_state()))
    return jsonify({
        "status": "success",
        "month": month,
        "jobs": jobs,
        "skipped": skipped,
        "job_count": len(jobs),
        "skipped_count": len(skipped),
    })


def _post_queue_enqueue(job: dict[str, Any], pin: str) -> dict[str, Any]:
    url = f"http://127.0.0.1:{get_server_port()}/api/queue/enqueue"
    body = {
        "pipeline_type": job["pipeline_type"],
        "pipeline_name": job.get("pipeline_name") or job["pipeline_type"],
        "fixture_id": job["fixture_id"],
        "fixture_name": job.get("fixture_name") or job["fixture_id"],
        "max_items": job.get("max_items", 1),
        "run_endpoint": job["run_endpoint"],
        "status_endpoint": job["status_endpoint"],
        "pin": pin,
    }
    payload = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if pin:
        headers["Authorization"] = f"Bearer {pin}"
        headers["X-Dashboard-PIN"] = pin
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": resp.status in (200, 201, 202), "response": data}
    except urllib.error.HTTPError as he:
        try:
            data = json.loads(he.read().decode("utf-8"))
        except Exception:
            data = {"error": str(he)}
        return {"ok": False, "response": data}
    except Exception as exc:
        return {"ok": False, "response": {"error": f"Queue connection error: {exc}"}}


@calendar_bp.route("/enqueue", methods=["POST"])
def enqueue_import():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    month = (request.form.get("month") or "October").strip() or "October"
    pin = (request.form.get("pin") or "").strip()
    slots, err = _parse_upload(month)
    if err:
        return jsonify({"status": "error", "error": err}), 400
    state = _load_state()
    jobs, skipped = _build_preview_jobs(slots, state)
    results: list[dict[str, Any]] = []
    for job in jobs:
        posted = _post_queue_enqueue(job, pin)
        results.append({
            "date": job.get("date"),
            "pipeline_type": job["pipeline_type"],
            "fixture_id": job["fixture_id"],
            "queued": bool(posted["ok"]),
            "queue_status": posted["response"].get("status"),
            "error": posted["response"].get("error"),
        })
    _save_state(state)
    return jsonify({
        "status": "success",
        "month": month,
        "enqueued": sum(1 for r in results if r["queued"]),
        "results": results,
        "skipped": skipped,
        "skipped_count": len(skipped),
    })
