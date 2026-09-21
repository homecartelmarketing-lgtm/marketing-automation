"""This or That Story Pipeline API Blueprint (/api/this-or-that/*)."""

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

this_or_that_story_bp = Blueprint("this_or_that_story", __name__, url_prefix="/api/this-or-that")


def get_this_or_that_fixtures() -> dict[str, dict[str, Any]]:
    """Return the 6 supported This or That Story fixture tables."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_THIS_OR_THAT")
                or "tblo42IkuhYLIQBzk"
            ).strip(),
            "target_flag": "chandeliers",
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_THIS_OR_THAT")
                or "tblS1VHp41RDfxztD"
            ).strip(),
            "target_flag": "pendant_lights",
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Floor Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_THIS_OR_THAT")
                or "tblaoqj8VPVHFmVQn"
            ).strip(),
            "target_flag": "floor_lamps",
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_THIS_OR_THAT")
                or "tblYAhjKckXtjUayx"
            ).strip(),
            "target_flag": "cluster_chandeliers",
            "total": 100,
        },
        "table-lamp": {
            "id": "table-lamp",
            "name": "Table Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMPS_THIS_OR_THAT")
                or "tblm1Ty2QkAlUcHJt"
            ).strip(),
            "target_flag": "table_lamps",
            "total": 100,
        },
        "wall-light": {
            "id": "wall-light",
            "name": "Wall Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT")
                or "tblZw6jvSa27oZDiN"
            ).strip(),
            "target_flag": "wall_lights",
            "total": 100,
        },
    }


THIS_OR_THAT_STATE: dict[str, Any] = {
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
THIS_OR_THAT_STATE_LOCK = threading.Lock()

THIS_OR_THAT_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_this_or_that_phase(line: str) -> tuple[str, int] | None:
    """Infer current This or That Story pipeline phase from stdout line."""
    lower = line.lower()
    if "phase 1" in lower or ("scraping" in lower and "akeneo" in lower) or "scrape" in lower:
        return "Phase 1/2: Akeneo 2-Item Product Scraping & Layout Attachment", 1
    if "phase 2" in lower or "generating this or that" in lower or "nano banana" in lower or "blending" in lower:
        return "Phase 2/2: Fal AI Nano Banana Pro 9:16 Story Comparison Generation", 2
    return None


@this_or_that_story_bp.route("/counts", methods=["GET"])
def get_this_or_that_counts():
    """Return live completed counts for all 6 This or That Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with THIS_OR_THAT_STATE_LOCK:
        if not force_refresh and (now - THIS_OR_THAT_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and THIS_OR_THAT_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": THIS_OR_THAT_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_tot_count(item):
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

        fixtures = get_this_or_that_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_tot_count, fixtures.items()):
                results[k] = v

        with THIS_OR_THAT_STATE_LOCK:
            THIS_OR_THAT_COUNTS_CACHE["timestamp"] = now
            THIS_OR_THAT_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@this_or_that_story_bp.route("/run", methods=["POST"])
