"""Style This Story AI Pipeline (Krea AI -> Fal Claude Sonnet 5 -> Fal Nano Banana Pro -> Story Cards).

End-to-end automated generation pipeline for Style This Story (9:16 vertical ratio).
Workflow:
  Phase 0: Akeneo Scrape (if needed): Scrapes Floor Lamp -> 'Furniture Item', 'Item Name', 'SKU', 'How would You Layout', 'Double Tap', Status: 'Standby'
  Phase 1: Krea AI 9:16 Interior Generation for 4 slots -> 'Interior', 'Interior2', 'Interior3', 'Interior4' (Moodboard: b1641228-beec-4823-8d01-1de3eec8410d)
  Phase 2: Fal AI Claude Sonnet 5 Vision Prompt Generation -> 'Prompt', 'Prompt2', 'Prompt3', 'Prompt4'
  Phase 3: Fal AI Nano Banana Pro 9:16 Blending -> 'Style This Blended' (4 photos)
  Phase 4: Fal AI Nano Banana Pro Story Cards Conversion:
           - Slide 1: 'How would You Layout' + Blended 1 -> 'how_would_you_style_this.jpg'
           - Slides 2-4: 'Double Tap' + Blended 2-4 -> 'Double Tap Converted' (3 cards)
           - Final 4 Story Cards -> 'STORY - Style This? (4)' & Status: 'Complete'

Usage::

    # Run full end-to-end interactive menu:
    python generate_style_this_story_pipeline.py --mode menu

    # Process 1 row end-to-end:
    python generate_style_this_story_pipeline.py --max-items 1

    # Process specific Record ID:
    python generate_style_this_story_pipeline.py --record-id recXXXXXXXXXXXXXX

    # Dry run test:
    python generate_style_this_story_pipeline.py --dry-run
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any

from PIL import Image
import requests

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.models import LocalImage
from content_automation.overlay import (
    create_style_this_double_tap_slide,
    create_style_this_slide_1,
)
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)

# Category-specific Configuration for Style This Story
STYLE_THIS_CATEGORIES: dict[str, dict[str, Any]] = {
    "floor_lamps": {
        "name": "Floor Lamps",
        "category_code": "floor_lamps",
        "table_id": os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_FLOOR_LAMPS", "").strip() or os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS", "").strip() or "tblvSAzXasTVI85r9",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_STYLE_THIS_FLOOR_LAMPS", "").strip() or "b1641228-beec-4823-8d01-1de3eec8410d",
        "prompt": "Generate me a modern bedroom that have beside a floor lamp",
    },
    "pendant_lights": {
        "name": "Pendant Lights",
        "category_code": "pendant_lights",
        "table_id": os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_PENDANT_LIGHTS", "").strip() or "tblWdz71nULR0TZx7",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_STYLE_THIS_PENDANT_LIGHTS", "").strip() or "0844ad92-c34a-4dc8-9d70-d09498dc098c",
        "prompt": "Generate me a modern dining room",
    },
    "chandeliers": {
        "name": "Chandeliers",
        "category_code": "chandeliers",
        "table_id": os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_CHANDELIER", "").strip() or "tblp6AMYb13NPqkuT",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_STYLE_THIS_CHANDELIER", "").strip() or "fda7090c-787b-4116-94cd-3feef613eaaa",
        "prompt": "Generate me a modern bedroom",
    },
    "wall_lights": {
        "name": "Wall Lights",
        "category_code": "wall_lights",
        "table_id": os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS_WALL_LIGHTS", "").strip() or "tblXJrvSBkJNhRHLa",
        "moodboard_id": os.getenv("KREA_MOODBOARD_ID_STYLE_THIS_WALL_LIGHTS", "").strip() or "b1641228-beec-4823-8d01-1de3eec8410d",
        "prompt": "Generate me a modern living room with a wall light",
    },
}

STYLE_THIS_TABLE_MAP: dict[str, str] = {
    k: v["table_id"] for k, v in STYLE_THIS_CATEGORIES.items()
}
STYLE_THIS_TABLE_MAP["chandelier"] = STYLE_THIS_CATEGORIES["chandeliers"]["table_id"]

STYLE_THIS_MOODBOARD_MAP: dict[str, str] = {
    k: v["moodboard_id"] for k, v in STYLE_THIS_CATEGORIES.items()
}
STYLE_THIS_MOODBOARD_MAP["chandelier"] = STYLE_THIS_CATEGORIES["chandeliers"]["moodboard_id"]

STYLE_THIS_PROMPT_MAP: dict[str, str] = {
    k: v["prompt"] for k, v in STYLE_THIS_CATEGORIES.items()
}
STYLE_THIS_PROMPT_MAP["chandelier"] = STYLE_THIS_CATEGORIES["chandeliers"]["prompt"]

TABLE_ID_TO_CATEGORY_CONFIG: dict[str, dict[str, Any]] = {
    v["table_id"]: v for v in STYLE_THIS_CATEGORIES.values()
}

# Configuration & Defaults
DEFAULT_TABLE_ID = STYLE_THIS_CATEGORIES["floor_lamps"]["table_id"]
DEFAULT_MOODBOARD_ID = STYLE_THIS_CATEGORIES["floor_lamps"]["moodboard_id"]
DEFAULT_CATEGORY = "floor_lamps"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
DEFAULT_INTERIOR_PROMPT = STYLE_THIS_CATEGORIES["floor_lamps"]["prompt"]

ASPECT_RATIO_9_16 = "9:16"
NANO_BANANA_PRO = "fal-ai/nano-banana-pro/edit"
CLAUDE_VISION_MODEL = "anthropic/claude-sonnet-5"

# Airtable Field Mappings
FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"
STATUS_FIELD = "Status"

STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "Processing Interior Generated Photo"
STATUS_GENERATING_PROMPT = "Processing Blending Prompt"
STATUS_BLENDED = "Processing Day Image"
STATUS_COMPLETE = "Complete"

INTERIOR_FIELDS = ["Interior", "Interior2", "Interior3", "Interior4"]
PROMPT_FIELDS = ["Prompt", "Prompt2", "Prompt3", "Prompt4"]
PROMPT_ALT_FIELDS = ["Prompt1", "Prompt2", "Prompt3", "Prompt4"]

BLENDED_FIELD = "Style This Blended"
BLENDED_FILENAMES = ["style_this01.jpg", "style_this02.jpg", "style_this03.jpg", "style_this04.jpg"]

HOW_WOULD_YOU_LAYOUT_FIELD = "How would You Layout"
DOUBLE_TAP_LAYOUT_FIELD = "Double Tap"
DOUBLE_TAP_CONVERTED_FIELD = "Double Tap Converted"

STYLE_THIS_TEXT_FIELDS = [
    "Style This Text Generated1",
    "Style This Text Generated2",
    "Style This Text Generated3",
]
STYLE_THIS_COLOR_FIELDS = [
    "Style This Auto Generated Color1",
    "Style This Auto Generated Color2",
    "Style This Auto Generated Color3",
]

STORY_FINAL_CANDIDATES = [
    "STORY - Style This? (4)",
    "STORY - Style This (4)",
    "STORY - Style This (2)",
    "STORY - Style This",
    "Story Cards",
]
FINAL_FILENAMES = [
    "how_would_you_style_this.jpg",
    "double_tap_blended01.jpg",
    "double_tap_blended02.jpg",
    "double_tap_blended03.jpg",
]

HOW_WOULD_YOU_PROMPT_PATH = Path("JSON Prompts/Style This/how_would_you_layout.json")
DOUBLE_TAP_PROMPT_PATH = Path("JSON Prompts/Style This/double_tap.json")

HOW_LAYOUT_IMG_CANDIDATES = [
    Path("JSON Prompts/Style This/how_would_you_layout.jpg"),
    Path("JSON Prompts/how_would_you_layout.jpg"),
]
DOUBLE_TAP_IMG_CANDIDATES = [
    Path("JSON Prompts/Style This/dobule_tap_layoujt.jpg"),
    Path("JSON Prompts/Style This/double_tap_layout.jpg"),
    Path("JSON Prompts/Style This/double_tap.jpg"),
]


def resolve_table_field(
    airtable: ScrapeAirtableClient,
    candidate_names: list[str],
    default_fallback: str | None = None,
) -> str:
    """Find first matching candidate field in Airtable schema."""
    try:
        schema = airtable.table_fields()
        for name in candidate_names:
            if name in schema:
                return name
    except Exception:
        pass
    return default_fallback or candidate_names[0]


def resolve_status_choice(
    airtable: ScrapeAirtableClient,
    candidate_choices: list[str],
) -> str:
    """Find matching singleSelect choice for Status."""
    try:
        schema = airtable.table_fields()
        status_info = schema.get("Status") or schema.get(STATUS_FIELD)
        if status_info and "choices" in status_info:
            available = status_info["choices"]
            for cand in candidate_choices:
                for c in available:
                    if c.strip().casefold() == cand.strip().casefold():
                        return c
    except Exception:
        pass
    return candidate_choices[0]


def extract_attachment_url(attachments: Any) -> str:
    """Extract accessible HTTP URL from Airtable attachment field."""
    if not attachments:
        return ""
    if isinstance(attachments, list) and len(attachments) > 0:
        first = attachments[0]
        if isinstance(first, dict):
            return str(first.get("url") or "").strip()
    if isinstance(attachments, dict):
        return str(attachments.get("url") or "").strip()
    return ""


def extract_attachment_urls(attachments: Any) -> list[str]:
    """Extract list of accessible HTTP URLs from Airtable attachment field."""
    urls = []
    if isinstance(attachments, list):
        for item in attachments:
            if isinstance(item, dict) and item.get("url"):
                urls.append(str(item["url"]).strip())
            elif isinstance(item, str) and item.startswith("http"):
                urls.append(item.strip())
    elif isinstance(attachments, dict) and attachments.get("url"):
        urls.append(str(attachments["url"]).strip())
    return urls


# ==============================================================================
# PHASE 1: Krea AI 9:16 4-Slot Room Interior Generation
# ==============================================================================

def generate_krea_interiors_for_style_this(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_INTERIOR_PROMPT,
    aspect_ratio: str = ASPECT_RATIO_9_16,
    dry_run: bool = False,
) -> list[str]:
    """Generate 4 9:16 interior room photos using Krea AI for slots 1-4."""
    item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
    print(f"\n  [PHASE 1/4] Generating 4 9:16 Room Interiors with Krea AI (Moodboard: {moodboard_id})...")

    if dry_run:
        print("  [DRY-RUN] Would generate 4 9:16 interior photos with Krea AI.")
        return ["https://dryrun.test/interior_1.jpg"] * 4

    urls: list[str] = []
    for idx, field_name in enumerate(INTERIOR_FIELDS, start=1):
        existing_val = fields.get(field_name)
        existing_url = extract_attachment_url(existing_val)
        if existing_url:
            print(f"  [SKIP] '{field_name}' already populated for {item_label}.")
            urls.append(existing_url)
            continue

        print(f"  [INFO] Generating '{field_name}' ({idx}/4) with Krea AI...")
        downloaded = None
        try:
            image_url = krea.generate(
                prompt,
                aspect_ratio=aspect_ratio,
                moodboard_id=moodboard_id,
            )
            downloaded = krea.download_image(image_url)
            filename = f"interior_{idx}_{record_id}.jpg"
            airtable.upload_attachment(record_id, field_name, downloaded, filename)
            urls.append(image_url)
            print(f"  [OK] Attached Krea image to '{field_name}' on record {record_id}")
        finally:
            if downloaded:
                downloaded.cleanup()

    target_status = resolve_status_choice(airtable, [STATUS_INTERIOR_GENERATED, "Interior Generated", "Standby"])
    airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
    return urls


# ==============================================================================
# PHASE 2: Claude Sonnet 5 Vision Analysis & Blending Prompts for 4 Slots
# ==============================================================================

def generate_blending_prompts_for_style_this(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    interior_urls: list[str],
    furniture_url: str,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Generate 4 detailed blending prompts using Claude Sonnet 5 Vision."""
    item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Modern Floor Lamp").strip()
    print(f"\n  [PHASE 2/4] Analyzing 4 Scenes & Writing Blending Prompts (Claude Sonnet 5 Vision)...")

    if dry_run:
        print("  [DRY-RUN] Would generate 4 Claude Sonnet 5 vision blending prompts.")
        return ["A modern bedroom with floor lamp placed elegantly."] * 4

    prompts: list[str] = []
    updates: dict[str, Any] = {}

    for idx, (int_field, int_url) in enumerate(zip(INTERIOR_FIELDS, interior_urls), start=1):
        target_prompt_field = resolve_table_field(airtable, [f"Prompt{idx}", f"Prompt", f"Prompt {idx}"], f"Prompt{idx}" if idx > 1 else "Prompt")
        existing_prompt = str(fields.get(target_prompt_field) or "").strip()
        if existing_prompt:
            prompts.append(existing_prompt)
            continue

        instruction = (
            f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo ('{int_field}') "
            f"and Image 2 as the product photo for '{item_name}' ('Furniture Item').\n"
            f"Generate a detailed, highly specific image-blending prompt for Nano Banana Pro (9:16 vertical ratio). "
            f"The prompt must describe naturally integrating, positioning, and standing the {item_name} from Image 2 onto the floor space in Image 1.\n"
            f"RULES:\n"
            f"1. The {item_name} shown in Image 2 MUST BE THE ONLY MAIN FLOOR LAMP in the entire final blended scene.\n"
            f"2. Ensure natural floor contact, realistic base shadow, authentic material textures, warm ambient glow (2700K-3000K), and photorealistic 8k styling.\n"
            f"3. Strictly maintain the exact room composition, wall color, architectural textures, and layout from Image 1.\n"
            f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
        )

        raw_prompt = fal.generate_vision_prompt(
            image_urls=[int_url, furniture_url],
            prompt=instruction,
            model=CLAUDE_VISION_MODEL,
        )
        clean_prompt = raw_prompt.strip().strip('"').strip("'")
        prompts.append(clean_prompt)
        updates[target_prompt_field] = clean_prompt
        print(f"  [OK] Generated prompt for slot {idx} ({len(clean_prompt)} chars) -> '{target_prompt_field}'")

    target_status = resolve_status_choice(airtable, [STATUS_GENERATING_PROMPT, "Processing Blending Prompt", "Generating Prompt for Blending"])
    updates[STATUS_FIELD] = target_status
    airtable.update_records([(record_id, updates)])
    return prompts


