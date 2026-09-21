#!/usr/bin/env python
"""Standalone YOLO-World Furniture Item Name Tagging Studio.

Interactive local web application for uploading room photos, detecting furniture
fixtures via local open-vocabulary YOLO-World, applying luxury 2-line floating
editorial stamps (Poppins 19px, solid white #FFFFFF), and downloading high-res images.

Usage:
    python standalone_item_tagger.py
    python standalone_item_tagger.py --port 5055 --no-browser
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
from pathlib import Path
import re
import sys
import threading
import time
import webbrowser
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from PIL import Image, ImageDraw, ImageFont

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from content_automation.akeneo_client import split_item_name
from content_automation.item_tagger import (
    CATEGORY_DETECTION_MAP,
    DEFAULT_CANVAS_PADDING,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_FONT_SIZE,
    DEFAULT_MARGIN,
    calculate_adaptive_text_position,
    detect_item_bbox,
    get_detection_queries_for_category,
    get_yolo_world_model,
    resolve_font_path,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("item_tagger_studio")

# Paths
OUTPUT_DIR = PROJECT_ROOT / "output" / "tagged_images"
UPLOAD_TEMP_DIR = PROJECT_ROOT / "output" / "temp_uploads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "assets"),
)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


# ----------------------------------------------------------------------
# Category Auto-Detection Helper
# ----------------------------------------------------------------------
KEYWORD_CATEGORY_MAPPINGS: list[tuple[list[str], str]] = [
    (["chandelier", "chandeliers", "crystal", "grand light"], "chandeliers"),
    (["pendant", "pendants", "hanging lamp", "drop light", "cord lamp"], "pendant_lights"),
    (["floor lamp", "standing lamp", "arc lamp", "tripod lamp"], "floor_lamps"),
    (["table lamp", "desk lamp", "bedside lamp", "nightstand lamp"], "table_lamps"),
    (["wall sconce", "sconce", "wall lamp", "bracket light"], "wall_sconces"),
    (["flush mount", "flushmount", "semi flush", "ceiling mount"], "flush_mounts"),
    (["dining table", "extendable table", "eating table"], "dining_tables"),
    (["coffee table", "cocktail table", "center table", "tea table"], "coffee_tables"),
    (["sofa", "couch", "sectional", "loveseat", "divan", "settee"], "sofas"),
    (["chair", "armchair", "lounge chair", "accent chair", "dining chair", "stool"], "chairs"),
]


def infer_category_from_text(text: str) -> str:
    """Infer likely YOLO category from item name or product type text."""
    lower = text.lower().strip()
    for keywords, category in KEYWORD_CATEGORY_MAPPINGS:
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", lower):
                return category
    # Fallback to general heuristics
    if "lamp" in lower:
        return "floor_lamps"
    if "light" in lower or "fixture" in lower:
        return "chandeliers"
    if "table" in lower:
        return "dining_tables"
    return "chandeliers"


# ----------------------------------------------------------------------
# Enhanced Custom Typography & Bounding Box Renderer
# ----------------------------------------------------------------------
def render_studio_tag(
    image: Image.Image,
    bbox: tuple[int, int, int, int] | None,
    item_name: str,
    product_type: str = "",
    *,
    placement: str = "auto",  # 'auto', 'left', 'right', 'manual'
    manual_coords: tuple[int, int] | None = None,
    font_size: int = DEFAULT_FONT_SIZE,
    line_spacing: int = 5,
    margin: int = DEFAULT_MARGIN,
    canvas_padding: int = DEFAULT_CANVAS_PADDING,
) -> tuple[Image.Image, tuple[int, int], tuple[int, int]]:
    """Render 2-line solid white tag with flexible placement support.

    Returns:
        (rendered_image, (text_x, text_y), (text_w, text_h))
    """
    img = image.convert("RGBA")
    w, h = img.size

    title = str(item_name or "").strip()
    subtitle = str(product_type or "").strip()
    if "|" in title and not subtitle:
        title, subtitle = split_item_name(title)

    bold_path = resolve_font_path("Poppins-Bold.ttf")
    reg_path = resolve_font_path("Poppins-Regular.ttf") or bold_path

    try:
        font_title = ImageFont.truetype(str(bold_path), font_size) if bold_path else ImageFont.load_default()
    except Exception:
        font_title = ImageFont.load_default()

    try:
        font_subtitle = ImageFont.truetype(str(reg_path), font_size) if reg_path else font_title
    except Exception:
        font_subtitle = font_title

    # Measure text bounding dimensions
    dummy = ImageDraw.Draw(img)

    def measure(txt: str, f: ImageFont.ImageFont) -> tuple[int, int]:
        if not txt:
            return 0, 0
        box = dummy.textbbox((0, 0), txt, font=f)
        return box[2] - box[0], box[3] - box[1]

    t_w, t_h = measure(title, font_title)
    s_w, s_h = measure(subtitle, font_subtitle) if subtitle else (0, 0)
    total_w = max(t_w, s_w)
    total_h = t_h + (line_spacing + s_h if subtitle else 0)

    # Determine coordinates
    if placement == "manual" and manual_coords:
        mx, my = manual_coords
        text_x = max(canvas_padding, min(mx, w - canvas_padding - total_w))
        text_y = max(canvas_padding, min(my, h - canvas_padding - total_h))
    elif bbox is not None:
        bx1, by1, bx2, by2 = bbox
        if placement == "left":
            left_candidate = bx1 - margin - total_w
            text_x = max(canvas_padding, left_candidate)
            mid_y = int(by1 + (by2 - by1) * 0.40)
            text_y = mid_y - (total_h // 2)
        elif placement == "right":
            right_candidate = bx2 + margin
            text_x = min(w - canvas_padding - total_w, right_candidate)
            mid_y = int(by1 + (by2 - by1) * 0.40)
            text_y = mid_y - (total_h // 2)
        else:
            # Default auto calculation
            text_x, text_y = calculate_adaptive_text_position(w, h, bbox, total_w, total_h)
    else:
        # No bbox and no manual coords: center on canvas upper-middle
        text_x = max(canvas_padding, (w - total_w) // 2)
        text_y = max(canvas_padding, int(h * 0.40) - (total_h // 2))

    # Clamp safely inside canvas
    if h >= 1800:
        min_y = max(canvas_padding, 160)
        max_y = min(h - canvas_padding - total_h, 1650 - total_h)
    else:
        min_y = canvas_padding
        max_y = h - canvas_padding - total_h
    text_y = max(min_y, min(text_y, max_y))
    text_x = max(canvas_padding, min(text_x, w - canvas_padding - total_w))

    # Render clean solid white typography
    txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)

    # Line 1: Bold Title
    draw.text((text_x, text_y), title, font=font_title, fill=(255, 255, 255, 255))

    # Line 2: Regular Subtitle
    if subtitle:
        sub_y = text_y + t_h + line_spacing
        draw.text((text_x, sub_y), subtitle, font=font_subtitle, fill=(255, 255, 255, 255))

    composite = Image.alpha_composite(img, txt_layer)
    return composite.convert("RGB"), (text_x, text_y), (total_w, total_h)


def draw_detection_overlay(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
    label: str,
    conf: float,
) -> Image.Image:
    """Draw sleek modern detection overlay (cyan borders, corner accents, label pill)."""
    img = image.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    bx1, by1, bx2, by2 = bbox
    cyan_stroke = (56, 189, 248, 220)  # #38BDF8
    cyan_fill = (56, 189, 248, 30)

    # Semi-transparent box
    draw.rectangle([bx1, by1, bx2, by2], outline=cyan_stroke, width=2, fill=cyan_fill)

    # Corner brackets (luxury camera viewfinder style)
    corner_len = min(24, (bx2 - bx1) // 4, (by2 - by1) // 4)
    if corner_len > 6:
        # Top-left
        draw.line([(bx1, by1), (bx1 + corner_len, by1)], fill=(255, 255, 255, 255), width=3)
        draw.line([(bx1, by1), (bx1, by1 + corner_len)], fill=(255, 255, 255, 255), width=3)
        # Top-right
        draw.line([(bx2, by1), (bx2 - corner_len, by1)], fill=(255, 255, 255, 255), width=3)
        draw.line([(bx2, by1), (bx2, by1 + corner_len)], fill=(255, 255, 255, 255), width=3)
        # Bottom-left
        draw.line([(bx1, by2), (bx1 + corner_len, by2)], fill=(255, 255, 255, 255), width=3)
        draw.line([(bx1, by2), (bx1 - corner_len, by2)], fill=(255, 255, 255, 255), width=3)
        # Bottom-right
        draw.line([(bx2, by2), (bx2 - corner_len, by2)], fill=(255, 255, 255, 255), width=3)
        draw.line([(bx2, by2), (bx2, by2 - corner_len)], fill=(255, 255, 255, 255), width=3)

    # Label badge
    badge_text = f"YOLO: {label} ({conf * 100:.1f}%)"
    try:
        font_badge = ImageFont.truetype(str(resolve_font_path("Poppins-Bold.ttf")), 14)
    except Exception:
        font_badge = ImageFont.load_default()

    bb = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    badge_pad_x = 8
    badge_pad_y = 4
    badge_x1 = max(4, bx1)
    badge_y1 = max(4, by1 - bh - (badge_pad_y * 2) - 4)
    badge_x2 = badge_x1 + bw + (badge_pad_x * 2)
    badge_y2 = badge_y1 + bh + (badge_pad_y * 2)

    draw.rounded_rectangle([badge_x1, badge_y1, badge_x2, badge_y2], radius=4, fill=(15, 23, 42, 220))
    draw.text((badge_x1 + badge_pad_x, badge_y1 + badge_pad_y), badge_text, font=font_badge, fill=(56, 189, 248, 255))

    return Image.alpha_composite(img, overlay).convert("RGB")


# ----------------------------------------------------------------------
# API Endpoints
# ----------------------------------------------------------------------
@app.route("/")
def index():
    """Serve the single-page studio web application."""
    return render_template("item_tagger_studio.html")


@app.route("/api/infer-category", methods=["POST"])
def api_infer_category():
    """Auto-detect category from typed text."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    cat = infer_category_from_text(text)
    return jsonify({"category": cat})


