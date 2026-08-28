"""Floor Lamp Before & After Reel (Day & Night Reel) AI Generation & Blending Pipeline.

Runs the complete AI pipeline for Floor Lamp Before & After Reel on Airtable (tbl2VoWOt7sSut4E2):
1. Krea AI Interior Photo Generation -> 'Interior Generated', Status -> 'Interior Generated'
2. Qwen 3.7 Flash Analysis & Prompt Generation -> 'Prompt for Blending', Status -> 'Generating Prompt for Blending'
3. Qwen Image 3.0 Pro Image-to-Image Blending -> 'Blended Image', Status -> 'Blended Image Generated'

Usage::

    python generate_day_night_reel_pipeline.py
    python generate_day_night_reel_pipeline.py --max-items 5
    python generate_day_night_reel_pipeline.py --category floor_lamps --style modern
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.kie_client import KieClient
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.qwen_client import QwenClient
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
STATUS_NIGHT_IMAGE = "Processing Night Image"
STATUS_MULTIPLE_ANGLE = "Multiple Angle Blended Image Generating"
STATUS_COMPLETE = "Complete"

INTERIOR_FIELD = "Interior Generated Photo"
INTERIOR_FIELD_FALLBACK = "Interior Generated"
INTERIOR_FIELDS = [INTERIOR_FIELD, INTERIOR_FIELD_FALLBACK]
INTERIOR_ASPECT_RATIO = "4:5"

PROMPT_FIELD = "Blending Prompt"
PROMPT_FIELD_FALLBACK = "Prompt for Blending"
PROMPT_FIELDS = [PROMPT_FIELD, PROMPT_FIELD_FALLBACK]

DAY_IMAGE_FIELD = "Day Image"
DAY_IMAGE_FIELD_FALLBACK = "Blended Image"
DAY_IMAGE_FIELDS = [DAY_IMAGE_FIELD, DAY_IMAGE_FIELD_FALLBACK]

NIGHT_IMAGE_FIELD = "Night Image"
NIGHT_IMAGE_FIELDS = [NIGHT_IMAGE_FIELD]

QWEN_PROMPT_MODEL = "qwen3.7-flash"
QWEN_BLEND_MODEL = "qwen-image-3.0-pro"


def get_first_field_value(fields: dict[str, Any], field_names: list[str]) -> Any:
    """Return the first populated value among candidate field names."""
    for name in field_names:
        if name in fields and fields[name]:
            return fields[name]
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
    """Generate Krea AI room interior photo into 'Interior Generated Photo' (or 'Interior Generated')."""
    airtable.ensure_fields({interior_field: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(INTERIOR_FIELDS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD])
    if not records:
        print("[OK] No records found in Airtable to populate interior photos.")
        return True

    unpopulated = [
        record
        for record in records
        if str(record.get("fields", {}).get(STATUS_FIELD) or "").strip().casefold() == STATUS_STANDBY.casefold()
        and not get_first_field_value(record.get("fields", {}), INTERIOR_FIELDS)
    ]
    if not unpopulated:
        print(f"[OK] No records found with Status '{STATUS_STANDBY}' missing interior photo field.")
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
            target_field = INTERIOR_FIELD_FALLBACK if INTERIOR_FIELD_FALLBACK in fields else interior_field
            airtable.upload_attachment(record_id, target_field, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_INTERIOR_GENERATED})])
            print(
                f"[OK] Attached Krea image to '{target_field}' and updated "
                f"{STATUS_FIELD} to '{STATUS_INTERIOR_GENERATED}' on record {record_id}"
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


def generate_qwen_blending_prompts(
    qwen: QwenClient,
    airtable: ScrapeAirtableClient,
    *,
    prompt_model: str = QWEN_PROMPT_MODEL,
    prompt_field: str = PROMPT_FIELD,
    limit_records: int | None = None,
) -> bool:
    """Generate detailed JSON prompt using Qwen 3.7 Flash into 'Blending Prompt'."""
    airtable.ensure_fields({prompt_field: "multilineText"})
    records = airtable.list_records(
        INTERIOR_FIELDS + PROMPT_FIELDS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable to generate prompts.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        interior_attachments = get_first_field_value(fields, INTERIOR_FIELDS)
        prompt_val = get_first_field_value(fields, PROMPT_FIELDS)
        if not interior_attachments:
            continue
        if prompt_val:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Qwen 3.7 Flash prompt generation (interior missing or blending prompt already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{prompt_field}' for {len(eligible)} record(s) "
        f"using Qwen 3.7 Flash ({prompt_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        interior_url = extract_attachment_url(get_first_field_value(fields, INTERIOR_FIELDS))
        furniture_url = extract_attachment_url(fields.get(FIELD_NAME))

        if not interior_url or not furniture_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Analyzing photos & generating prompt for "
            f"record {record_id} ({item_label}) with Qwen 3.7 Flash..."
        )

        try:
            blending_json_prompt = qwen.generate_blending_json_prompt(
                interior_url,
                furniture_url,
                model=prompt_model,
            )
            target_prompt_field = PROMPT_FIELD_FALLBACK if PROMPT_FIELD_FALLBACK in fields else prompt_field
            airtable.update_records([(record_id, {target_prompt_field: blending_json_prompt, STATUS_FIELD: STATUS_GENERATING_PROMPT})])
            print(f"[OK] Saved Qwen 3.7 Flash JSON prompt to '{target_prompt_field}' and updated {STATUS_FIELD} to '{STATUS_GENERATING_PROMPT}' on record {record_id}")
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed generating prompt for record {record_id}: {error}")
            failed += 1

    print(
        f"[INFO] Qwen 3.7 Flash prompt generation complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


def generate_qwen_image_blends(
    qwen: QwenClient,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = QWEN_BLEND_MODEL,
    day_field: str = DAY_IMAGE_FIELD,
    limit_records: int | None = None,
) -> bool:
    """Generate image-to-image blended photo using Qwen Image 3.0 Pro into 'Day Image' (or 'Blended Image')."""
    airtable.ensure_fields({day_field: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        INTERIOR_FIELDS + PROMPT_FIELDS + DAY_IMAGE_FIELDS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable for image blending.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        prompt_text = str(get_first_field_value(fields, PROMPT_FIELDS) or "").strip()
        day_attachments = get_first_field_value(fields, DAY_IMAGE_FIELDS)
        if not prompt_text:
            continue
        if day_attachments:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Qwen Image 3.0 Pro blending (prompt missing or Day Image already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{day_field}' for {len(eligible)} record(s) "
        f"using Qwen Image 3.0 Pro ({blend_model})..."
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
            f"record {record_id} ({item_label}) with Qwen Image 3.0 Pro..."
        )

        downloaded = None
        try:
            image_url = qwen.generate_image_3_pro(
                prompt_text,
                image_inputs,
                size="1728*2368",
                model=blend_model,
                image_labels=["Interior Generated photo", "Furniture Item photo"],
            )
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="blended_image_",
                suffix=".jpg",
                context=f"Download blended image from {image_url}",
            )
            filename = f"day_{record_id}.jpg"
            target_day_field = DAY_IMAGE_FIELD_FALLBACK if DAY_IMAGE_FIELD_FALLBACK in fields else day_field
            airtable.upload_attachment(record_id, target_day_field, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_BLENDED_IMAGE})])
            print(
                f"[OK] Attached blended image to '{target_day_field}' and updated "
                f"{STATUS_FIELD} to '{STATUS_BLENDED_IMAGE}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed blending image for record {record_id}: {error}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Qwen Image 3.0 Pro blending complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


def generate_qwen_night_images(
    qwen: QwenClient,
    airtable: ScrapeAirtableClient,
    *,
    blend_model: str = QWEN_BLEND_MODEL,
    night_field: str = NIGHT_IMAGE_FIELD,
    limit_records: int | None = None,
) -> bool:
    """Convert Day Image to Night Image using Qwen Image 3.0 Pro ('edit only')."""
    airtable.ensure_fields({night_field: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        DAY_IMAGE_FIELDS + NIGHT_IMAGE_FIELDS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable for day-to-night conversion.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        day_attachments = get_first_field_value(fields, DAY_IMAGE_FIELDS)
        night_attachments = get_first_field_value(fields, NIGHT_IMAGE_FIELDS)
        if not day_attachments:
            continue
        if night_attachments:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring Qwen Image 3.0 Pro day-to-night conversion (Day Image missing or Night Image already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{night_field}' for {len(eligible)} record(s) "
        f"using Qwen Image 3.0 Pro ({blend_model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        day_url = extract_attachment_url(get_first_field_value(fields, DAY_IMAGE_FIELDS))

        if not day_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing accessible Day Image URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Converting Day Image to Night Image for "
            f"record {record_id} ({item_label}) with Qwen Image 3.0 Pro..."
        )

        night_prompt = (
            "Transform this interior room photo from daytime to nighttime atmosphere. "
            "Darken all natural window daylight and ambient illumination to a dark evening/night environment. "
            "Turn ON and brightly illuminate the central light fixture in the scene, "
            "casting warm glowing ambient light, highlights, and soft dramatic shadows across the ceiling and room interior. "
            "Strictly maintain the exact room composition, architectural layout, and furniture placement, editing ONLY the lighting and time of day."
        )

        downloaded = None
        try:
            image_url = qwen.generate_image_3_pro(
                night_prompt,
                [day_url],
                size="1728*2368",
                model=blend_model,
                image_labels=["Daytime Interior Photo"],
            )
            response = requests.get(image_url, stream=True)
            downloaded = download_to_temp_file(
                response,
                prefix="night_image_",
                suffix=".jpg",
                context=f"Download night image from {image_url}",
            )
            filename = f"night_{record_id}.jpg"
            airtable.upload_attachment(record_id, night_field, downloaded, filename)
            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_COMPLETE})])
            print(
                f"[OK] Attached night image to '{night_field}' and updated "
                f"{STATUS_FIELD} to '{STATUS_COMPLETE}' on record {record_id}"
            )
            succeeded += 1
        except Exception as error:
            print(f"[ERROR] Failed converting night image for record {record_id}: {error}")
            failed += 1
        finally:
            if downloaded:
                downloaded.cleanup()

    print(
        f"[INFO] Qwen Image 3.0 Pro day-to-night conversion complete: {succeeded} succeeded, {failed} failed."
    )
    return failed == 0


MULTIPLE_ANGLE_FIELD = "Multiple Angle Blended Image"
FAL_MULTIPLE_ANGLE_MODEL = "fal-ai/qwen-image-edit-2511-multiple-angles"


def generate_multiple_angles_pipeline(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    model: str = FAL_MULTIPLE_ANGLE_MODEL,
    limit_records: int | None = None,
) -> bool:
    """Generate 4 different viewing angles using Fal AI into 'Multiple Angle Blended Image'."""
    airtable.ensure_fields({MULTIPLE_ANGLE_FIELD: "multipleAttachments", STATUS_FIELD: "singleSelect"})
    records = airtable.list_records(
        INTERIOR_FIELDS + [FIELD_NAME, SKU_FIELD, ITEM_NAME_FIELD, STATUS_FIELD] + PROMPT_FIELDS + DAY_IMAGE_FIELDS + NIGHT_IMAGE_FIELDS + [MULTIPLE_ANGLE_FIELD]
    )
    if not records:
        print("[OK] No records found in Airtable for multiple angle generation.")
        return True

    eligible = []
    for record in records:
        fields = record.get("fields", {})
        blended_attachments = get_first_field_value(fields, DAY_IMAGE_FIELDS) or get_first_field_value(fields, NIGHT_IMAGE_FIELDS) or fields.get("Moodboard V1 Blended")
        already_has_angles = fields.get(MULTIPLE_ANGLE_FIELD)
        if not blended_attachments:
            continue
        if already_has_angles:
            continue
        eligible.append(record)

    if not eligible:
        print(f"[OK] No records requiring multiple angle generation ('Day/Night Image' missing or '{MULTIPLE_ANGLE_FIELD}' already filled).")
        return True

    if limit_records is not None:
        eligible = eligible[:limit_records]

    print(
        f"[INFO] Generating '{MULTIPLE_ANGLE_FIELD}' (4 angles) for {len(eligible)} record(s) "
        f"using Fal AI ({model})..."
    )

    succeeded = 0
    failed = 0
    for position, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        item_label = fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id

        input_url = (
            extract_attachment_url(get_first_field_value(fields, NIGHT_IMAGE_FIELDS))
            or extract_attachment_url(get_first_field_value(fields, DAY_IMAGE_FIELDS))
            or extract_attachment_url(fields.get("Moodboard V1 Blended"))
        )
        if not input_url:
            print(f"[SKIP] Record {record_id} ({item_label}) missing blended attachment URL.")
            continue

        print(
            f"[INFO] [{position}/{len(eligible)}] Generating 4 viewing angles for "
            f"record {record_id} ({item_label}) with Fal AI ({model})..."
        )

        airtable.update_records([(record_id, {STATUS_FIELD: STATUS_MULTIPLE_ANGLE})])
        print(f"[INFO] Updated {STATUS_FIELD} to '{STATUS_MULTIPLE_ANGLE}' on record {record_id}")

        downloaded_list = []
        try:
            angle_urls = fal.generate_multiple_angles(
                input_url,
                prompt="Generate 4 different architectural viewing angles of this product in the room interior",
                num_images=4,
                model=model,
            )
            print(f"[OK] Fal AI returned {len(angle_urls)} image angle URL(s)")

            for idx, angle_url in enumerate(angle_urls, start=1):
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
                    airtable.upload_attachment(record_id, MULTIPLE_ANGLE_FIELD, downloaded, filename)
                except Exception as upload_err:
                    print(f"[WARN] Failed uploading angle {idx} for record {record_id}: {upload_err}")

            airtable.update_records([(record_id, {STATUS_FIELD: STATUS_COMPLETE})])
            print(
                f"[OK] Attached 4 angle images to '{MULTIPLE_ANGLE_FIELD}' and updated "
                f"{STATUS_FIELD} to '{STATUS_COMPLETE}' on record {record_id}"
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


from content_automation.config import load_settings, resolve_reel_table


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Before & After Reel AI Pipeline (Krea AI -> Qwen 3.7 Flash -> Qwen Image 3.0 Pro Day & Night -> Fal AI Multiple Angles)"
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["chandeliers", "floor_lamps", "pendant_lights"],
        default=None,
        help="Target table: chandeliers (tblODnfaNVP6SXn0A), floor_lamps (tbl2VoWOt7sSut4E2), or pendant_lights (tbleUP86Kw36G8Hdw)",
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
    base.require({"airtable", "krea", "qwen", "fal"})

    reel_config = resolve_reel_table(args.target, args.category)
    table_id = args.table_id or os.getenv(reel_config["env_table_key"], "").strip() or reel_config["default_table_id"]
    category_code = reel_config["table_code"] if args.category is None else args.category
    moodboard_id = (args.moodboard_id or "").strip() or moodboard_id_for_category(category_code) or reel_config.get("default_moodboard_id", "")

    settings = load_scrape_settings(
        category_code=category_code,
        style_code=args.style,
        table_id_override=table_id,
        settings=base,
    )

    print("=" * 64)
    print(f"Before & After Reel AI Generation & Blending Pipeline ({reel_config['label']})")
    print(f"Airtable destination: {settings.airtable_base_id} / {settings.airtable_table_id}")
    print(f"Krea Moodboard ID: {moodboard_id}")
    print(f"Akeneo Category: {reel_config['category_code']} | Style: {args.style}")
    print("=" * 64)

    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        settings.airtable_table_id,
    )
    krea = KreaClient(base.krea_token, base.krea_base_url)
    qwen = QwenClient(base.qwen_api_key, base.qwen_base_url)
    fal = FalClient(base.fal_key)

    overall_success = True

    # Step 1: Krea AI Room Interior Generation
    print(f"\n[PHASE 1/4] Krea AI Room Interior Photo Generation (Prompt: '{reel_config['interior_prompt']}')...")
    if not generate_krea_interiors_pipeline(
        krea,
        airtable,
        moodboard_id=moodboard_id,
        prompt=reel_config["interior_prompt"],
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 2: Qwen 3.7 Flash Blending Prompt Generation
    print("\n[PHASE 2/4] Qwen 3.7 Flash Blending Prompt Generation...")
    if not generate_qwen_blending_prompts(
        qwen,
        airtable,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 3: Qwen Image 3.0 Pro Day Image Blending
    print("\n[PHASE 3/4] Qwen Image 3.0 Pro Day Image Blending...")
    if not generate_qwen_image_blends(
        qwen,
        airtable,
        limit_records=args.max_items,
    ):
        overall_success = False

    # Step 4: Qwen Image 3.0 Pro Day to Night Photo Conversion
    print("\n[PHASE 4/4] Qwen Image 3.0 Pro Day to Night Photo Conversion...")
    if not generate_qwen_night_images(
        qwen,
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
