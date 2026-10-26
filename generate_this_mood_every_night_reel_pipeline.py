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
from content_automation.config import Settings, load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.foreign_key import generate_foreign_key
from content_automation.item_tagger import tag_blended_image
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename
from content_automation.prompts.scale import measurement_for_slot, product_type_for_slot, scale_clause
from content_automation.scale_guard import (
    blend_with_scale_guard,
    ensure_scale_fields,
    write_scale_fields,
)
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
PRODUCT_TYPE_FIELDS: dict[int, str] = {s: f"Product Type{s}" for s in SLOTS}
MEASUREMENT_FIELDS: dict[int, str] = {s: f"Measurement{s}" for s in SLOTS}
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
    | set(PRODUCT_TYPE_FIELDS.values())
    | set(MEASUREMENT_FIELDS.values())
    | set(INTERIOR_FIELDS.values())
    | set(INTERIOR_PROMPT_FIELDS.values())
    | set(INTERIOR_ANALYSIS_FIELDS.values())
    | set(GENERATED_PROMPT_FIELDS.values())
    | set(BLENDED_FIELDS.values())
    | set(KLING_FIELDS.values())
)

# Typography & Video specifications
SHOT_DURATION = 1.35  # seconds per shot
TOTAL_SHOTS_DURATION = 9.45  # 7 * 1.35s
TOTAL_REEL_DURATION = TOTAL_SHOTS_DURATION
OUTRO_DURATION = 2.5  # seconds for HomeCartel outro card
CENTER_OVERLAY_TEXT = "this mood every night"

TITLE_FONT_SIZE = 22
TYPE_FONT_SIZE = 19
TAG_RIGHT_MARGIN = 180
TAG_BOTTOM_MARGIN = 320
TAG_LINE_SPACING = 5

# HomeCartel outro candidates
OUTRO_CANDIDATES = [
    REPO_ROOT / "assets" / "outro_layout.jpg",
    REPO_ROOT / "Outro for All Reels" / "Outro.jpg",
    Path("assets/outro_layout.jpg"),
    Path("Outro for All Reels/Outro.jpg"),
]
OUTRO_FIELD = "Outro"
TARGET_BLENDED_NAMED_FIELD = "Blended Image with Name text"


def resolve_outro_file() -> Path | None:
    for cand in OUTRO_CANDIDATES:
        if cand.is_file():
            return cand
    return None


