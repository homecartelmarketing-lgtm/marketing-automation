"""Real-world scale calibration for product-to-room blend prompts.

All wording, type normalization and typical size ranges live here so every
pipeline applies one rule. ``ESTIMATED_PRODUCT_SIZES`` holds typical luxury
lighting ranges, not HomeCartel catalogue data; tune the numbers here when a
batch of renders shows a systematic bias.
"""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any

SCALE_RULES_VERSION = "scale-v1"

# normalized type: (width_min, width_max, height_min, height_max, drop_min, drop_max)
ESTIMATED_PRODUCT_SIZES: dict[str, tuple[int, int, int, int, int | None, int | None]] = {
    "chandelier": (60, 100, 50, 90, 75, 110),
    "cluster": (50, 120, 60, 100, 80, 120),
    "pendant": (20, 50, 20, 45, 60, 90),
    "table_lamp": (25, 45, 45, 75, None, None),
    "floor_lamp": (30, 50, 150, 180, None, None),
    "wall_sconce": (10, 25, 20, 45, None, None),
    "ceiling": (30, 60, 10, 25, None, None),
    "linear": (90, 150, 15, 30, 80, 100),
    "fixture": (30, 60, 40, 80, 70, 110),
}

PRODUCT_TYPE_LABELS: dict[str, str] = {
    "chandelier": "chandelier",
    "cluster": "cluster chandelier",
    "pendant": "pendant light",
    "table_lamp": "table lamp",
    "floor_lamp": "floor lamp",
    "wall_sconce": "wall sconce",
    "ceiling": "ceiling light",
    "linear": "linear chandelier",
    "fixture": "lighting fixture",
}

# Longest / most specific aliases first: "Cluster Chandelier" must be cluster,
# and "Ceiling Mounted" must be ceiling rather than chandelier.
_TYPE_MATCH_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cluster", ("cluster", "multi pendant", "multi light")),
    ("linear", ("linear", "island light", "bar light", "billiard")),
    ("pendant", ("pendant", "hanging light", "hanging lamp", "drop light")),
    ("ceiling", ("ceiling mounted", "ceiling mount", "ceiling light", "flush mount", "surface mount")),
    ("wall_sconce", ("wall sconce", "wall light", "wall lamp", "sconce")),
    ("table_lamp", ("table lamp", "desk lamp", "bedside lamp", "table light")),
    ("floor_lamp", ("floor lamp", "standing lamp", "standard lamp", "floor light")),
    ("chandelier", ("chandelier", "chandlier", "crystal")),
)

_HANGING_TYPES = frozenset({"chandelier", "cluster", "pendant", "linear"})
_HANGING_HEIGHT_IS_DROP_CM = 140
_SUSPICIOUS_WIDTH_CM = 200

_UNIT_CM = {
    "cm": 1.0,
    "mm": 0.1,
    "m": 100.0,
    "meter": 100.0,
    "metre": 100.0,
    "meters": 100.0,
    "metres": 100.0,
    "in": 2.54,
    "inch": 2.54,
    "inches": 2.54,
    '"': 2.54,
}

_UNIT_PATTERN = r'(cm|mm|metres?|meters?|m|inches|inch|in|")'

_AXIS_TOKEN = re.compile(
    r"(?<![a-z])(width|w|length|l|diameter|dia|d|height|h|drop)\s*[:.]?\s*"
    r"(\d+(?:\.\d+)?)\s*(?:" + _UNIT_PATTERN + r")?",
    re.IGNORECASE,
)

_BARE_RUN = re.compile(
    r"(\d+(?:\.\d+)?)\s*" + _UNIT_PATTERN + r"?\s*[x×*]\s*"
    r"(\d+(?:\.\d+)?)\s*" + _UNIT_PATTERN + r"?\s*"
    r"(?:[x×*]\s*(\d+(?:\.\d+)?)\s*" + _UNIT_PATTERN + r"?)?",
    re.IGNORECASE,
)


