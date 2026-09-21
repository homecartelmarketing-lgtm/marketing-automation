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

