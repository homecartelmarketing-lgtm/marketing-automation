"""Collection Category Feed Pipeline API Blueprint (/api/collection-feed/*)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys
import threading
import time
from typing import Any

from flask import Blueprint, jsonify, request
import requests

from .common import (
    MARKETING_DIR,
    extract_clean_error,
    is_authorized,
    is_any_pipeline_running,
    load_settings,
    register_pipeline,
    unregister_pipeline,
)

collection_feed_bp = Blueprint("collection_feed", __name__, url_prefix="/api/collection-feed")


def get_fixtures() -> dict[str, dict[str, Any]]:
    return {
        "collection": {
            "id": "collection",
            "name": "5-Room Collection",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_COLLECTION_CATEGORY_FEED") or "tbl5o1j3XvUaUqmjs").strip(),
            "total": 100,
        },
    }


_EXEC_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": 5,
    "elapsed_seconds": 0,
    "logs": [],
    "error": None,
    "process": None,
    "start_time": None,
}
_STATE_LOCK = threading.Lock()
_COUNTS_CACHE: dict[str, Any] = {}
_COUNTS_CACHE_TTL = 30.0


@collection_feed_bp.route("/counts", methods=["GET"])
def get_counts():
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")
    if not force_refresh and "data" in _COUNTS_CACHE:
        if now - _COUNTS_CACHE["time"] < _COUNTS_CACHE_TTL:
            return jsonify({"status": "success", "counts": _COUNTS_CACHE["data"], "cached": True})

    fixtures = get_fixtures()
    results: dict[str, Any] = {}

    def fetch_fixture_data(fix_key: str, fix_info: dict[str, Any]):
        table_id = fix_info["table_id"]
        from content_automation.airtable_client import fetch_status_breakdown
        sc = fetch_status_breakdown(table_id)
        return fix_key, {
            "id": fix_info["id"],
            "name": fix_info["name"],
            "table_id": table_id,
            "completed": sc["C"],
            "total": fix_info["total"],
            "status_counts": sc,
        }

    with ThreadPoolExecutor(max_workers=len(fixtures)) as executor:
        futures = [executor.submit(fetch_fixture_data, k, v) for k, v in fixtures.items()]
        for fut in futures:
            try:
                key, val = fut.result()
                results[key] = val
            except Exception as e:
                pass

    _COUNTS_CACHE["data"] = results
    _COUNTS_CACHE["time"] = now
    return jsonify({"status": "success", "counts": results, "cached": False})


@collection_feed_bp.route("/status", methods=["GET"])
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


@collection_feed_bp.route("/run", methods=["POST"])
def run_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    max_items = min(max(int(data.get("max_items", 1)), 1), 10)
    fixtures = get_fixtures()
    fix_info = fixtures["collection"]

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Collection Category Feed pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": "collection",
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": 5,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Collection Category Feed ({max_items} set(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("collection-feed", _EXEC_STATE)
        cmd = [
            sys.executable,
            "run_collection_category_feed.py",
            "--phase", "all",
            "--max-rows", str(max_items),
            "--execute",
        ]
        try:
            p = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
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
                    if "phase 1" in txt.lower() or "room interior" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 1: Sequential 5-Room Krea Generation"
                        _EXEC_STATE["current_phase_index"] = 1
                    elif "phase 2" in txt.lower() or "vision analysis" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 2: Claude Sonnet 5 Room Matching"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "phase 3" in txt.lower() or "akeneo" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 3: Targeted Akeneo Catalog Scraper"
                        _EXEC_STATE["current_phase_index"] = 3
                    elif "phase 4" in txt.lower() or "blending prompt" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 4: Blending Prompt Engineering"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "phase 5" in txt.lower() or "blending" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 5: Nano Banana Pro Image Blending"
                        _EXEC_STATE["current_phase_index"] = 5

            p.wait()
            with _STATE_LOCK:
                if p.returncode == 0:
                    _EXEC_STATE["status"] = "completed"
                    _EXEC_STATE["current_phase"] = "Completed successfully"
                else:
                    _EXEC_STATE["status"] = "error"
                    _EXEC_STATE["error"] = f"Process exited with code {p.returncode}"
        except Exception as e:
            with _STATE_LOCK:
                _EXEC_STATE["status"] = "error"
                _EXEC_STATE["error"] = str(e)
        finally:
            unregister_pipeline("collection-feed")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fix_info["name"]})


@collection_feed_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("collection-feed")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
