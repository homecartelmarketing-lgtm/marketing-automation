"""Moodboard #1 Feed AI Generation, Blending & Local Logo Overlay Pipeline.

Runs the complete AI & local composite pipeline for Moodboard #1 Feed on Airtable (tbl9u5vjgx8kuE44R):
1. [Phase 1/6] Krea AI Interior Generation (4:5, Moodboard ID: b5ffdcbb-192e-4528-8d86-d1a4cf496887) -> 'Interior Generated', Status -> 'Interior Generated'
2. [Phase 2/6] Fal AI Claude Sonnet 5 Prompt Generation -> 'Prompt for Blending', Status -> 'Generating Prompt for Blending'
3. [Phase 3/6] Fal AI Nano Banana Pro Image-to-Image Blending (4:5, 1k) -> 'Moodboard V1 Blended', Status -> 'Blended Image Generated'
4. [Phase 4/6] Local Python PIL Logo Overlay (Zero API / Exact Canva Position: 190.3x63.5 @ x=108, y=1178.5) -> 'Moodboard Added Watermark', Status -> 'Added Watermark Layout'
5. [Phase 5/6] Fal AI Nano Banana Pro Material Moodboard Conversion (4:5, 1k) -> 'Moodboard Converted', Status -> 'Moodboard Converted'
6. [Phase 6/6] Fal AI Nano Banana Pro Close-up Macro Photo Generation (4:5, 1k) -> 'Closeup Photo', Status -> 'Complete'

Usage::

    python generate_moodboard_1_feed.py
    python generate_moodboard_1_feed.py --max-items 5
    python generate_moodboard_1_feed.py --table-id tbl9u5vjgx8kuE44R
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from PIL import Image
import requests

from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.overlay import HOMECARTEL_LOGO_BOX, stamp_logo
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)

DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_MOODBOARD_1_FEED", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_MOODBOARD_FEED_1", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_REVISED_MOODBOARD_FEED", "").strip()
    or "tbl9u5vjgx8kuE44R"
)
DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_MOODBOARD_1_FEED", "").strip()
    or "b5ffdcbb-192e-4528-8d86-d1a4cf496887"
)
DEFAULT_PROMPT = "Generate me a modern living room with hanging chandelier from the ceiling"
DEFAULT_CATEGORY = "chandeliers"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"
STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "Interior Generated"
STATUS_GENERATING_PROMPT = "Generating Prompt for Blending"
STATUS_BLENDED_IMAGE = "Blended Image Generated"
STATUS_ADDED_WATERMARK = "Added Watermark Layout"
STATUS_MOODBOARD_CONVERTED = "Moodboard Converted"
STATUS_COMPLETE = "Complete"

INTERIOR_FIELD = "Interior Generated"
INTERIOR_ASPECT_RATIO = "4:5"
PROMPT_FIELD = "Prompt for Blending"
BLENDED_FIELD = "Moodboard V1 Blended"
WATERMARK_LAYOUT_FIELD = "Watermark Layout"
WATERMARK_ADDED_FIELD = "Moodboard Added Watermark"
MOODBOARD_LAYOUT_FIELD = "Moodboard Layout"
MOODBOARD_CONVERTED_FIELD = "Moodboard Converted"
CLOSEUP_LAYOUT_FIELD = "Closeup Photo Layout"
CLOSEUP_FIELD = "Closeup Photo"

FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_NANO_MODEL = os.getenv("FAL_NANO_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
NANO_ASPECT_RATIO = "4:5"
NANO_RESOLUTION = "1k"

AUDIT_LOG_DIR = Path("output/logs")
AUDIT_LOG_CLAUDE = AUDIT_LOG_DIR / "moodboard_1_feed_claude_logs.json"
AUDIT_LOG_FAL = AUDIT_LOG_DIR / "moodboard_1_feed_fal_logs.json"

DEFAULT_CONVERTED_PROMPT = json.dumps(
    {
        "assistant_instruction": {
            "generate_image": False,
            "instruction": "Do not generate image. Use this JSON as a reusable prompt for converting any uploaded interior photo into a three-material editorial moodboard.",
        },
        "task": "dynamic_interior_to_material_moodboard",
        "objective": "Analyze the current uploaded interior photo and convert it into a premium three-swatch material moodboard. The interior is dynamic and may change every time. Determine all materials, colors, textures, finishes, and labels from the current interior only. Use the reference only for layout, white background, typography, and editorial style.",
        "source_rules": {
            "dynamic_input": "Treat the uploaded interior photo as the only source for material selection.",
            "reanalyze_each_time": "Analyze every new interior from scratch. Never reuse materials unless genuinely visible in the new photo.",
            "no_room_recreation": "Do not include the full interior; translate the room into material samples only.",
        },
        "reference_rules": {
            "instruction": "Follow the reference moodboard's three-swatch arrangement, layering, white space, shadows, minimalist labels, and premium presentation. Do not copy its materials, colors, textures, labels, wording, or content."
        },
        "material_selection": {
            "count": 3,
            "instruction": "Identify the three most important design-defining materials, finishes, textures, or surfaces actually visible in the uploaded interior.",
            "logic": "Choose the best three genuine room materials. Any material categories mentioned in this JSON are guidance only and must never become automatic selections.",
            "accuracy": "Match visible color, undertone, grain, weave, veining, reflectivity, softness, roughness, and finish as closely as possible.",
            "exclude": "Do not select logos, watermarks, text overlays, people, complete furniture pieces, whole lighting fixtures, or decorative graphics.",
        },
        "strict_no_copy_rule": {
            "instruction": "Any material names, phrases, categories, or examples in this JSON are guidance only. Never copy, reuse, lightly modify, closely paraphrase, or treat them as default output. Do not copy text from the reference moodboard.",
            "label_generation": "Generate every final label independently from the current interior. There is no fixed vocabulary. Use a label only when it accurately describes a visibly detected material.",
            "enforcement": "Never output a material name merely because it appears in this prompt; it must be justified by the uploaded image.",
        },
        "swatch_rendering": {
            "instruction": "Render all three selections as realistic close-up physical samples, never flat color blocks.",
            "details": "Show authentic material-specific surface detail, including realistic grain, fibers, weave, veining, pores, texture, finish, or reflections. Painted surfaces should appear subtly tactile.",
            "quality": "Use photorealistic macro detail and soft studio lighting.",
        },
        "layout": {
            "background": "Pure white only. No gradients, colored backgrounds, patterns, or decorative scenery.",
            "upper_left": "Place one large square swatch in the upper-left area.",
            "upper_right": "Place one large square swatch in the upper-right area.",
            "lower_center": "Place the third swatch below the upper pair, approximately centered, with a subtle layered or overlapping relationship inspired by the reference.",
            "spacing": "Maintain generous white space and a balanced luxury-editorial composition.",
            "edges": "Use clean edges for rigid materials. Use a zigzag edge only for a genuinely soft material.",
            "shadows": "Add soft, diffused light-gray shadows beneath each sample.",
        },
        "labels": {
            "instruction": "Create one concise label for each swatch based strictly on its detected material, color, character, or finish.",
            "length": "Prefer two to four words.",
            "style": "Use refined interior-design terminology with a modern sans-serif font.",
            "placement": "Position each label near the top of its sample.",
            "legibility": "Use white text on dark samples and dark-neutral text on very light samples. Do not add boxes, banners, or heavy effects.",
            "anti_copy": "Do not copy or imitate any label shown in the reference image or any example wording contained in this JSON.",
        },
        "restrictions": "Do not include the original interior photo, miniature room images, furniture cutouts, complete decor objects, people, logos, watermarks, extra headlines, extra captions, or more than three swatches.",
        "output": {
            "orientation": "vertical portrait",
            "style": "minimalist, photorealistic premium editorial moodboard",
            "final_rule": "For every new interior, independently identify three context-specific materials and create three original labels. Never recycle, default to, imitate, or copy examples from this prompt or wording from the reference.",
        },
    },
    indent=2,
)

DEFAULT_CLOSEUP_PROMPT = (
    "Generate a photorealistic luxury macro detail product photograph of the exact furniture item "
    "from the 'Furniture Item' photo. Use the image in 'Closeup Photo Layout' as a strict reference for the "
    "composition style: a dynamic angled close-up view with a shallow depth of field, sharp focus on "
    "the item's material texture, metallic highlights, and fine craftsmanship in the foreground while "
    "the background softly blurs away against a seamless, clean light-neutral studio background with soft studio lighting."
)


def append_audit_log(log_entry: dict[str, Any], log_path: Path = AUDIT_LOG_CLAUDE) -> None:
    """Append a structured JSON log entry for auditing and transparency."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            logs = json.loads(log_path.read_text(encoding="utf-8"))
            if not isinstance(logs, list):
                logs = []
        except Exception:
            logs = []
    logs.append(log_entry)
    try:
        log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception as err:
        print(f"[WARN] Failed writing audit log: {err}")


