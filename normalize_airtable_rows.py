"""CLI: migrate legacy multi-product Airtable rows to one product per row.

Legacy rows packed several products into numbered slots (SKU2/Furniture Item2,
...). This walks each source row, gives every packed slot a row of its own, and
only then clears the slot it migrated -- and only once the new row has been
read back and verified, so an interrupted run never loses a product.

Dry run by default; pass --execute to write.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from content_automation.airtable_client import AirtableClient
from content_automation.akeneo_client import AkeneoClient, metadata_from_product
from content_automation.config import TABLES, load_settings
from content_automation.errors import AutomationError
from content_automation.fields import SLOT_COUNT, furniture_field, sku_field


# Tables known to still contain packed legacy rows.
LEGACY_TABLES = (
    "pendant_lights",
    "floor_lamps",
    "wall_sconces",
    "cluster_chandeliers",
)

# Slot 0 is the row's own product; slots 1.. are the packed extras to migrate.
FIRST_PACKED_SLOT = 1

PRIMARY_FIELDS = {
    "SKU": "singleLineText",
    "Item Name": "singleLineText",
    "Furniture Item": "multipleAttachments",
    "Product Type": "singleLineText",
    "Measurement": "singleLineText",
}

METADATA_FIELDS = ("Item Name", "Product Type", "Measurement")

VERIFY_ATTEMPTS = 6


@dataclass(frozen=True)
class PackedSlot:
    """One product sharing a legacy row with others."""

    source_id: str
    slot: int
    sku: str
    attachment: dict[str, Any]

    @property
    def label(self) -> str:
        return f"{self.source_id}:slot-{self.slot + 1}"

    @property
    def filename(self) -> str:
        return str(self.attachment.get("filename") or f"{self.sku}.jpg")

    def target_fields(self, metadata: dict[str, str]) -> dict[str, Any]:
        return {
            "SKU": self.sku,
            "Item Name": metadata["Item Name"],
            "Product Type": metadata["Product Type"],
            "Measurement": metadata["Measurement"],
            "Furniture Item": [
                {"url": self.attachment.get("url"), "filename": self.filename}
            ],
        }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Normalize legacy Airtable rows to one product per row."
    )
    parser.add_argument("--category", choices=(*LEGACY_TABLES, "all"), default="all")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write changes. Without it the run only reports what it would do.",
    )
    return parser.parse_args(argv)


def verify_target(
    client: AirtableClient,
    record_id: str,
    sku: str,
    expected_filename: str,
    *,
    attempts: int = VERIFY_ATTEMPTS,
) -> bool:
    """Read a row back until it shows the expected SKU and attachment.

    Airtable attachment writes settle asynchronously, so a freshly written row
    can briefly read back empty. Nothing is cleared until this returns True.
    """
    for attempt in range(attempts):
        fields = client.get_record(record_id).get("fields", {})
        attachments = fields.get("Furniture Item") or []
        matches = (
            str(fields.get("SKU") or "").strip() == sku
            and bool(attachments)
            and str(attachments[0].get("filename") or "") == expected_filename
        )
        if matches:
            return True
        if attempt < attempts - 1:
            time.sleep(1)
    return False


def packed_slots(record: dict[str, Any]) -> list[PackedSlot]:
    """Every migratable extra product on one legacy row."""
    source_id = str(record["id"])
    fields = record.get("fields", {})
    slots = []
    for slot in range(FIRST_PACKED_SLOT, SLOT_COUNT):
        sku = str(fields.get(sku_field(slot)) or "").strip()
        attachments = fields.get(furniture_field(slot)) or []
        if sku and attachments:
            slots.append(
                PackedSlot(
                    source_id=source_id,
                    slot=slot,
                    sku=sku,
                    attachment=attachments[0],
                )
            )
    return slots


def _index_by_identity(
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Index rows by their own SKU and by attachment filename.

    Both are needed to recognise a target this migration already created, so a
    re-run resumes instead of duplicating.
    """
    by_sku = {
        str(record.get("fields", {}).get("SKU") or "").strip(): record
        for record in records
        if record.get("fields", {}).get("SKU")
    }
    by_filename = {
        str(attachment.get("filename") or ""): record
        for record in records
        for attachment in (record.get("fields", {}).get("Furniture Item") or [])
        if attachment.get("filename")
    }
    return by_sku, by_filename


def _backfill_primary_metadata(
    client: AirtableClient,
    akeneo: AkeneoClient | None,
    record: dict[str, Any],
    *,
    execute: bool,
) -> None:
    """Fill in Item Name/Product Type/Measurement for the row's own product."""
    source_id = str(record["id"])
    fields = record.get("fields", {})
    sku = str(fields.get("SKU") or "").strip()
    if not sku or not (fields.get("Furniture Item") or []):
        return
    if all(str(fields.get(name) or "").strip() for name in METADATA_FIELDS):
        return

    if not execute:
        print(f"[PLAN] {source_id}: backfill metadata for {sku}")
        return

    assert akeneo is not None
    try:
        client.update_record(source_id, metadata_from_product(akeneo.get_product(sku)))
        print(f"[METADATA] {source_id}: backfilled {sku}")
    except Exception as error:
        print(f"[ERROR] {source_id}: primary metadata failed: {error}")


