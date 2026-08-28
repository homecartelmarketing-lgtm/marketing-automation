"""CLI: generate moodboard-reel blended images for the Chandelier Modern table.

For each row in the table, the script pairs every Interior slot with its
corresponding Furniture Item slot and the blend prompt from the Prompt field:

    Interior  + Furniture Item  + Prompt1 -> blended_mb1.jpg
    Interior2 + Furniture Item2 + Prompt2 -> blended_mb2.jpg
    Interior3 + Furniture Item3 + Prompt3 -> blended_mb3.jpg
    Interior4 + Furniture Item4 + Prompt4 -> blended_mb4.jpg

All four pairs are blended concurrently via KIE Nano Banana Pro.  The
blend prompt for each slot is read from the Airtable Prompt1..Prompt4
fields.  The finished images are uploaded to the **Moodboard Blended**
attachment field.

A second *convert* phase then runs on the same record: each of the four
blended images is blended again against the single photo in **Moodboard
Reference Photo**, using the prompt in **Moodboard Prompt**:

    blended_mb1 + Moodboard Reference Photo + Moodboard Prompt -> converted_mb1.jpg
    blended_mb2 + Moodboard Reference Photo + Moodboard Prompt -> converted_mb2.jpg
    blended_mb3 + Moodboard Reference Photo + Moodboard Prompt -> converted_mb3.jpg
    blended_mb4 + Moodboard Reference Photo + Moodboard Prompt -> converted_mb4.jpg

The four results are uploaded to the **Converted Moodboard** attachment
field, and only then is the record marked Complete.

Usage::

    python generate_moodboard_reel.py                  # dry run (default)
    python generate_moodboard_reel.py --execute         # live run
    python generate_moodboard_reel.py --execute --limit 5
    python generate_moodboard_reel.py --execute --record-id recXXXXXXXXXXXXXX
    python generate_moodboard_reel.py --execute --convert-only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from content_automation.assets import MAX_PROMPT_LENGTH, AssetCatalog
from content_automation.config import (
    MOODBOARD_REEL_CATEGORIES,
    TABLES,
    load_settings,
)
from content_automation.errors import AutomationError
from content_automation.fields import furniture_field, interior_field
from content_automation.http import request_with_retry, response_error
from content_automation.kie_client import KieClient
from content_automation.models import LocalImage

DEFAULT_TABLE_CODE = "chandelier_modern"
SLOT_COUNT = 4
BLENDED_FIELD = "Moodboard Blended"
CONVERTED_FIELD = "Converted Moodboard"
REFERENCE_FIELD = "Moodboard Reference Photo"
MOODBOARD_PROMPT_FIELD = "Moodboard Prompt"
ASPECT_RATIO = "9:16"
BLENDED_PREFIX = "blended_mb"
CONVERTED_PREFIX = "converted_mb"
REEL_FIELD = "REEL - Moodboard Reel"
REEL_FILENAME = "moodboard_reel.mp4"
COLLAGE_FILENAME = "collage_mb.jpg"
COLLAGE_COLS, COLLAGE_ROWS = 2, 2
MUSIC_FIELD = "Music Generated"
OUTRO_FIELD = "Outro"
OUTRO_SECONDS = 3
FADE_SECONDS = 1
AUDIO_BITRATE = "192k"
SLIDE_SECONDS = 2
VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920
VIDEO_FPS = 30
# Airtable's uploadAttachment endpoint caps files at roughly 5 MB.
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MODEL = "nano-banana-2"
# Fallback prompt used when a record's Moodboard Prompt field is empty.
# Bare filename so AssetCatalog's rglob search locates it under any asset root,
# with or without CONTENT_AUTOMATION_ASSET_ROOT set.
PROMPT_ASSET = "converted_moodboard.json"



def prompt_field(slot: int) -> str:
    """'Prompt1' for slot 0, 'Prompt2' for slot 1, etc."""
    return f"Prompt{slot + 1}"


# ---------------------------------------------------------------------------
# Lightweight Airtable helpers (no dependency on the full AirtableClient)
# ---------------------------------------------------------------------------

API_BASE = "https://api.airtable.com/v0"
CONTENT_BASE = "https://content.airtable.com/v0"


def _airtable_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _list_records(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    fields: list[str],
    *,
    formula: str = "",
) -> list[dict[str, Any]]:
    url = f"{API_BASE}/{base_id}/{table_id}"
    records: list[dict[str, Any]] = []
    offset = ""
    while True:
        params: list[tuple[str, str]] = [("pageSize", "100")]
        params.extend(("fields[]", f) for f in fields)
        if formula:
            params.append(("filterByFormula", formula))
        if offset:
            params.append(("offset", offset))
        resp = request_with_retry(
            session, "GET", url, headers=_airtable_headers(token), params=params
        )
        if not resp.ok:
            raise response_error(resp, "List Airtable records")
        payload = resp.json()
        records.extend(payload.get("records", []))
        offset = str(payload.get("offset") or "")
        if not offset:
            return records


def _ensure_field(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    field_name: str,
    field_type: str,
) -> None:
    """Create a field only if it doesn't exist yet."""
    schema_url = f"{API_BASE}/meta/bases/{base_id}/tables"
    resp = request_with_retry(
        session, "GET", schema_url, headers=_airtable_headers(token)
    )
    if not resp.ok:
        raise response_error(resp, "Airtable schema lookup")
    for table in resp.json().get("tables", []):
        if table.get("id") == table_id:
            existing = {f["name"] for f in table.get("fields", [])}
            if field_name in existing:
                return
            break
    else:
        raise AutomationError(f"Table {table_id} not found in base {base_id}")

    create_url = f"{API_BASE}/meta/bases/{base_id}/tables/{table_id}/fields"
    resp = request_with_retry(
        session,
        "POST",
        create_url,
        headers=_airtable_headers(token),
        json={"name": field_name, "type": field_type},
    )
    if not resp.ok:
        raise response_error(resp, f"Create field {field_name}")
    print(f"[OK] Created Airtable field '{field_name}'")


