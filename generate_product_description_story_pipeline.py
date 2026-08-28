"""Product Closeup w/ Description Generation & Logging Pipeline using Fal AI Nano Banana Pro.

Runs the AI image generation pipeline for Product Closeup w/ Description on Airtable:
1. Selects records with 'Furniture Item' attached where 'Product Closeup Description Converted' is missing.
2. Updates Airtable status to 'Processing'.
3. Calls Fal AI Nano Banana Pro API for Image-to-Image conversion.
4. Appends a detailed execution log to output/logs/fal_nano_product_description_logs.json.
5. Uploads the generated image to 'Product Closeup Description Converted' attachment field.
6. Updates Airtable status to 'Complete'.

Usage::

    python generate_product_description_story_pipeline.py
    python generate_product_description_story_pipeline.py --target chandelier
    python generate_product_description_story_pipeline.py --target pendant_lights --max-items 5
    python generate_product_description_story_pipeline.py --record-id rec123456
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

from content_automation.config import TABLES, load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.media import download_to_temp_file
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)

PRODUCT_DESCRIPTION_PIPELINE_TABLES: dict[str, dict[str, str]] = {
    "chandelier": {
        "category_code": "chandelier_product_description_story",
        "label": "Chandelier Product Closeup w/ Description",
        "default_table_id": "tblDcT6jovdAbKnfw",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "chandeliers": {
        "category_code": "chandelier_product_description_story",
        "label": "Chandelier Product Closeup w/ Description",
        "default_table_id": "tblDcT6jovdAbKnfw",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "pendant_light": {
        "category_code": "pendant_lights_product_description_story",
        "label": "Pendant Light Product Closeup w/ Description",
        "default_table_id": "tblDD2w4v0Idb4jAZ",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "pendant_lights": {
        "category_code": "pendant_lights_product_description_story",
        "label": "Pendant Light Product Closeup w/ Description",
        "default_table_id": "tblDD2w4v0Idb4jAZ",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "floor_lamp": {
        "category_code": "floor_lamp_product_description_story",
        "label": "Floor Lamp Product Closeup w/ Description",
        "default_table_id": "tblPvHyKGByWJCMtY",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION",
    },
    "floor_lamps": {
        "category_code": "floor_lamp_product_description_story",
        "label": "Floor Lamp Product Closeup w/ Description",
        "default_table_id": "tblPvHyKGByWJCMtY",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION",
    },
    "cluster_chandelier": {
        "category_code": "cluster_chandelier_product_description_story",
        "label": "Cluster Chandelier Product Closeup w/ Description",
        "default_table_id": "tblnIOQVywHcTgAtv",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "cluster_chandeliers": {
        "category_code": "cluster_chandelier_product_description_story",
        "label": "Cluster Chandelier Product Closeup w/ Description",
        "default_table_id": "tblnIOQVywHcTgAtv",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "table_lamp": {
        "category_code": "table_lamps_product_description_story",
        "label": "Table Lamps Product Closeup w/ Description",
        "default_table_id": "tbl5S9JEHSrjrLwxA",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION",
    },
    "table_lamps": {
        "category_code": "table_lamps_product_description_story",
        "label": "Table Lamps Product Closeup w/ Description",
        "default_table_id": "tbl5S9JEHSrjrLwxA",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION",
    },
    "wall_light": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "wall_lights": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "wall_sconces": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
    },
}

FIELD_LAYOUT = "Product Closeup Description Layout"
FIELD_FURNITURE_ITEM = "Furniture Item"
FIELD_ITEM_NAME = "Item Name"
FIELD_STATUS = "Status"
FIELD_OUTPUT_CONVERTED = "Product Closeup Description Converted"

STATUS_PROCESSING = "Processing"
STATUS_COMPLETE = "Complete"
STATUS_ERROR_NO_COMBINATION = "Error no Combination No Generation Request"

LOG_DIR = Path("output") / "logs"
LOG_FILE = LOG_DIR / "fal_nano_product_description_logs.json"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Fal AI Nano Banana Pro generation pipeline for Product Closeup w/ Description."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[
            "chandelier", "chandeliers",
            "pendant_light", "pendant_lights",
            "floor_lamp", "floor_lamps",
            "cluster_chandelier", "cluster_chandeliers",
            "table_lamp", "table_lamps",
            "wall_light", "wall_lights", "wall_sconces",
            "all",
        ],
        default="all",
        help="Target lighting category (default: all)",
    )
    parser.add_argument(
        "--category",
        "-c",
        default=None,
        help="Specific category code override",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    parser.add_argument(
        "--max-items",
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N records",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Process a single specific Airtable record ID",
    )
    parser.add_argument(
        "--model",
        default="fal-ai/nano-banana-pro/edit",
        help="Fal AI model name (default: fal-ai/nano-banana-pro/edit)",
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


def run_pipeline_for_table(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    label: str,
    model: str = "fal-ai/nano-banana-pro/edit",
    max_items: int | None = None,
    record_id: str | None = None,
) -> bool:
    airtable.ensure_fields({
        FIELD_OUTPUT_CONVERTED: "multipleAttachments",
        FIELD_STATUS: "singleSelect",
        FIELD_ITEM_NAME: "singleLineText",
    })

    records = airtable.list_records(
        [FIELD_LAYOUT, FIELD_FURNITURE_ITEM, FIELD_ITEM_NAME, FIELD_STATUS, FIELD_OUTPUT_CONVERTED, "SKU"]
    )
    if not records:
        print(f"[OK] No records found in table {label}.")
        return True

    if record_id:
        records = [r for r in records if r["id"] == record_id]

    eligible = []
    for r in records:
        fields = r.get("fields", {})
        furniture = fields.get(FIELD_FURNITURE_ITEM) or fields.get("Furniture Item1")
        converted = fields.get(FIELD_OUTPUT_CONVERTED)
        if not furniture:
            continue
        if converted and not record_id:
            continue
        eligible.append(r)

    if not eligible:
        print(f"[OK] No pending records requiring Fal AI generation in {label}.")
        return True

    if max_items is not None:
        eligible = eligible[:max_items]

    print("=" * 64)
    print(f"Running Fal AI Nano Banana Pro Pipeline for {label}")
    print(f"Targeting {len(eligible)} eligible record(s) with model: {model}")
    print("=" * 64)

    succeeded = 0
    failed = 0

    prompt_path = Path("JSON Prompts/Product Closeup V2/product_desc.json")

    for idx, record in enumerate(eligible, start=1):
        rec_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(FIELD_ITEM_NAME) or fields.get("SKU") or rec_id).strip()
        layout_val = fields.get(FIELD_LAYOUT) or fields.get("Product Closeup Description Layout1")
        furniture_val = fields.get(FIELD_FURNITURE_ITEM) or fields.get("Furniture Item1")

        layout_url = extract_attachment_url(layout_val)
        source_url = extract_attachment_url(furniture_val)

        if not layout_url or not source_url:
            print(f"[SKIP/ERROR] Record {rec_id} ({item_name}) missing mandatory attachment combination.")
            print(f"  - {FIELD_LAYOUT}: {'PRESENT' if layout_url else 'MISSING'}")
            print(f"  - {FIELD_FURNITURE_ITEM}: {'PRESENT' if source_url else 'MISSING'}")
            try:
                airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_ERROR_NO_COMBINATION})])
                print(f"[STATUS] Record {rec_id} status updated to '{STATUS_ERROR_NO_COMBINATION}'")
            except Exception as st_err:
                print(f"[WARN] Failed to update status to '{STATUS_ERROR_NO_COMBINATION}': {st_err}")
            continue

        input_urls = [layout_url, source_url]

        print(f"\n[{idx}/{len(eligible)}] Processing record {rec_id}: '{item_name}' (Inputs: 2 image(s))")

        # 1. Update status to 'Processing'
        try:
            airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_PROCESSING})])
            print(f"[OK] Record {rec_id} status updated to '{STATUS_PROCESSING}'")
        except Exception as st_err:
            print(f"[WARN] Failed to set status to '{STATUS_PROCESSING}': {st_err}")

        # 2. Format prompt
        if prompt_path.is_file():
            try:
                prompt_data = json.loads(prompt_path.read_text(encoding="utf-8-sig"))
                if "required_inputs" in prompt_data:
                    prompt_data["required_inputs"]["item_name"] = item_name
                prompt_text = json.dumps(prompt_data, ensure_ascii=False)
            except Exception:
                prompt_text = prompt_path.read_text(encoding="utf-8-sig")
        else:
            prompt_text = (
                f"High quality, professional studio product closeup with description layout for lighting fixture '{item_name}'. "
                "Clean, elegant, commercial presentation, vertical 9:16 portrait."
            )

        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        downloaded = None
        try:
            print(f"    Sending image blending request to Fal AI Nano Banana Pro ({model})...")
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
                prefix="product_desc_conv_",
                suffix=".jpg",
                context=f"Download generated image from {gen_url}",
            )

            # 3. Log details
            log_entry = {
                "timestamp": timestamp_str,
                "record_id": rec_id,
                "item_name": item_name,
                "source_image_url": source_url,
                "layout_image_url": layout_url,
                "generated_image_url": gen_url,
                "model": model,
                "status": STATUS_COMPLETE,
            }
            append_json_log(log_entry, LOG_FILE)

            # 4. Upload attachment to 'Product Closeup Description Converted'
            filename = f"converted_{item_name.replace(' ', '_')}_{rec_id}.jpg"
            airtable.upload_attachment(
                rec_id,
                FIELD_OUTPUT_CONVERTED,
                downloaded,
                filename,
            )
            print(f"[OK] Attached generated image to '{FIELD_OUTPUT_CONVERTED}' for record {rec_id}")

            # 5. Update status to 'Complete'
            airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_COMPLETE})])
            print(f"[OK] Record {rec_id} status updated to '{STATUS_COMPLETE}'")

            succeeded += 1

        except Exception as err:
            failed += 1
            print(f"[ERROR] Failed generation for record {rec_id}: {err}")
            log_entry = {
                "timestamp": timestamp_str,
                "record_id": rec_id,
                "item_name": item_name,
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

    if args.target in ("all", None):
        targets = [
            PRODUCT_DESCRIPTION_PIPELINE_TABLES["chandelier"],
            PRODUCT_DESCRIPTION_PIPELINE_TABLES["pendant_lights"],
            PRODUCT_DESCRIPTION_PIPELINE_TABLES["floor_lamps"],
            PRODUCT_DESCRIPTION_PIPELINE_TABLES["cluster_chandeliers"],
            PRODUCT_DESCRIPTION_PIPELINE_TABLES["table_lamps"],
            PRODUCT_DESCRIPTION_PIPELINE_TABLES["wall_lights"],
        ]
    else:
        cfg = PRODUCT_DESCRIPTION_PIPELINE_TABLES.get(args.target.lower())
        if not cfg:
            raise AutomationError(f"Unknown target '{args.target}'.")
        targets = [cfg]

    overall_success = True
    for cfg in targets:
        table_id = args.table_id or os.getenv(cfg["env_table_key"], "").strip() or cfg["default_table_id"]
        airtable = ScrapeAirtableClient(
            base_settings.airtable_token,
            base_settings.airtable_base_id,
            table_id,
        )
        if not run_pipeline_for_table(
            fal,
            airtable,
            label=cfg["label"],
            model=args.model,
            max_items=args.max_items,
            record_id=args.record_id,
        ):
            overall_success = False

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)