@app.route("/api/tag", methods=["POST"])
def api_tag_image():
    """Detect fixture with YOLO-World and render the luxury floating name stamp."""
    start_time = time.perf_counter()

    # Retrieve uploaded image file or existing filename
    image_file = request.files.get("image")
    existing_filename = request.form.get("existing_filename", "").strip()

    if image_file and image_file.filename:
        try:
            pil_img = Image.open(image_file.stream)
            pil_img = pil_img.convert("RGB")
        except Exception as e:
            return jsonify({"success": False, "error": f"Invalid image file: {str(e)}"}), 400
    elif existing_filename:
        candidate = UPLOAD_TEMP_DIR / existing_filename
        if not candidate.is_file():
            candidate = OUTPUT_DIR / existing_filename
        if not candidate.is_file():
            return jsonify({"success": False, "error": f"File '{existing_filename}' not found."}), 404
        pil_img = Image.open(candidate).convert("RGB")
    else:
        return jsonify({"success": False, "error": "No image file provided."}), 400

    # Parse text inputs
    raw_item_name = request.form.get("item_name", "").strip()
    raw_product_type = request.form.get("product_type", "").strip()

    if "|" in raw_item_name and not raw_product_type:
        line1, line2 = split_item_name(raw_item_name)
    else:
        line1, line2 = raw_item_name, raw_product_type

    if not line1 and not line2:
        line1 = "HomeCartel"
        line2 = "Interior Collection"

    # Category and query resolution
    category = request.form.get("category", "auto").strip().lower()
    custom_query = request.form.get("custom_query", "").strip()

    if category == "auto" or not category:
        category = infer_category_from_text(f"{line1} {line2}")

    queries = None
    if category == "custom" and custom_query:
        queries = [q.strip() for q in custom_query.split(",") if q.strip()]
    elif category:
        queries = get_detection_queries_for_category(category)

    # Confidence threshold
    try:
        conf_threshold = float(request.form.get("confidence", DEFAULT_CONFIDENCE_THRESHOLD))
    except ValueError:
        conf_threshold = DEFAULT_CONFIDENCE_THRESHOLD

    # Placement options
    placement = request.form.get("placement", "auto").strip().lower()
    manual_x = request.form.get("manual_x")
    manual_y = request.form.get("manual_y")
    manual_coords = None
    if manual_x is not None and manual_y is not None:
        try:
            manual_coords = (int(float(manual_x)), int(float(manual_y)))
            placement = "manual"
        except ValueError:
            pass

    font_size = int(request.form.get("font_size", DEFAULT_FONT_SIZE))

    # Run YOLO-World detection
    yolo_model = get_yolo_world_model()
    yolo_start = time.perf_counter()

    detected_bbox = None
    best_conf = 0.0

    if placement != "manual" or request.form.get("show_box") == "true":
        yolo_classes = queries or get_detection_queries_for_category(category)
        yolo_model.set_classes(yolo_classes)

        results = yolo_model.predict(
            source=pil_img,
            conf=conf_threshold,
            device="cpu",
            verbose=False,
        )

        if results and len(results) > 0 and results[0].boxes and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            best_score = -1.0
            w, h = pil_img.size
            for box in boxes:
                c = float(box.conf[0])
                coords = [int(round(coord)) for coord in box.xyxy[0].tolist()]
                bw = coords[2] - coords[0]
                bh = coords[3] - coords[1]
                if bw < 25 or bh < 25 or (bw * bh) > (w * h * 0.92):
                    continue
                if c > best_score:
                    best_score = c
                    detected_bbox = (coords[0], coords[1], coords[2], coords[3])
                    best_conf = c

    yolo_time = time.perf_counter() - yolo_start

    # Render tagged image
    tagged_img, text_pos, text_size = render_studio_tag(
        image=pil_img,
        bbox=detected_bbox,
        item_name=line1,
        product_type=line2,
        placement=placement,
        manual_coords=manual_coords,
        font_size=font_size,
    )

    # Render bbox preview if box is requested
    overlay_img = None
    if detected_bbox:
        overlay_img = draw_detection_overlay(
            tagged_img,
            detected_bbox,
            label=category.replace("_", " ").title(),
            conf=best_conf,
        )

    # Save outputs to disk
    timestamp = int(time.time() * 1000)
    clean_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", line1.strip()).strip("_") or "item"
    filename_tagged = f"{timestamp}_{clean_name}_tagged.jpg"
    filename_orig = f"{timestamp}_{clean_name}_original.jpg"
    filename_box = f"{timestamp}_{clean_name}_box.jpg" if detected_bbox else None

    tagged_path = OUTPUT_DIR / filename_tagged
    tagged_img.save(tagged_path, quality=95)

    orig_path = UPLOAD_TEMP_DIR / filename_orig
    pil_img.save(orig_path, quality=90)

    if overlay_img and filename_box:
        box_path = OUTPUT_DIR / filename_box
        overlay_img.save(box_path, quality=92)

    total_time = time.perf_counter() - start_time

    return jsonify(
        {
            "success": True,
            "detected": detected_bbox is not None,
            "bbox": list(detected_bbox) if detected_bbox else None,
            "confidence": round(best_conf, 3),
            "category": category,
            "queries": queries,
            "line1": line1,
            "line2": line2,
            "text_pos": list(text_pos),
            "text_size": list(text_size),
            "image_size": [pil_img.width, pil_img.height],
            "yolo_time_seconds": round(yolo_time, 3),
            "total_time_seconds": round(total_time, 3),
            "filename_tagged": filename_tagged,
            "filename_orig": filename_orig,
            "filename_box": filename_box,
            "tagged_url": f"/api/image/{filename_tagged}",
            "original_url": f"/api/image/{filename_orig}",
            "box_url": f"/api/image/{filename_box}" if filename_box else None,
            "download_url": f"/download/{filename_tagged}",
        }
    )


