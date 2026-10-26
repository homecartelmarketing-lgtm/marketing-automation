"""Paid scale enforcement for product-to-room blends.

The shared prompt rules already describe the real size, but an image model can
still ignore prose. This module adds a measured loop around the blend:

1. Claude Vision measures a known-size object in the room.
2. The fixture's supplier size is converted into an expected image fraction.
3. The prompt gets a numeric ``MEASURED SCALE TARGET`` lock.
4. Nano Banana Pro blends.
5. Claude Vision compares the fixture with the same reference.
6. One corrected re-blend runs only when the result is outside tolerance.

Everything is best-effort: a missing reference or a failed measurement falls
back to the existing prompt-only rule and never blocks the pipeline.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from typing import Any, Sequence

from .prompts.scale import (
    build_size_fact,
    fixture_span_with_source,
    normalize_product_type,
    product_type_label,
)

SCALE_GUARD_VERSION = "scale-guard-v1"
SCALE_AUDIT_FIELD = "Scale Audit"
SCALE_CHECK_FIELD = "Scale Check"
SCALE_RETRY_FIELD = "Scale Retry"
SCALE_REJECTED_BLEND_FIELD = "Rejected Blend"

SCALE_CHECK_CHOICES = (
    "Pass",
    "Pass After Retry",
    "Too Big",
    "Too Small",
    "No Reference",
    "Skipped",
    "Error",
)
SCALE_RETRY_CHOICES = ("Not Needed", "Retried", "Retry Failed")

SCALE_FIELDS: dict[str, str] = {
    SCALE_AUDIT_FIELD: "multilineText",
    SCALE_CHECK_FIELD: "singleSelect",
    SCALE_RETRY_FIELD: "singleSelect",
}

DEFAULT_VISION_MODEL = "anthropic/claude-sonnet-5"
DEFAULT_BLEND_MODEL = "fal-ai/nano-banana-pro/edit"
DEFAULT_TOLERANCE = 0.15

_CHECK_SEVERITY = {
    "Pass": 0,
    "Pass After Retry": 1,
    "Skipped": 2,
    "No Reference": 2,
    "Too Small": 3,
    "Too Big": 3,
    "Error": 4,
}
_RETRY_SEVERITY = {"Not Needed": 0, "Retried": 1, "Retry Failed": 2}

_FRACTION_KEYS = ("reference_fraction", "fixture_fraction")


@dataclass(frozen=True)
class Reference:
    name: str
    cm: float
    axis: str
    fraction: float
    confidence: str
    reason: str = ""


@dataclass(frozen=True)
class ScaleTarget:
    product_type: str
    label: str
    raw_measurement: str
    size_source: str
    axis: str
    fixture_cm: float
    reference: Reference
    target_fraction: float
    target_px: int | None = None


@dataclass(frozen=True)
class ScaleCheck:
    verdict: str
    ratio: float | None = None
    implied_cm: float | None = None
    reference_fraction: float | None = None
    fixture_fraction: float | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.verdict in ("Pass", "Pass After Retry")


@dataclass(frozen=True)
class ScaleGuardResult:
    image_url: str
    target: ScaleTarget | None
    first_check: ScaleCheck
    retry_check: ScaleCheck | None
    retry: str
    attempts: int
    kept_attempt: int = 1
    note: str = ""

    @property
    def check(self) -> ScaleCheck:
        if self.kept_attempt == 2 and self.retry_check is not None:
            return self.retry_check
        return self.first_check


def scale_guard_enabled() -> bool:
    """Global switch, on by default. Set SCALE_GUARD_ENABLED=0 to disable."""
    for key in ("SCALE_GUARD_ENABLED", "SCALE_GUARD"):
        raw = os.getenv(key)
        if raw is None:
            continue
        return raw.strip().lower() not in ("0", "false", "no", "off", "disabled")
    return True


def scale_tolerance() -> float:
    raw = os.getenv("SCALE_GUARD_TOLERANCE", "").strip()
    if not raw:
        return DEFAULT_TOLERANCE
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TOLERANCE
    return min(max(value, 0.05), 0.50)


def _fmt(value: float) -> str:
    return str(int(round(value))) if abs(value - round(value)) < 0.05 else f"{value:.1f}"


def _fraction(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 1.5 < number <= 100:
        number /= 100.0
    return number if 0.0 < number <= 1.0 else None


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from a model reply, tolerating fences."""
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start : end + 1])
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _sentence_label(label: str) -> str:
    text = str(label or "").strip() or "the fixture"
    return text[:1].upper() + text[1:]


