"""Ad Cover Pipeline API Blueprint (/api/ad-cover/*).

Serves the Studio "Ad Covers" tab: a 1:1 (1080x1080) ad cover plus its 9:16
(1080x1920) Story twin, both built locally from a Krea interior + Nano Banana Pro
product blend. Chandelier is the only runnable fixture today; the rest are
scaffolded placeholders that the frontend renders in a disabled "Coming soon" state.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import re
import subprocess
import sys
import threading
import time
from typing import Any

from flask import Blueprint, jsonify, request

from content_automation.airtable_client import fetch_status_breakdown
from content_automation.overlay import (
    AD_COVER_FIXTURE_ASSETS,
    AD_COVER_STORY_ASSETS,
    _resolve_asset_file,
)

from .common import (
    MARKETING_DIR,
    extract_clean_error,
    is_authorized,
    is_any_pipeline_running,
    register_pipeline,
    save_config_override,
    unregister_pipeline,
)

ad_cover_bp = Blueprint("ad_cover", __name__, url_prefix="/api/ad-cover")

AD_COVER_MOODBOARD_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CHANDELIER_AD_COVER",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "floor-lamp": {
        "env_key": "KREA_MOODBOARD_ID_FLOOR_LAMP_AD_COVER",
        "default": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
    },
    "table-lamp": {
        "env_key": "KREA_MOODBOARD_ID_TABLE_LAMP_AD_COVER",
        "default": "fb2487fb-2895-4d2c-9758-805aaf1bac69",
    },
    "cluster-chandelier": {
        "env_key": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_AD_COVER",
        "default": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
    },
    "pendant": {
        "env_key": "KREA_MOODBOARD_ID_PENDANT_AD_COVER",
        "default": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
    },
    "wall-light": {
        "env_key": "KREA_MOODBOARD_ID_WALL_LIGHT_AD_COVER",
        "default": "20c3beaf-0995-44bf-a7a3-ac790fe8f315",
    },
    "new-collection": {
        "env_key": "KREA_MOODBOARD_ID_NEW_COLLECTION_AD_COVER",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "on-sale": {
        "env_key": "KREA_MOODBOARD_ID_ON_SALE_AD_COVER",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
    "on-stock": {
        "env_key": "KREA_MOODBOARD_ID_ON_STOCK_AD_COVER",
        "default": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
    },
}

AD_COVER_PROMPT_CONFIG: dict[str, dict[str, str]] = {
    "chandelier": {
        "env_key": "AD_COVER_PROMPT_CHANDELIER",
        "default": "Generate me a modern living room",
    },
    "floor-lamp": {
        "env_key": "AD_COVER_PROMPT_FLOOR_LAMP",
        "default": "Generate me a modern living room with a standing floor lamp beside a sofa or lounge chair",
    },
    "table-lamp": {
        "env_key": "AD_COVER_PROMPT_TABLE_LAMP",
        "default": "Generate me a modern luxury bedroom bedside table or console with a table lamp",
    },
    "cluster-chandelier": {
        "env_key": "AD_COVER_PROMPT_CLUSTER_CHANDELIER",
        "default": "Generate me a luxury modern room with high ceiling featuring a cluster chandelier",
    },
    "pendant": {
        "env_key": "AD_COVER_PROMPT_PENDANT",
        "default": "Generate me a modern luxury dining room with hanging pendant light",
    },
    "wall-light": {
        "env_key": "AD_COVER_PROMPT_WALL_LIGHT",
        "default": "Generate me a modern luxury living room with wall sconce mounted on the wall",
    },
    "new-collection": {
        "env_key": "AD_COVER_PROMPT_NEW_COLLECTION",
        "default": "Generate me a modern luxury living room",
    },
    "on-sale": {
        "env_key": "AD_COVER_PROMPT_ON_SALE",
        "default": "Generate me a modern luxury living room with chandelier",
    },
    "on-stock": {
        "env_key": "AD_COVER_PROMPT_ON_STOCK",
        "default": "Generate me a modern interior with ambient lighting",
    },
}

# Scaffolded placeholder list kept for backward compatibility (all 6 are now runnable).
AD_COVER_PLACEHOLDER_FIXTURES: tuple[tuple[str, str], ...] = ()

# Phases 1-5 build the 1:1 ad cover; 6-7 rebuild it as a 9:16 Story.
AD_COVER_TOTAL_PHASES = 7

AD_COVER_PHASE_LABELS: dict[int, str] = {
    1: "Phase 1/7: Akeneo Product Scraping",
    2: "Phase 2/7: Krea AI 1:1 Interior Generation",
    3: "Phase 3/7: Claude Blending Prompt Analysis",
    4: "Phase 4/7: Nano Banana Pro Image Blending",
    5: "Phase 5/7: Local Pillow 1:1 Ad Cover Composite",
    6: "Phase 6/7: Nano Banana Pro 9:16 Story Extension",
    7: "Phase 7/7: Local Pillow 9:16 Story Composite",
}

_AD_COVER_PHASE_RE = re.compile(r"phase\s+(\d+)\s*/\s*\d+")


def resolve_ad_cover_moodboard_id(fixture_id: str) -> str:
    cfg = AD_COVER_MOODBOARD_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return cfg.get("default", "")


def resolve_ad_cover_prompt(fixture_id: str) -> str:
    cfg = AD_COVER_PROMPT_CONFIG.get(fixture_id, {})
    env_key = cfg.get("env_key")
    if env_key:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return cfg.get("default", "")


def resolve_ad_cover_asset(fixture_id: str) -> str:
    if fixture_id == "floor-lamp":
        if _resolve_asset_file("floor-lamp-collection.png") is not None:
            return "floor-lamp-collection.png"
        return AD_COVER_FIXTURE_ASSETS.get("floor-lamp", "trending.png")
    return AD_COVER_FIXTURE_ASSETS.get(fixture_id, "")


def resolve_ad_cover_story_asset(fixture_id: str) -> str:
    candidate = AD_COVER_STORY_ASSETS.get(fixture_id, "")
    if candidate and _resolve_asset_file(candidate) is not None:
        return candidate
    return ""


def get_ad_cover_fixtures() -> dict[str, dict[str, Any]]:
    """The 6 Ad Cover fixtures, all wired to dedicated Airtable tables and runnable."""
    return {
        "chandelier": {
            "id": "chandelier",
            "name": "Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_AD_COVER") or "tblwIsDGZBPuYJV2Z"
            ).strip(),
            "category_code": "chandelier_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("chandelier"),
            "prompt": resolve_ad_cover_prompt("chandelier"),
            "asset": resolve_ad_cover_asset("chandelier"),
            "story_asset": resolve_ad_cover_story_asset("chandelier"),
            "runnable": True,
            "total": 100,
        },
        "floor-lamp": {
            "id": "floor-lamp",
            "name": "Trending Lights",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMP_AD_COVER") or "tbl27FKuDUD4FdJUR"
            ).strip(),
            "category_code": "floor_lamp_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("floor-lamp"),
            "prompt": resolve_ad_cover_prompt("floor-lamp"),
            "asset": resolve_ad_cover_asset("floor-lamp"),
            "story_asset": resolve_ad_cover_story_asset("floor-lamp"),
            "runnable": True,
            "total": 100,
        },
        "table-lamp": {
            "id": "table-lamp",
            "name": "Table Lamp",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMP_AD_COVER") or "tblk3RfFqawHZ5Wrk"
            ).strip(),
            "category_code": "table_lamp_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("table-lamp"),
            "prompt": resolve_ad_cover_prompt("table-lamp"),
            "asset": resolve_ad_cover_asset("table-lamp"),
            "story_asset": resolve_ad_cover_story_asset("table-lamp"),
            "runnable": True,
            "total": 100,
        },
        "cluster-chandelier": {
            "id": "cluster-chandelier",
            "name": "Cluster Chandelier",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_AD_COVER") or "tbltouegkjgQwdr1u"
            ).strip(),
            "category_code": "cluster_chandelier_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("cluster-chandelier"),
            "prompt": resolve_ad_cover_prompt("cluster-chandelier"),
            "asset": resolve_ad_cover_asset("cluster-chandelier"),
            "story_asset": resolve_ad_cover_story_asset("cluster-chandelier"),
            "runnable": True,
            "total": 100,
        },
        "pendant": {
            "id": "pendant",
            "name": "Pendant Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_PENDANT_AD_COVER") or "tbl99Cwda2Xn93giT"
            ).strip(),
            "category_code": "pendant_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("pendant"),
            "prompt": resolve_ad_cover_prompt("pendant"),
            "asset": resolve_ad_cover_asset("pendant"),
            "story_asset": resolve_ad_cover_story_asset("pendant"),
            "runnable": True,
            "total": 100,
        },
        "wall-light": {
            "id": "wall-light",
            "name": "Wall Light",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_WALL_LIGHT_AD_COVER") or "tblUO5nybG9fIkhTT"
            ).strip(),
            "category_code": "wall_light_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("wall-light"),
            "prompt": resolve_ad_cover_prompt("wall-light"),
            "asset": resolve_ad_cover_asset("wall-light"),
            "story_asset": resolve_ad_cover_story_asset("wall-light"),
            "runnable": True,
            "total": 100,
        },
        "new-collection": {
            "id": "new-collection",
            "name": "New Collection",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_NEW_COLLECTION_AD_COVER") or "tbluMexgzcWE1pDZJ"
            ).strip(),
            "category_code": "new_collection_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("new-collection"),
            "prompt": resolve_ad_cover_prompt("new-collection"),
            "asset": resolve_ad_cover_asset("new-collection"),
            "story_asset": resolve_ad_cover_story_asset("new-collection"),
            "runnable": True,
            "total": 100,
        },
        "on-sale": {
            "id": "on-sale",
            "name": "On Sale Designs",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_ON_SALE_AD_COVER") or "tbleQIVBooVazAyk3"
            ).strip(),
            "category_code": "on_sale_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("on-sale"),
            "prompt": resolve_ad_cover_prompt("on-sale"),
            "asset": resolve_ad_cover_asset("on-sale"),
            "story_asset": resolve_ad_cover_story_asset("on-sale"),
            "runnable": True,
            "total": 100,
        },
        "on-stock": {
            "id": "on-stock",
            "name": "On Stock Designs",
            "table_id": (
                os.getenv("AIRTABLE_TABLE_ID_ON_STOCK_AD_COVER") or "tblX7tpTJhfH0UXmm"
            ).strip(),
            "category_code": "on_stock_ad_cover",
            "moodboard_id": resolve_ad_cover_moodboard_id("on-stock"),
            "prompt": resolve_ad_cover_prompt("on-stock"),
            "asset": resolve_ad_cover_asset("on-stock"),
            "story_asset": resolve_ad_cover_story_asset("on-stock"),
            "runnable": True,
            "total": 100,
        },
    }


AD_COVER_FIXTURES = get_ad_cover_fixtures()

STATE: dict[str, Any] = {
    "status": "idle",  # "idle" | "running" | "completed" | "error" | "stopped"
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": AD_COVER_TOTAL_PHASES,
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
    """Infer the current Ad Cover phase from a stdout line.

    The generator prints an explicit ``[Phase N/7]`` marker, so the numeric match
    runs first: since the 9:16 branch also says "Nano Banana", "blending",
    "Pillow" and "compositing", the loose keyword rules alone would keep phases 6
    and 7 pinned to phases 4 and 5.
    """
    lower = line.lower()

    # The startup banner names every asset and must not be read as progress.
    if "ad cover runner" in lower:
        return None

    numeric = _AD_COVER_PHASE_RE.search(lower)
    if numeric:
        number = int(numeric.group(1))
        label = AD_COVER_PHASE_LABELS.get(number)
        if label:
            return label, number

    # Story lines must be claimed before the generic 1:1 keyword rules.
    if "story" in lower:
        if any(
            needle in lower
            for needle in ("converted image story", "composit", "pillow", "complete")
        ):
            return AD_COVER_PHASE_LABELS[7], 7
        return AD_COVER_PHASE_LABELS[6], 6

    if "9:16" in lower and ("nano banana" in lower or "extend" in lower):
        return AD_COVER_PHASE_LABELS[6], 6
    if "converted image" in lower:
        return AD_COVER_PHASE_LABELS[5], 5
    if "scraping" in lower and "akeneo" in lower:
        return AD_COVER_PHASE_LABELS[1], 1
    if "krea" in lower and "interior" in lower:
        return AD_COVER_PHASE_LABELS[2], 2
    if ("claude" in lower and "prompt" in lower) or "blending prompt" in lower:
        return AD_COVER_PHASE_LABELS[3], 3
    if "nano banana" in lower or "blending" in lower or "blended image" in lower:
        return AD_COVER_PHASE_LABELS[4], 4
    if "compositing" in lower or "pillow" in lower:
        return AD_COVER_PHASE_LABELS[5], 5
    return None


@ad_cover_bp.route("/counts", methods=["GET"])
def get_ad_cover_counts():
    """Return live 5-badge status counts for every Ad Cover fixture."""
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")

    with STATE_LOCK:
        if (
            not force_refresh
            and (now - COUNTS_CACHE["timestamp"]) < CACHE_TTL_SECONDS
            and COUNTS_CACHE["data"]
        ):
            return jsonify({
                "status": "success",
                "counts": COUNTS_CACHE["data"],
                "cached": True,
            })

    try:
        fixtures = get_ad_cover_fixtures()
        runnable = {k: v for k, v in fixtures.items() if v.get("runnable") and v.get("table_id")}

        def fetch_count(item):
            key, fix = item
            from content_automation.airtable_client import fetch_status_breakdown
            try:
                breakdown = fetch_status_breakdown(fix["table_id"])
            except Exception:
                breakdown = {}
            return key, {
                "id": fix["id"],
                "name": fix["name"],
                "table_id": fix["table_id"],
                "moodboard_id": fix.get("moodboard_id") or resolve_ad_cover_moodboard_id(key),
                "prompt": fix.get("prompt") or resolve_ad_cover_prompt(key),
                "asset": fix.get("asset", ""),
                "story_asset": fix.get("story_asset", ""),
                "runnable": fix.get("runnable", False),
                "completed": breakdown.get("C", 0),
                "total": fix["total"],
                "status_counts": {
                    "P": breakdown.get("P", 0),
                    "S": breakdown.get("S", 0),
                    "C": breakdown.get("C", 0),
                    "D": breakdown.get("D", 0),
                    "FM": breakdown.get("FM", 0),
                },
            }

        results: dict[str, Any] = {}
        if runnable:
            with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
                for key, value in pool.map(fetch_count, runnable.items()):
                    results[key] = value

        # Placeholders keep the same shape but report no counts so the UI can
        # render them disabled instead of showing a misleading zero.
        for key, fix in fixtures.items():
            if key in results:
                continue
            results[key] = {
                "id": fix["id"],
                "name": fix["name"],
                "table_id": "",
                "moodboard_id": "",
                "prompt": "",
                "asset": "",
                "story_asset": "",
                "runnable": False,
                "completed": None,
                "total": fix["total"],
            }

        with STATE_LOCK:
            COUNTS_CACHE["timestamp"] = now
            COUNTS_CACHE["data"] = results

        return jsonify({"status": "success", "counts": results, "cached": False})
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


@ad_cover_bp.route("/moodboard", methods=["POST"])
def update_ad_cover_moodboard():
    """Persist a Krea Moodboard ID override for an Ad Cover fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_moodboard_id = str(payload.get("moodboard_id", "")).strip()

    if fixture_id not in AD_COVER_MOODBOARD_CONFIG:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400
    if not new_moodboard_id:
        return jsonify({"status": "error", "error": "Moodboard ID cannot be empty"}), 400

    try:
        save_config_override(AD_COVER_MOODBOARD_CONFIG[fixture_id]["env_key"], new_moodboard_id)
        with STATE_LOCK:
            COUNTS_CACHE["timestamp"] = 0
        return jsonify({
            "status": "success",
            "fixture_id": fixture_id,
            "moodboard_id": new_moodboard_id,
            "message": f"Successfully updated Moodboard ID for {fixture_id} (Studio setting)",
        })
    except Exception as err:
        return jsonify({"status": "error", "error": f"Failed to update Studio setting: {err}"}), 500