def _clear_attachment_field(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    record_id: str,
    field_name: str,
) -> None:
    url = f"{API_BASE}/{base_id}/{table_id}/{record_id}"
    resp = request_with_retry(
        session,
        "PATCH",
        url,
        headers=_airtable_headers(token),
        json={"fields": {field_name: []}},
    )
    if not resp.ok:
        raise response_error(resp, f"Clear {field_name}")


def _upload_attachment(
    session: requests.Session,
    token: str,
    base_id: str,
    record_id: str,
    field_name: str,
    image: LocalImage,
) -> None:
    import base64
    from urllib.parse import quote

    url = (
        f"{CONTENT_BASE}/{base_id}/{record_id}/"
        f"{quote(field_name, safe='')}/uploadAttachment"
    )
    payload = {
        "contentType": image.content_type or "image/jpeg",
        "file": base64.b64encode(image.path.read_bytes()).decode("ascii"),
        "filename": image.filename,
    }
    resp = request_with_retry(
        session, "POST", url, headers=_airtable_headers(token), json=payload
    )
    if not resp.ok:
        raise response_error(resp, f"Upload {image.filename} to {field_name}")


def _download_attachment_url(
    session: requests.Session,
    url: str,
    destination: Path,
) -> LocalImage:
    resp = request_with_retry(session, "GET", url)
    if not resp.ok:
        raise response_error(resp, f"Download attachment from Airtable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(resp.content)
    ct = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0]
    return LocalImage(destination, destination.name, ct)


def _update_status(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    record_id: str,
    status: str,
) -> None:
    """Set the Status field on a record (e.g. 'Processing', 'Complete')."""
    url = f"{API_BASE}/{base_id}/{table_id}/{record_id}"
    resp = request_with_retry(
        session,
        "PATCH",
        url,
        headers=_airtable_headers(token),
        json={"fields": {"Status": status}},
    )
    if not resp.ok:
        raise response_error(resp, f"Set Status to '{status}'")


# ---------------------------------------------------------------------------
# Slot data
# ---------------------------------------------------------------------------


@dataclass
class SlotPair:
    """One Interior + Furniture Item + Prompt triple to blend."""

    slot: int
    interior_url: str
    furniture_url: str
    prompt: str
    output_filename: str  # e.g. "blended_mb1.jpg"


def extract_slot_pairs(fields: dict[str, Any]) -> list[SlotPair]:
    """Return only the slots where Interior, Furniture Item, and Prompt all exist."""
    pairs: list[SlotPair] = []
    for slot in range(SLOT_COUNT):
        interior_attachments = fields.get(interior_field(slot)) or []
        furniture_attachments = fields.get(furniture_field(slot)) or []
        prompt_text = str(fields.get(prompt_field(slot)) or "").strip()
        if not interior_attachments or not furniture_attachments or not prompt_text:
            continue
        interior_url = str(interior_attachments[0].get("url") or "")
        furniture_url = str(furniture_attachments[0].get("url") or "")
        if not interior_url or not furniture_url:
            continue
        pairs.append(
            SlotPair(
                slot=slot,
                interior_url=interior_url,
                furniture_url=furniture_url,
                prompt=prompt_text,
                output_filename=f"blended_mb{slot + 1}.jpg",
            )
        )
    return pairs


# ---------------------------------------------------------------------------
# Blend one slot
# ---------------------------------------------------------------------------


def blend_one_slot(
    pair: SlotPair,
    kie: KieClient,
    workdir: Path,
    session: requests.Session,
) -> LocalImage:
    """Download both images, call KIE with the Airtable prompt, return result."""
    int_path = workdir / f"interior_{pair.slot}.jpg"
    fur_path = workdir / f"furniture_{pair.slot}.jpg"

    # Download source images to local disk
    interior = _download_attachment_url(session, pair.interior_url, int_path)
    furniture = _download_attachment_url(session, pair.furniture_url, fur_path)

    # Upload both to KIE's temporary hosting so they have public URLs
    interior_public = kie.upload(interior)
    furniture_public = kie.upload(furniture)

    # Call KIE Nano Banana Pro to blend using the prompt from Airtable
    result_url = kie.generate(
        pair.prompt,
        [interior_public, furniture_public],
        aspect_ratio=ASPECT_RATIO,
        resolution="1K",
        output_format="png",
    )

    # Download and save as JPEG
    destination = workdir / pair.output_filename
    return kie.download_jpeg(result_url, destination)


# ---------------------------------------------------------------------------
# Convert phase: re-blend each blended_mb* against the reference photo
# ---------------------------------------------------------------------------


@dataclass
class ConvertJob:
    """One blended image to re-blend against the moodboard reference photo."""

    slot: int
    blended: LocalImage
    output_filename: str  # e.g. "converted_mb1.jpg"


