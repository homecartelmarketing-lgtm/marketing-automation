"""Stamping a fixed-position logo onto a generated photo.

Kept free of any Airtable or provider knowledge so the placement maths can be
exercised on its own. The coordinates come from a design canvas rather than the
finished image, because providers do not promise an exact pixel size for a given
aspect ratio -- storing the box as a fraction of that canvas keeps the logo in
the same relative spot whatever comes back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps


@dataclass(frozen=True)
class LogoBox:
    """Where the logo sits, expressed against the canvas it was designed on."""

    x: float
    y: float
    width: float
    height: float
    canvas_width: int
    canvas_height: int
    # Multiplier on the box, anchored at its bottom-left corner so a bigger
    # mark grows up and to the right and keeps its margins. Raise this if the
    # watermark still reads small in the feed.
    scale: float = 1.0

    def scaled(self) -> tuple[float, float, float, float]:
        """``(x, y, width, height)`` after ``scale``, in canvas units."""
        width = self.width * self.scale
        height = self.height * self.scale
        return self.x, self.y + self.height - height, width, height


# HomeCartel brand mark, bottom-left of a Canva Instagram Post (4:5). The 108px
# left margin and the 108px gap below the box (1350 - 1178.5 - 63.5) match.
HOMECARTEL_LOGO_BOX = LogoBox(
    x=108.0,
    y=1178.5,
    width=190.3,
    height=63.5,
    canvas_width=1080,
    canvas_height=1350,
)

# HomeCartel brand mark, top-right of a Canva Instagram Story (9:16, 1080x1920).
# Matches Canva position: Width 190.3, Height 63.5, X 781.7, Y 108.0.
# 108px margin from top, 108px margin from right edge (1080 - 781.7 - 190.3 = 108).
HOMECARTEL_STORY_LOGO_BOX = LogoBox(
    x=781.7,
    y=108.0,
    width=190.3,
    height=63.5,
    canvas_width=1080,
    canvas_height=1920,
)


# Alpha at or above this counts as part of the mark. Background removers leave
# a dusting of alpha 1-15 across the whole canvas, and a plain non-zero test
# treats that haze as content -- which pins the bounding box to the full export
# and shrinks the mark to a fraction of the space it was given.
ALPHA_THRESHOLD = 8


def visible_bounds(
    logo: Image.Image,
    threshold: int = ALPHA_THRESHOLD,
) -> tuple[int, int, int, int] | None:
    """Bounding box of the logo's visible pixels, or ``None`` if fully clear.

    Read off the alpha channel alone. ``Image.getbbox()`` on an RGBA image
    treats any non-zero channel as content, so a transparent *white* margin --
    the usual result of exporting a light logo -- would not be trimmed.
    """
    alpha = logo.getchannel("A")
    return alpha.point(lambda value: 255 if value >= threshold else 0).getbbox()


def prepare_logo_image(logo_source: Image.Image) -> Image.Image:
    """Ensure logo has transparent background, removing solid background if present.

    Handles:
    1. Transparent PNGs (preserves existing alpha).
    2. Solid black background exports (e.g. Stories Sandbox.jpg canvas).
    3. Solid white or neutral background exports.
    4. Auto-detects background color from corner pixels if opaque.
    """
    logo = logo_source.convert("RGBA")
    alpha = logo.getchannel("A")
    min_a, max_a = alpha.getextrema()

    # If the image is fully opaque (e.g. JPG or non-transparent PNG), remove background
    if min_a >= 250:
        try:
            import numpy as np

            arr = np.array(logo)
            h, w, _ = arr.shape
            corners = np.array([
                arr[0, 0, :3],
                arr[0, w - 1, :3],
                arr[h - 1, 0, :3],
                arr[h - 1, w - 1, :3],
            ], dtype=np.float32)
            bg_rgb = corners.mean(axis=0)

            # Tolerance for background removal (handles JPEG compression noise)
            tolerance = 45.0
            diff = np.max(np.abs(arr[:, :, :3].astype(np.float32) - bg_rgb), axis=2)
            mask = diff <= tolerance
            arr[mask, 3] = 0

            # Soften edges slightly
            edge_mask = (diff > tolerance) & (diff <= tolerance + 20.0)
            if np.any(edge_mask):
                edge_alphas = (255.0 * ((diff[edge_mask] - tolerance) / 20.0)).astype(np.uint8)
                arr[edge_mask, 3] = edge_alphas

            processed_logo = Image.fromarray(arr, "RGBA")
            if visible_bounds(processed_logo) is not None:
                return processed_logo
            return logo_source.convert("RGBA")
        except Exception:
            # Fallback to pixel iteration if numpy is unavailable
            pixels = logo.load()
            width, height = logo.size
            corners = [
                pixels[0, 0][:3],
                pixels[width - 1, 0][:3],
                pixels[0, height - 1][:3],
                pixels[width - 1, height - 1][:3],
            ]
            bg_r = sum(c[0] for c in corners) // 4
            bg_g = sum(c[1] for c in corners) // 4
            bg_b = sum(c[2] for c in corners) // 4
            tolerance = 45

            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    diff = max(abs(r - bg_r), abs(g - bg_g), abs(b - bg_b))
                    if diff <= tolerance:
                        pixels[x, y] = (r, g, b, 0)
            if visible_bounds(logo) is None:
                return logo_source.convert("RGBA")

    return logo


def logo_placement(
    base_size: tuple[int, int],
    logo_size: tuple[int, int],
    box: LogoBox = HOMECARTEL_LOGO_BOX,
) -> tuple[int, int, int, int]:
    """``(left, top, width, height)`` for the logo, in base-image pixels.

    The box is scaled onto the base image, then the logo is fitted inside it
    with its own proportions intact and centred on whatever slack remains.
    ``logo_size`` is the size of the *visible* mark: pass trimmed dimensions,
    or the transparent margin eats into the space the brand mark should fill.
    """
    base_width, base_height = base_size
    logo_width, logo_height = logo_size
    if logo_width <= 0 or logo_height <= 0:
        raise ValueError(f"Logo has no area: {logo_size}")

    box_x, box_y, box_width, box_height = box.scaled()
    scale_x = base_width / box.canvas_width
    scale_y = base_height / box.canvas_height
    target_width = box_width * scale_x
    target_height = box_height * scale_y

    ratio = min(target_width / logo_width, target_height / logo_height)
    width = max(1, round(logo_width * ratio))
    height = max(1, round(logo_height * ratio))

    left = round(box_x * scale_x + (target_width - width) / 2)
    top = round(box_y * scale_y + (target_height - height) / 2)
    return left, top, width, height


def stamp_logo(
    base_path: Path | Image.Image,
    logo_path: Path | Image.Image,
    destination: Path | None = None,
    box: LogoBox = HOMECARTEL_LOGO_BOX,
) -> Path | Image.Image:
    """Composite ``logo_path`` onto ``base_path`` and optionally write a JPEG."""
    if isinstance(base_path, (str, Path)):
        source_base = Image.open(base_path)
        close_base = True
    else:
        source_base = base_path
        close_base = False

    if isinstance(logo_path, (str, Path)):
        source_logo = Image.open(logo_path)
        close_logo = True
    else:
        source_logo = logo_path
        close_logo = False

    try:
        base = source_base.convert("RGBA")
        logo = prepare_logo_image(source_logo)
        # Fit the mark itself, not the canvas it was exported on. Without this
        # a logo saved with transparent padding is shrunk to fit the padding,
        # and the visible wordmark lands far smaller than the box asks for.
        if bounds := visible_bounds(logo):
            logo = logo.crop(bounds)
        left, top, width, height = logo_placement(base.size, logo.size, box)
        resized = logo.resize((width, height), Image.LANCZOS)
        # The logo's own alpha is the mask, so a transparent PNG keeps the
        # photo visible around the mark instead of punching a box out of it.
        base.paste(resized, (left, top), resized)
        result_rgb = base.convert("RGB")

        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            result_rgb.save(
                dest_path,
                format="JPEG",
                quality=95,
                optimize=True,
            )
            return dest_path
        return result_rgb
    finally:
        if close_base:
            source_base.close()
        if close_logo:
            source_logo.close()


def split_item_name_for_story(name: str) -> tuple[str, str]:
    """Split full product item name into (title_bold, subtitle_regular).

    Formatting specification:
    - Line 1 (Bold): Brand series or primary identifier (e.g. 'Keyes', 'Zygadlo', 'Dorvalira D')
    - Line 2 (Regular): Product category and description (e.g. 'Modern LED Floor Lamp', 'Luxury Modern Chandelier')

    Examples:
    - 'Keyes I Modern LED Floor Lamp' -> ('Keyes', 'Modern LED Floor Lamp')
    - 'Keyes Modern LED Floor Lamp'   -> ('Keyes', 'Modern LED Floor Lamp')
    - 'Zygadlo | Luxury Modern Chandelier' -> ('Zygadlo', 'Luxury Modern Chandelier')
    - 'Dorvalira D | Contemporary Floor Lamp' -> ('Dorvalira D', 'Contemporary Floor Lamp')
    - 'Zerrie Linear Brass Island Chandelier' -> ('Zerrie', 'Linear Brass Island Chandelier')
    """
    import re

    clean = str(name or "").strip().strip("[]")
    if not clean:
        return "", ""

    # Case 1: Pipe separated, e.g. "Zygadlo | Luxury Modern Chandelier"
    if "|" in clean:
        parts = [p.strip() for p in clean.split("|", 1) if p.strip()]
        if len(parts) == 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            clean = parts[0]

    # Case 2: Match descriptive keyword boundary
    keywords = [
        "Modern", "Contemporary", "Luxury", "Minimalist", "Nordic", "Industrial",
        "Vintage", "Retro", "Linear", "LED", "Floor Lamp", "Table Lamp",
        "Pendant Light", "Pendant", "Chandelier", "Wall Sconce", "Wall Light",
        "Ceiling Light", "Desk Lamp", "Cluster Chandelier", "Ceramic Table Lamp",
        "Smoke Glass", "Brass", "Glass",
    ]
    pattern = r"\b(" + "|".join(keywords) + r")\b"
    match = re.search(pattern, clean, flags=re.IGNORECASE)
    if match and match.start() > 0:
        title = clean[:match.start()].strip().rstrip("|-: ")
        # Strip trailing Roman numerals/variant letters e.g. "Keyes I" -> "Keyes"
        title_clean = re.sub(r"\s+(?:[IVXLCDM]+|[A-Z]|\d+)\b$", "", title, flags=re.IGNORECASE).strip()
        subtitle = clean[match.start():].strip()
        return (title_clean if title_clean else title), subtitle

    # Case 3: Fallback split on first word
    words = clean.split(maxsplit=1)
    if len(words) == 2:
        return words[0], words[1]
    return clean, ""


def overlay_story_item_names(
    canvas: Image.Image,
    item_names: list[str],
    font_bold_path: Path | str | None = None,
    font_regular_path: Path | str | None = None,
    title_font_size: int = 34,
    subtitle_font_size: int = 24,
    text_color: tuple[int, int, int] = (255, 255, 255),
    shadow_color: tuple[int, int, int, int] | None = None,
    x_offset: float = 90.2,
    y_first_slot: float = 530.0,
    slot_height: int = 640,
) -> Image.Image:
    """Overlay two-line item names (Bold Series Title + Regular Subtitle) onto each slot of a 9:16 story grid.

    Example layout per slot:
      Keyes                     (Poppins-Bold, size 34)
      Modern LED Floor Lamp     (Poppins-Regular, size 24)

    Coordinates based on Canva layout:
    - Left margin X: 90.2 px
    - Slot 1 Y: ~530.0 px (Title) / ~572.0 px (Subtitle)
    - Slot 2 Y: Slot 1 Y + 640 px
    - Slot 3 Y: Slot 1 Y + 1280 px
    """
    if not item_names:
        return canvas

    if font_bold_path is None:
        font_bold_path = _resolve_font_path("Poppins-Bold.ttf")
    if font_regular_path is None:
        font_regular_path = _resolve_font_path("Poppins-Regular.ttf") or font_bold_path

    try:
        font_title = (
            ImageFont.truetype(str(font_bold_path), title_font_size)
            if font_bold_path
            else ImageFont.load_default()
        )
    except Exception:
        font_title = ImageFont.load_default()

    try:
        font_subtitle = (
            ImageFont.truetype(str(font_regular_path), subtitle_font_size)
            if font_regular_path
            else font_title
        )
    except Exception:
        font_subtitle = font_title

    img = canvas.convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    scale_y = canvas.height / 1920.0
    scale_x = canvas.width / 1080.0

    for idx, name in enumerate(item_names[:3]):
        if not name or not str(name).strip():
            continue
        title, subtitle = split_item_name_for_story(name)
        if not title:
            continue

        x = int(round(x_offset * scale_x))
        base_slot_y = (y_first_slot + idx * slot_height) * scale_y

        if subtitle:
            y_title = int(round(base_slot_y))
            y_sub = int(round(base_slot_y + 42 * scale_y))

            if shadow_color is not None:
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 1), (1, 2), (0, 2)]:
                    draw.text((x + dx, y_title + dy), title, font=font_title, fill=shadow_color)
            draw.text((x, y_title), title, font=font_title, fill=(*text_color, 255))

            if shadow_color is not None:
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 1), (1, 2), (0, 2)]:
                    draw.text((x + dx, y_sub + dy), subtitle, font=font_subtitle, fill=shadow_color)
            draw.text((x, y_sub), subtitle, font=font_subtitle, fill=(*text_color, 255))
        else:
            # Single line title
            y_single = int(round((y_first_slot + 20 + idx * slot_height) * scale_y))
            if shadow_color is not None:
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 1), (1, 2), (0, 2)]:
                    draw.text((x + dx, y_single + dy), title, font=font_title, fill=shadow_color)
            draw.text((x, y_single), title, font=font_title, fill=(*text_color, 255))

    combined = Image.alpha_composite(img, txt_layer)
    return combined.convert("RGB")


def create_three_image_story_grid(
    image_paths: list[Path | str | Image.Image],
    destination: Path | str | None = None,
    logo_path: Path | str | Image.Image | None = None,
    canvas_size: tuple[int, int] = (1080, 1920),
    logo_box: LogoBox = HOMECARTEL_STORY_LOGO_BOX,
    item_names: list[str] | None = None,
) -> Path | Image.Image:
    """Compose 3 images into a vertical 9:16 grid (3 equal rows) with optional logo and item names overlay.

    Each image fills a 1080x640 section with cover-crop (no distortion or letterboxing).
    Slot 1 (top): row 0 -> y: 0 to 640
    Slot 2 (middle): row 1 -> y: 640 to 1280
    Slot 3 (bottom): row 2 -> y: 1280 to 1920
    """
    if len(image_paths) != 3:
        raise ValueError(
            f"create_three_image_story_grid requires exactly 3 images, got {len(image_paths)}"
        )

    canvas_width, canvas_height = canvas_size
    slot_width = canvas_width
    slot_height = canvas_height // 3  # 640 for 1920 height

    canvas = Image.new("RGB", (canvas_width, canvas_height), (255, 255, 255))

    for idx, img_input in enumerate(image_paths):
        if isinstance(img_input, (str, Path)):
            with Image.open(img_input) as img:
                fitted = ImageOps.fit(
                    img.convert("RGB"),
                    (slot_width, slot_height),
                    method=Image.LANCZOS,
                    centering=(0.5, 0.5),
                )
        else:
            fitted = ImageOps.fit(
                img_input.convert("RGB"),
                (slot_width, slot_height),
                method=Image.LANCZOS,
                centering=(0.5, 0.5),
            )

        y_pos = idx * slot_height
        canvas.paste(fitted, (0, y_pos))

    # If item_names are provided, overlay them in Poppins-Bold at Canva coordinates
    if item_names:
        canvas = overlay_story_item_names(canvas, item_names)

    # If logo is provided, stamp it onto canvas
    if logo_path is not None:
        stamped = stamp_logo(canvas, logo_path, destination=None, box=logo_box)
        if isinstance(stamped, Image.Image):
            canvas = stamped

    if destination is not None:
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(
            dest_path,
            format="JPEG",
            quality=95,
            optimize=True,
        )
        return dest_path

    return canvas


@dataclass(frozen=True)
class StoryTextBox:
    """Bounding box for story typography layout on a design canvas."""

    x: float
    y: float
    width: float
    height: float
    canvas_width: int = 1080
    canvas_height: int = 1920


# Canva Instagram Story (9:16, 1080x1920) CTA text layout box:
# Width: 820.8 px, Height: 304.6 px, X: 151.2 px, Y: 1521.8 px
# Right margin: 151.2 + 820.8 = 972.0 px (108 px from right edge)
CTA_STORY_TEXT_BOX = StoryTextBox(
    x=151.2,
    y=1521.8,
    width=820.8,
    height=304.6,
    canvas_width=1080,
    canvas_height=1920,
)


def _resolve_font_path(font_name: str) -> Path | None:
    """Find a TTF font file by searching known candidate paths."""
    candidate_paths = [
        Path(__file__).parent / "fonts" / font_name,
        Path("content_automation/fonts") / font_name,
        Path("fonts") / font_name,
        Path(font_name),
    ]
    for c in candidate_paths:
        if c.is_file():
            return c
    return None


def overlay_cta_story_layout(
    canvas: Image.Image,
    item_name: str = "Singkwenta Dose",
    *,
    font_bold_path: Path | str | None = None,
    font_regular_path: Path | str | None = None,
    text_box: StoryTextBox = CTA_STORY_TEXT_BOX,
    headline_font_size: int = 48,
    body_font_size: int = 28,
    text_color: tuple[int, int, int] = (255, 255, 255),
    with_shadow: bool = False,
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 180),
) -> Image.Image:
    """Overlay right-aligned HomeCartel CTA text layout onto a 9:16 story image.

    Typography specification:
    - Bounding Box: X=151.2, Y=1521.8, Width=820.8, Height=304.6 (Right X = 972.0)
    - Headline / Item Name: Poppins-Bold, size 48 (auto-fits width if long)
    - Follow text: Poppins-Regular, size 28 (not bold, no shadow)
      Follow @HomeCartel for
      more home inspiration.
    - Contact info: Poppins-Regular, size 28
      0977 825 5588 (or send us a DM)
      (02) 8248 8071 | Dial 1
      sales@homecartel.com
    """
    if font_bold_path is None:
        font_bold_path = _resolve_font_path("Poppins-Bold.ttf")
    if font_regular_path is None:
        font_regular_path = _resolve_font_path("Poppins-Regular.ttf") or font_bold_path

    # Compute scaling factors if canvas dimensions differ from 1080x1920
    scale_x = canvas.width / text_box.canvas_width
    scale_y = canvas.height / text_box.canvas_height
    right_x = (text_box.x + text_box.width) * scale_x
    start_y = text_box.y * scale_y
    max_box_width = text_box.width * scale_x

    scaled_headline_size = int(round(headline_font_size * scale_y))
    scaled_body_size = int(round(body_font_size * scale_y))

    # Load body fonts
    try:
        font_body_bold = (
            ImageFont.truetype(str(font_bold_path), scaled_body_size)
            if font_bold_path
            else ImageFont.load_default()
        )
    except Exception:
        font_body_bold = ImageFont.load_default()

    try:
        font_body_reg = (
            ImageFont.truetype(str(font_regular_path), scaled_body_size)
            if font_regular_path
            else font_body_bold
        )
    except Exception:
        font_body_reg = font_body_bold

    # Headline font with auto-scaling to avoid overflowing the box width
    clean_title = str(item_name or "Singkwenta Dose").strip()
    title_size = scaled_headline_size
    font_title = None
    while title_size >= int(round(24 * scale_y)):
        try:
            candidate_font = (
                ImageFont.truetype(str(font_bold_path), title_size)
                if font_bold_path
                else ImageFont.load_default()
            )
        except Exception:
            candidate_font = ImageFont.load_default()
            font_title = candidate_font
            break

        bbox = candidate_font.getbbox(clean_title)
        if (bbox[2] - bbox[0]) <= max_box_width:
            font_title = candidate_font
            break
        title_size -= 2

    if font_title is None:
        try:
            font_title = (
                ImageFont.truetype(str(font_bold_path), title_size)
                if font_bold_path
                else ImageFont.load_default()
            )
        except Exception:
            font_title = ImageFont.load_default()

    img = canvas.convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    def draw_right_aligned(text: str, font: ImageFont.ImageFont, y_pos: float, text_shadow: bool = with_shadow) -> None:
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        x_pos = int(round(right_x - text_w))
        y_int = int(round(y_pos))
        if text_shadow:
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 1), (1, 2), (0, 2), (-1, 0), (1, 0)]:
                draw.text((x_pos + dx, y_int + dy), text, font=font, fill=shadow_color)
        draw.text((x_pos, y_int), text, font=font, fill=(*text_color, 255))

    current_y = start_y

    # 1. Headline / Item Name
    draw_right_aligned(clean_title, font_title, current_y, text_shadow=with_shadow)
    current_y += int(round(56 * scale_y))

    # 2. Follow @HomeCartel for more home inspiration. (Not bold, no shadow text)
    draw_right_aligned("Follow @HomeCartel for", font_body_reg, current_y, text_shadow=False)
    current_y += int(round(34 * scale_y))
    draw_right_aligned("more home inspiration.", font_body_reg, current_y, text_shadow=False)
    current_y += int(round(48 * scale_y))

    # 3. Contact details
    draw_right_aligned("0977 825 5588 (or send us a DM)", font_body_reg, current_y, text_shadow=with_shadow)
    current_y += int(round(34 * scale_y))
    draw_right_aligned("(02) 8248 8071 | Dial 1", font_body_reg, current_y, text_shadow=with_shadow)
    current_y += int(round(34 * scale_y))
    draw_right_aligned("sales@homecartel.com", font_body_reg, current_y, text_shadow=with_shadow)

    combined = Image.alpha_composite(img, txt_layer)
    return combined.convert("RGB")


def stamp_cta_story_watermark_and_logo(
    base_path: Path | str | Image.Image | None = None,
    logo_path: Path | str | Image.Image | None = None,
    item_name: str = "Singkwenta Dose",
    destination: Path | str | None = None,
    *,
    base_image_path: Path | str | Image.Image | None = None,
    output_path: Path | str | None = None,
    logo_box: LogoBox = HOMECARTEL_STORY_LOGO_BOX,
    text_box: StoryTextBox = CTA_STORY_TEXT_BOX,
    headline_font_size: int = 48,
    body_font_size: int = 28,
    with_shadow: bool = False,
) -> Path | Image.Image:
    """Stamp HomeCartel logo and right-aligned CTA text watermark onto a 9:16 image."""
    actual_base = base_path if base_path is not None else base_image_path
    actual_dest = destination if destination is not None else output_path
    if actual_base is None:
        raise ValueError("Missing base image path for CTA story watermark and logo stamping.")

    if isinstance(actual_base, (str, Path)):
        with Image.open(actual_base) as source_base:
            canvas = source_base.convert("RGB")
    else:
        canvas = actual_base.convert("RGB")

    # 1. Stamp Logo at top-right if provided
    if logo_path is not None:
        stamped = stamp_logo(canvas, logo_path, destination=None, box=logo_box)
        if isinstance(stamped, Image.Image):
            canvas = stamped

    # 2. Overlay right-aligned CTA text layout at bottom-right
    canvas = overlay_cta_story_layout(
        canvas,
        item_name=item_name,
        text_box=text_box,
        headline_font_size=headline_font_size,
        body_font_size=body_font_size,
        with_shadow=with_shadow,
    )

    if destination is not None:
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(
            dest_path,
            format="JPEG",
            quality=95,
            optimize=True,
        )
        return dest_path

    return canvas


# ==============================================================================
# Style This Story Layout Boxes & Functions (9:16 Canvas, 1080x1920)
# ==============================================================================

# Slide 1: 'How would you style this?' + 'ft. [Item Name]'
# Width 904.7, Height 152.3, X 87.7, Y 850.7 (Horizontally centered at X = 540.05)
STYLE_THIS_HEADLINE_BOX = StoryTextBox(
    x=87.7,
    y=850.7,
    width=904.7,
    height=152.3,
    canvas_width=1080,
    canvas_height=1920,
)

# Slide 2: Heart emoji asset
# Width 77.8, Height 69.3, anchored in bottom section alongside Double Tap text
STYLE_THIS_HEART_BOX = LogoBox(
    x=209.1,
    y=1396.8,
    width=77.8,
    height=69.3,
    canvas_width=1080,
    canvas_height=1920,
)

# Slide 2: 'Double tap if you choose:' (Poppins Bold, centered in bottom section)
# Width 904.7, Height 70.3, Y 1396.3 (24px gap above pill at Y=1490.6)
STYLE_THIS_DOUBLE_TAP_BOX = StoryTextBox(
    x=87.7,
    y=1396.3,
    width=904.7,
    height=70.3,
    canvas_width=1080,
    canvas_height=1920,
)

# Slide 2: Pill background + Claude Generated Text (Exact Canva specs: 606.4 x 70.3 at X=236.8, Y=1490.6)
STYLE_THIS_PILL_BOX = StoryTextBox(
    x=236.8,
    y=1490.6,
    width=606.4,
    height=70.3,
    canvas_width=1080,
    canvas_height=1920,
)

DEFAULT_STYLE_THIS_PILL_COLOR = "#adb481"


def _resolve_asset_file(asset_name: str) -> Path | None:
    """Find asset image by searching known candidate directories."""
    candidate_paths = [
        Path("assets") / asset_name,
        Path("content_automation/assets") / asset_name,
        Path("JSON Prompts/Style This") / asset_name,
        Path("JSON Prompts") / asset_name,
        Path(__file__).parent.parent / "assets" / asset_name,
        Path(__file__).parent / "assets" / asset_name,
        Path(asset_name),
    ]
    for c in candidate_paths:
        if c.is_file():
            return c
    return None


def create_style_this_slide_1(
    base_image: Path | str | Image.Image,
    logo_path: Path | str | Image.Image | None = None,
    item_name: str = "Modern Floor Lamp",
    destination: Path | str | None = None,
    *,
    logo_box: LogoBox = HOMECARTEL_STORY_LOGO_BOX,
    headline_box: StoryTextBox = STYLE_THIS_HEADLINE_BOX,
    font_path: Path | str | None = None,
) -> Path | Image.Image:
    """Create Slide 1 ('how_would_you_style_this.jpg') for Style This Story.

    1. Stamped HomeCartel Logo at top-right (X=781.7, Y=108.0, W=190.3, H=63.5)
    2. Centered two-line headline in Poppins-Light (non-bold, no shadow) at Canva coordinates (X=87.7, Y=850.7, W=904.7, H=152.3):
       - Line 1: 'How would you style this?'
       - Line 2: 'ft. [Item Name]'
    """
    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    try:
        canvas = source_base.convert("RGB")
        if canvas.size != (1080, 1920):
            canvas = ImageOps.fit(canvas, (1080, 1920), method=Image.LANCZOS, centering=(0.5, 0.5))

        # 1. Stamp Logo top-right (always resolve default logo if None)
        if logo_path is None:
            logo_path = _resolve_asset_file("homecartel_logo.png") or _resolve_asset_file("logo.png")

        if logo_path is not None:
            stamped = stamp_logo(canvas, logo_path, destination=None, box=logo_box)
            if isinstance(stamped, Image.Image):
                canvas = stamped

        # 2. Render Headline typography (Poppins Light, non-bold, no shadow)
        if font_path is None:
            font_path = (
                _resolve_font_path("Poppins-Light.ttf")
                or _resolve_font_path("Poppins-Regular.ttf")
                or _resolve_font_path("Poppins-Bold.ttf")
            )

        scale_x = canvas.width / headline_box.canvas_width
        scale_y = canvas.height / headline_box.canvas_height
        box_x = headline_box.x * scale_x
        box_y = headline_box.y * scale_y
        box_w = headline_box.width * scale_x
        center_x = box_x + box_w / 2.0

        # Clean item name formatting (strip brackets and extra bars)
        clean_name = str(item_name or "Modern Floor Lamp").strip().strip("[]")
        if "|" in clean_name:
            parts = [p.strip() for p in clean_name.split("|") if p.strip()]
            clean_name = parts[0] if parts else clean_name

        line1_text = "How would you style this?"
        line2_text = f"ft. {clean_name}"

        base_l1_size = int(round(44 * scale_y))  # Font size 44 Poppins-Light
        try:
            font_l1 = ImageFont.truetype(str(font_path), base_l1_size) if font_path else ImageFont.load_default()
        except Exception:
            font_l1 = ImageFont.load_default()

        bbox_l1 = font_l1.getbbox(line1_text)
        w_l1 = bbox_l1[2] - bbox_l1[0]

        # Auto-scale line 2 font size starting from 44px
        l2_size = int(round(44 * scale_y))
        font_l2 = None
        min_l2_size = int(round(24 * scale_y))
        while l2_size >= min_l2_size:
            try:
                candidate = ImageFont.truetype(str(font_path), l2_size) if font_path else ImageFont.load_default()
            except Exception:
                candidate = ImageFont.load_default()
                font_l2 = candidate
                break
            bbox = candidate.getbbox(line2_text)
            if (bbox[2] - bbox[0]) <= box_w:
                font_l2 = candidate
                break
            l2_size -= 2

        if font_l2 is None:
            try:
                font_l2 = ImageFont.truetype(str(font_path), l2_size) if font_path else ImageFont.load_default()
            except Exception:
                font_l2 = ImageFont.load_default()

        bbox_l2 = font_l2.getbbox(line2_text)
        w_l2 = bbox_l2[2] - bbox_l2[0]

        y_l1 = int(round(box_y + 14 * scale_y))
        y_l2 = int(round(box_y + 80 * scale_y))
        x_l1 = int(round(center_x - w_l1 / 2.0 - bbox_l1[0]))
        x_l2 = int(round(center_x - w_l2 / 2.0 - bbox_l2[0]))

        img = canvas.convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # Clean typography with no shadow/outline (Poppins Light)
        text_color = (255, 255, 255, 255)
        draw.text((x_l1, y_l1), line1_text, font=font_l1, fill=text_color)
        draw.text((x_l2, y_l2), line2_text, font=font_l2, fill=text_color)

        combined = Image.alpha_composite(img, txt_layer)
        result = combined.convert("RGB")

        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            result.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path
        return result
    finally:
        if close_base:
            source_base.close()


def create_style_this_double_tap_slide(
    base_image: Path | str | Image.Image,
    logo_path: Path | str | Image.Image | None = None,
    heart_asset_path: Path | str | Image.Image | None = None,
    claude_text: str = "Warm Olive",
    destination: Path | str | None = None,
    *,
    logo_box: LogoBox = HOMECARTEL_STORY_LOGO_BOX,
    heart_box: LogoBox = STYLE_THIS_HEART_BOX,
    double_tap_box: StoryTextBox = STYLE_THIS_DOUBLE_TAP_BOX,
    pill_box: StoryTextBox = STYLE_THIS_PILL_BOX,
    pill_color_hex: str = DEFAULT_STYLE_THIS_PILL_COLOR,
    font_path: Path | str | None = None,
) -> Path | Image.Image:
    """Create Slide 2-4 ('double_tap_blended0X.jpg') for Style This Story.

    1. Stamped HomeCartel Logo at top-right (X=781.7, Y=108.0, W=190.3, H=63.5)
    2. Heart Emoji & Headline 'Double tap if you choose:' in Poppins-Bold:
       Horizontally centered together as a single block in the bottom section (Y ≈ 1394).
    3. Rounded Pill background dynamically below headline (Y ≈ 1488) with color from Claude
       and centered Poppins-Bold vibe text in clean solid white.
    """
    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    try:
        canvas = source_base.convert("RGB")
        if canvas.size != (1080, 1920):
            canvas = ImageOps.fit(canvas, (1080, 1920), method=Image.LANCZOS, centering=(0.5, 0.5))

        # 1. Stamp Logo top-right (always resolve default logo if None)
        if logo_path is None:
            logo_path = _resolve_asset_file("homecartel_logo.png") or _resolve_asset_file("logo.png")

        if logo_path is not None:
            stamped = stamp_logo(canvas, logo_path, destination=None, box=logo_box)
            if isinstance(stamped, Image.Image):
                canvas = stamped

        scale_x = canvas.width / double_tap_box.canvas_width
        scale_y = canvas.height / double_tap_box.canvas_height

        img = canvas.convert("RGBA")

        # 2. Typography font setup (Poppins-Bold prioritized)
        if font_path is None:
            font_path = (
                _resolve_font_path("Poppins-Bold.ttf")
                or _resolve_font_path("Poppins-Regular.ttf")
                or _resolve_font_path("Poppins-Light.ttf")
            )

        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        headline_text = "Double tap if you choose:"
        hl_font_size = int(round(44 * scale_y))  # Font size 44 Poppins-Bold
        try:
            font_hl = ImageFont.truetype(str(font_path), hl_font_size) if font_path else ImageFont.load_default()
        except Exception:
            font_hl = ImageFont.load_default()

        bbox_hl = font_hl.getbbox(headline_text)
        tw_hl = bbox_hl[2] - bbox_hl[0]
        hl_visible_h = bbox_hl[3] - bbox_hl[1]

        # 3. Heart Emoji preparation
        if heart_asset_path is None:
            heart_asset_path = _resolve_asset_file("Heaart Emoji.jpg") or _resolve_asset_file("Heart Emoji.jpg")

        heart_resized = None
        target_w = 0
        target_h = 0
        close_heart = False
        if heart_asset_path:
            try:
                if isinstance(heart_asset_path, (str, Path)):
                    heart_source = Image.open(heart_asset_path)
                    close_heart = True
                else:
                    heart_source = heart_asset_path
                    close_heart = False

                heart_prep = prepare_logo_image(heart_source)
                bounds = visible_bounds(heart_prep)
                if bounds:
                    heart_prep = heart_prep.crop(bounds)

                target_w = int(round(heart_box.width * scale_x))
                target_h = int(round(heart_box.height * scale_y))
                heart_resized = heart_prep.resize((target_w, target_h), Image.LANCZOS)
            except Exception as err:
                print(f"[WARN] Failed to load heart emoji: {err}")
                heart_resized = None
                target_w = 0
                target_h = 0
            finally:
                if close_heart:
                    heart_source.close()

        gap_x = int(round(20.0 * scale_x)) if heart_resized is not None else 0
        total_hl_w = target_w + gap_x + tw_hl
        start_hl_x = (canvas.width - total_hl_w) / 2.0

        # Baseline vertical position in bottom section
        row_y = double_tap_box.y * scale_y
        row_h = double_tap_box.height * scale_y
        row_center_y = row_y + row_h / 2.0

        # Paste heart if available
        if heart_resized is not None:
            hx = int(round(start_hl_x))
            hy = int(round(row_center_y - target_h / 2.0))
            img.paste(heart_resized, (hx, hy), heart_resized)

        # Draw headline text (Poppins-Bold, solid white, no shadow)
        hl_x = int(round(start_hl_x + target_w + gap_x - bbox_hl[0]))
        hl_y = int(round(row_center_y - hl_visible_h / 2.0 - bbox_hl[1]))
        text_color = (255, 255, 255, 255)
        draw.text((hl_x, hl_y), headline_text, font=font_hl, fill=text_color)

        # 4. Exact Pill background (Canva spec: 606.4 x 70.3 at X=236.8, Y=1490.6, 100% opacity)
        clean_text = str(claude_text or "Warm Olive").strip().strip("[]\"'")
        pill_font_size = int(round(44 * scale_y))  # Font size 44 Poppins-Bold
        try:
            font_pill = ImageFont.truetype(str(font_path), pill_font_size) if font_path else ImageFont.load_default()
        except Exception:
            font_pill = ImageFont.load_default()

        bbox_p = font_pill.getbbox(clean_text)
        tw = bbox_p[2] - bbox_p[0]
        th = bbox_p[3] - bbox_p[1]

        # Exact Canva dimensions from pill_box
        pill_w = pill_box.width * scale_x
        pill_h = pill_box.height * scale_y
        pill_x = pill_box.x * scale_x
        pill_y = pill_box.y * scale_y
        pill_radius = min(int(round(pill_h / 2.0)), 40)

        hex_clean = pill_color_hex.lstrip("#")
        pill_rgb = tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4)) if len(hex_clean) == 6 else (173, 180, 129)

        pill_rect = [
            int(round(pill_x)),
            int(round(pill_y)),
            int(round(pill_x + pill_w)),
            int(round(pill_y + pill_h)),
        ]

        draw.rounded_rectangle(
            pill_rect,
            radius=pill_radius,
            fill=(*pill_rgb, 255),
        )

        # 5. Text inside pill (Font size 44 Poppins-Bold, centered, solid white, no shadow)
        pill_center_x = pill_x + pill_w / 2.0
        pill_center_y = pill_y + pill_h / 2.0
        text_px = int(round(pill_center_x - tw / 2.0 - bbox_p[0]))
        text_py = int(round(pill_center_y - th / 2.0 - bbox_p[1]))

        draw.text((text_px, text_py), clean_text, font=font_pill, fill=(255, 255, 255, 255))

        combined = Image.alpha_composite(img, txt_layer)
        result = combined.convert("RGB")

        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            result.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path
        return result
    finally:
        if close_base:
            source_base.close()


# ==============================================================================
# Tips & Edu Feed Thumbnail Typography & Layout (4:5 Canvas, 1080x1350)
# ==============================================================================

@dataclass(frozen=True)
class FeedTextBox:
    """Bounding box for 4:5 feed text typography on a design canvas (1080x1350)."""

    x: float
    y: float
    width: float
    height: float
    canvas_width: int = 1080
    canvas_height: int = 1350


@dataclass(frozen=True)
class FeedLineDivider:
    """Horizontal line divider on a 4:5 feed design canvas (1080x1350)."""

    start_x: float = 108.0
    end_x: float = 289.8
    start_y: float = 376.8
    end_y: float = 376.8
    thickness: float = 2.5
    canvas_width: int = 1080
    canvas_height: int = 1350


# Title Box: Width 597.4px, Height 66.8px, X 105px, Y 237.4px, Rotate 0°
TIPS_EDU_THUMBNAIL_TITLE_BOX = FeedTextBox(
    x=105.0,
    y=237.4,
    width=597.4,
    height=66.8,
    canvas_width=1080,
    canvas_height=1350,
)

# Subtitle Box: Width 522.5px, Height 50.5px, X 107px, Y 304.2px, Rotate 0°
TIPS_EDU_THUMBNAIL_SUBTITLE_BOX = FeedTextBox(
    x=107.0,
    y=304.2,
    width=522.5,
    height=50.5,
    canvas_width=1080,
    canvas_height=1350,
)

TIPS_EDU_THUMBNAIL_DIVIDER = FeedLineDivider(
    start_x=108.0,
    end_x=289.8,
    start_y=376.8,
    end_y=376.8,
    thickness=2.5,
    canvas_width=1080,
    canvas_height=1350,
)


def overlay_tips_edu_thumbnail_text(
    canvas: Image.Image,
    title_text: str,
    subtitle_text: str = "In 3 ways",
    *,
    font_bold_path: Path | str | None = None,
    font_light_path: Path | str | None = None,
    title_box: FeedTextBox = TIPS_EDU_THUMBNAIL_TITLE_BOX,
    subtitle_box: FeedTextBox = TIPS_EDU_THUMBNAIL_SUBTITLE_BOX,
    divider: FeedLineDivider = TIPS_EDU_THUMBNAIL_DIVIDER,
    title_font_size: int = 47,
    subtitle_font_size: int = 32,
    text_color: tuple[int, int, int] = (255, 255, 255),
    with_divider: bool = True,
) -> Image.Image:
    """Overlay bold Title (47px) and light Subtitle (32px) onto a 4:5 (1080x1350) thumbnail image.

    Clean typography with no subshadow or outline.
    """
    if not title_text or not str(title_text).strip():
        return canvas

    if font_bold_path is None:
        font_bold_path = _resolve_font_path("Poppins-Bold.ttf")
    if font_light_path is None:
        font_light_path = (
            _resolve_font_path("Poppins-Light.ttf")
            or _resolve_font_path("Poppins-Regular.ttf")
            or font_bold_path
        )

    img = canvas.convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    scale_x = canvas.width / title_box.canvas_width
    scale_y = canvas.height / title_box.canvas_height

    # 1. Title Typography (Poppins-Bold, font size 47, Plain White, no shadow)
    scaled_title_size = max(24, int(round(title_font_size * scale_y)))
    try:
        font_title = (
            ImageFont.truetype(str(font_bold_path), scaled_title_size)
            if font_bold_path
            else ImageFont.load_default()
        )
    except Exception:
        font_title = ImageFont.load_default()

    t_box_x = int(round(title_box.x * scale_x))
    t_box_y = int(round(title_box.y * scale_y))
    t_box_w = int(round(title_box.width * scale_x))

    clean_title = str(title_text).strip().strip('"\'`')
    words = clean_title.split()
    title_lines: list[str] = []
    current_line: list[str] = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font_title)
        line_w = bbox[2] - bbox[0]
        if line_w <= t_box_w or not current_line:
            current_line.append(word)
        else:
            title_lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        title_lines.append(" ".join(current_line))

    t_line_spacing = int(scaled_title_size * 0.18)
    curr_t_y = t_box_y

    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_h = bbox[3] - bbox[1]
        draw.text((t_box_x, curr_t_y), line, font=font_title, fill=(*text_color, 255))
        curr_t_y += line_h + t_line_spacing

    # 2. Subtitle Typography (Poppins-Light, font size 32, Plain White, no shadow)
    clean_sub = str(subtitle_text or "").strip().strip('"\'`')
    if clean_sub:
        scaled_sub_size = max(18, int(round(subtitle_font_size * scale_y)))
        try:
            font_sub = (
                ImageFont.truetype(str(font_light_path), scaled_sub_size)
                if font_light_path
                else font_title
            )
        except Exception:
            font_sub = font_title

        s_box_x = int(round(subtitle_box.x * scale_x))
        nominal_s_y = int(round(subtitle_box.y * scale_y))
        s_box_y = max(nominal_s_y, curr_t_y + int(scaled_title_size * 0.10))

        draw.text((s_box_x, s_box_y), clean_sub, font=font_sub, fill=(*text_color, 255))

        sub_bbox = draw.textbbox((0, 0), clean_sub, font=font_sub)
        sub_h = sub_bbox[3] - sub_bbox[1]
        curr_s_bottom = s_box_y + sub_h
    else:
        curr_s_bottom = curr_t_y

    # 3. Horizontal White Line Divider (Start X=108, End X=289.8, Y=376.8)
    if with_divider:
        line_start_x = int(round(divider.start_x * scale_x))
        line_end_x = int(round(divider.end_x * scale_x))
        nominal_line_y = int(round(divider.start_y * scale_y))
        line_y = max(nominal_line_y, curr_s_bottom + int(round(18 * scale_y)))
        line_thickness = max(2, int(round(divider.thickness * scale_y)))

        draw.line(
            [(line_start_x, line_y), (line_end_x, line_y)],
            fill=(*text_color, 255),
            width=line_thickness,
        )

    combined = Image.alpha_composite(img, txt_layer)
    return combined.convert("RGB")


def create_tips_edu_thumbnail_with_text(
    base_image: Path | str | Image.Image,
    title_text: str,
    subtitle_text: str = "In 3 ways",
    logo_path: Path | str | Image.Image | None = None,
    destination: Path | str | None = None,
    *,
    logo_box: LogoBox = HOMECARTEL_LOGO_BOX,
    title_box: FeedTextBox = TIPS_EDU_THUMBNAIL_TITLE_BOX,
    subtitle_box: FeedTextBox = TIPS_EDU_THUMBNAIL_SUBTITLE_BOX,
    divider: FeedLineDivider = TIPS_EDU_THUMBNAIL_DIVIDER,
    title_font_size: int = 47,
    subtitle_font_size: int = 32,
    with_divider: bool = True,
) -> Path | Image.Image:
    """Compose 4:5 Tips & Edu thumbnail with bold Title, light Subtitle, divider line, and bottom-left HomeCartel logo."""
    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    try:
        canvas = source_base.convert("RGB")
        if canvas.size != (1080, 1350):
            canvas = ImageOps.fit(canvas, (1080, 1350), method=Image.LANCZOS, centering=(0.5, 0.5))

        # 1. Overlay Title + Subtitle + Divider
        canvas = overlay_tips_edu_thumbnail_text(
            canvas,
            title_text=title_text,
            subtitle_text=subtitle_text,
            title_box=title_box,
            subtitle_box=subtitle_box,
            divider=divider,
            title_font_size=title_font_size,
            subtitle_font_size=subtitle_font_size,
            with_divider=with_divider,
        )

        # 2. Stamp HomeCartel Logo at bottom-left if provided or resolved
        if logo_path is None:
            logo_path = _resolve_asset_file("homecartel_logo.png") or _resolve_asset_file("logo.png")

        if logo_path is not None:
            stamped = stamp_logo(canvas, logo_path, destination=None, box=logo_box)
            if isinstance(stamped, Image.Image):
                canvas = stamped

        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path

        return canvas
    finally:
        if close_base:
            source_base.close()


# ==============================================================================
# Tips & Edu Feed Layout Typography (4:5 Canvas, 1080x1350)
# ==============================================================================

@dataclass(frozen=True)
class TipsEduFeedBox:
    """Bounding box for 4:5 tips and edu feed typography on a design canvas (1080x1350)."""

    x: float
    y: float
    width: float
    height: float
    canvas_width: int = 1080
    canvas_height: int = 1350


# Numeral (1, 2, 3): Font size 196 Poppins-Regular
# Canva position: Width 82px, Height 312.7px, X 147.8px, Y 942.2px, Rotate 0°
TIPS_EDU_FEED_NUMERAL_BOX = TipsEduFeedBox(
    x=147.8,
    y=942.2,
    width=82.0,
    height=312.7,
    canvas_width=1080,
    canvas_height=1350,
)

# Tip Text Box: Font size 32 Poppins-Regular
# Canva position: Width 755.3px, Height 176.5px, X 229.8px, Y 1007.3px, Rotate 0°
TIPS_EDU_FEED_TEXT_BOX = TipsEduFeedBox(
    x=229.8,
    y=1007.3,
    width=755.3,
    height=176.5,
    canvas_width=1080,
    canvas_height=1350,
)


def overlay_tips_edu_feed_layout(
    canvas: Image.Image,
    numeral: str | int = "1",
    tip_text: str = "",
    *,
    font_path: Path | str | None = None,
    numeral_font_path: Path | str | None = None,
    text_font_path: Path | str | None = None,
    numeral_box: TipsEduFeedBox = TIPS_EDU_FEED_NUMERAL_BOX,
    text_box: TipsEduFeedBox = TIPS_EDU_FEED_TEXT_BOX,
    numeral_font_size: int = 196,
    text_font_size: int = 32,
    line_spacing: float = 1.0,
    letter_spacing: int = 0,
    text_color: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Overlay clean white Numeral (196px Poppins-Regular) and bold Tip Text (32px Poppins-Bold) onto a 4:5 (1080x1350) feed image.

    Strictly adheres to Canva settings: Line spacing: 1, Letter spacing: 0, Top anchor.
    """
    if numeral_font_path is None:
        numeral_font_path = font_path or _resolve_font_path("Poppins-Regular.ttf") or _resolve_font_path("Poppins-Bold.ttf")

    if text_font_path is None:
        text_font_path = _resolve_font_path("Poppins-Bold.ttf") or font_path or numeral_font_path

    img = canvas.convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    scale_x = canvas.width / text_box.canvas_width
    scale_y = canvas.height / text_box.canvas_height

    # 1. Render Numeral (Poppins-Regular, font size 196, Plain White, no shadow)
    scaled_num_size = max(48, int(round(numeral_font_size * scale_y)))
    try:
        font_num = ImageFont.truetype(str(numeral_font_path), scaled_num_size) if numeral_font_path else ImageFont.load_default()
    except Exception:
        font_num = ImageFont.load_default()

    num_x = int(round(numeral_box.x * scale_x))
    num_y = int(round(numeral_box.y * scale_y))
    clean_num = str(numeral).strip()
    draw.text((num_x, num_y), clean_num, font=font_num, fill=(*text_color, 255))

    # 2. Render Tip Text (Poppins-Bold, font size 32, Line spacing 1.0, Letter spacing 0, Top Anchor)
    clean_tip = str(tip_text or "").strip().strip('"\'`')
    if clean_tip:
        # Calculate actual glyph bounds of the numeral to dynamically prevent text overlap.
        # Wider numerals (2 and 3) extend ~112-116px compared to numeral 1 (~63px).
        num_bbox = font_num.getbbox(clean_num)
        num_glyph_right = num_x + num_bbox[2]
        min_gap = int(round(19 * scale_x))
        t_box_x = max(int(round(text_box.x * scale_x)), num_glyph_right + min_gap)
        t_box_y = int(round(text_box.y * scale_y))

        # Anchor right edge to Canva boundary (229.8 + 755.3 = 985.1px)
        right_boundary = int(round((text_box.x + text_box.width) * scale_x))
        max_w = max(200.0, float(right_boundary - t_box_x))
        max_h = text_box.height * scale_y

        # Auto-fit text if necessary so it stays within max_h (with Line Spacing = 1.0)
        curr_text_size = max(20, int(round(text_font_size * scale_y)))
        font_text = None
        wrapped_lines: list[str] = []
        line_height = 0

        while curr_text_size >= max(18, int(round(22 * scale_y))):
            try:
                candidate_font = ImageFont.truetype(str(text_font_path), curr_text_size) if text_font_path else ImageFont.load_default()
            except Exception:
                candidate_font = ImageFont.load_default()

            words = clean_tip.split()
            candidate_lines: list[str] = []
            current_line: list[str] = []

            for word in words:
                test_line = " ".join(current_line + [word])
                line_w = candidate_font.getlength(test_line)
                if line_w <= max_w or not current_line:
                    current_line.append(word)
                else:
                    candidate_lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                candidate_lines.append(" ".join(current_line))

            # Canva Line spacing = 1.0 (exact font-size multiple)
            cand_line_height = int(round(curr_text_size * line_spacing))
            total_h = len(candidate_lines) * cand_line_height
            if total_h <= max_h + 10 or curr_text_size <= int(round(24 * scale_y)):
                font_text = candidate_font
                wrapped_lines = candidate_lines
                line_height = cand_line_height
                break
            curr_text_size -= 2

        if font_text is None:
            try:
                font_text = ImageFont.truetype(str(text_font_path), curr_text_size) if text_font_path else ImageFont.load_default()
            except Exception:
                font_text = ImageFont.load_default()
            line_height = int(round(curr_text_size * line_spacing))
            wrapped_lines = [clean_tip]

        # Top anchor: lines flow downwards starting from t_box_y (Canva Y: 1007.3px)
        curr_y = t_box_y
        for line in wrapped_lines:
            draw.text((t_box_x, curr_y), line, font=font_text, fill=(*text_color, 255))
            curr_y += line_height

    combined = Image.alpha_composite(img, txt_layer)
    return combined.convert("RGB")


