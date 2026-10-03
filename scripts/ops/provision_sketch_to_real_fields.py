"""Provision exact schema fields for Sketch to Real / Draw Reel tables in Airtable.

Usage:
    # Add fields to an existing table by ID:
    python scripts/ops/provision_sketch_to_real_fields.py --table-id tblXXXXXXXXXXXXXX

    # Add fields to an existing table by name:
    python scripts/ops/provision_sketch_to_real_fields.py --table-name "Chandeliers Sketch to Real Reel"

    # Automatically create a brand new table with all fields:
    python scripts/ops/provision_sketch_to_real_fields.py --create-table "Chandeliers Sketch to Real Reel"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from dotenv import dotenv_values, load_dotenv
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")

ENV_VALUES = dotenv_values(REPO_ROOT / ".env")
AIRTABLE_TOKEN = (
    os.getenv("AIRTABLE_TOKEN")
    or os.getenv("AIRTABLE_API_KEY")
    or ENV_VALUES.get("AIRTABLE_TOKEN")
    or ENV_VALUES.get("AIRTABLE_API_KEY")
)
BASE_ID = (
    os.getenv("AIRTABLE_BASE_ID")
    or ENV_VALUES.get("AIRTABLE_BASE_ID")
    or "appDM0jUDsaiThtR3"
)

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}

FIELDS_SCHEMA = [
    {"name": "Foreign Key ID", "type": "singleLineText"},
    {"name": "ID", "type": "number", "options": {"precision": 0}},
    {
        "name": "Date and Time Generated",
        "type": "dateTime",
        "options": {
            "timeZone": "Asia/Manila",
            "dateFormat": {"name": "iso"},
            "timeFormat": {"name": "24hour"},
        },
    },
    {
        "name": "Status",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Standby"},
                {"name": "In progress"},
                {"name": "Scheduled"},
                {"name": "Done"},
                {"name": "Discarded"},
                {"name": "For Manual"},
            ]
        },
    },
    {"name": "Furniture Item", "type": "multipleAttachments"},
    {"name": "SKU", "type": "singleLineText"},
    {"name": "Item Name", "type": "singleLineText"},
    {"name": "Product Type", "type": "singleLineText"},
    {"name": "Category", "type": "singleLineText"},
    {"name": "Price", "type": "singleLineText"},
    {"name": "Room Interior", "type": "multipleAttachments"},
    {"name": "Interior Prompt", "type": "multilineText"},
    {"name": "Blending Prompt", "type": "multilineText"},
    {"name": "Blended Image", "type": "multipleAttachments"},
    {"name": "Blended Image with Name text", "type": "multipleAttachments"},
    {"name": "Sketch Image", "type": "multipleAttachments"},
    {"name": "Reel Headline", "type": "singleLineText"},
    {"name": "Thumbnail with Generated Text", "type": "multipleAttachments"},
    {"name": "Raw Video", "type": "multipleAttachments"},
    {"name": "Music Generated", "type": "multipleAttachments"},
    {"name": "Outro", "type": "multipleAttachments"},
    {"name": "Final Video", "type": "multipleAttachments"},
]


def get_all_tables() -> list[dict]:
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("tables", [])


def create_table_with_fields(table_name: str) -> str:
    print(f"[*] Creating brand new table '{table_name}' in base {BASE_ID}...")
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    
    # Primary field
    primary_field = {"name": "Name", "type": "singleLineText"}
    
    # Combine primary + all other fields
    all_fields = [primary_field] + FIELDS_SCHEMA
    
    payload = {
        "name": table_name,
        "fields": all_fields,
    }
    
    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code not in (200, 201):
        print(f"[ERROR] Failed to create table: {resp.status_code} {resp.text}")
        sys.exit(1)
        
    data = resp.json()
    table_id = data["id"]
    print(f"[SUCCESS] Table '{table_name}' created successfully with ID: {table_id}")
    print(f"[SUCCESS] Total {len(data.get('fields', []))} fields provisioned!")
    return table_id


def add_fields_to_table(table_id: str, table_name: str = ""):
    print(f"[*] Fetching existing fields for table {table_id}...")
    tables = get_all_tables()
    target_table = next((t for t in tables if t["id"] == table_id), None)
    
    if not target_table:
        print(f"[ERROR] Table ID '{table_id}' not found in base {BASE_ID}!")
        sys.exit(1)
        
    t_name = target_table["name"]
    existing_field_names = {f["name"] for f in target_table.get("fields", [])}
    print(f"[*] Table '{t_name}' currently has {len(existing_field_names)} fields.")
    
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{table_id}/fields"
    
    added_count = 0
    skipped_count = 0
    
    for f in FIELDS_SCHEMA:
        fname = f["name"]
        if fname in existing_field_names:
            print(f"  [-] Field '{fname}' already exists -> skipping")
            skipped_count += 1
            continue
            
        print(f"  [+] Adding field '{fname}' ({f['type']})...", end=" ", flush=True)
        resp = requests.post(url, headers=HEADERS, json=f)
        if resp.status_code in (200, 201):
            print("OK")
            added_count += 1
        else:
            print(f"FAILED: {resp.status_code} {resp.text}")
            
    print(f"\n[DONE] Finished provisioning for '{t_name}' ({table_id})")
    print(f"       Added: {added_count} | Already existed: {skipped_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Add Sketch to Real fields to an Airtable table."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--table-id", help="Airtable Table ID (e.g. tblXXXXXXXXXXXXXX)")
    group.add_argument("--table-name", help="Existing table name in Airtable base")
    group.add_argument("--create-table", help="Name of new table to create from scratch")
    group.add_argument("--list-tables", action="store_true", help="List all tables in base")

    args = parser.parse_args()

    if not AIRTABLE_TOKEN:
        print("[ERROR] AIRTABLE_TOKEN is not configured in .env!")
        sys.exit(1)

    if args.list_tables:
        tables = get_all_tables()
        print(f"\nFound {len(tables)} tables in base {BASE_ID}:")
        for t in tables:
            print(f"  {t['id']} : {t['name']}")
        return

    if args.create_table:
        create_table_with_fields(args.create_table)
        return

    if args.table_id:
        add_fields_to_table(args.table_id)
        return

    if args.table_name:
        tables = get_all_tables()
        matches = [t for t in tables if t["name"].strip().lower() == args.table_name.strip().lower()]
        if not matches:
            print(f"[ERROR] No table found matching '{args.table_name}'")
            sys.exit(1)
        add_fields_to_table(matches[0]["id"])


if __name__ == "__main__":
    main()