def _slot_from_filename(filename: str, prefix: str, fallback: int) -> int:
    """Map 'blended_mb3.jpg' with prefix 'blended_mb' -> slot 2.

    Falls back to the attachment's position when the filename doesn't carry a
    slot number.
    """
    match = re.search(rf"{re.escape(prefix)}(\d+)", filename or "", re.IGNORECASE)
    if match:
        return int(match.group(1)) - 1
    return fallback


def images_from_field(
    attachments: list[dict[str, Any]],
    session: requests.Session,
    workdir: Path,
    prefix: str,
) -> dict[int, LocalImage]:
    """Download an attachment field to disk, keyed by slot index.

    `prefix` is the filename stem the slot number follows, e.g. 'blended_mb'
    for the Moodboard Blended field or 'converted_mb' for Converted Moodboard.
    """
    images: dict[int, LocalImage] = {}
    for position, attachment in enumerate(attachments):
        url = str(attachment.get("url") or "")
        if not url:
            continue
        filename = str(attachment.get("filename") or "")
        slot = _slot_from_filename(filename, prefix, position)
        destination = workdir / f"{prefix}{slot + 1}.jpg"
        images[slot] = _download_attachment_url(session, url, destination)
    return images


def resolve_prompt(fields: dict[str, Any], assets: AssetCatalog) -> str:
    """Airtable's Moodboard Prompt if set, else the bundled prompt asset.

    A JSON prompt is minified first, exactly as AssetCatalog.read_prompt does,
    so that pretty-printed whitespace in the Airtable field doesn't push real
    content past MAX_PROMPT_LENGTH and get truncated away.
    """
    prompt = str(fields.get(MOODBOARD_PROMPT_FIELD) or "").strip()
    if not prompt:
        return assets.read_prompt(PROMPT_ASSET)
    try:
        prompt = json.dumps(json.loads(prompt), ensure_ascii=False)
    except json.JSONDecodeError:
        pass  # Plain-text prompt; use it as written.
    return prompt[:MAX_PROMPT_LENGTH]


def convert_one_slot(
    job: ConvertJob,
    reference_public: str,
    prompt: str,
    kie: KieClient,
    workdir: Path,
) -> LocalImage:
    """Blend one blended_mb* image with the reference photo via Nano Banana Pro."""
    blended_public = kie.upload(job.blended)
    # Reference first: it is the layout/typography template the output must
    # match, so it carries more weight as the leading image. The blended
    # interior follows as the source of the actual materials.
    result_url = kie.generate(
        prompt,
        [reference_public, blended_public],
        aspect_ratio=ASPECT_RATIO,
        resolution="1K",
        output_format="png",
    )
    destination = workdir / job.output_filename
    return kie.download_jpeg(result_url, destination)


def convert_record(
    record_id: str,
    fields: dict[str, Any],
    blended_images: dict[int, LocalImage],
    *,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    kie: KieClient,
    assets: AssetCatalog,
    workdir: Path,
) -> dict[int, LocalImage] | None:
    """Re-blend every blended image against the reference photo and upload.

    Returns the converted images keyed by slot, or None if the phase failed.
    """
    reference_attachments = fields.get(REFERENCE_FIELD) or []
    prompt = resolve_prompt(fields, assets)

    if not reference_attachments:
        print(f"  [SKIP] {record_id}: no {REFERENCE_FIELD} attachment; convert phase skipped")
        return None

    reference_url = str(reference_attachments[0].get("url") or "")
    if not reference_url:
        print(f"  [SKIP] {record_id}: {REFERENCE_FIELD} attachment has no URL")
        return None

    print(f"  [INFO] {record_id}: converting {len(blended_images)} blended image(s)")

    # Download the reference photo once and upload it to KIE once -- the same
    # public URL is reused by all four conversions.
    reference = _download_attachment_url(
        session, reference_url, workdir / "moodboard_reference.jpg"
    )
    reference_public = kie.upload(reference)

    jobs = [
        ConvertJob(
            slot=slot,
            blended=blended_images[slot],
            output_filename=f"converted_mb{slot + 1}.jpg",
        )
        for slot in sorted(blended_images)
    ]

    results: dict[int, LocalImage] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=SLOT_COUNT) as pool:
        futures = {
            pool.submit(
                convert_one_slot, job, reference_public, prompt, kie, workdir
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                results[job.slot] = future.result()
                print(f"    [OK] slot {job.slot + 1} -> {job.output_filename}")
            except Exception as err:
                errors.append(f"slot {job.slot + 1}: {err}")
                print(f"    [ERROR] convert slot {job.slot + 1}: {err}")

    if not results:
        print(f"  [ERROR] {record_id}: all conversions failed")
        return None

    try:
        _clear_attachment_field(
            session, token, base_id, table_id, record_id, CONVERTED_FIELD
        )
    except Exception as err:
        print(f"  [WARN] Could not clear {CONVERTED_FIELD}: {err}")

    for slot in sorted(results):
        image = results[slot]
        _upload_attachment(session, token, base_id, record_id, CONVERTED_FIELD, image)
        print(f"    [OK] Uploaded {image.filename} -> {CONVERTED_FIELD}")

    if errors:
        print(f"  [WARN] {record_id}: {len(errors)} conversion(s) failed: {'; '.join(errors)}")
        return None

    print(f"  [OK] {record_id}: all {len(results)} converted images uploaded")
    return results


# ---------------------------------------------------------------------------
# Reel phase: stitch the eight stills into one MP4 slideshow
# ---------------------------------------------------------------------------


COLLAGE_CELLS = COLLAGE_COLS * COLLAGE_ROWS


def _fit_cover(source_path: Path, width: int, height: int):
    """Scale an image to cover a box, then centre-crop the overflow.

    Nothing is stretched and nothing is letterboxed - the aspect difference is
    absorbed by cropping the long edge.
    """
    from PIL import Image

    with Image.open(source_path) as source:
        image = source.convert("RGB")
        scale = max(width / image.width, height / image.height)
        resized = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.LANCZOS,
        )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def build_collage(
    converted: dict[int, LocalImage],
    workdir: Path,
) -> LocalImage | None:
    """Tile the four converted boards into one 2x2 grid at video resolution.

    The canvas is 1080x1920 (9:16) and, because the grid is 2x2, every cell is
    540x960 - also exactly 9:16. Each board is scaled to cover its cell and
    centre-cropped, so nothing is stretched or letterboxed.

    Returns None when there aren't exactly four boards to tile; the caller then
    simply starts the reel without an intro.
    """
    from PIL import Image

    slots = sorted(converted)
    if len(slots) != COLLAGE_CELLS:
        return None

    cell_w = VIDEO_WIDTH // COLLAGE_COLS
    cell_h = VIDEO_HEIGHT // COLLAGE_ROWS
    canvas = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))

    for index, slot in enumerate(slots):
        cell = _fit_cover(converted[slot].path, cell_w, cell_h)
        column, row = index % COLLAGE_COLS, index // COLLAGE_COLS
        canvas.paste(cell, (column * cell_w, row * cell_h))

    destination = workdir / COLLAGE_FILENAME
    canvas.save(destination, format="JPEG", quality=95, optimize=True)
    return LocalImage(destination, COLLAGE_FILENAME, "image/jpeg")


