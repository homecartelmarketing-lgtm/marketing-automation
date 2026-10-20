#!/usr/bin/env python3
"""Virtual Staging Reel Automation Pipeline (9:16 Vertical Video).

Transforms an empty luxury room into a photorealistic, fully-staged living room
using Fal AI Kling 3.0 Pro's start/end frame interpolation, featuring a HomeCartel
luxury chandelier dropping and settling into place with realistic gravity, physics,
and lighting.

Phases (the log prints ``[PHASE n/7]`` markers that the Studio reads):
---------------------------------------------------------------------
    Phase 1  Scrape 1 fresh active chandelier (Akeneo with base-wide dedup
             + strict Shopify Active & Published check)
             -> Furniture Item, Item Name, SKU, Category. Status -> "Standby".
    Phase 2  Generate 9:16 luxury room interior via Krea AI (krea-2-medium, 1K)
             using configurable moodboard and interior prompt
             -> Room Interior, Interior Prompt, Moodboard ID. Status -> "Interior Generated".
    Phase 3  Claude Sonnet 5 vision analyzes room interior and chandelier cutout
             to generate realistic ceiling mount & lighting prompt
             -> Blending Prompt. Status -> "Prompt Generated".
    Phase 4  Fal Nano Banana Pro blends the chandelier into the luxury room
             -> Fully Staged Room. Status -> "Blended Image Generated".
    Phase 5  Claude Sonnet 5 vision creates stripping instructions; Nano Banana Pro
             inpaints & removes all furniture to produce pixel-matched empty room
             -> Emptying Prompt, Empty Room Interior. Status -> "Empty Room Generated".
    Phase 6  Fal AI Kling 3.0 Pro (fal-ai/kling-video/v3/pro/image-to-video)
             Start Frame: Empty Room Interior, End Frame: Fully Staged Room, Duration: 10s
             -> Video Prompt, Raw Video. Status -> "Video Generated".
    Phase 7  Local Pillow product name pill overlay + HomeCartel Outro card (2.5s)
             + reference audio track (assets/virtual_staging_track.mp3) muxing
             + Claude Instagram caption
             -> Outro, Caption Generated, Final Video. Status -> "Done" + PHT timestamp.
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

from dotenv import load_dotenv
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.airtable_client import current_pht_timestamp
from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.caption import CAPTION_FIELD, generate_caption
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.foreign_key import generate_foreign_key
from content_automation.krea_client import KreaClient
from content_automation.media import download_url_to_temp_file
from content_automation.shopify_client import ShopifyClient
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
from content_automation.scraping.products import existing_product_identities, identity_key, product_item

# --------------------------------------------------------------------------
# Constants & Defaults
# --------------------------------------------------------------------------

DEFAULT_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_VIRTUAL_STAGING_REEL", "tblPYG5Ed4XURecu6")
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_VIRTUAL_STAGING_REEL"

DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_VIRTUAL_STAGING_REEL", "").strip()
    or "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3"
)
DEFAULT_INTERIOR_PROMPT = (
    os.getenv("PROMPT_VIRTUAL_STAGING_REEL", "").strip()
    or "Generate me a photo of a modern luxury living room with high ceilings, large windows, architectural styling, natural daylight, warm aesthetic, high end furniture"
)

CATEGORY_SLUG = "chandeliers"
CATEGORY_NAME = "Chandeliers"
CATEGORY_CODE = "SET"

ASPECT_RATIO = "9:16"
RESOLUTION = "1K"

CLAUDE_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"
KLING_MODEL = "fal-ai/kling-video/v3/pro/image-to-video"

# Reference audio and outro assets
AUDIO_PATH = REPO_ROOT / "assets" / "virtual_staging_track.mp3"
OUTRO_CANDIDATES = [
    REPO_ROOT / "assets" / "outro_layout.jpg",
    Path("assets/outro_layout.jpg"),
    REPO_ROOT / "Outro for All Reels" / "Outro.jpg",
]

FONT_CANDIDATES = [
    REPO_ROOT / "content_automation" / "fonts" / "Poppins-Bold.ttf",
    REPO_ROOT / "content_automation" / "fonts" / "Poppins-Medium.ttf",
    REPO_ROOT / "content_automation" / "fonts" / "Poppins-Regular.ttf",
]

# Airtable status constants
STATUS_STANDBY = "Standby"
STATUS_IN_PROGRESS = "In progress"
STATUS_EMPTY_ROOM_UPLOADED = "Empty Room Uploaded"
STATUS_INTERIOR_GENERATED = "Interior Generated"
STATUS_PROMPT_GENERATED = "Prompt Generated"
STATUS_BLENDED_GENERATED = "Blended Image Generated"
STATUS_EMPTY_ROOM_GENERATED = "Empty Room Generated"
STATUS_VIDEO_GENERATED = "Video Generated"
STATUS_DONE = "Done"

STATUS_CHOICES = [
    STATUS_STANDBY,
    STATUS_IN_PROGRESS,
    STATUS_EMPTY_ROOM_UPLOADED,
    STATUS_INTERIOR_GENERATED,
    STATUS_PROMPT_GENERATED,
    STATUS_BLENDED_GENERATED,
    STATUS_EMPTY_ROOM_GENERATED,
    STATUS_VIDEO_GENERATED,
    STATUS_DONE,
    "Scheduled",
    "Posted",
    "Discard",
    "For Manual",
]

# Field names
FIELD_FK = "Foreign Key ID"
FIELD_ID = "ID"
FIELD_STATUS = "Status"
FIELD_DATE_GENERATED = "Date and Time Generated"
FIELD_DATE_SCHEDULED = "Date and Time Scheduled"
FIELD_FURNITURE = "Furniture Item"
FIELD_ITEM_NAME = "Item Name"
FIELD_SKU = "SKU"
FIELD_CATEGORY = "Category"
FIELD_ROOM_INTERIOR = "Room Interior"
FIELD_INTERIOR_PROMPT = "Interior Prompt"
FIELD_MOODBOARD_ID = "Moodboard ID"
FIELD_BLENDING_PROMPT = "Blending Prompt"
FIELD_FULLY_STAGED = "Fully Staged Room"
FIELD_EMPTYING_PROMPT = "Emptying Prompt"
FIELD_EMPTY_ROOM = "Empty Room Interior"
FIELD_VIDEO_PROMPT = "Video Prompt"
FIELD_RAW_VIDEO = "Raw Video"
FIELD_OUTRO = "Outro"
FIELD_FINAL_VIDEO = "Final Video"
FIELD_CAPTION = CAPTION_FIELD
FIELD_SOURCE_MODE = "Source Mode"
FIELD_KLING_QUEUE = "Kling Queue Request"

REQUIRED_STANDARD_FIELDS: dict[str, str] = {
    FIELD_FK: "singleLineText",
    FIELD_ITEM_NAME: "singleLineText",
    FIELD_SKU: "singleLineText",
    FIELD_CATEGORY: "singleLineText",
    FIELD_FURNITURE: "multipleAttachments",
    FIELD_ROOM_INTERIOR: "multipleAttachments",
    FIELD_INTERIOR_PROMPT: "multilineText",
    FIELD_MOODBOARD_ID: "singleLineText",
    FIELD_BLENDING_PROMPT: "multilineText",
    FIELD_FULLY_STAGED: "multipleAttachments",
    FIELD_EMPTYING_PROMPT: "multilineText",
    FIELD_EMPTY_ROOM: "multipleAttachments",
    FIELD_VIDEO_PROMPT: "multilineText",
    FIELD_RAW_VIDEO: "multipleAttachments",
    FIELD_OUTRO: "multipleAttachments",
    FIELD_FINAL_VIDEO: "multipleAttachments",
    FIELD_CAPTION: "multilineText",
    FIELD_SOURCE_MODE: "singleLineText",
    FIELD_KLING_QUEUE: "multilineText",
}

UPLOAD_STAGING_INSTRUCTION = (
    "You are an expert luxury interior stylist and visual prompt engineer.\n"
    "Image 1 is an EMPTY room. Image 2 is a HomeCartel lighting fixture cutout: '{item_name}'.\n"
    "Write one image-edit prompt for Nano Banana Pro that furnishes THIS exact room and mounts THIS exact fixture.\n"
    "Furnish with: a main sofa, an area rug with a coffee table on it, a shelving cabinet against the right wall, "
    "wall art, a floor plant, pillows and a throw on the sofa, and small decor on the shelves and table. "
    "Match the room's architecture and style. Mount the fixture centered on the ceiling with a correct canopy and drop, lit warm (2700K).\n"
    "STRICT: keep the camera angle, framing, perspective, walls, windows, doors, floor material and daylight identical. "
    "Do not crop, zoom or re-frame. Realistic contact shadows and scale.\n"
    "Output ONLY the prompt text."
)

UPLOAD_KLING_PROMPT = (
    "Photorealistic interior, vertical video, one continuous shot. Slow, steady camera push-in throughout. "
    "The empty room holds still for a moment. First, the main sofa flies in from the left and lands softly with a slight bounce. "
    "Then the rug unrolls across the floor and the coffee table drops onto it. Next, the shelving cabinet slides in against the right "
    "wall and the chandelier lowers from the ceiling. Then wall art pops onto the wall, the plant rises into place, and pillows and a "
    "throw drop onto the sofa. Finally, small decor appears on the shelves and table, and everything settles. Each object moves quickly "
    "with motion blur and lands exactly in its final position. Walls, windows, floor and lighting never change. No people"
)

UPLOAD_KLING_NEGATIVE = (
    "blur, distort, low quality, shaky camera, cartoon, anime, text, watermark, deformed face, extra limbs"
)

AUTO_KLING_PROMPT = (
    "Turn the uploaded interior photo into a photorealistic empty-to-furnished room assembly animation. "
    "Use the uploaded photo as the finished-room target. Begin with the same room empty of movable furniture and decorations, "
    "then animate ONLY the objects visible in the photo into their original positions. Adapt automatically to any room type, layout "
    "and furniture style. Preserve the architecture, flooring, walls, windows, doors, permanent built-ins, lighting and color palette. "
    "Reconstruct plausible surfaces temporarily exposed behind removed objects. Never redesign the room or invent furniture. "
    "Create one continuous, satisfying self-furnishing sequence without people. Bring large furniture into place with short, smooth "
    "downward drops and subtle weighted settling. Keep furniture complete, including legs, upholstery, seat cushions and mattresses. "
    "Unfurl any rug before furniture resting on it lands. Add smaller decor, accent pieces, wall art, tabletop items and lighting "
    "after major furniture settles. Maintain physically plausible stacking, support and gravity. Ensure every object comes to rest "
    "in its exact location, orientation, scale and material appearance from the target photo. Keep camera angle, focal length, "
    "perspective and room geometry perfectly locked to the target photo. Maintain the identical lighting scheme, direction, intensity "
    "and shadow colors throughout. Keep shadows and reflections soft, grounded and consistent with the landing objects. Never introduce "
    "people, limbs, tools, motion blur streaks or unrelated props. Fixed tripod shot matching the target photo. Static framing, zero pan, "
    "zero tilt, zero zoom, zero camera drift. A seamless, photorealistic room assembly animation where an empty room transforms precisely "
    "into the uploaded finished-room photo."
)

AUTO_KLING_NEGATIVE = (
    "people, hands, workers, tools, scaffolding, construction, camera movement, panning, tilting, zooming, camera shake, "
    "warping, shifting walls, changing windows, morphing architecture, flickering lighting, fluctuating exposure, disappearing "
    "objects, duplicate furniture, floating items, clipping meshes, deformed legs, low resolution, cartoonish effects, CGI look, "
    "jerky motion, abrupt cuts, unfinished frames"
)


def clean_override(val: str | None) -> str | None:
    if not val:
        return None
    s = val.strip()
    if s.lower() in ("", "none", "null", "undefined"):
        return None
    return s


def resolve_upload_kling_prompt() -> str:
    override = clean_override(os.getenv("KLING_PROMPT_VIRTUAL_STAGING_REEL"))
    return override or UPLOAD_KLING_PROMPT


def resolve_upload_kling_negative() -> str:
    override = clean_override(os.getenv("KLING_NEGATIVE_PROMPT_VIRTUAL_STAGING_REEL"))
    return override or UPLOAD_KLING_NEGATIVE


def build_kling_payload(
    start_image_url: str,
    end_image_url: str,
    prompt: str,
    negative_prompt: str,
) -> dict[str, Any]:
    return {
        "start_image_url": start_image_url,
        "end_image_url": end_image_url,
        "prompt": prompt,
        "duration": "10",
        "generate_audio": False,
        "negative_prompt": negative_prompt,
    }


# --------------------------------------------------------------------------
# Clients Helper
# --------------------------------------------------------------------------


class Clients:
    def __init__(self, table_id: str | None = None) -> None:
        settings = load_settings()
        settings.require({"airtable", "fal", "krea", "akeneo"})

        self.table_id = table_id or DEFAULT_TABLE_ID
        self.airtable = ScrapeAirtableClient(
            token=settings.airtable_token,
            base_id=settings.airtable_base_id,
            table_id=self.table_id,
        )
        self.akeneo = AkeneoClient(
            host=settings.akeneo_host,
            client_id=settings.akeneo_client_id,
            secret=settings.akeneo_secret,
            username=settings.akeneo_username,
            password=settings.akeneo_password,
            channel_name=os.getenv("CHANNEL_NAME", ""),
        )
        self.fal = FalClient(api_key=settings.fal_key)
        self.krea = KreaClient(token=settings.krea_token, base_url=settings.krea_base_url)

        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Idempotently ensure all 21 fields exist with correct types."""
        try:
            self.airtable.ensure_fields(REQUIRED_STANDARD_FIELDS)
        except Exception as err:
            print(f"[WARN] Standard fields check returned: {err}")

        # Check options fields (ID, Status, Date fields)
        try:
            known = self.airtable.known_field_names(refresh=True)
            if FIELD_ID not in known:
                try:
                    self.airtable._request(
                        "POST",
                        self.airtable.fields_url,
                        json={"name": FIELD_ID, "type": "number", "options": {"precision": 0}},
                    )
                except Exception:
                    pass

            if FIELD_STATUS not in known:
                try:
                    self.airtable._request(
                        "POST",
                        self.airtable.fields_url,
                        json={
                            "name": FIELD_STATUS,
                            "type": "singleSelect",
                            "options": {"choices": [{"name": c} for c in STATUS_CHOICES]},
                        },
                    )
                except Exception:
                    pass

            date_options = {
                "dateFormat": {"name": "iso"},
                "timeFormat": {"name": "24hour"},
                "timeZone": "client",
            }
            for date_field in (FIELD_DATE_GENERATED, FIELD_DATE_SCHEDULED):
                if date_field not in known:
                    try:
                        self.airtable._request(
                            "POST",
                            self.airtable.fields_url,
                            json={"name": date_field, "type": "dateTime", "options": date_options},
                        )
                    except Exception:
                        pass
        except Exception as err:
            print(f"[WARN] Schema options check returned: {err}")


