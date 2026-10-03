#!/usr/bin/env python3
"""Prune stale generated media in the output/ directory.

Safety rules:
- Dry-run by default; requires --execute to delete.
- Retains files modified within --max-age-days (default: 30 days).
- Always preserves at least the latest --keep-recent files (default: 5) per directory.

Usage::
    # Dry run (inspect what would be pruned):
    python scripts/ops/prune_output.py

    # Live execution:
    python scripts/ops/prune_output.py --execute

    # Custom threshold (older than 14 days, keep latest 3):
    python scripts/ops/prune_output.py --execute --max-age-days 14 --keep-recent 3
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "output"


def prune_directory(
    target_dir: Path,
    max_age_days: int = 30,
    keep_recent: int = 5,
    execute: bool = False,
) -> tuple[int, int]:
    """Prune files older than max_age_days while keeping keep_recent latest files.

    Returns (files_deleted, bytes_freed).
    """
    if not target_dir.is_dir():
        print(f"Directory {target_dir} does not exist.")
        return 0, 0

    now = time.time()
    cutoff_time = now - (max_age_days * 86400)

    # Collect all regular files recursively
    all_files: list[Path] = [p for p in target_dir.rglob("*") if p.is_file()]
    if not all_files:
        print(f"No files found in {target_dir}.")
        return 0, 0

    # Sort files by modification time (newest first)
    all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Files to evaluate: everything after keep_recent
    eligible_for_deletion = all_files[keep_recent:]
    to_delete: list[Path] = []
    bytes_to_free = 0

    for f in eligible_for_deletion:
        try:
            stat = f.stat()
            if stat.st_mtime < cutoff_time:
                to_delete.append(f)
                bytes_to_free += stat.st_size
        except OSError:
            pass

    print(f"Found {len(all_files)} total files in {target_dir} ({sum(f.stat().st_size for f in all_files) / (1024*1024):.1f} MB).")
    print(f"Preserving top {min(len(all_files), keep_recent)} newest files regardless of age.")
    print(f"Cutoff age: {max_age_days} days. Eligible for pruning: {len(to_delete)} files ({bytes_to_free / (1024*1024):.1f} MB).")

    if not execute:
        print("\n[DRY RUN] No files deleted. Pass --execute to delete.")
        return 0, 0

    deleted_count = 0
    freed_bytes = 0
    for f in to_delete:
        try:
            size = f.stat().st_size
            f.unlink()
            deleted_count += 1
            freed_bytes += size
        except OSError as e:
            print(f"[WARN] Failed to delete {f}: {e}")

    print(f"\n[OK] Pruned {deleted_count} files. Freed {freed_bytes / (1024*1024):.1f} MB.")
    return deleted_count, freed_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune stale media from output/")
    parser.add_argument("--execute", action="store_true", help="Perform live deletion")
    parser.add_argument("--dry-run", action="store_true", help="Dry run only (default behavior)")
    parser.add_argument("--max-age-days", type=int, default=30, help="Max file age in days (default: 30)")
    parser.add_argument("--keep-recent", type=int, default=5, help="Number of newest files to always keep (default: 5)")
    args = parser.parse_args()

    print("=" * 70)
    print("HOMECARTEL OUTPUT DIRECTORY PRUNER")
    print("=" * 70)
    prune_directory(
        target_dir=OUTPUT_DIR,
        max_age_days=args.max_age_days,
        keep_recent=args.keep_recent,
        execute=args.execute,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
