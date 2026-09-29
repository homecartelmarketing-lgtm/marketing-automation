#!/usr/bin/env python3
"""One at a time Lights Reel Automation Pipeline (9:16).

Target Table: ``tblJpEtBudQZda319`` -- "One at a time Lights".

Phases
------
    Phase 1  Scrape 3 fresh lighting fixtures from Akeneo (Table Lamp, Ceiling Mounted, Pendant Light)
             -> Scraped Item 1..3 attachments + "Scraped Items" longText.
             Status -> "In progress".
    Phase 2  Generate 1 bedroom interior (Krea, 9:16, dark dusk scene)
             -> "Living Room Interior".
    Phase 3  ONE Claude call (anthropic/claude-sonnet-5) over [interior + 3 items]
             -> "Blending Prompt" (standard vision blending prompt for all 3 fixtures).
    Phase 4  Initial Room Blend (fal-ai/nano-banana-pro/edit, 9:16 1K)
             -> "Blended Image" (all 3 fixtures installed and illuminated).
    Phase 5  Progressive Lighting Variations (Fal Nano Banana Pro from "Blended Image"):
             - Variation 1: Table Lamp ON only (YOLO tagged) -> "Converted Image1"
             - Variation 2: Ceiling Mounted ON only (YOLO tagged) -> "Converted Image2"
             - Variation 3: Pendant Light ON only (YOLO tagged) -> "Converted Image3"
    Phase 6  Local FFmpeg in-place crossfade assembly (zero API cost):
             Sequence: Converted Image1 (2s) -> Converted Image2 (2s) ->
                       Converted Image3 (2s) -> Blended Image (2s) -> Outro (2.5s)
             Transitions: 0.8s smooth in-place crossfade dissolve.
             No black fade-in, silent audio for now.
             Converted Images 1, 2, 3 feature floating YOLO luxury item name tags.
             Blended Image stays clean with no tags (full illuminated bedroom reveal).
             -> "Final Video".
             Status -> "Done" (PHT timestamp auto-stamped).

Usage::
    python run_one_at_a_time_lights_reel.py --phase all --max-rows 1
    python run_one_at_a_time_lights_reel.py --record-id recXXXXXXXX
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
import requests
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.config import load_settings
from content_automation.errors import AutomationError, ProviderError
from content_automation.fal_client import FalClient
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

DEFAULT_TABLE_ID = "tblJpEtBudQZda319"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_ONE_AT_A_TIME_LIGHTS"

# 3 dedicated categories for the 3 slots per row
SLOTS = (1, 2, 3)
SLOT_CATEGORIES: dict[int, str] = {
    1: "table_lamps",
    2: "ceiling_lights",     # ceiling mounted
    3: "pendant_lights",
}
SLOT_LABELS: dict[int, str] = {
    1: "Table Lamp",
    2: "Ceiling Mounted Light",
    3: "Pendant Light",
}
ITEMS_PER_ROW = 3
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

# Krea interior generation (Phase 2) -- modern luxury bedroom
INTERIOR_MOODBOARD_ENV = "KREA_MOODBOARD_ID_ONE_AT_A_TIME_LIGHTS"
DEFAULT_MOODBOARD_ID = "fb2487fb-2895-4d2c-9758-805aaf1bac69"
INTERIOR_PROMPT = os.getenv(
    "PROMPT_ONE_AT_A_TIME_LIGHTS_REEL_INTERIOR",
    "Generate me a modern bedroom",
).strip() or "Generate me a modern bedroom"
INTERIOR_ASPECT_RATIO = "9:16"
INTERIOR_RESOLUTION = "1K"

# Fal Claude Sonnet (Phase 3)
CLAUDE_MODEL = "anthropic/claude-sonnet-5"

# Fal Nano Banana Pro (Phases 4 & 5)
NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"
BLEND_ASPECT_RATIO = "9:16"
BLEND_RESOLUTION = "1K"

# HomeCartel outro (Phase 6)
OUTRO_CANDIDATES = [
    Path(__file__).parent / "Outro for All Reels" / "Outro.jpg",
    Path(__file__).parent / "assets" / "outro_layout.jpg",
    Path("Outro for All Reels/Outro.jpg"),
    Path("assets/outro_layout.jpg"),
]
OUTRO_FIELD = "Outro"
OUTRO_SECONDS = 2.5

# Video timing constants (Phase 6 FFmpeg Crossfade)
HOLD_DURATION_SECONDS = 2.0
CROSSFADE_DURATION_SECONDS = 0.8
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Airtable field names for tblJpEtBudQZda319
STATUS_FIELD = "Status"
STATUS_IN_PROGRESS = "In progress"
STATUS_DONE = "Done"

SCRAPED_FIELDS = {
    1: "Scraped Item 1",
    2: "Scraped Item 2",
    3: "Scraped Item 3",
}
SCRAPED_ITEMS_FIELD = "Scraped Items"
SELECTED_ITEMS_FIELD = "Selected Items"
INTERIOR_FIELD = "Living Room Interior"
BLEND_PROMPT_FIELD = "Blending Prompt"
BLENDED_IMAGE_FIELD = "Blended Image"
CONVERTED_IMAGE_1_FIELD = "Converted Image1"
CONVERTED_IMAGE_2_FIELD = "Converted Image2"
CONVERTED_IMAGE_3_FIELD = "Converted Image3"
FINAL_VIDEO_FIELD = "Final Video"

ALL_READ_FIELDS = [
    STATUS_FIELD,
    SCRAPED_ITEMS_FIELD,
    SELECTED_ITEMS_FIELD,
    INTERIOR_FIELD,
    BLEND_PROMPT_FIELD,
    BLENDED_IMAGE_FIELD,
    CONVERTED_IMAGE_1_FIELD,
    CONVERTED_IMAGE_2_FIELD,
    CONVERTED_IMAGE_3_FIELD,
    FINAL_VIDEO_FIELD,
    OUTRO_FIELD,
    *SCRAPED_FIELDS.values(),
]

REQUIRED_FIELDS: dict[str, str] = {
    "Foreign Key ID": "singleLineText",
    "ID": "number",
    "Date and Time Generated": "dateTime",
    STATUS_FIELD: "singleSelect",
    SCRAPED_ITEMS_FIELD: "multilineText",
    BLEND_PROMPT_FIELD: "multilineText",
    OUTRO_FIELD: "multipleAttachments",
    **{name: "multipleAttachments" for name in SCRAPED_FIELDS.values()},
    INTERIOR_FIELD: "multipleAttachments",
    BLENDED_IMAGE_FIELD: "multipleAttachments",
    CONVERTED_IMAGE_1_FIELD: "multipleAttachments",
    CONVERTED_IMAGE_2_FIELD: "multipleAttachments",
    CONVERTED_IMAGE_3_FIELD: "multipleAttachments",
    FINAL_VIDEO_FIELD: "multipleAttachments",
}

VARIATION_CONFIG: dict[int, dict[str, str]] = {
    1: {
        "field": CONVERTED_IMAGE_1_FIELD,
        "filename": "oatl_lamp_on.jpg",
        "description": "Table Lamp ON only",
        "prompt": (
            "In this exact room, turn off the ceiling mounted light and pendant light completely. "
            "Make sure all room corners and the photo are dark, with only the bedside table lamp turned on, "
            "casting a warm golden glow onto the nightstand and nearby wall."
        ),
    },
    2: {
        "field": CONVERTED_IMAGE_2_FIELD,
        "filename": "oatl_ceiling_on.jpg",
        "description": "Ceiling Mounted ON only",
        "prompt": (
            "In this exact room, turn off the pendant light and table lamp completely. "
            "Make sure all room corners and the photo are dark, with only the ceiling mounted light turned on, "
            "casting an architectural ambient glow downward across the ceiling and room."
        ),
    },
    3: {
        "field": CONVERTED_IMAGE_3_FIELD,
        "filename": "oatl_pendant_on.jpg",
        "description": "Pendant Light ON only",
        "prompt": (
            "In this exact room, turn off the ceiling mounted light and table lamp completely. "
            "Make sure all room corners and the photo are dark, with only the pendant light turned on, "
            "casting a focused warm pool of light downward."
        ),
    },
}


# --------------------------------------------------------------------------
# Helpers & Prompt Construction
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


def _download_url(url: str, destination: Path, timeout: int = 600) -> Path:
    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    return destination


def _display_name(item: ProductItem) -> str:
    name = (item.item_name or "").strip()
    ptype = (item.product_type or "").strip()
    if ptype and ptype.lower() not in name.lower():
        return f"{name} | {ptype}"
    return name


def build_multi_fixture_blending_instruction(
    table_lamp_name: str,
    ceiling_light_name: str,
    pendant_light_name: str,
    interior_label: str = "Modern Bedroom Interior",
    aspect_ratio: str = "9:16",
) -> str:
    """Standardized vision blending instruction for 3 distinct fixtures (matching existing content style)."""
    return (
        f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the {interior_label} photo, "
        f"Image 2 as the product photo for Table Lamp '{table_lamp_name}', "
        f"Image 3 as the product photo for Ceiling Mounted Light '{ceiling_light_name}', and "
        f"Image 4 as the product photo for Pendant Light '{pendant_light_name}'.\n"
        f"First, visually examine Image 2, Image 3, and Image 4 to identify the exact lighting fixture types, physical forms, "
        f"materials, and proportions of each of the 3 fixtures.\n"
        f"Generate a detailed, highly specific image-blending prompt for Nano Banana Pro ({aspect_ratio} aspect ratio) "
        f"to seamlessly install and integrate all 3 lighting fixtures into the interior room in Image 1:\n"
        f"RULES:\n"
        f"1. Seamlessly integrate ALL THREE fixtures into the scene at once:\n"
        f"   - Place Table Lamp '{table_lamp_name}' (from Image 2) naturally on the bedside nightstand or table surface with realistic contact shadows.\n"
        f"   - Install Ceiling Mounted Light '{ceiling_light_name}' (from Image 3) mounted securely and flush centered on the ceiling with realistic architectural ceiling contact.\n"
        f"   - Hang Pendant Light '{pendant_light_name}' (from Image 4) suspended gracefully from the ceiling with proper canopy, suspension cord or rod, at an architecturally appropriate viewing height.\n"
        f"2. Remove, replace, or clear any pre-existing competing lighting fixtures in those target locations in Image 1.\n"
        f"3. Ensure authentic material textures (metals, brass, glass, fabrics, ceramics), warm ambient illumination (2700K-3000K) naturally casting soft light and subtle ambient shadows onto surrounding furniture and architecture, and photorealistic 8k styling.\n"
        f"4. Strictly maintain the exact room composition, wall color, architectural textures, and layout from Image 1.\n"
        f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
    )


def clean_claude_prompt(raw: str) -> str:
    """Extract clean prompt text from Claude's response (fences/quotes stripped)."""
    text = (raw or "").strip()
    if not text:
        return ""
    fenced = re.search(r"```(?:text)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return text.strip('"').strip("'").strip()


def assemble_in_place_crossfade_video(
    image_paths: list[Path],
    output_path: Path,
    *,
    hold_duration: float = HOLD_DURATION_SECONDS,
    crossfade_duration: float = CROSSFADE_DURATION_SECONDS,
    outro_path: Path | None = None,
    outro_duration: float = OUTRO_SECONDS,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    fps: int = VIDEO_FPS,
) -> Path:
    """Assemble a seamless vertical video using FFmpeg in-place crossfades between lighting states.

    The room remains stationary while the lighting switches smoothly from state to state.
    NO black opening fade, NO sliding cards/slideshow effects.
    """
    if not image_paths:
        raise AutomationError("Cannot assemble video without image paths")

    media_paths = [p for p in image_paths if p.is_file()]
    has_outro = outro_path is not None and outro_path.is_file()
    if has_outro and outro_path:
        media_paths.append(outro_path)

    total_media = len(media_paths)
    if total_media == 0:
        raise AutomationError("No valid media files found for video assembly")

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    durations: list[float] = []
    for i in range(total_media):
        is_last = (i == total_media - 1)
        dur = outro_duration if (is_last and has_outro) else hold_duration
        # Add crossfade buffer so input stream does not run out of frames during xfade
        durations.append(dur + crossfade_duration)

    cmd = [ffmpeg_bin, "-y"]
    for p, dur in zip(media_paths, durations):
        cmd.extend(["-loop", "1", "-t", f"{dur:.2f}", "-i", str(p)])

    fc: list[str] = []
    for i in range(total_media):
        fc.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]"
        )

    if total_media == 1:
        fc_out = "[v0]"
    else:
        prev = "v0"
        offset = hold_duration
        for i in range(total_media - 1):
            nxt = f"v{i + 1}"
            out_lbl = f"xf{i}" if i < total_media - 2 else "vout"
            fc.append(
                f"[{prev}][{nxt}]xfade=transition=fade:duration={crossfade_duration:.2f}:offset={offset:.2f}[{out_lbl}]"
            )
            prev = out_lbl
            offset += hold_duration
        fc_out = "[vout]"

    cmd.extend([
        "-filter_complex", ";".join(fc),
        "-map", fc_out,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AutomationError(
            f"FFmpeg assembly failed (exit code {result.returncode}):\n{result.stderr[-800:]}"
        )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise AutomationError("FFmpeg finished but output MP4 was not created or is empty")

    return output_path


# --------------------------------------------------------------------------
# Clients
# --------------------------------------------------------------------------


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
# Schema Provisioning & Phase 1 -- Scrape 3 Fresh Fixtures
# --------------------------------------------------------------------------


def _ensure_schema(clients: Clients) -> None:
    clients.airtable.ensure_fields(REQUIRED_FIELDS)
    clients.airtable.ensure_single_select_options(
        STATUS_FIELD, [STATUS_IN_PROGRESS, STATUS_DONE]
    )
    print("[OK] Airtable schema ready (fields + Status options).")


def _scrape_candidates_for_slot(
    clients: Clients,
    akeneo: AkeneoClient,
    category: str,
    style: str,
    needed: int,
    all_existing_filenames: set[str],
    all_existing_names: set[str],
    all_existing_skus: set[str],
    shopify_index: Any | None,
) -> list[ProductItem]:
    akeneo_category = categories.akeneo_category_code(category)
    query: dict[str, Any] = {
        "categories": [{"operator": "IN", "value": [akeneo_category]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    if style and style.lower() != "all":
        query["Style2"] = [{"operator": "IN", "value": [style]}]

    print(f"[INFO] Fetching {style} {category} products from Akeneo...")
    products = akeneo.fetch_products(query)

    existing_names_query, existing_media_query = existing_product_identities(
        products, all_existing_skus
    )
    combined_names = all_existing_names | existing_names_query

    selected, _stats = select_new_products(
        products,
        all_existing_skus,
        existing_item_names=combined_names,
        existing_media_codes=existing_media_query,
        category_code=category,
    )

    candidates: list[ProductItem] = []
    for item in selected:
        fn = attachment_filename(item.item_name, item.media_code)
        if identity_key(fn) in all_existing_filenames:
            print(f"[DEDUP SKIP] Existing photo: '{item.item_name}' (SKU: {item.sku})")
            continue
        if item.sku and item.sku.strip() in all_existing_skus:
            print(f"[DEDUP SKIP] Existing SKU: '{item.item_name}' (SKU: {item.sku})")
            continue
        if (item.item_name or "").strip().lower() in all_existing_names:
            print(f"[DEDUP SKIP] Existing Name: '{item.item_name}'")
            continue
        if shopify_index and not shopify_index.contains(item.sku, item.item_name):
            print(
                f"[SHOPIFY DRAFT/INACTIVE SKIP] Item '{item.item_name}' (SKU: {item.sku}) "
                "is Enabled in Akeneo but Draft/Inactive on Shopify -> skipping"
            )
            continue

        print(f"[DEDUP PASS] New unique {category} product selected: '{item.item_name}' (SKU: {item.sku})")
        candidates.append(item)
        all_existing_filenames.add(identity_key(fn))
        all_existing_skus.add((item.sku or "").strip())
        all_existing_names.add((item.item_name or "").strip().lower())
        if len(candidates) >= needed:
            break

    return candidates


def _scrape_candidates_grouped(
    clients: Clients, akeneo: AkeneoClient, style: str, num_rows: int
) -> list[list[ProductItem]]:
    """Scrape exactly 3 fixtures per row: Slot 1 Table Lamp, Slot 2 Ceiling Mounted, Slot 3 Pendant Light."""
    # 1. Base-wide deduplication
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

    all_existing_filenames = set(base_filenames)
    all_existing_names = set(base_names)
    all_existing_skus = set(base_skus)

    # 2. Existing identities in current table
    for record in clients.airtable.list_records(list(ALL_READ_FIELDS)):
        row = record.get("fields", {})
        for scraped_field in SCRAPED_FIELDS.values():
            att_list = row.get(scraped_field)
            if isinstance(att_list, list):
                for a in att_list:
                    if isinstance(a, dict) and a.get("filename"):
                        all_existing_filenames.add(identity_key(a["filename"]))
        for line in str(row.get(SCRAPED_ITEMS_FIELD) or "").splitlines():
            if line.strip():
                all_existing_names.add(line.strip().lower())

    # 3. Shopify published catalog cross-check (strict Active & Published)
    shopify_index = None
    try:
        print("[INFO] Loading published catalog from Shopify (homecartel.net)...")
        shopify = ShopifyClient()
        shopify_index = shopify.load_published_identities()
        print(
            f"[OK] Shopify Index Ready: {len(shopify_index.skus)} published SKU(s), "
            f"{len(shopify_index.titles)} title(s) indexed."
        )
    except Exception as s_err:
        print(f"[WARN] Shopify index check skipped: {s_err}")

    # 4. Scrape per slot
    slot_candidates: dict[int, list[ProductItem]] = {}
    for slot in SLOTS:
        category = SLOT_CATEGORIES[slot]
        items = _scrape_candidates_for_slot(
            clients,
            akeneo,
            category=category,
            style=style,
            needed=num_rows,
            all_existing_filenames=all_existing_filenames,
            all_existing_names=all_existing_names,
            all_existing_skus=all_existing_skus,
            shopify_index=shopify_index,
        )
        slot_candidates[slot] = items
        print(f"[INFO] Slot {slot} ({category}): found {len(items)}/{num_rows} candidate(s).")

    min_available = min(len(slot_candidates[s]) for s in SLOTS)
    if min_available == 0:
        print("[WARN] Not all 3 lighting categories have available fresh products.")
        return []

    rows: list[list[ProductItem]] = []
    for r in range(min_available):
        row = [slot_candidates[slot][r] for slot in SLOTS]
        rows.append(row)

    print(f"[PLAN] Assembled {len(rows)} complete 3-fixture row group(s).")
    return rows


def _create_row(clients: Clients, items: list[ProductItem], akeneo: AkeneoClient) -> str | None:
    lines = []
    for slot, item in zip(SLOTS, items):
        label = SLOT_LABELS.get(slot, "Fixture")
        lines.append(
            f"Slot {slot} ({label}) | {_display_name(item)} | SKU {item.sku or '-'} | {SLOT_CATEGORIES[slot]}"
        )
    fields: dict[str, Any] = {
        STATUS_FIELD: STATUS_IN_PROGRESS,
        SCRAPED_ITEMS_FIELD: "\n".join(lines),
    }
    try:
        record_id = clients.airtable.create_record(fields)
    except Exception as error:
        print(f"[ERROR] Could not create row: {error}")
        return None

    ok = True
    for slot, item in zip(SLOTS, items):
        try:
            downloaded = akeneo.download_media(item.media_code)
            filename = f"{item.sku or 'fixture'}_{item.media_code}.jpg"
            clients.airtable.upload_attachment(
                record_id, SCRAPED_FIELDS[slot], downloaded, filename
            )
            print(f"[OK] Slot {slot} ({SLOT_LABELS[slot]}): {item.sku} -> {record_id} / {SCRAPED_FIELDS[slot]}")
        except Exception as error:
            print(f"[ERROR] Upload product {item.sku} into slot {slot}: {error}")
            ok = False
    if not ok:
        print(f"[WARN] Row {record_id} created but one or more product uploads failed.")
    return record_id


def phase1_scrape(clients: Clients, max_rows: int | None, style: str) -> int:
    print("=" * 68)
    print("PHASE 1 -- Scrape 3 fresh lighting fixtures (Table, Ceiling, Pendant)")
    print("=" * 68)

    akeneo = clients.akeneo()
    akeneo.authenticate()

    groups = _scrape_candidates_grouped(clients, akeneo, style, max_rows or 1)
    if not groups:
        print("[OK] Not enough fresh active lighting fixtures to create a row.")
        return 0

    created = 0
    for index, group in enumerate(groups, start=1):
        print(f"[INFO] Creating row {index}/{len(groups)} with 3 lighting fixtures...")
        if _create_row(clients, group, akeneo):
            created += 1

    print(f"[OK] Phase 1 complete: created {created} row(s).")
    return created


# --------------------------------------------------------------------------
# Phase 2 -- Generate 1 Bedroom Interior (Krea, 9:16)
# --------------------------------------------------------------------------


def phase2_interior(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("  [Phase 2] Generating bedroom interior (Krea)...")
    if _first_attachment_url(fields, INTERIOR_FIELD):
        print("    [SKIP] interior already attached")
        return
    moodboard_id = os.getenv(INTERIOR_MOODBOARD_ENV, "").strip() or DEFAULT_MOODBOARD_ID
    prompt = os.getenv("PROMPT_ONE_AT_A_TIME_LIGHTS_REEL_INTERIOR", "").strip() or INTERIOR_PROMPT
    if not moodboard_id:
        print(
            f"    [WARN] {INTERIOR_MOODBOARD_ENV} is empty -- generating WITHOUT a moodboard reference."
        )
    url = clients.krea.generate(
        prompt=prompt,
        aspect_ratio=INTERIOR_ASPECT_RATIO,
        resolution=INTERIOR_RESOLUTION,
        moodboard_id=moodboard_id,
    )
    updates = {INTERIOR_FIELD: [{"url": url}]}
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print("    [OK] bedroom interior generated")


# --------------------------------------------------------------------------
# Phase 3 -- Claude Vision Blending Prompt (Standard Vision Prompt for 3 Fixtures)
# --------------------------------------------------------------------------


def _extract_slot_item_names(fields: dict[str, Any]) -> dict[int, str]:
    """Extract item names for slots 1, 2, and 3 from Scraped Items text."""
    slot_names: dict[int, str] = {
        1: "Table Lamp",
        2: "Ceiling Mounted Light",
        3: "Pendant Light",
    }
    raw_text = str(fields.get(SCRAPED_ITEMS_FIELD) or fields.get(SELECTED_ITEMS_FIELD) or "")
    for line in raw_text.splitlines():
        match = re.match(r"Slot (\d+).*?\|\s*(.+?)\s*\|\s*SKU", line.strip())
        if match:
            slot_names[int(match.group(1))] = match.group(2).strip()
    return slot_names


def phase3_claude(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("  [Phase 3] Claude Sonnet 5 vision blending prompt for all 3 fixtures...")
    if str(fields.get(BLEND_PROMPT_FIELD) or "").strip():
        print("    [SKIP] Blending prompt already present")
        return

    interior_url = _first_attachment_url(fields, INTERIOR_FIELD)
    lamp_url = _first_attachment_url(fields, SCRAPED_FIELDS[1])
    ceiling_url = _first_attachment_url(fields, SCRAPED_FIELDS[2])
    pendant_url = _first_attachment_url(fields, SCRAPED_FIELDS[3])

    if not interior_url or not lamp_url or not ceiling_url or not pendant_url:
        raise AutomationError(
            "Phase 3 requires Living Room Interior + all 3 Scraped Item attachments (Lamp, Ceiling, Pendant)"
        )

    slot_names = _extract_slot_item_names(fields)
    instruction = build_multi_fixture_blending_instruction(
        table_lamp_name=slot_names[1],
        ceiling_light_name=slot_names[2],
        pendant_light_name=slot_names[3],
        interior_label="Modern Luxury Bedroom Interior",
        aspect_ratio=BLEND_ASPECT_RATIO,
    )

    raw = clients.fal.generate_vision_prompt(
        image_urls=[interior_url, lamp_url, ceiling_url, pendant_url],
        prompt=instruction,
        model=CLAUDE_MODEL,
    )
    clean_prompt = clean_claude_prompt(raw)
    if not clean_prompt:
        raise AutomationError("Claude Sonnet 5 returned empty blending prompt")

    updates = {BLEND_PROMPT_FIELD: clean_prompt}
    clients.airtable.update_records([(record_id, updates)])
    fields.update(updates)
    print(f"    [OK] Blending prompt generated ({len(clean_prompt)} chars)")


# --------------------------------------------------------------------------
# Phase 4 -- Initial Room Blend (Fal Nano Banana Pro -> "Blended Image")
# --------------------------------------------------------------------------


def phase4_blend(clients: Clients, fields: dict[str, Any], workdir: Path, record_id: str, force: bool = False) -> Path:
    print("  [Phase 4] Initial room blend with all 3 fixtures (Fal Nano Banana Pro)...")
    destination = workdir / "oatl_blended.jpg"
    existing_blended = _first_attachment_url(fields, BLENDED_IMAGE_FIELD)
    if existing_blended and not force:
        print("    [SKIP] blended image already attached -> reusing existing blend")
        _download_url(existing_blended, destination, timeout=120)
        return destination

    interior_url = _first_attachment_url(fields, INTERIOR_FIELD)
    lamp_url = _first_attachment_url(fields, SCRAPED_FIELDS[1])
    ceiling_url = _first_attachment_url(fields, SCRAPED_FIELDS[2])
    pendant_url = _first_attachment_url(fields, SCRAPED_FIELDS[3])
    blend_prompt = str(fields.get(BLEND_PROMPT_FIELD) or "").strip()

    if not interior_url or not blend_prompt:
        raise AutomationError("Phase 4 requires Living Room Interior + Blending Prompt")

    result_url = clients.fal.generate(
        prompt=blend_prompt,
        image_urls=[interior_url, lamp_url, ceiling_url, pendant_url],
        aspect_ratio=BLEND_ASPECT_RATIO,
        resolution=BLEND_RESOLUTION,
        model=NANO_BANANA_MODEL,
    )
    _download_url(result_url, destination, timeout=120)
    clients.airtable.upload_attachment(record_id, BLENDED_IMAGE_FIELD, destination, "oatl_blended.jpg")
    fields[BLENDED_IMAGE_FIELD] = [{"url": result_url}]
    print(f"    [OK] Initial room blend uploaded -> {destination.name}")
    return destination


# --------------------------------------------------------------------------
# Phase 5 -- Progressive Lighting Variations (Fal Nano Banana Pro)
# --------------------------------------------------------------------------


def _tag_variation_image(
    image_path: Path,
    raw_item_name: str,
    default_product_type: str,
    category: str,
) -> Path:
    """Stamp 2-line floating product tag beside the active fixture using YOLO-World."""
    try:
        title, product_type = split_item_name(
            raw_item_name, fallback_product_type=default_product_type
        )
        tag_blended_image(
            image_input=image_path,
            item_name=title,
            product_type=product_type,
            category=category,
            destination=image_path,
            fallback_if_undetected=True,
        )
        print(f"    [YOLO TAG] Stamped '{title} | {product_type}' onto {image_path.name}")
    except Exception as err:
        print(f"    [WARN] YOLO tagging notice on {image_path.name}: {err}")
    return image_path


def phase5_variations(
    clients: Clients, fields: dict[str, Any], workdir: Path, record_id: str, force: bool = False
) -> dict[int, Path]:
    print("  [Phase 5] Generating 3 lighting variations from Blended Image (Fal Nano Banana Pro)...")
    blended_url = _first_attachment_url(fields, BLENDED_IMAGE_FIELD)
    if not blended_url:
        raise AutomationError("Phase 5 requires Blended Image attachment URL")

    slot_names = _extract_slot_item_names(fields)

    def process_variation(var_idx: int) -> tuple[int, Path]:
        cfg = VARIATION_CONFIG[var_idx]
        field_name = cfg["field"]
        dest = workdir / cfg["filename"]

        category = SLOT_CATEGORIES.get(var_idx, "")
        default_type = SLOT_LABELS.get(var_idx, "Fixture")
        raw_name = slot_names.get(var_idx, default_type)

        existing_url = _first_attachment_url(fields, field_name)
        if existing_url and not force:
            print(f"    [SKIP] {field_name} ({cfg['description']}) already attached -> reusing")
            _download_url(existing_url, dest, timeout=120)
            return var_idx, dest

        print(f"    -> Generating {cfg['description']} ({field_name})...")
        result_url = clients.fal.generate(
            prompt=cfg["prompt"],
            image_urls=[blended_url],
            aspect_ratio=BLEND_ASPECT_RATIO,
            resolution=BLEND_RESOLUTION,
            model=NANO_BANANA_MODEL,
        )
        _download_url(result_url, dest, timeout=120)

        # Apply YOLO item name tagging before uploading to Airtable
        _tag_variation_image(dest, raw_name, default_type, category)

        clients.airtable.upload_attachment(record_id, field_name, dest, cfg["filename"])
        fields[field_name] = [{"url": result_url}]
        print(f"    [OK] {field_name} ({cfg['description']}) uploaded -> {dest.name}")
        return var_idx, dest

    results: dict[int, Path] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_variation, idx) for idx in (1, 2, 3)]
        for fut in futures:
            idx, path = fut.result()
            results[idx] = path

    return results


# --------------------------------------------------------------------------
# Phase 6 -- FFmpeg In-Place Crossfade Mux & Outro
# --------------------------------------------------------------------------


def _resolve_outro(
    clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path
) -> Path | None:
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


def phase6_assembly(
    clients: Clients,
    record_id: str,
    fields: dict[str, Any],
    workdir: Path,
    variation_paths: dict[int, Path],
    blended_path: Path,
) -> Path:
    print("  [Phase 6] Assembling seamless in-place crossfade reel with FFmpeg...")
    outro = _resolve_outro(clients, record_id, fields, workdir)

    # Sequence: Converted Image1 -> Converted Image2 -> Converted Image3 -> Blended Image
    sequence_paths = [
        variation_paths[1],
        variation_paths[2],
        variation_paths[3],
        blended_path,
    ]

    output = workdir / f"one_at_a_time_lights_reel_{record_id}.mp4"
    assemble_in_place_crossfade_video(
        image_paths=sequence_paths,
        output_path=output,
        hold_duration=HOLD_DURATION_SECONDS,
        crossfade_duration=CROSSFADE_DURATION_SECONDS,
        outro_path=outro,
        outro_duration=OUTRO_SECONDS,
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
        fps=VIDEO_FPS,
    )

    clients.airtable.upload_attachment(
        record_id, FINAL_VIDEO_FIELD, output, f"one_at_a_time_lights_reel_{record_id}.mp4"
    )
    clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_DONE})])
    print("    [OK] Final Video uploaded & Status = Done (PHT timestamp auto-stamped)")
    return output


# --------------------------------------------------------------------------
# End-to-end row processor
# --------------------------------------------------------------------------


def process_row(clients: Clients, record_id: str, force: bool = False) -> bool:
    print(f"\n[ROW {record_id}] Processing One at a time Lights Reel...")
    record = clients.airtable.record(record_id)
    fields = dict(record.get("fields", {}))

    if not force and str(fields.get(STATUS_FIELD) or "").strip().lower() == STATUS_DONE.lower():
        print(
            f"[ROW {record_id}] Status is 'Done' -- strictly skipping "
            "(will not re-run even if any phase is missing; use --force to re-generate)."
        )
        return True

    # Mark In progress
    clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_IN_PROGRESS})])

    # Phase 2: Krea bedroom interior
    phase2_interior(clients, record_id, fields)

    # Phase 3: Claude vision prompt
    phase3_claude(clients, record_id, fields)

    # Phases 4-6: blend, 3 lighting variations, in-place crossfade assembly
    with tempfile.TemporaryDirectory(prefix=f"oatl_{record_id}_") as tmpdir:
        workdir = Path(tmpdir)
        blended_path = phase4_blend(clients, fields, workdir, record_id, force=force)
        variation_paths = phase5_variations(clients, fields, workdir, record_id, force=force)
        final_path = phase6_assembly(clients, record_id, fields, workdir, variation_paths, blended_path)

        # Save local copy
        save_dir = Path("output") / "content" / "one_at_a_time_lights_reel"
        save_dir.mkdir(parents=True, exist_ok=True)
        local_copy = save_dir / final_path.name
        shutil.copyfile(final_path, local_copy)
        print(f"[OK] Local video saved to: {local_copy}")

    return True


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="One at a time Lights Reel Automation Pipeline for table tblJpEtBudQZda319."
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
        "--mode",
        dest="phase",
        choices=["all", "scrape", "generate"],
        help="Alias for --phase",
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
        help="How many brand-new rows to create and process (default: 1)",
    )
    parser.add_argument(
        "--max-items",
        dest="max_rows",
        type=int,
        help="Alias for --max-rows",
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
    load_dotenv()
    args = parse_args(argv)

    clients = Clients(args.table_id)
    _ensure_schema(clients)
    print(f"[TARGET] Airtable Base: {clients.settings.airtable_base_id} | Table ID: {args.table_id}")

    if args.record_id:
        return 0 if process_row(clients, args.record_id, force=args.force) else 1

    if args.phase == "generate":
        print("[ERROR] --phase generate requires --record-id (existing rows are never re-run automatically).")
        return 1

    akeneo = clients.akeneo()
    akeneo.authenticate()

    groups = _scrape_candidates_grouped(clients, akeneo, args.style, args.max_rows or 1)
    if not groups:
        print("[ERROR] Not enough fresh active lighting fixtures found for a new row.")
        return 1

    if args.phase == "scrape":
        created = 0
        for index, group in enumerate(groups, start=1):
            print(f"[INFO] Creating row {index}/{len(groups)} with 3 lighting fixtures...")
            if _create_row(clients, group, akeneo):
                created += 1
        print(f"[OK] Phase 1 complete: created {created} row(s).")
        return 0

    # Phase all -- MANDATORY RULE: brand-new rows only, processed end-to-end.
    done = 0
    failures = 0
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
