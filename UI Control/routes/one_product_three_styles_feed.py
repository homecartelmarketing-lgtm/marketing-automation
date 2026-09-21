"""1 Product 3 Styles Feed Pipeline API Blueprint (/api/one-product-3-styles/*)."""

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

one_product_three_styles_bp = Blueprint(
    "one_product_three_styles_feed", __name__, url_prefix="/api/one-product-3-styles"
)

ONE_PRODUCT_THREE_STYLES_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_1_PRODUCT_3_STYLES",
        "fallback_env": "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        "default": "2a4a62bf-c6eb-49f8-8808-2543200634a0",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS_1_PRODUCT_3_STYLES",
        "fallback_env": "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        "default": "b1641228-beec-4823-8d01-1de3eec8410d",
    },
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIER_1_PRODUCT_3_STYLES",
        "fallback_env": "KREA_MOODBOARD_ID_CHANDELIERS",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
}


ONE_PRODUCT_THREE_STYLES_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "pendant": {
        "env_key": "ONE_PRODUCT_3_STYLES_PROMPT_PENDANT",
        "fallback_env": "KREA_PROMPT_PENDANT_LIGHTS_1_PRODUCT_3_STYLES",
        "default": "Generate me a luxury modern dining room with hanging pendant light",
    },
    "floor-lamp": {
        "env_key": "ONE_PRODUCT_3_STYLES_PROMPT_FLOOR_LAMP",
        "fallback_env": "KREA_PROMPT_FLOOR_LAMPS_1_PRODUCT_3_STYLES",
        "default": "Generate me a luxury modern living room lounge with standing floor lamp",
    },
    "chandelier": {
        "env_key": "ONE_PRODUCT_3_STYLES_PROMPT_CHANDELIER",
        "fallback_env": "KREA_PROMPT_CHANDELIER_1_PRODUCT_3_STYLES",
        "default": "Generate me a luxury modern grand living room with hanging chandelier",
    },
}


def resolve_moodboard_id(fixture_id: str) -> str:
    """Resolve active Krea Moodboard ID from .env or preset fallback."""
    cfg = ONE_PRODUCT_THREE_STYLES_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    fallback_env = cfg.get("fallback_env")
    default = cfg.get("default", "")

    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    if fallback_env:
        val = os.getenv(fallback_env, "").strip()
        if val:
            return val
    return default


def resolve_prompt(fixture_id: str) -> str:
    """Resolve active Krea Room Style 1 prompt from .env or preset fallback."""
    cfg = ONE_PRODUCT_THREE_STYLES_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    fallback_env = cfg.get("fallback_env")
    default = cfg.get("default", "")

    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    if fallback_env:
        val = os.getenv(fallback_env, "").strip()
        if val:
            return val
    return default


