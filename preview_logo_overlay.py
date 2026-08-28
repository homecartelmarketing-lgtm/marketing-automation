"""CLI: preview the HomeCartel watermark on a photo without paying for one.

The overlay is pure PIL, so judging its size and position needs no provider
call at all -- only a base photo and the logo. This reads both straight off an
Airtable record (or off disk), reports the numbers that explain what the logo
will look like, and writes a side-by-side sheet so a size can be picked in one
pass instead of one paid workflow run per attempt.

Usage::

    python preview_logo_overlay.py --record-id recXXXXXXXXXXXXXX
    python preview_logo_overlay.py --record-id recXXXX --scale 1.0 --scale 1.8
    python preview_logo_overlay.py --photo tmp/day.jpg --logo tmp/logo.png
    python preview_logo_overlay.py --record-id recXXXX --scale 1.5 --execute
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from content_automation.airtable_client import AirtableClient
from content_automation.config import TABLES, load_settings
from content_automation.errors import AutomationError
from content_automation.models import Attachment, LocalImage
from content_automation.overlay import (
    HOMECARTEL_LOGO_BOX,
    HOMECARTEL_STORY_LOGO_BOX,
    LogoBox,
    logo_placement,
    stamp_logo,
    visible_bounds,
)

DEFAULT_TABLE = "pendant_lights"
DEFAULT_FIELD = "FEED - Day & Night (2)"
DEFAULT_LOGO_FIELD = "Logo"
DEFAULT_SCALES = (1.0, 1.5, 2.0)
DEFAULT_OUT = Path("tmp") / "logo_preview"

# The slice of the canvas the comparison sheet shows, in the design canvas's
# own units. Wide and tall enough to hold the logo box even at 2.0x.
CROP_REGION_FEED = (0.0, 1060.0, 600.0, 1350.0)
CROP_REGION_STORY = (600.0, 0.0, 1080.0, 350.0)
CROP_REGION = CROP_REGION_FEED
LABEL_HEIGHT = 28
SHEET_BACKGROUND = (24, 24, 24)
SHEET_TEXT = (255, 255, 255)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Preview the logo watermark without any provider call."
    )
    parser.add_argument("--record-id", default="")
    parser.add_argument("--table", choices=sorted(TABLES), default=DEFAULT_TABLE)
    parser.add_argument("--field", default=DEFAULT_FIELD)
    parser.add_argument("--logo-field", default=DEFAULT_LOGO_FIELD)
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Which attachment in --field to stamp. Default the first.",
    )
    parser.add_argument("--photo", default="", help="Local base photo, skips Airtable.")
    parser.add_argument("--logo", default="", help="Local logo PNG, skips Airtable.")
    parser.add_argument(
        "--scale",
        type=float,
        action="append",
        help=f"Logo box multiplier. Repeatable. Default {DEFAULT_SCALES}.",
    )
    parser.add_argument(
        "--story",
        action="store_true",
        help="Use 9:16 Story logo placement (top-right, X=781.7, Y=108) instead of 4:5 Feed.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Also replace the attachment in Airtable with the stamped version.",
    )
    return parser.parse_args(argv)


def replace_attachment_id(
    original_ids: list[str],
    index: int,
    new_id: str,
) -> list[str]:
    """``original_ids`` with position ``index`` swapped for ``new_id``.

    Airtable appends an upload to the end of the field, so putting the stamped
    photo back where it came from means restating the whole order. Clearing the
    field instead would take any sibling attachment -- the night photo -- with
    it.
    """
    if not 0 <= index < len(original_ids):
        raise AutomationError(
            f"Attachment index {index} is out of range for "
            f"{len(original_ids)} attachment(s)"
        )
    return [
        new_id if position == index else attachment_id
        for position, attachment_id in enumerate(original_ids)
    ]


@dataclass(frozen=True)
class Sources:
    base: Path
    logo: Path
    base_name: str
    logo_name: str


def resolve_sources(
    args,
    client,
    out_dir: Path,
) -> tuple[Sources, list[tuple[str, str]]]:
    """Local paths for base and logo, plus the field's ``(id, filename)`` pairs."""
    base = Path(args.photo) if args.photo else None
    logo = Path(args.logo) if args.logo else None
    attachments_before: list[tuple[str, str]] = []

    if base is None or logo is None:
        if client is None:
            raise AutomationError(
                "--record-id is required unless both --photo and --logo are given"
            )
        fields = client.get_record(args.record_id).get("fields", {})
        if base is None:
            attachments = fields.get(args.field) or []
            if not attachments:
                raise AutomationError(
                    f"Record {args.record_id} has no {args.field} attachment"
                )
            if not 0 <= args.index < len(attachments):
                raise AutomationError(
                    f"--index {args.index} is out of range: {args.field} holds "
                    f"{len(attachments)} attachment(s)"
                )
            attachments_before = [
                (str(item.get("id") or ""), str(item.get("filename") or ""))
                for item in attachments
            ]
            base = _download(client, attachments[args.index], out_dir, "original")
        if logo is None:
            logo_attachments = fields.get(args.logo_field) or []
            if not logo_attachments:
                raise AutomationError(
                    f"Record {args.record_id} has no {args.logo_field} attachment"
                )
            logo = _download(client, logo_attachments[0], out_dir, "logo")

    for path, label in ((base, "photo"), (logo, "logo")):
        if not path.is_file():
            raise AutomationError(f"Missing {label}: {path}")
    return Sources(base, logo, base.name, logo.name), attachments_before


