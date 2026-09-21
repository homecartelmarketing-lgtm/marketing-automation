"""Tips & Educational Feed Pipeline API Blueprint (/api/tips-edu-feed/*)."""

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

tips_edu_feed_bp = Blueprint("tips_edu_feed", __name__, url_prefix="/api/tips-edu-feed")

TIPS_EDU_FEED_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIERS_TIPS_EDU_FEED",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_TIPS_EDU_FEED",
        "default": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS_TIPS_EDU_FEED",
        "default": "b1641228-beec-4823-8d01-1de3eec8410d",
    },
    "cluster-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIERS_TIPS_EDU_FEED",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
}

TIPS_EDU_FEED_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "TIPS_EDU_FEED_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room hanging chandelier from the ceiling",
    },
    "pendant": {
        "env_key": "TIPS_EDU_FEED_PROMPT_PENDANT",
        "default": "Generate me a modern dining room",
    },
    "floor-lamp": {
        "env_key": "TIPS_EDU_FEED_PROMPT_FLOOR_LAMP",
        "default": "Generate me a modern living room with empty floor space for a standing floor lamp",
    },
    "cluster-chandelier": {
        "env_key": "TIPS_EDU_FEED_PROMPT_CLUSTER_CHANDELIER",
        "default": "Generate me a luxury modern room with high ceiling for a cluster chandelier",
    },
}


def resolve_moodboard_id(fixture_id: str) -> str:
    cfg = TIPS_EDU_FEED_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def resolve_prompt(fixture_id: str) -> str:
    cfg = TIPS_EDU_FEED_PROMPT_CONFIG.get(fixture_id, {})
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
            "cli_target": "chandeliers",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_TIPS_EDU_FEED") or "tblQ65S51Dmauwx4c").strip(),
            "moodboard_id": resolve_moodboard_id("chandelier"),
            "prompt": resolve_prompt("chandelier"),
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Lights",
            "cli_target": "pendant_lights",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDU_FEED") or "tblIhCP3Gjg09QFCK").strip(),
            "moodboard_id": resolve_moodboard_id("pendant"),
            "prompt": resolve_prompt("pendant"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "cli_target": "floor_lamps",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_TIPS_EDU_FEED") or "tblQuhvktqYB59Ofw").strip(),
            "moodboard_id": resolve_moodboard_id("floor-lamp"),
            "prompt": resolve_prompt("floor-lamp"),
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "cli_target": "cluster_chandeliers",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIERS_TIPS_EDU_FEED") or "tblwY6eGQCD5bJeF1").strip(),
            "moodboard_id": resolve_moodboard_id("cluster-chandelier"),
            "prompt": resolve_prompt("cluster-chandelier"),
            "total": 100,
        },
    }


def build_generation_command(
    cli_target: str, max_items: int, moodboard_id: str, interior_prompt: str
) -> list[str]:
    """Launch the feed runner with the edited Krea interior settings."""
    return [
        sys.executable,
        "run_tips_and_edu_feed.py",
        "--target", cli_target,
        "--phase", "all",
        "--max-rows", str(max_items),
        "--moodboard-id", moodboard_id,
        "--prompt", interior_prompt,
        "--execute",
    ]


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


@tips_edu_feed_bp.route("/counts", methods=["GET"])
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


@tips_edu_feed_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    moodboard_id = data.get("moodboard_id", "").strip()
    if not fixture_id or not moodboard_id:
        return jsonify({"status": "error", "error": "fixture_id and moodboard_id required"}), 400

    cfg = TIPS_EDU_FEED_MOODBOARD_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "moodboard_id": moodboard_id})


@tips_edu_feed_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    prompt_text = data.get("prompt", "").strip()
    if not fixture_id or not prompt_text:
        return jsonify({"status": "error", "error": "fixture_id and prompt required"}), 400

    cfg = TIPS_EDU_FEED_PROMPT_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "prompt": prompt_text})


@tips_edu_feed_bp.route("/status", methods=["GET"])
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


@tips_edu_feed_bp.route("/run", methods=["POST"])
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
            return jsonify({"status": "error", "error": "Tips & Edu Feed pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": fixture_id,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": 6,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Tips & Educational Feed for {fix_info['name']} ({max_items} item(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("tips-edu-feed", _EXEC_STATE)
        cmd = build_generation_command(
            fix_info["cli_target"], max_items, active_moodboard_id, active_prompt
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
                    if "phase 1" in txt.lower() or "akeneo scrape" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 1: Akeneo Product Scraper"
                        _EXEC_STATE["current_phase_index"] = 1
                    elif "phase 2" in txt.lower() or "krea" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 2: Krea AI Interior Generation"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "phase 3" in txt.lower() or "prompt analysis" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 3: Claude Vision Prompting"
                        _EXEC_STATE["current_phase_index"] = 3
                    elif "phase 4" in txt.lower() or "banana pro blending" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 4: Banana Pro Room Blending"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "phase 5" in txt.lower() or "attaching item name" in txt.lower() or "tagging" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 5: YOLO Item Name Tagging"
                        _EXEC_STATE["current_phase_index"] = 5
                    elif "phase 6" in txt.lower() or "layout" in txt.lower():
                        _EXEC_STATE["current_phase"] = "Phase 6: Layout Assembly & Stamping"
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
            unregister_pipeline("tips-edu-feed")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fix_info["name"]})


@tips_edu_feed_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("tips-edu-feed")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
