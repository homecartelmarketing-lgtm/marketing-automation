"""Moodboard Story Pipeline API Blueprint (/api/moodboard-story/*)."""

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

moodboard_story_bp = Blueprint("moodboard_story", __name__, url_prefix="/api/moodboard-story")


MOODBOARD_STORY_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIERS_MOODBOARD_STORY",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_MOODBOARD_STORY",
        "default": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS_MOODBOARD_STORY",
        "default": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
    },
}

MOODBOARD_STORY_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "MOODBOARD_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room",
    },
    "pendant": {
        "env_key": "MOODBOARD_PROMPT_PENDANT",
        "default": "Generate me a modern dining room",
    },
    "floor-lamp": {
        "env_key": "MOODBOARD_PROMPT_FLOOR_LAMP",
        "default": "Generate me a modern living room with empty floor space for a standing floor lamp",
    },
}


def resolve_mb_moodboard_id(fixture_id: str) -> str:
    """Resolve active Krea Moodboard ID from .env or preset fallback."""
    cfg = MOODBOARD_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    # General fallbacks
    if fixture_id == "chandelier":
        val = os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
        if val:
            return val
    elif fixture_id == "pendant":
        val = os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
        if val:
            return val
    elif fixture_id == "floor-lamp":
        val = os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
        if val:
            return val
    return default


def resolve_mb_prompt(fixture_id: str) -> str:
    """Resolve active Krea Prompt from .env or preset fallback."""
    cfg = MOODBOARD_STORY_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def get_moodboard_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 3 supported Moodboard Story fixture tables."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_MOODBOARD_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_MOODBOARD_STORY")
                or "tblHQrci8d1K9ws2M"
            ).strip(),
            "category": "chandeliers",
            "moodboard_id": resolve_mb_moodboard_id("chandelier"),
            "prompt": resolve_mb_prompt("chandelier"),
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARD_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHT_MOODBOARD_STORY")
                or "tblkm119i48y0M1IQ"
            ).strip(),
            "category": "pendant_lights",
            "moodboard_id": resolve_mb_moodboard_id("pendant"),
            "prompt": resolve_mb_prompt("pendant"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_MOODBOARD_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_MOODBOARD_STORY")
                or "tblBaNeiSZeYrUawW"
            ).strip(),
            "category": "floor_lamps",
            "moodboard_id": resolve_mb_moodboard_id("floor-lamp"),
            "prompt": resolve_mb_prompt("floor-lamp"),
            "total": 100,
        },
    }


MOODBOARD_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": 5,
    "proc": None,
    "logs": [],
    "started_at": None,
    "ended_at": None,
    "exit_code": None,
    "error": None,
}
MOODBOARD_STATE_LOCK = threading.Lock()

MOODBOARD_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_moodboard_phase(line: str) -> tuple[str, int] | None:
    """Infer current Moodboard Story pipeline phase from stdout line."""
    lower = line.lower()
    if "ingestion" in lower or ("scraping" in lower and "akeneo" in lower):
        return "Phase 0/5: Akeneo Product Scraping", 0
    if "phase 1" in lower or "krea ai" in lower or ("krea" in lower and "interior" in lower):
        return "Phase 1/5: Krea AI 9:16 Vertical Interior Generation", 1
    if "phase 2" in lower or ("claude" in lower and "prompt" in lower) or "generated prompt" in lower:
        return "Phase 2/5: Claude Sonnet 5 Prompt Generation", 2
    if "phase 3" in lower or "blended image" in lower or "daytime blending" in lower:
        return "Phase 3/5: Fal AI Nano Banana Pro Daytime Blending", 3
    if "phase 4" in lower or "logo overlay" in lower or "logo" in lower:
        return "Phase 4/5: Logo Overlay Stamping", 4
    if "phase 5" in lower or "moodboard converted" in lower or "card conversion" in lower:
        return "Phase 5/5: Fal AI Moodboard Card Conversion & Final Upload", 5
    return None


