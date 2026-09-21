"""1 Product, 3 Styles Reel Pipeline API Blueprint (/api/one-product-3-styles-reel/*)."""

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

one_product_three_styles_reel_bp = Blueprint(
    "one_product_three_styles_reel",
    __name__,
    url_prefix="/api/one-product-3-styles-reel",
)

ONE_PRODUCT_THREE_STYLES_REEL_TABLE_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "AIRTABLE_TABLE_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL",
        "default": "tbl6ls4AWcEcynBpZ",
        "name": "Chandelier",
        "category": "chandeliers_one_product_three_styles_reel",
    },
}

ONE_PRODUCT_THREE_STYLES_REEL_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
}

ONE_PRODUCT_THREE_STYLES_REEL_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "PROMPT_ONE_PRODUCT_THREE_STYLES_REEL_CHANDELIER",
        "default": "Generate me a modern luxury living room with high ceiling for chandelier",
    },
}


def get_fixtures() -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for fix_id, tbl_cfg in ONE_PRODUCT_THREE_STYLES_REEL_TABLE_CONFIG.items():
        mb_cfg = ONE_PRODUCT_THREE_STYLES_REEL_MOODBOARD_CONFIG.get(fix_id, {})
        pr_cfg = ONE_PRODUCT_THREE_STYLES_REEL_PROMPT_CONFIG.get(fix_id, {})

        table_id = (
            os.getenv(tbl_cfg.get("env_key", ""))
            or tbl_cfg.get("default", "")
        ).strip()

        moodboard_id = (
            os.getenv(mb_cfg.get("env_key", ""))
            or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS")
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


@one_product_three_styles_reel_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({
        "status": "success",
        "fixtures": list(get_fixtures().values()),
    })


@one_product_three_styles_reel_bp.route("/counts", methods=["GET"])
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
            "total": sum(sc.values()),
            "completed": sc["C"],
            "status_counts": sc,
            "moodboard_id": fix_info.get("moodboard_id", ""),
            "prompt": fix_info.get("prompt", ""),
        }

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(fetch_fixture_data, k, v) for k, v in fixtures.items()]
        for f in futures:
            key, data = f.result()
            results[key] = data

    _COUNTS_CACHE["time"] = now
    _COUNTS_CACHE["data"] = results

    return jsonify({"status": "success", "counts": results, "cached": False})


@one_product_three_styles_reel_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    moodboard_id = data.get("moodboard_id", "").strip()
    if not fixture_id or not moodboard_id:
        return jsonify({"status": "error", "error": "fixture_id and moodboard_id required"}), 400

    cfg = ONE_PRODUCT_THREE_STYLES_REEL_MOODBOARD_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "moodboard_id": moodboard_id})


@one_product_three_styles_reel_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    fixture_id = data.get("fixture_id")
    prompt_text = data.get("prompt", "").strip()
    if not fixture_id or not prompt_text:
        return jsonify({"status": "error", "error": "fixture_id and prompt required"}), 400

    cfg = ONE_PRODUCT_THREE_STYLES_REEL_PROMPT_CONFIG.get(fixture_id)
    if not cfg:
        return jsonify({"status": "error", "error": f"Unknown fixture: {fixture_id}"}), 404

    env_key = cfg.get("env_key")
    if env_key:
        save_config_override(env_key, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": fixture_id, "prompt": prompt_text})


@one_product_three_styles_reel_bp.route("/status", methods=["GET"])
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


@one_product_three_styles_reel_bp.route("/run", methods=["POST"])
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
            return jsonify({"status": "error", "error": "1 Product, 3 Styles Reel pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": fixture_id,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": 5,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering 1 Product, 3 Styles Reel for {fix_info['name']} ({max_items} item(s))..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("one-product-3-styles-reel", f"1 Product, 3 Styles Reel ({fix_info['name']})")
        cmd = [
            sys.executable,
            "-u",
            "run_one_product_three_styles_reel.py",
            "--phase", "all",
            "--max-rows", str(max_items),
        ]
        if custom_moodboard:
            cmd.extend(["--moodboard-id", custom_moodboard])
        if custom_prompt:
            cmd.extend(["--prompt", custom_prompt])

        env_copy = os.environ.copy()
        cfg_mb = ONE_PRODUCT_THREE_STYLES_REEL_MOODBOARD_CONFIG.get(fixture_id, {})
        if custom_moodboard and cfg_mb.get("env_key"):
            env_copy[cfg_mb["env_key"]] = custom_moodboard
        cfg_pr = ONE_PRODUCT_THREE_STYLES_REEL_PROMPT_CONFIG.get(fixture_id, {})
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
                    if "akeneo" in low or "phase 1" in low or "ingestion" in low:
                        _EXEC_STATE["current_phase"] = "Phase 1: Akeneo Product Ingestion"
                        _EXEC_STATE["current_phase_index"] = 1
                    elif "interior" in low or "phase 2" in low or "krea" in low:
                        _EXEC_STATE["current_phase"] = "Phase 2: Krea Room Interiors (9:16)"
                        _EXEC_STATE["current_phase_index"] = 2
                    elif "claude" in low or "phase 3" in low or "prompt" in low:
                        _EXEC_STATE["current_phase"] = "Phase 3: Claude Vision Prompting"
                        _EXEC_STATE["current_phase_index"] = 3
                    elif "banana" in low or "phase 4:" in low or "blending" in low:
                        _EXEC_STATE["current_phase"] = "Phase 4: Nano Banana Pro Multi-Blending"
                        _EXEC_STATE["current_phase_index"] = 4
                    elif "phase 5.1" in low or "yolo" in low:
                        _EXEC_STATE["current_phase"] = "Phase 5.1: YOLO Item Name Tagging"
                        _EXEC_STATE["current_phase_index"] = 5
                    elif "phase 5.2" in low or "headline" in low:
                        _EXEC_STATE["current_phase"] = "Phase 5.2: Overlaying Centered Headline"
                        _EXEC_STATE["current_phase_index"] = 5
                    elif "phase 5.3" in low or "phase 5.4" in low or "video" in low or "reel" in low or "outro" in low or "phase 5" in low or "mp4" in low or "compil" in low:
                        _EXEC_STATE["current_phase"] = "Phase 5: Silent 9:16 Reel Video Compilation"
                        _EXEC_STATE["current_phase_index"] = 5

            p.wait()
            with _STATE_LOCK:
                if p.returncode == 0:
                    _EXEC_STATE["status"] = "completed"
                    _EXEC_STATE["current_phase"] = "Completed successfully"
                    _EXEC_STATE["current_phase_index"] = 5
                else:
                    _EXEC_STATE["status"] = "error"
                    _EXEC_STATE["error"] = extract_clean_error(_EXEC_STATE["logs"], p.returncode)
        except Exception as e:
            with _STATE_LOCK:
                _EXEC_STATE["status"] = "error"
                _EXEC_STATE["error"] = str(e)
        finally:
            unregister_pipeline("one-product-3-styles-reel")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fix_info["name"]})


@one_product_three_styles_reel_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("one-product-3-styles-reel")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