def _migrate_slot(
    client: AirtableClient,
    akeneo: AkeneoClient | None,
    slot: PackedSlot,
    existing: dict[str, Any] | None,
    *,
    execute: bool,
) -> bool:
    """Give one packed slot a row of its own. True once verified."""
    if not execute:
        if existing is not None:
            print(f"[RESUME] {slot.label} -> {existing['id']}")
        else:
            print(f"[PLAN] {slot.label}: create one row for SKU {slot.sku}")
        return False

    assert akeneo is not None

    if existing is not None:
        target_id = str(existing["id"])
        if verify_target(client, target_id, slot.sku, slot.filename, attempts=1):
            print(f"[RESUME] {slot.label} -> {target_id}")
            return True
        # A target exists but does not match; repair it rather than duplicate.
        try:
            metadata = metadata_from_product(akeneo.get_product(slot.sku))
            client.update_record(target_id, slot.target_fields(metadata))
        except Exception as error:
            print(f"[ERROR] Existing target repair failed for {slot.label}: {error}")
            return False
        if not verify_target(client, target_id, slot.sku, slot.filename):
            print(f"[ERROR] Repaired target failed verification: {slot.label}")
            return False
        print(f"[REPAIR] {slot.label} -> {target_id}")
        return True

    try:
        metadata = metadata_from_product(akeneo.get_product(slot.sku))
    except Exception as error:
        print(f"[ERROR] {slot.label}: Akeneo metadata failed: {error}")
        return False

    target_id = str(client.create_record(slot.target_fields(metadata))["id"])
    if not verify_target(client, target_id, slot.sku, slot.filename):
        print(f"[ERROR] New target failed verification: {slot.label}")
        return False
    print(f"[OK] {slot.label} -> {target_id}")
    return True


def _prepare_table(
    client: AirtableClient,
    *,
    execute: bool,
    backup_root: Path,
) -> list[str]:
    """Back up, ensure the one-product-per-row columns, and list the rows."""
    if execute:
        json_path, csv_path, _ = client.export_backup(backup_root)
        print(f"[BACKUP] {json_path}")
        print(f"[BACKUP] {csv_path}")

    if missing := client.ensure_fields(PRIMARY_FIELDS, execute=execute):
        verb = "created" if execute else "would create"
        print(f"[SCHEMA] {client.table.label}: {verb} {', '.join(missing)}")

    schema = client.schema(refresh=execute)
    fields = [
        name
        for slot in range(SLOT_COUNT)
        for name in (sku_field(slot), furniture_field(slot))
        if name in schema
    ]
    fields.extend(name for name in PRIMARY_FIELDS if name in schema)
    return fields


def normalize_table(
    client: AirtableClient,
    akeneo: AkeneoClient | None,
    *,
    execute: bool,
    backup_root: Path,
) -> tuple[int, int]:
    """Normalize one table. Returns (slots planned, slots migrated)."""
    fields = _prepare_table(client, execute=execute, backup_root=backup_root)
    records = client.list_records(fields=fields)
    by_sku, by_filename = _index_by_identity(records)

    planned = 0
    migrated = 0
    for record in records:
        source_id = str(record["id"])
        _backfill_primary_metadata(client, akeneo, record, execute=execute)

        cleared: dict[str, Any] = {}
        for slot in packed_slots(record):
            planned += 1
            existing = by_sku.get(slot.sku) or by_filename.get(slot.filename)
            if existing is not None and str(existing.get("id")) == source_id:
                existing = None

            if not _migrate_slot(client, akeneo, slot, existing, execute=execute):
                continue

            cleared[sku_field(slot.slot)] = ""
            cleared[furniture_field(slot.slot)] = []
            migrated += 1

        if execute and cleared:
            client.update_record(source_id, cleared)
            print(f"[CLEAR] {source_id}: cleared {len(cleared) // 2} verified slots")

    return planned, migrated


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    settings.require({"airtable"})
    if args.execute:
        settings.require({"akeneo"})

    categories = LEGACY_TABLES if args.category == "all" else (args.category,)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = settings.workspace / "backups" / f"airtable-normalization-{timestamp}"

    akeneo = (
        AkeneoClient(
            settings.akeneo_host,
            settings.akeneo_client_id,
            settings.akeneo_secret,
            settings.akeneo_username,
            settings.akeneo_password,
        )
        if args.execute
        else None
    )

    total_planned = 0
    total_migrated = 0
    for category in categories:
        table = TABLES[category]
        print(f"\n[{table.label}] {table.table_id}")
        planned, migrated = normalize_table(
            AirtableClient(settings.airtable_token, settings.airtable_base_id, table),
            akeneo,
            execute=args.execute,
            backup_root=backup_root,
        )
        total_planned += planned
        total_migrated += migrated

    if args.execute:
        print(f"\n[COMPLETE] migrated/cleared {total_migrated} verified legacy slots.")
    else:
        print(f"\n[DRY RUN] {total_planned} legacy slots would be normalized.")
        print(
            "[DRY RUN] No backup was written and no Airtable fields or rows "
            "were changed."
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
