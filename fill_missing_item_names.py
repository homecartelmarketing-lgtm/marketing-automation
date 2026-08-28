"""CLI: backfill Item Name on legacy one-SKU-per-row records.

Only touches tables still on the pre-slot "SKUs" schema; anything else is a
no-op. Uses the shared Airtable and Akeneo clients rather than its own.
"""

from __future__ import annotations

import argparse
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.errors import AutomationError
from content_automation.fields import ITEM_NAME_FIELD, LEGACY_SKU_FIELD
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
    product_item,
)
from content_automation.scraping.categories import SCRAPE_CATEGORIES


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Backfill Item Name on legacy Airtable rows"
    )
    parser.add_argument("--category", "-c", choices=SCRAPE_CATEGORIES, default=None)
    return parser.parse_args(argv)


def legacy_records(airtable: ScrapeAirtableClient) -> list[dict]:
    """Rows needing a name, or [] when the table is not on the legacy schema."""
    fields = airtable.known_field_names()
    if not {LEGACY_SKU_FIELD, ITEM_NAME_FIELD}.issubset(fields):
        print("[SKIP] Configured table does not use the legacy SKUs/Item Name schema")
        return []
    records = airtable.list_records([LEGACY_SKU_FIELD, ITEM_NAME_FIELD])
    return [
        record
        for record in records
        if record.get("fields", {}).get(LEGACY_SKU_FIELD)
        and not str(record.get("fields", {}).get(ITEM_NAME_FIELD) or "").strip()
    ]


def resolve_item_names(akeneo: AkeneoClient, records: list[dict]) -> list[tuple[str, str]]:
    """Look each row's SKU up in Akeneo, returning (record_id, item_name)."""
    resolved: list[tuple[str, str]] = []
    for record in records:
        sku = record.get("fields", {}).get(LEGACY_SKU_FIELD)
        if not sku:
            continue
        item = product_item(akeneo.find_product(sku))
        if item:
            resolved.append((record["id"], item.item_name))
    return resolved


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_scrape_settings(category_code=args.category)
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        settings.airtable_table_id,
    )

    records = legacy_records(airtable)
    if not records:
        return 0
    print(f"[INFO] Found {len(records)} legacy records missing Item Name")

    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=settings.channel_name,
    )
    akeneo.authenticate()

    updates = resolve_item_names(akeneo, records)
    if updates:
        airtable.update_records(
            [(record_id, {ITEM_NAME_FIELD: name}) for record_id, name in updates]
        )
    else:
        print("[OK] No legacy Item Name updates required")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
