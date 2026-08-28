"""Before & After Reel AI Generation & Blending Pipeline.

Runs the complete 5-Phase AI pipeline for Before & After Reel on Airtable (tbl2VoWOt7sSut4E2):
1. Krea AI Interior Photo Generation (9:16 Ratio) -> 'Interior Generated Photo' (Before)
2. Fal AI Claude Sonnet 5 Vision Analysis & Prompt Generation -> 'Blending Prompt'
3. Fal AI Nano Banana Pro Image-to-Image Blending (9:16 Ratio) -> 'Blended Image' / 'Day Image' (After)
4. Fal AI Multiple Angle Generation (9:16 Ratio, 4 Angles) -> 'Multiple Angle Blended Image'
5. Slideshow Reel Video Generation (9:16 MP4 Video with Claude Sonnet 5 Typography Title) -> 'Slide Show Before and After Reel'
   - Automatically compiles & exports the final reel video to '01_FINAL_REEL_VIDEO/' and source assets in Google Drive / local output

Usage::

    python generate_before_after_reel_pipeline.py
    python generate_before_after_reel_pipeline.py --target floor_lamps --max-items 1
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image
import requests

from content_automation.audio import analyze_music_for_cut_grid, add_onbeat_music
from content_automation.config import REEL_TABLES, load_settings, resolve_reel_table
from content_automation.errors import AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.models import LocalImage
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    moodboard_id_for_category,
)

DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_DAY_AND_NIGHT_REEL", "").strip()
    or "tbl2VoWOt7sSut4E2"
)
DEFAULT_MOODBOARD_ID = (
    os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
    or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
)
DEFAULT_PROMPT = (
    "Modern room interior, curvilinear modern furniture, warm neutral palette, "
    "tactile boucle textures, organic minimalist architecture, soft ambient natural daylight, "
    "NO existing lamps, NO secondary floor lamps, NO table lamps, NO pre-existing light fixtures, "
    "clean empty floor space ready for product integration, photorealistic 8k"
)
DEFAULT_CATEGORY = "floor_lamps"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "Processing Interior Generated Photo"
STATUS_GENERATING_PROMPT = "Processing Blending Prompt"
STATUS_BLENDED_IMAGE = "Processing Day Image"
STATUS_MULTIPLE_ANGLE = "Multiple Angle Blended Image Generating"
STATUS_GPT_IMAGE_2 = "Multiple Angle GPT Image 2 Regenerating"
STATUS_GPT_IMAGE_2_COMPLETE = "Multiple Angle GPT Image 2 Complete"
STATUS_SLIDESHOW_GENERATED = "Slide Show Before and After Reel Generating"
STATUS_COMPLETE = "Complete"

INTERIOR_FIELD = "Interior Generated Photo"
INTERIOR_FIELD_FALLBACK = "Interior Generated"
INTERIOR_FIELDS = [INTERIOR_FIELD, INTERIOR_FIELD_FALLBACK]
INTERIOR_ASPECT_RATIO = "9:16"

PROMPT_FIELD = "Blending Prompt"
PROMPT_FIELD_FALLBACK = "Prompt for Blending"
PROMPT_FIELDS = [PROMPT_FIELD, PROMPT_FIELD_FALLBACK]

BLENDED_IMAGE_FIELD = "Blended Image"
BLENDED_IMAGE_FIELD_FALLBACK = "Day Image"
BLENDED_IMAGE_FIELDS = [BLENDED_IMAGE_FIELD, BLENDED_IMAGE_FIELD_FALLBACK, "Moodboard V1 Blended"]

MULTIPLE_ANGLE_FIELD = "Multiple Angle Blended Image"
MULTIPLE_ANGLE_FIELDS = [MULTIPLE_ANGLE_FIELD]
REGENERATE_MULTIPLE_ANGLE_FIELD = "Regenerate Multiple Angle Blended Image"
REGENERATE_MULTIPLE_ANGLE_FIELDS = [
    REGENERATE_MULTIPLE_ANGLE_FIELD,
    "Regenerated Multiple Angle Blended Image",
    "Regenerate Multiple Angle",
    "Regenerated Multiple Angle",
]
FAL_MULTIPLE_ANGLE_MODEL = "fal-ai/qwen-image-edit-2511-multiple-angles"
GPT_IMAGE_2_MODEL = os.getenv("GPT_IMAGE_2_MODEL", "").strip() or "gpt-image-2"

SLIDESHOW_FIELD = "Slide Show Before and After Reel"
SLIDESHOW_FIELD_FALLBACK = "Slide Show Before & After Reel"
SLIDESHOW_FIELDS = [SLIDESHOW_FIELD, SLIDESHOW_FIELD_FALLBACK, "Slideshow Before and After Reel"]

THUMBNAIL_TEXT_FIELD = "Thumbnail with Generated Text"
THUMBNAIL_TEXT_FIELDS = [THUMBNAIL_TEXT_FIELD, "Thumbnail with Text", "Thumbnail Text"]

OUTRO_FIELD = "Outro"
OUTRO_FIELDS = [OUTRO_FIELD, "Outro Photo", "Outro Image"]

FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_BLENDING_MODEL = os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"

AUDIT_LOG_DIR = Path("output") / "logs"
AUDIT_LOG_CLAUDE_SONNET = AUDIT_LOG_DIR / "before_after_reel_claude_sonnet_logs.json"
AUDIT_LOG_NANO_BANANA = AUDIT_LOG_DIR / "before_after_reel_nano_banana_logs.json"
AUDIT_LOG_FAL_AI = AUDIT_LOG_DIR / "before_after_reel_fal_ai_logs.json"
AUDIT_LOG_GPT_IMAGE_2 = AUDIT_LOG_DIR / "before_after_reel_gpt_image_2_logs.json"

GDRIVE_REELS_DIR = Path("G:/My Drive/Before & After Reels")
GDRIVE_REELS_DIR_ALT = Path("G:/My Drive/Before and After Reels")
LOCAL_REELS_DIR = Path("output/content/before_and_after_reel")


def append_audit_log(log_entry: dict[str, Any], log_path: Path) -> None:
    """Append an API call audit record to the specified JSON log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            content = log_path.read_text(encoding="utf-8").strip()
            if content:
                logs = json.loads(content)
                if not isinstance(logs, list):
                    logs = [logs]
        except Exception:
            logs = []
    logs.append(log_entry)
    log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[AUDIT LOG] Appended log entry to {log_path}")


def sanitize_folder_name(name: str) -> str:
    """Sanitize string for Windows directory/file naming."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", str(name or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .")


def format_reel_folder_name(item_name: str = "", sku: str = "", record_id: str = "") -> str:
    """Generate clean folder name for Before & After Reel row."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    clean_name = sanitize_folder_name(item_name) if item_name else (sanitize_folder_name(sku) if sku else "Before_After_Reel")
    sku_tag = f" - {sanitize_folder_name(sku)}" if (sku and sku.lower() not in clean_name.lower()) else ""
    rec_tag = f" ({record_id})" if record_id else ""
    return f"{date_str} - {clean_name}{sku_tag}{rec_tag}"