@moodboard_story_bp.route("/counts", methods=["GET"])
def get_moodboard_counts():
    """Return live completed counts for all 3 Moodboard Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with MOODBOARD_STATE_LOCK:
        if not force_refresh and (now - MOODBOARD_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and MOODBOARD_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": MOODBOARD_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_moodboard_count(item):
            key, fix = item
            table_id = fix["table_id"]
            url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
            headers = {"Authorization": f"Bearer {token}"}
            params = {
                "filterByFormula": "OR({Status} = 'Posted', {Status} = 'Scheduled', {Status} = 'Schedule', {Status} = 'Complete', {Status} = 'Completed', {Status} = 'Done', {Status} = 'Already attached a room Interior', {Status} = 'Discard', {Status} = 'Discarded', {Status} = 'For Manual', {Status} = 'For  Manual', {Status} = 'Minor revision', {Status} = 'Minor Revision', {Status} = 'FM')",
                "fields[]": "Status",
                "pageSize": 100,
            }

            p_count = 0
            s_count = 0
            c_count = 0
            d_count = 0
            fm_count = 0
            offset = None

            while True:
                req_params = dict(params)
                if offset:
                    req_params["offset"] = offset

                try:
                    resp = requests.get(url, headers=headers, params=req_params, timeout=12)
                    if not resp.ok:
                        raise RuntimeError(f"Airtable count request failed with HTTP {resp.status_code}")
                    body = resp.json()
                    records = body.get("records", [])
                    for rec in records:
                        raw_status = str(rec.get("fields", {}).get("Status") or "").strip()
                        norm_status = " ".join(raw_status.lower().split())
                        if norm_status in ("posted", "processing", "pending", "in progress"):
                            p_count += 1
                        elif norm_status in ("scheduled", "schedule"):
                            s_count += 1
                        elif norm_status in ("complete", "completed", "done", "already attached a room interior"):
                            c_count += 1
                        elif norm_status in ("discard", "discarded"):
                            d_count += 1
                        elif norm_status in ("for manual", "for  manual", "minor revision", "minor revisions", "fm"):
                            fm_count += 1
                    offset = body.get("offset")
                    if not offset:
                        break
                except Exception:
                    raise

            return key, {
                "id": fix["id"],
                "name": fix["name"],
                "table_id": table_id,
                "moodboard_id": fix.get("moodboard_id") or resolve_mb_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_mb_prompt(key),
                "completed": c_count,
                "total": fix["total"],
                "status_counts": {
                    "P": p_count,
                    "S": s_count,
                    "C": c_count,
                    "D": d_count,
                    "FM": fm_count,
                },
            }

        fixtures = get_moodboard_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_moodboard_count, fixtures.items()):
                results[k] = v

        with MOODBOARD_STATE_LOCK:
            MOODBOARD_COUNTS_CACHE["timestamp"] = now
            MOODBOARD_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@moodboard_story_bp.route("/moodboard", methods=["POST"])
def update_moodboard_story_moodboard():
    """Update and persist Krea Moodboard ID in .env for a Moodboard Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in MOODBOARD_STORY_MOODBOARD_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_moodboard_id:
        return jsonify({
            "status": "error",
            "error": "Moodboard ID cannot be empty",
        }), 400

    cfg = MOODBOARD_STORY_MOODBOARD_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_moodboard_id)

        with MOODBOARD_STATE_LOCK:
            MOODBOARD_COUNTS_CACHE["timestamp"] = 0

        return jsonify({
            "status": "success",
            "fixture_id": fixture_id,
            "moodboard_id": new_moodboard_id,
            "message": f"Successfully updated Moodboard ID for {fixture_id} in .env",
        })
    except Exception as err:
        return jsonify({
            "status": "error",
            "error": f"Failed to update .env: {err}",
        }), 500


