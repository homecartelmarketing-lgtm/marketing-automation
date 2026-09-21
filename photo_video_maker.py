#!/usr/bin/env python3
"""Create a vertical product-photo video in the style of the reference.

The default output matches the reference format:
  * 720 x 1280 (9:16), 30 fps
  * ~2.9 seconds per photo
  * heavily zoomed full-screen duplicate background plus a centered
    portrait photo card (about 68% x 70% of the frame)
  * slow Ken Burns zoom while each photo holds
  * smooth upward background drift, as if the background enters from below
  * subpixel crop animation to prevent one-pixel zoom shaking
  * vertical push transition: the whole composition slides up and the
    next photo pushes in from the bottom
  * optional title text over any photo (--title, repeatable)
  * optional brand end card with logo + call-to-action (--brand, --cta,
    --logo), crossfaded in at the end

Quick start:
  pip install Pillow numpy imageio-ffmpeg
  python photo_video_maker.py photos --output product_video.mp4 \
      --title "Minimal Table Lamp" \
      --brand "YOUR BRAND" --cta "Shop now at yourbrand.com" \
      --audio music.mp3

You may also double-click/run this script without arguments to open a photo
picker. Photos found in a folder are ordered naturally by filename, so names
such as 01.jpg, 02.jpg, 03.jpg control the sequence.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
except ImportError as exc:
    raise SystemExit(
        "Missing Python packages. Install them with:\n"
        "  pip install Pillow numpy imageio-ffmpeg"
    ) from exc


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


@dataclass(frozen=True)
class Settings:
    width: int = 720
    height: int = 1280
    fps: int = 30
    seconds_per_photo: float = 2.9
    transition_seconds: float = 0.7
    card_width: float = 0.68
    card_height: float = 0.70
    background_zoom: float = 2.0
    background_brightness: float = 1.0
    background_pan: float = 0.08
    kenburns_zoom: float = 0.06
    focus_x: float = 0.50
    focus_y: float = 0.50
    titles: tuple[str, ...] = ()
    brand: str = ""
    cta: str = ""
    logo: str = ""
    outro: str = ""
    endcard_seconds: float = 2.5
    endcard_fade: float = 0.8
    endcard_color: str = "#EDE8DE"
    crf: int = 18
    preset: str = "medium"


@dataclass(frozen=True)
class PreparedPhoto:
    card_source: np.ndarray  # oversized card crop, for Ken Burns
    background_source: np.ndarray  # oversized full-frame crop, for Ken Burns
    title_layer: np.ndarray | None  # RGBA text overlay, frame sized
    title_alpha_max: float = 1.0


# --------------------------------------------------------------------------
# Photo collection
# --------------------------------------------------------------------------


def natural_key(path: Path) -> list[object]:
    """Sort 2.jpg before 10.jpg while remaining case-insensitive."""
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def collect_photos(inputs: Sequence[str]) -> list[Path]:
    photos: list[Path] = []
    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_dir():
            folder_photos = [
                item
                for item in path.iterdir()
                if item.is_file() and item.suffix.casefold() in IMAGE_EXTENSIONS
            ]
            photos.extend(sorted(folder_photos, key=natural_key))
        elif path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS:
            photos.append(path)
        else:
            raise ValueError(f"Not a supported photo or folder: {path}")

    # Remove accidental duplicates while keeping the requested sequence.
    seen: set[Path] = set()
    unique: list[Path] = []
    for photo in photos:
        resolved = photo.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def choose_photos_gui() -> tuple[list[str], str] | None:
    """Open a basic picker when the script is launched without arguments."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    try:
        root = tk.Tk()
        root.withdraw()
        root.update()
        selected = filedialog.askopenfilenames(
            title="Choose photos for the video",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            root.destroy()
            return None

        output = filedialog.asksaveasfilename(
            title="Save the finished video",
            defaultextension=".mp4",
            initialfile="product_video.mp4",
            filetypes=[("MP4 video", "*.mp4")],
        )
        root.destroy()
        if not output:
            return None
        return list(selected), output
    except tk.TclError:
        return None


def find_ffmpeg() -> str:
    """Use system FFmpeg, or imageio-ffmpeg's bundled copy when available."""
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "FFmpeg was not found. Run `pip install imageio-ffmpeg`, or install "
            "FFmpeg and add it to PATH."
        ) from exc


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

