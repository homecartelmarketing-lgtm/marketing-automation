#!/usr/bin/env python3
"""Promo Banner (1080x1920, 9:16 "Your Story"): the monthly promo ad that used to be rebuilt by hand in Canva.

Input is the main (wide) banner as a LOCAL file. Output is a 9:16 PNG with the HomeCartel logo, a tagline, a big
"10%OFF" / "15%OFF" and the date line:

    1. Nano Banana Pro (fal-ai/nano-banana-pro/edit) extends the wide banner to a 9:16 background (the only image API call).
    2. Claude Sonnet 5 (through fal) writes the short tagline from the banner's NAME (the image is supporting context).
    3. Local Pillow draws the logo and all text with the Canva layout (content_automation/overlay.py::draw_promo_banner).

No Airtable row is read or written. A failed tagline call never fails the run (it falls back to --tagline or the
cleaned banner name). Use the text-free banner (for example `christmas_banner_<rec>.jpg`, "Blended Banner") as the
input: the logo and text are drawn on top, so text already on the banner would be extended too.

Usage:
    python generate_promo_banner_pipeline.py --banner banner.jpg --discount 10 --month SEP --year 2026 --dry-run
    python generate_promo_banner_pipeline.py --banner "Festive Glow Banner.jpg" --discount 10 --month SEP --year 2026
    python generate_promo_banner_pipeline.py --banner b.jpg --discount 15 --month AUG --year 2026 \\
        --banner-name "Festive Glow Banner" --date-text "August 20-31, 2026" --resolution 2K
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from PIL import Image, ImageOps

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.errors import AutomationError  # noqa: E402
from content_automation.fal_client import FalClient  # noqa: E402
from content_automation.media import download_url_to_temp_file  # noqa: E402
from content_automation.overlay import PROMO_CANVAS_SIZE, draw_promo_banner  # noqa: E402
from content_automation.promo_calendar import (  # noqa: E402
    DISCOUNT_EVENT_KEYS,
    month_abbr,
    month_number,
    promo_caption,
    promo_date_text,
)
from content_automation.prompts import PROMO_OUTPAINT_PROMPT, build_promo_tagline_instruction  # noqa: E402

DEFAULT_MODEL = os.getenv("PROMO_BANNER_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
DEFAULT_RESOLUTION = os.getenv("PROMO_BANNER_RESOLUTION", "").strip() or "1K"
CLAUDE_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
OUTPUT_DIR = REPO_ROOT / "output" / "promo_banner"
TAGLINE_MAX_CHARS = 44
TAGLINE_MAX_WORDS = 7  # the prompt asks for 3-5; this only guards against a runaway answer
FAL_KEY_ENV_NAMES = ("FAL_KEY", "FAL_API_KEY")


# --------------------------------------------------------------------------
# Names, tagline cleaning (pure, unit tested)
# --------------------------------------------------------------------------

def clean_banner_name(value: str | Path) -> str:
    """'Festive Glow_Banner-2.jpg' -> 'Festive Glow Banner 2': file name without extension, _ and - as spaces."""
    text = Path(str(value)).stem if str(value).lower().endswith((".jpg", ".jpeg", ".png", ".webp")) else str(value)
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", text)).strip()


def clean_tagline(raw: Any, max_chars: int = TAGLINE_MAX_CHARS) -> str:
    """First non-empty line, without markdown, quotes, emoji or a trailing full stop, limited in length."""
    text = ""
    for line in str(raw or "").splitlines():
        if line.strip():
            text = line.strip()
            break
    text = re.sub(r"[*_#`>]+", "", text)  # markdown first, so "**Title:** ..." loses its label below
    text = re.sub(r"^\s*(title|tagline)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = text.replace("“", "").replace("”", "").replace('"', "").replace("‘", "'").replace("’", "'")
    text = re.sub(r"[^\w\s,'&!?.\-–|]", "", text, flags=re.UNICODE)  # drops emoji and symbols
    text = re.sub(r"\s+", " ", text).strip(" '.-")
    words = text.split()
    if len(words) > TAGLINE_MAX_WORDS:
        text = " ".join(words[:TAGLINE_MAX_WORDS])
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip(" ,'&-")
    return text


def output_stem(discount: int, month: int, year: int) -> str:
    return f"promo_{month_abbr(month)}-{year}-{int(discount)}OFF_9x16"


# --------------------------------------------------------------------------
# fal steps
# --------------------------------------------------------------------------

def fal_key() -> str:
    for name in FAL_KEY_ENV_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def make_fal_client() -> FalClient:
    key = fal_key()
    if not key:
        raise AutomationError("FAL_KEY (or FAL_API_KEY) is not set; use --dry-run to test the layout without fal.")
    return FalClient(api_key=key)


def to_9x16(fal: FalClient, banner_url: str, resolution: str = DEFAULT_RESOLUTION, model: str = DEFAULT_MODEL) -> Image.Image:
    """Nano Banana Pro extends the wide banner to 9:16; the result is fitted to exactly 1080x1920 (LANCZOS)."""
    print(f"  [INFO] Nano Banana Pro 9:16 extension ({model}, {resolution})...")
    image_url = fal.generate(
        PROMO_OUTPAINT_PROMPT,
        [banner_url],
        aspect_ratio="9:16",
        resolution=resolution,
        model=model,
        output_format="png",
    )
    downloaded = download_url_to_temp_file(
        requests.Session(), image_url, prefix="promo_bg_", suffix=".png",
        context=f"Download the 9:16 promo background from {image_url}",
    )
    with Image.open(downloaded.path) as opened:
        return ImageOps.fit(opened.convert("RGB"), PROMO_CANVAS_SIZE, method=Image.Resampling.LANCZOS)


def make_tagline(fal: FalClient | None, banner_url: str, banner_name: str, override: str = "") -> str:
    """The promo tagline. Never raises: --tagline wins; if Claude fails, use the cleaned banner name."""
    fallback = clean_tagline(banner_name) or clean_tagline(clean_banner_name(banner_name))
    if override.strip():
        return clean_tagline(override) or fallback
    if fal is None:
        return fallback
    try:
        reply = fal.generate_claude_vision(
            build_promo_tagline_instruction(banner_name),
            [banner_url],
            system_instruction="You are a luxury lighting copywriter for HomeCartel.",
            model=CLAUDE_MODEL,
        )
        tagline = clean_tagline(reply)
        if tagline:
            return tagline
        print(f"  [WARN] Claude returned no usable tagline ({str(reply)[:60]!r}); using the banner name.")
    except Exception as err:  # noqa: BLE001 - the tagline must never fail the run
        print(f"  [WARN] Claude tagline failed ({err}); using the banner name.")
    return fallback


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def run(
    banner: Path | str,
    discount: int,
    month: Any,
    year: int,
    *,
    banner_name: str = "",
    tagline: str = "",
    date_text: str = "",
    resolution: str = DEFAULT_RESOLUTION,
    dry_run: bool = False,
    output_dir: Path | None = None,
    fal: FalClient | None = None,
) -> Path:
    banner_path = Path(banner)
    if not banner_path.is_file():
        raise AutomationError(f"--banner file not found: {banner_path}")
    if int(discount) not in DISCOUNT_EVENT_KEYS:
        raise AutomationError(f"--discount must be 10 or 15 (got {discount!r}).")
    month_no = month_number(month)
    name = (banner_name or clean_banner_name(banner_path)).strip()
    dates = (date_text or promo_date_text(discount, month_no, year)).strip()
    caption = promo_caption(discount, dates)
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = output_stem(int(discount), month_no, int(year))
    if dry_run:
        stem += "_dryrun"  # a free layout test must never overwrite a real (live) background or promo

    print("=" * 70)
    print("HOMECARTEL MARKETING AI -- PROMO BANNER (1080x1920, 9:16)")
    print("=" * 70)
    print(f"Banner:   {banner_path}  (name: {name!r})")
    print(f"Discount: {int(discount)}% OFF | {dates}")
    print(f"Mode:     {'DRY RUN (no fal calls)' if dry_run else 'live (Nano Banana Pro + Claude Sonnet 5)'}")
    print("=" * 70)

    if dry_run:
        with Image.open(banner_path) as opened:
            background = ImageOps.fit(opened.convert("RGB"), PROMO_CANVAS_SIZE, method=Image.Resampling.LANCZOS)
        tag = make_tagline(None, "", name, tagline)
    else:
        client = fal or make_fal_client()
        print("[STEP 1] Uploading the banner to fal...")
        banner_url = client.upload_file(banner_path)
        print("[STEP 2] 9:16 background...")
        background = to_9x16(client, banner_url, resolution)
        print("[STEP 3] Tagline from the banner name...")
        tag = make_tagline(client, banner_url, name, tagline)
    print(f"  [OK] Tagline: {tag!r}")

    background_path = out_dir / f"{stem}_bg.png"
    background.save(background_path, "PNG", optimize=True)
    final_path = out_dir / f"{stem}.png"
    draw_promo_banner(background, discount=int(discount), tagline=tag, date_caption=caption, destination=final_path)
    print(f"  [OK] Background: {background_path}")
    print(f"  [SUCCESS] Promo banner: {final_path}")
    return final_path


def main() -> int:
    parser = argparse.ArgumentParser(description="HomeCartel promo banner (9:16) from the main banner")
    parser.add_argument("--banner", required=True, help="The main (wide) banner, a local image file")
    parser.add_argument("--discount", type=int, choices=sorted(DISCOUNT_EVENT_KEYS), required=True, help="10 or 15")
    parser.add_argument("--month", required=True, help="Month: SEP, September or 9")
    parser.add_argument("--year", type=int, required=True, help="Year, for example 2026")
    parser.add_argument("--banner-name", default="", help="Name the tagline is based on (default: the file name)")
    parser.add_argument("--tagline", default="", help="Use this tagline instead of asking Claude")
    parser.add_argument("--date-text", default="", help="Override the date, for example 'August 20–31, 2026' (default: the promotions calendar)")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, choices=["1K", "2K", "4K"], help="Nano Banana Pro resolution")
    parser.add_argument("--dry-run", action="store_true", help="No fal calls: centre-crop the banner and use the banner name as the tagline")
    args = parser.parse_args()
    run(
        args.banner,
        args.discount,
        args.month,
        args.year,
        banner_name=args.banner_name,
        tagline=args.tagline,
        date_text=args.date_text,
        resolution=args.resolution,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
