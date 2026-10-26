"""Bulk-provision the scale-audit columns across room-blend tables.

Idempotent: creates `Scale Audit` (multilineText), `Scale Check` and
`Scale Retry` (singleSelect) only where they are missing. Safe to re-run.

Table ids are discovered the same way as `provision_caption_fields.py`.
Banner tables and the podium-only Product Showcase table are skipped because
they never run a room blend.

Usage:
    python scripts/ops/provision_scale_fields.py --dry-run
    python scripts/ops/provision_scale_fields.py --table-id tblJpEtBudQZda319
    python scripts/ops/provision_scale_fields.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from content_automation.config import TABLES, load_settings
from content_automation.foreign_key import TABLE_PREFIX_MAP
from content_automation.scale_guard import (
    SCALE_AUDIT_FIELD,
    SCALE_CHECK_CHOICES,
    SCALE_CHECK_FIELD,
    SCALE_RETRY_CHOICES,
    SCALE_RETRY_FIELD,
    ensure_scale_fields,
)
from content_automation.scraping import ScrapeAirtableClient

WELL_KNOWN_TABLE_IDS: tuple[str, ...] = (
    "tblJpEtBudQZda319",  # OATL reel
    "tblUFR6OvFQaHnG1V",  # Sketch to Real chandelier
    "tblSALsUd5MXXnkp6",  # Sketch to Real pendant
    "tblhq1rz9CVCD7yiR",  # RBU reel
    "tblqXkdDw4O7hxJS4",  # HTR reel
    "tblDa5UOTUTlU1Xxy",  # TMEN reel
    "tblPYG5Ed4XURecu6",  # VST reel
    "tblwIsDGZBPuYJV2Z",  # ADC chandelier
    "tbl27FKuDUD4FdJUR",  # ADC floor lamp
    "tblk3RfFqawHZ5Wrk",  # ADC table lamp
    "tbltouegkjgQwdr1u",  # ADC cluster chandelier
    "tbl99Cwda2Xn93giT",  # ADC pendant
    "tblUO5nybG9fIkhTT",  # ADC wall light
    "tbluMexgzcWE1pDZJ",  # ADC new collection
    "tbleQIVBooVazAyk3",  # ADC on sale
    "tblX7tpTJhfH0UXmm",  # ADC on stock
)

# No room blend, so no scale audit: banners and the podium-only showcase deck.
EXCLUDED_TABLE_IDS: frozenset[str] = frozenset(
    {
        "tblgNk1Tp6qKUcduw",  # Christmas / Sale / third banner
        "tbln0MNBaVVrZ0wrF",  # Product Showcase Feed (podium)
    }
)

TABLE_ID_RE = re.compile(r"^tbl[A-Za-z0-9]{14}$")


def is_placeholder(table_id: str) -> bool:
    return not TABLE_ID_RE.match((table_id or "").strip())


def discover_table_ids() -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def add(table_id: str | None) -> None:
        tid = (table_id or "").strip()
        if not tid or tid in seen or is_placeholder(tid):
            return
        if tid in EXCLUDED_TABLE_IDS:
            return
        seen.add(tid)
        ids.append(tid)

    for tid in TABLE_PREFIX_MAP.keys():
        add(tid)
    for cfg in TABLES.values():
        add(cfg.table_id)
        if cfg.table_env:
            add(os.getenv(cfg.table_env, ""))
    for tid in WELL_KNOWN_TABLE_IDS:
        add(tid)
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Provision scale-audit columns across room-blend tables"
    )
    parser.add_argument(
        "--table-id",
        default="",
        help="Provision a single table only (default: all discovered tables)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the tables that would be provisioned without touching Airtable",
    )
    args = parser.parse_args(argv)

    if args.table_id.strip():
        table_ids = [args.table_id.strip()]
    else:
        table_ids = discover_table_ids()

    print("=" * 68)
    print(
        f" Scale audit provisioning | '{SCALE_AUDIT_FIELD}', "
        f"'{SCALE_CHECK_FIELD}', '{SCALE_RETRY_FIELD}'"
    )
    print(f" Tables: {len(table_ids)}")
    print("=" * 68)

    if args.dry_run:
        for tid in table_ids:
            prefix = TABLE_PREFIX_MAP.get(tid, "")
            label = f"  {tid}  {prefix}" if prefix else f"  {tid}"
            print(f"[DRY-RUN] would ensure scale audit fields on{label}")
        print(f"\n[DRY-RUN] {len(table_ids)} table(s) listed, no changes made.")
        return 0

    settings = load_settings()
    settings.require({"airtable"})

    ok = 0
    failed: list[str] = []
    for tid in table_ids:
        try:
            airtable = ScrapeAirtableClient(
                token=settings.airtable_token,
                base_id=settings.airtable_base_id,
                table_id=tid,
            )
            airtable.ensure_single_select_options(SCALE_CHECK_FIELD, SCALE_CHECK_CHOICES)
            airtable.ensure_single_select_options(SCALE_RETRY_FIELD, SCALE_RETRY_CHOICES)
            ensure_scale_fields(airtable)
            print(f"[OK] {tid}: ensured scale audit fields")
            ok += 1
        except Exception as exc:  # keep going; report at the end
            print(f"[FAIL] {tid}: {exc}")
            failed.append(tid)

    print("\n[RESULT] Scale audit provisioning summary:")
    print(f"  ok: {ok} | failed: {len(failed)} | total: {len(table_ids)}")
    for tid in failed:
        print(f"  x {tid}")
    if failed:
        print("[FAIL] Some tables could not be provisioned.")
        return 1
    print(f"[OK] Scale audit fields ensured on all {ok} table(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