@moodboard_story_bp.route("/prompt", methods=["POST"])
def update_moodboard_story_prompt():
    """Update and persist Krea Interior Generation Prompt in .env for a Moodboard Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in MOODBOARD_STORY_PROMPT_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_prompt:
        return jsonify({
            "status": "error",
            "error": "Prompt cannot be empty",
        }), 400

    cfg = MOODBOARD_STORY_PROMPT_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_prompt)

        with MOODBOARD_STATE_LOCK:
            MOODBOARD_COUNTS_CACHE["timestamp"] = 0

        return jsonify({
            "status": "success",
            "fixture_id": fixture_id,
            "prompt": new_prompt,
            "message": f"Successfully updated prompt for {fixture_id} in .env",
        })
    except Exception as err:
        return jsonify({
            "status": "error",
            "error": f"Failed to update .env: {err}",
        }), 500


@moodboard_story_bp.route("/run", methods=["POST"])
def run_moodboard_pipeline():
    """Trigger run_moodboard_story.py for a single fixture table (1 item)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = payload.get("fixture_id", "chandelier")
    max_items = int(payload.get("max_items", 1))

    fixtures = get_moodboard_fixtures()
    if fixture_id not in fixtures:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'. Supported: {list(fixtures.keys())}",
        }), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    category_flag = fix["category"]
    active_moodboard_id = fix.get("moodboard_id") or resolve_mb_moodboard_id(fixture_id)
    active_prompt = fix.get("prompt") or resolve_mb_prompt(fixture_id)

    with MOODBOARD_STATE_LOCK:
        if MOODBOARD_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "message": f"Moodboard pipeline is already running for {MOODBOARD_STATE.get('active_fixture')}",
            }), 409

        MOODBOARD_STATE["status"] = "running"
        MOODBOARD_STATE["active_fixture"] = fixture_id
        MOODBOARD_STATE["active_table_id"] = table_id
        MOODBOARD_STATE["current_phase"] = "Initializing Moodboard Story Pipeline..."
        MOODBOARD_STATE["current_phase_index"] = 0
        MOODBOARD_STATE["total_phases"] = 5
        MOODBOARD_STATE["logs"] = []
        MOODBOARD_STATE["started_at"] = time.time()
        MOODBOARD_STATE["ended_at"] = None
        MOODBOARD_STATE["exit_code"] = None
        MOODBOARD_STATE["error"] = None

    register_pipeline("moodboard_story", {"fixture": fixture_id, "table_id": table_id})

    def worker():
        script_path = MARKETING_DIR / "run_moodboard_story.py"
        cmd = [
            sys.executable,
            "-u",
            str(script_path),
            "--target",
            category_flag,
            "--batch-size",
            str(max_items),
        ]

        child_env = os.environ.copy()
        child_env["PYTHONUNBUFFERED"] = "1"
        child_env["MARKETING_AUTOMATION_HEADLESS"] = "1"
        if active_moodboard_id:
            child_env["KREA_MOODBOARD_ID"] = active_moodboard_id
            if fixture_id == "chandelier":
                child_env["KREA_MOODBOARD_ID_CHANDELIERS"] = active_moodboard_id
                child_env["MOODBOARD_ID_CHANDELIER"] = active_moodboard_id
            elif fixture_id == "pendant":
                child_env["KREA_MOODBOARD_ID_PENDANT_LIGHTS"] = active_moodboard_id
                child_env["MOODBOARD_ID_PENDANT_LIGHTS"] = active_moodboard_id
            elif fixture_id == "floor-lamp":
                child_env["KREA_MOODBOARD_ID_FLOOR_LAMPS"] = active_moodboard_id
                child_env["MOODBOARD_ID_FLOOR_LAMPS"] = active_moodboard_id
        if active_prompt:
            child_env["KREA_PROMPT"] = active_prompt
            if fixture_id == "chandelier":
                child_env["MOODBOARD_STORY_PROMPT_CHANDELIER"] = active_prompt
                child_env["MOODBOARD_PROMPT_CHANDELIER"] = active_prompt
            elif fixture_id == "pendant":
                child_env["MOODBOARD_STORY_PROMPT_PENDANT_LIGHTS"] = active_prompt
                child_env["MOODBOARD_PROMPT_PENDANT"] = active_prompt
            elif fixture_id == "floor-lamp":
                child_env["MOODBOARD_STORY_PROMPT_FLOOR_LAMPS"] = active_prompt
                child_env["MOODBOARD_PROMPT_FLOOR_LAMP"] = active_prompt

        with MOODBOARD_STATE_LOCK:
            MOODBOARD_STATE["logs"].append(f"[INIT] Command: {' '.join(cmd)}")
            MOODBOARD_STATE["logs"].append(f"[CONFIG] Table: {fix['name']} ({table_id})")
            MOODBOARD_STATE["logs"].append(f"[CONFIG] Moodboard ID: {active_moodboard_id}")
            MOODBOARD_STATE["logs"].append(f"[CONFIG] Prompt: {active_prompt}")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            with MOODBOARD_STATE_LOCK:
                MOODBOARD_STATE["proc"] = proc

            for line in iter(proc.stdout.readline, ""):
                clean_line = line.rstrip()
                if not clean_line:
                    continue
                with MOODBOARD_STATE_LOCK:
                    MOODBOARD_STATE["logs"].append(clean_line)
                    phase_info = detect_moodboard_phase(clean_line)
                    if phase_info:
                        label, idx = phase_info
                        MOODBOARD_STATE["current_phase"] = label
                        MOODBOARD_STATE["current_phase_index"] = idx

            proc.stdout.close()
            proc.wait()

            with MOODBOARD_STATE_LOCK:
                MOODBOARD_STATE["proc"] = None
                MOODBOARD_STATE["ended_at"] = time.time()
                MOODBOARD_STATE["exit_code"] = proc.returncode

                if proc.returncode == 0:
                    MOODBOARD_STATE["status"] = "completed"
                    MOODBOARD_STATE["current_phase"] = "Pipeline Finished Successfully"
                    MOODBOARD_STATE["current_phase_index"] = 5
                    MOODBOARD_STATE["logs"].append("[COMPLETE] Moodboard Pipeline finished with exit code 0.")
                    MOODBOARD_COUNTS_CACHE["timestamp"] = 0
                else:
                    clean_err = extract_clean_error(MOODBOARD_STATE["logs"], proc.returncode)
                    MOODBOARD_STATE["status"] = "error"
                    MOODBOARD_STATE["error"] = clean_err
                    MOODBOARD_STATE["logs"].append(f"[ERROR] {clean_err}")
        except Exception as err:
            with MOODBOARD_STATE_LOCK:
                MOODBOARD_STATE["status"] = "error"
                MOODBOARD_STATE["error"] = str(err)
                MOODBOARD_STATE["logs"].append(f"[EXCEPTION] Failed to run pipeline: {err}")
                MOODBOARD_STATE["proc"] = None
        finally:
            unregister_pipeline("moodboard_story")

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "moodboard_id": active_moodboard_id,
        "max_items": max_items,
    })


