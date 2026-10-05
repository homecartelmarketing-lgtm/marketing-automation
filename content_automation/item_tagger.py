"""Automated Zero-Cost Furniture Item Name Tagging Engine for Blended Feeds.

Detects furniture items (e.g. chandeliers, pendant lights, floor lamps, sofas)
using open-vocabulary YOLO-World (CPU, 100% free local inference) and stamps
an editorial two-line floating product tag directly beside the item:
    Line 1: Item Name in Poppins-Bold (19px)
    Line 2: Product Type in Poppins-Regular (19px)

Follows strict mode (skips stamping if confidence is below threshold to avoid misplacement)
and automatically uploads to Airtable field 'Blended Image with Name text'.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont
import requests

from content_automation.akeneo_client import split_item_name
from content_automation.media import download_to_temp_file

logger = logging.getLogger("item_tagger")

TARGET_BLENDED_FIELD = "Blended Image with Name text"
DEFAULT_FONT_SIZE = 19
DEFAULT_CONFIDENCE_THRESHOLD = 0.20
DEFAULT_MARGIN = 24
DEFAULT_CANVAS_PADDING = 40

# Deterministic lower-right fallback geometry per output format.
# Bottom margins clear Instagram chrome (feed image is clean; story has the
# reply bar; reel has caption + progress bar). The reel right margin additionally
# clears the like/comment/share action rail (x ~ 950-1080).
FALLBACK_BOTTOM_MARGIN = {"feed": 120, "story": 320, "reel": 320}
FALLBACK_RIGHT_MARGIN = {"feed": 60, "story": 60, "reel": 180}
FALLBACK_LINE_SPACING = 5

# Category to open-vocabulary detection queries
CATEGORY_DETECTION_MAP: dict[str, list[str]] = {
    "chandeliers": ["chandelier", "ceiling light fixture", "hanging light", "pendant light"],
    "chandelier": ["chandelier", "ceiling light fixture", "hanging light", "pendant light"],
    "pendant_lights": ["pendant light", "hanging lamp", "ceiling light fixture", "chandelier"],
    "pendant_light": ["pendant light", "hanging lamp", "ceiling light fixture", "chandelier"],
    "floor_lamps": ["floor lamp", "standing lamp", "tall lamp"],
    "floor_lamp": ["floor lamp", "standing lamp", "tall lamp"],
    "table_lamps": ["table lamp", "desk lamp", "bedside lamp"],
    "table_lamp": ["table lamp", "desk lamp", "bedside lamp"],
    "wall_sconces": ["wall lamp", "wall sconce", "sconce light"],
    "wall_sconce": ["wall lamp", "wall sconce", "sconce light"],
    "flush_mounts": ["flush mount light", "ceiling light fixture"],
    "flush_mount": ["flush mount light", "ceiling light fixture"],
    "ceiling_lights": ["ceiling light fixture", "ceiling light", "flush mount light", "ceiling lamp", "chandelier"],
    "ceiling_light": ["ceiling light fixture", "ceiling light", "flush mount light", "ceiling lamp", "chandelier"],
    "dining_tables": ["dining table", "table"],
    "dining_table": ["dining table", "table"],
    "coffee_tables": ["coffee table", "low table"],
    "coffee_table": ["coffee table", "low table"],
    "sofas": ["sofa", "couch", "living room sofa"],
    "sofa": ["sofa", "couch", "living room sofa"],
    "chairs": ["armchair", "accent chair", "dining chair", "chair"],
    "chair": ["armchair", "accent chair", "dining chair", "chair"],
}

_YOLO_MODEL: Any = None


def resolve_font_path(font_name: str) -> Path | None:
    """Resolve font file path across known project directories."""
    candidate_paths = [
        Path(__file__).parent / "fonts" / font_name,
        Path("content_automation/fonts") / font_name,
        Path("fonts") / font_name,
        Path(font_name),
    ]
    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate
    return None


def resolve_tag_names(
    raw_item_name: str, anchor: Any, type_hint: str = ""
) -> tuple[str, str]:
    """Split the 2-line YOLO tag into (item title, product type).

    `AirtableClient.product_from_record` already splits "Name | Type" into
    a bare `anchor.item_name` + `anchor.product_type`. The bare name has no
    pipe left, so the anchor's own product_type must head the fallback
    chain; otherwise rows with an empty "Product Type" field render
    Line 1 only.

    `type_hint` (fixture/category display type, e.g. "Pendant Light") is the
    final fallback so Line 2 is never empty and never an invented word.
    """
    fields = getattr(anchor, "fields", {}) or {}
    return split_item_name(
        str(raw_item_name or "").strip(),
        fallback_product_type=str(
            getattr(anchor, "product_type", "")
            or fields.get("Product Type")
            or type_hint
            or ""
        ),
    )


# Fixture/category code -> human display type for guaranteed Line 2.
CATEGORY_FIXTURE_TYPE: dict[str, str] = {
    "chandelier": "Chandelier",
    "chandeliers": "Chandelier",
    "cluster": "Cluster Chandelier",
    "cluster_chandelier": "Cluster Chandelier",
    "cluster_chandeliers": "Cluster Chandelier",
    "pendant": "Pendant Light",
    "pendant_light": "Pendant Light",
    "pendant_lights": "Pendant Light",
    "floor_lamp": "Floor Lamp",
    "floor_lamps": "Floor Lamp",
    "table_lamp": "Table Lamp",
    "table_lamps": "Table Lamp",
    "wall_light": "Wall Light",
    "wall_lights": "Wall Light",
    "wall_sconce": "Wall Sconce",
    "wall_sconces": "Wall Sconce",
    "ceiling_mounted": "Ceiling Light",
    "ceiling_light": "Ceiling Light",
    "flush_mount": "Ceiling Light",
    "linear_chandelier": "Linear Chandelier",
}


def fixture_display_type(category: str) -> str:
    """Human display type for a fixture/category code (guaranteed Line 2)."""
    cat_key = str(category or "").strip().lower().replace("-", "_")
    if cat_key in CATEGORY_FIXTURE_TYPE:
        return CATEGORY_FIXTURE_TYPE[cat_key]
    for key in sorted(CATEGORY_FIXTURE_TYPE, key=len, reverse=True):
        if key in cat_key:
            return CATEGORY_FIXTURE_TYPE[key]
    return ""


def normalize_output_format(output_format: str | None) -> str:
    """Normalize to ``feed`` | ``story`` | ``reel`` (defaults to ``story``)."""
    key = str(output_format or "").strip().lower()
    if key in FALLBACK_BOTTOM_MARGIN:
        return key
    if "feed" in key or "4:5" in key or "4x5" in key:
        return "feed"
    if "reel" in key:
        return "reel"
    return "story"


def measure_tag_pill(
    item_name: str = "",
    product_type: str = "",
    font_size: int = DEFAULT_FONT_SIZE,
) -> tuple[int, int]:
    """Measure the (width, height) of the 2-line tag pill in pixels."""
    raw_title = str(item_name or "").strip()
    raw_sub = str(product_type or "").strip()
    if "|" in raw_title and not raw_sub:
        raw_title, raw_sub = split_item_name(raw_title)
    title, subtitle = raw_title.strip(), raw_sub.strip()

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

    probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)

    def _size(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
        if not text:
            return 0, 0
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0], box[3] - box[1]

    title_w, title_h = _size(title, font_title)
    sub_w, sub_h = _size(subtitle, font_subtitle) if subtitle else (0, 0)
    return max(title_w, sub_w), title_h + (FALLBACK_LINE_SPACING + sub_h if subtitle else 0)


def lower_right_fallback_position(
    image_size: tuple[int, int],
    item_name: str = "",
    product_type: str = "",
    output_format: str | None = "story",
    font_size: int = DEFAULT_FONT_SIZE,
) -> tuple[int, int]:
    """Deterministic lower-right tag position for an output format.

    Right/bottom margins clear per-format Instagram chrome (see
    ``FALLBACK_*_MARGIN``). The pill is measured from the actual tag text so
    long item names stay fully inside the canvas.
    """
    fmt = normalize_output_format(output_format)
    w, h = image_size
    pill_w, pill_h = measure_tag_pill(item_name, product_type, font_size)
    right_margin = FALLBACK_RIGHT_MARGIN[fmt]
    bottom_margin = FALLBACK_BOTTOM_MARGIN[fmt]
    x = max(0, w - pill_w - right_margin)
    y = max(0, h - pill_h - bottom_margin)
    return x, y


def get_detection_queries_for_category(category: str) -> list[str]:
    """Return prioritized open-vocabulary queries for YOLO-World."""
    cat_key = str(category or "").strip().lower().replace("-", "_")
    if cat_key in CATEGORY_DETECTION_MAP:
        return CATEGORY_DETECTION_MAP[cat_key]

    # Resilient root category matching (e.g. 'pendant_lights_moodboard_story' -> 'pendant_lights')
    for key in sorted(CATEGORY_DETECTION_MAP.keys(), key=len, reverse=True):
        if key in cat_key:
            return CATEGORY_DETECTION_MAP[key]

    clean_name = cat_key.replace("_", " ")
    if clean_name:
        return [clean_name, f"{clean_name} fixture", "furniture", "light fixture"]
    return ["lighting fixture", "furniture item", "chandelier", "lamp", "sofa"]


def resolve_yolo_model_path(model_name: str = "yolov8s-worldv2.pt") -> str:
    """Resolve model weights from assets/models/ first, with fallback to root."""
    repo_root = Path(__file__).resolve().parent.parent
    candidates = [
        repo_root / "assets" / "models" / model_name,
        repo_root / model_name,
        Path(model_name),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return model_name


def get_yolo_world_model(model_name: str = "yolov8s-worldv2.pt") -> Any:
    """Lazy-load and cache singleton YOLO-World open-vocabulary detector."""
    global _YOLO_MODEL
    if _YOLO_MODEL is None:
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as err:
            raise ImportError(
                "ultralytics is required for YOLO-World item detection. Run: pip install ultralytics"
            ) from err

        target_model = resolve_yolo_model_path(model_name)
        logger.info(f"Initializing YOLO-World model '{target_model}' on CPU...")
        _YOLO_MODEL = YOLO(target_model)
    return _YOLO_MODEL


def detect_item_bbox(
    image: Image.Image,
    category: str = "",
    *,
    queries: list[str] | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    model: Any = None,
) -> tuple[int, int, int, int] | None:
    """Detect the target furniture item bounding box using YOLO-World.

    Returns:
        (x1, y1, x2, y2) pixel bounding box, or None if not detected above threshold (strict mode).
    """
    if model is None:
        model = get_yolo_world_model()

    search_queries = queries or get_detection_queries_for_category(category)
    model.set_classes(search_queries)

    # Convert to RGB if needed (handles RGBA or palletized images)
    rgb_img = image.convert("RGB")
    width, height = rgb_img.size

    # Run inference on CPU
    results = model.predict(source=rgb_img, conf=confidence_threshold, device="cpu", verbose=False)
    if not results or len(results) == 0:
        return None

    result = results[0]
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return None

    # Filter and find the best bounding box
    best_box = None
    best_score = -1.0

    for box in boxes:
        conf = float(box.conf[0])
        x1, y1, x2, y2 = [int(round(coord)) for coord in box.xyxy[0].tolist()]

        box_w = x2 - x1
        box_h = y2 - y1

        # Reject tiny noise boxes (less than 30px or < 1% canvas area)
        if box_w < 30 or box_h < 30:
            continue
        # Reject giant boxes that cover > 90% of entire canvas (likely full room)
        if (box_w * box_h) > (width * height * 0.90):
            continue

        if conf > best_score:
            best_score = conf
            best_box = (x1, y1, x2, y2)

    return best_box


def brightest_region_center(
    image: Image.Image,
    grid: int = 6,
) -> tuple[int, int]:
    """Center of the brightest grid cell (cheap lighting-fixture saliency cue)."""
    gray = image.convert("L")
    w, h = gray.size
    px = gray.load()
    best: tuple[int, int] | None = None
    best_score = -1.0
    for gy in range(grid):
        for gx in range(grid):
            x0, y0 = gx * w // grid, gy * h // grid
            x1, y1 = (gx + 1) * w // grid, (gy + 1) * h // grid
            total = 0
            count = 0
            for yy in range(y0, y1, max(1, (y1 - y0) // 8)):
                for xx in range(x0, x1, max(1, (x1 - x0) // 8)):
                    total += px[xx, yy]
                    count += 1
            score = total / max(count, 1)
            if score > best_score:
                best_score = score
                best = ((x0 + x1) // 2, (y0 + y1) // 2)
    return best or (w // 2, h // 2)


def bbox_near_point(
    bbox: tuple[int, int, int, int],
    point: tuple[int, int],
    tolerance: float = 0.35,
    image_size: tuple[int, int] | None = None,
) -> bool:
    """True when a bbox edge/center is within tolerance (fraction of diagonal)."""
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    px, py = point
    corners = [(x1, y1), (x2, y1), (x1, y2), (x2, y2), (cx, cy)]
    if image_size is None:
        diag = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1.0
    else:
        diag = (image_size[0] ** 2 + image_size[1] ** 2) ** 0.5 or 1.0
    return any((((cx_ - px) ** 2 + (cy_ - py) ** 2) ** 0.5) / diag <= tolerance for cx_, cy_ in corners)


def detect_with_retry_ladder(
    image: Image.Image,
    category: str = "",
    *,
    thresholds: tuple[float, ...] = (DEFAULT_CONFIDENCE_THRESHOLD, 0.10),
    generic_queries: list[str] | None = None,
    validate_saliency: bool = True,
) -> tuple[int, int, int, int] | None:
    """YOLO-World detection with a retry ladder + brightness-saliency validation.

    Tries category queries at each threshold (high to low), then generic
    queries at the lowest threshold. A hit far from the brightest region is
    treated as a likely false positive (e.g. window/daylight) and retried —
    only the final fallback position is deterministic lower-right.
    """
    tried: list[tuple[float, list[str]]] = [
        (t, get_detection_queries_for_category(category)) for t in thresholds
    ]
    if generic_queries:
        tried.append((thresholds[-1], generic_queries))

    bright = brightest_region_center(image) if validate_saliency else None
    for threshold, queries in tried:
        try:
            bbox = detect_item_bbox(image, category=category, queries=queries, confidence_threshold=threshold)
        except Exception:
            continue
        if bbox is None:
            continue
        if validate_saliency and bright is not None:
            if not bbox_near_point(bbox, bright, image_size=image.size):
                logger.info(
                    f"[TAGGER] Rejecting bbox {bbox} (far from bright region) at "
                    f"conf {threshold}; retrying..."
                )
                continue
        return bbox
    return None


def calculate_adaptive_text_position(
    canvas_width: int,
    canvas_height: int,
    bbox: tuple[int, int, int, int],
    text_width: int,
    text_height: int,
    *,
    margin: int = DEFAULT_MARGIN,
    canvas_padding: int = DEFAULT_CANVAS_PADDING,
) -> tuple[int, int]:
    """Compute optimal (x, y) placement beside the detected item.

    Prioritizes right-hand side placement, auto-flipping to left side if
    too close to the right canvas margin. Y coordinate centers against item.
    """
    bx1, by1, bx2, by2 = bbox

    # 1. Horizontal calculation
    right_candidate_x = bx2 + margin
    if (right_candidate_x + text_width) <= (canvas_width - canvas_padding):
        text_x = right_candidate_x
    else:
        # Flip to left side
        left_candidate_x = bx1 - margin - text_width
        text_x = max(canvas_padding, left_candidate_x)

    # 2. Vertical calculation
    # Center against upper-mid section of the fixture
    fixture_mid_y = int(by1 + (by2 - by1) * 0.40)
    text_y = fixture_mid_y - (text_height // 2)

    # Clamp within canvas boundaries with Instagram Story safe-zone support
    if canvas_height >= 1800:
        # 9:16 Story Canvas (1080x1920): Clear top header (160px) and bottom interactive area (1650px)
        min_y = max(canvas_padding, 160)
        max_y = min(canvas_height - canvas_padding - text_height, 1650 - text_height)
    else:
        # Standard Feed Canvas (e.g. 4:5 1080x1350)
        min_y = canvas_padding
        max_y = canvas_height - canvas_padding - text_height

    text_y = max(min_y, min(text_y, max_y))

    return text_x, text_y


def render_item_name_tag(
    image: Image.Image,
    bbox: tuple[int, int, int, int] | None = None,
    item_name: str = "",
    product_type: str = "",
    *,
    position: tuple[int, int] | None = None,
    font_size: int = DEFAULT_FONT_SIZE,
    text_color: tuple[int, int, int] = (255, 255, 255),
    with_shadow: bool = False,
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 180),
    font_bold_path: Path | str | None = None,
    font_regular_path: Path | str | None = None,
    line_spacing: int = 5,
) -> Image.Image:
    """Render 2-line floating product tag directly beside the furniture item.

    Line 1: Item Name in Poppins-Bold (19px) - Pure Clean Solid White (#FFFFFF)
    Line 2: Product Type in Poppins-Regular (19px) - Pure Clean Solid White (#FFFFFF)
    """
    img = image.convert("RGBA")
    w, h = img.size

    # Split item_name if contains pipe delimiter (e.g. "Halvor | Modern Floor Lamp")
    raw_title = str(item_name or "").strip()
    raw_sub = str(product_type or "").strip()
    if "|" in raw_title and not raw_sub:
        raw_title, raw_sub = split_item_name(raw_title)

    title = raw_title.strip()
    subtitle = raw_sub.strip()

    # Resolve fonts
    bold_path = Path(font_bold_path) if font_bold_path else resolve_font_path("Poppins-Bold.ttf")
    reg_path = Path(font_regular_path) if font_regular_path else (
        resolve_font_path("Poppins-Regular.ttf") or bold_path
    )

    try:
        font_title = ImageFont.truetype(str(bold_path), font_size) if bold_path else ImageFont.load_default()
    except Exception:
        font_title = ImageFont.load_default()

    try:
        font_subtitle = ImageFont.truetype(str(reg_path), font_size) if reg_path else font_title
    except Exception:
        font_subtitle = font_title

    # Measure text bounding boxes
    draw_dummy = ImageDraw.Draw(img)

    def get_text_size(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
        if not text:
            return 0, 0
        box = draw_dummy.textbbox((0, 0), text, font=font)
        return box[2] - box[0], box[3] - box[1]

    title_w, title_h = get_text_size(title, font_title)
    sub_w, sub_h = get_text_size(subtitle, font_subtitle) if subtitle else (0, 0)

    total_w = max(title_w, sub_w)
    total_h = title_h + (line_spacing + sub_h if subtitle else 0)

    # Determine adaptive placement coordinates
    if position is not None:
        x, y = position
    elif bbox is not None:
        x, y = calculate_adaptive_text_position(w, h, bbox, total_w, total_h)
    else:
        # Default safe Upper/Mid-Left fallback zone (X: 100, Y: 800 for 1080x1920)
        x = int(round(100 * w / 1080))
        y = int(round(800 * h / 1920))

    # Draw onto transparent text layer (pure solid white text, no black outline)
    txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)

    if with_shadow:
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 1), (1, 2)]:
            draw.text((x + dx, y + dy), title, font=font_title, fill=shadow_color)
            if subtitle:
                draw.text((x + dx, y + title_h + line_spacing + dy), subtitle, font=font_subtitle, fill=shadow_color)

    # Draw Line 1: Title (Bold, Solid White)
    draw.text((x, y), title, font=font_title, fill=(*text_color, 255))

    # Draw Line 2: Subtitle (Regular, Solid White), if present
    if subtitle:
        sub_y = y + title_h + line_spacing
        draw.text((x, sub_y), subtitle, font=font_subtitle, fill=(*text_color, 255))

    combined = Image.alpha_composite(img, txt_layer)
    return combined.convert("RGB")


def tag_blended_image(
    image_input: Path | str | Image.Image,
    item_name: str,
    product_type: str = "",
    category: str = "",
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    destination: Path | str | None = None,
    fallback_if_undetected: bool = True,
    fallback_position: tuple[int, int] | None = None,
    output_format: str | None = "story",
    retry_thresholds: tuple[float, ...] = (DEFAULT_CONFIDENCE_THRESHOLD, 0.10),
    retry_queries: tuple[str, ...] = ("lamp", "chandelier", "light fixture"),
) -> tuple[Image.Image | None, tuple[int, int, int, int] | None]:
    """Detect item and stamp the 2-line floating tag onto a blended image.

    Detection runs a retry ladder (category queries at each threshold, then
    generic queries) before falling back to the deterministic lower-right
    position for ``output_format`` (``feed`` | ``story`` | ``reel``).

    Returns:
        (tagged_image, bbox) or (None, None) if detection failed in strict mode.
        If fallback_if_undetected is True, returns (tagged_image, None) with
        the tag positioned at the lower-right fallback coordinates.
    """
    if isinstance(image_input, Image.Image):
        image = image_input
    else:
        image = Image.open(image_input)

    try:
        bbox = detect_with_retry_ladder(
            image,
            category=category,
            thresholds=retry_thresholds,
            generic_queries=list(retry_queries),
        )
    except Exception as detect_err:
        # YOLO-World needs ultralytics + CLIP; hosted images may lack them. Treat that as
        # "undetected" so the tag still lands at the deterministic fallback position.
        logger.warning(f"[TAGGER] Item detection unavailable ({detect_err}); using fallback handling.")
        bbox = None
    if bbox is None:
        if not fallback_if_undetected:
            logger.warning(
                f"[STRICT MODE] Item '{item_name}' (category: '{category}') was not detected. "
                f"Skipping name tag to prevent misplacement."
            )
            return None, None

        logger.info(
            f"[FALLBACK MODE] Item '{item_name}' (category: '{category}') undetected. "
            f"Applying deterministic lower-right tag position ({normalize_output_format(output_format)})..."
        )
        pos = fallback_position
        if pos is None:
            pos = lower_right_fallback_position(
                image.size,
                item_name=item_name,
                product_type=product_type,
                output_format=output_format,
            )

        tagged_image = render_item_name_tag(
            image=image,
            bbox=None,
            item_name=item_name,
            product_type=product_type,
            position=pos,
            font_size=DEFAULT_FONT_SIZE,
        )
        if destination:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            tagged_image.save(dest_path, quality=95)
        return tagged_image, None

    tagged_image = render_item_name_tag(
        image=image,
        bbox=bbox,
        item_name=item_name,
        product_type=product_type,
        font_size=DEFAULT_FONT_SIZE,
    )

    if destination:
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tagged_image.save(dest_path, quality=95)

    return tagged_image, bbox


def tag_and_upload_blended_image(
    airtable: Any,
    record_id: str,
    blended_source: str | Path | list[Any] | dict[str, Any],
    item_name: str,
    product_type: str = "",
    category: str = "",
    *,
    target_field: str = TARGET_BLENDED_FIELD,
    output_filename_prefix: str = "blended_named",
    fallback_if_undetected: bool = True,
    fallback_position: tuple[int, int] | None = None,
    output_tagged_paths: list[Path] | None = None,
    output_format: str | None = "story",
) -> bool:
    """Helper to process one or multiple blended images and upload to Airtable field."""
    # Resolve image URL(s) or file path(s)
    image_urls: list[str] = []
    if isinstance(blended_source, list):
        for item in blended_source:
            if isinstance(item, dict) and (item.get("url") or item.get("permalink")):
                image_urls.append(str(item.get("url") or item.get("permalink")))
            elif isinstance(item, str) and item.startswith("http"):
                image_urls.append(item)
            elif isinstance(item, (str, Path)) and Path(item).is_file():
                image_urls.append(str(item))
    elif isinstance(blended_source, dict) and (blended_source.get("url") or blended_source.get("permalink")):
        image_urls.append(str(blended_source.get("url") or blended_source.get("permalink")))
    elif isinstance(blended_source, str) and blended_source.startswith("http"):
        image_urls.append(blended_source)
    elif isinstance(blended_source, (str, Path)) and Path(blended_source).is_file():
        image_urls.append(str(blended_source))

    if not image_urls:
        logger.warning(f"[SKIP] No valid image sources found for record {record_id}")
        return False

    try:
        airtable.ensure_fields({target_field: "multipleAttachments"})
    except Exception:
        pass

    uploaded_count = 0
    for idx, source in enumerate(image_urls, start=1):
        temp_download = None
        local_path: Path
        try:
            if source.startswith("http"):
                resp = requests.get(source, stream=True, timeout=30)
                temp_download = download_to_temp_file(
                    resp,
                    prefix="blend_tag_in_",
                    suffix=".jpg",
                    context=f"Download blended image from {source}",
                )
                local_path = temp_download.path
            else:
                local_path = Path(source)

            temp_out_dir = Path("output/temp/tagged_blends")
            temp_out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{output_filename_prefix}_{record_id}_{idx}.jpg"
            out_file = temp_out_dir / filename

            tagged_img, bbox = tag_blended_image(
                image_input=local_path,
                item_name=item_name,
                product_type=product_type,
                category=category,
                fallback_if_undetected=fallback_if_undetected,
                fallback_position=fallback_position,
                output_format=output_format,
                destination=out_file,
            )
            if tagged_img is None:
                continue

            if output_tagged_paths is not None:
                output_tagged_paths.append(out_file)

            # Upload to Airtable
            class TempWrapper:
                def __init__(self, p: Path):
                    self.path = p
                    self.filename = filename
                    self.content_type = "image/jpeg"
                def cleanup(self):
                    pass

            try:
                airtable.upload_attachment(record_id, target_field, TempWrapper(out_file), filename)
            except TypeError:
                airtable.upload_attachment(record_id, target_field, TempWrapper(out_file))
            uploaded_count += 1
            print(f"[OK] Uploaded tagged blended image ({filename}) to '{target_field}' for record {record_id}")
        except Exception as err:
            print(f"[ERROR] Failed tagging/uploading blended image for record {record_id}: {err}")
        finally:
            if temp_download:
                temp_download.cleanup()

    return uploaded_count > 0
