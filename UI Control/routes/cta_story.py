"""CTA Story Pipeline API Blueprint (/api/cta/*)."""

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

cta_bp = Blueprint("cta_story", __name__, url_prefix="/api/cta")

CTA_STORY_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIER_CTA",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_CTA",
        "default": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
    },
    "cluster-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_CTA",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
    "table-lamp": {
        "env_key": "KREA_MOODBOARD_ID_TABLE_LAMPS_CTA",
        "default": "351d992d-19e3-4b1e-aa46-08a842796c61",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMP_CTA",
        "default": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
    },
}

CTA_STORY_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "CTA_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room",
    },
    "pendant": {
        "env_key": "CTA_PROMPT_PENDANT_LIGHTS",
        "default": "Generate me a modern dining room",
    },
    "cluster-chandelier": {
        "env_key": "CTA_PROMPT_CLUSTER_CHANDELIER",
        "default": "Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait",
    },
    "table-lamp": {
        "env_key": "CTA_PROMPT_TABLE_LAMPS",
        "default": "Generate me a modern bedroom with a table lamp side by side",
    },
    "floor-lamp": {
        "env_key": "CTA_PROMPT_FLOOR_LAMPS",
        "default": "Modern living room interior, stylish lounge chair, warm ambient lighting, spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait",
    },
}


def resolve_cta_moodboard_id(fixture_id: str) -> str:
    """Resolve active Krea Moodboard ID from .env or preset fallback."""
    cfg = CTA_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    # Fallback checks for alternate env var names
    if fixture_id == "floor-lamp":
        val = (
            os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMP_CTA", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
        )
        if val:
            return val
    elif fixture_id == "table-lamp":
        val = (
            os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS_DAY_NIGHT_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS", "").strip()
        )
        if val:
            return val
    elif fixture_id == "chandelier":
        val = os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
        if val:
            return val
    elif fixture_id == "pendant":
        val = os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
        if val:
            return val
    elif fixture_id == "cluster-chandelier":
        val = (
            os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER", "").strip()
        )
        if val:
            return val
    return default


def resolve_cta_prompt(fixture_id: str) -> str:
    """Resolve active Krea Prompt from .env or preset fallback."""
    cfg = CTA_STORY_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def get_cta_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 5 supported CTA Story fixture tables with table IDs, moodboard IDs, and prompts."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_CTA") or "tblYHdVq14FjMWg5o").strip(),
            "category_code": "chandelier_cta_story",
            "moodboard_id": resolve_cta_moodboard_id("chandelier"),
            "prompt": resolve_cta_prompt("chandelier"),
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Lights",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_CTA") or "tblfl7fqFZa2vUieB").strip(),
            "category_code": "pendant_lights_cta_story",
            "moodboard_id": resolve_cta_moodboard_id("pendant"),
            "prompt": resolve_cta_prompt("pendant"),
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_CTA") or "tblSpGJLO3faYfIDY").strip(),
            "category_code": "cluster_chandelier_cta_story",
            "moodboard_id": resolve_cta_moodboard_id("cluster-chandelier"),
            "prompt": resolve_cta_prompt("cluster-chandelier"),
            "total": 100,
        },
        "table-lamp": {
            "id": "table-lamp",
            "name": "Table Lamps",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMPS_CTA") or "tblKJeCCp4zQ6g7Em").strip(),
            "category_code": "table_lamps_cta_story",
            "moodboard_id": resolve_cta_moodboard_id("table-lamp"),
            "prompt": resolve_cta_prompt("table-lamp"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_CTA") or os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_CTA") or "tblPKSYyjgbgMypE2").strip(),
            "category_code": "floor_lamp_cta_story",
            "moodboard_id": resolve_cta_moodboard_id("floor-lamp"),
            "prompt": resolve_cta_prompt("floor-lamp"),
            "total": 100,
        },
    }

# Backward compatibility alias
CTA_FIXTURES = get_cta_fixtures()

STATE: dict[str, Any] = {
    "status": "idle",  # "idle" | "running" | "completed" | "error" | "stopped"
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": 6,
    "proc": None,
    "logs": [],
    "started_at": None,
    "ended_at": None,
    "exit_code": None,
    "error": None,
}
STATE_LOCK = threading.Lock()

COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_phase(line: str) -> tuple[str, int] | None:
    """Infer current pipeline phase from stdout line."""
    lower = line.lower()
    if "phase 1" in lower or ("scraping" in lower and "akeneo" in lower):
        return "Phase 1/6: Akeneo Product Scraping", 1
    if "phase 2" in lower or "generating krea interior" in lower or ("krea" in lower and "interior" in lower):
        return "Phase 2/6: Krea AI Interior Generation", 2
    if "phase 3" in lower or ("claude" in lower and "prompt" in lower) or "blending prompt" in lower:
        return "Phase 3/6: Claude Blending Prompt Analysis", 3
    if "phase 4" in lower or "blending" in lower or "nano banana" in lower:
        return "Phase 4/6: Nano Banana Pro Image Blending", 4
    if "phase 5" in lower or "headline" in lower or "word generated" in lower:
        return "Phase 5/6: Claude Headline Analysis", 5
    if "phase 6" in lower or "stamping" in lower or "watermark" in lower or "converted image" in lower:
        return "Phase 6/6: Logo & CTA Layout Stamping", 6
    return None


@cta_bp.route("/counts", methods=["GET"])
def get_cta_counts():
    """Return live completed counts for all 5 CTA Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with STATE_LOCK:
        if not force_refresh and (now - COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_cta_count(item):
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
                "moodboard_id": fix.get("moodboard_id") or resolve_cta_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_cta_prompt(key),
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

        fixtures = get_cta_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_cta_count, fixtures.items()):
                results[k] = v

        with STATE_LOCK:
            COUNTS_CACHE["timestamp"] = now
            COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@cta_bp.route("/moodboard", methods=["POST"])
def update_cta_moodboard():
    """Update and persist Krea Moodboard ID in .env for a CTA Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in CTA_STORY_MOODBOARD_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_moodboard_id:
        return jsonify({
            "status": "error",
            "error": "Moodboard ID cannot be empty",
        }), 400

    cfg = CTA_STORY_MOODBOARD_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        if fixture_id == "floor-lamp":
            env_content = env_file.read_text(encoding="utf-8") if env_file.is_file() else ""
            if "KREA_MOODBOARD_ID_FLOOR_LAMP_CTA" in env_content:
                env_key = "KREA_MOODBOARD_ID_FLOOR_LAMP_CTA"
            elif "KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA" in env_content:
                env_key = "KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA"

        save_config_override(env_key, new_moodboard_id)
        if fixture_id == "floor-lamp":
            save_config_override("KREA_MOODBOARD_ID_FLOOR_LAMP_CTA", new_moodboard_id)
            save_config_override("KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA", new_moodboard_id)

        # Invalidate counts cache so next fetch reflects new moodboard
        with STATE_LOCK:
            COUNTS_CACHE["timestamp"] = 0

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


