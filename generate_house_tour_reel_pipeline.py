#!/usr/bin/env python3
"""House Tour Reel Automation Pipeline (9:16, organic-modern/Japandi home tour).

Target Table: ``tblqXkdDw4O7hxJS4`` -- "House Tour Reel".

This pipeline turns 11 freshly scraped lighting products (one per room) into a
vertical 9:16 home-tour reel: each product is blended into a Krea-generated
organic-modern/Japandi room interior using unified moodboard ID
``fda7090c-787b-4116-94cd-3feef613eaaa`` and video-accurate prompts, each blend
is animated with Fal Kling V3 Turbo Pro (3 s alternating pans), and the clips
are assembled locally with FFmpeg (1 s crossfades, Poppins title overlays,
HomeCartel outro, ElevenLabs music). No caption is written.

Slots (11-room luxury home tour)
--------------------------------
    Slot 1  Living Room Lounge Corner  -- Chandelier   (chandeliers)
    Slot 2  Primary Bedroom            -- Table Lamp   (table_lamps)
    Slot 3  Dining Room Table          -- Pendant      (pendant_lights)
    Slot 4  Kitchen Counter            -- Pendant      (pendant_lights)
    Slot 5  Living Room Central        -- Floor Lamp   (floor_lamps)
    Slot 6  Dining Credenza Wall       -- Wall Light   (wall_sconces)
    Slot 7  Living Room Media Console  -- Table Lamp   (table_lamps)
    Slot 8  Primary Bedroom Dressing   -- Wall Light   (wall_sconces)
    Slot 9  Entryway Foyer             -- Chandelier   (chandeliers)
    Slot 10 Guest Bedroom Bed          -- Ceiling Light (ceiling_mounted)
    Slot 11 Guest Bedroom Dresser      -- Pendant Light (pendant_lights)

Phases (the log prints ``[PHASE n/8]`` markers that the Studio reads)
---------------------------------------------------------------------
    Phase 1  Generate 11 room interiors via Krea AI (krea-2-medium, 9:16, 1K)
             using unified moodboard and video-accurate Interior Prompt1..11
             -> Interior1..11. Status -> "Interior Generated".
    Phase 2  Claude Sonnet 5 Vision analyzes each room interior to determine
             exact mounting placement, lighting/shadow direction, and
             recommended lighting category/materials -> Interior Analysis1..11.
             Status -> "Interior Analyzed".
    Phase 3  Scrape 11 fresh fixtures matching Claude's analysis (Akeneo with
             base-wide dedup + strict Shopify Active & Published check)
             -> Furniture Item1..11, Item Name1..11, SKU1..11.
             Status -> "Standby".
    Phase 4  Blend prompts (Fal Claude Sonnet ``anthropic/claude-sonnet-5``)
             combining room, product, and Phase 2 Interior Analysis
             -> Generated Prompt1..11. Status -> "Prompt Generated".
    Phase 5  Blend (Fal Nano Banana Pro ``fal-ai/nano-banana-pro/edit``,
             9:16, 1K) + YOLO-World Poppins item-name tags
             (``Blended Image with Name text``) -> Blended Image1..11.
             Status -> "Blended Image Generated".
    Phase 6  Motion clips (Fal Kling V3 Turbo Pro image-to-video,
             3s each, alternating left/right pans) -> Kling Video1..11.
             Status -> "Kling Video Generated" (or "Generation Failed Via Kling").
    Phase 7  Background music (Fal ElevenLabs Music
             ``fal-ai/elevenlabs/music``) -> Music Generated.
             Status -> "Music Generated".
    Phase 8  Reel assembly (local FFmpeg: 1s crossfades, Poppins title
             overlays, HomeCartel outro, music mux)
             -> Final Video. Status -> "Done".

Usage::

    # ONE row, end to end (scrape 11 fresh fixtures, build its reel, stop):
    python generate_house_tour_reel_pipeline.py --phase all

    # Multiple rows:
    python generate_house_tour_reel_pipeline.py --phase all --max-rows 3

    # Just scrape new 11-fixture groups into Airtable (no video):
    python generate_house_tour_reel_pipeline.py --phase scrape --max-rows 1

    # Re-render one explicit row (the ONLY way to touch an existing row):
    python generate_house_tour_reel_pipeline.py --record-id recXXXXXXXX
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import urllib.request
import requests

from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.media import attachment_filename
from content_automation.shopify_client import ShopifyClient
from content_automation.scraping import categories
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import fetch_all_base_existing_identities
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    identity_key,
    select_new_products,
)

# --------------------------------------------------------------------------
# Constants -- table layout & engines
# --------------------------------------------------------------------------

DEFAULT_TABLE_ID = "tblqXkdDw4O7hxJS4"
TABLE_ENV_KEY = "AIRTABLE_TABLE_ID_HOUSE_TOUR_REEL"

REPO_ROOT = Path(__file__).resolve().parent

DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"

SLOTS = tuple(range(1, 12))
SLOT_CATEGORIES: dict[int, str] = {
    1: "chandeliers",
    2: "table_lamps",
    3: "pendant_lights",
    4: "pendant_lights",
    5: "floor_lamps",
    6: "wall_sconces",
    7: "table_lamps",
    8: "wall_sconces",
    9: "chandeliers",
    10: "ceiling_mounted",
    11: "pendant_lights",
}
SLOT_LABELS: dict[int, str] = {
    1: "Chandelier",
    2: "Table Lamp",
    3: "Pendant Light",
    4: "Pendant Light",
    5: "Floor Lamp",
    6: "Wall Light",
    7: "Table Lamp",
    8: "Wall Light",
    9: "Chandelier",
    10: "Ceiling Light",
    11: "Pendant Light",
}
SLOT_ROOMS: dict[int, str] = {
    1: "Living Room Lounge Corner",
    2: "Primary Bedroom",
    3: "Dining Room Table",
    4: "Kitchen Counter",
    5: "Living Room Central",
    6: "Dining Credenza Wall",
    7: "Living Room Media Console",
    8: "Primary Bedroom Dressing",
    9: "Entryway Foyer",
    10: "Guest Bedroom Bed",
    11: "Guest Bedroom Dresser",
}

# Unified Moodboard ID for all 11 rooms (organic-modern Japandi)
DEFAULT_MOODBOARD_ID = "fda7090c-787b-4116-94cd-3feef613eaaa"
SLOT_MOODBOARD_DEFAULTS: dict[int, str] = {s: DEFAULT_MOODBOARD_ID for s in SLOTS}

# Env keys the Studio card's per-room moodboard pencils write
# (see UI Control/routes/house_tour_reel.py ROOMS[...]["moodboard_env"]).
GENERIC_MOODBOARD_ENV_KEY = "KREA_MOODBOARD_ID_HOUSE_TOUR_REEL"


def room_moodboard_env_key(slot: int) -> str:
    return f"{GENERIC_MOODBOARD_ENV_KEY}_ROOM{slot}"


# 11 Ultra-detailed reusable prompts derived frame-by-frame from assets/house_tour_reference.mp4
DEFAULT_INTERIOR_PROMPTS: dict[int, str] = {
    1: (
        "Generate me a photo of an organic modern Japandi living room lounge corner, "
        "low-profile cream off-white boucle sofa with dark brown check cushion, dark espresso hardwood flooring, "
        "sculptural carved dark wood stool side table, leaning asymmetrical wavy brass floor mirror, "
        "tall rustic earthenware clay vase with delicate budding plum blossom branches, "
        "floor-to-ceiling sheer white pleated linen drapes diffusing soft morning light, warm cream matte plaster wall, "
        "with clean open ceiling space ready for a luxury chandelier, photorealistic 8k, serene wabi-sabi interior"
    ),
    2: (
        "Generate me a photo of an organic modern Japandi primary bedroom main bed wall, "
        "solid dark walnut low-profile platform bed with smooth rounded-edge headboard, "
        "textured dark espresso linen duvet and sheets with an extra-long ribbed beige lumbar bolster pillow, "
        "diptych of two dark-framed minimalist abstract earth-tone art canvases centered above headboard, "
        "bedside nightstand on right with empty surface ready for a designer table lamp, cylindrical drum nightstand on left, "
        "floor-to-ceiling dark taupe drapes, plush cream rug, photorealistic 8k, luxury peaceful bedroom"
    ),
    3: (
        "Generate me a photo of an organic modern Japandi dining room, "
        "rounded-corner dining table with white matte tabletop and sculptural dark walnut curved A-frame legs, "
        "surrounded by Hans Wegner CH24 Wishbone chairs in dark walnut with natural rush woven seats, "
        "dark smoked glass footed centerpiece bowl, textured warm brown area rug over dark flooring, "
        "background view of integrated matte taupe kitchen cabinetry and arched mirror, "
        "clean ceiling space centered directly above the dining table ready for a suspended pendant light, photorealistic 8k"
    ),
    4: (
        "Generate me a photo of an organic modern Japandi kitchen corner and coffee station, "
        "two-tone custom cabinetry with matte dark taupe flat-panel upper cabinets and textured vertical-grain natural oak lower drawers "
        "with slim brass pulls, polished white quartz countertops, glossy beveled white subway tile backsplash, "
        "corner styled with a two-tier wooden tea shelf displaying ceramic canisters and bamboo matcha whisk, "
        "clean countertop corner ready for a designer table lamp, warm under-cabinet task lighting, photorealistic 8k"
    ),
    5: (
        "Generate me a photo of an organic modern Japandi living room central seating area, "
        "curved low-profile cream linen sofa with chocolate velvet throw pillow and woven fringe blanket, "
        "minimalist dark walnut rectangular coffee table styled with art books and ceramic tray, "
        "curved dark olive velvet ottoman daybed, tall potted indoor Dracaena tree in dark minimalist ceramic planter, "
        "textured earth-toned relief plaster canvas art on warm beige wall, leaning arched brass mirror, "
        "plush neutral area rug over dark flooring, with clean open ceiling space ready for a chandelier, photorealistic 8k"
    ),
    6: (
        "Generate me a photo of an organic modern Japandi dining room credenza wall, "
        "edge of walnut dining table with Wishbone chairs, wall-mounted dark wood multi-grid shadow box display shelf "
        "showcasing artisanal ceramic teacups, fluted dark walnut slatted console table in background, "
        "slender black pedestal vase with dried botanical stems, textured beige limewash walls, "
        "empty floor and console space ready for a lighting fixture, warm ambient afternoon lighting, photorealistic 8k"
    ),
    7: (
        "Generate me a photo of an organic modern Japandi living room media wall, "
        "wall-mounted slim flat-screen television, long low-profile dark walnut credenza with minimalist tab pulls, "
        "styled with ceramic sculpture on marble tray, empty tabletop surface on the credenza ready for a designer table lamp, "
        "woven paper cord Hans Wegner style accent armchair in corner, textured low-pile beige rug over dark wood floor, "
        "warm beige matte plaster walls, soft natural daylight from side doorway, photorealistic 8k"
    ),
    8: (
        "Generate me a photo of an organic modern Japandi primary bedroom dressing nook, "
        "symmetrical floor-to-ceiling heavy taupe linen drapery hanging from black curtain rods, "
        "standing arched oak-framed floor mirror, rounded matte black fluted ceramic pot with a lush snake plant, "
        "mirror reflection showing a walnut platform bed with mocha linen bedding and abstract art diptych, "
        "empty wall space ready for a wall light, soft morning light filtering through linen, photorealistic 8k"
    ),
    9: (
        "Generate me a photo of an organic modern Japandi entryway foyer, "
        "dark walnut console cabinet with rounded waterfall edges, large organic pebble-shaped wavy brass wall mirror, "
        "weathered wabi-sabi clay pottery vase with tall budding branch stems, smooth matte off-white plaster walls, "
        "empty tabletop surface on the console ready for an illuminated designer table lamp, "
        "warm moody ambient interior lighting, soft shadows, photorealistic 8k, luxury residential entry"
    ),
    10: (
        "Generate me a photo of an organic modern Japandi guest bedroom, "
        "dark stained wood platform bed frame with inset headboard and sled base, rich warm brown linen duvet "
        "with a velvet dusty terracotta accent pillow, dark walnut bedside nightstand with ceramic pitcher vase holding dry branches, "
        "empty bedside nightstand surface ready for a luxury table lamp, "
        "floor-to-ceiling sheer white linen curtains with bright soft daylight streaming through, "
        "dark textured grid-patterned carpet, minimalist framed artwork on neutral plaster wall, photorealistic 8k"
    ),
    11: (
        "Generate me a photo of an organic modern Japandi guest bedroom dresser wall, "
        "rich fluted dark walnut six-drawer dresser with horizontal brushed brass tab pulls, "
        "large floating organic wavy pebble-shaped wall mirror with slim brass trim reflecting curtained window light, "
        "surface of dresser styled with ceramic dish and dry botanical stems, with open spot ready for a designer table lamp, "
        "cream boucle accent chair beside dresser, dark textured grid area rug, warm natural daylight, photorealistic 8k"
    ),
}
SLOT_PROMPT_DEFAULTS = DEFAULT_INTERIOR_PROMPTS
INTERIOR_ASPECT_RATIO = "9:16"
INTERIOR_RESOLUTION = "1K"


# Fal Claude Sonnet (Phase 3)
CLAUDE_MODEL = "anthropic/claude-sonnet-5"

# Fal Nano Banana Pro (Phase 4)
NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"
BLEND_ASPECT_RATIO = "9:16"
BLEND_RESOLUTION = "1K"

# Local FFmpeg assembly (Phase 8)
OUTRO_SECONDS = 2.5
POPPINS_BOLD = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Bold.ttf"
POPPINS_REGULAR = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Regular.ttf"
POPPINS_MEDIUM = REPO_ROOT / "content_automation" / "fonts" / "Poppins-Medium.ttf"

# Pacing modes
PACING_REFERENCE = "reference"
PACING_RELAXED = "relaxed"
DEFAULT_PACING = PACING_REFERENCE

# Transition cut styles
CUT_STYLE_SNAP = "snap"
CUT_STYLE_DISSOLVE = "dissolve"
DEFAULT_CUT_STYLE = CUT_STYLE_SNAP

# Overlay typography styles
OVERLAY_STYLE_REFERENCE = "reference"
OVERLAY_STYLE_TAG = "tag"
OVERLAY_STYLE_HYBRID = "hybrid"
DEFAULT_OVERLAY_STYLE = OVERLAY_STYLE_REFERENCE

# Reference pacing: 2.0 seconds per room across 11 rooms (22.0s total runtime)
REFERENCE_SHOT_DURATIONS: list[float] = [2.0] * len(SLOTS)
REFERENCE_TOTAL_SECONDS: float = sum(REFERENCE_SHOT_DURATIONS)  # 22.0
KLING_TRIM_START: float = 0.5  # Trim 0.5s..2.5s from 3.0s Kling motion clip for smooth constant velocity

# Upper-third chic lowercase Poppins title settings (matching reference reel)
REFERENCE_TITLE_FONT = POPPINS_MEDIUM
REFERENCE_TITLE_FONT_SIZE = 44
REFERENCE_TITLE_TEXT_Y = 480  # Upper-third (y ~ 25% on 1080x1920)
# Note: Zero default room style fallbacks. If Claude Vision fails or is empty,
# upper-third title text is completely omitted.

# Lower-third animated item name settings
PRODUCT_NAME_FONT = POPPINS_MEDIUM
PRODUCT_NAME_FONT_SIZE = 32
PRODUCT_NAME_TEXT_Y = 1600  # Lower-third (above captions and platform UI)
PRODUCT_ANIM_DELAY = 0.25   # seconds after shot cut before reveal starts
PRODUCT_ANIM_DURATION = 0.30  # seconds fade/slide duration
PRODUCT_ANIM_OFFSET_Y = 20  # pixels to slide upward into position

# Legacy title-card spec mirroring the "Blended Image with Name text" YOLO tag
# (item_tagger.render_item_name_tag): Poppins, solid white, no shadow,
# item name Bold, product type Regular, lower-right reel geometry.
TITLE_FONT_SIZE = 18
TYPE_FONT_SIZE = 18
TAG_RIGHT_MARGIN = 180
TAG_BOTTOM_MARGIN = 320
TAG_LINE_SPACING = 5

# HomeCartel outro
OUTRO_CANDIDATES = [
    REPO_ROOT / "Outro for All Reels" / "Outro.jpg",
    REPO_ROOT / "assets" / "outro_layout.jpg",
    Path("Outro for All Reels/Outro.jpg"),
    Path("assets/outro_layout.jpg"),
]
OUTRO_FIELD = "Outro"

# Background music (Fal AI ElevenLabs Music). Default: ON for House Tour.
# Set HOUSE_TOUR_MUSIC_ENABLED=false in .env or pass --no-music for silent.
_MUSIC_ENV = os.getenv("HOUSE_TOUR_MUSIC_ENABLED", "true").strip().lower()
MUSIC_ENABLED = _MUSIC_ENV not in ("false", "0", "no", "off")
MUSIC_MODEL = "fal-ai/elevenlabs/music"
MUSIC_PROMPT = (
    "Warm organic-modern home tour instrumental, soft acoustic guitar, "
    "gentle ambient pads, calm Japandi boutique vibe, seamless loop"
)
MUSIC_DURATION = 24  # seconds (covers 22.0s reel and 24.5s with outro)

# Fal Kling V3 Turbo Pro image-to-video (Phase 5): 3 s per blend,
# alternating pan directions across the rooms (odd slots pan left).
KLING_MODEL = "fal-ai/kling-video/v3/turbo/pro/image-to-video"
KLING_DURATION = 3  # seconds (DurationEnum "3" is valid per fal.ai schema)
KLING_DIRECTIONS: dict[int, str] = {
    slot: ("left" if slot % 2 == 1 else "right") for slot in SLOTS
}
KLING_MAX_ATTEMPTS = 2

# Local FFmpeg reel assembly: dimensions & legacy timings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
CLIP_SECONDS = 3.0
XFADE_SECONDS = 1.0

# Airtable field names for tblqXkdDw4O7hxJS4
STATUS_FIELD = "Status"
STATUS_STANDBY = "Standby"
STATUS_IN_PROGRESS = "In progress"
STATUS_INTERIOR = "Interior Generated"
STATUS_INTERIOR_ANALYZED = "Interior Analyzed"
STATUS_PROMPT = "Prompt Generated"
STATUS_BLENDED = "Blended Image Generated"
STATUS_KLING = "Kling Video Generated"
STATUS_KLING_FAILED = "Generation Failed Via Kling"
STATUS_MUSIC = "Music Generated"
STATUS_DONE = "Done"
STATUS_OPTIONS = [
    STATUS_STANDBY,
    STATUS_IN_PROGRESS,
    STATUS_INTERIOR,
    STATUS_INTERIOR_ANALYZED,
    STATUS_PROMPT,
    STATUS_BLENDED,
    STATUS_KLING,
    STATUS_KLING_FAILED,
    STATUS_MUSIC,
    STATUS_DONE,
    "Complete",
    "Posted",
    "Scheduled",
    "Discard",
    "For Manual",
]

FURNITURE_FIELDS = {s: f"Furniture Item{s}" for s in SLOTS}
ITEM_NAME_FIELDS = {s: f"Item Name{s}" for s in SLOTS}
SKU_FIELDS = {s: f"SKU{s}" for s in SLOTS}
INTERIOR_FIELDS = {s: f"Interior{s}" for s in SLOTS}
INTERIOR_PROMPT_FIELDS = {s: f"Interior Prompt{s}" for s in SLOTS}
INTERIOR_ANALYSIS_FIELDS = {s: f"Interior Analysis{s}" for s in SLOTS}
PROMPT_FIELDS = {s: f"Generated Prompt{s}" for s in SLOTS}
BLENDED_FIELDS = {s: f"Blended Image{s}" for s in SLOTS}
KLING_FIELDS = {s: f"Kling Video{s}" for s in SLOTS}
TAGGED_FIELD = "Blended Image with Name text"
MUSIC_FIELD = "Music Generated"
FINAL_VIDEO_FIELD = "Final Video"
INTERIOR_PROMPT_FIELD = "Interior Prompt"
MOODBOARD_FIELD = "Moodboard ID"

REQUIRED_FIELDS: dict[str, str] = {
    "Foreign Key ID": "singleLineText",
    INTERIOR_PROMPT_FIELD: "multilineText",
    MOODBOARD_FIELD: "singleLineText",
    MUSIC_FIELD: "multipleAttachments",
    OUTRO_FIELD: "multipleAttachments",
    FINAL_VIDEO_FIELD: "multipleAttachments",
    TAGGED_FIELD: "multipleAttachments",
    STATUS_FIELD: "singleSelect",
    **{FURNITURE_FIELDS[s]: "multipleAttachments" for s in SLOTS},
    **{ITEM_NAME_FIELDS[s]: "singleLineText" for s in SLOTS},
    **{SKU_FIELDS[s]: "multilineText" for s in SLOTS},
    **{INTERIOR_FIELDS[s]: "multipleAttachments" for s in SLOTS},
    **{INTERIOR_PROMPT_FIELDS[s]: "multilineText" for s in SLOTS},
    **{INTERIOR_ANALYSIS_FIELDS[s]: "multilineText" for s in SLOTS},
    **{PROMPT_FIELDS[s]: "multilineText" for s in SLOTS},
    **{BLENDED_FIELDS[s]: "multipleAttachments" for s in SLOTS},
    **{KLING_FIELDS[s]: "multipleAttachments" for s in SLOTS},
}

ALL_READ_FIELDS = [
    STATUS_FIELD,
    *FURNITURE_FIELDS.values(),
    *ITEM_NAME_FIELDS.values(),
    *SKU_FIELDS.values(),
    *INTERIOR_FIELDS.values(),
    *INTERIOR_PROMPT_FIELDS.values(),
    *INTERIOR_ANALYSIS_FIELDS.values(),
    *PROMPT_FIELDS.values(),
    *BLENDED_FIELDS.values(),
    *KLING_FIELDS.values(),
    TAGGED_FIELD,
    MUSIC_FIELD,
    OUTRO_FIELD,
    FINAL_VIDEO_FIELD,
    INTERIOR_PROMPT_FIELD,
    MOODBOARD_FIELD,
]

PRODUCTS_PER_ROW = len(SLOTS)


def _interior_analysis_instruction(slot: int) -> str:
    room = SLOT_ROOMS[slot]
    opening_hint = (
        "For the opening room (slot 1), you may suggest 'mini home tour' or 'mini home tour • living room'.\n"
        if slot == 1
        else ""
    )
    return (
        f"You are a luxury interior lighting architect inspecting a generated organic-modern Japandi {room.lower()} photograph.\n"
        f"{opening_hint}"
        "Carefully analyze the spatial composition and determine the optimal lighting fixture to elevate this space.\n"
        "Respond with concise, structured analysis covering:\n"
        "1. RECOMMENDED CATEGORY: Specify exactly one lighting type from: "
        "[chandeliers, pendant_lights, table_lamps, floor_lamps, wall_sconces, ceiling_mounted].\n"
        "2. PHYSICAL PLACEMENT: Precise placement coordinates (e.g., centered above dining table, "
        "on the right bedside nightstand table surface, standing in the rear left corner beside sofa, "
        "mounted on wall at eye level beside mirror).\n"
        "3. DESIGN & FINISH: Recommended architectural materials and silhouette "
        "(e.g., brushed warm brass, fluted smoked glass, raw travertine, organic ceramic) to harmonize with the room's textures.\n"
        "4. LIGHTING INTEGRATION: Ambient illumination, color temperature, and realistic shadow direction.\n"
        "5. ROOM TITLE: A concise, chic 2-3 word lowercase editorial title for this specific room "
        "(e.g., 'mini home tour', 'living room lounge', 'dining nook', 'kitchen island', 'primary suite', 'guest bedroom').\n"
        "Keep the full analysis concise and actionable (under 130 words)."
    )


def extract_category_from_analysis(analysis_text: str, default_category: str) -> str:
    """Extract recommended category from Claude's analysis text."""
    import re
    text = (analysis_text or "").lower().replace("_", " ")
    match = re.search(r"recommended\s+category\s*:\s*([^\n\r.]+)", text, re.IGNORECASE)
    target = match.group(1).strip().lower() if match else text

    category_map = {
        "chandelier": "chandeliers",
        "pendant": "pendant_lights",
        "table lamp": "table_lamps",
        "floor lamp": "floor_lamps",
        "wall sconce": "wall_sconces",
        "wall light": "wall_sconces",
        "ceiling mount": "ceiling_mounted",
        "ceiling light": "ceiling_mounted",
    }
    for keyword, cat in category_map.items():
        if keyword in target:
            return cat
    for keyword, cat in category_map.items():
        if keyword in text:
            return cat
    return default_category


