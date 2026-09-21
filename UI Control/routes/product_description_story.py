"""Product Closeup w/ Description Story Pipeline API Blueprint (/api/product-description-story/*)."""

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
    unregister_pipeline,
)

product_description_story_bp = Blueprint("product_description_story", __name__, url_prefix="/api/product-description-story")


def get_product_description_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 6 supported Product Description Story fixture tables."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_PRODUCT_DESCRIPTION")
                or "tblDcT6jovdAbKnfw"
            ).strip(),
            "target_flag": "chandelier",
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION")
                or "tblDD2w4v0Idb4jAZ"
            ).strip(),
            "target_flag": "pendant_light",
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_PRODUCT_DESCRIPTION")
                or "tblPvHyKGByWJCMtY"
            ).strip(),
            "target_flag": "floor_lamp",
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION")
                or "tblnIOQVywHcTgAtv"
            ).strip(),
            "target_flag": "cluster_chandelier",
            "total": 100,
        },
        "table-lamp": {
            "id": "table-lamp",
            "name": "Table Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION")
                or "tbl5S9JEHSrjrLwxA"
            ).strip(),
            "target_flag": "table_lamp",
            "total": 100,
        },
        "wall-light": {
            "id": "wall-light",
            "name": "Wall Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION")
                or "tblYqudlgjYMNRROM"
            ).strip(),
            "target_flag": "wall_light",
            "total": 100,
        },
    }


PROD_DESC_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": 2,
    "proc": None,
    "logs": [],
    "started_at": None,
    "ended_at": None,
    "exit_code": None,
    "error": None,
}
PROD_DESC_STATE_LOCK = threading.Lock()

PROD_DESC_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_prod_desc_phase(line: str) -> tuple[str, int] | None:
    """Infer current Product Description Story pipeline phase from stdout line."""
    lower = line.lower()
    if "step 1" in lower or ("scraping" in lower and "akeneo" in lower) or "scrape" in lower:
        return "Phase 1/2: Akeneo Product Scraping & Layout Attachment", 1
    if "step 2" in lower or "nano banana" in lower or "blending" in lower or "generating" in lower:
        return "Phase 2/2: Fal AI Nano Banana Pro 9:16 Description Card Blending", 2
    return None