FONT_DIRECTORIES = (
    str(Path(__file__).parent / "content_automation" / "fonts"),
    str(Path("content_automation/fonts")),
    "C:/Windows/Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/Library/Fonts",
    "/System/Library/Fonts",
    str(Path.home() / "Library/Fonts"),
    str(Path.home() / ".fonts"),
)

TITLE_FONTS = (
    "poppins-regular.ttf",
    "poppins-semibold.ttf",
    "poppins-bold.ttf",
    "montserrat-semibold.ttf",
    "montserrat-bold.ttf",
    "segoeuib.ttf",
    "arialbd.ttf",
    "dejavusans-bold.ttf",
    "liberationsans-bold.ttf",
)

BRAND_FONTS = (
    "arialbd.ttf",
    "helveticaneue-bold.ttf",
    "segoeuib.ttf",
    "montserrat-extrabold.ttf",
    "poppins-bold.ttf",
    "dejavusans-bold.ttf",
    "liberationsans-bold.ttf",
)

BODY_FONTS = (
    "arial.ttf",
    "segoeui.ttf",
    "poppins-regular.ttf",
    "montserrat-regular.ttf",
    "dejavusans.ttf",
    "liberationsans-regular.ttf",
)


def find_font(candidates: Sequence[str], size: int) -> ImageFont.FreeTypeFont:
    wanted = [name.casefold() for name in candidates]
    found: dict[str, str] = {}
    for directory in FONT_DIRECTORIES:
        if not os.path.isdir(directory):
            continue
        for base, _dirs, files in os.walk(directory):
            for file_name in files:
                lowered = file_name.casefold()
                if lowered in wanted and lowered not in found:
                    found[lowered] = os.path.join(base, file_name)
    for name in wanted:
        if name in found:
            return ImageFont.truetype(found[name], size)
    return ImageFont.load_default(size)


# --------------------------------------------------------------------------
# Image preparation
# --------------------------------------------------------------------------