@app.route("/api/image/<filename>")
def api_serve_image(filename: str):
    """Serve image from outputs or temp uploads."""
    for folder in [OUTPUT_DIR, UPLOAD_TEMP_DIR]:
        target = folder / filename
        if target.is_file():
            return send_file(target, mimetype="image/jpeg")
    return jsonify({"error": "Image not found"}), 404


@app.route("/download/<filename>")
def api_download_image(filename: str):
    """Attachment download endpoint for high-resolution tagged output."""
    target = OUTPUT_DIR / filename
    if not target.is_file():
        target = UPLOAD_TEMP_DIR / filename
    if not target.is_file():
        return jsonify({"error": "File not found"}), 404
    return send_file(target, as_attachment=True, download_name=filename)


@app.route("/api/history")
def api_history():
    """Retrieve list of recently tagged items from disk."""
    items = []
    tagged_files = sorted(
        OUTPUT_DIR.glob("*_tagged.jpg"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:24]

    for p in tagged_files:
        stat = p.stat()
        name_parts = p.stem.split("_")
        display_name = " ".join(name_parts[1:-1]).title() if len(name_parts) >= 3 else p.stem
        items.append(
            {
                "filename": p.name,
                "name": display_name,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "size_kb": round(stat.st_size / 1024, 1),
                "url": f"/api/image/{p.name}",
                "download_url": f"/download/{p.name}",
            }
        )
    return jsonify({"items": items})


# ----------------------------------------------------------------------
# CLI and Server Entrypoint
# ----------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Standalone YOLO-World Item Name Stamping Studio")
    parser.add_argument("--port", type=int, default=5055, help="Port to bind server (default: 5055)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    return parser.parse_args()


def open_browser_delayed(url: str, delay: float = 1.0):
    def _open():
        time.sleep(delay)
        logger.info(f"Opening browser at: {url}")
        webbrowser.open(url)

    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    args = parse_args()
    url = f"http://{args.host}:{args.port}"
    print("=" * 70)
    print("  [STUDIO] HomeCartel Luxury Studio - YOLO Item Name Stamping Engine")
    print(f"  [SERVER] Running at: {url}")
    print("  [ENGINE] Free Local YOLO-World Detection (CPU)")
    print("=" * 70)

    if not args.no_browser:
        open_browser_delayed(url)

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