def normalize_product_type(raw: str) -> str:
    """Map free-text product types to one of the keys in the size table."""
    text = re.sub(r"[_\-/]+", " ", str(raw or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "fixture"
    for normalized, aliases in _TYPE_MATCH_ORDER:
        if any(alias in text for alias in aliases):
            return normalized
    return "fixture"


def _clean(text: str) -> str:
    value = html.unescape(str(text or ""))
    value = value.replace("×", "x").replace("✕", "x")
    return re.sub(r"\s+", " ", value).strip()


def _to_cm(value: float, unit: str) -> float:
    return value * _UNIT_CM.get(str(unit or "").strip().lower(), 1.0)


def _shared_unit(entries: list[tuple[str, float, str]]) -> str:
    explicit = {unit.lower() for _, _, unit in entries if unit}
    return next(iter(explicit)) if len(explicit) == 1 else "cm"


def parse_measurement_cm(text: str) -> tuple[float | None, float | None, float | None]:
    """Return ``(width, depth, height)`` in centimetres, or ``None`` per axis.

    Understands labelled axes (``W120*L120*H300cm``, ``W 25cm x H 48cm``,
    ``Dia 60cm``) and bare runs (``120 x 80 x 25 cm``, ``12" x 30"``). It never
    raises: unparseable text returns three ``None`` values.
    """
    raw = _clean(text)
    if not raw:
        return (None, None, None)

    entries: list[tuple[str, float, str]] = []
    for match in _AXIS_TOKEN.finditer(raw):
        entries.append((match.group(1).lower(), float(match.group(2)), match.group(3) or ""))

    if entries:
        shared = _shared_unit(entries)
        width = depth = height = None
        for label, value, unit in entries:
            cm = _to_cm(value, unit or shared)
            if label in ("width", "w"):
                width = cm
            elif label in ("length", "l"):
                depth = cm
            elif label in ("diameter", "dia", "d"):
                width = cm
                depth = cm
            elif label in ("height", "h"):
                height = cm
            # "drop" is intentionally ignored here; the prompt derives the drop.
        return (width, depth, height)

    match = _BARE_RUN.search(raw)
    if not match:
        return (None, None, None)

    values = [match.group(1), match.group(3), match.group(5)]
    units = [match.group(2) or "", match.group(4) or "", match.group(6) or ""]
    present = [
        (index, float(value), units[index])
        for index, value in enumerate(values)
        if value is not None
    ]
    if not present:
        return (None, None, None)

    shared = _shared_unit(present)
    numbers = [_to_cm(value, unit or shared) for _, value, unit in present]
    if len(numbers) == 2:
        return (numbers[0], None, numbers[1])
    if len(numbers) >= 3:
        return (numbers[0], numbers[1], numbers[2])
    return (numbers[0], None, None)


def _fmt(value: float) -> str:
    return str(int(round(value))) if abs(value - round(value)) < 0.05 else f"{value:.1f}"


def product_type_label(product_type: str) -> str:
    """Human-readable noun for prompt prose, for example ``ceiling light``."""
    return PRODUCT_TYPE_LABELS.get(normalize_product_type(product_type), "lighting fixture")


def _label_for(product_type: str, label: str | None) -> str:
    if label and label.strip():
        return label.strip()
    return product_type_label(product_type)


def _strip_article(label: str) -> str:
    text = str(label or "").strip()
    for article in ("a ", "an ", "the "):
        if text.lower().startswith(article):
            return text[len(article) :].strip()
    return text


def _with_article(label: str) -> str:
    text = str(label or "").strip()
    if not text:
        return "the fixture"
    if text.lower().startswith(("a ", "an ", "the ")):
        return text
    return ("an " if text[0].lower() in "aeiou" else "a ") + text


def fixture_span_with_source(
    product_type: str,
    measurement: str,
    *,
    axis: str = "horizontal",
) -> tuple[float, str]:
    """Return ``(centimetres, source)`` for one axis of the fixture.

    ``source`` is ``"supplier"`` when the parsed supplier value is usable and
    ``"typical"`` when the type-range midpoint stands in. Hanging fixtures whose
    stated height is really a maximum drop fall back to the body-height range,
    matching :func:`build_size_fact`.
    """
    normalized = normalize_product_type(product_type)
    hint = ESTIMATED_PRODUCT_SIZES.get(normalized) or ESTIMATED_PRODUCT_SIZES["fixture"]
    width, depth, height = parse_measurement_cm(measurement) if measurement else (None, None, None)

    if axis.lower() == "vertical":
        if height is not None and not (
            normalized in _HANGING_TYPES and height > _HANGING_HEIGHT_IS_DROP_CM
        ):
            return height, "supplier"
        return (hint[2] + hint[3]) / 2.0, "typical"

    value = width if width is not None else depth
    if value is not None and value <= _SUSPICIOUS_WIDTH_CM:
        return value, "supplier"
    return (hint[0] + hint[1]) / 2.0, "typical"


def build_size_fact(product_type: str, measurement: str, *, label: str) -> str:
    """One sentence describing the product's real size for the blend prompt."""
    normalized = normalize_product_type(product_type)
    raw = str(measurement or "").strip()
    hint = ESTIMATED_PRODUCT_SIZES.get(normalized) or ESTIMATED_PRODUCT_SIZES["fixture"]
    width, depth, height = parse_measurement_cm(raw) if raw else (None, None, None)

    note = ""
    if width is not None and width > _SUSPICIOUS_WIDTH_CM:
        width = None
        depth = None
        note = f"The stated width is implausibly large for {_with_article(label)}; trust the cutout instead. "
    if (
        normalized in _HANGING_TYPES
        and height is not None
        and height > _HANGING_HEIGHT_IS_DROP_CM
    ):
        height = None
        width_min, width_max, height_min, height_max, _, _ = hint
        note += (
            f"The stated height looks like the maximum adjustable drop, not the body height; "
            f"keep the body within the typical {_strip_article(label)} range of about "
            f"{width_min}-{width_max} cm wide and {height_min}-{height_max} cm tall. "
        )

    if width is not None or depth is not None or height is not None:
        parts: list[str] = []
        span = width if width is not None else depth
        if span is not None:
            parts.append(f"about {_fmt(span)} cm wide")
        if width is not None and depth is not None and abs(depth - width) > 1:
            parts.append(f"{_fmt(depth)} cm deep")
        if height is not None:
            parts.append(f"{_fmt(height)} cm tall")
        described = ", ".join(parts)
        return (
            f"The supplier lists {raw}; that is {described}. Treat this as the true size when it is "
            f"plausible for {_with_article(label)}; if the cutout clearly shows different proportions, trust the cutout. {note}"
        ).strip()

    if raw:
        return (
            f'The supplier lists "{raw}". Convert it to centimetres (1 in = 2.54 cm, 1 mm = 0.1 cm) '
            f"and use it when it is plausible for {_with_article(label)}; otherwise trust the cutout and the typical range below. {note}"
        ).strip()

    if normalized != "fixture":
        width_min, width_max, height_min, height_max, drop_min, drop_max = hint
        drop = (
            f", with a total drop of about {drop_min}-{drop_max} cm from the ceiling"
            if drop_min is not None and drop_max is not None
            else ""
        )
        return (
            f"No supplier dimension is available. Estimate from the cutout; a typical {_strip_article(label)} is about "
            f"{width_min}-{width_max} cm wide and {height_min}-{height_max} cm tall{drop}. "
            "These ranges are typical estimates, not exact product data."
        )

    return (
        "No supplier dimension or product type is available. Estimate from the cutout against the room's "
        "furniture and choose a typical statement-lighting size, about 50-90 cm wide and 40-90 cm tall."
    )


def build_scale_rule(product_type: str, measurement: str, *, label: str = "the fixture") -> str:
    """Numbered rule inserted into the shared blending instruction."""
    size_fact = build_size_fact(product_type, measurement, label=label)
    return (
        "3. SIZE AND SCALE - an oversized fixture is the most common failure, so prevent it explicitly:\n"
        "   - Measure the room in Image 1 first: ceiling height (use 2.6 m when unclear), door height about 2.0 m, "
        "sofa seat about 45 cm, dining table top about 75 cm, kitchen counter about 90 cm, bedside table top about 55 cm.\n"
        f"   - {size_fact}\n"
        "   - State the fixture's real width and height in centimetres in the prompt you write, and compare it with "
        "one piece of furniture that is actually visible in Image 1, for example \"about 80 cm wide, roughly half "
        "the width of the dining table below it\".\n"
        "   - Hanging fixtures: the total drop is canopy + rod/chain + body. Keep at least 210 cm clear above the floor "
        "where people walk, 80-90 cm above a dining table top, and 85-95 cm above a kitchen island. On a low ceiling "
        "shorten the rod or chain instead of shrinking the body.\n"
        "   - If a stated dimension cannot fit the room (for example a 300 cm chandelier under a 260 cm ceiling), treat "
        "that number as an adjustable drop or a shipping size and never render the body that tall.\n"
        "   - Never enlarge the fixture to fill the frame and never scale it to the image edges. When the evidence is "
        "ambiguous, choose the smaller plausible size."
    )


def scale_clause(product_type: str, measurement: str, *, label: str = "the fixture") -> str:
    """Compact scale paragraph for a pipeline that owns its full instruction."""
    size_fact = build_size_fact(product_type, measurement, label=label)
    return (
        f"REAL-WORLD SIZE (critical): before placing {label}, establish the room's scale from its ceiling and furniture.\n"
        f"{size_fact}\n"
        "The fixture must keep its true size relative to nearby objects: a sofa seat is about 45 cm high, a dining table "
        "top about 75 cm, a kitchen counter about 90 cm, a bedside table about 55 cm, a door about 2.0 m and a ceiling "
        "about 2.6 m.\n"
        "Keep at least 210 cm clear above the floor under any hanging fixture, 80-90 cm above a dining table and "
        "85-95 cm above a kitchen island; on a low ceiling shorten the rod or chain instead of shrinking the body.\n"
        "Never enlarge the fixture to fill the frame; when unsure choose the smaller plausible size."
    )


def _slot_field_names(base: str, slot: int) -> tuple[str, ...]:
    if slot < 0:
        slot = 0
    if slot == 0:
        return (base, f"{base}1", f"{base} 1")
    return (f"{base}{slot + 1}", f"{base} {slot + 1}")


def _field_value(fields: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = fields.get(name)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def measurement_for_slot(fields: dict[str, Any], slot: int = 0) -> str:
    return _field_value(fields, _slot_field_names("Measurement", slot))


def product_type_for_slot(fields: dict[str, Any], slot: int = 0) -> str:
    return _field_value(fields, _slot_field_names("Product Type", slot))


def item_name_for_slot(fields: dict[str, Any], slot: int = 0) -> str:
    return _field_value(fields, _slot_field_names("Item Name", slot))


def blend_instruction_from_fields(
    fields: dict[str, Any],
    slot: int = 0,
    *,
    interior_label: str = "Room Interior",
    item_name: str | None = None,
    aspect_ratio: str = "9:16",
    extra_instructions: str = "",
) -> str:
    """Build the shared blend instruction from one Airtable record's fields."""
    from . import build_vision_blending_instruction

    raw_name = str(item_name or item_name_for_slot(fields, slot) or "").strip()
    display_name = raw_name
    split_type = ""
    if "|" in raw_name:
        left, right = raw_name.split("|", 1)
        display_name = left.strip() or raw_name
        split_type = right.strip()

    product_type = product_type_for_slot(fields, slot) or split_type
    return build_vision_blending_instruction(
        interior_label=interior_label,
        item_name=display_name or "Lighting Fixture",
        aspect_ratio=aspect_ratio,
        extra_instructions=extra_instructions,
        product_type=product_type,
        measurement=measurement_for_slot(fields, slot),
    )


def scale_cache_digest(product_type: str, measurement: str) -> str:
    """Stable digest so cached prompts cannot be reused after rule changes."""
    normalized_type = normalize_product_type(product_type)
    parsed = parse_measurement_cm(measurement) if measurement else (None, None, None)
    if any(value is not None for value in parsed):
        material = "|".join("?" if value is None else f"{value:.1f}" for value in parsed)
    else:
        material = re.sub(r"\s+", " ", str(measurement or "")).strip().casefold()
    payload = f"{SCALE_RULES_VERSION}|{normalized_type}|{material}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