def open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(white, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
        return image.copy()


def cover(
    image: Image.Image,
    size: tuple[int, int],
    focus_x: float,
    focus_y: float,
) -> Image.Image:
    return ImageOps.fit(
        image,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(focus_x, focus_y),
    )


def card_size(settings: Settings) -> tuple[int, int]:
    card_width = max(2, int(round(settings.width * settings.card_width)))
    card_height = max(2, int(round(settings.height * settings.card_height)))
    # H.264/yuv420 works most reliably with even dimensions.
    card_width -= card_width % 2
    card_height -= card_height % 2
    return card_width, card_height


def wrap_title(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        words = raw_line.split()
        if not words:
            continue
        current = words[0]
        for word in words[1:]:
            attempt = f"{current} {word}"
            if font.getlength(attempt) <= max_width:
                current = attempt
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines or [text]


def render_title_layer(title: str, settings: Settings) -> np.ndarray:
    """White centered title with a soft shadow at X=176.7, Y=1651.8 (W=726.6, H=44.5) using Poppins Regular."""
    # Scale coordinates to current resolution relative to 1080x1920 reference
    scale_x = settings.width / 1080.0
    scale_y = settings.height / 1920.0

    # User design: Poppins Regular 28pt at 1080x1920
    size = max(10, int(round(28 * scale_y)))
    font = find_font(TITLE_FONTS, size)

    # User design box: W=726.6, H=44.5, X=176.7, Y=1651.8
    box_w = 726.6 * scale_x
    box_h = 44.5 * scale_y
    box_x = 176.7 * scale_x
    box_y = 1651.8 * scale_y

    max_width = int(box_w)
    lines = wrap_title(title, font, max_width)

    layer = Image.new("RGBA", (settings.width, settings.height), (0, 0, 0, 0))
    line_height = int(round(size * 1.15))
    block_height = line_height * len(lines)

    # Centered horizontally at box center (box_x + box_w / 2.0 = 540 * scale_x)
    center_x = box_x + (box_w / 2.0)
    top_y = box_y + (box_h - block_height) / 2.0

    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    for index, line in enumerate(lines):
        line_width = font.getlength(line)
        x = center_x - (line_width / 2.0)
        y = top_y + index * line_height
        shadow_draw.text((x + 1, y + 2), line, font=font, fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=2))
    layer = Image.alpha_composite(layer, shadow)

    draw = ImageDraw.Draw(layer)
    for index, line in enumerate(lines):
        line_width = font.getlength(line)
        x = center_x - (line_width / 2.0)
        y = top_y + index * line_height
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
    return np.asarray(layer, dtype=np.uint8)


def prepare_photo(path: Path, title: str, settings: Settings) -> PreparedPhoto:
    source = open_rgb(path)
    zoom_headroom = 1.0 + settings.kenburns_zoom + 0.02

    # Card: portrait crop with headroom for the slow zoom.
    card_w, card_h = card_size(settings)
    card_source = cover(
        source,
        (int(round(card_w * zoom_headroom)), int(round(card_h * zoom_headroom))),
        settings.focus_x,
        settings.focus_y,
    )

    # Background: heavily zoomed duplicate of the same photo.
    bg_scale = settings.background_zoom * zoom_headroom
    background = cover(
        source,
        (int(round(settings.width * bg_scale)), int(round(settings.height * bg_scale))),
        settings.focus_x,
        settings.focus_y,
    )
    if abs(settings.background_brightness - 1.0) > 1e-3:
        background = ImageEnhance.Brightness(background).enhance(
            settings.background_brightness
        )

    title_layer = render_title_layer(title, settings) if title.strip() else None
    return PreparedPhoto(
        card_source=np.asarray(card_source, dtype=np.uint8),
        background_source=np.asarray(background, dtype=np.uint8),
        title_layer=title_layer,
    )


# --------------------------------------------------------------------------
# Frame composition
# --------------------------------------------------------------------------


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def zoom_crop(
    source: np.ndarray,
    out_size: tuple[int, int],
    zoom: float,
    upward_motion: float = 0.0,
) -> np.ndarray:
    """Render a zoomed crop with stable subpixel sampling.

    ``upward_motion`` is measured in output pixels. Positive values move the
    visible image upward by moving the virtual crop window downward. Using a
    fractional transform instead of rounded integer crop coordinates removes
    the small frame-to-frame shake that can appear during a slow zoom.
    """
    out_w, out_h = out_size
    src_h, src_w = source.shape[:2]
    zoom = max(1e-6, float(zoom))

    # All prepared sources share the output aspect ratio, so dividing both
    # dimensions by the same zoom keeps the crop perfectly proportional.
    window_w = min(float(src_w), max(2.0, src_w / zoom))
    window_h = min(float(src_h), max(2.0, src_h / zoom))
    x = (src_w - window_w) * 0.5
    y = (src_h - window_h) * 0.5

    # Convert the requested on-screen travel to source pixels. Clamp it so the
    # crop never samples outside the prepared background.
    y += upward_motion * (window_h / out_h)
    x = min(max(0.0, x), max(0.0, src_w - window_w))
    y = min(max(0.0, y), max(0.0, src_h - window_h))

    image = Image.fromarray(source)
    return np.asarray(
        image.transform(
            out_size,
            Image.Transform.EXTENT,
            (x, y, x + window_w, y + window_h),
            resample=Image.Resampling.BICUBIC,
        ),
        dtype=np.uint8,
    )


def shadow_alpha(settings: Settings) -> np.ndarray:
    card_w, card_h = card_size(settings)
    x = (settings.width - card_w) // 2
    y = (settings.height - card_h) // 2
    mask = Image.new("L", (settings.width, settings.height), 0)
    rectangle = Image.new("L", (card_w, card_h), 90)
    mask.paste(rectangle, (x, y + 8))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=18))
    return np.asarray(mask, dtype=np.uint16)


