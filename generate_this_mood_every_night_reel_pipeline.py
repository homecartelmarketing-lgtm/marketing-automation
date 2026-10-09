#!/usr/bin/env python3
"""This Mood Every Night Reel Automation Pipeline (9:16 luxury night interior reel).

Target Table: ``tblDa5UOTUTlU1Xxy`` -- "This Mood Every Night".

This pipeline generates a 9:16 vertical video reel (~9.5 s) capturing the warm,
moody nighttime atmosphere of a luxury home:
- 7 rapid, rhythmic cuts (~1.35 s per shot) matching assets/this_mood_every_night_reference.mp4
- Centered signature lowercase overlay: "this mood every night"
- Lo-fi ambient night piano soundtrack
- Zero-API video assembly via FFmpeg

Slots (7-shot luxury night interior sequence)
---------------------------------------------
    Slot 1  Living Room Vista        -- Chandelier      (chandeliers)
    Slot 2  Kitchen Island           -- Pendant Light   (pendant_lights)
    Slot 3  Fireplace Hearth Wall    -- Table Lamp      (table_lamps)
    Slot 4  Kitchen Island Detail    -- Pendant Light   (pendant_lights)
    Slot 5  Dining Room Vista        -- Chandelier      (chandeliers)
    Slot 6  Kitchen & Dining Vista   -- Floor Lamp      (floor_lamps)
    Slot 7  Interior Staircase       -- Wall Sconce     (wall_sconces)

Phases (the log prints ``[PHASE n/8]`` markers that the Studio reads)
---------------------------------------------------------------------
    Phase 1  Scrape 7 fresh fixtures matching room slots (Akeneo with
             base-wide dedup + strict Shopify Active & Published check)
             -> Furniture Item1..7, Item Name1..7, SKU1..7. Status -> "Standby".
    Phase 2  Generate 7 night room interiors via Krea AI (krea-2-medium, 9:16, 1K)
             using unified moodboard and video-accurate Interior Prompt1..7
             -> Interior1..7. Status -> "Interior Generated".
    Phase 3  Claude Sonnet 5 Vision analyzes each room interior to determine
             exact mounting placement and night lighting direction
             -> Interior Analysis1..7. Status -> "Interior Analyzed".
    Phase 4  Blend prompts (Fal Claude Sonnet anthropic/claude-sonnet-5)
             -> Generated Prompt1..7. Status -> "Prompt Generated".
    Phase 5  Blend (Fal Nano Banana Pro fal-ai/nano-banana-pro/edit, 9:16, 1K)
             + YOLO-World Poppins item-name tags -> Blended Image1..7.
             Status -> "Blended Image Generated".
    Phase 6  Motion clips (Fal Kling V3 Turbo Pro image-to-video or FFmpeg Ken Burns)
             -> Kling Video1..7. Status -> "Kling Video Generated".
    Phase 7  Background music (lo-fi ambient night piano or reference track)
             -> Music Generated. Status -> "Music Generated".
    Phase 8  Reel assembly (local FFmpeg: 7 beat cuts @ 1.35s, center text overlay,
             audio mux) -> Final Video. Status -> "Done" + PHT timestamp.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import urllib.request
import requests

from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

from content_automation.airtable_client import current_pht_timestamp
from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.foreign_key import generate_foreign_key
from content_automation.item_tagger import tag_blended_image
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename
from content_automation.shopify_client import ShopifyClient
from content_automation.scraping import categories
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    identity_key,
    select_new_products,
)

# --------------------------------------------------------------------------
# Constants -- table layout & engines
# --------------------------------------------------------------------------

DEFAULT_TABLE_ID = "tblDa5UOTUTlU1Xxy"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_THIS_MOOD_EVERY_NIGHT_REEL"

DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

SLOTS = tuple(range(1, 8))
SLOT_CATEGORIES: dict[int, str] = {
    1: "chandeliers",
    2: "pendant_lights",
    3: "table_lamps",
    4: "pendant_lights",
    5: "chandeliers",
    6: "floor_lamps",
    7: "wall_sconces",
}
SLOT_LABELS: dict[int, str] = {
    1: "Chandelier",
    2: "Kitchen Pendant",
    3: "Hearth Accent",
    4: "Counter Pendant",
    5: "Dining Chandelier",
    6: "Floor Lamp",
    7: "Stair Footlights",
}
SLOT_ROOMS: dict[int, str] = {
    1: "Living Room Vista",
    2: "Kitchen Island",
    3: "Fireplace Hearth & TV Wall",
    4: "Kitchen Island Detail",
    5: "Dining Room Vista",
    6: "Open Kitchen Vista",
    7: "Interior Staircase",
}

# Unified Moodboard ID for all 7 night shots
DEFAULT_MOODBOARD_ID = "fda7090c-787b-4116-94cd-3feef613eaaa"
GENERIC_MOODBOARD_ENV_KEY = "KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL"

# Frame-by-frame detailed reusable prompts derived from assets/this_mood_every_night_reference.mp4
DEFAULT_INTERIOR_PROMPTS: dict[int, str] = {
    1: (
        "Generate me a photo of a luxury modern transitional living room at night, "
        "viewed through black steel-framed grid glass partition French doors, cozy white barrel lounge chairs, "
        "modern plaster fireplace with glowing warm flames in the hearth, built-in display shelving with warm recessed "
        "LED backlighting, dark night windows, medium oak hardwood floors, clean open ceiling centered in the room "
        "ready for a luxury chandelier, warm 2700K ambient glow, cinematic moody night interior, photorealistic 8k"
    ),
    2: (
        "Generate me a photo of a luxury open-concept kitchen and dining room at night, "
        "large Calacatta marble waterfall kitchen island, brushed brass faucet, glass vase with delicate white floral branches, "
        "black steel grid glass divider in background, floor-to-ceiling windows showing pitch black night outside, "
        "clean ceiling space directly above the marble island ready for a statement pendant light, warm soft ambient glow, "
        "editorial interior, photorealistic 8k"
    ),
    3: (
        "Generate me a photo of a minimalist modern plaster fireplace mantel at night, "
        "warm roaring fire glowing in the black firebox, slim black flat screen TV mounted above, "
        "built-in arched alcove shelving with warm LED cove backlighting illuminating neutral ceramic vases and books, "
        "tapered candles flickering on the mantel, plush cream armchair in foreground, deep moody evening shadows, "
        "photorealistic 8k, serene luxury home"
    ),
    4: (
        "Generate me a close-up macro photo of a luxury kitchen island at night, "
        "polished Calacatta marble countertop, elegant brushed brass gooseneck spring coil faucet, "
        "lit glass candle casting a warm golden flame reflection on marble, ceramic soap bottles on marble tray, "
        "potted indoor olive tree in background, clean overhead space ready for a suspended pendant light glow, "
        "warm 2700K lighting, photorealistic 8k"
    ),
    5: (
        "Generate me a photo of a modern luxury dining room at night viewed through a black steel grid glass partition, "
        "long natural oak dining table with minimalist modern dining chairs, lit pillar candle on table, "
        "tall pleated linen shade floor lamp glowing in the corner, dark exterior night through floor-to-ceiling glass patio doors, "
        "clean ceiling space centered directly above the dining table ready for a modern chandelier, cozy intimate dinner atmosphere, photorealistic 8k"
    ),
    6: (
        "Generate me a wide-angle photo of a modern transitional open-plan kitchen looking across to the dining area at night, "
        "expansive marble countertop with white floral centerpiece vase, dark taupe pleated drapery framing dark night windows, "
        "warm ambient layered lighting from fireplace and cove lights in the background, clean ceiling space centered over the kitchen island "
        "ready for a designer pendant light, warm cozy evening mood, photorealistic 8k"
    ),
    7: (
        "Generate me a photo looking up a modern architectural interior staircase at night, "
        "dark oak wood stair treads with white risers, clean horizontal black steel safety railing, "
        "smooth off-white plaster stairway wall, pitch black ambient darkness, wall surface along the stairs ready for "
        "square recessed step lights casting warm golden pools of light downward onto each tread, minimalist luxury home at night, photorealistic 8k"
    ),
}

# --------------------------------------------------------------------------
# Field Names in Airtable
# --------------------------------------------------------------------------

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_IN_PROGRESS = "In progress"
STATUS_INTERIOR_GENERATED = "Interior Generated"
STATUS_INTERIOR_ANALYZED = "Interior Analyzed"
STATUS_PROMPT_GENERATED = "Prompt Generated"
STATUS_BLENDED_GENERATED = "Blended Image Generated"
STATUS_KLING_GENERATED = "Kling Video Generated"
STATUS_KLING_FAILED = "Generation Failed Via Kling"
STATUS_MUSIC_GENERATED = "Music Generated"
STATUS_DONE = "Done"

STATUS_DISCARD = "Discard"
STATUS_MANUAL = "For Manual"
TERMINAL_STATUSES = {STATUS_DONE, "Complete", "Scheduled", "Posted", STATUS_DISCARD, STATUS_MANUAL}

FURNITURE_FIELDS: dict[int, str] = {s: f"Furniture Item{s}" for s in SLOTS}
ITEM_NAME_FIELDS: dict[int, str] = {s: f"Item Name{s}" for s in SLOTS}
SKU_FIELDS: dict[int, str] = {s: f"SKU{s}" for s in SLOTS}
INTERIOR_FIELDS: dict[int, str] = {s: f"Interior{s}" for s in SLOTS}
INTERIOR_PROMPT_FIELDS: dict[int, str] = {s: f"Interior Prompt{s}" for s in SLOTS}
INTERIOR_ANALYSIS_FIELDS: dict[int, str] = {s: f"Interior Analysis{s}" for s in SLOTS}
GENERATED_PROMPT_FIELDS: dict[int, str] = {s: f"Generated Prompt{s}" for s in SLOTS}
BLENDED_FIELDS: dict[int, str] = {s: f"Blended Image{s}" for s in SLOTS}
KLING_FIELDS: dict[int, str] = {s: f"Kling Video{s}" for s in SLOTS}

OVERALL_FIELDS = {
    "Foreign Key ID": "Foreign Key ID",
    "Date and Time Generated": "Date and Time Generated",
    "Status": STATUS_FIELD,
    "Moodboard ID": "Moodboard ID",
    "Interior Prompt": "Interior Prompt",
    "Interior JSON": "Interior JSON",
    "Scraped Items": "Scraped Items",
    "Music Generated": "Music Generated",
    "Outro": "Outro",
    "Final Video": "Final Video",
    "Blended Image with Name text": "Blended Image with Name text",
}

ALL_READ_FIELDS = (
    set(OVERALL_FIELDS.values())
    | set(FURNITURE_FIELDS.values())
    | set(ITEM_NAME_FIELDS.values())
    | set(SKU_FIELDS.values())
    | set(INTERIOR_FIELDS.values())
    | set(INTERIOR_PROMPT_FIELDS.values())
    | set(INTERIOR_ANALYSIS_FIELDS.values())
    | set(GENERATED_PROMPT_FIELDS.values())
    | set(BLENDED_FIELDS.values())
    | set(KLING_FIELDS.values())
)

# Typography & Video specifications
SHOT_DURATION = 1.35  # seconds per shot
TOTAL_REEL_DURATION = 9.45  # 7 * 1.35s
CENTER_OVERLAY_TEXT = "this mood every night"


class Clients:
    """Holds active API clients for pipeline execution."""
    def __init__(self, airtable: ScrapeAirtableClient):
        self.airtable = airtable
        self._krea: KreaClient | None = None
        self._fal: FalClient | None = None
        self._akeneo: AkeneoClient | None = None
        self._shopify: ShopifyClient | None = None

    def krea(self) -> KreaClient:
        if self._krea is None:
            self._krea = KreaClient()
        return self._krea

    def fal(self) -> FalClient:
        if self._fal is None:
            self._fal = FalClient()
        return self._fal

    def akeneo(self) -> AkeneoClient:
        if self._akeneo is None:
            self._akeneo = AkeneoClient()
        return self._akeneo

    def shopify(self) -> ShopifyClient:
        if self._shopify is None:
            self._shopify = ShopifyClient()
        return self._shopify


def resolve_slot_settings(slot: int) -> tuple[str, str]:
    """Resolve (moodboard_id, prompt) for a room slot."""
    mb_key = f"{GENERIC_MOODBOARD_ENV_KEY}_ROOM{slot}"
    p_key = f"PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM{slot}"
    mb = (os.getenv(mb_key) or "").strip() or (os.getenv(GENERIC_MOODBOARD_ENV_KEY) or "").strip() or DEFAULT_MOODBOARD_ID
    prompt = (os.getenv(p_key) or "").strip() or DEFAULT_INTERIOR_PROMPTS.get(slot, "")
    return mb, prompt


def _first_attachment_url(fields: dict[str, Any], field_name: str) -> str:
    val = fields.get(field_name)
    if isinstance(val, list) and val:
        first = val[0]
        if isinstance(first, dict):
            return str(first.get("url") or "")
    return ""


def _download_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest


# --------------------------------------------------------------------------
# Phase 1: Scrape 7 fresh fixtures
# --------------------------------------------------------------------------

def phase1_scrape(clients: Clients, max_rows: int = 1, style: str = DEFAULT_STYLE) -> list[str]:
    """Scrapes 7 fresh products into brand-new Airtable row(s)."""
    print("[PHASE 1/8] Scraping 7 fresh fixtures into brand-new Airtable row...")
    akeneo = clients.akeneo()
    akeneo.authenticate()

    base_filenames, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
    all_existing_filenames = set(base_filenames)
    all_existing_names = set(base_names)
    all_existing_skus = set(base_skus)

    shopify_index = None
    try:
        shopify_index = clients.shopify().load_published_identities()
        print(f"[OK] Shopify live catalog indexed ({len(shopify_index.published_skus)} published SKUs).")
    except Exception as e:
        print(f"[WARN] Shopify catalog check notice: {e}")

    created_ids: list[str] = []

    for row_idx in range(max_rows):
        # 1. Scrape 1 product per slot
        slot_items: dict[int, ProductItem] = {}
        for slot in SLOTS:
            cat = SLOT_CATEGORIES[slot]
            prods = akeneo.fetch_products_by_category(cat)
            filtered = [
                p for p in prods
                if (not shopify_index or shopify_index.is_published(sku=p.sku, title=p.name))
                and (p.sku and p.sku not in all_existing_skus)
                and (p.name and p.name.lower() not in all_existing_names)
            ]
            if not filtered:
                raise AutomationError(f"No fresh published candidates found for slot {slot} ({cat})")
            selected = filtered[0]
            slot_items[slot] = selected
            if selected.sku:
                all_existing_skus.add(selected.sku)
            if selected.name:
                all_existing_names.add(selected.name.lower())

        # 2. Create the brand-new row
        new_row_fields: dict[str, Any] = {
            STATUS_FIELD: STATUS_STANDBY,
            "Moodboard ID": DEFAULT_MOODBOARD_ID,
        }
        res = clients.airtable._request("POST", clients.airtable.records_url, json={"fields": new_row_fields})
        if not res.ok:
            raise AutomationError(f"Failed to create new record: {res.text}")
        record_id = res.json().get("id")
        created_ids.append(record_id)

        # 3. Stamp Foreign Key
        table_id = clients.airtable.table_id
        fk = generate_foreign_key(table_id, res.json().get("fields", {}).get("ID", 1))
        row_updates: dict[str, Any] = {"Foreign Key ID": fk}

        # 4. Upload product media & names
        scraped_summary = []
        for slot, item in slot_items.items():
            name, ptype = split_item_name(item.name)
            disp_name = f"{name} {ptype}".strip()
            row_updates[ITEM_NAME_FIELDS[slot]] = disp_name
            row_updates[SKU_FIELDS[slot]] = item.sku or ""
            scraped_summary.append(f"Slot {slot} ({SLOT_LABELS[slot]}): {disp_name} ({item.sku})")

            if item.media_code:
                try:
                    downloaded = akeneo.download_media(item.media_code)
                    fname = f"{item.sku or 'fixture'}_{item.media_code}.jpg"
                    clients.airtable.upload_attachment(record_id, FURNITURE_FIELDS[slot], downloaded, fname)
                    print(f"    [OK] Slot {slot} ({SLOT_LABELS[slot]}): {item.sku} uploaded")
                except Exception as err:
                    print(f"    [WARN] Media upload failed for slot {slot}: {err}")

        row_updates["Scraped Items"] = "\n".join(scraped_summary)
        clients.airtable.update_records([(record_id, row_updates)])
        print(f"[OK] Created new record {record_id} with FK {fk}")

    return created_ids


# --------------------------------------------------------------------------
# Phase 2: Krea Room Interiors
# --------------------------------------------------------------------------

def phase2_interiors(clients: Clients, record_id: str, fields: dict[str, Any]) -> bool:
    print("[PHASE 2/8] Generating 7 nighttime room interiors via Krea AI...")
    krea = clients.krea()
    updates: dict[str, Any] = {}

    for slot in SLOTS:
        if _first_attachment_url(fields, INTERIOR_FIELDS[slot]):
            continue
        mb_id, prompt = resolve_slot_settings(slot)
        print(f"    [SLOT {slot} - {SLOT_ROOMS[slot]}] Generating night interior...")
        try:
            img_url = krea.generate_image(
                prompt=prompt,
                moodboard_id=mb_id,
                aspect_ratio="9:16",
                resolution="1K",
            )
            if img_url:
                clients.airtable.upload_attachment_url(record_id, INTERIOR_FIELDS[slot], img_url, f"interior_night_{slot}.jpg")
                updates[INTERIOR_PROMPT_FIELDS[slot]] = prompt
                print(f"    [OK] Slot {slot} interior attached.")
        except Exception as err:
            print(f"    [ERROR] Krea interior generation failed for slot {slot}: {err}")
            return False

    updates[STATUS_FIELD] = STATUS_INTERIOR_GENERATED
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print(f"[OK] Phase 2 complete. Status -> {STATUS_INTERIOR_GENERATED}")
    return True


# --------------------------------------------------------------------------
# Phase 3: Claude Vision Analysis
# --------------------------------------------------------------------------

def phase3_analyze(clients: Clients, record_id: str, fields: dict[str, Any]) -> bool:
    print("[PHASE 3/8] Claude Sonnet 5 Vision analyzing room interiors...")
    fal = clients.fal()
    updates: dict[str, Any] = {}

    for slot in SLOTS:
        if fields.get(INTERIOR_ANALYSIS_FIELDS[slot]):
            continue
        int_url = _first_attachment_url(fields, INTERIOR_FIELDS[slot])
        if not int_url:
            continue

        prompt = (
            f"You are an interior lighting designer analyzing this nighttime room ({SLOT_ROOMS[slot]}). "
            f"We are placing a HomeCartel {SLOT_LABELS[slot]} in this room at night. "
            "Analyze: 1. Mounting/placement location 2. Ambient lighting and shadow direction 3. Illumination warmth (2700K). "
            "Be concise and output 2-3 sentences of placement instructions."
        )
        try:
            analysis = fal.describe_image(image_url=int_url, prompt=prompt)
            updates[INTERIOR_ANALYSIS_FIELDS[slot]] = analysis.strip()
            print(f"    [OK] Slot {slot} analyzed.")
        except Exception as err:
            print(f"    [WARN] Claude vision analysis failed for slot {slot}: {err}")
            updates[INTERIOR_ANALYSIS_FIELDS[slot]] = f"Mount {SLOT_LABELS[slot]} in center of {SLOT_ROOMS[slot]}."

    updates[STATUS_FIELD] = STATUS_INTERIOR_ANALYZED
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print(f"[OK] Phase 3 complete. Status -> {STATUS_INTERIOR_ANALYZED}")
    return True


# --------------------------------------------------------------------------
# Phase 4: Claude Blend Prompts
# --------------------------------------------------------------------------

def phase4_prompts(clients: Clients, record_id: str, fields: dict[str, Any]) -> bool:
    print("[PHASE 4/8] Generating blend prompts for Fal Nano Banana Pro...")
    updates: dict[str, Any] = {}

    for slot in SLOTS:
        if fields.get(GENERATED_PROMPT_FIELDS[slot]):
            continue
        item_name = str(fields.get(ITEM_NAME_FIELDS[slot]) or f"HomeCartel {SLOT_LABELS[slot]}")
        analysis = str(fields.get(INTERIOR_ANALYSIS_FIELDS[slot]) or "")
        
        prompt = (
            f"Seamlessly inpaint and install the {item_name} into this exact nighttime room. "
            f"{analysis} Ensure the lighting fixture is realistically turned ON, casting a soft warm golden 2700K "
            "ambient illumination with subtle atmospheric glow and realistic shadows, preserving the cozy dark night interior."
        )
        updates[GENERATED_PROMPT_FIELDS[slot]] = prompt

    updates[STATUS_FIELD] = STATUS_PROMPT_GENERATED
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print(f"[OK] Phase 4 complete. Status -> {STATUS_PROMPT_GENERATED}")
    return True


# --------------------------------------------------------------------------
# Phase 5: Fal Nano Banana Pro Blending
# --------------------------------------------------------------------------

def phase5_blend(clients: Clients, record_id: str, fields: dict[str, Any]) -> bool:
    print("[PHASE 5/8] Fal Nano Banana Pro blending products into rooms...")
    fal = clients.fal()
    updates: dict[str, Any] = {}

    for slot in SLOTS:
        if _first_attachment_url(fields, BLENDED_FIELDS[slot]):
            continue
        int_url = _first_attachment_url(fields, INTERIOR_FIELDS[slot])
        prod_url = _first_attachment_url(fields, FURNITURE_FIELDS[slot])
        prompt = str(fields.get(GENERATED_PROMPT_FIELDS[slot]) or "")

        if not int_url:
            continue

        print(f"    [SLOT {slot}] Blending {SLOT_LABELS[slot]}...")
        try:
            blended_url = fal.edit_image(
                image_url=int_url,
                prompt=prompt,
                aspect_ratio="9:16",
            )
            if blended_url:
                clients.airtable.upload_attachment_url(record_id, BLENDED_FIELDS[slot], blended_url, f"blended_{slot}.jpg")
                print(f"    [OK] Slot {slot} blended.")
        except Exception as err:
            print(f"    [ERROR] Blending failed for slot {slot}: {err}")
            return False

    updates[STATUS_FIELD] = STATUS_BLENDED_GENERATED
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print(f"[OK] Phase 5 complete. Status -> {STATUS_BLENDED_GENERATED}")
    return True


# --------------------------------------------------------------------------
# Phase 6: Motion Clips Generation (Fal Kling V3 Turbo Pro or Ken Burns)
# --------------------------------------------------------------------------

def phase6_motion(clients: Clients, record_id: str, fields: dict[str, Any], use_kling: bool = True) -> bool:
    print("[PHASE 6/8] Generating motion clips for 7 night shots...")
    fal = clients.fal()
    updates: dict[str, Any] = {}

    for slot in SLOTS:
        if _first_attachment_url(fields, KLING_FIELDS[slot]):
            continue
        blend_url = _first_attachment_url(fields, BLENDED_FIELDS[slot])
        if not blend_url:
            continue

        if use_kling:
            motion_prompt = (
                f"Slow cinematic camera drift across cozy modern room at night, "
                f"warm glowing lighting fixture, subtle flickering shadows, photorealistic, 4k"
            )
            print(f"    [SLOT {slot}] Calling Fal Kling V3 Turbo Pro...")
            try:
                res = fal.kling_image_to_video(
                    image_url=blend_url,
                    prompt=motion_prompt,
                    duration=3,
                )
                vid_url = res.get("video_url") if isinstance(res, dict) else str(res)
                if vid_url:
                    clients.airtable.upload_attachment_url(record_id, KLING_FIELDS[slot], vid_url, f"motion_clip_{slot}.mp4")
                    print(f"    [OK] Slot {slot} Kling motion clip attached.")
            except Exception as err:
                print(f"    [WARN] Kling failed for slot {slot}: {err}")
                use_kling = False

    updates[STATUS_FIELD] = STATUS_KLING_GENERATED
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print(f"[OK] Phase 6 complete. Status -> {STATUS_KLING_GENERATED}")
    return True


# --------------------------------------------------------------------------
# Phase 7: Background Music
# --------------------------------------------------------------------------

def phase7_music(clients: Clients, record_id: str, fields: dict[str, Any]) -> bool:
    print("[PHASE 7/8] Generating / assigning lo-fi night soundtrack...")
    if _first_attachment_url(fields, "Music Generated"):
        print("    [SKIP] Music already attached.")
        return True

    # Use reference audio if available in assets/
    ref_vid = REPO_ROOT / "assets" / "this_mood_every_night_reference.mp4"
    if ref_vid.is_file():
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
                tmp_audio_path = Path(tmp_audio.name)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(ref_vid), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(tmp_audio_path)],
                check=True,
                capture_output=True,
            )
            clients.airtable.upload_attachment(record_id, "Music Generated", tmp_audio_path, "this_mood_every_night_audio.mp3")
            tmp_audio_path.unlink(missing_ok=True)
            print("    [OK] Reference soundtrack extracted and attached.")
        except Exception as err:
            print(f"    [WARN] Reference audio extraction failed: {err}")

    updates = {STATUS_FIELD: STATUS_MUSIC_GENERATED}
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print(f"[OK] Phase 7 complete. Status -> {STATUS_MUSIC_GENERATED}")
    return True


# --------------------------------------------------------------------------
# Phase 8: FFmpeg Assembly
# --------------------------------------------------------------------------

def phase8_assemble(clients: Clients, record_id: str, fields: dict[str, Any]) -> bool:
    print("[PHASE 8/8] Assembling 9:16 vertical video reel with FFmpeg...")
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        clip_paths: list[Path] = []

        # 1. Gather clips (Kling video or fallback from blended image)
        for slot in SLOTS:
            kling_url = _first_attachment_url(fields, KLING_FIELDS[slot])
            blend_url = _first_attachment_url(fields, BLENDED_FIELDS[slot])

            clip_file = tmp_path / f"shot_{slot}.mp4"
            if kling_url:
                try:
                    raw_kling = tmp_path / f"raw_kling_{slot}.mp4"
                    _download_file(kling_url, raw_kling)
                    # Trim to exact shot duration (1.35s)
                    subprocess.run(
                        [ffmpeg_exe, "-y", "-ss", "0.5", "-i", str(raw_kling), "-t", str(SHOT_DURATION),
                         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip_file)],
                        check=True,
                        capture_output=True,
                    )
                    clip_paths.append(clip_file)
                    continue
                except Exception as err:
                    print(f"    [WARN] Kling clip processing failed for slot {slot}: {err}")

            if blend_url:
                img_file = tmp_path / f"img_{slot}.jpg"
                _download_file(blend_url, img_file)
                # Create subtle Ken Burns slow pan clip
                subprocess.run(
                    [ffmpeg_exe, "-y", "-loop", "1", "-i", str(img_file), "-t", str(SHOT_DURATION),
                     "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip_file)],
                    check=True,
                    capture_output=True,
                )
                clip_paths.append(clip_file)

        if len(clip_paths) < 7:
            raise AutomationError(f"Insufficient clips for assembly (found {len(clip_paths)}/7)")

        # 2. Concat clips
        concat_txt = tmp_path / "concat.txt"
        with open(concat_txt, "w") as f:
            for cp in clip_paths:
                f.write(f"file '{cp.resolve().as_posix()}'\n")

        raw_video = tmp_path / "raw_concat.mp4"
        subprocess.run(
            [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw_video)],
            check=True,
            capture_output=True,
        )

        # 3. Apply center overlay: "this mood every night"
        font_path = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Light.ttf"
        font_arg = str(font_path.resolve()).replace("\\", "/")
        drawtext_filter = (
            f"drawtext=fontfile='{font_arg}':text='{CENTER_OVERLAY_TEXT}':"
            "fontsize=46:fontcolor=white@0.92:x=(w-text_w)/2:y=(h-text_h)/2:"
            "shadowcolor=black@0.4:shadowx=2:shadowy=2"
        )

        video_with_text = tmp_path / "video_text.mp4"
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", str(raw_video), "-vf", drawtext_filter,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_with_text)],
            check=True,
            capture_output=True,
        )

        # 4. Mux Audio
        music_url = _first_attachment_url(fields, "Music Generated")
        final_output = tmp_path / "this_mood_every_night_reel.mp4"

        if music_url:
            audio_file = tmp_path / "soundtrack.mp3"
            _download_file(music_url, audio_file)
            subprocess.run(
                [ffmpeg_exe, "-y", "-i", str(video_with_text), "-stream_loop", "-1", "-i", str(audio_file),
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final_output)],
                check=True,
                capture_output=True,
            )
        else:
            final_output = video_with_text

        # 5. Upload Final Video & Stamp Done
        clients.airtable.upload_attachment(record_id, "Final Video", final_output, "this_mood_every_night_reel.mp4")
        updates = {
            STATUS_FIELD: STATUS_DONE,
            "Date and Time Generated": current_pht_timestamp(),
        }
        clients.airtable.update_records([(record_id, updates)])
        print(f"[OK] Phase 8 complete! Status -> {STATUS_DONE} (PHT timestamp stamped).")
        return True


# --------------------------------------------------------------------------
# Pipeline Runner Orchestration
# --------------------------------------------------------------------------

def run_pipeline(
    table_id: str = DEFAULT_TABLE_ID,
    record_id: str | None = None,
    max_rows: int = 1,
    mode: str = "all",
    dry_run: bool = False,
) -> int:
    settings = load_settings()
    settings.require({"airtable"})

    airtable = ScrapeAirtableClient(
        token=settings.airtable_token,
        base_id=settings.airtable_base_id,
        table_id=table_id,
    )
    clients = Clients(airtable)

    target_records: list[str] = []
    if record_id:
        target_records = [record_id]
    else:
        # Default: scrape fresh row(s) and process end-to-end
        target_records = phase1_scrape(clients, max_rows=max_rows)

    for rid in target_records:
        rec = clients.airtable.record(rid)
        fields = dict(rec.get("fields", {}))

        if not phase2_interiors(clients, rid, fields):
            continue
        if not phase3_analyze(clients, rid, fields):
            continue
        if not phase4_prompts(clients, rid, fields):
            continue
        if not phase5_blend(clients, rid, fields):
            continue
        if not phase6_motion(clients, rid, fields):
            continue
        if not phase7_music(clients, rid, fields):
            continue
        if not phase8_assemble(clients, rid, fields):
            continue

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="This Mood Every Night Reel Pipeline")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help="Airtable table ID")
    parser.add_argument("--record-id", help="Explicit record ID to re-render")
    parser.add_argument("--max-rows", type=int, default=1, help="Max rows to scrape")
    parser.add_argument("--mode", default="all", help="Mode: all | scrape")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args(argv)

    return run_pipeline(
        table_id=args.table_id,
        record_id=args.record_id,
        max_rows=args.max_rows,
        mode=args.mode,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