# ==============================================================================
# PHASE 3: Fal AI Nano Banana Pro 4-Slot Image Blending
# ==============================================================================

def generate_blends_for_style_this(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    interior_urls: list[str],
    furniture_url: str,
    prompts: list[str],
    *,
    dry_run: bool = False,
) -> list[str]:
    """Blend the furniture item into all 4 interiors -> 'Style This Blended'."""
    item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
    print(f"\n  [PHASE 3/4] Blending 4 Room Photos at 9:16 (Fal AI Nano Banana Pro)...")

    if dry_run:
        print("  [DRY-RUN] Would blend 4 photos at 9:16 with Fal AI Nano Banana Pro.")
        return ["https://dryrun.test/blended_1.jpg"] * 4

    existing_blends = extract_attachment_urls(fields.get(BLENDED_FIELD))
    if len(existing_blends) == 4:
        print(f"  [SKIP] 'Style This Blended' already has 4 blended images for {item_label}.")
        return existing_blends

    blended_urls: list[str] = []
    downloaded_files = []

    for idx, (int_url, prompt_text, filename) in enumerate(zip(interior_urls, prompts, BLENDED_FILENAMES), start=1):
        print(f"  [INFO] Blending slot {idx}/4 ({filename})...")
        image_url = fal.generate(
            prompt=prompt_text,
            image_urls=[int_url, furniture_url],
            aspect_ratio=ASPECT_RATIO_9_16,
            model=NANO_BANANA_PRO,
        )
        blended_urls.append(image_url)

        resp = requests.get(image_url, stream=True)
        temp_img = download_to_temp_file(
            resp,
            prefix=f"blend_{idx}_",
            suffix=".jpg",
            context=f"Download blend {idx}",
        )
        downloaded_files.append((temp_img, filename))

    # Upload all 4 blended images to 'Style This Blended'
    target_blended_field = resolve_table_field(airtable, [BLENDED_FIELD, "Style This Blended Image", "Blended Image"], BLENDED_FIELD)
    for temp_img, filename in downloaded_files:
        try:
            airtable.upload_attachment(record_id, target_blended_field, temp_img, filename)
        finally:
            temp_img.cleanup()

    target_status = resolve_status_choice(airtable, [STATUS_BLENDED, "Blended Image Generated", "Processing Day Image"])
    airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
    print(f"  [OK] Uploaded 4 blended photos to '{target_blended_field}' and updated {STATUS_FIELD} on {record_id}")
    return blended_urls