def create_tips_edu_feed_image(
    base_image: Path | str | Image.Image,
    numeral: str | int = "1",
    tip_text: str = "",
    destination: Path | str | None = None,
    *,
    numeral_box: TipsEduFeedBox = TIPS_EDU_FEED_NUMERAL_BOX,
    text_box: TipsEduFeedBox = TIPS_EDU_FEED_TEXT_BOX,
    numeral_font_size: int = 196,
    text_font_size: int = 32,
    line_spacing: float = 1.0,
    letter_spacing: int = 0,
    font_path: Path | str | None = None,
    numeral_font_path: Path | str | None = None,
    text_font_path: Path | str | None = None,
) -> Path | Image.Image:
    """Compose 4:5 Tips & Edu Feed post (1080x1350) adhering to Canva settings (Line Spacing 1, Letter Spacing 0, Top Anchor)."""
    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    try:
        canvas = source_base.convert("RGB")
        if canvas.size != (1080, 1350):
            canvas = ImageOps.fit(canvas, (1080, 1350), method=Image.LANCZOS, centering=(0.5, 0.5))

        result = overlay_tips_edu_feed_layout(
            canvas,
            numeral=numeral,
            tip_text=tip_text,
            font_path=font_path,
            numeral_font_path=numeral_font_path,
            text_font_path=text_font_path,
            numeral_box=numeral_box,
            text_box=text_box,
            numeral_font_size=numeral_font_size,
            text_font_size=text_font_size,
            line_spacing=line_spacing,
            letter_spacing=letter_spacing,
        )

        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            result.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path

        return result
    finally:
        if close_base:
            source_base.close()


