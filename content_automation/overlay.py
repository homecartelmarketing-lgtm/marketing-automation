"""Stamping a fixed-position logo onto a generated photo.

Kept free of any Airtable or provider knowledge so the placement maths can be
exercised on its own. The coordinates come from a design canvas rather than the
finished image, because providers do not promise an exact pixel size for a given
aspect ratio -- storing the box as a fraction of that canvas keeps the logo in
the same relative spot whatever comes back.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


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
    base_path: Path | str | Image.Image,
    logo_path: Path | str | Image.Image | None = None,
    item_name: str = "Singkwenta Dose",
    destination: Path | str | None = None,
    *,
    logo_box: LogoBox = HOMECARTEL_STORY_LOGO_BOX,
    text_box: StoryTextBox = CTA_STORY_TEXT_BOX,
    headline_font_size: int = 48,
    body_font_size: int = 28,
    with_shadow: bool = False,
) -> Path | Image.Image:
    """Stamp HomeCartel logo and right-aligned CTA text watermark onto a 9:16 image."""
    if isinstance(base_path, (str, Path)):
        with Image.open(base_path) as source_base:
            canvas = source_base.convert("RGB")
    else:
        canvas = base_path.convert("RGB")

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
# Width 77.8, Height 69.3, X 250.8, Y 212.5 (aligned before Double Tap text at X=346.6, Y=212.0)
STYLE_THIS_HEART_BOX = LogoBox(
    x=250.8,
    y=212.5,
    width=77.8,
    height=69.3,
    canvas_width=1080,
    canvas_height=1920,
)

# Slide 2: 'Double tap if you choose:'
# Width 904.7, Height 70.3, X 346.6, Y 212.0
STYLE_THIS_DOUBLE_TAP_BOX = StoryTextBox(
    x=346.6,
    y=212.0,
    width=904.7,
    height=70.3,
    canvas_width=1080,
    canvas_height=1920,
)

# Slide 2: Pill background + Claude Generated Text
# Width 606.4, Height 70.3, X 236.8, Y 1488 (dynamically hugs text, centered horizontally)
STYLE_THIS_PILL_BOX = StoryTextBox(
    x=236.8,
    y=1488.0,
    width=606.4,
    height=70.3,
    canvas_width=1080,
    canvas_height=1920,
)

# Vertical gap (in canvas px) between the 'Double tap if you choose:' headline and the pill below it
STYLE_THIS_DOUBLE_TAP_PILL_GAP = 24.0

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
    2. Heart Emoji + 'Double tap if you choose:' headline rendered as one
       horizontally-centered group, sitting directly above the pill.
    3. Headline text in Poppins-Bold (no shadow), Solid White.
    4. Rounded color Pill for the Claude-generated vibe text anchored to the
       shape spec (X=236.8, Y=1488, W=606.4, H=70.3), centered horizontally,
       width dynamically hugging the text, with centered Poppins-Light text.
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

        # ------------------------------------------------------------------
        # Geometry is computed top-down so the headline (heart + 'Double tap
        # if you choose:') and the Claude-generated color pill are all
        # centered horizontally and stacked together. The pill anchors to
        # STYLE_THIS_PILL_BOX (X=236.8, Y=1488, W=606.4, H=70.3) and the
        # headline sits directly above it.
        # ------------------------------------------------------------------

        # Resolve fonts up-front (needed for measuring the headline & pill text)
        # - Pill (Claude vibe text): Poppins-Light
        # - Headline ('Double tap if you choose:'): Poppins-Bold
        if font_path is None:
            font_path = (
                _resolve_font_path("Poppins-Light.ttf")
                or _resolve_font_path("Poppins-Regular.ttf")
                or _resolve_font_path("Poppins-Bold.ttf")
            )
        headline_font_path = (
            _resolve_font_path("Poppins-Bold.ttf")
            or _resolve_font_path("Poppins-SemiBold.ttf")
            or font_path
        )

        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # --- Pill text metrics (Font size 44 Poppins-Light) ---
        clean_text = str(claude_text or "Warm Olive").strip().strip("[]\"'")
        pill_font_size = int(round(44 * scale_y))
        try:
            font_pill = ImageFont.truetype(str(font_path), pill_font_size) if font_path else ImageFont.load_default()
        except Exception:
            font_pill = ImageFont.load_default()

        bbox_p = font_pill.getbbox(clean_text)
        tw = bbox_p[2] - bbox_p[0]
        th = bbox_p[3] - bbox_p[1]

        # --- Dynamic Pill geometry (roundness 89 / rounded ends, hugging text) ---
        # Height & vertical anchor follow the shape spec (H=70.3, Y=1488),
        # width dynamically hugs the text but the pill stays centered on the canvas.
        pad_x = 44.0 * scale_x  # 44px horizontal spread on each side
        pill_w = tw + pad_x * 2.0
        pill_h = pill_box.height * scale_y  # 70.3px
        pill_x = (canvas.width - pill_w) / 2.0  # Centered horizontally (X=236.8 for default width)
        pill_y = pill_box.y * scale_y  # Y = 1488
        pill_radius = min(int(round(pill_h / 2.0)), 40)

        # --- Headline (heart + 'Double tap if you choose:') centered above pill ---
        headline_text = "Double tap if you choose:"
        hl_font_size = int(round(44 * scale_y))  # Font size 44 Poppins-Bold
        try:
            font_hl = ImageFont.truetype(str(headline_font_path), hl_font_size) if headline_font_path else ImageFont.load_default()
        except Exception:
            font_hl = ImageFont.load_default()

        bbox_hl = font_hl.getbbox(headline_text)
        hl_w = bbox_hl[2] - bbox_hl[0]
        hl_visible_h = bbox_hl[3] - bbox_hl[1]

        # Heart dimensions (scaled) and the gap between the heart and the text
        heart_w = int(round(heart_box.width * scale_x))
        heart_h = int(round(heart_box.height * scale_y))
        heart_gap = int(round(18.0 * scale_x))  # spacing between heart and headline text
        has_heart = bool(heart_asset_path) or _resolve_asset_file("Heaart Emoji.jpg") or _resolve_asset_file("Heart Emoji.jpg")
        group_w = (heart_w + heart_gap if has_heart else 0) + hl_w

        # Center the heart+text group horizontally
        group_x = (canvas.width - group_w) / 2.0
        # Place the headline group above the pill with a fixed gap
        gap = STYLE_THIS_DOUBLE_TAP_PILL_GAP * scale_y
        group_center_y = pill_y - gap - (max(heart_h, hl_visible_h) / 2.0)

        # Heart position (left of the text, vertically centered on the group)
        heart_x = int(round(group_x))
        heart_y = int(round(group_center_y - heart_h / 2.0))

        # Headline text position (right of the heart, vertically centered on the group)
        hl_x = int(round(group_x + (heart_w + heart_gap if has_heart else 0) - bbox_hl[0]))
        hl_y = int(round(group_center_y - hl_visible_h / 2.0 - bbox_hl[1]))

        # 2. Heart Emoji overlay (centered as part of the headline group)
        if heart_asset_path is None:
            heart_asset_path = _resolve_asset_file("Heaart Emoji.jpg") or _resolve_asset_file("Heart Emoji.jpg")

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

                heart_resized = heart_prep.resize((heart_w, heart_h), Image.LANCZOS)
                img.paste(heart_resized, (heart_x, heart_y), heart_resized)
                if close_heart:
                    heart_source.close()
            except Exception as err:
                print(f"[WARN] Failed to overlay heart emoji: {err}")

        # 3. Headline text (Poppins Bold, no shadow/outline)
        text_color = (255, 255, 255, 255)
        draw.text((hl_x, hl_y), headline_text, font=font_hl, fill=text_color)

        # 4. Dynamic Pill background (roundness 89 / rounded ends, 100% opacity)

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

        # 5. Text inside pill (Font size 44 Poppins-Light, centered, no shadow)
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