def reel_sequence(
    blended: dict[int, LocalImage],
    converted: dict[int, LocalImage],
    collage: LocalImage | None = None,
) -> list[LocalImage]:
    """Optional collage intro, then converted/blended for each slot in order.

    collage, converted_mb1, blended_mb1, converted_mb2, blended_mb2, ...
    Slots missing from either side are skipped so a partial record still
    produces a coherent reel.
    """
    sequence: list[LocalImage] = [collage] if collage else []
    for slot in sorted(set(blended) & set(converted)):
        sequence.append(converted[slot])
        sequence.append(blended[slot])
    return sequence


def _normalize_slides(sequence: list[LocalImage], workdir: Path) -> list[Path]:
    """Render every slide to an identically-sized JPEG for the concat demuxer.

    The concat demuxer needs uniform stream parameters: feed it images of
    differing dimensions and it silently drops the odd ones out. The collage is
    1080x1920 while the boards are 768x1376, so each slide is re-rendered at the
    final video size up front rather than relying on an ffmpeg scale filter.
    """
    paths: list[Path] = []
    for index, image in enumerate(sequence, start=1):
        destination = workdir / f"slide_{index:02d}.jpg"
        frame = _fit_cover(image.path, VIDEO_WIDTH, VIDEO_HEIGHT)
        frame.save(destination, format="JPEG", quality=95, optimize=True)
        paths.append(destination)
    return paths


def _write_concat_file(slides: list[tuple[Path, int]], destination: Path) -> None:
    """Write an ffmpeg concat demuxer list next to the images it references.

    Each entry carries its own duration so the outro can run longer than the
    regular slides. Only bare filenames are written - ffmpeg resolves them
    relative to this file's own directory, which sidesteps Windows backslash
    escaping.
    """
    lines: list[str] = []
    for path, seconds in slides:
        lines.append(f"file '{path.name}'")
        lines.append(f"duration {seconds}")
    # The concat demuxer drops the final entry's duration, so the last image is
    # repeated without one to make it hold for its full slide.
    lines.append(f"file '{slides[-1][0].name}'")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_reel(
    sequence: list[LocalImage],
    workdir: Path,
    outro: LocalImage | None = None,
    music: LocalImage | None = None,
) -> LocalImage:
    """Stitch a prepared slide sequence into one MP4 via the bundled ffmpeg.

    An optional outro card is appended behind a fade through black, and an
    optional music track is mixed underneath and faded out over the outro.
    """
    import imageio_ffmpeg

    if not sequence:
        raise AutomationError("No slides to build a reel from")

    # The outro is normalized alongside the slides so every concat input shares
    # the same dimensions - the demuxer silently drops mismatched frames.
    frames = sequence + ([outro] if outro else [])
    paths = _normalize_slides(frames, workdir)

    slideshow_seconds = len(sequence) * SLIDE_SECONDS
    slides = [(path, SLIDE_SECONDS) for path in paths[: len(sequence)]]
    if outro:
        slides.append((paths[-1], OUTRO_SECONDS))
    total_seconds = slideshow_seconds + (OUTRO_SECONDS if outro else 0)

    concat_path = workdir / "reel_concat.txt"
    _write_concat_file(slides, concat_path)
    destination = workdir / REEL_FILENAME

    # Every slide is already VIDEO_WIDTH x VIDEO_HEIGHT, so no scaling here.
    video_filter = f"fps={VIDEO_FPS},format=yuv420p"
    if outro:
        # Two plain fades on one timeline rather than xfade: darken the last
        # slide to black, then bring the outro up out of black.
        #
        # Each fade MUST be gated with `enable`. On its own, fade=out holds
        # every later frame black and fade=in holds every earlier frame black,
        # so chaining them ungated blanks the entire video. The commas inside
        # between() are escaped because commas separate filters in a graph.
        fade_out_at = slideshow_seconds - FADE_SECONDS
        fade_in_at = slideshow_seconds
        fade_in_end = slideshow_seconds + FADE_SECONDS
        video_filter += (
            f",fade=t=out:st={fade_out_at}:d={FADE_SECONDS}"
            f":enable=between(t\\,{fade_out_at}\\,{fade_in_at})"
            f",fade=t=in:st={fade_in_at}:d={FADE_SECONDS}"
            f":enable=between(t\\,{fade_in_at}\\,{fade_in_end})"
        )

    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_path.name,
    ]
    if music:
        # The track is usually shorter than the reel, so loop it to fill.
        command += ["-stream_loop", "-1", "-i", music.path.name]

    command += ["-vf", video_filter]
    if music:
        # Fade the music out across the outro, or across the final second when
        # there is no outro to fade under.
        fade_start = slideshow_seconds if outro else total_seconds - FADE_SECONDS
        fade_length = OUTRO_SECONDS if outro else FADE_SECONDS
        command += [
            "-af", f"afade=t=out:st={fade_start}:d={fade_length}",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
            "-map", "0:v:0",
            "-map", "1:a:0",
        ]

    command += [
        "-t", str(total_seconds),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        destination.name,
    ]
    result = subprocess.run(
        command, cwd=workdir, capture_output=True, text=True
    )
    if result.returncode != 0 or not destination.is_file():
        raise AutomationError(
            f"ffmpeg failed to build the reel: {result.stderr.strip() or result.returncode}"
        )

    return LocalImage(destination, REEL_FILENAME, "video/mp4")