# ---------------------------------------------------------------------------
# Tips & Edu Story (9:16, 1080x1920): local layout, no image API.
# Positions are measured from JSON Prompts/Tips and Edu Story/stories (33).jpg.
# Canva sizes are points (1 pt = 4/3 px): title 40 pt ExtraBold, tip 28 pt Regular.
# ---------------------------------------------------------------------------
TIPS_EDU_STORY_SIZE = (1080, 1920)
TIPS_EDU_STORY_TITLE = "Style Tip of the Day"
TIPS_EDU_STORY_TITLE_PT = 40.0
TIPS_EDU_STORY_TIP_PT = 28.0
TIPS_EDU_STORY_TITLE_ORIGIN = (119, 1356)  # text origin; ink starts at x=121, y=1369
TIPS_EDU_STORY_UNDERLINE = (113, 1437, 633, 1439)  # x0, y0, x1, y1 (x1/y1 exclusive): 520 x 2 px
TIPS_EDU_STORY_TIP_ORIGIN = (113, 1541)  # text origin; ink starts at x=118, y=1546
TIPS_EDU_STORY_TIP_MAX_WIDTH = 854  # symmetric 113 px side margins
TIPS_EDU_STORY_TIP_MAX_LINES = 4
TIPS_EDU_STORY_TIP_MIN_PX = 28.0
# Soft dark gradient so white text stays legible on light photos (0 -> ~65% black).
TIPS_EDU_STORY_GRADIENT_START_Y = 1150
TIPS_EDU_STORY_GRADIENT_MAX_ALPHA = 166


