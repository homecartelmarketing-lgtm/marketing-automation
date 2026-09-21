"""Unified FIFO Generation Queue Manager for HomeCartel Marketing Studio.

Enables cross-tab sequential content generation:
- Tracks the active executing job (with phase, progress, elapsed time, and logs).
- Maintains a FIFO pending queue of jobs submitted from any tab (Story, Feed, Reel).
- Automatically triggers the next job when the current job completes or fails.
- Provides REST endpoints:
    GET  /api/queue/status       -> Active job, pending queue, and recent history
    POST /api/queue/enqueue      -> Submit a new job (starts immediately if idle)
    POST /api/queue/cancel       -> Cancel/remove a pending job from queue
    POST /api/queue/clear        -> Remove all pending jobs from queue
    POST /api/queue/stop-current -> Stop the active running job (advances to next)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from flask import Blueprint, jsonify, request

CURRENT_DIR = Path(__file__).resolve().parent.parent
MARKETING_DIR = CURRENT_DIR.parent

if str(MARKETING_DIR) not in sys.path:
    sys.path.insert(0, str(MARKETING_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from routes.common import DASHBOARD_PIN, is_authorized

queue_bp = Blueprint("queue", __name__, url_prefix="/api/queue")

# ---------------------------------------------------------------------------
# State Structures
# ---------------------------------------------------------------------------
_QUEUE_LOCK = threading.Lock()
_ACTIVE_JOB: dict[str, Any] | None = None
_PENDING_QUEUE: list[dict[str, Any]] = []
_JOB_HISTORY: list[dict[str, Any]] = []
_WORKER_THREAD: threading.Thread | None = None
_SERVER_PORT: int = 5200


def set_server_port(port: int) -> None:
    global _SERVER_PORT
    _SERVER_PORT = port


def get_server_port() -> int:
    port_env = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT") or os.environ.get("PORT")
    if port_env:
        try:
            return int(port_env)
        except Exception:
            pass
    return _SERVER_PORT


# ---------------------------------------------------------------------------
# Internal HTTP Helpers
# ---------------------------------------------------------------------------
def _dispatch_job_run(job: dict[str, Any]) -> tuple[bool, str]:
    """Trigger the pipeline's run endpoint via internal HTTP POST."""
    port = get_server_port()
    endpoint = job.get("run_endpoint", "")
    if not endpoint:
        return False, "No run_endpoint specified in job"

    url = f"http://127.0.0.1:{port}{endpoint}"
    payload = json.dumps({
        "fixture_id": job.get("fixture_id"),
        "max_items": job.get("max_items", 1),
        "moodboard_id": job.get("moodboard_id"),
        "prompt": job.get("prompt"),
        "pin": job.get("pin", ""),
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }
    pin = job.get("pin", "")
    if pin:
        headers["Authorization"] = f"Bearer {pin}"
        headers["X-Dashboard-PIN"] = pin

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if resp.status in (200, 201, 202):
                return True, data.get("message") or "Pipeline started successfully"
            return False, data.get("error") or f"HTTP {resp.status}"
    except urllib.error.HTTPError as he:
        try:
            body = json.loads(he.read().decode("utf-8"))
            err_msg = body.get("error") or body.get("message") or str(he)
        except Exception:
            err_msg = str(he)
        return False, f"Run failed ({he.code}): {err_msg}"
    except Exception as exc:
        return False, f"Dispatch connection error: {exc}"


def _fetch_job_status(job: dict[str, Any]) -> dict[str, Any]:
    """Query the pipeline's status endpoint via internal HTTP GET."""
    port = get_server_port()
    endpoint = job.get("status_endpoint", "")
    if not endpoint:
        return {"status": "error", "error": "No status_endpoint specified"}

    url = f"http://127.0.0.1:{port}{endpoint}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"status": "running", "error": f"Status check error: {exc}"}


def _dispatch_job_stop(job: dict[str, Any]) -> tuple[bool, str]:
    """Trigger the pipeline's stop endpoint via internal HTTP POST."""
    port = get_server_port()
    endpoint = job.get("stop_endpoint", "")
    if not endpoint:
        return False, "No stop_endpoint specified"

    url = f"http://127.0.0.1:{port}{endpoint}"
    headers = {"Content-Type": "application/json"}
    pin = job.get("pin", "")
    if pin:
        headers["Authorization"] = f"Bearer {pin}"
        headers["X-Dashboard-PIN"] = pin

    try:
        req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data.get("status") or "Pipeline stopped"
    except Exception as exc:
        return False, f"Stop request error: {exc}"


# ---------------------------------------------------------------------------
# Background Queue Worker Loop
# ---------------------------------------------------------------------------
def _queue_worker_loop() -> None:
    """Continuous background worker loop processing jobs FIFO."""
    global _ACTIVE_JOB, _PENDING_QUEUE, _JOB_HISTORY

    while True:
        try:
            with _QUEUE_LOCK:
                # If no active job, check if we can pop the next pending job
                if _ACTIVE_JOB is None and _PENDING_QUEUE:
                    next_job = _PENDING_QUEUE.pop(0)
                    next_job["status"] = "running"
                    next_job["started_at"] = time.time()
                    next_job["current_phase"] = "Initializing in Queue Worker..."
                    next_job["current_phase_index"] = 0
                    next_job["elapsed_seconds"] = 0
                    next_job["logs"] = [f"[{time.strftime('%X')}] Picked from Generation Queue: {next_job.get('fixture_name')}"]
                    next_job["_dispatched"] = False
                    _ACTIVE_JOB = next_job

                curr_job = dict(_ACTIVE_JOB) if _ACTIVE_JOB is not None else None

            if not curr_job:
                time.sleep(1.0)
                continue

            # If the active job hasn't been dispatched to its /run endpoint yet, dispatch it now
            if not curr_job.get("_dispatched"):
                success, msg = _dispatch_job_run(curr_job)
                with _QUEUE_LOCK:
                    if _ACTIVE_JOB and _ACTIVE_JOB["id"] == curr_job["id"]:
                        _ACTIVE_JOB["_dispatched"] = True
                        if not success:
                            _ACTIVE_JOB["status"] = "error"
                            _ACTIVE_JOB["error"] = msg
                            _ACTIVE_JOB["logs"].append(f"[{time.strftime('%X')}] ERROR: {msg}")
                        else:
                            _ACTIVE_JOB["logs"].append(f"[{time.strftime('%X')}] Successfully dispatched: {msg}")

                if not success:
                    # Move directly to history as failed
                    with _QUEUE_LOCK:
                        if _ACTIVE_JOB and _ACTIVE_JOB["id"] == curr_job["id"]:
                            hist_item = dict(_ACTIVE_JOB)
                            hist_item["finished_at"] = time.time()
                            hist_item["duration_seconds"] = int(time.time() - hist_item.get("started_at", time.time()))
                            _JOB_HISTORY.insert(0, hist_item)
                            if len(_JOB_HISTORY) > 30:
                                _JOB_HISTORY.pop()
                            _ACTIVE_JOB = None
                    time.sleep(2.0)
                    continue

            # Poll status of the running pipeline
            status_data = _fetch_job_status(curr_job)
            run_status = status_data.get("status", "running")

            with _QUEUE_LOCK:
                if _ACTIVE_JOB and _ACTIVE_JOB["id"] == curr_job["id"]:
                    _ACTIVE_JOB["current_phase"] = status_data.get("current_phase") or _ACTIVE_JOB.get("current_phase")
                    _ACTIVE_JOB["current_phase_index"] = status_data.get("current_phase_index", _ACTIVE_JOB.get("current_phase_index", 0))
                    _ACTIVE_JOB["total_phases"] = status_data.get("total_phases", _ACTIVE_JOB.get("total_phases", 5))
                    _ACTIVE_JOB["elapsed_seconds"] = status_data.get("elapsed_seconds") or int(time.time() - _ACTIVE_JOB.get("started_at", time.time()))
                    if "logs" in status_data and isinstance(status_data["logs"], list):
                        _ACTIVE_JOB["logs"] = status_data["logs"][-100:]
                    if "error" in status_data and status_data["error"]:
                        _ACTIVE_JOB["error"] = status_data["error"]

            # If finished (completed, error, or stopped)
            if run_status in ("completed", "success", "done", "error", "stopped"):
                with _QUEUE_LOCK:
                    if _ACTIVE_JOB and _ACTIVE_JOB["id"] == curr_job["id"]:
                        hist_item = dict(_ACTIVE_JOB)
                        hist_item["status"] = "completed" if run_status in ("completed", "success", "done") else run_status
                        hist_item["finished_at"] = time.time()
                        hist_item["duration_seconds"] = int(time.time() - hist_item.get("started_at", time.time()))
                        _JOB_HISTORY.insert(0, hist_item)
                        if len(_JOB_HISTORY) > 30:
                            _JOB_HISTORY.pop()
                        _ACTIVE_JOB = None

                # Cool-off pause between consecutive queue items
                time.sleep(2.0)
            else:
                time.sleep(1.5)

        except Exception as exc:
            print(f"[Queue Worker Exception] {exc}")
            time.sleep(2.0)


def ensure_worker_started() -> None:
    """Ensure the background queue processor thread is running."""
    global _WORKER_THREAD
    with _QUEUE_LOCK:
        if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
            _WORKER_THREAD = threading.Thread(target=_queue_worker_loop, daemon=True, name="GenerationQueueWorker")
            _WORKER_THREAD.start()


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------
@queue_bp.route("/status", methods=["GET"])
def get_queue_status():
    """Return active running job, pending FIFO queue, and recent history."""
    ensure_worker_started()
    with _QUEUE_LOCK:
        active_clean = None
        if _ACTIVE_JOB:
            active_clean = {
                "id": _ACTIVE_JOB.get("id"),
                "pipeline_type": _ACTIVE_JOB.get("pipeline_type"),
                "pipeline_name": _ACTIVE_JOB.get("pipeline_name"),
                "fixture_id": _ACTIVE_JOB.get("fixture_id"),
                "fixture_name": _ACTIVE_JOB.get("fixture_name"),
                "format_tab": _ACTIVE_JOB.get("format_tab"),
                "subtab_index": _ACTIVE_JOB.get("subtab_index"),
                "table_id": _ACTIVE_JOB.get("table_id"),
                "current_phase": _ACTIVE_JOB.get("current_phase", "Processing..."),
                "current_phase_index": _ACTIVE_JOB.get("current_phase_index", 0),
                "total_phases": _ACTIVE_JOB.get("total_phases", 5),
                "elapsed_seconds": _ACTIVE_JOB.get("elapsed_seconds", 0),
                "logs": _ACTIVE_JOB.get("logs", [])[-100:],
                "error": _ACTIVE_JOB.get("error"),
                "status": _ACTIVE_JOB.get("status", "running"),
                "started_at": _ACTIVE_JOB.get("started_at"),
            }

        queue_clean = [
            {
                "id": j.get("id"),
                "pipeline_type": j.get("pipeline_type"),
                "pipeline_name": j.get("pipeline_name"),
                "fixture_id": j.get("fixture_id"),
                "fixture_name": j.get("fixture_name"),
                "format_tab": j.get("format_tab"),
                "subtab_index": j.get("subtab_index"),
                "table_id": j.get("table_id"),
                "enqueued_at": j.get("enqueued_at"),
                "status": "pending",
                "max_items": j.get("max_items", 1),
            }
            for j in _PENDING_QUEUE
        ]

        history_clean = [
            {
                "id": h.get("id"),
                "pipeline_name": h.get("pipeline_name"),
                "fixture_name": h.get("fixture_name"),
                "format_tab": h.get("format_tab"),
                "status": h.get("status"),
                "duration_seconds": h.get("duration_seconds", 0),
                "finished_at": h.get("finished_at"),
                "error": h.get("error"),
            }
            for h in _JOB_HISTORY[:15]
        ]

        return jsonify({
            "status": "success",
            "is_busy": _ACTIVE_JOB is not None,
            "active_job": active_clean,
            "queue": queue_clean,
            "queue_length": len(queue_clean),
            "history": history_clean,
        })


@queue_bp.route("/enqueue", methods=["POST"])
def enqueue_job():
    """Submit a content generation job into the queue."""
    global _ACTIVE_JOB
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    ensure_worker_started()
    data = request.get_json(silent=True) or {}

    pipeline_type = str(data.get("pipeline_type", "")).strip()
    fixture_id = str(data.get("fixture_id", "")).strip()
    run_endpoint = str(data.get("run_endpoint", "")).strip()
    status_endpoint = str(data.get("status_endpoint", "")).strip()

    if not pipeline_type or not fixture_id or not run_endpoint or not status_endpoint:
        return jsonify({
            "status": "error",
            "error": "Missing required fields: pipeline_type, fixture_id, run_endpoint, status_endpoint",
        }), 400

    job_id = f"job_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    pin = str(data.get("pin", "")).strip()

    new_job = {
        "id": job_id,
        "pipeline_type": pipeline_type,
        "pipeline_name": str(data.get("pipeline_name", pipeline_type)),
        "fixture_id": fixture_id,
        "fixture_name": str(data.get("fixture_name", fixture_id)),
        "format_tab": str(data.get("format_tab", "feed")),
        "subtab_index": int(data.get("subtab_index", 0)),
        "table_id": str(data.get("table_id", "")),
        "moodboard_id": data.get("moodboard_id"),
        "prompt": data.get("prompt"),
        "max_items": min(max(int(data.get("max_items", 1)), 1), 10),
        "run_endpoint": run_endpoint,
        "status_endpoint": status_endpoint,
        "stop_endpoint": str(data.get("stop_endpoint", "")),
        "pin": pin,
        "enqueued_at": time.time(),
        "status": "pending",
        "_dispatched": False,
    }

    with _QUEUE_LOCK:
        # Check if already in queue to prevent duplicate spamming
        for existing in _PENDING_QUEUE:
            if existing.get("pipeline_type") == pipeline_type and existing.get("fixture_id") == fixture_id:
                return jsonify({
                    "status": "already_queued",
                    "message": f"Fixture '{new_job['fixture_name']}' is already in the generation queue.",
                    "job_id": existing.get("id"),
                }), 200

        # If currently idle, set directly as active job
        if _ACTIVE_JOB is None:
            new_job["status"] = "running"
            new_job["started_at"] = time.time()
            new_job["current_phase"] = "Starting generation..."
            new_job["current_phase_index"] = 0
            new_job["elapsed_seconds"] = 0
            new_job["logs"] = [f"[{time.strftime('%X')}] Direct Start: {new_job['fixture_name']}"]
            _ACTIVE_JOB = new_job
            queue_pos = 0
            action_status = "started"
            message = f"Started generation for {new_job['fixture_name']}"
        else:
            _PENDING_QUEUE.append(new_job)
            queue_pos = len(_PENDING_QUEUE)
            action_status = "queued"
            message = f"Added {new_job['fixture_name']} to generation queue (#{queue_pos} in line)"

    return jsonify({
        "status": action_status,
        "message": message,
        "job_id": job_id,
        "queue_position": queue_pos,
        "fixture_name": new_job["fixture_name"],
    }), 201 if action_status == "queued" else 200


@queue_bp.route("/cancel", methods=["POST"])
def cancel_queued_job():
    """Cancel and remove a pending job from the queue."""
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    job_id = str(data.get("job_id", "")).strip()
    fixture_id = str(data.get("fixture_id", "")).strip()

    if not job_id and not fixture_id:
        return jsonify({"status": "error", "error": "job_id or fixture_id required"}), 400

    removed = False
    removed_name = ""
    with _QUEUE_LOCK:
        idx = -1
        for i, j in enumerate(_PENDING_QUEUE):
            if (job_id and j.get("id") == job_id) or (fixture_id and j.get("fixture_id") == fixture_id):
                idx = i
                removed_name = j.get("fixture_name", "")
                break
        if idx >= 0:
            cancelled = _PENDING_QUEUE.pop(idx)
            cancelled["status"] = "cancelled"
            cancelled["finished_at"] = time.time()
            _JOB_HISTORY.insert(0, cancelled)
            removed = True

    if removed:
        return jsonify({
            "status": "success",
            "message": f"Removed '{removed_name}' from generation queue.",
        })
    return jsonify({
        "status": "not_found",
        "message": "Job was not found in pending queue.",
    }), 404


@queue_bp.route("/clear", methods=["POST"])
def clear_queue():
    """Clear all pending jobs in the queue."""
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    with _QUEUE_LOCK:
        count = len(_PENDING_QUEUE)
        for j in _PENDING_QUEUE:
            j["status"] = "cancelled"
            j["finished_at"] = time.time()
            _JOB_HISTORY.insert(0, j)
        _PENDING_QUEUE.clear()

    return jsonify({
        "status": "success",
        "message": f"Cleared {count} item(s) from generation queue.",
        "cleared_count": count,
    })


@queue_bp.route("/stop-current", methods=["POST"])
def stop_current_job():
    """Stop the actively running job and advance to the next queued item."""
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    curr_job = None
    with _QUEUE_LOCK:
        if _ACTIVE_JOB:
            curr_job = dict(_ACTIVE_JOB)

    if not curr_job:
        return jsonify({"status": "idle", "message": "No pipeline is currently executing."})

    success, msg = _dispatch_job_stop(curr_job)
    with _QUEUE_LOCK:
        if _ACTIVE_JOB and _ACTIVE_JOB["id"] == curr_job["id"]:
            _ACTIVE_JOB["status"] = "stopped"
            _ACTIVE_JOB["logs"].append(f"[{time.strftime('%X')}] Stopped via Queue Controller.")

    return jsonify({
        "status": "stopping",
        "message": f"Stop request sent to {curr_job.get('fixture_name')}: {msg}",
    })
