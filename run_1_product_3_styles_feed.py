"""1 Product, 3 Styles Feed (4-Phase AI Content Automation Pipeline).

Flow Architecture:
1. Phase 1 (Akeneo 1-Item Scrape):
   Scrapes 1 modern product into 1 Airtable row (Furniture Item, SKU, Item Name)
   with Status -> 'Standby'.
2. Phase 2 (Krea AI Room Interiors - 3 Styles @ 4:5 1K):
   Generates 3 distinct room styles/interiors at 4:5 aspect ratio, 1K resolution
   using Krea AI (krea-2-medium) with the category moodboard.
   Uploads to 'Interior1', 'Interior2', 'Interior3' (or 'Interior').
   Status -> 'Phase 2 - Ready'.
3. Phase 3 (Fal AI Claude Sonnet 5 Prompt Analysis):
   Uses anthropic/claude-sonnet-5 via Fal AI vision to analyze the 1 product against
   each of the 3 room styles and write tailored blending prompts to 'Prompt1', 'Prompt2', and 'Prompt3' (Long Text).
   Status -> 'Phase 3 - Ready'.
4. Phase 4 (Fal AI Nano Banana Pro Blending @ 4:5, 1K Quality + Canva Logo Stamping on Slide 1):
   Blends the product into the 3 room styles using Prompt1, Prompt2, and Prompt3 via fal-ai/nano-banana-pro/edit (4:5, 1K).
   Stamps the official HomeCartel® logo from 'Logo' onto the 1st blended image (W=190.3, H=63.5, X=108.0, Y=1178.5).
   Uploads all 3 images into '1 Product 3 Style Blended'.
   Status -> 'Complete'.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from PIL import Image, UnidentifiedImageError

from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.config import load_settings
from content_automation.errors import AssetValidationError, AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.prompts import build_vision_blending_instruction
from content_automation.krea_client import KreaClient
from content_automation.item_tagger import (
    TARGET_BLENDED_FIELD,
    tag_blended_image,
)
from content_automation.overlay import HOMECARTEL_LOGO_BOX, stamp_logo
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.furniture_item import (
    fetch_all_base_existing_identities,
    format_item_name_with_product_type,
)
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    identity_key,
    select_new_products,
)
from content_automation.media import attachment_filename
from content_automation.shopify_client import ShopifyClient

PHT = timezone(timedelta(hours=8))  # Philippine Standard Time (UTC+8)


def pht_timestamp() -> str:
    return datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p PHT")


@dataclass(frozen=True) 
class RoomStyleSpec:
    slot: int
    name: str
    prompt: str
    target_interior_field: str
    target_prompt_field: str
    output_filename: str


@dataclass(frozen=True)
class PipelinePreset:
    key: str
    name: str
    category_code: str
    table_id: str
    moodboard_id: str
    room_styles: tuple[RoomStyleSpec, ...]


PRESETS: dict[str, PipelinePreset] = {
    "chandeliers": PipelinePreset(
        key="chandeliers",
        name="Chandeliers",
        category_code="chandeliers",
        table_id=os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_1_PRODUCT_3_STYLES", "").strip()
        or os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_ONE_PRODUCT_THREE_STYLES", "").strip()
        or os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS", "").strip()
        or "tblrlfqBGe5EjS5PI",
        moodboard_id=os.getenv("KREA_MOODBOARD_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES", "").strip()
        or "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        room_styles=(
            RoomStyleSpec(
                slot=1,
                name="Grand Living Room",
                prompt="Generate me a luxury modern grand living room with hanging chandelier",
                target_interior_field="Interior1",
                target_prompt_field="Prompt1",
                output_filename="1_product_3_styles_blended1.jpg",
            ),
            RoomStyleSpec(
                slot=2,
                name="Luxury Dining Room",
                prompt="Generate me a luxury modern dining room with hanging chandelier",
                target_interior_field="Interior2",
                target_prompt_field="Prompt2",
                output_filename="1_product_3_styles_blended2.jpg",
            ),
            RoomStyleSpec(
                slot=3,
                name="High Ceiling Foyer",
                prompt="Generate me a luxury modern high ceiling entryway foyer with hanging chandelier",
                target_interior_field="Interior3",
                target_prompt_field="Prompt3",
                output_filename="1_product_3_styles_blended3.jpg",
            ),
        ),
    ),
    "pendant_lights": PipelinePreset(
        key="pendant_lights",
        name="Pendant Lights",
        category_code="pendant_lights",
        table_id=os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_1_PRODUCT_3_STYLES", "").strip()
        or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_ONE_PRODUCT_THREE_STYLES", "").strip()
        or os.getenv("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_3_PRODUCT_1_STYLE", "").strip()
        or "tblRy52kCasisCWzd",
        moodboard_id=os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
        or "2a4a62bf-c6eb-49f8-8808-2543200634a0",
        room_styles=(
            RoomStyleSpec(
                slot=1,
                name="Dining Room",
                prompt="Generate me a luxury modern dining room with hanging pendant light",
                target_interior_field="Interior1",
                target_prompt_field="Prompt1",
                output_filename="1_product_3_styles_blended1.jpg",
            ),
            RoomStyleSpec(
                slot=2,
                name="Kitchen Island",
                prompt="Generate me a luxury modern kitchen island with hanging pendant light",
                target_interior_field="Interior2",
                target_prompt_field="Prompt2",
                output_filename="1_product_3_styles_blended2.jpg",
            ),
            RoomStyleSpec(
                slot=3,
                name="Living Room Corner",
                prompt="Generate me a luxury modern living room with hanging pendant light",
                target_interior_field="Interior3",
                target_prompt_field="Prompt3",
                output_filename="1_product_3_styles_blended3.jpg",
            ),
        ),
    ),
    "floor_lamps": PipelinePreset(
        key="floor_lamps",
        name="Floor Lamps",
        category_code="floor_lamps",
        table_id=os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_1_PRODUCT_3_STYLES", "").strip()
        or os.getenv("AIRTABLE_TABLE_ID_FLOOR_LAMPS_ONE_PRODUCT_THREE_STYLES", "").strip()
        or "tbl9GIq2QeYCwMhWU",
        moodboard_id=os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
        or os.getenv("KREA_MOODBOARD_ID_STYLE_THIS_FLOOR_LAMPS", "").strip()
        or "b1641228-beec-4823-8d01-1de3eec8410d",
        room_styles=(
            RoomStyleSpec(
                slot=1,
                name="Living Room Lounge",
                prompt="Generate me a luxury modern living room lounge with standing floor lamp",
                target_interior_field="Interior1",
                target_prompt_field="Prompt1",
                output_filename="1_product_3_styles_blended1.jpg",
            ),
            RoomStyleSpec(
                slot=2,
                name="Bedroom Corner",
                prompt="Generate me a luxury modern bedroom corner with standing floor lamp",
                target_interior_field="Interior2",
                target_prompt_field="Prompt2",
                output_filename="1_product_3_styles_blended2.jpg",
            ),
            RoomStyleSpec(
                slot=3,
                name="Study Reading Nook",
                prompt="Generate me a luxury modern study reading nook with standing floor lamp",
                target_interior_field="Interior3",
                target_prompt_field="Prompt3",
                output_filename="1_product_3_styles_blended3.jpg",
            ),
        ),
    ),
}

KREA_ASPECT_RATIO = "4:5"
KREA_RESOLUTION = "1K"
KREA_MODEL_LABEL = "krea-2-medium"

FAL_CLAUDE_MODEL = "anthropic/claude-sonnet-5"
FAL_CLAUDE_ENDPOINT = "openrouter/router/vision"

FAL_NANO_MODEL = "fal-ai/nano-banana-pro/edit"
FAL_NANO_ASPECT_RATIO = "4:5"
FAL_NANO_RESOLUTION = "1k"

FURNITURE_FIELD = "Furniture Item"
SKU_FIELD = "SKU"
ITEM_NAME_FIELD = "Item Name"
LOGO_FIELD = "Logo"
INTERIOR_FIELDS = ["Interior1", "Interior2", "Interior3"]
PROMPT_FIELDS = ["Prompt1", "Prompt2", "Prompt3"]
BLENDED_FIELD = "1 Product 3 Style Blended"
BLENDED_FIELD_FALLBACKS = [
    "1 Product 3 Style Blended",
    "1 Style 3 Product Blended",
    "Blended Image",
]
STATUS_FIELD = "Status"


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


def append_audit_log(log_entry: dict[str, Any], log_path: Path) -> None:
    """Append a complete, raw, and indented JSON audit record for human auditing."""
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
    log_path.write_text(
        json.dumps(logs, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"[AUDIT LOG] Appended log record to {log_path.name}")


class OneProductThreeStylesRunner:
    def __init__(
        self,
        preset: PipelinePreset,
        *,
        table_id_override: str | None = None,
        moodboard_id_override: str | None = None,
        prompt_override: str | None = None,
        style_code: str | None = None,
        settings: Any = None,
        airtable: ScrapeAirtableClient | None = None,
        akeneo: AkeneoClient | None = None,
        krea: KreaClient | None = None,
        fal: FalClient | None = None,
        logger: JsonlRunLogger | None = None,
    ) -> None:
        self.preset = preset
        self.table_id = table_id_override or preset.table_id
        self.category_code = preset.category_code
        self.style_code = (
            style_code or os.getenv("AKENEO_STYLE", "modern").strip() or "modern"
        )
        self.moodboard_id = moodboard_id_override or preset.moodboard_id

        # Resolve prompt override for Style 1 from argument or environment
        env_prompt_key = {
            "chandeliers": "ONE_PRODUCT_3_STYLES_PROMPT_CHANDELIER",
            "pendant_lights": "ONE_PRODUCT_3_STYLES_PROMPT_PENDANT",
            "floor_lamps": "ONE_PRODUCT_3_STYLES_PROMPT_FLOOR_LAMP",
        }.get(preset.key, "")
        self.prompt_override = (
            (prompt_override or "").strip()
            or (os.getenv(env_prompt_key, "").strip() if env_prompt_key else "")
            or None
        )

        self.settings = settings or load_settings()
        self.airtable = airtable or ScrapeAirtableClient(
            self.settings.airtable_token, self.settings.airtable_base_id, self.table_id
        )
        self.akeneo = akeneo or AkeneoClient(
            self.settings.akeneo_host,
            self.settings.akeneo_client_id,
            self.settings.akeneo_secret,
            self.settings.akeneo_username,
            self.settings.akeneo_password,
            channel_name=os.getenv("CHANNEL_NAME", "home_cartel"),
        )
        self.krea = krea or KreaClient(
            self.settings.krea_token, self.settings.krea_base_url
        )
        self.fal = fal or FalClient(self.settings.fal_key)
        self.run_id = uuid.uuid4().hex
        self.logger = logger or JsonlRunLogger(
            self.settings.workspace,
            f"1_product_3_styles_{self.preset.key}",
            self.run_id,
        )

    @property
    def audit_log_dir(self) -> Path:
        path = self.settings.workspace / "output" / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def artifact_root(self) -> Path:
        path = (
            self.settings.output_dir
            / "1_product_3_styles_feed"
            / self.preset.key
            / "artifacts"
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _artifact_path(self, record_id: str, filename: str) -> Path:
        path = self.artifact_root / record_id
        path.mkdir(parents=True, exist_ok=True)
        return path / filename

    def _schema_fields(self) -> dict[str, str]:
        return {
            FURNITURE_FIELD: "multipleAttachments",
            SKU_FIELD: "multilineText",
            ITEM_NAME_FIELD: "multilineText",
            LOGO_FIELD: "multipleAttachments",
            "Interior1": "multipleAttachments",
            "Interior2": "multipleAttachments",
            "Interior3": "multipleAttachments",
            "Interior": "multipleAttachments",
            "Prompt1": "multilineText",
            "Prompt2": "multilineText",
            "Prompt3": "multilineText",
            BLENDED_FIELD: "multipleAttachments",
        }

    def _status_values(self) -> list[str]:
        return [
            "Standby",
            "Phase 2 - Processing",
            "Phase 2 - Ready",
            "Phase 2 - Failed",
            "Phase 3 - Processing",
            "Phase 3 - Ready",
            "Phase 3 - Failed",
            "Phase 4 - Processing",
            "Phase 4 - Failed",
            "Complete",
            "Posted",
            "Discard",
            "Minor Revision",
            "For Manual",
            "Error",
        ]

    def preflight(self) -> None:
        self.airtable.ensure_fields(self._schema_fields())
        self.airtable.ensure_single_select_options("Status", self._status_values())
        self.logger.event(
            "preflight_completed", table_id=self.table_id, preset=self.preset.key
        )
        print(
            f"[PREFLIGHT] Schema verified for table {self.table_id} ({self.preset.name})"
        )

    @staticmethod
    def _has_attachment(fields: dict[str, Any], field_name: str) -> bool:
        return bool(fields.get(field_name) or [])

    def _get_blended_field_name(self, fields: dict[str, Any]) -> str:
        for name in BLENDED_FIELD_FALLBACKS:
            if name in fields:
                return name
        return BLENDED_FIELD

    @staticmethod
    def _attachment_url(fields: dict[str, Any], field_name: str) -> str:
        attachments = fields.get(field_name) or []
        if (
            isinstance(attachments, list)
            and attachments
            and isinstance(attachments[0], dict)
        ):
            url = str(attachments[0].get("url") or "").strip()
            if url:
                return url
        raise AssetValidationError(f"Missing accessible attachment: {field_name}")

    def _get_logo_url(self, record_fields: dict[str, Any]) -> str:
        """Find logo attachment URL from current record or table records."""
        # 1. Current record
        for key in (LOGO_FIELD, "Watermark Layout", "Moodboard Watermark", "watermark", "Logo Image"):
            if self._has_attachment(record_fields, key):
                try:
                    return self._attachment_url(record_fields, key)
                except Exception:
                    pass

        # 2. Search any record in the table for a Logo attachment
        try:
            records = self.airtable.list_records([LOGO_FIELD, "Watermark Layout", "Moodboard Watermark"])
            for r in records:
                rf = r.get("fields", {})
                for key in (LOGO_FIELD, "Watermark Layout", "Moodboard Watermark"):
                    if self._has_attachment(rf, key):
                        try:
                            return self._attachment_url(rf, key)
                        except Exception:
                            pass
        except Exception:
            pass

        return ""

    def _get_interior_urls(self, fields: dict[str, Any]) -> list[str]:
        """Extract URLs for the 3 room interiors from Interior1..3 or multi-attachment Interior."""
        urls: list[str] = []
        for slot_field in INTERIOR_FIELDS:
            if self._has_attachment(fields, slot_field):
                urls.append(self._attachment_url(fields, slot_field))

        if len(urls) >= 3:
            return urls[:3]

        # Fallback: Check multi-attachment 'Interior'
        shared_interior = fields.get("Interior") or []
        if isinstance(shared_interior, list):
            for att in shared_interior:
                if isinstance(att, dict) and att.get("url"):
                    urls.append(str(att["url"]).strip())

        if len(urls) >= 3:
            return urls[:3]

        return urls

    @staticmethod
    def _validate_image_file(path: Path, label: str) -> None:
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as error:
            raise AssetValidationError(f"Unreadable {label}: {path}") from error

    @staticmethod
    def _download(url: str, destination: Path) -> Path:
        response = requests.get(url, stream=True, timeout=180)
        if not response.ok:
            raise ProviderError(
                f"Download generated media failed ({response.status_code})"
            )
        temporary = destination.with_suffix(destination.suffix + ".part")
        with temporary.open("wb") as stream:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    stream.write(chunk)
        temporary.replace(destination)
        return destination

    def _update_status(self, record_id: str, status: str) -> None:
        self.airtable.update_records([(record_id, {STATUS_FIELD: status})])
        self.logger.event("status_updated", record_id=record_id, status=status)

    def _records(self) -> list[dict[str, Any]]:
        fields = list(self._schema_fields()) + [STATUS_FIELD]
        records = self.airtable.list_records(fields)
        return sorted(
            records,
            key=lambda item: (
                str(item.get("createdTime") or ""),
                str(item.get("id") or ""),
            ),
        )

    def _phase_for_record(self, record: dict[str, Any]) -> int | None:
        fields = record.get("fields", {})
        status = str(fields.get(STATUS_FIELD) or "").strip().lower()
        if (
            status in (
                "error",
                "skip",
                "skipped",
                "ignore",
                "disabled",
                "posted",
                "complete",
                "completed",
                "discard",
                "discarded",
                "minor revision",
                "minor revisions",
                "for manual",
                "fm",
            )
            or "error" in status
        ):
            return None

        # Check 1 product
        if not self._has_attachment(fields, FURNITURE_FIELD):
            return None

        interior_urls = self._get_interior_urls(fields)
        if len(interior_urls) < 3:
            return 2

        # Check if all 3 prompts are populated
        has_prompts = (
            str(fields.get("Prompt1") or "").strip()
            and str(fields.get("Prompt2") or "").strip()
            and str(fields.get("Prompt3") or "").strip()
        )
        if not has_prompts:
            return 3

        blended_field = self._get_blended_field_name(fields)
        blended_count = len(fields.get(blended_field) or [])
        if blended_count < 3:
            return 4

        return None

    def _next_incomplete(self) -> tuple[dict[str, Any] | None, int]:
        for record in self._records():
            next_phase = self._phase_for_record(record)
            if next_phase:
                return record, next_phase
        return None, 0

    def _find_for_phase(self, phase: int) -> dict[str, Any] | None:
        for record in self._records():
            if self._phase_for_record(record) == phase:
                return record
        return None

    def run(
        self,
        phase: int | str = "all",
        target_record_id: str | None = None,
        max_rows: int = 1,
        scrape_first: bool = False,
    ) -> None:
        self.preflight()
        if phase == "all":
            if target_record_id:
                record = self.airtable.get_record(target_record_id)
                start_phase = self._phase_for_record(record) or 2
                for phase_num in range(start_phase, 5):
                    self._run_phase(phase_num, record["id"])
                return

            for _ in range(max_rows):
                record = None
                start_phase = 2
                if scrape_first:
                    scraped_records = self.phase_1(max_items=1)
                    if scraped_records:
                        record = scraped_records[0]
                        start_phase = 2
                if record is None:
                    record, start_phase = self._next_incomplete()
                    if record is None:
                        scraped_records = self.phase_1(max_items=1)
                        if not scraped_records:
                            break
                        record = scraped_records[0]
                        start_phase = 2

                for phase_num in range(start_phase, 5):
                    self._run_phase(phase_num, record["id"])
            return

        phase_number = int(phase)
        if phase_number == 1:
            self.phase_1(max_items=max_rows)
            return

        if target_record_id:
            record = self.airtable.get_record(target_record_id)
        else:
            record = self._find_for_phase(phase_number)

        if record is None:
            raise AutomationError(
                f"No Airtable row is eligible for phase {phase_number}"
            )
        self._run_phase(phase_number, record["id"])

    def _run_phase(self, phase: int, record_id: str) -> None:
        phase_names = {
            1: "Akeneo 1-Product Ingestion",
            2: "Krea AI Room Interiors (3 Styles @ 4:5 1K)",
            3: "Fal AI Claude Sonnet 5 Vision Prompt Analysis (Prompt1, Prompt2, Prompt3)",
            4: "Fal AI Nano Banana Pro Multi-Blending (4:5, 1K Quality + Slide 1 Logo)",
        }
        phase_label = phase_names.get(phase, f"Phase {phase}")
        print(
            f"\n[INFO] >>> Starting Phase {phase}/4: {phase_label} for record {record_id}...",
            flush=True,
        )
        self._update_status(record_id, f"Phase {phase} - Processing")
        self.logger.event("phase_started", record_id=record_id, phase=phase)
        try:
            if phase == 2:
                self.phase_2(record_id)
            elif phase == 3:
                self.phase_3(record_id)
            elif phase == 4:
                self.phase_4(record_id)

            if phase == 4:
                self._update_status(record_id, "Complete")
                print(
                    f"[OK] Record {record_id} is 100% COMPLETE! 3 Blended images (Slide 1 with logo) uploaded to '{BLENDED_FIELD}'.\n",
                    flush=True,
                )
            else:
                self._update_status(record_id, f"Phase {phase} - Ready")
                print(
                    f"[OK] Phase {phase} completed successfully for record {record_id}.\n",
                    flush=True,
                )
            self.logger.event("phase_completed", record_id=record_id, phase=phase)
        except Exception as error:
            self._update_status(record_id, f"Phase {phase} - Failed")
            print(
                f"[ERROR] Phase {phase} failed for record {record_id}: {error}\n",
                flush=True,
            )
            self.logger.event(
                "phase_failed", record_id=record_id, phase=phase, error=str(error)
            )
            raise

    # -------------------------------------------------------------------------
    # PHASE 1: AKENEO PRODUCT SCRAPE (WITH CROSS-TABLE DEDUPLICATION)
    # -------------------------------------------------------------------------
    def phase_1(
        self,
        max_items: int = 1,
        cross_table_dedup: bool = True,
        shopify_cross_check: bool = True,
    ) -> list[dict[str, Any]]:
        print(
            f"\n[INFO] >>> Starting Phase 1: Akeneo Product Ingestion ({self.category_code}, style={self.style_code})...",
            flush=True,
        )
        self.logger.event(
            "phase_started",
            phase=1,
            category=self.category_code,
            style=self.style_code,
        )
        self.akeneo.authenticate()

        # 1. Gather all existing SKUs, Item Names, and attachment filenames from the current table
        records = self.airtable.list_records([SKU_FIELD, FURNITURE_FIELD, ITEM_NAME_FIELD])
        existing_skus: set[str] = set()
        existing_names: set[str] = set()
        existing_filenames: set[str] = set()

        for r in records:
            f = r.get("fields", {})
            val = str(f.get(SKU_FIELD) or "").strip()
            if val:
                existing_skus.add(val)
                existing_skus.add(identity_key(val))
            name_val = str(f.get(ITEM_NAME_FIELD) or "").strip()
            if name_val:
                existing_names.add(identity_key(name_val))
                if " | " in name_val:
                    base_part = name_val.split(" | ")[0].strip()
                    if base_part:
                        existing_names.add(identity_key(base_part))
            for att in f.get(FURNITURE_FIELD) or []:
                if isinstance(att, dict) and att.get("filename"):
                    existing_filenames.add(identity_key(att["filename"]))

        # 2. Cross-table deduplication scan across all tables in the Airtable base
        if cross_table_dedup and getattr(self.airtable, "base_id", None):
            try:
                print("[INFO] Performing cross-table deduplication scan across all Airtable tables...")
                base_skus, base_names, base_files = fetch_all_base_existing_identities(self.airtable)
                existing_skus.update(base_skus)
                existing_names.update(base_names)
                existing_filenames.update(base_files)
                print(
                    f"[INFO] Cross-table deduplication active: Found {len(base_skus)} existing SKU(s), "
                    f"{len(base_names)} item name(s), and {len(base_files)} attachment filename(s) across all base tables."
                )
            except Exception as dedup_err:
                print(f"[WARN] Cross-table deduplication scan note: {dedup_err}")

        # 3. Shopify Cross-check (only scrape products that actually exist/are published on Shopify)
        shopify_index = None
        if shopify_cross_check:
            try:
                shopify = ShopifyClient()
                shopify_index = shopify.load_published_identities()
            except Exception as s_err:
                print(f"[WARN] Shopify cross-check initialization note: {s_err}")

        # 4. Query Akeneo for active/enabled items
        akeneo_cat = akeneo_category_code(self.category_code)
        query: dict[str, Any] = {
            "categories": [{"operator": "IN", "value": [akeneo_cat]}],
            "enabled": [{"operator": "=", "value": True}],
        }
        if self.style_code and self.style_code.lower() != "all":
            query["Style2"] = [{"operator": "IN", "value": [self.style_code]}]

        print(
            f"[INFO] Fetching active {self.style_code or 'all'} {self.category_code} products from Akeneo..."
        )
        products = self.akeneo.fetch_products(query)

        derived_names, derived_media = existing_product_identities(
            products, existing_skus
        )
        existing_names.update(derived_names)
        existing_filenames.update(derived_media)

        candidates, stats = select_new_products(
            products,
            existing_skus,
            existing_item_names=existing_names,
            existing_media_codes=existing_filenames,
            category_code=self.category_code,
        )

        filtered_items: list[ProductItem] = []
        for item in candidates:
            filename = attachment_filename(item.item_name, item.media_code)
            if identity_key(filename) in existing_filenames:
                print(f"[DEDUP SKIP] Existing item: '{item.item_name}' (SKU: {item.sku}) already exists in Airtable")
                continue
            if shopify_index and not shopify_index.contains(item.sku, item.item_name):
                print(f"[SHOPIFY SKIP] Item '{item.item_name}' (SKU: {item.sku}) is Enabled in Akeneo but Draft/Inactive in Shopify -> skipping")
                continue

            # Strict category and title keyword matching ("kung ano name ng table ids yan lang sscrape")
            searchable_title = f"{item.item_name} {item.product_type}".lower()
            if self.category_code == "chandeliers":
                if "chandelier" not in searchable_title:
                    print(f"[NAME FILTER SKIP] Item '{item.item_name}' does not contain 'chandelier' -> skipping")
                    continue
                if any(kw in searchable_title for kw in ("cluster", "linear")):
                    print(f"[NAME FILTER SKIP] Item '{item.item_name}' contains cluster/linear -> skipping for Chandeliers table")
                    continue
            elif self.category_code == "pendant_lights":
                if "pendant" not in searchable_title:
                    print(f"[NAME FILTER SKIP] Item '{item.item_name}' does not contain 'pendant' -> skipping")
                    continue
            elif self.category_code == "floor_lamps":
                if "floor" not in searchable_title:
                    print(f"[NAME FILTER SKIP] Item '{item.item_name}' does not contain 'floor' -> skipping")
                    continue

            print(f"[MATCH PASS] Valid candidate passed all checks: '{item.item_name}' (SKU: {item.sku})")
            filtered_items.append(item)

        if not filtered_items:
            raise AutomationError(
                f"Akeneo returned 0 new products for category '{self.category_code}' and style '{self.style_code}'."
            )

        items_to_create = filtered_items[:max_items]
        created_records: list[dict[str, Any]] = []

        for selected_item in items_to_create:
            display_name = format_item_name_with_product_type(
                selected_item.item_name,
                selected_item.product_type,
                category_code=self.category_code,
            )
            record_payload = {
                SKU_FIELD: selected_item.sku,
                ITEM_NAME_FIELD: display_name,
                STATUS_FIELD: "Standby",
            }
            record_id = self.airtable.create_record(record_payload)
            print(
                f"[OK] Created row {record_id} for Product: {selected_item.sku} ({display_name})"
            )

            # Download and upload media for the product
            download = None
            try:
                download = self.akeneo.download_media(selected_item.media_code)
                filename = attachment_filename(selected_item.item_name, selected_item.media_code)
                self.airtable.upload_attachment(
                    record_id, FURNITURE_FIELD, download, filename
                )
                print(f"  [+] Uploaded {selected_item.sku} to '{FURNITURE_FIELD}' ({filename})")
            finally:
                if download:
                    download.cleanup()

            self._update_status(record_id, "Standby")
            self.logger.event(
                "phase_completed",
                phase=1,
                record_id=record_id,
                sku=selected_item.sku,
            )
            append_audit_log(
                {
                    "timestamp": pht_timestamp(),
                    "record_id": record_id,
                    "sku": selected_item.sku,
                    "item_name": display_name,
                    "media_code": selected_item.media_code,
                    "category": self.category_code,
                    "style": self.style_code,
                    "table_id": self.table_id,
                    "status": "Standby",
                },
                self.audit_log_dir
                / f"1_product_3_styles_{self.preset.key}_akeneo_logs.json",
            )
            created_records.append(self.airtable.get_record(record_id))

        return created_records

    # -------------------------------------------------------------------------
    # PHASE 2: KREA AI ROOM INTERIORS (3 STYLES @ 4:5 1K)
    # -------------------------------------------------------------------------
    def phase_2(self, record_id: str) -> None:
        fields = self.airtable.get_record(record_id).get("fields", {})
        sku = str(fields.get(SKU_FIELD) or record_id)
        item_name = str(fields.get(ITEM_NAME_FIELD) or sku)

        print(
            f"  Generating 3 Room Style Interiors with Krea AI (Moodboard: {self.moodboard_id})...",
            flush=True,
        )
        krea_audit_logs: list[dict[str, Any]] = []
        downloaded_interiors: list[Path] = []

        for spec in self.preset.room_styles:
            active_prompt = spec.prompt
            if spec.slot == 1 and self.prompt_override:
                active_prompt = self.prompt_override
                print(
                    f"  [{spec.slot}/3] Style '{spec.name}' (Custom Prompt) -> \"{active_prompt}\"",
                    flush=True,
                )
            else:
                print(
                    f"  [{spec.slot}/3] Style '{spec.name}' -> Prompt: \"{active_prompt}\"",
                    flush=True,
                )
            url = self.krea.generate(
                active_prompt,
                aspect_ratio=KREA_ASPECT_RATIO,
                resolution=KREA_RESOLUTION,
                moodboard_id=self.moodboard_id,
            )
            dest = self._artifact_path(
                record_id, f"interior_style{spec.slot}_{record_id}.jpg"
            )
            self._download(url, dest)
            self._validate_image_file(dest, f"Interior Style {spec.slot}")
            downloaded_interiors.append(dest)

            # Upload to slot field (e.g. Interior1) and also support shared 'Interior'
            print(
                f"        Uploading to '{spec.target_interior_field}'...", flush=True
            )
            self.airtable.upload_attachment(
                record_id, spec.target_interior_field, dest, dest.name
            )

            krea_audit_logs.append(
                {
                    "slot": spec.slot,
                    "style_name": spec.name,
                    "prompt": active_prompt,
                    "output_url": url,
                    "local_path": str(dest),
                    "target_field": spec.target_interior_field,
                }
            )

        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=2,
            provider="krea",
            model=KREA_MODEL_LABEL,
            moodboard_id=self.moodboard_id,
            interiors_generated=len(downloaded_interiors),
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": sku,
                "item_name": item_name,
                "phase": "Phase 2: Krea AI 3-Style Room Interiors (4:5, 1K)",
                "api_provider": "Krea AI",
                "model": KREA_MODEL_LABEL,
                "moodboard_id": self.moodboard_id,
                "styles": krea_audit_logs,
            },
            self.audit_log_dir / f"1_product_3_styles_{self.preset.key}_krea_logs.json",
        )

    # -------------------------------------------------------------------------
    # PHASE 3: FAL AI CLAUDE SONNET 5 PROMPT ANALYSIS (PROMPT1, PROMPT2, PROMPT3)
    # -------------------------------------------------------------------------
    def phase_3(self, record_id: str) -> None:
        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})
        furniture_url = self._attachment_url(fields, FURNITURE_FIELD)
        interior_urls = self._get_interior_urls(fields)

        if len(interior_urls) < 3:
            raise AssetValidationError(
                f"Record {record_id} requires 3 interior images from Phase 2; found {len(interior_urls)}"
            )

        updates: dict[str, str] = {}
        claude_audit_logs: list[dict[str, Any]] = []
        raw_item_name = str(fields.get(ITEM_NAME_FIELD) or "").strip()

        for idx, spec in enumerate(self.preset.room_styles):
            interior_url = interior_urls[idx]
            prompt_field = spec.target_prompt_field

            system_instruction = build_vision_blending_instruction(
                interior_label=f"Modern Room Interior ({spec.name})",
                item_name=raw_item_name,
                aspect_ratio="4:5",
            )

            print(
                f"  [{idx + 1}/3] Analyzing Interior Style {idx + 1} ({spec.name}) + Furniture Item with Fal Claude Sonnet 5...",
                flush=True,
            )
            prompt_text = self.fal.generate_vision_prompt(
                image_urls=[interior_url, furniture_url],
                prompt=system_instruction,
                model=FAL_CLAUDE_MODEL,
                endpoint=FAL_CLAUDE_ENDPOINT,
            )
            updates[prompt_field] = prompt_text
            print(f"        Saved to '{prompt_field}': \"{prompt_text[:90]}...\"")

            claude_audit_logs.append(
                {
                    "slot": spec.slot,
                    "style_name": spec.name,
                    "target_prompt_field": prompt_field,
                    "input_interior_url": interior_url,
                    "input_furniture_url": furniture_url,
                    "generated_prompt": prompt_text,
                }
            )

        self.airtable.update_records([(record_id, updates)])
        print(f"  [OK] Saved Prompt1, Prompt2, Prompt3 (Long Text) to Airtable.")

        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=3,
            provider="fal",
            model=FAL_CLAUDE_MODEL,
            prompts_generated=len(updates),
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get(SKU_FIELD) or ""),
                "item_name": str(fields.get(ITEM_NAME_FIELD) or record_id),
                "phase": "Phase 3: Fal AI Claude Sonnet 5 Prompt Analysis (3 Slots)",
                "api_provider": "Fal AI (Claude Sonnet 5)",
                "api_model": FAL_CLAUDE_MODEL,
                "endpoint": FAL_CLAUDE_ENDPOINT,
                "slots": claude_audit_logs,
            },
            self.audit_log_dir
            / f"1_product_3_styles_{self.preset.key}_claude_logs.json",
        )

    # -------------------------------------------------------------------------
    # PHASE 4: FAL AI NANO BANANA PRO MULTI-BLENDING + LOGO STAMPING ON SLIDE 1
    # -------------------------------------------------------------------------
    def phase_4(self, record_id: str) -> None:
        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})
        furniture_url = self._attachment_url(fields, FURNITURE_FIELD)
        interior_urls = self._get_interior_urls(fields)

        if len(interior_urls) < 3:
            raise AssetValidationError(
                f"Record {record_id} requires 3 interior images; found {len(interior_urls)}"
            )

        blended_paths: list[Path] = []
        fal_banana_logs: list[dict[str, Any]] = []

        for idx, spec in enumerate(self.preset.room_styles):
            prompt_field = spec.target_prompt_field
            prompt = (
                str(fields.get(prompt_field) or "").strip()
                or str(fields.get("Prompt1") or "").strip()
                or str(fields.get("Prompt") or "").strip()
            )
            if not prompt:
                raise AssetValidationError(f"Field '{prompt_field}' is empty")

            interior_url = interior_urls[idx]
            filename = spec.output_filename
            destination = self._artifact_path(record_id, filename)

            print(
                f"  [{idx + 1}/3] Blending Style {idx + 1} ({spec.name}) with Fal AI Nano Banana Pro (4:5, 1K)...",
                flush=True,
            )
            result_url = self.fal.generate(
                prompt=prompt,
                image_urls=[interior_url, furniture_url],
                aspect_ratio=FAL_NANO_ASPECT_RATIO,
                resolution=FAL_NANO_RESOLUTION,
                model=FAL_NANO_MODEL,
            )
            self._download(result_url, destination)
            self._validate_image_file(destination, f"Blended Style {idx + 1}")
            blended_paths.append(destination)
            print(f"  [+] Generated & verified {filename}")

            fal_banana_logs.append(
                {
                    "slot": spec.slot,
                    "style_name": spec.name,
                    "prompt_field": prompt_field,
                    "prompt": prompt,
                    "input_interior_url": interior_url,
                    "input_furniture_url": furniture_url,
                    "output_image_url": result_url,
                    "local_artifact_path": str(destination),
                    "model": FAL_NANO_MODEL,
                    "aspect_ratio": FAL_NANO_ASPECT_RATIO,
                    "resolution": FAL_NANO_RESOLUTION,
                }
            )

        # Auto-tag furniture item name onto all 3 blended slides IN PLACE (zero-cost local YOLO-World)
        category_defaults = {
            "chandeliers": "Chandelier",
            "pendant_lights": "Pendant Light",
            "floor_lamps": "Floor Lamp",
        }
        default_ptype = category_defaults.get(self.preset.key, "Chandelier")
        raw_item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or record_id).strip()
        item_title, product_type = split_item_name(
            raw_item_name, fallback_product_type=str(fields.get("Product Type") or default_ptype)
        )
        if not product_type:
            product_type = default_ptype

        print(f"  [+] Tagging item name ('{item_title}') onto all {len(blended_paths)} blended slides via YOLO-World...")
        for slide_idx, slide_path in enumerate(blended_paths, start=1):
            try:
                tag_blended_image(
                    image_input=slide_path,
                    item_name=item_title,
                    product_type=product_type,
                    category=self.preset.key,
                    destination=slide_path,
                    fallback_if_undetected=True,
                )
                print(f"    [ITEM TAGGING] Stamped '{item_title}' ({product_type}) onto Slide {slide_idx}")
            except Exception as tag_err:
                print(f"    [WARN] YOLO tagging notice on Slide {slide_idx}: {tag_err}")

        # Stamp HomeCartel Logo onto Slide 1 (First Blended Image)
        logo_url = self._get_logo_url(fields)
        if logo_url:
            logo_dest = self._artifact_path(record_id, f"logo_{record_id}.png")
            print(f"  [+] Downloading brand logo from '{LOGO_FIELD}' attachment...", flush=True)
            self._download(logo_url, logo_dest)
            try:
                print(
                    f"  [+] Stamping HomeCartel logo onto Slide 1 (Canva Box: W=190.3, H=63.5, X=108.0, Y=1178.5)...",
                    flush=True,
                )
                watermarked_slide1 = self._artifact_path(
                    record_id, "1_product_3_styles_blended1_watermarked.jpg"
                )
                stamp_logo(
                    blended_paths[0],
                    logo_dest,
                    destination=watermarked_slide1,
                    box=HOMECARTEL_LOGO_BOX,
                )
                self._validate_image_file(watermarked_slide1, "Watermarked Slide 1")
                blended_paths[0] = watermarked_slide1
                print(f"  [OK] Successfully stamped HomeCartel logo onto Slide 1!")
            except Exception as stamp_err:
                print(f"  [WARN] Failed stamping logo onto Slide 1: {stamp_err}")
        else:
            print(f"  [WARN] No 'Logo' attachment found in table; proceeding with unstamped Slide 1.")

        # Upload all 3 blended images to Airtable
        target_blended_field = self._get_blended_field_name(fields)
        print(
            f"  [+] Uploading 3 blended images (Slide 1 with Logo) to '{target_blended_field}'...",
            flush=True,
        )
        for path in blended_paths:
            self.airtable.upload_attachment(
                record_id, target_blended_field, path, path.name
            )

        # Mirror the name-stamped, logo-stamped deliverable slides to 'Blended Image with Name text'
        try:
            try:
                self.airtable.clear_attachment_field(record_id, TARGET_BLENDED_FIELD)
            except Exception:
                pass
            print(f"  [+] Uploading stamped slides -> '{TARGET_BLENDED_FIELD}'...")
            for path in blended_paths:
                self.airtable.upload_attachment(
                    record_id, TARGET_BLENDED_FIELD, path, f"tagged_{path.name}"
                )
        except Exception as tag_err:
            print(f"  [WARN] Failed mirroring stamped slides to '{TARGET_BLENDED_FIELD}' for record {record_id}: {tag_err}")

        self.logger.event(
            "provider_completed",
            record_id=record_id,
            phase=4,
            provider="fal",
            model=FAL_NANO_MODEL,
            aspect_ratio=FAL_NANO_ASPECT_RATIO,
            resolution=FAL_NANO_RESOLUTION,
            watermarked_slide1=bool(logo_url),
            blended_count=len(blended_paths),
        )
        append_audit_log(
            {
                "timestamp": pht_timestamp(),
                "record_id": record_id,
                "sku": str(fields.get(SKU_FIELD) or ""),
                "item_name": str(fields.get(ITEM_NAME_FIELD) or record_id),
                "phase": "Phase 4: Fal AI Nano Banana Pro Multi-Blending + Slide 1 Logo Stamping",
                "api_provider": "Fal AI (Nano Banana Pro) + Local PIL Overlay",
                "api_model": FAL_NANO_MODEL,
                "target_field": target_blended_field,
                "logo_url": logo_url,
                "canva_logo_box": {
                    "width": HOMECARTEL_LOGO_BOX.width,
                    "height": HOMECARTEL_LOGO_BOX.height,
                    "x": HOMECARTEL_LOGO_BOX.x,
                    "y": HOMECARTEL_LOGO_BOX.y,
                    "rotation": "0 deg",
                },
                "slots": fal_banana_logs,
            },
            self.audit_log_dir
            / f"1_product_3_styles_{self.preset.key}_fal_banana_logs.json",
        )


def show_menu() -> PipelinePreset:
    print("\n" + "=" * 68)
    print("        1 PRODUCT, 3 STYLES FEED AUTOMATION MENU        ")
    print("=" * 68)
    print(" Select Destination Category Preset:\n")
    print(" [1] Chandeliers")
    print(f"     Table ID : {PRESETS['chandeliers'].table_id}")
    print(f"     Moodboard: {PRESETS['chandeliers'].moodboard_id}\n")
    print(" [2] Pendant Lights")
    print(f"     Table ID : {PRESETS['pendant_lights'].table_id}")
    print(f"     Moodboard: {PRESETS['pendant_lights'].moodboard_id}\n")
    print(" [3] Floor Lamps")
    print(f"     Table ID : {PRESETS['floor_lamps'].table_id}")
    print(f"     Moodboard: {PRESETS['floor_lamps'].moodboard_id}\n")
    print(" [0] Exit\n")
    print("=" * 68)

    while True:
        try:
            choice = input(" Enter choice [0-3]: ").strip()
            if choice in ("1", "chandelier", "chandeliers", "tblrlfqbge5ejs5pi"):
                return PRESETS["chandeliers"]
            elif choice in ("2", "pendant", "pendant_lights", "pendants", "tblry52kcasiscwzd"):
                return PRESETS["pendant_lights"]
            elif choice in ("3", "floor", "floor_lamp", "floor_lamps", "tbl9giq2qeycwmhwu"):
                return PRESETS["floor_lamps"]
            elif choice in ("0", "exit", "quit", "q"):
                print("[INFO] Exiting.")
                sys.exit(0)
            print("[WARN] Invalid option. Please enter 1, 2, 3, or 0.")
        except (KeyboardInterrupt, EOFError):
            print("\n[INFO] Exiting.")
            sys.exit(0)


def resolve_preset(target_arg: str | None) -> PipelinePreset:
    if not target_arg:
        if sys.stdin.isatty():
            return show_menu()
        return PRESETS["chandeliers"]

    key = target_arg.lower().strip()
    if key in ("1", "chandelier", "chandeliers", "tblrlfqbge5ejs5pi", "tblm1odmxdp9safds"):
        return PRESETS["chandeliers"]
    if key in ("2", "pendant", "pendant_lights", "pendants", "tblry52kcasiscwzd"):
        return PRESETS["pendant_lights"]
    if key in ("3", "floor", "floor_lamp", "floor_lamps", "tbl9giq2qeycwmhwu"):
        return PRESETS["floor_lamps"]
    if key in PRESETS:
        return PRESETS[key]

    print(f"[WARN] Unknown target '{target_arg}'. Defaulting to menu...")
    return show_menu() if sys.stdin.isatty() else PRESETS["chandeliers"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="1 Product, 3 Styles Feed: 4-Phase AI Automation Pipeline."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=(
            "chandeliers",
            "chandelier",
            "pendant_lights",
            "pendant_light",
            "pendant",
            "floor_lamps",
            "floor_lamp",
            "floor",
            "1",
            "2",
            "3",
            "menu",
        ),
        default=None,
        help="Target category preset: chandeliers (1), pendant_lights (2), or floor_lamps (3).",
    )
    parser.add_argument(
        "--phase",
        choices=("1", "2", "3", "4", "all"),
        default="all",
        help="Run specific phase (1..4) or all phases (default: all).",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable table ID override.",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Target specific Airtable record ID.",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Krea Moodboard ID override.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Krea Room Style 1 interior prompt override.",
    )
    parser.add_argument(
        "--max-rows",
        "--max-items",
        "-n",
        type=int,
        default=1,
        help="Maximum rows to process in batch mode (default: 1).",
    )
    parser.add_argument(
        "--scrape-first",
        action="store_true",
        help="Force scraping a new unique product first before processing Phase 2-4.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.target == "menu":
        preset = show_menu()
    else:
        preset = resolve_preset(args.target)

    runner = OneProductThreeStylesRunner(
        preset=preset,
        table_id_override=args.table_id,
        moodboard_id_override=args.moodboard_id,
        prompt_override=args.prompt,
    )
    print("=" * 68)
    print(f"1 Product, 3 Styles Feed Pipeline | {preset.name}")
    print(f"Destination Table: {runner.table_id}")
    print(f"Akeneo Category  : {runner.category_code}")
    print(f"Krea Moodboard ID: {runner.moodboard_id}")
    if runner.prompt_override:
        print(f"Custom Style 1 Pr: {runner.prompt_override}")
    print(f"Target Phase     : {args.phase}")
    print(f"Max Rows         : {args.max_rows}")
    print(f"Scrape First     : {args.scrape_first}")
    print("=" * 68)
    runner.run(
        phase=args.phase,
        target_record_id=args.record_id,
        max_rows=args.max_rows,
        scrape_first=args.scrape_first,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