@moodboard_story_bp.route("/status", methods=["GET"])
def get_moodboard_status():
    """Return live pipeline execution state and recent stdout logs."""
    with MOODBOARD_STATE_LOCK:
        elapsed = 0
        if MOODBOARD_STATE["started_at"]:
            end = MOODBOARD_STATE["ended_at"] or time.time()
            elapsed = int(end - MOODBOARD_STATE["started_at"])

        return jsonify({
            "status": MOODBOARD_STATE["status"],
            "active_fixture": MOODBOARD_STATE["active_fixture"],
            "active_table_id": MOODBOARD_STATE["active_table_id"],
            "current_phase": MOODBOARD_STATE["current_phase"],
            "current_phase_index": MOODBOARD_STATE["current_phase_index"],
            "total_phases": MOODBOARD_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": MOODBOARD_STATE["exit_code"],
            "error": MOODBOARD_STATE["error"],
            "logs": MOODBOARD_STATE["logs"][-150:],
        })


@moodboard_story_bp.route("/stop", methods=["POST"])
def stop_moodboard_pipeline():
    """Stop/cancel the running pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with MOODBOARD_STATE_LOCK:
        proc = MOODBOARD_STATE.get("proc")
        if not proc or MOODBOARD_STATE["status"] != "running":
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            MOODBOARD_STATE["status"] = "stopped"
            MOODBOARD_STATE["logs"].append("[USER] Pipeline execution cancelled by user.")
            unregister_pipeline("moodboard_story")
            return jsonify({"status": "stopped"})
        except Exception as err:
            return jsonify({"status": "error", "error": str(err)}), 500