def _axis_word(axis: str) -> str:
    return "width" if str(axis).lower() == "horizontal" else "height"


def _default_label(product_type: str) -> str:
    return f"the {product_type_label(normalize_product_type(product_type))}"


def build_measure_instruction(
    product_type: str,
    measurement: str,
    *,
    item_name: str = "",
    label: str = "",
    aspect_ratio: str = "9:16",
) -> str:
    normalized = normalize_product_type(product_type)
    type_label = product_type_label(normalized)
    label = label or _default_label(normalized)
    display_name = str(item_name or "").split("|", 1)[0].strip() or label
    size_fact = build_size_fact(normalized, measurement, label=label)
    pairing = {
        "chandelier": "dining table length (180 cm) or kitchen island length (200 cm)",
        "cluster": "dining table length (180 cm) or kitchen island length (200 cm)",
        "linear": "dining table length (180 cm) or kitchen island length (200 cm)",
        "pendant": "dining table length (180 cm) or kitchen island length (200 cm)",
        "table_lamp": "bedside table height (55 cm), side table height (55 cm) or console height (75 cm)",
        "floor_lamp": "sofa seat height (45 cm) or door height (200 cm)",
        "wall_sconce": "door height (200 cm) or door width (80 cm)",
        "ceiling": "dining table length (180 cm) or door height (200 cm)",
    }.get(normalized, "dining table length (180 cm), sofa length (200 cm) or door height (200 cm)")
    return (
        "You are a measurement estimator for luxury interior photos. "
        f"Image 1 is the room; Image 2 is the isolated product cutout. The frame is {aspect_ratio}.\n"
        f"Product: {display_name} ({type_label}). {size_fact}\n"
        "Choose ONE reference object in Image 1 that is fully visible, close to where the product will be "
        f"placed, and has a standard size. Best match for this product: {pairing}.\n"
        "Standard sizes you may use: dining table length 180 cm, dining table height 75 cm, sofa length 200 cm, "
        "sofa seat height 45 cm, queen bed width 160 cm, bedside table height 55 cm, kitchen island length 200 cm, "
        "kitchen counter height 90 cm, door height 200 cm, door width 80 cm.\n"
        "Do not use a tiny, distant or partly hidden object, and do not use the product cutout as the reference.\n"
        "Estimate the reference object's visible extent as a decimal FRACTION of the image width for a horizontal "
        "object, or of the image height for a vertical object. Use its full visible length/width or full visible "
        "height. The fixture will be measured on the same axis.\n"
        "Return ONLY a JSON object with exactly these keys:\n"
        '{"reference": "dining table", "reference_cm": 180, "axis": "horizontal", '
        '"reference_fraction": 0.42, "confidence": "high", "reason": "one short sentence"}\n'
        'If no reliable reference is visible, return {"reference": null, "reference_cm": 0, "axis": "", '
        '"reference_fraction": 0, "confidence": "low", "reason": "why not"}.\n'
        "reference_fraction must be between 0 and 1 (not a percentage and not pixels). "
        "No markdown fences and no text outside the JSON."
    )


def build_check_instruction(target: ScaleTarget, *, label: str = "") -> str:
    label = label or target.label
    axis_word = _axis_word(target.axis)
    return (
        "You are a measurement checker for a composited interior photo. Image 1 is the final blend.\n"
        f"Reference object: {target.reference.name}, real {axis_word} about {_fmt(target.reference.cm)} cm.\n"
        f"Lighting fixture: {label}, real {axis_word} about {_fmt(target.fixture_cm)} cm.\n"
        f"Estimate the visible {axis_word} of BOTH objects as a decimal FRACTION of the image {axis_word}. "
        "Use their widest visible width for a horizontal axis, or their full visible height for a vertical axis.\n"
        "Return ONLY a JSON object with exactly these keys:\n"
        '{"reference_visible": true, "fixture_visible": true, "reference_fraction": 0.40, '
        '"fixture_fraction": 0.20, "confidence": "high", "reason": "one short sentence"}\n'
        "Fractions must be between 0 and 1 (not percentages and not pixels). If either object is not visible, "
        "set its visible key to false and its fraction to null. No markdown fences and no text outside the JSON."
    )