def get_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 3 supported 1 Product 3 Styles Feed fixture tables."""
    return {
        "pendant": {
            "id": "pendant",
            "name": "Pendant Lights",
            "cli_target": "pendant_lights",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_1_PRODUCT_3_STYLES")
                or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_ONE_PRODUCT_THREE_STYLES")
                or "tblRy52kCasisCWzd"
            ).strip(),
            "category_code": "pendant_lights_one_product_three_styles",
            "moodboard_id": resolve_moodboard_id("pendant"),
            "prompt": resolve_prompt("pendant"),
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "cli_target": "floor_lamps",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_1_PRODUCT_3_STYLES")
                or os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_ONE_PRODUCT_THREE_STYLES")
                or "tbl9GIq2QeYCwMhWU"
            ).strip(),
            "category_code": "floor_lamps_one_product_three_styles",
            "moodboard_id": resolve_moodboard_id("floor-lamp"),
            "prompt": resolve_prompt("floor-lamp"),
            "total": 100,
        },
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "cli_target": "chandeliers",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_1_PRODUCT_3_STYLES")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_ONE_PRODUCT_THREE_STYLES")
                or "tblrlfqBGe5EjS5PI"
            ).strip(),
            "category_code": "chandeliers_one_product_three_styles",
            "moodboard_id": resolve_moodboard_id("chandelier"),
            "prompt": resolve_prompt("chandelier"),
            "total": 100,
        },
    }


# In-memory execution state
STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": 4,
    "logs": [],
    "started_at": None,
    "ended_at": None,
    "exit_code": None,
    "error": None,
    "process": None,
}

STATE_LOCK = threading.Lock()

# Counts cache
COUNTS_CACHE: dict[str, Any] = {
    "data": {},
    "timestamp": 0,
}
COUNTS_CACHE_TTL = 30  # seconds


@one_product_three_styles_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    """Return configured 1 Product 3 Styles Feed fixtures."""
    return jsonify({
        "status": "success",
        "fixtures": list(get_fixtures().values()),
    })


@one_product_three_styles_bp.route("/counts", methods=["GET"])
def get_live_counts():
    """Fetch live record counts and P, C, D, FM status breakdown from Airtable."""
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1", "yes")
    now = time.time()

    with STATE_LOCK:
        if (
            not force_refresh
            and COUNTS_CACHE["data"]
            and (now - COUNTS_CACHE["timestamp"] < COUNTS_CACHE_TTL)
        ):
            return jsonify({
                "status": "success",
                "counts": COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        settings = load_settings(MARKETING_DIR / ".env") if MARKETING_DIR else load_settings()
        token = (
            (getattr(settings, "airtable_token", None) if settings else None)
            or os.getenv("AIRTABLE_TOKEN")
            or os.getenv("AIRTABLE_API_KEY")
        )
        base_id = (
            (getattr(settings, "airtable_base_id", None) if settings else None)
            or os.getenv("AIRTABLE_BASE_ID")
        )

        if not token or not base_id:
            return jsonify({
                "status": "error",
                "error": "Missing AIRTABLE_TOKEN or AIRTABLE_BASE_ID in .env",
            }), 500

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        results: dict[str, Any] = {}

        def fetch_fixture_count(item: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
            key, fix = item
            table_id = fix["table_id"]
            url = f"https://api.airtable.com/v0/{base_id}/{table_id}"

            p_count = 0
            s_count = 0
            c_count = 0
            d_count = 0
            fm_count = 0

            offset = None
            params: dict[str, Any] = {
                "pageSize": 100,
            }

            for _ in range(20):  # Cap pagination at 2000 records
                if offset:
                    params["offset"] = offset
                try:
                    resp = requests.get(url, headers=headers, params=params, timeout=20)
                    if not resp.ok:
                        break
                    body = resp.json()
                    records = body.get("records", [])
                    for rec in records:
                        fields = rec.get("fields", {})
                        raw_status = str(fields.get("Status") or "").strip()
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
                        else:
                            # Fallback check for completed blended image attachments
                            blended_att = (
                                fields.get("1 Product 3 Style Blended")
                                or fields.get("Blended Image")
                                or []
                            )
                            if isinstance(blended_att, list) and len(blended_att) >= 3:
                                c_count += 1

                    offset = body.get("offset")
                    if not offset:
                        break
                except Exception:
                    break

            return key, {
                "id": fix["id"],
                "name": fix["name"],
                "table_id": table_id,
                "moodboard_id": fix.get("moodboard_id") or resolve_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_prompt(key),
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

        fixtures = get_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_fixture_count, fixtures.items()):
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


@one_product_three_styles_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    """Update and persist Krea Moodboard ID in .env for a 1 Product 3 Styles Feed fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in ONE_PRODUCT_THREE_STYLES_MOODBOARD_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_moodboard_id:
        return jsonify({
            "status": "error",
            "error": "Moodboard ID cannot be empty",
        }), 400

    cfg = ONE_PRODUCT_THREE_STYLES_MOODBOARD_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    fallback_env = cfg.get("fallback_env")
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_moodboard_id)
        if fallback_env:
            save_config_override(fallback_env, new_moodboard_id)

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