def _wrap_text_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    for word in text.split():
        trial = " ".join(current + [word])
        if current and font.getlength(trial) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def overlay_tips_edu_story_layout(
    canvas: Image.Image,
    tip_text: str,
    *,
    title_font_path: Path | str | None = None,
    tip_font_path: Path | str | None = None,
    text_color: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Draw the "Style Tip of the Day" story layout on top of a blended room photo.

    The photo is cover-fitted to 1080x1920 and never repainted; only a bottom gradient, the
    title, its underline and the tip sentence are added. The logo is stamped separately with
    ``stamp_logo`` so there is exactly one.
    """
    base = ImageOps.fit(
        canvas.convert("RGB"), TIPS_EDU_STORY_SIZE, method=Image.LANCZOS, centering=(0.5, 0.5)
    ).convert("RGBA")
    width, height = base.size

    gradient_h = height - TIPS_EDU_STORY_GRADIENT_START_Y
    ramp = Image.linear_gradient("L").resize((width, gradient_h), Image.BILINEAR)
    ramp = ramp.point(lambda v: int(v * TIPS_EDU_STORY_GRADIENT_MAX_ALPHA / 255))
    shade = Image.new("RGBA", (width, gradient_h), (0, 0, 0, 255))
    shade.putalpha(ramp)
    base.alpha_composite(shade, (0, TIPS_EDU_STORY_GRADIENT_START_Y))

    title_path = (
        title_font_path
        or _resolve_font_path("Poppins-ExtraBold.ttf")
        or _resolve_font_path("Poppins-Bold.ttf")
    )
    tip_path = tip_font_path or _resolve_font_path("Poppins-Regular.ttf") or title_path

    def load(path: Path | str | None, size: float) -> ImageFont.ImageFont:
        try:
            return ImageFont.truetype(str(path), size) if path else ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()

    draw = ImageDraw.Draw(base)
    fill = (*text_color, 255)

    title_font = load(title_path, TIPS_EDU_STORY_TITLE_PT * CANVA_PT_TO_PX)
    draw.text(TIPS_EDU_STORY_TITLE_ORIGIN, TIPS_EDU_STORY_TITLE, font=title_font, fill=fill)
    draw.rectangle(
        [
            TIPS_EDU_STORY_UNDERLINE[0],
            TIPS_EDU_STORY_UNDERLINE[1],
            TIPS_EDU_STORY_UNDERLINE[2] - 1,
            TIPS_EDU_STORY_UNDERLINE[3] - 1,
        ],
        fill=fill,
    )

    clean_tip = " ".join(str(tip_text or "").split())
    if clean_tip:
        size = TIPS_EDU_STORY_TIP_PT * CANVA_PT_TO_PX
        tip_font = load(tip_path, size)
        lines = _wrap_text_to_width(clean_tip, tip_font, TIPS_EDU_STORY_TIP_MAX_WIDTH)
        # Shrink only when the sentence would need more than the allowed lines.
        while len(lines) > TIPS_EDU_STORY_TIP_MAX_LINES and size > TIPS_EDU_STORY_TIP_MIN_PX:
            size -= 1.0
            tip_font = load(tip_path, size)
            lines = _wrap_text_to_width(clean_tip, tip_font, TIPS_EDU_STORY_TIP_MAX_WIDTH)
        try:
            ascent, descent = tip_font.getmetrics()
            line_height = ascent + descent
        except Exception:
            line_height = int(round(size * 1.4))
        x, y = TIPS_EDU_STORY_TIP_ORIGIN
        for line in lines:
            draw.text((x, y), line, font=tip_font, fill=fill)
            y += line_height

    return base.convert("RGB")


def create_tips_edu_story_image(
    base_image: Path | str | Image.Image,
    tip_text: str,
    destination: Path | str | None = None,
    *,
    logo_path: Path | str | None = None,
) -> Path | Image.Image:
    """Compose the full Tips & Edu Story (1080x1920): photo + local text layout + one logo."""
    if isinstance(base_image, (str, Path)):
        source = Image.open(base_image)
        close_source = True
    else:
        source = base_image
        close_source = False
    try:
        result = overlay_tips_edu_story_layout(source, tip_text)
    finally:
        if close_source:
            source.close()

    if logo_path is not None and Path(logo_path).is_file():
        result = stamp_logo(result, Path(logo_path), None, HOMECARTEL_STORY_LOGO_BOX)

    if destination is not None:
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        result.save(dest, "JPEG", quality=95, optimize=True)
        return dest
    return result


@dataclass(frozen=True)
class MoodboardTextureBox:
    """Canva coordinate box for Moodboard Reel 3-panel textures (1080x1920 canvas)."""

    x: float
    y: float
    width: float
    height: float


# Exact Canva coordinates for the 3 horizontal panels in Moodboard Reel (1080 x 1920 px):
MOODBOARD_TEXTURE_TOP_BOX = MoodboardTextureBox(x=355.5, y=268.8, width=368.9, height=76.2)
MOODBOARD_TEXTURE_MID_BOX = MoodboardTextureBox(x=231.6, y=921.9, width=632.9, height=76.2)
MOODBOARD_TEXTURE_BOT_BOX = MoodboardTextureBox(x=346.9, y=1559.0, width=386.1, height=76.2)


def overlay_moodboard_textures(
    base_image: Path | str | Image.Image,
    texture_top: str = "",
    texture_middle: str = "",
    texture_bottom: str = "",
    *,
    destination: Path | str | None = None,
    font_path: Path | str | None = None,
    top_box: MoodboardTextureBox = MOODBOARD_TEXTURE_TOP_BOX,
    mid_box: MoodboardTextureBox = MOODBOARD_TEXTURE_MID_BOX,
    bot_box: MoodboardTextureBox = MOODBOARD_TEXTURE_BOT_BOX,
    font_size: int = 40,
    line_width: int = 150,
    line_thickness: int = 2,
    text_color: tuple[int, int, int] = (255, 255, 255),
) -> Path | Image.Image:
    """Overlay 3 uppercase texture words with centered underline bars onto a 9:16 (1080x1920) moodboard image.

    Renders clean Poppins typography with tracking and Canva coordinates:
      - Top Panel: Box (X=355.5, Y=268.8, W=368.9, H=76.2)
      - Middle Panel: Box (X=231.6, Y=921.9, W=632.9, H=76.2)
      - Bottom Panel: Box (X=346.9, Y=1559.0, W=386.1, H=76.2)
    Each panel features a centered uppercase word and a ~150px centered thin white underline bar.
    Zero layout API cost: executes 100% locally via Python Pillow.
    """
    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    try:
        canvas = source_base.convert("RGB")
        if canvas.size != (1080, 1920):
            canvas = ImageOps.fit(canvas, (1080, 1920), method=Image.LANCZOS, centering=(0.5, 0.5))

        resolved_font_path = (
            Path(font_path)
            if font_path
            else (_resolve_font_path("Poppins-Regular.ttf") or _resolve_font_path("Poppins-Light.ttf") or _resolve_font_path("Poppins-Bold.ttf"))
        )

        draw = ImageDraw.Draw(canvas)

        panels = [
            (top_box, texture_top),
            (mid_box, texture_middle),
            (bot_box, texture_bottom),
        ]

        for box, raw_text in panels:
            word = str(raw_text or "").strip().upper()
            if not word:
                continue

            current_font_size = font_size
            font = (
                ImageFont.truetype(str(resolved_font_path), current_font_size)
                if resolved_font_path
                else ImageFont.load_default()
            )

            # Auto-calculate tracking based on word length
            if len(word) <= 4:
                tracking = 10
            elif len(word) <= 7:
                tracking = 8
            else:
                tracking = 6

            # Auto-scale font down if word exceeds box width
            while current_font_size > 22:
                char_widths = [font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in word]
                calc_width = sum(char_widths) + tracking * (len(word) - 1)
                if calc_width <= (box.width - 20):
                    break
                current_font_size -= 2
                if resolved_font_path:
                    font = ImageFont.truetype(str(resolved_font_path), current_font_size)

            char_widths = [font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in word]
            text_width = sum(char_widths) + tracking * (len(word) - 1)

            # Center text horizontally in box
            start_x = box.x + (box.width - text_width) / 2.0
            start_y = box.y + 20.0

            # Draw letters with letter spacing (tracking)
            cur_x = start_x
            for i, ch in enumerate(word):
                draw.text((cur_x, start_y), ch, font=font, fill=text_color)
                cur_x += char_widths[i] + tracking

            # Draw centered underline bar
            actual_line_w = min(line_width, int(box.width - 20))
            line_x = box.x + (box.width - actual_line_w) / 2.0
            line_y = box.y + 76.0
            draw.rectangle(
                [line_x, line_y, line_x + actual_line_w, line_y + line_thickness],
                fill=text_color,
            )

        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path

        return canvas
    finally:
        if close_base:
            source_base.close()



def overlay_centered_headline(
    base_image: Path | str | Image.Image,
    headline: str,
    destination: Path | str | None = None,
    *,
    font_path: Path | str | None = None,
    font_size: int = 48,
    text_color: tuple[int, int, int] = (255, 255, 255),
) -> Path | Image.Image:
    """Overlay a centered headline on a 9:16 vertical image.
    
    Uses Poppins-Bold by default, pure white text, no shadow.
    Auto-scales the font size if the text is too wide for the canvas.
    """
    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    try:
        canvas = source_base.convert("RGB")
        if font_path is None:
            font_path = _resolve_font_path("Poppins-Bold.ttf")

        # Auto-scaling logic
        current_size = font_size
        font = None
        max_width = canvas.width - 100  # 50px padding on each side
        
        while current_size >= 24:
            try:
                font = ImageFont.truetype(str(font_path), current_size) if font_path else ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()
                break
                
            bbox = font.getbbox(headline)
            text_width = bbox[2] - bbox[0]
            if text_width <= max_width:
                break
            current_size -= 2
            
        if font is None:
            font = ImageFont.load_default()
            
        draw = ImageDraw.Draw(canvas)
        bbox = font.getbbox(headline)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center coordinates
        x = (canvas.width - text_width) / 2.0
        y = (canvas.height - text_height) / 2.0
        
        draw.text((x, y), headline, font=font, fill=text_color)
        
        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path
            
        return canvas
    finally:
        if close_base:
            source_base.close()


# ---------------------------------------------------------------------------
# Christmas Banner title + subtitle (21:9): white Poppins (Medium title, Regular subtitle), soft drop shadow
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BannerTextBox:
    """Text box measured on the 1800x600 banner design canvas."""

    x: float
    y: float
    width: float
    height: float
    canvas_width: int = 1800
    canvas_height: int = 600


# Editor boxes for the banner text (design canvas 1800x600 px).
BANNER_TITLE_BOX = BannerTextBox(x=60, y=340.7, width=1053.6, height=130.9)
BANNER_SUBTITLE_BOX = BannerTextBox(x=60, y=457.9, width=999.5, height=73.4)
# Font sizes come from the Canva editor, which counts in points: 1 pt = 4/3 px.
BANNER_TITLE_FONT_SIZE = 81.8
BANNER_SUBTITLE_FONT_SIZE = 46.3
CANVA_PT_TO_PX = 4.0 / 3.0
# Weights and tight tracking measured from the reference sample (stem width 11-12 px at 109 px
# is Poppins Medium, not Bold; tracking is what makes each line as wide as in the sample).
BANNER_TITLE_FONT_FILE = "Poppins-Medium.ttf"
BANNER_SUBTITLE_FONT_FILE = "Poppins-Regular.ttf"
BANNER_TITLE_LETTER_SPACING_EM = -0.092
BANNER_SUBTITLE_LETTER_SPACING_EM = -0.098
# Soft dark "lift" shadow under the white text (intensity 100 = the reference look).
BANNER_SHADOW_INTENSITY = 100
BANNER_SHADOW_COLOR: tuple[int, int, int] = (0, 0, 0)
_SHADOW_BLUR_EM = 0.145  # gaussian sigma as a fraction of the font size
_SHADOW_OFFSET_EM = 0.04  # downward offset as a fraction of the font size
_SHADOW_MAX_ALPHA = 0.56  # peak shadow opacity at intensity 100 (fitted to the reference sample)


def _tracked_width(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, tracking_px: float) -> float:
    return font.getlength(text) + tracking_px * max(0, len(text) - 1)


def _fit_single_line_font(
    text: str,
    font_path: Path | None,
    size_px: float,
    max_width: float,
    tracking_em: float,
    *,
    floor_ratio: float = 0.6,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Largest font (<= size_px) whose tracked line fits max_width; never below floor_ratio * size_px."""
    if font_path is None:
        return ImageFont.load_default()
    current = float(size_px)
    floor = max(8.0, size_px * floor_ratio)
    while True:
        try:
            font = ImageFont.truetype(str(font_path), current)  # fractional sizes need Pillow >= 10.1
        except (TypeError, ValueError):
            font = ImageFont.truetype(str(font_path), int(round(current)))
        except Exception:
            return ImageFont.load_default()
        if _tracked_width(text, font, tracking_em * current) <= max_width or current <= floor:
            return font
        current -= 2.0


def _draw_tracked_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: int | tuple[int, ...],
    tracking_px: float,
) -> None:
    """Draw left-aligned, vertically centred text with letter spacing.

    Each glyph is placed at its kerned prefix width plus i * tracking_px, so pair kerning is kept.
    """
    x, y = xy
    for index, char in enumerate(text):
        offset = font.getlength(text[:index]) + index * tracking_px
        draw.text((x + offset, y), char, font=font, fill=fill, anchor="lm")


