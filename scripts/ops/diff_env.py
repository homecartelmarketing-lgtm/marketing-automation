#!/usr/bin/env python3
"""Audit and reconcile environment variable drift between .env and .env.example.

Usage::
    # Scan drift:
    python scripts/ops/diff_env.py

    # Automatically synchronize missing documented keys into .env.example:
    python scripts/ops/diff_env.py --sync
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
EXAMPLE_FILE = REPO_ROOT / ".env.example"


def parse_env_keys(file_path: Path) -> dict[str, str]:
    """Parse keys and their raw line entries from an env file."""
    if not file_path.is_file():
        return {}
    keys: dict[str, str] = {}
    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = pattern.match(stripped)
            if m:
                key = m.group(1)
                keys[key] = stripped
    return keys


def sanitize_value_for_example(key: str, raw_line: str) -> str:
    """Generate a safe placeholder value for .env.example without leaking secrets."""
    key_upper = key.upper()
    if any(s in key_upper for s in ("KEY", "SECRET", "TOKEN", "PASSWORD", "PIN", "AUTH")):
        return f"{key}=your_{key.lower()}_here"
    if "TABLE_ID" in key_upper:
        return f"{key}=tblYourTableIdHere"
    if "MOODBOARD_ID" in key_upper:
        return f"{key}=your-krea-moodboard-uuid-here"
    if "PROMPT" in key_upper:
        # Generic prompt placeholder
        return f'{key}="Your custom prompt template here"'
    return f"{key}="


def diff_environments(sync: bool = False) -> int:
    if not ENV_FILE.is_file():
        print(f"[ERROR] .env file not found at {ENV_FILE}")
        return 1
    if not EXAMPLE_FILE.is_file():
        print(f"[ERROR] .env.example file not found at {EXAMPLE_FILE}")
        return 1

    env_entries = parse_env_keys(ENV_FILE)
    example_entries = parse_env_keys(EXAMPLE_FILE)

    env_keys = set(env_entries.keys())
    example_keys = set(example_entries.keys())

    only_in_env = sorted(list(env_keys - example_keys))
    only_in_example = sorted(list(example_keys - env_keys))

    # Identify debug residue
    debug_residue = [k for k in env_keys if k.startswith("TEST_") or "OVERRIDE" in k]

    print("=" * 70)
    print("HOMECARTEL ENVIRONMENT DRIFT AUDIT (.env vs .env.example)")
    print("=" * 70)
    print(f".env total keys:        {len(env_keys)}")
    print(f".env.example total keys: {len(example_keys)}")
    print(f"Keys in .env only:      {len(only_in_env)}")
    print(f"Keys in .example only:  {len(only_in_example)}")
    print("=" * 70)

    if debug_residue:
        print("\n[!] Debug Residue Keys Detected in .env:")
        for k in debug_residue:
            print(f"    - {k}")

    if only_in_env:
        print(f"\n[+] Keys in .env but MISSING from .env.example ({len(only_in_env)} keys):")
        for k in only_in_env:
            print(f"    - {k}")

    if only_in_example:
        print(f"\n[-] Keys documented in .env.example but MISSING from live .env ({len(only_in_example)} keys):")
        for k in only_in_example:
            print(f"    - {k}")

    if sync and only_in_env:
        print("\n[*] Synchronizing missing keys into .env.example (with safe placeholders)...")
        with open(EXAMPLE_FILE, "a", encoding="utf-8") as f:
            f.write("\n\n# ====================================================================\n")
            f.write("# Automatically synchronized keys from .env audit\n")
            f.write("# ====================================================================\n")
            for k in only_in_env:
                if k in debug_residue:
                    continue  # do not copy debug residue to example
                placeholder = sanitize_value_for_example(k, env_entries[k])
                f.write(f"{placeholder}\n")
        print(f"[OK] Appended {len(only_in_env) - len(debug_residue)} safe key templates to {EXAMPLE_FILE.name}")

    if not only_in_env and not only_in_example and not debug_residue:
        print("\n[OK] .env and .env.example are in perfect synchronization!")
        return 0

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit .env vs .env.example drift")
    parser.add_argument("--sync", action="store_true", help="Sync missing keys into .env.example")
    args = parser.parse_args()
    return diff_environments(sync=args.sync)


if __name__ == "__main__":
    sys.exit(main())
