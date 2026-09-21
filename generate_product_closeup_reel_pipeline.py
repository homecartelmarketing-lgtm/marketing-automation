#!/usr/bin/env python3
"""Product Closeup Reel Automation Pipeline (9:16, with Fal ElevenLabs background music).

Target Table: ``tblqBZ946hVdOpmDV`` -- "Product Closeup Table Lamps".

This pipeline turns freshly scraped Table Lamp products into a vertical
9:16 reel by blending each product into an AI-generated modern-bedroom
interior and rendering the results with ``photo_video_maker.py``.

Phases
------
    Phase 1  Scrape Table Lamps (Akeneo with Deduplication) -> Furniture Item1..4, Item Name1..4
             Enabled items only, ordered newest -> oldest, 4 lamps per row.
             Status -> "Standby".
    Phase 2  Generate 4 interiors (Krea)      -> Interior1..4
             Moodboard ``fb2487fb-2895-4d2c-9758-805aaf1bac69`` +
             prompt "Generate me a modern bedroom".  Status -> "In progress".
    Phase 3  Blend prompts (Fal Claude Sonnet)-> Generated Prompt1..4
             ``anthropic/claude-sonnet-5`` analyses [interior + product].
    Phase 4  Blend (Fal Nano Banana Pro)      -> local blended stills
             ``fal-ai/nano-banana-pro/edit`` (9:16, 1K).
    Phase 4.5 Outro                           -> "Outro" attachment field
             HomeCartel outro ('assets/outro_layout.jpg' or 'Outro for All Reels/Outro.jpg')
             is attached to the row and appended to the end of the reel.
    Phase 4.7 Background Music               -> Fal ElevenLabs Music API (fal-ai/elevenlabs/music)
    Phase 5  Reel assembly (photo_video_maker)-> Final Video
             720x1280 MP4 with Fal ElevenLabs background music and HomeCartel outro.
             Status -> "Done".

Usage::

    # ONE row, end to end (scrape a 4-lamp group, build its reel, stop):
    python generate_product_closeup_reel_pipeline.py --phase all

    # Multiple rows:
    python generate_product_closeup_reel_pipeline.py --phase all --max-rows 3

    # Just scrape new Table Lamp groups into Airtable (no video):
    python generate_product_closeup_reel_pipeline.py --phase scrape --max-rows 1

    # Finish existing pending rows in Airtable (no scraping):
    python generate_product_closeup_reel_pipeline.py --phase generate

    # Process a single specific row:
    python generate_product_closeup_reel_pipeline.py --record-id recXXXXXXXX
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
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

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename
from content_automation.shopify_client import ShopifyCatalogIndex, ShopifyClient
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

DEFAULT_TABLE_ID = "tblqBZ946hVdOpmDV"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_CLOSEUP_REEL"

AKENEO_CATEGORY = "table_lamps"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

# Krea interior generation (Phase 2)
INTERIOR_MOODBOARD_ID = "fb2487fb-2895-4d2c-9758-805aaf1bac69"  # Table Lamps board
INTERIOR_PROMPT = "Generate me a modern bedroom"


def resolve_interior_settings() -> tuple[str, str]:
    """Resolve the Studio edit settings when an interior is generated."""
    return (
        os.getenv("KREA_MOODBOARD_ID_TABLE_LAMPS_PRODUCT_CLOSEUP_REEL", "").strip()
        or os.getenv("KREA_MOODBOARD_ID_PRODUCT_CLOSEUP_REEL", "").strip()
        or INTERIOR_MOODBOARD_ID,
        os.getenv("PROMPT_PRODUCT_CLOSEUP_REEL_TABLE_LAMP", "").strip()
        or INTERIOR_PROMPT,
    )
INTERIOR_ASPECT_RATIO = "9:16"
INTERIOR_RESOLUTION = "1K"

# Fal Claude Sonnet (Phase 3)
CLAUDE_MODEL = "anthropic/claude-sonnet-5"

# Fal Nano Banana Pro (Phase 4)
NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"
BLEND_ASPECT_RATIO = "9:16"
BLEND_RESOLUTION = "1K"

# Reel render (Phase 5)
RENDERER = Path(__file__).with_name("photo_video_maker.py")
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
OUTRO_SECONDS = 2.9

# HomeCartel outro
OUTRO_CANDIDATES = [
    Path(__file__).parent / "Outro for All Reels" / "Outro.jpg",
    Path(__file__).parent / "assets" / "outro_layout.jpg",
    Path("Outro for All Reels/Outro.jpg"),
    Path("assets/outro_layout.jpg"),
]
OUTRO_FIELD = "Outro"

# Background music (Fal AI ElevenLabs Music). Default: OFF (silent reel).
# Set PRODUCT_CLOSEUP_MUSIC_ENABLED=true in .env or pass --with-music to enable.
MUSIC_ENABLED = os.getenv("PRODUCT_CLOSEUP_MUSIC_ENABLED", "false").strip().lower() in ("true", "1", "yes")
MUSIC_MODEL = "fal-ai/elevenlabs/music"
MUSIC_PROMPT = (
    "Smooth luxury modern lounge instrumental, warm ambient chords, "
    "elegant boutique vibe, gentle acoustic rhythms, seamless loop"
)
MUSIC_DURATION = 16  # seconds

# Airtable field names for tblqBZ946hVdOpmDV
STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"

SLOTS = (1, 2, 3, 4)
FURNITURE_FIELDS = {
    1: "Furniture Item1",
    2: "Furniture Item2",
    3: "Furniture Item3",
    4: "Furniture Item4",
}
ITEM_NAME_FIELDS = {
    1: "Item Name1",
    2: "Item Name2",
    3: "Item Name3",
    4: "Item Name4",
}
INTERIOR_FIELDS = {
    1: "Interior1",
    2: "Interior2",
    3: "Interior3",
    4: "Interior4",
}
PROMPT_FIELDS = {
    1: "Generated Prompt1",
    2: "Generated Prompt2",
    3: "Generated Prompt3",
    4: "Generated Prompt4",
}
FINAL_VIDEO_FIELD = "Final Video"

PRODUCTS_PER_ROW = len(SLOTS)

ALL_READ_FIELDS = [
    STATUS_FIELD,
    *FURNITURE_FIELDS.values(),
    *ITEM_NAME_FIELDS.values(),
    *INTERIOR_FIELDS.values(),
    *PROMPT_FIELDS.values(),
    OUTRO_FIELD,
    FINAL_VIDEO_FIELD,
]

CLAUDE_INSTRUCTION = (
    "You are a product-photography prompt engineer. Look at the two images: "
    "the first is a modern bedroom interior, the second is a table lamp product. "
    "Write a single detailed image-editing prompt (no preamble, no markdown) that "
    "instructs an image model to place this exact table lamp naturally onto a "
    "bedside table or surface inside the bedroom, keeping the lamp's shape, colour "
    "and proportions identical, with photorealistic lighting, soft shadows and a "
    "cohesive warm interior mood. Emphasise a tasteful close-up composition of the "
    "lamp within the room. Do not change the lamp design."
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _first_attachment_url(fields: dict[str, Any], field_name: str) -> str:
    value = fields.get(field_name)
    if isinstance(value, list) and value:
        return str(value[0].get("url") or "")
    return ""


def resolve_outro_file() -> Path | None:
    for cand in OUTRO_CANDIDATES:
        if cand.is_file():
            return cand.resolve()
    return None


class Clients:
    def __init__(self, table_id: str | None = None) -> None:
        self.settings = load_settings()
        resolved_table = table_id or os.getenv(TABLE_ENV_KEY, "").strip() or DEFAULT_TABLE_ID
        self.airtable = ScrapeAirtableClient(
            self.settings.airtable_token,
            self.settings.airtable_base_id,
            resolved_table,
        )
        self.krea = KreaClient(
            token=self.settings.krea_token,
            base_url=self.settings.krea_base_url,
        )
        self.fal = FalClient(api_key=self.settings.fal_key)

    def akeneo(self) -> AkeneoClient:
        return AkeneoClient(
            host=os.getenv("AKENEO_HOST", ""),
            client_id=os.getenv("AKENEO_CLIENT_ID", ""),
            secret=os.getenv("AKENEO_SECRET", ""),
            username=os.getenv("AKENEO_USERNAME", ""),
            password=os.getenv("AKENEO_PASSWORD", ""),
            channel_name=os.getenv("CHANNEL_NAME", ""),
        )


# --------------------------------------------------------------------------
# Phase 1 -- Scrape Table Lamps with Full Deduplication
# --------------------------------------------------------------------------


def _plan_new_pairs(clients: Clients, style: str, akeneo: AkeneoClient):
    # 1. Stored identities in current table tblqBZ946hVdOpmDV
    stored_names: set[str] = set()
    stored_filenames: set[str] = set()
    for record in clients.airtable.list_records(list(ALL_READ_FIELDS)):
        row = record.get("fields", {})
        for name_field in ITEM_NAME_FIELDS.values():
            val = str(row.get(name_field) or "").strip()
            if val:
                stored_names.add(val.lower())
        for furn_field in FURNITURE_FIELDS.values():
            att_list = row.get(furn_field)
            if isinstance(att_list, list):
                for a in att_list:
                    if isinstance(a, dict) and a.get("filename"):
                        stored_filenames.add(identity_key(a["filename"]))

    # 2. Cross-table deduplication across entire base
    base_filenames: set[str] = set()
    base_names: set[str] = set()
    base_skus: set[str] = set()
    try:
        base_filenames, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
        print(
            f"[INFO] Cross-table deduplication active: Found {len(base_skus)} existing SKU(s), "
            f"{len(base_names)} item name(s), and {len(base_filenames)} attachment filename(s) across all base tables."
        )
    except Exception as e:
        print(f"[WARN] Base deduplication fetch notice: {e}")

    all_existing_filenames = stored_filenames | base_filenames
    all_existing_names = stored_names | base_names
    all_existing_skus = base_skus

    # 3. Shopify published catalog cross-check
    shopify_index = None
    try:
        print("[INFO] Fetching published catalog from Shopify (homecartel.net)...")
        shopify = ShopifyClient()
        prods = shopify.fetch_all_products()
        shopify_index = ShopifyCatalogIndex.build(prods)
        print(f"[OK] Shopify Index Ready: {shopify_index.product_count} published products indexed.")
    except Exception as s_err:
        print(f"[WARN] Shopify index check skipped: {s_err}")

    akeneo_category = categories.akeneo_category_code(AKENEO_CATEGORY)
    query: dict[str, Any] = {
        "categories": [{"operator": "IN", "value": [akeneo_category]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    if style and style.lower() != "all":
        query["Style2"] = [{"operator": "IN", "value": [style]}]

    print(f"[INFO] Fetching {style} {AKENEO_CATEGORY} products from Akeneo...")
    products = akeneo.fetch_products(query)

    existing_names_query, existing_media_query = existing_product_identities(products, all_existing_skus)
    combined_names = all_existing_names | existing_names_query

    selected, stats = select_new_products(
        products,
        all_existing_skus,
        existing_item_names=combined_names,
        existing_media_codes=existing_media_query,
        category_code=AKENEO_CATEGORY,
    )

    filtered_candidates: list[ProductItem] = []
    for item in selected:
        fn = attachment_filename(item.item_name, item.media_code)
        if identity_key(fn) in all_existing_filenames:
            print(f"[DEDUP SKIP] Existing photo: '{item.item_name}' (SKU: {item.sku}) already exists in Airtable")
            continue
        if item.sku and item.sku.strip() in all_existing_skus:
            print(f"[DEDUP SKIP] Existing SKU: '{item.item_name}' (SKU: {item.sku}) already exists in Airtable")
            continue
        if (item.item_name or "").strip().lower() in all_existing_names:
            print(f"[DEDUP SKIP] Existing Name: '{item.item_name}' already exists in Airtable")
            continue
        if shopify_index and not shopify_index.contains(item.sku, item.item_name):
            try:
                print(
                    f"[SHOPIFY DRAFT/INACTIVE SKIP] Item '{item.item_name}' (SKU: {item.sku}) is Enabled in Akeneo "
                    "but Draft/Inactive in Shopify -> skipping to next unique item"
                )
            except Exception:
                print(
                    f"[SHOPIFY DRAFT/INACTIVE SKIP] SKU {item.sku} is Enabled in Akeneo "
                    "but Draft/Inactive in Shopify -> skipping to next unique item"
                )
            continue

        print(f"[DEDUP PASS] New unique product selected: '{item.item_name}' (SKU: {item.sku})")
        filtered_candidates.append(item)

    print(
        f"[PLAN] {len(filtered_candidates)} new unique candidate(s) passed deduplication."
    )

    n = PRODUCTS_PER_ROW
    groups = [
        filtered_candidates[i : i + n]
        for i in range(0, len(filtered_candidates), n)
        if len(filtered_candidates[i : i + n]) == n
    ]
    return groups


def _create_row_from_pair(clients: Clients, pair: list[ProductItem], akeneo: AkeneoClient) -> str | None:
    fields: dict[str, Any] = {STATUS_FIELD: STATUS_STANDBY}
    for slot, item in zip(SLOTS, pair):
        fields[ITEM_NAME_FIELDS[slot]] = _display_name(item)
    try:
        record_id = clients.airtable.create_record(fields)
    except Exception as error:
        print(f"[ERROR] Could not create row: {error}")
        return None
    ok = True
    for slot, item in zip(SLOTS, pair):
        if not _upload_product(clients, record_id, slot, item, akeneo):
            ok = False
    if not ok:
        print(f"[WARN] Row {record_id} created but one or more product uploads failed.")
    return record_id


def phase1_scrape(clients: Clients, max_rows: int | None, style: str) -> int:
    print("=" * 68)
    print("PHASE 1 -- Scrape Table Lamps (4 per row, Akeneo with Deduplication)")
    print("=" * 68)

    akeneo = clients.akeneo()
    akeneo.authenticate()

    pairs = _plan_new_pairs(clients, style, akeneo)
    if max_rows is not None:
        pairs = pairs[:max_rows]
    if not pairs:
        print("[OK] No complete 4-lamp groups available to create.")
        return 0

    created = 0
    for index, pair in enumerate(pairs, start=1):
        print(f"[INFO] Creating row {index}/{len(pairs)} with 4 table lamps...")
        if _create_row_from_pair(clients, pair, akeneo):
            created += 1
    print(f"[OK] Phase 1 complete: created {created} row(s).")
    return created


def _display_name(item: ProductItem) -> str:
    name = (item.item_name or "").strip()
    ptype = (item.product_type or "").strip()
    if ptype and ptype.lower() not in name.lower():
        return f"{name} | {ptype}"
    return name


def _upload_product(
    clients: Clients,
    record_id: str,
    slot: int,
    item: ProductItem,
    akeneo: AkeneoClient,
) -> bool:
    field_name = FURNITURE_FIELDS[slot]
    try:
        downloaded = akeneo.download_media(item.media_code)
        filename = f"{item.sku or 'lamp'}_{item.media_code}.jpg"
        clients.airtable.upload_attachment(record_id, field_name, downloaded, filename)
        print(f"[OK] {item.sku} -> {record_id} / {field_name}")
        return True
    except Exception as error:
        print(f"[ERROR] Upload product {item.sku} into slot {slot}: {error}")
        return False


# --------------------------------------------------------------------------
# Phase 2 -- Generate 4 Krea interiors
# --------------------------------------------------------------------------


def phase2_interiors(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    moodboard_id, interior_prompt = resolve_interior_settings()
    print("  [Phase 2] Generating room interiors (Krea)...")
    updates: dict[str, Any] = {}

    def generate_one(slot: int):
        field_name = INTERIOR_FIELDS[slot]
        if _first_attachment_url(fields, field_name):
            print(f"    [SKIP] slot {slot} already has an interior")
            return
        if not _first_attachment_url(fields, FURNITURE_FIELDS[slot]):
            print(f"    [SKIP] slot {slot} has no product -- skipping interior")
            return
        print(f"    -> requesting Krea interior for slot {slot}...")
        url = clients.krea.generate_image(
            prompt=interior_prompt,
            moodboard_id=moodboard_id,
            aspect_ratio=INTERIOR_ASPECT_RATIO,
            resolution=INTERIOR_RESOLUTION,
        )
        updates[field_name] = [{"url": url}]
        print(f"    [OK] slot {slot} interior generated")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(generate_one, SLOTS))

    if updates:
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)


# --------------------------------------------------------------------------
# Phase 3 -- Blend prompts via Fal Claude Sonnet
# --------------------------------------------------------------------------


def phase3_prompts(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("  [Phase 3] Generating blend prompts (Fal Claude Sonnet)...")
    updates: dict[str, Any] = {}

    def author_one(slot: int):
        field_name = PROMPT_FIELDS[slot]
        if str(fields.get(field_name) or "").strip():
            print(f"    [SKIP] slot {slot} already has a prompt")
            return
        interior_url = _first_attachment_url(fields, INTERIOR_FIELDS[slot])
        product_url = _first_attachment_url(fields, FURNITURE_FIELDS[slot])
        if not interior_url or not product_url:
            print(f"    [SKIP] slot {slot} missing interior or product -- skipping prompt")
            return
        print(f"    -> asking Claude for slot {slot} blend prompt...")
        prompt = clients.fal.generate_vision_prompt(
            image_urls=[interior_url, product_url],
            prompt=CLAUDE_INSTRUCTION,
            model=CLAUDE_MODEL,
        )
        updates[field_name] = prompt
        print(f"    [OK] slot {slot} blend prompt authored")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(author_one, SLOTS))

    if updates:
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)


# --------------------------------------------------------------------------
# Phase 4 -- Blend each lamp into its interior via Fal Nano Banana Pro
# --------------------------------------------------------------------------


def phase4_blends(clients: Clients, fields: dict[str, Any], workdir: Path, record_id: str = "") -> list[Path]:
    print("  [Phase 4] Blending lamps into bedrooms (Fal Nano Banana Pro)...")

    def blend_slot(slot: int) -> Path | None:
        interior_url = _first_attachment_url(fields, INTERIOR_FIELDS[slot])
        product_url = _first_attachment_url(fields, FURNITURE_FIELDS[slot])
        prompt = str(fields.get(PROMPT_FIELDS[slot]) or "").strip()
        if not interior_url or not product_url or not prompt:
            print(f"    [SKIP] slot {slot} incomplete -- skipping blend")
            return None

        destination = workdir / f"slot{slot}_blended.jpg"
        print(f"    -> blending slot {slot}...")
        try:
            result_url = clients.fal.generate(
                prompt=prompt,
                image_urls=[interior_url, product_url],
                aspect_ratio=BLEND_ASPECT_RATIO,
                resolution=BLEND_RESOLUTION,
                model=NANO_BANANA_MODEL,
            )
            resp = requests.get(result_url, timeout=60)
            with open(destination, "wb") as f:
                f.write(resp.content)
            print(f"    [OK] slot {slot} blended -> {destination.name}")

            # Auto-tag furniture item name onto blended still using YOLO-World
            try:
                from content_automation.akeneo_client import split_item_name
                from content_automation.item_tagger import TARGET_BLENDED_FIELD, tag_blended_image
                raw_name = str(fields.get(ITEM_NAME_FIELDS[slot]) or fields.get(f"SKU{slot}") or f"Table Lamp {slot}").strip()
                item_title, product_type = split_item_name(raw_name, fallback_product_type="Table Lamp")
                tag_blended_image(
                    image_input=destination,
                    item_name=item_title,
                    product_type=product_type,
                    category="table_lamps",
                    destination=destination,
                    fallback_if_undetected=True,
                )
                print(f"    [ITEM TAGGING] Stamped '{item_title}' onto slot {slot} blended still with YOLO")
                try:
                    clients.airtable.ensure_fields({TARGET_BLENDED_FIELD: "multipleAttachments"})
                    if record_id:
                        clients.airtable.upload_attachment(record_id, TARGET_BLENDED_FIELD, destination, f"blended_tagged_slot{slot}.jpg")
                except Exception:
                    pass
            except Exception as tag_err:
                print(f"    [WARN] YOLO tagging notice on slot {slot}: {tag_err}")

            return destination
        except Exception as error:
            print(f"    [ERROR] slot {slot} blend: {error}")
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(blend_slot, SLOTS))
    return [path for path in results if path is not None]


# --------------------------------------------------------------------------
# Phase 4.5 & 4.7 & 5 -- Outro, ElevenLabs Music & Reel Assembly
# --------------------------------------------------------------------------


def _resolve_outro(clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path) -> Path | None:
    # 1) Use attached Outro if already in record
    outro_url = _first_attachment_url(fields, OUTRO_FIELD)
    if outro_url:
        try:
            dest = workdir / "outro.jpg"
            resp = requests.get(outro_url, timeout=60)
            with open(dest, "wb") as f:
                f.write(resp.content)
            print("    [OK] Outro downloaded from Airtable 'Outro' field")
            return dest
        except Exception as error:
            print(f"    [WARN] Could not download attached Outro ({error})")

    # 2) Fallback to local outro asset
    local_outro = resolve_outro_file()
    if not local_outro:
        print("    [WARN] Local outro asset not found; reel will have NO outro.")
        return None

    try:
        clients.airtable.upload_attachment(record_id, OUTRO_FIELD, local_outro, "HomeCartel_Outro.jpg")
        print(f"    [OK] Outro ({local_outro.name}) attached to row 'Outro' field")
    except Exception as error:
        print(f"    [WARN] Could not attach outro to row ({error}); using local file anyway.")
    return local_outro


def _generate_music(clients: Clients, workdir: Path) -> Path | None:
    if not MUSIC_ENABLED:
        print("  [Phase 4.7] Background music is OFF -> compiling silent video-only reel.")
        return None
    print("  [Phase 4.7] Generating background music via Fal ElevenLabs Music...")
    try:
        audio_url = clients.fal.generate_elevenlabs_music(
            prompt=MUSIC_PROMPT,
            duration=MUSIC_DURATION,
            model=MUSIC_MODEL,
        )
    except Exception as error:
        print(f"    [WARN] Music generation notice: {error}; reel will be silent.")
        return None
    if not audio_url:
        return None
    dest = workdir / "elevenlabs_music.mp3"
    try:
        urllib.request.urlretrieve(audio_url, dest)
    except Exception as error:
        print(f"    [WARN] Could not download music ({error}); reel will be silent.")
        return None
    if not dest.is_file() or dest.stat().st_size == 0:
        return None
    print(f"    [OK] Fal ElevenLabs background music ready -> {dest.name}")
    return dest


# Text overlay for product clips (Poppins Regular 28pt)
TEXT_FONT_SIZE = 28
def phase5_render(
    stills: list[Path],
    workdir: Path,
    item_names: list[str] | None = None,
    outro: Path | None = None,
    audio: Path | None = None,
) -> Path:
    print("  [Phase 5] Rendering animated reel with photo_video_maker.py...")
    if not stills:
        raise AutomationError("No blended stills to render into a reel")

    output = workdir / "product_closeup_reel.mp4"
    command = [
        sys.executable,
        str(RENDERER),
        *[str(path) for path in stills],
        "--output",
        str(output),
        "--width",
        str(REEL_WIDTH),
        "--height",
        str(REEL_HEIGHT),
        "--seconds",
        "2.9",
        "--transition",
        "0.7",
    ]

    # Pass --title for each product lamp slide (Poppins Regular 28pt)
    for i, _path in enumerate(stills):
        if item_names and i < len(item_names):
            name = item_names[i].strip()
            command.extend(["--title", name])
            if name:
                print(f"    [TEXT] Slide {i + 1}: '{name}' (Poppins Regular 28pt)")
        else:
            command.extend(["--title", ""])

    # Outro is passed as static end card with 0.8s smooth fade-in and 2.5s motionless hold (NO card animation)
    if outro is not None and Path(outro).is_file():
        command.extend([
            "--outro", str(outro),
            "--endcard-seconds", "2.5",
            "--endcard-fade", "0.8",
        ])
        print("    [INFO] HomeCartel outro configured as static end card (0.8s smooth cross-fade, 2.5s hold, NO card animation)")

    if audio is not None and Path(audio).is_file():
        command.extend(["--audio", str(audio)])
        print(f"    [INFO] Background music attached: {Path(audio).name}")

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise AutomationError(
            f"photo_video_maker.py failed with code {result.returncode}:\n"
            f"{result.stderr or result.stdout}"
        )
    if not output.is_file() or output.stat().st_size == 0:
        raise AutomationError("Renderer exited 0 but output MP4 was not created")

    print(f"    [OK] Reel rendered successfully with animation ({output.stat().st_size // 1024} KB)")
    return output


# --------------------------------------------------------------------------
# End-to-end row processor
# --------------------------------------------------------------------------


def process_row(clients: Clients, record_id: str, force: bool = False) -> bool:
    print(f"\n[ROW {record_id}] Processing Product Closeup Reel...")
    record = clients.airtable.record(record_id)
    fields = dict(record.get("fields", {}))

    # Skip already completed rows unless force is True
    if not force and str(fields.get(STATUS_FIELD) or "").strip().lower() == STATUS_DONE.lower():
        print(f"[ROW {record_id}] Status is 'Done' -- strictly skipping (will not re-run even if any phase is missing; use --force to re-generate).")
        return True

    # Mark In progress
    clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_IN_PROGRESS})])

    # Phase 2: Krea interiors
    phase2_interiors(clients, record_id, fields)

    # Phase 3: Claude blend prompts
    phase3_prompts(clients, record_id, fields)

    # Phase 4 & 5: Blend & render
    with tempfile.TemporaryDirectory(prefix=f"closeup_{record_id}_") as tmpdir:
        workdir = Path(tmpdir)
        stills = phase4_blends(clients, fields, workdir, record_id=record_id)
        if not stills:
            print(f"[ROW {record_id}] FAILED -- no stills blended.")
            return False

        outro = _resolve_outro(clients, record_id, fields, workdir)
        audio = _generate_music(clients, workdir)
        names = [str(fields.get(ITEM_NAME_FIELDS[s]) or "").strip() for s in SLOTS]
        mp4_path = phase5_render(stills, workdir, item_names=names, outro=outro, audio=audio)

        # Upload final video
        print(f"  [Upload] Uploading {mp4_path.name} to Airtable...")
        clients.airtable.upload_attachment(
            record_id, FINAL_VIDEO_FIELD, mp4_path, f"product_closeup_reel_{record_id}.mp4"
        )
        clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_DONE})])
        print(f"[ROW {record_id}] COMPLETE -> Final Video uploaded & Status = Done")

        # Save local copy
        save_dir = Path("output") / "content" / "product_closeup_reel"
        save_dir.mkdir(parents=True, exist_ok=True)
        local_copy = save_dir / f"product_closeup_reel_{record_id}.mp4"
        shutil.copyfile(mp4_path, local_copy)
        print(f"[OK] Local video saved to: {local_copy}")

    return True


def pending_record_ids(clients: Clients) -> list[str]:
    pending: list[str] = []
    for record in clients.airtable.list_records(list(ALL_READ_FIELDS)):
        row = record.get("fields", {})
        status = str(row.get(STATUS_FIELD) or "").strip().lower()
        # Strictly skip any row that has status 'Done'
        if status == STATUS_DONE.lower():
            continue
        has_any_product = any(bool(row.get(f)) for f in FURNITURE_FIELDS.values())
        if has_any_product:
            pending.append(record["id"])
    return pending


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Product Closeup Reel Automation Pipeline for table tblqBZ946hVdOpmDV."
    )
    parser.add_argument(
        "--table-id",
        default=DEFAULT_TABLE_ID,
        help=f"Destination Airtable Table ID (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--phase",
        choices=["all", "scrape", "generate"],
        default="all",
        help="Which phase to run (default: all)",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Process a single specific Airtable record ID",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=1,
        help="How many rows to process (default: 1; use 0 for all)",
    )
    parser.add_argument(
        "--style",
        default=DEFAULT_STYLE,
        help="Akeneo style filter (default: modern)",
    )
    parser.add_argument(
        "--with-music",
        action="store_true",
        help="Enable Fal ElevenLabs background music generation (default: False / silent reel)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-processing even if record is already marked Done",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    global MUSIC_ENABLED
    load_dotenv()
    args = parse_args(argv)

    if args.with_music:
        MUSIC_ENABLED = True

    clients = Clients(args.table_id)
    print(f"[TARGET] Airtable Base: {clients.settings.airtable_base_id} | Table ID: {args.table_id}")

    if args.record_id:
        return 0 if process_row(clients, args.record_id, force=args.force) else 1

    limit = None if (args.max_rows is None or args.max_rows <= 0) else args.max_rows

    if args.phase == "scrape":
        phase1_scrape(clients, limit, args.style)
        return 0

    if args.phase == "generate":
        ids = pending_record_ids(clients)
        if limit is not None:
            ids = ids[:limit]
        if not ids:
            print("[OK] No pending rows to process.")
            return 0
        print(f"[INFO] Processing {len(ids)} pending row(s) end-to-end...")
        failures = sum(0 if process_row(clients, rid) else 1 for rid in ids)
        return 1 if failures else 0

    # Phase all -- MANDATORY RULE: Always generate brand-new rows!
    # Every run scrapes 4 fresh active products into a brand-new row and processes it end-to-end.
    # NEVER search for, pick up, or re-run remaining, old, or incomplete rows in the table.
    akeneo = clients.akeneo()
    akeneo.authenticate()
    pairs = _plan_new_pairs(clients, args.style, akeneo)
    if not pairs:
        print("[ERROR] No eligible active table lamps found for new row.")
        return 1

    done = 0
    failures = 0
    target_count = limit or 1
    for pair in pairs[:target_count]:
        print(f"\n===== BRAND-NEW ROW {done + 1} of {target_count} (Fresh Scrape & Process End-to-End) =====")
        record_id = _create_row_from_pair(clients, pair, akeneo)
        if not record_id:
            failures += 1
            continue
        if process_row(clients, record_id):
            done += 1
        else:
            failures += 1

    if done == 0 and failures == 0:
        print("[OK] Nothing to do -- no new products available.")
        return 0
    print(f"\n[OK] Finished {done} brand-new row(s) end-to-end; {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        sys.exit(2)