def _download_optional(
    fields: dict[str, Any],
    field_name: str,
    session: requests.Session,
    destination: Path,
    record_id: str,
) -> LocalImage | None:
    """Download the first attachment of an optional field, or return None.

    Used for the outro card and the music track - both are nice-to-have, so a
    missing one is reported rather than treated as a failure.
    """
    attachments = fields.get(field_name) or []
    url = str(attachments[0].get("url") or "") if attachments else ""
    if not url:
        print(f"    [INFO] no {field_name}: skipping")
        return None
    try:
        image = _download_attachment_url(session, url, destination)
    except Exception as err:
        print(f"    [WARN] could not download {field_name}: {err}")
        return None
    print(f"    [OK] {field_name}: {attachments[0].get('filename')}")
    return image


def build_and_upload_reel(
    record_id: str,
    blended: dict[int, LocalImage],
    converted: dict[int, LocalImage],
    *,
    fields: dict[str, Any],
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    workdir: Path,
) -> bool:
    """Build the slideshow and attach it to the REEL field."""
    try:
        collage = build_collage(converted, workdir)
    except Exception as err:
        print(f"    [WARN] collage intro skipped: {err}")
        collage = None
    if collage:
        print(f"    [OK] {collage.filename} ({COLLAGE_COLS}x{COLLAGE_ROWS} intro)")
    else:
        print(
            f"    [INFO] no collage intro: needs exactly {COLLAGE_CELLS} "
            f"{CONVERTED_FIELD} images"
        )

    sequence = reel_sequence(blended, converted, collage)
    if not sequence:
        print(f"  [ERROR] {record_id}: no blended/converted pairs to build a reel from")
        return False

    outro = _download_optional(
        fields, OUTRO_FIELD, session, workdir / "outro.jpg", record_id
    )
    music = _download_optional(
        fields, MUSIC_FIELD, session, workdir / "reel_music.mp3", record_id
    )

    total = len(sequence) * SLIDE_SECONDS + (OUTRO_SECONDS if outro else 0)
    print(
        f"  [INFO] {record_id}: building {len(sequence)}-slide reel"
        f"{' + outro' if outro else ''}"
        f"{' + music' if music else ''} ({total}s @ {VIDEO_WIDTH}x{VIDEO_HEIGHT})"
    )

    try:
        reel = build_reel(sequence, workdir, outro, music)
    except Exception as err:
        print(f"    [ERROR] reel build failed: {err}")
        return False

    size = reel.path.stat().st_size
    print(f"    [OK] {reel.filename} ({size / 1024 / 1024:.2f} MB)")
    if size > MAX_ATTACHMENT_BYTES:
        print(
            f"    [ERROR] {reel.filename} is {size / 1024 / 1024:.2f} MB, over Airtable's "
            f"{MAX_ATTACHMENT_BYTES / 1024 / 1024:.0f} MB attachment limit. "
            "Raise -crf in build_reel() to shrink it."
        )
        return False

    try:
        _clear_attachment_field(session, token, base_id, table_id, record_id, REEL_FIELD)
    except Exception as err:
        print(f"  [WARN] Could not clear {REEL_FIELD}: {err}")

    _upload_attachment(session, token, base_id, record_id, REEL_FIELD, reel)
    print(f"    [OK] Uploaded {reel.filename} -> {REEL_FIELD}")
    return True


# ---------------------------------------------------------------------------
# Process one record
# ---------------------------------------------------------------------------


