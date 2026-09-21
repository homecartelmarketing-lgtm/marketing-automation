"""Moodboard Reel Pipeline API Blueprint (/api/moodboard-reel/*)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
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
    is_any_pipeline_running,
    register_pipeline,
    save_config_override,
    unregister_pipeline,
)

moodboard_reel_bp = Blueprint("moodboard_reel", __name__, url_prefix="/api/moodboard-reel")

MOODBOARD_REEL_TABLE_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "AIRTABLE_TABLE_ID_CHANDELIER_MODERN_MOODBOARDREEL",
        "fallback_env": "AIRTABLE_TABLE_ID_MB_REEL_CHANDELIER",
        "default": "tbl026zbECJJ9FRfj",
        "name": "Chandelier Modern",
        "category": "chandelier_modern",
    },
    "pendant": {
        "env_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARDREEL",
        "fallback_env": "AIRTABLE_TABLE_ID_MB_REEL_PENDANT",
        "default": "tblpjRudEy6fobIrP",
        "name": "Pendant Lights",
        "category": "pendant_lights_reel",
    },
    "cluster-chandelier": {
        "env_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_MOODBOARDREEL",
        "fallback_env": "AIRTABLE_TABLE_ID_MB_REEL_CLUSTER",
        "default": "tblJX6rd5nhhEuWbL",
        "name": "Cluster Chandeliers",
        "category": "cluster_chandeliers_reel",
    },
    "linear-chandelier": {
        "env_key": "AIRTABLE_TABLE_ID_LINEAR_CHANDELIER_MOODBOARDREEL",
        "fallback_env": "AIRTABLE_TABLE_ID_MB_REEL_LINEAR",
        "default": "tblj4DVzllYa8pliK",
        "name": "Linear Chandeliers",
        "category": "linear_chandeliers_reel",
    },
    "floor-lamp": {
        "env_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_MOODBOARDREEL",
        "fallback_env": "AIRTABLE_TABLE_ID_MB_REEL_FLOOR_LAMP",
        "default": "tblF3ot4fdHN2VCQn",
        "name": "Floor Lamps",
        "category": "floor_lamps_reel",
    },
    "wall-sconce": {
        "env_key": "AIRTABLE_TABLE_ID_WALL_SCONCE_MOODBOARDREEL",
        "fallback_env": "AIRTABLE_TABLE_ID_MB_REEL_WALL_SCONCE",
        "default": "tbli7nuOEhR8inzva",
        "name": "Wall Sconces",
        "category": "wall_sconces_reel",
    },
    "table-lamp": {
        "env_key": "AIRTABLE_TABLE_ID_TABLE_LAMP_MOODBOARDREEL",
        "fallback_env": "AIRTABLE_TABLE_ID_MB_REEL_TABLE_LAMP",
        "default": "tblr0uAYkDWDQZinl",
        "name": "Table Lamps",
        "category": "table_lamps_reel",
    },
}

MOODBOARD_REEL_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIER_MODERN",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        "default": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
    },
    "cluster-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
    "linear-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_LINEAR_CHANDELIER",
        "default": "994a703c-4c6b-498a-bb27-7609615a74bd",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        "default": "b1641228-beec-4823-8d01-1de3eec8410d",
    },
    "wall-sconce": {
        "env_key": "KREA_MOODBOARD_ID_WALL_SCONCE",
        "default": "afa1317e-7be1-47f5-9d6f-91c7769a767d",
    },
    "table-lamp": {
        "env_key": "KREA_MOODBOARD_ID_TABLE_LAMPS",
        "default": "257569e1-7be8-4412-a90f-acbc347e4646",
    },
}

MOODBOARD_REEL_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "PROMPT_MOODBOARD_REEL_CHANDELIER",
        "default": "Generate me a modern living room",
    },
    "pendant": {
        "env_key": "PROMPT_MOODBOARD_REEL_PENDANT",
        "default": "Generate me a modern dining room",
    },
    "cluster-chandelier": {
        "env_key": "PROMPT_MOODBOARD_REEL_CLUSTER",
        "default": "Generate me a luxury modern room with high ceiling for cluster chandelier",
    },
    "linear-chandelier": {
        "env_key": "PROMPT_MOODBOARD_REEL_LINEAR",
        "default": "Generate me a modern luxury kitchen island dining space",
    },
    "floor-lamp": {
        "env_key": "PROMPT_MOODBOARD_REEL_FLOOR_LAMP",
        "default": "Generate me a modern living room with empty floor space for a standing floor lamp",
    },
    "wall-sconce": {
        "env_key": "PROMPT_MOODBOARD_REEL_WALL_SCONCE",
        "default": "Generate me a modern hallway or living room with wall sconce",
    },
    "table-lamp": {
        "env_key": "PROMPT_MOODBOARD_REEL_TABLE_LAMP",
        "default": "Generate me a modern bedroom with bedside table for a table lamp",
    },
}


def get_fixtures() -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for fix_id, tbl_cfg in MOODBOARD_REEL_TABLE_CONFIG.items():
        mb_cfg = MOODBOARD_REEL_MOODBOARD_CONFIG.get(fix_id, {})
        pr_cfg = MOODBOARD_REEL_PROMPT_CONFIG.get(fix_id, {})

        table_id = (
            os.getenv(tbl_cfg.get("env_key", ""))
            or (os.getenv(tbl_cfg.get("fallback_env", "")) if tbl_cfg.get("fallback_env") else "")
            or tbl_cfg.get("default", "")
        ).strip()

        moodboard_id = (
            os.getenv(mb_cfg.get("env_key", ""))
            or mb_cfg.get("default", "")
        ).strip()

        prompt = (
            os.getenv(pr_cfg.get("env_key", ""))
            or pr_cfg.get("default", "")
        ).strip()

        fixtures[fix_id] = {
            "id": fix_id,
            "name": tbl_cfg["name"],
            "category": tbl_cfg["category"],
            "table_id": table_id,
            "total": 100,
            "moodboard_id": moodboard_id,
            "prompt": prompt,
        }
    return fixtures


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


@moodboard_reel_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({
        "status": "success",
        "fixtures": list(get_fixtures().values()),
    })


@moodboard_reel_bp.route("/counts", methods=["GET"])
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

    with ThreadPoolExecutor(max_workers=max(1, len(fixtures))) as executor:
        futures = [executor.submit(fetch_fixture_data, k, v) for k, v in fixtures.items()]
        for fut in futures:
            try:
                key, val = fut.result()
                results[key] = val
            except Exception:
                pass

    _COUNTS_CACHE["data"] = results
    _COUNTS_CACHE["time"] = now
    return jsonify({"status": "success", "counts": results, "cached": False})


@moodboard_reel_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    moodboard_id = data.get("moodboard_id", "").strip()
    if not fixture_id or not moodboard_id:
        return jsonify({"status": "error", "error": "fixture_id and moodboard_id required"}), 400

    cfg = MOODBOARD_REEL_MOODBOARD_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "moodboard_id": moodboard_id})


@moodboard_reel_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    prompt_text = data.get("prompt", "").strip()
    if not fixture_id or not prompt_text:
        return jsonify({"status": "error", "error": "fixture_id and prompt required"}), 400

    cfg = MOODBOARD_REEL_PROMPT_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "prompt": prompt_text})


@moodboard_reel_bp.route("/status", methods=["GET"])
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


@moodboard_reel_bp.route("/run", methods=["POST"])
def run_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    custom_moodboard = (data.get("moodboard_id") or "").strip()
    custom_prompt = (data.get("prompt") or "").strip()
    max_items = min(max(int(data.get("max_items", 1)), 1), 10)

    fixtures = get_fixtures()
    if not fixture_id or fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Invalid fixture: {fixture_id}"}), 400

    fix_info = fixtures[fixture_id]

    running, desc = is_any_pipeline_running()
    if running:
        return jsonify({"status": "error", "error": f"Another pipeline is currently active: {desc}"}), 409

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Moodboard Reel pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": fixture_id,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": 5,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Moodboard Reel for {fix_info['name']} ({max_items} item(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("moodboard-reel", f"Moodboard Reel ({fix_info['name']})")
        cmd = [
            sys.executable,
            "-u",
            "run_moodboard_reel.py",
            "--category", fix_info["category"],
            "--phase", "all",
            "--limit", str(max_items),
            "--moodboard-id", custom_moodboard or fix_info["moodboard_id"],
            "--interior-prompt", custom_prompt or fix_info["prompt"],
        ]
        env_copy = os.environ.copy()
        cfg_mb = MOODBOARD_REEL_MOODBOARD_CONFIG.get(fixture_id, {})
        if custom_moodboard and cfg_mb.get("env_key"):
            env_copy[cfg_mb["env_key"]] = custom_moodboard
        cfg_pr = MOODBOARD_REEL_PROMPT_CONFIG.get(fixture_id, {})
        if custom_prompt and cfg_pr.get("env_key"):
            env_copy[cfg_pr["env_key"]] = custom_prompt

        try:
            p = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env_copy,
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
                    if "scrape" in low or "akeneo" in low:
                        _EXEC_STATE["current_phase"] = "Phase 1: Akeneo 4-Product Scraper"
                        _EXEC_STATE["current_phase_index"] = 1
                    elif "interior" in low or "krea" in low:
                        _EXEC_STATE["current_phase"] = "Phase 2: Krea Room Interiors"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "[phase 2.5]" in low:
                        _EXEC_STATE["current_phase"] = "Phase 2.5: Claude Vision Prompting"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "[phase 3]" in low or "banana" in low or "blending" in low:
                        _EXEC_STATE["current_phase"] = "Phase 3: Nano Banana Pro Blending"
                        _EXEC_STATE["current_phase_index"] = 3
                    elif "[phase 4]" in low or "converting" in low:
                        _EXEC_STATE["current_phase"] = "Phase 4: 3-Panel Moodboard Conversion"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "[phase 4.2]" in low or "texture" in low or "stamping" in low:
                        _EXEC_STATE["current_phase"] = "Phase 4.2: Texture Extraction & Typography Stamping"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "[phase 5]" in low or "video" in low or "music" in low or "reel" in low:
                        _EXEC_STATE["current_phase"] = "Phase 5: Reel Video Assembly"
                        _EXEC_STATE["current_phase_index"] = 5

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
            unregister_pipeline("moodboard-reel")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fix_info["name"]})


@moodboard_reel_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("moodboard-reel")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
