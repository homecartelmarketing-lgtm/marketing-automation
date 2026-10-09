"""Provision This Mood Every Night Reel table schema (tblDa5UOTUTlU1Xxy).

Idempotent: creates only missing columns and reconciles choices. Safe to re-run.

Usage:
    python scripts/ops/provision_this_mood_every_night_fields.py
    python scripts/ops/provision_this_mood_every_night_fields.py --table-id tblDa5UOTUTlU1Xxy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.scraping import ScrapeAirtableClient

DEFAULT_TABLE_ID = "tblDa5UOTUTlU1Xxy"

STATUS_FIELD = "Status"
STATUS_CHOICES = (
    "Standby",
    "In progress",
    "Interior Generated",
    "Interior Analyzed",
    "Prompt Generated",
    "Blended Image Generated",
    "Kling Video Generated",
    "Generation Failed Via Kling",
    "Music Generated",
    "Done",
    "Complete",
    "Posted",
    "Scheduled",
    "Discard",
    "For Manual",
)

SLOTS = tuple(range(1, 8))  # 7 slots

# Non-product columns the This Mood Every Night Reel pipeline reads/writes.
STANDARD_FIELDS: dict[str, str] = {
    "Foreign Key ID": "singleLineText",
    "Moodboard ID": "singleLineText",
    "Interior Prompt": "multilineText",
    "Interior JSON": "multilineText",
    "Scraped Items": "multilineText",
    "Music Generated": "multipleAttachments",
    "Outro": "multipleAttachments",
    "Final Video": "multipleAttachments",
    "Blended Image with Name text": "multipleAttachments",
}

for _slot in SLOTS:
    STANDARD_FIELDS[f"Furniture Item{_slot}"] = "multipleAttachments"
    STANDARD_FIELDS[f"Item Name{_slot}"] = "singleLineText"
    STANDARD_FIELDS[f"SKU{_slot}"] = "multilineText"
    STANDARD_FIELDS[f"Interior{_slot}"] = "multipleAttachments"
    STANDARD_FIELDS[f"Interior Prompt{_slot}"] = "multilineText"
    STANDARD_FIELDS[f"Interior Analysis{_slot}"] = "multilineText"
    STANDARD_FIELDS[f"Generated Prompt{_slot}"] = "multilineText"
    STANDARD_FIELDS[f"Blended Image{_slot}"] = "multipleAttachments"
    STANDARD_FIELDS[f"Kling Video{_slot}"] = "multipleAttachments"

OPTION_FIELDS: dict[str, tuple[str, dict[str, object]]] = {
    "Date and Time Generated": (
        "dateTime",
        {
            "dateFormat": {"name": "iso"},
            "timeFormat": {"name": "24hour"},
            "timeZone": "Asia/Manila",
        },
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision This Mood Every Night Reel Airtable fields")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help="This Mood Every Night table id")
    args = parser.parse_args(argv)

    settings = load_settings()
    settings.require({"airtable"})

    airtable = ScrapeAirtableClient(
        token=settings.airtable_token,
        base_id=settings.airtable_base_id,
        table_id=args.table_id,
    )

    print("=" * 68)
    print(f" This Mood Every Night field provisioning | table {args.table_id}")
    print(f" Base: {settings.airtable_base_id}")
    print("=" * 68)

    before = set(airtable.known_field_names(refresh=True))

    airtable.ensure_fields(STANDARD_FIELDS)
    print(f"[OK] Ensured standard columns ({len(STANDARD_FIELDS)} fields)")

    for name, (field_type, options) in OPTION_FIELDS.items():
        if name in airtable.known_field_names():
            print(f"[OK] Column '{name}' ({field_type}) already present")
            continue
        response = airtable._request(
            "POST",
            airtable.fields_url,
            json={"name": name, "type": field_type, "options": options},
        )
        if not response.ok:
            raise AutomationError(
                f"Create Airtable {field_type} field {name} failed "
                f"({response.status_code}): {response.text}"
            )
        airtable._schema = None
        print(f"[OK] Created column '{name}' ({field_type})")

    airtable.ensure_single_select_options(STATUS_FIELD, STATUS_CHOICES)
    print(f"[OK] Ensured single-select '{STATUS_FIELD}' with {len(STATUS_CHOICES)} choices")

    after = airtable.known_field_names(refresh=True)
    schema = airtable.table_fields()
    created = sorted(after - before)
    print("\n[RESULT] Newly created columns:")
    for name in created:
        print(f"  + {name}")
    if not created:
        print("  (none - schema was already complete)")

    print(f"\n[OK] Total field count on table: {len(schema)}")
    print("[OK] This Mood Every Night Reel table schema is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
