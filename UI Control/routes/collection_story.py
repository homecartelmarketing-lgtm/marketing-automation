"""Collection Category Story Pipeline API Blueprint (/api/collection-story/*)."""

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

collection_story_bp = Blueprint("collection_story", __name__, url_prefix="/api/collection-story")


COLLECTION_STORY_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_COLLEC_STORY_PENDANT",
        "default": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
    },
    "wall-light": {
        "env_key": "KREA_MOODBOARD_ID_COLLEC_STORY_WALL_LIGHT",
        "default": "afa1317e-7be1-47f5-9d6f-91c7769a767d",
    },
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_COLLEC_STORY_CHANDELIER",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_COLLEC_STORY_FLOOR_LAMP",
        "default": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
    },
    "cluster-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_COLLEC_STORY_CLUSTER_CHANDELIER",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
}

COLLECTION_STORY_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "pendant": {
        "env_key": "COLLEC_STORY_PROMPT_PENDANT",
        "default": "Generate me a modern dining room hanging pendant light not too oversize item",
    },
    "wall-light": {
        "env_key": "COLLEC_STORY_PROMPT_WALL_LIGHT",
        "default": "Generate me a modern living room with wall sconce mounted on the wall",
    },
    "chandelier": {
        "env_key": "COLLEC_STORY_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room hanging chandelier",
    },
    "floor-lamp": {
        "env_key": "COLLEC_STORY_PROMPT_FLOOR_LAMP",
        "default": "Generate me a modern bedroom that have beside a floor lamp",
    },
    "cluster-chandelier": {
        "env_key": "COLLEC_STORY_PROMPT_CLUSTER_CHANDELIER",
        "default": "Generate me a modern living room with cluster chandelier hanging from the ceiling",
    },
}


def resolve_moodboard_id(fixture_id: str) -> str:
    """Resolve active Krea Moodboard ID from .env or preset fallback."""
    cfg = COLLECTION_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def resolve_collec_prompt(fixture_id: str) -> str:
    """Resolve active Krea Prompt from .env or preset fallback."""
    cfg = COLLECTION_STORY_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def get_collection_story_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 5 supported Collection Category Story fixture tables with table IDs, moodboard IDs, and prompts."""
    return {
        "pendant": {
            "id": "pendant",
            "name": "Pendant Lights",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_COLLEC_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_PENDANT_COLLEC_STORY")
                or "tblSSVJnubFk2yBm3"
            ).strip(),
            "moodboard_id": resolve_moodboard_id("pendant"),
            "prompt": resolve_collec_prompt("pendant"),
            "total": 100,
        },
        "wall-light": {
            "id": "wall-light",
            "name": "Wall Lights",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_WALL_LIGHTS_COLLEC_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_WALL_LIGHT_COLLEC_STORY")
                or "tbl98UU0h4uFyFIlL"
            ).strip(),
            "moodboard_id": resolve_moodboard_id("wall-light"),
            "prompt": resolve_collec_prompt("wall-light"),
            "total": 100,
        },
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_COLLEC_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_COLLEC_STORY")
                or "tblJMJQlrnlDb1GtN"
            ).strip(),
            "moodboard_id": resolve_moodboard_id("chandelier"),
            "prompt": resolve_collec_prompt("chandelier"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_COLLEC_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_COLLEC_STORY")
                or "tblloZLRSKwOCg247"
            ).strip(),
            "moodboard_id": resolve_moodboard_id("floor-lamp"),
            "prompt": resolve_collec_prompt("floor-lamp"),
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIERS_COLLEC_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_COLLEC_STORY")
                or "tblsXXcoZZD4q6WWt"
            ).strip(),
            "moodboard_id": resolve_moodboard_id("cluster-chandelier"),
            "prompt": resolve_collec_prompt("cluster-chandelier"),
            "total": 100,
        },
    }


COLLEC_STORY_STATE: dict[str, Any] = {
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
COLLEC_STORY_STATE_LOCK = threading.Lock()

COLLEC_STORY_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_collec_phase(line: str) -> tuple[str, int] | None:
    """Infer current Collection Category Story pipeline phase from stdout line."""
    lower = line.lower()
    if "phase 1" in lower or ("scraping" in lower and "akeneo" in lower) or "scrape" in lower:
        return "Phase 1/5: Akeneo Product Scraping & Layout", 1
    if "phase 2" in lower or "krea" in lower or "interior" in lower:
        return "Phase 2/5: Krea AI Room Interiors (3 Slots)", 2
    if "phase 3" in lower or ("claude" in lower and "prompt" in lower) or "blending prompt" in lower:
        return "Phase 3/5: Claude Blending Prompt Analysis", 3
    if "phase 4" in lower or ("blending" in lower and ("nano" in lower or "banana" in lower)):
        return "Phase 4/5: Nano Banana Pro Image Blending (3 Slots)", 4
    if "phase 5" in lower or "conversion" in lower or "grid" in lower or "converted" in lower or "pillow" in lower or "logo" in lower:
        return "Phase 5/5: 9:16 Auto-Grid & Brand Overlays Stamping", 5
    return None


@collection_story_bp.route("/counts", methods=["GET"])
def get_collec_story_counts():
    """Return live completed counts for all 5 Collection Category Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with COLLEC_STORY_STATE_LOCK:
        if not force_refresh and (now - COLLEC_STORY_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and COLLEC_STORY_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": COLLEC_STORY_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_collec_count(item):
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
                "moodboard_id": fix.get("moodboard_id") or resolve_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_collec_prompt(key),
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

        fixtures = get_collection_story_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_collec_count, fixtures.items()):
                results[k] = v

        with COLLEC_STORY_STATE_LOCK:
            COLLEC_STORY_COUNTS_CACHE["timestamp"] = now
            COLLEC_STORY_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@collection_story_bp.route("/moodboard", methods=["POST"])