# ==============================================================================
# PHASE 4: Local Python Pillow Story Cards Generation (Zero Fal Nano Banana API Cost)
# ==============================================================================

def generate_story_cards_for_style_this(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record_id: str,
    fields: dict[str, Any],
    blended_urls: list[str],
    *,
    dry_run: bool = False,
) -> bool:
    """Generate final 4 9:16 Story Cards via local Python Pillow: Slide 1 (How Would You) + Slides 2-4 (Double Tap)."""
    item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Modern Floor Lamp").strip()
    product_type = str(fields.get("Product Type") or "Floor Lamp").strip()
    item_label = f"{item_name} | {product_type}" if product_type and product_type.lower() not in item_name.lower() else item_name

    print(f"\n  [PHASE 4/4] Creating 4 Story Cards via Local Python Pillow (Slide 1: How Would You + Slides 2-4: Double Tap)...")

    if dry_run:
        print("  [DRY-RUN] Would generate 4 final Story Cards with local Pillow overlay.")
        return True

    if not blended_urls or len(blended_urls) == 0:
        print(f"  [ERROR] No blended image URLs found for record {record_id}.")
        return False

    # Map blended attachment URLs by filename if available, else by index
    blended_raw = fields.get(BLENDED_FIELD) or fields.get("Style This Blended Image") or []
    file_url_map: dict[str, str] = {}
    if isinstance(blended_raw, list):
        for item in blended_raw:
            if isinstance(item, dict) and item.get("url"):
                fn = str(item.get("filename") or "").strip().lower()
                file_url_map[fn] = str(item["url"]).strip()

    # 1. Download Logo if present
    logo_url = extract_attachment_url(fields.get("Logo") or fields.get("Brand Logo") or fields.get("Watermark"))
    logo_temp = None
    if logo_url:
        resp = requests.get(logo_url, stream=True)
        logo_temp = download_to_temp_file(resp, prefix="logo_story_", suffix=".png", context="Download logo for story")

    # 2. Slide 1: 'how_would_you_style_this.jpg' (from style_this01.jpg)
    b1_url = file_url_map.get("style_this01.jpg") or (blended_urls[0] if len(blended_urls) > 0 else "")
    if not b1_url:
        print(f"  [ERROR] No blended image URL found for slide 1 on record {record_id}.")
        return False

    print(f"  [INFO] Rendering Slide 1: 'how_would_you_style_this.jpg' (Logo + Centered Headline 'ft. {item_name}')...")
    resp_b1 = requests.get(b1_url, stream=True)
    temp_b1 = download_to_temp_file(resp_b1, prefix="blend_1_", suffix=".jpg", context="Download blend 1")
    
    out_dir = Path("scratch/style_this_output") / record_id
    out_dir.mkdir(parents=True, exist_ok=True)
    slide1_path = out_dir / FINAL_FILENAMES[0]

    try:
        create_style_this_slide_1(
            base_image=temp_b1.path,
            logo_path=logo_temp.path if logo_temp else None,
            item_name=item_name,
            destination=slide1_path,
        )
    finally:
        temp_b1.cleanup()

    # 3. Slides 2-4: 'double_tap_blended01.jpg', '02.jpg', '03.jpg' (from style_this02.jpg, 03.jpg, 04.jpg)
    double_tap_cards: list[tuple[Path, str]] = []
    slot_filenames = ["style_this02.jpg", "style_this03.jpg", "style_this04.jpg"]
    
    for idx in range(1, 4):
        target_src_fn = slot_filenames[idx - 1]
        b_url = file_url_map.get(target_src_fn) or (blended_urls[idx] if len(blended_urls) > idx else "")
        if not b_url:
            print(f"  [WARN] No blended image URL found for slot {idx + 1} ({target_src_fn}). Skipping slide.")
            continue

        fname = f"double_tap_blended0{idx}.jpg"
        print(f"  [INFO] Processing Slide {idx + 1}: '{fname}' from '{target_src_fn}'...")

        target_text_field = resolve_table_field(
            airtable,
            [STYLE_THIS_TEXT_FIELDS[idx - 1], f"Style This Text Generated {idx}", f"Style This Text {idx}"],
            STYLE_THIS_TEXT_FIELDS[idx - 1],
        )
        target_color_field = resolve_table_field(
            airtable,
            [STYLE_THIS_COLOR_FIELDS[idx - 1], f"Style This Auto Generated Color {idx}", f"Style This Auto Color {idx}"],
            STYLE_THIS_COLOR_FIELDS[idx - 1],
        )

        existing_vibe = str(fields.get(target_text_field) or "").strip()
        existing_color = str(fields.get(target_color_field) or "").strip()

        claude_vibe_text = "Warm Olive"
        claude_pill_color = "#adb481"

        if existing_vibe and existing_color:
            claude_vibe_text = existing_vibe
            claude_pill_color = existing_color
            print(f"    [SKIP] Found existing text '{claude_vibe_text}' in '{target_text_field}' & color '{claude_pill_color}' in '{target_color_field}'")
        else:
            # Analyze room color & dynamic pill HEX color via Claude Vision
            try:
                color_prompt = (
                    "Analyze the dominant visual color atmosphere and visible palette of this interior design photograph.\n"
                    "1. Generate a concise, natural, consumer-friendly 1 to 3 word color or style vibe description (e.g. 'Warm Olive', 'Terracotta Amber', 'Sage Minimalist', 'Muted Brass', 'Charcoal Slate').\n"
                    "2. Select a rich, harmonious HEX color code from that specific photograph to use as the background badge/pill behind white text.\n"
                    "RULES: Return ONLY a valid JSON object with no preamble, no markdown, and no quotes around the JSON, in this exact format:\n"
                    "{\"vibe_name\": \"Warm Olive\", \"hex_color\": \"#adb481\"}"
                )
                raw_resp = fal.generate_vision_prompt(
                    image_urls=[b_url],
                    prompt=color_prompt,
                    model=CLAUDE_VISION_MODEL,
                ).strip()

                cleaned_json = raw_resp
                if "{" in cleaned_json and "}" in cleaned_json:
                    cleaned_json = cleaned_json[cleaned_json.find("{"):cleaned_json.rfind("}") + 1]

                data = json.loads(cleaned_json)
                vibe = str(data.get("vibe_name") or "").strip().strip("[]\"'")
                hex_code = str(data.get("hex_color") or "").strip().strip("[]\"'")

                if vibe and len(vibe) <= 40:
                    claude_vibe_text = vibe
                if hex_code.startswith("#") and (len(hex_code) == 7 or len(hex_code) == 4):
                    claude_pill_color = hex_code
                elif len(hex_code) == 6:
                    claude_pill_color = f"#{hex_code}"

                print(f"    [OK] Claude Vision detected vibe: '{claude_vibe_text}' | Pill HEX: '{claude_pill_color}'")

                # Save generated text and color to Airtable before rendering
                if not dry_run:
                    airtable.update_records([(record_id, {
                        target_text_field: claude_vibe_text,
                        target_color_field: claude_pill_color,
                    })])
                    print(f"    [OK] Saved to Airtable: '{target_text_field}'='{claude_vibe_text}', '{target_color_field}'='{claude_pill_color}'")
            except Exception as err:
                if 'raw_resp' in locals() and raw_resp and not raw_resp.startswith("{") and len(raw_resp) <= 40:
                    claude_vibe_text = raw_resp.strip().strip('"').strip("'").strip("[]")
                print(f"    [WARN] Claude vision color analysis using '{claude_vibe_text}' | HEX: '{claude_pill_color}': {err}")

        resp_dt = requests.get(b_url, stream=True)
        temp_dt = download_to_temp_file(resp_dt, prefix=f"blend_{idx+1}_", suffix=".jpg", context=f"Download blend {idx+1}")
        dt_path = out_dir / fname

        try:
            create_style_this_double_tap_slide(
                base_image=temp_dt.path,
                logo_path=logo_temp.path if logo_temp else None,
                heart_asset_path=None,  # auto-resolves assets/Heaart Emoji.jpg
                claude_text=claude_vibe_text,
                destination=dt_path,
                pill_color_hex=claude_pill_color,
            )
            double_tap_cards.append((dt_path, fname))
        finally:
            temp_dt.cleanup()

    if logo_temp:
        logo_temp.cleanup()

    # 4. Upload Double Tap Converted (3 cards)
    target_dt_converted_field = resolve_table_field(airtable, [DOUBLE_TAP_CONVERTED_FIELD, "Double Tap Converted"], DOUBLE_TAP_CONVERTED_FIELD)
    for dt_path, fname in double_tap_cards:
        airtable.upload_attachment(record_id, target_dt_converted_field, dt_path, fname)

    # 5. Upload all 4 final Story Cards to 'STORY - Style This? (4)'
    target_story_field = resolve_table_field(airtable, STORY_FINAL_CANDIDATES, STORY_FINAL_CANDIDATES[0])
    all_final_cards = [(slide1_path, FINAL_FILENAMES[0])] + double_tap_cards
    for card_path, fname in all_final_cards:
        airtable.upload_attachment(record_id, target_story_field, card_path, fname)

    target_status = resolve_status_choice(airtable, [STATUS_COMPLETE, "Complete"])
    airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
    print(f"  [OK] Successfully uploaded 4 final Story Cards to '{target_story_field}' and set Status='{target_status}' on {record_id}!")
    return True