def _download(client, raw_attachment: dict, out_dir: Path, prefix: str) -> Path:
    attachment = Attachment.from_airtable(raw_attachment)
    suffix = Path(attachment.filename).suffix or ".jpg"
    destination = out_dir / f"{prefix}{suffix}"
    return client.download_attachment(attachment, destination).path


def describe_logo(logo_path: Path) -> tuple[tuple[int, int], tuple[int, int], bool]:
    """``(raw_size, trimmed_size, has_alpha)`` for the logo file."""
    with Image.open(logo_path) as source:
        has_alpha = source.mode in {"RGBA", "LA"} or "transparency" in source.info
        logo = source.convert("RGBA")
        raw_size = logo.size
        bounds = visible_bounds(logo)
        trimmed = logo.crop(bounds).size if bounds else raw_size
    return raw_size, trimmed, has_alpha


def report(sources: Sources, box: LogoBox, scales: list[float]) -> None:
    with Image.open(sources.base) as base:
        base_size = base.size
    raw, trimmed, has_alpha = describe_logo(sources.logo)

    width, height = base_size
    print(f"[BASE]  {sources.base_name}  {width}x{height}  ({_ratio(base_size)})")

    padding = ""
    if trimmed != raw:
        trimmed_area = (trimmed[0] * trimmed[1]) / (raw[0] * raw[1])
        padding = f"  ({round((1 - trimmed_area) * 100)}% transparent padding trimmed)"
    print(
        f"[LOGO]  {sources.logo_name}  {raw[0]}x{raw[1]} raw -> "
        f"{trimmed[0]}x{trimmed[1]} trimmed{padding}"
    )
    if not has_alpha:
        print(
            "[WARN]  The logo has no alpha channel, so its background will show "
            "as a solid block. Upload a transparent PNG."
        )
    if trimmed == raw:
        print(
            "[INFO]  Nothing to trim -- the logo is already tight. If it still "
            "reads small, raise --scale rather than re-exporting."
        )

    for scale in scales:
        left, top, logo_width, logo_height = logo_placement(
            base_size,
            trimmed,
            _scaled_box(box, scale),
        )
        share = logo_width / width * 100
        print(
            f"[{scale:g}x]   left={left} top={top} size={logo_width}x{logo_height}"
            f"   ({share:.1f}% of width)"
        )


def _ratio(size: tuple[int, int]) -> str:
    width, height = size
    if abs(width / height - 0.8) < 0.01:
        return "4:5"
    if abs(width / height - 0.5625) < 0.01:
        return "9:16"
    return f"{width}:{height}"


def _scaled_box(box: LogoBox, scale: float) -> LogoBox:
    return LogoBox(
        box.x,
        box.y,
        box.width,
        box.height,
        box.canvas_width,
        box.canvas_height,
        scale=scale,
    )


def crop_box(
    base_size: tuple[int, int],
    box: LogoBox,
    region: tuple[float, float, float, float] = CROP_REGION,
) -> tuple[int, int, int, int]:
    """``region`` mapped onto a real image, in pixels."""
    base_width, base_height = base_size
    scale_x = base_width / box.canvas_width
    scale_y = base_height / box.canvas_height
    left, top, right, bottom = region
    return (
        max(0, round(left * scale_x)),
        max(0, round(top * scale_y)),
        min(base_width, round(right * scale_x)),
        min(base_height, round(bottom * scale_y)),
    )


