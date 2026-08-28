"""This or That Generation & Logging Pipeline using Fal AI Nano Banana Pro.

Runs the end-to-end 2-phase pipeline for This or That Story on Airtable:
1. Phase 1 (Scrape): Scrapes 2 products from Akeneo into 1 Airtable row with 'This or That Layout' attached.
2. Phase 2 (Generate): Takes the record, formats the JSON prompt, calls Fal AI Nano Banana Pro, and saves output to 'Story This or That (1)' / 'This or That Converted'.

Usage::

    python generate_this_or_that_pipeline.py --target wall_lights --count 1
    python generate_this_or_that_pipeline.py --target table_lamps --count 1
    python generate_this_or_that_pipeline.py --target cluster_chandelier --count 1
    python generate_this_or_that_pipeline.py --target floor_lamp --count 1
    python generate_this_or_that_pipeline.py --target all --count 1
    python generate_this_or_that_pipeline.py --mode generate --record-id rec123456
"""

from __future__ import annotations

import argparse
import datetime
from datetime import timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from PIL import Image
import requests

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import TABLES, load_settings
from content_automation.errors import AssetValidationError, AutomationError
from content_automation.fal_client import FalClient
from content_automation.media import download_to_temp_file
from content_automation.scraping import (
    ScrapeAirtableClient,
    ScrapeRunner,
    load_scrape_settings,
)
from content_automation.scraping.categories import SCRAPE_CATEGORIES, akeneo_category_code

PHT = timezone(timedelta(hours=8))

def pht_timestamp() -> str:
    return datetime.datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")

THIS_OR_THAT_TABLES: dict[str, dict[str, str]] = {
    "wall_lights": {
        "category_code": "wall_lights_this_or_that",
        "label": "Wall Lights This or That",
        "default_table_id": "tblZw6jvSa27oZDiN",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT",
    },
    "wall_light": {
        "category_code": "wall_lights_this_or_that",
        "label": "Wall Lights This or That",
        "default_table_id": "tblZw6jvSa27oZDiN",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT",
    },
    "wall_sconces": {
        "category_code": "wall_lights_this_or_that",
        "label": "Wall Lights This or That",
        "default_table_id": "tblZw6jvSa27oZDiN",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT",
    },
    "table_lamps": {
        "category_code": "table_lamps_this_or_that",
        "label": "Table Lamps This or That",
        "default_table_id": "tblm1Ty2QkAlUcHJt",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_THIS_OR_THAT",
    },
    "table_lamp": {
        "category_code": "table_lamps_this_or_that",
        "label": "Table Lamps This or That",
        "default_table_id": "tblm1Ty2QkAlUcHJt",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_THIS_OR_THAT",
    },
    "cluster_chandelier": {
        "category_code": "cluster_chandelier_this_or_that",
        "label": "Cluster Chandelier This or That",
        "default_table_id": "tblYAhjKckXtjUayx",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_THIS_OR_THAT",
    },
    "cluster_chandeliers": {
        "category_code": "cluster_chandelier_this_or_that",
        "label": "Cluster Chandelier This or That",
        "default_table_id": "tblYAhjKckXtjUayx",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_THIS_OR_THAT",
    },
    "floor_lamp": {
        "category_code": "floor_lamp_this_or_that",
        "label": "Floor Lamp This or That",
        "default_table_id": "tblaoqj8VPVHFmVQn",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_THIS_OR_THAT",
    },
    "floor_lamps": {
        "category_code": "floor_lamp_this_or_that",
        "label": "Floor Lamp This or That",
        "default_table_id": "tblaoqj8VPVHFmVQn",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_THIS_OR_THAT",
    },
    "chandeliers": {
        "category_code": "chandeliers_this_or_that",
        "label": "Chandelier This or That",
        "default_table_id": "tblo42IkuhYLIQBzk",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIERS_THIS_OR_THAT",
    },
    "chandelier": {
        "category_code": "chandeliers_this_or_that",
        "label": "Chandelier This or That",
        "default_table_id": "tblo42IkuhYLIQBzk",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIERS_THIS_OR_THAT",
    },
    "pendant_lights": {
        "category_code": "pendant_lights_this_or_that",
        "label": "Pendant Lights This or That",
        "default_table_id": "tblS1VHp41RDfxztD",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_THIS_OR_THAT",
    },
    "pendant_light": {
        "category_code": "pendant_lights_this_or_that",
        "label": "Pendant Lights This or That",
        "default_table_id": "tblS1VHp41RDfxztD",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_THIS_OR_THAT",
    },
}