def build_lock_text(target: ScaleTarget) -> str:
    axis_word = _axis_word(target.axis)
    target_pct = target.target_fraction * 100.0
    reference_pct = target.reference.fraction * 100.0
    ratio = target.fixture_cm / target.reference.cm
    pixels = f" (about {target.target_px} px)" if target.target_px else ""
    return (
        "MEASURED SCALE TARGET (lock this exactly):\n"
        f"The {target.reference.name} in Image 1 is about {_fmt(target.reference.cm)} cm {axis_word} "
        f"and fills about {reference_pct:.0f}% of the image {axis_word}.\n"
        f"{_sentence_label(target.label)} is {_fmt(target.fixture_cm)} cm {axis_word}, so it must fill about "
        f"{target_pct:.0f}% of the image {axis_word}{pixels}, about {ratio:.2f} times the {axis_word} of the "
        f"{target.reference.name}. Do not make it larger than this and keep its true proportions from Image 2."
    )


def build_retry_correction(target: ScaleTarget, check: ScaleCheck) -> str:
    axis_word = _axis_word(target.axis)
    target_pct = target.target_fraction * 100.0
    pixels = f" (about {target.target_px} px)" if target.target_px else ""
    observed = "different from the target"
    factor_text = ""
    if check.implied_cm and check.implied_cm > 0:
        observed = f"about {_fmt(check.implied_cm)} cm {axis_word}"
        factor = target.fixture_cm / check.implied_cm
        factor_text = f", scaling it to about {factor:.0%} of its previous size"
    return (
        "SCALE CORRECTION (apply exactly): the previous render shows the fixture at "
        f"{observed}, but its true {axis_word} is {_fmt(target.fixture_cm)} cm. "
        f"Redraw the fixture at exactly {_fmt(target.fixture_cm)} cm {axis_word}, filling about "
        f"{target_pct:.0f}% of the image {axis_word}{pixels}{factor_text}. "
        "Keep its design, position, lighting and the rest of the room unchanged."
    )


def _reference_from_data(data: dict[str, Any]) -> Reference | None:
    raw_name = data.get("reference")
    if raw_name is None or str(raw_name).strip().lower() in ("", "null", "none"):
        return None
    confidence = str(data.get("confidence") or "medium").strip().lower()
    if confidence == "low":
        return None
    axis = str(data.get("axis") or "").strip().lower()
    if axis not in ("horizontal", "vertical"):
        return None
    try:
        cm = float(data.get("reference_cm"))
    except (TypeError, ValueError):
        return None
    if not 10.0 <= cm <= 500.0:
        return None
    fraction = _fraction(data.get("reference_fraction"))
    if fraction is None or not 0.03 <= fraction <= 0.97:
        return None
    return Reference(
        name=str(raw_name).strip(),
        cm=cm,
        axis=axis,
        fraction=fraction,
        confidence=confidence,
        reason=str(data.get("reason") or "").strip()[:200],
    )


def compute_scale_target(
    fal: Any,
    *,
    room_url: str,
    product_url: str,
    product_type: str = "",
    measurement: str = "",
    item_name: str = "",
    label: str = "",
    aspect_ratio: str = "9:16",
    vision_model: str = DEFAULT_VISION_MODEL,
    image_size: tuple[int, int] | None = None,
) -> ScaleTarget | None:
    """One Claude Vision call that returns a usable measured target, or None."""
    if not room_url or not product_url:
        return None
    normalized = normalize_product_type(product_type)
    label = label or _default_label(normalized)
    instruction = build_measure_instruction(
        normalized,
        measurement,
        item_name=item_name,
        label=label,
        aspect_ratio=aspect_ratio,
    )
    try:
        raw = fal.generate_vision_prompt(
            image_urls=[room_url, product_url],
            prompt=instruction,
            model=vision_model,
        )
    except Exception as error:  # noqa: BLE001 - a paid guard must never block the blend
        print(f"[WARN] Scale measurement call failed: {error}")
        return None

    data = parse_json_object(raw)
    if not data:
        print("[WARN] Scale measurement returned no usable JSON; using the prompt-only rule.")
        return None
    reference = _reference_from_data(data)
    if reference is None:
        print("[WARN] Scale measurement found no reliable reference; using the prompt-only rule.")
        return None

    fixture_cm, source = fixture_span_with_source(
        normalized, measurement, axis=reference.axis
    )
    if fixture_cm <= 0:
        return None
    target_fraction = reference.fraction * fixture_cm / reference.cm
    if not 0.01 <= target_fraction <= 0.95:
        return None

    target_px = None
    if image_size and len(image_size) == 2:
        width, height = image_size
        base = width if reference.axis == "horizontal" else height
        if base and base > 0:
            target_px = int(round(target_fraction * base))

    return ScaleTarget(
        product_type=normalized,
        label=label,
        raw_measurement=str(measurement or "").strip(),
        size_source=source,
        axis=reference.axis,
        fixture_cm=fixture_cm,
        reference=reference,
        target_fraction=target_fraction,
        target_px=target_px,
    )


