"""Moodboard #1 Feed Pipeline API Blueprint (/api/moodboard-1-feed/*)."""

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
    save_config_override,
    unregister_pipeline,
)

moodboard_1_feed_bp = Blueprint("moodboard_1_feed", __name__, url_prefix="/api/moodboard-1-feed")

MOODBOARD_1_FEED_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIERS_MB1_FEED",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_MB1_FEED",
        "default": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS_MB1_FEED",
        "default": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
    },
}

MOODBOARD_1_FEED_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "MB1_FEED_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room",
    },
    "pendant": {
        "env_key": "MB1_FEED_PROMPT_PENDANT",
        "default": "Generate me a modern dining room",
    },
    "floor-lamp": {
        "env_key": "MB1_FEED_PROMPT_FLOOR_LAMP",
        "default": "Generate me a modern living room with empty floor space for a standing floor lamp",
    },
}


def resolve_moodboard_id(fixture_id: str) -> str:
    cfg = MOODBOARD_1_FEED_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def resolve_prompt(fixture_id: str) -> str:
    cfg = MOODBOARD_1_FEED_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def get_fixtures() -> dict[str, dict[str, Any]]:
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "category": "chandeliers",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_MB1_FEED") or "tbl9u5vjgx8kuE44R").strip(),
            "moodboard_id": resolve_moodboard_id("chandelier"),
            "prompt": resolve_prompt("chandelier"),
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Light",
            "category": "pendant_lights",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MB1_FEED") or "tblOvvYdgsNTXh2zK").strip(),
            "moodboard_id": resolve_moodboard_id("pendant"),
            "prompt": resolve_prompt("pendant"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "category": "floor_lamps",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_MB1_FEED") or "tbl6uTmwM23KK9ocO").strip(),
            "moodboard_id": resolve_moodboard_id("floor-lamp"),
            "prompt": resolve_prompt("floor-lamp"),
            "total": 100,
        },
    }


def build_generation_command(
    table_id: str, category: str, max_items: int, moodboard_id: str, interior_prompt: str
) -> list[str]:
    """Pass category and card settings to run_full_moodboard_1_feed.py for end-to-end automation."""
    cmd = [
        sys.executable,
        "-u",
        "run_full_moodboard_1_feed.py",
        "--category", category or "chandeliers",
        "--table-id", table_id,
        "--max-items", str(max_items),
    ]
    if moodboard_id:
        cmd.extend(["--moodboard-id", moodboard_id])
    if interior_prompt:
        cmd.extend(["--prompt", interior_prompt])
    return cmd


_EXEC_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": 6,
    "elapsed_seconds": 0,
    "logs": [],
    "error": None,
    "process": None,
    "start_time": None,
}
_STATE_LOCK = threading.Lock()
_COUNTS_CACHE: dict[str, Any] = {}
_COUNTS_CACHE_TTL = 30.0


@moodboard_1_feed_bp.route("/counts", methods=["GET"])
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
            "moodboard_id": fix_info["moodboard_id"],
            "prompt": fix_info["prompt"],
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


@moodboard_1_feed_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    moodboard_id = data.get("moodboard_id", "").strip()
    if not fixture_id or not moodboard_id:
        return jsonify({"status": "error", "error": "fixture_id and moodboard_id required"}), 400

    cfg = MOODBOARD_1_FEED_MOODBOARD_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "moodboard_id": moodboard_id})


@moodboard_1_feed_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    prompt_text = data.get("prompt", "").strip()
    if not fixture_id or not prompt_text:
        return jsonify({"status": "error", "error": "fixture_id and prompt required"}), 400

    cfg = MOODBOARD_1_FEED_PROMPT_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "prompt": prompt_text})


@moodboard_1_feed_bp.route("/status", methods=["GET"])
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


@moodboard_1_feed_bp.route("/run", methods=["POST"])
def run_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id", "chandelier")
    max_items = min(max(int(data.get("max_items", 1)), 1), 10)
    fixtures = get_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Invalid fixture_id: {fixture_id}"}), 400

    fix_info = fixtures[fixture_id]
    active_moodboard_id = str(data.get("moodboard_id") or fix_info["moodboard_id"]).strip()
    active_prompt = str(data.get("prompt") or fix_info["prompt"]).strip()
    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Moodboard #1 Feed pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": fixture_id,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": 6,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Moodboard #1 Feed for {fix_info['name']} ({max_items} item(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("moodboard-1-feed", _EXEC_STATE)
        cmd = build_generation_command(
            fix_info["table_id"],
            fix_info.get("category", "chandeliers"),
            max_items,
            active_moodboard_id,
            active_prompt,
        )
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
                    if "step 1/2" in txt.lower() or "ingesting" in txt.lower() or "akeneo" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 0: Scraping Active Product from Akeneo"
                        _EXEC_STATE["current_phase_index"] = 0
                    elif "phase 1" in txt.lower() or "krea" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 1: Krea AI Interior Generation"
                        _EXEC_STATE["current_phase_index"] = 1
                    elif "phase 2" in txt.lower() or "prompt" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 2: Claude Sonnet 5 Prompting"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "phase 3" in txt.lower() or "blending" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 3: Nano Banana Pro Blending + YOLO Item Tagging"
                        _EXEC_STATE["current_phase_index"] = 3
                    elif "phase 4" in txt.lower() or "watermark" in txt.lower() or "logo" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 4: Python PIL Brand Logo Stamping"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "phase 5" in txt.lower() or "moodboard converted" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 5: Material Moodboard Conversion"
                        _EXEC_STATE["current_phase_index"] = 5
                    elif "phase 6" in txt.lower() or "closeup" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 6: Macro Product Close-up Shot"
                        _EXEC_STATE["current_phase_index"] = 6

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
            unregister_pipeline("moodboard-1-feed")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fix_info["name"]})


@moodboard_1_feed_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("moodboard-1-feed")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
