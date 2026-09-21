"""Batch Runner CLI: Automated Furniture Item Name Tagging for Blended Feeds.

Scans any Airtable table for rows with blended images, detects furniture coordinates
using local zero-cost YOLO-World, and uploads the tagged photo to 'Blended Image with Name text'.

Usage::

    # Run for Moodboard #1 Feed:
    python run_blended_item_tagger.py --table-id tbl9u5vjgx8kuE44R --category chandeliers

    # Run for Moodboard #2 Feed:
    python run_blended_item_tagger.py --table-id tbltWgQKOYjuHw6tx --category chandeliers

    # Run for 1 Product 3 Styles Feed:
    python run_blended_item_tagger.py --table-id tblrlfqBGe5EjS5PI --category chandeliers

    # Process up to 5 items with custom confidence threshold:
    python run_blended_item_tagger.py --table-id tbl9u5vjgx8kuE44R --max-items 5 --conf 0.20
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from content_automation.akeneo_client import split_item_name
from content_automation.fields import ITEM_NAME_FIELD, PRODUCT_TYPE_FIELD, sku_field
from content_automation.item_tagger import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    TARGET_BLENDED_FIELD,
    tag_and_upload_blended_image,
)
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)

# Known candidate fields holding blended photos across different feeds
CANDIDATE_BLENDED_FIELDS = [
    "Moodboard V1 Blended",
    "Blended Image",
    "1 Product 3 Style Blended",
    "Day Image",
    "Night Image",
    "Blended",
]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Batch tag furniture item names onto blended feed photos"
    )
    parser.add_argument("--table-id", "-t", required=True, help="Airtable table ID")
    parser.add_argument(
        "--category",
        "-c",
        default="chandeliers",
        help="Category for detection (e.g. chandeliers, pendant_lights, floor_lamps, sofas)",
    )
    parser.add_argument(
        "--source-field",
        "-s",
        default=None,
        help="Airtable source field containing blended image(s). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--target-field",
        default=TARGET_BLENDED_FIELD,
        help=f"Airtable target field (default: '{TARGET_BLENDED_FIELD}')",
    )
    parser.add_argument(
        "--max-items",
        "-m",
        type=int,
        default=None,
        help="Maximum records to process",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Detection confidence threshold (default: {DEFAULT_CONFIDENCE_THRESHOLD})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-tag records even if target field already has attachments",
    )
    return parser.parse_args(argv)


def detect_source_field(known_fields: set[str], requested_field: str | None = None) -> str | None:
    """Find which blended image field is present on this table."""
    if requested_field and requested_field in known_fields:
        return requested_field

    for candidate in CANDIDATE_BLENDED_FIELDS:
        if candidate in known_fields:
            return candidate
    return None


def main(argv=None) -> int:
    load_dotenv()
    args = parse_args(argv)

    settings = load_scrape_settings()
    airtable = ScrapeAirtableClient(
        api_key=settings.airtable_api_key,
        base_id=settings.airtable_base_id,
        table_id=args.table_id,
    )

    known_fields = airtable.known_field_names()
    source_field = detect_source_field(known_fields, args.source_field)

    if not source_field:
        print(
            f"[ERROR] Could not find a supported blended image field on table {args.table_id}.\n"
            f"Available fields: {sorted(list(known_fields))}\n"
            f"Please specify --source-field explicitly."
        )
        return 1

    target_field = args.target_field
    airtable.ensure_fields({target_field: "multipleAttachments"})

    fetch_fields = [source_field, ITEM_NAME_FIELD, sku_field(0), target_field, PRODUCT_TYPE_FIELD]
    records = airtable.list_records(fetch_fields)
    if not records:
        print(f"[INFO] No records found in table {args.table_id}.")
        return 0

    eligible = []
    for r in records:
        fields = r.get("fields", {})
        source_val = fields.get(source_field)
        if not source_val:
            continue
        if not args.force and fields.get(target_field):
            continue
        eligible.append(r)

    if not eligible:
        print(
            f"[OK] All records in table {args.table_id} already have '{target_field}' "
            f"(or missing '{source_field}')."
        )
        return 0

    if args.max_items is not None:
        eligible = eligible[: args.max_items]

    print(
        f"[INFO] Processing {len(eligible)} record(s) on table {args.table_id} "
        f"using source '{source_field}' -> target '{target_field}'..."
    )

    succeeded = 0
    skipped = 0
    failed = 0

    for idx, record in enumerate(eligible, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        raw_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(sku_field(0)) or "").strip()
        product_type = str(fields.get(PRODUCT_TYPE_FIELD) or "").strip()

        if not raw_name:
            print(f"[SKIP] Record {record_id} has no Item Name or SKU.")
            skipped += 1
            continue

        item_name, p_type = split_item_name(raw_name, fallback_product_type=product_type)

        print(f"\n[INFO] [{idx}/{len(eligible)}] Tagging Record {record_id}: '{item_name}' | '{p_type}'...")
        source_attachments = fields.get(source_field)

        ok = tag_and_upload_blended_image(
            airtable=airtable,
            record_id=record_id,
            blended_source=source_attachments,
            item_name=item_name,
            product_type=p_type,
            category=args.category,
            target_field=target_field,
        )

        if ok:
            succeeded += 1
        else:
            failed += 1

    print(f"\n[SUMMARY] Item tagging complete: {succeeded} succeeded, {skipped} skipped, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
