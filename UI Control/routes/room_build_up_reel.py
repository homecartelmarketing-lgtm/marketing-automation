"""Room Build-Up Reel Pipeline API Blueprint (/api/room-build-up-reel/*)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Any

from flask import Blueprint, jsonify, request

from .common import (
    MARKETING_DIR,
    extract_clean_error,
    is_authorized,
    register_pipeline,
    save_config_override,
    unregister_pipeline,
)

room_build_up_reel_bp = Blueprint(
    "room_build_up_reel", __name__, url_prefix="/api/room-build-up-reel"
)

FIXTURE_ID = "room-build-up"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_ROOM_BUILD_UP_REEL"
TABLE_DEFAULT = "tblhq1rz9CVCD7yiR"
# The reel has two rooms, each with its own moodboard. The Studio pencil edits one value and applies it to both.
MOODBOARD_ENV_KEYS = (
    "KREA_MOODBOARD_ID_ROOM_BUILD_UP_REEL_ROOM1",
    "KREA_MOODBOARD_ID_ROOM_BUILD_UP_REEL_ROOM2",
)
MOODBOARD_DEFAULT = "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3"
# Same for the Krea interior prompt: one Studio edit is applied to both rooms.
# The pipeline reads these env keys directly (generate_room_build_up_reel_pipeline._room_prompt).
PROMPT_ENV_KEYS = (
    "PROMPT_ROOM_BUILD_UP_REEL_ROOM1",
    "PROMPT_ROOM_BUILD_UP_REEL_ROOM2",
)
PROMPT_DEFAULT = "Generate me a modern living room"
TOTAL_PHASES = 7

PHASE_LABELS: dict[int, str] = {
    1: "Phase 1: Akeneo Scraper (Pendant + Chandelier)",
    2: "Phase 2: Krea Furnished Interiors",
    3: "Phase 3: Claude Blending Prompts",
    4: "Phase 4: Nano Banana Pro Fixture Blend",
    5: "Phase 5: Claude Removal Plans",
    6: "Phase 6: Nano Banana Pro Removals",
    7: "Phase 7: Hard-Cut Assembly + Sound",
}
_PHASE_RE = re.compile(r"\[PHASE\s+(\d+)\s*/\s*\d+\]", re.IGNORECASE)


def update_phase_from_log(state: dict[str, Any], line: str) -> None:
    """Advance the phase from an explicit `[PHASE n/7]` log marker (never moves backwards)."""
    match = _PHASE_RE.search(line)
    if not match:
        return
    idx = int(match.group(1))
    if idx in PHASE_LABELS and idx >= int(state.get("current_phase_index") or 0):
        state["current_phase"] = PHASE_LABELS[idx]
        state["current_phase_index"] = idx


def get_fixture() -> dict[str, Any]:
    return {
        "id": FIXTURE_ID,
        "name": "Room Build-Up",
        "table_id": (os.getenv(TABLE_ENV_KEY) or TABLE_DEFAULT).strip(),
        "total": 100,
        "moodboard_id": (os.getenv(MOODBOARD_ENV_KEYS[0]) or MOODBOARD_DEFAULT).strip(),
        "prompt": (os.getenv(PROMPT_ENV_KEYS[0]) or PROMPT_DEFAULT).strip(),
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


@room_build_up_reel_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({"status": "success", "fixtures": [get_fixture()]})


@room_build_up_reel_bp.route("/counts", methods=["GET"])
def get_counts():
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")
    if not force_refresh and "data" in _COUNTS_CACHE:
        if now - _COUNTS_CACHE["time"] < _COUNTS_CACHE_TTL:
            return jsonify({"status": "success", "counts": _COUNTS_CACHE["data"], "cached": True})

    fixture = get_fixture()
    results: dict[str, Any] = {}
    try:
        from content_automation.airtable_client import fetch_status_breakdown

        sc = fetch_status_breakdown(fixture["table_id"])
        results[FIXTURE_ID] = {
            "id": fixture["id"],
            "name": fixture["name"],
            "table_id": fixture["table_id"],
            "completed": sc["C"],
            "total": fixture["total"],
            "moodboard_id": fixture["moodboard_id"],
            "prompt": fixture["prompt"],
            "status_counts": sc,
        }
    except Exception:
        pass

    _COUNTS_CACHE["data"] = results
    _COUNTS_CACHE["time"] = now
    return jsonify({"status": "success", "counts": results, "cached": False})


@room_build_up_reel_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    moodboard_id = (data.get("moodboard_id") or "").strip()
    if not moodboard_id:
        return jsonify({"status": "error", "error": "moodboard_id required"}), 400
    for env_key in MOODBOARD_ENV_KEYS:
        save_config_override(env_key, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "moodboard_id": moodboard_id})


@room_build_up_reel_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    prompt_text = (data.get("prompt") or "").strip()
    if not prompt_text:
        return jsonify({"status": "error", "error": "prompt required"}), 400
    for env_key in PROMPT_ENV_KEYS:
        save_config_override(env_key, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "prompt": prompt_text})


@room_build_up_reel_bp.route("/status", methods=["GET"])
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


@room_build_up_reel_bp.route("/run", methods=["POST"])
def run_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    custom_moodboard = (data.get("moodboard_id") or "").strip()
    max_items = min(max(int(data.get("max_items", 1)), 1), 10)
    fixture = get_fixture()

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Room Build-Up Reel pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": FIXTURE_ID,
            "active_table_id": fixture["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": TOTAL_PHASES,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Room Build-Up Reel ({max_items} row(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("room-build-up-reel", "Room Build-Up Reel")
        cmd = [
            sys.executable,
            "-u",
            "run_room_build_up_reel.py",
            "--table-id", fixture["table_id"],
            "--max-rows", str(max_items),
        ]
        if custom_moodboard:
            cmd += ["--moodboard-id", custom_moodboard]
        try:
            p = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
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
                    update_phase_from_log(_EXEC_STATE, txt)
            p.wait()
            with _STATE_LOCK:
                if p.returncode == 0:
                    _EXEC_STATE["status"] = "completed"
                    _EXEC_STATE["current_phase"] = "Completed successfully"
                else:
                    _EXEC_STATE["status"] = "error"
                    _EXEC_STATE["error"] = extract_clean_error(_EXEC_STATE["logs"], p.returncode)
        except Exception as e:
            with _STATE_LOCK:
                _EXEC_STATE["status"] = "error"
                _EXEC_STATE["error"] = str(e)
        finally:
            unregister_pipeline("room-build-up-reel")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fixture["name"]})


@room_build_up_reel_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("room-build-up-reel")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
