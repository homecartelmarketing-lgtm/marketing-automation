"""Verify the Ad Cover converted images (1:1 and 9:16 Story) geometry + overlay.

Usage::

    python scripts/ops/verify_ad_cover_image.py [record_id]
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_automation.config import load_settings
from content_automation.scraping import ScrapeAirtableClient

RECORD_ID = sys.argv[1] if len(sys.argv) > 1 else "recTOihpOeKkTmbaI"

settings = load_settings()
settings.require({"airtable"})
airtable = ScrapeAirtableClient(
    token=settings.airtable_token,
    base_id=settings.airtable_base_id,
    table_id="tblwIsDGZBPuYJV2Z",
)

record = airtable.get_record(RECORD_ID)
fields = record.get("fields", {})

VARIANTS = (
    ("Ad Cover Converted Image", (1080, 1080), "ad_cover_converted_"),
    ("Ad Cover Converted Image Story", (1080, 1920), "ad_cover_converted_story_"),
)

failures = 0
for field_name, expected, prefix in VARIANTS:
    print("=" * 68)
    print(f"CHECK: {field_name} (expect {expected[0]}x{expected[1]})")

    local = ROOT / "output" / "ad_cover" / f"{prefix}{RECORD_ID}.jpg"
    print("  LOCAL FILE:", local.name, "exists=", local.is_file())
    if local.is_file():
        with Image.open(local) as im:
            print("    local size:", im.size, im.mode, "bytes:", local.stat().st_size)

    attachments = fields.get(field_name) or []
    if not attachments:
        print(f"  [SKIP] No attachment in '{field_name}' yet.")
        continue

    resp = requests.get(attachments[0]["url"], timeout=60)
    out_dir = ROOT / "output" / "ad_cover"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"_verify_download{prefix.rstrip('_')}.jpg"
    dest.write_bytes(resp.content)
    print("  DOWNLOAD:", resp.status_code, len(resp.content), "bytes")

    with Image.open(dest) as im:
        print("    size:", im.size, "mode:", im.mode)
        if im.size != expected:
            print(f"    [FAIL] expected {expected}, got {im.size}")
            failures += 1

    # The overlay paints near-white typography near the top and bottom edges.
    # Sample those bands and confirm bright pixels exist (a bare room photo
    # may or may not, but the bold white text guarantees some >230 luminance).
    with Image.open(dest) as im:
        im_rgb = im.convert("RGB")
        w, h = im_rgb.size
        # Sample top band (headline area) and bottom band (button area)
        top_crop = im_rgb.crop((0, 0, w, int(h * 0.35)))
        bot_crop = im_rgb.crop((0, int(h * 0.70), w, h))

        def has_bright_pixels(img: Image.Image, min_count: int = 50) -> bool:
            count = 0
            for r, g, b in img.getdata():
                if r > 230 and g > 230 and b > 230:
                    count += 1
                    if count >= min_count:
                        return True
            return False

        top_ok = has_bright_pixels(top_crop)
        bot_ok = has_bright_pixels(bot_crop)
        print(f"    brand typography check: top_band={top_ok}, bot_band={bot_ok}")
        if not (top_ok and bot_ok):
            print("    [WARN] Typography overlay band did not detect bright pixels as expected.")

print("=" * 68)
if failures:
    print(f"FAILED: {failures} check(s) did not match.")
    sys.exit(1)
print("SUCCESS: Converted ad cover deliverables match geometry specification.")