def extract_attachment_url(field_value: Any) -> str:
    """Pull primary HTTP download URL from Airtable attachment field value."""
    if isinstance(field_value, list) and field_value:
        first = field_value[0]
        if isinstance(first, dict):
            return str(first.get("url") or first.get("permalink") or "")
    if isinstance(field_value, dict):
        return str(field_value.get("url") or field_value.get("permalink") or "")
    return ""


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1 — Krea AI Room Interior Generation (4:5)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_v1_interiors(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_PROMPT,
    interior_field: str = INTERIOR_FIELD,
    aspect_ratio: str = INTERIOR_ASPECT_RATIO,
    limit_records: int | None = None,
) -> bool:
    """Generate 1 Krea interior photo per record into interior_field for Standby records."""
    airtable.ensure_fields({interior_field: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        [interior_field, FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable to populate interior photos.")
        return True

    unpopulated = [
        record
        for record in records
        if str(record.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold() == STATUS_STANDBY.casefold()
        and not record.get("fields", {}).get(interior_field)
    ]
    if not unpopulated:
        print(f"[OK] No records found with Status '{STATUS_STANDBY}' missing '{interior_field}'.")
        return True

    if limit_records is not None:
        unpopulated = unpopulated[:limit_records]

    print(
        f"[INFO] Generating '{interior_field}' for {len(unpopulated)} '{STATUS_STANDBY}' record(s) "
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
            filename = f"interior_{record_id}.jpg"
            airtable.upload_attachment(record_id, interior_field, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_INTERIOR_GENERATED})])
            print(
                f"[OK] Attached Krea image to '{interior_field}' and updated "
                f"{STATUS_FIELD} to '{STATUS_INTERIOR_GENERATED}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(
                f"[ERROR] Failed generating '{interior_field}' for record {record_id}: {error}"
            )
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Krea interior generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Fal AI Claude Sonnet 5 Prompt Analysis
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_v1_prompts(
    fal: FalClient | Any,
    airtable: ScrapeAirtableClient,
    *,
    prompt_model: str = FAL_VISION_MODEL,
    limit_records: int | None = None,
) -> bool:
    """Generate detailed blending prompt using Claude Sonnet 5 via Fal AI into 'Prompt for Blending'."""
    airtable.ensure_fields({PROMPT_FIELD: "multilineText"})
    records = airtable.list_records(
        [INTERIOR_FIELD, FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, PROMPT_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable to generate prompts.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        interior_attachments = fields.get(INTERIOR_FIELD)
        # CRITICAL GUARD: Only call Claude if Interior Generated photo EXISTS and Prompt for Blending is empty
        if not interior_attachments:
            continue
        if fields.get(PROMPT_FIELD):
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Claude Sonnet 5 prompt generation ('{INTERIOR_FIELD}' missing or '{PROMPT_FIELD}' already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{PROMPT_FIELD}' for {len(eligible)} record(s) "
        f"using Claude Sonnet 5 via Fal AI ({prompt_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id).strip()

        interior_url = extract_attachment_url(fields.get(INTERIOR_FIELD))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))

        if not interior_url or not furniture_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing photos & generating prompt for "
            f"record {record_id} ({item_label}) with Claude Sonnet 5..."
        )

        instruction = (
            f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
            f"and Image 2 as the product photo for '{item_label}' ('Furniture Item').\n"
            f"Generate a detailed, photorealistic image-blending prompt for Nano Banana Pro (4:5 portrait aspect ratio). "
            f"The prompt must describe naturally mounting and integrating the '{item_label}' from Image 2 into the room interior from Image 1.\n"
            f"CRITICAL ISOLATION & MOUNTING RULES:\n"
            f"1. The '{item_label}' shown in Image 2 MUST BE THE PRIMARY/ONLY CEILING OR STATEMENT FIXTURE in the scene.\n"
            f"2. Remove and replace any placeholder or pre-existing conflicting fixtures from Image 1.\n"
            f"3. Ensure authentic materials, realistic chain/rod/cord hanging mounting, ceiling canopy, natural warm illumination, soft ambient glow, and accurate contact shadows on surrounding ceiling, walls, and floors.\n"
            f"4. Maintain a luxury editorial 4:5 vertical portrait composition.\n\n"
            f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
        )

        try:
            if hasattr(fal, "generate_vision_prompt"):
                blending_prompt = fal.generate_vision_prompt(
                    image_urls=[interior_url, furniture_url],
                    prompt=instruction,
                    model=prompt_model,
                ).strip().strip('"').strip("'")
            elif hasattr(fal, "generate_blending_json_prompt"):
                blending_prompt = fal.generate_blending_json_prompt(
                    interior_url,
                    furniture_url,
                    model=prompt_model,
                )
            else:
                raise AutomationError("Fal client does not support vision prompt generation")

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 2: Claude Sonnet 5 Prompt Generation",
                "api_provider": "Fal AI / OpenRouter",
                "api_model": prompt_model,
                "input_interior_url": interior_url,
                "input_furniture_url": furniture_url,
                "generated_prompt": blending_prompt,
            }, AUDIT_LOG_CLAUDE)

            airtable.update_records([(record_id, {PROMPT_FIELD: blending_prompt, STATUS_FIELD: STATUS_GENERATING_PROMPT})])
            print(f"[OK] Saved Claude Sonnet 5 prompt to '{PROMPT_FIELD}' and updated {STATUS_FIELD} to '{STATUS_GENERATING_PROMPT}' on record {record_id}")
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating prompt for record {record_id}: {error}")
            failed += 1

    print(
        f"[INFO] Claude Sonnet 5 prompt generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Fal AI Nano Banana Pro Image Blending (4:5, 1k)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_v1_blends(
    fal: FalClient | Any,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = FAL_NANO_MODEL,
    aspect_ratio: str = NANO_ASPECT_RATIO,
    resolution: str = NANO_RESOLUTION,
    limit_records: int | None = None,
) -> bool:
    """Generate image-to-image blended photo using Nano Banana Pro via Fal AI (4:5, 1k) into 'Moodboard V1 Blended'."""
    airtable.ensure_fields({BLENDED_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        [INTERIOR_FIELD, FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD, PROMPT_FIELD, BLENDED_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable for image blending.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        prompt_text = str(fields.get(PROMPT_FIELD) or "").strip()
        blended_attachments = fields.get(BLENDED_FIELD)
        if not prompt_text:
            continue
        if blended_attachments:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Nano Banana Pro blending ('{PROMPT_FIELD}' missing or '{BLENDED_FIELD}' already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{BLENDED_FIELD}' for {len(eligible)} record(s) "
        f"using Nano Banana Pro via Fal AI ({blend_model}, {aspect_ratio}, {resolution})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
        prompt_text = str(fields.get(PROMPT_FIELD) or "").strip()

        interior_url = extract_attachment_url(fields.get(INTERIOR_FIELD))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))
        image_inputs = [url for url in (interior_url, furniture_url) if url]

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating blended photo for "
            f"record {record_id} ({item_label}) with Nano Banana Pro..."
        )

        downloaded = None
        try:
            image_url = fal.generate(
                prompt=prompt_text,
                image_urls=image_inputs,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                model=blend_model,
            )
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="blended_image_",
                suffix=".jpg",
                context=f"Download blended image from {image_url}",
            )
            filename = f"blended_{record_id}.jpg"
            airtable.upload_attachment(record_id, BLENDED_FIELD, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_BLENDED_IMAGE})])
            print(
                f"[OK] Attached blended image to '{BLENDED_FIELD}' and updated "
                f"{STATUS_FIELD} to '{STATUS_BLENDED_IMAGE}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            err_msg = str(error).encode("ascii", errors="replace").decode("ascii")
            print(f"[ERROR] Failed blending image for record {record_id}: {err_msg}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Nano Banana Pro blending complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4 — Local Python PIL Logo Overlay (190.3x63.5 @ x=108, y=1178.5)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_v1_watermarks(
    airtable: ScrapeAirtableClient,
    *,
    limit_records: int | None = None,
) -> bool:
    """Stamp HomeCartel brand mark onto 'Moodboard V1 Blended' using local PIL into 'Moodboard Added Watermark'.

    Zero API call / instant local script:
    - Base Canvas: 1080x1350 (4:5)
    - Box: width 190.3px, height 63.5px, x 108.0px, y 1178.5px, 0 degrees
    """
    airtable.ensure_fields({
        BLENDED_FIELD: "multipleAttachments",
        WATERMARK_LAYOUT_FIELD: "multipleAttachments",
        WATERMARK_ADDED_FIELD: "multipleAttachments",
        STATUS_FIELD: "singleSelect",
    })
    records = airtable.list_records(
        [BLENDED_FIELD, WATERMARK_LAYOUT_FIELD, WATERMARK_ADDED_FIELD, "Moodboard Watermark", "Logo", SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable to process watermark layout.")
        return True

    eligible = [
        record
        for record in records
        if record.get("fields", {}).get(BLENDED_FIELD)
        and not record.get("fields", {}).get(WATERMARK_ADDED_FIELD)
    ]
    if limit_records is not None:
        eligible = eligible[:limit_records]

    if not eligible:
        print(
            f"[OK] No records requiring watermark overlay "
            f"('{BLENDED_FIELD}' missing or '{WATERMARK_ADDED_FIELD}' already filled)."
        )
        return True

    print(
        f"[INFO] Stamping local PIL logo watermark onto {len(eligible)} record(s) "
        f"(Coordinates: W=190.3, H=63.5, X=108.0, Y=1178.5)..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        blended_url = extract_attachment_url(fields.get(BLENDED_FIELD))
        # Look for logo/layout attachment in record fields
        logo_url = (
            extract_attachment_url(fields.get(WATERMARK_LAYOUT_FIELD))
            or extract_attachment_url(fields.get("Moodboard Watermark"))
            or extract_attachment_url(fields.get("Logo"))
        )

        # If no logo in record, look for any record in the table with a watermark/logo
        if not logo_url:
            for other in records:
                cand = (
                    extract_attachment_url(other.get("fields", {}).get(WATERMARK_LAYOUT_FIELD))
                    or extract_attachment_url(other.get("fields", {}).get("Moodboard Watermark"))
                    or extract_attachment_url(other.get("fields", {}).get("Logo"))
                )
                if cand:
                    logo_url = cand
                    break

        if not blended_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing blended image URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Stamping logo for "
            f"record {record_id} ({item_label}) with local PIL..."
        )

        dl_blended = None
        dl_logo = None
        out_file = None
        try:
            resp_blended = requests.get(blended_url, stream=True)
            dl_blended = download_to_temp_file(
                resp_blended,
                prefix="wm_blend_",
                suffix=".jpg",
                context=f"Download blended image from {blended_url}",
            )

            if logo_url:
                resp_logo = requests.get(logo_url, stream=True)
                dl_logo = download_to_temp_file(
                    resp_logo,
                    prefix="wm_logo_",
                    suffix=".png",
                    context=f"Download logo from {logo_url}",
                )
                logo_source = dl_logo.path
            else:
                # Fallback to local default logo or white canvas text
                candidate_local_logos = [
                    Path("content_automation/assets/logo.png"),
                    Path("static/img/logo.png"),
                    Path("logo.png"),
                ]
                found_logo = next((p for p in candidate_local_logos if p.is_file()), None)
                if not found_logo:
                    print(f"[WARN] No logo attachment or local file found; skipping overlay for record {record_id}")
                    failed += 1
                    continue
                logo_source = found_logo

            out_path = Path(dl_blended.path).with_name(f"watermarked_{record_id}.jpg")
            stamp_logo(
                Path(dl_blended.path),
                logo_source,
                destination=out_path,
                box=HOMECARTEL_LOGO_BOX,
            )

            filename = f"watermarked_{record_id}.jpg"
            airtable.upload_attachment(record_id, WATERMARK_ADDED_FIELD, out_path, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_ADDED_WATERMARK})])
            print(
                f"[OK] Attached watermarked image to '{WATERMARK_ADDED_FIELD}' and updated "
                f"{STATUS_FIELD} to '{STATUS_ADDED_WATERMARK}' on record {record_id}"
            )
            succeeded += 1
            if out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass
        except Exception as error:
            err_msg = str(error).encode("ascii", errors="replace").decode("ascii")
            print(f"[ERROR] Failed stamping watermark for record {record_id}: {err_msg}")
            failed += 1
        finally:
            if dl_blended:
                dl_blended.cleanup()
            if dl_logo:
                dl_logo.cleanup()

    print(
        f"[INFO] Local PIL logo overlay complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 5 — Fal AI Nano Banana Pro Material Moodboard Conversion (4:5, 1k)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_v1_converted(
    fal: FalClient | Any,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = FAL_NANO_MODEL,
    aspect_ratio: str = NANO_ASPECT_RATIO,
    resolution: str = NANO_RESOLUTION,
    limit_records: int | None = None,
) -> bool:
    """Convert 'Moodboard V1 Blended' photo + 'Moodboard Layout' into 'Moodboard Converted' using Nano Banana Pro (4:5, 1k)."""
    airtable.ensure_fields({
        BLENDED_FIELD: "multipleAttachments",
        MOODBOARD_LAYOUT_FIELD: "multipleAttachments",
        MOODBOARD_CONVERTED_FIELD: "multipleAttachments",
        STATUS_FIELD: "singleSelect",
    })
    records = airtable.list_records(
        [BLENDED_FIELD, MOODBOARD_LAYOUT_FIELD, MOODBOARD_CONVERTED_FIELD, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable to process converted moodboard.")
        return True

    eligible = [
        record
        for record in records
        if record.get("fields", {}).get(BLENDED_FIELD)
        and record.get("fields", {}).get(MOODBOARD_LAYOUT_FIELD)
        and not record.get("fields", {}).get(MOODBOARD_CONVERTED_FIELD)
    ]
    if limit_records is not None:
        eligible = eligible[:limit_records]

    if not eligible:
        print(
            f"[OK] No records requiring Nano Banana Pro moodboard conversion "
            f"('{BLENDED_FIELD}' missing, '{MOODBOARD_LAYOUT_FIELD}' missing, or '{MOODBOARD_CONVERTED_FIELD}' already filled)."
        )
        return True

    print(
        f"[INFO] Generating '{MOODBOARD_CONVERTED_FIELD}' for {len(eligible)} record(s) "
        f"using Nano Banana Pro via Fal AI ({blend_model}, {aspect_ratio}, {resolution})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        blended_url = extract_attachment_url(fields.get(BLENDED_FIELD))
        layout_url = extract_attachment_url(fields.get(MOODBOARD_LAYOUT_FIELD))
        image_inputs = [url for url in (blended_url, layout_url) if url]

        print(
            f"[INFO] [{position}/{len(eligible)}] Converting moodboard for "
            f"record {record_id} ({item_label}) with Nano Banana Pro..."
        )

        downloaded = None
        try:
            image_url = fal.generate(
                prompt=DEFAULT_CONVERTED_PROMPT,
                image_urls=image_inputs,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                model=blend_model,
            )
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="converted_moodboard_",
                suffix=".jpg",
                context=f"Download converted moodboard from {image_url}",
            )
            filename = f"converted_{record_id}.jpg"
            airtable.upload_attachment(record_id, MOODBOARD_CONVERTED_FIELD, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_MOODBOARD_CONVERTED})])
            print(
                f"[OK] Attached converted image to '{MOODBOARD_CONVERTED_FIELD}' and updated "
                f"{STATUS_FIELD} to '{STATUS_MOODBOARD_CONVERTED}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            err_msg = str(error).encode("ascii", errors="replace").decode("ascii")
            print(f"[ERROR] Failed converting moodboard for record {record_id}: {err_msg}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Nano Banana Pro moodboard conversion complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# ══════════════════════════════════════════════════════════════════════════
# PHASE 6 — Fal AI Nano Banana Pro Close-up Photo Generation (4:5, 1k)
# ══════════════════════════════════════════════════════════════════════════

def generate_moodboard_v1_closeups(
    fal: FalClient | Any,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = FAL_NANO_MODEL,
    aspect_ratio: str = NANO_ASPECT_RATIO,
    resolution: str = NANO_RESOLUTION,
    limit_records: int | None = None,
) -> bool:
    """Generate close-up macro product photo using 'Furniture Item' + 'Closeup Photo Layout' reference into 'Closeup Photo' (4:5, 1k)."""
    airtable.ensure_fields({
        FIELD_NAME: "multipleAttachments",
        CLOSEUP_LAYOUT_FIELD: "multipleAttachments",
        CLOSEUP_FIELD: "multipleAttachments",
        STATUS_FIELD: "singleSelect",
    })
    records = airtable.list_records(
        [FIELD_NAME, CLOSEUP_LAYOUT_FIELD, CLOSEUP_FIELD, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable to process close-up photos.")
        return True

    eligible = [
        record
        for record in records
        if record.get("fields", {}).get(FIELD_NAME)
        and record.get("fields", {}).get(CLOSEUP_LAYOUT_FIELD)
        and not record.get("fields", {}).get(CLOSEUP_FIELD)
    ]
    if limit_records is not None:
        eligible = eligible[:limit_records]

    if not eligible:
        print(
            f"[OK] No records requiring close-up photo generation "
            f"('{FIELD_NAME}' missing, '{CLOSEUP_LAYOUT_FIELD}' missing, or '{CLOSEUP_FIELD}' already filled)."
        )
        return True

    print(
        f"[INFO] Generating '{CLOSEUP_FIELD}' for {len(eligible)} record(s) "
        f"using Nano Banana Pro via Fal AI ({blend_model}, {aspect_ratio}, {resolution})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))
        layout_url = extract_attachment_url(fields.get(CLOSEUP_LAYOUT_FIELD))
        image_inputs = [url for url in (furniture_url, layout_url) if url]

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating close-up photo for "
            f"record {record_id} ({item_label}) with Nano Banana Pro..."
        )

        downloaded = None
        try:
            image_url = fal.generate(
                prompt=DEFAULT_CLOSEUP_PROMPT,
                image_urls=image_inputs,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                model=blend_model,
            )
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="closeup_photo_",
                suffix=".jpg",
                context=f"Download close-up photo from {image_url}",
            )
            filename = f"closeup_{record_id}.jpg"
            airtable.upload_attachment(record_id, CLOSEUP_FIELD, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_COMPLETE})])
            print(
                f"[OK] Attached close-up image to '{CLOSEUP_FIELD}' and updated "
                f"{STATUS_FIELD} to '{STATUS_COMPLETE}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            err_msg = str(error).encode("ascii", errors="replace").decode("ascii")
            print(f"[ERROR] Failed generating close-up photo for record {record_id}: {err_msg}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Nano Banana Pro close-up generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


def finalize_completed_records(airtable: ScrapeAirtableClient) -> None:
    """Ensure any record with 'Closeup Photo' attached is set to Status 'Complete'."""
    records = airtable.list_records([CLOSEUP_FIELD, STATUS_FIELD])
    to_complete = [
        (record["id"], {STATUS_FIELD: STATUS_COMPLETE})
        for record in records
        if record.get("fields", {}).get(CLOSEUP_FIELD)
        and str(record.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold() != STATUS_COMPLETE.casefold()
    ]
    if to_complete:
        airtable.update_records(to_complete)
        print(f"[OK] Automatically updated Status to '{STATUS_COMPLETE}' for {len(to_complete)} completed record(s).")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Generate Krea AI room interior photos, Fal AI Claude Sonnet 5 prompts, "
            "Nano Banana Pro blending (4:5 1k), local PIL logo stamping, and moodboard conversions "
            "for Moodboard #1 Feed (tbl9u5vjgx8kuE44R)."
        )
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N records",
    )
    parser.add_argument(
        "--table-id",
        default=DEFAULT_TABLE_ID,
        help=f"Airtable destination table ID (default: {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--moodboard-id",
        default=DEFAULT_MOODBOARD_ID,
        help=f"Krea Moodboard ID (default: {DEFAULT_MOODBOARD_ID})",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help=f"Prompt for Krea interior photo generation",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=INTERIOR_ASPECT_RATIO,
        help=f"Aspect ratio for Krea interior photo generation (default: {INTERIOR_ASPECT_RATIO})",
    )
    parser.add_argument(
        "--vision-model",
        default=FAL_VISION_MODEL,
        help=f"Fal AI vision model for prompt analysis (default: {FAL_VISION_MODEL})",
    )
    parser.add_argument(
        "--blend-model",
        default=FAL_NANO_MODEL,
        help=f"Fal AI Nano Banana Pro model code (default: {FAL_NANO_MODEL})",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    base = load_settings()
    settings = load_scrape_settings(
        category_code=DEFAULT_CATEGORY,
        style_code=DEFAULT_STYLE,
        table_id_override=args.table_id,
        settings=base,
    )

    base.require({"krea", "fal"})
    krea = KreaClient(base.krea_token, base.krea_base_url)
    fal = FalClient(base.fal_key)
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        settings.airtable_table_id,
    )

    print("=" * 64)
    print("Moodboard #1 Feed AI Generation & Local Overlay Pipeline")
    print(f"Airtable Destination: {settings.airtable_base_id} / {settings.airtable_table_id}")
    print(f"Krea Moodboard ID: {args.moodboard_id}")
    print(f"Claude Vision Model: {args.vision_model}")
    print(f"Fal Nano Model: {args.blend_model} (4:5, 1k)")
    print(f"Local PIL Logo Overlay: W={HOMECARTEL_LOGO_BOX.width}, H={HOMECARTEL_LOGO_BOX.height} @ X={HOMECARTEL_LOGO_BOX.x}, Y={HOMECARTEL_LOGO_BOX.y}")
    print("=" * 64)

    overall_success = True

    # Step 1: Krea Interior Generation (Standby -> Interior Generated)
    print("\n[PHASE 1/6] Krea AI Interior Generation...")
    if not generate_moodboard_v1_interiors(
        krea,
        airtable,
        moodboard_id=args.moodboard_id,
        prompt=args.prompt,
        interior_field=INTERIOR_FIELD,
        aspect_ratio=args.aspect_ratio,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 2: Claude Sonnet 5 Prompt Generation (Interior Generated -> Generating Prompt for Blending)
    print("\n[PHASE 2/6] Fal AI Claude Sonnet 5 Blending Prompt Generation...")
    if not generate_moodboard_v1_prompts(
        fal,
        airtable,
        prompt_model=args.vision_model,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 3: Nano Banana Pro Blending (Generating Prompt for Blending -> Blended Image Generated)
    print("\n[PHASE 3/6] Fal AI Nano Banana Pro Image Blending (4:5, 1k)...")
    if not generate_moodboard_v1_blends(
        fal,
        airtable,
        blend_model=args.blend_model,
        aspect_ratio=NANO_ASPECT_RATIO,
        resolution=NANO_RESOLUTION,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 4: Local PIL Logo Overlay (Blended Image Generated -> Added Watermark Layout)
    print("\n[PHASE 4/6] Local PIL Logo Overlay (Zero API)...")
    if not generate_moodboard_v1_watermarks(
        airtable,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 5: Nano Banana Pro Material Moodboard Conversion (Added Watermark Layout -> Moodboard Converted)
    print("\n[PHASE 5/6] Fal AI Nano Banana Pro Material Moodboard Conversion (4:5, 1k)...")
    if not generate_moodboard_v1_converted(
        fal,
        airtable,
        blend_model=args.blend_model,
        aspect_ratio=NANO_ASPECT_RATIO,
        resolution=NANO_RESOLUTION,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 6: Nano Banana Pro Close-up Photo Generation (Moodboard Converted -> Complete)
    print("\n[PHASE 6/6] Fal AI Nano Banana Pro Close-up Photo Generation (4:5, 1k)...")
    if not generate_moodboard_v1_closeups(
        fal,
        airtable,
        blend_model=args.blend_model,
        aspect_ratio=NANO_ASPECT_RATIO,
        resolution=NANO_RESOLUTION,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Automatically set Status to 'Complete' for all records that have completed the final phase
    finalize_completed_records(airtable)

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