def run_this_or_that_pipeline():
    """Trigger generate_this_or_that_pipeline.py for a single fixture table (1 row = 2 items)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = payload.get("fixture_id", "chandelier")
    max_items = int(payload.get("max_items", 1))

    fixtures = get_this_or_that_fixtures()
    if fixture_id not in fixtures:
        return jsonify({
            "status": "error",
            "error": f"Unknown fixture '{fixture_id}'. Supported: {list(fixtures.keys())}",
        }), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]
    target_flag = fix["target_flag"]

    with THIS_OR_THAT_STATE_LOCK:
        if THIS_OR_THAT_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "message": f"This or That pipeline is already running for {THIS_OR_THAT_STATE.get('active_fixture')}",
            }), 409

        THIS_OR_THAT_STATE["status"] = "running"
        THIS_OR_THAT_STATE["active_fixture"] = fixture_id
        THIS_OR_THAT_STATE["active_table_id"] = table_id
        THIS_OR_THAT_STATE["current_phase"] = "Initializing This or That Story Pipeline..."
        THIS_OR_THAT_STATE["current_phase_index"] = 0
        THIS_OR_THAT_STATE["total_phases"] = 2
        THIS_OR_THAT_STATE["logs"] = []
        THIS_OR_THAT_STATE["started_at"] = time.time()
        THIS_OR_THAT_STATE["ended_at"] = None
        THIS_OR_THAT_STATE["exit_code"] = None
        THIS_OR_THAT_STATE["error"] = None

    register_pipeline("this_or_that_story", {"fixture": fixture_id, "table_id": table_id})

    def worker():
        script_path = MARKETING_DIR / "generate_this_or_that_pipeline.py"
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

        with THIS_OR_THAT_STATE_LOCK:
            THIS_OR_THAT_STATE["logs"].append(f"[INIT] Command: {' '.join(cmd)}")
            THIS_OR_THAT_STATE["logs"].append(f"[CONFIG] Table: {fix['name']} ({table_id})")

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

            with THIS_OR_THAT_STATE_LOCK:
                THIS_OR_THAT_STATE["proc"] = proc

            for line in iter(proc.stdout.readline, ""):
                clean_line = line.rstrip()
                if not clean_line:
                    continue
                with THIS_OR_THAT_STATE_LOCK:
                    THIS_OR_THAT_STATE["logs"].append(clean_line)
                    phase_info = detect_this_or_that_phase(clean_line)
                    if phase_info:
                        label, idx = phase_info
                        THIS_OR_THAT_STATE["current_phase"] = label
                        THIS_OR_THAT_STATE["current_phase_index"] = idx

            proc.stdout.close()
            proc.wait()

            with THIS_OR_THAT_STATE_LOCK:
                THIS_OR_THAT_STATE["proc"] = None
                THIS_OR_THAT_STATE["ended_at"] = time.time()
                THIS_OR_THAT_STATE["exit_code"] = proc.returncode

                if proc.returncode == 0:
                    THIS_OR_THAT_STATE["status"] = "completed"
                    THIS_OR_THAT_STATE["current_phase"] = "Pipeline Finished Successfully"
                    THIS_OR_THAT_STATE["current_phase_index"] = 2
                    THIS_OR_THAT_STATE["logs"].append("[COMPLETE] This or That Pipeline finished with exit code 0.")
                    THIS_OR_THAT_COUNTS_CACHE["timestamp"] = 0
                else:
                    clean_err = extract_clean_error(THIS_OR_THAT_STATE["logs"], proc.returncode)
                    THIS_OR_THAT_STATE["status"] = "error"
                    THIS_OR_THAT_STATE["error"] = clean_err
                    THIS_OR_THAT_STATE["logs"].append(f"[ERROR] {clean_err}")
        except Exception as err:
            with THIS_OR_THAT_STATE_LOCK:
                THIS_OR_THAT_STATE["status"] = "error"
                THIS_OR_THAT_STATE["error"] = str(err)
                THIS_OR_THAT_STATE["logs"].append(f"[EXCEPTION] Failed to run pipeline: {err}")
                THIS_OR_THAT_STATE["proc"] = None
        finally:
            unregister_pipeline("this_or_that_story")

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "max_items": max_items,
    })


@this_or_that_story_bp.route("/status", methods=["GET"])
def get_this_or_that_status():
    """Return live pipeline execution state and recent stdout logs."""
    with THIS_OR_THAT_STATE_LOCK:
        elapsed = 0
        if THIS_OR_THAT_STATE["started_at"]:
            end = THIS_OR_THAT_STATE["ended_at"] or time.time()
            elapsed = int(end - THIS_OR_THAT_STATE["started_at"])

        return jsonify({
            "status": THIS_OR_THAT_STATE["status"],
            "active_fixture": THIS_OR_THAT_STATE["active_fixture"],
            "active_table_id": THIS_OR_THAT_STATE["active_table_id"],
            "current_phase": THIS_OR_THAT_STATE["current_phase"],
            "current_phase_index": THIS_OR_THAT_STATE["current_phase_index"],
            "total_phases": THIS_OR_THAT_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": THIS_OR_THAT_STATE["exit_code"],
            "error": THIS_OR_THAT_STATE["error"],
            "logs": THIS_OR_THAT_STATE["logs"][-150:],
        })


@this_or_that_story_bp.route("/stop", methods=["POST"])
def stop_this_or_that_pipeline():
    """Stop/cancel the running pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with THIS_OR_THAT_STATE_LOCK:
        proc = THIS_OR_THAT_STATE.get("proc")
        if not proc or THIS_OR_THAT_STATE["status"] != "running":
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            THIS_OR_THAT_STATE["status"] = "stopped"
            THIS_OR_THAT_STATE["logs"].append("[USER] Pipeline execution cancelled by user.")
            unregister_pipeline("this_or_that_story")
            return jsonify({"status": "stopped"})
        except Exception as err:
            return jsonify({"status": "error", "error": str(err)}), 500