def _shadow_layer(
    size: tuple[int, int],
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    tracking_px: float,
    color: tuple[int, int, int],
    intensity: float,
) -> Image.Image:
    """RGBA soft drop shadow: the glyphs, offset down, blurred, tinted with color (intensity 0-100)."""
    strength = max(0.0, min(1.0, intensity / 100.0))
    font_px = float(getattr(font, "size", 24) or 24)
    mask = Image.new("L", size, 0)
    _draw_tracked_text(
        ImageDraw.Draw(mask), (xy[0], xy[1] + font_px * _SHADOW_OFFSET_EM), text, font, 255, tracking_px
    )
    blurred = mask.filter(ImageFilter.GaussianBlur(max(1.0, font_px * _SHADOW_BLUR_EM)))
    alpha = blurred.point(lambda v: int(v * strength * _SHADOW_MAX_ALPHA))
    layer = Image.new("RGBA", size, (*color, 0))
    layer.putalpha(alpha)
    return layer


def overlay_banner_title_subtitle(
    base_image: Path | str | Image.Image,
    title: str,
    subtitle: str,
    destination: Path | str | None = None,
    *,
    title_box: BannerTextBox = BANNER_TITLE_BOX,
    subtitle_box: BannerTextBox = BANNER_SUBTITLE_BOX,
    title_font_size: float = BANNER_TITLE_FONT_SIZE,
    subtitle_font_size: float = BANNER_SUBTITLE_FONT_SIZE,
    title_letter_spacing_em: float = BANNER_TITLE_LETTER_SPACING_EM,
    subtitle_letter_spacing_em: float = BANNER_SUBTITLE_LETTER_SPACING_EM,
    shadow_intensity: float = BANNER_SHADOW_INTENSITY,
    shadow_color: tuple[int, int, int] = BANNER_SHADOW_COLOR,
    text_color: tuple[int, int, int] = (255, 255, 255),
) -> Path | Image.Image:
    """Stamp a white Poppins-Medium title and a white Poppins-Regular subtitle, each with a soft shadow.

    Boxes and font sizes are given on the 1800x600 Canva design canvas (sizes in Canva points,
    1 pt = 4/3 px). x, width and font size scale with the image width; y and height scale with the
    image height, so the text keeps its relative place in the frame. Each text is one line,
    vertically centred in its box, left-aligned at box.x, with tight letter spacing, and shrinks
    (to no less than 60% of its size) to fit the box width.
    """
    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    try:
        canvas = source_base.convert("RGBA")
        title_path = _resolve_font_path(BANNER_TITLE_FONT_FILE) or _resolve_font_path("Poppins-Bold.ttf")
        subtitle_path = _resolve_font_path(BANNER_SUBTITLE_FONT_FILE)

        def stamp(
            box: BannerTextBox, text: str, font_path: Path | None, size_pt: float, spacing_em: float
        ) -> None:
            nonlocal canvas
            scale_x = canvas.width / box.canvas_width
            scale_y = canvas.height / box.canvas_height
            font = _fit_single_line_font(
                text, font_path, size_pt * CANVA_PT_TO_PX * scale_x, box.width * scale_x, spacing_em
            )
            font_px = float(getattr(font, "size", 24) or 24)
            tracking_px = spacing_em * font_px
            xy = (box.x * scale_x, (box.y + box.height / 2.0) * scale_y)
            if shadow_intensity > 0:
                shadow = _shadow_layer(canvas.size, xy, text, font, tracking_px, shadow_color, shadow_intensity)
                canvas = Image.alpha_composite(canvas, shadow)
            _draw_tracked_text(ImageDraw.Draw(canvas), xy, text, font, (*text_color, 255), tracking_px)

        title = (title or "").strip()
        subtitle = (subtitle or "").strip()
        if title:
            stamp(title_box, title, title_path, title_font_size, title_letter_spacing_em)
        if subtitle:
            stamp(subtitle_box, subtitle, subtitle_path, subtitle_font_size, subtitle_letter_spacing_em)

        result = canvas.convert("RGB")
        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            result.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path
        return result
    finally:
        if close_base:
            source_base.close()