def process_record(
    record_id: str,
    fields: dict[str, Any],
    *,
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    kie: KieClient,
    assets: AssetCatalog,
    workdir_root: Path,
    execute: bool,
    convert_only: bool = False,
    reel_only: bool = False,
) -> bool:
    existing_blended = fields.get(BLENDED_FIELD) or []
    existing_converted = fields.get(CONVERTED_FIELD) or []
    pairs = [] if (convert_only or reel_only) else extract_slot_pairs(fields)

    if reel_only and not (existing_blended and existing_converted):
        print(
            f"  [SKIP] {record_id}: needs both {BLENDED_FIELD} and "
            f"{CONVERTED_FIELD} to build a reel"
        )
        return True

    if not pairs and not existing_blended:
        reason = (
            f"no {BLENDED_FIELD} attachments to convert"
            if convert_only
            else "no complete Interior+Furniture+Prompt triples found"
        )
        print(f"  [SKIP] {record_id}: {reason}")
        return True

    if pairs:
        slot_labels = ", ".join(f"slot {p.slot + 1}" for p in pairs)
        print(f"  [INFO] {record_id}: blending {len(pairs)} pair(s) ({slot_labels})")

    if not execute:
        for pair in pairs:
            prompt_preview = pair.prompt[:60] + "..." if len(pair.prompt) > 60 else pair.prompt
            print(f"    [DRY] {interior_field(pair.slot)} + {furniture_field(pair.slot)} + {prompt_field(pair.slot)} -> {pair.output_filename}")
            print(f"           Prompt: {prompt_preview.encode('ascii', 'replace').decode('ascii')}")
        _preview_convert(fields, pairs, existing_blended, assets)
        _preview_reel(pairs, existing_blended, fields)
        return True

    # Mark as Processing
    try:
        _update_status(session, token, base_id, table_id, record_id, "Processing")
        print(f"  [STATUS] {record_id} -> Processing")
    except Exception as err:
        print(f"  [WARN] Could not set Status to Processing: {err}")

    workdir = workdir_root / record_id
    workdir.mkdir(parents=True, exist_ok=True)

    # -- Phase 1: blend Interior + Furniture into blended_mb1..4 -------------
    results: dict[int, LocalImage] = {}
    errors: list[str] = []

    if pairs:
        with ThreadPoolExecutor(max_workers=SLOT_COUNT) as pool:
            futures = {
                pool.submit(blend_one_slot, pair, kie, workdir, session): pair
                for pair in pairs
            }
            for future in as_completed(futures):
                pair = futures[future]
                try:
                    results[pair.slot] = future.result()
                    print(f"    [OK] slot {pair.slot + 1} -> {pair.output_filename}")
                except Exception as err:
                    errors.append(f"slot {pair.slot + 1}: {err}")
                    print(f"    [ERROR] slot {pair.slot + 1}: {err}")

        if not results:
            print(f"  [ERROR] {record_id}: all blends failed")
            _set_failed(session, token, base_id, table_id, record_id)
            return False

        # Upload blended images to the Moodboard Blended field
        try:
            _clear_attachment_field(session, token, base_id, table_id, record_id, BLENDED_FIELD)
        except Exception as err:
            print(f"  [WARN] Could not clear {BLENDED_FIELD}: {err}")

        for slot in sorted(results):
            image = results[slot]
            _upload_attachment(session, token, base_id, record_id, BLENDED_FIELD, image)
            print(f"    [OK] Uploaded {image.filename} -> {BLENDED_FIELD}")

        if errors:
            print(f"  [WARN] {record_id}: {len(errors)} slot(s) failed: {'; '.join(errors)}")
            _set_failed(session, token, base_id, table_id, record_id)
            return False

        print(f"  [OK] {record_id}: all {len(results)} blended images uploaded")
    else:
        # Resuming: pull the already-blended images back down from Airtable
        results = images_from_field(existing_blended, session, workdir, BLENDED_PREFIX)
        if not results:
            print(f"  [ERROR] {record_id}: could not download {BLENDED_FIELD} attachments")
            _set_failed(session, token, base_id, table_id, record_id)
            return False
        print(f"  [INFO] {record_id}: reusing {len(results)} existing {BLENDED_FIELD} image(s)")

    # -- Phase 2: convert each blended image against the reference photo -----
    if reel_only:
        converted = images_from_field(
            existing_converted, session, workdir, CONVERTED_PREFIX
        )
        if not converted:
            print(f"  [ERROR] {record_id}: could not download {CONVERTED_FIELD} attachments")
            _set_failed(session, token, base_id, table_id, record_id)
            return False
        print(
            f"  [INFO] {record_id}: reusing {len(converted)} existing "
            f"{CONVERTED_FIELD} image(s)"
        )
    else:
        converted = convert_record(
            record_id,
            fields,
            results,
            session=session,
            token=token,
            base_id=base_id,
            table_id=table_id,
            kie=kie,
            assets=assets,
            workdir=workdir,
        )
        if converted is None:
            _set_failed(session, token, base_id, table_id, record_id)
            return False

    # -- Phase 3: stitch the stills into one MP4 slideshow -------------------
    if not build_and_upload_reel(
        record_id,
        results,
        converted,
        fields=fields,
        session=session,
        token=token,
        base_id=base_id,
        table_id=table_id,
        workdir=workdir,
    ):
        _set_failed(session, token, base_id, table_id, record_id)
        return False

    # Mark as Complete
    try:
        _update_status(session, token, base_id, table_id, record_id, "Complete")
        print(f"  [STATUS] {record_id} -> Complete")
    except Exception as err:
        print(f"  [WARN] Could not set Status to Complete: {err}")

    return True


