"""Day & Night Story Pipeline API Blueprint (/api/day-night-story/*)."""

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

day_night_story_bp = Blueprint("day_night_story", __name__, url_prefix="/api/day-night-story")


DAY_NIGHT_STORY_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIERS_DAY_NIGHT_STORY",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_DAY_NIGHT_STORY",
        "default": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS_DAY_NIGHT_STORY",
        "default": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
    },
    "table-lamp": {
        "env_key": "KREA_MOODBOARD_ID_TABLE_LAMPS_DAY_NIGHT_STORY",
        "default": "257569e1-7be8-4412-a90f-acbc347e4646",
    },
    "cluster-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
}

DAY_NIGHT_STORY_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "DAY_NIGHT_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room",
    },
    "pendant": {
        "env_key": "DAY_NIGHT_PROMPT_PENDANT",
        "default": "Generate me a modern dining room with plain ceiling for hanging pendant light",
    },
    "floor-lamp": {
        "env_key": "DAY_NIGHT_PROMPT_FLOOR_LAMP",
        "default": "Generate me a modern living room with empty floor space for a standing floor lamp",
    },
    "table-lamp": {
        "env_key": "DAY_NIGHT_PROMPT_TABLE_LAMP",
        "default": "Generate me a modern bedroom with a bedside table for a table lamp",
    },
    "cluster-chandelier": {
        "env_key": "DAY_NIGHT_PROMPT_CLUSTER_CHANDELIER",
        "default": "Generate me a luxury modern room with high ceiling for a cluster chandelier",
    },
}


def resolve_day_night_moodboard_id(fixture_id: str) -> str:
    """Resolve active Krea Moodboard ID from .env or preset fallback."""
    cfg = DAY_NIGHT_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    # Fallback to general env vars
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
    elif fixture_id == "table-lamp":
        val = os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS", "").strip()
        if val:
            return val
    elif fixture_id == "cluster-chandelier":
        val = os.getenv("KREA_MOODBOARD_ID_CLUSTER_CHANDELIER", "").strip()
        if val:
            return val
    return default


def resolve_day_night_prompt(fixture_id: str) -> str:
    """Resolve active Krea Prompt from .env or preset fallback."""
    cfg = DAY_NIGHT_STORY_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    default = cfg.get("default", "")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return default


def get_day_night_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 5 supported Day & Night Story fixture tables."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_DAY_NIGHT_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_DAY_NIGHT_STORY")
                or "tblKkCf88UVQ3Yu07"
            ).strip(),
            "category": "chandeliers",
            "moodboard_id": resolve_day_night_moodboard_id("chandelier"),
            "prompt": resolve_day_night_prompt("chandelier"),
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_NIGHT_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHT_DAY_NIGHT_STORY")
                or "tblaNyYZCR7E6TXtv"
            ).strip(),
            "category": "pendant_lights",
            "moodboard_id": resolve_day_night_moodboard_id("pendant"),
            "prompt": resolve_day_night_prompt("pendant"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_DAY_NIGHT_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_DAY_NIGHT_STORY")
                or "tblr1hlsjGcs9QKCy"
            ).strip(),
            "category": "floor_lamps",
            "moodboard_id": resolve_day_night_moodboard_id("floor-lamp"),
            "prompt": resolve_day_night_prompt("floor-lamp"),
            "total": 100,
        },
        "table-lamp": {
            "id": "table-lamp",
            "name": "Table Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMPS_DAY_NIGHT_STORY")
                or os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMP_DAY_NIGHT_STORY")
                or "tblhvM9Saq18YqONB"
            ).strip(),
            "category": "table_lamps",
            "moodboard_id": resolve_day_night_moodboard_id("table-lamp"),
            "prompt": resolve_day_night_prompt("table-lamp"),
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY")
                or "tblgcvB4WFKOpSIQl"
            ).strip(),
            "category": "cluster_chandeliers",
            "moodboard_id": resolve_day_night_moodboard_id("cluster-chandelier"),
            "prompt": resolve_day_night_prompt("cluster-chandelier"),
            "total": 100,
        },
    }


DAY_NIGHT_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": 4,
    "proc": None,
    "logs": [],
    "started_at": None,
    "ended_at": None,
    "exit_code": None,
    "error": None,
}
DAY_NIGHT_STATE_LOCK = threading.Lock()