# ---------------------------------------------------------------------------
# Sale banner (1800x600): two interior photos either side of a red sale panel
# ---------------------------------------------------------------------------
# Geometry, fonts, sizes and tracking are fitted numerically to the Canva reference sample
# (1800x600). Everything is Poppins: Medium for the headline, SALE and the big numbers,
# Regular for UP TO, %, OFF and the captions, all with about -0.09 em tracking.

SALE_CANVAS_SIZE = (1800, 600)
SALE_PANEL_X = (483, 1317)  # red panel columns [483, 1317): 834 px wide, full height
SALE_PANEL_COLOR: tuple[int, int, int] = (255, 49, 49)
SALE_PANEL_MIN_CONTRAST = 4.5  # WCAG AA for normal text: white text on the panel must reach this ratio
SALE_SIDE_SLOTS = ((0, 483), (1317, 1800))  # left / right interior photo columns
SALE_TEXT_COLOR: tuple[int, int, int] = (255, 255, 255)
SALE_TRACKING_EM = -0.09

SALE_HEADLINE_TEXT = "Limited -Time Offer"


def parse_hex_color(text: object) -> tuple[int, int, int] | None:
    """First '#RGB' / '#RRGGBB' in ``text`` (or a bare hex string) as an RGB tuple, else None."""
    raw = str(text or "").strip()
    match = re.search(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])", raw)
    if match:
        digits = match.group(1)
    elif re.fullmatch(r"[0-9a-fA-F]{6}|[0-9a-fA-F]{3}", raw):
        digits = raw
    else:
        return None
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def format_hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def contrast_with_white(rgb: tuple[int, int, int]) -> float:
    """WCAG contrast ratio between white and ``rgb`` (1.0 = identical, 21.0 = black)."""
    def channel(value: int) -> float:
        v = value / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return 1.05 / (luminance + 0.05)


