"""Provision the Ad Cover Chandelier table schema (tblwIsDGZBPuYJV2Z).

Idempotent: creates only the columns that are missing and reconciles any that
exist with the wrong type. Safe to re-run.

Usage::

    python scripts/ops/ensure_ad_cover_fields.py
    python scripts/ops/ensure_ad_cover_fields.py --table-id tblwIsDGZBPuYJV2Z
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_automation.config import TABLES, load_settings
from content_automation.errors import AutomationError
from content_automation.fields import furniture_field, item_name_field, price_field, sku_field
from content_automation.scraping import ScrapeAirtableClient

DEFAULT_TABLE_ID = TABLES["chandelier_ad_cover"].table_id

STATUS_FIELD = "Status"
STATUS_CHOICES = (
    "Standby",
    "Ad Cover Interior Generated",
    "Ad Cover Blended Image Generated",
    "Ad Cover Blended Image Story Generated",
    "Ad Cover Converted Image Generated",
    "Ad Cover Converted Image Story Generated",
    "Complete",
    "Discarded",
)

EXPECTED_FIELDS = (
    ("Foreign Key ID", "singleLineText", None),
    ("ID", "singleLineText", None),
    (
        STATUS_FIELD,
        "singleSelect",
        {"choices": [{"name": choice} for choice in STATUS_CHOICES]},
    ),
    ("Date and Time Generated", "dateTime", {"timeZone": "Asia/Manila", "dateFormat": {"name": "iso"}}),
    ("Blending Prompt", "multilineText", None),
    ("Ad Cover Interior", "multipleAttachments", None),
    ("Ad Cover Blended Image", "multipleAttachments", None),
    ("Ad Cover Blended Image Story", "multipleAttachments", None),
    ("Ad Cover Converted Image", "multipleAttachments", None),
    ("Ad Cover Converted Image Story", "multipleAttachments", None),
    (furniture_field(1), "multipleAttachments", None),
    (item_name_field(1), "singleLineText", None),
    (sku_field(1), "singleLineText", None),
    (price_field(1), "number", {"precision": 0}),
    ("Category Code 1", "singleLineText", None),
)


def ensure_ad_cover_fields(table_id: str | None = None) -> None:
    settings = load_settings()
    settings.require({"airtable"})

    resolved_table_id = table_id or DEFAULT_TABLE_ID
    client = ScrapeAirtableClient(
        token=settings.airtable_token,
        base_id=settings.airtable_base_id,
        table_id=resolved_table_id,
    )

    url = f"{client.meta_base_url}/bases/{client.base_id}/tables"
    response = client.session.get(url, headers=client._headers())
    if not response.ok:
        raise AutomationError(
            f"Failed to fetch base schema: {response.status_code} {response.text}"
        )

    target_table = None
    for table in response.json().get("tables", []):
        if table.get("id") == resolved_table_id:
            target_table = table
            break

    if not target_table:
        raise AutomationError(f"Table '{resolved_table_id}' not found in base schema.")

    existing_fields = {field["name"]: field for field in target_table.get("fields", [])}
    print(f"Table: {target_table.get('name')} ({resolved_table_id})")
    print(f"Existing fields: {len(existing_fields)}")

    created = 0
    updated = 0

    for name, field_type, options in EXPECTED_FIELDS:
        if name not in existing_fields:
            payload: dict = {"name": name, "type": field_type}
            if options:
                payload["options"] = options

            create_url = f"{client.meta_base_url}/bases/{client.base_id}/tables/{resolved_table_id}/fields"
            create_resp = client.session.post(create_url, headers=client._headers(), json=payload)
            if create_resp.ok:
                print(f"  [CREATED] {name} ({field_type})")
                created += 1
            else:
                print(f"  [FAIL] Could not create {name}: {create_resp.status_code} {create_resp.text}")
        else:
            current = existing_fields[name]
            if name == STATUS_FIELD and field_type == "singleSelect" and options:
                current_choices = {c["name"] for c in current.get("options", {}).get("choices", [])}
                missing_choices = [c for c in options["choices"] if c["name"] not in current_choices]
                if missing_choices:
                    merged = list(current.get("options", {}).get("choices", [])) + missing_choices
                    patch_url = f"{client.meta_base_url}/bases/{client.base_id}/tables/{resolved_table_id}/fields/{current['id']}"
                    patch_resp = client.session.patch(
                        patch_url,
                        headers=client._headers(),
                        json={"options": {"choices": merged}},
                    )
                    if patch_resp.ok:
                        print(f"  [UPDATED] {name} added choices: {[c['name'] for c in missing_choices]}")
                        updated += 1
                    else:
                        print(f"  [WARN] Failed to update choices for {name}: {patch_resp.text}")
                else:
                    print(f"  [OK] {name} (choices intact)")
            else:
                print(f"  [OK] {name} ({current.get('type')})")

    print(f"\nDone: {created} created, {updated} updated.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure schema for Ad Cover table in Airtable.")
    parser.add_argument("--table-id", default=None, help="Airtable table ID (defaults to chandelier_ad_cover).")
    args = parser.parse_args()
    ensure_ad_cover_fields(table_id=args.table_id)


if __name__ == "__main__":
    main()
