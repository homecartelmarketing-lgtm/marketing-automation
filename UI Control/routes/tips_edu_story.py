"""Tips & Educational Story Pipeline API Blueprint (/api/tips-edu/*)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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

tips_edu_bp = Blueprint("tips_edu_story", __name__, url_prefix="/api/tips-edu")

import os

TIPS_EDU_STORY_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_TIPS_EDU_STORY",
        "default": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS_TIPS_EDU_STORY",
        "default": "b1641228-beec-4823-8d01-1de3eec8410d",
    },
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIERS_TIPS_EDU_STORY",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
    "ceiling-mounted": {
        "env_key": "KREA_MOODBOARD_ID_CEILING_MOUNTED_TIPS_EDU_STORY",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
    "table-lamp": {
        "env_key": "KREA_MOODBOARD_ID_TABLE_LAMPS_TIPS_EDU_STORY",
        "default": "257569e1-7be8-4412-a90f-acbc347e4646",
    },
    "cluster-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIERS_TIPS_EDU_STORY",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
}

TIPS_EDU_STORY_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "pendant": {
        "env_key": "TIPS_EDU_PROMPT_PENDANT_LIGHTS",
        "default": "Generate me a modern dining room",
    },
    "floor-lamp": {
        "env_key": "TIPS_EDU_PROMPT_FLOOR_LAMPS",
        "default": "Generate a premium modern interior in a vertical 9:16 composition with a clearly visible, prominent standing floor lamp beside an armchair. The floor lamp must be fully in frame and clearly visible from top to base. Bright, photorealistic, elegant modern room styling, no text or unrelated lighting fixtures.",
    },
    "chandelier": {
        "env_key": "TIPS_EDU_PROMPT_CHANDELIERS",
        "default": "Generate me a modern living room",
    },
    "ceiling-mounted": {
        "env_key": "TIPS_EDU_PROMPT_CEILING_MOUNTED",
        "default": "Generate a premium modern hallway interior in a vertical 9:16 composition with clean walls and a plain, flat ceiling with a central focal point for a flush-mount ceiling light. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    },
    "table-lamp": {
        "env_key": "TIPS_EDU_PROMPT_TABLE_LAMPS",
        "default": "Generate a premium modern bedroom interior in a vertical 9:16 composition with a prominent bedside nightstand table surface in full view for a table lamp. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    },
    "cluster-chandelier": {
        "env_key": "TIPS_EDU_PROMPT_CLUSTER_CHANDELIERS",
        "default": "Generate a premium modern high-ceiling living room interior in a vertical 9:16 composition with a spacious vertical ceiling volume for a hanging cluster chandelier. Bright, photorealistic, elegant modern styling, no text or unrelated lighting fixtures.",
    },
}


def resolve_tips_edu_moodboard_id(fixture_id: str) -> str:
    """Resolve active Krea Moodboard ID from .env or preset fallback."""
    cfg = TIPS_EDU_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    # Fallback to general env vars
    if fixture_id == "pendant":
        val = os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
        if val:
            return val
    elif fixture_id == "floor-lamp":
        val = (
            os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMP", "").strip()
        )
        if val:
            return val
    elif fixture_id == "chandelier":
        val = (
            os.getenv("KREA_MOODBOARD_ID_CHANDELIER_TIPS_EDU_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
        )
        if val:
            return val
    elif fixture_id == "ceiling-mounted":
        val = (
            os.getenv("KREA_MOODBOARD_ID_CEILING_LIGHTS_TIPS_EDU_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CEILING_LIGHT_TIPS_EDU_STORY", "").strip()
        )
        if val:
            return val
    elif fixture_id == "table-lamp":
        val = (
            os.getenv("KREA_MOODBOARD_ID_TABLE_LAMP_TIPS_EDU_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS", "").strip()
        )
        if val:
            return val
    elif fixture_id == "cluster-chandelier":
        val = (
            os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_TIPS_EDU_STORY", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER", "").strip()
        )
        if val:
            return val
    return default


def resolve_tips_edu_prompt(fixture_id: str) -> str:
    """Resolve active Krea Prompt from .env or preset fallback."""
    cfg = TIPS_EDU_STORY_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    # Fallback to general/alternate env vars
    if fixture_id == "chandelier":
        val = os.getenv("TIPS_EDU_PROMPT_CHANDELIER", "").strip()
        if val:
            return val
    elif fixture_id == "pendant":
        val = os.getenv("TIPS_EDU_PROMPT_PENDANT", "").strip()
        if val:
            return val
    elif fixture_id == "floor-lamp":
        val = os.getenv("TIPS_EDU_PROMPT_FLOOR_LAMP", "").strip()
        if val:
            return val
    elif fixture_id == "ceiling-mounted":
        val = os.getenv("TIPS_EDU_PROMPT_CEILING_LIGHTS", "").strip()
        if val:
            return val
    elif fixture_id == "table-lamp":
        val = os.getenv("TIPS_EDU_PROMPT_TABLE_LAMP", "").strip()
        if val:
            return val
    elif fixture_id == "cluster-chandelier":
        val = os.getenv("TIPS_EDU_PROMPT_CLUSTER_CHANDELIER", "").strip()
        if val:
            return val
    return default


# The 6 supported Tips & Educational Story fixture tables (dynamically resolved from .env)
def get_tips_edu_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 6 supported Tips & Educational Story fixture tables with table IDs, moodboards, and prompts resolved from .env."""
    return {
        "pendant": {
            "id": "pendant",
            "name": "Pendant Lights",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDU_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHT_TIPS_EDU_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_PENDANT_TIPS_EDU_STORY")
                or "tblwnFN5a8fLzKuP4"
            ).strip(),
            "target": "pendant_lights",
            "moodboard_id": resolve_tips_edu_moodboard_id("pendant"),
            "prompt": resolve_tips_edu_prompt("pendant"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_TIPS_EDU_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_TIPS_EDU_STORY")
                or "tblJxWwZexgBHl26B"
            ).strip(),
            "target": "floor_lamps",
            "moodboard_id": resolve_tips_edu_moodboard_id("floor-lamp"),
            "prompt": resolve_tips_edu_prompt("floor-lamp"),
            "total": 100,
        },
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_TIPS_EDU_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_TIPS_EDU_STORY")
                or "tblpFiaNn1Ym9fTTk"
            ).strip(),
            "target": "chandeliers",
            "moodboard_id": resolve_tips_edu_moodboard_id("chandelier"),
            "prompt": resolve_tips_edu_prompt("chandelier"),
            "total": 100,
        },
        "ceiling-mounted": {
            "id": "ceiling-mounted",
            "name": "Ceiling Mounted",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CEILING_MOUNTED_TIPS_EDU_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_CEILING_LIGHTS_TIPS_EDU_STORY")
                or "tblGlRibUZXB9R3Gt"
            ).strip(),
            "target": "ceiling_mounted",
            "moodboard_id": resolve_tips_edu_moodboard_id("ceiling-mounted"),
            "prompt": resolve_tips_edu_prompt("ceiling-mounted"),
            "total": 100,
        },
        "table-lamp": {
            "id": "table-lamp",
            "name": "Table Lamps",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMPS_TIPS_EDU_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMP_TIPS_EDU_STORY")
                or "tblZtENqILDAekLv2"
            ).strip(),
            "target": "table_lamps",
            "moodboard_id": resolve_tips_edu_moodboard_id("table-lamp"),
            "prompt": resolve_tips_edu_prompt("table-lamp"),
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIERS_TIPS_EDU_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_TIPS_EDU_STORY")
                or "tbllzkE2prSyj9BaD"
            ).strip(),
            "target": "cluster_chandeliers",
            "moodboard_id": resolve_tips_edu_moodboard_id("cluster-chandelier"),
            "prompt": resolve_tips_edu_prompt("cluster-chandelier"),
            "total": 100,
        },
    }