def check_scale(
    fal: Any,
    *,
    blended_url: str,
    target: ScaleTarget,
    vision_model: str = DEFAULT_VISION_MODEL,
    tolerance: float | None = None,
) -> ScaleCheck:
    """One Claude Vision call comparing the blend with the measured target."""
    if not blended_url:
        return ScaleCheck(verdict="Error", reason="missing blended image URL")
    try:
        raw = fal.generate_vision_prompt(
            image_urls=[blended_url],
            prompt=build_check_instruction(target),
            model=vision_model,
        )
    except Exception as error:  # noqa: BLE001
        return ScaleCheck(verdict="Error", reason=str(error)[:200])

    data = parse_json_object(raw)
    if not data:
        return ScaleCheck(verdict="Error", reason="unparseable check response")
    if data.get("reference_visible") is False:
        return ScaleCheck(verdict="No Reference", reason="reference not visible in the blend")
    if data.get("fixture_visible") is False:
        return ScaleCheck(verdict="Error", reason="fixture not visible in the blend")

    reference_fraction = _fraction(data.get("reference_fraction"))
    fixture_fraction = _fraction(data.get("fixture_fraction"))
    if reference_fraction is None:
        return ScaleCheck(verdict="No Reference", reason="reference fraction missing")
    if fixture_fraction is None:
        return ScaleCheck(verdict="Error", reason="fixture fraction missing")

    implied_cm = fixture_fraction / reference_fraction * target.reference.cm
    ratio = implied_cm / target.fixture_cm if target.fixture_cm else 0.0
    limit = scale_tolerance() if tolerance is None else tolerance
    if 1.0 - limit <= ratio <= 1.0 + limit:
        verdict = "Pass"
    else:
        verdict = "Too Big" if ratio > 1.0 else "Too Small"
    return ScaleCheck(
        verdict=verdict,
        ratio=ratio,
        implied_cm=implied_cm,
        reference_fraction=reference_fraction,
        fixture_fraction=fixture_fraction,
        reason=str(data.get("reason") or "").strip()[:200],
    )


def _generate_blend(
    fal: Any,
    *,
    prompt: str,
    room_url: str,
    product_url: str,
    aspect_ratio: str,
    resolution: str | None,
    model: str,
    output_format: str | None,
) -> str:
    extra = {"output_format": output_format} if output_format else {}
    return fal.generate(
        prompt=prompt,
        image_urls=[room_url, product_url],
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        model=model,
        **extra,
    )


