"""Backfill Utility: Tag Item Names onto Blended Images & Re-stamp Watermarks for Moodboard #1 Feed.

Scans the 3 supported Moodboard #1 Feed tables in Airtable:
  - Chandeliers (tbl9u5vjgx8kuE44R)
  - Pendant Lights (tblOvvYdgsNTXh2zK)
  - Floor Lamps (tbl6uTmwM23KK9ocO)

For every record with 'Moodboard V1 Blended':
1. Detects the lighting fixture using YOLO-World and stamps a 2-line product badge (Poppins font).
2. Uploads the tagged composite to 'Moodboard V1 Blended' and 'Blended Image with Name text'.
3. Re-stamps the HomeCartel logo at Canva coordinates (190.3x63.5 @ 108, 1178.5) onto the tagged image.
4. Uploads the final composite to 'Moodboard Added Watermark' so Slide 1 and Slide 2 both feature the item name.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import Any

import requests
from PIL import Image

from content_automation.akeneo_client import split_item_name
from content_automation.config import load_settings
from content_automation.item_tagger import (
    TARGET_BLENDED_FIELD,
    tag_and_upload_blended_image,
)
from content_automation.media import download_to_temp_file
from content_automation.overlay import HOMECARTEL_LOGO_BOX, stamp_logo
from content_automation.scraping.airtable import ScrapeAirtableClient

TABLES = [
    {
        "name": "Chandeliers",
        "table_id": "tbl9u5vjgx8kuE44R",
        "category": "chandeliers",
        "default_type": "Chandelier",
    },
    {
        "name": "Pendant Lights",
        "table_id": "tblOvvYdgsNTXh2zK",
        "category": "pendant_lights",
        "default_type": "Pendant Light",
    },
    {
        "name": "Floor Lamps",
        "table_id": "tbl6uTmwM23KK9ocO",
        "category": "floor_lamps",
        "default_type": "Floor Lamp",
    },
]

BLENDED_FIELD = "Moodboard V1 Blended"
WATERMARK_ADDED_FIELD = "Moodboard Added Watermark"


def extract_attachment_url(field_val: Any) -> str | None:
    if isinstance(field_val, list) and field_val:
        first = field_val[0]
        if isinstance(first, dict):
            return first.get("url") or first.get("permalink")
    elif isinstance(field_val, dict):
        return field_val.get("url") or field_val.get("permalink")
    return None


class LocalFileWrapper:
    def __init__(self, path: Path, filename: str):
        self.path = path
        self.filename = filename
        self.content_type = "image/jpeg"

    def cleanup(self):
        pass


def backfill_table(settings, table_info: dict[str, Any]) -> int:
    name = table_info["name"]
    table_id = table_info["table_id"]
    category = table_info["category"]
    default_type = table_info["default_type"]

    print(f"\n{'='*64}")
    print(f" Checking Moodboard #1 Feed: {name} ({table_id})...")
    print(f"{'='*64}")

    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )

    records = airtable.list_records(
        [
            BLENDED_FIELD,
            TARGET_BLENDED_FIELD,
            WATERMARK_ADDED_FIELD,
            "Logo",
            "Moodboard Watermark",
            "Watermark Layout",
            "Item Name",
            "SKU",
            "Product Type",
        ]
    )

    eligible: list[dict[str, Any]] = []
    for r in records:
        f = r.get("fields", {})
        blended = f.get(BLENDED_FIELD) or []
        if blended:
            eligible.append(r)

    print(f"[INFO] Found {len(eligible)} record(s) with '{BLENDED_FIELD}'.")
    if not eligible:
        return 0

    # Locate fallback logo across records
    table_logo_url: str | None = None
    for r in records:
        f = r.get("fields", {})
        cand = (
            extract_attachment_url(f.get("Logo"))
            or extract_attachment_url(f.get("Moodboard Watermark"))
            or extract_attachment_url(f.get("Watermark Layout"))
        )
        if cand:
            table_logo_url = cand
            break

    success_count = 0
    for idx, r in enumerate(eligible, start=1):
        record_id = r["id"]
        fields = r.get("fields", {})
        blended = fields.get(BLENDED_FIELD) or []
        raw_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
        item_title, p_type = split_item_name(raw_name, fallback_product_type=str(fields.get("Product Type") or default_type))
        if not p_type:
            p_type = default_type

        blended_url = extract_attachment_url(blended)
        if not blended_url:
            print(f"[{idx}/{len(eligible)}] Skipping {record_id}: no blended image URL.")
            continue

        print(f"\n[{idx}/{len(eligible)}] Processing {record_id} | Name: '{item_title}' | Category: '{p_type}'...")

        # 1. Download current blend
        dl_temp = None
        logo_temp = None
        try:
            resp = requests.get(blended_url, stream=True, timeout=30)
            dl_temp = download_to_temp_file(
                resp,
                prefix="mb1_backfill_",
                suffix=".jpg",
                context=f"Download blend for {record_id}",
            )

            # 2. Tag with YOLO-World
            tagged_paths: list[Path] = []
            tag_and_upload_blended_image(
                airtable=airtable,
                record_id=record_id,
                blended_source=dl_temp.path,
                item_name=item_title,
                product_type=p_type,
                category=category,
                target_field=TARGET_BLENDED_FIELD,
                fallback_if_undetected=True,
                output_tagged_paths=tagged_paths,
            )

            if not tagged_paths or not tagged_paths[0].is_file():
                print(f"[ERROR] Tagging failed to produce an output file for {record_id}")
                continue

            tagged_file = tagged_paths[0]

            # 3. Upload tagged composite to 'Moodboard V1 Blended'
            v1_filename = f"blended_{record_id}.jpg"
            airtable.upload_attachment(record_id, BLENDED_FIELD, LocalFileWrapper(tagged_file, v1_filename), v1_filename)
            print(f"[OK] Uploaded tagged image to '{BLENDED_FIELD}' on {record_id}")

            # 4. Resolve logo and stamp onto newly tagged image
            logo_url = (
                extract_attachment_url(fields.get("Logo"))
                or extract_attachment_url(fields.get("Moodboard Watermark"))
                or extract_attachment_url(fields.get("Watermark Layout"))
                or table_logo_url
            )

            if logo_url:
                resp_logo = requests.get(logo_url, stream=True, timeout=30)
                logo_temp = download_to_temp_file(
                    resp_logo,
                    prefix="mb1_logo_",
                    suffix=".png",
                    context=f"Download logo for {record_id}",
                )
                logo_source = logo_temp.path
            else:
                candidate_local_logos = [
                    Path("assets/Logo.png"),
                    Path("assets/homecartel_logo.png"),
                    Path("content_automation/assets/logo.png"),
                ]
                logo_source = next((p for p in candidate_local_logos if p.is_file()), None)

            if logo_source:
                watermarked_out = tagged_file.with_name(f"watermarked_{record_id}.jpg")
                stamp_logo(
                    tagged_file,
                    logo_source,
                    destination=watermarked_out,
                    box=HOMECARTEL_LOGO_BOX,
                )
                wm_filename = f"watermarked_{record_id}.jpg"
                airtable.upload_attachment(
                    record_id,
                    WATERMARK_ADDED_FIELD,
                    LocalFileWrapper(watermarked_out, wm_filename),
                    wm_filename,
                )
                print(f"[OK] Re-stamped logo and uploaded to '{WATERMARK_ADDED_FIELD}' on {record_id}")
                if watermarked_out.exists():
                    watermarked_out.unlink()
            else:
                print(f"[WARN] No logo found; skipped re-stamping watermark for {record_id}")

            success_count += 1
            print(f"[SUCCESS] Record {record_id} fully backfilled with tags & watermark!")
        except Exception as exc:
            print(f"[ERROR] Failed processing record {record_id}: {exc}")
        finally:
            if dl_temp:
                dl_temp.cleanup()
            if logo_temp:
                logo_temp.cleanup()

    print(f"\n[SUMMARY] Table {name}: {success_count}/{len(eligible)} record(s) successfully backfilled.")
    return success_count


def main() -> int:
    settings = load_settings()
    total_updated = 0
    for t in TABLES:
        total_updated += backfill_table(settings, t)

    print(f"\n{'='*64}")
    print(f"🎉 BACKFILL COMPLETE! Total records updated: {total_updated}")
    print(f"{'='*64}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
