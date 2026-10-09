#!/usr/bin/env python3
"""Diagnose House Tour Krea failures without touching Airtable.

Submits a few small Krea ``krea-2-medium`` jobs and prints Krea's RAW reply, so
we can tell whether Krea rejects the moodboard ID or the long House Tour prompt.

* No Airtable / Akeneo / Fal / Kling calls. Only Krea.
* Never prints the API token.
* Each ACCEPTED job is one Krea generation (small cost). Rejected ones are free.
* Reads the real defaults straight from generate_house_tour_reel_pipeline.py via
  ``ast`` (no heavy imports, so CI only needs ``requests``).

Env (loaded from the repo .env when python-dotenv is installed):
    KREA_API_TOKEN      required
    KREA_API_BASE       optional (default https://api.krea.ai)
    EXTRA_MOODBOARD_ID  optional extra board to test with a short prompt

Usage::

    python scripts/ops/krea_moodboard_check.py
    python scripts/ops/krea_moodboard_check.py --extra-moodboard-id <uuid>
"""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import sys

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_FILE = REPO_ROOT / "generate_house_tour_reel_pipeline.py"

KNOWN_GOOD_BOARD = "b5ffdcbb-192e-4528-8d86-d1a4cf496887"  # used by other pipelines
SHORT_PROMPT = "Generate me a modern living room"


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env")


def load_pipeline_defaults() -> tuple[str, dict[int, str]]:
    tree = ast.parse(PIPELINE_FILE.read_text(encoding="utf-8"))
    moodboard = ""
    prompts: dict[int, str] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        else:
            continue
        if name == "DEFAULT_MOODBOARD_ID" and value is not None:
            moodboard = ast.literal_eval(value)
        elif name == "DEFAULT_INTERIOR_PROMPTS" and value is not None:
            prompts = ast.literal_eval(value)
    return moodboard, prompts


def submit(base: str, token: str, label: str, prompt: str, moodboard_id: str) -> bool:
    payload: dict = {
        "prompt": prompt,
        "aspect_ratio": "9:16",
        "resolution": "1K",
        "creativity": "high",
    }
    if moodboard_id:
        payload["moodboards"] = [{"id": moodboard_id, "strength": 0.23}]
    url = f"{base}/generate/image/krea/krea-2/medium"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
    except Exception as error:  # network / DNS / timeout
        print(f"[{label}] REQUEST FAILED: {error}")
        return False
    verdict = "ACCEPTED" if response.ok else "REJECTED"
    print(
        f"[{label}] moodboard={moodboard_id or '(none)'} prompt_chars={len(prompt)} "
        f"-> HTTP {response.status_code} {verdict}"
    )
    print(f"    Krea reply: {(response.text or '').strip()[:800]}")
    return response.ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Krea for House Tour moodboard/prompt rejections.")
    parser.add_argument("--extra-moodboard-id", default="", help="Optional extra moodboard to test")
    args = parser.parse_args(argv)

    load_env()
    token = os.getenv("KREA_API_TOKEN", "").strip()
    base = (os.getenv("KREA_API_BASE", "").strip() or "https://api.krea.ai").rstrip("/")
    if not token:
        print("[ERROR] KREA_API_TOKEN is empty (set it in .env or the environment).")
        return 1

    default_board, prompts = load_pipeline_defaults()
    if not default_board or not prompts:
        print("[ERROR] Could not read DEFAULT_MOODBOARD_ID / DEFAULT_INTERIOR_PROMPTS from the pipeline file.")
        return 1
    longest_slot = max(prompts, key=lambda s: len(prompts[s]))

    print(f"Krea base: {base}")
    print(f"House Tour default moodboard: {default_board}")
    print(f"Longest House Tour prompt: slot {longest_slot} ({len(prompts[longest_slot])} chars)\n")

    results: dict[str, bool] = {}
    results["A default board + short prompt"] = submit(base, token, "A", SHORT_PROMPT, default_board)
    results["B known-good board + short prompt"] = submit(base, token, "B", SHORT_PROMPT, KNOWN_GOOD_BOARD)
    results["C no board + longest House Tour prompt"] = submit(
        base, token, "C", prompts[longest_slot], ""
    )
    if results["A default board + short prompt"]:
        results["D default board + slot 1 prompt (exact prod call)"] = submit(
            base, token, "D", prompts[1], default_board
        )
    extra = (args.extra_moodboard_id or os.getenv("EXTRA_MOODBOARD_ID", "")).strip()
    if extra:
        results[f"E extra board {extra} + short prompt"] = submit(base, token, "E", SHORT_PROMPT, extra)

    print("\n================ SUMMARY ================")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print("=========================================")
    a = results["A default board + short prompt"]
    b = results["B known-good board + short prompt"]
    c = results["C no board + longest House Tour prompt"]
    if not a and b:
        print("VERDICT: Krea rejects the House Tour default moodboard for this key. Switch the board.")
    elif a and not c:
        print("VERDICT: Moodboard is fine; the long House Tour prompts are being rejected.")
    elif not a and not b:
        print("VERDICT: Every request failed -> check KREA_API_TOKEN / Krea account credits first.")
    else:
        print("VERDICT: Krea accepts these requests. The Studio failure is elsewhere (or a different key on Railway).")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
