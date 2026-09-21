"""Product Closeup w/ Specs Story Generation & Logging Pipeline using Fal AI Nano Banana Pro.

Blends:
1. 'Furniture item' (Product Photo)
2. 'Product Closeup w/ Specs Layout' (Layout Template: 'product_specs_layout.png')

Uses the prompt from:
'JSON Prompts/Product Closeup with Specs/product_closeup_specs.json'

Outputs:
- Generates 9:16 story image via Fal AI Nano Banana Pro ('fal-ai/nano-banana-pro/edit')
- Uploads the blended result directly into Airtable field 'PCS Story'
- Updates record Status: 'Processing' -> 'Done'
- Appends execution log to output/logs/fal_nano_banana_specs_story_logs.json

Usage::

    python generate_product_specs_story_pipeline.py
    python generate_product_specs_story_pipeline.py --limit 1
    python generate_product_specs_story_pipeline.py --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

import requests

from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.item_tagger import tag_and_upload_blended_image
from content_automation.media import download_to_temp_file
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)

PRODUCT_SPECS_PIPELINE_TABLES: dict[str, dict[str, str]] = {
    "chandelier": {
        "category_code": "chandelier_product_specs_story",
        "label": "Chandelier Product Closeup w/ Specs",
        "default_table_id": "tblEGTB6BodRVDqBV",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_SPECS",
    },
    "chandeliers": {
        "category_code": "chandelier_product_specs_story",
        "label": "Chandelier Product Closeup w/ Specs",
        "default_table_id": "tblEGTB6BodRVDqBV",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_SPECS",
    },
}

DEFAULT_MODEL = "fal-ai/nano-banana-pro/edit"

FIELD_LAYOUT = "Product Closeup w/ Specs Layout"
FIELD_FURNITURE_ITEM = "Furniture item"
FIELD_ITEM_NAME = "Item Name"
FIELD_STATUS = "Status"
FIELD_OUTPUT_PCS_STORY = "PCS Story"

STATUS_STANDBY = "Standby"  
STATUS_PROCESSING = "Processing"
STATUS_DONE = "Complete"
STATUS_ERROR_NO_COMBINATION = "Error no Combination No Generation Request"

TERMINAL_AND_PROTECTED_STATUSES = {
    "complete", "completed", "done", "finished",
    "posted", "scheduled", "schedule",
    "discard", "discarded",
    "for manual", "minor revision", "minor revisions", "fm",
}

LOG_DIR = Path("output") / "logs"
LOG_FILE = LOG_DIR / "fal_nano_banana_specs_story_logs.json"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Fal AI Nano Banana Pro blending pipeline for Product Closeup w/ Specs -> 'PCS Story'."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["chandelier", "chandeliers", "all"],
        default="chandeliers",
        help="Target category (default: chandeliers)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override Airtable destination Table ID",
    )
    parser.add_argument(
        "--max-items",
        "--limit",
        "-n",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N pending records",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Process a single specific Airtable record ID",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Fal AI model code (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Process record even if PCS Story is already filled",
    )
    return parser.parse_args(argv)


def append_json_log(log_entry: dict[str, Any], log_path: Path = LOG_FILE) -> None:
    """Append a log record to the JSON log file."""
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
    print(f"[LOG] Appended execution log entry to {log_path}")


def extract_attachment_url(val: Any) -> str:
    if isinstance(val, list) and val:
        item = val[0]
        if isinstance(item, dict):
            return str(item.get("url") or "").strip()
        if isinstance(item, str):
            return item.strip()
    elif isinstance(val, str):
        return val.strip()
    return ""


def build_specs_prompt(raw_item_name: str, fallback_type: str = "Chandelier") -> str:
    """Read product_closeup_specs.json and inject clean item_name, product_type, and specs."""
    prompt_candidates = [
        Path("JSON Prompts/Product Closeup with Specs/product_closeup_specs.json"),
        Path("product_closeup_specs.json"),
    ]
    prompt_file = next((p for p in prompt_candidates if p.is_file()), None)

    name_str = (raw_item_name or "").strip()
    if " | " in name_str:
        parts = [p.strip() for p in name_str.split(" | ") if p.strip()]
        base_name = parts[0]
        product_type = parts[1] if len(parts) > 1 else fallback_type
    else:
        base_name = name_str or "Modern Lighting"
        product_type = fallback_type

    if prompt_file:
        try:
            prompt_data = json.loads(prompt_file.read_text(encoding="utf-8-sig"))
            if "USER_TEXT_INPUT" in prompt_data:
                prompt_data["USER_TEXT_INPUT"]["item_name"] = base_name
                prompt_data["USER_TEXT_INPUT"]["product_type"] = product_type
                # Keep specs clean and editorial
                prompt_data["USER_TEXT_INPUT"]["spec_1"] = f"Collection: {product_type}"
            return json.dumps(prompt_data, ensure_ascii=False)
        except Exception as err:
            print(f"[WARN] Error parsing prompt JSON ({err}), using fallback text formatting.")

    return (
        f"Luxury minimalist 9:16 product catalog poster for '{base_name}' ({product_type}). "
        "Left side: large close-up crop of the uploaded product. Right side: smaller full product view. "
        "Keep HomeCartel logo in exact place. Lower right text: bold item name and product type. "
        "Clean white studio background, photorealistic luxury editorial presentation."
    )


def run_pipeline_for_table(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    label: str,
    model: str = DEFAULT_MODEL,
    max_items: int | None = None,
    record_id: str | None = None,
    force: bool = False,
) -> bool:
    airtable.ensure_fields({
        FIELD_OUTPUT_PCS_STORY: "multipleAttachments",
        FIELD_STATUS: "singleSelect",
        FIELD_ITEM_NAME: "singleLineText",
    })

    records = airtable.list_records(
        [FIELD_LAYOUT, FIELD_FURNITURE_ITEM, FIELD_ITEM_NAME, FIELD_STATUS, FIELD_OUTPUT_PCS_STORY]
    )
    if not records:
        print(f"[OK] No records found in table {label}.")
        return True

    if record_id:
        records = [r for r in records if r["id"] == record_id]
        if not records:
            print(f"[ERROR] Record {record_id} was not found in {label}.")
            return False

    eligible = []
    for r in records:
        fields = r.get("fields", {})
        furniture = fields.get(FIELD_FURNITURE_ITEM) or fields.get("Furniture Item")
        pcs_story = fields.get(FIELD_OUTPUT_PCS_STORY)
        if not furniture:
            continue
        status_cf = str(fields.get(FIELD_STATUS) or "").strip().casefold()
        if status_cf in TERMINAL_AND_PROTECTED_STATUSES and not record_id and not force:
            continue
        if pcs_story and not record_id and not force:
            continue
        eligible.append(r)

    if not eligible:
        print(f"[OK] No pending records requiring Nano Banana Pro generation in {label}.")
        return True

    if max_items is not None:
        eligible = eligible[:max_items]

    print("=" * 72)
    print(f"🚀 Running Fal AI Nano Banana Pro Generation Pipeline for {label}")
    print(f"Targeting {len(eligible)} eligible record(s) -> Output field: '{FIELD_OUTPUT_PCS_STORY}'")
    print(f"Model: {model}")
    print("=" * 72)

    succeeded = 0
    failed = 0

    for idx, record in enumerate(eligible, start=1):
        rec_id = record["id"]
        fields = record.get("fields", {})
        raw_name = str(fields.get(FIELD_ITEM_NAME) or rec_id).strip()
        layout_val = fields.get(FIELD_LAYOUT)
        furniture_val = fields.get(FIELD_FURNITURE_ITEM) or fields.get("Furniture Item")

        layout_url = extract_attachment_url(layout_val)
        source_url = extract_attachment_url(furniture_val)

        if not layout_url or not source_url:
            print(f"[SKIP/ERROR] Record {rec_id} ({raw_name}) missing mandatory attachment inputs:")
            print(f"  - {FIELD_LAYOUT}: {'PRESENT' if layout_url else 'MISSING'}")
            print(f"  - {FIELD_FURNITURE_ITEM}: {'PRESENT' if source_url else 'MISSING'}")
            try:
                airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_ERROR_NO_COMBINATION})])
                print(f"[STATUS] Record {rec_id} status updated to '{STATUS_ERROR_NO_COMBINATION}'")
            except Exception as st_err:
                print(f"[WARN] Failed to set status: {st_err}")
            failed += 1
            continue

        # Layout first as reference, followed by source product image
        input_urls = [layout_url, source_url]

        print(f"\n[{idx}/{len(eligible)}] Processing record {rec_id}: '{raw_name}' (Inputs: 2 image(s))")

        # 1. Update status to 'Processing'
        try:
            airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_PROCESSING})])
            print(f"[STATUS] Record {rec_id} status updated to '{STATUS_PROCESSING}'")
        except Exception as st_err:
            print(f"[WARN] Failed to set status to '{STATUS_PROCESSING}': {st_err}")

        # 2. Build formatted prompt
        prompt_text = build_specs_prompt(raw_name)

        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        downloaded = None

        try:
            print(f"    Sending image blending request to Fal AI ({model})...")
            gen_url = fal.generate(
                prompt_text,
                input_urls,
                aspect_ratio="9:16",
                resolution="1K",
                model=model,
            )
            print(f"[OK] Fal AI Generated URL for record {rec_id}: {gen_url}")

            # Download generated image locally
            resp = requests.get(gen_url, stream=True, timeout=60)
            downloaded = download_to_temp_file(
                resp,
                prefix="pcs_story_gen_",
                suffix=".jpg",
                context=f"Download generated image from {gen_url}",
            )

            # 3. Log details to output/logs/
            log_entry = {
                "timestamp": timestamp_str,
                "record_id": rec_id,
                "item_name": raw_name,
                "source_image_url": source_url,
                "layout_image_url": layout_url,
                "generated_image_url": gen_url,
                "model": model,
                "target_field": FIELD_OUTPUT_PCS_STORY,
                "status": STATUS_DONE,
            }
            append_json_log(log_entry, LOG_FILE)

            # 4. Upload attachment to 'PCS Story'
            clean_filename_base = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in raw_name)
            filename = f"pcs_story_{clean_filename_base}_{rec_id}.jpg"
            airtable.upload_attachment(
                rec_id,
                FIELD_OUTPUT_PCS_STORY,
                downloaded,
                filename,
            )
            print(f"[OK] Attached generated story card to '{FIELD_OUTPUT_PCS_STORY}' ({filename})")

            # 4b. Tag and upload to 'Blended Image with Name text'
            try:
                tag_and_upload_blended_image(
                    airtable=airtable,
                    record_id=rec_id,
                    blended_source=downloaded.path,
                    item_name=raw_name,
                    category="chandeliers",
                    target_field="Blended Image with Name text",
                    fallback_if_undetected=True,
                )
            except Exception as tag_err:
                print(f"[WARN] Tagging for 'Blended Image with Name text' skipped: {tag_err}")

            # 5. Update status to 'Done'
            airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_DONE})])
            print(f"[STATUS] Record {rec_id} status updated to '{STATUS_DONE}'")

            succeeded += 1

        except Exception as err:
            failed += 1
            print(f"[ERROR] Failed generation for record {rec_id}: {err}")
            log_entry = {
                "timestamp": timestamp_str,
                "record_id": rec_id,
                "item_name": raw_name,
                "source_image_url": source_url,
                "generated_image_url": "",
                "status": "Failed",
                "error": str(err),
            }
            append_json_log(log_entry, LOG_FILE)
        finally:
            if downloaded:
                downloaded.cleanup()

    print(f"\n[SUMMARY] {label}: {succeeded} succeeded, {failed} failed.")
    return failed == 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    base_settings = load_settings()
    base_settings.require({"fal"})

    fal = FalClient(api_key=base_settings.fal_key)

    cfg = PRODUCT_SPECS_PIPELINE_TABLES["chandeliers"]
    table_id = args.table_id or os.getenv(cfg["env_table_key"], "").strip() or cfg["default_table_id"]

    scrape_settings = load_scrape_settings(
        category_code=cfg["category_code"],
        table_id_override=table_id,
        settings=base_settings,
    )
    airtable = ScrapeAirtableClient(
        scrape_settings.airtable_token,
        scrape_settings.airtable_base_id,
        scrape_settings.airtable_table_id,
    )

    ok = run_pipeline_for_table(
        fal,
        airtable,
        label=cfg["label"],
        model=args.model,
        max_items=args.max_items,
        record_id=args.record_id,
        force=args.force,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