def blend_with_scale_guard(
    fal: Any,
    *,
    prompt: str,
    room_url: str,
    product_url: str,
    product_type: str = "",
    measurement: str = "",
    item_name: str = "",
    label: str = "",
    aspect_ratio: str = "9:16",
    resolution: str | None = "1K",
    model: str = DEFAULT_BLEND_MODEL,
    output_format: str | None = "jpeg",
    vision_model: str = DEFAULT_VISION_MODEL,
    image_size: tuple[int, int] | None = None,
    tolerance: float | None = None,
) -> ScaleGuardResult:
    """Blend once, measure, and retry at most once when the size is off."""
    if not scale_guard_enabled():
        url = _generate_blend(
            fal,
            prompt=prompt,
            room_url=room_url,
            product_url=product_url,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            model=model,
            output_format=output_format,
        )
        return ScaleGuardResult(
            image_url=url,
            target=None,
            first_check=ScaleCheck(verdict="Skipped", reason="scale guard disabled"),
            retry_check=None,
            retry="Not Needed",
            attempts=1,
        )

    target = compute_scale_target(
        fal,
        room_url=room_url,
        product_url=product_url,
        product_type=product_type,
        measurement=measurement,
        item_name=item_name,
        label=label,
        aspect_ratio=aspect_ratio,
        vision_model=vision_model,
        image_size=image_size,
    )
    if target is None:
        url = _generate_blend(
            fal,
            prompt=prompt,
            room_url=room_url,
            product_url=product_url,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            model=model,
            output_format=output_format,
        )
        return ScaleGuardResult(
            image_url=url,
            target=None,
            first_check=ScaleCheck(
                verdict="No Reference",
                reason="no usable reference; used the prompt-only scale rule",
            ),
            retry_check=None,
            retry="Not Needed",
            attempts=1,
        )

    locked_prompt = f"{prompt.strip()}\n\n{build_lock_text(target)}"
    first_url = _generate_blend(
        fal,
        prompt=locked_prompt,
        room_url=room_url,
        product_url=product_url,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        model=model,
        output_format=output_format,
    )
    first_check = check_scale(
        fal,
        blended_url=first_url,
        target=target,
        vision_model=vision_model,
        tolerance=tolerance,
    )
    if first_check.ok or first_check.verdict in ("No Reference", "Error"):
        return ScaleGuardResult(
            image_url=first_url,
            target=target,
            first_check=first_check,
            retry_check=None,
            retry="Not Needed",
            attempts=1,
        )

    retry_prompt = f"{locked_prompt}\n\n{build_retry_correction(target, first_check)}"
    try:
        retry_url = _generate_blend(
            fal,
            prompt=retry_prompt,
            room_url=room_url,
            product_url=product_url,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            model=model,
            output_format=output_format,
        )
    except Exception as error:  # noqa: BLE001
        return ScaleGuardResult(
            image_url=first_url,
            target=target,
            first_check=first_check,
            retry_check=None,
            retry="Retry Failed",
            attempts=1,
            note=str(error)[:200],
        )

    retry_check = check_scale(
        fal,
        blended_url=retry_url,
        target=target,
        vision_model=vision_model,
        tolerance=tolerance,
    )
    if retry_check.ok:
        return ScaleGuardResult(
            image_url=retry_url,
            target=target,
            first_check=first_check,
            retry_check=replace(retry_check, verdict="Pass After Retry"),
            retry="Retried",
            attempts=2,
            kept_attempt=2,
        )

    if first_check.ratio is not None and retry_check.ratio is not None:
        first_error = abs(1.0 - first_check.ratio)
        retry_error = abs(1.0 - retry_check.ratio)
        if first_error <= retry_error:
            return ScaleGuardResult(
                image_url=first_url,
                target=target,
                first_check=first_check,
                retry_check=retry_check,
                retry="Retried",
                attempts=2,
                kept_attempt=1,
                note="retry was not better; kept attempt 1",
            )
        return ScaleGuardResult(
            image_url=retry_url,
            target=target,
            first_check=first_check,
            retry_check=retry_check,
            retry="Retried",
            attempts=2,
            kept_attempt=2,
        )

    return ScaleGuardResult(
        image_url=retry_url,
        target=target,
        first_check=first_check,
        retry_check=retry_check,
        retry="Retried",
        attempts=2,
        kept_attempt=2,
        note="retry kept but not measurable",
    )


def _check_line(label: str, check: ScaleCheck) -> str:
    if check.ratio is None:
        return f"{label}: {check.verdict}"
    return f"{label}: {check.ratio:.0%} of target -> {check.verdict}"


