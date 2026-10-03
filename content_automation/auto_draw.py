"""Auto Draw Engine: Traces item outlines and renders real-time line-drawing reveal video.

Ported from C:\\Users\\User\\Downloads\\Auto Draw\\auto_draw_reveal.py.
Automates comparing an empty room interior (BEFORE) with a finished room scene (AFTER),
extracting the newly added lighting fixture's vector stroke paths via Canny edge subtraction,
generating an outline preview image (Sketch Image), and rendering a line-drawing reveal MP4 video.
"""

from __future__ import annotations

import math
from pathlib import Path
import subprocess
import sys
from typing import Sequence

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageOps


def load_rgb(path: Path | str) -> Image.Image:
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def edge_paths(edge_map: np.ndarray, min_length: float = 12.0) -> list[np.ndarray]:
    """Convert one-pixel edges to vector paths without tracing both contour borders."""
    ys, xs = np.nonzero(edge_map)
    pixels = set(zip(xs.tolist(), ys.tolist()))
    graph: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for x, y in pixels:
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            q = (x + dx, y + dy)
            if q not in pixels:
                continue
            if dx and dy and ((x + dx, y) in pixels or (x, y + dy) in pixels):
                continue
            neighbors.append(q)
        graph[(x, y)] = sorted(neighbors, key=lambda q: (q[1], q[0]))

    used: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    paths: list[np.ndarray] = []

    def key(a: tuple[int, int], b: tuple[int, int]):
        return (a, b) if a < b else (b, a)

    # Trace branches/endpoints first, then remaining closed loops
    starts = sorted(pixels, key=lambda p: (len(graph[p]) == 2, p[1], p[0]))
    for start in starts:
        for neighbor in graph[start]:
            if key(start, neighbor) in used:
                continue
            path = [start]
            prev, cur = start, neighbor
            used.add(key(prev, cur))
            while True:
                path.append(cur)
                choices = [n for n in graph[cur] if key(cur, n) not in used]
                if len(graph[cur]) != 2 or not choices:
                    break
                nxt = choices[0]
                used.add(key(cur, nxt))
                prev, cur = cur, nxt
            arr = np.asarray(path, dtype=np.float32)
            if len(arr) > 1 and np.linalg.norm(np.diff(arr, axis=0), axis=1).sum() >= min_length:
                # Simplify pixel stair steps while retaining product shape
                arr = cv2.approxPolyDP(arr.reshape(-1, 1, 2), 0.65, False).reshape(-1, 2)
                paths.append(arr)

    # Top-to-bottom bands, left-to-right within each band
    paths.sort(key=lambda p: (int(p[:, 1].min() // 35), float(p[:, 0].mean())))
    return paths


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def parse_hex_color(hex_color: str) -> np.ndarray:
    clean = hex_color.lstrip("#")
    if len(clean) == 3:
        clean = "".join([c * 2 for c in clean])
    rgb = tuple(bytes.fromhex(clean))
    return np.array(rgb, dtype=np.float32)


def process_scene_edges(
    before_img: Image.Image,
    after_img: Image.Image,
    target_width: int = 1080,
    box: Sequence[float] | None = None,
    edge_low: int = 25,
    edge_high: int = 70,
    min_path: float = 12.0,
    keep_background_edges: bool = False,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], int, int]:
    """Resize scenes, compute Canny edge subtraction, and return paths."""
    ow, oh = after_img.size
    w = target_width
    h = round(oh / ow * w / 2) * 2

    before_arr = np.array(before_img.resize((w, h), Image.Resampling.LANCZOS))
    finished_arr = np.array(after_img.resize((w, h), Image.Resampling.LANCZOS))

    mask = np.zeros((h, w), np.uint8)
    if box and len(box) == 4:
        x1, y1, x2, y2 = box
        bx1 = max(0, min(w, round(x1 * w / ow)))
        bx2 = max(0, min(w, round(x2 * w / ow)))
        by1 = max(0, min(h, round(y1 * h / oh)))
        by2 = max(0, min(h, round(y2 * h / oh)))
        mask[by1:by2, bx1:bx2] = 255
    else:
        # Full image mask if no bounding box specified
        mask.fill(255)

    def edges(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0.8)
        return cv2.Canny(gray, edge_low, edge_high, L2gradient=True)

    selected = cv2.bitwise_and(edges(finished_arr), mask)
    if not keep_background_edges:
        # Suppress edges already present in the empty room
        old = cv2.dilate(edges(before_arr), np.ones((3, 3), np.uint8))
        selected[old > 0] = 0

    paths = edge_paths(selected, min_path)
    if not paths:
        # Fallback if edge subtraction is too aggressive: try lower threshold without subtraction
        raw_edges = cv2.bitwise_and(edges(finished_arr), mask)
        paths = edge_paths(raw_edges, min_path)

    return before_arr, finished_arr, paths, w, h


def extract_outline_preview(
    before_path: Path | str,
    after_path: Path | str,
    output_path: Path | str,
    box: Sequence[float] | None = None,
    color: str = "#ad803d",
    line_width: float = 1.2,
    target_width: int = 1080,
) -> Path:
    """Extract and save outline preview image (Sketch Image)."""
    before_img = load_rgb(before_path)
    after_img = load_rgb(after_path)
    before_arr, _, paths, w, h = process_scene_edges(
        before_img, after_img, target_width=target_width, box=box
    )
    col_arr = parse_hex_color(color)
    thickness = max(1, round(line_width))
    ink = np.zeros((h, w), np.uint8)

    for path in paths:
        for a, b in zip(path[:-1], path[1:]):
            cv2.line(ink, tuple(np.rint(a).astype(int)), tuple(np.rint(b).astype(int)), 255, thickness, cv2.LINE_AA)

    alpha = (ink.astype(np.float32) / 255.0)[:, :, None]
    comp = np.clip(before_arr.astype(np.float32) * (1.0 - alpha) + col_arr * alpha, 0, 255).astype(np.uint8)

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(comp).save(out_p, "PNG")
    return out_p


def render_auto_draw_video(
    before_path: Path | str,
    after_path: Path | str,
    output_path: Path | str,
    box: Sequence[float] | None = None,
    draw_seconds: float = 4.5,
    transition_seconds: float = 1.8,
    end_hold: float = 2.0,
    color: str = "#ad803d",
    line_width: float = 1.2,
    target_width: int = 1080,
    fps: int = 30,
    after_tagged_path: Path | str | None = None,
) -> Path:
    """Render frame-by-frame animated line-drawing reveal video via FFmpeg."""
    before_img = load_rgb(before_path)
    after_img = load_rgb(after_path)
    before_arr, finished_arr, paths, w, h = process_scene_edges(
        before_img, after_img, target_width=target_width, box=box
    )

    if not paths:
        raise ValueError("No usable outlines could be extracted for Auto Draw video.")

    tagged_arr: np.ndarray | None = None
    if after_tagged_path and Path(after_tagged_path).is_file():
        tagged_img = load_rgb(after_tagged_path)
        tagged_arr = np.array(tagged_img.resize((w, h), Image.Resampling.LANCZOS)).astype(np.float32)

    segments: list[tuple[np.ndarray, np.ndarray, float]] = []
    for path in paths:
        for a, b in zip(path[:-1], path[1:]):
            length = float(np.linalg.norm(b - a))
            if length > 0:
                segments.append((a, b, length))
    total_length = sum(s[2] for s in segments)

    col_arr = parse_hex_color(color)
    thickness = max(1, round(line_width))
    ink = np.zeros((h, w), np.uint8)

    def stroke(a: np.ndarray, b: np.ndarray):
        cv2.line(ink, tuple(np.rint(a).astype(int)), tuple(np.rint(b).astype(int)), 255, thickness, cv2.LINE_AA)

    def composite(base: np.ndarray, opacity: float = 1.0) -> np.ndarray:
        alpha = (ink.astype(np.float32) / 255.0 * opacity)[:, :, None]
        return np.clip(base * (1.0 - alpha) + col_arr * alpha, 0, 255).astype(np.uint8)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    start = 0.5
    transition_start = start + draw_seconds + 0.3
    duration = transition_start + transition_seconds + end_hold

    command = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
        "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_p),
    ]

    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    ink.fill(0)
    index = 0
    completed = 0.0
    bg = before_arr.astype(np.float32)
    end = finished_arr.astype(np.float32)

    total_frames = math.ceil(duration * fps)
    transition_end = transition_start + transition_seconds
    tag_fade_dur = 0.4
    try:
        for frame_number in range(total_frames):
            t = frame_number / fps
            progress = max(0.0, min(1.0, (t - start) / draw_seconds))
            target = progress * total_length
            while index < len(segments) and completed + segments[index][2] <= target + 1e-5:
                a, b, length = segments[index]
                stroke(a, b)
                completed += length
                index += 1
            if index < len(segments) and target > completed:
                a, b, length = segments[index]
                stroke(a, a + (b - a) * min(1.0, (target - completed) / length))

            if t < transition_end:
                blend = ease((t - transition_start) / transition_seconds)
                frame = composite(bg * (1.0 - blend) + end * blend, 1.0 - blend)
            else:
                if tagged_arr is not None:
                    tag_blend = ease((t - transition_end) / tag_fade_dur)
                    frame = np.clip(end * (1.0 - tag_blend) + tagged_arr * tag_blend, 0, 255).astype(np.uint8)
                else:
                    frame = finished_arr
            process.stdin.write(frame.tobytes())

        process.stdin.close()
        rc = process.wait()
        if rc != 0:
            raise RuntimeError(f"FFmpeg encoding exited with code {rc}")
    except BaseException:
        process.kill()
        process.wait()
        raise

    return out_p

