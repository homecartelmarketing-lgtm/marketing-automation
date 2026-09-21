"""Preview and test script for Tips & Educational Feed Thumbnail Text Overlay."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from content_automation.overlay import (
    HOMECARTEL_LOGO_BOX,
    TIPS_EDU_THUMBNAIL_DIVIDER,
    TIPS_EDU_THUMBNAIL_SUBTITLE_BOX,
    TIPS_EDU_THUMBNAIL_TITLE_BOX,
    create_tips_edu_thumbnail_with_text,
    overlay_tips_edu_thumbnail_text,
)


def run_preview(
    base_image_path: str | Path | None = None,
    title_text: str = "Modern Living Room Lighting Tips",
    subtitle_text: str = "In 3 ways",
    output_path: str | Path = "output/preview_tips_edu_thumbnail.jpg",
) -> Path:
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if base_image_path and Path(base_image_path).is_file():
        base_img = Image.open(base_image_path)
    else:
        base_img = Image.new("RGB", (1080, 1350), color=(35, 45, 55))

    logo_candidates = [
        Path("assets/homecartel_logo.png"),
        Path("JSON Prompts/homecartel_logo.png"),
        Path("content_automation/assets/logo.png"),
        Path("static/img/logo.png"),
    ]
    logo_path = next((p for p in logo_candidates if p.is_file()), None)

    saved_path = create_tips_edu_thumbnail_with_text(
        base_image=base_img,
        title_text=title_text,
        subtitle_text=subtitle_text,
        logo_path=logo_path,
        destination=out_file,
        title_font_size=47,
        subtitle_font_size=32,
        with_divider=True,
    )

    print(f"[OK] Saved preview thumbnail to: {saved_path}")
    print(f"     Title      : \"{title_text}\" (Poppins-Bold 47px, Box: W={TIPS_EDU_THUMBNAIL_TITLE_BOX.width}, H={TIPS_EDU_THUMBNAIL_TITLE_BOX.height}, X={TIPS_EDU_THUMBNAIL_TITLE_BOX.x}, Y={TIPS_EDU_THUMBNAIL_TITLE_BOX.y})")
    print(f"     Subtitle   : \"{subtitle_text}\" (Poppins-Light 32px, Box: W={TIPS_EDU_THUMBNAIL_SUBTITLE_BOX.width}, H={TIPS_EDU_THUMBNAIL_SUBTITLE_BOX.height}, X={TIPS_EDU_THUMBNAIL_SUBTITLE_BOX.x}, Y={TIPS_EDU_THUMBNAIL_SUBTITLE_BOX.y})")
    print(f"     Divider    : Start X={TIPS_EDU_THUMBNAIL_DIVIDER.start_x}, End X={TIPS_EDU_THUMBNAIL_DIVIDER.end_x}, Y={TIPS_EDU_THUMBNAIL_DIVIDER.start_y}")
    print(f"     Logo Box   : Box: W={HOMECARTEL_LOGO_BOX.width}, H={HOMECARTEL_LOGO_BOX.height}, X={HOMECARTEL_LOGO_BOX.x}, Y={HOMECARTEL_LOGO_BOX.y}")
    return Path(saved_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview Tips & Edu Feed Thumbnail Text Overlay")
    parser.add_argument("--image", "-i", default=None, help="Base image path")
    parser.add_argument("--title", "-t", default="Modern Living Room Lighting Tips", help="Title text")
    parser.add_argument("--subtitle", "-s", default="In 3 ways", help="Subtitle text")
    parser.add_argument("--output", "-o", default="output/preview_tips_edu_thumbnail.jpg", help="Output file path")
    args = parser.parse_args()

    run_preview(
        base_image_path=args.image,
        title_text=args.title,
        subtitle_text=args.subtitle,
        output_path=args.output,
    )