def format_scale_audit(
    result: ScaleGuardResult,
    *,
    slot: int | None = None,
    total: int | None = None,
) -> str:
    header = SCALE_GUARD_VERSION
    if slot is not None:
        header += f" | slot {slot} of {total}" if total else f" | slot {slot}"
    lines = [header]
    target = result.target
    if target is not None:
        source = target.raw_measurement or "(no supplier measurement)"
        lines.append(
            f"size: {target.size_source} {source} -> {_fmt(target.fixture_cm)} cm {target.axis}"
        )
        lines.append(
            f"reference: {target.reference.name} {_fmt(target.reference.cm)} cm {target.axis}, "
            f"{target.reference.fraction:.0%} of image {target.axis} ({target.reference.confidence})"
        )
        target_line = f"target: {target.target_fraction:.0%} of image {target.axis}"
        if target.target_px:
            target_line += f" ({target.target_px} px)"
        lines.append(target_line)
    else:
        lines.append("reference: none")
    lines.append(_check_line("attempt 1", result.first_check))
    if result.retry_check is not None:
        lines.append(_check_line("attempt 2", result.retry_check))
    lines.append(f"retry: {result.retry} | kept: attempt {result.kept_attempt}")
    if result.note:
        lines.append(f"note: {result.note}")
    return "\n".join(lines)


def merge_scale_fields(
    results: Sequence[tuple[int, ScaleGuardResult] | ScaleGuardResult],
) -> dict[str, str]:
    """One row-level Airtable update for one or more blended fixtures."""
    pairs: list[tuple[int | None, ScaleGuardResult]] = []
    for item in results:
        if isinstance(item, tuple):
            pairs.append((item[0], item[1]))
        else:
            pairs.append((None, item))
    if not pairs:
        return {}

    total = len(pairs)
    audits = [
        format_scale_audit(result, slot=slot, total=total if slot is not None else None)
        for slot, result in pairs
    ]
    verdicts = [result.check.verdict for _, result in pairs]
    retries = [result.retry for _, result in pairs]
    return {
        SCALE_AUDIT_FIELD: "\n\n".join(audits),
        SCALE_CHECK_FIELD: max(verdicts, key=lambda value: _CHECK_SEVERITY.get(value, 0)),
        SCALE_RETRY_FIELD: max(retries, key=lambda value: _RETRY_SEVERITY.get(value, 0)),
    }


def ensure_scale_fields(airtable: Any) -> None:
    """Create the audit columns when the table does not have them yet."""
    try:
        ensure_select = getattr(airtable, "ensure_single_select_options", None)
        if callable(ensure_select):
            ensure_select(SCALE_CHECK_FIELD, SCALE_CHECK_CHOICES)
            ensure_select(SCALE_RETRY_FIELD, SCALE_RETRY_CHOICES)
            airtable.ensure_fields({SCALE_AUDIT_FIELD: "multilineText"})
            return
        ensure_fields = getattr(airtable, "ensure_fields", None)
        if callable(ensure_fields):
            try:
                ensure_fields(dict(SCALE_FIELDS), execute=True)
            except TypeError:
                ensure_fields(dict(SCALE_FIELDS))
    except Exception as error:  # noqa: BLE001 - schema setup must not stop a paid run
        print(f"[WARN] Could not ensure scale audit fields: {error}")


def _typecast_patch(airtable: Any, record_id: str, fields: dict[str, str]) -> bool:
    """Last-resort field write, used when the client's batch update has no typecast."""
    request = getattr(airtable, "_request", None)
    base_id = str(getattr(airtable, "base_id", "") or "")
    table_id = str(getattr(airtable, "table_id", "") or "")
    if not callable(request) or not base_id or not table_id:
        return False
    try:
        response = request(
            "PATCH",
            f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}",
            json={"fields": fields, "typecast": True},
        )
    except Exception:  # noqa: BLE001
        return False
    return bool(getattr(response, "ok", False))


def write_scale_fields(
    airtable: Any,
    record_id: str,
    results: Sequence[tuple[int, ScaleGuardResult] | ScaleGuardResult],
    *,
    ensure_on_failure: bool = True,
) -> None:
    """Persist the audit without ever failing the pipeline."""
    fields = merge_scale_fields(results)
    if not fields or not record_id:
        return
    try:
        airtable.update_records([(record_id, fields)])
        return
    except Exception as error:  # noqa: BLE001
        if not ensure_on_failure:
            print(f"[WARN] Could not write scale audit to {record_id}: {error}")
            return
    ensure_scale_fields(airtable)
    try:
        airtable.update_records([(record_id, fields)])
        return
    except Exception as error:  # noqa: BLE001
        if _typecast_patch(airtable, record_id, fields):
            return
        print(f"[WARN] Could not write scale audit to {record_id}: {error}")
