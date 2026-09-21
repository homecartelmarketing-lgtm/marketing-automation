"""Scratchpad and temporary file lifecycle manager for containerized environments (Zoho Catalyst / Docker).

Prevents container disk space exhaustion by:
1. Purging temporary files in output/temp and output/temp_uploads after upload.
2. Providing a scheduled/maintenance cleanup routine that purges files older than a specified threshold.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any

LOGGER = logging.getLogger(__name__)

MARKETING_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = MARKETING_DIR / "output"

TEMP_DIRS = [
    OUTPUT_DIR / "temp",
    OUTPUT_DIR / "temp_uploads",
    OUTPUT_DIR / "tagged_images",
    OUTPUT_DIR / "item_tag_preview",
    OUTPUT_DIR / "style_this_preview",
]


def safe_remove_file(path: str | Path | None) -> bool:
    """Safely delete a temporary file after upload, ignoring missing files."""
    if not path:
        return False
    try:
        p = Path(path)
        if p.is_file():
            p.unlink(missing_ok=True)
            return True
    except Exception as err:
        LOGGER.warning(f"Could not delete temporary file {path}: {err}")
    return False


def prune_scratchpad(
    max_age_hours: float = 24.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scan temporary directories and delete files older than max_age_hours."""
    cutoff_time = time.time() - (max_age_hours * 3600.0)
    deleted_count = 0
    deleted_bytes = 0
    scanned_count = 0

    for directory in TEMP_DIRS:
        if not directory.exists() or not directory.is_dir():
            continue

        for root, _, files in os.walk(directory):
            for file_name in files:
                file_path = Path(root) / file_name
                scanned_count += 1
                try:
                    stats = file_path.stat()
                    if stats.st_mtime < cutoff_time:
                        file_size = stats.st_size
                        if not dry_run:
                            file_path.unlink(missing_ok=True)
                        deleted_count += 1
                        deleted_bytes += file_size
                except Exception as err:
                    LOGGER.debug(f"Error checking {file_path}: {err}")

    mb_freed = round(deleted_bytes / (1024 * 1024), 2)
    return {
        "status": "success",
        "scanned_files": scanned_count,
        "deleted_files": deleted_count,
        "bytes_freed": deleted_bytes,
        "mb_freed": mb_freed,
        "dry_run": dry_run,
    }
