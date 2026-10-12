"""This Mood Every Night Reel Pipeline API Blueprint (/api/this-mood-every-night-reel/*).

Single Studio card ("This Mood Every Night") on shared table ``tblDa5UOTUTlU1Xxy``.
The card's moodboard + prompt pencils carry 7 night room values:
(Living Room Vista, Kitchen Island, Fireplace Hearth, Kitchen Detail, Dining Room, Open Kitchen, Staircase),
persisted to per-room env keys::

    KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM1..7
    PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM1..7
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Any

from flask import Blueprint, jsonify, request

from .common import (
    MARKETING_DIR,
    extract_clean_error,
    is_authorized,
    register_pipeline,
    save_config_override,
    unregister_pipeline,
)

this_mood_every_night_reel_bp = Blueprint(
    "this_mood_every_night_reel", __name__, url_prefix="/api/this-mood-every-night-reel"
)

FIXTURE_ID = "this-mood-every-night"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_THIS_MOOD_EVERY_NIGHT_REEL"
TABLE_DEFAULT = "tblDa5UOTUTlU1Xxy"

ROOMS: dict[str, dict[str, Any]] = {
    "living-room": {
        "label": "Living Room Vista",
        "slot": 1,
        "moodboard_env": "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM1",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM1",
        "prompt_default": (
            "Generate me a photo of a luxury modern transitional living room at night, "
            "viewed through black steel-framed grid glass partition French doors, cozy white barrel lounge chairs, "
            "modern plaster fireplace with glowing warm flames in the hearth, built-in display shelving with warm recessed "
            "LED backlighting, dark night windows, medium oak hardwood floors, clean open ceiling centered in the room "
            "ready for a luxury chandelier, warm 2700K ambient glow, cinematic moody night interior, photorealistic 8k"
        ),
    },
    "kitchen-island": {
        "label": "Kitchen Island",
        "slot": 2,
        "moodboard_env": "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM2",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM2",
        "prompt_default": (
            "Generate me a photo of a luxury open-concept kitchen and dining room at night, "
            "large Calacatta marble waterfall kitchen island, brushed brass faucet, glass vase with delicate white floral branches, "
            "black steel grid glass divider in background, floor-to-ceiling windows showing pitch black night outside, "
            "clean ceiling space directly above the marble island ready for a statement pendant light, warm soft ambient glow, "
            "editorial interior, photorealistic 8k"
        ),
    },
    "fireplace-hearth": {
        "label": "Fireplace Hearth Wall",
        "slot": 3,
        "moodboard_env": "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM3",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM3",
        "prompt_default": (
            "Generate me a photo of a minimalist modern plaster fireplace mantel at night, "
            "warm roaring fire glowing in the black firebox, slim black flat screen TV mounted above, "
            "built-in arched alcove shelving with warm LED cove backlighting illuminating neutral ceramic vases and books, "
            "tapered candles flickering on the mantel, plush cream armchair in foreground, deep moody evening shadows, "
            "photorealistic 8k, serene luxury home"
        ),
    },
    "kitchen-detail": {
        "label": "Kitchen Island Detail",
        "slot": 4,
        "moodboard_env": "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM4",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM4",
        "prompt_default": (
            "Generate me a close-up macro photo of a luxury kitchen island at night, "
            "polished Calacatta marble countertop, elegant brushed brass gooseneck spring coil faucet, "
            "lit glass candle casting a warm golden flame reflection on marble, ceramic soap bottles on marble tray, "
            "potted indoor olive tree in background, clean overhead space ready for a suspended pendant light glow, "
            "warm 2700K lighting, photorealistic 8k"
        ),
    },
    "dining-room": {
        "label": "Dining Room Vista",
        "slot": 5,
        "moodboard_env": "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM5",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM5",
        "prompt_default": (
            "Generate me a photo of a modern luxury dining room at night viewed through a black steel grid glass partition, "
            "long natural oak dining table with minimalist modern dining chairs, lit pillar candle on table, "
            "tall pleated linen shade floor lamp glowing in the corner, dark exterior night through floor-to-ceiling glass patio doors, "
            "clean ceiling space centered directly above the dining table ready for a modern chandelier, cozy intimate dinner atmosphere, photorealistic 8k"
        ),
    },
    "kitchen-open": {
        "label": "Kitchen & Dining Vista",
        "slot": 6,
        "moodboard_env": "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM6",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM6",
        "prompt_default": (
            "Generate me a wide-angle photo of a modern transitional open-plan kitchen looking across to the dining area at night, "
            "expansive marble countertop with white floral centerpiece vase, dark taupe pleated drapery framing dark night windows, "
            "warm ambient layered lighting from fireplace and cove lights in the background, clean ceiling space centered over the kitchen island "
            "ready for a designer pendant light, warm cozy evening mood, photorealistic 8k"
        ),
    },
    "staircase": {
        "label": "Interior Staircase",
        "slot": 7,
        "moodboard_env": "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM7",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM7",
        "prompt_default": (
            "Generate me a photo looking up a modern architectural interior staircase at night, "
            "dark oak wood stair treads with white risers, clean horizontal black steel safety railing, "
            "smooth off-white plaster stairway wall, pitch black ambient darkness, wall surface along the stairs ready for "
            "square recessed step lights casting warm golden pools of light downward onto each tread, minimalist luxury home at night, photorealistic 8k"
        ),
    },
}

TOTAL_PHASES = 8
PHASE_LABELS: dict[int, str] = {
    1: "Phase 1: Scraping 7 Fresh Night Fixtures",
    2: "Phase 2: Krea Nighttime Room Interiors",
    3: "Phase 3: Claude Sonnet 5 Vision Analysis",
    4: "Phase 4: Claude Sonnet 5 Blend Prompts",
    5: "Phase 5: Fal Nano Banana Pro Blending",
    6: "Phase 6: Motion Clips Generation",
    7: "Phase 7: Background Music",
    8: "Phase 8: FFmpeg Assembly + Title Overlay",
}
_PHASE_RE = re.compile(r"\[PHASE\s+(\d+)\s*/\s*\d+\]", re.IGNORECASE)


def update_phase_from_log(state: dict[str, Any], line: str) -> None:
    match = _PHASE_RE.search(line)
    if not match:
        return
    idx = int(match.group(1))
    if idx in PHASE_LABELS and idx >= int(state.get("current_phase_index") or 0):
        state["current_phase"] = PHASE_LABELS[idx]
        state["current_phase_index"] = idx


def _room_moodboard(room: dict[str, Any]) -> str:
    return os.getenv(room["moodboard_env"], "").strip() or room["moodboard_default"]


def _room_prompt(room: dict[str, Any]) -> str:
    return os.getenv(room["prompt_env"], "").strip() or room["prompt_default"]


def get_room_entries() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": room["label"],
            "moodboard_id": _room_moodboard(room),
            "prompt": _room_prompt(room),
        }
        for key, room in ROOMS.items()
    ]


def get_fixture() -> dict[str, Any]:
    return {
        "id": FIXTURE_ID,
        "name": "This Mood Every Night",
        "table_id": (os.getenv(TABLE_ENV_KEY) or TABLE_DEFAULT).strip(),
        "total": 100,
        "rooms": get_room_entries(),
    }


def _validate_rooms_dict(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    if set(str(k) for k in raw) != set(ROOMS):
        return None
    cleaned: dict[str, str] = {}
    for key in ROOMS:
        val = str(raw.get(key) or "").strip()
        if not val or val.lower() in ("none", "null", "undefined"):
            return None
        cleaned[key] = val
    return cleaned


_EXEC_STATE: dict[str, Any] = {
    "status": "idle",
    "active_fixture": None,
    "active_table_id": None,
    "current_phase": "",
    "current_phase_index": 0,
    "total_phases": TOTAL_PHASES,
    "elapsed_seconds": 0,
    "logs": [],
    "error": None,
    "process": None,
    "start_time": None,
}
_STATE_LOCK = threading.Lock()
_COUNTS_CACHE: dict[str, Any] = {}
_COUNTS_CACHE_TTL = 30.0


@this_mood_every_night_reel_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({"status": "success", "fixtures": [get_fixture()]})


@this_mood_every_night_reel_bp.route("/counts", methods=["GET"])
def get_counts():
    now = time.time()
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1")
    if not force_refresh and "data" in _COUNTS_CACHE:
        if now - _COUNTS_CACHE["time"] < _COUNTS_CACHE_TTL:
            return jsonify({"status": "success", "counts": _COUNTS_CACHE["data"], "cached": True})

    fixture = get_fixture()
    results: dict[str, Any] = {}
    try:
        from content_automation.airtable_client import fetch_status_breakdown

        sc = fetch_status_breakdown(fixture["table_id"])
        results[FIXTURE_ID] = {
            "id": fixture["id"],
            "name": fixture["name"],
            "table_id": fixture["table_id"],
            "completed": sc["C"],
            "total": fixture["total"],
            "rooms": fixture["rooms"],
            "status_counts": sc,
        }
    except Exception:
        pass

    _COUNTS_CACHE["data"] = results
    _COUNTS_CACHE["time"] = now
    return jsonify({"status": "success", "counts": results, "cached": False})


@this_mood_every_night_reel_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    rooms = _validate_rooms_dict(data.get("rooms"))
    if rooms is None:
        return jsonify({
            "status": "error",
            "error": "rooms required: one moodboard ID per room (7 room keys)",
        }), 400
    for key, moodboard_id in rooms.items():
        save_config_override(ROOMS[key]["moodboard_env"], moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "rooms": rooms})


@this_mood_every_night_reel_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    rooms = _validate_rooms_dict(data.get("rooms"))
    if rooms is None:
        return jsonify({
            "status": "error",
            "error": "rooms required: one prompt per room (7 room keys)",
        }), 400
    for key, prompt_text in rooms.items():
        save_config_override(ROOMS[key]["prompt_env"], prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "rooms": rooms})


@this_mood_every_night_reel_bp.route("/status", methods=["GET"])
def get_status():
    with _STATE_LOCK:
        elapsed = int(time.time() - _EXEC_STATE["start_time"]) if _EXEC_STATE.get("start_time") else 0
        return jsonify({
            "status": _EXEC_STATE["status"],
            "active_fixture": _EXEC_STATE["active_fixture"],
            "active_table_id": _EXEC_STATE["active_table_id"],
            "current_phase": _EXEC_STATE["current_phase"],
            "current_phase_index": _EXEC_STATE["current_phase_index"],
            "total_phases": _EXEC_STATE["total_phases"],
            "elapsed_seconds": elapsed,
            "logs": _EXEC_STATE["logs"][-150:],
            "error": _EXEC_STATE["error"],
        })


@this_mood_every_night_reel_bp.route("/run", methods=["POST"])
def run_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    fixture_id = (data.get("fixture_id") or FIXTURE_ID).strip()
    if fixture_id != FIXTURE_ID:
        return jsonify({"status": "error", "error": f"Invalid fixture: {fixture_id}"}), 400
    max_items = min(max(int(data.get("max_items", 1)), 1), 10)
    fixture = get_fixture()

    with _STATE_LOCK:
        if _EXEC_STATE["status"] == "running":
            return jsonify({"status": "error", "error": "This Mood Every Night Reel pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": FIXTURE_ID,
            "active_table_id": fixture["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": TOTAL_PHASES,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering This Mood Every Night Reel ({max_items} row(s), 7-shot tour)..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("this-mood-every-night-reel", "This Mood Every Night Reel")
        cmd = [
            sys.executable,
            "-u",
            "run_this_mood_every_night_reel.py",
            "--table-id", fixture["table_id"],
            "--max-rows", str(max_items),
        ]
        try:
            p = subprocess.Popen(
                cmd,
                cwd=str(MARKETING_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            with _STATE_LOCK:
                _EXEC_STATE["process"] = p
            for line in iter(p.stdout.readline, ""):
                txt = line.strip()
                if not txt:
                    continue
                with _STATE_LOCK:
                    _EXEC_STATE["logs"].append(txt)
                    update_phase_from_log(_EXEC_STATE, txt)
            p.wait()
            with _STATE_LOCK:
                if p.returncode == 0:
                    _EXEC_STATE["status"] = "completed"
                    _EXEC_STATE["current_phase"] = "Completed successfully"
                else:
                    _EXEC_STATE["status"] = "error"
                    _EXEC_STATE["error"] = extract_clean_error(_EXEC_STATE["logs"], p.returncode)
        except Exception as e:
            with _STATE_LOCK:
                _EXEC_STATE["status"] = "error"
                _EXEC_STATE["error"] = str(e)
        finally:
            unregister_pipeline("this-mood-every-night-reel")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fixture["name"]})


@this_mood_every_night_reel_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("this-mood-every-night-reel")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