@one_product_three_styles_bp.route("/prompt", methods=["POST"])
def update_prompt():
    """Update and persist Krea Room Style 1 prompt in .env for a 1 Product 3 Styles Feed fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in ONE_PRODUCT_THREE_STYLES_PROMPT_CONFIG:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'",
        }), 400

    if not new_prompt:
        return jsonify({
            "status": "error",
            "error": "Prompt cannot be empty",
        }), 400

    cfg = ONE_PRODUCT_THREE_STYLES_PROMPT_CONFIG[fixture_id]
    env_key = cfg["env_key"]
    fallback_env = cfg.get("fallback_env")
    env_file = MARKETING_DIR / ".env"

    try:
        save_config_override(env_key, new_prompt)
        if fallback_env:
            save_config_override(fallback_env, new_prompt)

        with STATE_LOCK:
            COUNTS_CACHE["timestamp"] = 0

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


@one_product_three_styles_bp.route("/run", methods=["POST"])
def run_pipeline():
    """Trigger run_1_product_3_styles_feed.py with --scrape-first for a single fixture table."""
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

    fixtures = get_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    active_moodboard_id = custom_moodboard_id or fix.get("moodboard_id") or resolve_moodboard_id(fixture_id)
    active_prompt = custom_prompt or fix.get("prompt") or resolve_prompt(fixture_id)

    # Persist overridden moodboard_id to overrides/env if explicitly provided and changed
    if custom_moodboard_id and custom_moodboard_id != fix.get("moodboard_id"):
        cfg = ONE_PRODUCT_THREE_STYLES_MOODBOARD_CONFIG.get(fixture_id, {})
        env_key = cfg.get("env_key")
        fallback_env = cfg.get("fallback_env")
        if env_key:
            try:
                save_config_override(env_key, custom_moodboard_id)
                if fallback_env:
                    save_config_override(fallback_env, custom_moodboard_id)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist moodboard_id: {e}")

    # Persist overridden prompt to overrides/env if explicitly provided and changed
    if custom_prompt and custom_prompt != fix.get("prompt"):
        p_cfg = ONE_PRODUCT_THREE_STYLES_PROMPT_CONFIG.get(fixture_id, {})
        p_env_key = p_cfg.get("env_key")
        p_fallback_env = p_cfg.get("fallback_env")
        if p_env_key:
            try:
                save_config_override(p_env_key, custom_prompt)
                if p_fallback_env:
                    save_config_override(p_fallback_env, custom_prompt)
            except Exception as e:
                print(f"[WARN] Failed to auto-persist prompt: {e}")

    # Check global concurrency across all pipelines
    running, other_desc = is_any_pipeline_running(exclude="one-product-3-styles")
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
                "message": f"1 Product 3 Styles Feed pipeline is already running for {STATE['active_fixture']}",
            }), 409

        STATE["status"] = "running"
        STATE["active_fixture"] = fixture_id
        STATE["active_table_id"] = table_id
        STATE["current_phase"] = "Phase 1/4: Initializing Pipeline..."
        STATE["current_phase_index"] = 1
        STATE["logs"] = [f"[START] Triggered 1 Product, 3 Styles Feed for {fix['name']} ({table_id}, {max_items} item, Scrape-First)..."]
        STATE["started_at"] = time.time()
        STATE["ended_at"] = None
        STATE["exit_code"] = None
        STATE["error"] = None

    register_pipeline("one-product-3-styles", f"1 Product 3 Styles Feed - {fix['name']}")

    def worker():
        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / "run_1_product_3_styles_feed.py"),
            "--target",
            fix["cli_target"],
            "--table-id",
            table_id,
            "--max-rows",
            str(max_items),
            "--moodboard-id",
            active_moodboard_id,
            "--prompt",
            active_prompt,
            "--scrape-first",
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
                STATE["process"] = proc

            for line in iter(proc.stdout.readline, ""):
                line_clean = line.rstrip()
                if not line_clean:
                    continue

                with STATE_LOCK:
                    STATE["logs"].append(line_clean)
                    if len(STATE["logs"]) > 200:
                        STATE["logs"] = STATE["logs"][-200:]

                    # Update phase progress
                    if "Starting Phase 1/4" in line_clean or "Starting Phase 1:" in line_clean:
                        STATE["current_phase"] = "Phase 1/4: Akeneo Scrape (Shopify Deduplication)"
                        STATE["current_phase_index"] = 1
                    elif "Starting Phase 2/4" in line_clean or "Phase 2/4:" in line_clean:
                        STATE["current_phase"] = "Phase 2/4: Krea AI 3 Room Interiors"
                        STATE["current_phase_index"] = 2
                    elif "Starting Phase 3/4" in line_clean or "Phase 3/4:" in line_clean:
                        STATE["current_phase"] = "Phase 3/4: Fal Claude Prompt Analysis"
                        STATE["current_phase_index"] = 3
                    elif "Starting Phase 4/4" in line_clean or "Phase 4/4:" in line_clean:
                        STATE["current_phase"] = "Phase 4/4: Nano Banana Pro Blending + Logo"
                        STATE["current_phase_index"] = 4
                    elif "100% COMPLETE" in line_clean:
                        STATE["current_phase"] = "Complete"
                        STATE["current_phase_index"] = 4

            proc.wait()
            with STATE_LOCK:
                STATE["exit_code"] = proc.returncode
                STATE["ended_at"] = time.time()
                STATE["process"] = None
                if proc.returncode == 0:
                    STATE["status"] = "completed"
                    STATE["current_phase"] = "Complete"
                    STATE["current_phase_index"] = 4
                    STATE["logs"].append("[DONE] Pipeline execution completed successfully.")
                else:
                    STATE["status"] = "error"
                    STATE["error"] = extract_clean_error(STATE["logs"], default_code=proc.returncode, default="Pipeline exited with error.")
                    STATE["logs"].append(f"[ERROR] Process exited with code {proc.returncode}")
        except Exception as err:
            with STATE_LOCK:
                STATE["status"] = "error"
                STATE["error"] = str(err)
                STATE["ended_at"] = time.time()
                STATE["process"] = None
                STATE["logs"].append(f"[EXCEPTION] {err}")
        finally:
            unregister_pipeline("one-product-3-styles")
            with STATE_LOCK:
                COUNTS_CACHE["timestamp"] = 0

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    return jsonify({
        "status": "started",
        "message": f"Started 1 Product 3 Styles Feed pipeline for {fix['name']}",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "moodboard_id": active_moodboard_id,
    })


@one_product_three_styles_bp.route("/status", methods=["GET"])
def get_pipeline_status():
    """Return current execution status and recent logs."""
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
            "logs": STATE["logs"][-60:],
            "error": STATE["error"],
            "exit_code": STATE["exit_code"],
        })


@one_product_three_styles_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    """Gracefully terminate running pipeline process."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with STATE_LOCK:
        proc = STATE.get("process")
        if not proc or STATE["status"] != "running":
            return jsonify({
                "status": "not_running",
                "message": "No active pipeline to stop",
            })

        try:
            proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
                proc.kill()
            STATE["status"] = "stopped"
            STATE["ended_at"] = time.time()
            STATE["process"] = None
            STATE["logs"].append("[STOPPED] Process terminated by user.")
        except Exception as e:
            return jsonify({"status": "error", "error": f"Failed to kill process: {e}"}), 500

    unregister_pipeline("one-product-3-styles")
    return jsonify({
        "status": "stopped",
        "message": "Pipeline stopped successfully",
    })
