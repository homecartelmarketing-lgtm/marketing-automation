"""Verify the Ad Cover end-to-end result in Airtable.

Usage::

    python scripts/ops/verify_ad_cover_row.py
    python scripts/ops/verify_ad_cover_row.py [record_id]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_automation.config import load_settings
from content_automation.scraping import ScrapeAirtableClient

settings = load_settings()
settings.require({"airtable"})

airtable = ScrapeAirtableClient(
    token=settings.airtable_token,
    base_id=settings.airtable_base_id,
    table_id="tblwIsDGZBPuYJV2Z",
)

records = airtable.list_records(
    [
        "Foreign Key ID",
        "ID",
        "Status",
        "Date and Time Generated",
        "Ad Cover Interior",
        "Ad Cover Blended Image",
        "Ad Cover Blended Image Story",
        "Ad Cover Converted Image",
        "Ad Cover Converted Image Story",
    ]
)

print(f"Total records in table: {len(records)}")

filter_id = sys.argv[1] if len(sys.argv) > 1 else None

for r in records:
    rec_id = r.get("id")
    if filter_id and rec_id != filter_id and r.get("fields", {}).get("ID") != filter_id:
        continue

    f = r.get("fields", {})
    fk = f.get("Foreign Key ID", "-")
    item_id = f.get("ID", "-")
    status = f.get("Status", "-")
    dt = f.get("Date and Time Generated", "-")

    interior = f.get("Ad Cover Interior") or []
    blended = f.get("Ad Cover Blended Image") or []
    blended_story = f.get("Ad Cover Blended Image Story") or []
    converted = f.get("Ad Cover Converted Image") or []
    converted_story = f.get("Ad Cover Converted Image Story") or []

    print("-" * 60)
    print(f"Record: {rec_id} | FK: {fk} | ID: {item_id}")
    print(f"  Status: {status} | Date: {dt}")
    print(f"  Interior (9:16):  {len(interior)} file(s) - {[x.get('filename') for x in interior]}")
    print(f"  Blended (1:1):    {len(blended)} file(s) - {[x.get('filename') for x in blended]}")
    print(f"  Blended (9:16):   {len(blended_story)} file(s) - {[x.get('filename') for x in blended_story]}")
    print(f"  Converted (1:1):  {len(converted)} file(s) - {[x.get('filename') for x in converted]}")
    print(f"  Converted (9:16): {len(converted_story)} file(s) - {[x.get('filename') for x in converted_story]}")