def extract_room_title_from_analysis(
    analysis_text: str, slot: int = 0, default_title: str = ""
) -> str:
    """Extract a chic lowercase room title from Claude's analysis text.

    Looks for '5. ROOM TITLE: ...' or 'ROOM TITLE: ...'.
    Returns empty string if Claude Vision did not identify a room title.
    NO hardcoded room style fallback!
    """
    import re
    if not analysis_text:
        return default_title.strip().lower() if default_title else ""

    match = re.search(
        r"(?:5\.\s*)?(?:editorial\s+)?room\s+title\s*:\s*([^\n\r.]+)",
        analysis_text,
        re.IGNORECASE,
    )
    if match:
        val = match.group(1).strip().lower()
        val = re.sub(r'["\']', '', val).strip()
        if val:
            return val

    # If Claude Vision didn't explicitly identify a room title, do not fallback to defaults.
    return default_title.strip().lower() if default_title else ""


def _claude_instruction(slot: int, analysis_notes: str = "") -> str:
    room = SLOT_ROOMS[slot]
    label = SLOT_LABELS[slot]
    placement = {
        1: "mounted centered on the ceiling with realistic canopy contact",
        2: "on the bedside nightstand surface",
        3: "suspended over the dining table at proper hanging height",
        4: "suspended over the kitchen counter or island at proper hanging height",
        5: "standing upright on the floor beside the lounge seating",
        6: "mounted flush against the wall at eye level",
        7: "on the credenza surface",
        8: "mounted on the wall beside the vanity mirror",
        9: "mounted centered on the entryway ceiling",
        10: "flush-mounted centered on the ceiling",
        11: "suspended at proper hanging height over the bed or desk",
    }[slot]
    base = (
        "You are a product-photography prompt engineer. Look at the two images: "
        f"the first is an organic-modern Japandi {room.lower()} interior, the second "
        f"is a {label.lower()} product. "
    )
    if analysis_notes and analysis_notes.strip():
        base += f"\nRoom Interior Analysis & Placement Guidance:\n{analysis_notes.strip()}\n"
    base += (
        "Write a single detailed image-editing prompt (no preamble, no markdown) that "
        f"instructs an image model to place this exact {label.lower()} naturally into "
        f"the {room.lower()} ({placement}), keeping the fixture's shape, colour and "
        "proportions identical, with photorealistic warm lighting, soft shadows and a "
        "cohesive organic-modern Japandi mood. Do not change the product design."
    )
    return base


