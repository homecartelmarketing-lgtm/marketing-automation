"""Fal AI Nano Banana Pro CTA conversion checkpoint for the dedicated CTA table."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

from .assets import AssetCatalog
from .config import Settings
from .errors import AssetValidationError
from .fal_client import FalClient
from .overlay import (
    CTA_STORY_TEXT_BOX,
    HOMECARTEL_STORY_LOGO_BOX,
    stamp_cta_story_watermark_and_logo,
)
from .phased_content import (
    JsonlRunLogger,
    PhasedContentRunner,
)
from .scraping.airtable import ScrapeAirtableClient


CTA_TABLE_ID = "tblYHdVq14FjMWg5o"
SOURCE_FIELD = "CTA Blended Image"
SOURCE_FIELD_FALLBACKS = ["CTA Blended Image", "CTA Blended", "CTA Interior", "CTA Interior Image", "Interior", "Interior Image"]
LAYOUT_FIELD = "CTA Blended Image Watermark Layout"
LAYOUT_FIELD_FALLBACKS = [
    "CTA Blended Image Watermark Layout",
    "Watermark Layout",
    "CTA Watermark Layout",
    "CTA Layout",
]
LOGO_FIELD = "Logo"
LOGO_FIELD_FALLBACKS = [
    "Logo",
    "Brand Logo",
    "Watermark",
    "Logo Image",
    "CTA Blended Image Watermark Layout",
    "Watermark Layout",
]
WORD_GENERATED_FIELD = "Word Generated"
WORD_GENERATED_FALLBACKS = [
    "Word Generated",
    "Word Generate",
    "Generated Words",
    "Words Generated",
    "CTA Headline",
    "Headline",
]
OUTPUT_FIELD = "CTA Converted Image"
OUTPUT_FIELD_FALLBACKS = [
    "CTA Converted Image",
    "CTA Converted Blended",
    "Watermark Added",
    "Watemark Added",
    "CTA Watermark Added",
]
STATUS_PROCESSING = "CTA Conversion - Processing"
STATUS_FAILED = "CTA Conversion - Failed"
FAL_NANO_BANANA_MODEL = "fal-ai/nano-banana-pro/edit"


def _get_first_field_value(fields: dict[str, Any], candidates: list[str]) -> Any:
    for name in candidates:
        val = fields.get(name)
        if val:
            return val
    return None


def _get_first_field_name(fields: dict[str, Any], candidates: list[str]) -> str:
    for name in candidates:
        if name in fields:
            return name
    return candidates[0]


def _attachment_url(fields: dict[str, Any], field_name_or_candidates: str | list[str]) -> str:
    candidates = [field_name_or_candidates] if isinstance(field_name_or_candidates, str) else field_name_or_candidates
    value = _get_first_field_value(fields, candidates)
    if isinstance(value, list) and value and isinstance(value[0], dict):
        url = str(value[0].get("url") or "").strip()
        if url:
            return url
    elif isinstance(value, dict):
        url = str(value.get("url") or "").strip()
        if url:
            return url
    raise AssetValidationError(f"Missing accessible attachment from candidate fields: {candidates}")


def _record_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    return str(record.get("createdTime") or ""), str(record.get("id") or "")


def run_cta_conversion(
    settings: Settings,
    *,
    table_id: str = CTA_TABLE_ID,
    max_items: int = 1,
    target_record_id: str | None = None,
    airtable: ScrapeAirtableClient | None = None,
    fal: FalClient | None = None,
    model: str = FAL_NANO_BANANA_MODEL,
    aspect_ratio: str = "9:16",
    logger: JsonlRunLogger | None = None,
    use_local_pil: bool | None = None,
) -> bool:
    """Convert CTA background with Logo & CTA Watermark layout using local Python PIL or Fal AI."""
    client = airtable or ScrapeAirtableClient(
        settings.airtable_token, settings.airtable_base_id, table_id
    )
    run_logger = logger or JsonlRunLogger(settings.workspace, "cta_story", uuid.uuid4().hex)
    client.ensure_fields(
        {
            OUTPUT_FIELD: "multipleAttachments",
        }
    )
    client.ensure_single_select_options(
        "Status", [STATUS_PROCESSING, STATUS_FAILED, "Complete"]
    )
    all_fields_to_fetch = list(
        set(
            SOURCE_FIELD_FALLBACKS
            + LAYOUT_FIELD_FALLBACKS
            + LOGO_FIELD_FALLBACKS
            + WORD_GENERATED_FALLBACKS
            + OUTPUT_FIELD_FALLBACKS
            + ["Furniture Item", "Item Name", "SKU", "Status"]
        )
    )
    records = sorted(
        client.list_records(all_fields_to_fetch),
        key=_record_sort_key,
    )
    if target_record_id:
        eligible = [
            record
            for record in records
            if str(record["id"]) == str(target_record_id)
            and _get_first_field_value(record.get("fields", {}), SOURCE_FIELD_FALLBACKS)
        ]
    else:
        eligible = [
            record
            for record in records
            if _get_first_field_value(record.get("fields", {}), SOURCE_FIELD_FALLBACKS)
            and not _get_first_field_value(record.get("fields", {}), OUTPUT_FIELD_FALLBACKS)
        ][:max_items]
    if not eligible:
        run_logger.event("no_eligible_records", table_id=table_id)
        return True

    output_root = settings.output_dir / "cta_story" / "conversion"
    output_root.mkdir(parents=True, exist_ok=True)
    failures = 0

    should_use_api = (use_local_pil is False) or (use_local_pil is None and fal is not None)
    if should_use_api and fal is not None:
        prompt = AssetCatalog(settings.workspace).read_prompt("CTA/CTA.json")
        for record in eligible:
            record_id = str(record["id"])
            try:
                client.update_records([(record_id, {"Status": STATUS_PROCESSING})])
                run_logger.event("phase_started", record_id=record_id, phase="conversion")
                fields = record.get("fields", {})
                source_url = _attachment_url(fields, SOURCE_FIELD_FALLBACKS)
                layout_url = _attachment_url(fields, LAYOUT_FIELD_FALLBACKS)

                source_path = output_root / f"{record_id}_cta_source.jpg"
                PhasedContentRunner._download(source_url, source_path)
                PhasedContentRunner._validate_9_16(source_path, SOURCE_FIELD)

                input_urls = [source_url, layout_url]
                generated_url = fal.generate(
                    prompt,
                    input_urls,
                    aspect_ratio=aspect_ratio,
                    resolution="1K",
                    model=model,
                )
                provider_label = "fal"

                output_path = output_root / f"{record_id}_cta_converted.jpg"
                PhasedContentRunner._download(generated_url, output_path)
                PhasedContentRunner._validate_9_16(output_path, OUTPUT_FIELD)
                target_out_field = _get_first_field_name(fields, OUTPUT_FIELD_FALLBACKS)
                client.upload_attachment(record_id, target_out_field, output_path, output_path.name)
                client.update_records([(record_id, {"Status": "Complete"})])
                run_logger.event(
                    "phase_completed",
                    record_id=record_id,
                    phase="conversion",
                    provider=provider_label,
                    model=model,
                    aspect_ratio=aspect_ratio,
                    attachment_filename=output_path.name,
                )
            except Exception as error:
                failures += 1
                client.update_records([(record_id, {"Status": STATUS_FAILED})])
                run_logger.event(
                    "phase_failed", record_id=record_id, phase="conversion", error=str(error)
                )
        return failures == 0

    # Default: Local Python Pillow Stamping (Logo + Locked CTA Text Watermark Layout)
    for record in eligible:
        record_id = str(record["id"])
        try:
            client.update_records([(record_id, {"Status": STATUS_PROCESSING})])
            run_logger.event("phase_started", record_id=record_id, phase="conversion")
            fields = record.get("fields", {})

            source_url = _attachment_url(fields, SOURCE_FIELD_FALLBACKS)
            source_path = output_root / f"{record_id}_cta_source.jpg"
            PhasedContentRunner._download(source_url, source_path)
            PhasedContentRunner._validate_9_16(source_path, SOURCE_FIELD)

            # Resolve Logo URL from record, other records, or local assets
            logo_url = ""
            try:
                logo_url = _attachment_url(fields, LOGO_FIELD_FALLBACKS)
            except Exception:
                for other in records:
                    try:
                        logo_url = _attachment_url(other.get("fields", {}), LOGO_FIELD_FALLBACKS)
                        if logo_url:
                            break
                    except Exception:
                        continue

            logo_path = None
            if logo_url:
                logo_path = output_root / f"{record_id}_logo.png"
                PhasedContentRunner._download(logo_url, logo_path)
            else:
                candidate_local_logos = [
                    Path("assets/homecartel_logo.png"),
                    Path("JSON Prompts/homecartel_logo.png"),
                    Path("content_automation/assets/logo.png"),
                    Path("static/img/logo.png"),
                    Path("scratch/refined_logo.png"),
                    Path("logo.png"),
                ]
                for p in candidate_local_logos:
                    if p.is_file():
                        logo_path = p
                        break

            # If this record does not have a Logo attached yet, upload it
            if not _get_first_field_value(fields, LOGO_FIELD_FALLBACKS) and logo_path and Path(logo_path).is_file():
                try:
                    target_logo_field = _get_first_field_name(fields, LOGO_FIELD_FALLBACKS)
                    client.upload_attachment(record_id, target_logo_field, Path(logo_path), "homecartel_logo.png")
                except Exception:
                    pass

            headline_text = str(
                _get_first_field_value(fields, WORD_GENERATED_FALLBACKS)
                or fields.get("Item Name")
                or fields.get("SKU")
                or "Singkwenta Dose"
            ).strip()

            output_path = output_root / f"{record_id}_cta_converted.jpg"
            stamp_cta_story_watermark_and_logo(
                source_path,
                logo_path=logo_path,
                item_name=headline_text,
                destination=output_path,
                headline_font_size=48,
                body_font_size=28,
            )

            PhasedContentRunner._validate_9_16(output_path, OUTPUT_FIELD)
            target_out_field = _get_first_field_name(fields, OUTPUT_FIELD_FALLBACKS)
            client.upload_attachment(record_id, target_out_field, output_path, output_path.name)
            client.update_records([(record_id, {"Status": "Complete"})])
            run_logger.event(
                "phase_completed",
                record_id=record_id,
                phase="conversion",
                provider="pillow",
                model="local_pillow",
                aspect_ratio=aspect_ratio,
                attachment_filename=output_path.name,
            )
        except Exception as error:
            failures += 1
            client.update_records([(record_id, {"Status": STATUS_FAILED})])
            run_logger.event(
                "phase_failed", record_id=record_id, phase="conversion", error=str(error)
            )

    return failures == 0