FIELD_LAYOUT = "This or That Layout"
FIELD_FURNITURE_ITEM_1 = "Furniture Item"
FIELD_FURNITURE_ITEM_2 = "Furniture Item2"
FIELD_ITEM_NAME_1 = "Item Name"
FIELD_ITEM_NAME_2 = "Item Name2"
FIELD_PRODUCT_TYPE_1 = "Product Type"
FIELD_PRODUCT_TYPE_2 = "Product Type2"
FIELD_STATUS = "Status"

STATUS_STANDBY = "Standby"
STATUS_PROCESSING = "Processing"
STATUS_COMPLETE = "Complete"
STATUS_ERROR = "Error"

LOG_DIR = Path("output") / "logs"
LOG_FILE = LOG_DIR / "fal_nano_this_or_that_logs.json"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Fal AI Nano Banana Pro generation pipeline for This or That Story."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[*THIS_OR_THAT_TABLES.keys(), "all"],
        default="wall_lights",
        help="Target lighting category (default: wall_lights)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["all", "scrape", "generate"],
        default="all",
        help="Pipeline execution mode (default: all - end-to-end scrape then generate row-by-row)",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=1,
        help="Number of rows (pairs) to process (default: 1)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default="modern",
        help="Akeneo Style2 filter (default: modern)",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Target a specific record ID in Airtable",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override destination Airtable Table ID",
    )
    parser.add_argument(
        "--model",
        default="fal-ai/nano-banana-pro/edit",
        help="Fal AI model endpoint (default: fal-ai/nano-banana-pro/edit)",
    )
    return parser.parse_args(argv)


