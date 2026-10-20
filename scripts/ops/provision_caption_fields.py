"""Bulk-provision the universal `Caption Generated` column across all tables.

Idempotent: `ScrapeAirtableClient.ensure_fields` creates only the missing
column (and reconciles a wrong type). Safe to re-run.

Table ids are discovered from `foreign_key.TABLE_PREFIX_MAP` keys plus
`config.TABLES` values (defaults + live env overrides) plus the well-known
reel/banner ids below. Placeholders and duplicates are skipped.

Usage:
    python scripts/ops/provision_caption_fields.py --dry-run
    python scripts/ops/provision_caption_fields.py --table-id tblJpEtBudQZda319
    python scripts/ops/provision_caption_fields.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from content_automation.caption import CAPTION_FIELD, CAPTION_FIELD_TYPE
from content_automation.config import TABLES, load_settings
from content_automation.foreign_key import TABLE_PREFIX_MAP
from content_automation.scraping import ScrapeAirtableClient

# Well-known reel/banner tables (kept explicit so they are covered even if
# a mapping entry is ever renamed). ADC covers all 9 Ad Cover fixtures.
WELL_KNOWN_TABLE_IDS: tuple[str, ...] = (
    "tblJpEtBudQZda319",  # OATL reel
    "tblUFR6OvFQaHnG1V",  # Sketch to Real chandelier
    "tblSALsUd5MXXnkp6",  # Sketch to Real pendant
    "tblhq1rz9CVCD7yiR",  # RBU reel
    "tblqXkdDw4O7hxJS4",  # HTR reel
    "tblDa5UOTUTlU1Xxy",  # TMEN reel
    "tblPYG5Ed4XURecu6",  # VST reel
    "tblgNk1Tp6qKUcduw",  # XMS Christmas/Sale banner
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

# Real Airtable table ids are `tbl` + 14 base62 chars. Anything else stored
# in the maps (e.g. `tblSketchToRealReel`, `tblVirtualStagingReel`, empty
# strings) is a placeholder and must be skipped.
TABLE_ID_RE = re.compile(r"^tbl[A-Za-z0-9]{14}$")


def is_placeholder(table_id: str) -> bool:
    """True for empty values and non-Airtable-id placeholders."""
    return not TABLE_ID_RE.match((table_id or "").strip())


def discover_table_ids() -> list[str]:
    """Collect every real table id, deduped, in discovery order."""
    ids: list[str] = []
    seen: set[str] = set()

    def add(table_id: str | None) -> None:
        tid = (table_id or "").strip()
        if not tid or tid in seen or is_placeholder(tid):
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
        description="Provision Caption Generated column across all Airtable tables"
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
    print(f" Caption provisioning | field '{CAPTION_FIELD}' ({CAPTION_FIELD_TYPE})")
    print(f" Tables: {len(table_ids)}")
    print("=" * 68)

    if args.dry_run:
        for tid in table_ids:
            prefix = TABLE_PREFIX_MAP.get(tid, "")
            label = f"  {tid}  {prefix}" if prefix else f"  {tid}"
            print(f"[DRY-RUN] would ensure '{CAPTION_FIELD}' on{label}")
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
            airtable.ensure_fields({CAPTION_FIELD: CAPTION_FIELD_TYPE})
            print(f"[OK] {tid}: ensured '{CAPTION_FIELD}'")
            ok += 1
        except Exception as exc:  # keep going; report at the end
            print(f"[FAIL] {tid}: {exc}")
            failed.append(tid)

    print("\n[RESULT] Caption provisioning summary:")
    print(f"  ok: {ok} | failed: {len(failed)} | total: {len(table_ids)}")
    for tid in failed:
        print(f"  x {tid}")
    if failed:
        print("[FAIL] Some tables could not be provisioned.")
        return 1
    print(f"[OK] '{CAPTION_FIELD}' ensured on all {ok} table(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