def _ffmpeg_escape_drawtext(text: str) -> str:
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def _ffmpeg_escape_fontfile(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:")


def measure_tag_lines(
    title: str, subtitle: str, title_size: int = TITLE_FONT_SIZE, type_size: int = TYPE_FONT_SIZE
) -> tuple[int, int, int, int]:
    """Measure the 2-line tag with the real Poppins fonts."""
    from PIL import ImageFont

    bold_path = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Bold.ttf"
    reg_path = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Regular.ttf"
    try:
        font_title = ImageFont.truetype(str(bold_path), title_size)
    except Exception:
        font_title = ImageFont.load_default()
    try:
        font_type = ImageFont.truetype(str(reg_path), type_size)
    except Exception:
        font_type = font_title

    def _size(text: str, font: Any) -> tuple[int, int]:
        if not text:
            return 0, 0
        box = font.getbbox(text)
        return box[2] - box[0], box[3] - box[1]

    title_w, title_h = _size(title, font_title)
    type_w, type_h = _size(subtitle, font_type)
    return title_w, title_h, type_w, type_h


def tag_reel_position(
    title: str, subtitle: str, width: int = 1080, height: int = 1920
) -> tuple[int, int, int]:
    """Calculate lower-right (x, y_title, y_type) for reel tag stamping."""
    title_w, title_h, type_w, type_h = measure_tag_lines(title, subtitle)
    pill_w = max(title_w, type_w)
    pill_h = title_h + (TAG_LINE_SPACING + type_h if subtitle else 0)
    x = max(0, width - pill_w - TAG_RIGHT_MARGIN)
    y_title = max(0, height - pill_h - TAG_BOTTOM_MARGIN)
    y_type = y_title + title_h + TAG_LINE_SPACING
    return x, y_title, y_type


def format_item_display_name(title: str, product_type: str, fallback_label: str = "") -> str:
    """Format a clean, luxury product display name combining item name and product type.

    E.g.:
      ('Mina 7', 'Chandelier') -> 'Mina 7 Chandelier'
      ('Landon', 'Pendant Light') -> 'Landon Pendant Light'
      ('Aria Pendant Light', 'Pendant Light') -> 'Aria Pendant Light'
    """
    clean_title = (title or "").strip()
    clean_type = (product_type or fallback_label or "").strip()
    if not clean_title:
        return clean_type
    if not clean_type:
        return clean_title

    # Remove generic marketing adjectives like Modern, LED, Luxury
    clean_type_simplified = re.sub(
        r"\b(modern|led|luxury|gold frost|designer)\b", "", clean_type, flags=re.IGNORECASE
    ).strip()
    clean_type_simplified = re.sub(r"\s+", " ", clean_type_simplified)
    if not clean_type_simplified:
        clean_type_simplified = clean_type

    if clean_type_simplified.lower() in clean_title.lower():
        return clean_title
    return f"{clean_title} {clean_type_simplified}".strip()


def measure_single_tag(text: str, font_size: int = TITLE_FONT_SIZE) -> tuple[int, int]:
    """Measure single line width and height for luxury product tags."""
    from PIL import ImageFont

    bold_path = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Bold.ttf"
    try:
        font = ImageFont.truetype(str(bold_path), font_size)
    except Exception:
        font = ImageFont.load_default()
    box = font.getbbox(text or "")
    return box[2] - box[0], box[3] - box[1]




class Clients:
    """Holds active API clients for pipeline execution."""
    def __init__(self, airtable: ScrapeAirtableClient, settings: Settings | None = None):
        self.airtable = airtable
        self.settings = settings or load_settings()
        self._krea: KreaClient | None = None
        self._fal: FalClient | None = None
        self._akeneo: AkeneoClient | None = None
        self._shopify: ShopifyClient | None = None
        try:
            self.airtable.ensure_fields(
                {
                    **{name: "singleLineText" for name in PRODUCT_TYPE_FIELDS.values()},
                    **{name: "singleLineText" for name in MEASUREMENT_FIELDS.values()},
                }
            )
        except Exception:
            pass
        ensure_scale_fields(self.airtable)

    def krea(self) -> KreaClient:
        if self._krea is None:
            self._krea = KreaClient(
                token=self.settings.krea_token,
                base_url=self.settings.krea_base_url,
            )
        return self._krea

    def fal(self) -> FalClient:
        if self._fal is None:
            self._fal = FalClient(api_key=self.settings.fal_key)
        return self._fal

    def akeneo(self) -> AkeneoClient:
        if self._akeneo is None:
            self._akeneo = AkeneoClient(
                host=self.settings.akeneo_host or os.getenv("AKENEO_HOST", ""),
                client_id=self.settings.akeneo_client_id or os.getenv("AKENEO_CLIENT_ID", ""),
                secret=self.settings.akeneo_secret or os.getenv("AKENEO_SECRET", ""),
                username=self.settings.akeneo_username or os.getenv("AKENEO_USERNAME", ""),
                password=self.settings.akeneo_password or os.getenv("AKENEO_PASSWORD", ""),
                channel_name=os.getenv("CHANNEL_NAME", ""),
            )
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

def _plan_new_candidates(
    slot: int,
    needed: int,
    akeneo: AkeneoClient,
    style: str,
    all_existing_filenames: set[str],
    all_existing_names: set[str],
    all_existing_skus: set[str],
    shopify_index: Any | None,
) -> list[ProductItem]:
    category = SLOT_CATEGORIES[slot]
    akeneo_category = categories.akeneo_category_code(category)
    query: dict[str, Any] = {
        "categories": [{"operator": "IN", "value": [akeneo_category]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    if style and style.lower() != "all":
        query["Style2"] = [{"operator": "IN", "value": [style]}]

    print(f"[INFO] Fetching {style} {category} products from Akeneo (slot {slot}: {SLOT_ROOMS[slot]})...")
    raw_products = akeneo.fetch_products(query)

    existing_names_query, existing_media_query = existing_product_identities(
        raw_products, all_existing_skus
    )
    combined_names = all_existing_names | existing_names_query

    selected, _stats = select_new_products(
        raw_products,
        all_existing_skus,
        existing_item_names=combined_names,
        existing_media_codes=existing_media_query,
        category_code=category,
    )

    candidates: list[ProductItem] = []
    for item in selected:
        fn = attachment_filename(item.item_name, item.media_code)
        if identity_key(fn) in all_existing_filenames:
            continue
        if item.sku and item.sku.strip() in all_existing_skus:
            continue
        if (item.item_name or "").strip().lower() in all_existing_names:
            continue
        if shopify_index is not None and not shopify_index.contains(item.sku, item.item_name):
            continue

        candidates.append(item)
        all_existing_filenames.add(identity_key(fn))
        if item.sku:
            all_existing_skus.add(item.sku.strip())
        all_existing_names.add((item.item_name or "").strip().lower())
        if len(candidates) >= needed:
            break

    return candidates


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
        print(f"[OK] Shopify live catalog indexed ({len(shopify_index.skus)} published SKUs).")
    except Exception as e:
        print(f"[WARN] Shopify catalog check notice: {e}")

    created_ids: list[str] = []

    for row_idx in range(max_rows):
        # 1. Scrape 1 product per slot
        slot_items: dict[int, ProductItem] = {}
        for slot in SLOTS:
            candidates = _plan_new_candidates(
                slot=slot,
                needed=1,
                akeneo=akeneo,
                style=style,
                all_existing_filenames=all_existing_filenames,
                all_existing_names=all_existing_names,
                all_existing_skus=all_existing_skus,
                shopify_index=shopify_index,
            )
            if not candidates:
                raise AutomationError(f"No fresh published candidates found for slot {slot} ({SLOT_CATEGORIES[slot]})")
            slot_items[slot] = candidates[0]

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
            name, ptype = split_item_name(item.item_name)
            fallback_type = fixture_display_type(SLOT_CATEGORIES[slot])
            disp_name = format_item_display_name(name, ptype or fallback_type)
            row_updates[ITEM_NAME_FIELDS[slot]] = disp_name
            row_updates[SKU_FIELDS[slot]] = item.sku or ""
            row_updates[PRODUCT_TYPE_FIELDS[slot]] = ptype or fallback_type
            if item.measurement:
                row_updates[MEASUREMENT_FIELDS[slot]] = item.measurement
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
            analysis = fal.analyze_image(prompt=prompt, image_urls=[int_url])
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
            "ambient illumination with subtle atmospheric glow and realistic shadows, preserving the cozy dark night interior.\n\n"
            f"{scale_clause(product_type_for_slot(fields, slot - 1) or SLOT_LABELS[slot], measurement_for_slot(fields, slot - 1), label=f'the {SLOT_LABELS[slot].lower()}')}"
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
            scale_result = None
            if prod_url:
                scale_result = blend_with_scale_guard(
                    fal,
                    prompt=prompt,
                    room_url=int_url,
                    product_url=prod_url,
                    product_type=str(fields.get(PRODUCT_TYPE_FIELDS[slot]) or ""),
                    measurement=str(fields.get(MEASUREMENT_FIELDS[slot]) or ""),
                    item_name=str(fields.get(ITEM_NAME_FIELDS[slot]) or ""),
                    label=f"the {SLOT_LABELS[slot].lower()}",
                    aspect_ratio="9:16",
                    resolution="1K",
                    model="fal-ai/nano-banana-pro/edit",
                )
                blended_url = scale_result.image_url
            else:
                blended_url = fal.generate(
                    prompt=prompt,
                    image_urls=[int_url],
                    aspect_ratio="9:16",
                    resolution="1K",
                    model="fal-ai/nano-banana-pro/edit",
                )
            if blended_url:
                clients.airtable.upload_attachment_url(record_id, BLENDED_FIELDS[slot], blended_url, f"blended_{slot}.jpg")
                fields[BLENDED_FIELDS[slot]] = [{"url": blended_url}]
                if scale_result is not None:
                    write_scale_fields(clients.airtable, record_id, [(slot - 1, scale_result)])
                print(f"    [OK] Slot {slot} blended.")
        except Exception as err:
            print(f"    [ERROR] Blending failed for slot {slot}: {err}")
            return False

    # Tag blended images and populate 'Blended Image with Name text'
    existing_tagged = fields.get(TARGET_BLENDED_NAMED_FIELD)
    if not existing_tagged or len(existing_tagged) < len(SLOTS):
        print("    [TAGGING] Stamping product tags onto blended images -> 'Blended Image with Name text'...")
        from content_automation.item_tagger import fixture_display_type, tag_and_upload_blended_image

        for slot in SLOTS:
            b_url = _first_attachment_url(fields, BLENDED_FIELDS[slot])
            if not b_url:
                continue
            raw_name = str(fields.get(ITEM_NAME_FIELDS[slot]) or "").strip()
            fallback_type = fixture_display_type(SLOT_CATEGORIES[slot])
            title, product_type = split_item_name(raw_name, fallback_product_type=fallback_type)
            try:
                tag_and_upload_blended_image(
                    airtable=clients.airtable,
                    record_id=record_id,
                    blended_source=b_url,
                    item_name=title,
                    product_type=product_type,
                    category=SLOT_CATEGORIES[slot],
                    target_field=TARGET_BLENDED_NAMED_FIELD,
                    output_filename_prefix=f"TMEN_{record_id}_slot{slot}",
                    output_format="reel",
                )
            except Exception as tag_err:
                print(f"    [WARN] Failed tagging blended image for slot {slot}: {tag_err}")

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
    # Refresh fields from Airtable to ensure all uploaded attachments are present
    rec = clients.airtable.record(record_id)
    fields.update(rec.get("fields", {}))

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
                vid_url = fal.generate_kling_video(
                    prompt=motion_prompt,
                    image_url=blend_url,
                    duration=3,
                )
                if vid_url:
                    clients.airtable.upload_attachment_url(record_id, KLING_FIELDS[slot], vid_url, f"motion_clip_{slot}.mp4")
                    fields[KLING_FIELDS[slot]] = [{"url": vid_url}]
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
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
                tmp_audio_path = Path(tmp_audio.name)
            subprocess.run(
                [ffmpeg_exe, "-y", "-i", str(ref_vid), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(tmp_audio_path)],
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
    # Refresh fields from Airtable to ensure all uploaded attachments are present
    rec = clients.airtable.record(record_id)
    fields.update(rec.get("fields", {}))

    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    from content_automation.item_tagger import fixture_display_type

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
                         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
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
                     "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip_file)],
                    check=True,
                    capture_output=True,
                )
                clip_paths.append(clip_file)

        if len(clip_paths) < 7:
            raise AutomationError(f"Insufficient clips for assembly (found {len(clip_paths)}/7)")

        # 2. Resolve & append HomeCartel Outro
        outro_file = resolve_outro_file()
        if outro_file:
            print(f"    [INFO] Appending HomeCartel outro card ({outro_file.name})...")
            # Ensure outro is uploaded to Airtable 'Outro' field if not present
            if not _first_attachment_url(fields, OUTRO_FIELD):
                try:
                    clients.airtable.upload_attachment(record_id, OUTRO_FIELD, outro_file, "outro.jpg")
                    print("    [OK] Outro attached to Airtable field 'Outro'.")
                except Exception as o_err:
                    print(f"    [WARN] Failed uploading Outro attachment: {o_err}")

            outro_clip = tmp_path / "shot_outro.mp4"
            subprocess.run(
                [
                    ffmpeg_exe, "-y", "-loop", "1", "-i", str(outro_file), "-t", str(OUTRO_DURATION),
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,fade=t=in:st=0:d=0.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(outro_clip),
                ],
                check=True,
                capture_output=True,
            )
            clip_paths.append(outro_clip)

        # 3. Concat clips
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

        # 4. Construct drawtext filters
        drawtext_filters: list[str] = []

        # A) Center overlay: "this mood every night" (active ONLY during the 7 shots, t=0..9.45s)
        font_light_path = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Light.ttf"
        font_light_arg = _ffmpeg_escape_fontfile(font_light_path)
        drawtext_filters.append(
            f"drawtext=fontfile='{font_light_arg}':text='{CENTER_OVERLAY_TEXT}':"
            "fontsize=46:fontcolor=white@0.92:x=(w-text_w)/2:y=(h-text_h)/2:"
            "shadowcolor=black@0.4:shadowx=2:shadowy=2:"
            f"enable='between(t,0,{TOTAL_SHOTS_DURATION:.2f})'"
        )

        # Ensure Airtable record's Item Name fields include the product type
        airtable_item_updates = {}
        for slot in SLOTS:
            raw_name = str(fields.get(ITEM_NAME_FIELDS[slot]) or "").strip()
            fallback_type = fixture_display_type(SLOT_CATEGORIES[slot])
            title, subtitle = split_item_name(raw_name, fallback_product_type=fallback_type)
            disp_name = format_item_display_name(title, subtitle)
            if disp_name and disp_name != raw_name:
                airtable_item_updates[ITEM_NAME_FIELDS[slot]] = disp_name
                fields[ITEM_NAME_FIELDS[slot]] = disp_name
        if airtable_item_updates:
            try:
                clients.airtable.update_records([(record_id, airtable_item_updates)])
            except Exception as e_up:
                print(f"    [WARN] Notice updating Item Name fields in Airtable: {e_up}")

        # B) Lower-right Product Tag (Item Name + Product Type) with smooth fluid reveal and fade-out
        font_bold_path = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Bold.ttf"
        font_bold_arg = _ffmpeg_escape_fontfile(font_bold_path)

        for slot in SLOTS:
            start_t = (slot - 1) * SHOT_DURATION
            end_t = slot * SHOT_DURATION
            raw_name = str(fields.get(ITEM_NAME_FIELDS[slot]) or "").strip()
            fallback_type = fixture_display_type(SLOT_CATEGORIES[slot])
            title, subtitle = split_item_name(raw_name, fallback_product_type=fallback_type)
            display_name = format_item_display_name(title, subtitle)

            if not display_name:
                continue

            tw, th = measure_single_tag(display_name, TITLE_FONT_SIZE)
            x = max(0, 1080 - tw - TAG_RIGHT_MARGIN)
            y_base = max(0, 1920 - th - TAG_BOTTOM_MARGIN)

            # Smooth fluid transition timings within the 1.35s shot:
            # - Starts at +0.10s
            # - Fades in & slides 15px upward from +0.10s to +0.35s
            # - Holds steady from +0.35s to (end - 0.20s)
            # - Fades out smoothly from (end - 0.20s) to end
            t_in_start = start_t + 0.10
            t_in_end = start_t + 0.35
            t_out_start = end_t - 0.20
            t_out_end = end_t

            alpha_expr = (
                f"if(lt(t,{t_in_start:.2f}),0,"
                f"if(lt(t,{t_in_end:.2f}),(t-{t_in_start:.2f})/0.25,"
                f"if(lt(t,{t_out_start:.2f}),1,"
                f"if(lt(t,{t_out_end:.2f}),({t_out_end:.2f}-t)/0.20,0))))"
            )
            y_expr = (
                f"{y_base} + if(lt(t,{t_in_start:.2f}),15,"
                f"if(lt(t,{t_in_end:.2f}),(1-(t-{t_in_start:.2f})/0.25)*15,0))"
            )

            esc_name = _ffmpeg_escape_drawtext(display_name)
            window = f"enable='between(t,{start_t:.2f},{end_t:.2f})'"

            drawtext_filters.append(
                f"drawtext=fontfile='{font_bold_arg}':text='{esc_name}':"
                f"fontsize={TITLE_FONT_SIZE}:fontcolor=white:x={x}:y='{y_expr}':alpha='{alpha_expr}':"
                f"shadowcolor=black@0.45:shadowx=2:shadowy=2:{window}"
            )

        video_with_text = tmp_path / "video_text.mp4"
        vf_arg = ",".join(drawtext_filters)
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", str(raw_video), "-vf", vf_arg,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_with_text)],
            check=True,
            capture_output=True,
        )

        # 5. Mux Audio with smooth outro audio fade
        total_duration = TOTAL_SHOTS_DURATION + (OUTRO_DURATION if outro_file else 0.0)
        fade_start = max(0.0, total_duration - 1.0)
        music_url = _first_attachment_url(fields, "Music Generated")
        final_output = tmp_path / "this_mood_every_night_reel.mp4"

        if music_url:
            audio_file = tmp_path / "soundtrack.mp3"
            _download_file(music_url, audio_file)
            subprocess.run(
                [
                    ffmpeg_exe, "-y", "-i", str(video_with_text), "-stream_loop", "-1", "-i", str(audio_file),
                    "-filter_complex", f"[1:a]atrim=duration={total_duration:.2f},asetpts=PTS-STARTPTS,afade=t=out:st={fade_start:.2f}:d=1.0[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    str(final_output)
                ],
                check=True,
                capture_output=True,
            )
        else:
            final_output = video_with_text

        # 6. Upload Final Video & Stamp Done
        clients.airtable.upload_attachment(record_id, "Final Video", final_output, f"TMEN_{record_id}_final.mp4")
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
    clients = Clients(airtable, settings)

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
