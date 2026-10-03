"""Christmas Banner Pipeline API Blueprint (/api/christmas-banner/*)."""

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
    save_config_override,
    unregister_pipeline,
)

christmas_banner_bp = Blueprint(
    "christmas_banner", __name__, url_prefix="/api/christmas-banner"
)

FIXTURE_ID = "christmas_banner"
CATEGORY_LABEL = "Christmas Banner"  # Banner Set rows (Christmas + Sale banner on one row) use this Category
PIPELINE_KEY = "christmas-banner"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_CHRISTMAS_BANNER"
DEFAULT_TABLE_ID = "tblgNk1Tp6qKUcduw"
MOODBOARD_ENV_KEY = "KREA_MOODBOARD_ID_CHRISTMAS_BANNER"
PROMPT_ENV_KEY = "CHRISTMAS_BANNER_PROMPT"
DEFAULT_MOODBOARD_ID = "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
DEFAULT_PROMPT = (
    "Generate me a photo of a modern luxury living room with a Christmas vibe: a decorated Christmas tree, "
    "warm festive styling with garlands and soft fairy lights, a sofa and armchair seating area, a side table "
    "and console, high ceilings, clean architecture, warm cozy evening light, wide cinematic panoramic composition, "
    "with empty ceiling, wall and floor spaces for lighting fixtures"
)
SCRIPT_NAME = "generate_banner_set_pipeline.py"  # one run = Christmas + Sale + third banner on ONE Airtable row
TOTAL_PHASES = 15
PHASE_LABELS = {
    1: "Phase 1: Akeneo Scrape (10 products) & Catalog Verification",
    2: "Phase 2: Krea Christmas Living Room (2.35:1)",
    3: "Phase 3: Claude Vision Blending Prompt",
    4: "Phase 4: Nano Banana Pro 21:9 Banner Blend",
    5: "Phase 5: Claude Title + Subtitle",
    6: "Phase 6: Poppins Title/Subtitle Overlay (Shadow)",
    7: "Phase 7: Sale Banner - Krea Dining Room + Kitchen (4:5)",
    8: "Phase 8: Sale Banner - Claude Blending Prompts",
    9: "Phase 9: Sale Banner - Nano Banana Pro Room Blends",
    10: "Phase 10: Sale Banner - Calendar Captions + Claude Panel Colour",
    11: "Phase 11: Sale Banner - 1800x600 Composite",
    12: "Phase 12: Third Banner - Krea Modern Christmas Bedroom (3:2)",
    13: "Phase 13: Third Banner - Claude Blending Prompt",
    14: "Phase 14: Third Banner - Nano Banana Pro Bedroom Blend",
    15: "Phase 15: Third Banner - Composite (Sale Colour Panel + Text)",
}
# The banners print their own "[PHASE n]" lines one after the other: Christmas 2-6, then the Sale banner's 2-6 again
# (our 7-11), then the third banner's 2-5 (our 12-15). Each banner's "[PHASE 6]" ends its stage.
SALE_PHASE_OFFSET = 5
PHASE_STAGE_OFFSET = 5


def phase_index(n: int, stage: int) -> int:
    """Studio phase number for a printed "[PHASE n]" while in ``stage`` (0 Christmas, 1 Sale, 2 third)."""
    return n if stage == 0 or n < 2 else n + PHASE_STAGE_OFFSET * stage


def get_fixture() -> dict[str, Any]:
    return {
        "id": FIXTURE_ID,
        "name": "Banner Set",
        "table_id": (os.getenv(TABLE_ENV_KEY) or DEFAULT_TABLE_ID).strip(),
        "total": 100,
        "moodboard_id": (os.getenv(MOODBOARD_ENV_KEY) or DEFAULT_MOODBOARD_ID).strip(),
        "prompt": (os.getenv(PROMPT_ENV_KEY) or DEFAULT_PROMPT).strip(),
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


@christmas_banner_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({"status": "success", "fixtures": [get_fixture()]})


@christmas_banner_bp.route("/counts", methods=["GET"])
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
            "moodboard_id": fix["moodboard_id"],
            "prompt": fix["prompt"],
            "status_counts": sc,
        }
    }
    _COUNTS_CACHE["data"] = data
    _COUNTS_CACHE["time"] = now
    return jsonify({"status": "success", "counts": data, "cached": False})


@christmas_banner_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    moodboard_id = (data.get("moodboard_id") or "").strip()
    if not moodboard_id:
        return jsonify({"status": "error", "error": "moodboard_id required"}), 400
    save_config_override(MOODBOARD_ENV_KEY, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "moodboard_id": moodboard_id})


@christmas_banner_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    prompt_text = (data.get("prompt") or "").strip()
    if not prompt_text:
        return jsonify({"status": "error", "error": "prompt required"}), 400
    save_config_override(PROMPT_ENV_KEY, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "prompt": prompt_text})


@christmas_banner_bp.route("/status", methods=["GET"])
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


@christmas_banner_bp.route("/run", methods=["POST"])
def run_pipeline_route():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    custom_moodboard = (data.get("moodboard_id") or "").strip()
    custom_prompt = (data.get("prompt") or "").strip()

    fix_info = get_fixture()

    running, desc = is_any_pipeline_running()
    if running:
        return jsonify({"status": "error", "error": f"Another pipeline is currently active: {desc}"}), 409

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Christmas Banner pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": FIXTURE_ID,
            "active_table_id": fix_info["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": TOTAL_PHASES,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering the Banner Set (one row, three banners)..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline(PIPELINE_KEY, "Banner Set")

        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / SCRIPT_NAME),
            "--table-id", fix_info["table_id"],
        ]
        if custom_moodboard:
            cmd.extend(["--moodboard-id", custom_moodboard])
        if custom_prompt:
            cmd.extend(["--interior-prompt", custom_prompt])

        try:
            p = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                text=True,
                bufsize=1,
            )
            with _STATE_LOCK:
                _EXEC_STATE["process"] = p

            stage = 0  # 0 Christmas banner, 1 Sale banner, 2 third banner
            for line in iter(p.stdout.readline, ""):
                txt = line.strip()
                if not txt:
                    continue
                with _STATE_LOCK:
                    _EXEC_STATE["logs"].append(txt)
                    low = txt.lower()
                    # The pipeline prints "[PHASE n]" headers; only those move the phase. Each banner's own
                    # "[PHASE 6]" ends its stage, and the next banner then prints its phases from 2 again.
                    for n in range(1, 7):
                        if f"[phase {n}]" in low:
                            idx = phase_index(n, stage)
                            _EXEC_STATE["current_phase"] = PHASE_LABELS[idx]
                            _EXEC_STATE["current_phase_index"] = idx
                            if n == 6 and stage < 2:
                                stage += 1

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
                    _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Banner Set completed successfully.")
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
        "message": "Started Banner Set",
        "fixture_id": FIXTURE_ID,
    })


@christmas_banner_bp.route("/stop", methods=["POST"])
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
