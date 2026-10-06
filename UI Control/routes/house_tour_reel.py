"""House Tour Reel Pipeline API Blueprint (/api/house-tour-reel/*).

Single Studio card ("House Tour") on shared table ``tblqXkdDw4O7hxJS4``.
The card's moodboard + prompt pencils each carry 11 room values
(Living, Bedroom, Dining, Kitchen, Lounge, Hallway, Office, Bathroom,
Entryway, Sunroom, Kids Bedroom), persisted to per-room env keys::

    KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM1..4
    PROMPT_HOUSE_TOUR_REEL_ROOM1..4

A Run from the card processes the FULL 11-room tour into one brand-new row
(rooms cannot run solo) using the saved per-room settings.
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

house_tour_reel_bp = Blueprint(
    "house_tour_reel", __name__, url_prefix="/api/house-tour-reel"
)

FIXTURE_ID = "house-tour"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_HOUSE_TOUR_REEL"
TABLE_DEFAULT = "tblqXkdDw4O7hxJS4"

# room key -> room wiring. Env keys match
# generate_house_tour_reel_pipeline.resolve_slot_settings().
ROOMS: dict[str, dict[str, Any]] = {
    "living-room": {
        "label": "Living Room Corner",
        "slot": 1,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM1",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM1",
        "prompt_default": (
            "An ultra-realistic, cinematic eye-level interior photo of a luxury organic-modern Japandi living room. "
            "Curved cream bouclé three-seater sofa, dark stained solid oak fluted media credenza, smooth off-white "
            "limewash walls, herringbone light oak flooring, textured beige wool rug, travertine side table, tall fiddle leaf fig "
            "in an earthy terracotta planter. Soft warm diffused daylight from sheer linen curtains, serene calm atmosphere, "
            "clean ceiling space ready for a flush-mounted ceiling light or chandelier, architectural digest photography, 8k."
        ),
    },
    "bedroom": {
        "label": "Living Room Seating",
        "slot": 2,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM2",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM2",
        "prompt_default": (
            "An eye-level architectural interior photo of a cozy Japandi living room seating corner. "
            "Low-profile ivory upholstered lounge armchairs, sculpted organic travertine low coffee table, pale microcement walls, "
            "large minimalist abstract canvas in warm stone tones, wide-plank white oak flooring. Warm golden hour ambient light, "
            "spacious uncluttered corner floor area ready for a standing sculptural floor lamp, luxury editorial interior styling, 8k."
        ),
    },
    "dining-room": {
        "label": "Living Room Media Wall",
        "slot": 3,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM3",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM3",
        "prompt_default": (
            "A wide cinematic perspective of an organic-modern living room media wall and lounge. "
            "Horizontal fluted dark walnut credenza beneath a frameless Samsung Frame artwork display, limewash beige plaster backdrop, "
            "sculptural travertine decorative pedestals, warm beige bouclé modular sofa section, natural light filtering through sheer drapes, "
            "empty credenza surface space ready for a ceramic table lamp, high-end Japandi interior design, 8k."
        ),
    },
    "kitchen": {
        "label": "Dining Room Table",
        "slot": 4,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM4",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM4",
        "prompt_default": (
            "An eye-level interior photo of a Japandi dining room centered on an expansive oval solid light oak dining table. "
            "Surrounded by six curved oak dining chairs with woven natural rope seats, warm grey microcement flooring, matte chalk-wash walls, "
            "ceramic footed fruit bowl centerpiece, soft diffused daylight, completely empty ceiling space directly above table ready for an organic-form pendant chandelier, 8k."
        ),
    },
    "lounge": {
        "label": "Dining Room Credenza",
        "slot": 5,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM5",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM5",
        "prompt_default": (
            "A medium architectural shot of an elegant dining room credenza feature wall. "
            "Low-profile fluted dark oak sideboard with honed beige marble top, smooth warm beige limewash plaster wall, "
            "shallow matte ceramic decorative urns, solid oak herringbone floor, soft warm architectural spotlighting, "
            "uncluttered upper wall space ready for mounted linear wall sconces, tranquil wabi-sabi Japandi atmosphere, 8k."
        ),
    },
    "hallway": {
        "label": "Entryway Foyer",
        "slot": 6,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM6",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM6",
        "prompt_default": (
            "A welcoming eye-level photo of a minimalist luxury entryway foyer. "
            "Seamless polished microcement flooring in warm greige, off-white limewash walls, floating curved dark oak console shelf, "
            "large organic asymmetrical wavy brass-framed full-length mirror leaning gracefully, small olive tree in a fluted raw clay vessel, "
            "warm afternoon sunlight with gentle shadows, uncluttered wall space ready for a designer wall sconce, 8k."
        ),
    },
    "office": {
        "label": "Kitchen Island",
        "slot": 7,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM7",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM7",
        "prompt_default": (
            "A cinematic perspective of a luxury open-concept Japandi kitchen. "
            "Two-tone custom cabinetry with warm matte taupe uppers and natural fluted oak base cabinets, honed light travertine countertops "
            "and waterfall island edge, integrated dark bronze cooktop, sculptural beige ceramic vase with dried bunny tails, "
            "soft natural morning daylight, completely clear ceiling zone directly above the island counter ready for multi-fixture pendant lighting, 8k."
        ),
    },
    "bathroom": {
        "label": "Primary Dressing Alcove",
        "slot": 8,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM8",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM8",
        "prompt_default": (
            "A tranquil eye-level perspective of a luxury primary bedroom dressing area and vanity alcove. "
            "Floor-to-ceiling built-in seamless natural white oak wardrobe millwork with integrated warm vertical LED channel glows, "
            "curved ivory bouclé vanity dressing stool, smooth chalk-white plaster alcove wall, plush high-pile beige wool carpet, "
            "open wall area beside the wardrobe ready for a minimalist contemporary wall lamp, serene Japandi ambiance, 8k."
        ),
    },
    "entryway": {
        "label": "Primary Bed Suite",
        "slot": 9,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM9",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM9",
        "prompt_default": (
            "An eye-level architectural interior photo of a serene Japandi primary bedroom suite. "
            "Low platform bed frame in natural bleached oak, layered washed beige linen duvet and waffle-knit oatmeal throw pillows, "
            "fluted vertical oak slat acoustic accent wall paneling behind bed, matching floating oak bedside nightstands, "
            "soft warm morning daylight streaming through floor-to-ceiling sheer curtains, uncluttered bedside tabletop ready for a table lamp, 8k."
        ),
    },
    "sunroom": {
        "label": "Guest Bedroom Bed",
        "slot": 10,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM10",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM10",
        "prompt_default": (
            "A bright eye-level shot of a wabi-sabi Japandi guest bedroom. "
            "Upholstered ivory linen platform bed frame, natural sand-hued stonewashed bedding, warm greige microcement feature wall, "
            "round travertine pedestal bedside nightstand, large leafy potted indoor ficus in rough stone planter, "
            "soft airy natural light, clear open ceiling expanse centered above bed ready for a flush-mounted ceiling light fixture, 8k."
        ),
    },
    "kids-room": {
        "label": "Guest Dresser Corner",
        "slot": 11,
        "moodboard_env": "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM11",
        "moodboard_default": "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt_env": "PROMPT_HOUSE_TOUR_REEL_ROOM11",
        "prompt_default": (
            "A calm architectural vignette of a guest bedroom reading nook and vanity corner. "
            "Low four-drawer horizontal oak dresser chest, large circular backlit minimalist frameless mirror, small organic ceramic dish, "
            "curved ivory bouclé accent armchair, wide-plank blonde oak wood floor with textured neutral runner rug, "
            "spacious ceiling corner space directly above the reading chair ready for a low-hanging accent pendant light, 8k."
        ),
    },
}
TOTAL_PHASES = 8

PHASE_LABELS: dict[int, str] = {
    1: "Phase 1: Krea 11-Room Interior Generation",
    2: "Phase 2: Claude Vision Interior Analysis",
    3: "Phase 3: Akeneo Context-Aware Fixture Scraper",
    4: "Phase 4: Claude Sonnet 5 Blending Prompts",
    5: "Phase 5: Nano Banana Pro Blend + YOLO Poppins Tags",
    6: "Phase 6: Kling 3s Pan Clips",
    7: "Phase 7: ElevenLabs Background Music",
    8: "Phase 8: FFmpeg xfade Assembly + Outro",
}
_PHASE_RE = re.compile(r"\[PHASE\s+(\d+)\s*/\s*\d+\]", re.IGNORECASE)


def update_phase_from_log(state: dict[str, Any], line: str) -> None:
    """Advance the phase from an explicit `[PHASE n/8]` log marker (never moves backwards)."""
    match = _PHASE_RE.search(line)
    if not match:
        return
    idx = int(match.group(1))
    if idx in PHASE_LABELS and idx >= int(state.get("current_phase_index") or 0):
        state["current_phase"] = PHASE_LABELS[idx]
        state["current_phase_index"] = idx


def _room_moodboard(room: dict[str, Any]) -> str:
    return (os.getenv(room["moodboard_env"], "").strip() or room["moodboard_default"])


def _room_prompt(room: dict[str, Any]) -> str:
    return (os.getenv(room["prompt_env"], "").strip() or room["prompt_default"])


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
        "name": "House Tour",
        "table_id": (os.getenv(TABLE_ENV_KEY) or TABLE_DEFAULT).strip(),
        "total": 100,
        "rooms": get_room_entries(),
    }


def _validate_rooms_dict(raw: Any) -> dict[str, str] | None:
    """Validate a {room_key: value} payload; None when invalid.

    Output follows canonical slot order (ROOMS registry) regardless of
    payload key order -- this Flask version's test client serializes JSON
    with sorted keys, and browsers preserve insertion order, so neither can
    be relied on for save order.
    """
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


@house_tour_reel_bp.route("/fixtures", methods=["GET"])
def list_fixtures():
    return jsonify({"status": "success", "fixtures": [get_fixture()]})


@house_tour_reel_bp.route("/counts", methods=["GET"])
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


@house_tour_reel_bp.route("/moodboard", methods=["POST"])
def update_moodboard():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    rooms = _validate_rooms_dict(data.get("rooms"))
    if rooms is None:
        return jsonify({
            "status": "error",
            "error": "rooms required: one moodboard ID per room (11 room keys)",
        }), 400
    for key, moodboard_id in rooms.items():
        save_config_override(ROOMS[key]["moodboard_env"], moodboard_id)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "rooms": rooms})


@house_tour_reel_bp.route("/prompt", methods=["POST"])
def update_prompt():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    rooms = _validate_rooms_dict(data.get("rooms"))
    if rooms is None:
        return jsonify({
            "status": "error",
            "error": "rooms required: one prompt per room (11 room keys)",
        }), 400
    for key, prompt_text in rooms.items():
        save_config_override(ROOMS[key]["prompt_env"], prompt_text)
    _COUNTS_CACHE.clear()
    return jsonify({"status": "success", "fixture_id": FIXTURE_ID, "rooms": rooms})


@house_tour_reel_bp.route("/status", methods=["GET"])
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


@house_tour_reel_bp.route("/run", methods=["POST"])
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
            return jsonify({"status": "error", "error": "House Tour Reel pipeline is already running"}), 409
        _EXEC_STATE.update({
            "status": "running",
            "active_fixture": FIXTURE_ID,
            "active_table_id": fixture["table_id"],
            "current_phase": "Starting pipeline...",
            "current_phase_index": 0,
            "total_phases": TOTAL_PHASES,
            "elapsed_seconds": 0,
            "logs": [f"[{time.strftime('%X')}] Triggering House Tour Reel ({max_items} row(s), full 11-room tour)..."],
            "error": None,
            "start_time": time.time(),
        })

    def run_worker():
        register_pipeline("house-tour-reel", "House Tour Reel")
        # The run uses the SAVED per-room Studio settings (inherited via the
        # server environment). No per-run overrides: the pencils hold the 4 values.
        cmd = [
            sys.executable,
            "-u",
            "run_house_tour_reel.py",
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
            unregister_pipeline("house-tour-reel")
            _COUNTS_CACHE.clear()

    threading.Thread(target=run_worker, daemon=True).start()
    return jsonify({"status": "started", "fixture": fixture["name"]})


@house_tour_reel_bp.route("/stop", methods=["POST"])
def stop_pipeline():
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    with _STATE_LOCK:
        p = _EXEC_STATE.get("process")
        if p and p.poll() is None:
            p.terminate()
            _EXEC_STATE["status"] = "stopped"
            _EXEC_STATE["logs"].append(f"[{time.strftime('%X')}] Pipeline manually stopped.")
            unregister_pipeline("house-tour-reel")
            return jsonify({"status": "stopped"})
    return jsonify({"status": "idle"})