def resolve_reel_output_dir(
    record_id: str,
    item_name: str = "",
    sku: str = "",
    base_dir_override: str | Path | None = None,
) -> Path:
    """Get or create organized output directory for a reel in output/content/before_and_after_reel or Google Drive."""
    folder_name = format_reel_folder_name(item_name, sku, record_id)

    if base_dir_override:
        target_dir = Path(base_dir_override) / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    target_dir = LOCAL_REELS_DIR / folder_name
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir
    except Exception as err:
        print(f"  [WARN] Failed creating directory '{target_dir}': {err}")
        LOCAL_REELS_DIR.mkdir(parents=True, exist_ok=True)
        return LOCAL_REELS_DIR


def export_reel_artifacts(
    record_id: str,
    item_name: str,
    sku: str,
    video_path: Path,
    source_assets: list[tuple[Path | str, str]],
    *,
    prompts: dict[str, str] | None = None,
    category: str = "Lighting",
    room: str = "Living room",
    duration_str: str = "0:14",
    cost_str: str = "$0.05",
    base_dir_override: str | Path | None = None,
) -> Path | None:
    """Export final reel video, source assets, prompts, and summary_metadata.json to output/content/before_and_after_reel and Google Drive."""
    try:
        reel_dir = resolve_reel_output_dir(record_id, item_name, sku, base_dir_override=base_dir_override)

        # 1. 01_FINAL_REEL_VIDEO folder
        video_dir = reel_dir / "01_FINAL_REEL_VIDEO"
        video_dir.mkdir(parents=True, exist_ok=True)
        final_video_dest = video_dir / f"slideshow_{record_id}.mp4"
        if Path(video_path).is_file():
            shutil.copy2(video_path, final_video_dest)
            print(f"[REEL EXPORT] Copied final reel video to: {final_video_dest}")

        # 2. 02_SOURCE_ASSETS folder
        assets_dir = reel_dir / "02_SOURCE_ASSETS"
        assets_dir.mkdir(parents=True, exist_ok=True)
        for src_path, dest_name in source_assets:
            src = Path(src_path)
            if src.is_file():
                shutil.copy2(src, assets_dir / dest_name)

        # 3. prompts_used.txt
        prompts = prompts or {}
        blending_p = prompts.get("blending_prompt", "")
        title_p = prompts.get("title", "")
        jazz_p = prompts.get("jazz_prompt", "")
        prompts_text = (
            f"BEFORE & AFTER REEL: {item_name} ({record_id})\n"
            f"{'=' * 60}\n"
            f"Item Name : {item_name}\n"
            f"SKU       : {sku}\n"
            f"Record ID : {record_id}\n"
            f"Generated : {datetime.now(timezone.utc).isoformat()}\n\n"
            f"--- CLAUDE SONNET 5 BLENDING PROMPT ---\n"
            f"{blending_p}\n\n"
            f"--- REEL TITLE (POPPINS TYPOGRAPHY) ---\n"
            f"{title_p}\n\n"
            f"--- JAZZ MUSIC PROMPT ---\n"
            f"{jazz_p}\n"
        )
        (reel_dir / "prompts_used.txt").write_text(prompts_text, encoding="utf-8")

        # 4. summary_metadata.json
        meta_data = {
            "record_id": record_id,
            "product_name": item_name,
            "sku": sku,
            "category": category,
            "room": room,
            "status": "Done",
            "duration": duration_str,
            "cost": cost_str,
            "timestamp": datetime.now().strftime("%b %d, %Y"),
            "video_filename": f"slideshow_{record_id}.mp4",
            "video_relative_path": f"01_FINAL_REEL_VIDEO/slideshow_{record_id}.mp4",
        }
        (reel_dir / "summary_metadata.json").write_text(
            json.dumps(meta_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"[REEL EXPORT] Compiled full reel folder at: {reel_dir}")

        # Also mirror to Google Drive if mounted
        if GDRIVE_REELS_DIR.exists() and not base_dir_override:
            try:
                gdrive_dest = GDRIVE_REELS_DIR / reel_dir.name
                shutil.copytree(reel_dir, gdrive_dest, dirs_exist_ok=True)
                print(f"[GOOGLE DRIVE SYNC] Synced reel folder to: {gdrive_dest}")
            except Exception as gdrive_err:
                print(f"  [WARN] Could not sync to Google Drive: {gdrive_err}")

        return reel_dir
    except Exception as err:
        print(f"[WARN] Failed exporting reel artifacts: {err}")
        return None


def get_first_field_value(fields: dict[str, Any], field_names: list[str]) -> Any:
    """Return the first populated value among candidate field names."""
    for name in field_names:
        if name in fields and fields[name]:
            return fields[name]
    return None


def get_first_field_name(fields: dict[str, Any], field_names: list[str]) -> str | None:
    """Return the first matching field name string that exists in fields dictionary."""
    for name in field_names:
        if name in fields:
            return name
    return None


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


def extract_all_attachment_urls(attachments: Any) -> list[str]:
    """Extract all accessible HTTP URLs from an Airtable attachment field list."""
    if not attachments:
        return []
    urls = []
    if isinstance(attachments, list):
        for att in attachments:
            if isinstance(att, dict) and att.get("url"):
                urls.append(str(att["url"]).strip())
            elif isinstance(att, str) and att.startswith("http"):
                urls.append(att.strip())
    elif isinstance(attachments, dict) and attachments.get("url"):
        urls.append(str(attachments["url"]).strip())
    elif isinstance(attachments, str) and attachments.startswith("http"):
        urls.append(attachments.strip())
    return [u for u in urls if u]


def resolve_table_field(
    airtable: ScrapeAirtableClient,
    candidate_names: list[str],
    default_fallback: str | None = None,
) -> str:
    """Find the first matching candidate field name that actually exists in this Airtable table's schema."""
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
    """Find the matching singleSelect choice for Status in this Airtable table's schema."""
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


def generate_krea_interiors_pipeline(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    moodboard_id: str = DEFAULT_MOODBOARD_ID,
    prompt: str = DEFAULT_PROMPT,
    aspect_ratio: str = INTERIOR_ASPECT_RATIO,
    interior_field: str = INTERIOR_FIELD,
    limit_records: int | None = None,
) -> bool:
    """Generate Krea AI room interior photo into 'Interior Generated Photo' (Phase 1: Before Image)."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable to populate interior photos.")
        return True

    unpopulated = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("complete", "done"):
            continue
        if get_first_field_value(fields, INTERIOR_FIELDS):
            continue
        unpopulated.append(record)

    if not unpopulated:
        print("[OK] No records requiring interior photo generation.")
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
            target_field = resolve_table_field(airtable, INTERIOR_FIELDS, interior_field)
            target_status = resolve_status_choice(airtable, [STATUS_INTERIOR_GENERATED, "Interior Generated", "Processing Interior Generated Photo"])
            airtable.upload_attachment(record_id, target_field, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
            print(
                f"[OK] Attached Krea image to '{target_field}' and updated "
                f"{STATUS_FIELD} to '{target_status}' on record {record_id}"
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

    print(
        f"[INFO] Krea interior generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


def generate_claude_blending_prompts(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    vision_model: str = FAL_VISION_MODEL,
    prompt_field: str = PROMPT_FIELD,
    placement_rule: str = "",
    limit_records: int | None = None,
) -> bool:
    """Generate detailed blending prompt using Fal AI Claude Sonnet 5 into 'Blending Prompt' (Phase 2)."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable to generate prompts.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("complete", "done"):
            continue
        interior_attachments = get_first_field_value(fields, INTERIOR_FIELDS)
        prompt_val = get_first_field_value(fields, PROMPT_FIELDS)
        if not interior_attachments:
            continue
        if prompt_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Claude Sonnet 5 prompt generation (interior missing or blending prompt already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{prompt_field}' for {len(eligible)} record(s) "
        f"using Fal AI Claude Sonnet 5 ({vision_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Modern Lighting Fixture").strip()
        item_label = f"{record_id} ({item_name})"

        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELDS))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))

        if not interior_url or not furniture_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing photos & generating prompt for "
            f"record {record_id} ({item_label}) with Fal AI Claude Sonnet 5..."
        )

        placement_addon = f"\n6. SPECIFIC FIXTURE PLACEMENT RULE: {placement_rule}" if placement_rule else ""

        instruction = (
            f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo ('Interior Generated Photo') "
            f"and Image 2 as the product photo for '{item_name}' ('Furniture Item').\n"
            f"Generate a detailed, highly specific image-blending prompt for Nano Banana Pro (9:16 vertical ratio). "
            f"The prompt must describe naturally integrating and mounting/placing the {item_name} from Image 2 into the room interior from Image 1.\n"
            f"CRITICAL ISOLATION & MOUNTING RULES:\n"
            f"1. The {item_name} shown in Image 2 MUST BE THE ONLY MAIN LIGHTING FIXTURE/FURNITURE ITEM of its kind in the entire final blended scene.\n"
            f"2. If Image 1 contains ANY pre-existing competing lighting fixtures or lamps, explicitly instruct to remove and replace them with the exact {item_name} from Image 2.\n"
            f"3. Strictly exclude unnecessary, competing clutter or duplicate items.\n"
            f"4. Ensure natural placement/hanging height, realistic canopy/base mounting, authentic materials, warm ambient illumination (3000K), soft contact shadows on surrounding walls/floors, and photorealistic 8k architectural styling.\n"
            f"5. Strictly maintain the exact room composition, wall color, architectural textures, and layout from Image 1.{placement_addon}\n\n"
            f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
        )

        try:
            image_inputs = [interior_url, furniture_url]
            raw_prompt = fal.generate_vision_prompt(
                image_urls=image_inputs,
                prompt=instruction,
                model=vision_model,
            )
            blending_prompt = raw_prompt.strip().strip('"').strip("'")

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 2: Fal AI Claude Sonnet 5 Blending Prompt Generation",
                "api_provider": "fal.ai",
                "api_model": vision_model,
                "input_interior_url": interior_url,
                "input_furniture_url": furniture_url,
                "generated_blending_prompt": blending_prompt,
            }, AUDIT_LOG_CLAUDE_SONNET)

            target_prompt_field = resolve_table_field(airtable, PROMPT_FIELDS, prompt_field)
            target_status = resolve_status_choice(airtable, [STATUS_GENERATING_PROMPT, "Generating Prompt for Blending", "Processing Blending Prompt"])
            airtable.update_records([(record_id, {target_prompt_field: blending_prompt, STATUS_FIELD: target_status})])
            print(f"[OK] Saved Claude Sonnet 5 prompt to '{target_prompt_field}' and updated {STATUS_FIELD} to '{target_status}' on record {record_id}")
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating prompt for record {record_id}: {error}")
            failed += 1

    print(
        f"[INFO] Claude Sonnet 5 prompt generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# Alias for backward compatibility
generate_qwen_blending_prompts = generate_claude_blending_prompts


def generate_nano_banana_pro_blends(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = FAL_BLENDING_MODEL,
    blended_field: str = BLENDED_IMAGE_FIELD,
    limit_records: int | None = None,
) -> bool:
    """Generate image-to-image blended photo using Fal AI Nano Banana Pro into 'Blended Image' (Phase 3: After Image)."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable for image blending.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("complete", "done"):
            continue
        prompt_text = str(get_first_field_value(fields, PROMPT_FIELDS) or "").strip()
        blended_attachments = get_first_field_value(fields, BLENDED_IMAGE_FIELDS)
        if not prompt_text:
            continue
        if blended_attachments:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Nano Banana Pro blending (prompt missing or Blended Image already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{blended_field}' for {len(eligible)} record(s) "
        f"using Fal AI Nano Banana Pro ({blend_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id
        prompt_text = str(get_first_field_value(fields, PROMPT_FIELDS) or "").strip()

        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELDS))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))
        image_inputs = [url for url in (interior_url, furniture_url) if url]

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating blended photo for "
            f"record {record_id} ({item_label}) with Fal AI Nano Banana Pro..."
        )

        downloaded = None
        try:
            image_url = fal.generate(
                prompt=prompt_text,
                image_urls=image_inputs,
                aspect_ratio="9:16",
                resolution="1K",
                model=blend_model,
            )
            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 3: Fal AI Nano Banana Pro Day Image Blending",
                "api_provider": "fal.ai",
                "api_model": blend_model,
                "input_prompt": prompt_text,
                "input_image_urls": image_inputs,
                "output_image_url": image_url,
            }, AUDIT_LOG_NANO_BANANA)
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="blended_image_",
                suffix=".jpg",
                context=f"Download blended image from {image_url}",
            )
            filename = f"blended_{record_id}.jpg"
            target_blended_field = resolve_table_field(airtable, BLENDED_IMAGE_FIELDS, blended_field)
            target_status = resolve_status_choice(airtable, [STATUS_BLENDED_IMAGE, "Blended Image Generated", "Processing Day Image"])
            airtable.upload_attachment(record_id, target_blended_field, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
            print(
                f"[OK] Attached blended image to '{target_blended_field}' and updated "
                f"{STATUS_FIELD} to '{target_status}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed blending image for record {record_id}: {error}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Fal AI Nano Banana Pro blending complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


# Alias for backward compatibility
generate_qwen_image_blends = generate_nano_banana_pro_blends


def generate_multiple_angles_pipeline(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    model: str = FAL_MULTIPLE_ANGLE_MODEL,
    limit_records: int | None = None,
) -> bool:
    """Generate 4 different viewing angles from 'Blended Image' using Fal AI into 'Multiple Angle Blended Image' (Phase 4)."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable for multiple angle generation.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("complete", "done"):
            continue
        blended_attachments = get_first_field_value(fields, BLENDED_IMAGE_FIELDS)
        already_has_angles = fields.get(MULTIPLE_ANGLE_FIELD)
        if not blended_attachments:
            continue
        if already_has_angles:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Fal AI multiple angle generation ('Blended Image' missing or '{MULTIPLE_ANGLE_FIELD}' already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{MULTIPLE_ANGLE_FIELD}' (4 angles, 9:16 ratio) for {len(eligible)} record(s) "
        f"using Fal AI ({model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        blended_url = extract_attachment_url(get_first_field_value(fields, BLENDED_IMAGE_FIELDS))
        prompt_text = str(get_first_field_value(fields, PROMPT_FIELDS) or "").strip()

        if not blended_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible Blended Image URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating 4 viewing angles from Blended Image for "
            f"record {record_id} ({item_label}) with Fal AI ({model})..."
        )

        airtable.update_records([(record_id, {STATUS_FIELD: STATUS_MULTIPLE_ANGLE})])
        print(f"[INFO] Updated {STATUS_FIELD} to '{STATUS_MULTIPLE_ANGLE}' on record {record_id}")

        ANGLE_PRESETS = [
            {"name": "Front Eye-Level View", "horizontal_angle": 0, "vertical_angle": 5, "zoom": 4.5},
            {"name": "Right Perspective View", "horizontal_angle": 40, "vertical_angle": 15, "zoom": 5.0},
            {"name": "Left Perspective View", "horizontal_angle": 320, "vertical_angle": 15, "zoom": 5.0},
            {"name": "Elevated Detail View", "horizontal_angle": 15, "vertical_angle": 25, "zoom": 6.5},
        ]

        downloaded_list = []
        target_angles_field = resolve_table_field(airtable, MULTIPLE_ANGLE_FIELDS, MULTIPLE_ANGLE_FIELD)
        multi_angle_negative_prompt = (
            "distorted furniture, morphed lighting fixture, altered product shape, changing item design, "
            "different light fixture, deformed canopy, bent metal, warped proportions, changing colors, "
            "altering room structure, changing wall texture, changing furniture layout, duplicate fixtures, "
            "floating objects, disjointed parts, vanishing details, extra lamps, new furniture, changing floor, "
            "perspective distortion, fish-eye distortion, stretched geometry, blurry, noisy, low resolution, "
            "artifacts, oversaturated, unrealistic shadows, bad composition, watermark, text, signature"
        )
        try:
            angle_urls = []
            for preset in ANGLE_PRESETS:
                h_ang = preset["horizontal_angle"]
                v_ang = preset["vertical_angle"]
                zm = preset["zoom"]
                custom_angle_prompt = (
                    f"<sks> Precise {preset['name']} camera rotation of the exact same room interior and {item_label}. "
                    "Strictly maintain the identical product design, proportions, finishes, and exact room architecture from the reference photo. "
                    f"Only rotate the camera viewpoint (azimuth: {h_ang}°, elevation: {v_ang}°, distance: {zm}). "
                    "Zero changes to lighting shape, furniture placement, or room layout. Photorealistic architectural photography."
                )
                try:
                    urls = fal.generate_multiple_angles(
                        blended_url,
                        prompt=custom_angle_prompt,
                        horizontal_angle=h_ang,
                        vertical_angle=v_ang,
                        zoom=zm,
                        lora_scale=1.0,
                        guidance_scale=6.5,
                        num_inference_steps=35,
                        acceleration="regular",
                        negative_prompt=multi_angle_negative_prompt,
                        image_size="portrait_16_9",
                        num_images=1,
                        model=model,
                    )
                    if urls:
                        angle_urls.append(urls[0])
                except Exception as p_err:
                    print(f"[WARN] Failed generating {preset['name']}: {p_err}")

            if not angle_urls or len(angle_urls) < 4:
                # Fallback to batch call if any individual angle generation was missing
                try:
                    batch_urls = fal.generate_multiple_angles(
                        blended_url,
                        prompt=(
                            f"<sks> 4 different perspective camera viewing angles of the exact same room interior and {item_label}. "
                            "Maintain identical fixture structure, room layout, and decor with zero distortion."
                        ),
                        lora_scale=1.0,
                        guidance_scale=6.5,
                        num_inference_steps=35,
                        acceleration="regular",
                        negative_prompt=multi_angle_negative_prompt,
                        image_size="portrait_16_9",
                        num_images=4,
                        model=model,
                    )
                    for b_url in batch_urls:
                        if len(angle_urls) >= 4:
                            break
                        if b_url not in angle_urls:
                            angle_urls.append(b_url)
                except Exception as b_err:
                    print(f"[WARN] Fallback batch angle generation notice: {b_err}")

            print(f"[OK] Fal AI returned {len(angle_urls)} image angle URL(s)")

            if not angle_urls:
                raise ProviderError("Fal AI multiple angle generation returned 0 image URLs.")

            for idx, angle_url in enumerate(angle_urls[:4], start=1):
                try:
                    response = requests.get(angle_url, stream=True)
                    downloaded = download_to_temp_file(
                        response,
                        prefix=f"angle_{idx}_",
                        suffix=".jpg",
                        context=f"Download angle image from {angle_url}",
                    )
                    downloaded_list.append(downloaded)
                    filename = f"angle_{idx}_{record_id}.jpg"
                    airtable.upload_attachment(record_id, target_angles_field, downloaded, filename)
                except Exception as upload_err:
                    print(f"[WARN] Failed uploading angle {idx} for record {record_id}: {upload_err}")

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 4: Fal AI Multiple Angle Generation",
                "api_model": model,
                "api_key_env_var": "FAL_KEY",
                "input_blended_url": blended_url,
                "num_angles_generated": len(angle_urls),
                "output_angle_urls": angle_urls[:4],
            }, AUDIT_LOG_FAL_AI)
            target_status = resolve_status_choice(airtable, [STATUS_MULTIPLE_ANGLE, "Multiple Angle Blended Image Generating", "Complete"])
            airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
            print(
                f"[OK] Attached {len(downloaded_list)} angle images to '{target_angles_field}' and updated "
                f"{STATUS_FIELD} on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed multiple angle generation for record {record_id}: {error}")
            failed += 1
        finally:
            for downloaded in downloaded_list:
                try:
                    downloaded.cleanup()
                except Exception:
                    pass

    print(
        f"[INFO] Multiple angle generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


def regenerate_multiple_angles_with_gpt_image_pipeline(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    model: str = GPT_IMAGE_2_MODEL,
    aspect_ratio: str = "9:16",
    limit_records: int | None = None,
) -> bool:
    """Regenerate and enhance the 4 angle photos in 'Multiple Angle Blended Image' strictly using GPT Image 2 API via Fal AI (Phase 5)."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable for GPT Image 2 regeneration.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("complete", "done", STATUS_GPT_IMAGE_2_COMPLETE.casefold(), STATUS_SLIDESHOW_GENERATED.casefold()):
            continue
        if get_first_field_value(fields, REGENERATE_MULTIPLE_ANGLE_FIELDS):
            continue
        angle_attachments = fields.get(MULTIPLE_ANGLE_FIELD)
        if not angle_attachments:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring GPT Image 2 angle regeneration ('{MULTIPLE_ANGLE_FIELD}' missing or already completed).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Regenerating '{MULTIPLE_ANGLE_FIELD}' (4 angles, {aspect_ratio} ratio) for {len(eligible)} record(s) "
        f"strictly using Fal AI GPT Image 2 API ({model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        angle_urls = extract_all_attachment_urls(fields.get(MULTIPLE_ANGLE_FIELD))
        prompt_text = str(get_first_field_value(fields, PROMPT_FIELDS) or "").strip()

        if not angle_urls:
            print(f"[SKIP] Record {record_id} ({item_label}) has no accessible angle attachment URLs.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Regenerating {len(angle_urls[:4])} viewing angles strictly with Fal AI GPT Image 2 for "
            f"record {record_id} ({item_label}) in {aspect_ratio}..."
        )

        try:
            target_status = resolve_status_choice(airtable, [STATUS_GPT_IMAGE_2, "Multiple Angle GPT Image 2 Regenerating", STATUS_MULTIPLE_ANGLE])
            airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
            print(f"[INFO] Updated {STATUS_FIELD} to '{target_status}' on record {record_id}")
        except Exception as status_err:
            print(f"[WARN] Could not update transient status for record {record_id}: {status_err}")

        downloaded_list = []
        target_regen_field = resolve_table_field(airtable, REGENERATE_MULTIPLE_ANGLE_FIELDS, REGENERATE_MULTIPLE_ANGLE_FIELD)
        try:
            regenerated_urls = []
            for idx, angle_url in enumerate(angle_urls[:4], start=1):
                regen_prompt = (
                    f"Regenerate me this image"
                ).strip()

                out_url = ""
                # Call GPT Image 2 via Fal AI API
                try:
                    out_url = fal.generate_gpt_image_2(
                        prompt=regen_prompt,
                        image_urls=[angle_url],
                        aspect_ratio=aspect_ratio,
                        model=model,
                    )
                    if out_url:
                        print(f"[OK] Fal AI GPT Image 2 ({model}) regenerated angle {idx} (9:16): {out_url}")
                except Exception as gpt_err:
                    print(f"[ERROR] Fal AI GPT Image 2 error for angle {idx}: {gpt_err}")

                if out_url:
                    regenerated_urls.append(out_url)

            if not regenerated_urls:
                raise AutomationError(f"Fal AI GPT Image 2 ({model}) failed to generate any regenerated angles for record {record_id}")

            # Download and upload 9:16 JPEG attachments to Airtable 'Regenerate Multiple Angle Blended Image'
            for idx, r_url in enumerate(regenerated_urls[:4], start=1):
                try:
                    resp = requests.get(r_url, stream=True)
                    downloaded = download_to_temp_file(
                        resp,
                        prefix=f"angle_{idx}_gpt2_",
                        suffix=".jpg",
                        context=f"Download regenerated angle {idx} from {r_url}",
                    )
                    downloaded_list.append(downloaded)
                    filename = f"angle_{idx}_{record_id}.jpg"
                    airtable.upload_attachment(record_id, target_regen_field, downloaded, filename)
                except Exception as up_err:
                    print(f"[WARN] Failed uploading regenerated angle {idx} for record {record_id}: {up_err}")

            append_audit_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "item_label": item_label,
                "phase": "Phase 5: GPT Image 2 Multiple Angle Regeneration",
                "api_model": model,
                "aspect_ratio": aspect_ratio,
                "target_field": target_regen_field,
                "input_angle_urls": angle_urls[:4],
                "output_regenerated_urls": regenerated_urls[:4],
            }, AUDIT_LOG_GPT_IMAGE_2)

            done_status = resolve_status_choice(airtable, [STATUS_GPT_IMAGE_2_COMPLETE, "Multiple Angle GPT Image 2 Complete", "Standby"])
            airtable.update_records([(record_id, {STATUS_FIELD: done_status})])
            print(
                f"[OK] Uploaded {len(downloaded_list)} regenerated 9:16 angle images to '{target_regen_field}' and updated "
                f"{STATUS_FIELD} to '{done_status}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed GPT Image 2 regeneration for record {record_id}: {error}")
            failed += 1
        finally:
            for downloaded in downloaded_list:
                try:
                    downloaded.cleanup()
                except Exception:
                    pass

    print(
        f"[INFO] GPT Image 2 multiple angle regeneration complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


def overlay_centered_poppins_text(
    pil_img: Image.Image,
    text: str,
    font_path: Path | str | None = None,
    font_size: int | None = None,
    text_color: str = "#FFFFFF",
    shadow_color: str = "#000000",
) -> Image.Image:
    """Overlay text centered on image using Poppins-Light font (not all caps, no shadow)."""
    import textwrap
    from PIL import ImageDraw, ImageFont

    if not text or not text.strip():
        return pil_img.copy()

    if font_path is None:
        base_fonts = Path(__file__).parent / "content_automation" / "fonts"
        candidates = [
            base_fonts / "Poppins-Light.ttf",
            base_fonts / "Poppins-Regular.ttf",
            Path("content_automation/fonts/Poppins-Light.ttf"),
            Path("content_automation/fonts/Poppins-Regular.ttf"),
            Path("Poppins-Light.ttf"),
        ]
        for c in candidates:
            if c.is_file():
                font_path = c
                break

    img = pil_img.copy().convert("RGB")
    width, height = img.size
    draw = ImageDraw.Draw(img)

    target_size = font_size or max(42, int(height * 0.042))
    try:
        font = ImageFont.truetype(str(font_path), target_size)
    except Exception:
        font = ImageFont.load_default()

    clean_text = text.strip()
    wrapped_lines = textwrap.wrap(clean_text, width=22) or [clean_text]

    line_bboxes = [draw.textbbox((0, 0), line, font=font) for line in wrapped_lines]
    line_widths = [b[2] - b[0] for b in line_bboxes]
    line_heights = [b[3] - b[1] for b in line_bboxes]

    total_height = sum(line_heights) + (len(wrapped_lines) - 1) * 14
    start_y = (height - total_height) // 2

    current_y = start_y
    for i, line in enumerate(wrapped_lines):
        line_w = line_widths[i]
        line_h = line_heights[i]
        x = (width - line_w) // 2

        draw.text((x, current_y), line, font=font, fill=text_color)
        current_y += line_h + 14

    return img


def build_before_after_slideshow_video(
    first_slide_image_path: Path | None = None,
    angle_image_paths: list[Path] | None = None,
    output_mp4_path: Path | None = None,
    *,
    interior_image_path: Path | None = None,
    outro_image_path: Path | None = None,
    audio_path: Path | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    first_slide_duration: float = 3.0,
    interior_duration: float = 3.0,
    angle_duration: float = 2.0,
    outro_duration: float = 3.0,
    fade_duration: float = 1.0,
    dim_factor: float = 0.65,
    title_text: str = "",
) -> Path:
    """Build a 9:16 vertical H.264 MP4 slideshow video reel with optional background audio.

    Slide 1 ('Thumbnail with Generated Text'): 3.0s duration, dimmed brightness with centered Poppins text overlay (Before).
    Slides 2-5 ('Multiple Angle Blended Image'): 2.0s duration each (After).
    Slide 6 ('Outro' if present): 3.0s duration, with a 1.0s Fade to Black transition before Outro.
    Audio: Synced background track merged using FFmpeg.
    """
    from PIL import ImageEnhance

    slide1_path = first_slide_image_path or interior_image_path
    if not slide1_path or not Path(slide1_path).is_file():
        raise AutomationError(f"Cannot build slideshow video: Slide 1 image missing ({slide1_path})")

    if output_mp4_path is None:
        raise AutomationError("output_mp4_path is required")

    angles = [p for p in (angle_image_paths or []) if Path(p).is_file()]
    has_outro = outro_image_path is not None and Path(outro_image_path).is_file()

    temp_raw = output_mp4_path.with_name(f"raw_{output_mp4_path.name}")
    temp_raw.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_raw), fourcc, fps, (width, height))

    # 1. Write Slide 1 (Thumbnail / Before Image)
    with Image.open(slide1_path) as pil_img:
        pil_img = pil_img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        # If raw interior was passed and title_text is requested, apply dimming and text
        if title_text and not first_slide_image_path:
            pil_img = ImageEnhance.Brightness(pil_img).enhance(dim_factor)
            pil_img = overlay_centered_poppins_text(pil_img, title_text)
        frame_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        s1_frames = int((first_slide_duration or interior_duration) * fps)
        for _ in range(s1_frames):
            writer.write(frame_bgr)

    # 2. Write Angle Slides (After Images)
    total_angles = len(angles)
    for idx, angle_path in enumerate(angles, start=1):
        with Image.open(angle_path) as pil_img:
            pil_img = pil_img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            frame_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            num_frames = int(angle_duration * fps)

            is_last_angle = has_outro and (idx == total_angles)
            if is_last_angle:
                fade_frames = int(fade_duration * fps)
                normal_frames = max(0, num_frames - fade_frames)
                for _ in range(normal_frames):
                    writer.write(frame_bgr)
                for i in range(fade_frames):
                    factor = 1.0 - (i / max(1, fade_frames))
                    faded = (frame_bgr.astype(np.float32) * factor).astype(np.uint8)
                    writer.write(faded)
            else:
                for _ in range(num_frames):
                    writer.write(frame_bgr)

    # 3. Write Outro slide (3.0s duration)
    if has_outro:
        with Image.open(outro_image_path) as outro_pil:
            outro_pil = outro_pil.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            outro_bgr = cv2.cvtColor(np.array(outro_pil), cv2.COLOR_RGB2BGR)

            outro_num_frames = int(outro_duration * fps)
            fade_in_frames = int(0.5 * fps)
            for i in range(fade_in_frames):
                factor = i / max(1, fade_in_frames)
                faded_in = (outro_bgr.astype(np.float32) * factor).astype(np.uint8)
                writer.write(faded_in)

            for _ in range(max(0, outro_num_frames - fade_in_frames)):
                writer.write(outro_bgr)

    writer.release()

    # 4. FFmpeg encoding (with optional audio merge)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if audio_path and Path(audio_path).is_file():
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(temp_raw),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "+faststart",
            str(output_mp4_path),
        ]
    else:
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(temp_raw),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_mp4_path),
        ]

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if temp_raw.exists():
        try:
            temp_raw.unlink(missing_ok=True)
        except Exception:
            pass

    if completed.returncode != 0:
        raise AutomationError(f"FFmpeg slideshow encoding failed: {completed.stderr}")
    return output_mp4_path


def generate_slideshow_reels_pipeline(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    vision_model: str = FAL_VISION_MODEL,
    slideshow_field: str = SLIDESHOW_FIELD,
    thumbnail_field: str = THUMBNAIL_TEXT_FIELD,
    outro_field: str = OUTRO_FIELD,
    limit_records: int | None = None,
) -> bool:
    """Generate 9:16 Slideshow Reel MP4 video with Claude Sonnet 5 typography title, thumbnail, and Google Drive compilation (Phase 5)."""
    records = airtable.list_records()
    if not records:
        print("[OK] No records found in Airtable for slideshow video reel generation.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        interior_attachments = get_first_field_value(fields, INTERIOR_FIELDS)
        angle_attachments = fields.get(MULTIPLE_ANGLE_FIELD)
        slideshow_attachments = get_first_field_value(fields, SLIDESHOW_FIELDS) or fields.get(slideshow_field)
        if status in ("complete", "done") or slideshow_attachments:
            continue
        if not interior_attachments or not angle_attachments:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring slideshow reel generation ('Interior Generated' / '{MULTIPLE_ANGLE_FIELD}' missing or '{slideshow_field}' already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{thumbnail_field}' & '{slideshow_field}' (9:16 Video Reel) for {len(eligible)} record(s)..."
    )

    used_titles: set[str] = set()
    if AUDIT_LOG_CLAUDE_SONNET.exists():
        try:
            log_content = AUDIT_LOG_CLAUDE_SONNET.read_text(encoding="utf-8").strip()
            if log_content:
                past_entries = json.loads(log_content)
                if isinstance(past_entries, list):
                    for entry in past_entries:
                        t = str(entry.get("generated_title_text") or "").strip()
                        if t:
                            used_titles.add(t)
        except Exception:
            pass

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_name_val = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Modern Lighting Fixture").strip()
        sku_val = str(fields.get(SKU_FIELD) or "").strip()
        item_label = f"{record_id} ({item_name_val})"

        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELDS))
        blended_url = extract_attachment_url(get_first_field_value(fields, BLENDED_IMAGE_FIELDS)) or interior_url
        outro_url = extract_attachment_url(get_first_field_value(fields, OUTRO_FIELDS))
        angle_attachments = (
            get_first_field_value(fields, REGENERATE_MULTIPLE_ANGLE_FIELDS)
            or fields.get(MULTIPLE_ANGLE_FIELD)
            or []
        )

        angle_urls = []
        if isinstance(angle_attachments, list):
            for att in angle_attachments:
                if isinstance(att, dict) and att.get("url"):
                    angle_urls.append(str(att["url"]).strip())
        elif isinstance(angle_attachments, dict) and angle_attachments.get("url"):
            angle_urls.append(str(angle_attachments["url"]).strip())

        if not interior_url or not angle_urls:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible Interior or Angle attachment URLs.")
            continue

        existing_thumb = get_first_field_value(fields, THUMBNAIL_TEXT_FIELDS)
        existing_thumb_url = extract_attachment_url(existing_thumb)
        has_existing_thumb = bool(existing_thumb_url)

        title_text = ""
        jazz_music_prompt = ""

        if has_existing_thumb:
            print(f"[INFO] Record {record_id} ({item_label}) already has 'Thumbnail with Generated Text' attached. Skipping Claude title generation.")
        else:
            print(
                f"[INFO] [{position}/{len(eligible)}] Analyzing Blended Image with Fal AI Claude Sonnet 5 for unique title & jazz music prompt..."
            )
            try:
                title_instruction = (
                    "You are an expert interior design branding specialist. Analyze this modern room interior photo. "
                    "Generate a short, elegant, aesthetic 1 to 5 word interior title for a luxury Instagram reel (e.g. 'Warm Minimalist Living', 'Curated Organic Loft', 'Sculptural Dining Ambiance'). "
                    "Do NOT use ALL CAPS. Use title case. "
                    f"Avoid using these previously used titles: {', '.join(sorted(used_titles)[:20]) if used_titles else 'None'}. "
                    "Return ONLY the 1-5 word title with no preamble, quotes, or punctuation."
                )
                raw_title = fal.generate_vision_prompt(
                    image_urls=[blended_url],
                    prompt=title_instruction,
                    model=vision_model,
                )
                title_text = raw_title.strip().strip('"').strip("'")
                if title_text:
                    used_titles.add(title_text)

                jazz_instruction = (
                    "You are an expert music curator and AI prompt engineer for high-end luxury interior design reels. "
                    "Create a vivid, atmospheric, single-paragraph text-to-audio music prompt for a modern upbeat jazz track. "
                    "Requirements: (1) Warm acoustic jazz instruments like Rhodes electric piano, walking upright bass, gentle saxophone, and crisp brushed drum kit. "
                    "(2) Steady rhythmic beat at 120 BPM in 4/4 time. "
                    "(3) Sophisticated, elegant atmosphere. "
                    "Return ONLY the prompt string with no quotes or preamble."
                )
                raw_jazz = fal.generate_vision_prompt(
                    image_urls=[blended_url],
                    prompt=jazz_instruction,
                    model=vision_model,
                )
                jazz_music_prompt = raw_jazz.strip().strip('"').strip("'")

                print(f"[OK] Claude title: '{title_text}' | Jazz music prompt: '{jazz_music_prompt}'")
                append_audit_log({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "record_id": record_id,
                    "item_label": item_label,
                    "phase": "Phase 5: Slideshow Reel - Fal AI Claude Sonnet 5 Title & Music Prompt",
                    "api_provider": "fal.ai",
                    "api_model": vision_model,
                    "input_blended_url": blended_url,
                    "generated_title_text": title_text,
                    "generated_jazz_music_prompt": jazz_music_prompt,
                }, AUDIT_LOG_CLAUDE_SONNET)
            except Exception as claude_err:
                print(f"[WARN] Claude prompt generation fallback: {claude_err}")
                title_text = title_text or "Modern Interior Style"
                jazz_music_prompt = jazz_music_prompt or "Smooth relaxing lounge jazz with warm piano and gentle brushed drums"

        try:
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_SLIDESHOW_GENERATED})])
            print(f"[INFO] Updated {STATUS_FIELD} to '{STATUS_SLIDESHOW_GENERATED}' on record {record_id}")
        except Exception as status_err:
            print(f"[WARN] Could not update transient status for record {record_id}: {status_err}")

        temp_dir = Path(tempfile.mkdtemp(prefix="slideshow_reel_"))
        interior_temp = None
        thumb_temp = None
        outro_temp = None
        angle_temps = []
        try:
            # Download interior photo (required for generating thumbnail or export)
            interior_resp = requests.get(interior_url, stream=True)
            interior_temp = download_to_temp_file(interior_resp, prefix="interior_", suffix=".jpg", context="Download interior slide")

            first_slide_path: Path | None = None

            # Download or generate Thumbnail with Generated Text (Slide 1)
            if has_existing_thumb and existing_thumb_url:
                try:
                    thumb_resp = requests.get(existing_thumb_url, stream=True)
                    thumb_temp = download_to_temp_file(thumb_resp, prefix="thumbnail_", suffix=".jpg", context="Download existing thumbnail slide")
                    first_slide_path = thumb_temp.path
                    print(f"[OK] Downloaded existing 'Thumbnail with Generated Text' for record {record_id} (Slide 1)")
                except Exception as t_err:
                    print(f"[WARN] Failed downloading existing thumbnail: {t_err}")

            if not first_slide_path:
                try:
                    from PIL import ImageEnhance
                    with Image.open(interior_temp.path) as interior_pil:
                        dimmed_pil = ImageEnhance.Brightness(interior_pil.convert("RGB")).enhance(0.65)
                        thumb_pil = overlay_centered_poppins_text(dimmed_pil, title_text) if title_text else dimmed_pil
                        thumb_saved_path = temp_dir / f"thumbnail_{record_id}.jpg"
                        thumb_pil.save(thumb_saved_path, quality=95)
                        first_slide_path = thumb_saved_path

                        target_thumb_field = resolve_table_field(airtable, THUMBNAIL_TEXT_FIELDS, thumbnail_field)
                        local_thumb = LocalImage(thumb_saved_path, f"thumbnail_{record_id}.jpg", "image/jpeg")
                        airtable.upload_attachment(record_id, target_thumb_field, local_thumb, f"thumbnail_{record_id}.jpg")
                        print(f"[OK] Attached centered Poppins text thumbnail to '{target_thumb_field}' on record {record_id}")
                except Exception as thumb_err:
                    print(f"[WARN] Failed generating thumbnail text image for record {record_id}: {thumb_err}")
                    first_slide_path = interior_temp.path

            if outro_url:
                try:
                    outro_resp = requests.get(outro_url, stream=True)
                    outro_temp = download_to_temp_file(outro_resp, prefix="outro_", suffix=".jpg", context="Download outro slide")
                    print(f"[OK] Downloaded Outro slide photo for record {record_id}")
                except Exception as outro_err:
                    print(f"[WARN] Outro photo download error for record {record_id}: {outro_err}")

            for idx, a_url in enumerate(angle_urls[:4], start=1):
                try:
                    a_resp = requests.get(a_url, stream=True)
                    a_file = download_to_temp_file(a_resp, prefix=f"angle_{idx}_", suffix=".jpg", context=f"Download angle {idx} slide")
                    angle_temps.append(a_file)
                except Exception as err:
                    print(f"[WARN] Failed downloading angle slide {idx}: {err}")

            # Synthesize background jazz track via Fal AI ElevenLabs Music API (fal-ai/elevenlabs/music)
            audio_temp = None
            if jazz_music_prompt:
                try:
                    print(f"[INFO] Synthesizing background jazz track via Fal AI ElevenLabs Music (fal-ai/elevenlabs/music)...")
                    audio_url = fal.generate_elevenlabs_music(
                        prompt=jazz_music_prompt,
                        duration=14,
                        model="fal-ai/elevenlabs/music",
                    )
                    if audio_url:
                        audio_resp = requests.get(audio_url, stream=True)
                        audio_temp = download_to_temp_file(
                            audio_resp,
                            prefix="elevenlabs_jazz_",
                            suffix=".mp3",
                            context=f"Download ElevenLabs music for record {record_id}",
                        )
                        print(f"[OK] Downloaded ElevenLabs background jazz audio for record {record_id}")
                except Exception as music_err:
                    print(f"[WARN] Fal AI ElevenLabs music generation notice: {music_err}")

            output_mp4_path = temp_dir / f"slideshow_reel_{record_id}.mp4"
            build_before_after_slideshow_video(
                first_slide_image_path=first_slide_path,
                angle_image_paths=[f.path for f in angle_temps],
                output_mp4_path=output_mp4_path,
                outro_image_path=outro_temp.path if outro_temp else None,
                audio_path=audio_temp.path if audio_temp else None,
                width=1080,
                height=1920,
                fps=30,
                first_slide_duration=3.0,
                angle_duration=2.0,
                outro_duration=3.0,
                fade_duration=1.0,
            )

            # Upload video to Airtable attachment field 'Slide Show Before and After Reel'
            local_video = LocalImage(output_mp4_path, f"slideshow_{record_id}.mp4", "video/mp4")
            target_field = resolve_table_field(airtable, SLIDESHOW_FIELDS, slideshow_field)
            target_status = resolve_status_choice(airtable, [STATUS_COMPLETE, "Complete"])
            airtable.upload_attachment(record_id, target_field, local_video, f"slideshow_{record_id}.mp4")
            airtable.update_records([(record_id, {STATUS_FIELD: target_status})])
            print(
                f"[OK] Attached slideshow MP4 video to '{target_field}' attachment field and updated "
                f"{STATUS_FIELD} to '{target_status}' on record {record_id}"
            )

            # Compile and export final video and source assets to Google Drive / local storage
            source_assets_to_export: list[tuple[Path | str, str]] = [
                (interior_temp.path, f"interior_{record_id}.jpg"),
            ]
            if first_slide_path and Path(first_slide_path).is_file():
                source_assets_to_export.append((first_slide_path, f"thumbnail_{record_id}.jpg"))
            for idx, a_file in enumerate(angle_temps, start=1):
                source_assets_to_export.append((a_file.path, f"angle_{idx}_{record_id}.jpg"))
            if outro_temp:
                source_assets_to_export.append((outro_temp.path, f"outro_{record_id}.jpg"))

            # Download blended image to include in source assets
            blended_temp = None
            if blended_url and blended_url.startswith("http"):
                try:
                    b_resp = requests.get(blended_url, stream=True)
                    blended_temp = download_to_temp_file(b_resp, prefix="blended_", suffix=".jpg", context="Download blended image for export")
                    source_assets_to_export.append((blended_temp.path, f"blended_{record_id}.jpg"))
                except Exception:
                    pass

            export_reel_artifacts(
                record_id=record_id,
                item_name=item_name_val,
                sku=sku_val,
                video_path=output_mp4_path,
                source_assets=source_assets_to_export,
                prompts={
                    "blending_prompt": str(get_first_field_value(fields, PROMPT_FIELDS) or ""),
                    "title": title_text,
                    "jazz_prompt": jazz_music_prompt,
                },
                category=str(fields.get("Category") or "Lighting"),
                duration_str="0:14",
                cost_str="$0.05",
            )

            if blended_temp:
                try:
                    blended_temp.cleanup()
                except Exception:
                    pass

            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating slideshow video reel for record {record_id}: {error}")
            failed += 1
        finally:
            if interior_temp:
                try:
                    interior_temp.cleanup()
                except Exception:
                    pass
            if thumb_temp:
                try:
                    thumb_temp.cleanup()
                except Exception:
                    pass
            if outro_temp:
                try:
                    outro_temp.cleanup()
                except Exception:
                    pass
            if audio_temp:
                try:
                    audio_temp.cleanup()
                except Exception:
                    pass
            for a_file in angle_temps:
                try:
                    a_file.cleanup()
                except Exception:
                    pass
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
    print(
        f"[INFO] Slideshow video reel pipeline complete: {succeeded} succeeded, "
        f"{failed} failed."
    )
    return failed == 0


def parse_args(argv=None):
    preset_keys = list(REEL_TABLES.keys())
    parser = argparse.ArgumentParser(
        description="Before & After Reel AI Pipeline (Krea AI -> Fal Claude Sonnet 5 -> Fal Nano Banana Pro Blended -> Fal Multiple Angles -> Slideshow Reel Video)"
    )
    parser.add_argument(
        "--target",
        "-t",
        default=None,
        help=f"Target table preset ({', '.join(preset_keys)}) or table ID",
    )
    parser.add_argument(
        "--category",
        "-c",
        default=None,
        help="Category code override",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Style code filter in Akeneo (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N records per phase",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Krea Moodboard ID override",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    base = load_settings()
    base.require({"airtable", "krea", "fal"})

    reel_config = resolve_reel_table(args.target, args.category)
    table_id = args.table_id or os.getenv(reel_config["env_table_key"], "").strip() or reel_config["default_table_id"]
    category_code = reel_config["category_code"] if args.category is None else args.category
    if category_code and not os.getenv("AKENEO_CATEGORY"):
        os.environ["AKENEO_CATEGORY"] = category_code
    moodboard_id = args.moodboard_id or moodboard_id_for_category(category_code) or reel_config["default_moodboard_id"]

    settings = load_scrape_settings()

    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )
    krea = KreaClient(base.krea_token, base.krea_base_url)
    fal = FalClient(base.fal_key)

    overall_success = True

    # Phase 1: Krea AI Room Interior Generation (9:16 Ratio - Before Image)
    print(f"\n[PHASE 1/5] Krea AI Room Interior Photo Generation (Prompt: '{reel_config['interior_prompt']}')...")
    if not generate_krea_interiors_pipeline(
        krea,
        airtable,
        moodboard_id=moodboard_id,
        prompt=reel_config["interior_prompt"],
        limit_records=args.max_items,
    ):
        overall_success = False

    # Phase 2: Fal AI Claude Sonnet 5 Blending Prompt Generation
    print("\n[PHASE 2/5] Fal AI Claude Sonnet 5 Blending Prompt Generation...")
    if not generate_claude_blending_prompts(
        fal,
        airtable,
        placement_rule=reel_config.get("placement_rule", ""),
        limit_records=args.max_items,
    ):
        overall_success = False

    # Phase 3: Fal AI Nano Banana Pro Day Image Blending (9:16 Ratio - After Image)
    print("\n[PHASE 3/5] Fal AI Nano Banana Pro Image Blending (9:16 Ratio)...")
    if not generate_nano_banana_pro_blends(
        fal,
        airtable,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Phase 4: Fal AI Multiple Angle Generation (fal-ai/qwen-image-edit-2511-multiple-angles, 9:16 Ratio)
    print("\n[PHASE 4/5] Fal AI Multiple Angle Generation (fal-ai/qwen-image-edit-2511-multiple-angles)...")
    if not generate_multiple_angles_pipeline(
        fal,
        airtable,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Phase 5: Slideshow Reel Video Generation (Slide Show Before and After Reel)
    print("\n[PHASE 5/5] Slideshow Reel Video Generation (Slide Show Before and After Reel)...")
    if not generate_slideshow_reels_pipeline(
        fal,
        airtable,
        limit_records=args.max_items,
    ):
        overall_success = False

    print("\n" + "=" * 64)
    if overall_success:
        print(f"[OK] {reel_config['label']} AI Pipeline completed successfully!")
    else:
        print("[WARN] Pipeline completed with one or more warnings/errors.")
    print("=" * 64)

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