DAY_NIGHT_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_day_night_phase(line: str) -> tuple[str, int] | None:
    """Infer current Day & Night Story pipeline phase from stdout line."""
    lower = line.lower()
    if "phase 0" in lower or ("scraping" in lower and "akeneo" in lower):
        return "Phase 0/4: Akeneo Product Scraping (Standby)", 0
    if "phase 1" in lower or "krea ai room interior" in lower or ("krea" in lower and "interior" in lower):
        return "Phase 1/4: Krea AI 9:16 Vertical Interior Generation", 1
    if "phase 2" in lower or ("claude" in lower and "prompt" in lower) or "blending prompt" in lower:
        return "Phase 2/4: Claude Sonnet 5 Prompt Analysis", 2
    if "phase 3" in lower or "daytime blending" in lower or "day_photo" in lower:
        return "Phase 3/4: Fal AI Nano Banana Pro Daytime Blending", 3
    if "phase 4" in lower or "night transformation" in lower or "night_photo" in lower:
        return "Phase 4/4: Fal AI Nano Banana Pro Night Transformation & Logo Overlay", 4
    return None


@day_night_story_bp.route("/counts", methods=["GET"])
def get_day_night_counts():
    """Return live completed counts for all 5 Day & Night Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with DAY_NIGHT_STATE_LOCK:
        if not force_refresh and (now - DAY_NIGHT_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and DAY_NIGHT_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": DAY_NIGHT_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_day_night_count(item):
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

            try:
                while True:
                    req_params = dict(params)
                    if offset:
                        req_params["offset"] = offset

                    resp = requests.get(url, headers=headers, params=req_params, timeout=12)
                    if not resp.ok:
                        print(f"[WARN] Airtable count for {key} ({table_id}) failed: HTTP {resp.status_code}")
                        break
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
            except Exception as exc:
                print(f"[ERROR] Exception while fetching Airtable counts for {key} ({table_id}): {exc}")

            return key, {
                "id": fix["id"],
                "name": fix["name"],
                "table_id": table_id,
                "moodboard_id": fix.get("moodboard_id") or resolve_day_night_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_day_night_prompt(key),
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

        fixtures = get_day_night_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_day_night_count, fixtures.items()):
                results[k] = v

        with DAY_NIGHT_STATE_LOCK:
            DAY_NIGHT_COUNTS_CACHE["timestamp"] = now
            DAY_NIGHT_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@day_night_story_bp.route("/moodboard", methods=["POST"])
def update_day_night_moodboard():
    """Update and persist Krea Moodboard ID in .env for a Day & Night Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in DAY_NIGHT_STORY_MOODBOARD_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_moodboard_id:
        return jsonify({
            "status": "error",
            "error": "Moodboard ID cannot be empty",
        }), 400

    cfg = DAY_NIGHT_STORY_MOODBOARD_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_moodboard_id)

        with DAY_NIGHT_STATE_LOCK:
            DAY_NIGHT_COUNTS_CACHE["timestamp"] = 0

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