TIPS_EDU_STATE: dict[str, Any] = {
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
TIPS_EDU_STATE_LOCK = threading.Lock()

TIPS_EDU_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_tips_phase(line: str) -> tuple[str, int] | None:
    """Infer current Tips & Edu Story pipeline phase from stdout line."""
    lower = line.lower()
    if "phase 1" in lower or ("scraping" in lower and "akeneo" in lower):
        return "Phase 1/5: Akeneo Product Scraping", 1
    if "phase 2" in lower or "generating krea interior" in lower or ("krea" in lower and "interior" in lower):
        return "Phase 2/5: Krea AI Interior Generation", 2
    if "phase 3" in lower or ("claude" in lower and "prompt" in lower) or "blending prompt" in lower:
        return "Phase 3/5: Claude Blending Prompt Analysis", 3
    if "phase 4" in lower or ("blending" in lower and ("nano" in lower or "item tagging" in lower or "stamping" in lower)):
        return "Phase 4/5: Nano Banana Pro Blending & Name Tagging", 4
    if "phase 5" in lower or "layout conversion" in lower or "story conversion" in lower or "converted" in lower:
        return "Phase 5/5: Story Layout Conversion & Stamping", 5
    return None


@tips_edu_bp.route("/counts", methods=["GET"])
def get_tips_edu_counts():
    """Return live completed counts for all 6 Tips & Edu Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with TIPS_EDU_STATE_LOCK:
        if not force_refresh and (now - TIPS_EDU_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and TIPS_EDU_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": TIPS_EDU_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_tips_count(item):
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
                "moodboard_id": fix.get("moodboard_id") or resolve_tips_edu_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_tips_edu_prompt(key),
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

        fixtures = get_tips_edu_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_tips_count, fixtures.items()):
                results[k] = v

        with TIPS_EDU_STATE_LOCK:
            TIPS_EDU_COUNTS_CACHE["timestamp"] = now
            TIPS_EDU_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@tips_edu_bp.route("/moodboard", methods=["POST"])
def update_tips_edu_moodboard():
    """Update and persist Krea Moodboard ID in .env for a Tips & Edu Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in TIPS_EDU_STORY_MOODBOARD_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_moodboard_id:
        return jsonify({
            "status": "error",
            "error": "Moodboard ID cannot be empty",
        }), 400

    cfg = TIPS_EDU_STORY_MOODBOARD_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_moodboard_id)

        # Invalidate counts cache so next fetch reflects new moodboard
        with TIPS_EDU_STATE_LOCK:
            TIPS_EDU_COUNTS_CACHE["timestamp"] = 0

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


