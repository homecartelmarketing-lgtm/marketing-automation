"""Sketch to Real Reel Pipeline API Blueprint (/api/sketch-to-draw-reel/*)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
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

sketch_to_draw_reel_bp = Blueprint(
    "sketch_to_draw_reel", __name__, url_prefix="/api/sketch-to-draw-reel"
)

SKETCH_TO_DRAW_TABLE_CONFIG: dict[str, dict[str, str]] = {
    "chandeliers": {
        "env_key": "AIRTABLE_TABLE_ID_CHANDELIERS_SKETCH_TO_REAL_REEL",
        "fallback_env": "AIRTABLE_TABLE_ID_CHANDELIERS_SKETCH_TO_DRAW_REEL",
        "default": "tblUFR6OvFQaHnG1V",
        "name": "Chandeliers",
        "target": "chandeliers",
    },
    "pendant": {
        "env_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_SKETCH_TO_REAL_REEL",
        "fallback_env": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_SKETCH_TO_DRAW_REEL",
        "default": "tblSketchToRealPendants",
        "name": "Pendant Lights",
        "target": "pendant_lights",
    },
    "floor_lamp": {
        "env_key": "AIRTABLE_TABLE_ID_FLOOR_LAMPS_SKETCH_TO_REAL_REEL",
        "fallback_env": "AIRTABLE_TABLE_ID_FLOOR_LAMPS_SKETCH_TO_DRAW_REEL",
        "default": "tblSketchToRealFloorLamps",
        "name": "Floor Lamps",
        "target": "floor_lamps",
    },
    "table_lamp": {
        "env_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_SKETCH_TO_REAL_REEL",
        "fallback_env": "AIRTABLE_TABLE_ID_TABLE_LAMPS_SKETCH_TO_DRAW_REEL",
        "default": "tblSketchToRealTableLamps",
        "name": "Table Lamps",
        "target": "table_lamps",
    },
    "ceiling_mounted": {
        "env_key": "AIRTABLE_TABLE_ID_CEILING_MOUNTED_SKETCH_TO_REAL_REEL",
        "fallback_env": "AIRTABLE_TABLE_ID_CEILING_MOUNTED_SKETCH_TO_DRAW_REEL",
        "default": "tblSketchToRealCeilingMounted",
        "name": "Ceiling Mounted",
        "target": "ceiling_mounted",
    },
}

SKETCH_TO_DRAW_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandeliers": {
        "env_key": "KREA_MOODBOARD_ID_SKETCH_TO_REAL_CHANDELIERS",
        "fallback_env": "KREA_MOODBOARD_ID_SKETCH_TO_DRAW_CHANDELIERS",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_SKETCH_TO_REAL_PENDANTS",
        "fallback_env": "KREA_MOODBOARD_ID_SKETCH_TO_DRAW_PENDANTS",
        "default": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    },
    "floor_lamp": {
        "env_key": "KREA_MOODBOARD_ID_SKETCH_TO_REAL_FLOOR_LAMPS",
        "fallback_env": "KREA_MOODBOARD_ID_SKETCH_TO_DRAW_FLOOR_LAMPS",
        "default": "b1641228-beec-4823-8d01-1de3eec8410d",
    },
    "table_lamp": {
        "env_key": "KREA_MOODBOARD_ID_SKETCH_TO_REAL_TABLE_LAMPS",
        "fallback_env": "KREA_MOODBOARD_ID_SKETCH_TO_DRAW_TABLE_LAMPS",
        "default": "fb2487fb-2895-4d2c-9758-805aaf1bac69",
    },
    "ceiling_mounted": {
        "env_key": "KREA_MOODBOARD_ID_SKETCH_TO_REAL_CHANDELIERS",
        "fallback_env": "KREA_MOODBOARD_ID_SKETCH_TO_DRAW_CHANDELIERS",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
}

SKETCH_TO_DRAW_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandeliers": {
        "env_key": "PROMPT_SKETCH_TO_REAL_REEL_CHANDELIER",
        "fallback_env": "PROMPT_SKETCH_TO_DRAW_REEL_CHANDELIER",
        "default": "Generate me a photo a modern luxury living room with high ceilings, clean architecture, warm natural daylight",
    },
    "pendant": {
        "env_key": "PROMPT_SKETCH_TO_REAL_REEL_PENDANT",
        "fallback_env": "PROMPT_SKETCH_TO_DRAW_REEL_PENDANT",
        "default": "Generate me a photo a modern dining room with dining table, elegant aesthetic, soft ambient lighting",
    },
    "floor_lamp": {
        "env_key": "PROMPT_SKETCH_TO_REAL_REEL_FLOOR_LAMP",
        "fallback_env": "PROMPT_SKETCH_TO_DRAW_REEL_FLOOR_LAMP",
        "default": "Generate me a modern living room with lounge seating area, empty corner for standing floor lamp",
    },
    "table_lamp": {
        "env_key": "PROMPT_SKETCH_TO_REAL_REEL_TABLE_LAMP",
        "fallback_env": "PROMPT_SKETCH_TO_DRAW_REEL_TABLE_LAMP",
        "default": "Generate me a modern bedroom with nightstand bedside table, warm contemporary interior",
    },
    "ceiling_mounted": {
        "env_key": "PROMPT_SKETCH_TO_REAL_REEL_CEILING_MOUNTED",
        "fallback_env": "PROMPT_SKETCH_TO_DRAW_REEL_CEILING_MOUNTED",
        "default": "Generate me a modern hallway or contemporary bedroom ceiling, minimalist architectural space",
    },
}


def get_fixtures() -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for fix_id, tbl_cfg in SKETCH_TO_DRAW_TABLE_CONFIG.items():
        mb_cfg = SKETCH_TO_DRAW_MOODBOARD_CONFIG.get(fix_id, {})
        pr_cfg = SKETCH_TO_DRAW_PROMPT_CONFIG.get(fix_id, {})

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
            or os.getenv("PROMPT_SKETCH_TO_DRAW_REEL", "")
            or pr_cfg.get("default", "")
        ).strip()

        fixtures[fix_id] = {
            "id": fix_id,
            "name": tbl_cfg["name"],
            "target": tbl_cfg["target"],
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
    "total_phases": 7,
    "elapsed_seconds": 0,
    "logs": [],
    "error": None,
    "process": None,
    "start_time": None,
}
_STATE_LOCK = threading.Lock()
_COUNTS_CACHE: dict[str, Any] = {}
_COUNTS_CACHE_TTL = 30.0


@sketch_to_draw_reel_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({
        "status": "success",
        "fixtures": list(get_fixtures().values()),
    })


@sketch_to_draw_reel_bp.route("/counts", methods=["GET"])
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
        try:
            from content_automation.airtable_client import fetch_status_breakdown
            sc = fetch_status_breakdown(table_id)
        except Exception:
            sc = {"P": 0, "S": 0, "C": 0, "D": 0, "FM": 0, "total": 0}
        return fix_key, {
            "id": fix_info["id"],
            "name": fix_info["name"],
            "table_id": table_id,
            "completed": sc.get("C", 0),
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


@sketch_to_draw_reel_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    moodboard_id = (data.get("moodboard_id") or "").strip()
    if not fixture_id or not moodboard_id:
        return jsonify({"status": "error", "error": "fixture_id and moodboard_id required"}), 400

    cfg = SKETCH_TO_DRAW_MOODBOARD_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "moodboard_id": moodboard_id})


@sketch_to_draw_reel_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    prompt_text = (data.get("prompt") or "").strip()
    if not fixture_id or not prompt_text:
        return jsonify({"status": "error", "error": "fixture_id and prompt required"}), 400

    cfg = SKETCH_TO_DRAW_PROMPT_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "prompt": prompt_text})


@sketch_to_draw_reel_bp.route("/status", methods=["GET"])
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


@sketch_to_draw_reel_bp.route("/run", methods=["POST"])
def run_pipeline_route():
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
            return jsonify({"status": "error", "error": "Sketch to Real Reel pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": fixture_id,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": 7,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Sketch to Real Reel for {fix_info['name']} ({max_items} row(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("sketch-to-draw-reel", f"Sketch to Real Reel ({fix_info['name']})")

        # Resolve script location (prefers Sketch to Real, falls back to Sketch to Draw)
        script_candidates = [
            MARKETING_DIR / "python-content-script" / "generate_sketch_to_real_reel_pipeline.py",
            MARKETING_DIR / "generate_sketch_to_real_reel_pipeline.py",
            MARKETING_DIR / "python-content-script" / "generate_sketch_to_draw_reel_pipeline.py",
            MARKETING_DIR / "generate_sketch_to_draw_reel_pipeline.py",
        ]
        script_path = None
        for cand in script_candidates:
            if cand.exists():
                script_path = str(cand)
                break
        if not script_path:
            script_path = str(MARKETING_DIR / "python-content-script" / "generate_sketch_to_real_reel_pipeline.py")

        cmd = [
            sys.executable,
            "-u",
            script_path,
            "--target", fix_info["target"],
            "--table-id", fix_info["table_id"],
            "--max-items", str(max_items),
        ]
        if custom_moodboard:
            cmd.extend(["--moodboard-id", custom_moodboard])
        if custom_prompt:
            cmd.extend(["--interior-prompt", custom_prompt])

        env_copy = os.environ.copy()
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
                    if "phase 1" in low or "scrap" in low:
                        _EXEC_STATE["current_phase"] = "Phase 1: Akeneo Scrape & Catalog Verification"
                        _EXEC_STATE["current_phase_index"] = 1
                    elif "phase 2" in low or "interior" in low:
                        _EXEC_STATE["current_phase"] = "Phase 2: Krea Room Interior Generation"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "phase 3" in low or "claude" in low:
                        _EXEC_STATE["current_phase"] = "Phase 3: Claude Vision Analysis & Headline"
                        _EXEC_STATE["current_phase_index"] = 3
                    elif "phase 4" in low or "blend" in low:
                        _EXEC_STATE["current_phase"] = "Phase 4: Fal Nano Banana Pro Room Blend & YOLO Tagging"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "phase 5" in low or "sketch" in low or "outline" in low:
                        _EXEC_STATE["current_phase"] = "Phase 5: Auto Draw Outline & Cover Generation"
                        _EXEC_STATE["current_phase_index"] = 5
                    elif "phase 6" in low or "video" in low or "draw" in low:
                        _EXEC_STATE["current_phase"] = "Phase 6: Auto Draw Reveal Video Rendering"
                        _EXEC_STATE["current_phase_index"] = 6
                    elif "phase 7" in low or "outro" in low or "mux" in low:
                        _EXEC_STATE["current_phase"] = "Phase 7: FFmpeg Outro Concatenation"
                        _EXEC_STATE["current_phase_index"] = 7

            p.wait()
            rc = p.returncode

            with _STATE_LOCK:
                _EXEC_STATE["process"] = None
                if rc == 0:
                    _EXEC_STATE["status"] = "completed"
                    _EXEC_STATE["current_phase"] = "Completed"
                    _EXEC_STATE["current_phase_index"] = 7
                    _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Sketch to Real Reel completed successfully.")
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
            unregister_pipeline("sketch-to-draw-reel")
            _COUNTS_CACHE.clear()

    t = threading.Thread(target=run_worker, daemon=True)
    t.start()

    return jsonify({
        "status": "success",
        "message": f"Started Sketch to Real Reel for {fix_info['name']}",
        "fixture_id": fixture_id,
        "max_items": max_items,
    })


@sketch_to_draw_reel_bp.route("/stop", methods=["POST"])
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
            unregister_pipeline("sketch-to-draw-reel")
            return jsonify({"status": "success", "message": "Pipeline stopped"})
        return jsonify({"status": "error", "error": "No active pipeline to stop"}), 400
