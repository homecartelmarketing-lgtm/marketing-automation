"""Sale Banner Pipeline API Blueprint (/api/sale-banner/*)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Any

from flask import Blueprint, jsonify, request

from .common import (
    MARKETING_DIR,
    is_authorized,
    is_any_pipeline_running,
    register_pipeline,
    unregister_pipeline,
)

sale_banner_bp = Blueprint(
    "sale_banner", __name__, url_prefix="/api/sale-banner"
)

FIXTURE_ID = "sale_banner"
CATEGORY_LABEL = "Sale Banner"  # rows of this pipeline in the table it shares with the Christmas banner
PIPELINE_KEY = "sale-banner"
TABLE_ENV_KEYS = ("AIRTABLE_TABLE_ID_SALE_BANNER", "AIRTABLE_TABLE_ID_CHRISTMAS_BANNER")
DEFAULT_TABLE_ID = "tblgNk1Tp6qKUcduw"
SCRIPT_NAME = "generate_sale_banner_pipeline.py"
TOTAL_PHASES = 6
PHASE_LABELS = {
    1: "Phase 1: Akeneo Scrape (3 pendant lights)",
    2: "Phase 2: Krea Dining Room + Kitchen (4:5)",
    3: "Phase 3: Claude Vision Blending Prompts (2 rooms)",
    4: "Phase 4: Nano Banana Pro Room Blends (4:5)",
    5: "Phase 5: Sale Captions (Calendar) + Panel Colour (Claude)",
    6: "Phase 6: Sale Banner Composite (1800x600)",
}


def resolve_table_id() -> str:
    for key in TABLE_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return DEFAULT_TABLE_ID


def get_fixture() -> dict[str, Any]:
    return {
        "id": FIXTURE_ID,
        "name": "Sale Banner",
        "table_id": resolve_table_id(),
        "total": 100,
    }


_EXEC_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": TOTAL_PHASES,
    "elapsed_seconds": 0,
    "logs": [],
    "error": None,
    "process": None,
    "start_time": None,
}
_STATE_LOCK = threading.Lock()
_COUNTS_CACHE: dict[str, Any] = {}
_COUNTS_CACHE_TTL = 30.0


@sale_banner_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({"status": "success", "fixtures": [get_fixture()]})


@sale_banner_bp.route("/counts", methods=["GET"])
def get_counts():
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")
    if not force_refresh and "data" in _COUNTS_CACHE:
        if now - _COUNTS_CACHE["time"] < _COUNTS_CACHE_TTL:
            return jsonify({"status": "success", "counts": _COUNTS_CACHE["data"], "cached": True})

    fix = get_fixture()
    sc = {"P": 0, "S": 0, "C": 0, "D": 0, "FM": 0, "total": 0}
    try:
        from content_automation.airtable_client import fetch_status_breakdown
        sc = fetch_status_breakdown(fix["table_id"], category=CATEGORY_LABEL)
    except Exception:
        pass
    data = {
        FIXTURE_ID: {
            "id": FIXTURE_ID,
            "name": fix["name"],
            "table_id": fix["table_id"],
            "completed": sc.get("C", 0),
            "total": fix["total"],
            "status_counts": sc,
        }
    }
    _COUNTS_CACHE["data"] = data
    _COUNTS_CACHE["time"] = now
    return jsonify({"status": "success", "counts": data, "cached": False})


@sale_banner_bp.route("/status", methods=["GET"])
def get_status():
    with _STATE_LOCK:
        elapsed = int(time.time() - _EXEC_STATE["start_time"]) if _EXEC_STATE.get("start_time") else 0
        return jsonify({
            "status": _EXEC_STATE["status"],
            "active_fixture": _EXEC_STATE["active_fixture"],
            "active_table_id": _EXEC_STATE["active_table_id"],
            "current_phase": _EXEC_STATE["current_phase"],
            "current_phase_index": _EXEC_STATE["current_phase_index"],
            "total_phases": _EXEC_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "logs": _EXEC_STATE["logs"][-150:],
            "error": _EXEC_STATE["error"],
        })


@sale_banner_bp.route("/run", methods=["POST"])
def run_pipeline_route():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    fix_info = get_fixture()

    running, desc = is_any_pipeline_running()
    if running:
        return jsonify({"status": "error", "error": f"Another pipeline is currently active: {desc}"}), 409

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Sale Banner pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": FIXTURE_ID,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": TOTAL_PHASES,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Sale Banner (1800x600)..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline(PIPELINE_KEY, "Sale Banner")

        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / SCRIPT_NAME),
            "--table-id", fix_info["table_id"],
        ]

        try:
            p = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=os.environ.copy(),
                text=True,
                bufsize=1,
            )
            with _STATE_LOCK:
                _EXEC_STATE["process"] = p

            for line in iter(p.stdout.readline, ""):
                txt = line.strip()
                if not txt:
                    continue
                with _STATE_LOCK:
                    _EXEC_STATE["logs"].append(txt)
                    low = txt.lower()
                    # The pipeline prints "[PHASE n]" headers; only those move the phase.
                    for idx, label in PHASE_LABELS.items():
                        if f"[phase {idx}]" in low:
                            _EXEC_STATE["current_phase"] = label
                            _EXEC_STATE["current_phase_index"] = idx

            p.wait()
            rc = p.returncode

            with _STATE_LOCK:
                _EXEC_STATE["process"] = None
                if _EXEC_STATE["status"] == "stopped":
                    pass
                elif rc == 0:
                    _EXEC_STATE["status"] = "completed"
                    _EXEC_STATE["current_phase"] = "Completed"
                    _EXEC_STATE["current_phase_index"] = TOTAL_PHASES
                    _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Sale Banner completed successfully.")
                else:
                    _EXEC_STATE["status"] = "error"
                    _EXEC_STATE["error"] = f"Process exited with code {rc}"
                    _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] ERROR: Process failed with code {rc}")
        except Exception as e:
            with _STATE_LOCK:
                _EXEC_STATE["status"] = "error"
                _EXEC_STATE["error"] = str(e)
                _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Exception: {e}")
        finally:
            unregister_pipeline(PIPELINE_KEY)
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()

    return jsonify({
        "status": "success",
        "message": "Started Sale Banner",
        "fixture_id": FIXTURE_ID,
    })


@sale_banner_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["current_phase"] = "Stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline stopped by user.")
            unregister_pipeline(PIPELINE_KEY)
            return jsonify({"status": "success", "message": "Pipeline stopped"})
        return jsonify({"status": "error", "error": "No active pipeline to stop"}), 400