def append_audit_log(entry: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logs = []
    if LOG_FILE.is_file():
        try:
            logs = json.loads(LOG_FILE.read_text(encoding="utf-8"))
            if not isinstance(logs, list):
                logs = []
        except Exception:
            logs = []
    logs.append(entry)
    LOG_FILE.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[AUDIT LOG] Appended log entry to {LOG_FILE.name}")


def extract_attachment_url(val: Any) -> str:
    if isinstance(val, list) and len(val) > 0:
        first = val[0]
        if isinstance(first, dict):
            return first.get("url") or ""
        elif isinstance(first, str):
            return first
    elif isinstance(val, dict):
        return val.get("url") or ""
    elif isinstance(val, str):
        return val
    return ""


def get_clean_name_and_type(name_val: str, type_val: str, default_type: str = "Lighting Fixture") -> tuple[str, str]:
    name = str(name_val or "").strip()
    ptype = str(type_val or "").strip() or default_type
    if "|" in name:
        parts = [p.strip() for p in name.split("|", 1)]
        name = parts[0]
        if len(parts) > 1 and parts[1]:
            ptype = parts[1]
    return name, ptype


def find_this_or_that_layout_path() -> Path:
    candidates = [
        Path("JSON Prompts/This or That/thisorthatlayout.jpg"),
        Path("JSON Prompts/thisorthatlayout.jpg"),
        Path("thisorthatlayout.jpg"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    for base in [Path("JSON Prompts"), Path(".")]:
        if base.is_dir():
            matches = list(base.rglob("thisorthatlayout.jpg"))
            if matches:
                return matches[0]
    raise FileNotFoundError("thisorthatlayout.jpg was not found in workspace")


def resolve_final_field(schema: dict[str, Any]) -> str:
    for candidate in ("Story This or That (1)", "STORY - This or That (1)", "This or That Converted", "Story - This or That (1)"):
        if candidate in schema:
            return candidate
    for k in schema:
        if "this or that" in k.lower() and ("story" in k.lower() or "converted" in k.lower()):
            return k
    return "Story This or That (1)"


def build_runtime_prompt(top_name: str, top_type: str, bottom_name: str, bottom_type: str) -> str:
    prompt_path = Path("JSON Prompts/This or That/this_or_that_json_prompt.json")
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt JSON not found at {prompt_path}")
    data = json.loads(prompt_path.read_text(encoding="utf-8-sig"))
    manual = data.get("manual_inputs", {})
    if "top_item" not in manual:
        manual["top_item"] = {}
    if "bottom_item" not in manual:
        manual["bottom_item"] = {}
    manual["top_item"]["item_name"] = top_name
    manual["top_item"]["item_type"] = top_type
    manual["bottom_item"]["item_name"] = bottom_name
    manual["bottom_item"]["item_type"] = bottom_type
    data["manual_inputs"] = manual
    return json.dumps(data, ensure_ascii=False)


def run_single_record_generation(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    record: dict[str, Any],
    label: str,
    model: str = "fal-ai/nano-banana-pro/edit",
) -> bool:
    rec_id = record["id"]
    fields = record.get("fields", {})
    schema = airtable.table_fields()
    final_field = resolve_final_field(schema)

    # 1. Check layout and product attachments
    layout_val = fields.get(FIELD_LAYOUT)
    top_item_val = fields.get(FIELD_FURNITURE_ITEM_1) or fields.get("Furniture Item1")
    bottom_item_val = fields.get(FIELD_FURNITURE_ITEM_2) or fields.get("Furniture Item 2")

    # If layout is missing on the record, upload it now
    layout_url = extract_attachment_url(layout_val)
    if not layout_url:
        try:
            layout_file = find_this_or_that_layout_path()
            airtable.upload_attachment(rec_id, FIELD_LAYOUT, layout_file, "thisorthatlayout.jpg")
            rec_updated = airtable.get_record(rec_id)
            fields = rec_updated.get("fields", {})
            layout_url = extract_attachment_url(fields.get(FIELD_LAYOUT))
            print(f"[OK] Uploaded missing layout photo to record {rec_id}")
        except Exception as lay_err:
            print(f"[WARN] Could not auto-upload layout to record {rec_id}: {lay_err}")

    top_url = extract_attachment_url(top_item_val)
    bottom_url = extract_attachment_url(bottom_item_val)

    if not layout_url or not top_url or not bottom_url:
        print(f"[SKIP/ERROR] Record {rec_id} missing mandatory attachments:")
        print(f"  - {FIELD_LAYOUT}: {'PRESENT' if layout_url else 'MISSING'}")
        print(f"  - Top Item ({FIELD_FURNITURE_ITEM_1}): {'PRESENT' if top_url else 'MISSING'}")
        print(f"  - Bottom Item ({FIELD_FURNITURE_ITEM_2}): {'PRESENT' if bottom_url else 'MISSING'}")
        return False

    # Determine fallback product type from label
    fallback_type = "Wall Light" if "wall" in label.lower() else (
        "Table Lamp" if "table" in label.lower() else (
            "Cluster Chandelier" if "cluster" in label.lower() else (
                "Floor Lamp" if "floor" in label.lower() else (
                    "Chandelier" if "chandelier" in label.lower() else (
                        "Pendant Light" if "pendant" in label.lower() else "Lighting Fixture"
                    )
                )
            )
        )
    )

    # 2. Extract item names and types
    raw_top_name = fields.get(FIELD_ITEM_NAME_1) or fields.get("Item Name1") or "Top Fixture"
    raw_top_type = fields.get(FIELD_PRODUCT_TYPE_1) or fields.get("Product Type1") or fallback_type
    raw_bottom_name = fields.get(FIELD_ITEM_NAME_2) or fields.get("Item Name 2") or "Bottom Fixture"
    raw_bottom_type = fields.get(FIELD_PRODUCT_TYPE_2) or fields.get("Product Type 2") or fallback_type

    top_name, top_type = get_clean_name_and_type(raw_top_name, raw_top_type, default_type=fallback_type)
    bottom_name, bottom_type = get_clean_name_and_type(raw_bottom_name, raw_bottom_type, default_type=fallback_type)

    print(f"\n[PHASE 2/2] Generating This or That Story for record {rec_id}:")
    print(f"  - Top: '{top_name}' ({top_type})")
    print(f"  - Bottom: '{bottom_name}' ({bottom_type})")
    print(f"  - Model: {model} | Aspect Ratio: 9:16 | Resolution: 1K")
    print(f"  - Image 1 (Layout): {layout_url}")
    print(f"  - Image 2 (Top Item / {FIELD_FURNITURE_ITEM_1}): {top_url}")
    print(f"  - Image 3 (Bottom Item / {FIELD_FURNITURE_ITEM_2}): {bottom_url}")

    # Set Status to Processing
    try:
        airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_PROCESSING})])
    except Exception:
        pass

    # 3. Build dynamic prompt and invoke Fal AI
    prompt_text = build_runtime_prompt(top_name, top_type, bottom_name, bottom_type)
    input_urls = [layout_url, top_url, bottom_url]

    start_time = datetime.datetime.now()
    try:
        result_url = fal.generate(
            prompt=prompt_text,
            image_urls=input_urls,
            aspect_ratio="9:16",
            resolution="1K",
            model=model,
        )
    except Exception as fal_err:
        print(f"[ERROR] Fal AI generation failed for {rec_id}: {fal_err}")
        try:
            airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_ERROR})])
        except Exception:
            pass
        return False

    duration = (datetime.datetime.now() - start_time).total_seconds()
    print(f"[OK] Generated Story Image in {duration:.1f}s: {result_url}")

    # 4. Download and upload to Airtable output field
    resp = requests.get(result_url, stream=True)
    temp_file = download_to_temp_file(resp, prefix="this_or_that_", suffix=".jpg", context=f"Download {result_url}")
    try:
        with Image.open(temp_file.path) as img:
            w, h = img.size
            print(f"[OK] Output dimensions: {w}x{h}")
        out_filename = f"this_or_that_{rec_id}.jpg"
        airtable.upload_attachment(rec_id, final_field, temp_file, out_filename)
        print(f"[OK] Attached output image to '{final_field}' on record {rec_id}")

        # Update status to Complete
        airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_COMPLETE})])
        print(f"[STATUS] Record {rec_id} marked as '{STATUS_COMPLETE}'")

        # Audit log
        append_audit_log({
            "timestamp": pht_timestamp(),
            "record_id": rec_id,
            "table": label,
            "model": model,
            "top_item": {"name": top_name, "type": top_type},
            "bottom_item": {"name": bottom_name, "type": bottom_type},
            "result_url": result_url,
            "duration_seconds": duration,
            "output_field": final_field,
            "status": "SUCCESS",
        })
        return True
    except Exception as up_err:
        print(f"[ERROR] Failed uploading result for {rec_id}: {up_err}")
        return False
    finally:
        temp_file.cleanup()


