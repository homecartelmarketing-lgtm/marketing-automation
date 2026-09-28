"""Preview and test the local Python Pillow overlay for Style This Story.

Renders Slide 1 ('How would you style this? ft. [Item Name]') and
Slide 2-4 ('Double tap if you choose:' + Heart Emoji + #adb481 Rounded Pill).

Usage:
    # 1. Quick test using downloaded sample assets:
    python preview_style_this_overlay.py

    # 2. Preview from a specific Airtable Record ID:
    python preview_style_this_overlay.py --record-id recFxXwIFimDuVQs9

    # 3. Custom item name and custom local images:
    python preview_style_this_overlay.py --item "Gravira Swing Arm Lamp" --text "Warm Olive"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from PIL import Image
import requests

from content_automation.config import load_settings
from content_automation.media import download_to_temp_file
from content_automation.overlay import (
    DEFAULT_STYLE_THIS_PILL_COLOR,
    create_style_this_double_tap_slide,
    create_style_this_slide_1,
)
from content_automation.scraping import ScrapeAirtableClient


DEFAULT_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID_STYLE_THIS", "").strip() or "tblvSAzXasTVI85r9"


def preview_from_airtable_record(record_id: str, table_id: str = DEFAULT_TABLE_ID):
    settings = load_settings()
    settings.require({"airtable"})

    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )
    rec = airtable.get_record(record_id)
    fields = rec.get("fields", {})
    item_name = str(fields.get("Item Name") or fields.get("SKU") or "Modern Floor Lamp").strip()
    blended_items = fields.get("Style This Blended") or []
    logo_items = fields.get("Logo") or []

    if not blended_items:
        print(f"[ERROR] Record {record_id} has no 'Style This Blended' images.")
        return

    out_dir = Path("output/style_this_preview") / record_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[PREVIEW] Processing Record: {record_id}")
    print(f"  Item Name: {item_name}")
    print(f"  Blended Images: {len(blended_items)}")

    # Download Logo if present
    logo_temp = None
    if logo_items:
        logo_url = logo_items[0].get("url")
        if logo_url:
            resp = requests.get(logo_url, stream=True)
            logo_temp = download_to_temp_file(resp, prefix="logo_", suffix=".png", context="Download logo")

    # Slide 1
    b1_url = blended_items[0].get("url")
    resp_b1 = requests.get(b1_url, stream=True)
    temp_b1 = download_to_temp_file(resp_b1, prefix="b1_", suffix=".jpg", context="Download slide 1")
    slide1_out = out_dir / "preview_how_would_you_style_this.jpg"
    try:
        create_style_this_slide_1(
            base_image=temp_b1.path,
            logo_path=logo_temp.path if logo_temp else None,
            item_name=item_name,
            destination=slide1_out,
        )
        print(f"  [OK] Saved Slide 1 Preview -> {slide1_out}")
    finally:
        temp_b1.cleanup()

    # Slide 2 (and 3, 4 if present)
    vibe_samples = ["Warm Olive", "Earthy Sand", "Amber Glow", "Sage Minimalist"]
    for idx, b_item in enumerate(blended_items[1:], start=1):
        dt_url = b_item.get("url")
        resp_dt = requests.get(dt_url, stream=True)
        temp_dt = download_to_temp_file(resp_dt, prefix=f"dt_{idx}_", suffix=".jpg", context=f"Download slide {idx+1}")
        dt_out = out_dir / f"preview_double_tap_blended0{idx}.jpg"

        # Read generated text and color from Airtable record if available
        text_field = f"Style This Text Generated{idx}"
        color_field = f"Style This Auto Generated Color{idx}"
        vibe_text = str(fields.get(text_field) or "").strip() or vibe_samples[(idx - 1) % len(vibe_samples)]
        pill_color = str(fields.get(color_field) or "").strip() or DEFAULT_STYLE_THIS_PILL_COLOR

        try:
            create_style_this_double_tap_slide(
                base_image=temp_dt.path,
                logo_path=logo_temp.path if logo_temp else None,
                claude_text=vibe_text,
                destination=dt_out,
                pill_color_hex=pill_color,
            )
            print(f"  [OK] Saved Slide {idx + 1} Preview -> {dt_out} (Vibe: '{vibe_text}', Color: '{pill_color}')")
        finally:
            temp_dt.cleanup()

    if logo_temp:
        logo_temp.cleanup()

    print(f"\n[DONE] All previews generated in: {out_dir}\n")


def preview_from_local_files(
    slide1_path: Path | str,
    slide2_path: Path | str | None,
    item_name: str = "Gravira Floor Lamp Swing Arm",
    claude_text: str = "Warm Olive",
    pill_color_hex: str = DEFAULT_STYLE_THIS_PILL_COLOR,
    logo_path: Path | str | None = None,
    out_dir: Path | str = "output/style_this_preview",
):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    s1_out = out_path / "preview_slide1.jpg"
    create_style_this_slide_1(
        base_image=slide1_path,
        logo_path=logo_path,
        item_name=item_name,
        destination=s1_out,
    )
    print(f"  [OK] Slide 1 generated: {s1_out}")

    if slide2_path and Path(slide2_path).is_file():
        s2_out = out_path / "preview_slide2.jpg"
        create_style_this_double_tap_slide(
            base_image=slide2_path,
            logo_path=logo_path,
            claude_text=claude_text,
            destination=s2_out,
            pill_color_hex=pill_color_hex,
        )
        print(f"  [OK] Slide 2 generated: {s2_out} (Color: {pill_color_hex})")


def main():
    parser = argparse.ArgumentParser(description="Preview Style This Story Layouts")
    parser.add_argument("--record-id", "-r", help="Airtable Record ID to preview")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help="Airtable Table ID")
    parser.add_argument("--item", default="Gravira Floor Lamp Swing Arm", help="Product item name")
    parser.add_argument("--text", default="Warm Olive", help="Claude generated text for pill")
    parser.add_argument("--color", default=DEFAULT_STYLE_THIS_PILL_COLOR, help="Pill HEX color (e.g. #adb481, #c17c5f)")
    parser.add_argument("--slide1", help="Path to local slide 1 blended image")
    parser.add_argument("--slide2", help="Path to local slide 2 blended image")
    parser.add_argument("--logo", help="Path to logo PNG/JPG")
    args = parser.parse_args()

    if args.record_id:
        preview_from_airtable_record(args.record_id, args.table_id)
        return

    # Check default test input paths
    s1 = args.slide1 or "scratch/test_inputs/style_this01.jpg"
    s2 = args.slide2 or "scratch/test_inputs/style_this02.jpg"
    logo = args.logo or "scratch/test_inputs/logo.png"

    if not Path(s1).is_file():
        # Create a dummy test image if not exists
        Path("scratch/test_inputs").mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (1080, 1920), color=(140, 120, 100))
        img.save(s1)
        img.save(s2)

    print(f"\n[PREVIEW] Generating local preview using: {s1} and {s2}...")
    preview_from_local_files(
        slide1_path=s1,
        slide2_path=s2 if Path(s2).is_file() else None,
        item_name=args.item,
        claude_text=args.text,
        pill_color_hex=args.color,
        logo_path=logo if Path(logo).is_file() else None,
    )


if __name__ == "__main__":
    main()
