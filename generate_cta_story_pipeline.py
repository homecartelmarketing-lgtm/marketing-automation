"""CTA Story AI Generation & Blending Pipeline.

Runs the complete 6-phase AI pipeline for CTA Story on Airtable:
1. Akeneo Product Scraping -> 'Furniture Item' + 'CTA Blended Image Watermark Layout' + 'Logo', Status -> 'Standby'
2. Krea AI Interior Photo Generation (9:16) -> 'CTA Interior', Status -> 'CTA Interior Generated'
3. Claude Sonnet 5 Prompt Analysis (via Fal AI) -> 'Blending Prompt', Status -> 'Blending Prompt Generated'
4. Fal AI Nano Banana Pro Blending (9:16) -> 'CTA Blended Image', Status -> 'CTA Blended Image Generated'
5. Claude Sonnet 5 Headline Analysis (via Fal AI) -> 'Word Generated'
6. Python Local CTA Layout & Logo Stamping (9:16) -> 'CTA Converted Image' / 'Watermark Added', Status -> 'Complete'

Usage::

    python generate_cta_story_pipeline.py
    python generate_cta_story_pipeline.py --max-items 5
    python generate_cta_story_pipeline.py --category chandelier_cta_story
    python generate_cta_story_pipeline.py --mode conversion --table-id tblYHdVq14FjMWg5o
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from content_automation.config import TABLES, load_settings
from content_automation.cta_conversion import run_cta_conversion
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.kie_client import KieClient
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.overlay import (
    CTA_STORY_TEXT_BOX,
    HOMECARTEL_STORY_LOGO_BOX,
    overlay_cta_story_layout,
    stamp_cta_story_watermark_and_logo,
)
from content_automation.qwen_client import QwenClient
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    moodboard_id_for_category,
)
from standalone_scrape_akeneo import run_category_scrape

DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_CTA", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_CTA_STORY", "").strip()
    or "tblYHdVq14FjMWg5o"
)
DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_CHANDELIER_CTA", "").strip()
    or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
    or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
    or "fda7090c-787b-4116-94cd-3feef613eaaa"
)
DEFAULT_PROMPT = "Generate me a modern living room"

CTA_INTERIOR_PROMPTS: dict[str, str] = {
    "table_lamps_cta_story": "Generate me a modern bedroom with a table lamp side by side",
    "chandelier_cta_story": "Generate me a modern living room",
    "cta_story": "Generate me a modern living room",
    "cluster_chandelier_cta_story": (
        "Modern high-ceiling room interior, luxury contemporary architecture, warm neutral tones, "
        "clean open ceiling space ready for cluster chandelier integration, photorealistic 8k vertical portrait"
    ),
    "pendant_lights_cta_story": (
        "Modern dining room or kitchen interior, warm minimalist design, soft ambient daylight, "
        "clean ceiling focal point ready for pendant light integration, photorealistic 8k vertical portrait"
    ),
    "floor_lamp_cta_story": (
        "Modern living room interior, stylish lounge chair, warm ambient lighting, "
        "spacious floor corner ready for floor lamp integration, photorealistic 8k vertical portrait"
    ),
    "wall_lights_cta_story": (
        "Modern living room or bedroom hallway, clean textured accent wall, soft ambient daylight, "
        "empty wall space ready for wall sconce lighting fixture, photorealistic 8k vertical portrait"
    ),
}


def prompt_for_category(category_code: str, custom_prompt: str | None = None) -> str:
    """Return the designated interior prompt for a category or custom override."""
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()
    return CTA_INTERIOR_PROMPTS.get(category_code, DEFAULT_PROMPT)


DEFAULT_CATEGORY = "chandelier_cta_story"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "CTA Interior Generated"
STATUS_GENERATING_PROMPT = "Blending Prompt Generated"
STATUS_BLENDED_IMAGE = "CTA Blended Image Generated"
STATUS_ADDED_WATERMARK = "Watermark Added Layout"
STATUS_COMPLETE = "Complete"

INTERIOR_FIELD = "CTA Interior"
INTERIOR_FIELD_FALLBACKS = ["CTA Interior", "CTA Interior Image", "Interior", "Interior Image"]
INTERIOR_ASPECT_RATIO = "9:16"

PROMPT_FIELD = "Blending Prompt"
PROMPT_FIELD_FALLBACKS = [
    "Blending Prompt",
    "CTA Prompt Blending",
    "Prompt",
    "Blend Prompt",
    "Blending Prompt Generated",
]

BLENDED_FIELD = "CTA Blended Image"
BLENDED_FIELD_FALLBACKS = [
    "CTA Blended Image",
    "CTA Blended",
    "Blended Image",
    "Blended Photo",
]
BLENDED_ASPECT_RATIO = "9:16"

LAYOUT_FIELD = "CTA Blended Image Watermark Layout"
LAYOUT_FIELD_FALLBACKS = [
    "CTA Blended Image Watermark Layout",
    "CTA Layout",
    "Watermark Layout",
    "Layout",
    "CTA Overlay Layout",
]

LOGO_FIELD = "Logo"
LOGO_FIELD_FALLBACKS = [
    "Logo",
    "HomeCartel Logo",
    "Brand Logo",
    "Watermark Logo",
]

WATERMARK_FIELD = "Watermark Added"
WATERMARK_FIELD_FALLBACKS = [
    "Watermark Added",
    "Watermark Added Layout",
    "Watermarked Image",
    "Watermark Added Image",
    "CTA Converted Image",
    "CTA Converted Blended",
]

CONVERTED_FIELD_FALLBACKS = [
    "CTA Converted Image",
    "CTA Converted Blended",
    "Watermark Added",
    "Watermark Added Layout",
    "Watermarked Image",
]

WORD_GENERATED_FIELD = "Word Generated"
WORD_GENERATED_FALLBACKS = [
    "Word Generated",
    "Word Generate",
    "Generated Words",
    "Words Generated",
    "CTA Headline",
    "Headline",
]

FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_BLENDING_MODEL = os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
QWEN_PROMPT_MODEL = "qwen3.7-flash"
QWEN_BLEND_MODEL = "qwen-image-3.0-pro"


def base_has_key(client: Any) -> bool:
    return bool(getattr(client, "api_key", None))


def get_first_field_value(fields: dict[str, Any], field_names: list[str]) -> Any:
    """Return the first populated value among candidate field names."""
    for name in field_names:
        if name in fields and fields[name]:
            return fields[name]
    return None


def get_first_field_name(fields: dict[str, Any], field_names: list[str]) -> str:
    """Return the first matching field name that exists in fields dictionary."""
    for name in field_names:
        if name in fields:
            return name
    return field_names[0]


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


def make_layout_transparent(img: Image.Image, threshold: int = 35) -> Image.Image:
    """Convert layout overlay image to RGBA and turn solid background transparent."""
    img = img.convert("RGBA")
    extrema = img.getextrema()
    if extrema[3][0] < 255:
        return img

    w, h = img.size
    corners = [
        img.getpixel((0, 0)),
        img.getpixel((w - 1, 0)),
        img.getpixel((0, h - 1)),
        img.getpixel((w - 1, h - 1)),
    ]
    avg_brightness = sum((c[0] + c[1] + c[2]) / 3.0 for c in corners) / 4.0
    is_dark_bg = avg_brightness < 128

    rgb_data = img.convert("RGB").tobytes()
    alpha_data = bytearray(w * h)

    for i in range(w * h):
        r_val = rgb_data[i * 3]
        g_val = rgb_data[i * 3 + 1]
        b_val = rgb_data[i * 3 + 2]
        if is_dark_bg:
            if not (r_val <= threshold and g_val <= threshold and b_val <= threshold):
                alpha_data[i] = 255
        else:
            if not (r_val >= (255 - threshold) and g_val >= (255 - threshold) and b_val >= (255 - threshold)):
                alpha_data[i] = 255

    new_alpha = Image.frombytes("L", (w, h), bytes(alpha_data))
    img.putalpha(new_alpha)
    return img


def overlay_watermark_layout(
    blended_path: str | Path,
    layout_path: str | Path,
    output_path: str | Path,
    threshold: int = 35,
) -> Path:
    """Overlay transparent layout photo on top of blended base photo, saving result."""
    base_img = Image.open(blended_path).convert("RGBA")
    layout_img = Image.open(layout_path)

    transparent_layout = make_layout_transparent(layout_img, threshold=threshold)
    if transparent_layout.size != base_img.size:
        transparent_layout = transparent_layout.resize(base_img.size, Image.Resampling.LANCZOS)

    composited = Image.alpha_composite(base_img, transparent_layout).convert("RGB")
    composited.save(output_path, "JPEG", quality=95)
    return Path(output_path)


def find_cta_layout_path() -> Path | None:
    """Locate local cta_layout.jpg file from project tree."""
    candidates = [
        Path(__file__).parent / "JSON Prompts" / "CTA" / "cta_layout.jpg",
        Path(__file__).parent / "JSON Prompts" / "cta_layout.jpg",
        Path(__file__).parent / "cta_layout.jpg",
        Path(__file__).parent / "assets" / "cta_layout.jpg",
        Path(__file__).parent / "assets" / "CTA" / "cta_layout.jpg",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def find_homecartel_logo_path() -> Path | None:
    """Locate local HomeCartel logo asset from project tree."""
    candidates = [
        Path(__file__).parent / "assets" / "homecartel_logo.png",
        Path(__file__).parent / "assets" / "logo.png",
        Path(__file__).parent / "logo.png",
        Path(__file__).parent / "homecartel_logo.png",
        Path(__file__).parent / "JSON Prompts" / "CTA" / "homecartel_logo.png",
        Path(__file__).parent / "JSON Prompts" / "homecartel_logo.png",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def get_existing_logo_attachment_from_table(airtable: ScrapeAirtableClient) -> dict[str, Any] | None:
    """Find an existing populated Logo attachment from any record in the table."""
    try:
        records = airtable.list_records(LOGO_FIELD_FALLBACKS)
        for record in records:
            logo_val = get_first_field_value(record.get("fields", {}), LOGO_FIELD_FALLBACKS)
            if logo_val:
                if isinstance(logo_val, list) and len(logo_val) > 0 and isinstance(logo_val[0], dict):
                    return logo_val[0]
                elif isinstance(logo_val, dict):
                    return logo_val
    except Exception as e:
        print(f"[DEBUG] Table logo scan skipped: {e}")
    return None


def ensure_cta_layout_uploaded(airtable: ScrapeAirtableClient, record_id: str, fields: dict[str, Any]) -> bool:
    """Ensure CTA layout asset is populated on the record."""
    target_field = get_first_field_name(fields, LAYOUT_FIELD_FALLBACKS)
    if get_first_field_value(fields, LAYOUT_FIELD_FALLBACKS):
        return True

    layout_path = find_cta_layout_path()
    if not layout_path:
        print("[WARN] Local 'cta_layout.jpg' not found in project tree; skipping layout attachment upload.")
        return False

    try:
        airtable.upload_attachment(record_id, target_field, layout_path, "cta_layout.jpg")
        print(f"[OK] Uploaded layout 'cta_layout.jpg' to '{target_field}' on record {record_id}")
        return True
    except Exception as error:
        print(f"[ERROR] Failed uploading layout to record {record_id}: {error}")
        return False


def ensure_cta_logo_uploaded(airtable: ScrapeAirtableClient, record_id: str, fields: dict[str, Any]) -> bool:
    """Ensure HomeCartel brand logo asset is populated on the record."""
    target_field = get_first_field_name(fields, LOGO_FIELD_FALLBACKS)
    if get_first_field_value(fields, LOGO_FIELD_FALLBACKS):
        return True

    logo_path = find_homecartel_logo_path()
    if logo_path and logo_path.exists():
        try:
            airtable.upload_attachment(record_id, target_field, logo_path, logo_path.name)
            print(f"[OK] Uploaded logo '{logo_path.name}' to '{target_field}' on record {record_id}")
            return True
        except Exception as error:
            print(f"[WARN] Local logo upload failed for record {record_id}: {error}")

    table_logo = get_existing_logo_attachment_from_table(airtable)
    if table_logo and table_logo.get("url"):
        import requests
        try:
            resp = requests.get(table_logo["url"], stream=True, timeout=30)
            if resp.status_code == 200:
                dl = download_to_temp_file(resp, prefix="logo_copy_", suffix=".png", context="Table logo copy")
                try:
                    airtable.upload_attachment(record_id, target_field, dl.path, "homecartel_logo.png")
                    print(f"[OK] Copied existing logo from Airtable to '{target_field}' on record {record_id}")
                    return True
                finally:
                    dl.cleanup()
        except Exception as error:
            print(f"[WARN] Failed copying logo from other Airtable records: {error}")

    return False


def safe_update_status(airtable: ScrapeAirtableClient, record_id: str, status_value: str) -> None:
    try:
        airtable.update_records([(record_id, {STATUS_FIELD: status_value})])
    except Exception:
        pass


def backfill_missing_cta_assets(airtable: ScrapeAirtableClient) -> None:
    records = airtable.list_records(LAYOUT_FIELD_FALLBACKS + LOGO_FIELD_FALLBACKS + [FIELD_NAME, STATUS_FIELD])
    for rec in records:
        f = rec.get("fields", {})
        ensure_cta_layout_uploaded(airtable, rec["id"], f)
        ensure_cta_logo_uploaded(airtable, rec["id"], f)


def sort_records_by_id(records: list[dict]) -> list[dict]:
    def sort_key(record: dict):
        fields = record.get("fields", {})
        for key in ("ID", "Auto Number", "No", "Number", "Id", "id", "Row"):
            val = fields.get(key)
            if val is not None:
                try:
                    return (0, int(val))
                except (ValueError, TypeError):
                    return (0, str(val))
        return (1, record.get("createdTime", ""))

    return sorted(records, key=sort_key)


def generate_krea_interiors(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_PROMPT,
    aspect_ratio: str = INTERIOR_ASPECT_RATIO,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate Krea AI room interior photo into 'CTA Interior'."""
    airtable.ensure_fields({INTERIOR_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(INTERIOR_FIELD_FALLBACKS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"])
    if not records:
        print("[OK] No records found in Airtable to populate interior photos.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    unpopulated = [
        record
        for record in records
        if not get_first_field_value(record.get("fields", {}), INTERIOR_FIELD_FALLBACKS)
    ]
    if not unpopulated:
        print(f"[OK] No records found missing interior photo field ('{INTERIOR_FIELD}').")
        return True

    if limit_records is not None:
        unpopulated = unpopulated[:limit_records]

    print(
        f"[INFO] Generating '{INTERIOR_FIELD}' for {len(unpopulated)} record(s) "
        f"using Krea AI (Moodboard ID: {moodboard_id}, Aspect Ratio: {aspect_ratio})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(unpopulated, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
        print(
            f"[INFO] [{position}/{len(unpopulated)}] Generating photo for "
            f"record {record_id} ({item_label})..."
        )

        downloaded = None
        try:
            image_url = krea.generate(
                prompt,
                aspect_ratio=aspect_ratio,
                moodboard_id=moodboard_id,
            )
            downloaded = krea.download_image(image_url)
            filename = f"cta_interior_{record_id}.jpg"
            target_field = get_first_field_name(fields, INTERIOR_FIELD_FALLBACKS)
            airtable.upload_attachment(record_id, target_field, downloaded, filename)
            safe_update_status(airtable, record_id, STATUS_INTERIOR_GENERATED)
            print(
                f"[OK] Attached Krea image to '{target_field}' and updated "
                f"{STATUS_FIELD} on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(
                f"[ERROR] Failed generating interior photo for record {record_id}: {error}"
            )
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(f"[INFO] Krea CTA interior generation complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def generate_claude_blending_prompts(
    fal_or_qwen: Any,
    airtable: ScrapeAirtableClient,
    *,
    vision_model: str = FAL_VISION_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate detailed blending prompt using Claude Sonnet 5 via Fal AI into 'Blending Prompt'."""
    airtable.ensure_fields({PROMPT_FIELD: "multilineText"})
    records = airtable.list_records(
        INTERIOR_FIELD_FALLBACKS + PROMPT_FIELD_FALLBACKS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to generate prompts.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        interior_attachments = get_first_field_value(fields, INTERIOR_FIELD_FALLBACKS)
        prompt_val = get_first_field_value(fields, PROMPT_FIELD_FALLBACKS)
        if not interior_attachments:
            continue
        if prompt_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Claude Sonnet 5 prompt generation (CTA interior missing or blending prompt already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{PROMPT_FIELD}' for {len(eligible)} record(s) "
        f"using Claude Sonnet 5 via Fal AI ({vision_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Lighting Fixture").strip()
        item_label = f"{record_id} ({item_name})"

        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELD_FALLBACKS))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))

        if not interior_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible CTA Interior attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing photos & generating CTA blending prompt for "
            f"record {record_id} ({item_label}) with Claude Sonnet 5..."
        )

        image_urls = [url for url in [interior_url, furniture_url] if url]
        instruction = (
            f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo ('CTA Interior') "
            f"and Image 2 as the product photo for '{item_name}' ('Furniture Item').\n"
            f"Write a precise, photorealistic image-to-image blending prompt to seamlessly integrate and install "
            f"the lighting fixture/furniture item '{item_name}' into the interior room in Image 1. "
            f"Describe exact realistic placement (e.g. hung gracefully from ceiling center above living area, standing on floor, or mounted on wall), "
            f"natural warm illumination casting soft light and subtle ambient shadows onto surrounding furniture and architecture, "
            f"matching perspective, exact textures, luxury modern aesthetic, 8k vertical portrait resolution, hyperrealistic. "
            f"Output ONLY the prompt text without commentary or preamble."
        )

        try:
            if hasattr(fal_or_qwen, "analyze_image"):
                generated_prompt = fal_or_qwen.analyze_image(
                    prompt=instruction,
                    image_urls=image_urls,
                    model=vision_model,
                )
            elif hasattr(fal_or_qwen, "describe_image"):
                generated_prompt = fal_or_qwen.describe_image(interior_url, prompt=instruction)
            else:
                generated_prompt = (
                    f"Seamlessly install the luxury {item_name} fixture into the modern room interior, "
                    f"hanging from ceiling with soft warm glow casting realistic ambient light and subtle drop shadows, "
                    f"photorealistic 8k vertical architectural composition"
                )

            target_field = get_first_field_name(fields, PROMPT_FIELD_FALLBACKS)
            airtable.update_records([(record_id, {target_field: generated_prompt.strip()})])
            safe_update_status(airtable, record_id, STATUS_GENERATING_PROMPT)
            print(
                f"[OK] Generated prompt ({len(generated_prompt.strip())} chars) for "
                f"record {record_id} and updated '{target_field}'"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating Claude prompt for record {record_id}: {error}")
            failed += 1

    print(f"[INFO] Claude Sonnet 5 prompt generation complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


generate_qwen_blending_prompts = generate_claude_blending_prompts


def generate_cta_blended_images(
    fal_or_blend_client: Any,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = FAL_BLENDING_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate 9:16 CTA Blended Image using Fal AI Nano Banana Pro into 'CTA Blended Image'."""
    airtable.ensure_fields({BLENDED_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        INTERIOR_FIELD_FALLBACKS + PROMPT_FIELD_FALLBACKS + BLENDED_FIELD_FALLBACKS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to generate blended images.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        prompt_val = get_first_field_value(fields, PROMPT_FIELD_FALLBACKS)
        blended_val = get_first_field_value(fields, BLENDED_FIELD_FALLBACKS)
        if not prompt_val:
            continue
        if blended_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Nano Banana Pro CTA blending (prompt missing or blended image already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{BLENDED_FIELD}' for {len(eligible)} record(s) "
        f"using Fal AI Nano Banana Pro ({blend_model}, Aspect Ratio: {BLENDED_ASPECT_RATIO})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        prompt_str = str(get_first_field_value(fields, PROMPT_FIELD_FALLBACKS)).strip()
        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELD_FALLBACKS))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))

        image_urls = [url for url in [interior_url, furniture_url] if url]
        if not image_urls:
            print(f"[SKIP] Record {record_id} ({item_label}) has no accessible source image URLs.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Blending CTA image for "
            f"record {record_id} ({item_label}) with Fal AI Nano Banana Pro..."
        )

        downloaded = None
        try:
            if hasattr(fal_or_blend_client, "generate"):
                image_url = fal_or_blend_client.generate(
                    prompt=prompt_str,
                    image_urls=image_urls,
                    aspect_ratio=BLENDED_ASPECT_RATIO,
                    resolution="1K",
                    model=blend_model,
                )
                import requests
                resp = requests.get(image_url, stream=True)
                downloaded = download_to_temp_file(
                    resp,
                    prefix="cta_blend_",
                    suffix=".jpg",
                    context=f"Download CTA blended image from {image_url}",
                )
            elif hasattr(fal_or_blend_client, "generate_image_3_pro"):
                image_url = fal_or_blend_client.generate_image_3_pro(
                    prompt_str,
                    image_urls,
                    aspect_ratio=BLENDED_ASPECT_RATIO,
                    size="1536*2688",
                    model=blend_model,
                    image_labels=["CTA Interior photo", "Furniture Item photo"],
                )
                import requests
                resp = requests.get(image_url, stream=True)
                downloaded = download_to_temp_file(
                    resp,
                    prefix="cta_blend_",
                    suffix=".jpg",
                    context=f"Download Qwen blended image from {image_url}",
                )
            else:
                raise AutomationError("No valid blending client method available.")

            filename = f"cta_blended_{record_id}.jpg"
            target_field = get_first_field_name(fields, BLENDED_FIELD_FALLBACKS)
            airtable.upload_attachment(record_id, target_field, downloaded, filename)
            safe_update_status(airtable, record_id, STATUS_BLENDED_IMAGE)
            print(
                f"[OK] Attached CTA blended image to '{target_field}' and updated "
                f"{STATUS_FIELD} on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed blending CTA image for record {record_id}: {error}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(f"[INFO] Fal AI Nano Banana Pro CTA blending complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def generate_claude_word_generated(
    fal_or_vision: Any,
    airtable: ScrapeAirtableClient,
    *,
    vision_model: str = FAL_VISION_MODEL,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Generate luxury 2-3 word headline in 'Word Generated' using Claude Sonnet 5."""
    airtable.ensure_fields({WORD_GENERATED_FIELD: "singleLineText"})
    records = airtable.list_records(
        BLENDED_FIELD_FALLBACKS + WORD_GENERATED_FALLBACKS + [ITEM_NAME_FIELD, SKU_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to generate words.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        blended_val = get_first_field_value(fields, BLENDED_FIELD_FALLBACKS)
        word_val = get_first_field_value(fields, WORD_GENERATED_FALLBACKS)
        if not blended_val:
            continue
        if word_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Claude Sonnet 5 word generation (blended image missing or word already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{WORD_GENERATED_FIELD}' for {len(eligible)} record(s) "
        f"using Claude Sonnet 5 via Fal AI ({vision_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Lighting Fixture").strip()
        item_label = f"{record_id} ({item_name})"

        blended_url = extract_attachment_url(get_first_field_value(fields, BLENDED_FIELD_FALLBACKS))
        if not blended_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible CTA Blended Image attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing CTA blended image for "
            f"record {record_id} ({item_label}) with Claude Sonnet 5..."
        )

        instruction = (
            "Analyze this luxury interior and lighting design image ('CTA Blended Image'). "
            "Generate an original, elegant, luxury 2 to 4 word headline or hook that captures the unique visual vibe, architectural aesthetic, lighting mood, and interior style shown in the room for an Instagram Story. "
            "Do NOT include or mention any product item names, brand names, catalog titles, or SKU codes. "
            "Base the words purely and dynamically on the visual composition, textures, colors, and lighting atmosphere in the image. "
            "Keep it concise, elegant, and punchy. Output ONLY the 2 to 4 words without quotation marks, commentary, explanations, or extra punctuation."
        )

        try:
            if hasattr(fal_or_vision, "analyze_image"):
                generated_words = fal_or_vision.analyze_image(
                    prompt=instruction,
                    image_urls=[blended_url],
                    model=vision_model,
                )
            else:
                generated_words = "Modern Luxury Living"

            cleaned_words = generated_words.strip().strip('"\'')
            target_field = get_first_field_name(fields, WORD_GENERATED_FALLBACKS)
            airtable.update_records([(record_id, {target_field: cleaned_words})])
            print(
                f"[OK] Generated words '{cleaned_words}' for record {record_id} and updated '{target_field}'"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating Claude words for record {record_id}: {error}")
            failed += 1

    print(f"[INFO] Claude word generation complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def generate_watermark_added_images(
    airtable: ScrapeAirtableClient,
    *,
    limit_records: int | None = None,
    target_record_id: str | None = None,
) -> bool:
    """Stamp Logo and Canva CTA text watermark layout using Python Pillow."""
    airtable.ensure_fields({WATERMARK_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        BLENDED_FIELD_FALLBACKS + WATERMARK_FIELD_FALLBACKS + LOGO_FIELD_FALLBACKS + WORD_GENERATED_FALLBACKS + [ITEM_NAME_FIELD, SKU_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        print("[OK] No records found in Airtable to composite watermark layout.")
        return True

    records = sort_records_by_id(records)
    if target_record_id:
        records = [r for r in records if r["id"] == target_record_id]

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        blended_val = get_first_field_value(fields, BLENDED_FIELD_FALLBACKS)
        watermark_val = get_first_field_value(fields, WATERMARK_FIELD_FALLBACKS)
        if not blended_val:
            continue
        if watermark_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring watermark layout compositing (blended missing or watermark already added).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Stamping HomeCartel logo & CTA text watermark layout (Python Pillow) for {len(eligible)} record(s) "
        f"into '{WATERMARK_FIELD}'..."
    )

    import requests
    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "HomeCartel Lighting").strip()
        item_label = f"{record_id} ({item_name})"

        blended_url = extract_attachment_url(get_first_field_value(fields, BLENDED_FIELD_FALLBACKS))
        if not blended_url:
            print(f"[SKIP] Record {record_id} ({item_label}) has no accessible CTA Blended Image.")
            continue

        logo_url = extract_attachment_url(get_first_field_value(fields, LOGO_FIELD_FALLBACKS))
        words_val = get_first_field_value(fields, WORD_GENERATED_FALLBACKS)
        display_headline = str(words_val).strip() if words_val else item_name

        print(
            f"[INFO] [{position}/{len(eligible)}] Stamping Logo & CTA layout for "
            f"record {record_id} ({item_label}) with local Python Pillow..."
        )

        dl_blended = None
        dl_logo = None
        out_path = None
        try:
            resp_b = requests.get(blended_url, stream=True, timeout=30)
            dl_blended = download_to_temp_file(resp_b, prefix="blend_in_", suffix=".jpg", context="Blended photo dl")

            logo_source_path = None
            if logo_url:
                try:
                    resp_l = requests.get(logo_url, stream=True, timeout=30)
                    dl_logo = download_to_temp_file(resp_l, prefix="logo_in_", suffix=".png", context="Logo dl")
                    logo_source_path = dl_logo.path
                except Exception as e:
                    print(f"[WARN] Failed downloading logo attachment, falling back to local: {e}")

            if not logo_source_path:
                local_logo = find_homecartel_logo_path()
                if local_logo:
                    logo_source_path = local_logo

            with tempfile.NamedTemporaryFile(suffix="_cta_converted.jpg", delete=False) as tf:
                out_path = tf.name

            stamp_cta_story_watermark_and_logo(
                base_image_path=dl_blended.path,
                logo_path=logo_source_path,
                output_path=out_path,
                item_name=display_headline,
            )

            filename = f"cta_converted_{record_id}.jpg"
            output_field_name = get_first_field_name(fields, WATERMARK_FIELD_FALLBACKS)
            airtable.upload_attachment(record_id, output_field_name, out_path, filename)
            safe_update_status(airtable, record_id, STATUS_COMPLETE)
            print(
                f"[OK] Attached composited photo to '{output_field_name}' and updated "
                f"{STATUS_FIELD} on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed compositing watermark layout for record {record_id}: {error}")
            failed += 1
        finally:
            if dl_blended:
                dl_blended.cleanup()
            if dl_logo:
                dl_logo.cleanup()
            if out_path and Path(out_path).exists():
                try:
                    Path(out_path).unlink()
                except Exception:
                    pass
    print(f"[INFO] Watermark layout compositing complete: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def get_first_incomplete_record(airtable: ScrapeAirtableClient) -> dict[str, Any] | None:
    records = airtable.list_records(
        INTERIOR_FIELD_FALLBACKS
        + PROMPT_FIELD_FALLBACKS
        + BLENDED_FIELD_FALLBACKS
        + WORD_GENERATED_FALLBACKS
        + CONVERTED_FIELD_FALLBACKS
        + [FIELD_NAME, ITEM_NAME_FIELD, SKU_FIELD, STATUS_FIELD, "ID", "Auto Number", "No"]
    )
    if not records:
        return None
    records = sort_records_by_id(records)
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().lower()
        if status in {"complete", "completed"}:
            continue
        converted_val = get_first_field_value(fields, CONVERTED_FIELD_FALLBACKS)
        if converted_val:
            continue
        return record
    return None


def show_menu() -> str:
    print("\n" + "=" * 64)
    print("           CTA STORY AI GENERATION & BLENDING MENU           ")
    print("=" * 64)
    print(" Select a phase to run:\n")
    print(" [1] Scrape Akeneo Products to Airtable (1 item)")
    print(" [2] Krea AI Interior Generation (9:16) -> 'CTA Interior'")
    print(" [3] Claude Sonnet 5 Prompt Generation (Fal AI) -> 'Blending Prompt'")
    print(" [4] Fal AI Nano Banana Pro Blending (9:16) -> 'CTA Blended Image'")
    print(" [5] Claude Sonnet 5 Headline Generation -> 'Word Generated'")
    print(" [6] Python Local CTA Layout & Logo Stamping (9:16) -> 'CTA Converted Image'")
    print(" [7] Run Full End-to-End Pipeline (Scrape Akeneo 1 item + Steps 2-6)")
    print(" [8] Exit\n")

    menu_choices = {
        "1": "scrape",
        "2": "interior",
        "3": "prompt",
        "4": "blend",
        "5": "words",
        "6": "conversion",
        "7": "all",
        "8": "exit",
    }
    while True:
        choice = input(" Enter choice [1-8]: ").strip()
        if choice in menu_choices:
            return menu_choices[choice]
        print("[WARN] Invalid option. Please enter 1, 2, 3, 4, 5, 6, 7, or 8.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="CTA Story AI Generation & Blending Pipeline"
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["scrape", "interior", "prompt", "blend", "words", "conversion", "watermark", "all", "menu"],
        default="all",
        help="Mode of operation: scrape, interior, prompt, blend, words, conversion, all, or menu (default: all)",
    )
    parser.add_argument(
        "--category",
        "-c",
        default=DEFAULT_CATEGORY,
        help=f"Target table category (default: {DEFAULT_CATEGORY})",
    )
    parser.add_argument(
        "--prompt",
        "-p",
        default=None,
        help="Optional custom prompt override for Krea interior generation",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Style code filter (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override Airtable destination table ID",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=1,
        metavar="N",
        help="Process at most N records in each phase (default: 1)",
    )
    return parser.parse_args(argv)


def run_pipeline(
    mode: str = "all",
    category_code: str = DEFAULT_CATEGORY,
    style_code: str = DEFAULT_STYLE,
    custom_prompt: str | None = None,
    table_id_override: str | None = None,
    max_items: int = 1,
) -> int:
    base_settings = load_settings()
    scrape_settings = load_scrape_settings(
        category_code=category_code,
        style_code=style_code,
        table_id_override=table_id_override,
    )

    interior_prompt = prompt_for_category(scrape_settings.category_code, custom_prompt)
    target_table_id = (
        table_id_override
        or scrape_settings.airtable_table_id
        or DEFAULT_TABLE_ID
    )

    airtable = ScrapeAirtableClient(
        token=scrape_settings.airtable_token,
        base_id=scrape_settings.airtable_base_id,
        table_id=target_table_id,
    )

    print("=" * 64)
    print(f"CTA Story Pipeline | Category: {scrape_settings.category_code}")
    print(f"Airtable: Base {scrape_settings.airtable_base_id} / Table {target_table_id}")
    print("=" * 64)

    moodboard_id = moodboard_id_for_category(scrape_settings.category_code, DEFAULT_MOODBOARD_ID)
    count = max_items or 1
    failures = 0

    if mode == "scrape":
        print(f"[INFO] Phase 1: Scraping {count} product item(s) from Akeneo to Airtable...")
        for i in range(count):
            try:
                if not run_category_scrape(
                    category_code=scrape_settings.category_code,
                    style_code=scrape_settings.style_code,
                    items_per_row_override=1,
                    max_items=1,
                    table_id_override=target_table_id,
                ):
                    failures += 1
                else:
                    newly_scraped = get_first_incomplete_record(airtable)
                    if newly_scraped:
                        ensure_cta_layout_uploaded(airtable, newly_scraped["id"], newly_scraped.get("fields", {}))
                        ensure_cta_logo_uploaded(airtable, newly_scraped["id"], newly_scraped.get("fields", {}))
            except Exception as error:
                print(f"[ERROR] Failed scraping Akeneo products: {error}")
                failures += 1
        backfill_missing_cta_assets(airtable)
        return 1 if failures else 0

    if mode == "interior":
        base_settings.require({"krea"})
        krea = KreaClient(base_settings.krea_token, base_url=base_settings.krea_base_url)
        return 0 if generate_krea_interiors(
            krea,
            airtable,
            moodboard_id=moodboard_id,
            prompt=interior_prompt,
            limit_records=count,
        ) else 1

    if mode == "prompt":
        base_settings.require({"fal"})
        fal_client = FalClient(base_settings.fal_key)
        return 0 if generate_claude_blending_prompts(
            fal_client,
            airtable,
            limit_records=count,
        ) else 1

    if mode == "blend":
        base_settings.require({"fal"})
        fal_client = FalClient(base_settings.fal_key)
        return 0 if generate_cta_blended_images(
            fal_client,
            airtable,
            limit_records=count,
        ) else 1

    if mode == "words":
        base_settings.require({"fal"})
        fal_client = FalClient(base_settings.fal_key)
        return 0 if generate_claude_word_generated(
            fal_client,
            airtable,
            limit_records=count,
        ) else 1

    if mode == "conversion":
        return 0 if run_cta_conversion(
            base_settings,
            table_id=target_table_id,
            max_items=count,
            use_local_pil=True,
        ) else 1

    # mode == 'all': Full 6-Phase Row-by-Row Pipeline Loop
    base_settings.require({"krea", "fal"})
    krea = KreaClient(base_settings.krea_token, base_url=base_settings.krea_base_url)
    fal_client = FalClient(base_settings.fal_key)

    for row_idx in range(1, count + 1):
        print(f"\n{'=' * 30} ROW {row_idx}/{count} {'=' * 30}")
        incomplete_rec = get_first_incomplete_record(airtable)
        if incomplete_rec:
            target_record_id = incomplete_rec["id"]
            fields = incomplete_rec.get("fields", {})
            label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or target_record_id
            print(f"[INFO] Found incomplete row: Record {target_record_id} ({label}). Completing this row...")
        else:
            print(f"[INFO] [Phase 1/6] Scraping 1 product item from Akeneo to Airtable...")
            try:
                if not run_category_scrape(
                    category_code=scrape_settings.category_code,
                    style_code=scrape_settings.style_code,
                    items_per_row_override=1,
                    max_items=1,
                    table_id_override=target_table_id,
                ):
                    print(f"[WARN] Akeneo scrape returned warnings on Row {row_idx}.")
            except Exception as error:
                print(f"[ERROR] Failed scraping Akeneo products on Row {row_idx}: {error}")
                failures += 1
                continue

            newly_scraped_rec = get_first_incomplete_record(airtable)
            if not newly_scraped_rec:
                print(f"[WARN] No incomplete record found after scrape on Row {row_idx}.")
                continue
            target_record_id = newly_scraped_rec["id"]
            fields = newly_scraped_rec.get("fields", {})
            ensure_cta_layout_uploaded(airtable, target_record_id, fields)
            ensure_cta_logo_uploaded(airtable, target_record_id, fields)

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}
        item_label = current_fields.get(ITEM_NAME_FIELD) or current_fields.get(SKU_FIELD) or target_record_id

        # Phase 2: Krea AI Interior Generation (9:16) -> 'CTA Interior'
        if not get_first_field_value(current_fields, INTERIOR_FIELD_FALLBACKS):
            print(f"[INFO] [Phase 2/6] Generating 9:16 Room Interior with Krea AI for Record {target_record_id}...")
            ok_phase2 = generate_krea_interiors(
                krea,
                airtable,
                moodboard_id=moodboard_id,
                prompt=interior_prompt,
                target_record_id=target_record_id,
            )
            if not ok_phase2:
                print(f"[ERROR] Phase 2 Interior generation failed on Record {target_record_id}.")
                failures += 1
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 3: Claude Sonnet 5 Prompt Generation -> 'Blending Prompt'
        if not get_first_field_value(current_fields, PROMPT_FIELD_FALLBACKS):
            print(f"[INFO] [Phase 3/6] Analyzing Photos with Claude Sonnet 5 for Record {target_record_id}...")
            ok_phase3 = generate_claude_blending_prompts(
                fal_client,
                airtable,
                target_record_id=target_record_id,
            )
            if not ok_phase3:
                print(f"[ERROR] Phase 3 Claude Prompt generation failed on Record {target_record_id}.")
                failures += 1
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 4: Fal AI Nano Banana Pro Blending (9:16) -> 'CTA Blended Image'
        if not get_first_field_value(current_fields, BLENDED_FIELD_FALLBACKS):
            print(f"[INFO] [Phase 4/6] Blending Furniture + Interior with Fal AI Nano Banana Pro for Record {target_record_id}...")
            ok_phase4 = generate_cta_blended_images(
                fal_client,
                airtable,
                target_record_id=target_record_id,
            )
            if not ok_phase4:
                print(f"[ERROR] Phase 4 Nano Banana Pro blending failed on Record {target_record_id}.")
                failures += 1
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 5: Claude Sonnet 5 Headline Analysis -> 'Word Generated'
        if not get_first_field_value(current_fields, WORD_GENERATED_FALLBACKS):
            print(f"[INFO] [Phase 5/6] Analyzing 'CTA Blended Image' with Claude Sonnet 5 for Record {target_record_id}...")
            ok_phase5 = generate_claude_word_generated(
                fal_client,
                airtable,
                target_record_id=target_record_id,
            )
            if not ok_phase5:
                print(f"[ERROR] Phase 5 Claude Headline Analysis failed on Record {target_record_id}.")
                failures += 1
                continue

        rec_fetch = airtable.get_record(target_record_id)
        current_fields = rec_fetch.get("fields", {}) if rec_fetch else {}

        # Phase 6: Python Local CTA Layout & Logo Stamping (9:16) -> 'CTA Converted Image' / 'Watermark Added'
        if not get_first_field_value(current_fields, CONVERTED_FIELD_FALLBACKS):
            print(f"[INFO] [Phase 6/6] Stamping Logo & CTA Layout (Python Pillow) for Record {target_record_id}...")
            ok_phase6 = run_cta_conversion(
                base_settings,
                table_id=target_table_id,
                target_record_id=target_record_id,
                use_local_pil=True,
            )
            if not ok_phase6:
                print(f"[ERROR] Phase 6 Local CTA conversion failed on Record {target_record_id}.")
                failures += 1
                continue

        print(f"[ROW {row_idx} COMPLETE] Record {target_record_id} is 100% COMPLETE! Status: Complete.")

    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = args.mode

    if mode == "menu":
        mode = show_menu()
        if mode == "exit":
            print("[INFO] Exiting CTA Story Pipeline. Goodbye!")
            return 0

    return run_pipeline(
        mode=mode,
        category_code=args.category,
        style_code=args.style,
        custom_prompt=args.prompt,
        table_id_override=args.table_id,
        max_items=args.max_items,
    )


if __name__ == "__main__":
    sys.exit(main())