@ad_cover_bp.route("/prompt", methods=["POST"])
def update_ad_cover_prompt():
    """Persist a Krea interior prompt override for an Ad Cover fixture."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "")).strip()
    new_prompt = str(payload.get("prompt", "")).strip()

    if fixture_id not in AD_COVER_PROMPT_CONFIG:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400
    if not new_prompt:
        return jsonify({"status": "error", "error": "Prompt cannot be empty"}), 400

    try:
        save_config_override(AD_COVER_PROMPT_CONFIG[fixture_id]["env_key"], new_prompt)
        with STATE_LOCK:
            COUNTS_CACHE["timestamp"] = 0
        return jsonify({
            "status": "success",
            "fixture_id": fixture_id,
            "prompt": new_prompt,
            "message": f"Successfully updated prompt for {fixture_id} (Studio setting)",
        })
    except Exception as err:
        return jsonify({"status": "error", "error": f"Failed to update Studio setting: {err}"}), 500


@ad_cover_bp.route("/run", methods=["POST"])
def run_ad_cover_pipeline():
    """Spawn generate_ad_cover_pipeline.py for one fixture (1 brand-new row)."""
    if not is_authorized(request):
        return jsonify({
            "status": "error",
            "error": "Unauthorized: Invalid or missing Dashboard PIN",
            "needs_pin": True,
        }), 401

    payload = request.get_json(silent=True) or {}
    fixture_id = str(payload.get("fixture_id", "chandelier")).strip() or "chandelier"
    max_items = int(payload.get("max_items", 1) or 1)
    custom_moodboard_id = str(payload.get("moodboard_id", "")).strip()
    custom_prompt = str(payload.get("prompt", "")).strip()

    fixtures = get_ad_cover_fixtures()
    fix = fixtures.get(fixture_id)
    if fix is None:
        return jsonify({"status": "error", "error": f"Unknown fixture '{fixture_id}'"}), 400
    if not fix.get("runnable") or not fix.get("table_id"):
        return jsonify({
            "status": "error",
            "error": f"Ad Cover '{fix['name']}' is not available yet (coming soon).",
        }), 400

    table_id = fix["table_id"]
    active_moodboard_id = (
        custom_moodboard_id or fix.get("moodboard_id") or resolve_ad_cover_moodboard_id(fixture_id)
    )
    active_prompt = custom_prompt or fix.get("prompt") or resolve_ad_cover_prompt(fixture_id)

    if custom_moodboard_id and custom_moodboard_id != fix.get("moodboard_id"):
        try:
            save_config_override(
                AD_COVER_MOODBOARD_CONFIG[fixture_id]["env_key"], custom_moodboard_id
            )
        except Exception as err:
            print(f"[WARN] Failed to auto-persist moodboard_id: {err}")

    if custom_prompt and custom_prompt != fix.get("prompt"):
        try:
            save_config_override(AD_COVER_PROMPT_CONFIG[fixture_id]["env_key"], custom_prompt)
        except Exception as err:
            print(f"[WARN] Failed to auto-persist prompt: {err}")

    running, other_desc = is_any_pipeline_running(exclude="ad_cover")
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
                "message": f"Ad Cover pipeline is already running for {STATE['active_fixture']}",
            }), 409

        STATE["status"] = "running"
        STATE["active_fixture"] = fixture_id
        STATE["active_table_id"] = table_id
        STATE["current_phase"] = "Phase 1/7: Initializing Pipeline..."
        STATE["current_phase_index"] = 1
        STATE["logs"] = [
            f"[START] Triggered Ad Cover Pipeline for {fix['name']} ({table_id}, {max_items} item)..."
        ]
        STATE["started_at"] = time.time()
        STATE["ended_at"] = None
        STATE["exit_code"] = None
        STATE["error"] = None

    register_pipeline("ad_cover", f"Ad Cover - {fix['name']}")

    def worker():
        cmd = [
            sys.executable,
            "-u",
            str(MARKETING_DIR / "generate_ad_cover_pipeline.py"),
            "--fixture",
            fixture_id,
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
                stdin=subprocess.DEVNULL,
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
                    STATE["current_phase_index"] = AD_COVER_TOTAL_PHASES
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
            unregister_pipeline("ad_cover")

    threading.Thread(target=worker, daemon=True).start()

    return jsonify({
        "status": "started",
        "fixture_id": fixture_id,
        "table_id": table_id,
        "moodboard_id": active_moodboard_id,
        "max_items": max_items,
    })


@ad_cover_bp.route("/status", methods=["GET"])
def get_ad_cover_status():
    """Return live Ad Cover execution state and recent stdout logs."""
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


@ad_cover_bp.route("/stop", methods=["POST"])
def stop_ad_cover_pipeline():
    """Stop/cancel the running Ad Cover pipeline."""
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
            unregister_pipeline("ad_cover")
            return jsonify({"status": "stopped"})
        except Exception as err:
            return jsonify({"status": "error", "error": str(err)}), 500
