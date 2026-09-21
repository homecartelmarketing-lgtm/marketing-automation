"""1 Product, 3 Styles Reel (5-Phase AI Content Automation Pipeline).

Flow Architecture:
1. Phase 1 (Akeneo 1-Item Scrape):
   Scrapes 1 modern chandelier into Airtable (Furniture Item, SKU, Item Name)
   with Status -> 'Standby' and Foreign Key ID 'OP3S-REEL-CH-<row_id>'.
   If a row already exists without a product, populates that row.
2. Phase 2 (Krea AI Room Interiors - 3 Styles @ 9:16, 1K):
   Generates 3 distinct room styles/interiors at 9:16 aspect ratio, 1K resolution
   using Krea AI with chandelier moodboard.
   Uploads to 'Interior1', 'Interior2', 'Interior3'.
   Status -> 'Phase 2 - Ready'.
3. Phase 3 (Fal AI Claude Sonnet 5 Prompt Analysis):
   Uses anthropic/claude-sonnet-5 via Fal AI vision to analyze the chandelier against
   each of the 3 room styles and write tailored blending prompts to 'Prompt1', 'Prompt2', 'Prompt3'.
   Status -> 'Phase 3 - Ready'.
4. Phase 4 (Fal AI Nano Banana Pro Multi-Blending @ 9:16, 1K Quality):
   Blends chandelier into the 3 room styles via fal-ai/nano-banana-pro/edit (9:16, 1K).
   Uploads all 3 images into '1 Product 3 Style Blended'.
   Status -> 'Phase 4 - Ready'.
5. Phase 5 (YOLO Tagging & Silent 9:16 Reel Video Compilation):
   Auto-tags chandelier item name onto all 3 blended slides using local zero-cost YOLO-World
   and uploads to 'Blended Image with Name text'.
   Compiles the tagged slides into a silent 9:16 vertical MP4 with 5s, 4s,
   and 4s photo holds, followed by a 5s outro with 0.5s fade out.
   Uploads to 'Converted Reel'.
   Status -> 'Complete' and stamps Philippine Time (UTC+8) into 'Date and Time Generated'.
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

from content_automation.airtable_client import current_pht_timestamp
from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.config import load_settings
from content_automation.errors import AssetValidationError, AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.prompts import build_vision_blending_instruction
from content_automation.krea_client import KreaClient
from content_automation.item_tagger import (
    TARGET_BLENDED_FIELD,
    tag_and_upload_blended_image,
)
from content_automation.models import LocalImage
from content_automation.overlay import overlay_centered_headline
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.furniture_item import (
    attachment_filename,
    fetch_all_base_existing_identities,
    format_item_name_with_product_type,
)
from content_automation.scraping.products import (
    ProductItem,
    existing_product_identities,
    identity_key,
    select_new_products,
)
from content_automation.shopify_client import ShopifyClient
from content_automation.video import slideshow_with_fade_out

# -----------------------------------------------------------------------------
# CONSTANTS & DEFAULTS
# -----------------------------------------------------------------------------
DEFAULT_TABLE_ID = "tbl6ls4AWcEcynBpZ"
DEFAULT_MOODBOARD_ID = "de6ad512-870d-4ab7-a48c-3f3ca85faf24"
DEFAULT_PROMPT = "Generate me a modern luxury living room with high ceiling for chandelier"
KREA_ASPECT_RATIO = "9:16"
KREA_RESOLUTION = "1K"
FAL_NANO_ASPECT_RATIO = "9:16"
FAL_NANO_RESOLUTION = "1K"
FAL_NANO_MODEL = "fal-ai/nano-banana-pro/edit"
FAL_CLAUDE_MODEL = "anthropic/claude-sonnet-5"
FAL_CLAUDE_ENDPOINT = "openrouter/router/vision"

FURNITURE_FIELD = "Furniture Item"
SKU_FIELD = "SKU"
ITEM_NAME_FIELD = "Item Name"
STATUS_FIELD = "Status"
BLENDED_FIELD = "1 Product 3 Style Blended"
TAGGED_BLENDED_FIELD = "Blended Image with Name text"
CONVERTED_REEL_FIELD = "Converted Reel"
OUTRO_FIELD = "Outro"
TIMESTAMP_FIELD = "Date and Time Generated"
FOREIGN_KEY_FIELD = "Foreign Key ID"

BLENDED_PHOTO_SECONDS = (5.0, 4.0, 4.0)
OUTRO_SECONDS = 5.0
OUTRO_TRANSITION_SECONDS = 0.5
OUTRO_FADE_SECONDS = 0.5


@dataclass(frozen=True)
class RoomStyleSpec:
    slot: int
    name: str
    target_prompt_field: str
    interior_prompt_template: str
    interior_filename: str
    output_filename: str


STYLE_SPECS: tuple[RoomStyleSpec, ...] = (
    RoomStyleSpec(
        slot=1,
        name="Living Room",
        target_prompt_field="Prompt1",
        interior_prompt_template="Generate me a luxury modern living room with high ceiling for chandelier",
        interior_filename="1_product_3_styles_reel_interior_style1.jpg",
        output_filename="1_product_3_styles_reel_blended1.jpg",
    ),
    RoomStyleSpec(
        slot=2,
        name="Dining Room",
        target_prompt_field="Prompt2",
        interior_prompt_template="Generate me a luxury modern dining room with dining table for chandelier",
        interior_filename="1_product_3_styles_reel_interior_style2.jpg",
        output_filename="1_product_3_styles_reel_blended2.jpg",
    ),
    RoomStyleSpec(
        slot=3,
        name="Entryway Foyer",
        target_prompt_field="Prompt3",
        interior_prompt_template="Generate me a luxury modern entryway foyer with high ceiling for chandelier",
        interior_filename="1_product_3_styles_reel_interior_style3.jpg",
        output_filename="1_product_3_styles_reel_blended3.jpg",
    ),
)


class OneProductThreeStylesReelRunner:
    """End-to-end 5-Phase pipeline runner for 1 Product 3 Styles Reel."""

    def __init__(
        self,
        table_id: str | None = None,
        moodboard_id: str | None = None,
        prompt_override: str | None = None,
    ):
        self.settings = load_settings()
        self.table_id = (
            table_id
            or os.getenv("AIRTABLE_TABLE_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL")
            or DEFAULT_TABLE_ID
        ).strip()
        self.moodboard_id = (
            moodboard_id
            or os.getenv("KREA_MOODBOARD_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL")
            or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS")
            or DEFAULT_MOODBOARD_ID
        ).strip()
        self.prompt_override = (
            prompt_override
            or os.getenv("PROMPT_ONE_PRODUCT_THREE_STYLES_REEL_CHANDELIER")
            or DEFAULT_PROMPT
        ).strip()

        self.airtable = ScrapeAirtableClient(
            self.settings.airtable_token,
            self.settings.airtable_base_id,
            self.table_id,
        )
        self.akeneo = AkeneoClient(
            self.settings.akeneo_host,
            self.settings.akeneo_client_id,
            self.settings.akeneo_secret,
            self.settings.akeneo_username,
            self.settings.akeneo_password,
            channel_name=os.getenv("CHANNEL_NAME", "home_cartel"),
        )
        self.krea = KreaClient(
            self.settings.krea_token,
            self.settings.krea_base_url,
        )
        self.fal = FalClient(self.settings.fal_key)

        self.artifact_root = Path("output/1_product_3_styles_reel")
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def _artifact_path(self, record_id: str, filename: str) -> Path:
        dest_dir = self.artifact_root / record_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir / filename

    def _download(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, stream=True, timeout=90)
        resp.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return destination

    def _attachment_url(self, fields: dict[str, Any], field_name: str) -> str:
        items = fields.get(field_name) or []
        if not items:
            return ""
        if isinstance(items, list):
            first = items[0]
            if isinstance(first, dict):
                return str(first.get("url") or first.get("permalink") or "")
        return ""

    def _get_interior_urls(self, fields: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        for slot in (1, 2, 3):
            url = self._attachment_url(fields, f"Interior{slot}")
            if url:
                urls.append(url)
        if not urls:
            url = self._attachment_url(fields, "Interior")
            if url:
                urls.append(url)
        return urls

    def _update_status(self, record_id: str, status_value: str) -> None:
        updates: dict[str, Any] = {STATUS_FIELD: status_value}
        if status_value.lower() in ("complete", "completed", "done"):
            updates[TIMESTAMP_FIELD] = current_pht_timestamp()
        try:
            self.airtable.update_records([(record_id, updates)])
        except Exception as e:
            print(f"[WARN] Failed to update status to '{status_value}' for {record_id}: {e}", flush=True)

    # -------------------------------------------------------------------------
    # PHASE 1: AKENEO PRODUCT INGESTION
    # -------------------------------------------------------------------------
    def phase_1(
        self,
        max_items: int = 1,
        target_record_id: str | None = None,
        cross_table_dedup: bool = True,
    ) -> list[str]:
        print("\n[INFO] Phase 1/5: Akeneo Product Ingestion (chandeliers)...", flush=True)
        self.akeneo.authenticate()

        # 1. Gather all existing SKUs and names in current table
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

        # 2. Cross-table deduplication scan across all tables in the base
        if cross_table_dedup and getattr(self.airtable, "base_id", None):
            try:
                base_skus, base_names, base_files = fetch_all_base_existing_identities(self.airtable)
                existing_skus.update(base_skus)
                existing_names.update(base_names)
                existing_filenames.update(base_files)
                print(
                    f"  [INFO] Cross-table deduplication active: {len(base_skus)} base SKUs, "
                    f"{len(base_names)} item names registered.",
                    flush=True,
                )
            except Exception as dedup_err:
                print(f"  [WARN] Cross-table deduplication note: {dedup_err}", flush=True)

        # 3. Shopify Cross-check (optional check for active products)
        shopify_index = None
        try:
            shopify = ShopifyClient()
            shopify_index = shopify.load_published_identities()
        except Exception:
            pass

        # 4. Query Akeneo for active/enabled chandelier products
        akeneo_cat = akeneo_category_code("chandeliers")
        query: dict[str, Any] = {
            "categories": [{"operator": "IN", "value": [akeneo_cat]}],
            "enabled": [{"operator": "=", "value": True}],
            "Style2": [{"operator": "IN", "value": ["modern"]}],
        }
        print("  [INFO] Fetching active modern chandeliers from Akeneo PIM...", flush=True)
        products = self.akeneo.fetch_products(query)
        if not products:
            # Fall back without style filter if modern returns 0
            query.pop("Style2", None)
            products = self.akeneo.fetch_products(query)

        derived_names, derived_media = existing_product_identities(products, existing_skus)
        existing_names.update(derived_names)
        existing_filenames.update(derived_media)

        candidates, _ = select_new_products(
            products,
            existing_skus,
            existing_item_names=existing_names,
            existing_media_codes=existing_filenames,
            category_code="chandeliers",
        )

        filtered_items: list[ProductItem] = []
        for item in candidates:
            filename = attachment_filename(item.item_name, item.media_code)
            if identity_key(filename) in existing_filenames:
                continue
            if shopify_index and not shopify_index.contains(item.sku, item.item_name):
                continue
            searchable_title = f"{item.item_name} {item.product_type}".lower()
            if "chandelier" not in searchable_title:
                continue
            if any(kw in searchable_title for kw in ("cluster", "linear")):
                continue
            filtered_items.append(item)

        if not filtered_items:
            raise AutomationError("Akeneo returned 0 new unique modern chandelier products.")

        items_to_process = filtered_items[:max_items]
        processed_record_ids: list[str] = []

        for selected_item in items_to_process:
            display_name = format_item_name_with_product_type(
                selected_item.item_name,
                selected_item.product_type,
                category_code="chandeliers",
            )

            # If target_record_id provided (e.g. empty blank row), populate it
            if target_record_id:
                record_id = target_record_id
                self.airtable.update_records([(
                    record_id,
                    {
                        SKU_FIELD: selected_item.sku,
                        ITEM_NAME_FIELD: display_name,
                        STATUS_FIELD: "Standby",
                    },
                )])
                print(f"  [OK] Populated existing row {record_id} with {selected_item.sku} ({display_name})", flush=True)
            else:
                record_id = self.airtable.create_record({
                    SKU_FIELD: selected_item.sku,
                    ITEM_NAME_FIELD: display_name,
                    STATUS_FIELD: "Standby",
                })
                print(f"  [OK] Created new row {record_id} with {selected_item.sku} ({display_name})", flush=True)

            # Download & upload product media
            download = None
            try:
                download = self.akeneo.download_media(selected_item.media_code)
                fname = attachment_filename(selected_item.item_name, selected_item.media_code)
                self.airtable.upload_attachment(record_id, FURNITURE_FIELD, download, fname)
                print(f"  [+] Uploaded {selected_item.sku} to '{FURNITURE_FIELD}' ({fname})", flush=True)
            finally:
                if download:
                    download.cleanup()

            self._update_status(record_id, "Standby")
            processed_record_ids.append(record_id)

        return processed_record_ids

    # -------------------------------------------------------------------------
    # PHASE 2: KREA AI ROOM INTERIORS (3 STYLES @ 9:16)
    # -------------------------------------------------------------------------
    def phase_2(self, record_id: str) -> list[Path]:
        print(f"\n[INFO] Phase 2/5: Krea Room Interiors (9:16) for record {record_id}...", flush=True)
        self._update_status(record_id, "Phase 2 - Processing")

        interior_paths: list[Path] = []
        for idx, spec in enumerate(STYLE_SPECS, start=1):
            field_name = f"Interior{idx}"
            prompt = self.prompt_override if idx == 1 else spec.interior_prompt_template
            print(f"  [{idx}/3] Generating Style {idx} ({spec.name}) with Krea AI (9:16, 1K)...", flush=True)

            image_url = self.krea.generate(
                prompt=prompt,
                aspect_ratio=KREA_ASPECT_RATIO,
                resolution=KREA_RESOLUTION,
                moodboard_id=self.moodboard_id,
            )
            dest = self._artifact_path(record_id, spec.interior_filename)
            self._download(image_url, dest)
            interior_paths.append(dest)

            # Upload to Airtable Interior1/2/3
            try:
                self.airtable.upload_attachment(record_id, field_name, dest, dest.name)
                print(f"  [+] Uploaded Style {idx} to '{field_name}'.", flush=True)
            except Exception as e:
                print(f"  [WARN] Failed uploading to '{field_name}': {e}", flush=True)

        self._update_status(record_id, "Phase 2 - Ready")
        return interior_paths

    # -------------------------------------------------------------------------
    # PHASE 3: FAL AI CLAUDE SONNET 5 VISION PROMPTING
    # -------------------------------------------------------------------------
    def phase_3(self, record_id: str) -> dict[str, str]:
        print(f"\n[INFO] Phase 3/5: Claude Vision Prompting for record {record_id}...", flush=True)
        self._update_status(record_id, "Phase 3 - Processing")

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})
        furniture_url = self._attachment_url(fields, FURNITURE_FIELD)
        interior_urls = self._get_interior_urls(fields)

        if not furniture_url:
            raise AssetValidationError(f"Record {record_id} has no '{FURNITURE_FIELD}' attachment")
        if len(interior_urls) < 3:
            raise AssetValidationError(f"Record {record_id} requires 3 interior images; found {len(interior_urls)}")

        updates: dict[str, str] = {}
        raw_item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Lighting Fixture").strip()

        for idx, spec in enumerate(STYLE_SPECS):
            interior_url = interior_urls[idx]
            prompt_field = spec.target_prompt_field

            system_prompt = build_vision_blending_instruction(
                interior_label=f"Modern Room Interior ({spec.name})",
                item_name=raw_item_name,
                aspect_ratio="9:16",
            )

            print(f"  [{idx + 1}/3] Analyzing {spec.name} + Chandelier with Claude Sonnet 5...", flush=True)
            prompt_text = self.fal.generate_vision_prompt(
                image_urls=[interior_url, furniture_url],
                prompt=system_prompt,
                model=FAL_CLAUDE_MODEL,
                endpoint=FAL_CLAUDE_ENDPOINT,
            )
            updates[prompt_field] = prompt_text
            print(f"  [+] Generated '{prompt_field}': \"{prompt_text[:80]}...\"", flush=True)

        # Generate Versatile Styling Reel Headline (Strictly NO item name, SKU, or brand name)
        item_name = str(fields.get(ITEM_NAME_FIELD) or "Chandelier").strip()
        headline_prompt = (
            "You are an expert luxury architectural and interior design copywriter. "
            "Write an evocative, high-end 3-5 word headline showcasing how a single luxury lighting piece effortlessly styles 3 different room settings. "
            "Examples of acceptable tone: 'One Piece, Three Living Aesthetics', 'Elevating Every Living Space', 'Versatile Elegance Across Rooms', 'One Design, Distinctive Ambiances'. "
            "CRITICAL RULES: "
            "1. DO NOT mention the product name, model name, brand name, or SKU under any circumstances. "
            "2. DO NOT use words like 'product' or 'chandelier' or 'lamp'. "
            "3. Return ONLY the 3-5 word headline text, with no quotation marks, no punctuation, and no extra words."
        )
        print("  [4/3] Generating Reel Headline with Claude Sonnet 5 (no item name)...", flush=True)
        headline_text = self.fal.generate_vision_prompt(
            image_urls=[furniture_url],
            prompt=headline_prompt,
            model=FAL_CLAUDE_MODEL,
            endpoint=FAL_CLAUDE_ENDPOINT,
        )
        headline_text = headline_text.strip().strip('"').strip("'").strip(".").strip()

        # Safety clean: If Claude accidentally included the item name, fallback to a verified luxury styling hook
        if item_name:
            for word in item_name.split():
                clean_word = word.strip("|,.-_()[]").lower()
                if len(clean_word) > 3 and clean_word in headline_text.lower():
                    headline_text = "One Design, Three Living Aesthetics"
                    break
        # Check if Reel Headline column exists in Airtable schema before batch updating
        try:
            available_fields = set(self.airtable.table_fields().keys())
            if "Reel Headline" in available_fields:
                updates["Reel Headline"] = headline_text
            elif "Caption Generated" in available_fields:
                updates["Caption Generated"] = headline_text
        except Exception:
            updates["Reel Headline"] = headline_text
        print(f"  [+] Generated 'Reel Headline': \"{headline_text}\"", flush=True)

        try:
            self.airtable.update_records([(record_id, updates)])
        except Exception as err:
            if "Reel Headline" in str(err) and "Reel Headline" in updates:
                print("  [WARN] 'Reel Headline' field missing in Airtable table, retrying without it...", flush=True)
                del updates["Reel Headline"]
                self.airtable.update_records([(record_id, updates)])
            else:
                raise
        self._update_status(record_id, "Phase 3 - Ready")
        print("  [OK] Saved Prompt1, Prompt2, Prompt3 to Airtable.", flush=True)
        return updates

    # -------------------------------------------------------------------------
    # PHASE 4: FAL AI NANO BANANA PRO MULTI-BLENDING (9:16)
    # -------------------------------------------------------------------------
    def phase_4(self, record_id: str) -> list[Path]:
        print(f"\n[INFO] Phase 4/5: Nano Banana Pro Multi-Blending for record {record_id}...", flush=True)
        self._update_status(record_id, "Phase 4 - Processing")

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})
        furniture_url = self._attachment_url(fields, FURNITURE_FIELD)
        interior_urls = self._get_interior_urls(fields)

        if not furniture_url or len(interior_urls) < 3:
            raise AssetValidationError(f"Record {record_id} missing furniture or interior attachments")

        blended_paths: list[Path] = []
        for idx, spec in enumerate(STYLE_SPECS):
            prompt = (
                str(fields.get(spec.target_prompt_field) or "").strip()
                or "Blend this chandelier naturally hanging from the ceiling with realistic lighting and reflections."
            )
            interior_url = interior_urls[idx]
            destination = self._artifact_path(record_id, spec.output_filename)

            print(f"  [{idx + 1}/3] Blending Style {idx + 1} ({spec.name}) @ 9:16...", flush=True)
            result_url = self.fal.generate(
                prompt=prompt,
                image_urls=[interior_url, furniture_url],
                aspect_ratio=FAL_NANO_ASPECT_RATIO,
                resolution=FAL_NANO_RESOLUTION,
                model=FAL_NANO_MODEL,
            )
            self._download(result_url, destination)
            blended_paths.append(destination)
            print(f"  [+] Generated & downloaded {spec.output_filename}", flush=True)

        # Upload all 3 blended images to '1 Product 3 Style Blended'
        print(f"  [+] Uploading 3 blended images to '{BLENDED_FIELD}'...", flush=True)
        for path in blended_paths:
            self.airtable.upload_attachment(record_id, BLENDED_FIELD, path, path.name)

        self._update_status(record_id, "Phase 4 - Ready")
        return blended_paths

    # -------------------------------------------------------------------------
    # PHASE 5: YOLO TAGGING & SILENT 9:16 REEL VIDEO COMPILATION
    # -------------------------------------------------------------------------
    def phase_5(self, record_id: str, blended_paths: list[Path] | None = None) -> Path:
        print(f"\n[INFO] Phase 5/5: Silent 9:16 Reel Video Compilation for record {record_id}...", flush=True)
        self._update_status(record_id, "Phase 5 - Processing")

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})

        # If blended_paths not provided, download existing blended images
        if not blended_paths:
            blended_items = fields.get(BLENDED_FIELD) or []
            blended_paths = []
            for idx, item in enumerate(blended_items):
                url = item.get("url") or item.get("permalink") if isinstance(item, dict) else str(item)
                if url:
                    dest = self._artifact_path(record_id, f"blended_download_{idx + 1}.jpg")
                    self._download(url, dest)
                    blended_paths.append(dest)

        if not blended_paths:
            raise AssetValidationError(f"Record {record_id} has no blended images in '{BLENDED_FIELD}'")

        # 1. Zero-Cost YOLO Item Name Tagging
        print("  [+] Phase 5.1: Zero-Cost YOLO item name tagging on blended slides...", flush=True)
        tagged_paths: list[Path] = []
        try:
            raw_item_name = str(fields.get(ITEM_NAME_FIELD) or fields.get(SKU_FIELD) or "Chandelier").strip()
            item_title, product_type = split_item_name(raw_item_name, fallback_product_type="Chandelier")
            if not product_type:
                product_type = "Chandelier"

            tag_and_upload_blended_image(
                airtable=self.airtable,
                record_id=record_id,
                blended_source=blended_paths,
                item_name=item_title,
                product_type=product_type,
                category="chandeliers",
                target_field=TAGGED_BLENDED_FIELD,
                output_filename_prefix="blended_named",
                fallback_if_undetected=True,
                output_tagged_paths=tagged_paths,
            )
            print(f"  [OK] Uploaded tagged slides to '{TAGGED_BLENDED_FIELD}'.", flush=True)
        except Exception as e:
            print(f"  [WARN] YOLO tagging fallback note: {e}", flush=True)

        # 2. Prepare Slides for Reel & Apply Centered Headline
        slides_to_use = tagged_paths if (tagged_paths and len(tagged_paths) == len(blended_paths)) else blended_paths
        
        headline_text = str(fields.get("Reel Headline") or "One Piece, Three Living Aesthetics").strip()
        print(f"  [+] Phase 5.2: Overlaying centered headline on slides: '{headline_text}'...", flush=True)
        final_paths: list[Path] = []
        for idx, p in enumerate(slides_to_use):
            dest = self._artifact_path(record_id, f"slide_with_headline_{idx + 1}.jpg")
            overlay_centered_headline(
                base_image=p,
                headline=headline_text,
                destination=dest,
                font_size=48,
                text_color=(255, 255, 255)
            )
            final_paths.append(dest)

        local_slides = [LocalImage(p, p.name, "image/jpeg") for p in final_paths]

        # 3. Resolve Outro Image
        outro_url = self._attachment_url(fields, OUTRO_FIELD)
        outro_dest = self._artifact_path(record_id, "outro.jpg")
        if outro_url:
            self._download(outro_url, outro_dest)
            local_outro = LocalImage(outro_dest, "outro.jpg", "image/jpeg")
        else:
            candidates_outro = [
                Path("assets/outro_layout.jpg"),
                Path("Outro for All Reels/Outro.jpg"),
            ]
            found_outro = next((p for p in candidates_outro if p.is_file()), None)
            if found_outro:
                local_outro = LocalImage(found_outro, found_outro.name, "image/jpeg")
            else:
                raise AssetValidationError("No Outro image found in record or local assets.")

        # 4. Compile Silent 9:16 Video (5s, 4s, 4s blended photos + 5s outro)
        video_dest = self._artifact_path(record_id, "1_product_3_styles_reel.mp4")
        print(f"  [+] Phase 5.3: Compiling silent 9:16 MP4 slideshow video ({BLENDED_PHOTO_SECONDS} photo holds)...", flush=True)
        slideshow_with_fade_out(
            slides=local_slides,
            outro=local_outro,
            destination=video_dest,
            per_slide_seconds=BLENDED_PHOTO_SECONDS,
            outro_seconds=OUTRO_SECONDS,
            transition_to_outro_seconds=OUTRO_TRANSITION_SECONDS,
            fade_out_seconds=OUTRO_FADE_SECONDS,
            width=1080,
            height=1920,
            fps=30,
        )
        print(f"  [OK] Compiled silent reel MP4: {video_dest.name}", flush=True)

        # 5. Upload final MP4 to 'Converted Reel'
        print(f"  [+] Phase 5.4: Uploading video to '{CONVERTED_REEL_FIELD}'...", flush=True)
        self.airtable.upload_attachment(record_id, CONVERTED_REEL_FIELD, video_dest, video_dest.name)

        # 6. Mark 100% Complete & Stamp PHT Timestamp
        self._update_status(record_id, "Complete")
        print(f"  [OK] Record {record_id} is 100% COMPLETE! Stamped timestamp and Status -> Complete.\n", flush=True)
        return video_dest

    # -------------------------------------------------------------------------
    # MAIN PIPELINE RUNNER (END-TO-END)
    # -------------------------------------------------------------------------
    def _run_all_phases_for_record(self, record_id: str) -> None:
        print(f"\n=======================================================", flush=True)
        print(f"Running End-to-End Pipeline for Record: {record_id}", flush=True)
        print(f"=======================================================", flush=True)

        record = self.airtable.get_record(record_id)
        fields = record.get("fields", {})

        # Phase 1 check: Furniture Item
        furniture_url = self._attachment_url(fields, FURNITURE_FIELD)
        if not furniture_url:
            print(f"[INFO] Record {record_id} has no product attached. Populating via Phase 1...", flush=True)
            self.phase_1(max_items=1, target_record_id=record_id)
            record = self.airtable.get_record(record_id)
            fields = record.get("fields", {})

        # Phase 2 check: Krea Room Interiors (9:16)
        interiors = self._get_interior_urls(fields)
        if len(interiors) < 3:
            self.phase_2(record_id)
            record = self.airtable.get_record(record_id)
            fields = record.get("fields", {})

        # Phase 3 check: Claude Vision Prompts
        p1 = str(fields.get("Prompt1") or "").strip()
        p2 = str(fields.get("Prompt2") or "").strip()
        p3 = str(fields.get("Prompt3") or "").strip()
        if not (p1 and p2 and p3):
            self.phase_3(record_id)
            record = self.airtable.get_record(record_id)
            fields = record.get("fields", {})

        # Phase 4 check: Nano Banana Pro Multi-Blending (9:16)
        blended_items = fields.get(BLENDED_FIELD) or []
        blended_paths: list[Path] | None = None
        if len(blended_items) < 3:
            blended_paths = self.phase_4(record_id)
            record = self.airtable.get_record(record_id)
            fields = record.get("fields", {})

        # Phase 5 check: YOLO Tagging & Silent Reel Video Compilation
        reel_items = fields.get(CONVERTED_REEL_FIELD) or []
        if not reel_items:
            print(f"[INFO] Proceeding to Phase 5: Silent 9:16 Reel Video Compilation for record {record_id}...", flush=True)
            self.phase_5(record_id, blended_paths=blended_paths)
        else:
            status = str(fields.get(STATUS_FIELD) or "").lower().strip()
            if status not in ("complete", "completed", "done", "discard", "discarded"):
                self._update_status(record_id, "Complete")

    def run(
        self,
        phase: str = "all",
        target_record_id: str | None = None,
        max_rows: int = 1,
        scrape_first: bool = False,
    ) -> None:
        print(f"\n[INFO] Starting 1 Product 3 Styles Reel Pipeline (Phase: {phase}, Rows: {max_rows})...", flush=True)

        if phase == "all":
            if target_record_id:
                self._run_all_phases_for_record(target_record_id)
                return

            records_processed = 0
            if scrape_first:
                new_records = self.phase_1(max_items=max_rows)
                for rec_id in new_records:
                    self._run_all_phases_for_record(rec_id)
                    records_processed += 1
                    if records_processed >= max_rows:
                        return

            # Process existing records that are not complete
            all_records = self.airtable.list_records()
            for rec in all_records:
                if records_processed >= max_rows:
                    break
                status = str(rec.get("fields", {}).get(STATUS_FIELD) or "").lower().strip()
                if status in ("complete", "completed", "done", "discard", "discarded"):
                    continue
                self._run_all_phases_for_record(rec["id"])
                records_processed += 1

            if records_processed == 0:
                print("[INFO] No pending rows found. Ingesting a new product from Akeneo...", flush=True)
                new_records = self.phase_1(max_items=max_rows)
                for rec_id in new_records:
                    self._run_all_phases_for_record(rec_id)
            return

        # Specific Phase execution
        p = int(phase)
        if p == 1:
            self.phase_1(max_items=max_rows, target_record_id=target_record_id)
        elif p == 2:
            rec_id = target_record_id or self._find_first_pending_record()
            if rec_id:
                self.phase_2(rec_id)
        elif p == 3:
            rec_id = target_record_id or self._find_first_pending_record()
            if rec_id:
                self.phase_3(rec_id)
        elif p == 4:
            rec_id = target_record_id or self._find_first_pending_record()
            if rec_id:
                self.phase_4(rec_id)
        elif p == 5:
            rec_id = target_record_id or self._find_first_pending_record()
            if rec_id:
                self.phase_5(rec_id)

    def _find_first_pending_record(self) -> str | None:
        all_records = self.airtable.list_records()
        for rec in all_records:
            status = str(rec.get("fields", {}).get(STATUS_FIELD) or "").lower().strip()
            if status not in ("complete", "completed", "done", "discard", "discarded"):
                return rec["id"]
        return None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="1 Product, 3 Styles Reel: 5-Phase Automation Pipeline")
    parser.add_argument("--phase", "-p", choices=("1", "2", "3", "4", "5", "all"), default="all")
    parser.add_argument("--table-id", default=None)
    parser.add_argument("--record-id", default=None)
    parser.add_argument("--moodboard-id", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--max-rows", "-n", type=int, default=1)
    parser.add_argument("--scrape-first", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    runner = OneProductThreeStylesReelRunner(
        table_id=args.table_id,
        moodboard_id=args.moodboard_id,
        prompt_override=args.prompt,
    )
    print("=" * 68)
    print("1 Product, 3 Styles Reel Pipeline (Chandelier)")
    print(f"Table ID: {runner.table_id}")
    print(f"Phase   : {args.phase}")
    print(f"Max Rows: {args.max_rows}")
    print("=" * 68, flush=True)
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
    except AutomationError as err:
        print(f"[FATAL] {err}", file=sys.stderr)
        raise SystemExit(2)