def _set_failed(
    session: requests.Session,
    token: str,
    base_id: str,
    table_id: str,
    record_id: str,
) -> None:
    try:
        _update_status(session, token, base_id, table_id, record_id, "Failed")
    except Exception:
        pass


def _preview_convert(
    fields: dict[str, Any],
    pairs: list[SlotPair],
    existing_blended: list[dict[str, Any]],
    assets: AssetCatalog,
) -> None:
    """Dry-run summary of what the convert phase would do."""
    reference_attachments = fields.get(REFERENCE_FIELD) or []

    if not reference_attachments:
        print(f"    [DRY] convert phase would be skipped: no {REFERENCE_FIELD}")
        return

    prompt = resolve_prompt(fields, assets)
    source = (
        MOODBOARD_PROMPT_FIELD
        if str(fields.get(MOODBOARD_PROMPT_FIELD) or "").strip()
        else PROMPT_ASSET
    )

    slots = [p.slot for p in pairs] or [
        _slot_from_filename(str(a.get("filename") or ""), BLENDED_PREFIX, i)
        for i, a in enumerate(existing_blended)
    ]
    for slot in sorted(slots):
        print(
            f"    [DRY] blended_mb{slot + 1}.jpg + {REFERENCE_FIELD} + "
            f"prompt -> converted_mb{slot + 1}.jpg"
        )
    preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
    print(f"           Prompt ({len(prompt)} chars from {source}):")
    print(f"           {preview.encode('ascii', 'replace').decode('ascii')}")


