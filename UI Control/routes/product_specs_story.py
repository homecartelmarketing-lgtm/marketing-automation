"""Product Closeup w/ Specifications Story Pipeline API Blueprint (/api/product-specs/*)."""

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
    is_authorized,
    is_any_pipeline_running,
    load_settings,
    register_pipeline,
    unregister_pipeline,
)

product_specs_bp = Blueprint("product_specs_story", __name__, url_prefix="/api/product-specs")


def get_product_specs_fixtures() -> dict[str, dict[str, Any]]:
    """Return supported Product Specs fixture tables with table IDs resolved from .env."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_SPECS")
                or os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_PRODUCT_SPECS")
                or "tblEGTB6BodRVDqBV"
            ).strip(),
            "total": 100,
        },
    }


PRODUCT_SPECS_STATE: dict[str, Any] = {
    "status": "idle",  # "idle" | "running" | "completed" | "error" | "stopped"
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
PRODUCT_SPECS_STATE_LOCK = threading.Lock()

PRODUCT_SPECS_COUNTS_CACHE: dict[str, Any] = {
    "timestamp": 0,
    "data": {},
}
CACHE_TTL_SECONDS = 10


def detect_product_specs_phase(line: str) -> tuple[str, int] | None:
    """Infer current Product Specs Story pipeline phase from stdout line."""
    lower = line.lower()
    if "step 1" in lower or ("scraping" in lower and "akeneo" in lower) or "scrape" in lower or "layout" in lower:
        return "Phase 1/2: Akeneo Product Scraping & Specs Layout Attachment", 1
    if "step 2" in lower or "nano banana" in lower or "pcs story" in lower or "blending" in lower or "generating" in lower:
        return "Phase 2/2: Fal AI Nano Banana Pro 9:16 Specs Card Blending & Airtable Upload", 2
    return None


@product_specs_bp.route("/counts", methods=["GET"])
def get_product_specs_counts():
    """Return live completed counts for Product Specs Story tables from Airtable."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with PRODUCT_SPECS_STATE_LOCK:
        if not force_refresh and (now - PRODUCT_SPECS_COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS and PRODUCT_SPECS_COUNTS_CACHE["data"]:
            return jsonify({
                "status": "success",
                "counts": PRODUCT_SPECS_COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        if not load_settings:
            raise RuntimeError("Cannot import load_settings from marketing-automation")

        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        results = {}

        def fetch_specs_count(item):
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

        fixtures = get_product_specs_fixtures()
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            for k, v in pool.map(fetch_specs_count, fixtures.items()):
                results[k] = v

        with PRODUCT_SPECS_STATE_LOCK:
            PRODUCT_SPECS_COUNTS_CACHE["timestamp"] = now
            PRODUCT_SPECS_COUNTS_CACHE["data"] = results

        return jsonify({
            "status": "success",
            "counts": results,
            "cached": False,
        })
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@product_specs_bp.route("/run", methods=["POST"])
def run_product_specs_pipeline():
    """Trigger run_full_product_specs_story.py for a single fixture table (1 item)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = payload.get("fixture_id", "chandelier")
    max_items = int(payload.get("max_items", 1))

    fixtures = get_product_specs_fixtures()
    if fixture_id not in fixtures:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400

    fix = fixtures[fixture_id]
    table_id = fix["table_id"]

    running, other_desc = is_any_pipeline_running(exclude="product-specs")
    if running:
        return jsonify({
            "status": "already_running",
            "message": f"Another pipeline is currently running ({other_desc}). Please wait for it to finish.",
        }), 409

    with PRODUCT_SPECS_STATE_LOCK:
        if PRODUCT_SPECS_STATE["status"] == "running":
            return jsonify({
                "status": "already_running",
                "active_fixture": PRODUCT_SPECS_STATE["active_fixture"],
                "message": f"Product Specs pipeline is already running for {PRODUCT_SPECS_STATE['active_fixture']}",
            }), 409

        PRODUCT_SPECS_STATE["status"] = "running"
        PRODUCT_SPECS_STATE["active_fixture"] = fixture_id
        PRODUCT_SPECS_STATE["active_table_id"] = table_id
        PRODUCT_SPECS_STATE["current_phase"] = "Phase 1/2: Initializing Specs Pipeline..."
        PRODUCT_SPECS_STATE["current_phase_index"] = 1
        PRODUCT_SPECS_STATE["total_phases"] = 2
        PRODUCT_SPECS_STATE["logs"] = [
            f"[START] Triggered Product Closeup Specs Pipeline for {fix['name']} ({table_id}, {max_items} item)..."
        ]
        PRODUCT_SPECS_STATE["started_at"] = time.time()
        PRODUCT_SPECS_STATE["ended_at"] = None
        PRODUCT_SPECS_STATE["exit_code"] = None
        PRODUCT_SPECS_STATE["error"] = None

    register_pipeline("product-specs", f"Product Specs Story - {fix['name']}")

    def worker():
        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / "run_full_product_specs_story.py"),
            "--count",
            str(max_items),
            "--table-id",
            table_id,
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

            with PRODUCT_SPECS_STATE_LOCK:
                PRODUCT_SPECS_STATE["proc"] = proc

            for raw_line in iter(proc.stdout.readline, ""):
                if not raw_line:
                    break
                line = raw_line.rstrip()
                with PRODUCT_SPECS_STATE_LOCK:
                    PRODUCT_SPECS_STATE["logs"].append(line)
                    if len(PRODUCT_SPECS_STATE["logs"]) > 1000:
                        PRODUCT_SPECS_STATE["logs"].pop(0)

                    detected = detect_product_specs_phase(line)
                    if detected:
                        PRODUCT_SPECS_STATE["current_phase"], PRODUCT_SPECS_STATE["current_phase_index"] = detected

            proc.stdout.close()
            proc.wait()
            ret_code = proc.returncode

            with PRODUCT_SPECS_STATE_LOCK:
                PRODUCT_SPECS_STATE["ended_at"] = time.time()
                PRODUCT_SPECS_STATE["exit_code"] = ret_code
                if ret_code == 0:
                    PRODUCT_SPECS_STATE["status"] = "completed"
                    PRODUCT_SPECS_STATE["current_phase"] = "Phase 2/2: Pipeline Completed Successfully"
                    PRODUCT_SPECS_STATE["current_phase_index"] = 2
                    PRODUCT_SPECS_STATE["logs"].append(f"\n[DONE] Pipeline completed successfully for {fix['name']} (Code {ret_code})")
                else:
                    PRODUCT_SPECS_STATE["status"] = "error"
                    PRODUCT_SPECS_STATE["error"] = f"Process exited with non-zero code {ret_code}"
                    PRODUCT_SPECS_STATE["logs"].append(f"\n[ERROR] Pipeline exited with code {ret_code}")

        except Exception as err:
            with PRODUCT_SPECS_STATE_LOCK:
                PRODUCT_SPECS_STATE["status"] = "error"
                PRODUCT_SPECS_STATE["error"] = str(err)
                PRODUCT_SPECS_STATE["logs"].append(f"\n[FATAL] Execution failed: {err}")
        finally:
            unregister_pipeline("product-specs")
            with PRODUCT_SPECS_STATE_LOCK:
                PRODUCT_SPECS_STATE["proc"] = None

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "max_items": max_items,
    })


@product_specs_bp.route("/status", methods=["GET"])
def get_product_specs_status():
    """Return live execution status and logs for Product Specs Story pipeline."""
    with PRODUCT_SPECS_STATE_LOCK:
        elapsed = 0
        if PRODUCT_SPECS_STATE["started_at"]:
            end = PRODUCT_SPECS_STATE["ended_at"] or time.time()
            elapsed = int(end - PRODUCT_SPECS_STATE["started_at"])

        return jsonify({
            "status": PRODUCT_SPECS_STATE["status"],
            "active_fixture": PRODUCT_SPECS_STATE["active_fixture"],
            "active_table_id": PRODUCT_SPECS_STATE["active_table_id"],
            "current_phase": PRODUCT_SPECS_STATE["current_phase"],
            "current_phase_index": PRODUCT_SPECS_STATE["current_phase_index"],
            "total_phases": PRODUCT_SPECS_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "exit_code": PRODUCT_SPECS_STATE["exit_code"],
            "error": PRODUCT_SPECS_STATE["error"],
            "logs": PRODUCT_SPECS_STATE["logs"][-300:],
        })


@product_specs_bp.route("/stop", methods=["POST"])
def stop_product_specs_pipeline():
    """Cancel running Product Specs Story pipeline."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    with PRODUCT_SPECS_STATE_LOCK:
        proc = PRODUCT_SPECS_STATE.get("proc")
        if not proc or proc.poll() is not None:
            return jsonify({"status": "not_running", "message": "No active pipeline to stop"})

        try:
            proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
                proc.kill()
        except Exception as err:
            return jsonify({"status": "error", "error": f"Failed to terminate process: {err}"}), 500

        PRODUCT_SPECS_STATE["status"] = "stopped"
        PRODUCT_SPECS_STATE["ended_at"] = time.time()
        PRODUCT_SPECS_STATE["logs"].append("\n[STOP] Pipeline execution stopped by user request.")
        PRODUCT_SPECS_STATE["proc"] = None

    unregister_pipeline("product-specs")
    return jsonify({"status": "stopped", "message": "Pipeline cancelled successfully"})
