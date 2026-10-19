#!/usr/bin/env python3
"""CLI runner for Virtual Staging Reel pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from generate_virtual_staging_reel_pipeline import main

if __name__ == "__main__":
    sys.exit(main())
