#!/usr/bin/env python3
"""Room Build-Up Reel Automation Pipeline (9:16, ~4.8 s, stop-motion "empty room -> furnished room").

Reference: ``new-contnet.mp4``. Two rooms are furnished in three hard-cut steps each (camera locked),
with a short pop sound on every change. The reel is built in REVERSE: Krea draws a fully furnished room,
a HomeCartel fixture is blended in, then Nano Banana Pro removes the contents layer by layer; the images
are finally played empty -> furnished with local FFmpeg.

Phases (the log prints ``[PHASE n/7]`` markers that the Studio reads)
    1  Scrape 2 fresh fixtures (Pendant Light for Room 1, Chandelier for Room 2) -> brand-new row
    2  Krea: one furnished 9:16 room per room (fixed prompt + moodboard ID)       -> Room n Interior
    3  Claude Sonnet 5: blending prompt for the fixture of each room             -> Blending Prompt n
    4  Nano Banana Pro: blend the fixture into the room (state "Full")            -> Room n Full
    5  Claude Sonnet 5 vision: inventory + 3 cumulative removal prompts           -> Removal Plan n
    6  Nano Banana Pro chained removals Full -> Layer 2 -> Layer 1 -> Empty       -> Room n Layer 2/1/Empty
    7  Local assembly (hard cuts, frame exact) + ElevenLabs pop/whoosh sound       -> Raw Video, Final Video

Usage::
    python run_room_build_up_reel.py --max-rows 1
    python run_room_build_up_reel.py --record-id recXXXXXXXX      # explicit re-render of one row
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import imageio_ffmpeg
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageFilter, ImageOps

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from content_automation.akeneo_client import AkeneoClient
from content_automation.errors import AutomationError
from content_automation.prompts import build_vision_blending_instruction
from content_automation.scraping import categories
from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
from content_automation.scraping.products import ProductItem, identity_key
from content_automation.shopify_client import ShopifyClient
from generate_one_at_a_time_lights_reel_pipeline import (
    Clients,
    _display_name,
    _download_url,
    _first_attachment_url,
    _scrape_candidates_for_slot,
    clean_claude_prompt,
)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DEFAULT_TABLE_ID = "tblhq1rz9CVCD7yiR"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_ROOM_BUILD_UP_REEL"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

ROOMS = (1, 2)
ROOM_CATEGORIES: dict[int, str] = {1: "pendant_lights", 2: "chandeliers"}
ROOM_LABELS: dict[int, str] = {1: "Pendant Light", 2: "Chandelier"}

# Krea uses a FIXED prompt; the moodboard ID carries the style.
ROOM_PROMPT_ENV: dict[int, str] = {
    1: "PROMPT_ROOM_BUILD_UP_REEL_ROOM1",
    2: "PROMPT_ROOM_BUILD_UP_REEL_ROOM2",
}
ROOM_PROMPT_DEFAULT = "Generate me a modern living room"
ROOM_MOODBOARD_ENV: dict[int, str] = {
    1: "KREA_MOODBOARD_ID_ROOM_BUILD_UP_REEL_ROOM1",
    2: "KREA_MOODBOARD_ID_ROOM_BUILD_UP_REEL_ROOM2",
}
ROOM_MOODBOARD_DEFAULT: dict[int, str] = {
    1: "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
    2: "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
}
ASPECT_RATIO = "9:16"
RESOLUTION = "1K"
CLAUDE_MODEL = "anthropic/claude-sonnet-5"
NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"

# Reel timeline measured on new-contnet.mp4 (30 fps, 144 frames = 4.8 s, hard cuts, no transitions).
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
TOTAL_FRAMES = 144
CUT_FRAMES = (19, 38, 57, 75, 95, 113, 132)  # 0.63 / 1.27 / 1.90 / 2.50 / 3.17 / 3.77 / 4.40 s
TOTAL_SECONDS = TOTAL_FRAMES / VIDEO_FPS
SCENE_CUT_FRAME = 75  # Room 1 -> Room 2

# Build order of the states inside a room (empty first, full room last).
STATE_FULL = "Full"
STATE_LAYER_2 = "Layer 2"
STATE_LAYER_1 = "Layer 1"
STATE_EMPTY = "Empty"
BUILD_ORDER = (STATE_EMPTY, STATE_LAYER_1, STATE_LAYER_2, STATE_FULL)
REMOVAL_ORDER = (STATE_LAYER_2, STATE_LAYER_1, STATE_EMPTY)  # produced from Full, in this order

# Sound
SFX_DIR = Path(__file__).parent / "assets" / "room_buildup_sfx"
SFX_PROMPTS: dict[str, str] = {
    "pop": "A short soft pop sound effect, like an object appearing, dry, clean, no music, about half a second",
    "whoosh": "A quick soft whoosh sound effect for a scene change, airy and smooth, no music, about half a second",
}
OPENING_HIT_SECONDS = 0.08

STATUS_FIELD = "Status"
STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"
STATUS_FOR_MANUAL = "For Manual"
STATUS_OPTIONS = [STATUS_IN_PROGRESS, STATUS_DONE, "Scheduled", "Posted", "Discard", STATUS_FOR_MANUAL]

RAW_VIDEO_FIELD = "Raw Video"
FINAL_VIDEO_FIELD = "Final Video"

MAX_STEP_ATTEMPTS = 3
MIN_STEP_SIMILARITY = 0.72
MIN_DETAIL_DROP = 0.97  # new edge density must be below previous * this


def f_item(room: int) -> str:
    return f"Furniture Item{room}"


def f_name(room: int) -> str:
    return f"Item Name{room}"


def f_sku(room: int) -> str:
    return f"SKU{room}"


def f_interior(room: int) -> str:
    return f"Room {room} Interior"


def f_blend_prompt(room: int) -> str:
    return f"Blending Prompt {room}"


def f_removal_plan(room: int) -> str:
    return f"Removal Plan {room}"


def f_state(room: int, state: str) -> str:
    return f"Room {room} {state}"


REQUIRED_FIELDS: dict[str, str] = {
    "Foreign Key ID": "singleLineText",
    "Date and Time Generated": "dateTime",
    "Date and Time Scheduled": "dateTime",
    "Caption Generated": "multilineText",
    STATUS_FIELD: "singleSelect",
    RAW_VIDEO_FIELD: "multipleAttachments",
    FINAL_VIDEO_FIELD: "multipleAttachments",
}
for _room in ROOMS:
    REQUIRED_FIELDS[f_item(_room)] = "multipleAttachments"
    REQUIRED_FIELDS[f_name(_room)] = "multilineText"
    REQUIRED_FIELDS[f_sku(_room)] = "singleLineText"
    REQUIRED_FIELDS[f_interior(_room)] = "multipleAttachments"
    REQUIRED_FIELDS[f_blend_prompt(_room)] = "multilineText"
    REQUIRED_FIELDS[f_removal_plan(_room)] = "multilineText"
    for _state in (STATE_FULL, STATE_LAYER_2, STATE_LAYER_1, STATE_EMPTY):
        REQUIRED_FIELDS[f_state(_room, _state)] = "multipleAttachments"

ALL_READ_FIELDS = [STATUS_FIELD, RAW_VIDEO_FIELD, FINAL_VIDEO_FIELD, *REQUIRED_FIELDS]


# --------------------------------------------------------------------------
# Reel timeline (pure, unit-tested)
# --------------------------------------------------------------------------


def state_boundaries() -> list[int]:
    """Frame index where each of the 8 states starts, plus the end: [0, 19, 38, ..., 144]."""
    return [0, *CUT_FRAMES, TOTAL_FRAMES]


def state_frame_counts() -> list[int]:
    bounds = state_boundaries()
    return [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]


def reel_sequence(room_images: dict[int, dict[str, Path]]) -> list[Path]:
    """The 8 stills in playing order: Room 1 empty -> full, then Room 2 empty -> full."""
    sequence: list[Path] = []
    for room in ROOMS:
        for state in BUILD_ORDER:
            sequence.append(room_images[room][state])
    return sequence


def sfx_hits() -> list[tuple[str, float]]:
    """(kind, seconds) for every sound: whoosh at the start and at the Room 1 -> Room 2 cut, pop on the other cuts."""
    hits: list[tuple[str, float]] = [("whoosh", OPENING_HIT_SECONDS)]
    for frame in CUT_FRAMES:
        kind = "whoosh" if frame == SCENE_CUT_FRAME else "pop"
        hits.append((kind, round(frame / VIDEO_FPS, 3)))
    return hits


# --------------------------------------------------------------------------
# Claude prompts (pure, unit-tested)
# --------------------------------------------------------------------------

KEEP_IDENTICAL_SUFFIX = (
    " Keep the camera angle, framing, walls, windows, floor, ceiling and lighting exactly identical to the input "
    "image. Do not move, redraw or restyle anything that remains. No text, no people."
)

DEFAULT_REMOVAL_PROMPTS = (
    "Remove the hanging light fixture and all small accessories and decor objects (vases, plants, books, candles, "
    "cushions, small lamps) from this room. Leave the main furniture exactly as it is.",
    "Remove the soft furnishings, rugs, curtains, wall art, mirrors and all secondary furniture (side tables, stools, "
    "coffee table, shelves). Leave only the largest main furniture pieces exactly as they are.",
    "Remove ALL remaining furniture and objects from this room so it is completely empty: bare walls, floor, windows "
    "and ceiling only. Fill the places where objects stood with the matching floor and wall surface.",
)


def build_removal_plan_instruction(fixture_label: str, fixture_name: str) -> str:
    return (
        "You are preparing a stop-motion 'room build-up' video. The image is a fully furnished room that contains "
        f"the HomeCartel {fixture_label} '{fixture_name}'.\n"
        "Look carefully at the image and list what is really in it, then write 3 CUMULATIVE removal prompts for an "
        "image-editing model; each prompt is applied to the result of the previous one:\n"
        f"1. Remove the {fixture_label} '{fixture_name}' plus the small decor and accessories (name them: vases, plants, "
        "books, cushions, small lamps, candles, bowls...). Everything else stays.\n"
        "2. Remove soft furnishings and secondary pieces (name them: rugs, curtains, wall art, mirrors, side tables, "
        "stools, coffee table, shelves...). Only the largest main furniture stays.\n"
        "3. Remove ALL remaining furniture and objects (name them) so only bare walls, floor, windows and ceiling "
        "remain, and say to restore the floor and wall surface behind every removed object.\n"
        "Use the real item names and positions you see (for example 'the round dining table and four chairs').\n"
        'Return ONLY a JSON object: {"inventory": ["item", ...], "prompts": ["prompt 1", "prompt 2", "prompt 3"]} '
        "with no markdown fences and no commentary."
    )


def parse_removal_plan(raw: str) -> dict[str, Any]:
    """Parse Claude's JSON (tolerating fences / chatter). Always returns exactly 3 usable prompts."""
    text = (raw or "").strip()
    inventory: list[str] = []
    prompts: list[str] = []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                inventory = [str(i).strip() for i in (data.get("inventory") or []) if str(i).strip()]
                prompts = [str(p).strip() for p in (data.get("prompts") or []) if str(p).strip()]
        except (ValueError, TypeError):
            pass
    used_fallback = len(prompts) < 3
    final = list(prompts[:3])
    for default in DEFAULT_REMOVAL_PROMPTS[len(final):]:
        final.append(default)
    final = [p if p.rstrip().endswith(KEEP_IDENTICAL_SUFFIX.strip()) else p.rstrip() + KEEP_IDENTICAL_SUFFIX for p in final]
    return {"inventory": inventory, "prompts": final, "used_fallback": used_fallback}


