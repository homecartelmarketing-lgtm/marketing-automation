"""Style This? Story Pipeline API Blueprint (/api/style-this/*)."""

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

style_this_bp = Blueprint("style_this_story", __name__, url_prefix="/api/style-this")

STYLE_THIS_STORY_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_STYLE_THIS_CHANDELIER",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_STYLE_THIS_FLOOR_LAMPS",
        "default": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
    },
}

STYLE_THIS_STORY_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "STYLE_THIS_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room",
    },
    "floor-lamp": {
        "env_key": "STYLE_THIS_PROMPT_FLOOR_LAMPS",
        "default": "Modern living room interior, stylish lounge chair, warm ambient lighting, spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait",
    },
}


def resolve_style_this_moodboard_id(fixture_id: str) -> str:
    """Resolve active Krea Moodboard ID from .env or preset fallback."""
    cfg = STYLE_THIS_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    # Fallback to general env vars
    if fixture_id == "chandelier":
        val = (
            os.getenv("KREA_MOODBOARD_ID_STYLE_THIS_CHANDELIERS", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
        )
        if val:
            return val
    elif fixture_id == "floor-lamp":
        val = (
            os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMP", "").strip()
        )
        if val:
            return val
    return default


def resolve_style_this_prompt(fixture_id: str) -> str:
    """Resolve active Krea Prompt from .env or preset fallback."""
    cfg = STYLE_THIS_STORY_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    # Fallback to general env vars
    if fixture_id == "chandelier":
        val = os.getenv("STYLE_THIS_PROMPT_CHANDELIERS", "").strip()
        if val:
            return val
    elif fixture_id == "floor-lamp":
        val = os.getenv("STYLE_THIS_PROMPT_FLOOR_LAMP", "").strip()
        if val:
            return val
    return default


def get_style_this_fixtures() -> dict[str, dict[str, Any]]:
    """Return supported Style This? fixture tables with table IDs, moodboard IDs, and prompts resolved from .env."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_CHANDELIER")
                or os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_CHANDELIERS")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_STYLE_THIS")
                or "tblYge5R7LwTJkEHC"
            ).strip(),
            "category": "chandeliers",
            "moodboard_id": resolve_style_this_moodboard_id("chandelier"),
            "prompt": resolve_style_this_prompt("chandelier"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_FLOOR_LAMPS")
                or os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_FLOOR_LAMP")
                or os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS")
                or "tblvSAzXasTVI85r9"
            ).strip(),
            "category": "floor_lamps",
            "moodboard_id": resolve_style_this_moodboard_id("floor-lamp"),
            "prompt": resolve_style_this_prompt("floor-lamp"),
            "total": 100,
        },
    }


STYLE_THIS_STATE: dict[str, Any] = {
    "status": "idle",  # "idle" | "running" | "completed" | "error" | "stopped"
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
STYLE_THIS_STATE_LOCK = threading.Lock()

STYLE_THIS_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_style_this_phase(line: str) -> tuple[str, int] | None:
    """Infer current Style This? Story pipeline phase from stdout line."""
    lower = line.lower()
    if "phase 0" in lower or "scraping" in lower or "akeneo" in lower or "scrape" in lower:
        return "Phase 1/5: Akeneo Product Scraping & Deduplication", 1
    if "phase 1" in lower or "interior" in lower or "krea" in lower:
        return "Phase 2/5: Krea AI 9:16 Room Interior Generation (4 Slots)", 2
    if "phase 2" in lower or "claude" in lower or "prompt" in lower or "color" in lower or "vibe" in lower:
        return "Phase 3/5: Claude Sonnet 5 Prompt & Color Analysis", 3
    if "phase 3" in lower or "nano banana" in lower or "blended" in lower or "blending" in lower:
        return "Phase 4/5: Nano Banana Pro 9:16 Image Blending (4 Slots)", 4
    if "phase 4" in lower or "double tap" in lower or "layout" in lower or "converted" in lower or "pillow" in lower:
        return "Phase 5/5: Story Cards Layout Conversion & Stamping", 5
    return None


@style_this_bp.route("/counts", methods=["GET"])
def get_style_this_counts():
    """Return live completed counts for all 4 Style This? Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with STYLE_THIS_STATE_LOCK:
        if not force_refresh and (now - STYLE_THIS_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and STYLE_THIS_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": STYLE_THIS_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_style_count(item):
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
                "moodboard_id": fix.get("moodboard_id") or resolve_style_this_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_style_this_prompt(key),
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

        fixtures = get_style_this_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_style_count, fixtures.items()):
                results[k] = v

        with STYLE_THIS_STATE_LOCK:
            STYLE_THIS_COUNTS_CACHE["timestamp"] = now
            STYLE_THIS_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@style_this_bp.route("/moodboard", methods=["POST"])
def update_style_this_moodboard():
    """Update and persist Krea Moodboard ID in .env for a Style This? Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in STYLE_THIS_STORY_MOODBOARD_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_moodboard_id:
        return jsonify({
            "status": "error",
            "error": "Moodboard ID cannot be empty",
        }), 400

    cfg = STYLE_THIS_STORY_MOODBOARD_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_moodboard_id)

        # Invalidate counts cache so next fetch reflects new moodboard
        with STYLE_THIS_STATE_LOCK:
            STYLE_THIS_COUNTS_CACHE["timestamp"] = 0

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


@style_this_bp.route("/prompt", methods=["POST"])
def update_style_this_prompt():
    """Update and persist Krea Prompt in .env for a Style This? Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in STYLE_THIS_STORY_PROMPT_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_prompt:
        return jsonify({
            "status": "error",
            "error": "Prompt cannot be empty",
        }), 400

    cfg = STYLE_THIS_STORY_PROMPT_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_prompt)

        with STYLE_THIS_STATE_LOCK:
            STYLE_THIS_COUNTS_CACHE["timestamp"] = 0

        return jsonify({
            "status": "success",
            "fixture_id": fixture_id,
            "prompt": new_prompt,
            "message": f"Successfully updated Krea Prompt for {fixture_id} in .env",
        })
    except Exception as err:
        return jsonify({
            "status": "error",
            "error": f"Failed to update .env: {err}",
        }), 500