def ensure_white_text_contrast(
    rgb: tuple[int, int, int], minimum: float = SALE_PANEL_MIN_CONTRAST
) -> tuple[int, int, int]:
    """Darken ``rgb`` in small steps (keeping its hue) until white text on it reaches ``minimum``."""
    color = tuple(int(c) for c in rgb)
    for _ in range(80):
        if contrast_with_white(color) >= minimum:
            break
        color = tuple(int(c * 0.96) for c in color)
    return color  # type: ignore[return-value]


@dataclass(frozen=True)
class SaleTextStyle:
    """One fitted text element: font file, size in px and tracking in em."""

    font_file: str
    size: float
    tracking_em: float = SALE_TRACKING_EM


# Canva shows font sizes in points; Pillow wants pixels on the 1800x600 canvas (1 pt = 4/3 px).
SALE_PT_TO_PX = 4.0 / 3.0
SALE_HEADLINE_PT = 60.9
SALE_WORD_PT = 168.0
SALE_NUMBER_PT = 141.0
SALE_UPTO_PT = 26.7
SALE_PERCENT_PT = 50.5
SALE_OFF_PT = 51.3

SALE_HEADLINE_STYLE = SaleTextStyle("Poppins-Medium.ttf", SALE_HEADLINE_PT * SALE_PT_TO_PX)
SALE_WORD_STYLE = SaleTextStyle("Poppins-Medium.ttf", SALE_WORD_PT * SALE_PT_TO_PX)
# The reference sample's "XX" was fitted at -0.17 em (the X glyphs overlap); real digits read better at the shared -0.09.
SALE_NUMBER_STYLE = SaleTextStyle("Poppins-Medium.ttf", SALE_NUMBER_PT * SALE_PT_TO_PX)
SALE_UPTO_STYLE = SaleTextStyle("Poppins-Regular.ttf", SALE_UPTO_PT * SALE_PT_TO_PX)
SALE_PERCENT_STYLE = SaleTextStyle("Poppins-Regular.ttf", SALE_PERCENT_PT * SALE_PT_TO_PX)
SALE_OFF_STYLE = SaleTextStyle("Poppins-Regular.ttf", SALE_OFF_PT * SALE_PT_TO_PX)
SALE_CAPTION_STYLE = SaleTextStyle("Poppins-Regular.ttf", 17.8)

# Headline and SALE are centred on the ink centres measured on the sample (so a size change never shifts them),
# each on its own baseline.
SALE_HEADLINE_INK_CENTER = 909.5
SALE_HEADLINE_BASELINE = 117.0
SALE_WORD_INK_CENTER = 900.5
SALE_WORD_BASELINE = 299.0

# Percent block, measured on the left block of the sample; both blocks use this geometry.
SALE_BLOCK_CENTERS = (709.5, 1092.5)  # ink centre of each block (UP TO .. OFF)
SALE_NUMBER_BASELINE = 493.0
SALE_PERCENT_BASELINE = 401.0
SALE_OFF_BASELINE = 462.0
SALE_UPTO_INK_BOTTOM = 408
SALE_UPTO_TO_NUMBER = 27.0  # UP TO ink-left to number ink-left
SALE_NUMBER_TO_PERCENT = 5.0  # number ink-right to % ink-left
SALE_NUMBER_TO_OFF = 6.0  # number ink-right to OFF ink-left

# Captions: two or three centred lines under each block.
SALE_CAPTION_CENTERS = (702.0, 1086.0)
SALE_CAPTION_FIRST_BASELINE = 535.5
SALE_CAPTION_LINE_PITCH = 20.6
SALE_CAPTION_MAX_WIDTH = 290.0
SALE_CAPTION_MAX_LINES = 3


def _sale_font(style: SaleTextStyle) -> ImageFont.FreeTypeFont:
    path = _resolve_font_path(style.font_file)
    if path is None:
        raise FileNotFoundError(f"Poppins font not found: {style.font_file}")
    try:
        return ImageFont.truetype(str(path), style.size)
    except (TypeError, ValueError):
        return ImageFont.truetype(str(path), int(round(style.size)))


def _sale_text_ink(text: str, font: ImageFont.FreeTypeFont, tracking_px: float) -> tuple[float, float, float, float]:
    """Ink box (left, top, right, bottom, all inclusive) of tracked text drawn at origin (0, 0), baseline anchor.

    Measured from a raster (fully covered pixels only) because ``font.getbbox`` reports advance
    widths, not ink. Fully covered pixels match how the reference sample was measured.
    """
    size = float(getattr(font, "size", 24) or 24)
    pad = int(size) + 8
    base = int(size * 1.3)
    width = int(font.getlength(text) + abs(tracking_px) * len(text) + pad * 2)
    strip = Image.new("L", (width, int(size * 2) + pad), 0)
    strip_draw = ImageDraw.Draw(strip)
    for index, char in enumerate(text):
        offset = font.getlength(text[:index]) + index * tracking_px
        strip_draw.text((pad + offset, base), char, font=font, fill=255, anchor="ls")
    box = strip.point(lambda v: 255 if v >= 245 else 0).getbbox()
    if not box:
        return 0.0, 0.0, 0.0, 0.0
    left, top, right, bottom = box
    return float(left - pad), float(top - base), float(right - 1 - pad), float(bottom - 1 - base)


def _sale_draw_text(
    draw: ImageDraw.ImageDraw,
    origin: tuple[float, float],
    text: str,
    style: SaleTextStyle,
    fill: tuple[int, ...] = (*SALE_TEXT_COLOR, 255),
) -> tuple[float, float, float, float]:
    """Draw left-to-right tracked text with its left origin and baseline at ``origin``; returns the ink box."""
    font = _sale_font(style)
    tracking_px = style.tracking_em * style.size
    x, base = origin
    for index, char in enumerate(text):
        offset = font.getlength(text[:index]) + index * tracking_px
        draw.text((x + offset, base), char, font=font, fill=fill, anchor="ls")
    l, t, r, b = _sale_text_ink(text, font, tracking_px)
    return x + l, base + t, x + r, base + b


def _sale_draw_text_centered(
    draw: ImageDraw.ImageDraw, center_x: float, baseline: float, text: str, style: SaleTextStyle
) -> tuple[float, float, float, float]:
    """Draw tracked text so the centre of its ink box sits on ``center_x``; returns the ink box."""
    font = _sale_font(style)
    left, _, right, _ = _sale_text_ink(text, font, style.tracking_em * style.size)
    return _sale_draw_text(draw, (center_x - (left + right) / 2.0, baseline), text, style)


