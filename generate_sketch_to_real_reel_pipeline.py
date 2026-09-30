#!/usr/bin/env python3
"""Sketch to Real Reel Automation Pipeline (9:16 Vertical Video).

Transforms an architectural hand-drawn outline sketch of a room into a photorealistic,
fully-styled luxury room with illuminated warm ambient lighting, complete with Instagram
cover photo, Auto Draw line-drawing reveal video, and branded outro.

Core Principles:
1. Zero-API Edge Extraction & Tracing:
   Uses the local Auto Draw engine (content_automation.auto_draw) to perform Canny edge
   subtraction between empty room interior (BEFORE) and blended room scene (AFTER), isolating
   the lighting fixture outlines without requiring any external sketch generation API.
2. No Price Field:
   Completely omits the Price field from Airtable schema and scraping logic.
3. No ElevenLabs Music:
   Zero ElevenLabs audio calls. Video renders with local audio or silent outro muxing.
4. Minimalist Claude Vision:
   Claude Sonnet 5 only generates the Blending Prompt and 3-5 word Reel Headline.
   No sketch prompt, no video prompt, and no caption generation.

Phases
------
    Phase 1  Akeneo Scrape (1 fresh active fixture) + strict Shopify catalog check + base-wide dedup
             -> Creates brand-new row in Airtable (Status: "In progress")
             -> Stamps Foreign Key ID (STR-REEL-<CODE>-<ROW_ID>), Furniture Item, SKU, Item Name, Category.
    Phase 2  Generate 9:16 luxury room interior via Krea AI (krea-2-medium, 1K)
             -> Attached to "Room Interior" (BEFORE scene for Auto Draw).
    Phase 3  Claude Sonnet 5 vision analysis over [interior + product cutout]
             -> Generates Blending Prompt and Reel Headline (saved to Airtable).
    Phase 4  Fal Nano Banana Pro Photorealistic Room Blend (9:16, 1K)
             -> "Blended Image" (AFTER scene for Auto Draw) + YOLO-World tagged variant.
    Phase 5  Auto Draw Outline Extraction & Cover Generation
             -> Extracts fixture vector outline preview -> "Sketch Image"
             -> Stamped with centered Poppins-Bold luxury headline -> "Thumbnail with Generated Text" (Cover).
    Phase 6  Auto Draw Animated Reveal Video Rendering
             -> Real-time frame-by-frame line-drawing reveal MP4 via local FFmpeg -> "Raw Video".
    Phase 7  Local FFmpeg Outro Concatenation (Silent / Local Audio, Zero ElevenLabs)
             -> Outro card merge with 0.5s dissolve fade -> "Final Video", "Outro"
             -> Status: "Done" (C badge, auto PHT timestamp).

Usage:
    python run_sketch_to_real_reel.py --target chandeliers --max-items 1
    python generate_sketch_to_real_reel_pipeline.py --target pendant_lights --max-items 1
    python generate_sketch_to_real_reel_pipeline.py --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
import requests
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load environment
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.airtable_client import current_pht_timestamp
from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.auto_draw import extract_outline_preview, render_auto_draw_video
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.foreign_key import generate_foreign_key
from content_automation.item_tagger import tag_blended_image
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.shopify_client import ShopifyClient
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
from content_automation.scraping.products import existing_product_identities, identity_key

# --------------------------------------------------------------------------
# Constants & Defaults
# --------------------------------------------------------------------------

DEFAULT_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL") or os.getenv(
    "AIRTABLE_TABLE_ID_SKETCH_TO_DRAW_REEL", "tblSketchToRealReel"
)

TARGET_CONFIG: dict[str, dict[str, Any]] = {
    "chandeliers": {
        "name": "Chandeliers",
        "category": "chandeliers",
        "code": "CH",
        "env_key": "AIRTABLE_TABLE_ID_CHANDELIERS_SKETCH_TO_REAL_REEL",
        "fallback_env_keys": [
            "AIRTABLE_TABLE_ID_CHANDELIERS_SKETCH_TO_DRAW_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_DRAW_REEL",
        ],
        "default_table": "tblSketchToRealChandeliers",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_REAL_CHANDELIERS")
        or os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_DRAW_CHANDELIERS")
        or "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "prompt": "Generate me a photo a modern luxury living room with high ceilings, clean architecture, warm natural daylight",
    },
    "pendant_lights": {
        "name": "Pendant Lights",
        "category": "pendant_lights",
        "code": "PE",
        "env_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_SKETCH_TO_REAL_REEL",
        "fallback_env_keys": [
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_SKETCH_TO_DRAW_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_DRAW_REEL",
        ],
        "default_table": "tblSketchToRealPendants",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_REAL_PENDANTS")
        or os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_DRAW_PENDANTS")
        or "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
        "prompt": "Generate me a photo a modern dining room with dining table, elegant aesthetic, soft ambient lighting",
    },
    "floor_lamps": {
        "name": "Floor Lamps",
        "category": "floor_lamps",
        "code": "FL",
        "env_key": "AIRTABLE_TABLE_ID_FLOOR_LAMPS_SKETCH_TO_REAL_REEL",
        "fallback_env_keys": [
            "AIRTABLE_TABLE_ID_FLOOR_LAMPS_SKETCH_TO_DRAW_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_DRAW_REEL",
        ],
        "default_table": "tblSketchToRealFloorLamps",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_REAL_FLOOR_LAMPS")
        or os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_DRAW_FLOOR_LAMPS")
        or "b1641228-beec-4823-8d01-1de3eec8410d",
        "prompt": "Generate me a modern living room with lounge seating area, empty corner for standing floor lamp",
    },
    "table_lamps": {
        "name": "Table Lamps",
        "category": "table_lamps",
        "code": "TL",
        "env_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_SKETCH_TO_REAL_REEL",
        "fallback_env_keys": [
            "AIRTABLE_TABLE_ID_TABLE_LAMPS_SKETCH_TO_DRAW_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_DRAW_REEL",
        ],
        "default_table": "tblSketchToRealTableLamps",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_REAL_TABLE_LAMPS")
        or os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_DRAW_TABLE_LAMPS")
        or "fb2487fb-2895-4d2c-9758-805aaf1bac69",
        "prompt": "Generate me a modern bedroom with nightstand bedside table, warm contemporary interior",
    },
    "ceiling_mounted": {
        "name": "Ceiling Mounted",
        "category": "ceiling_lights",
        "code": "CM",
        "env_key": "AIRTABLE_TABLE_ID_CEILING_MOUNTED_SKETCH_TO_REAL_REEL",
        "fallback_env_keys": [
            "AIRTABLE_TABLE_ID_CEILING_MOUNTED_SKETCH_TO_DRAW_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_REAL_REEL",
            "AIRTABLE_TABLE_ID_SKETCH_TO_DRAW_REEL",
        ],
        "default_table": "tblSketchToRealCeilingMounted",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_REAL_CHANDELIERS")
        or os.getenv("KREA_MOODBOARD_ID_SKETCH_TO_DRAW_CHANDELIERS")
        or "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "prompt": "Generate me a modern hallway or contemporary bedroom ceiling, minimalist architectural space",
    },
}

# Airtable Field Names (Streamlined Schema: NO Price, NO Caption, NO Music)
FIELD_FK_ID = "Foreign Key ID"
FIELD_ID = "ID"
FIELD_DATE_GENERATED = "Date and Time Generated"
FIELD_STATUS = "Status"
FIELD_FURNITURE = "Furniture Item"
FIELD_SKU = "SKU"
FIELD_ITEM_NAME = "Item Name"
FIELD_CATEGORY = "Category"
FIELD_INTERIOR = "Room Interior"
FIELD_INTERIOR_PROMPT = "Interior Prompt"
FIELD_BLEND_PROMPT = "Blending Prompt"
FIELD_BLENDED_IMAGE = "Blended Image"
FIELD_BLENDED_TAGGED = "Blended Image with Name text"
FIELD_SKETCH_IMAGE = "Sketch Image"
FIELD_HEADLINE = "Reel Headline"
FIELD_THUMBNAIL_TEXT = "Thumbnail with Generated Text"
FIELD_RAW_VIDEO = "Raw Video"
FIELD_OUTRO = "Outro"
FIELD_FINAL_VIDEO = "Final Video"

# Status values
STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"

# Outro assets
OUTRO_CANDIDATES = [
    REPO_ROOT / "assets" / "outro_layout.jpg",
    REPO_ROOT / "Outro for All Reels" / "Outro.jpg",
    Path("assets/outro_layout.jpg"),
    Path("Outro for All Reels/Outro.jpg"),
]

# Audio candidates (optional local audio, NO ElevenLabs calls)
AUDIO_CANDIDATES = [
    REPO_ROOT / "assets" / "audio.mp3",
    REPO_ROOT / "assets" / "jazz_music.mp3",
    REPO_ROOT / "assets" / "soundtrack.mp3",
]

# Font paths
FONT_BOLD_CANDIDATES = [
    REPO_ROOT / "content_automation" / "fonts" / "Poppins-Bold.ttf",
    REPO_ROOT / "python-content-script" / "Poppins-Bold.ttf",
    REPO_ROOT / "assets" / "Poppins-Bold.ttf",
]


class PipelineClients:
    def __init__(self, table_id: str):
        settings = load_settings()
        self.airtable = ScrapeAirtableClient(table_id=table_id)
        self.akeneo = AkeneoClient()
        self.fal = FalClient()
        self.krea = KreaClient()
        self.table_id = table_id


def resolve_font(size: int = 54) -> ImageFont.FreeTypeFont:
    for candidate in FONT_BOLD_CANDIDATES:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                pass
    return ImageFont.load_default()


def resolve_outro_file() -> Path:
    for p in OUTRO_CANDIDATES:
        if p.is_file():
            return p
    dummy = Path("output/temp_outro.jpg")
    dummy.parent.mkdir(parents=True, exist_ok=True)
    if not dummy.is_file():
        img = Image.new("RGB", (1080, 1920), color=(18, 18, 18))
        img.save(dummy, "JPEG")
    return dummy


def resolve_audio_file() -> Path | None:
    for p in AUDIO_CANDIDATES:
        if p.is_file():
            return p
    return None


# --------------------------------------------------------------------------
# PHASE 1: Akeneo Scraping & Shopify Catalog Verification (NO Price Field)
# --------------------------------------------------------------------------

def run_phase_1_scrape(
    clients: PipelineClients,
    target_key: str,
    max_items: int = 1,
    style: str = "modern",
) -> list[str]:
    """Scrape fresh active product, verify on Shopify, dedup across base, create brand-new row without price."""
    cfg = TARGET_CONFIG.get(target_key, TARGET_CONFIG["chandeliers"])
    category_slug = cfg["category"]
    print(f"\n[PHASE 1] Scraping {max_items} fresh product(s) for {cfg['name']} (Category: {category_slug})...")

    # 1. Base-wide deduplication check
    base_filenames: set[str] = set()
    base_names: set[str] = set()
    base_skus: set[str] = set()
    try:
        base_filenames, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
        print(f"  [OK] Base-wide dedup: {len(base_skus)} existing SKU(s), {len(base_names)} title(s) registered.")
    except Exception as e:
        print(f"  [WARN] Base-wide dedup notice: {e}")

    # 2. Existing identities in current table + compute next row ID for Foreign Key
    existing_record_count = 0
    max_row_id = 0
    try:
        records = clients.airtable.list_records([FIELD_SKU, FIELD_ITEM_NAME, FIELD_FURNITURE, FIELD_ID, FIELD_FK_ID])
        existing_record_count = len(records)
        for r in records:
            f = r.get("fields", {})
            if f.get(FIELD_SKU):
                base_skus.add(str(f[FIELD_SKU]).strip().lower())
            if f.get(FIELD_ITEM_NAME):
                base_names.add(str(f[FIELD_ITEM_NAME]).strip().lower())
            val_id = f.get(FIELD_ID)
            if isinstance(val_id, (int, float)):
                max_row_id = max(max_row_id, int(val_id))
            att = f.get(FIELD_FURNITURE)
            if isinstance(att, list):
                for a in att:
                    if isinstance(a, dict) and a.get("filename"):
                        base_filenames.add(identity_key(a["filename"]))
    except Exception:
        pass

    # 3. Shopify published catalog verification
    shopify_index = None
    try:
        print("  [INFO] Verifying live published catalog from Shopify (homecartel.net)...")
        shopify = ShopifyClient()
        shopify_index = shopify.load_published_identities()
        print(f"  [OK] Shopify Index loaded: {len(shopify_index.skus)} active published SKU(s).")
    except Exception as e:
        print(f"  [WARN] Shopify index skipped: {e}")

    # 4. Search Akeneo
    print(f"  [INFO] Querying Akeneo PIM for active items in '{category_slug}'...")
    candidates = clients.akeneo.search_products(
        category=category_slug,
        limit=50,
        style=style,
    )
    print(f"  [INFO] Akeneo returned {len(candidates)} raw candidate(s).")

    created_records: list[str] = []
    current_counter = max_row_id if max_row_id > 0 else existing_record_count

    for cand in candidates:
        if len(created_records) >= max_items:
            break

        sku = (cand.sku or "").strip()
        item_name = (cand.name or "").strip()
        clean_name = split_item_name(item_name)
        norm_sku = sku.lower()
        norm_name = clean_name.lower()

        if not sku or not cand.media_code:
            continue

        # Dedup check
        if norm_sku in base_skus or norm_name in base_names:
            continue

        # Shopify active check
        if shopify_index and not shopify_index.contains(sku, clean_name):
            print(f"  [SKIP] SKU '{sku}' ({clean_name}) is not active on Shopify.")
            continue

        # Download product media cutout
        try:
            temp_cutout = clients.akeneo.download_media(cand.media_code)
        except Exception as err:
            print(f"  [WARN] Failed to download media for {sku}: {err}")
            continue

        current_counter += 1
        # Generate Foreign Key ID: STR-REEL-<CODE>-<ROW_ID>
        fk_id = generate_foreign_key(
            table_id=clients.table_id,
            row_id=current_counter,
            table_name=f"Sketch to Real {cfg['name']}",
        )

        # Create BRAND-NEW row in Airtable (STRICTLY NO PRICE FIELD)
        row_fields: dict[str, Any] = {
            FIELD_STATUS: STATUS_IN_PROGRESS,
            FIELD_FK_ID: fk_id,
            FIELD_SKU: sku,
            FIELD_ITEM_NAME: clean_name,
            FIELD_CATEGORY: cfg["name"],
        }

        try:
            record_id = clients.airtable.create_record(row_fields)
        except Exception as err:
            print(f"  [ERROR] Failed to create Airtable record: {err}")
            continue

        # Upload product attachment
        filename = f"{sku}_{cand.media_code}.png"
        clients.airtable.upload_attachment(record_id, FIELD_FURNITURE, temp_cutout, filename)

        # Mark dedup sets
        base_skus.add(norm_sku)
        base_names.add(norm_name)
        created_records.append(record_id)
        print(f"  [OK] Created brand-new row {record_id} ({fk_id}) for '{clean_name}' (SKU: {sku}).")

    if not created_records:
        print(f"  [WARN] No new eligible products scraped for {category_slug}.")
    return created_records


# --------------------------------------------------------------------------
# PHASE 2: Krea Room Interior Generation (9:16)
# --------------------------------------------------------------------------

def run_phase_2_interior(
    clients: PipelineClients,
    record_id: str,
    target_key: str,
    custom_moodboard: str = "",
    custom_prompt: str = "",
) -> tuple[str, Path]:
    """Generate luxury 9:16 room interior via Krea AI (BEFORE scene for Auto Draw)."""
    cfg = TARGET_CONFIG.get(target_key, TARGET_CONFIG["chandeliers"])
    moodboard_id = (custom_moodboard or cfg["moodboard_id"]).strip()
    prompt = (custom_prompt or cfg["prompt"]).strip()

    print(f"\n[PHASE 2] Generating Krea luxury room interior for record {record_id}...")
    print(f"  Prompt: \"{prompt}\"")
    print(f"  Moodboard ID: {moodboard_id or 'None'}")

    krea_url = clients.krea.generate_image(
        prompt=prompt,
        moodboard_id=moodboard_id,
        aspect_ratio="9:16",
        resolution="1K",
    )
    print(f"  [OK] Krea generated interior: {krea_url[:70]}...")

    temp_interior = download_to_temp_file(krea_url, suffix=".jpg")
    clients.airtable.upload_attachment(record_id, FIELD_INTERIOR, temp_interior, f"krea_interior_{record_id}.jpg")
    clients.airtable.update_record(record_id, {
        FIELD_INTERIOR_PROMPT: prompt,
        FIELD_STATUS: "Interior Generated",
    })
    return krea_url, temp_interior


# --------------------------------------------------------------------------
# PHASE 3: Claude Sonnet 5 Vision Analysis (Blending Prompt & Headline ONLY)
# --------------------------------------------------------------------------

def run_phase_3_claude(
    clients: PipelineClients,
    record_id: str,
) -> dict[str, str]:
    """Claude Sonnet 5 writes Blending Prompt and 3-5 word Reel Headline. No caption, no sketch prompt."""
    print(f"\n[PHASE 3] Claude Sonnet 5 vision analysis for record {record_id}...")
    rec = clients.airtable.get_record(record_id)
    fields = rec.get("fields", {})

    sku = str(fields.get(FIELD_SKU) or "")
    item_name = str(fields.get(FIELD_ITEM_NAME) or "Lighting Fixture")
    category = str(fields.get(FIELD_CATEGORY) or "Lighting")

    interior_atts = fields.get(FIELD_INTERIOR) or []
    furniture_atts = fields.get(FIELD_FURNITURE) or []

    if not interior_atts or not furniture_atts:
        raise AutomationError(f"Record {record_id} missing Room Interior or Furniture Item attachments.")

    interior_url = interior_atts[0].get("url")
    furniture_url = furniture_atts[0].get("url")

    system_instruction = (
        "You are an expert luxury architectural lighting creative director for HomeCartel. "
        "Analyze the isolated lighting fixture cutout and the luxury empty room interior photo. "
        "Return ONLY a clean JSON object with the requested keys."
    )

    user_prompt = f"""Product Details:
- Name: {item_name}
- Category: {category}
- SKU: {sku}

Generate a JSON object with EXACTLY these 2 keys:
1. "blending_prompt": A highly specific instruction for Fal Nano Banana Pro to place this exact lighting fixture naturally into the room interior. Describe its physical positioning, suspension/mount, scale, and that it is fully turned on casting a warm ambient luxury glow.
2. "reel_headline": A punchy, luxury 3-to-5 word headline / hook for the reel cover (e.g. "From Sketch to Real", "The Art of Illumination", "Architect's Vision Realized").

Return ONLY the raw JSON object without markdown fences."""

    response_text = clients.fal.generate_claude_vision(
        prompt=user_prompt,
        image_urls=[furniture_url, interior_url],
        system_instruction=system_instruction,
    )

    clean_json = response_text.strip()
    clean_json = re.sub(r"^```(?:json)?", "", clean_json, flags=re.MULTILINE)
    clean_json = re.sub(r"```$", "", clean_json, flags=re.MULTILINE).strip()

    try:
        data = json.loads(clean_json)
    except Exception:
        data = {
            "blending_prompt": f"Install this {item_name} seamlessly into the room interior. It is installed and illuminated with a warm ambient golden glow.",
            "reel_headline": "From Sketch to Real",
        }

    updates: dict[str, Any] = {
        FIELD_BLEND_PROMPT: data.get("blending_prompt", ""),
        FIELD_HEADLINE: data.get("reel_headline", "From Sketch to Real"),
        FIELD_STATUS: "Prompt Generated",
    }
    clients.airtable.update_record(record_id, updates)
    print(f"  [OK] Saved Blending Prompt and Headline \"{updates[FIELD_HEADLINE]}\" to Airtable.")
    return data


# --------------------------------------------------------------------------
# PHASE 4: Fal Nano Banana Pro Photorealistic Room Blend & YOLO Tagging
# --------------------------------------------------------------------------

def run_phase_4_blend(
    clients: PipelineClients,
    record_id: str,
) -> tuple[str, Path]:
    """Blend product into room interior using Fal Nano Banana Pro (AFTER scene for Auto Draw)."""
    print(f"\n[PHASE 4] Nano Banana Pro photorealistic blend for record {record_id}...")
    rec = clients.airtable.get_record(record_id)
    fields = rec.get("fields", {})

    interior_atts = fields.get(FIELD_INTERIOR) or []
    furniture_atts = fields.get(FIELD_FURNITURE) or []
    blend_prompt = str(fields.get(FIELD_BLEND_PROMPT) or "").strip()
    item_name = str(fields.get(FIELD_ITEM_NAME) or "Lighting Fixture")

    if not interior_atts or not furniture_atts or not blend_prompt:
        raise AutomationError(f"Record {record_id} missing inputs for room blending.")

    interior_url = interior_atts[0].get("url")
    furniture_url = furniture_atts[0].get("url")

    # Generate blend
    blended_url = clients.fal.generate(
        prompt=blend_prompt,
        image_urls=[interior_url, furniture_url],
        aspect_ratio="9:16",
        resolution="1K",
        model="fal-ai/nano-banana-pro/edit",
    )
    print(f"  [OK] Nano Banana Pro blend produced: {blended_url[:70]}...")

    temp_blended = download_to_temp_file(blended_url, suffix=".jpg")
    clients.airtable.upload_attachment(record_id, FIELD_BLENDED_IMAGE, temp_blended, f"blended_{record_id}.jpg")

    # YOLO-World luxury floating product tagging
    try:
        print("  [INFO] Running YOLO-World item tagger on blended image...")
        tag_result = tag_blended_image(
            image_path=temp_blended,
            item_name=item_name,
            output_dir=Path(tempfile.gettempdir()),
        )
        if tag_result and tag_result.path.is_file():
            clients.airtable.upload_attachment(
                record_id,
                FIELD_BLENDED_TAGGED,
                tag_result.path,
                f"blended_tagged_{record_id}.jpg",
            )
            print(f"  [OK] Tagged blended variant attached to '{FIELD_BLENDED_TAGGED}'.")
    except Exception as e:
        print(f"  [WARN] YOLO item tagger notice: {e}")

    clients.airtable.update_record(record_id, {FIELD_STATUS: "Blended Image Generated"})
    return blended_url, temp_blended


# --------------------------------------------------------------------------
# PHASE 5: Auto Draw Outline Extraction & Cover Generation
# --------------------------------------------------------------------------

def run_phase_5_sketch(
    clients: PipelineClients,
    record_id: str,
    before_path: Path,
    after_path: Path,
) -> tuple[Path, Path]:
    """Extract outline preview via local Auto Draw Canny subtraction and generate Instagram cover."""
    print(f"\n[PHASE 5] Auto Draw outline extraction & thumbnail cover generation for record {record_id}...")
    rec = clients.airtable.get_record(record_id)
    fields = rec.get("fields", {})
    headline = str(fields.get(FIELD_HEADLINE) or "From Sketch to Real").strip()

    # 1. Local Auto Draw Edge Subtraction (BEFORE vs AFTER)
    outline_preview_path = Path(tempfile.gettempdir()) / f"sketch_outline_{record_id}.png"
    print("  [INFO] Extracting vector outline preview via Canny edge subtraction...")
    extract_outline_preview(
        before_path=before_path,
        after_path=after_path,
        output_path=outline_preview_path,
        color="#ad803d",
        line_width=1.2,
        target_width=1080,
    )
    print(f"  [OK] Auto Draw outline generated: {outline_preview_path}")

    clients.airtable.upload_attachment(
        record_id,
        FIELD_SKETCH_IMAGE,
        outline_preview_path,
        f"sketch_outline_{record_id}.png",
    )

    # 2. Local Pillow Cover: Dim outline slightly and stamp centered Poppins-Bold headline
    print(f"  [INFO] Stamping centered cover typography: \"{headline}\"...")
    cover_path = Path(tempfile.gettempdir()) / f"sketch_cover_{record_id}.jpg"
    with Image.open(outline_preview_path) as img:
        img = img.convert("RGB")
        if img.size != (1080, 1920):
            img = img.resize((1080, 1920), Image.Resampling.LANCZOS)

        # Subtle dimming for text readability
        enhancer = ImageEnhance.Brightness(img)
        cover_img = enhancer.enhance(0.85)

        draw = ImageDraw.Draw(cover_img)
        font = resolve_font(size=56)

        # Word wrap headline
        words = headline.split()
        lines: list[str] = []
        cur_line: list[str] = []
        for w in words:
            cur_line.append(w)
            bbox = font.getbbox(" ".join(cur_line))
            if bbox[2] - bbox[0] > 900:
                cur_line.pop()
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        total_text_height = len(lines) * 70
        start_y = 650 - (total_text_height // 2)

        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            w = bbox[2] - bbox[0]
            x = (1080 - w) // 2
            y = start_y + (i * 70)
            # Subtle drop shadow
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

        cover_img.save(cover_path, "JPEG", quality=95)

    clients.airtable.upload_attachment(
        record_id,
        FIELD_THUMBNAIL_TEXT,
        cover_path,
        f"cover_{record_id}.jpg",
    )
    clients.airtable.update_record(record_id, {FIELD_STATUS: "Sketch Generated"})
    print(f"  [OK] Cover attached to '{FIELD_THUMBNAIL_TEXT}'.")
    return outline_preview_path, cover_path


# --------------------------------------------------------------------------
# PHASE 6: Auto Draw Reveal Video Rendering (Real-time Line Drawing)
# --------------------------------------------------------------------------

def run_phase_6_video(
    clients: PipelineClients,
    record_id: str,
    before_path: Path,
    after_path: Path,
) -> Path:
    """Render real-time line-drawing reveal video via Auto Draw vector path tracing."""
    print(f"\n[PHASE 6] Auto Draw line-drawing reveal video rendering for record {record_id}...")
    raw_video_path = Path(tempfile.gettempdir()) / f"raw_video_{record_id}.mp4"

    render_auto_draw_video(
        before_path=before_path,
        after_path=after_path,
        output_path=raw_video_path,
        draw_seconds=4.5,
        transition_seconds=1.8,
        end_hold=2.0,
        color="#ad803d",
        line_width=1.2,
        target_width=1080,
        fps=30,
    )
    print(f"  [OK] Auto Draw reveal video compiled: {raw_video_path}")

    clients.airtable.upload_attachment(record_id, FIELD_RAW_VIDEO, raw_video_path, f"raw_video_{record_id}.mp4")
    clients.airtable.update_record(record_id, {FIELD_STATUS: "Video Generated"})
    return raw_video_path


# --------------------------------------------------------------------------
# PHASE 7: Local FFmpeg Outro Concatenation (Silent / Local Audio, Zero ElevenLabs)
# --------------------------------------------------------------------------

def run_phase_7_outro(
    clients: PipelineClients,
    record_id: str,
    raw_video_path: Path,
) -> Path:
    """Concatenate with HomeCartel outro card silently or with local audio (ZERO ElevenLabs calls)."""
    print(f"\n[PHASE 7] Final outro concatenation for record {record_id} (Zero ElevenLabs)...")
    outro_file = resolve_outro_file()
    audio_file = resolve_audio_file()

    final_video_path = Path(tempfile.gettempdir()) / f"final_reel_{record_id}.mp4"
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # Get raw video duration
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(raw_video_path),
    ]
    raw_dur = 8.5
    try:
        pr = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
        if pr.returncode == 0 and pr.stdout.strip():
            raw_dur = float(pr.stdout.strip())
    except Exception:
        pass

    outro_dur = 2.5
    total_dur = raw_dur + outro_dur
    fade_start = max(0.0, raw_dur - 0.5)

    filters = [
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,format=yuv420p,trim=duration={raw_dur:g},setpts=PTS-STARTPTS,fade=t=out:st={fade_start:g}:d=0.5[mainv]",
        f"[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,format=yuv420p,trim=duration={outro_dur:g},setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.5[outrov]",
        "[mainv][outrov]concat=n=2:v=1:a=0[v]",
    ]

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(raw_video_path),
        "-loop", "1", "-i", str(outro_file),
    ]

    if audio_file and audio_file.is_file():
        print(f"  [INFO] Muxing local soundtrack: {audio_file.name} (with outro audio fade)...")
        filters.append(
            f"[2:a]atrim=duration={total_dur:g},asetpts=PTS-STARTPTS,afade=t=out:st={total_dur - 1.5:g}:d=1.5[a]"
        )
        cmd.extend([
            "-stream_loop", "-1", "-i", str(audio_file),
            "-filter_complex", ";".join(filters),
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            str(final_video_path),
        ])
    else:
        # Silent video
        cmd.extend([
            "-filter_complex", ";".join(filters),
            "-map", "[v]",
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            str(final_video_path),
        ])

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise AutomationError(f"FFmpeg outro merge failed: {res.stderr[-500:]}")

    # Attach Outro & Final Video to Airtable
    clients.airtable.upload_attachment(record_id, FIELD_OUTRO, outro_file, "Outro.jpg")
    clients.airtable.upload_attachment(record_id, FIELD_FINAL_VIDEO, final_video_path, f"STR_{record_id}_final.mp4")

    # Set status to Done + auto stamp PHT timestamp
    clients.airtable.update_record(record_id, {
        FIELD_STATUS: STATUS_DONE,
        FIELD_DATE_GENERATED: current_pht_timestamp(),
    })
    print(f"  [SUCCESS] Record {record_id} reached Complete / Done (C badge)!")
    return final_video_path


# --------------------------------------------------------------------------
# Pipeline Orchestration
# --------------------------------------------------------------------------

def run_pipeline(
    target: str = "chandeliers",
    table_id: str | None = None,
    max_items: int = 1,
    mode: str = "all",
    record_id: str | None = None,
    moodboard_id: str = "",
    interior_prompt: str = "",
) -> None:
    """Execute end-to-end Sketch to Real Reel pipeline."""
    target_key = target.lower().strip()
    if target_key not in TARGET_CONFIG:
        target_key = "chandeliers"

    cfg = TARGET_CONFIG[target_key]

    resolved_table_id = table_id
    if not resolved_table_id:
        resolved_table_id = os.getenv(cfg["env_key"])
        if not resolved_table_id:
            for fallback_env in cfg.get("fallback_env_keys", []):
                val = os.getenv(fallback_env)
                if val:
                    resolved_table_id = val
                    break
        if not resolved_table_id:
            resolved_table_id = cfg.get("default_table", DEFAULT_TABLE_ID)

    print("=" * 70)
    print("HOMECARTEL MARKETING AI -- SKETCH TO REAL REEL PIPELINE")
    print("=" * 70)
    print(f"Target:          {cfg['name']} ({cfg['category']})")
    print(f"Table ID:        {resolved_table_id}")
    print(f"Mode:            {mode}")
    print(f"Max Items:       {max_items}")
    print("Zero-API Engine: Auto Draw (Canny Subtraction & Vector Reveal)")
    print("=" * 70)

    clients = PipelineClients(table_id=resolved_table_id)

    # Specific record re-render
    if record_id:
        records_to_process = [record_id]
        print(f"[TARGET] Processing explicitly targeted record: {record_id}")
    else:
        # MANDATORY OPERATING RULE: Scrape fresh products into BRAND-NEW rows
        records_to_process = run_phase_1_scrape(clients, target_key=target_key, max_items=max_items)

    for rec_id in records_to_process:
        print(f"\n>>> PROCESSING RECORD {rec_id} END-TO-END <<<")
        try:
            # Phase 2: Krea room interior (BEFORE scene)
            krea_url, interior_local = run_phase_2_interior(
                clients,
                record_id=rec_id,
                target_key=target_key,
                custom_moodboard=moodboard_id,
                custom_prompt=interior_prompt,
            )

            # Phase 3: Claude vision analysis (Blending Prompt & Headline ONLY)
            run_phase_3_claude(clients, record_id=rec_id)

            # Phase 4: Fal Nano Banana Pro room blend (AFTER scene) + YOLO tagging
            blended_url, blended_local = run_phase_4_blend(clients, record_id=rec_id)

            # Phase 5: Auto Draw outline extraction & cover generation
            outline_path, cover_path = run_phase_5_sketch(
                clients,
                record_id=rec_id,
                before_path=interior_local,
                after_path=blended_local,
            )

            # Phase 6: Auto Draw reveal video rendering
            raw_video_path = run_phase_6_video(
                clients,
                record_id=rec_id,
                before_path=interior_local,
                after_path=blended_local,
            )

            # Phase 7: Local FFmpeg Outro & Audio Muxing (Silent / Local Audio, Zero ElevenLabs)
            final_video_path = run_phase_7_outro(
                clients,
                record_id=rec_id,
                raw_video_path=raw_video_path,
            )

            print(f"\n>>> COMPLETED RECORD {rec_id} SUCCESSFULLY! <<<")
            print(f"Final Video: {final_video_path}")
        except Exception as e:
            print(f"\n[ERROR] Pipeline failed on record {rec_id}: {e}")
            try:
                clients.airtable.update_record(rec_id, {FIELD_STATUS: "For Manual"})
            except Exception:
                pass
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="HomeCartel Sketch to Real Reel Pipeline")
    parser.add_argument(
        "--target",
        choices=["chandeliers", "pendant_lights", "floor_lamps", "table_lamps", "ceiling_mounted"],
        default="chandeliers",
        help="Target lighting category fixture",
    )
    parser.add_argument("--table-id", default="", help="Airtable Table ID override")
    parser.add_argument("--max-items", type=int, default=1, help="Number of fresh products to scrape & process")
    parser.add_argument("--mode", default="all", help="Pipeline execution mode (default: all)")
    parser.add_argument("--record-id", default=None, help="Explicit record ID to re-process (skips scrape)")
    parser.add_argument("--moodboard-id", default="", help="Custom Krea moodboard ID")
    parser.add_argument("--interior-prompt", default="", help="Custom Krea interior prompt override")

    args = parser.parse_args()

    run_pipeline(
        target=args.target,
        table_id=args.table_id or None,
        max_items=args.max_items,
        mode=args.mode,
        record_id=args.record_id,
        moodboard_id=args.moodboard_id,
        interior_prompt=args.interior_prompt,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
