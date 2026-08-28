"""Tips & Edu Feeds (3 Interiors + 1 Thumbnail, 3 Products, 3 Blends, 3 Layout Feeds) Complete Automation Pipeline.

Target Table: Tips & Educational Feed (tblEy5batpOObnZ4J / tblIhCP3Gjg09QFCK)

Phases:
1. Akeneo Scrape (Modern Chandeliers / Pendant Lights):
   Packs modern lighting products into 1 Airtable row:
   - Slot 1: Furniture Item, SKU, Item Name
   - Slot 2: Furniture Item2, SKU2, Item Name2
   - Slot 3: Furniture Item3, SKU3, Item Name3
   - Slot 4: Furniture Item4, SKU4, Item Name4
   Sets Status -> 'Standby'.

2. Krea AI Interior & Thumbnail Generation (4:5 Ratio, 1K Resolution):
   Uses preset moodboard ID with category prompt to generate 3 room photos:
   - Interior1 (Slot 1)
   - Interior2 (Slot 2)
   - Interior3 (Slot 3)
   Uses thumbnail moodboard ID ('ec860c16-10e4-429e-bba6-ff068bcb80b1') to generate:
   - Exterior Photo -> Analyzed by Claude Sonnet 5 for a 5-Word Tips Title
   - Stamped with HomeCartel Brand Logo (from 'Logo' field) + Centered Poppins Bold Title
   - Uploaded to 'Thumbnail'
   Sets Status -> 'Already attached a room Interior'.

3. Claude Sonnet 5 Prompt Analysis (via Fal AI):
   Uses Fal AI OpenRouter vision API and model 'anthropic/claude-sonnet-5'
   to generate tailored photorealistic image blending prompts:
   - Interior1 + Furniture Item  -> Prompt1
   - Interior2 + Furniture Item2 -> Prompt2
   - Interior3 + Furniture Item3 -> Prompt3
   Sets Status -> 'Already attached a room Interior'.

4. Fal AI Nano Banana Pro Blending (4:5 Ratio, 1K Quality):
   Uses model 'fal-ai/nano-banana-pro/edit' at 4:5 ratio and 1K quality
   to blend each product into its corresponding interior using Prompt1..3.
   Uploads all 3 generated blended photos into 'Tips and Edu Blended'.
   Sets Status -> 'Already attached a room Interior'.

5. Fal AI Nano Banana Pro Layout Blending -> Final Feed:
   Uses model 'fal-ai/nano-banana-pro/edit' to blend each blended photo
   with Layout templates 1..3 using JSON prompts (tipsedufeeds1..3.json):
   - Tips and Edu Layout1 + Blend 1 (tipsedufeeds1.json)
   - Tips and Edu Layout2 + Blend 2 (tipsedufeeds2.json)
   - Tips and Edu Layout3 + Blend 3 (tipsedufeeds3.json)
   Uploads all 3 generated feed photos into 'Tips and Edu Feeds'.
   Sets Status -> 'Complete'.

Usage:
    python run_tips_and_edu_feed.py
    python run_tips_and_edu_feed.py --phase all --execute
    python run_tips_and_edu_feed.py --phase 1 --max-rows 1 --execute
    python run_tips_and_edu_feed.py --phase 5 --execute
    python run_tips_and_edu_feed.py --target pendant_lights --phase all --execute
    python run_tips_and_edu_feed.py --record-id recXXXX --phase all --execute
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import functools
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any
import uuid

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, UnidentifiedImageError
import requests

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import load_settings
from content_automation.errors import AssetValidationError, AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import download_to_temp_file
from content_automation.overlay import HOMECARTEL_LOGO_BOX, prepare_logo_image, stamp_logo
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    select_new_products,
)

print = functools.partial(print, flush=True)

# ── Timezone & Default Constants ──────────────────────────────────────────

PHT = timezone(timedelta(hours=8))  # Philippine Standard Time (UTC+8)


def pht_timestamp() -> str:
    return datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")


DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

KREA_ASPECT_RATIO = "4:5"
KREA_RESOLUTION = "1K"
KREA_MODEL_LABEL = "krea-2-medium"

FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_BLENDING_MODEL = os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
BLENDING_ASPECT_RATIO = "4:5"
BLENDING_RESOLUTION = "1K"

STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_INTERIOR_ATTACHED = "Already attached a room Interior"
STATUS_PROCESSING = "Processing"
STATUS_COMPLETE = "Complete"
BLENDED_FIELD = "Tips and Edu Blended"
FINAL_FEED_FIELD = "Tips and Edu Feeds"
FINAL_FEED_ASPECT_RATIO = os.getenv("FINAL_FEED_ASPECT_RATIO", "").strip() or "4:5"
FINAL_FEED_RESOLUTION = "1K"

LOGO_FIELD = "Logo"
LOGO_FIELD_FALLBACKS = ("Logo", "Homecartel Logo", "Brand Logo", "Logo Image", "watermark")

THUMBNAIL_FIELD = "Thumbnail"
DEFAULT_THUMBNAIL_MOODBOARD_ID = "ec860c16-10e4-429e-bba6-ff068bcb80b1"
DEFAULT_THUMBNAIL_PROMPT = os.getenv("KREA_PROMPT_TIPS_EDU_THUMBNAIL", "").strip() or os.getenv("KREA_PROMPT_THUMBNAIL", "").strip() or "Generate me a modern house exterior"

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class LayoutSlotConfig:
    slot_index: int
    layout_field: str
    prompt_file: Path
    fallback_template: Path


LAYOUT_SLOTS: tuple[LayoutSlotConfig, ...] = (
    LayoutSlotConfig(
        slot_index=1,
        layout_field="Tips and Edu Layout1",
        prompt_file=BASE_DIR / "Tips and Edu Feeds" / "tipsedufeeds1.json",
        fallback_template=BASE_DIR / "Tips and Edu Feeds" / "tips-and-edu-layout.jpg",
    ),
    LayoutSlotConfig(
        slot_index=2,
        layout_field="Tips and Edu Layout2",
        prompt_file=BASE_DIR / "Tips and Edu Feeds" / "tipsedufeeds2.json",
        fallback_template=BASE_DIR / "Tips and Edu Feeds" / "tips-and-edu-layout2.jpg",
    ),
    LayoutSlotConfig(
        slot_index=3,
        layout_field="Tips and Edu Layout3",
        prompt_file=BASE_DIR / "Tips and Edu Feeds" / "tipsedufeeds3.json",
        fallback_template=BASE_DIR / "Tips and Edu Feeds" / "tips-and-edu-layout3.jpg",
    ),
)




# ── Presets Configuration ────────────────────────────────────────────────

@dataclass(frozen=True)
class TipsAndEduPreset:
    key: str  # "chandeliers" or "pendant_lights"
    label: str
    default_table_id: str
    env_table_key: str
    category_code: str
    default_moodboard_id: str
    env_moodboard_key: str
    interior_prompt: str
    fixture_label: str  # "chandelier" or "pendant light"


PRESETS: dict[str, TipsAndEduPreset] = {
    "chandeliers": TipsAndEduPreset(
        key="chandeliers",
        label="Chandelier Tips & Edu Feed",
        default_table_id="tblEy5batpOObnZ4J",
        env_table_key="AIRTABLE_TABLE_ID_TIPS_EDUCATIONAL_FEED",
        category_code="chandeliers",
        default_moodboard_id="b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        env_moodboard_key="KREA_MOODBOARD_ID_CHANDELIERS",
        interior_prompt="Generate me a modern living room hanging chandelier from the ceiling",
        fixture_label="chandelier",
    ),
    "pendant_lights": TipsAndEduPreset(
        key="pendant_lights",
        label="Pendant Light Tips & Edu Feed",
        default_table_id="tblIhCP3Gjg09QFCK",
        env_table_key="AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDUCATIONAL_FEED",
        category_code="pendant_lights",
        default_moodboard_id="de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
        env_moodboard_key="KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        interior_prompt="Generate me a modern dining room",
        fixture_label="pendant light",
    ),
}

TABLE_TO_PRESET: dict[str, str] = {
    "tblEy5batpOObnZ4J": "chandeliers",
    "tblIhCP3Gjg09QFCK": "pendant_lights",
}


def resolve_tips_and_edu_preset(
    target_arg: str | None = None,
    table_id_arg: str | None = None,
    category_arg: str | None = None,
    prompt_if_interactive: bool = True,
) -> TipsAndEduPreset:
    """Resolve which Tips & Edu Feed destination table / category preset to use."""
    # 1. Check table_id_arg
    if table_id_arg:
        tid = table_id_arg.strip()
        if tid in TABLE_TO_PRESET:
            return PRESETS[TABLE_TO_PRESET[tid]]
        for p in PRESETS.values():
            if p.default_table_id.lower() == tid.lower():
                return p
        cat = (category_arg or "").strip().lower()
        if "pendant" in cat:
            base = PRESETS["pendant_lights"]
            return TipsAndEduPreset(
                key=base.key,
                label=base.label,
                default_table_id=tid,
                env_table_key=base.env_table_key,
                category_code=base.category_code,
                default_moodboard_id=base.default_moodboard_id,
                env_moodboard_key=base.env_moodboard_key,
                interior_prompt=base.interior_prompt,
                fixture_label=base.fixture_label,
            )
        base = PRESETS["chandeliers"]
        return TipsAndEduPreset(
            key=base.key,
            label=base.label,
            default_table_id=tid,
            env_table_key=base.env_table_key,
            category_code=base.category_code,
            default_moodboard_id=base.default_moodboard_id,
            env_moodboard_key=base.env_moodboard_key,
            interior_prompt=base.interior_prompt,
            fixture_label=base.fixture_label,
        )

    # 2. Check target_arg / category_arg
    raw = (target_arg or category_arg or "").strip().lower()
    if raw:
        if raw in ("1", "chandeliers", "chandelier", "tbley5batpoobnz4j"):
            return PRESETS["chandeliers"]
        if raw in ("2", "pendant_lights", "pendant_light", "pendant", "tblihcp3gjg09qfck"):
            return PRESETS["pendant_lights"]
        if raw in PRESETS:
            return PRESETS[raw]

    # 3. Interactive prompt
    if prompt_if_interactive and sys.stdin.isatty():
        print("\n" + "=" * 64)
        print("Select Tips & Edu Feed Destination Table:")
        print("=" * 64)
        print("  [1] Chandelier Tips & Edu Feed")
        print("      Table ID : tblEy5batpOObnZ4J | Category: chandeliers")
        print("      Moodboard: b5ffdcbb-192e-4528-8d86-d1a4cf496887")
        print("  [2] Pendant Light Tips & Edu Feed")
        print("      Table ID : tblIhCP3Gjg09QFCK | Category: pendant_lights")
        print("      Moodboard: de5f4ff8-518c-4d6b-b606-ce1d5dac51f3")
        print("=" * 64)
        try:
            choice = input("Enter choice [1 or 2] (default: 1): ").strip().lower()
            if choice in ("2", "pendant", "pendant_light", "pendant_lights", "tblihcp3gjg09qfck"):
                return PRESETS["pendant_lights"]
            return PRESETS["chandeliers"]
        except (EOFError, KeyboardInterrupt):
            pass

    return PRESETS["chandeliers"]



# ── Slot Configuration ───────────────────────────────────────────────────

@dataclass(frozen=True)
class SlotConfig:
    slot_index: int  # 1, 2, 3
    furniture_field: str
    sku_field: str
    item_name_field: str
    interior_field: str
    prompt_field: str


SLOTS: list[SlotConfig] = [
    SlotConfig(
        slot_index=1,
        furniture_field="Furniture Item",
        sku_field="SKU",
        item_name_field="Item Name",
        interior_field="Interior1",
        prompt_field="Prompt1",
    ),
    SlotConfig(
        slot_index=2,
        furniture_field="Furniture Item2",
        sku_field="SKU2",
        item_name_field="Item Name2",
        interior_field="Interior2",
        prompt_field="Prompt2",
    ),
    SlotConfig(
        slot_index=3,
        furniture_field="Furniture Item3",
        sku_field="SKU3",
        item_name_field="Item Name3",
        interior_field="Interior3",
        prompt_field="Prompt3",
    ),
]


def get_slot_interior_val(fields: dict[str, Any], slot: SlotConfig) -> Any:
    """Retrieve slot interior attachment value, supporting Interior1 with fallback to legacy Interior."""
    val = fields.get(slot.interior_field)
    if not val and slot.slot_index == 1:
        val = fields.get("Interior")
    return val


OPTIONAL_SLOT_4 = {
    "furniture_field": "Furniture Item4",
    "sku_field": "SKU4",
    "item_name_field": "Item Name4",
}


class JsonlRunLogger:
    """Append redacted, machine-readable events without leaking credentials."""

    _SENSITIVE_KEY = re.compile(
        r"(?:key|token|authorization|secret|password|base64|data_uri|url)$",
        re.IGNORECASE,
    )

    def __init__(self, workspace: Path, automation: str, run_id: str) -> None:
        root = workspace / "output" / "logs" / automation
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / f"{datetime.now(PHT):%Y-%m-%d}.jsonl"
        self.run_id = run_id

    @classmethod
    def _redact(cls, value: Any, key: str = "") -> Any:
        if cls._SENSITIVE_KEY.search(key):
            return "[REDACTED]"
        if isinstance(value, str):
            if "data:" in value or "Authorization:" in value:
                return "[REDACTED]"
            shortened = re.sub(r"https?://[^\s'\"]+", "[REDACTED_URL]", value[:1000])
            return re.sub(r"\bsk-[A-Za-z0-9._-]+", "[REDACTED]", shortened)
        if isinstance(value, dict):
            return {str(k): cls._redact(v, str(k)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._redact(item, key) for item in value]
        return value

    def event(self, event: str, **details: Any) -> None:
        payload = self._redact(details)
        line = {
            "timestamp": pht_timestamp(),
            "run_id": self.run_id,
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")


# ── Audit Logging & Helpers ──────────────────────────────────────────────

AUDIT_LOG_DIR = Path("output") / "logs"
AUDIT_LOG_AKENEO = AUDIT_LOG_DIR / "tips_and_edu_feed_akeneo_logs.json"
AUDIT_LOG_KREA = AUDIT_LOG_DIR / "tips_and_edu_feed_krea_logs.json"
AUDIT_LOG_CLAUDE = AUDIT_LOG_DIR / "tips_and_edu_feed_claude_logs.json"
AUDIT_LOG_FAL_NANO = AUDIT_LOG_DIR / "tips_and_edu_feed_fal_nano_logs.json"
AUDIT_LOG_LAYOUT = AUDIT_LOG_DIR / "tips_and_edu_feed_layout_logs.json"
AUDIT_LOG_ERROR = AUDIT_LOG_DIR / "tips_and_edu_feed_error_logs.json"


def append_audit_log(log_entry: dict[str, Any], log_path: Path) -> None:
    """Append an audit record to the specified JSON log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            content = log_path.read_text(encoding="utf-8").strip()
            if content:
                logs = json.loads(content)
                if not isinstance(logs, list):
                    logs = [logs]
        except Exception:
            logs = []
    logs.append(log_entry)
    log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  [AUDIT LOG] Appended log entry to {log_path.name}")