def _sale_centered_width(text: str, style: SaleTextStyle) -> float:
    font = _sale_font(style)
    return font.getlength(text) + style.tracking_em * style.size * max(0, len(text) - 1)


def wrap_sale_caption(
    text: str,
    style: SaleTextStyle = SALE_CAPTION_STYLE,
    max_width: float = SALE_CAPTION_MAX_WIDTH,
    max_lines: int = SALE_CAPTION_MAX_LINES,
) -> list[str]:
    """Greedy word wrap that reproduces the sample's line breaks; extra words go on the last line."""
    words = str(text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and _sale_centered_width(trial, style) > max_width and len(lines) < max_lines - 1:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _sale_cover_fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _sale_draw_percent_block(
    canvas: Image.Image, percent: str, center_x: float
) -> None:
    """UP TO (rotated) + big number + % over OFF, the block centred on ``center_x`` (ink centre)."""
    draw = ImageDraw.Draw(canvas)
    number_font = _sale_font(SALE_NUMBER_STYLE)
    n_l, _, n_r, _ = _sale_text_ink(percent, number_font, SALE_NUMBER_STYLE.tracking_em * SALE_NUMBER_STYLE.size)
    number_w = n_r - n_l
    off_font = _sale_font(SALE_OFF_STYLE)
    off_l, _, off_r, _ = _sale_text_ink("OFF", off_font, SALE_OFF_STYLE.tracking_em * SALE_OFF_STYLE.size)
    off_w = off_r - off_l

    # Ink-space layout, left edge of "UP TO" = 0.
    number_left = SALE_UPTO_TO_NUMBER
    number_right = number_left + number_w
    off_left = number_right + SALE_NUMBER_TO_OFF
    block_w = off_left + off_w
    block_left = center_x - block_w / 2.0

    # UP TO: horizontal ink rotated 90 degrees counter-clockwise, ink-left at block_left.
    up_font = _sale_font(SALE_UPTO_STYLE)
    up_tracking = SALE_UPTO_STYLE.tracking_em * SALE_UPTO_STYLE.size
    pad = int(SALE_UPTO_STYLE.size)
    width = int(up_font.getlength("UP TO") + abs(up_tracking) * 6 + pad * 2)
    strip = Image.new("L", (width, int(SALE_UPTO_STYLE.size * 2)), 0)
    strip_draw = ImageDraw.Draw(strip)
    for index, char in enumerate("UP TO"):
        strip_draw.text(
            (pad + up_font.getlength("UP TO"[:index]) + index * up_tracking, SALE_UPTO_STYLE.size * 1.4),
            char, font=up_font, fill=255, anchor="ls",
        )
    rotated = strip.rotate(90, expand=True)
    ink = rotated.getbbox()
    if ink:
        rotated = rotated.crop(ink)
        canvas.paste(
            Image.new("RGB", rotated.size, SALE_TEXT_COLOR),
            (int(round(block_left)), int(SALE_UPTO_INK_BOTTOM - rotated.size[1] + 1)),
            rotated,
        )

    # Big number, then % (superscript) and OFF to its right.
    num_origin_x = block_left + number_left - n_l
    _sale_draw_text(draw, (num_origin_x, SALE_NUMBER_BASELINE), percent, SALE_NUMBER_STYLE)
    pct_font = _sale_font(SALE_PERCENT_STYLE)
    p_l, _, _, _ = _sale_text_ink("%", pct_font, 0.0)
    _sale_draw_text(
        draw,
        (block_left + number_right + SALE_NUMBER_TO_PERCENT - p_l, SALE_PERCENT_BASELINE),
        "%", SALE_PERCENT_STYLE,
    )
    _sale_draw_text(
        draw, (block_left + off_left - off_l, SALE_OFF_BASELINE), "OFF", SALE_OFF_STYLE
    )


def draw_sale_banner(
    left_image: Path | str | Image.Image,
    right_image: Path | str | Image.Image,
    *,
    percent_left: str | int = 10,
    percent_right: str | int = 15,
    caption_left: str = "On all items from curated monthly collection on [Date]",
    caption_right: str = "On all items from a curated collection on [Date]",
    headline: str = SALE_HEADLINE_TEXT,
    destination: Path | str | None = None,
    panel_color: tuple[int, int, int] | str | None = None,
) -> Path | Image.Image:
    """Compose the 1800x600 sale banner: interiors left and right, coloured panel with the sale text between.

    ``panel_color`` is an RGB tuple or a hex string; None or an unparseable value keeps the sample's red.

    The two photos are cover-fitted into their 483 px slots. Text is white Poppins fitted to the
    reference sample. Captions wrap on the sample's line breaks and are centred under each block.
    """
    width, height = SALE_CANVAS_SIZE
    if isinstance(panel_color, str):
        panel_color = parse_hex_color(panel_color)
    panel: tuple[int, int, int] = tuple(panel_color) if panel_color else SALE_PANEL_COLOR  # type: ignore[assignment]

    def open_rgb(source: Path | str | Image.Image) -> Image.Image:
        if isinstance(source, (str, Path)):
            with Image.open(source) as opened:
                return opened.convert("RGB")
        return source.convert("RGB")

    canvas = Image.new("RGB", (width, height), panel)
    for source, (x0, x1) in zip((left_image, right_image), SALE_SIDE_SLOTS):
        canvas.paste(_sale_cover_fit(open_rgb(source), (x1 - x0, height)), (x0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([SALE_PANEL_X[0], 0, SALE_PANEL_X[1] - 1, height - 1], fill=panel)
    # The reference panel spans x 482.5 to 1317.5, so the two edge columns are a 50% mix of panel and photo.
    for edge_x in (SALE_PANEL_X[0] - 1, SALE_PANEL_X[1]):
        column = canvas.crop((edge_x, 0, edge_x + 1, height))
        canvas.paste(Image.blend(column, Image.new("RGB", column.size, panel), 0.5), (edge_x, 0))

    _sale_draw_text_centered(draw, SALE_HEADLINE_INK_CENTER, SALE_HEADLINE_BASELINE, headline, SALE_HEADLINE_STYLE)
    _sale_draw_text_centered(draw, SALE_WORD_INK_CENTER, SALE_WORD_BASELINE, "SALE", SALE_WORD_STYLE)

    for percent, center_x in zip((percent_left, percent_right), SALE_BLOCK_CENTERS):
        _sale_draw_percent_block(canvas, str(percent), center_x)

    for caption, center_x in zip((caption_left, caption_right), SALE_CAPTION_CENTERS):
        for line_index, line in enumerate(wrap_sale_caption(caption)):
            line_w = _sale_centered_width(line, SALE_CAPTION_STYLE)
            _sale_draw_text(
                draw,
                (center_x - line_w / 2.0, SALE_CAPTION_FIRST_BASELINE + line_index * SALE_CAPTION_LINE_PITCH),
                line, SALE_CAPTION_STYLE,
            )

    if destination is not None:
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(dest_path, "JPEG", quality=95, optimize=True)
        return dest_path
    return canvas


# ---------------------------------------------------------------------------
# Ad Cover local composite (1:1 1080x1080 and 9:16 1080x1920 Story)
# ---------------------------------------------------------------------------

# Per-fixture transparent PNG overlays carrying the tagline + HomeCartel mark.
# Rendered 100% locally so no API call is ever made for Ad Cover typography.
AD_COVER_FIXTURE_ASSETS: dict[str, str] = {
    "chandelier": "chand-collection.png",
    "floor-lamp": "trending.png",
    "table-lamp": "table-lamps-collection.png",
    "cluster-chandelier": "clsuter-collec.png",
    "pendant": "pendant-light-collec.png",
    "wall-light": "wall-collec.png",
    "new-collection": "new-collection.png",
    "on-sale": "on-sale.png",
    "on-stock": "on-stock-feed.png",
}

# The 9:16 Story variant of the same overlay, kept in its own registry so a
# fixture that has no story PNG can never fall back onto the square one and get
# stretched across a 1080x1920 canvas.
AD_COVER_STORY_ASSETS: dict[str, str] = {
    "chandelier": "ad-cover-chandelier-story.png",
    "table-lamp": "table-lamps-collection.story.png",
    "floor-lamp": "trending-lights-collection-story.png",
    "cluster-chandelier": "cluster-chandelier-collection-story.png",
    "pendant": "pendant-light-collect-story.png",
    "new-collection": "new-collection-story.png",
    "on-sale": "on-sale-story-collection.png",
    "on-stock": "on-stock-collection-story.png",
}

AD_COVER_CANVAS_SIZE = (1080, 1080)
AD_COVER_STORY_CANVAS_SIZE = (1080, 1920)


def overlay_ad_cover_layout(
    base_image: Path | str | Image.Image,
    fixture: str = "chandelier",
    destination: Path | str | None = None,
    *,
    asset_name: str | None = None,
    canvas_size: tuple[int, int] = AD_COVER_CANVAS_SIZE,
) -> Path | Image.Image:
    """Composite the fixture's transparent Ad Cover overlay over a room photo.

    The overlay asset already contains the tagline and the HomeCartel brand mark
    on a transparent background, so this is a pure local Pillow composite with
    zero API cost. The room photo is centre-cropped to ``canvas_size`` (1080x1080
    for the square feed cover, 1080x1920 for the 9:16 Story variant) so the
    result always fills the requested canvas cleanly.

    Returns the saved ``Path`` when ``destination`` is given, otherwise the
    in-memory ``Image`` (RGB).
    """
    if fixture == "floor-lamp" and canvas_size == AD_COVER_CANVAS_SIZE and not asset_name:
        fl_custom = _resolve_asset_file("floor-lamp-collection.png")
        if fl_custom is not None:
            resolved_name = "floor-lamp-collection.png"
        else:
            resolved_name = AD_COVER_FIXTURE_ASSETS.get(fixture)
    else:
        resolved_name = asset_name or (
            AD_COVER_STORY_ASSETS.get(fixture)
            if canvas_size == AD_COVER_STORY_CANVAS_SIZE
            else AD_COVER_FIXTURE_ASSETS.get(fixture)
        )
    overlay_path = _resolve_asset_file(resolved_name) if resolved_name else None
    if overlay_path is None:
        if canvas_size == AD_COVER_STORY_CANVAS_SIZE:
            fallback_name = AD_COVER_STORY_ASSETS.get("chandelier") if fixture == "chandelier" else None
        else:
            fallback_name = AD_COVER_FIXTURE_ASSETS.get(fixture) or AD_COVER_FIXTURE_ASSETS.get("chandelier")
        overlay_path = _resolve_asset_file(fallback_name) if fallback_name else None

    if overlay_path is None:
        raise FileNotFoundError(
            f"Ad Cover overlay asset {resolved_name!r} was not found in any known asset directory."
        )

    if isinstance(base_image, (str, Path)):
        source_base = Image.open(base_image)
        close_base = True
    else:
        source_base = base_image
        close_base = False

    overlay_src = Image.open(overlay_path)
    try:
        canvas = ImageOps.fit(
            source_base.convert("RGB"),
            canvas_size,
            method=Image.LANCZOS,
            centering=(0.5, 0.5),
        ).convert("RGBA")

        overlay = overlay_src.convert("RGBA")
        if overlay.size != canvas_size:
            overlay = overlay.resize(canvas_size, Image.LANCZOS)

        composited = Image.alpha_composite(canvas, overlay).convert("RGB")

        if destination is not None:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            composited.save(dest_path, "JPEG", quality=95, optimize=True)
            return dest_path

        return composited
    finally:
        overlay_src.close()
        if close_base:
            source_base.close()