def comparison_sheet(
    stamped: list[tuple[float, Path]],
    box: LogoBox,
    destination: Path,
    region: tuple[float, float, float, float] = CROP_REGION,
) -> Path:
    """Stack the cropped logo region from each scale, labelled."""
    if not stamped:
        raise AutomationError("Nothing to compare")
    bands: list[tuple[float, Image.Image]] = []
    for scale, path in stamped:
        with Image.open(path) as image:
            bands.append((scale, image.convert("RGB").crop(crop_box(image.size, box, region))))

    width = max(band.width for _, band in bands)
    height = sum(band.height + LABEL_HEIGHT for _, band in bands)
    sheet = Image.new("RGB", (width, height), SHEET_BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    offset = 0
    for scale, band in bands:
        draw.text((8, offset + 8), f"{scale:g}x", fill=SHEET_TEXT, font=font)
        offset += LABEL_HEIGHT
        sheet.paste(band, (0, offset))
        offset += band.height

    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, format="JPEG", quality=95, optimize=True)
    return destination


def write_back(
    client,
    args,
    stamped: Path,
    attachments_before: list[tuple[str, str]],
) -> None:
    """Swap the stamped photo in for the one it was made from."""
    ids_before = [attachment_id for attachment_id, _ in attachments_before]
    known = {attachment_id for attachment_id in ids_before if attachment_id}
    client.upload_attachment(
        args.record_id,
        args.field,
        LocalImage(stamped, stamped.name, "image/jpeg"),
    )
    current = client.get_record(args.record_id).get("fields", {}).get(args.field, [])
    added = [
        str(item.get("id") or "")
        for item in current
        if str(item.get("id") or "") not in known
    ]
    if len(added) != 1:
        raise AutomationError(
            f"Expected exactly one new attachment after upload, found {len(added)}"
        )
    client.set_attachment_ids(
        args.record_id,
        args.field,
        replace_attachment_id(ids_before, args.index, added[0]),
    )
    # Built from the filenames captured before the upload, so the check does
    # not depend on where Airtable chose to append the new attachment.
    client.verify_attachment_filenames(
        args.record_id,
        args.field,
        [
            stamped.name if position == args.index else filename
            for position, (_, filename) in enumerate(attachments_before)
        ],
    )


def main(argv=None) -> int:
    args = parse_args(argv)
    scales = args.scale or list(DEFAULT_SCALES)
    if any(scale <= 0 for scale in scales):
        raise SystemExit("--scale must be greater than zero")
    if args.execute and len(scales) != 1:
        raise SystemExit(
            "--execute writes one image back, so give exactly one --scale"
        )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = None
    if args.record_id:
        settings = load_settings()
        settings.require({"airtable"})
        client = AirtableClient(
            settings.airtable_token,
            settings.airtable_base_id,
            TABLES[args.table],
        )
    if args.execute and client is None:
        raise SystemExit("--execute needs --record-id")

    sources, attachments_before = resolve_sources(args, client, out_dir)
    with Image.open(sources.base) as img:
        is_story_ratio = abs(img.width / img.height - 9 / 16) < 0.05
    is_story = args.story or "STORY" in args.field.upper() or is_story_ratio
    box = HOMECARTEL_STORY_LOGO_BOX if is_story else HOMECARTEL_LOGO_BOX
    crop_region = CROP_REGION_STORY if is_story else CROP_REGION_FEED
    if is_story:
        print("[MODE]  Using 9:16 Story Logo Placement (Top-Right: X=781.7, Y=108.0, 190.3x63.5)")
    else:
        print("[MODE]  Using 4:5 Feed Logo Placement (Bottom-Left: X=108.0, Y=1178.5, 190.3x63.5)")
    report(sources, box, scales)

    stamped: list[tuple[float, Path]] = []
    for scale in scales:
        destination = out_dir / f"stamped_{scale:g}x.jpg"
        stamp_logo(sources.base, sources.logo, destination, _scaled_box(box, scale))
        stamped.append((scale, destination))
        print(f"[WROTE] {destination}")

    sheet = comparison_sheet(stamped, box, out_dir / "comparison.jpg", region=crop_region)
    print(f"[SHEET] {sheet}")

    if args.execute:
        write_back(client, args, stamped[0][1], attachments_before)
        print(
            f"[AIRTABLE] {args.field}[{args.index}] replaced on {args.record_id}. "
            f"The original is still at {sources.base}."
        )
    else:
        print("[LOCAL] Nothing was changed in Airtable. Pass --execute to write back.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