def resolve_font(size: int = 34) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
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


def get_first_attachment_url(fields: dict[str, Any], field_name: str) -> str | None:
    val = fields.get(field_name)
    if isinstance(val, list) and val:
        first = val[0]
        if isinstance(first, dict) and first.get("url"):
            return str(first["url"])
    return None


def download_attachment(url: str, dest_path: Path, timeout: int = 120) -> Path:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=timeout)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    return dest_path


# --------------------------------------------------------------------------
# Phase 1: Scrape Fresh Chandelier
# --------------------------------------------------------------------------


def phase1_scrape(clients: Clients, max_items: int = 1) -> list[str]:
    print(f"\n[PHASE 1/7] Akeneo Product Scrape & Shopify Catalog Cross-Verification...")
    created_records: list[str] = []

    # 1. Base-wide deduplication index
    print("  [INFO] Building base-wide deduplication index across all Airtable tables...")
    try:
        base_skus, base_names, base_filenames = fetch_all_base_existing_identities(
            clients.airtable,
        )
        print(f"  [OK] Base index: {len(base_skus)} SKU(s), {len(base_names)} name(s).")
    except Exception as err:
        print(f"  [WARN] Base-wide dedup lookup failed: {err}; continuing with local dedup.")
        base_filenames, base_names, base_skus = set(), set(), set()

    # 2. Local table records count & max row ID
    max_row_id = 0
    try:
        existing_records = clients.airtable.list_records(fields=[FIELD_ID, FIELD_SKU, FIELD_ITEM_NAME])
        for r in existing_records:
            f = r.get("fields", {})
            val_id = f.get(FIELD_ID)
            if isinstance(val_id, (int, float)):
                max_row_id = max(max_row_id, int(val_id))
    except Exception:
        existing_records = []

    # 3. Shopify published catalog verification
    shopify_index = None
    try:
        print("  [INFO] Verifying live published catalog from Shopify (homecartel.net)...")
        shopify = ShopifyClient()
        shopify_index = shopify.load_published_identities()
        print(f"  [OK] Shopify Index loaded: {len(shopify_index.skus)} active published SKU(s).")
    except Exception as err:
        print(f"  [WARN] Shopify index skipped: {err}")

    # 4. Search Akeneo for chandeliers
    print(f"  [INFO] Querying Akeneo PIM for active items in '{CATEGORY_SLUG}'...")
    query: dict[str, Any] = {
        "categories": [{"operator": "IN", "value": [CATEGORY_SLUG]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    raw_candidates = clients.akeneo.fetch_products(query)
    raw_candidates.sort(
        key=lambda x: str(x.get("updated") or x.get("created") or ""),
        reverse=True,
    )
    print(f"  [INFO] Akeneo returned {len(raw_candidates)} raw candidate(s).")

    candidates = []
    for raw in raw_candidates:
        item = product_item(raw)
        if item:
            candidates.append(item)

    current_counter = max_row_id if max_row_id > 0 else len(existing_records)

    for cand in candidates:
        if len(created_records) >= max_items:
            break

        sku = (cand.sku or "").strip()
        item_name = (cand.item_name or "").strip()
        clean_name, _ = split_item_name(item_name, fallback_product_type=CATEGORY_NAME)
        norm_sku = sku.lower()
        norm_name = clean_name.lower()

        if not sku or not cand.media_code:
            continue

        if norm_sku in base_skus or norm_name in base_names:
            continue

        if shopify_index and not shopify_index.contains(sku, clean_name):
            print(f"  [SKIP] SKU '{sku}' ({clean_name}) is not active & published on Shopify.")
            continue

        # Download product media cutout
        try:
            temp_cutout = clients.akeneo.download_media(cand.media_code)
        except Exception as err:
            print(f"  [WARN] Failed to download media for {sku}: {err}")
            continue

        current_counter += 1
        row_id_val = current_counter
        fk_id = generate_foreign_key(clients.table_id, row_id_val, "Virtual Staging Reel")

        new_fields = {
            FIELD_ITEM_NAME: clean_name,
            FIELD_SKU: sku,
            FIELD_CATEGORY: CATEGORY_SLUG,
            FIELD_STATUS: STATUS_STANDBY,
        }
        id_info = clients.airtable.table_fields().get(FIELD_ID, {})
        if id_info.get("type") != "autoNumber":
            new_fields[FIELD_ID] = row_id_val
            new_fields[FIELD_FK] = fk_id

        print(f"  [INFO] Creating new row: {sku} - {clean_name}...")
        try:
            record_id = clients.airtable.create_record(new_fields)
            clients.airtable.upload_attachment(
                record_id,
                FIELD_FURNITURE,
                temp_cutout,
                filename=f"{sku}_{cand.media_code}.png",
            )
            created_records.append(record_id)
            print(f"  [OK] Row {record_id} created successfully with product cutout.")
            base_skus.add(norm_sku)
            base_names.add(norm_name)
        except Exception as err:
            print(f"  [ERROR] Failed to create Airtable row: {err}")
            continue

    return created_records


# --------------------------------------------------------------------------
# Phase 2: Krea Luxury Interior Generation
# --------------------------------------------------------------------------


def phase2_interior(
    clients: Clients,
    record_id: str,
    fields: dict[str, Any],
    moodboard_id: str,
    interior_prompt: str,
) -> str:
    print(f"\n[PHASE 2/7] Krea Luxury Interior Generation for record {record_id}...")
    existing_url = get_first_attachment_url(fields, FIELD_ROOM_INTERIOR)
    if existing_url:
        print(f"  [SKIP] {FIELD_ROOM_INTERIOR} already attached.")
        return existing_url

    mb_id = moodboard_id or str(fields.get(FIELD_MOODBOARD_ID) or "").strip() or DEFAULT_MOODBOARD_ID
    prompt_txt = interior_prompt or str(fields.get(FIELD_INTERIOR_PROMPT) or "").strip() or DEFAULT_INTERIOR_PROMPT

    print(f"  [INFO] Generating 9:16 interior with Krea AI (moodboard: {mb_id[:8]}...)...")
    url = clients.krea.generate(
        prompt=prompt_txt,
        aspect_ratio=ASPECT_RATIO,
        resolution=RESOLUTION,
        moodboard_id=mb_id,
    )
    if not url:
        raise AutomationError("Krea AI failed to return a room interior image URL")

    # Download to temp file and upload attachment
    temp_interior = Path(tempfile.gettempdir()) / f"interior_{record_id}.jpg"
    download_attachment(url, temp_interior)

    clients.airtable.upload_attachment(record_id, FIELD_ROOM_INTERIOR, temp_interior, f"interior_{record_id}.jpg")
    clients.airtable.update_record(
        record_id,
        {
            FIELD_INTERIOR_PROMPT: prompt_txt,
            FIELD_MOODBOARD_ID: mb_id,
            FIELD_STATUS: STATUS_INTERIOR_GENERATED,
        },
    )
    print(f"  [OK] Room interior uploaded. Status -> '{STATUS_INTERIOR_GENERATED}'.")
    fields[FIELD_ROOM_INTERIOR] = [{"url": url}]
    return url


def phase2_upload(clients: Clients, record_id: str, fields: dict[str, Any], empty_room_url: str) -> str:
    print(f"\n[PHASE 2/7] Ingesting Uploaded Empty Room Interior for record {record_id}...")
    fal_url = clients.fal.ensure_fal_url(empty_room_url, filename=f"empty_room_{record_id}.jpg")

    temp_empty = Path(tempfile.gettempdir()) / f"empty_room_{record_id}.jpg"
    download_attachment(fal_url, temp_empty)

    clients.airtable.upload_attachment(record_id, FIELD_EMPTY_ROOM, temp_empty, f"empty_room_{record_id}.jpg")
    clients.airtable.upload_attachment(record_id, FIELD_ROOM_INTERIOR, temp_empty, f"empty_room_{record_id}.jpg")
    clients.airtable.update_record(
        record_id,
        {
            FIELD_STATUS: STATUS_EMPTY_ROOM_UPLOADED,
            FIELD_SOURCE_MODE: "Upload",
        },
    )
    print(f"  [OK] Empty room attached to both {FIELD_EMPTY_ROOM} and {FIELD_ROOM_INTERIOR}.")
    print(f"       Status -> '{STATUS_EMPTY_ROOM_UPLOADED}', {FIELD_SOURCE_MODE} -> 'Upload'.")
    fields[FIELD_EMPTY_ROOM] = [{"url": fal_url}]
    fields[FIELD_ROOM_INTERIOR] = [{"url": fal_url}]
    fields[FIELD_SOURCE_MODE] = "Upload"
    return fal_url


# --------------------------------------------------------------------------
# Phase 3: Claude Sonnet 5 Blending Prompt Generation
# --------------------------------------------------------------------------


def phase3_blending_prompt(clients: Clients, record_id: str, fields: dict[str, Any]) -> str:
    print(f"\n[PHASE 3/7] Claude Sonnet 5 Blending Prompt Generation for record {record_id}...")
    existing = str(fields.get(FIELD_BLENDING_PROMPT) or "").strip()
    if existing:
        print(f"  [SKIP] {FIELD_BLENDING_PROMPT} already present.")
        return existing

    interior_url = get_first_attachment_url(fields, FIELD_ROOM_INTERIOR)
    cutout_url = get_first_attachment_url(fields, FIELD_FURNITURE)
    item_name = str(fields.get(FIELD_ITEM_NAME) or "luxury chandelier").strip()

    if not interior_url or not cutout_url:
        raise AutomationError("Missing interior or product cutout attachment for blending prompt generation")

    is_upload = str(fields.get(FIELD_SOURCE_MODE) or "").lower() == "upload"
    if is_upload:
        prompt_instruction = UPLOAD_STAGING_INSTRUCTION.format(item_name=item_name)
    else:
        prompt_instruction = (
            f"You are an expert luxury interior designer and visual prompt engineer.\n"
            f"Analyze this luxury room interior and the product cutout of the HomeCartel lighting fixture: '{item_name}'.\n"
            f"Write a precise, photorealistic image-to-image blending prompt for Fal Nano Banana Pro to install and mount "
            f"this exact chandelier on the ceiling in the visual center of the living room.\n\n"
            f"Guidelines:\n"
            f"1. Mount the chandelier securely to the ceiling with a realistic canopy and drop rod/chain appropriate to the ceiling height.\n"
            f"2. Illuminate the chandelier with warm ambient glow (2700K), casting soft realistic light downwards onto the room and furniture.\n"
            f"3. Ensure seamless integration: realistic shadows on the ceiling and walls, reflections in windows or polished surfaces, "
            f"and physically accurate scale.\n"
            f"4. Do NOT change or distort the existing room furniture, walls, or architecture.\n"
            f"Output ONLY the prompt text."
        )

    print("  [INFO] Requesting Claude Sonnet 5 vision blending prompt via Fal AI...")
    blending_prompt_text = clients.fal.generate_vision_prompt(
        image_urls=[interior_url, cutout_url],
        prompt=prompt_instruction,
        model=CLAUDE_MODEL,
    )
    blending_prompt_text = blending_prompt_text.strip().strip('"').strip("'")

    clients.airtable.update_record(
        record_id,
        {
            FIELD_BLENDING_PROMPT: blending_prompt_text,
            FIELD_STATUS: STATUS_PROMPT_GENERATED,
        },
    )
    print(f"  [OK] Blending prompt generated ({len(blending_prompt_text)} chars). Status -> '{STATUS_PROMPT_GENERATED}'.")
    fields[FIELD_BLENDING_PROMPT] = blending_prompt_text
    return blending_prompt_text


# --------------------------------------------------------------------------
# Phase 4: Fal Nano Banana Pro Room Blend
# --------------------------------------------------------------------------


def phase4_room_blend(clients: Clients, record_id: str, fields: dict[str, Any]) -> str:
    print(f"\n[PHASE 4/7] Fal Nano Banana Pro Photorealistic Room Blend for record {record_id}...")
    existing_url = get_first_attachment_url(fields, FIELD_FULLY_STAGED)
    if existing_url:
        print(f"  [SKIP] {FIELD_FULLY_STAGED} already attached.")
        return existing_url

    interior_url = get_first_attachment_url(fields, FIELD_ROOM_INTERIOR)
    cutout_url = get_first_attachment_url(fields, FIELD_FURNITURE)
    blending_prompt = str(fields.get(FIELD_BLENDING_PROMPT) or "").strip()

    if not interior_url or not cutout_url or not blending_prompt:
        raise AutomationError("Missing interior, cutout, or blending prompt for Phase 4 room blend")

    interior_fal_url = clients.fal.ensure_fal_url(interior_url, filename=f"interior_{record_id}.jpg")
    cutout_fal_url = clients.fal.ensure_fal_url(cutout_url, filename=f"cutout_{record_id}.png")

    print(f"  [INFO] Blending chandelier into room with Nano Banana Pro ({NANO_BANANA_MODEL})...")
    url = clients.fal.generate(
        prompt=blending_prompt,
        image_urls=[interior_fal_url, cutout_fal_url],
        aspect_ratio=ASPECT_RATIO,
        resolution=RESOLUTION,
        model=NANO_BANANA_MODEL,
    )
    if not url:
        raise AutomationError("Fal Nano Banana Pro failed to return blended image URL")

    temp_staged = Path(tempfile.gettempdir()) / f"staged_{record_id}.jpg"
    download_attachment(url, temp_staged)

    from content_automation.media import crop_to_reel
    cropped_staged = Path(tempfile.gettempdir()) / f"staged_916_{record_id}.jpg"
    try:
        crop_to_reel(temp_staged, cropped_staged)
        upload_path = cropped_staged
    except Exception as crop_err:
        print(f"  [WARN] crop_to_reel skipped on blended image ({crop_err}); using original")
        upload_path = temp_staged

    clients.airtable.upload_attachment(record_id, FIELD_FULLY_STAGED, upload_path, f"fully_staged_{record_id}.jpg")
    clients.airtable.update_record(record_id, {FIELD_STATUS: STATUS_BLENDED_GENERATED})
    print(f"  [OK] Fully staged room uploaded. Status -> '{STATUS_BLENDED_GENERATED}'.")
    fields[FIELD_FULLY_STAGED] = [{"url": url}]
    return url


# --------------------------------------------------------------------------
# Phase 5: Claude Empty-Room Conversion & Nano Banana Pro Stripping
# --------------------------------------------------------------------------


def phase5_empty_room_conversion(clients: Clients, record_id: str, fields: dict[str, Any]) -> str:
    if str(fields.get(FIELD_SOURCE_MODE) or "").lower() == "upload":
        print(f"\n[PHASE 5/7] Empty-room stripping SKIPPED (source=upload)")
        existing_url = get_first_attachment_url(fields, FIELD_EMPTY_ROOM)
        if existing_url:
            return existing_url
        raise AutomationError("Missing Empty Room Interior attachment for Phase 5 skip")

    print(f"\n[PHASE 5/7] Claude Empty-Room Conversion & Nano Banana Pro Stripping for record {record_id}...")
    existing_url = get_first_attachment_url(fields, FIELD_EMPTY_ROOM)
    if existing_url:
        print(f"  [SKIP] {FIELD_EMPTY_ROOM} already attached.")
        return existing_url

    staged_url = get_first_attachment_url(fields, FIELD_FULLY_STAGED)
    if not staged_url:
        raise AutomationError("Missing Fully Staged Room attachment for empty room conversion")

    # 1. Claude vision removal prompt
    emptying_prompt = str(fields.get(FIELD_EMPTYING_PROMPT) or "").strip()
    if not emptying_prompt:
        prompt_instruction = (
            "You are an expert architectural vision AI. Examine this fully furnished and staged luxury living room image.\n"
            "Write a concise, precise image-to-image editing prompt for Fal Nano Banana Pro to completely strip and empty this room.\n\n"
            "Strict Instructions:\n"
            "1. Remove ALL movable furniture and decor: sofa, sectional couch, coffee table, armchairs, area rugs, floor lamps, "
            "table lamps, bookcase, wall decor, pillows, throws, plants, and the chandelier hanging from the ceiling.\n"
            "2. PRESERVE the exact room architecture, camera angle, perspective, walls, windows, doors, baseboards, and ceiling beams.\n"
            "3. Reconstruct clean, continuous, bare hardwood/stone flooring across the entire room where furniture and rugs sat.\n"
            "4. Make the ceiling completely smooth and clean where the chandelier was mounted.\n"
            "5. Maintain identical natural daylight direction, exposure, and color palette.\n"
            "Output ONLY the editing prompt text."
        )
        print("  [INFO] Generating emptying prompt with Claude Sonnet 5 vision...")
        emptying_prompt = clients.fal.generate_vision_prompt(
            image_urls=[staged_url],
            prompt=prompt_instruction,
            model=CLAUDE_MODEL,
        ).strip().strip('"').strip("'")
        clients.airtable.update_record(record_id, {FIELD_EMPTYING_PROMPT: emptying_prompt})
        fields[FIELD_EMPTYING_PROMPT] = emptying_prompt
        print(f"  [OK] Emptying prompt created ({len(emptying_prompt)} chars).")

    # 2. Nano Banana Pro inpaint/edit to produce pixel-matched empty room
    print(f"  [INFO] Stripping room to bare architecture with Nano Banana Pro ({NANO_BANANA_MODEL})...")
    url = clients.fal.generate(
        prompt=emptying_prompt,
        image_urls=[staged_url],
        aspect_ratio=ASPECT_RATIO,
        resolution=RESOLUTION,
        model=NANO_BANANA_MODEL,
    )
    if not url:
        raise AutomationError("Fal Nano Banana Pro failed to return empty room image URL")

    temp_empty = Path(tempfile.gettempdir()) / f"empty_room_{record_id}.jpg"
    download_attachment(url, temp_empty)

    clients.airtable.upload_attachment(record_id, FIELD_EMPTY_ROOM, temp_empty, f"empty_room_{record_id}.jpg")
    clients.airtable.update_record(record_id, {FIELD_STATUS: STATUS_EMPTY_ROOM_GENERATED})
    print(f"  [OK] Empty room interior uploaded. Status -> '{STATUS_EMPTY_ROOM_GENERATED}'.")
    fields[FIELD_EMPTY_ROOM] = [{"url": url}]
    return url


# --------------------------------------------------------------------------
# Phase 6: Fal AI Kling 3.0 Pro Virtual Staging Video Generation
# --------------------------------------------------------------------------


def phase6_kling_video(clients: Clients, record_id: str, fields: dict[str, Any]) -> str:
    print(f"\n[PHASE 6/7] Fal AI Kling 3.0 Pro Virtual Staging Video Generation for record {record_id}...")
    existing_url = get_first_attachment_url(fields, FIELD_RAW_VIDEO)
    if existing_url:
        print(f"  [SKIP] {FIELD_RAW_VIDEO} already attached.")
        return existing_url

    empty_url = get_first_attachment_url(fields, FIELD_EMPTY_ROOM)
    staged_url = get_first_attachment_url(fields, FIELD_FULLY_STAGED)

    if not empty_url or not staged_url:
        raise AutomationError("Phase 6 requires both Empty Room Interior and Fully Staged Room attachments")

    start_fal_url = clients.fal.ensure_fal_url(empty_url, filename=f"empty_{record_id}.jpg")
    end_fal_url = clients.fal.ensure_fal_url(staged_url, filename=f"staged_{record_id}.jpg")

    is_upload = str(fields.get(FIELD_SOURCE_MODE) or "").lower() == "upload"
    if is_upload:
        prompt_text = resolve_upload_kling_prompt()
        neg_prompt_text = resolve_upload_kling_negative()
    else:
        prompt_text = AUTO_KLING_PROMPT
        neg_prompt_text = AUTO_KLING_NEGATIVE

    # Resume check: if Kling Queue Request exists and has status_url and response_url
    queue_data = None
    queue_raw = fields.get(FIELD_KLING_QUEUE)
    if queue_raw:
        try:
            queue_data = json.loads(queue_raw) if isinstance(queue_raw, str) else queue_raw
        except Exception:
            queue_data = None

    if queue_data and queue_data.get("status_url") and queue_data.get("response_url"):
        print("  [RESUME] Found existing Kling queue request. Resuming polling without re-submitting...")
        status_url = queue_data["status_url"]
        response_url = queue_data["response_url"]
    else:
        payload = build_kling_payload(start_fal_url, end_fal_url, prompt_text, neg_prompt_text)
        print(f"  [INFO] Submitting to Kling 3.0 Pro Queue ({KLING_MODEL})...")
        print(f"         Start Image (Empty):  {start_fal_url[:60]}...")
        print(f"         End Image (Staged):   {end_fal_url[:60]}...")
        print(f"         Duration: 10s | Audio: False")
        queue_res = clients.fal.submit_queue(KLING_MODEL, payload)
        queue_res["submitted_at"] = time.time()
        status_url = queue_res["status_url"]
        response_url = queue_res["response_url"]
        clients.airtable.update_record(
            record_id,
            {
                FIELD_KLING_QUEUE: json.dumps(queue_res),
                FIELD_VIDEO_PROMPT: prompt_text,
            },
        )
        fields[FIELD_KLING_QUEUE] = json.dumps(queue_res)
        fields[FIELD_VIDEO_PROMPT] = prompt_text

    t0 = time.time()

    def on_log(state: str, st_data: dict[str, Any]) -> None:
        elapsed = int(time.time() - t0)
        print(f"  [FAL AI] Kling status: {state} (elapsed {elapsed}s)")

    result = clients.fal.poll_queue_urls(
        status_url,
        response_url,
        interval=5.0,
        max_wait=1200.0,
        on_log=on_log,
    )
    video_url = (result.get("video") or {}).get("url") or ""
    if not video_url:
        raise AutomationError(f"Kling 3.0 Pro video generation failed to return a video URL: {result}")

    temp_video = Path(tempfile.gettempdir()) / f"raw_video_{record_id}.mp4"
    download_attachment(video_url, temp_video, timeout=180)

    try:
        clients.airtable.upload_attachment(record_id, FIELD_RAW_VIDEO, temp_video, f"raw_video_{record_id}.mp4", timeout=300.0)
    except Exception as upload_err:
        print(f"  [WARN] Base64 upload_attachment failed ({upload_err}); attaching video directly via URL...")
        clients.airtable.upload_attachment_url(record_id, FIELD_RAW_VIDEO, video_url, filename=f"raw_video_{record_id}.mp4")

    clients.airtable.update_record(record_id, {FIELD_STATUS: STATUS_VIDEO_GENERATED})
    print(f"  [OK] Raw video attached ({temp_video.stat().st_size:,} bytes). Status -> '{STATUS_VIDEO_GENERATED}'.")
    fields[FIELD_RAW_VIDEO] = [{"url": video_url}]
    return video_url


# --------------------------------------------------------------------------
# Phase 7: Local Pillow Tag, Outro Concatenation & Audio Muxing
# --------------------------------------------------------------------------


def render_branding_pill_overlay(item_name: str, output_path: Path) -> Path:
    """Renders a 1080x1920 RGBA transparent overlay with a sleek product branding pill."""
    overlay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_bold = resolve_font(size=32)
    font_brand = resolve_font(size=30)

    brand_text = "HomeCartel"
    separator = " — "
    display_title = item_name or "Modern Chandelier"
    full_text = f"{brand_text}{separator}{display_title}"

    # Measure text bounding box
    bbox = draw.textbbox((0, 0), full_text, font=font_bold)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Pill sizing & padding
    pad_x = 32
    pad_y = 16
    pill_w = text_w + (pad_x * 2)
    pill_h = text_h + (pad_y * 2)

    # Position: bottom left corner with 70px left margin, 120px bottom margin
    x0 = 70
    y0 = 1920 - 120 - pill_h
    x1 = x0 + pill_w
    y1 = y0 + pill_h

    # Semi-transparent dark luxury pill background
    pill_bg = (14, 14, 16, 210)
    pill_border = (255, 255, 255, 50)
    radius = pill_h // 2

    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=pill_bg, outline=pill_border, width=2)

    # Draw text in crisp white
    text_x = x0 + pad_x
    text_y = y0 + pad_y - 2
    draw.text((text_x, text_y), full_text, fill=(255, 255, 255, 245), font=font_bold)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path, "PNG")
    return output_path


def phase7_assemble_final_reel(clients: Clients, record_id: str, fields: dict[str, Any]) -> str:
    print(f"\n[PHASE 7/7] Local Pillow Branding Tag, Outro Concatenation & Audio Muxing for record {record_id}...")
    existing_url = get_first_attachment_url(fields, FIELD_FINAL_VIDEO)
    if existing_url:
        print(f"  [SKIP] {FIELD_FINAL_VIDEO} already attached.")
        return existing_url

    raw_video_url = get_first_attachment_url(fields, FIELD_RAW_VIDEO)
    if not raw_video_url:
        raise AutomationError("Missing Raw Video attachment for Phase 7 assembly")

    temp_raw = Path(tempfile.gettempdir()) / f"raw_video_{record_id}.mp4"
    if not temp_raw.is_file() or temp_raw.stat().st_size == 0:
        download_attachment(raw_video_url, temp_raw, timeout=180)

    item_name = str(fields.get(FIELD_ITEM_NAME) or "Modern Chandelier").strip()
    sku = str(fields.get(FIELD_SKU) or "").strip()

    # 1. Render branding pill PNG overlay
    pill_overlay_path = Path(tempfile.gettempdir()) / f"branding_pill_{record_id}.png"
    render_branding_pill_overlay(item_name, pill_overlay_path)

    # 2. Resolve Outro Card
    outro_file = resolve_outro_file()
    print(f"  [INFO] Outro card resolved: {outro_file}")
    if FIELD_OUTRO not in fields or not fields.get(FIELD_OUTRO):
        try:
            clients.airtable.upload_attachment(record_id, FIELD_OUTRO, outro_file, "outro_layout.jpg")
        except Exception:
            pass

    # 3. Resolve Reference Audio Track
    audio_file = AUDIO_PATH if AUDIO_PATH.is_file() else (REPO_ROOT / "assets" / "virtual_staging_track.mp3")
    has_audio = audio_file.is_file()
    if has_audio:
        print(f"  [INFO] Audio track resolved: {audio_file} ({audio_file.stat().st_size:,} bytes).")
    else:
        print("  [WARN] assets/virtual_staging_track.mp3 not found; rendering silent reel.")

    # 4. Measure raw video duration
    raw_dur = 10.0
    try:
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(temp_raw),
        ]
        pr = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
        if pr.returncode == 0 and pr.stdout.strip():
            raw_dur = float(pr.stdout.strip())
    except Exception:
        pass

    outro_dur = 2.5
    total_dur = raw_dur + outro_dur
    fade_start = max(0.0, raw_dur - 0.5)

    final_mp4_path = Path(tempfile.gettempdir()) / f"final_reel_{record_id}.mp4"
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # FFmpeg filtergraph:
    # [0:v] raw video, [1:v] pill overlay, [2:v] outro card image, [3:a] audio track
    filters = [
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,format=yuv420p,trim=duration={raw_dur:g},setpts=PTS-STARTPTS[vbase]",
        f"[vbase][1:v]overlay=0:0:enable='between(t,0,{raw_dur:g})'[vtagged]",
        f"[vtagged]fade=t=out:st={fade_start:g}:d=0.5[mainv]",
        f"[2:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,format=yuv420p,trim=duration={outro_dur:g},setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.5[outrov]",
        "[mainv][outrov]concat=n=2:v=1:a=0[v]",
    ]

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(temp_raw),
        "-i", str(pill_overlay_path),
        "-loop", "1", "-i", str(outro_file),
    ]

    if has_audio:
        filters.append(
            f"[3:a]atrim=duration={total_dur:g},asetpts=PTS-STARTPTS,afade=t=out:st={total_dur - 1.0:g}:d=1.0[a]"
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
            str(final_mp4_path),
        ])
    else:
        cmd.extend([
            "-filter_complex", ";".join(filters),
            "-map", "[v]",
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            str(final_mp4_path),
        ])

    print("  [INFO] Executing FFmpeg video assembly...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise AutomationError(f"FFmpeg assembly failed:\n{res.stderr[-800:]}")

    if not final_mp4_path.is_file() or final_mp4_path.stat().st_size == 0:
        raise AutomationError("FFmpeg completed but final reel MP4 was not created or is empty")

    print(f"  [OK] Final video assembled: {final_mp4_path.stat().st_size:,} bytes.")

    # 5. Generate universal Instagram caption via shared helper (never blocks Done)
    caption_text = str(fields.get(FIELD_CAPTION) or "").strip()
    if not caption_text:
        print("  [INFO] Generating Instagram caption with shared helper...")
        staged_url = get_first_attachment_url(fields, FIELD_FULLY_STAGED) or raw_video_url
        caption_text, used_fallback = generate_caption(
            clients.fal, item_name, "Chandelier", [staged_url] if staged_url else [], "chandeliers",
        )
        try:
            clients.airtable.update_record(record_id, {FIELD_CAPTION: caption_text})
        except Exception as err:
            print(f"  [WARN] Caption update failed: {err}")
        suffix = " (fallback)" if used_fallback else ""
        print(f"  [OK] Caption generated.{suffix}")

    # 6. Upload final video & complete row
    clients.airtable.upload_attachment(record_id, FIELD_FINAL_VIDEO, final_mp4_path, f"final_reel_{record_id}.mp4")
    now_pht = current_pht_timestamp()
    clients.airtable.update_record(
        record_id,
        {
            FIELD_STATUS: STATUS_DONE,
            FIELD_DATE_GENERATED: now_pht,
        },
    )
    print(f"  [OK] Row marked '{STATUS_DONE}' with timestamp {now_pht}.")
    return str(final_mp4_path)


# --------------------------------------------------------------------------
# Pipeline Orchestrator (Single Record)
# --------------------------------------------------------------------------


def process_record(
    clients: Clients,
    record_id: str,
    moodboard_id: str = "",
    prompt: str = "",
    mode: str = "all",
    source: str = "auto",
    empty_room_url: str = "",
) -> None:
    print(f"\n{'='*72}\n Processing Virtual Staging Reel: {record_id} (mode={mode}, source={source})\n{'='*72}")
    rec = clients.airtable.get_record(record_id)
    fields = rec.get("fields", {})

    status = str(fields.get(FIELD_STATUS) or "")
    if status in ("Scheduled", "Posted"):
        print(f"  [SKIP] Record {record_id} has protected status '{status}'.")
        return

    # Check if record already has Source Mode recorded
    if source == "upload" or str(fields.get(FIELD_SOURCE_MODE) or "").lower() == "upload":
        fields[FIELD_SOURCE_MODE] = "Upload"

    # Phase 2
    if mode in ("all", "interior"):
        if source == "upload":
            target_url = empty_room_url or get_first_attachment_url(fields, FIELD_EMPTY_ROOM)
            if not target_url:
                raise AutomationError("Upload mode requires an empty room URL")
            phase2_upload(clients, record_id, fields, target_url)
        else:
            phase2_interior(clients, record_id, fields, moodboard_id, prompt)

    # Phase 3
    if mode in ("all", "prompt"):
        phase3_blending_prompt(clients, record_id, fields)

    # Phase 4
    if mode in ("all", "blend"):
        phase4_room_blend(clients, record_id, fields)

    # Phase 5
    if mode in ("all", "empty"):
        if source == "upload" or str(fields.get(FIELD_SOURCE_MODE) or "").lower() == "upload":
            print(f"\n[PHASE 5/7] Empty-room stripping SKIPPED (source=upload)")
        else:
            phase5_empty_room_conversion(clients, record_id, fields)

    # Phase 6
    if mode in ("all", "video"):
        phase6_kling_video(clients, record_id, fields)

    # Phase 7
    if mode in ("all", "assemble"):
        phase7_assemble_final_reel(clients, record_id, fields)

    print(f"\n[DONE] Successfully processed {record_id} end-to-end.\n")


# --------------------------------------------------------------------------
# Main Execution Entrypoint
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Virtual Staging Reel Pipeline (9:16 Kling 3.0 Pro)")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help="Airtable table ID")
    parser.add_argument("--max-items", "--max-rows", dest="max_items", type=int, default=1, help="Number of rows to generate")
    parser.add_argument("--record-id", default="", help="Process specific record ID")
    parser.add_argument(
        "--mode",
        default="all",
        choices=["all", "scrape", "interior", "prompt", "blend", "empty", "video", "assemble"],
        help="Pipeline phase mode",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "upload"],
        default="auto",
        help="Source mode: 'auto' (Krea room generation) or 'upload' (user-provided empty room)",
    )
    parser.add_argument(
        "--empty-room-url",
        default="",
        help="Public/Fal URL of uploaded empty room photo (required when --source upload)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Inspect and validate without mutating Airtable")
    parser.add_argument("--moodboard-id", default="", help="Override Krea moodboard ID")
    parser.add_argument("--prompt", default="", help="Override Krea room interior prompt")

    args = parser.parse_args(argv)

    if args.source == "upload":
        if not args.empty_room_url:
            parser.error("--empty-room-url is required when --source upload")
        if args.max_items > 1:
            print(f"[WARN] --max-items was set to {args.max_items}, but upload mode only supports 1 item per run. Forcing max_items=1.")
            args.max_items = 1

    print("=" * 72)
    print(" HomeCartel AI Content Automation -- Virtual Staging Reel")
    print(f" Table ID:       {args.table_id}")
    print(f" Mode:           {args.mode}")
    print(f" Source:         {args.source}")
    print(f" Empty Room URL: {args.empty_room_url or '(none)'}")
    print(f" Max Items:      {args.max_items}")
    print(f" Record ID:      {args.record_id or '(scrape fresh)'}")
    print(f" Dry Run:        {args.dry_run}")
    print("=" * 72)

    clients = Clients(table_id=args.table_id)

    if args.dry_run:
        print("[DRY-RUN] Schema verified. Ready to scrape fresh chandelier.")
        return 0

    if args.record_id:
        process_record(
            clients,
            args.record_id,
            moodboard_id=args.moodboard_id,
            prompt=args.prompt,
            mode=args.mode,
            source=args.source,
            empty_room_url=args.empty_room_url,
        )
        return 0

    # Scrape fresh chandelier and process end-to-end
    created_ids = phase1_scrape(clients, max_items=args.max_items)
    if not created_ids:
        print("[WARN] No new chandeliers scraped or available.")
        return 0

    if args.mode == "scrape":
        print(f"[OK] Scraped {len(created_ids)} row(s). Exiting as requested by mode='scrape'.")
        return 0

    for rid in created_ids:
        process_record(
            clients,
            rid,
            moodboard_id=args.moodboard_id,
            prompt=args.prompt,
            mode=args.mode,
            source=args.source,
            empty_room_url=args.empty_room_url,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