def _preview_reel(
    pairs: list[SlotPair],
    existing_blended: list[dict[str, Any]],
    fields: dict[str, Any],
) -> None:
    """Dry-run summary of the slideshow the reel phase would build."""
    slots = [p.slot for p in pairs] or [
        _slot_from_filename(str(a.get("filename") or ""), BLENDED_PREFIX, i)
        for i, a in enumerate(existing_blended)
    ]
    slots = sorted(set(slots))
    if not slots:
        return

    outro = (fields.get(OUTRO_FIELD) or [None])[0]
    music = (fields.get(MUSIC_FIELD) or [None])[0]

    # The collage intro only exists when all four boards are present.
    has_collage = len(slots) == COLLAGE_CELLS
    slides = len(slots) * 2 + (1 if has_collage else 0)
    total = slides * SLIDE_SECONDS + (OUTRO_SECONDS if outro else 0)
    print(
        f"    [DRY] reel: {slides} slides"
        f"{' + outro' if outro else ''} = {total}s "
        f"@ {VIDEO_WIDTH}x{VIDEO_HEIGHT} -> {REEL_FIELD}"
    )
    start = 0
    if has_collage:
        print(
            f"           {start:>2}-{start + SLIDE_SECONDS:>2}s  {COLLAGE_FILENAME}"
            f"  ({COLLAGE_COLS}x{COLLAGE_ROWS} of {CONVERTED_PREFIX}1..{COLLAGE_CELLS})"
        )
        start += SLIDE_SECONDS
    for slot in slots:
        for prefix in (CONVERTED_PREFIX, BLENDED_PREFIX):
            print(f"           {start:>2}-{start + SLIDE_SECONDS:>2}s  {prefix}{slot + 1}.jpg")
            start += SLIDE_SECONDS
    if outro:
        print(
            f"           {start:>2}-{start + OUTRO_SECONDS:>2}s  "
            f"{outro.get('filename')}  (fade through black, {FADE_SECONDS}s)"
        )
        start += OUTRO_SECONDS
    if music:
        fade_start = total - (OUTRO_SECONDS if outro else FADE_SECONDS)
        print(
            f"           music: {music.get('filename')}, "
            f"fades out {fade_start}-{total}s"
        )
    else:
        print(f"           music: none ({MUSIC_FIELD} empty) - silent reel")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate moodboard-reel blended images for a reel table"
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=MOODBOARD_REEL_CATEGORIES,
        default=DEFAULT_TABLE_CODE,
        help=f"Moodboard reel table to process (default: {DEFAULT_TABLE_CODE})",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually call AI providers and write to Airtable (default: dry run)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N records",
    )
    parser.add_argument(
        "--record-id",
        action="append",
        default=[],
        help="Process only this record (repeatable)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help=(
            "Skip records that already have a REEL - Moodboard Reel video, and "
            "resume partially-finished records from their furthest completed "
            "phase (default: true)"
        ),
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="Re-generate even if the output fields already have content",
    )
    parser.add_argument(
        "--model",
        default=MODEL,
        help=(
            f"KIE model to use for both phases (default: {MODEL}). "
            "Falls back to nano-banana-pro if your API key is not authorized "
            "for the default."
        ),
    )
    parser.add_argument(
        "--convert-only",
        action="store_true",
        help=(
            "Skip the blend phase and only convert the existing Moodboard "
            "Blended attachments into Converted Moodboard"
        ),
    )
    parser.add_argument(
        "--reel-only",
        action="store_true",
        help=(
            "Skip the blend and convert phases and only rebuild the MP4 reel "
            "from the existing Moodboard Blended and Converted Moodboard "
            "attachments (makes no AI calls)"
        ),
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    settings.require({"airtable"})

    table = TABLES[args.category]
    table_id = table.table_id
    base_id = settings.airtable_base_id
    token = settings.airtable_token

    mode = "EXECUTE" if args.execute else "DRY RUN"
    if args.reel_only:
        phase = "reel only"
    elif args.convert_only:
        phase = "convert + reel"
    else:
        phase = "blend + convert + reel"
    print(f"[{mode}] Moodboard Reel Blender -- {table.label}  ({phase})")
    print(f"  Table: {base_id} / {table_id}")
    print(f"  Blended field: {BLENDED_FIELD}")
    print(f"  Converted field: {CONVERTED_FIELD}")
    print(f"  Reel field: {REEL_FIELD}")
    print(f"  Model: {args.model}")
    print(f"  Aspect ratio: {ASPECT_RATIO}")
    print(
        f"  Reel: {SLIDE_SECONDS}s/slide @ {VIDEO_WIDTH}x{VIDEO_HEIGHT} "
        f"{VIDEO_FPS}fps (converted then blended, per slot)"
    )
    print(f"  Prompts from: Prompt1..Prompt4 fields, then {MOODBOARD_PROMPT_FIELD}")
    print(f"  Prompt fallback: {PROMPT_ASSET}")
    print()

    session = requests.Session()

    # Ensure the destination fields exist
    if args.execute:
        settings.require({"kie"})
        _ensure_field(session, token, base_id, table_id, BLENDED_FIELD, "multipleAttachments")
        _ensure_field(session, token, base_id, table_id, CONVERTED_FIELD, "multipleAttachments")
        _ensure_field(session, token, base_id, table_id, REEL_FIELD, "multipleAttachments")

    # Build provider clients
    kie = KieClient(
        settings.kie_api_key,
        settings.kie_api_base,
        settings.kie_upload_base,
        settings.callback_url,
        model=args.model,
    )
    assets = AssetCatalog(settings.workspace)

    # Fetch records from Airtable
    needed_fields = [
        BLENDED_FIELD,
        CONVERTED_FIELD,
        REEL_FIELD,
        REFERENCE_FIELD,
        MOODBOARD_PROMPT_FIELD,
        MUSIC_FIELD,
        OUTRO_FIELD,
    ]
    for slot in range(SLOT_COUNT):
        needed_fields.extend([
            interior_field(slot),
            furniture_field(slot),
            prompt_field(slot),
        ])

    records = _list_records(session, token, base_id, table_id, needed_fields)
    print(f"[INFO] Found {len(records)} record(s) in {table.label}")

    # Filter to specific record IDs if requested
    if args.record_id:
        requested = set(args.record_id)
        records = [r for r in records if r["id"] in requested]
        if not records:
            print(f"[WARN] None of the requested record IDs were found")
            return 1

    # Convert-only runs need existing blended attachments to work from
    if args.convert_only:
        original = len(records)
        records = [r for r in records if r.get("fields", {}).get(BLENDED_FIELD)]
        skipped = original - len(records)
        if skipped:
            print(f"[INFO] Skipping {skipped} record(s) with no {BLENDED_FIELD} to convert")

    # Reel-only runs need both image fields already populated
    if args.reel_only:
        original = len(records)
        records = [
            r for r in records
            if r.get("fields", {}).get(BLENDED_FIELD)
            and r.get("fields", {}).get(CONVERTED_FIELD)
        ]
        skipped = original - len(records)
        if skipped:
            print(f"[INFO] Skipping {skipped} record(s) without both image fields")

    # Skip records whose final output is already there
    if args.skip_existing:
        original = len(records)
        # The reel video is the last deliverable, so that is what "done" means.
        # Records missing it fall through and resume from their furthest
        # completed phase.
        records = [r for r in records if not r.get("fields", {}).get(REEL_FIELD)]
        skipped = original - len(records)
        if skipped:
            print(f"[INFO] Skipping {skipped} record(s) that already have {REEL_FIELD}")

    # Apply limit
    if args.limit:
        records = records[: args.limit]

    if not records:
        print("[OK] No records to process")
        return 0

    print(f"[INFO] Processing {len(records)} record(s)...\n")

    # Working directory for temporary downloads
    workdir = settings.output_dir / "moodboard_reel" / args.category
    workdir.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    failed = 0
    for position, record in enumerate(records, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})
        print(f"[{position}/{len(records)}] Record {record_id}")

        # Resume from the furthest completed phase rather than redoing paid
        # AI work: both image fields present means only the reel is missing;
        # blended alone means convert + reel still need to run.
        resumable = args.skip_existing and not args.convert_only
        reel_only = args.reel_only or (
            resumable
            and bool(fields.get(BLENDED_FIELD))
            and bool(fields.get(CONVERTED_FIELD))
        )
        convert_only = not reel_only and (
            args.convert_only or (resumable and bool(fields.get(BLENDED_FIELD)))
        )

        ok = process_record(
            record_id,
            fields,
            session=session,
            token=token,
            base_id=base_id,
            table_id=table_id,
            kie=kie,
            assets=assets,
            workdir_root=workdir,
            execute=args.execute,
            convert_only=convert_only,
            reel_only=reel_only,
        )
        if ok:
            succeeded += 1
        else:
            failed += 1
        print()

    print(f"[SUMMARY] processed={succeeded + failed}, succeeded={succeeded}, failed={failed}")
    if not args.execute:
        print("[DRY RUN] No AI calls were made and no Airtable records were modified.")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