@cta_bp.route("/prompt", methods=["POST"])
def update_cta_prompt():
    """Update and persist Krea Interior Generation Prompt in .env for a CTA Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in CTA_STORY_PROMPT_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_prompt:
        return jsonify({
            "status": "error",
            "error": "Prompt cannot be empty",
        }), 400

    cfg = CTA_STORY_PROMPT_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_prompt)

        with STATE_LOCK:
            COUNTS_CACHE["timestamp"] = 0

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


@cta_bp.route("/run", methods=["POST"])
def run_cta_pipeline():
    """Trigger generate_cta_story_pipeline.py for a single fixture table (1 item)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = payload.get("fixture_id", "chandelier")
    max_items = int(payload.get("max_items", 1))
    custom_moodboard_id = str(payload.get("moodboard_id", "")).strip()
    custom_prompt = str(payload.get("prompt", "")).strip()

    fixtures = get_cta_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    active_moodboard_id = custom_moodboard_id or fix.get("moodboard_id") or resolve_cta_moodboard_id(fixture_id)
    active_prompt = custom_prompt or fix.get("prompt") or resolve_cta_prompt(fixture_id)

    # Persist overridden moodboard to overrides/env if explicitly provided and changed
    if custom_moodboard_id and custom_moodboard_id != fix.get("moodboard_id"):
        cfg = CTA_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
        env_key = cfg.get("env_key")
        env_file = MARKETING_DIR / ".env"
        if fixture_id == "floor-lamp":
            env_content = env_file.read_text(encoding="utf-8") if env_file.is_file() else ""
            if "KREA_MOODBOARD_ID_FLOOR_LAMP_CTA" in env_content:
                env_key = "KREA_MOODBOARD_ID_FLOOR_LAMP_CTA"
            elif "KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA" in env_content:
                env_key = "KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA"
        if env_key:
            try:
                save_config_override(env_key, custom_moodboard_id)
                if fixture_id == "floor-lamp":
                    save_config_override("KREA_MOODBOARD_ID_FLOOR_LAMP_CTA", custom_moodboard_id)
                    save_config_override("KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA", custom_moodboard_id)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist moodboard_id: {e}")

    # Persist overridden prompt to overrides/env if explicitly provided and changed
    if custom_prompt and custom_prompt != fix.get("prompt"):
        p_cfg = CTA_STORY_PROMPT_CONFIG.get(fixture_id, {})
        p_key = p_cfg.get("env_key")
        if p_key:
            try:
                save_config_override(p_key, custom_prompt)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist prompt: {e}")

    # Check global concurrency
    running, other_desc = is_any_pipeline_running(exclude="cta")
    if running:
        return jsonify({
            "status": "already_running",
            "message": f"Another pipeline is currently running ({other_desc}). Please wait for it to finish.",
        }), 409

    with STATE_LOCK:
        if STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "active_fixture": STATE["active_fixture"],
                "message": f"CTA Story pipeline is already running for {STATE['active_fixture']}",
            }), 409

        STATE["status"] = "running"
        STATE["active_fixture"] = fixture_id
        STATE["active_table_id"] = table_id
        STATE["current_phase"] = "Phase 1/6: Initializing Pipeline..."
        STATE["current_phase_index"] = 1
        STATE["logs"] = [f"[START] Triggered CTA Story Pipeline for {fix['name']} ({table_id}, {max_items} item)..."]
        STATE["started_at"] = time.time()
        STATE["ended_at"] = None
        STATE["exit_code"] = None
        STATE["error"] = None

    register_pipeline("cta", f"CTA Story - {fix['name']}")

    def worker():
        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / "generate_cta_story_pipeline.py"),
            "--table-id",
            table_id,
            "--max-items",
            str(max_items),
            "--mode",
            "all",
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

            with STATE_LOCK:
                STATE["proc"] = proc

            for raw_line in iter(proc.stdout.readline, ""):
                if not raw_line:
                    break
                line = raw_line.rstrip()
                with STATE_LOCK:
                    STATE["logs"].append(line)
                    if len(STATE["logs"]) > 1000:
                        STATE["logs"].pop(0)

                    detected = detect_phase(line)
                    if detected:
                        STATE["current_phase"], STATE["current_phase_index"] = detected

            proc.stdout.close()
            proc.wait()

            with STATE_LOCK:
                STATE["exit_code"] = proc.returncode
                STATE["ended_at"] = time.time()
                STATE["proc"] = None
                if proc.returncode == 0:
                    STATE["status"] = "completed"
                    STATE["current_phase"] = "Pipeline Finished Successfully ✓"
                    STATE["current_phase_index"] = 6
                    STATE["logs"].append("[COMPLETE] Pipeline finished with exit code 0.")
                    COUNTS_CACHE["timestamp"] = 0
                else:
                    clean_err = extract_clean_error(STATE["logs"], proc.returncode)
                    STATE["status"] = "error"
                    STATE["error"] = clean_err
                    STATE["logs"].append(f"[ERROR] {clean_err}")
        except Exception as err:
            with STATE_LOCK:
                STATE["status"] = "error"
                STATE["error"] = str(err)
                STATE["logs"].append(f"[EXCEPTION] Failed to run pipeline: {err}")
                STATE["proc"] = None
        finally:
            unregister_pipeline("cta")

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "moodboard_id": active_moodboard_id,
        "max_items": max_items,
    })


@cta_bp.route("/status", methods=["GET"])
def get_cta_status():
    """Return live pipeline execution state and recent stdout logs."""
    with STATE_LOCK:
        elapsed = 0
        if STATE["started_at"]:
            end = STATE["ended_at"] or time.time()
            elapsed = int(end - STATE["started_at"])

        return jsonify({
            "status": STATE["status"],
            "active_fixture": STATE["active_fixture"],
            "active_table_id": STATE["active_table_id"],
            "current_phase": STATE["current_phase"],
            "current_phase_index": STATE["current_phase_index"],
            "total_phases": STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": STATE["exit_code"],
            "error": STATE["error"],
            "logs": STATE["logs"][-150:],
        })


@cta_bp.route("/stop", methods=["POST"])
def stop_cta_pipeline():
    """Stop/cancel the running pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with STATE_LOCK:
        proc = STATE.get("proc")
        if not proc or STATE["status"] != "running":
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            STATE["status"] = "stopped"
            STATE["logs"].append("[USER] Pipeline execution cancelled by user.")
            unregister_pipeline("cta")
            return jsonify({"status": "stopped"})
        except Exception as err:
            return jsonify({"status": "error", "error": str(err)}), 500