def run_row_by_row_pipeline(
    target_key: str,
    count: int = 1,
    style: str = "modern",
    mode: str = "all",
    record_id: str | None = None,
    table_id_override: str | None = None,
    model: str = "fal-ai/nano-banana-pro/edit",
) -> bool:
    config = THIS_OR_THAT_TABLES.get(target_key)
    if not config:
        raise AutomationError(f"Unknown target '{target_key}'. Valid targets: {list(THIS_OR_THAT_TABLES.keys())}")

    category_code = config["category_code"]
    label = config["label"]
    table_id = table_id_override or os.getenv(config["env_table_key"], "").strip() or config["default_table_id"]

    settings = load_settings()
    scrape_settings = load_scrape_settings(
        category_code=category_code,
        style_code=style,
        table_id_override=table_id,
        settings=settings,
    )
    airtable = ScrapeAirtableClient(
        scrape_settings.airtable_token,
        scrape_settings.airtable_base_id,
        scrape_settings.airtable_table_id,
    )
    akeneo = AkeneoClient(
        scrape_settings.akeneo_host,
        scrape_settings.akeneo_client_id,
        scrape_settings.akeneo_secret,
        scrape_settings.akeneo_username,
        scrape_settings.akeneo_password,
        channel_name=scrape_settings.channel_name,
    )
    fal = FalClient(api_key=settings.fal_key)

    # Ensure Airtable schema
    airtable.ensure_fields({
        FIELD_LAYOUT: "multipleAttachments",
        "Story This or That (1)": "multipleAttachments",
        FIELD_STATUS: "singleSelect",
        FIELD_ITEM_NAME_1: "singleLineText",
        FIELD_ITEM_NAME_2: "singleLineText",
    })

    print("=" * 80)
    print(f"[START] HOME CARTEL THIS OR THAT PIPELINE: {label.upper()}")
    print(f"Table ID: {table_id} | Mode: {mode.upper()} | Target Count: {count}")
    print("=" * 80)

    if record_id:
        record = airtable.get_record(record_id)
        return run_single_record_generation(fal, airtable, record, label, model=model)

    if mode == "generate":
        # Process existing pending records
        records = airtable.list_records([FIELD_LAYOUT, FIELD_FURNITURE_ITEM_1, FIELD_FURNITURE_ITEM_2, FIELD_ITEM_NAME_1, FIELD_ITEM_NAME_2, FIELD_STATUS, "Story This or That (1)", "This or That Converted"])
        final_field = resolve_final_field(airtable.table_fields())
        pending = [
            r for r in records
            if (r.get("fields", {}).get(FIELD_FURNITURE_ITEM_1) or r.get("fields", {}).get("Furniture Item1"))
            and not r.get("fields", {}).get(final_field)
        ]
        if not pending:
            print(f"[OK] No pending records found to generate in {label}.")
            return True
        pending = pending[:count]
        succeeded = 0
        for idx, rec in enumerate(pending, start=1):
            print(f"\n--- Processing Row {idx}/{len(pending)} ({rec['id']}) ---")
            if run_single_record_generation(fal, airtable, rec, label, model=model):
                succeeded += 1
        return succeeded == len(pending)

    # Mode: 'all' (End-to-End Row-by-Row: Scrape 1 Row -> Generate 1 Row -> Repeat)
    successes = 0
    for row_idx in range(1, count + 1):
        print(f"\n{'=' * 30} ROW {row_idx}/{count} {'=' * 30}")
        print(f"[PHASE 1/2] Scraping 2 new {style} products from Akeneo for {label}...")

        runner = ScrapeRunner(
            akeneo,
            airtable,
            category_code=category_code,
            style_code=style,
            items_per_row=2,
            max_items=2,
        )
        scrape_ok = runner.run()
        if not scrape_ok:
            print(f"[WARN] Scraping encountered issues on Row {row_idx}.")

        if mode == "scrape":
            if scrape_ok:
                successes += 1
            continue

        # Find the newly created or most recent pending record
        records = airtable.list_records([FIELD_LAYOUT, FIELD_FURNITURE_ITEM_1, FIELD_FURNITURE_ITEM_2, FIELD_ITEM_NAME_1, FIELD_ITEM_NAME_2, FIELD_STATUS, "Story This or That (1)", "This or That Converted"])
        final_field = resolve_final_field(airtable.table_fields())
        eligible = [
            r for r in records
            if (r.get("fields", {}).get(FIELD_FURNITURE_ITEM_1) or r.get("fields", {}).get("Furniture Item1"))
            and not r.get("fields", {}).get(final_field)
        ]

        if not eligible:
            print(f"[INFO] No pending records eligible for generation after scrape on Row {row_idx}.")
            continue

        target_record = eligible[-1]  # Take the newest eligible row
        gen_ok = run_single_record_generation(fal, airtable, target_record, label, model=model)
        if gen_ok:
            successes += 1
            print(f"[ROW {row_idx} COMPLETE] 1 row scraped & story generated successfully!")
        else:
            print(f"[ROW {row_idx} FAILED] Generation failed for row {target_record['id']}.")

    print("\n" + "=" * 80)
    print(f"[COMPLETE] PIPELINE RUN FINISHED: {successes}/{count} row(s) completed successfully.")
    print("=" * 80 + "\n")
    return successes == count


def main(argv=None) -> int:
    args = parse_args(argv)
    canonical_targets = [
        "chandeliers",
        "pendant_lights",
        "floor_lamp",
        "cluster_chandelier",
        "table_lamps",
        "wall_lights",
    ]
    targets = canonical_targets if args.target == "all" else [args.target]
    all_ok = True
    for target in targets:
        ok = run_row_by_row_pipeline(
            target_key=target,
            count=args.count,
            style=args.style,
            mode=args.mode,
            record_id=args.record_id,
            table_id_override=args.table_id,
            model=args.model,
        )
        if not ok:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        sys.exit(2)
