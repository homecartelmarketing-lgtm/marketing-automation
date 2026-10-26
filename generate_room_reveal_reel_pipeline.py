#!/usr/bin/env python3
"""Room Reveal Reel Automation Pipeline (9:16, build-up reveal + HomeCartel outro).

One locked camera angle. Krea draws a fully furnished room, a HomeCartel fixture is blended in,
then Nano Banana Pro removes the contents layer by layer until the room is bare. The stills play
in reverse -- empty room first, then each layer appears until the finished blended photo -- and
the Final Video closes on the HomeCartel outro card.

Phases (the log prints ``[PHASE n/7]`` markers that the Studio reads)
    1  Scrape 1 fresh fixture -> brand-new row
    2  Krea: one furnished 9:16 room (fixed prompt + moodboard)         -> Room Interior
    3  Claude Sonnet 5: blending prompt for the fixture                 -> Blending Prompt
    4  Nano Banana Pro: blend the fixture into the room (state "Full")  -> Full
    5  Claude Sonnet 5 vision: inventory + 3 cumulative removal prompts -> Removal Plan
    6  Nano Banana Pro chained removals Full -> Layer 2 -> Layer 1 -> Empty
    7  Local assembly (build-up hard cuts) + outro card + ElevenLabs pop/whoosh -> Raw Video, Final Video

Usage::
    python run_room_reveal_reel.py --max-rows 1
    python run_room_reveal_reel.py --record-id recXXXXXXXX      # explicit re-render of one row
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

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
from content_automation.prompts.scale import blend_instruction_from_fields
from content_automation.scale_guard import (
    ScaleGuardResult,
    blend_with_scale_guard,
    ensure_scale_fields,
    write_scale_fields,
)
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
from generate_room_build_up_reel_pipeline import (
    assemble_hard_cut_video,
    ensure_sfx_assets,
    mix_sound_track,
)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DEFAULT_TABLE_ID = "tbldk5nac1UeYHd77"  # Room Reveal (Airtable base appDM0jUDsaiThtR3)
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_ROOM_REVEAL_REEL"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

DEFAULT_CATEGORY = "chandeliers"
CATEGORY_ENV_KEY = "ROOM_REVEAL_REEL_CATEGORY"
CATEGORY_LABELS: dict[str, str] = {
    "chandeliers": "Chandelier",
    "pendant_lights": "Pendant Light",
    "floor_lamps": "Floor Lamp",
    "table_lamps": "Table Lamp",
    "wall_lights": "Wall Light",
    "ceiling_mounted": "Ceiling Light",
    "cluster_chandeliers": "Cluster Chandelier",
}

# Krea uses a FIXED prompt; the moodboard ID carries the style.
ROOM_PROMPT_ENV = "PROMPT_ROOM_REVEAL_REEL"
ROOM_PROMPT_DEFAULT = "Generate me a modern living room"
ROOM_MOODBOARD_ENV = "KREA_MOODBOARD_ID_ROOM_REVEAL_REEL"
ROOM_MOODBOARD_DEFAULT = "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3"

ASPECT_RATIO = "9:16"
RESOLUTION = "1K"
CLAUDE_MODEL = "anthropic/claude-sonnet-5"
NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"

# 4 build-up segments, then the HomeCartel outro card in the Final Video.
# The stills are produced by REMOVING from `Full`, but they play in reverse:
# Empty -> Layer 1 -> Layer 2 -> Full. Empty holds 24 frames at the open, the finished room 36 at the end.
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
STATE_FRAMES = (24, 20, 20, 36)
TOTAL_FRAMES = sum(STATE_FRAMES)  # 100 frames = 3.333 s of build-up
TOTAL_SECONDS = TOTAL_FRAMES / VIDEO_FPS

OUTRO_SECONDS = 2.5
OUTRO_FRAMES = round(OUTRO_SECONDS * VIDEO_FPS)  # 75 frames
FINAL_SECONDS = TOTAL_SECONDS + OUTRO_SECONDS  # 5.833 s
OUTRO_CANDIDATES = (
    Path(__file__).resolve().parent / "assets" / "outro_layout.jpg",
    Path("assets/outro_layout.jpg"),
)

STATE_FULL = "Full"
STATE_LAYER_2 = "Layer 2"
STATE_LAYER_1 = "Layer 1"
STATE_EMPTY = "Empty"
ALL_STATES = (STATE_FULL, STATE_LAYER_2, STATE_LAYER_1, STATE_EMPTY)
REMOVAL_ORDER = (STATE_LAYER_2, STATE_LAYER_1, STATE_EMPTY)  # produced from Full, in this order
REVEAL_ORDER = (
    STATE_EMPTY,
    STATE_LAYER_1,
    STATE_LAYER_2,
    STATE_FULL,
)

# Sound
OPENING_HIT_SECONDS = 0.08

STATUS_FIELD = "Status"
STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"
STATUS_FOR_MANUAL = "For Manual"
STATUS_OPTIONS = [STATUS_IN_PROGRESS, STATUS_DONE, "Scheduled", "Posted", "Discard", STATUS_FOR_MANUAL]

ID_FIELD = "ID"
RAW_VIDEO_FIELD = "Raw Video"
FINAL_VIDEO_FIELD = "Final Video"

F_ITEM = "Furniture Item"
F_NAME = "Item Name"
F_SKU = "SKU"
F_PRODUCT_TYPE = "Product Type"
F_MEASUREMENT = "Measurement"
F_INTERIOR = "Room Interior"
F_BLEND_PROMPT = "Blending Prompt"
F_REMOVAL_PLAN = "Removal Plan"

REQUIRED_FIELDS: dict[str, str] = {
    "Foreign Key ID": "singleLineText",
    "Date and Time Generated": "dateTime",
    "Date and Time Scheduled": "dateTime",
    "Caption Generated": "multilineText",
    STATUS_FIELD: "singleSelect",
    F_ITEM: "multipleAttachments",
    F_NAME: "multilineText",
    F_SKU: "singleLineText",
    F_PRODUCT_TYPE: "singleLineText",
    F_MEASUREMENT: "singleLineText",
    F_INTERIOR: "multipleAttachments",
    F_BLEND_PROMPT: "multilineText",
    F_REMOVAL_PLAN: "multilineText",
    RAW_VIDEO_FIELD: "multipleAttachments",
    FINAL_VIDEO_FIELD: "multipleAttachments",
}
for _state in ALL_STATES:
    REQUIRED_FIELDS[_state] = "multipleAttachments"

ALL_READ_FIELDS = [STATUS_FIELD, RAW_VIDEO_FIELD, FINAL_VIDEO_FIELD, *REQUIRED_FIELDS]

MAX_STEP_ATTEMPTS = 3
MIN_STEP_SIMILARITY = 0.72
MIN_DETAIL_DROP = 0.97  # new edge density must be below previous * this


def _category() -> str:
    return (os.getenv(CATEGORY_ENV_KEY, "").strip() or DEFAULT_CATEGORY).lower()


def _category_label() -> str:
    category = _category()
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def _room_moodboard() -> str:
    return os.getenv(ROOM_MOODBOARD_ENV, "").strip() or ROOM_MOODBOARD_DEFAULT


def _room_prompt() -> str:
    return os.getenv(ROOM_PROMPT_ENV, "").strip() or ROOM_PROMPT_DEFAULT


def _split_name(fields: dict[str, Any]) -> tuple[str, str]:
    raw = str(fields.get(F_NAME) or "").strip()
    stored_type = str(fields.get(F_PRODUCT_TYPE) or "").strip()
    if "|" in raw:
        title, ptype = (part.strip() for part in raw.split("|", 1))
        return title, ptype or stored_type or _category_label()
    return raw or _category_label(), stored_type or _category_label()


# --------------------------------------------------------------------------
# Reel timeline (pure, unit-tested)
# --------------------------------------------------------------------------


def cut_frames() -> tuple[int, ...]:
    """Frame index of every hard cut between the 7 segments."""
    frames: list[int] = []
    total = 0
    for count in STATE_FRAMES[:-1]:
        total += count
        frames.append(total)
    return tuple(frames)


OUTRO_FRAME = TOTAL_FRAMES  # first frame of the outro card in the Final Video


def reel_sequence(images: dict[str, Path]) -> list[Path]:
    """The 4 stills in playing order: the empty room first, the finished blend last."""
    return [images[state] for state in REVEAL_ORDER]


def final_sequence(images: dict[str, Path], outro_card: Path) -> list[Path]:
    """The Final Video plays the build-up, then holds the HomeCartel outro card."""
    return [*reel_sequence(images), outro_card]


def sfx_hits() -> list[tuple[str, float]]:
    """Whoosh as the empty room opens and again on the outro card; pop on every layer that appears."""
    hits: list[tuple[str, float]] = [("whoosh", OPENING_HIT_SECONDS)]
    for frame in cut_frames():
        hits.append(("pop", round(frame / VIDEO_FPS, 3)))
    hits.append(("whoosh", round(OUTRO_FRAME / VIDEO_FPS, 3)))
    return hits


def resolve_outro_card() -> Path:
    """The 1080x1920 HomeCartel end card (same asset Virtual Staging ends on)."""
    for candidate in OUTRO_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise AutomationError("Outro card not found at assets/outro_layout.jpg")


# --------------------------------------------------------------------------
# Claude prompts (pure, unit-tested)
# --------------------------------------------------------------------------

KEEP_IDENTICAL_SUFFIX = (
    " The camera is locked on a tripod: keep the exact same angle, perspective, framing, walls, windows, "
    "floor, ceiling and lighting as the input image. Do not move, redraw or restyle anything that remains. "
    "No text, no people."
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
        "You are preparing a stop-motion 'room reveal' video that empties a room and then rebuilds it. The image is a "
        f"fully furnished room that contains the HomeCartel {fixture_label} '{fixture_name}'.\n"
        "Look carefully at the image and list what is really in it, then write 3 CUMULATIVE removal prompts for an "
        "image-editing model; each prompt is applied to the result of the previous one:\n"
        f"1. Remove the {fixture_label} '{fixture_name}' plus the small decor and accessories (name them: vases, plants, "
        "books, cushions, small lamps, candles, bowls...). Everything else stays.\n"
        "2. Remove soft furnishings and secondary pieces (name them: rugs, curtains, wall art, mirrors, side tables, "
        "stools, coffee table, shelves...). Only the largest main furniture stays.\n"
        "3. Remove ALL remaining furniture and objects (name them) so only bare walls, floor, windows and ceiling "
        "remain, and say to restore the floor and wall surface behind every removed object.\n"
        "Use the real item names and positions you see (for example 'the round dining table and four chairs').\n"
        "The camera never moves: every prompt must keep the same angle, perspective and framing.\n"
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
# Airtable / scrape
# --------------------------------------------------------------------------


def _ensure_id_field(clients: Clients) -> None:
    try:
        known = clients.airtable.known_field_names(refresh=True)
        if ID_FIELD in known:
            return
        clients.airtable._request(
            "POST", clients.airtable.fields_url, json={"name": ID_FIELD, "type": "autoNumber"}
        )
    except Exception as error:
        print(f"[WARN] Could not create the '{ID_FIELD}' field: {error}")


def _ensure_schema(clients: Clients) -> None:
    clients.airtable.ensure_fields(REQUIRED_FIELDS)
    clients.airtable.ensure_single_select_options(STATUS_FIELD, STATUS_OPTIONS)
    ensure_scale_fields(clients.airtable)
    _ensure_id_field(clients)
    print("[OK] Airtable schema ready (fields + Status options).")


def _scrape_fixtures(clients: Clients, akeneo: AkeneoClient, style: str, num_rows: int) -> list[ProductItem]:
    """Fresh, Shopify-active, never-used fixtures for brand-new rows (base-wide dedup)."""
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
        for att in row.get(F_ITEM) or []:
            if isinstance(att, dict) and att.get("filename"):
                all_filenames.add(identity_key(att["filename"]))
        name = str(row.get(F_NAME) or "").strip().lower()
        if name:
            all_names.add(name)
        sku = str(row.get(F_SKU) or "").strip()
        if sku:
            all_skus.add(sku)

    shopify_index = None
    try:
        print("[INFO] Loading published catalog from Shopify (homecartel.net)...")
        shopify_index = ShopifyClient().load_published_identities()
    except Exception as error:
        print(f"[WARN] Shopify index check skipped: {error}")

    category = _category()
    items = _scrape_candidates_for_slot(
        clients,
        akeneo,
        category=category,
        style=style,
        needed=num_rows,
        all_existing_filenames=all_filenames,
        all_existing_names=all_names,
        all_existing_skus=all_skus,
        shopify_index=shopify_index,
    )
    print(f"[INFO] {_category_label()} ({category}): found {len(items)}/{num_rows} candidate(s).")
    return items


def _create_row(clients: Clients, item: ProductItem, akeneo: AkeneoClient) -> str | None:
    fields: dict[str, Any] = {
        STATUS_FIELD: STATUS_IN_PROGRESS,
        F_NAME: _display_name(item),
        F_SKU: item.sku or "",
        F_PRODUCT_TYPE: item.product_type or _category_label(),
    }
    if item.measurement:
        fields[F_MEASUREMENT] = item.measurement
    try:
        record_id = clients.airtable.create_record(fields)
    except Exception as error:
        print(f"[ERROR] Could not create row: {error}")
        return None
    try:
        downloaded = akeneo.download_media(item.media_code)
        filename = f"{item.sku or 'fixture'}_{item.media_code}.jpg"
        clients.airtable.upload_attachment(record_id, F_ITEM, downloaded, filename)
        print(f"[OK] {_category_label()}: {item.sku} -> {record_id} / {F_ITEM}")
    except Exception as error:
        print(f"[WARN] Row {record_id} created but the product photo upload failed: {error}")
    return record_id


# --------------------------------------------------------------------------
# Phases 2-7 (one row)
# --------------------------------------------------------------------------


def phase2_interior(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("[PHASE 2/7] Krea furnished interior (fixed prompt + moodboard)...", flush=True)
    if _first_attachment_url(fields, F_INTERIOR):
        print(f"    [SKIP] {F_INTERIOR} already attached")
        return
    url = clients.krea.generate(
        prompt=_room_prompt(),
        aspect_ratio=ASPECT_RATIO,
        resolution=RESOLUTION,
        moodboard_id=_room_moodboard(),
    )
    clients.airtable.update_records([(record_id, {F_INTERIOR: [{"url": url}]})])
    fields[F_INTERIOR] = [{"url": url}]
    print("    [OK] Room interior generated")


def phase3_blend_prompt(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("[PHASE 3/7] Claude Sonnet 5 blending prompt...", flush=True)
    if str(fields.get(F_BLEND_PROMPT) or "").strip():
        print(f"    [SKIP] {F_BLEND_PROMPT} already present")
        return
    interior_url = _first_attachment_url(fields, F_INTERIOR)
    product_url = _first_attachment_url(fields, F_ITEM)
    if not interior_url or not product_url:
        raise AutomationError(f"Phase 3 needs {F_INTERIOR} and {F_ITEM}")
    title, ptype = _split_name(fields)
    instruction = blend_instruction_from_fields(
        fields,
        0,
        interior_label="Furnished Modern Living Room Interior",
        item_name=f"{title} | {ptype}",
        aspect_ratio=ASPECT_RATIO,
        extra_instructions=(
            "Do not add, remove or move any furniture, art or decor; only install this lighting fixture and "
            "remove a competing fixture of the same kind. The room must stay recognisably the same, and the camera "
            "angle must not change."
        ),
    )
    raw = clients.fal.generate_vision_prompt(
        image_urls=[interior_url, product_url], prompt=instruction, model=CLAUDE_MODEL
    )
    prompt = clean_claude_prompt(raw)
    if not prompt:
        raise AutomationError("Claude returned an empty blending prompt")
    clients.airtable.update_records([(record_id, {F_BLEND_PROMPT: prompt})])
    fields[F_BLEND_PROMPT] = prompt
    print(f"    [OK] Blending prompt ({len(prompt)} chars)")


def phase4_blend(clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path) -> tuple[Path, str]:
    """State FULL. Returns (local_path, remote_url)."""
    print("[PHASE 4/7] Nano Banana Pro blend: fixture into the room (full room state)...", flush=True)
    dest = workdir / "room_full.jpg"
    existing = _first_attachment_url(fields, STATE_FULL)
    if existing:
        print(f"    [SKIP] {STATE_FULL} already attached -> reusing")
        _download_url(existing, dest, timeout=120)
        return dest, existing

    interior_url = _first_attachment_url(fields, F_INTERIOR)
    product_url = _first_attachment_url(fields, F_ITEM)
    prompt = str(fields.get(F_BLEND_PROMPT) or "").strip()
    if not (interior_url and product_url and prompt):
        raise AutomationError("Phase 4 needs interior, product and blending prompt")

    label = str(fields.get(F_PRODUCT_TYPE) or "lighting fixture").strip().lower()
    scale_result: ScaleGuardResult = blend_with_scale_guard(
        clients.fal,
        prompt=prompt,
        room_url=interior_url,
        product_url=product_url,
        product_type=str(fields.get(F_PRODUCT_TYPE) or ""),
        measurement=str(fields.get(F_MEASUREMENT) or ""),
        item_name=str(fields.get(F_NAME) or ""),
        label=f"the {label}",
        aspect_ratio=ASPECT_RATIO,
        resolution=RESOLUTION,
        model=NANO_BANANA_MODEL,
    )
    url = scale_result.image_url
    _download_url(url, dest, timeout=120)
    clients.airtable.upload_attachment(record_id, STATE_FULL, dest, dest.name)
    write_scale_fields(clients.airtable, record_id, [(0, scale_result)])
    print("    [OK] Full room uploaded")
    return dest, url


def phase5_removal_plan(
    clients: Clients, record_id: str, fields: dict[str, Any], full_url: str
) -> dict[str, Any]:
    print("[PHASE 5/7] Claude vision removal plan (inventory + 3 cumulative removals)...", flush=True)
    stored = str(fields.get(F_REMOVAL_PLAN) or "").strip()
    if stored:
        print(f"    [SKIP] {F_REMOVAL_PLAN} already present")
        return parse_removal_plan(stored)

    title, ptype = _split_name(fields)
    raw = clients.fal.generate_vision_prompt(
        image_urls=[full_url],
        prompt=build_removal_plan_instruction(ptype, title),
        model=CLAUDE_MODEL,
    )
    plan = parse_removal_plan(raw)
    if plan["used_fallback"]:
        print("    [WARN] Claude's plan was unusable, generic removal prompts are used.")
    value = json.dumps({"inventory": plan["inventory"], "prompts": plan["prompts"]}, ensure_ascii=False, indent=2)
    clients.airtable.update_records([(record_id, {F_REMOVAL_PLAN: value})])
    fields[F_REMOVAL_PLAN] = value
    print(f"    [OK] Removal plan ({len(plan['inventory'])} items listed)")
    return plan


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
    full: tuple[Path, str],
    plan: dict[str, Any],
    workdir: Path,
) -> dict[str, Path]:
    print("[PHASE 6/7] Nano Banana Pro chained removals (Full -> Layer 2 -> Layer 1 -> Empty)...", flush=True)
    images: dict[str, Path] = {STATE_FULL: full[0]}
    prev_path, prev_url = full
    for state, prompt in zip(REMOVAL_ORDER, plan["prompts"]):
        dest = workdir / f"room_{state.lower().replace(' ', '_')}.jpg"
        existing = _first_attachment_url(fields, state)
        if existing:
            print(f"    [SKIP] {state} already attached -> reusing")
            _download_url(existing, dest, timeout=120)
            images[state] = dest
            prev_path, prev_url = dest, existing
            continue
        path, url = _removal_step(clients, prev_path, prev_url, prompt, dest, state)
        clients.airtable.upload_attachment(record_id, state, path, path.name)
        images[state] = path
        prev_path, prev_url = path, url
        print(f"    [OK] {state} uploaded")
    return images


def phase7_assemble(
    clients: Clients,
    record_id: str,
    images: dict[str, Path],
    workdir: Path,
) -> Path:
    print("[PHASE 7/7] Build-up assembly + HomeCartel outro + ElevenLabs pop/whoosh sound (local FFmpeg)...", flush=True)
    sequence = reel_sequence(images)
    raw_video = assemble_hard_cut_video(
        sequence,
        workdir / f"room_reveal_raw_{record_id}.mp4",
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
        fps=VIDEO_FPS,
        frame_counts=list(STATE_FRAMES),
    )
    clients.airtable.upload_attachment(record_id, RAW_VIDEO_FIELD, raw_video, raw_video.name)
    print("    [OK] Raw Video (silent build-up, no outro) uploaded")

    sfx = ensure_sfx_assets(clients.fal)
    track = mix_sound_track(
        sfx,
        workdir / "room_reveal_sound.m4a",
        hits=sfx_hits(),
        total_seconds=FINAL_SECONDS,
    )
    outro_card = resolve_outro_card()
    final_video = assemble_hard_cut_video(
        final_sequence(images, outro_card),
        workdir / f"room_reveal_{record_id}.mp4",
        audio_path=track,
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
        fps=VIDEO_FPS,
        frame_counts=[*STATE_FRAMES, OUTRO_FRAMES],
    )
    clients.airtable.upload_attachment(record_id, FINAL_VIDEO_FIELD, final_video, final_video.name)
    clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_DONE})])
    print("    [OK] Final Video (build-up + outro) uploaded & Status = Done (PHT timestamp auto-stamped)")
    return final_video


def process_row(clients: Clients, record_id: str, force: bool = False) -> bool:
    print(f"\n[ROW {record_id}] Processing Room Reveal Reel...", flush=True)
    fields = dict(clients.airtable.record(record_id).get("fields", {}))
    if not force and str(fields.get(STATUS_FIELD) or "").strip().lower() == STATUS_DONE.lower():
        print(f"[ROW {record_id}] Status is 'Done' -- skipping (use --force to re-generate).")
        return True
    try:
        clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_IN_PROGRESS})])
        phase2_interior(clients, record_id, fields)
        phase3_blend_prompt(clients, record_id, fields)
        with tempfile.TemporaryDirectory(prefix=f"rrv_{record_id}_") as tmp:
            workdir = Path(tmp)
            full = phase4_blend(clients, record_id, fields, workdir)
            plan = phase5_removal_plan(clients, record_id, fields, full[1])
            images = phase6_removals(clients, record_id, fields, full, plan, workdir)
            final_path = phase7_assemble(clients, record_id, images, workdir)
            save_dir = Path("output") / "content" / "room_reveal_reel"
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
    parser = argparse.ArgumentParser(description="Room Reveal Reel Automation Pipeline.")
    parser.add_argument("--table-id", default=None, help=f"Airtable table ID (or {TABLE_ENV_KEY})")
    parser.add_argument("--phase", choices=["all", "scrape", "generate"], default="all")
    parser.add_argument("--mode", dest="phase", choices=["all", "scrape", "generate"], help="Alias for --phase")
    parser.add_argument("--record-id", default=None, help="Explicit record to (re)process; skips scraping")
    parser.add_argument("--max-rows", type=int, default=1, help="How many brand-new rows to create and process")
    parser.add_argument("--max-items", dest="max_rows", type=int, help="Alias for --max-rows")
    parser.add_argument("--style", default=DEFAULT_STYLE, help="Akeneo style filter (default: modern)")
    parser.add_argument("--category", default=None, help=f"Akeneo category (default: {DEFAULT_CATEGORY})")
    parser.add_argument("--moodboard-id", default=None, help="Override the Krea moodboard")
    parser.add_argument("--prompt", default=None, help="Override the Krea interior prompt")
    parser.add_argument("--force", action="store_true", help="Re-run even if the row is already Done")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    load_dotenv()
    args = parse_args(argv)
    if args.moodboard_id:
        os.environ[ROOM_MOODBOARD_ENV] = args.moodboard_id
    if args.prompt:
        os.environ[ROOM_PROMPT_ENV] = args.prompt
    if args.category:
        os.environ[CATEGORY_ENV_KEY] = args.category

    table_id = args.table_id or os.getenv(TABLE_ENV_KEY, "").strip() or DEFAULT_TABLE_ID

    clients = Clients(table_id)
    _ensure_schema(clients)
    print(f"[TARGET] Airtable Base: {clients.settings.airtable_base_id} | Table ID: {table_id}")

    if args.record_id:
        return 0 if process_row(clients, args.record_id, force=args.force) else 1
    if args.phase == "generate":
        print("[ERROR] --phase generate requires --record-id (existing rows are never re-run automatically).")
        return 1

    print(
        f"[PHASE 1/7] Akeneo scrape: {args.max_rows or 1} new row(s) of 1 {_category_label()}...",
        flush=True,
    )
    akeneo = clients.akeneo()
    akeneo.authenticate()
    items = _scrape_fixtures(clients, akeneo, args.style, args.max_rows or 1)
    if not items:
        print(f"[ERROR] Not enough fresh active {_category_label()} fixtures found for a new row.")
        return 1

    if args.phase == "scrape":
        created = sum(1 for item in items if _create_row(clients, item, akeneo))
        print(f"[OK] Scrape complete: created {created} row(s).")
        return 0

    done = failures = 0
    for item in items[: args.max_rows or 1]:
        record_id = _create_row(clients, item, akeneo)
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