# ==============================================================================
# End-to-End Single Row Processor
# ==============================================================================

def process_single_style_this_row(
    krea: KreaClient,
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record: dict[str, Any],
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_INTERIOR_PROMPT,
    dry_run: bool = False,
) -> bool:
    """Run all phases sequentially on a single Style This Story record."""
    record_id = record["id"]
    fields = record.get("fields", {})
    item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
    status = fields.get(STATUS_FIELD, STATUS_STANDBY)

    print("\n" + "=" * 64)
    print(f" [STYLE THIS ROW START] Processing Record: {record_id}")
    print(f" Item: {item_label}")
    print(f" Status: {status}")
    print("=" * 64)

    start_time = time.time()
    try:
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))
        if not furniture_url:
            print(f"[SKIP] Record {record_id} has no '{FIELD_NAME}' image attachment.")
            return False

        # Phase 1: Krea AI Interior Generation
        interior_urls = generate_krea_interiors_for_style_this(
            krea,
            airtable,
            record_id,
            fields,
            moodboard_id=moodboard_id,
            prompt=prompt,
            dry_run=dry_run,
        )

        # Refresh fields after Phase 1
        if not dry_run:
            fields = airtable.get_record(record_id).get("fields", {})

        # Phase 2: Claude Sonnet 5 Vision Blending Prompts
        prompts = generate_blending_prompts_for_style_this(
            fal,
            airtable,
            record_id,
            fields,
            interior_urls,
            furniture_url,
            dry_run=dry_run,
        )

        # Refresh fields after Phase 2
        if not dry_run:
            fields = airtable.get_record(record_id).get("fields", {})

        # Phase 3: Fal AI Nano Banana Pro Image Blends
        blended_urls = generate_blends_for_style_this(
            fal,
            airtable,
            record_id,
            fields,
            interior_urls,
            furniture_url,
            prompts,
            dry_run=dry_run,
        )

        # Refresh fields after Phase 3
        if not dry_run:
            fields = airtable.get_record(record_id).get("fields", {})

        # Phase 4: Story Cards Conversion ('How Would You' + 'Double Tap')
        generate_story_cards_for_style_this(
            fal,
            airtable,
            record_id,
            fields,
            blended_urls,
            dry_run=dry_run,
        )

        elapsed = time.time() - start_time
        print(f"\n[STYLE THIS ROW COMPLETE] Record {record_id} finished in {elapsed:.1f}s")
        return True
    except Exception as err:
        print(f"\n[ERROR] Failed processing record {record_id}: {err}")
        return False