@tips_edu_bp.route("/prompt", methods=["POST"])
def update_tips_edu_prompt():
    """Update and persist Krea Prompt in .env for a Tips & Edu Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in TIPS_EDU_STORY_PROMPT_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_prompt:
        return jsonify({
            "status": "error",
            "error": "Prompt cannot be empty",
        }), 400

    cfg = TIPS_EDU_STORY_PROMPT_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_prompt)

        with TIPS_EDU_STATE_LOCK:
            TIPS_EDU_COUNTS_CACHE["timestamp"] = 0

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


@tips_edu_bp.route("/run", methods=["POST"])
def run_tips_edu_pipeline():
    """Trigger run_tips_and_edu_story.py for a single fixture table (1 item)."""
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

    fixtures = get_tips_edu_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    target_category = fix["target"]
    active_moodboard_id = custom_moodboard_id or fix.get("moodboard_id") or resolve_tips_edu_moodboard_id(fixture_id)
    active_prompt = custom_prompt or fix.get("prompt") or resolve_tips_edu_prompt(fixture_id)

    # Persist overridden moodboard to overrides/env if explicitly provided and changed
    if custom_moodboard_id and custom_moodboard_id != fix.get("moodboard_id"):
        cfg = TIPS_EDU_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
        env_key = cfg.get("env_key")
        if env_key:
            try:
                save_config_override(env_key, custom_moodboard_id)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist moodboard_id: {e}")

    # Persist overridden prompt to overrides/env if explicitly provided and changed
    if custom_prompt and custom_prompt != fix.get("prompt"):
        cfg = TIPS_EDU_STORY_PROMPT_CONFIG.get(fixture_id, {})
        env_key = cfg.get("env_key")
        if env_key:
            try:
                save_config_override(env_key, custom_prompt)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist prompt: {e}")

    # Check global concurrency
    running, other_desc = is_any_pipeline_running(exclude="tips_edu")
    if running:
        return jsonify({
            "status": "already_running",
            "message": f"Another pipeline is currently running ({other_desc}). Please wait for it to finish.",
        }), 409

    with TIPS_EDU_STATE_LOCK:
        if TIPS_EDU_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "active_fixture": TIPS_EDU_STATE["active_fixture"],
                "message": f"Tips & Edu Story pipeline is already running for {TIPS_EDU_STATE['active_fixture']}",
            }), 409

        TIPS_EDU_STATE["status"] = "running"
        TIPS_EDU_STATE["active_fixture"] = fixture_id
        TIPS_EDU_STATE["active_table_id"] = table_id
        TIPS_EDU_STATE["current_phase"] = "Phase 1/5: Initializing Pipeline..."
        TIPS_EDU_STATE["current_phase_index"] = 1
        TIPS_EDU_STATE["logs"] = [f"[START] Triggered Tips & Edu Story Pipeline for {fix['name']} ({table_id}, target={target_category})..."]
        TIPS_EDU_STATE["started_at"] = time.time()
        TIPS_EDU_STATE["ended_at"] = None
        TIPS_EDU_STATE["exit_code"] = None
        TIPS_EDU_STATE["error"] = None

    register_pipeline("tips_edu", f"Tips & Edu Story - {fix['name']}")

    def worker():
        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / "run_tips_and_edu_story.py"),
            "--target",
            target_category,
            "--table-id",
            table_id,
            "--phase",
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

            with TIPS_EDU_STATE_LOCK:
                TIPS_EDU_STATE["proc"] = proc

            for raw_line in iter(proc.stdout.readline, ""):
                if not raw_line:
                    break
                line = raw_line.rstrip()
                with TIPS_EDU_STATE_LOCK:
                    TIPS_EDU_STATE["logs"].append(line)
                    if len(TIPS_EDU_STATE["logs"]) > 1000:
                        TIPS_EDU_STATE["logs"].pop(0)

                    detected = detect_tips_phase(line)
                    if detected:
                        TIPS_EDU_STATE["current_phase"], TIPS_EDU_STATE["current_phase_index"] = detected

            proc.stdout.close()
            proc.wait()

            with TIPS_EDU_STATE_LOCK:
                TIPS_EDU_STATE["exit_code"] = proc.returncode
                TIPS_EDU_STATE["ended_at"] = time.time()
                TIPS_EDU_STATE["proc"] = None
                if proc.returncode == 0:
                    TIPS_EDU_STATE["status"] = "completed"
                    TIPS_EDU_STATE["current_phase"] = "Tips & Edu Pipeline Finished Successfully ✓"
                    TIPS_EDU_STATE["current_phase_index"] = 5
                    TIPS_EDU_STATE["logs"].append("[COMPLETE] Tips & Edu Story pipeline finished with exit code 0.")
                    TIPS_EDU_COUNTS_CACHE["timestamp"] = 0
                else:
                    TIPS_EDU_STATE["status"] = "error"
                    TIPS_EDU_STATE["error"] = extract_clean_error(TIPS_EDU_STATE["logs"], proc.returncode)
                    TIPS_EDU_STATE["logs"].append(f"[ERROR] Process exited with error code {proc.returncode}.")
        except Exception as err:
            with TIPS_EDU_STATE_LOCK:
                TIPS_EDU_STATE["status"] = "error"
                TIPS_EDU_STATE["error"] = str(err)
                TIPS_EDU_STATE["logs"].append(f"[EXCEPTION] Failed to run Tips & Edu pipeline: {err}")
                TIPS_EDU_STATE["proc"] = None
        finally:
            unregister_pipeline("tips_edu")

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "moodboard_id": active_moodboard_id,
        "prompt": active_prompt,
        "target": target_category,
        "max_items": max_items,
    })


@tips_edu_bp.route("/status", methods=["GET"])
def get_tips_edu_status():
    """Return live Tips & Edu pipeline execution state and recent stdout logs."""
    with TIPS_EDU_STATE_LOCK:
        elapsed = 0
        if TIPS_EDU_STATE["started_at"]:
            end = TIPS_EDU_STATE["ended_at"] or time.time()
            elapsed = int(end - TIPS_EDU_STATE["started_at"])

        return jsonify({
            "status": TIPS_EDU_STATE["status"],
            "active_fixture": TIPS_EDU_STATE["active_fixture"],
            "active_table_id": TIPS_EDU_STATE["active_table_id"],
            "current_phase": TIPS_EDU_STATE["current_phase"],
            "current_phase_index": TIPS_EDU_STATE["current_phase_index"],
            "total_phases": TIPS_EDU_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": TIPS_EDU_STATE["exit_code"],
            "error": TIPS_EDU_STATE["error"],
            "logs": TIPS_EDU_STATE["logs"][-150:],
        })


@tips_edu_bp.route("/stop", methods=["POST"])
def stop_tips_edu_pipeline():
    """Stop/cancel the running Tips & Edu pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with TIPS_EDU_STATE_LOCK:
        proc = TIPS_EDU_STATE.get("proc")
        if not proc or TIPS_EDU_STATE["status"] != "running":
            return jsonify({"status": "not_running", "message": "No active Tips & Edu pipeline to stop"})

        try:
            proc.terminate()
            TIPS_EDU_STATE["status"] = "stopped"
            TIPS_EDU_STATE["logs"].append("[USER] Tips & Edu pipeline execution cancelled by user.")
            unregister_pipeline("tips_edu")
            return jsonify({"status": "stopped"})
        except Exception as err:
            return jsonify({"status": "error", "error": str(err)}), 500