@product_description_story_bp.route("/counts", methods=["GET"])
def get_product_description_counts():
    """Return live completed counts for all 6 Product Description Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with PROD_DESC_STATE_LOCK:
        if not force_refresh and (now - PROD_DESC_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and PROD_DESC_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": PROD_DESC_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_prod_desc_count(item):
            key, fix = item
            table_id = fix["table_id"]
            url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
            headers = {"Authorization": f"Bearer {token}"}
            params = {
                "filterByFormula": "OR({Status} = 'Posted', {Status} = 'Scheduled', {Status} = 'Schedule', {Status} = 'Complete', {Status} = 'Completed', {Status} = 'Done', {Status} = 'Discard', {Status} = 'Discarded', {Status} = 'For Manual', {Status} = 'For  Manual', {Status} = 'Minor revision', {Status} = 'Minor Revision', {Status} = 'FM')",
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
                        if norm_status == "posted":
                            p_count += 1
                        elif norm_status in ("scheduled", "schedule"):
                            s_count += 1
                        elif norm_status in ("complete", "completed", "done"):
                            c_count += 1
                        elif norm_status in ("discard", "discarded"):
                            d_count += 1
                        elif norm_status in ("for manual", "minor revision", "minor revisions", "fm"):
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

        fixtures = get_product_description_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_prod_desc_count, fixtures.items()):
                results[k] = v

        with PROD_DESC_STATE_LOCK:
            PROD_DESC_COUNTS_CACHE["timestamp"] = now
            PROD_DESC_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@product_description_story_bp.route("/run", methods=["POST"])
def run_product_description_pipeline():
    """Trigger run_full_product_description_story.py for a single fixture table (1 item)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = payload.get("fixture_id", "chandelier")
    max_items = int(payload.get("max_items", 1))

    fixtures = get_product_description_fixtures()
    if fixture_id not in fixtures:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'. Supported: {list(fixtures.keys())}",
        }), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    target_flag = fix["target_flag"]

    with PROD_DESC_STATE_LOCK:
        if PROD_DESC_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "message": f"Product Description pipeline is already running for {PROD_DESC_STATE.get('active_fixture')}",
            }), 409

        PROD_DESC_STATE["status"] = "running"
        PROD_DESC_STATE["active_fixture"] = fixture_id
        PROD_DESC_STATE["active_table_id"] = table_id
        PROD_DESC_STATE["current_phase"] = "Initializing Product Description Story Pipeline..."
        PROD_DESC_STATE["current_phase_index"] = 0
        PROD_DESC_STATE["total_phases"] = 2
        PROD_DESC_STATE["logs"] = []
        PROD_DESC_STATE["started_at"] = time.time()
        PROD_DESC_STATE["ended_at"] = None
        PROD_DESC_STATE["exit_code"] = None
        PROD_DESC_STATE["error"] = None

    register_pipeline("product_description_story", {"fixture": fixture_id, "table_id": table_id})

    def worker():
        script_path = MARKETING_DIR / "run_full_product_description_story.py"
        cmd = [
            sys.executable,
            "-u",
            str(script_path),
            "--target",
            target_flag,
            "--count",
            str(max_items),
        ]

        child_env = os.environ.copy()
        child_env["PYTHONUNBUFFERED"] = "1"
        child_env["MARKETING_AUTOMATION_HEADLESS"] = "1"

        with PROD_DESC_STATE_LOCK:
            PROD_DESC_STATE["logs"].append(f"[INIT] Command: {' '.join(cmd)}")
            PROD_DESC_STATE["logs"].append(f"[CONFIG] Table: {fix['name']} ({table_id})")

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

            with PROD_DESC_STATE_LOCK:
                PROD_DESC_STATE["proc"] = proc

            for line in iter(proc.stdout.readline, ""):
                clean_line = line.rstrip()
                if not clean_line:
                    continue
                with PROD_DESC_STATE_LOCK:
                    PROD_DESC_STATE["logs"].append(clean_line)
                    phase_info = detect_prod_desc_phase(clean_line)
                    if phase_info:
                        label, idx = phase_info
                        PROD_DESC_STATE["current_phase"] = label
                        PROD_DESC_STATE["current_phase_index"] = idx

            proc.stdout.close()
            proc.wait()

            with PROD_DESC_STATE_LOCK:
                PROD_DESC_STATE["proc"] = None
                PROD_DESC_STATE["ended_at"] = time.time()
                PROD_DESC_STATE["exit_code"] = proc.returncode

                if proc.returncode == 0:
                    PROD_DESC_STATE["status"] = "completed"
                    PROD_DESC_STATE["current_phase"] = "Pipeline Finished Successfully"
                    PROD_DESC_STATE["current_phase_index"] = 2
                    PROD_DESC_STATE["logs"].append("[COMPLETE] Product Description Pipeline finished with exit code 0.")
                    PROD_DESC_COUNTS_CACHE["timestamp"] = 0
                else:
                    clean_err = extract_clean_error(PROD_DESC_STATE["logs"], proc.returncode)
                    PROD_DESC_STATE["status"] = "error"
                    PROD_DESC_STATE["error"] = clean_err
                    PROD_DESC_STATE["logs"].append(f"[ERROR] {clean_err}")
        except Exception as err:
            with PROD_DESC_STATE_LOCK:
                PROD_DESC_STATE["status"] = "error"
                PROD_DESC_STATE["error"] = str(err)
                PROD_DESC_STATE["logs"].append(f"[EXCEPTION] Failed to run pipeline: {err}")
                PROD_DESC_STATE["proc"] = None
        finally:
            unregister_pipeline("product_description_story")

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "max_items": max_items,
    })


@product_description_story_bp.route("/status", methods=["GET"])
def get_product_description_status():
    """Return live pipeline execution state and recent stdout logs."""
    with PROD_DESC_STATE_LOCK:
        elapsed = 0
        if PROD_DESC_STATE["started_at"]:
            end = PROD_DESC_STATE["ended_at"] or time.time()
            elapsed = int(end - PROD_DESC_STATE["started_at"])

        return jsonify({
            "status": PROD_DESC_STATE["status"],
            "active_fixture": PROD_DESC_STATE["active_fixture"],
            "active_table_id": PROD_DESC_STATE["active_table_id"],
            "current_phase": PROD_DESC_STATE["current_phase"],
            "current_phase_index": PROD_DESC_STATE["current_phase_index"],
            "total_phases": PROD_DESC_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": PROD_DESC_STATE["exit_code"],
            "error": PROD_DESC_STATE["error"],
            "logs": PROD_DESC_STATE["logs"][-150:],
        })


@product_description_story_bp.route("/stop", methods=["POST"])
def stop_product_description_pipeline():
    """Stop/cancel the running pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with PROD_DESC_STATE_LOCK:
        proc = PROD_DESC_STATE.get("proc")
        if not proc or PROD_DESC_STATE["status"] != "running":
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            PROD_DESC_STATE["status"] = "stopped"
            PROD_DESC_STATE["logs"].append("[USER] Pipeline execution cancelled by user.")
            unregister_pipeline("product_description_story")
            return jsonify({"status": "stopped"})
        except Exception as err:
            return jsonify({"status": "error", "error": str(err)}), 500
