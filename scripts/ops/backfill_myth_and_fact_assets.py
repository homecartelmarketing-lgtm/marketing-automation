"""Backfill missing Logo Watermark and Outro Layout in Chandelier Myth & Fact Story table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from content_automation.airtable_client import AirtableClient
from content_automation.config import TABLES, load_settings
from content_automation.models import LocalImage


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Backfill 'Logo Watermark For Story' and 'Outro Layout' on Myth & Fact Story records."
    )
    parser.add_argument(
        "--record-id",
        "-r",
        action="append",
        default=[],
        help="Target specific record ID(s). Repeatable. Default all records.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect records and preview changes without modifying Airtable.",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Overwrite existing attachments even if field is already populated.",
    )
    return parser.parse_args(argv)


def attach_file(client: AirtableClient, record_id: str, field_name: str, path: Path) -> None:
    img = LocalImage(path, path.name)
    client.clear_attachment_field(record_id, field_name)
    client.upload_attachment(record_id, field_name, img)
    client.verify_attachment_filenames(record_id, field_name, [img.filename])


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    settings.require({"airtable"})

    table_def = TABLES["chandelier_myth_and_fact_story"]
    client = AirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_def,
    )

    logo_path = Path("assets/homecartel_logo.png")
    outro_path = Path("assets/Outro-Myth-Fact.png")

    if not logo_path.is_file():
        print(f"[ERROR] Missing logo file: {logo_path}")
        return 1
    if not outro_path.is_file():
        print(f"[ERROR] Missing outro layout file: {outro_path}")
        return 1

    print("=" * 64)
    print(" [HOMECARTEL] MYTH & FACT STORY ASSET BACKFILL")
    print(f" Table   : {table_def.label} ({table_def.table_id})")
    print(f" Mode    : {'DRY RUN (Preview)' if args.dry_run else 'LIVE EXECUTION'}")
    print(f" Logo    : {logo_path}")
    print(f" Outro   : {outro_path}")
    print("=" * 64)

    records = client.list_records()
    if args.record_id:
        records = [r for r in records if r.get("id") in args.record_id]

    print(f"\nProcessing {len(records)} record(s)...")

    logo_updated = 0
    outro_updated = 0

    for rec in records:
        record_id = rec.get("id")
        fields = rec.get("fields", {})
        item_name = fields.get("Item Name") or fields.get("SKU") or record_id

        # 1. Logo Watermark For Story
        existing_logo = fields.get("Logo Watermark For Story") or []
        needs_logo = False
        if not existing_logo or args.force_overwrite:
            needs_logo = True
        else:
            first_fn = str(existing_logo[0].get("filename") or "").lower()
            if "homecartel_logo" not in first_fn:
                needs_logo = True

        if needs_logo:
            print(f"  [LOGO NEEDED] Record {record_id} ('{item_name}'): existing={[a.get('filename') for a in existing_logo]}")
            if not args.dry_run:
                try:
                    attach_file(client, record_id, "Logo Watermark For Story", logo_path)
                    print(f"  [OK] Uploaded 'homecartel_logo.png' -> 'Logo Watermark For Story' for {record_id}")
                    logo_updated += 1
                except Exception as e:
                    print(f"  [ERROR] Failed uploading logo for {record_id}: {e}")
            else:
                logo_updated += 1
        else:
            print(f"  [LOGO SKIP] Record {record_id} already has correct logo.")

        # 2. Outro Layout
        existing_outro = fields.get("Outro Layout") or []
        needs_outro = False
        if not existing_outro or args.force_overwrite:
            needs_outro = True
        else:
            first_fn = str(existing_outro[0].get("filename") or "").lower()
            if "outro-myth-fact" not in first_fn:
                needs_outro = True

        if needs_outro:
            print(f"  [OUTRO NEEDED] Record {record_id} ('{item_name}'): existing={[a.get('filename') for a in existing_outro]}")
            if not args.dry_run:
                try:
                    attach_file(client, record_id, "Outro Layout", outro_path)
                    print(f"  [OK] Uploaded 'Outro-Myth-Fact.png' -> 'Outro Layout' for {record_id}")
                    outro_updated += 1
                except Exception as e:
                    print(f"  [ERROR] Failed uploading outro layout for {record_id}: {e}")
            else:
                outro_updated += 1
        else:
            print(f"  [OUTRO SKIP] Record {record_id} already has correct outro layout.")

    print("\n" + "=" * 64)
    print(f" Backfill Summary: {logo_updated} logo(s) updated, {outro_updated} outro layout(s) updated.")
    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