def kling_motion_prompt(slot: int) -> str:
    """Deterministic Kling image-to-video prompt for a room slot.

    The move comes purely from the alternating pan pattern (odd slots pan
    left, even slots pan right): no extra API call. Keeps the fixture
    perfectly still while the camera glides across the room.
    """
    direction = KLING_DIRECTIONS[slot]
    move = (
        "slow smooth cinematic pan from right to left"
        if direction == "left"
        else "slow smooth cinematic pan from left to right"
    )
    room = SLOT_ROOMS[slot].lower()
    label = SLOT_LABELS[slot].lower()
    return (
        f"A {move} across this organic-modern Japandi {room} interior, gently "
        f"revealing the space around the {label}. The {label} itself stays "
        "perfectly still and identical in shape, colour and proportions. "
        "Warm natural light, photorealistic interior videography, no people, "
        "no text, no new objects appearing."
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _first_attachment_url(fields: dict[str, Any], field_name: str) -> str:
    value = fields.get(field_name)
    if isinstance(value, list) and value:
        return str(value[0].get("url") or "")
    return ""


def resolve_outro_file() -> Path | None:
    for cand in OUTRO_CANDIDATES:
        if cand.is_file():
            return cand.resolve()
    return None


class Clients:
    def __init__(self, table_id: str | None = None) -> None:
        self.settings = load_settings()
        resolved_table = table_id or os.getenv(TABLE_ENV_KEY, "").strip() or DEFAULT_TABLE_ID
        self.table_id = resolved_table
        self.airtable = ScrapeAirtableClient(
            self.settings.airtable_token,
            self.settings.airtable_base_id,
            resolved_table,
        )
        self.krea = KreaClient(
            token=self.settings.krea_token,
            base_url=self.settings.krea_base_url,
        )
        self.fal = FalClient(api_key=self.settings.fal_key)

    def akeneo(self) -> AkeneoClient:
        return AkeneoClient(
            host=os.getenv("AKENEO_HOST", ""),
            client_id=os.getenv("AKENEO_CLIENT_ID", ""),
            secret=os.getenv("AKENEO_SECRET", ""),
            username=os.getenv("AKENEO_USERNAME", ""),
            password=os.getenv("AKENEO_PASSWORD", ""),
            channel_name=os.getenv("CHANNEL_NAME", ""),
        )


def _ensure_schema(clients: Clients) -> None:
    clients.airtable.ensure_fields(REQUIRED_FIELDS)
    clients.airtable.ensure_single_select_options(STATUS_FIELD, STATUS_OPTIONS)
    print("[OK] Airtable schema ready (fields + Status options).")


# --------------------------------------------------------------------------
# Phase 1 -- Scrape 11 fresh fixtures (one per room slot)
# --------------------------------------------------------------------------


def _scrape_candidates_for_slot(
    clients: Clients,
    akeneo: AkeneoClient,
    slot: int,
    style: str,
    needed: int,
    all_existing_filenames: set[str],
    all_existing_names: set[str],
    all_existing_skus: set[str],
    shopify_index: Any | None,
    category_override: str | None = None,
) -> list[ProductItem]:
    category = category_override or SLOT_CATEGORIES[slot]
    akeneo_category = categories.akeneo_category_code(category)
    query: dict[str, Any] = {
        "categories": [{"operator": "IN", "value": [akeneo_category]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    if style and style.lower() != "all":
        query["Style2"] = [{"operator": "IN", "value": [style]}]

    print(f"[INFO] Fetching {style} {category} products from Akeneo (slot {slot}: {SLOT_ROOMS[slot]})...")
    products = akeneo.fetch_products(query)

    existing_names_query, existing_media_query = existing_product_identities(
        products, all_existing_skus
    )
    combined_names = all_existing_names | existing_names_query

    selected, _stats = select_new_products(
        products,
        all_existing_skus,
        existing_item_names=combined_names,
        existing_media_codes=existing_media_query,
        category_code=category,
    )

    candidates: list[ProductItem] = []
    for item in selected:
        fn = attachment_filename(item.item_name, item.media_code)
        if identity_key(fn) in all_existing_filenames:
            print(f"[DEDUP SKIP] Existing photo: '{item.item_name}' (SKU: {item.sku})")
            continue
        if item.sku and item.sku.strip() in all_existing_skus:
            print(f"[DEDUP SKIP] Existing SKU: '{item.item_name}' (SKU: {item.sku})")
            continue
        if (item.item_name or "").strip().lower() in all_existing_names:
            print(f"[DEDUP SKIP] Existing Name: '{item.item_name}'")
            continue
        if shopify_index is not None:
            try:
                live = shopify_index.contains(item.sku, item.item_name)
            except Exception:
                live = True
            if not live:
                print(
                    f"[SHOPIFY DRAFT/INACTIVE SKIP] Item '{item.item_name}' (SKU: {item.sku}) "
                    "is not active on Shopify -> skipping"
                )
                continue

        print(f"[DEDUP PASS] New unique {category} product selected: '{item.item_name}' (SKU: {item.sku})")
        candidates.append(item)
        all_existing_filenames.add(identity_key(fn))
        if item.sku:
            all_existing_skus.add(item.sku.strip())
        all_existing_names.add((item.item_name or "").strip().lower())
        if len(candidates) >= needed:
            break

    return candidates


def _plan_new_groups(
    clients: Clients, akeneo: AkeneoClient, style: str, num_rows: int
) -> list[list[ProductItem]]:
    # 1. Base-wide dedup across all 60+ tables.
    try:
        base_filenames, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
        print(
            f"[INFO] Cross-table deduplication active: {len(base_skus)} existing SKU(s), "
            f"{len(base_names)} item name(s), {len(base_filenames)} attachment filename(s)."
        )
    except Exception as error:
        print(f"[WARN] Base deduplication fetch notice: {error}")
        base_filenames, base_names, base_skus = set(), set(), set()

    all_existing_filenames = set(base_filenames)
    all_existing_names = set(base_names)
    all_existing_skus = set(base_skus)

    # 2. Identities already in this table.
    for record in clients.airtable.list_records(list(ALL_READ_FIELDS)):
        row = record.get("fields", {})
        for field_map in (ITEM_NAME_FIELDS, SKU_FIELDS):
            for fname in field_map.values():
                val = str(row.get(fname) or "").strip()
                if val:
                    (all_existing_names if field_map is ITEM_NAME_FIELDS else all_existing_skus).add(
                        val.lower() if field_map is ITEM_NAME_FIELDS else val
                    )
        for fname in FURNITURE_FIELDS.values():
            att_list = row.get(fname)
            if isinstance(att_list, list):
                for a in att_list:
                    if isinstance(a, dict) and a.get("filename"):
                        all_existing_filenames.add(identity_key(a["filename"]))

    # 3. Shopify published catalog (strict Active & Published).
    shopify_index = None
    try:
        print("[INFO] Loading published catalog from Shopify (homecartel.net)...")
        shopify_index = ShopifyClient().load_published_identities()
        print("[OK] Shopify Index Ready (published identities indexed).")
    except Exception as error:
        print(f"[WARN] Shopify index check skipped: {error}")

    slot_candidates: dict[int, list[ProductItem]] = {}
    for slot in SLOTS:
        items = _scrape_candidates_for_slot(
            clients,
            akeneo,
            slot=slot,
            style=style,
            needed=num_rows,
            all_existing_filenames=all_existing_filenames,
            all_existing_names=all_existing_names,
            all_existing_skus=all_existing_skus,
            shopify_index=shopify_index,
        )
        slot_candidates[slot] = items
        print(f"[INFO] Slot {slot} ({SLOT_CATEGORIES[slot]}): found {len(items)}/{num_rows} candidate(s).")

    available = min(len(slot_candidates[s]) for s in SLOTS)
    if available == 0:
        return []
    return [[slot_candidates[slot][i] for slot in SLOTS] for i in range(available)]


def _display_name(item: ProductItem) -> str:
    name = (item.item_name or "").strip()
    ptype = (item.product_type or "").strip()
    if ptype and ptype.lower() not in name.lower():
        return f"{name} | {ptype}"
    return name


def _create_row(
    clients: Clients,
    items: list[ProductItem] | None = None,
    akeneo: AkeneoClient | None = None,
) -> str | None:
    fields: dict[str, Any] = {
        STATUS_FIELD: STATUS_STANDBY,
        MOODBOARD_FIELD: DEFAULT_MOODBOARD_ID,
        INTERIOR_PROMPT_FIELD: DEFAULT_INTERIOR_PROMPTS[1],
    }
    for slot in SLOTS:
        fields[INTERIOR_PROMPT_FIELDS[slot]] = DEFAULT_INTERIOR_PROMPTS[slot]
    if items:
        for slot, item in zip(SLOTS, items):
            fields[ITEM_NAME_FIELDS[slot]] = _display_name(item)
            fields[SKU_FIELDS[slot]] = item.sku or ""
    try:
        record_id = clients.airtable.create_record(fields)
    except Exception as error:
        print(f"[ERROR] Could not create row: {error}")
        return None

    if items and akeneo:
        ok = True
        for slot, item in zip(SLOTS, items):
            try:
                downloaded = akeneo.download_media(item.media_code)
                filename = f"{item.sku or 'fixture'}_{item.media_code}.jpg"
                clients.airtable.upload_attachment(record_id, FURNITURE_FIELDS[slot], downloaded, filename)
                print(f"[OK] Slot {slot} ({SLOT_LABELS[slot]}): {item.sku} -> {record_id} / {FURNITURE_FIELDS[slot]}")
            except Exception as error:
                print(f"[ERROR] Upload product {item.sku} into slot {slot}: {error}")
                ok = False
        if not ok:
            print(f"[WARN] Row {record_id} created but one or more product uploads failed.")
    return record_id


# --------------------------------------------------------------------------
# Phase 1 -- Generate 11 Krea interiors from pre-crafted prompts
# --------------------------------------------------------------------------


def resolve_slot_settings(
    slot: int,
    prompt_override: str = "",
    moodboard_override: str = "",
    fields: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Resolve (moodboard_id, interior_prompt) for a slot.

    NOTE: this file used to define ``resolve_slot_settings`` twice. Python keeps
    the last definition, and that one never read the per-room keys the Studio
    card saves, so Studio moodboard edits were silently ignored and every run
    used the hardcoded DEFAULT_MOODBOARD_ID. There is now ONE definition.

    Moodboard priority:
      1. moodboard_override (explicit argument)
      2. KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM{slot} (Studio per-room pencil;
         CLI --moodboard-id also sets these for every room)
      3. KREA_MOODBOARD_ID_HOUSE_TOUR_REEL (generic fallback for all rooms)
      4. DEFAULT_MOODBOARD_ID
    Interior Prompt priority (unchanged):
      1. prompt_override (CLI or Studio argument)
      2. os.getenv("PROMPT_HOUSE_TOUR_REEL")
      3. Airtable row field Interior Prompt{slot}
      4. DEFAULT_INTERIOR_PROMPTS[slot]
    """
    mb_id = (
        moodboard_override.strip()
        or os.getenv(room_moodboard_env_key(slot), "").strip()
        or os.getenv(GENERIC_MOODBOARD_ENV_KEY, "").strip()
        or DEFAULT_MOODBOARD_ID
    )

    row_prompt = ""
    if fields:
        row_prompt = str(fields.get(INTERIOR_PROMPT_FIELDS[slot]) or "").strip()

    prompt = (
        prompt_override.strip()
        or os.getenv("PROMPT_HOUSE_TOUR_REEL", "").strip()
        or row_prompt
        or DEFAULT_INTERIOR_PROMPTS.get(slot, "")
    )
    return mb_id, prompt


def phase1_interiors(
    clients: Clients,
    record_id: str,
    fields: dict[str, Any],
) -> None:
    print("[PHASE 1/8] Generating 11 room interiors from pre-crafted prompts (Krea AI)...")
    updates: dict[str, Any] = {}
    prompt_used: dict[int, str] = {}
    moodboard_used: dict[int, str] = {}

    def generate_one(slot: int):
        field_name = INTERIOR_FIELDS[slot]
        if _first_attachment_url(fields, field_name):
            print(f"    [SKIP] slot {slot} ({SLOT_ROOMS[slot]}) already has an interior")
            return
        moodboard_id, interior_prompt = resolve_slot_settings(slot, fields=fields)
        moodboard_used[slot] = moodboard_id
        prompt_used[slot] = interior_prompt
        print(f"    -> requesting Krea {SLOT_ROOMS[slot]} interior for slot {slot} (moodboard {moodboard_id})...")
        url = clients.krea.generate_image(
            prompt=interior_prompt,
            moodboard_id=moodboard_id,
            aspect_ratio=INTERIOR_ASPECT_RATIO,
            resolution=INTERIOR_RESOLUTION,
        )
        updates[field_name] = [{"url": url}]
        print(f"    [OK] slot {slot} interior generated")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(generate_one, SLOTS))

    if updates:
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)
    if prompt_used:
        try:
            clients.airtable.update_records([(
                record_id,
                {
                    INTERIOR_PROMPT_FIELD: "\n".join(
                        f"Slot {s} ({SLOT_ROOMS[s]}): {prompt_used[s]}" for s in sorted(prompt_used)
                    ),
                    MOODBOARD_FIELD: "\n".join(
                        f"Slot {s}: {moodboard_used[s]}" for s in sorted(moodboard_used)
                    ),
                    STATUS_FIELD: STATUS_INTERIOR,
                },
            )])
        except Exception as error:
            print(f"    [WARN] Could not stamp interior prompt/moodboard ({error})")
    else:
        try:
            clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_INTERIOR})])
        except Exception:
            pass


# --------------------------------------------------------------------------
# Phase 2 -- Claude Sonnet 5 Vision analyzes room interiors
# --------------------------------------------------------------------------


def phase2_analyze_interiors(
    clients: Clients,
    record_id: str,
    fields: dict[str, Any],
) -> None:
    print("[PHASE 2/8] Analyzing room interiors with Claude Sonnet 5 Vision...")
    updates: dict[str, Any] = {}

    def analyze_one(slot: int):
        field_name = INTERIOR_ANALYSIS_FIELDS[slot]
        if str(fields.get(field_name) or "").strip():
            print(f"    [SKIP] slot {slot} already has interior analysis")
            return
        interior_url = _first_attachment_url(fields, INTERIOR_FIELDS[slot])
        if not interior_url:
            print(f"    [SKIP] slot {slot} missing interior -- skipping analysis")
            return
        print(f"    -> asking Claude to analyze slot {slot} ({SLOT_ROOMS[slot]}) interior...")
        analysis = clients.fal.generate_vision_prompt(
            image_urls=[interior_url],
            prompt=_interior_analysis_instruction(slot),
            model=CLAUDE_MODEL,
        )
        updates[field_name] = analysis
        print(f"    [OK] slot {slot} interior analyzed")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(analyze_one, SLOTS))

    if updates:
        updates[STATUS_FIELD] = STATUS_INTERIOR_ANALYZED
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)
    else:
        try:
            clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_INTERIOR_ANALYZED})])
        except Exception:
            pass


# --------------------------------------------------------------------------
# Phase 3 -- Context-aware product scraper matching Claude's analysis
# --------------------------------------------------------------------------


def phase3_scrape(
    clients: Clients,
    record_id: str,
    fields: dict[str, Any],
    akeneo: AkeneoClient | None = None,
    style: str = DEFAULT_STYLE,
) -> bool:
    print("[PHASE 3/8] Scraping matching Akeneo fixtures based on room analysis...")
    slots_needing_products = [s for s in SLOTS if not _first_attachment_url(fields, FURNITURE_FIELDS[s])]
    if not slots_needing_products:
        print("    [SKIP] all 11 slots already have products")
        return True

    if akeneo is None:
        akeneo = clients.akeneo()
        akeneo.authenticate()

    # 1. Base-wide dedup across all 60+ tables.
    try:
        base_filenames, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
        print(
            f"[INFO] Cross-table deduplication active: {len(base_skus)} existing SKU(s), "
            f"{len(base_names)} item name(s), {len(base_filenames)} attachment filename(s)."
        )
    except Exception as error:
        print(f"[WARN] Base deduplication fetch notice: {error}")
        base_filenames, base_names, base_skus = set(), set(), set()

    all_existing_filenames = set(base_filenames)
    all_existing_names = set(base_names)
    all_existing_skus = set(base_skus)

    # 2. Identities already in this table.
    for record in clients.airtable.list_records(list(ALL_READ_FIELDS)):
        row = record.get("fields", {})
        for field_map in (ITEM_NAME_FIELDS, SKU_FIELDS):
            for fname in field_map.values():
                val = str(row.get(fname) or "").strip()
                if val:
                    (all_existing_names if field_map is ITEM_NAME_FIELDS else all_existing_skus).add(
                        val.lower() if field_map is ITEM_NAME_FIELDS else val
                    )
        for fname in FURNITURE_FIELDS.values():
            att_list = row.get(fname)
            if isinstance(att_list, list):
                for a in att_list:
                    if isinstance(a, dict) and a.get("filename"):
                        all_existing_filenames.add(identity_key(a["filename"]))

    for s in SLOTS:
        sku = str(fields.get(SKU_FIELDS[s]) or "").strip()
        if sku:
            all_existing_skus.add(sku)
        nm = str(fields.get(ITEM_NAME_FIELDS[s]) or "").strip()
        if nm:
            all_existing_names.add(nm.lower())

    # 3. Shopify published catalog (strict Active & Published).
    shopify_index = None
    try:
        print("[INFO] Loading published catalog from Shopify (homecartel.net)...")
        shopify_index = ShopifyClient().load_published_identities()
        print("[OK] Shopify Index Ready (published identities indexed).")
    except Exception as error:
        print(f"[WARN] Shopify index check skipped: {error}")

    row_updates: dict[str, Any] = {}
    for slot in slots_needing_products:
        analysis_text = str(fields.get(INTERIOR_ANALYSIS_FIELDS[slot]) or "")
        recommended_cat = extract_category_from_analysis(analysis_text, SLOT_CATEGORIES[slot])
        print(f"    [SLOT {slot}] Recommended category from analysis: '{recommended_cat}' (default: '{SLOT_CATEGORIES[slot]}')")

        candidates = _scrape_candidates_for_slot(
            clients,
            akeneo,
            slot=slot,
            style=style,
            needed=1,
            all_existing_filenames=all_existing_filenames,
            all_existing_names=all_existing_names,
            all_existing_skus=all_existing_skus,
            shopify_index=shopify_index,
            category_override=recommended_cat,
        )
        if not candidates and recommended_cat != SLOT_CATEGORIES[slot]:
            print(f"    [FALLBACK] No candidates for '{recommended_cat}', trying default '{SLOT_CATEGORIES[slot]}'...")
            candidates = _scrape_candidates_for_slot(
                clients,
                akeneo,
                slot=slot,
                style=style,
                needed=1,
                all_existing_filenames=all_existing_filenames,
                all_existing_names=all_existing_names,
                all_existing_skus=all_existing_skus,
                shopify_index=shopify_index,
                category_override=SLOT_CATEGORIES[slot],
            )

        if not candidates:
            print(f"[ERROR] Could not find fresh candidate for slot {slot}")
            return False

        item = candidates[0]
        disp_name = _display_name(item)
        row_updates[ITEM_NAME_FIELDS[slot]] = disp_name
        row_updates[SKU_FIELDS[slot]] = item.sku or ""
        try:
            downloaded = akeneo.download_media(item.media_code)
            filename = f"{item.sku or 'fixture'}_{item.media_code}.jpg"
            clients.airtable.upload_attachment(record_id, FURNITURE_FIELDS[slot], downloaded, filename)
            print(f"[OK] Slot {slot} ({recommended_cat}): {item.sku} uploaded -> {FURNITURE_FIELDS[slot]}")
        except Exception as error:
            print(f"[ERROR] Upload product {item.sku} into slot {slot}: {error}")
            return False

    row_updates[STATUS_FIELD] = STATUS_STANDBY
    clients.airtable.update_records([(record_id, row_updates)])
    fields.update(row_updates)
    try:
        fresh_rec = clients.airtable.record(record_id).get("fields", {})
        for s in SLOTS:
            if s in slots_needing_products:
                fields[FURNITURE_FIELDS[s]] = fresh_rec.get(FURNITURE_FIELDS[s], [])
    except Exception:
        pass
    print(f"[OK] Phase 3 complete: matching fixtures populated, Status -> {STATUS_STANDBY}")
    return True


def phase1_scrape(clients: Clients, max_rows: int | None, style: str) -> int:
    """Convenience runner: creates brand-new row(s) and runs Phases 1..3."""
    print("[PHASE 1..3] Scrape fresh House Tour: Generate interiors -> Analyze -> Scrape matching fixtures")
    created = 0
    for i in range(max_rows or 1):
        record_id = _create_row(clients)
        if not record_id:
            continue
        rec = clients.airtable.record(record_id)
        fields = dict(rec.get("fields", {}))
        phase1_interiors(clients, record_id, fields)
        phase2_analyze_interiors(clients, record_id, fields)
        if phase3_scrape(clients, record_id, fields, style=style):
            created += 1
    print(f"[OK] Complete: created {created} row(s) with interiors, analysis & matching products.")
    return created


# --------------------------------------------------------------------------
# Phase 4 -- Blend prompts via Fal Claude Sonnet
# --------------------------------------------------------------------------


def phase4_prompts(clients: Clients, record_id: str, fields: dict[str, Any]) -> None:
    print("[PHASE 4/8] Generating blend prompts (Fal Claude Sonnet 5)...")
    updates: dict[str, Any] = {}

    def author_one(slot: int):
        field_name = PROMPT_FIELDS[slot]
        if str(fields.get(field_name) or "").strip():
            print(f"    [SKIP] slot {slot} already has a prompt")
            return
        interior_url = _first_attachment_url(fields, INTERIOR_FIELDS[slot])
        product_url = _first_attachment_url(fields, FURNITURE_FIELDS[slot])
        if not interior_url or not product_url:
            print(f"    [SKIP] slot {slot} missing interior or product -- skipping prompt")
            return
        analysis_notes = str(fields.get(INTERIOR_ANALYSIS_FIELDS[slot]) or "").strip()
        print(f"    -> asking Claude for slot {slot} ({SLOT_ROOMS[slot]}) blend prompt...")
        prompt = clients.fal.generate_vision_prompt(
            image_urls=[interior_url, product_url],
            prompt=_claude_instruction(slot, analysis_notes=analysis_notes),
            model=CLAUDE_MODEL,
        )
        updates[field_name] = prompt
        print(f"    [OK] slot {slot} blend prompt authored")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(author_one, SLOTS))

    if updates:
        updates[STATUS_FIELD] = STATUS_PROMPT
        clients.airtable.update_records([(record_id, updates)])
        fields.update(updates)


# --------------------------------------------------------------------------
# Phase 5 -- Blend via Fal Nano Banana Pro + YOLO Poppins tags
# --------------------------------------------------------------------------


def phase5_blends(
    clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path
) -> list[Path]:
    print("[PHASE 5/8] Blending fixtures into rooms (Fal Nano Banana Pro) + YOLO Poppins tags...")

    def blend_slot(slot: int) -> tuple[int, Path | None, str]:
        """Blend one slot. Returns (slot, local still or None, blend URL or '').

        The blend URL is returned (not written into ``fields`` here) so the
        caller can update the shared row state on the main thread.
        """
        interior_url = _first_attachment_url(fields, INTERIOR_FIELDS[slot])
        product_url = _first_attachment_url(fields, FURNITURE_FIELDS[slot])
        prompt = str(fields.get(PROMPT_FIELDS[slot]) or "").strip()
        if not interior_url or not product_url or not prompt:
            print(f"    [SKIP] slot {slot} incomplete -- skipping blend")
            return slot, None, ""

        clean_dest = workdir / f"slot{slot}_blended.jpg"
        tagged_dest = workdir / f"slot{slot}_blended_tagged.jpg"
        existing_url = _first_attachment_url(fields, BLENDED_FIELDS[slot])
        if existing_url:
            # Airtable-only reuse: warm a local copy so reruns skip Nano Banana.
            try:
                resp = requests.get(existing_url, timeout=120)
                resp.raise_for_status()
                clean_dest.write_bytes(resp.content)
                print(f"    [SKIP] slot {slot} blend already attached -> reusing URL")
                return slot, clean_dest, existing_url
            except Exception as error:
                print(f"    [WARN] Could not reuse slot {slot} blend ({error}); regenerating...")

        print(f"    -> blending slot {slot} ({SLOT_ROOMS[slot]} / {SLOT_LABELS[slot]})...")
        try:
            result_url = clients.fal.generate(
                prompt=prompt,
                image_urls=[interior_url, product_url],
                aspect_ratio=BLEND_ASPECT_RATIO,
                resolution=BLEND_RESOLUTION,
                model=NANO_BANANA_MODEL,
            )
            resp = requests.get(result_url, timeout=120)
            resp.raise_for_status()
            clean_dest.write_bytes(resp.content)
            clients.airtable.upload_attachment(
                record_id, BLENDED_FIELDS[slot], clean_dest, f"house_tour_blended_slot{slot}.jpg"
            )
            print(f"    [OK] slot {slot} blended -> {clean_dest.name}")

            # YOLO-World Poppins item-name tag (bedroom = slot 2 included).
            try:
                from content_automation.akeneo_client import split_item_name
                from content_automation.item_tagger import tag_blended_image

                raw_name = str(
                    fields.get(ITEM_NAME_FIELDS[slot]) or fields.get(SKU_FIELDS[slot]) or SLOT_LABELS[slot]
                ).strip()
                item_title, product_type = split_item_name(raw_name, fallback_product_type=SLOT_LABELS[slot])
                tag_blended_image(
                    image_input=clean_dest,
                    item_name=item_title,
                    product_type=product_type,
                    category=SLOT_CATEGORIES[slot],
                    destination=tagged_dest,
                    fallback_if_undetected=True,
                    output_format="reel",
                )
                print(f"    [ITEM TAGGING] Stamped '{item_title}' onto slot {slot} blend with YOLO (Poppins)")
                try:
                    clients.airtable.ensure_fields({TAGGED_FIELD: "multipleAttachments"})
                    clients.airtable.upload_attachment(
                        record_id, TAGGED_FIELD, tagged_dest, f"house_tour_tagged_slot{slot}.jpg"
                    )
                except Exception:
                    pass
                still_path = tagged_dest if tagged_dest.is_file() else clean_dest
                return slot, still_path, result_url
            except Exception as tag_err:
                print(f"    [WARN] YOLO tagging notice on slot {slot}: {tag_err}")
                return slot, clean_dest, result_url
        except Exception as error:
            print(f"    [ERROR] slot {slot} blend: {error}")
            return slot, None, ""

    from concurrent.futures import as_completed

    blended: dict[int, tuple[Path | None, str]] = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(blend_slot, slot): slot for slot in SLOTS}
        for future in as_completed(futures):
            slot, path, url = future.result()
            blended[slot] = (path, url)
    # Hand the fresh blend URLs to downstream phases on the MAIN thread:
    # Phase 5 reads them from this same ``fields`` dict, which was fetched
    # before Phase 4 ran. Missing this update starves Kling with an empty URL.
    for slot in SLOTS:
        _path, url = blended[slot]
        if url:
            fields[BLENDED_FIELDS[slot]] = [{"url": url}]
    stills = [path for path, _url in (blended[slot] for slot in SLOTS) if path is not None]
    if stills:
        try:
            clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_BLENDED})])
        except Exception:
            pass
    return stills


# --------------------------------------------------------------------------
# Phase 6 -- Kling V3 Turbo Pro motion clips + Phase 7 music + Phase 8 assembly
# --------------------------------------------------------------------------


def _resolve_outro(clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path) -> Path | None:
    outro_url = _first_attachment_url(fields, OUTRO_FIELD)
    if outro_url:
        try:
            dest = workdir / "outro.jpg"
            resp = requests.get(outro_url, timeout=60)
            dest.write_bytes(resp.content)
            print("    [OK] Outro downloaded from Airtable 'Outro' field")
            return dest
        except Exception as error:
            print(f"    [WARN] Could not download attached Outro ({error})")

    local_outro = resolve_outro_file()
    if not local_outro:
        print("    [WARN] Local outro asset not found; reel will have NO outro.")
        return None
    try:
        clients.airtable.upload_attachment(record_id, OUTRO_FIELD, local_outro, "HomeCartel_Outro.jpg")
        print(f"    [OK] Outro ({local_outro.name}) attached to row 'Outro' field")
    except Exception as error:
        print(f"    [WARN] Could not attach outro to row ({error}); using local file anyway.")
    return local_outro


def _generate_music(clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path) -> Path | None:
    print("[PHASE 7/8] Background music (Fal ElevenLabs Music)...")
    if not MUSIC_ENABLED:
        print("    [INFO] Music disabled (--no-music) -> silent reel.")
        return None
    if _first_attachment_url(fields, MUSIC_FIELD):
        print("    [SKIP] music already attached -> reusing")
        try:
            dest = workdir / "house_tour_music.mp3"
            resp = requests.get(_first_attachment_url(fields, MUSIC_FIELD), timeout=60)
            dest.write_bytes(resp.content)
            return dest
        except Exception:
            return None
    try:
        audio_url = clients.fal.generate_elevenlabs_music(
            prompt=MUSIC_PROMPT,
            duration=MUSIC_DURATION,
            model=MUSIC_MODEL,
        )
    except Exception as error:
        print(f"    [WARN] Music generation notice: {error}; reel will be silent.")
        return None
    if not audio_url:
        return None
    dest = workdir / "house_tour_music.mp3"
    try:
        urllib.request.urlretrieve(audio_url, dest)
    except Exception as error:
        print(f"    [WARN] Could not download music ({error}); reel will be silent.")
        return None
    if not dest.is_file() or dest.stat().st_size == 0:
        return None
    try:
        clients.airtable.upload_attachment(record_id, MUSIC_FIELD, dest, "house_tour_music.mp3")
        clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_MUSIC})])
    except Exception as error:
        print(f"    [WARN] Could not attach music to row ({error}); using local file anyway.")
    print(f"    [OK] Fal ElevenLabs background music ready -> {dest.name}")
    return dest


# --------------------------------------------------------------------------
# Phase 6 -- Kling V3 Turbo Pro image-to-video (3 s alternating pans)
# --------------------------------------------------------------------------


def phase6_kling(
    clients: Clients, record_id: str, fields: dict[str, Any], workdir: Path
) -> list[Path] | None:
    """Animate each clean blend with Fal Kling (3 s, L/R/L/R pans).

    Returns the 11 clip paths in slot order, or None after stamping
    ``STATUS_KLING_FAILED`` when any slot fails.
    """
    print("[PHASE 6/8] Animating blends with Fal Kling V3 Turbo Pro (3 s alternating pans)...")

    # Resume safety: merge freshly fetched blend URLs for slots this run has
    # not (re)blended -- e.g. a retry after Phase 4 already uploaded them.
    try:
        fresh = clients.airtable.record(record_id).get("fields", {})
        for slot in SLOTS:
            if not _first_attachment_url(fields, BLENDED_FIELDS[slot]):
                url = _first_attachment_url(fresh, BLENDED_FIELDS[slot])
                if url:
                    fields[BLENDED_FIELDS[slot]] = [{"url": url}]
                    print(f"    [RESUME] slot {slot} blend URL recovered from Airtable")
    except Exception as error:
        print(f"    [WARN] Could not refresh blend URLs from Airtable ({error})")

    def animate_slot(slot: int) -> tuple[int, Path]:
        dest = workdir / f"slot{slot}_kling.mp4"
        existing = _first_attachment_url(fields, KLING_FIELDS[slot])
        if existing:
            try:
                resp = requests.get(existing, timeout=120)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                print(f"    [SKIP] slot {slot} Kling clip already attached -> reusing")
                return slot, dest
            except Exception as error:
                print(f"    [WARN] Could not reuse slot {slot} Kling clip ({error}); regenerating...")
        blend_url = _first_attachment_url(fields, BLENDED_FIELDS[slot])
        if not blend_url:
            raise AutomationError(f"slot {slot} has no blended image to animate with Kling")
        prompt = kling_motion_prompt(slot)
        print(f"    -> Kling {KLING_DIRECTIONS[slot]}-pan clip for slot {slot} ({SLOT_ROOMS[slot]})...")
        # Stage the blend on fal storage first (reliable fetch for Kling per
        # fal.ai files-upload docs); fall back to the Airtable URL if staging fails.
        source_path = workdir / f"slot{slot}_blend_source.jpg"
        try:
            resp = requests.get(blend_url, timeout=120)
            resp.raise_for_status()
            source_path.write_bytes(resp.content)
        except Exception as error:
            raise AutomationError(f"slot {slot} could not download blended image: {error}")
        kling_image_url = blend_url
        try:
            staged_url = clients.fal.upload_file(source_path)
            if staged_url:
                kling_image_url = str(staged_url).strip() or blend_url
                print(f"    [OK] slot {slot} blend staged on fal storage")
        except Exception as error:
            print(f"    [WARN] slot {slot} fal upload failed ({error}); using Airtable URL")
        last_error: Exception | None = None
        for attempt in range(1, KLING_MAX_ATTEMPTS + 1):
            try:
                video_url = clients.fal.generate_kling_video(
                    prompt=prompt,
                    image_url=kling_image_url,
                    duration=KLING_DURATION,
                    model=KLING_MODEL,
                )
                resp = requests.get(video_url, timeout=300)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                if dest.stat().st_size == 0:
                    raise AutomationError("downloaded Kling clip is empty")
                clients.airtable.upload_attachment(
                    record_id, KLING_FIELDS[slot], dest, f"house_tour_kling_slot{slot}.mp4"
                )
                print(f"    [OK] slot {slot} Kling clip -> {dest.name}")
                return slot, dest
            except Exception as error:
                last_error = error
                print(f"    [WARN] slot {slot} Kling attempt {attempt}/{KLING_MAX_ATTEMPTS}: {error}")
        raise AutomationError(f"slot {slot} Kling failed after {KLING_MAX_ATTEMPTS} attempts: {last_error}")

    try:
        from concurrent.futures import as_completed

        results: dict[int, Path] = {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(animate_slot, slot): slot for slot in SLOTS}
            for future in as_completed(futures):
                slot, path = future.result()
                results[slot] = path
        ordered = [results[slot] for slot in SLOTS]
    except Exception as error:
        print(f"    [ERROR] Kling image-to-video failed: {error}")
        try:
            clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_KLING_FAILED})])
            print(f"    [STATUS] Row {record_id} -> '{STATUS_KLING_FAILED}'")
        except Exception:
            pass
        return None

    try:
        clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_KLING})])
    except Exception:
        pass
    return ordered


# --------------------------------------------------------------------------
# Phase 7 -- Local FFmpeg assembly (1 s xfades, Poppins titles, outro, music)
# --------------------------------------------------------------------------


def _ffmpeg_escape_drawtext(text: str) -> str:
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
    )


def _ffmpeg_escape_fontfile(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def measure_tag_lines(title: str, subtitle: str) -> tuple[int, int, int, int]:
    """Measure the 2-line tag with the real Poppins fonts.

    Returns ``(title_w, title_h, type_w, type_h)`` in canvas pixels, using the
    same ``ImageFont.getbbox`` call the YOLO tagger measures with.
    """
    from PIL import ImageFont

    try:
        font_title = ImageFont.truetype(str(POPPINS_BOLD), TITLE_FONT_SIZE)
    except Exception:
        font_title = ImageFont.load_default()
    try:
        font_type = ImageFont.truetype(str(POPPINS_REGULAR), TYPE_FONT_SIZE)
    except Exception:
        font_type = font_title

    def _size(text: str, font) -> tuple[int, int]:
        if not text:
            return 0, 0
        box = font.getbbox(text)
        return box[2] - box[0], box[3] - box[1]

    title_w, title_h = _size(title, font_title)
    type_w, type_h = _size(subtitle, font_type)
    return title_w, title_h, type_w, type_h


def tag_reel_position(title: str, subtitle: str) -> tuple[int, int, int]:
    """Lower-right tag origin for reels, mirroring the YOLO tagger fallback.

    Returns ``(x, y_title, y_type)`` with reel margins (right 180, bottom 320)
    and 5 px line spacing, so the two lines never overlap each other.
    """
    title_w, title_h, type_w, type_h = measure_tag_lines(title, subtitle)
    pill_w = max(title_w, type_w)
    pill_h = title_h + (TAG_LINE_SPACING + type_h if subtitle else 0)
    x = max(0, VIDEO_WIDTH - pill_w - TAG_RIGHT_MARGIN)
    y_title = max(0, VIDEO_HEIGHT - pill_h - TAG_BOTTOM_MARGIN)
    y_type = y_title + title_h + TAG_LINE_SPACING
    return x, y_title, y_type


def format_item_display_name(title: str, product_type: str, fallback_label: str = "") -> str:
    """Format a clean, luxury product display name combining item name and product type.

    E.g.:
      ('Kansa', 'Table Lamp') -> 'kansa table lamp'
      ('Indus', 'Modern LED Wall Light') -> 'indus wall light'
      ('Adela', 'Modern Pendant Light') -> 'adela pendant light'
    """
    clean_title = (title or "").strip()
    clean_type = (product_type or fallback_label or "").strip()
    if not clean_title:
        return clean_type.lower()
    if not clean_type:
        return clean_title.lower()

    # Normalize clean_type to remove generic marketing adjectives like "Modern", "LED", "Luxury"
    import re
    simplified_type = re.sub(
        r"\b(modern|led|luxury|gold frost|designer)\b", "", clean_type, flags=re.IGNORECASE
    ).strip()
    simplified_type = re.sub(r"\s+", " ", simplified_type)
    if not simplified_type:
        simplified_type = clean_type

    if simplified_type.lower() in clean_title.lower():
        return clean_title.lower()
    return f"{clean_title} {simplified_type}".strip().lower()


def build_house_tour_filter(
    slide_texts: list[tuple[str, str]] | None = None,
    *,
    room_titles: list[str] | None = None,
    with_outro: bool = False,
    pacing: str = DEFAULT_PACING,
    cut_style: str = DEFAULT_CUT_STYLE,
    overlay_style: str = DEFAULT_OVERLAY_STYLE,
) -> tuple[str, str, float]:
    """Build the FFmpeg filter_complex for 11 Kling clips + optional outro.

    Modes:
      - pacing="reference", cut_style="snap", overlay_style="reference" (DEFAULT):
        22.0 s runtime (2.0 s per room across 11 rooms). Each 3s Kling
        clip is trimmed at its smoothest motion window ([0.5, 2.5]) and concatenated
        with clean snap cuts. Upper-third centered lowercase Poppins titles
        appear dynamically from Claude room analysis, and lower-third animated item names
        reveal smoothly after each cut.
      - pacing="relaxed", cut_style="dissolve", overlay_style="tag":
        24.5 s slow slideshow with 1.0 s crossfades and lower-right Poppins tags.

    Returns ``(filter, out_label, total_seconds)``.
    """
    scale_pad = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps={VIDEO_FPS},format=yuv420p"
    )
    parts: list[str] = []

    if pacing == PACING_REFERENCE and cut_style == CUT_STYLE_SNAP:
        # Reference mode: 22.0s total, trimmed snap cuts at 2.0s per room
        for i, dur in enumerate(REFERENCE_SHOT_DURATIONS):
            start_trim = KLING_TRIM_START
            end_trim = start_trim + dur
            parts.append(
                f"[{i}:v]{scale_pad},trim=start={start_trim:.2f}:end={end_trim:.2f},setpts=PTS-STARTPTS[v{i}]"
            )

        concat_inputs = "".join(f"[v{i}]" for i in range(len(REFERENCE_SHOT_DURATIONS)))
        parts.append(f"{concat_inputs}concat=n={len(REFERENCE_SHOT_DURATIONS)}:v=1:a=0[vbase]")
        prev = "vbase"
        total = REFERENCE_TOTAL_SECONDS

        if with_outro:
            oi = len(SLOTS)
            parts.append(f"[{oi}:v]{scale_pad}[vout0]")
            parts.append(
                f"[{prev}][vout0]xfade=transition=fade:duration=0.5:offset={total:.2f}[vx]"
            )
            prev = "vx"
            total += OUTRO_SECONDS

        if overlay_style in (OVERLAY_STYLE_REFERENCE, OVERLAY_STYLE_HYBRID):
            font_title_path = POPPINS_MEDIUM if POPPINS_MEDIUM.is_file() else POPPINS_BOLD
            font_title = _ffmpeg_escape_fontfile(font_title_path)
            font_product_path = PRODUCT_NAME_FONT if PRODUCT_NAME_FONT.is_file() else POPPINS_MEDIUM
            font_product = _ffmpeg_escape_fontfile(font_product_path)
            cum_time = 0.0
            for i, slot in enumerate(SLOTS):
                dur = REFERENCE_SHOT_DURATIONS[i]
                start = cum_time
                end = cum_time + dur
                cum_time += dur

                # 1. Upper-third room title (strictly from Claude Vision analysis only; no default fallback)
                title = ""
                if room_titles and i < len(room_titles):
                    title = (room_titles[i] or "").strip()
                if title:
                    out_lbl = f"vt{i}title"
                    escaped_title = _ffmpeg_escape_drawtext(title.lower())
                    parts.append(
                        f"[{prev}]drawtext=fontfile='{font_title}':text='{escaped_title}':"
                        f"fontsize={REFERENCE_TITLE_FONT_SIZE}:fontcolor=white:x=(w-text_w)/2:y={REFERENCE_TITLE_TEXT_Y}:"
                        f"shadowcolor=black@0.35:shadowx=2:shadowy=2:"
                        f"enable='between(t,{start:.2f},{end:.2f})'[{out_lbl}]"
                    )
                    prev = out_lbl

                # 2. Lower-third animated item name reveal (fluid fade-in & upward slide)
                if slide_texts and i < len(slide_texts):
                    item_entry = slide_texts[i]
                    if isinstance(item_entry, tuple):
                        t_val = (item_entry[0] or "").strip()
                        pt_val = (item_entry[1] or "").strip() if len(item_entry) > 1 else ""
                    else:
                        t_val = str(item_entry or "").strip()
                        pt_val = ""
                    item_display = format_item_display_name(
                        t_val, pt_val, fallback_label=SLOT_LABELS.get(slot, "")
                    )
                    if item_display:
                        anim_start = start + PRODUCT_ANIM_DELAY
                        anim_dur = PRODUCT_ANIM_DURATION
                        anim_offset = PRODUCT_ANIM_OFFSET_Y
                        # Slide upward into position at PRODUCT_NAME_TEXT_Y
                        y_expr = (
                            f"{PRODUCT_NAME_TEXT_Y} + if(lt(t,{anim_start:.2f}),{anim_offset},"
                            f"if(lt(t,{anim_start + anim_dur:.2f}),(1-(t-{anim_start:.2f})/{anim_dur:.2f})*{anim_offset},0))"
                        )
                        # Fade in opacity from 0 to 1
                        alpha_expr = (
                            f"if(lt(t,{anim_start:.2f}),0,"
                            f"if(lt(t,{anim_start + anim_dur:.2f}),(t-{anim_start:.2f})/{anim_dur:.2f},1))"
                        )
                        out_lbl_prod = f"vt{i}prod"
                        escaped_name = _ffmpeg_escape_drawtext(item_display.lower())
                        parts.append(
                            f"[{prev}]drawtext=fontfile='{font_product}':text='{escaped_name}':"
                            f"fontsize={PRODUCT_NAME_FONT_SIZE}:fontcolor=white:x=(w-text_w)/2:"
                            f"y='{y_expr}':alpha='{alpha_expr}':"
                            f"shadowcolor=black@0.45:shadowx=2:shadowy=2:"
                            f"enable='between(t,{anim_start:.2f},{end:.2f})'[{out_lbl_prod}]"
                        )
                        prev = out_lbl_prod

        elif overlay_style == OVERLAY_STYLE_TAG:
            font_bold = _ffmpeg_escape_fontfile(POPPINS_BOLD)
            font_reg = _ffmpeg_escape_fontfile(POPPINS_REGULAR)
            cum_time = 0.0
            for i, slot in enumerate(SLOTS):
                dur = REFERENCE_SHOT_DURATIONS[i]
                start = cum_time
                end = cum_time + dur
                cum_time += dur
                title, subtitle = "", ""
                if slide_texts and i < len(slide_texts):
                    title = (slide_texts[i][0] or "").strip()
                    subtitle = (slide_texts[i][1] or "").strip()
                if not title and not subtitle:
                    continue
                x, y_title, y_type = tag_reel_position(title, subtitle)
                window = f"enable='between(t,{start:.2f},{end:.2f})'"
                if title:
                    parts.append(
                        f"[{prev}]drawtext=fontfile='{font_bold}':text='{_ffmpeg_escape_drawtext(title)}':"
                        f"fontsize={TITLE_FONT_SIZE}:fontcolor=white:x={x}:y={y_title}:{window}[vt{i}a]"
                    )
                    prev = f"vt{i}a"
                if subtitle:
                    parts.append(
                        f"[{prev}]drawtext=fontfile='{font_reg}':text='{_ffmpeg_escape_drawtext(subtitle)}':"
                        f"fontsize={TYPE_FONT_SIZE}:fontcolor=white:x={x}:y={y_type}:{window}[vt{i}b]"
                    )
                    prev = f"vt{i}b"

    else:
        # Relaxed / dissolve mode (legacy): 3s clips, 1s crossfades (~24.5s total)
        for i in range(len(SLOTS)):
            parts.append(f"[{i}:v]{scale_pad}[v{i}]")

        prev = "v0"
        offset = CLIP_SECONDS - XFADE_SECONDS
        for i in range(1, len(SLOTS)):
            out_lbl = f"x{i}"
            parts.append(
                f"[{prev}][v{i}]xfade=transition=fade:duration={XFADE_SECONDS:.1f}:offset={offset:.1f}[{out_lbl}]"
            )
            prev = out_lbl
            offset += CLIP_SECONDS - XFADE_SECONDS

        if with_outro:
            oi = len(SLOTS)
            parts.append(f"[{oi}:v]{scale_pad}[vout0]")
            parts.append(
                f"[{prev}][vout0]xfade=transition=fade:duration={XFADE_SECONDS:.1f}:offset={offset:.1f}[vx]"
            )
            prev = "vx"
            total = offset + OUTRO_SECONDS
        else:
            total = offset - (CLIP_SECONDS - XFADE_SECONDS) + CLIP_SECONDS

        font_bold = _ffmpeg_escape_fontfile(POPPINS_BOLD)
        font_reg = _ffmpeg_escape_fontfile(POPPINS_REGULAR)
        step = CLIP_SECONDS - XFADE_SECONDS
        for i, slot in enumerate(SLOTS):
            title, subtitle = "", ""
            if slide_texts and i < len(slide_texts):
                title = (slide_texts[i][0] or "").strip()
                subtitle = (slide_texts[i][1] or "").strip()
            if not title and not subtitle:
                continue
            x, y_title, y_type = tag_reel_position(title, subtitle)
            start, end = i * step, i * step + CLIP_SECONDS - XFADE_SECONDS
            window = f"enable='between(t,{start:.1f},{end:.1f})'"
            if title:
                parts.append(
                    f"[{prev}]drawtext=fontfile='{font_bold}':text='{_ffmpeg_escape_drawtext(title)}':"
                    f"fontsize={TITLE_FONT_SIZE}:fontcolor=white:x={x}:y={y_title}:{window}[vt{i}a]"
                )
                prev = f"vt{i}a"
            if subtitle:
                parts.append(
                    f"[{prev}]drawtext=fontfile='{font_reg}':text='{_ffmpeg_escape_drawtext(subtitle)}':"
                    f"fontsize={TYPE_FONT_SIZE}:fontcolor=white:x={x}:y={y_type}:{window}[vt{i}b]"
                )
                prev = f"vt{i}b"

    return ";".join(parts), prev, total


def phase8_assemble(
    clips: list[Path],
    workdir: Path,
    slide_texts: list[tuple[str, str]] | None = None,
    room_titles: list[str] | None = None,
    outro: Path | None = None,
    audio: Path | None = None,
    *,
    pacing: str = DEFAULT_PACING,
    cut_style: str = DEFAULT_CUT_STYLE,
    overlay_style: str = DEFAULT_OVERLAY_STYLE,
    with_outro: bool | None = None,
) -> Path:
    desc = (
        f"22.0s reference pacing ({cut_style} cuts, {overlay_style} titles)"
        if pacing == PACING_REFERENCE
        else f"24.5s relaxed pacing ({cut_style} cuts, {overlay_style} titles)"
    )
    print(f"[PHASE 8/8] Assembling Kling clips with FFmpeg ({desc})...")
    if len(clips) != len(SLOTS) or any(not Path(p).is_file() for p in clips):
        raise AutomationError(f"Phase 8 requires all {len(SLOTS)} Kling clip MP4s")

    import imageio_ffmpeg

    has_outro = (with_outro is True) if with_outro is not None else (
        (pacing == PACING_RELAXED) and (outro is not None and Path(outro).is_file())
    )
    if has_outro and (outro is None or not Path(outro).is_file()):
        has_outro = False

    filt, out_label, total = build_house_tour_filter(
        slide_texts,
        room_titles=room_titles,
        with_outro=has_outro,
        pacing=pacing,
        cut_style=cut_style,
        overlay_style=overlay_style,
    )

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    output = workdir / "house_tour_reel.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg_bin, "-y"]
    for clip in clips:
        cmd.extend(["-i", str(clip)])
    if has_outro and outro is not None:
        cmd.extend(["-loop", "1", "-t", f"{OUTRO_SECONDS + XFADE_SECONDS:.1f}", "-i", str(outro)])
    audio_idx: int | None = None
    if audio is not None and Path(audio).is_file():
        audio_idx = len(clips) + (1 if has_outro else 0)
        cmd.extend(["-stream_loop", "-1", "-i", str(audio)])

    if audio_idx is not None:
        filt = (
            f"{filt};[{audio_idx}:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={max(0.0, total - 0.5):.2f}:d=0.5[aout]"
        )
        cmd.extend([
            "-filter_complex", filt,
            "-map", f"[{out_label}]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output),
        ])
    else:
        cmd.extend([
            "-filter_complex", filt,
            "-map", f"[{out_label}]",
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output),
        ])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AutomationError(f"FFmpeg house-tour assembly failed:\n{(result.stderr or '')[-800:]}")
    if not output.is_file() or output.stat().st_size == 0:
        raise AutomationError("FFmpeg finished but output MP4 was not created or is empty")
    print(f"    [OK] Reel assembled ({output.stat().st_size // 1024} KB, ~{total:.1f} s)")
    return output


# --------------------------------------------------------------------------
# End-to-end row processor
# --------------------------------------------------------------------------


def process_row(
    clients: Clients,
    record_id: str,
    force: bool = False,
    *,
    pacing: str = DEFAULT_PACING,
    cut_style: str = DEFAULT_CUT_STYLE,
    overlay_style: str = DEFAULT_OVERLAY_STYLE,
    outro_style: str | None = None,
) -> bool:
    print(f"\n[ROW {record_id}] Processing House Tour Reel...")
    record = clients.airtable.record(record_id)
    fields = dict(record.get("fields", {}))

    if not force and str(fields.get(STATUS_FIELD) or "").strip().lower() == STATUS_DONE.lower():
        print(f"[ROW {record_id}] Status is 'Done' -- strictly skipping (use --force to re-generate).")
        return True

    clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_IN_PROGRESS})])

    with tempfile.TemporaryDirectory(prefix=f"housetour_{record_id}_") as tmpdir:
        workdir = Path(tmpdir)
        # Phase 1: Krea 11 room interiors
        phase1_interiors(clients, record_id, fields)

        # Phase 2: Claude Sonnet 5 Vision analysis
        phase2_analyze_interiors(clients, record_id, fields)

        # Phase 3: Akeneo product scraper matching Claude's analysis
        if not phase3_scrape(clients, record_id, fields):
            print(f"[ROW {record_id}] FAILED -- product scraping failed.")
            return False

        # Phase 4: Claude Sonnet 5 blend prompts
        phase4_prompts(clients, record_id, fields)

        # Phase 5: Nano Banana Pro blends + YOLO tags
        stills = phase5_blends(clients, record_id, fields, workdir)
        if not stills:
            print(f"[ROW {record_id}] FAILED -- no stills blended.")
            return False

        # Phase 6: Kling motion clips
        clips = phase6_kling(clients, record_id, fields, workdir)
        if not clips:
            print(f"[ROW {record_id}] FAILED -- Kling video generation failed (Status = '{STATUS_KLING_FAILED}').")
            return False

        # Phase 7: ElevenLabs background music
        outro = _resolve_outro(clients, record_id, fields, workdir)
        audio = _generate_music(clients, record_id, fields, workdir)

        # Phase 8: Local FFmpeg assembly
        slide_texts: list[tuple[str, str]] = []
        room_titles: list[str] = []
        for s in SLOTS:
            raw = str(fields.get(ITEM_NAME_FIELDS[s]) or "").strip()
            title, product_type = split_item_name(raw, fallback_product_type=SLOT_LABELS[s])
            slide_texts.append((title, product_type))
            if title:
                print(f"    [TEXT] Slide {s}: '{title}' / '{product_type}'")

            analysis_text = str(fields.get(INTERIOR_ANALYSIS_FIELDS[s]) or "").strip()
            room_title = extract_room_title_from_analysis(analysis_text, slot=s)
            room_titles.append(room_title)
            if room_title:
                print(f"    [ROOM] Slide {s}: '{room_title}'")

        with_outro_val = None
        if outro_style == "none":
            with_outro_val = False
        elif outro_style == "branded":
            with_outro_val = True

        mp4_path = phase8_assemble(
            clips,
            workdir,
            slide_texts=slide_texts,
            room_titles=room_titles,
            outro=outro,
            audio=audio,
            pacing=pacing,
            cut_style=cut_style,
            overlay_style=overlay_style,
            with_outro=with_outro_val,
        )

        print(f"  [Upload] Uploading {mp4_path.name} to Airtable...")
        clients.airtable.upload_attachment(
            record_id, FINAL_VIDEO_FIELD, mp4_path, f"house_tour_reel_{record_id}.mp4"
        )
        clients.airtable.update_records([(record_id, {STATUS_FIELD: STATUS_DONE})])
        print(f"[ROW {record_id}] COMPLETE -> Final Video uploaded & Status = Done")

        save_dir = Path("output") / "content" / "house_tour_reel"
        save_dir.mkdir(parents=True, exist_ok=True)
        local_copy = save_dir / f"house_tour_reel_{record_id}.mp4"
        shutil.copyfile(mp4_path, local_copy)
        print(f"[OK] Local video saved to: {local_copy}")

    return True


# Backward-compatibility aliases for legacy test suites and external callers
phase2_interiors = phase1_interiors
phase3_interiors = phase1_interiors
phase3_prompts = phase4_prompts
phase4_blends = phase5_blends
phase5_kling = phase6_kling
phase7_assemble = phase8_assemble
phase8_assemble = phase8_assemble


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="House Tour Reel Automation Pipeline for table tblqXkdDw4O7hxJS4."
    )
    parser.add_argument(
        "--table-id",
        default="",
        help=f"Destination Airtable Table ID (default: env {TABLE_ENV_KEY} or {DEFAULT_TABLE_ID})",
    )
    parser.add_argument(
        "--phase",
        choices=["all", "scrape", "interiors", "analyze", "prompts", "blends", "kling", "music", "assemble", "generate"],
        default="all",
        help="Which phase to run (default: all)",
    )
    parser.add_argument(
        "--mode",
        dest="phase",
        choices=["all", "scrape", "interiors", "analyze", "prompts", "blends", "kling", "music", "assemble", "generate"],
        help="Alias for --phase",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Process a single specific Airtable record ID",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=1,
        help="How many brand-new rows to create and process (default: 1)",
    )
    parser.add_argument(
        "--max-items",
        dest="max_rows",
        type=int,
        help="Alias for --max-rows",
    )
    parser.add_argument(
        "--style",
        default=DEFAULT_STYLE,
        help="Akeneo style filter (default: modern)",
    )
    parser.add_argument(
        "--moodboard-id",
        default="",
        help="Override the Krea moodboard for ALL 11 rooms",
    )
    parser.add_argument(
        "--prompt",
        default="",
        help="Override the Krea interior prompt for ALL 11 rooms",
    )
    parser.add_argument(
        "--pacing",
        choices=["reference", "relaxed"],
        default=DEFAULT_PACING,
        help="Video pacing: 'reference' (22.0s tour, 2.0s per room) or 'relaxed' (24.5s slow crossfades). Default: reference",
    )
    parser.add_argument(
        "--cut-style",
        choices=["snap", "dissolve"],
        default=DEFAULT_CUT_STYLE,
        help="Transition cut style: 'snap' (hard beat cuts) or 'dissolve' (1s crossfades). Default: snap",
    )
    parser.add_argument(
        "--overlay-style",
        choices=["reference", "tag", "hybrid"],
        default=DEFAULT_OVERLAY_STYLE,
        help="On-screen title overlay style: 'reference' (upper-third lowercase serif), 'tag' (lower-right corner), 'hybrid' (both). Default: reference",
    )
    parser.add_argument(
        "--outro",
        dest="outro_style",
        choices=["none", "branded"],
        default=None,
        help="Outro style: 'none' (seamless loop) or 'branded' (appends HomeCartel outro). Default: none for reference pacing, branded for relaxed",
    )
    parser.add_argument(
        "--with-music",
        action="store_true",
        help="Enable Fal ElevenLabs background music (default: enabled)",
    )
    parser.add_argument(
        "--no-music",
        action="store_true",
        help="Disable background music generation (silent reel)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-processing even if record is already marked Done",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    global MUSIC_ENABLED
    load_dotenv()
    args = parse_args(argv)
    if args.no_music:
        MUSIC_ENABLED = False
    if args.with_music:
        MUSIC_ENABLED = True
    if args.moodboard_id:
        # Apply to ALL rooms: per-room Studio keys outrank the generic key in
        # resolve_slot_settings(), so set both.
        os.environ[GENERIC_MOODBOARD_ENV_KEY] = args.moodboard_id
        for slot in SLOTS:
            os.environ[room_moodboard_env_key(slot)] = args.moodboard_id
    if args.prompt:
        os.environ["PROMPT_HOUSE_TOUR_REEL"] = args.prompt

    table_id = args.table_id or os.getenv(TABLE_ENV_KEY, "").strip() or DEFAULT_TABLE_ID
    clients = Clients(table_id)
    _ensure_schema(clients)
    print(f"[TARGET] Airtable Base: {clients.settings.airtable_base_id} | Table ID: {table_id}")

    if args.record_id:
        return 0 if process_row(
            clients,
            args.record_id,
            force=args.force,
            pacing=args.pacing,
            cut_style=args.cut_style,
            overlay_style=args.overlay_style,
            outro_style=args.outro_style,
        ) else 1

    if args.phase == "generate":
        print("[ERROR] --phase generate requires --record-id (existing rows are never re-run automatically).")
        return 1

    if args.phase == "scrape":
        created = phase1_scrape(clients, args.max_rows or 1, args.style)
        return 0 if created else 1

    # Phase all -- MANDATORY RULE: brand-new rows only, processed end-to-end.
    done = 0
    failures = 0
    for i in range(args.max_rows or 1):
        record_id = _create_row(clients)
        if not record_id:
            failures += 1
            continue
        if process_row(
            clients,
            record_id,
            pacing=args.pacing,
            cut_style=args.cut_style,
            overlay_style=args.overlay_style,
            outro_style=args.outro_style,
        ):
            done += 1
        else:
            failures += 1

    print(f"\n[OK] Finished {done} brand-new row(s) end-to-end; {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        sys.exit(2)