def append_error_log(
    record_id: str,
    phase: str | int,
    error: Exception | str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append a structured error entry to the error audit log."""
    append_audit_log(
        {
            "timestamp": pht_timestamp(),
            "record_id": record_id,
            "phase": phase,
            "error": str(error),
            "details": details or {},
        },
        AUDIT_LOG_ERROR,
    )


def extract_attachment_url(attachments: Any) -> str:
    """Extract accessible HTTP URL from an Airtable attachment field."""
    if not attachments:
        return ""
    if isinstance(attachments, list) and len(attachments) > 0:
        first = attachments[0]
        if isinstance(first, dict):
            return str(first.get("url") or "").strip()
    if isinstance(attachments, dict):
        return str(attachments.get("url") or "").strip()
    return ""


def sort_attachments_by_slot(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort attachments so slot 1, 2, 3 are in exact order."""
    if not isinstance(attachments, list):
        return []

    def get_slot_index(att: dict[str, Any]) -> int:
        if not isinstance(att, dict):
            return 99
        filename = str(att.get("filename") or "").lower()
        for idx in (1, 2, 3):
            if f"_{idx}_" in filename or f"0{idx}" in filename or f"_{idx}." in filename or f"blended_{idx}" in filename or f"feed_{idx}" in filename:
                return idx
        return 99

    sorted_atts = sorted(attachments, key=get_slot_index)
    if all(get_slot_index(a) < 99 for a in sorted_atts) and len(sorted_atts) == len(attachments):
        return sorted_atts
    return attachments



def _clean_env_val(val: str | None) -> str:
    """Return stripped string or empty if placeholder."""
    if not val:
        return ""
    v = val.strip()
    if "input here" in v.lower() or "your_" in v.lower() or "<" in v:
        return ""
    return v


# ── Poppins Typography & Thumbnail Title Helpers ───────────────────────────

@dataclass(frozen=True)
class TextBox:
    """Position and dimensions for text expressed against Canva 1080x1350 canvas."""
    x: float
    y: float
    width: float
    height: float
    canvas_width: int = 1080
    canvas_height: int = 1350


@dataclass(frozen=True)
class LineDivider:
    """Horizontal line divider expressed against Canva 1080x1350 canvas."""
    start_x: float = 108.0
    end_x: float = 289.8
    start_y: float = 376.8
    end_y: float = 376.8
    thickness: float = 2.5
    canvas_width: int = 1080
    canvas_height: int = 1350

    @property
    def y(self) -> float:
        return self.start_y


HOMECARTEL_THUMBNAIL_TITLE_BOX = TextBox(
    x=105.0,
    y=237.4,
    width=597.4,
    height=66.8,
    canvas_width=1080,
    canvas_height=1350,
)

HOMECARTEL_THUMBNAIL_SUBTITLE_BOX = TextBox(
    x=107.0,
    y=304.2,
    width=522.5,
    height=50.5,
    canvas_width=1080,
    canvas_height=1350,
)

HOMECARTEL_THUMBNAIL_DIVIDER = LineDivider(
    start_x=108.0,
    end_x=289.8,
    start_y=376.8,
    end_y=376.8,
    thickness=2.5,
    canvas_width=1080,
    canvas_height=1350,
)

STATIC_THUMBNAIL_SUBTITLE = "In 3 ways"


def resolve_poppins_font(style: str = "bold", size: int = 56) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Resolve Poppins font path from local font assets."""
    font_file_map = {
        "bold": "Poppins-Bold.ttf",
        "regular": "Poppins-Regular.ttf",
        "light": "Poppins-Light.ttf",
    }
    filename = font_file_map.get(style.lower(), "Poppins-Bold.ttf")
    base_fonts = Path(__file__).parent / "content_automation" / "fonts"
    candidates = [
        base_fonts / filename,
        Path("content_automation/fonts") / filename,
        Path("fonts") / filename,
        Path(filename),
    ]
    for c in candidates:
        if c.is_file():
            try:
                return ImageFont.truetype(str(c), size)
            except Exception:
                pass
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def overlay_thumbnail_title(
    pil_img: Image.Image,
    title_text: str,
    *,
    subtitle_text: str = STATIC_THUMBNAIL_SUBTITLE,
    title_box: TextBox = HOMECARTEL_THUMBNAIL_TITLE_BOX,
    subtitle_box: TextBox = HOMECARTEL_THUMBNAIL_SUBTITLE_BOX,
    divider: LineDivider = HOMECARTEL_THUMBNAIL_DIVIDER,
    title_font_size: int = 42,
    subtitle_font_size: int = 32,
    text_color: str = "#FFFFFF",
    dim_factor: float = 1.0,
) -> Image.Image:
    """Overlay title (42px Poppins-Bold), static subtitle ('In 3 ways', 32px Poppins-Light), and line break divider in plain white with no shadow or outline."""
    if not title_text or not title_text.strip():
        return pil_img.copy()

    img = pil_img.copy().convert("RGB")
    if dim_factor < 1.0:
        img = ImageEnhance.Brightness(img).enhance(dim_factor)

    width, height = img.size
    scale_x = width / title_box.canvas_width
    scale_y = height / title_box.canvas_height

    draw = ImageDraw.Draw(img)

    # 1. Render Generated Title (Poppins-Bold, font size 42, Plain White)
    t_box_x = int(round(title_box.x * scale_x))
    t_box_y = int(round(title_box.y * scale_y))
    t_box_w = int(round(title_box.width * scale_x))

    scaled_title_size = max(24, int(round(title_font_size * scale_y)))
    font_title = resolve_poppins_font(style="bold", size=scaled_title_size)

    clean_title = title_text.strip()
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

    t_line_spacing = int(scaled_title_size * 0.22)
    curr_t_y = t_box_y

    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_h = bbox[3] - bbox[1]
        draw.text((t_box_x, curr_t_y), line, font=font_title, fill=text_color)
        curr_t_y += line_h + t_line_spacing

    # 2. Render Subtitle 'In 3 ways' (Poppins-Light, font size 32, Plain White)
    if subtitle_text:
        s_box_x = int(round(subtitle_box.x * scale_x))
        nominal_s_y = int(round(subtitle_box.y * scale_y))
        s_box_y = max(nominal_s_y, curr_t_y + int(scaled_title_size * 0.15))

        scaled_sub_size = max(18, int(round(subtitle_font_size * scale_y)))
        font_sub = resolve_poppins_font(style="light", size=scaled_sub_size)

        clean_sub = subtitle_text.strip()
        draw.text((s_box_x, s_box_y), clean_sub, font=font_sub, fill=text_color)

        sub_bbox = draw.textbbox((0, 0), clean_sub, font=font_sub)
        sub_h = sub_bbox[3] - sub_bbox[1]
        curr_s_bottom = s_box_y + sub_h
    else:
        curr_s_bottom = curr_t_y

    # 3. Render Line Break / Horizontal Divider (Plain White Line: start X=108, end X=289.8, Y=376.8)
    line_start_x = int(round(divider.start_x * scale_x))
    line_end_x = int(round(divider.end_x * scale_x))
    nominal_line_y = int(round(divider.start_y * scale_y))
    line_y = max(nominal_line_y, curr_s_bottom + int(round(22 * scale_y)))
    line_thickness = max(2, int(round(divider.thickness * scale_y)))

    draw.line(
        [(line_start_x, line_y), (line_end_x, line_y)],
        fill=text_color,
        width=line_thickness,
    )

    return img


def generate_thumbnail_title_prompt(
    fal: FalClient,
    exterior_url: str,
    item_names: list[str] | None = None,
    fixture_label: str = "lighting",
    model: str = FAL_VISION_MODEL,
) -> str:
    """Generate a punchy, highly readable 5-word title for Tips & Edu Feed exterior thumbnail using Claude Sonnet 5."""
    items_desc = f" Featured tips products include: {', '.join(item_names)}." if item_names else ""
    instruction = (
        "You are an expert interior design branding specialist and social media director for HomeCartel.\n"
        f"Analyze this modern exterior photo. This post is an educational Instagram Tips & Edu carousel feed showcasing 3 practical tips for styling modern {fixture_label} fixtures in interior spaces.{items_desc}\n\n"
        "Generate a punchy, elegant, and clearly descriptive 5-word title (target exactly 4 to 6 words) that introduces the tips and interior lighting for the cover thumbnail.\n"
        "Examples:\n"
        "- 5 Modern Dining Lighting Tips\n"
        "- Essential Living Room Lighting Tips\n"
        "- Modern Chandelier Home Styling Tips\n"
        "- How To Style Modern Lighting\n"
        "- Curated Lighting For Modern Homes\n\n"
        "Rules:\n"
        "1. Do NOT use ALL CAPS. Use Title Case.\n"
        "2. Keep it between 4 and 6 words (ideally 5 words).\n"
        "3. Output ONLY the title text. No quotes, no markdown, no punctuation, and no preamble."
    )
    raw_title = fal.generate_vision_prompt([exterior_url], instruction, model=model)
    clean_title = raw_title.strip().strip('"').strip("'").strip("`").strip()
    return clean_title


# ── Pipeline Runner Class ────────────────────────────────────────────────

class TipsAndEduFeedRunner:
    """End-to-end multi-phase automation runner for Tips & Edu Feeds."""

    def __init__(
        self,
        *,
        preset: TipsAndEduPreset | None = None,
        table_id: str | None = None,
        moodboard_id: str | None = None,
        thumbnail_moodboard_id: str | None = None,
        interior_prompt: str | None = None,
        thumbnail_prompt: str | None = None,
        category_code: str | None = None,
        style_code: str = DEFAULT_STYLE,
        akeneo: AkeneoClient | None = None,
        krea: KreaClient | None = None,
        fal: FalClient | None = None,
        airtable: ScrapeAirtableClient | None = None,
        logger: JsonlRunLogger | None = None,
    ) -> None:
        self.settings = load_settings()

        if preset is None:
            self.preset = resolve_tips_and_edu_preset(
                target_arg=None,
                table_id_arg=table_id,
                category_arg=category_code,
                prompt_if_interactive=False,
            )
        else:
            self.preset = preset

        env_table = _clean_env_val(os.getenv(self.preset.env_table_key))
        self.table_id = (
            (table_id or "").strip()
            or env_table
            or self.preset.default_table_id
        )

        env_mb = _clean_env_val(os.getenv(self.preset.env_moodboard_key))
        self.moodboard_id = (
            (moodboard_id or "").strip()
            or env_mb
            or self.preset.default_moodboard_id
        )

        env_thumb_mb = _clean_env_val(os.getenv("KREA_MOODBOARD_ID_TIPS_EDU_THUMBNAIL")) or _clean_env_val(os.getenv("KREA_MOODBOARD_ID_THUMBNAIL"))
        self.thumbnail_moodboard_id = (
            (thumbnail_moodboard_id or "").strip()
            or env_thumb_mb
            or DEFAULT_THUMBNAIL_MOODBOARD_ID
        )
        self.thumbnail_field = THUMBNAIL_FIELD

        self.interior_prompt = (
            (interior_prompt or "").strip()
            or self.preset.interior_prompt
        )

        env_thumb_prompt = _clean_env_val(os.getenv("KREA_PROMPT_TIPS_EDU_THUMBNAIL")) or _clean_env_val(os.getenv("KREA_PROMPT_THUMBNAIL"))
        self.thumbnail_prompt = (
            (thumbnail_prompt or "").strip()
            or env_thumb_prompt
            or DEFAULT_THUMBNAIL_PROMPT
        )
        self.category_code = category_code or self.preset.category_code
        self.style_code = style_code or DEFAULT_STYLE
        self.fixture_label = self.preset.fixture_label

        self.airtable = airtable or ScrapeAirtableClient(
            self.settings.airtable_token,
            self.settings.airtable_base_id,
            self.table_id,
        )

        channel = os.getenv("CHANNEL_NAME", "home_cartel").strip()
        self.akeneo = akeneo or AkeneoClient(
            self.settings.akeneo_host,
            self.settings.akeneo_client_id,
            self.settings.akeneo_secret,
            self.settings.akeneo_username,
            self.settings.akeneo_password,
            channel_name=channel,
        )

        self.krea = krea or KreaClient(
            self.settings.krea_token,
            self.settings.krea_base_url,
        )

        self.fal_key = (
            self.settings.fal_key
            or os.getenv("FAL_KEY", "").strip()
            or os.getenv("FAL_API_KEY", "").strip()
        )
        self.fal = fal or FalClient(self.fal_key)

        self.run_id = uuid.uuid4().hex
        self.logger = logger or JsonlRunLogger(
            Path("."), f"tips_and_edu_feed_{self.preset.key}", self.run_id
        )

    @property
    def artifact_root(self) -> Path:
        path = Path("output") / "tips_and_edu_feed" / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _artifact_path(self, record_id: str, filename: str) -> Path:
        path = self.artifact_root / record_id
        path.mkdir(parents=True, exist_ok=True)
        return path / filename

    def _schema_fields(self) -> dict[str, str]:
        return {
            "Furniture Item": "multipleAttachments",
            "SKU": "multilineText",
            "Item Name": "singleLineText",
            "Furniture Item2": "multipleAttachments",
            "SKU2": "multilineText",
            "Item Name2": "singleLineText",
            "Furniture Item3": "multipleAttachments",
            "SKU3": "multilineText",
            "Item Name3": "singleLineText",
            "Furniture Item4": "multipleAttachments",
            "SKU4": "multilineText",
            "Item Name4": "singleLineText",
            LOGO_FIELD: "multipleAttachments",
            self.thumbnail_field: "multipleAttachments",
            "Interior1": "multipleAttachments",
            "Interior2": "multipleAttachments",
            "Interior3": "multipleAttachments",
            "Prompt1": "multilineText",
            "Prompt2": "multilineText",
            "Prompt3": "multilineText",
            BLENDED_FIELD: "multipleAttachments",
            "Tips and Edu Layout1": "multipleAttachments",
            "Tips and Edu Layout2": "multipleAttachments",
            "Tips and Edu Layout3": "multipleAttachments",
            FINAL_FEED_FIELD: "multipleAttachments",
        }

    def _get_logo_path(self, record_fields: dict[str, Any], record_id: str) -> Path | None:
        """Resolve HomeCartel logo path from record attachment, table records, or local assets."""
        # 1. Check current record attachment
        for key in LOGO_FIELD_FALLBACKS:
            val = record_fields.get(key)
            url = extract_attachment_url(val)
            if url:
                logo_dest = self._artifact_path(record_id, f"logo_{record_id}.png")
                try:
                    self._download(url, logo_dest)
                    if logo_dest.is_file():
                        return logo_dest
                except Exception as e:
                    print(f"    [WARN] Failed to download logo from field '{key}': {e}")

        # 2. Check other table records for Logo attachment
        try:
            records = self.airtable.list_records(list(LOGO_FIELD_FALLBACKS))
            for r in records:
                rf = r.get("fields", {})
                for key in LOGO_FIELD_FALLBACKS:
                    url = extract_attachment_url(rf.get(key))
                    if url:
                        logo_dest = self._artifact_path(record_id, f"logo_{record_id}.png")
                        try:
                            self._download(url, logo_dest)
                            if logo_dest.is_file():
                                return logo_dest
                        except Exception:
                            pass
        except Exception:
            pass

        # 3. Check local candidate logo files
        local_candidates = [
            Path("assets/homecartel_logo.png"),
            Path("JSON Prompts/homecartel_logo.png"),
            Path("content_automation/assets/logo.png"),
            Path("static/img/logo.png"),
            Path("scratch/refined_logo.png"),
            Path("logo.png"),
        ]
        for p in local_candidates:
            if p.is_file():
                return p
        return None

    def _status_values(self) -> list[str]:
        return [
            STATUS_STANDBY,
            STATUS_INTERIOR_ATTACHED,
            STATUS_PROCESSING,
            STATUS_COMPLETE,
        ]

    def preflight(self, *, execute: bool = True) -> None:
        """Ensure all required fields and single-select values exist."""
        if execute:
            self.airtable.ensure_fields(self._schema_fields())
            self.airtable.ensure_single_select_options(STATUS_FIELD, self._status_values())
            print(f"[PREFLIGHT] Schema verified for table {self.table_id} (Tips & Edu Feeds)")
        else:
            print(f"[DRY RUN] Would verify schema for table {self.table_id}")

    def _update_status(self, record_id: str, status: str) -> None:
        self.airtable.update_records([(record_id, {STATUS_FIELD: status})])
        self.logger.event("status_updated", record_id=record_id, status=status)

    @staticmethod
    def _download(url: str, destination: Path) -> Path:
        response = requests.get(url, stream=True, timeout=180)
        if not response.ok:
            raise ProviderError(f"Download generated media failed ({response.status_code})")
        temporary = destination.with_suffix(destination.suffix + ".part")
        with temporary.open("wb") as stream:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    stream.write(chunk)
        temporary.replace(destination)
        return destination

    @staticmethod
    def _validate_dimensions(path: Path, dimensions: tuple[int, int], label: str) -> None:
        try:
            with Image.open(path) as image:
                actual = image.size
        except (OSError, UnidentifiedImageError) as error:
            raise AssetValidationError(f"Unreadable {label}: {path}") from error
        if actual != dimensions:
            raise AssetValidationError(
                f"{label} must be {dimensions[0]}x{dimensions[1]}, found {actual[0]}x{actual[1]}"
            )

    def _records(self) -> list[dict[str, Any]]:
        fields = list(self._schema_fields()) + [STATUS_FIELD, "Interior"]
        records = self.airtable.list_records(fields)
        return sorted(
            records,
            key=lambda item: (str(item.get("createdTime") or ""), str(item.get("id") or "")),
        )

    def _phase_for_record(self, record: dict[str, Any]) -> int | None:
        """Determine next incomplete phase for a given record."""
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().casefold()
        if status in ("complete", "done", "skip", "skipped") or "error" in status:
            return None

        # Check product items (Furniture Item 1, 2, 3)
        has_products = all(
            bool(fields.get(slot.furniture_field)) for slot in SLOTS
        )
        if not has_products:
            return None

        # Check interiors (Interior1 / Interior, Interior2, Interior3) and Thumbnail
        has_interiors = (
            bool(get_slot_interior_val(fields, SLOTS[0]))
            and bool(fields.get("Interior2"))
            and bool(fields.get("Interior3"))
            and bool(fields.get(self.thumbnail_field))
        )
        if not has_interiors:
            return 2

        # Check prompts (Prompt1, Prompt2, Prompt3)
        has_prompts = all(
            bool(str(fields.get(slot.prompt_field) or "").strip()) for slot in SLOTS
        )
        if not has_prompts:
            return 3

        # Check blended images in 'Tips and Edu Blended'
        blended_count = len(fields.get(BLENDED_FIELD) or [])
        if blended_count < 3:
            return 4

        # Check final layout feed images in 'Tips and Edu Feeds'
        final_count = len(fields.get(FINAL_FEED_FIELD) or [])
        if final_count < 3:
            return 5

        return None



    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1: AKENEO SCRAPE
    # ══════════════════════════════════════════════════════════════════════════

    def phase_1(self, *, seed: int | None = None, execute: bool = True) -> dict[str, Any] | None:
        """Scrape 4 modern lighting products into a new Airtable row."""
        print("\n" + "=" * 70)
        print(f"PHASE 1: Akeneo 4-Product Scrape (Category: {self.category_code}, Style: {self.style_code})")
        print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
        print("=" * 70)

        if not execute:
            print(f"[DRY RUN] Would authenticate with Akeneo and scrape {self.fixture_label} items.")
            return None

        phase_start = time.monotonic()
        try:
            self.akeneo.authenticate()

            # Gather existing SKUs across all 4 slots
            records = self.airtable.list_records(["SKU", "SKU2", "SKU3", "SKU4"])
            existing_skus: set[str] = set()
            for r in records:
                f = r.get("fields", {})
                for key in ("SKU", "SKU2", "SKU3", "SKU4"):
                    val = str(f.get(key) or "").strip()
                    if val:
                        existing_skus.add(val)

            products = self.akeneo.fetch_products(
                {
                    "categories": [
                        {"operator": "IN", "value": [akeneo_category_code(self.category_code)]}
                    ],
                    "Style2": [{"operator": "IN", "value": [self.style_code]}],
                }
            )

            existing_names, existing_media = existing_product_identities(products, existing_skus)
            candidates, _ = select_new_products(
                products,
                existing_skus,
                existing_item_names=existing_names,
                existing_media_codes=existing_media,
                category_code=self.category_code,
            )

            # Filter out linear chandeliers from normal chandelier feed if needed
            if self.category_code == "chandeliers":
                filtered_candidates = [
                    c for c in candidates
                    if "linear" not in (c.item_name or "").lower()
                    and "linear" not in (c.sku or "").lower()
                    and "cluster" not in (c.item_name or "").lower()
                ]
                if len(filtered_candidates) < 4:
                    filtered_candidates = candidates
            else:
                filtered_candidates = candidates

            if len(filtered_candidates) < 3:
                raise AutomationError(
                    f"Akeneo returned only {len(filtered_candidates)} new products; need at least 3 for a full row."
                )

            # Randomize candidate pool so we pick random modern products instead of strictly top-4
            if len(filtered_candidates) <= 4:
                selected_items = filtered_candidates
            else:
                rng = random.Random(seed)
                shuffled_candidates = list(filtered_candidates)
                rng.shuffle(shuffled_candidates)
                selected_items = shuffled_candidates[:4]

            record_payload: dict[str, Any] = {
                STATUS_FIELD: STATUS_STANDBY,
            }
            for idx, item in enumerate(selected_items):
                slot_idx = idx + 1
                if slot_idx <= 3:
                    cfg = SLOTS[idx]
                    record_payload[cfg.sku_field] = item.sku
                    record_payload[cfg.item_name_field] = item.item_name
                elif slot_idx == 4:
                    record_payload[OPTIONAL_SLOT_4["sku_field"]] = item.sku
                    record_payload[OPTIONAL_SLOT_4["item_name_field"]] = item.item_name

            record_id = self.airtable.create_record(record_payload)
            skus_str = ", ".join(it.sku for it in selected_items)
            print(f"[OK] Created row {record_id} with SKUs: {skus_str}")

            # Download and upload media for selected products
            for idx, item in enumerate(selected_items):
                slot_idx = idx + 1
                target_field = SLOTS[idx].furniture_field if slot_idx <= 3 else OPTIONAL_SLOT_4["furniture_field"]
                download = None
                try:
                    download = self.akeneo.download_media(item.media_code)
                    filename = Path(item.media_code).name or f"{item.sku}.jpg"
                    self.airtable.upload_attachment(record_id, target_field, download, filename)
                    print(f"  [+] Uploaded {item.sku} to '{target_field}'")
                finally:
                    if download:
                        download.cleanup()

            self._update_status(record_id, STATUS_STANDBY)
            duration = round(time.monotonic() - phase_start, 2)
            append_audit_log(
                {
                    "timestamp": pht_timestamp(),
                    "record_id": record_id,
                    "items": [
                        {
                            "slot": idx + 1,
                            "sku": it.sku,
                            "item_name": it.item_name,
                            "media_code": it.media_code,
                        }
                        for idx, it in enumerate(selected_items)
                    ],
                    "category": self.category_code,
                    "style": self.style_code,
                    "table_id": self.table_id,
                    "status": STATUS_STANDBY,
                    "duration_seconds": duration,
                },
                AUDIT_LOG_AKENEO,
            )
            return self.airtable.get_record(record_id)
        except Exception as err:
            append_error_log("new_row", 1, err, {"category": self.category_code, "style": self.style_code})
            raise

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2: KREA AI 3-INTERIOR & THUMBNAIL GENERATION (4:5)
    # ══════════════════════════════════════════════════════════════════════════

    def phase_2(self, record_id: str, *, execute: bool = True) -> bool:
        """Generate 3 distinct 4:5 interior photos (Interior1, Interior2, Interior3) and 1 Thumbnail using Krea AI."""
        print(f"\n[PHASE 2] Krea AI 3-Interior & Thumbnail Generation (4:5) for Record: {record_id}")
        print(f"Interior Moodboard ID : {self.moodboard_id}")
        print(f"Thumbnail Moodboard ID: {self.thumbnail_moodboard_id}")
        print(f"Prompt                : \"{self.interior_prompt}\"")
        print(f"Mode                  : {'EXECUTE' if execute else 'DRY RUN'}")

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})

        self._update_status(record_id, STATUS_PROCESSING)
        phase_start = time.monotonic()
        generated_logs: list[dict[str, Any]] = []

        # 1. Generate 3 Room Interiors (Interior1, Interior2, Interior3)
        for slot in SLOTS:
            target_field = slot.interior_field
            existing_attachment = get_slot_interior_val(fields, slot)
            if existing_attachment:
                print(f"  Slot {slot.slot_index} ('{target_field}'): Already populated, skipping generation.")
                continue

            print(f"\n  [{slot.slot_index}/3] Generating 4:5 interior for '{target_field}'...")
            if not execute:
                print(f"    [DRY RUN] Would generate interior with prompt: \"{self.interior_prompt}\"")
                continue

            slot_start = time.monotonic()
            try:
                url = self.krea.generate(
                    self.interior_prompt,
                    aspect_ratio=KREA_ASPECT_RATIO,
                    resolution=KREA_RESOLUTION,
                    moodboard_id=self.moodboard_id,
                )
                print(f"    [OK] Interior generated: {url}")

                downloaded = self.krea.download_image(url)
                filename = f"interior{slot.slot_index}_{record_id}.jpg"
                try:
                    print(f"    Uploading to Airtable field '{target_field}'...")
                    self.airtable.upload_attachment(record_id, target_field, downloaded, filename)
                    print(f"    [OK] Uploaded to '{target_field}' successfully.")
                finally:
                    downloaded.cleanup()

                slot_duration = round(time.monotonic() - slot_start, 2)
                generated_logs.append({
                    "slot": slot.slot_index,
                    "target_field": target_field,
                    "image_url": url,
                    "moodboard_id": self.moodboard_id,
                    "prompt": self.interior_prompt,
                    "duration_seconds": slot_duration,
                })
            except Exception as err:
                print(f"    [ERROR] Failed interior generation for Slot {slot.slot_index}: {err}")
                append_error_log(record_id, 2, err, {
                    "slot": slot.slot_index,
                    "target_field": target_field,
                    "moodboard_id": self.moodboard_id,
                    "prompt": self.interior_prompt,
                })
                raise

        # 2. Generate Thumbnail (Moodboard: ec860c16-10e4-429e-bba6-ff068bcb80b1 + Claude 5-Word Title + HomeCartel Logo)
        existing_thumb = fields.get(self.thumbnail_field)
        if existing_thumb:
            print(f"  Thumbnail ('{self.thumbnail_field}'): Already populated, skipping generation.")
        else:
            print(f"\n  [Thumbnail] Generating 4:5 exterior thumbnail for '{self.thumbnail_field}' (Moodboard: {self.thumbnail_moodboard_id})...")
            if not execute:
                print(f"    [DRY RUN] Would generate thumbnail with prompt: \"{self.thumbnail_prompt}\", analyze with Claude Sonnet 5 for 5-word title, and stamp HomeCartel logo.")
            else:
                thumb_start = time.monotonic()
                try:
                    url = self.krea.generate(
                        self.thumbnail_prompt,
                        aspect_ratio=KREA_ASPECT_RATIO,
                        resolution=KREA_RESOLUTION,
                        moodboard_id=self.thumbnail_moodboard_id,
                    )
                    print(f"    [OK] Exterior photo generated: {url}")

                    # Step 2a: Generate 5-Word Title via Claude Sonnet 5
                    item_names = [
                        str(fields.get(slot.item_name_field) or "").strip()
                        for slot in SLOTS
                        if str(fields.get(slot.item_name_field) or "").strip()
                    ]
                    print(f"    [+] Analyzing exterior with {FAL_VISION_MODEL} to generate 5-word tips title...")
                    title_text = generate_thumbnail_title_prompt(
                        self.fal,
                        url,
                        item_names=item_names,
                        fixture_label=self.fixture_label,
                        model=FAL_VISION_MODEL,
                    )
                    print(f"    [OK] Generated 5-Word Title: \"{title_text}\"")

                    # Step 2b: Download raw exterior and composite with Title + HomeCartel Logo
                    downloaded = self.krea.download_image(url)
                    raw_path = self._artifact_path(record_id, f"thumbnail_raw_{record_id}.jpg")
                    try:
                        import shutil
                        shutil.copyfile(downloaded.path, raw_path)
                    finally:
                        downloaded.cleanup()

                    # Render centered Poppins Bold title with high visibility
                    with Image.open(raw_path) as raw_img:
                        composed_img = overlay_thumbnail_title(raw_img, title_text)

                        # Step 2c: Stamp HomeCartel Logo
                        logo_path = self._get_logo_path(fields, record_id)
                        if logo_path:
                            print(f"    [+] Stamping HomeCartel logo from '{logo_path}' onto bottom-left (Canva Box: W=190.3, H=63.5, X=108.0, Y=1178.5)...")
                            stamped = stamp_logo(composed_img, logo_path, box=HOMECARTEL_LOGO_BOX)
                            if isinstance(stamped, Image.Image):
                                composed_img = stamped
                        else:
                            print("    [WARN] No HomeCartel logo found; proceeding with title-only thumbnail.")

                        final_thumb_path = self._artifact_path(record_id, f"thumbnail_{record_id}.jpg")
                        composed_img.convert("RGB").save(final_thumb_path, format="JPEG", quality=95)

                    # Step 2d: Upload composite thumbnail to Airtable
                    print(f"    Uploading composite thumbnail with Title & Logo to Airtable field '{self.thumbnail_field}'...")
                    self.airtable.upload_attachment(record_id, self.thumbnail_field, final_thumb_path, f"thumbnail_{record_id}.jpg")
                    print(f"    [OK] Uploaded to '{self.thumbnail_field}' successfully.")

                    # Save title to Airtable if field exists
                    try:
                        known_fields = self.airtable.table_fields()
                        for title_col in ("Thumbnail Title", "Word Generated", "Title"):
                            if title_col in known_fields:
                                self.airtable.update_records([(record_id, {title_col: title_text})])
                                break
                    except Exception:
                        pass

                    thumb_duration = round(time.monotonic() - thumb_start, 2)
                    generated_logs.append({
                        "slot": "thumbnail",
                        "target_field": self.thumbnail_field,
                        "image_url": url,
                        "moodboard_id": self.thumbnail_moodboard_id,
                        "prompt": self.thumbnail_prompt,
                        "title_text": title_text,
                        "logo_stamped": bool(logo_path),
                        "duration_seconds": thumb_duration,
                    })
                except Exception as err:
                    print(f"    [ERROR] Failed thumbnail generation: {err}")
                    append_error_log(record_id, 2, err, {
                        "slot": "thumbnail",
                        "target_field": self.thumbnail_field,
                        "moodboard_id": self.thumbnail_moodboard_id,
                        "prompt": self.thumbnail_prompt,
                    })
                    raise

        if execute and generated_logs:
            total_duration = round(time.monotonic() - phase_start, 2)
            append_audit_log(
                {
                    "timestamp": pht_timestamp(),
                    "record_id": record_id,
                    "phase": "Phase 2: Krea AI Interior & Thumbnail Generation",
                    "interior_moodboard_id": self.moodboard_id,
                    "thumbnail_moodboard_id": self.thumbnail_moodboard_id,
                    "interior_prompt": self.interior_prompt,
                    "thumbnail_prompt": self.thumbnail_prompt,
                    "aspect_ratio": KREA_ASPECT_RATIO,
                    "resolution": KREA_RESOLUTION,
                    "duration_seconds": total_duration,
                    "slots": generated_logs,
                },
                AUDIT_LOG_KREA,
            )

        self._update_status(record_id, STATUS_INTERIOR_ATTACHED)
        print(f"[OK] Phase 2 completed for record {record_id}.")
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3: CLAUDE SONNET 5 PROMPT ANALYSIS (VIA FAL AI)
    # ══════════════════════════════════════════════════════════════════════════

    def phase_3(self, record_id: str, *, execute: bool = True) -> bool:
        """Generate 3 tailored blending prompts using Claude Sonnet 5 via Fal AI."""
        print(f"\n[PHASE 3] Claude Sonnet 5 Prompt Analysis (via Fal AI) for Record: {record_id}")
        print(f"Model       : {FAL_VISION_MODEL}")
        print(f"Fal Key     : {self.fal_key[:8]}...{self.fal_key[-4:] if len(self.fal_key) > 12 else ''}")
        print(f"Mode        : {'EXECUTE' if execute else 'DRY RUN'}")

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})

        self._update_status(record_id, STATUS_PROCESSING)
        phase_start = time.monotonic()
        prompt_updates: dict[str, str] = {}
        log_updates: dict[str, Any] = {}

        for slot in SLOTS:
            prompt_field = slot.prompt_field
            existing_prompt = str(fields.get(prompt_field) or "").strip()
            if existing_prompt:
                print(f"  Slot {slot.slot_index} ('{prompt_field}'): Already populated, skipping.")
                continue

            interior_val = get_slot_interior_val(fields, slot)
            interior_url = extract_attachment_url(interior_val)

            furniture_val = fields.get(slot.furniture_field)
            furniture_url = extract_attachment_url(furniture_val)

            item_name = str(fields.get(slot.item_name_field) or f"{self.fixture_label.title()} {slot.slot_index}").strip()

            if not interior_url or not furniture_url:
                print(f"  [WARN] Slot {slot.slot_index}: Missing interior ({slot.interior_field}) or product ({slot.furniture_field}). Cannot generate prompt.")
                continue

            print(f"\n  [{slot.slot_index}/3] Analyzing {slot.interior_field} + {slot.furniture_field} ('{item_name}') via {FAL_VISION_MODEL}...")
            if not execute:
                print(f"    [DRY RUN] Would generate prompt for {prompt_field}")
                continue

            instruction = (
                f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the Room Interior photo "
                f"and Image 2 as the product photo for '{item_name}'.\n"
                f"Generate a detailed, clean, photorealistic image blending prompt that will place this {item_name} lighting fixture in this room interior.\n\n"
                f"CRITICAL LIGHTING FIXTURE RULES:\n"
                f"1. The {item_name} lighting fixture shown in Image 2 MUST BE THE ONLY LIGHTING FIXTURE in the entire final blended scene.\n"
                f"2. If Image 1 contains ANY pre-existing lighting fixtures, lamps, or secondary light fixtures, REMOVE THEM so that ONLY the exact {item_name} lighting fixture is present in the final photo.\n"
                f"3. Ensure appropriate sizing and ratio of the lighting fixture is observed. No exaggeration.\n"
                f"4. If a ceiling is visible in the generated interior photo, the {item_name} lighting fixture should be properly attached to the ceiling.\n"
                f"5. If there is no ceiling visible, ensure that the {item_name} lighting fixture is properly placed at a natural location.\n"
                f"6. Strictly exclude unnecessary, extra, competing furniture items, human, people, duplicate fixtures, or clutter.\n"
                f"7. Ensure natural hanging height, natural furniture item placement, realistic illumination, soft downward & ambient glow, natural contact shadows on surrounding walls/floors, and authentic materials.\n\n"
                f"Output ONLY the prompt text, with no preamble or markdown quotes."
            )

            slot_start = time.monotonic()
            try:
                raw_prompt = self.fal.generate_vision_prompt(
                    [interior_url, furniture_url],
                    instruction,
                    model=FAL_VISION_MODEL,
                )
                clean_prompt = raw_prompt.strip().strip('"').strip("'")
                slot_duration = round(time.monotonic() - slot_start, 2)
                prompt_updates[prompt_field] = clean_prompt
                log_updates[prompt_field] = {
                    "slot": slot.slot_index,
                    "item_name": item_name,
                    "input_interior_url": interior_url,
                    "input_furniture_url": furniture_url,
                    "prompt": clean_prompt,
                    "model": FAL_VISION_MODEL,
                    "duration_seconds": slot_duration,
                }
                print(f"    [OK] Prompt generated for '{prompt_field}' in {slot_duration}s ({len(clean_prompt)} chars): {clean_prompt[:60]}...")
            except Exception as err:
                print(f"    [ERROR] Claude vision prompt failed for Slot {slot.slot_index}: {err}")
                append_error_log(record_id, 3, err, {
                    "slot": slot.slot_index,
                    "item_name": item_name,
                    "interior_url": interior_url,
                    "furniture_url": furniture_url,
                    "model": FAL_VISION_MODEL,
                })
                raise

        if execute and prompt_updates:
            total_duration = round(time.monotonic() - phase_start, 2)
            self.airtable.update_records([(record_id, prompt_updates)])
            print(f"  [OK] Saved {len(prompt_updates)} prompt(s) to Airtable record {record_id}")
            append_audit_log(
                {
                    "timestamp": pht_timestamp(),
                    "record_id": record_id,
                    "phase": "Phase 3: Claude Sonnet 5 Prompt Analysis (via Fal AI)",
                    "model": FAL_VISION_MODEL,
                    "duration_seconds": total_duration,
                    "prompts": log_updates,
                },
                AUDIT_LOG_CLAUDE,
            )

        self._update_status(record_id, STATUS_INTERIOR_ATTACHED)
        print(f"[OK] Phase 3 completed for record {record_id}.")
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4: FAL AI NANO BANANA PRO BLENDING (4:5 RATIO, 1K QUALITY)
    # ══════════════════════════════════════════════════════════════════════════

    def phase_4(self, record_id: str, *, execute: bool = True) -> bool:
        """Blend 3 products into interiors using Fal AI Nano Banana Pro (4:5 Ratio, 1K Quality) and upload to 'Tips and Edu Blended'."""
        print(f"\n[PHASE 4] Fal AI Nano Banana Pro Blending (4:5 Ratio, 1K Quality) for Record: {record_id}")
        print(f"Model       : {FAL_BLENDING_MODEL}")
        print(f"Aspect Ratio: {BLENDING_ASPECT_RATIO}")
        print(f"Resolution  : {BLENDING_RESOLUTION}")
        print(f"Target Field: '{BLENDED_FIELD}' (Attaching 3 blended photos)")
        print(f"Mode        : {'EXECUTE' if execute else 'DRY RUN'}")

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})

        existing_blended = fields.get(BLENDED_FIELD) or []
        if len(existing_blended) >= 3:
            print(f"[OK] Record {record_id} already has {len(existing_blended)} blended images in '{BLENDED_FIELD}'.")
            self._update_status(record_id, STATUS_COMPLETE)
            return True

        self._update_status(record_id, STATUS_PROCESSING)
        phase_start = time.monotonic()
        blended_paths: list[Path] = []
        blended_log_entries: list[dict[str, Any]] = []
        all_succeeded = True

        for slot in SLOTS:
            interior_val = get_slot_interior_val(fields, slot)
            interior_url = extract_attachment_url(interior_val)

            furniture_val = fields.get(slot.furniture_field)
            furniture_url = extract_attachment_url(furniture_val)

            prompt_raw = str(fields.get(slot.prompt_field) or "").strip()
            item_name = str(fields.get(slot.item_name_field) or f"{self.fixture_label.title()} {slot.slot_index}").strip()

            if not interior_url or not furniture_url or not prompt_raw:
                print(f"  [WARN] Slot {slot.slot_index}: Missing interior, furniture, or prompt. Cannot blend.")
                all_succeeded = False
                continue

            blending_prompt = prompt_raw
            try:
                parsed = json.loads(prompt_raw)
                if isinstance(parsed, dict) and "final_blending_prompt" in parsed:
                    blending_prompt = parsed["final_blending_prompt"]
            except Exception:
                pass

            filename = f"tips_and_edu_blended_{slot.slot_index}_{record_id}.jpg"
            destination = self._artifact_path(record_id, filename)

            print(f"\n  [{slot.slot_index}/3] Blending {slot.furniture_field} ('{item_name}') into {slot.interior_field} via {FAL_BLENDING_MODEL}...")
            if not execute:
                print(f"    [DRY RUN] Would blend with {FAL_BLENDING_MODEL} (aspect_ratio={BLENDING_ASPECT_RATIO}, resolution={BLENDING_RESOLUTION})")
                continue

            slot_start = time.monotonic()
            try:
                print(f"    Sending image blending request to Fal AI Nano Banana Pro...")
                blended_url = self.fal.generate(
                    blending_prompt,
                    [interior_url, furniture_url],
                    aspect_ratio=BLENDING_ASPECT_RATIO,
                    resolution=BLENDING_RESOLUTION,
                    model=FAL_BLENDING_MODEL,
                )
                print(f"    [OK] Blended image generated: {blended_url}")

                self._download(blended_url, destination)
                with Image.open(destination) as img:
                    actual_size = img.size
                blended_paths.append(destination)
                slot_duration = round(time.monotonic() - slot_start, 2)
                print(f"    [OK] Verified & saved local artifact in {slot_duration}s: {destination.name} ({actual_size[0]}x{actual_size[1]})")

                blended_log_entries.append({
                    "slot": slot.slot_index,
                    "item_name": item_name,
                    "furniture_field": slot.furniture_field,
                    "interior_field": slot.interior_field,
                    "prompt_field": slot.prompt_field,
                    "input_interior_url": interior_url,
                    "input_furniture_url": furniture_url,
                    "prompt_used": blending_prompt,
                    "output_image_url": blended_url,
                    "local_path": str(destination),
                    "aspect_ratio": BLENDING_ASPECT_RATIO,
                    "resolution": BLENDING_RESOLUTION,
                    "duration_seconds": slot_duration,
                })
            except Exception as err:
                print(f"    [ERROR] Failed blending Slot {slot.slot_index}: {err}")
                append_error_log(record_id, 4, err, {
                    "slot": slot.slot_index,
                    "item_name": item_name,
                    "interior_url": interior_url,
                    "furniture_url": furniture_url,
                    "prompt": blending_prompt,
                    "model": FAL_BLENDING_MODEL,
                })
                all_succeeded = False

        if execute and blended_paths:
            total_duration = round(time.monotonic() - phase_start, 2)
            print(f"\n  [+] Uploading {len(blended_paths)} blended image(s) to '{BLENDED_FIELD}' on record {record_id}...")
            for path in blended_paths:
                self.airtable.upload_attachment(record_id, BLENDED_FIELD, path, path.name)
                print(f"    [+] Uploaded {path.name} to '{BLENDED_FIELD}'")

            append_audit_log(
                {
                    "timestamp": pht_timestamp(),
                    "record_id": record_id,
                    "phase": "Phase 4: Fal AI Nano Banana Pro Blending",
                    "model": FAL_BLENDING_MODEL,
                    "aspect_ratio": BLENDING_ASPECT_RATIO,
                    "resolution": BLENDING_RESOLUTION,
                    "duration_seconds": total_duration,
                    "target_field": BLENDED_FIELD,
                    "slots": blended_log_entries,
                },
                AUDIT_LOG_FAL_NANO,
            )

        if all_succeeded and len(blended_paths) == 3:
            self._update_status(record_id, STATUS_INTERIOR_ATTACHED)
            print(f"\n[OK] Phase 4 completed for record {record_id}! All 3 Blended images attached to '{BLENDED_FIELD}'.\n")
            return True
        else:
            if not execute:
                print(f"[DRY RUN] Completed simulation for record {record_id}.")
                return True
            self._update_status(record_id, STATUS_INTERIOR_ATTACHED)
            print(f"[WARN] Phase 4 partially failed for record {record_id}.")
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 5: FAL AI NANO BANANA PRO LAYOUT BLENDING -> TIPS AND EDU FEEDS
    # ══════════════════════════════════════════════════════════════════════════

    def phase_5(self, record_id: str, *, execute: bool = True) -> bool:
        """Blend 3 finished blended photos with Layout 1, 2, 3 templates using Fal AI Nano Banana Pro and upload to 'Tips and Edu Feeds'."""
        print(f"\n[PHASE 5] Fal AI Nano Banana Pro Layout Blending for Record: {record_id}")
        print(f"Model       : {FAL_BLENDING_MODEL}")
        print(f"Aspect Ratio: {FINAL_FEED_ASPECT_RATIO}")
        print(f"Resolution  : {FINAL_FEED_RESOLUTION}")
        print(f"Target Field: '{FINAL_FEED_FIELD}' (Attaching 3 final layout feed photos)")
        print(f"Mode        : {'EXECUTE' if execute else 'DRY RUN'}")

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})

        existing_finals = fields.get(FINAL_FEED_FIELD) or []
        if len(existing_finals) >= 3:
            print(f"[OK] Record {record_id} already has {len(existing_finals)} images in '{FINAL_FEED_FIELD}'.")
            self._update_status(record_id, STATUS_COMPLETE)
            return True

        blended_attachments = fields.get(BLENDED_FIELD) or []
        if len(blended_attachments) < 3:
            print(f"[WARN] Record {record_id} has only {len(blended_attachments)}/3 blended images in '{BLENDED_FIELD}'. Cannot run Phase 5.")
            return False

        sorted_blends = sort_attachments_by_slot(blended_attachments)

        self._update_status(record_id, STATUS_PROCESSING)
        phase_start = time.monotonic()
        final_paths: list[Path] = []
        layout_log_entries: list[dict[str, Any]] = []
        all_succeeded = True

        for slot_cfg in LAYOUT_SLOTS:
            slot_idx = slot_cfg.slot_index
            layout_field = slot_cfg.layout_field
            prompt_file = slot_cfg.prompt_file
            fallback_template = slot_cfg.fallback_template

            blend_attachment = sorted_blends[slot_idx - 1] if slot_idx - 1 < len(sorted_blends) else None
            blended_url = extract_attachment_url(blend_attachment)

            if not blended_url:
                print(f"  [WARN] Slot {slot_idx}: Missing blended image from '{BLENDED_FIELD}'.")
                all_succeeded = False
                continue

            layout_attachment = fields.get(layout_field)
            layout_url = extract_attachment_url(layout_attachment)

            if not layout_url:
                if fallback_template and fallback_template.exists():
                    print(f"  Slot {slot_idx}: '{layout_field}' empty in Airtable. Uploading template {fallback_template.name}...")
                    if execute:
                        self.airtable.upload_attachment(record_id, layout_field, fallback_template, fallback_template.name)
                        refreshed = self.airtable.get_record(record_id)
                        fields = refreshed.get("fields", {})
                        layout_url = extract_attachment_url(fields.get(layout_field))
                        print(f"    [OK] Uploaded template to '{layout_field}'.")
                else:
                    print(f"  [WARN] Slot {slot_idx}: Missing layout template for '{layout_field}'.")
                    all_succeeded = False
                    continue

            if not prompt_file.exists():
                print(f"  [ERROR] Slot {slot_idx}: Prompt file not found: {prompt_file}")
                all_succeeded = False
                continue

            layout_prompt = prompt_file.read_text(encoding="utf-8").strip()

            filename = f"tips_and_edu_feed_{slot_idx}_{record_id}.jpg"
            destination = self._artifact_path(record_id, filename)

            print(f"\n  [{slot_idx}/3] Blending '{layout_field}' + Blended Image {slot_idx} via {FAL_BLENDING_MODEL} ({prompt_file.name})...")
            if not execute:
                print(f"    [DRY RUN] Would blend layout using {prompt_file.name} into {FINAL_FEED_FIELD}")
                continue

            slot_start = time.monotonic()
            try:
                print(f"    Sending layout blending request to Fal AI Nano Banana Pro...")
                final_url = self.fal.generate(
                    layout_prompt,
                    [layout_url, blended_url],
                    aspect_ratio=FINAL_FEED_ASPECT_RATIO,
                    resolution=FINAL_FEED_RESOLUTION,
                    model=FAL_BLENDING_MODEL,
                )
                print(f"    [OK] Layout blended image generated: {final_url}")

                self._download(final_url, destination)
                with Image.open(destination) as img:
                    actual_size = img.size
                final_paths.append(destination)
                slot_duration = round(time.monotonic() - slot_start, 2)
                print(f"    [OK] Verified & saved local artifact in {slot_duration}s: {destination.name} ({actual_size[0]}x{actual_size[1]})")

                layout_log_entries.append({
                    "slot": slot_idx,
                    "layout_field": layout_field,
                    "prompt_file": prompt_file.name,
                    "input_layout_url": layout_url,
                    "input_blended_url": blended_url,
                    "output_image_url": final_url,
                    "local_path": str(destination),
                    "aspect_ratio": FINAL_FEED_ASPECT_RATIO,
                    "resolution": FINAL_FEED_RESOLUTION,
                    "duration_seconds": slot_duration,
                })
            except Exception as err:
                print(f"    [ERROR] Failed layout blending Slot {slot_idx}: {err}")
                append_error_log(record_id, 5, err, {
                    "slot": slot_idx,
                    "layout_field": layout_field,
                    "prompt_file": prompt_file.name,
                    "layout_url": layout_url,
                    "blended_url": blended_url,
                    "model": FAL_BLENDING_MODEL,
                })
                all_succeeded = False

        if execute and final_paths:
            total_duration = round(time.monotonic() - phase_start, 2)
            print(f"\n  [+] Uploading {len(final_paths)} final layout image(s) to '{FINAL_FEED_FIELD}' on record {record_id}...")
            for path in final_paths:
                self.airtable.upload_attachment(record_id, FINAL_FEED_FIELD, path, path.name)
                print(f"    [+] Uploaded {path.name} to '{FINAL_FEED_FIELD}'")

            append_audit_log(
                {
                    "timestamp": pht_timestamp(),
                    "record_id": record_id,
                    "phase": "Phase 5: Fal AI Nano Banana Pro Layout Blending",
                    "model": FAL_BLENDING_MODEL,
                    "aspect_ratio": FINAL_FEED_ASPECT_RATIO,
                    "resolution": FINAL_FEED_RESOLUTION,
                    "duration_seconds": total_duration,
                    "target_field": FINAL_FEED_FIELD,
                    "slots": layout_log_entries,
                },
                AUDIT_LOG_LAYOUT,
            )

        if all_succeeded and len(final_paths) == 3:
            self._update_status(record_id, STATUS_COMPLETE)
            print(f"\n[OK] Record {record_id} is 100% COMPLETE! All 3 Final Feed Layouts attached to '{FINAL_FEED_FIELD}'.\n")
            return True
        else:
            if not execute:
                print(f"[DRY RUN] Completed simulation for record {record_id}.")
                return True
            self._update_status(record_id, STATUS_INTERIOR_ATTACHED)
            print(f"[WARN] Phase 5 partially failed for record {record_id}.")
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # RUNNER DISPATCHER
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        phase: int | str = "all",
        target_record_id: str | None = None,
        max_rows: int | None = None,
        execute: bool = True,
    ) -> None:
        """Run complete pipeline or specific phase across target records."""
        self.preflight(execute=execute)

        if str(phase).lower() == "all":
            if target_record_id:
                record = self.airtable.get_record(target_record_id)
                start_phase = self._phase_for_record(record) or 2
                records_to_process = [record]
            else:
                # Find incomplete records
                all_recs = self._records()
                records_to_process = [r for r in all_recs if self._phase_for_record(r) is not None]
                if not records_to_process:
                    print("[INFO] No existing rows need processing. Creating a new row via Phase 1...")
                    new_rec = self.phase_1(execute=execute)
                    if new_rec:
                        records_to_process = [new_rec]

            if max_rows is not None:
                records_to_process = records_to_process[:max_rows]

            print(f"[INFO] Processing {len(records_to_process)} record(s) through remaining phases...")
            for idx, rec in enumerate(records_to_process, start=1):
                rec_id = rec["id"]
                current_phase = self._phase_for_record(self.airtable.get_record(rec_id)) or 2
                print(f"\n>>> [{idx}/{len(records_to_process)}] Processing Record {rec_id} starting at Phase {current_phase} <<<")
                for p_num in range(current_phase, 6):
                    self._run_single_phase(p_num, rec_id, execute=execute)
            return

        phase_num = int(phase)
        if phase_num == 1:
            count = max_rows or 1
            for i in range(count):
                print(f"\n--- Scraping Row {i+1}/{count} ---")
                self.phase_1(execute=execute)
            return

        if target_record_id:
            self._run_single_phase(phase_num, target_record_id, execute=execute)
            return

        # Find eligible records for this phase
        records = self._records()
        targets = [r for r in records if self._phase_for_record(r) == phase_num]
        if not targets:
            print(f"[INFO] No records currently eligible for Phase {phase_num}.")
            return

        if max_rows is not None:
            targets = targets[:max_rows]

        print(f"[INFO] Found {len(targets)} record(s) eligible for Phase {phase_num}.")
        for idx, rec in enumerate(targets, start=1):
            print(f"\n--- [{idx}/{len(targets)}] Processing Record {rec['id']} ---")
            self._run_single_phase(phase_num, rec["id"], execute=execute)

    def _run_single_phase(self, phase: int, record_id: str, *, execute: bool = True) -> None:
        phase_names = {
            1: "Akeneo Scrape",
            2: "Krea AI 3-Interior Photo Generation",
            3: "Claude Sonnet 5 Prompt Analysis (via Fal AI)",
            4: "Fal AI Nano Banana Pro Blending (4:5, 1K Quality)",
            5: "Fal AI Nano Banana Pro Layout Blending -> Tips and Edu Feeds",
        }
        label = phase_names.get(phase, f"Phase {phase}")
        print(f"\n>>> Executing Phase {phase}/5: {label} for Record: {record_id} <<<")
        self.logger.event("phase_started", record_id=record_id, phase=phase, phase_label=label)

        try:
            if phase == 2:
                self.phase_2(record_id, execute=execute)
            elif phase == 3:
                self.phase_3(record_id, execute=execute)
            elif phase == 4:
                self.phase_4(record_id, execute=execute)
            elif phase == 5:
                self.phase_5(record_id, execute=execute)
            self.logger.event("phase_completed", record_id=record_id, phase=phase, phase_label=label)
        except Exception as error:
            append_error_log(record_id, phase, error, {"phase_label": label})
            self.logger.event("phase_failed", record_id=record_id, phase=phase, error=str(error))
            raise



# ── CLI & Argument Parsing ───────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Tips & Edu Feeds (3 Interiors, 3 Products, 3 Blends, 3 Layout Feeds) Automation Pipeline."
    )
    parser.add_argument(
        "--phase",
        "-p",
        choices=("1", "2", "3", "4", "5", "all"),
        default="all",
        help="Phase to run (1..5 or all, default: all).",
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=(
            "chandeliers",
            "pendant_lights",
            "chandelier",
            "pendant",
            "1",
            "2",
        ),
        default=None,
        help="Target category / table preset (1: chandeliers, 2: pendant_lights).",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=("chandeliers", "pendant_lights"),
        default=None,
        help="Akeneo category code override.",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override Airtable Table ID (default: tblEy5batpOObnZ4J for Chandeliers, tblIhCP3Gjg09QFCK for Pendant Lights).",
    )
    parser.add_argument(
        "--record-id",
        "-r",
        default=None,
        help="Target specific Airtable record ID.",
    )
    parser.add_argument(
        "--max-rows",
        "-n",
        type=int,
        default=None,
        help="Process at most N rows.",
    )

    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Krea Moodboard ID override.",
    )
    parser.add_argument(
        "--thumbnail-moodboard-id",
        default=None,
        help="Krea Moodboard ID override for Thumbnail (default: ec860c16-10e4-429e-bba6-ff068bcb80b1).",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Krea interior prompt override.",
    )
    parser.add_argument(
        "--thumbnail-prompt",
        default=None,
        help="Krea thumbnail prompt override (default: from DEFAULT_THUMBNAIL_PROMPT / KREA_PROMPT_TIPS_EDU_THUMBNAIL).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=True,
        help="Execute actions (default: True). Use --dry-run for simulation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_false",
        dest="execute",
        help="Run without calling generation APIs or modifying Airtable.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    preset = resolve_tips_and_edu_preset(
        target_arg=args.target,
        table_id_arg=args.table_id,
        category_arg=args.category,
        prompt_if_interactive=True,
    )

    runner = TipsAndEduFeedRunner(
        preset=preset,
        table_id=args.table_id,
        moodboard_id=args.moodboard_id,
        thumbnail_moodboard_id=args.thumbnail_moodboard_id,
        interior_prompt=args.prompt,
        thumbnail_prompt=args.thumbnail_prompt,
        category_code=args.category,
    )

    print("=" * 70)
    print("        TIPS & EDU FEEDS AUTOMATION PIPELINE        ")
    print("=" * 70)
    print(f" Preset             : {runner.preset.label}")
    print(f" Destination Table  : {runner.table_id}")
    print(f" Category Code      : {runner.category_code}")
    print(f" Krea Moodboard ID  : {runner.moodboard_id}")
    print(f" Thumbnail Moodboard: {runner.thumbnail_moodboard_id}")
    print(f" Interior Prompt    : \"{runner.interior_prompt}\"")
    print(f" Thumbnail Prompt   : \"{runner.thumbnail_prompt}\"")
    print(f" Vision Model       : {FAL_VISION_MODEL} (via Fal AI)")
    print(f" Blending Model     : {FAL_BLENDING_MODEL} ({BLENDING_ASPECT_RATIO}, {BLENDING_RESOLUTION})")
    print(f" Target Phase       : {args.phase}")
    print(f" Execution Mode     : {'EXECUTE' if args.execute else 'DRY RUN'}")
    print("=" * 70)

    runner.run(
        phase=args.phase,
        target_record_id=args.record_id,
        max_rows=args.max_rows,
        execute=args.execute,
    )
    return 0




if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
