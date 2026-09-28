"""CLI utility to preview automated item name tagging on a blended image.

Usage:
    python preview_item_tag_overlay.py
    python preview_item_tag_overlay.py --image "path/to/room.jpg" --name "Halvor" --type "Modern Floor Lamp with Marble Base" --category floor_lamps
    python preview_item_tag_overlay.py --image "path/to/room.jpg" --name "Nordic Brass Chandelier" --category chandeliers
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time

from PIL import Image

from content_automation.item_tagger import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_FONT_SIZE,
    detect_item_bbox,
    render_item_name_tag,
    tag_blended_image,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Preview item name tagging on a blended room image")
    parser.add_argument(
        "--image",
        "-i",
        default="output/style_this_preview/clean_room_preview.jpg",
        help="Path to local room image",
    )
    parser.add_argument(
        "--name",
        "-n",
        default="Halvor",
        help="Item Name (Line 1, bold, e.g. 'Halvor')",
    )
    parser.add_argument(
        "--type",
        "-t",
        default="Modern Floor Lamp with Marble Base",
        help="Product Type (Line 2, regular, e.g. 'Modern Floor Lamp with Marble Base')",
    )
    parser.add_argument(
        "--category",
        "-c",
        default="floor_lamps",
        help="Product category for YOLO-World detection (e.g. chandeliers, floor_lamps, pendant_lights, sofas)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="output/item_tag_preview/preview_tagged.jpg",
        help="Path to save tagged preview output image",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help="YOLO-World confidence threshold (default: 0.20)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    image_path = Path(args.image)
    if not image_path.is_file():
        # Search for another candidate image in output/ if default not found
        candidates = list(Path("output").rglob("*.jpg"))
        if candidates:
            image_path = candidates[0]
            print(f"[INFO] Image '{args.image}' not found, using candidate: {image_path}")
        else:
            print(f"[ERROR] Image '{args.image}' does not exist.")
            return 1

    print(f"[INFO] Loading image: {image_path}")
    img = Image.open(image_path)
    print(f"[INFO] Canvas dimensions: {img.width}x{img.height}")
    print(f"[INFO] Target Category: '{args.category}'")
    print(f"[INFO] Line 1 (Bold, 19px): '{args.name}'")
    print(f"[INFO] Line 2 (Regular, 19px): '{args.type}'")

    start_time = time.perf_counter()
    bbox = detect_item_bbox(img, category=args.category, confidence_threshold=args.conf)
    detect_time = time.perf_counter() - start_time

    if bbox is None:
        print(f"[WARN] No item detected for category '{args.category}' with confidence >= {args.conf}")
        print("[WARN] Strict mode: Stamping skipped to prevent misplacement.")
        return 1

    print(f"[OK] Detected bounding box: (X1={bbox[0]}, Y1={bbox[1]}, X2={bbox[2]}, Y2={bbox[3]}) in {detect_time:.3f}s")

    tagged_img = render_item_name_tag(
        image=img,
        bbox=bbox,
        item_name=args.name,
        product_type=args.type,
        font_size=DEFAULT_FONT_SIZE,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tagged_img.save(out_path, quality=95)
    print(f"[SUCCESS] Tagged preview saved to: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
