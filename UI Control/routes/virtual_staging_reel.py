"""Virtual Staging Reel Pipeline API Blueprint (/api/virtual-staging-reel/*)."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from PIL import Image

from content_automation.config import load_settings
from content_automation.fal_client import FalClient
from generate_virtual_staging_reel_pipeline import UPLOAD_KLING_PROMPT, clean_override

from .common import (
    MARKETING_DIR,
    extract_clean_error,
    is_authorized,
    register_pipeline,
    save_config_override,
    unregister_pipeline,
)

virtual_staging_reel_bp = Blueprint(
    "virtual_staging_reel", __name__, url_prefix="/api/virtual-staging-reel"
)

FIXTURE_ID = "virtual-staging"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_VIRTUAL_STAGING_REEL"
TABLE_DEFAULT = "tblPYG5Ed4XURecu6"

MOODBOARD_ENV_KEY = "KREA_MOODBOARD_ID_VIRTUAL_STAGING_REEL"
MOODBOARD_DEFAULT = "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3"

PROMPT_ENV_KEY = "PROMPT_VIRTUAL_STAGING_REEL"
PROMPT_DEFAULT = (
    "Generate me a photo of a modern luxury living room with high ceilings, large windows, "
    "architectural styling, natural daylight, warm aesthetic, high end furniture"
)
KLING_PROMPT_ENV_KEY = "KLING_PROMPT_VIRTUAL_STAGING_REEL"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

TOTAL_PHASES = 7

AUTO_PHASE_LABELS: dict[int, str] = {
    1: "Phase 1: Akeneo Product Scrape & Shopify Check",
    2: "Phase 2: Krea Luxury Interior Generation",
    3: "Phase 3: Claude Blending Prompt Generation",
    4: "Phase 4: Fal Nano Banana Pro Room Blend",
    5: "Phase 5: Claude Vision Empty-Room Stripping",
    6: "Phase 6: Fal Kling 3.0 Pro Video Generation",
    7: "Phase 7: Branded Pill, Outro & Audio Muxing",
}

UPLOAD_PHASE_LABELS: dict[int, str] = {
    1: "Phase 1: Akeneo Product Scrape & Shopify Check",
    2: "Phase 2: Empty Room Upload",
    3: "Phase 3: Claude Staging Prompt Generation",
    4: "Phase 4: Fal Nano Banana Pro Room Blend (End Frame)",
    5: "Phase 5: Skipped (uploaded room)",
    6: "Phase 6: Fal Kling 3.0 Pro Video Generation (Queue)",
    7: "Phase 7: Branded Pill, Outro & Audio Muxing",
}

PHASE_LABELS = AUTO_PHASE_LABELS
_PHASE_RE = re.compile(r"\[PHASE\s+(\d+)\s*/\s*\d+\]", re.IGNORECASE)


def update_phase_from_log(state: dict[str, Any], line: str) -> None:
    """Advance the phase from an explicit `[PHASE n/7]` log marker (never moves backwards)."""
    match = _PHASE_RE.search(line)
    if not match:
        return
    idx = int(match.group(1))
    labels = state.get("phase_labels") or AUTO_PHASE_LABELS
    if idx in labels and idx >= int(state.get("current_phase_index") or 0):
        state["current_phase"] = labels[idx]
        state["current_phase_index"] = idx


def get_fixture() -> dict[str, Any]:
    saved_kling = clean_override(os.getenv(KLING_PROMPT_ENV_KEY))
    return {
        "id": FIXTURE_ID,
        "name": "Virtual Staging",
        "table_id": (os.getenv(TABLE_ENV_KEY) or TABLE_DEFAULT).strip(),
        "total": 100,
        "moodboard_id": (os.getenv(MOODBOARD_ENV_KEY) or MOODBOARD_DEFAULT).strip(),
        "prompt": (os.getenv(PROMPT_ENV_KEY) or PROMPT_DEFAULT).strip(),
        "kling_prompt": saved_kling or UPLOAD_KLING_PROMPT,
    }


_EXEC_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": TOTAL_PHASES,
    "phase_labels": AUTO_PHASE_LABELS,
    "elapsed_seconds": 0,
    "logs": [],
    "error": None,
    "process": None,
    "start_time": None,
}
_STATE_LOCK = threading.Lock()
_COUNTS_CACHE: dict[str, Any] = {}
_COUNTS_CACHE_TTL = 30.0


@virtual_staging_reel_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({"status": "success", "fixtures": [get_fixture()]})


@virtual_staging_reel_bp.route("/counts", methods=["GET"])
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
            "completed": sc.get("C", 0),
            "total": fixture["total"],
            "moodboard_id": fixture["moodboard_id"],
            "prompt": fixture["prompt"],
            "kling_prompt": fixture.get("kling_prompt", ""),
            "status_counts": sc,
        }
    except Exception:
        results[FIXTURE_ID] = {
            "id": fixture["id"],
            "name": fixture["name"],
            "table_id": fixture["table_id"],
            "completed": 0,
            "total": fixture["total"],
            "moodboard_id": fixture["moodboard_id"],
            "prompt": fixture["prompt"],
            "kling_prompt": fixture.get("kling_prompt", ""),
            "status_counts": {},
        }

    _COUNTS_CACHE["data"] = results
    _COUNTS_CACHE["time"] = now
    return jsonify({"status": "success", "counts": results, "cached": False})


@virtual_staging_reel_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    moodboard_id = (data.get("moodboard_id") or "").strip()
    if not moodboard_id or moodboard_id.lower() in ("none", "null", "undefined"):
        return jsonify({"status": "error", "error": "moodboard_id required"}), 400
    save_config_override(MOODBOARD_ENV_KEY, moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "moodboard_id": moodboard_id})


@virtual_staging_reel_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    prompt_text = (data.get("prompt") or "").strip()
    if not prompt_text or prompt_text.lower() in ("none", "null", "undefined"):
        return jsonify({"status": "error", "error": "prompt required"}), 400
    save_config_override(PROMPT_ENV_KEY, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "prompt": prompt_text})


@virtual_staging_reel_bp.route("/kling-prompt", methods=["POST"])
def update_kling_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    prompt_text = (data.get("prompt") or "").strip()
    if not prompt_text or prompt_text.lower() in ("none", "null", "undefined"):
        return jsonify({"status": "error", "error": "Valid prompt text is required"}), 400
    save_config_override(KLING_PROMPT_ENV_KEY, prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "kling_prompt": prompt_text})


@virtual_staging_reel_bp.route("/upload-empty-room", methods=["POST"])
def upload_empty_room():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({"status": "error", "error": "File exceeds 15 MB limit"}), 413

    if "file" not in request.files:
        return jsonify({"status": "error", "error": "No file uploaded"}), 400

    file = request.files["file"]
    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"status": "error", "error": f"Unsupported file type '{ext}'. Allowed: JPEG, PNG, WebP"}), 415

    temp_input = Path(tempfile.gettempdir()) / f"upload_raw_{int(time.time() * 1000)}{ext}"
    temp_output = Path(tempfile.gettempdir()) / f"empty_room_{int(time.time() * 1000)}.jpg"
    try:
        file.save(str(temp_input))
        if temp_input.stat().st_size > MAX_UPLOAD_BYTES:
            return jsonify({"status": "error", "error": "File exceeds 15 MB limit"}), 413

        try:
            with Image.open(temp_input) as img:
                img.verify()
        except Exception as img_err:
            return jsonify({"status": "error", "error": f"Invalid or corrupted image: {img_err}"}), 415

        from content_automation.media import crop_to_reel

        try:
            crop_to_reel(temp_input, temp_output, size=(1080, 1920), min_short_side=720)
        except ValueError as val_err:
            return jsonify({"status": "error", "error": str(val_err)}), 422

        settings = load_settings()
        fal = FalClient(api_key=settings.fal_key)
        empty_room_url = fal.upload_file(temp_output)
        return jsonify({
            "status": "success",
            "empty_room_url": empty_room_url,
            "width": 1080,
            "height": 1920,
        })
    finally:
        temp_input.unlink(missing_ok=True)
        temp_output.unlink(missing_ok=True)



@virtual_staging_reel_bp.route("/status", methods=["GET"])
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


@virtual_staging_reel_bp.route("/run", methods=["POST"])
def run_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    source = str(data.get("source", "auto") or "auto").strip().lower()
    if source not in ("auto", "upload"):
        return jsonify({"status": "error", "error": "Invalid source: must be 'auto' or 'upload'"}), 400

    empty_room_url = str(data.get("empty_room_url") or "").strip()
    if source == "upload":
        if not empty_room_url:
            return jsonify({"status": "error", "error": "empty_room_url is required when source is 'upload'"}), 400
        parsed = urlparse(empty_room_url)
        host = (parsed.hostname or "").lower()
        if not (host == "fal.media" or host.endswith(".fal.media")):
            return jsonify({"status": "error", "error": "Invalid empty_room_url: must be a fal.media URL"}), 400
        max_items = 1
    else:
        try:
            max_items = min(max(int(data.get("max_items", 1) or 1), 1), 10)
        except (TypeError, ValueError):
            return jsonify({"error": "max_items must be an integer"}), 400

    custom_moodboard = (data.get("moodboard_id") or "").strip()
    custom_prompt = (data.get("prompt") or "").strip()
    dry_run = bool(data.get("dry_run"))
    record_id = (data.get("record_id") or "").strip()
    fixture = get_fixture()

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "Virtual Staging Reel pipeline is already running"}), 409
        phase_labels = UPLOAD_PHASE_LABELS if source == "upload" else AUTO_PHASE_LABELS
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": FIXTURE_ID,
            "active_table_id": fixture["table_id"],
            "phase_labels": phase_labels,
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": TOTAL_PHASES,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering Virtual Staging Reel ({max_items} row(s), source={source})..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("virtual-staging-reel", "Virtual Staging Reel")
        cmd = [
            sys.executable,
            "-u",
            "generate_virtual_staging_reel_pipeline.py",
            "--table-id", fixture["table_id"],
            "--max-items", str(max_items),
        ]
        if source == "upload":
            cmd += ["--source", "upload", "--empty-room-url", empty_room_url]
        if custom_moodboard:
            cmd += ["--moodboard-id", custom_moodboard]
        if custom_prompt:
            cmd += ["--prompt", custom_prompt]
        if dry_run:
            cmd.append("--dry-run")
        if record_id:
            cmd += ["--record-id", record_id]
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
            unregister_pipeline("virtual-staging-reel")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fixture["name"]})


@virtual_staging_reel_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("virtual-staging-reel")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