# --------------------------------------------------------------------------
# Local image checks (free): did the step keep the room and really remove things?
# --------------------------------------------------------------------------


def _gray(path: Path, size: tuple[int, int]) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(ImageOps.fit(img.convert("L"), size, Image.BILINEAR), dtype=np.float32)


def image_similarity(path_a: Path, path_b: Path) -> float:
    """1.0 = same coarse picture. Compares blurred 48x85 grayscale versions (robust to small repaints)."""
    size = (48, 85)
    a = _gray(path_a, size)
    b = _gray(path_b, size)
    return float(1.0 - np.abs(a - b).mean() / 255.0)


def edge_density(path: Path) -> float:
    """Amount of detail (furniture, objects) in the picture: mean edge strength of a 256-wide grayscale copy."""
    with Image.open(path) as img:
        small = ImageOps.fit(img.convert("L"), (256, 456), Image.BILINEAR).filter(ImageFilter.FIND_EDGES)
        return float(np.asarray(small, dtype=np.float32).mean() / 255.0)


def evaluate_removal_step(prev_path: Path, new_path: Path) -> tuple[bool, dict[str, float]]:
    similarity = image_similarity(prev_path, new_path)
    prev_detail = edge_density(prev_path)
    new_detail = edge_density(new_path)
    metrics = {"similarity": similarity, "prev_detail": prev_detail, "new_detail": new_detail}
    ok = similarity >= MIN_STEP_SIMILARITY and new_detail <= prev_detail * MIN_DETAIL_DROP
    return ok, metrics