# ==============================================================================
# CLI Argument Parser & Main Entry Point
# ==============================================================================

def run_style_this_conversion_pipeline(
    airtable: ScrapeAirtableClient,
    fal: FalClient,
    records: list[dict[str, Any]],
    *,
    max_items: int = 1,
    dry_run: bool = False,
) -> int:
    """Run local Pillow layout conversion on records with 'Style This Blended' images."""
    print(f"\n[INFO] Running Style This Story Layout Conversion (Mode: {'DRY RUN' if dry_run else 'LIVE'})...")
    succeeded = 0
    failed = 0

    to_process = records[:max_items]
    for idx, record in enumerate(to_process, start=1):
        rec_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or rec_id
        blended_urls = extract_attachment_urls(fields.get(BLENDED_FIELD))

        print(f"\n>>> [CONVERSION ROW {idx}/{len(to_process)}] Record: {rec_id} ({item_label}) <<<")
        if not blended_urls:
            print(f"  [SKIP] Record {rec_id} has no '{BLENDED_FIELD}' images.")
            continue

        print(f"  [INFO] Found {len(blended_urls)} blended images in '{BLENDED_FIELD}'.")
        ok = generate_story_cards_for_style_this(
            fal,
            airtable,
            rec_id,
            fields,
            blended_urls,
            dry_run=dry_run,
        )
        if ok:
            succeeded += 1
        else:
            failed += 1

    print("\n" + "=" * 64)
    print(f" Style This Conversion Finished: {succeeded} Succeeded, {failed} Failed.")
    print("=" * 64)
    return 0 if failed == 0 else 1


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Style This Story AI Pipeline (Krea AI -> Claude Sonnet 5 -> Nano Banana Pro -> Story Cards)"
    )
    parser.add_argument(
        "--mode",
        choices=["all", "conversion", "menu"],
        default="all",
        help="Run mode: 'all' (process rows end-to-end), 'conversion' (stamp local Pillow layouts on blended rows), or 'menu' (interactive menu)",
    )
    parser.add_argument(
        "--limit",
        "--batch-size",
        "-n",
        dest="max_items",
        type=int,
        default=1,
        help="Number of rows to process sequentially (default: 1)",
    )
    parser.add_argument(
        "--record-id",
        "-r",
        action="append",
        default=[],
        help="Specific Airtable Record ID to process",
    )
    parser.add_argument(
        "--category",
        choices=["floor_lamps", "wall_lights", "pendant_lights", "chandeliers", "chandelier"],
        default=None,
        help="Style This Category (auto-selects matching Table ID: floor_lamps, wall_lights, pendant_lights, chandeliers)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help=f"Airtable Table ID (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--moodboard-id",
        default=DEFAULT_MOODBOARD_ID,
        help=f"Krea Moodboard ID (default: {DEFAULT_MOODBOARD_ID})",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_INTERIOR_PROMPT,
        help=f"Krea Interior Prompt (default: '{DEFAULT_INTERIOR_PROMPT}')",
    )
    parser.add_argument(
        "--style",
        default=DEFAULT_STYLE,
        help=f"Akeneo Style2 code (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without calling paid APIs or mutating Airtable",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip Akeneo auto-scraping",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape products from Akeneo into Airtable without running generation",
    )
    return parser.parse_args(argv)


def run_pipeline(
    *,
    mode: str = "all",
    table_id: str = DEFAULT_TABLE_ID,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_INTERIOR_PROMPT,
    style: str = DEFAULT_STYLE,
    max_items: int = 1,
    record_ids: list[str] | None = None,
    dry_run: bool = False,
    no_scrape: bool = False,
    scrape_only: bool = False,
) -> int:
    """Execute the complete Style This Story pipeline."""
    settings = load_settings()
    if not dry_run:
        if mode == "conversion":
            settings.require({"airtable", "fal"})
        else:
            settings.require({"airtable", "krea", "fal"})

    scrape_settings = load_scrape_settings(
        category_code=DEFAULT_CATEGORY,
        style_code=style,
        table_id_override=table_id,
        settings=settings,
    )

    airtable = ScrapeAirtableClient(
        scrape_settings.airtable_token,
        scrape_settings.airtable_base_id,
        table_id,
    )
    krea = KreaClient(settings.krea_token, settings.krea_base_url)
    fal = FalClient(settings.fal_key)

    cat_cfg = TABLE_ID_TO_CATEGORY_CONFIG.get(table_id, STYLE_THIS_CATEGORIES["floor_lamps"])
    cat_label = cat_cfg["name"]
    target_category_code = cat_cfg["category_code"]

    if moodboard_id == DEFAULT_MOODBOARD_ID and cat_cfg.get("moodboard_id"):
        moodboard_id = cat_cfg["moodboard_id"]
    if prompt == DEFAULT_INTERIOR_PROMPT and cat_cfg.get("prompt"):
        prompt = cat_cfg["prompt"]

    print("\n" + "=" * 64)
    print(" HomeCartel - Style This Story AI Pipeline (9:16 Ratio)")
    print(f" Category: {cat_label} | Target Table: {table_id}")
    print(f" Moodboard ID: {moodboard_id}")
    print(f" Interior Prompt: \"{prompt}\"")
    print(f" Mode: {mode.upper()} ({'DRY RUN' if dry_run else 'LIVE RUN'})")
    print(f" Batch Size: {max_items} row(s)")
    print("=" * 64)

    # If conversion mode requested:
    if mode == "conversion":
        records = airtable.list_records()
        if record_ids:
            target_records = [rec for rec in records if rec["id"] in record_ids]
        else:
            target_records = [
                rec for rec in records
                if rec.get("fields", {}).get(BLENDED_FIELD)
            ]
        if not target_records:
            print("\n[OK] No records with 'Style This Blended' found for conversion!")
            return 0
        return run_style_this_conversion_pipeline(
            airtable,
            fal,
            target_records,
            max_items=max_items,
            dry_run=dry_run,
        )

    # 1. Check existing pending rows in Airtable
    records = airtable.list_records()
    pending_records = [
        rec for rec in records
        if str(rec.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold() != STATUS_COMPLETE.casefold()
        and rec.get("fields", {}).get(FIELD_NAME)
    ]

    # 2. Auto-Scrape if no pending rows and scraping allowed
    if not pending_records and not no_scrape and not record_ids:
        print(f"\n[INFO] No pending rows found in Airtable table '{table_id}'. Scraping {max_items} new {cat_label} from Akeneo...")
        akeneo = AkeneoClient(
            settings.akeneo_host,
            settings.akeneo_client_id,
            settings.akeneo_secret,
            settings.akeneo_username,
            settings.akeneo_password,
            channel_name=scrape_settings.channel_name,
        )
        runner = FurnitureItemScrapeRunner(
            akeneo,
            airtable,
            category_code=target_category_code,
            style_code=style,
            field_name=FIELD_NAME,
            item_name_field=ITEM_NAME_FIELD,
            sku_field=SKU_FIELD,
            status_field=STATUS_FIELD,
            default_status=STATUS_STANDBY,
            include_product_type_in_name=True,
            max_items=max_items,
            cross_table_dedup=True,
        )
        scrape_ok = runner.run(execute=not dry_run)
        if scrape_only:
            print(f"[OK] Scrape-only finished: {'Success' if scrape_ok else 'No new items'}.")
            return 0 if scrape_ok else 1

        records = airtable.list_records()
        pending_records = [
            rec for rec in records
            if str(rec.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold() != STATUS_COMPLETE.casefold()
            and rec.get("fields", {}).get(FIELD_NAME)
        ]

    if scrape_only:
        print("[INFO] Scrape-only flag set. Skipping generation.")
        return 0

    # 3. Filter records to process
    if record_ids:
        to_process = [rec for rec in records if rec["id"] in record_ids]
    else:
        to_process = pending_records[:max_items]

    if not to_process:
        print("\n[OK] No pending rows to process in Airtable!")
        return 0

    print(f"\n[INFO] Starting sequential row-by-row generation for {len(to_process)} Style This row(s)...")

    succeeded = 0
    failed = 0
    for idx, record in enumerate(to_process, start=1):
        print(f"\n>>> [STYLE THIS ROW {idx}/{len(to_process)}] <<<")
        success = process_single_style_this_row(
            krea,
            fal,
            airtable,
            record,
            moodboard_id=moodboard_id,
            prompt=prompt,
            dry_run=dry_run,
        )
        if success:
            succeeded += 1
        else:
            failed += 1

    print("\n" + "=" * 64)
    print(f" Style This Story Pipeline Finished: {succeeded} Succeeded, {failed} Failed.")
    print("=" * 64)
    return 0 if failed == 0 else 1


def run_interactive_menu():
    """Interactive CLI menu for Style This Story."""
    while True:
        print("\n" + "=" * 64)
        print(" Style This Story Automation - Select Category / Table")
        print("=" * 64)
        print("  [1] 🛋️ Floor Lamps     (Table: tblvSAzXasTVI85r9 | Moodboard: b1641228...)")
        print("  [2] 💡 Pendant Lights   (Table: tblWdz71nULR0TZx7 | Moodboard: 0844ad92...)")
        print("  [3] 🏮 Chandeliers      (Table: tblp6AMYb13NPqkuT | Moodboard: fda7090c...)")
        print("  [4] 🕯️ Wall Lights      (Table: tblXJrvSBkJNhRHLa | Moodboard: Default)")
        print("  [0] Exit")
        print("=" * 64)
        try:
            cat_choice = input("Select Category [1-4, 0]: ").strip()
            if cat_choice == "0":
                break
            
            cat_keys = ["floor_lamps", "pendant_lights", "chandeliers", "wall_lights"]
            if not cat_choice.isdigit() or int(cat_choice) not in range(1, 5):
                print("[WARN] Invalid selection. Please enter a number between 1 and 4.")
                continue

            selected_key = cat_keys[int(cat_choice) - 1]
            cfg = STYLE_THIS_CATEGORIES[selected_key]

            while True:
                print("\n" + "-" * 64)
                print(f" Style This Story: {cfg['name']} ({cfg['table_id']})")
                print(f" Moodboard ID: {cfg['moodboard_id']}")
                print(f" Krea Prompt: \"{cfg['prompt']}\"")
                print("-" * 64)
                print("  [1] Run Next Pending Row (End-to-End: Scrape -> Krea -> Fal -> Cards)")
                print("  [2] Convert Existing Blended Rows into Story Cards (Free Layout)")
                print("  [3] Run Batch of Pending Rows (Enter quantity)")
                print(f"  [4] Scrape New {cfg['name']} from Akeneo Only")
                print("  [5] Process Specific Airtable Record ID")
                print("  [6] Dry Run Simulation (Read-only check)")
                print("  [0] Back to Category Selection")
                print("-" * 64)
                action_choice = input("Enter action [0-6]: ").strip()
                if action_choice == "0":
                    break
                elif action_choice == "1":
                    run_pipeline(mode="all", table_id=cfg["table_id"], moodboard_id=cfg["moodboard_id"], prompt=cfg["prompt"], max_items=1)
                elif action_choice == "2":
                    run_pipeline(mode="conversion", table_id=cfg["table_id"], moodboard_id=cfg["moodboard_id"], prompt=cfg["prompt"], max_items=1)
                elif action_choice == "3":
                    num_str = input("How many rows to process? [default: 3]: ").strip()
                    limit = int(num_str) if num_str.isdigit() else 3
                    run_pipeline(mode="all", table_id=cfg["table_id"], moodboard_id=cfg["moodboard_id"], prompt=cfg["prompt"], max_items=limit)
                elif action_choice == "4":
                    run_pipeline(mode="all", table_id=cfg["table_id"], moodboard_id=cfg["moodboard_id"], prompt=cfg["prompt"], max_items=1, scrape_only=True)
                elif action_choice == "5":
                    rec_id = input("Enter Airtable Record ID (e.g. recXXXXXXXX): ").strip()
                    if rec_id:
                        conv_choice = input("Run conversion only? (y/N): ").strip().lower()
                        m = "conversion" if conv_choice == "y" else "all"
                        run_pipeline(mode=m, table_id=cfg["table_id"], moodboard_id=cfg["moodboard_id"], prompt=cfg["prompt"], record_ids=[rec_id])
                elif action_choice == "6":
                    run_pipeline(mode="all", table_id=cfg["table_id"], moodboard_id=cfg["moodboard_id"], prompt=cfg["prompt"], max_items=1, dry_run=True)
        except (KeyboardInterrupt, EOFError):
            break


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.mode == "menu":
        run_interactive_menu()
        return 0

    target_table_id = args.table_id
    if not target_table_id:
        if args.category:
            target_table_id = STYLE_THIS_TABLE_MAP.get(args.category, DEFAULT_TABLE_ID)
        else:
            target_table_id = DEFAULT_TABLE_ID

    cat_cfg = TABLE_ID_TO_CATEGORY_CONFIG.get(target_table_id, STYLE_THIS_CATEGORIES["floor_lamps"])

    target_moodboard_id = args.moodboard_id
    if target_moodboard_id == DEFAULT_MOODBOARD_ID:
        if args.category and args.category in STYLE_THIS_MOODBOARD_MAP:
            target_moodboard_id = STYLE_THIS_MOODBOARD_MAP[args.category]
        elif target_table_id in TABLE_ID_TO_MOODBOARD_MAP:
            target_moodboard_id = TABLE_ID_TO_MOODBOARD_MAP[target_table_id]
        elif cat_cfg.get("moodboard_id"):
            target_moodboard_id = cat_cfg["moodboard_id"]

    target_prompt = args.prompt
    if target_prompt == DEFAULT_INTERIOR_PROMPT:
        if args.category and args.category in STYLE_THIS_PROMPT_MAP:
            target_prompt = STYLE_THIS_PROMPT_MAP[args.category]
        elif cat_cfg.get("prompt"):
            target_prompt = cat_cfg["prompt"]

    return run_pipeline(
        mode=args.mode,
        table_id=target_table_id,
        moodboard_id=target_moodboard_id,
        prompt=target_prompt,
        style=args.style,
        max_items=args.max_items,
        record_ids=args.record_id,
        dry_run=args.dry_run,
        no_scrape=args.no_scrape,
        scrape_only=args.scrape_only,
    )


if __name__ == "__main__":
    sys.exit(main())