@style_this_bp.route("/run", methods=["POST"])
def run_style_this_pipeline():
    """Trigger generate_style_this_story_pipeline.py for a single fixture table (1 item)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = payload.get("fixture_id", "floor-lamp")
    max_items = int(payload.get("max_items", 1))
    custom_moodboard_id = str(payload.get("moodboard_id", "")).strip()
    custom_prompt = str(payload.get("prompt", "")).strip()

    fixtures = get_style_this_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    active_moodboard_id = custom_moodboard_id or fix.get("moodboard_id") or resolve_style_this_moodboard_id(fixture_id)
    active_prompt = custom_prompt or fix.get("prompt") or resolve_style_this_prompt(fixture_id)

    # Persist overridden moodboard to overrides/env if explicitly provided and changed
    if custom_moodboard_id and custom_moodboard_id != fix.get("moodboard_id"):
        cfg = STYLE_THIS_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
        env_key = cfg.get("env_key")
        if env_key:
            try:
                save_config_override(env_key, custom_moodboard_id)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist moodboard_id: {e}")

    # Persist overridden prompt to overrides/env if explicitly provided and changed
    if custom_prompt and custom_prompt != fix.get("prompt"):
        cfg = STYLE_THIS_STORY_PROMPT_CONFIG.get(fixture_id, {})
        env_key = cfg.get("env_key")
        if env_key:
            try:
                save_config_override(env_key, custom_prompt)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist prompt: {e}")

    running, other_desc = is_any_pipeline_running(exclude="style-this")
    if running:
        return jsonify({
            "status": "already_running",
            "message": f"Another pipeline is currently running ({other_desc}). Please wait for it to finish.",
        }), 409

    with STYLE_THIS_STATE_LOCK:
        if STYLE_THIS_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "active_fixture": STYLE_THIS_STATE["active_fixture"],
                "message": f"Style This pipeline is already running for {STYLE_THIS_STATE['active_fixture']}",
            }), 409

        STYLE_THIS_STATE["status"] = "running"
        STYLE_THIS_STATE["active_fixture"] = fixture_id
        STYLE_THIS_STATE["active_table_id"] = table_id
        STYLE_THIS_STATE["current_phase"] = "Phase 1/5: Initializing Pipeline..."
        STYLE_THIS_STATE["current_phase_index"] = 1
        STYLE_THIS_STATE["total_phases"] = 5
        STYLE_THIS_STATE["logs"] = [
            f"[START] Triggered Style This Pipeline for {fix['name']} ({table_id}, {max_items} item)..."
        ]
        STYLE_THIS_STATE["started_at"] = time.time()
        STYLE_THIS_STATE["ended_at"] = None
        STYLE_THIS_STATE["exit_code"] = None
        STYLE_THIS_STATE["error"] = None

    register_pipeline("style-this", f"Style This Story - {fix['name']}")

    def worker():
        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / "generate_style_this_story_pipeline.py"),
            "--table-id",
            table_id,
            "--limit",
            str(max_items),
            "--moodboard-id",
            active_moodboard_id,
            "--prompt",
            active_prompt,
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            with STYLE_THIS_STATE_LOCK:
                STYLE_THIS_STATE["proc"] = proc

            for raw_line in iter(proc.stdout.readline, ""):
                if not raw_line:
                    break
                line = raw_line.rstrip()
                with STYLE_THIS_STATE_LOCK:
                    STYLE_THIS_STATE["logs"].append(line)
                    if len(STYLE_THIS_STATE["logs"]) > 1000:
                        STYLE_THIS_STATE["logs"].pop(0)

                    detected = detect_style_this_phase(line)
                    if detected:
                        STYLE_THIS_STATE["current_phase"], STYLE_THIS_STATE["current_phase_index"] = detected

            proc.stdout.close()
            proc.wait()
            ret_code = proc.returncode

            with STYLE_THIS_STATE_LOCK:
                STYLE_THIS_STATE["ended_at"] = time.time()
                STYLE_THIS_STATE["exit_code"] = ret_code
                if ret_code == 0:
                    STYLE_THIS_STATE["status"] = "completed"
                    STYLE_THIS_STATE["current_phase"] = "Phase 5/5: Pipeline Completed Successfully"
                    STYLE_THIS_STATE["current_phase_index"] = 5
                    STYLE_THIS_STATE["logs"].append(f"\n[DONE] Pipeline completed successfully for {fix['name']} (Code {ret_code})")
                else:
                    STYLE_THIS_STATE["status"] = "error"
                    STYLE_THIS_STATE["error"] = extract_clean_error(STYLE_THIS_STATE["logs"], ret_code)
                    STYLE_THIS_STATE["logs"].append(f"\n[ERROR] Pipeline exited with code {ret_code}")

        except Exception as err:
            with STYLE_THIS_STATE_LOCK:
                STYLE_THIS_STATE["status"] = "error"
                STYLE_THIS_STATE["error"] = str(err)
                STYLE_THIS_STATE["logs"].append(f"\n[FATAL] Execution failed: {err}")
        finally:
            unregister_pipeline("style-this")
            with STYLE_THIS_STATE_LOCK:
                STYLE_THIS_STATE["proc"] = None

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "moodboard_id": active_moodboard_id,
        "prompt": active_prompt,
        "max_items": max_items,
    })


@style_this_bp.route("/status", methods=["GET"])
def get_style_this_status():
    """Return live execution status and logs for Style This? Story pipeline."""
    with STYLE_THIS_STATE_LOCK:
        elapsed = 0
        if STYLE_THIS_STATE["started_at"]:
            end = STYLE_THIS_STATE["ended_at"] or time.time()
            elapsed = int(end - STYLE_THIS_STATE["started_at"])

        return jsonify({
            "status": STYLE_THIS_STATE["status"],
            "active_fixture": STYLE_THIS_STATE["active_fixture"],
            "active_table_id": STYLE_THIS_STATE["active_table_id"],
            "current_phase": STYLE_THIS_STATE["current_phase"],
            "current_phase_index": STYLE_THIS_STATE["current_phase_index"],
            "total_phases": STYLE_THIS_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": STYLE_THIS_STATE["exit_code"],
            "error": STYLE_THIS_STATE["error"],
            "logs": STYLE_THIS_STATE["logs"][-300:],
        })


@style_this_bp.route("/stop", methods=["POST"])
def stop_style_this_pipeline():
    """Cancel running Style This? Story pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with STYLE_THIS_STATE_LOCK:
        proc = STYLE_THIS_STATE.get("proc")
        if not proc or proc.poll() is not None:
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
                proc.kill()
        except Exception as err:
            return jsonify({"status": "error", "error": f"Failed to terminate process: {err}"}), 500

        STYLE_THIS_STATE["status"] = "stopped"
        STYLE_THIS_STATE["ended_at"] = time.time()
        STYLE_THIS_STATE["logs"].append("\n[STOP] Pipeline execution stopped by user request.")
        STYLE_THIS_STATE["proc"] = None

    unregister_pipeline("style-this")
    return jsonify({"status": "stopped", "message": "Pipeline cancelled successfully"})