def compose_photo_frame(
    photo: PreparedPhoto,
    local_progress: float,
    local_seconds: float,
    shadow: np.ndarray,
    settings: Settings,
) -> np.ndarray:
    """One full frame for a photo at `local_progress` (0..1) through its hold."""
    # Easing gives both zoom and drift zero velocity at the beginning and end,
    # avoiding a visible jolt when a new photo takes over.
    motion = smoothstep(local_progress)
    zoom = 1.0 + settings.kenburns_zoom * motion
    background_travel = settings.height * settings.background_pan * motion
    card_w, card_h = card_size(settings)

    frame = zoom_crop(
        photo.background_source,
        (settings.width, settings.height),
        settings.background_zoom * zoom,
        upward_motion=background_travel,
    )
    inverse = 255 - shadow
    frame = ((frame.astype(np.uint16) * inverse[..., None]) // 255).astype(np.uint8)

    card = zoom_crop(photo.card_source, (card_w, card_h), zoom)
    x = (settings.width - card_w) // 2
    y = (settings.height - card_h) // 2
    frame[y : y + card_h, x : x + card_w] = card

    if photo.title_layer is not None:
        fade = smoothstep((local_seconds - 0.15) / 0.35)
        if fade > 0.0:
            alpha = (photo.title_layer[..., 3:4].astype(np.float32) / 255.0) * fade
            rgb = photo.title_layer[..., :3].astype(np.float32)
            frame = (
                frame.astype(np.float32) * (1.0 - alpha) + rgb * alpha
            ).astype(np.uint8)
    return frame


def vertical_push(
    top_frame: np.ndarray, bottom_frame: np.ndarray, progress: float
) -> np.ndarray:
    """Push the current frame up while the next slides in from the bottom."""
    height = top_frame.shape[0]
    offset = int(round(height * smoothstep(progress)))
    if offset <= 0:
        return top_frame
    if offset >= height:
        return bottom_frame
    result = np.empty_like(top_frame)
    result[: height - offset] = top_frame[offset:]
    result[height - offset :] = bottom_frame[:offset]
    return result


# --------------------------------------------------------------------------
# End card
# --------------------------------------------------------------------------


def parse_color(text: str) -> tuple[int, int, int]:
    value = text.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"Not a valid hex color: {text}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def render_end_card(settings: Settings) -> np.ndarray:
    if settings.outro.strip():
        outro_path = Path(settings.outro).expanduser()
        if outro_path.is_file():
            with Image.open(outro_path) as raw_outro:
                card = cover(raw_outro.convert("RGB"), (settings.width, settings.height), 0.5, 0.5)
            return np.asarray(card, dtype=np.uint8)

    color = parse_color(settings.endcard_color)
    card = Image.new("RGB", (settings.width, settings.height), color)
    draw = ImageDraw.Draw(card)

    brand_size = max(12, int(round(settings.height * 0.062)))
    brand_font = find_font(BRAND_FONTS, brand_size)
    max_width = int(settings.width * 0.82)
    lines = wrap_title(settings.brand.upper(), brand_font, max_width)
    line_height = int(round(brand_size * 1.06))
    block_height = line_height * len(lines)

    logo_image: Image.Image | None = None
    logo_gap = 0
    if settings.logo:
        logo_path = Path(settings.logo).expanduser()
        if logo_path.is_file():
            with Image.open(logo_path) as raw_logo:
                logo_image = raw_logo.convert("RGBA").copy()
            logo_height = int(round(settings.height * 0.075))
            logo_width = max(
                1, int(round(logo_image.width * logo_height / logo_image.height))
            )
            logo_image = logo_image.resize(
                (logo_width, logo_height), Image.Resampling.LANCZOS
            )
            logo_gap = int(round(settings.height * 0.028))

    total = block_height + (logo_image.height + logo_gap if logo_image else 0)
    top = (settings.height - total) // 2

    if logo_image is not None:
        card.paste(
            logo_image,
            ((settings.width - logo_image.width) // 2, top),
            logo_image,
        )
        top += logo_image.height + logo_gap

    for index, line in enumerate(lines):
        line_width = brand_font.getlength(line)
        draw.text(
            ((settings.width - line_width) / 2, top + index * line_height),
            line,
            font=brand_font,
            fill=(20, 20, 20),
        )

    if settings.cta.strip():
        cta_size = max(10, int(round(settings.height * 0.028)))
        cta_font = find_font(BODY_FONTS, cta_size)
        cta_width = cta_font.getlength(settings.cta)
        draw.text(
            (
                (settings.width - cta_width) / 2,
                int(settings.height * 0.925),
            ),
            settings.cta,
            font=cta_font,
            fill=(35, 35, 35),
        )
    return np.asarray(card, dtype=np.uint8)


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------


def make_frame(
    photos: Sequence[PreparedPhoto],
    end_card: np.ndarray | None,
    time_seconds: float,
    shadow: np.ndarray,
    settings: Settings,
) -> np.ndarray:
    count = len(photos)
    photos_duration = count * settings.seconds_per_photo

    def photo_frame(index: int, at_time: float) -> np.ndarray:
        start = index * settings.seconds_per_photo
        local = at_time - start
        progress = local / settings.seconds_per_photo
        return compose_photo_frame(photos[index], progress, local, shadow, settings)

    if end_card is not None and time_seconds >= photos_duration - 1e-9:
        fade = smoothstep(
            (time_seconds - photos_duration) / max(settings.endcard_fade, 1e-6)
        )
        if fade >= 1.0:
            return end_card
        last = photo_frame(count - 1, photos_duration - 1e-3)
        return (
            last.astype(np.float32) * (1.0 - fade)
            + end_card.astype(np.float32) * fade
        ).astype(np.uint8)

    half = settings.transition_seconds * 0.5
    boundary = int(round(time_seconds / settings.seconds_per_photo))
    if 1 <= boundary < count:
        boundary_time = boundary * settings.seconds_per_photo
        start = boundary_time - half
        end = boundary_time + half
        if start <= time_seconds < end:
            progress = (time_seconds - start) / settings.transition_seconds
            current = photo_frame(boundary - 1, time_seconds)
            following = photo_frame(boundary, max(boundary_time, time_seconds))
            return vertical_push(current, following, progress)

    index = min(count - 1, int(time_seconds / settings.seconds_per_photo))
    return photo_frame(index, time_seconds)


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------


def ffmpeg_command(
    ffmpeg: str,
    output: Path,
    audio: Path | None,
    duration: float,
    settings: Settings,
) -> list[str]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        f"{settings.width}x{settings.height}",
        "-r",
        str(settings.fps),
        "-i",
        "-",
    ]
    if audio is not None:
        command.extend(["-stream_loop", "-1", "-i", str(audio)])

    command.extend(
        [
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-preset",
            settings.preset,
            "-crf",
            str(settings.crf),
            "-pix_fmt",
            "yuv420p",
        ]
    )
    if audio is not None:
        fade_start = max(0.0, duration - 1.0)
        command.extend(
            [
                "-map",
                "1:a:0",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-af",
                f"afade=t=out:st={fade_start:.3f}:d=1",
                "-t",
                f"{duration:.6f}",
            ]
        )
    else:
        command.append("-an")

    command.extend(["-movflags", "+faststart", str(output)])
    return command


def render_video(
    paths: Sequence[Path],
    output: Path,
    audio: Path | None,
    settings: Settings,
) -> None:
    if settings.width % 2 or settings.height % 2:
        raise ValueError("Video width and height must be even numbers.")
    if settings.transition_seconds <= 0:
        raise ValueError("Transition duration must be greater than zero.")
    if settings.transition_seconds >= settings.seconds_per_photo:
        raise ValueError("Transition duration must be shorter than photo duration.")
    if not 0.30 <= settings.card_width <= 1.00:
        raise ValueError("Card width must be between 0.30 and 1.00.")
    if not 0.30 <= settings.card_height <= 1.00:
        raise ValueError("Card height must be between 0.30 and 1.00.")
    if settings.background_zoom < 1.0:
        raise ValueError("Background zoom must be at least 1.0.")
    if not 0.0 <= settings.kenburns_zoom <= 0.5:
        raise ValueError("Ken Burns zoom must be between 0.0 and 0.5.")

    print(f"Preparing {len(paths)} photo(s)...")
    titles = list(settings.titles) + [""] * (len(paths) - len(settings.titles))
    prepared = [
        prepare_photo(path, title, settings)
        for path, title in zip(paths, titles)
    ]
    shadow = shadow_alpha(settings)
    end_card = render_end_card(settings) if (settings.outro.strip() or settings.brand.strip()) else None

    duration = len(prepared) * settings.seconds_per_photo
    if end_card is not None:
        duration += settings.endcard_seconds
    total_frames = int(round(duration * settings.fps))
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    command = ffmpeg_command(ffmpeg, output, audio, duration, settings)
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise RuntimeError("Could not start FFmpeg.")

    last_percent = -1
    try:
        for frame_number in range(total_frames):
            time_seconds = frame_number / settings.fps
            frame = make_frame(prepared, end_card, time_seconds, shadow, settings)
            process.stdin.write(frame.tobytes())
            percent = int((frame_number + 1) * 100 / total_frames)
            if percent // 5 != last_percent // 5:
                print(f"Rendering: {percent:3d}%", flush=True)
                last_percent = percent
        process.stdin.close()
        return_code = process.wait()
        error_text = process.stderr.read().decode("utf-8", errors="replace").strip()
    except (BrokenPipeError, KeyboardInterrupt):
        process.kill()
        error_text = process.stderr.read().decode("utf-8", errors="replace").strip()
        if error_text:
            raise RuntimeError(f"FFmpeg stopped unexpectedly:\n{error_text}")
        raise

    if return_code != 0:
        raise RuntimeError(f"FFmpeg failed:\n{error_text or 'Unknown encoding error'}")
    print(f"Finished: {output.resolve()}")


def existing_audio(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Audio file does not exist: {path}")
    return path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Turn product photos into a 9:16 scrolling-panel slideshow matching "
            "the supplied reference video."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        nargs="*",
        help="Photo file(s), or a folder containing photos",
    )
    parser.add_argument("-o", "--output", default="product_video.mp4")
    parser.add_argument("--audio", help="Optional music/audio file; it loops if short")
    parser.add_argument("--seconds", type=float, default=2.9, help="Seconds per photo")
    parser.add_argument(
        "--transition", type=float, default=0.7, help="Vertical push duration"
    )
    parser.add_argument(
        "--title",
        action="append",
        default=[],
        help=(
            "Title text drawn over a photo; repeat the flag for later photos "
            "in order (pass an empty string to skip one)"
        ),
    )
    parser.add_argument("--brand", default="", help="Brand name for the end card")
    parser.add_argument(
        "--cta",
        default="",
        help='End-card call to action, e.g. "Shop now at yourbrand.com"',
    )
    parser.add_argument("--logo", default="", help="Optional logo image for the end card")
    parser.add_argument(
        "--outro", default="", help="Optional static outro image for the end card (fades in smoothly without animation)"
    )
    parser.add_argument(
        "--endcard-seconds", type=float, default=2.5, help="End-card duration"
    )
    parser.add_argument(
        "--endcard-fade", type=float, default=0.8, help="Fade-in duration for the end card (seconds)"
    )
    parser.add_argument(
        "--endcard-color", default="#EDE8DE", help="End-card background hex color"
    )
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1280)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--card-width",
        type=float,
        default=0.68,
        help="Card width as a fraction of the frame",
    )
    parser.add_argument(
        "--card-height",
        type=float,
        default=0.70,
        help="Card height as a fraction of the frame",
    )
    parser.add_argument(
        "--background-zoom",
        type=float,
        default=2.0,
        help="How much the full-screen duplicate background is magnified",
    )
    parser.add_argument(
        "--background-brightness",
        type=float,
        default=1.0,
        help="Brightness multiplier for the background",
    )
    parser.add_argument(
        "--background-pan",
        type=float,
        default=0.08,
        help=(
            "Smooth upward background travel as a fraction of frame height "
            "(0 disables; 0.08 moves it upward by 8%%)"
        ),
    )
    parser.add_argument(
        "--zoom",
        type=float,
        default=0.06,
        help="Ken Burns zoom amount over each photo's hold (0 disables)",
    )
    parser.add_argument(
        "--focus-x",
        type=float,
        default=0.50,
        help="Horizontal crop focus from 0.0 (left) to 1.0 (right)",
    )
    parser.add_argument(
        "--focus-y",
        type=float,
        default=0.50,
        help="Vertical crop focus from 0.0 (top) to 1.0 (bottom)",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="H.264 quality; lower is better and larger",
    )
    parser.add_argument(
        "--preset",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
        ],
        default="medium",
        help="H.264 encoding speed",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    gui_choice: tuple[list[str], str] | None = None
    if not raw_argv:
        gui_choice = choose_photos_gui()
        if gui_choice is None:
            parser.print_help()
            print("\nNo photos were selected.", file=sys.stderr)
            return 2
        raw_argv = [*gui_choice[0], "--output", gui_choice[1]]

    args = parser.parse_args(raw_argv)
    try:
        photos = collect_photos(args.input)
        if not photos:
            raise ValueError("No supported photos were found.")
        if not 0.0 <= args.focus_x <= 1.0 or not 0.0 <= args.focus_y <= 1.0:
            raise ValueError("Crop focus values must be between 0.0 and 1.0.")
        if args.seconds <= 0 or args.fps <= 0:
            raise ValueError("Seconds and fps must be greater than zero.")
        if not 0.0 < args.background_brightness <= 2.0:
            raise ValueError("Background brightness must be greater than 0 and at most 2.")
        if not 0.0 <= args.background_pan <= 0.50:
            raise ValueError("Background pan must be between 0.0 and 0.50.")
        parse_color(args.endcard_color)

        settings = Settings(
            width=args.width,
            height=args.height,
            fps=args.fps,
            seconds_per_photo=args.seconds,
            transition_seconds=args.transition,
            card_width=args.card_width,
            card_height=args.card_height,
            background_zoom=args.background_zoom,
            background_brightness=args.background_brightness,
            background_pan=args.background_pan,
            kenburns_zoom=args.zoom,
            focus_x=args.focus_x,
            focus_y=args.focus_y,
            titles=tuple(args.title),
            brand=args.brand,
            cta=args.cta,
            logo=args.logo,
            outro=args.outro,
            endcard_seconds=args.endcard_seconds,
            endcard_fade=args.endcard_fade,
            endcard_color=args.endcard_color,
            crf=args.crf,
            preset=args.preset,
        )
        output = Path(args.output).expanduser().resolve()
        audio = existing_audio(args.audio)
        render_video(photos, output, audio, settings)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
