"""Style Reel Slideshow Pipeline API Blueprint (/api/style-reel-slideshow/*)."""

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

style_reel_slideshow_bp = Blueprint("style_reel_slideshow", __name__, url_prefix="/api/style-reel-slideshow")

STYLE_REEL_TABLE_CONFIG: dict[str, dict[str, str]] = {
    "style-tour": {
        "env_key": "AIRTABLE_TABLE_ID_STYLE_REEL_SLIDESHOW",
        "fallback_env": "AIRTABLE_TABLE_ID_STYLE_REEL",
        "default": "tblFFEvkHb3jLKrcv",
        "name": "5-Room Style Tour",
    },
}

STYLE_REEL_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "style-tour": {
        "env_key": "KREA_MOODBOARD_ID_STYLE_REEL_SLIDESHOW",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
}

STYLE_REEL_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "style-tour": {
        "env_key": "PROMPT_STYLE_REEL_SLIDESHOW",
        "default": "Generate 5 coherent modern rooms for a cohesive home tour",
    },
}


def get_fixtures() -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for fix_id, tbl_cfg in STYLE_REEL_TABLE_CONFIG.items():
        mb_cfg = STYLE_REEL_MOODBOARD_CONFIG.get(fix_id, {})
        pr_cfg = STYLE_REEL_PROMPT_CONFIG.get(fix_id, {})

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


@style_reel_slideshow_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({
        "status": "success",
        "fixtures": list(get_fixtures().values()),
    })


@style_reel_slideshow_bp.route("/counts", methods=["GET"])
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


@style_reel_slideshow_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id", "style-tour")
    moodboard_id = data.get("moodboard_id", "").strip()
    if not moodboard_id:
        return jsonify({"status": "error", "error": "moodboard_id required"}), 400

    cfg = STYLE_REEL_MOODBOARD_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "moodboard_id": moodboard_id})


@style_reel_slideshow_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id", "style-tour")
    prompt_text = data.get("prompt", "").strip()
    if not prompt_text:
        return jsonify({"status": "error", "error": "prompt required"}), 400

    cfg = STYLE_REEL_PROMPT_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "prompt": prompt_text})


@style_reel_slideshow_bp.route("/status", methods=["GET"])
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


@style_reel_slideshow_bp.route("/run", methods=["POST"])
def run_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id", "style-tour")
    custom_moodboard = (data.get("moodboard_id") or "").strip()
    custom_prompt = (data.get("prompt") or "").strip()
    max_items = min(max(int(data.get("max_items", 1)), 1), 10)

    fixtures = get_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Invalid fixture: {fixture_id}"}), 400

    fix_info = fixtures[fixture_id]

    running, desc = is_any_pipeline_running()
    if running:
        return jsonify({"status": "error", "error": f"Another pipeline is currently active: {desc}"}), 409

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Style Reel Slideshow pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": fixture_id,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": 5,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Style Reel Slideshow for {fix_info['name']} ({max_items} item(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("style-reel-slideshow", f"Style Reel Slideshow ({fix_info['name']})")
        cmd = [
            sys.executable,
            "-u",
            "run_style_reel_slideshow.py",
            "--phase", "all",
            "--max-rows", str(max_items),
            "--execute",
        ]
        env_copy = os.environ.copy()
        if custom_moodboard:
            env_copy["KREA_MOODBOARD_ID_STYLE_REEL_SLIDESHOW"] = custom_moodboard
        if custom_prompt:
            env_copy["PROMPT_STYLE_REEL_SLIDESHOW"] = custom_prompt

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
                    if "phase 1" in low or "scrape" in low or "akeneo" in low:
                        _EXEC_STATE["current_phase"] = "Phase 1: Multi-Category Akeneo Scrape"
                        _EXEC_STATE["current_phase_index"] = 1
                    elif "phase 2" in low or "interior" in low or "krea" in low:
                        _EXEC_STATE["current_phase"] = "Phase 2: Sequential Krea Interior Generation"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "phase 3" in low or "claude" in low or "prompt" in low:
                        _EXEC_STATE["current_phase"] = "Phase 3: Claude Vision Prompt Analysis"
                        _EXEC_STATE["current_phase_index"] = 3
                    elif "phase 4" in low or "banana" in low or "blend" in low:
                        _EXEC_STATE["current_phase"] = "Phase 4: Fal AI Nano Banana Pro Blending"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "phase 5" in low or "slideshow" in low or "video" in low or "ffmpeg" in low or "done" in low:
                        _EXEC_STATE["current_phase"] = "Phase 5: FFmpeg Slideshow Video Generation"
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
            unregister_pipeline("style-reel-slideshow")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fix_info["name"]})


@style_reel_slideshow_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("style-reel-slideshow")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