@day_night_story_bp.route("/prompt", methods=["POST"])
def update_day_night_prompt():
    """Update and persist Krea Interior Generation Prompt in .env for a Day & Night Story fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in DAY_NIGHT_STORY_PROMPT_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_prompt:
        return jsonify({
            "status": "error",
            "error": "Prompt cannot be empty",
        }), 400

    cfg = DAY_NIGHT_STORY_PROMPT_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_prompt)

        with DAY_NIGHT_STATE_LOCK:
            DAY_NIGHT_COUNTS_CACHE["timestamp"] = 0

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


@day_night_story_bp.route("/run", methods=["POST"])
def run_day_night_pipeline():
    """Trigger run_day_night_story.py for a single fixture table (1 item)."""
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

    fixtures = get_day_night_fixtures()
    if fixture_id not in fixtures:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'. Supported: {list(fixtures.keys())}",
        }), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    category_flag = fix["category"]
    active_moodboard_id = custom_moodboard_id or fix.get("moodboard_id") or resolve_day_night_moodboard_id(fixture_id)
    active_prompt = custom_prompt or fix.get("prompt") or resolve_day_night_prompt(fixture_id)

    # Persist overridden moodboard if explicitly provided and changed
    if custom_moodboard_id and custom_moodboard_id != fix.get("moodboard_id"):
        cfg_mb_opt = DAY_NIGHT_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
        env_key_mb = cfg_mb_opt.get("env_key")
        if env_key_mb:
            try:
                save_config_override(env_key_mb, custom_moodboard_id)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist moodboard_id: {e}")

    # Persist overridden prompt if explicitly provided and changed
    if custom_prompt and custom_prompt != fix.get("prompt"):
        cfg_pr_opt = DAY_NIGHT_STORY_PROMPT_CONFIG.get(fixture_id, {})
        env_key_pr = cfg_pr_opt.get("env_key")
        if env_key_pr:
            try:
                save_config_override(env_key_pr, custom_prompt)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist prompt: {e}")

    # Check global concurrency
    running, other_desc = is_any_pipeline_running(exclude="day_night_story")
    if running:
        return jsonify({
            "status": "already_running",
            "message": f"Another pipeline is currently running ({other_desc}). Please wait for it to finish.",
        }), 409

    with DAY_NIGHT_STATE_LOCK:
        if DAY_NIGHT_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "message": f"Day & Night pipeline is already running for {DAY_NIGHT_STATE.get('active_fixture')}",
            }), 409

        DAY_NIGHT_STATE["status"] = "running"
        DAY_NIGHT_STATE["active_fixture"] = fixture_id
        DAY_NIGHT_STATE["active_table_id"] = table_id
        DAY_NIGHT_STATE["current_phase"] = "Initializing Day & Night Story Pipeline..."
        DAY_NIGHT_STATE["current_phase_index"] = 0
        DAY_NIGHT_STATE["total_phases"] = 4
        DAY_NIGHT_STATE["logs"] = [f"[START] Triggered Day & Night Story Pipeline for {fix['name']} ({table_id}, {max_items} item)..."]
        DAY_NIGHT_STATE["started_at"] = time.time()
        DAY_NIGHT_STATE["ended_at"] = None
        DAY_NIGHT_STATE["exit_code"] = None
        DAY_NIGHT_STATE["error"] = None

    register_pipeline("day_night_story", {"fixture": fixture_id, "table_id": table_id})

    def worker():
        try:
            script_path = MARKETING_DIR / "run_day_night_story.py"
            cmd = [
                sys.executable,
                "-u",
                str(script_path),
                "--target",
                category_flag,
                "--table-id",
                table_id,
                "--limit",
                str(max_items),
            ]
            if active_moodboard_id:
                cmd.extend(["--moodboard-id", active_moodboard_id])
            if active_prompt:
                cmd.extend(["--prompt", active_prompt])

            child_env = os.environ.copy()
            child_env["PYTHONUNBUFFERED"] = "1"
            child_env["MARKETING_AUTOMATION_HEADLESS"] = "1"

            # Forward active prompt and moodboard overrides to child execution environment
            cfg_pr = DAY_NIGHT_STORY_PROMPT_CONFIG.get(fixture_id, {})
            if active_prompt:
                if cfg_pr.get("env_key"):
                    child_env[cfg_pr["env_key"]] = active_prompt
                if fixture_id == "pendant":
                    child_env["DAY_NIGHT_STORY_PROMPT_PENDANT_LIGHTS"] = active_prompt
                    child_env["DAY_NIGHT_PROMPT_PENDANT_LIGHTS"] = active_prompt
                elif fixture_id == "table-lamp":
                    child_env["DAY_NIGHT_STORY_PROMPT_TABLE_LAMPS"] = active_prompt
                    child_env["DAY_NIGHT_PROMPT_TABLE_LAMPS"] = active_prompt
                elif fixture_id == "floor-lamp":
                    child_env["DAY_NIGHT_STORY_PROMPT_FLOOR_LAMPS"] = active_prompt
                    child_env["DAY_NIGHT_PROMPT_FLOOR_LAMPS"] = active_prompt
                elif fixture_id == "cluster-chandelier":
                    child_env["DAY_NIGHT_STORY_PROMPT_CLUSTER_CHANDELIER"] = active_prompt
                    child_env["DAY_NIGHT_PROMPT_CLUSTER_CHANDELIER"] = active_prompt
                elif fixture_id == "chandelier":
                    child_env["DAY_NIGHT_STORY_PROMPT_CHANDELIER"] = active_prompt
                    child_env["DAY_NIGHT_PROMPT_CHANDELIER"] = active_prompt

            cfg_mb = DAY_NIGHT_STORY_MOODBOARD_CONFIG.get(fixture_id, {})
            if active_moodboard_id:
                if cfg_mb.get("env_key"):
                    child_env[cfg_mb["env_key"]] = active_moodboard_id
                if fixture_id == "chandelier":
                    child_env["KREA_MOODBOARD_ID_CHANDELIERS"] = active_moodboard_id
                elif fixture_id == "pendant":
                    child_env["KREA_MOODBOARD_ID_PENDANT_LIGHTS"] = active_moodboard_id
                elif fixture_id == "floor-lamp":
                    child_env["KREA_MOODBOARD_ID_FLOOR_LAMPS"] = active_moodboard_id
                elif fixture_id == "table-lamp":
                    child_env["KREA_MOODBOARD_ID_TABLE_LAMPS"] = active_moodboard_id
                elif fixture_id == "cluster-chandelier":
                    child_env["KREA_MOODBOARD_ID_CLUSTER_CHANDELIER"] = active_moodboard_id

            table_env_key = {
                "chandelier": "AIRTABLE_TABLE_ID_CHANDELIER_DAY_NIGHT_STORY",
                "pendant": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_NIGHT_STORY",
                "floor-lamp": "AIRTABLE_TABLE_ID_FLOOR_LAMPS_DAY_NIGHT_STORY",
                "table-lamp": "AIRTABLE_TABLE_ID_TABLE_LAMPS_DAY_NIGHT_STORY",
                "cluster-chandelier": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY",
            }.get(fixture_id)
            if table_env_key:
                child_env[table_env_key] = table_id

            with DAY_NIGHT_STATE_LOCK:
                DAY_NIGHT_STATE["logs"].append(f"[INIT] Command: {' '.join(cmd)}")
                DAY_NIGHT_STATE["logs"].append(f"[CONFIG] Table: {fix['name']} ({table_id})")
                DAY_NIGHT_STATE["logs"].append(f"[CONFIG] Moodboard ID: {active_moodboard_id}")
                if active_prompt:
                    DAY_NIGHT_STATE["logs"].append(f"[CONFIG] Prompt: {active_prompt}")

            proc = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            with DAY_NIGHT_STATE_LOCK:
                DAY_NIGHT_STATE["proc"] = proc

            for line in iter(proc.stdout.readline, ""):
                clean_line = line.rstrip()
                if not clean_line:
                    continue
                with DAY_NIGHT_STATE_LOCK:
                    DAY_NIGHT_STATE["logs"].append(clean_line)
                    if len(DAY_NIGHT_STATE["logs"]) > 1000:
                        DAY_NIGHT_STATE["logs"].pop(0)
                    phase_info = detect_day_night_phase(clean_line)
                    if phase_info:
                        label, idx = phase_info
                        DAY_NIGHT_STATE["current_phase"] = label
                        DAY_NIGHT_STATE["current_phase_index"] = idx

            proc.stdout.close()
            proc.wait()

            with DAY_NIGHT_STATE_LOCK:
                DAY_NIGHT_STATE["ended_at"] = time.time()
                DAY_NIGHT_STATE["exit_code"] = proc.returncode

                if proc.returncode == 0:
                    DAY_NIGHT_STATE["status"] = "completed"
                    DAY_NIGHT_STATE["current_phase"] = "Pipeline Finished Successfully"
                    DAY_NIGHT_STATE["current_phase_index"] = 4
                    DAY_NIGHT_STATE["logs"].append("[COMPLETE] Day & Night Pipeline finished with exit code 0.")
                    DAY_NIGHT_COUNTS_CACHE["timestamp"] = 0
                else:
                    clean_err = extract_clean_error(DAY_NIGHT_STATE["logs"], proc.returncode)
                    DAY_NIGHT_STATE["status"] = "error"
                    DAY_NIGHT_STATE["error"] = clean_err
                    DAY_NIGHT_STATE["logs"].append(f"[ERROR] {clean_err}")
        except Exception as err:
            with DAY_NIGHT_STATE_LOCK:
                DAY_NIGHT_STATE["status"] = "error"
                DAY_NIGHT_STATE["error"] = str(err)
                DAY_NIGHT_STATE["logs"].append(f"[EXCEPTION] Failed to run pipeline: {err}")
        finally:
            unregister_pipeline("day_night_story")
            with DAY_NIGHT_STATE_LOCK:
                DAY_NIGHT_STATE["proc"] = None

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "moodboard_id": active_moodboard_id,
        "max_items": max_items,
    })


@day_night_story_bp.route("/status", methods=["GET"])
def get_day_night_status():
    """Return live pipeline execution state and recent stdout logs."""
    with DAY_NIGHT_STATE_LOCK:
        elapsed = 0
        if DAY_NIGHT_STATE["started_at"]:
            end = DAY_NIGHT_STATE["ended_at"] or time.time()
            elapsed = int(end - DAY_NIGHT_STATE["started_at"])

        return jsonify({
            "status": DAY_NIGHT_STATE["status"],
            "active_fixture": DAY_NIGHT_STATE["active_fixture"],
            "active_table_id": DAY_NIGHT_STATE["active_table_id"],
            "current_phase": DAY_NIGHT_STATE["current_phase"],
            "current_phase_index": DAY_NIGHT_STATE["current_phase_index"],
            "total_phases": DAY_NIGHT_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": DAY_NIGHT_STATE["exit_code"],
            "error": DAY_NIGHT_STATE["error"],
            "logs": DAY_NIGHT_STATE["logs"][-150:],
        })


@day_night_story_bp.route("/stop", methods=["POST"])
def stop_day_night_pipeline():
    """Stop/cancel the running pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with DAY_NIGHT_STATE_LOCK:
        proc = DAY_NIGHT_STATE.get("proc")
        if not proc or DAY_NIGHT_STATE["status"] != "running":
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            DAY_NIGHT_STATE["status"] = "stopped"
            DAY_NIGHT_STATE["logs"].append("[USER] Pipeline execution cancelled by user.")
            unregister_pipeline("day_night_story")
            return jsonify({"status": "stopped"})
        except Exception as err:
            return jsonify({"status": "error", "error": str(err)}), 500