# --------------------------------------------------------------------------
# Video assembly + sound (local FFmpeg, zero API cost)
# --------------------------------------------------------------------------


def assemble_hard_cut_video(
    image_paths: list[Path],
    output_path: Path,
    *,
    audio_path: Path | None = None,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    fps: int = VIDEO_FPS,
    frame_counts: list[int] | None = None,
) -> Path:
    """Write the stills as a frame-exact stop-motion video: instant cuts, no transitions."""
    import cv2

    counts = frame_counts or state_frame_counts()
    if len(image_paths) != len(counts):
        raise AutomationError(f"Expected {len(counts)} images for the reel, got {len(image_paths)}")
    missing = [str(p) for p in image_paths if not Path(p).is_file()]
    if missing:
        raise AutomationError(f"Reel images missing: {missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path = output_path.with_name(f"raw_{output_path.name}")
    writer = cv2.VideoWriter(str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    try:
        for image_path, frames in zip(image_paths, counts):
            with Image.open(image_path) as img:
                fitted = ImageOps.fit(img.convert("RGB"), (width, height), Image.LANCZOS)
            frame_bgr = cv2.cvtColor(np.asarray(fitted), cv2.COLOR_RGB2BGR)
            for _ in range(frames):
                writer.write(frame_bgr)
    finally:
        writer.release()

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-i", str(raw_path)]
    if audio_path is not None:
        cmd += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        raw_path.unlink(missing_ok=True)
    except Exception:
        pass
    if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        raise AutomationError(f"FFmpeg encoding failed (exit {result.returncode}): {result.stderr[-600:]}")
    return output_path


def synthesize_fallback_sfx(kind: str, destination: Path) -> Path:
    """Local stand-in for a sound effect (used only if ElevenLabs is unavailable)."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if kind == "pop":
        source = "aevalsrc=0.9*sin(2*PI*(260+900*exp(-t*28))*t)*exp(-t*26):d=0.35:s=44100"
    else:
        source = "anoisesrc=d=0.55:c=pink:a=0.5:r=44100,lowpass=f=4200,afade=t=in:d=0.18,afade=t=out:st=0.25:d=0.3"
    result = subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", source, "-ac", "2", "-ar", "44100", str(destination)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not destination.is_file():
        raise AutomationError(f"Could not synthesize fallback '{kind}' sound: {result.stderr[-300:]}")
    return destination


def ensure_sfx_assets(fal: Any | None, sfx_dir: Path | None = None) -> dict[str, Path]:
    """Return {'pop': path, 'whoosh': path}. Generated once with ElevenLabs and cached in assets/."""
    folder = sfx_dir or SFX_DIR
    folder.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for kind, prompt in SFX_PROMPTS.items():
        target = folder / f"{kind}.mp3"
        if target.is_file() and target.stat().st_size > 0:
            paths[kind] = target
            continue
        generated = False
        if fal is not None:
            try:
                url = fal.generate_elevenlabs_sound_effect(prompt, duration=1.0)
                _download_url(url, target, timeout=120)
                generated = target.is_file() and target.stat().st_size > 0
                if generated:
                    print(f"    [OK] ElevenLabs '{kind}' sound effect generated and cached -> {target.name}")
            except Exception as error:
                print(f"    [WARN] ElevenLabs '{kind}' sound effect failed ({error}); using a local stand-in.")
        if not generated:
            target = synthesize_fallback_sfx(kind, folder / f"{kind}_fallback.wav")
        paths[kind] = target
    return paths


def mix_sound_track(
    sfx: dict[str, Path],
    output_path: Path,
    *,
    hits: list[tuple[str, float]] | None = None,
    total_seconds: float = TOTAL_SECONDS,
) -> Path:
    """Place the pop / whoosh at every hit time over a faint room-tone bed (AAC-ready stereo 44.1 kHz)."""
    plan = hits or sfx_hits()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    inputs: list[str] = ["-f", "lavfi", "-t", f"{total_seconds:.3f}", "-i", "anoisesrc=c=pink:a=0.012:r=44100"]
    kinds = sorted({kind for kind, _ in plan})
    index_by_kind: dict[str, int] = {}
    for kind in kinds:
        index_by_kind[kind] = len(index_by_kind) + 1
        inputs += ["-i", str(sfx[kind])]

    filters: list[str] = ["[0:a]lowpass=f=1800,aformat=sample_rates=44100:channel_layouts=stereo[bed]"]
    labels = ["[bed]"]
    uses = {kind: sum(1 for k, _ in plan if k == kind) for kind in kinds}
    for kind in kinds:
        split_labels = "".join(f"[{kind}_{n}]" for n in range(uses[kind]))
        filters.append(
            f"[{index_by_kind[kind]}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"asplit={uses[kind]}{split_labels}" if uses[kind] > 1 else
            f"[{index_by_kind[kind]}:a]aformat=sample_rates=44100:channel_layouts=stereo[{kind}_0]"
        )
    counters = {kind: 0 for kind in kinds}
    for position, (kind, seconds) in enumerate(plan):
        n = counters[kind]
        counters[kind] += 1
        delay_ms = int(round(seconds * 1000))
        filters.append(f"[{kind}_{n}]adelay={delay_ms}|{delay_ms}[hit{position}]")
        labels.append(f"[hit{position}]")
    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,"
        f"alimiter=limit=0.95,atrim=0:{total_seconds:.3f}[aout]"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[aout]", "-ar", "44100", "-ac", "2",
           str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not output_path.is_file():
        raise AutomationError(f"FFmpeg sound mix failed (exit {result.returncode}): {result.stderr[-600:]}")
    return output_path


# --------------------------------------------------------------------------
# Airtable / scrape
# --------------------------------------------------------------------------


def _ensure_schema(clients: Clients) -> None:
    clients.airtable.ensure_fields(REQUIRED_FIELDS)
    clients.airtable.ensure_single_select_options(STATUS_FIELD, STATUS_OPTIONS)
    print("[OK] Airtable schema ready (fields + Status options).")


def _scrape_room_fixtures(clients: Clients, akeneo: AkeneoClient, style: str, num_rows: int) -> list[list[ProductItem]]:
    """Fresh, Shopify-active, never-used fixtures: Room 1 Pendant Light, Room 2 Chandelier (base-wide dedup)."""
    base_filenames: set[str] = set()
    base_names: set[str] = set()
    base_skus: set[str] = set()
    try:
        base_filenames, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
        print(
            f"[INFO] Cross-table deduplication active: {len(base_skus)} existing SKU(s), "
            f"{len(base_names)} item name(s), {len(base_filenames)} attachment filename(s)."
        )
    except Exception as error:
        print(f"[WARN] Base deduplication fetch notice: {error}")
    all_filenames, all_names, all_skus = set(base_filenames), set(base_names), set(base_skus)

    for record in clients.airtable.list_records(list(ALL_READ_FIELDS)):
        row = record.get("fields", {})
        for room in ROOMS:
            for att in row.get(f_item(room)) or []:
                if isinstance(att, dict) and att.get("filename"):
                    all_filenames.add(identity_key(att["filename"]))
            name = str(row.get(f_name(room)) or "").strip().lower()
            if name:
                all_names.add(name)
            sku = str(row.get(f_sku(room)) or "").strip()
            if sku:
                all_skus.add(sku)

    shopify_index = None
    try:
        print("[INFO] Loading published catalog from Shopify (homecartel.net)...")
        shopify_index = ShopifyClient().load_published_identities()
    except Exception as error:
        print(f"[WARN] Shopify index check skipped: {error}")

    per_room: dict[int, list[ProductItem]] = {}
    for room in ROOMS:
        items = _scrape_candidates_for_slot(
            clients,
            akeneo,
            category=ROOM_CATEGORIES[room],
            style=style,
            needed=num_rows,
            all_existing_filenames=all_filenames,
            all_existing_names=all_names,
            all_existing_skus=all_skus,
            shopify_index=shopify_index,
        )
        per_room[room] = items
        print(f"[INFO] Room {room} ({ROOM_LABELS[room]}): found {len(items)}/{num_rows} candidate(s).")

    available = min(len(per_room[room]) for room in ROOMS)
    if available == 0:
        return []
    return [[per_room[room][i] for room in ROOMS] for i in range(available)]


def _create_row(clients: Clients, items: list[ProductItem], akeneo: AkeneoClient) -> str | None:
    fields: dict[str, Any] = {STATUS_FIELD: STATUS_IN_PROGRESS}
    for room, item in zip(ROOMS, items):
        fields[f_name(room)] = _display_name(item)
        fields[f_sku(room)] = item.sku or ""
    try:
        record_id = clients.airtable.create_record(fields)
    except Exception as error:
        print(f"[ERROR] Could not create row: {error}")
        return None
    ok = True
    for room, item in zip(ROOMS, items):
        try:
            downloaded = akeneo.download_media(item.media_code)
            filename = f"{item.sku or 'fixture'}_{item.media_code}.jpg"
            clients.airtable.upload_attachment(record_id, f_item(room), downloaded, filename)
            print(f"[OK] Room {room} ({ROOM_LABELS[room]}): {item.sku} -> {record_id} / {f_item(room)}")
        except Exception as error:
            print(f"[ERROR] Upload product {item.sku} for room {room}: {error}")
            ok = False
    if not ok:
        print(f"[WARN] Row {record_id} created but one or more product uploads failed.")
    return record_id


# --------------------------------------------------------------------------
# Phases 2-7 (one row)
# --------------------------------------------------------------------------


def _room_moodboard(room: int) -> str:
    return os.getenv(ROOM_MOODBOARD_ENV[room], "").strip() or ROOM_MOODBOARD_DEFAULT[room]


def _room_prompt(room: int) -> str:
    return os.getenv(ROOM_PROMPT_ENV[room], "").strip() or ROOM_PROMPT_DEFAULT


def _split_name(fields: dict[str, Any], room: int) -> tuple[str, str]:
    raw = str(fields.get(f_name(room)) or "").strip()
    if "|" in raw:
        title, ptype = (part.strip() for part in raw.split("|", 1))
        return title, ptype or ROOM_LABELS[room]
    return raw or ROOM_LABELS[room], ROOM_LABELS[room]


def phase2_interiors(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("[PHASE 2/7] Krea furnished interiors (fixed prompt + moodboard)...", flush=True)

    def one(room: int) -> tuple[int, str]:
        if _first_attachment_url(fields, f_interior(room)):
            print(f"    [SKIP] {f_interior(room)} already attached")
            return room, ""
        url = clients.krea.generate(
            prompt=_room_prompt(room),
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
            moodboard_id=_room_moodboard(room),
        )
        return room, url

    with ThreadPoolExecutor(max_workers=len(ROOMS)) as pool:
        results = list(pool.map(one, ROOMS))
    updates: dict[str, Any] = {}
    for room, url in results:
        if url:
            updates[f_interior(room)] = [{"url": url}]
            print(f"    [OK] Room {room} interior generated")
    if updates:
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)


def phase3_blend_prompts(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("[PHASE 3/7] Claude Sonnet 5 blending prompts (one fixture per room)...", flush=True)
    updates: dict[str, Any] = {}
    for room in ROOMS:
        if str(fields.get(f_blend_prompt(room)) or "").strip():
            print(f"    [SKIP] {f_blend_prompt(room)} already present")
            continue
        interior_url = _first_attachment_url(fields, f_interior(room))
        product_url = _first_attachment_url(fields, f_item(room))
        if not interior_url or not product_url:
            raise AutomationError(f"Phase 3 needs {f_interior(room)} and {f_item(room)}")
        title, ptype = _split_name(fields, room)
        instruction = build_vision_blending_instruction(
            interior_label="Furnished Modern Living Room Interior",
            item_name=f"{title} ({ptype})",
            aspect_ratio=ASPECT_RATIO,
            extra_instructions=(
                "Do not add, remove or move any furniture, art or decor; only install this lighting fixture and "
                "remove a competing fixture of the same kind. The room must stay recognisably the same."
            ),
        )
        raw = clients.fal.generate_vision_prompt(
            image_urls=[interior_url, product_url], prompt=instruction, model=CLAUDE_MODEL
        )
        prompt = clean_claude_prompt(raw)
        if not prompt:
            raise AutomationError(f"Claude returned an empty blending prompt for room {room}")
        updates[f_blend_prompt(room)] = prompt
        print(f"    [OK] Room {room} blending prompt ({len(prompt)} chars)")
    if updates:
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)


def phase4_blend(clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path) -> dict[int, tuple[Path, str]]:
    """State FULL per room. Returns {room: (local_path, remote_url)}."""
    print("[PHASE 4/7] Nano Banana Pro blend: fixture into each room (full room state)...", flush=True)

    def one(room: int) -> tuple[int, Path, str]:
        dest = workdir / f"room{room}_full.jpg"
        existing = _first_attachment_url(fields, f_state(room, STATE_FULL))
        if existing:
            print(f"    [SKIP] {f_state(room, STATE_FULL)} already attached -> reusing")
            _download_url(existing, dest, timeout=120)
            return room, dest, existing
        interior_url = _first_attachment_url(fields, f_interior(room))
        product_url = _first_attachment_url(fields, f_item(room))
        prompt = str(fields.get(f_blend_prompt(room)) or "").strip()
        if not (interior_url and product_url and prompt):
            raise AutomationError(f"Phase 4 needs interior, product and blending prompt for room {room}")
        url = clients.fal.generate(
            prompt=prompt,
            image_urls=[interior_url, product_url],
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
            model=NANO_BANANA_MODEL,
        )
        _download_url(url, dest, timeout=120)
        clients.airtable.upload_attachment(record_id, f_state(room, STATE_FULL), dest, dest.name)
        print(f"    [OK] Room {room} full room uploaded")
        return room, dest, url

    with ThreadPoolExecutor(max_workers=len(ROOMS)) as pool:
        return {room: (path, url) for room, path, url in pool.map(one, ROOMS)}


def phase5_removal_plans(clients: Clients, record_id: str, fields: dict[str, Any], fulls: dict[int, tuple[Path, str]]) -> dict[int, dict[str, Any]]:
    print("[PHASE 5/7] Claude vision removal plans (inventory + 3 cumulative removals)...", flush=True)
    plans: dict[int, dict[str, Any]] = {}
    updates: dict[str, Any] = {}
    for room in ROOMS:
        stored = str(fields.get(f_removal_plan(room)) or "").strip()
        if stored:
            plans[room] = parse_removal_plan(stored)
            print(f"    [SKIP] {f_removal_plan(room)} already present")
            continue
        title, ptype = _split_name(fields, room)
        raw = clients.fal.generate_vision_prompt(
            image_urls=[fulls[room][1]],
            prompt=build_removal_plan_instruction(ptype, title),
            model=CLAUDE_MODEL,
        )
        plan = parse_removal_plan(raw)
        if plan["used_fallback"]:
            print(f"    [WARN] Room {room}: Claude's plan was unusable, generic removal prompts are used.")
        plans[room] = plan
        updates[f_removal_plan(room)] = json.dumps(
            {"inventory": plan["inventory"], "prompts": plan["prompts"]}, ensure_ascii=False, indent=2
        )
        print(f"    [OK] Room {room} removal plan ({len(plan['inventory'])} items listed)")
    if updates:
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)
    return plans


def _removal_step(
    clients: Clients,
    prev_path: Path,
    prev_url: str,
    prompt: str,
    dest: Path,
    label: str,
) -> tuple[Path, str]:
    """One Nano Banana removal with local checks; keeps the best of up to MAX_STEP_ATTEMPTS."""
    best: tuple[float, Path, str] | None = None
    for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
        url = clients.fal.generate(
            prompt=prompt,
            image_urls=[prev_url],
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
            model=NANO_BANANA_MODEL,
        )
        candidate = dest.with_name(f"{dest.stem}_try{attempt}{dest.suffix}")
        _download_url(url, candidate, timeout=120)
        ok, metrics = evaluate_removal_step(prev_path, candidate)
        print(
            f"    [{label}] attempt {attempt}: similarity {metrics['similarity']:.2f}, detail "
            f"{metrics['prev_detail']:.3f} -> {metrics['new_detail']:.3f} -> {'OK' if ok else 'rejected'}"
        )
        if ok:
            shutil.copyfile(candidate, dest)
            return dest, url
        score = metrics["new_detail"] - (metrics["similarity"] * 0.05)
        if metrics["similarity"] >= MIN_STEP_SIMILARITY * 0.85 and (best is None or score < best[0]):
            best = (score, candidate, url)
    if best is None:
        raise AutomationError(f"{label}: no usable removal result after {MAX_STEP_ATTEMPTS} attempts")
    print(f"    [WARN] {label}: no attempt passed every check; using the closest one.")
    shutil.copyfile(best[1], dest)
    return dest, best[2]


def phase6_removals(
    clients: Clients,
    record_id: str,
    fields: dict[str, Any],
    fulls: dict[int, tuple[Path, str]],
    plans: dict[int, dict[str, Any]],
    workdir: Path,
) -> dict[int, dict[str, Path]]:
    print("[PHASE 6/7] Nano Banana Pro chained removals (Full -> Layer 2 -> Layer 1 -> Empty)...", flush=True)

    def one(room: int) -> tuple[int, dict[str, Path]]:
        images: dict[str, Path] = {STATE_FULL: fulls[room][0]}
        prev_path, prev_url = fulls[room]
        for state, prompt in zip(REMOVAL_ORDER, plans[room]["prompts"]):
            dest = workdir / f"room{room}_{state.lower().replace(' ', '_')}.jpg"
            existing = _first_attachment_url(fields, f_state(room, state))
            if existing:
                print(f"    [SKIP] {f_state(room, state)} already attached -> reusing")
                _download_url(existing, dest, timeout=120)
                images[state] = dest
                prev_path, prev_url = dest, existing
                continue
            path, url = _removal_step(clients, prev_path, prev_url, prompt, dest, f"Room {room} {state}")
            clients.airtable.upload_attachment(record_id, f_state(room, state), path, path.name)
            images[state] = path
            prev_path, prev_url = path, url
            print(f"    [OK] {f_state(room, state)} uploaded")
        return room, images

    with ThreadPoolExecutor(max_workers=len(ROOMS)) as pool:
        return dict(pool.map(one, ROOMS))


def phase7_assemble(
    clients: Clients,
    record_id: str,
    room_images: dict[int, dict[str, Path]],
    workdir: Path,
) -> Path:
    print("[PHASE 7/7] Frame-exact hard-cut assembly + ElevenLabs pop/whoosh sound (local FFmpeg)...", flush=True)
    sequence = reel_sequence(room_images)
    raw_video = assemble_hard_cut_video(sequence, workdir / f"room_build_up_raw_{record_id}.mp4")
    clients.airtable.upload_attachment(record_id, RAW_VIDEO_FIELD, raw_video, raw_video.name)
    print("    [OK] Raw Video (silent) uploaded")

    sfx = ensure_sfx_assets(clients.fal)
    track = mix_sound_track(sfx, workdir / "room_build_up_sound.m4a")
    final_video = assemble_hard_cut_video(sequence, workdir / f"room_build_up_reel_{record_id}.mp4", audio_path=track)
    clients.airtable.upload_attachment(record_id, FINAL_VIDEO_FIELD, final_video, final_video.name)
    clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_DONE})])
    print("    [OK] Final Video uploaded & Status = Done (PHT timestamp auto-stamped)")
    return final_video


def process_row(clients: Clients, record_id: str, force: bool = False) -> bool:
    print(f"\n[ROW {record_id}] Processing Room Build-Up Reel...", flush=True)
    fields = dict(clients.airtable.record(record_id).get("fields", {}))
    if not force and str(fields.get(STATUS_FIELD) or "").strip().lower() == STATUS_DONE.lower():
        print(f"[ROW {record_id}] Status is 'Done' -- skipping (use --force to re-generate).")
        return True
    try:
        clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_IN_PROGRESS})])
        phase2_interiors(clients, record_id, fields)
        phase3_blend_prompts(clients, record_id, fields)
        with tempfile.TemporaryDirectory(prefix=f"rbu_{record_id}_") as tmp:
            workdir = Path(tmp)
            fulls = phase4_blend(clients, record_id, fields, workdir)
            plans = phase5_removal_plans(clients, record_id, fields, fulls)
            room_images = phase6_removals(clients, record_id, fields, fulls, plans, workdir)
            final_path = phase7_assemble(clients, record_id, room_images, workdir)
            save_dir = Path("output") / "content" / "room_build_up_reel"
            save_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(final_path, save_dir / final_path.name)
            print(f"[OK] Local video saved to: {save_dir / final_path.name}")
        return True
    except Exception as error:
        print(f"[ERROR] Row {record_id} failed: {error}", flush=True)
        try:
            clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_FOR_MANUAL})])
        except Exception:
            pass
        return False


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Room Build-Up Reel Automation Pipeline.")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help=f"Airtable table ID (default: {DEFAULT_TABLE_ID})")
    parser.add_argument("--phase", choices=["all", "scrape", "generate"], default="all")
    parser.add_argument("--mode", dest="phase", choices=["all", "scrape", "generate"], help="Alias for --phase")
    parser.add_argument("--record-id", default=None, help="Explicit record to (re)process; skips scraping")
    parser.add_argument("--max-rows", type=int, default=1, help="How many brand-new rows to create and process")
    parser.add_argument("--max-items", dest="max_rows", type=int, help="Alias for --max-rows")
    parser.add_argument("--style", default=DEFAULT_STYLE, help="Akeneo style filter (default: modern)")
    parser.add_argument("--moodboard-id", default=None, help="Override the Krea moodboard for BOTH rooms")
    parser.add_argument("--force", action="store_true", help="Re-run even if the row is already Done")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    load_dotenv()
    args = parse_args(argv)
    if args.moodboard_id:
        for env_key in ROOM_MOODBOARD_ENV.values():
            os.environ[env_key] = args.moodboard_id

    table_id = args.table_id or os.getenv(TABLE_ENV_KEY, "").strip() or DEFAULT_TABLE_ID
    clients = Clients(table_id)
    _ensure_schema(clients)
    print(f"[TARGET] Airtable Base: {clients.settings.airtable_base_id} | Table ID: {table_id}")

    if args.record_id:
        return 0 if process_row(clients, args.record_id, force=args.force) else 1
    if args.phase == "generate":
        print("[ERROR] --phase generate requires --record-id (existing rows are never re-run automatically).")
        return 1

    print(f"[PHASE 1/7] Akeneo scrape: {args.max_rows or 1} new row(s) of 2 fixtures (Pendant + Chandelier)...", flush=True)
    akeneo = clients.akeneo()
    akeneo.authenticate()
    groups = _scrape_room_fixtures(clients, akeneo, args.style, args.max_rows or 1)
    if not groups:
        print("[ERROR] Not enough fresh active fixtures (pendant + chandelier) found for a new row.")
        return 1

    if args.phase == "scrape":
        created = sum(1 for group in groups if _create_row(clients, group, akeneo))
        print(f"[OK] Scrape complete: created {created} row(s).")
        return 0

    done = failures = 0
    for group in groups[: args.max_rows or 1]:
        record_id = _create_row(clients, group, akeneo)
        if not record_id:
            failures += 1
            continue
        if process_row(clients, record_id):
            done += 1
        else:
            failures += 1
    print(f"\n[OK] Finished {done} brand-new row(s) end-to-end; {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
