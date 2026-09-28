"""Backfill Utility: Tag Item Names onto Blended Images for 1 Product 3 Styles Feeds.

Scans the 3 supported 1 Product 3 Styles Feed tables in Airtable:
  - Chandeliers (tblrlfqBGe5EjS5PI)
  - Pendant Lights (tblRy52kCasisCWzd)
  - Floor Lamps (tbl9GIq2QeYCwMhWU)

Finds all records where '1 Product 3 Style Blended' has images, but
'Blended Image with Name text' is empty.
Tags the furniture fixture with YOLO-World (floating 2-line Poppins pill)
and uploads the 3 tagged slides to 'Blended Image with Name text'.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from content_automation.akeneo_client import split_item_name
from content_automation.config import load_settings
from content_automation.item_tagger import (
    TARGET_BLENDED_FIELD,
    tag_and_upload_blended_image,
)
from content_automation.scraping.airtable import ScrapeAirtableClient

TABLES = [
    {
        "name": "Chandeliers",
        "table_id": "tblrlfqBGe5EjS5PI",
        "category": "chandeliers",
        "default_type": "Chandelier",
    },
    {
        "name": "Pendant Lights",
        "table_id": "tblRy52kCasisCWzd",
        "category": "pendant_lights",
        "default_type": "Pendant Light",
    },
    {
        "name": "Floor Lamps",
        "table_id": "tbl9GIq2QeYCwMhWU",
        "category": "floor_lamps",
        "default_type": "Floor Lamp",
    },
]


def backfill_table(settings, table_info: dict[str, Any]) -> int:
    name = table_info["name"]
    table_id = table_info["table_id"]
    category = table_info["category"]
    default_type = table_info["default_type"]

    print(f"\n{'='*64}")
    print(f" Checking {name} ({table_id})...")
    print(f"{'='*64}")

    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )

    records = airtable.list_records(
        [
            "1 Product 3 Style Blended",
            "1 Product 3 Styles Blended",
            TARGET_BLENDED_FIELD,
            "Item Name",
            "SKU",
            "Product Type",
        ]
    )

    eligible: list[dict[str, Any]] = []
    for r in records:
        f = r.get("fields", {})
        blended = f.get("1 Product 3 Style Blended") or f.get("1 Product 3 Styles Blended") or []
        tagged = f.get(TARGET_BLENDED_FIELD) or []
        if blended and not tagged:
            eligible.append(r)

    print(f"[INFO] Found {len(eligible)} record(s) needing '{TARGET_BLENDED_FIELD}' backfill.")
    if not eligible:
        return 0

    success_count = 0
    for idx, r in enumerate(eligible, start=1):
        record_id = r["id"]
        fields = r.get("fields", {})
        blended = fields.get("1 Product 3 Style Blended") or fields.get("1 Product 3 Styles Blended") or []
        raw_name = str(fields.get("Item Name") or fields.get("SKU") or record_id).strip()
        item_title, p_type = split_item_name(raw_name, fallback_product_type=str(fields.get("Product Type") or default_type))
        if not p_type:
            p_type = default_type

        print(f"\n [{idx}/{len(eligible)}] Tagging {record_id} | Name: '{item_title}' | Type: '{p_type}'...")
        ok = tag_and_upload_blended_image(
            airtable=airtable,
            record_id=record_id,
            blended_source=blended,
            item_name=item_title,
            product_type=p_type,
            category=category,
            target_field=TARGET_BLENDED_FIELD,
            output_filename_prefix=f"{category}_tagged",
            fallback_if_undetected=True,
        )
        if ok:
            success_count += 1
            print(f" [+] Successfully backfilled {record_id} -> '{TARGET_BLENDED_FIELD}'")
        else:
            print(f" [!] Failed to backfill {record_id}")
        time.sleep(0.5)

    return success_count


def main():
    settings = load_settings()
    total_backfilled = 0
    for t in TABLES:
        count = backfill_table(settings, t)
        total_backfilled += count

    print(f"\n{'='*64}")
    print(f"[SUMMARY] Total records backfilled with item name tags: {total_backfilled}")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()