def update_collec_story_moodboard():
    """Update and persist Krea Moodboard ID in .env for a Collection Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in COLLECTION_STORY_MOODBOARD_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_moodboard_id:
        return jsonify({
            "status": "error",
            "error": "Moodboard ID cannot be empty",
        }), 400

    cfg = COLLECTION_STORY_MOODBOARD_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_moodboard_id)

        # Invalidate counts cache so next fetch reflects new moodboard
        with COLLEC_STORY_STATE_LOCK:
            COLLEC_STORY_COUNTS_CACHE["timestamp"] = 0

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


@collection_story_bp.route("/prompt", methods=["POST"])
def update_collec_story_prompt():
    """Update and persist Krea Interior Generation Prompt in .env for a Collection Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in COLLECTION_STORY_PROMPT_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_prompt:
        return jsonify({
            "status": "error",
            "error": "Prompt cannot be empty",
        }), 400

    cfg = COLLECTION_STORY_PROMPT_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_prompt)

        with COLLEC_STORY_STATE_LOCK:
            COLLEC_STORY_COUNTS_CACHE["timestamp"] = 0

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


@collection_story_bp.route("/run", methods=["POST"])
def run_collec_story_pipeline():
    """Trigger generate_collection_category_story_pipeline.py for a single fixture table (1 item)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = payload.get("fixture_id", "pendant")
    max_items = int(payload.get("max_items", 1))
    custom_moodboard_id = str(payload.get("moodboard_id", "")).strip()
    custom_prompt = str(payload.get("prompt", "")).strip()

    fixtures = get_collection_story_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    active_moodboard_id = custom_moodboard_id or fix.get("moodboard_id") or resolve_moodboard_id(fixture_id)
    active_prompt = custom_prompt or fix.get("prompt") or resolve_collec_prompt(fixture_id)

    # If custom moodboard_id was provided, persist to overrides/env as the new default
    if custom_moodboard_id and fixture_id in COLLECTION_STORY_MOODBOARD_CONFIG:
        cfg = COLLECTION_STORY_MOODBOARD_CONFIG[fixture_id]
        env_key = cfg["env_key"]
        try:
            save_config_override(env_key, custom_moodboard_id)
            with COLLEC_STORY_STATE_LOCK:
                COLLEC_STORY_COUNTS_CACHE["timestamp"] = 0
        except Exception:
            pass

    # If custom prompt was provided, persist to overrides/env as the new default
    if custom_prompt and fixture_id in COLLECTION_STORY_PROMPT_CONFIG:
        p_cfg = COLLECTION_STORY_PROMPT_CONFIG[fixture_id]
        p_key = p_cfg["env_key"]
        try:
            save_config_override(p_key, custom_prompt)
            with COLLEC_STORY_STATE_LOCK:
                COLLEC_STORY_COUNTS_CACHE["timestamp"] = 0
        except Exception:
            pass

    # Check global concurrency across pipelines
    running, other_desc = is_any_pipeline_running(exclude="collection-story")
    if running:
        return jsonify({
            "status": "already_running",
            "message": f"Another pipeline is currently running ({other_desc}). Please wait for it to finish.",
        }), 409

    with COLLEC_STORY_STATE_LOCK:
        if COLLEC_STORY_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "active_fixture": COLLEC_STORY_STATE["active_fixture"],
                "message": f"Collection Category Story pipeline is already running for {COLLEC_STORY_STATE['active_fixture']}",
            }), 409

        COLLEC_STORY_STATE["status"] = "running"
        COLLEC_STORY_STATE["active_fixture"] = fixture_id
        COLLEC_STORY_STATE["active_table_id"] = table_id
        COLLEC_STORY_STATE["current_phase"] = "Phase 1/5: Initializing Pipeline..."
        COLLEC_STORY_STATE["current_phase_index"] = 1
        COLLEC_STORY_STATE["total_phases"] = 5
        COLLEC_STORY_STATE["logs"] = [
            f"[START] Triggered Collection Category Story Pipeline for {fix['name']} ({table_id}, Moodboard: {active_moodboard_id}, {max_items} item)..."
        ]
        COLLEC_STORY_STATE["started_at"] = time.time()
        COLLEC_STORY_STATE["ended_at"] = None
        COLLEC_STORY_STATE["exit_code"] = None
        COLLEC_STORY_STATE["error"] = None

    register_pipeline("collection-story", f"Collection Category Story - {fix['name']}")

    def worker():
        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / "generate_collection_category_story_pipeline.py"),
            "--table-id",
            table_id,
            "--max-items",
            str(max_items),
            "--moodboard-id",
            active_moodboard_id,
            "--prompt",
            active_prompt,
            "--mode",
            "all",
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

            with COLLEC_STORY_STATE_LOCK:
                COLLEC_STORY_STATE["proc"] = proc

            for raw_line in iter(proc.stdout.readline, ""):
                if not raw_line:
                    break
                line = raw_line.rstrip()
                with COLLEC_STORY_STATE_LOCK:
                    COLLEC_STORY_STATE["logs"].append(line)
                    if len(COLLEC_STORY_STATE["logs"]) > 1000:
                        COLLEC_STORY_STATE["logs"].pop(0)

                    detected = detect_collec_phase(line)
                    if detected:
                        COLLEC_STORY_STATE["current_phase"], COLLEC_STORY_STATE["current_phase_index"] = detected

            proc.stdout.close()
            proc.wait()
            ret_code = proc.returncode

            with COLLEC_STORY_STATE_LOCK:
                COLLEC_STORY_STATE["ended_at"] = time.time()
                COLLEC_STORY_STATE["exit_code"] = ret_code
                if ret_code == 0:
                    COLLEC_STORY_STATE["status"] = "completed"
                    COLLEC_STORY_STATE["current_phase"] = "Phase 5/5: Pipeline Completed Successfully"
                    COLLEC_STORY_STATE["current_phase_index"] = 5
                    COLLEC_STORY_STATE["logs"].append(f"\n[DONE] Pipeline completed successfully for {fix['name']} (Code {ret_code})")
                else:
                    clean_err = extract_clean_error(COLLEC_STORY_STATE["logs"], ret_code)
                    COLLEC_STORY_STATE["status"] = "error"
                    COLLEC_STORY_STATE["error"] = clean_err
                    COLLEC_STORY_STATE["logs"].append(f"\n[ERROR] {clean_err}")

        except Exception as err:
            with COLLEC_STORY_STATE_LOCK:
                COLLEC_STORY_STATE["status"] = "error"
                COLLEC_STORY_STATE["error"] = str(err)
                COLLEC_STORY_STATE["logs"].append(f"\n[FATAL] Execution failed: {err}")
        finally:
            unregister_pipeline("collection-story")
            with COLLEC_STORY_STATE_LOCK:
                COLLEC_STORY_STATE["proc"] = None

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "max_items": max_items,
    })


@collection_story_bp.route("/status", methods=["GET"])
def get_collec_story_status():
    """Return live execution status and logs for the Collection Category Story pipeline."""
    with COLLEC_STORY_STATE_LOCK:
        elapsed = 0
        if COLLEC_STORY_STATE["started_at"]:
            end = COLLEC_STORY_STATE["ended_at"] or time.time()
            elapsed = int(end - COLLEC_STORY_STATE["started_at"])

        return jsonify({
            "status": COLLEC_STORY_STATE["status"],
            "active_fixture": COLLEC_STORY_STATE["active_fixture"],
            "active_table_id": COLLEC_STORY_STATE["active_table_id"],
            "current_phase": COLLEC_STORY_STATE["current_phase"],
            "current_phase_index": COLLEC_STORY_STATE["current_phase_index"],
            "total_phases": COLLEC_STORY_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": COLLEC_STORY_STATE["exit_code"],
            "error": COLLEC_STORY_STATE["error"],
            "logs": COLLEC_STORY_STATE["logs"][-300:],
        })


@collection_story_bp.route("/stop", methods=["POST"])
def stop_collec_story_pipeline():
    """Cancel running Collection Category Story pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with COLLEC_STORY_STATE_LOCK:
        proc = COLLEC_STORY_STATE.get("proc")
        if not proc or proc.poll() is not None:
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
                proc.kill()
        except Exception as err:
            return jsonify({"status": "error", "error": f"Failed to terminate process: {err}"}), 500

        COLLEC_STORY_STATE["status"] = "stopped"
        COLLEC_STORY_STATE["ended_at"] = time.time()
        COLLEC_STORY_STATE["logs"].append("\n[STOP] Pipeline execution stopped by user request.")
        COLLEC_STORY_STATE["proc"] = None

    unregister_pipeline("collection-story")
    return jsonify({"status": "stopped", "message": "Pipeline cancelled successfully"})
