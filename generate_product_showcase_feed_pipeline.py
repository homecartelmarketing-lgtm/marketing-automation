"""Product Showcase Feed (4:5 Ratio) AI Generation & Blending Pipeline.

This pipeline is DEDICATED to Product Showcase Feeds (4:5 Ratio) for Table Lamps on Airtable
(default Table ID: tbln0MNBaVVrZ0wrF - "Product Showcase Feed Table Lamp").

Workflow per Row (3 Active Products -> 4 Feed Slides):
    0. Akeneo Scraping (3 ACTIVE Table Lamps per row, disabled items strictly skipped)
       -> 'Furniture Item1', 'Item Name1', 'Furniture Item2', 'Item Name2', 'Furniture Item3', 'Item Name3'
       -> Status: 'Standby'
    1. Slide 1 (Thumbnail): 3 Table Lamps blended onto 3-podium layout ('Multiple Platform' / 'thumbnail_plat.jpg')
    2. Slide 2 (Solo 1): Product 1 on single podium ('Solo Thumbnail' / 'solo_plat.jpg') + 'Item Name1'
    3. Slide 3 (Solo 2): Product 2 on single podium + 'Item Name2'
    4. Slide 4 (Solo 3): Product 3 on single podium + 'Item Name3'
    5. Final Assembly: Attach all 4 slides to 'FEED - Product Showcase Feed' -> Status: 'Done'
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import re
import shutil
import sys
import tempfile
import time
from typing import Any, List, Optional
import requests

from PIL import Image

from content_automation.airtable_client import current_pht_timestamp
from content_automation.akeneo_client import AkeneoClient, first_attribute, split_item_name
from content_automation.config import load_settings
from content_automation.errors import AutomationError, ProviderError
from content_automation.fal_client import FalClient
from content_automation.media import attachment_filename, download_to_temp_file
from content_automation.overlay import HOMECARTEL_LOGO_BOX, stamp_logo
from content_automation.scraping import ScrapeAirtableClient, load_scrape_settings
from content_automation.scraping.categories import (
    SCRAPE_CATEGORIES,
    akeneo_category_code,
)
from content_automation.scraping.products import (
    ProductItem,
    product_item,
    _newest_first,
)
from content_automation.shopify_client import ShopifyCatalogIndex, ShopifyClient


# ── Configurations ─────────────────────────────────────────────────────────────

DEFAULT_TABLE_ID = (
    os.getenv("AIRTABLE_TABLE_ID_PRODUCT_SHOWCASE_FEED", "").strip()
    or os.getenv("AIRTABLE_TABLE_ID_TABLE_LAMPS", "").strip()
    or "tbln0MNBaVVrZ0wrF"
)
DEFAULT_CATEGORY = "table_lamps"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"
ASPECT_RATIO_4_5 = "4:5"

OUTPUT_FEED_FIELD = "FEED - Product Showcase Feed"
LEGACY_OUTPUT_FEED_FIELD = "FEED - Product Showcase Feed (4)"

PROJECT_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = PROJECT_ROOT / "JSON Prompts" / "Product Showcase Feed"
DEFAULT_THUMBNAIL_LAYOUT = PROMPTS_DIR / "thumbnail_plat.jpg"
DEFAULT_SOLO_LAYOUT = PROMPTS_DIR / "solo_plat.jpg"
THUMBNAIL_PROMPT_PATH = PROMPTS_DIR / "product-showcase-feed_thubmanail.json"
SOLO_PROMPT_PATH = PROMPTS_DIR / "product-showcase-feed-solo.json"


# ── Helpers & Asset Resolution ──────────────────────────────────────────────────

def load_prompt_template(path: Path) -> str:
    """Load JSON prompt template as string."""
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8")
def extract_attachment_url(record_fields: dict, field_name: str) -> Optional[str]:
    """Extract primary URL from an attachment field."""
    attachments = record_fields.get(field_name) or []
    if not attachments:
        return None
    att = attachments[0]
    return att.get("url") or att.get("thumbnails", {}).get("full", {}).get("url")


def resolve_logo_path(record_fields: dict | None = None) -> tuple[Path, Any]:
    """Resolve HomeCartel logo path, checking table attachment first, then local disk fallback."""
    if record_fields:
        for fname in ("Logo", "Logo Watermark", "Brand Logo"):
            url = extract_attachment_url(record_fields, fname)
            if url:
                try:
                    resp = requests.get(url, stream=True, timeout=20)
                    downloaded = download_to_temp_file(
                        resp, prefix="feed_logo_", suffix=".png", context="Download table logo"
                    )
                    return downloaded.path, downloaded
                except Exception as err:
                    print(f"   [WARN] Failed downloading logo attachment ({err}), using local asset.", flush=True)
                break

    candidates = [
        Path("assets/homecartel_logo.png"),
        Path(__file__).parent / "assets" / "homecartel_logo.png",
        Path("assets/Logo.png"),
        Path(__file__).parent / "assets" / "Logo.png",
    ]
    for p in candidates:
        if p.is_file():
            return p, None
    return Path("assets/homecartel_logo.png"), None


def get_slot_product_info(record_fields: dict, slot_idx: int) -> tuple[Optional[str], str]:
    """Extract product image URL and item name for a 1-indexed slot (1, 2, 3)."""
    # Image candidates
    img_candidates = [
        f"Furniture Item{slot_idx}",
        f"Furniture Item {slot_idx}",
        f"Furniture Item{'' if slot_idx == 1 else slot_idx}",
    ]
    img_url = None
    for f in img_candidates:
        url = extract_attachment_url(record_fields, f)
        if url:
            img_url = url
            break

    # Name candidates
    name_candidates = [
        f"Item Name{slot_idx}",
        f"Item Name {slot_idx}",
        f"Item Name{'' if slot_idx == 1 else slot_idx}",
        f"Title{slot_idx}",
        f"Product Name{slot_idx}",
    ]
    item_name = ""
    for f in name_candidates:
        val = record_fields.get(f)
        if val:
            item_name = str(val).strip()
            break

    return img_url, item_name


def resolve_thumbnail_layout_url(
    record_fields: dict,
    fal: FalClient,
    airtable: Optional[ScrapeAirtableClient] = None,
    record_id: Optional[str] = None,
) -> str:
    """Get multiple platform layout URL (from Airtable attachment or uploaded local default)."""
    candidates = ["Multiple Platform", "Thumbnail Platform", "Multiple Platform Layout"]
    for c in candidates:
        url = extract_attachment_url(record_fields, c)
        if url:
            return url

    if not DEFAULT_THUMBNAIL_LAYOUT.is_file():
        raise FileNotFoundError(f"Default thumbnail layout not found at {DEFAULT_THUMBNAIL_LAYOUT}")

    # Auto-upload and attach to Airtable record field if missing
    if airtable and record_id:
        try:
            print(f"   [ATTACH] Auto-uploading '{DEFAULT_THUMBNAIL_LAYOUT.name}' to Airtable 'Multiple Platform'...", flush=True)
            airtable.upload_attachment(record_id, "Multiple Platform", DEFAULT_THUMBNAIL_LAYOUT, DEFAULT_THUMBNAIL_LAYOUT.name)
            rec = airtable.get_record(record_id)
            if rec:
                url = extract_attachment_url(rec.get("fields", {}), "Multiple Platform")
                if url:
                    return url
        except Exception as e:
            print(f"   [WARN] Could not attach Multiple Platform to Airtable: {e}", flush=True)

    return fal.upload_file(str(DEFAULT_THUMBNAIL_LAYOUT))


def resolve_solo_layout_url(
    record_fields: dict,
    fal: FalClient,
    slot_idx: int = 1,
    airtable: Optional[ScrapeAirtableClient] = None,
    record_id: Optional[str] = None,
) -> str:
    """Get solo platform layout URL (from Airtable attachment or uploaded local default)."""
    candidates = [
        "Solo Thumbnail",
        "Solo Platform",
        f"Solo Thumbnail{slot_idx}",
        f"Solo Platform{slot_idx}",
    ]
    for c in candidates:
        url = extract_attachment_url(record_fields, c)
        if url:
            return url

    if not DEFAULT_SOLO_LAYOUT.is_file():
        raise FileNotFoundError(f"Default solo layout not found at {DEFAULT_SOLO_LAYOUT}")

    # Auto-upload and attach to Airtable record field if missing
    if airtable and record_id:
        try:
            print(f"   [ATTACH] Auto-uploading '{DEFAULT_SOLO_LAYOUT.name}' to Airtable 'Solo Thumbnail'...", flush=True)
            airtable.upload_attachment(record_id, "Solo Thumbnail", DEFAULT_SOLO_LAYOUT, DEFAULT_SOLO_LAYOUT.name)
            rec = airtable.get_record(record_id)
            if rec:
                url = extract_attachment_url(rec.get("fields", {}), "Solo Thumbnail")
                if url:
                    return url
        except Exception as e:
            print(f"   [WARN] Could not attach Solo Thumbnail to Airtable: {e}", flush=True)

    return fal.upload_file(str(DEFAULT_SOLO_LAYOUT))


def resolve_output_field(record_fields: dict) -> str:
    """Resolve target output field name."""
    if OUTPUT_FEED_FIELD in record_fields:
        return OUTPUT_FEED_FIELD
    if LEGACY_OUTPUT_FEED_FIELD in record_fields:
        return LEGACY_OUTPUT_FEED_FIELD
    return OUTPUT_FEED_FIELD


def load_table_identities(airtable: ScrapeAirtableClient) -> tuple[set[str], set[str]]:
    """Collect all existing SKUs and Item Names from Airtable records to prevent duplicates."""
    records = airtable.list_records()
    existing_skus: set[str] = set()
    existing_names: set[str] = set()
    for rec in records:
        fields = rec.get("fields", {})
        for slot in range(1, 4):
            for f in [f"SKU{slot}", f"SKU {slot}", f"SKU{'' if slot == 1 else slot}"]:
                val = fields.get(f)
                if val:
                    existing_skus.add(str(val).strip().lower())
            for f in [f"Item Name{slot}", f"Item Name {slot}", f"Item Name{'' if slot == 1 else slot}"]:
                val = fields.get(f)
                if val:
                    existing_names.add(str(val).strip().lower())
    return existing_skus, existing_names


# ── Scraping Logic (Active Products Only) ───────────────────────────────────────

def scrape_active_table_lamps(
    akeneo: AkeneoClient,
    airtable: ScrapeAirtableClient,
    rows: int = 1,
    style: str = DEFAULT_STYLE,
    shopify_check: bool = True,
    dry_run: bool = False,
) -> list[str]:
    """Scrape active Table Lamps from Akeneo and create rows in Airtable (3 items per row).

    Strict rule: Only products with enabled=True are scraped; disabled products are skipped.
    Cross-checks candidates against active/published catalog in Shopify (homecartel.net).
    """
    print(f"\n[INFO] Authenticating with Akeneo PIM & Loading Table Inventory...")
    akeneo.authenticate()

    existing_skus, existing_names = load_table_identities(airtable)
    print(f"[INFO] Current Airtable inventory: {len(existing_skus)} SKUs, {len(existing_names)} Names")

    # Shopify published catalog cross-check
    shopify_index: ShopifyCatalogIndex | None = None
    if shopify_check:
        try:
            print("[INFO] Fetching published catalog from Shopify (homecartel.net)...")
            shopify = ShopifyClient()
            shopify_index = shopify.load_published_identities()
        except Exception as s_err:
            print(f"[WARN] Shopify index check skipped: {s_err}")
    else:
        print("[INFO] Shopify cross-check disabled via configuration.")

    akeneo_cat = akeneo_category_code(DEFAULT_CATEGORY)
    query = {
        "categories": [{"operator": "IN", "value": [akeneo_cat]}],
        "Style2": [{"operator": "IN", "value": [style]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    print(f"[INFO] Fetching active {style} Table Lamps from Akeneo...")
    raw_products = akeneo.fetch_products(query)
    print(f"[INFO] Received {len(raw_products)} raw items from Akeneo.")

    # Filter strictly for enabled, non-duplicate, image-bearing products
    candidates: list[ProductItem] = []
    skipped_disabled = 0
    skipped_duplicate = 0
    skipped_shopify = 0

    for raw in _newest_first(raw_products):
        if raw.get("enabled") is False:
            skipped_disabled += 1
            continue

        item = product_item(raw)
        if item is None:
            continue

        sku_clean = item.sku.strip().lower()
        name_clean = item.item_name.strip().lower()

        if sku_clean in existing_skus or name_clean in existing_names:
            skipped_duplicate += 1
            continue

        if shopify_index and not shopify_index.contains(item.sku, item.item_name):
            try:
                print(
                    f"[SHOPIFY DRAFT/INACTIVE SKIP] Item '{item.item_name}' (SKU: {item.sku}) is Enabled in Akeneo "
                    "but Draft/Inactive in Shopify -> skipping to next unique item"
                )
            except Exception:
                print(
                    f"[SHOPIFY DRAFT/INACTIVE SKIP] SKU {item.sku} is Enabled in Akeneo "
                    "but Draft/Inactive in Shopify -> skipping to next unique item"
                )
            skipped_shopify += 1
            continue

        # Prevent duplicate selection within this current run
        existing_skus.add(sku_clean)
        existing_names.add(name_clean)
        candidates.append(item)

    print(
        f"[INFO] Filtered candidates: {len(candidates)} active eligible items. "
        f"(Skipped: {skipped_disabled} disabled, {skipped_duplicate} duplicates, {skipped_shopify} not live on Shopify)"
    )

    needed_items = rows * 3
    if len(candidates) < needed_items:
        print(f"[WARNING] Requested {rows} rows ({needed_items} items) but only found {len(candidates)} new active items.")

    created_record_ids: list[str] = []
    items_to_process = candidates[:needed_items]

    # Chunk into 3-item groups per row
    chunks = [items_to_process[i : i + 3] for i in range(0, len(items_to_process), 3)]

    for chunk_idx, group in enumerate(chunks, 1):
        if len(group) < 3:
            print(f"[WARNING] Skipping incomplete group ({len(group)} items) for row {chunk_idx}.")
            continue

        print(f"\n[INFO] Creating Airtable Row {chunk_idx}/{len(chunks)} with 3 Active Table Lamps:")
        if dry_run:
            names = [p.item_name for p in group]
            skus = [p.sku for p in group]
            print(f"   [DRY-RUN] Would create Airtable row with items: {names} (SKUs: {skus})")
            created_record_ids.append(f"dry_run_rec_{chunk_idx}")
            continue

        record_fields: dict[str, Any] = {
            "Status": "Standby",
        }

        temp_files_to_cleanup = []
        try:
            for slot_idx, prod in enumerate(group, 1):
                record_fields[f"Item Name{slot_idx}"] = prod.item_name

            rec_id = airtable.create_record(record_fields)
            print(f"[SUCCESS] Created Airtable Record base: {rec_id}")

            for slot_idx, prod in enumerate(group, 1):
                print(f"   Slot {slot_idx}: {prod.item_name} (SKU: {prod.sku})")
                media = akeneo.download_media(prod.media_code)
                temp_files_to_cleanup.append(media.path)
                
                airtable.upload_attachment(
                    rec_id,
                    f"Furniture Item{slot_idx}",
                    media.path,
                    f"product_slot_{slot_idx}_{prod.sku}.jpg",
                )

            # Automatically attach default platform layouts into Airtable fields
            if DEFAULT_THUMBNAIL_LAYOUT.is_file():
                print(f"   Attaching Multiple Platform layout ({DEFAULT_THUMBNAIL_LAYOUT.name})...", flush=True)
                airtable.upload_attachment(
                    rec_id,
                    "Multiple Platform",
                    DEFAULT_THUMBNAIL_LAYOUT,
                    DEFAULT_THUMBNAIL_LAYOUT.name,
                )
            if DEFAULT_SOLO_LAYOUT.is_file():
                print(f"   Attaching Solo Thumbnail layout ({DEFAULT_SOLO_LAYOUT.name})...", flush=True)
                airtable.upload_attachment(
                    rec_id,
                    "Solo Thumbnail",
                    DEFAULT_SOLO_LAYOUT,
                    DEFAULT_SOLO_LAYOUT.name,
                )

            print(f"[SUCCESS] Created complete Airtable Record: {rec_id} (Status: Standby)", flush=True)
            created_record_ids.append(rec_id)
        finally:
            for tf in temp_files_to_cleanup:
                try:
                    if tf.is_file():
                        tf.unlink(missing_ok=True)
                except Exception:
                    pass

    return created_record_ids


# ── Generation Pipeline (Nano Banana Pro / Fal AI) ─────────────────────────────

def generate_product_showcase_feed_for_record(
    record_id: str,
    record_fields: dict,
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    dry_run: bool = False,
) -> bool:
    """Generate the 4-slide Product Showcase Feed for one Airtable record."""
    print(f"\n=======================================================", flush=True)
    print(f"[PROCESS] Processing Product Showcase Feed for Record: {record_id}", flush=True)
    print(f"=======================================================", flush=True)

    # 1. Validate Product Slots (with retry/wait for Airtable async attachment processing)
    p1_url = p2_url = p3_url = None
    p1_name = p2_name = p3_name = ""
    for attempt in range(5):
        p1_url, p1_name = get_slot_product_info(record_fields, 1)
        p2_url, p2_name = get_slot_product_info(record_fields, 2)
        p3_url, p3_name = get_slot_product_info(record_fields, 3)
        if p1_url and p2_url and p3_url:
            break
        print(f"   [WAIT] Waiting for Airtable attachment ingestion (attempt {attempt + 1}/5)...", flush=True)
        time.sleep(2.0)
        rec = airtable.get_record(record_id)
        if rec:
            record_fields = rec.get("fields", {})

    if not p1_url or not p2_url or not p3_url:
        print(f"[ERROR] Missing product attachments for record {record_id}!", flush=True)
        print(f"   Slot 1: {bool(p1_url)} ({p1_name})", flush=True)
        print(f"   Slot 2: {bool(p2_url)} ({p2_name})", flush=True)
        print(f"   Slot 3: {bool(p3_url)} ({p3_name})", flush=True)
        return False

    print(f"[*] Slot 1: {p1_name}", flush=True)
    print(f"[*] Slot 2: {p2_name}", flush=True)
    print(f"[*] Slot 3: {p3_name}", flush=True)

    if not dry_run:
        airtable.update_records([(record_id, {
            "Status": "Processing",
            "Date and Time": current_pht_timestamp(),
        })])

    # 2. Resolve Platforms (with auto-attachment to Airtable if missing)
    print(f"\n[INFO] Resolving layouts...", flush=True)
    thumbnail_layout_url = resolve_thumbnail_layout_url(record_fields, fal, airtable=airtable, record_id=record_id)
    solo_layout_url = resolve_solo_layout_url(record_fields, fal, slot_idx=1, airtable=airtable, record_id=record_id)

    generated_slide_urls: list[str] = []

    # ── Slide 1: 3-Product Thumbnail ───────────────────────────────────────────
    print(f"\n[1/4] Generating Slide 1 (3-Podium Group Showcase Slide)...", flush=True)
    thumb_prompt = load_prompt_template(THUMBNAIL_PROMPT_PATH)
    if len(thumb_prompt) > 5000:
        thumb_prompt = thumb_prompt[:5000]

    thumb_inputs = [thumbnail_layout_url, p1_url, p2_url, p3_url]
    if dry_run:
        print(f"   [DRY-RUN] Would call Fal AI with 4 images -> 4:5 ratio", flush=True)
        slide1_url = "https://fal.media/mock_slide_1.jpg"
    else:
        slide1_url = fal.generate(
            prompt=thumb_prompt,
            image_urls=thumb_inputs,
            aspect_ratio=ASPECT_RATIO_4_5,
            model="fal-ai/nano-banana-pro/edit",
        )
        print(f"   [DONE] Slide 1 Result: {slide1_url}", flush=True)
    generated_slide_urls.append(slide1_url)

    # ── Slides 2-4: Solo Product Slides ─────────────────────────────────────────
    solo_items = [
        (1, p1_url, p1_name),
        (2, p2_url, p2_name),
        (3, p3_url, p3_name),
    ]

    solo_template = load_prompt_template(SOLO_PROMPT_PATH)

    for slot_idx, prod_url, prod_name in solo_items:
        step_num = slot_idx + 1
        print(f"\n[{step_num}/4] Generating Slide {step_num} (Solo Product {slot_idx}: {prod_name})...", flush=True)
        
        prompt = solo_template
        if prod_name:
            prompt = prompt.replace("[INPUT_ITEM_NAME_HERE]", prod_name)
            prompt = prompt.replace("[Item Name]", prod_name)

        if len(prompt) > 5000:
            prompt = prompt[:5000]

        solo_inputs = [solo_layout_url, prod_url]
        if dry_run:
            print(f"   [DRY-RUN] Would call Fal AI with solo layout + product image -> 4:5 ratio", flush=True)
            slide_url = f"https://fal.media/mock_slide_{step_num}.jpg"
        else:
            slide_url = fal.generate(
                prompt=prompt,
                image_urls=solo_inputs,
                aspect_ratio=ASPECT_RATIO_4_5,
                model="fal-ai/nano-banana-pro/edit",
            )
            print(f"   [DONE] Slide {step_num} Result: {slide_url}", flush=True)
        generated_slide_urls.append(slide_url)

    # ── Stamp HomeCartel Logo onto ALL 4 Slides (Canva 4:5 Box: W=190.3, H=63.5, X=108.0, Y=1178.5) ──
    print(f"\n[LOGO] Stamping HomeCartel Feed logo onto all 4 slides...", flush=True)
    temp_downloads = []
    stamped_slide_paths = []
    logo_temp = None

    if dry_run:
        for idx in range(1, 5):
            print(
                f"   [DRY-RUN] Would stamp HomeCartel logo onto Slide {idx} "
                f"(Canva Box: W={HOMECARTEL_LOGO_BOX.width}, H={HOMECARTEL_LOGO_BOX.height}, "
                f"X={HOMECARTEL_LOGO_BOX.x}, Y={HOMECARTEL_LOGO_BOX.y})",
                flush=True,
            )
        print(f"   [DRY-RUN] Would auto-tag Solo Slides (2, 3, 4) with YOLO and upload to '{TARGET_BLENDED_FIELD}'", flush=True)
        print(f"   [DRY-RUN] Would attach all 4 watermarked slides to '{output_field}' and set Status to Done", flush=True)
        return True

    try:
        logo_path, logo_temp = resolve_logo_path(record_fields)
        for idx, url in enumerate(generated_slide_urls, 1):
            resp = requests.get(url, stream=True, timeout=30)
            dl = download_to_temp_file(resp, prefix=f"showcase_slide_{idx}_in_", suffix=".jpg", context=f"Download slide {idx}")
            temp_downloads.append(dl)

            stamped_file = Path(tempfile.gettempdir()) / f"stamped_showcase_{record_id}_{idx}.jpg"
            if logo_path and logo_path.is_file():
                try:
                    stamp_logo(dl.path, logo_path, destination=stamped_file, box=HOMECARTEL_LOGO_BOX)
                    if stamped_file.is_file():
                        stamped_slide_paths.append(stamped_file)
                        print(
                            f"   [+] Stamped HomeCartel Feed logo onto Slide {idx} "
                            f"(Canva Box: W={HOMECARTEL_LOGO_BOX.width}, H={HOMECARTEL_LOGO_BOX.height}, "
                            f"X={HOMECARTEL_LOGO_BOX.x}, Y={HOMECARTEL_LOGO_BOX.y})",
                            flush=True,
                        )
                    else:
                        stamped_slide_paths.append(dl.path)
                except Exception as stamp_err:
                    print(f"   [WARN] Failed stamping logo on Slide {idx}: {stamp_err}", flush=True)
                    stamped_slide_paths.append(dl.path)
            else:
                stamped_slide_paths.append(dl.path)

        # ── Auto-tag Solo Slides with YOLO Item Tagger ─────────────────────────────
        for slot_idx, _, prod_name in solo_items:
            step_num = slot_idx + 1
            source_for_yolo = stamped_slide_paths[slot_idx] if len(stamped_slide_paths) > slot_idx else generated_slide_urls[slot_idx]
            try:
                from content_automation.akeneo_client import split_item_name
                from content_automation.item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
                item_title, product_type = split_item_name(prod_name, fallback_product_type="Table Lamp")
                tag_and_upload_blended_image(
                    airtable=airtable,
                    record_id=record_id,
                    blended_source=source_for_yolo,
                    item_name=item_title,
                    product_type=product_type,
                    category="table_lamps",
                    target_field=TARGET_BLENDED_FIELD,
                    output_filename_prefix=f"showcase_solo_{slot_idx}",
                    fallback_if_undetected=True,
                )
            except Exception as tag_err:
                print(f"   [WARN] YOLO item tagging on Slide {step_num}: {tag_err}", flush=True)

        # ── Final Assembly: Upload 4 Watermarked Slides to Airtable ────────────────
        output_field = resolve_output_field(record_fields)
        print(f"\n[UPLOAD] Uploading all 4 watermarked slides to Airtable field '{output_field}'...", flush=True)

        try:
            airtable.clear_attachment_field(record_id, output_field)
        except Exception:
            pass

        for idx, spath in enumerate(stamped_slide_paths, 1):
            airtable.upload_attachment(record_id, output_field, spath, f"showcase_slide_{idx}_{record_id}.jpg")

        airtable.update_records([
            (
                record_id,
                {
                    "Status": "Done",
                    "Date and Time Generated": current_pht_timestamp(),
                },
            )
        ])

        print(f"\n[SUCCESS] Record {record_id} successfully completed! (4 watermarked slides attached)", flush=True)
        return True
    finally:
        for dl in temp_downloads:
            try:
                dl.cleanup()
            except Exception:
                pass
        for spath in stamped_slide_paths:
            if isinstance(spath, Path) and spath.is_file() and str(tempfile.gettempdir()) in str(spath):
                try:
                    spath.unlink(missing_ok=True)
                except Exception:
                    pass
        if logo_temp:
            try:
                logo_temp.cleanup()
            except Exception:
                pass


# ── Pipeline Runner ────────────────────────────────────────────────────────────

def run_pipeline(
    mode: str = "menu",
    max_items: int = 1,
    record_id: Optional[str] = None,
    table_id: str = DEFAULT_TABLE_ID,
    dry_run: bool = False,
    shopify_check: bool = True,
) -> bool:
    """Execute the Product Showcase Feed pipeline according to specified mode."""
    scrape_settings = load_scrape_settings(
        category_code=DEFAULT_CATEGORY,
        style_code=DEFAULT_STYLE,
        table_id_override=table_id,
    )
    general_settings = load_settings()

    airtable = ScrapeAirtableClient(
        scrape_settings.airtable_token,
        scrape_settings.airtable_base_id,
        scrape_settings.airtable_table_id,
    )

    akeneo = AkeneoClient(
        scrape_settings.akeneo_host,
        scrape_settings.akeneo_client_id,
        scrape_settings.akeneo_secret,
        scrape_settings.akeneo_username,
        scrape_settings.akeneo_password,
        channel_name=scrape_settings.channel_name,
    )

    fal = FalClient(api_key=general_settings.fal_key)

    print(f"==================================================")
    print(f"  HomeCartel - Product Showcase Feed Pipeline")
    print(f"  Target Table ID: {scrape_settings.airtable_table_id}")
    print(f"  Category: {DEFAULT_CATEGORY} ({DEFAULT_STYLE})")
    print(f"==================================================")

    # 1. Mode: Scrape
    if mode == "scrape":
        created = scrape_active_table_lamps(
            akeneo,
            airtable,
            rows=max_items,
            style=DEFAULT_STYLE,
            shopify_check=shopify_check,
            dry_run=dry_run,
        )
        print(f"\n[RESULT] Scraped {len(created)} new rows into Airtable.")
        return len(created) > 0

    # 2. Mode: Generate
    if mode == "generate":
        if record_id:
            rec = airtable.get_record(record_id)
            if not rec:
                print(f"[ERROR] Record {record_id} not found.")
                return False
            return generate_product_showcase_feed_for_record(
                record_id, rec.get("fields", {}), fal, airtable, dry_run=dry_run
            )

        all_records = airtable.list_records()
        records = [
            r for r in all_records
            if r.get("fields", {}).get("Status") == "Standby"
        ]
        if not records:
            # Also check if there are records with empty status but valid products and no final output
            records = [
                r for r in all_records
                if not r.get("fields", {}).get(OUTPUT_FEED_FIELD)
                and not r.get("fields", {}).get(LEGACY_OUTPUT_FEED_FIELD)
                and (r.get("fields", {}).get("Furniture Item1") or r.get("fields", {}).get("Furniture Item"))
            ]

        if not records:
            print(f"[INFO] No pending Standby records found in table {scrape_settings.airtable_table_id}.")
            return True

        print(f"[INFO] Found {len(records)} pending record(s). Processing up to {max_items}...")
        success_count = 0
        for r in records[:max_items]:
            rec_id = r["id"]
            fields = r.get("fields", {})
            ok = generate_product_showcase_feed_for_record(rec_id, fields, fal, airtable, dry_run=dry_run)
            if ok:
                success_count += 1

        print(f"\n[SUMMARY] Successfully processed {success_count}/{min(len(records), max_items)} record(s).")
        return success_count > 0

    # 3. Mode: All (Prioritize Pending Rows -> Scrape New Rows -> Generate)
    if mode == "all":
        # Check if there are already pending rows that need generation before scraping new items
        all_recs = airtable.list_records()
        pending_records = [
            r for r in all_recs
            if (
                r.get("fields", {}).get("Status") in ("Standby", "Processing")
                or not r.get("fields", {}).get(OUTPUT_FEED_FIELD)
            )
            and (r.get("fields", {}).get("Furniture Item1") or r.get("fields", {}).get("Furniture Item"))
        ]

        created_ids = []
        if pending_records:
            print(f"[INFO] Found {len(pending_records)} pending/in-progress row(s) ready for generation.", flush=True)
            created_ids = [r["id"] for r in pending_records[:max_items]]
        else:
            print(f"\n>>> Phase 0: Scraping {max_items} row(s) of active Table Lamps from Akeneo...", flush=True)
            created_ids = scrape_active_table_lamps(
                akeneo,
                airtable,
                rows=max_items,
                style=DEFAULT_STYLE,
                shopify_check=shopify_check,
                dry_run=dry_run,
            )

        if not created_ids:
            print("[INFO] No pending rows found and no new rows created.", flush=True)
            return True

        print(f"\n>>> Phase 1-4: Generating Feeds for {len(created_ids)} row(s)...", flush=True)
        success_count = 0
        for rec_id in created_ids:
            rec = airtable.get_record(rec_id)
            if rec:
                ok = generate_product_showcase_feed_for_record(
                    rec_id, rec.get("fields", {}), fal, airtable, dry_run=dry_run
                )
                if ok:
                    success_count += 1

        print(f"\n[FINAL SUMMARY] End-to-End completed {success_count}/{len(created_ids)} record(s).", flush=True)
        return success_count > 0

    # 4. Mode: Interactive Menu
    if mode == "menu":
        while True:
            print("\n" + "=" * 50)
            print("  Product Showcase Feed - Main Menu")
            print("=" * 50)
            print("  [1] Full Automation (Scrape 3 Active Items -> Generate 4 Slides -> Upload)")
            print("  [2] Scrape Only (Fetch 3 Active Table Lamps from Akeneo)")
            print("  [3] Generate Only (Process pending Standby rows)")
            print("  [4] Process Specific Record ID")
            print("  [5] Exit")
            print("-" * 50)
            choice = input("Enter selection [1-5]: ").strip()

            if choice == "1":
                num = input("How many rows to process? (default: 1): ").strip()
                rows = int(num) if num.isdigit() and int(num) > 0 else 1
                run_pipeline(mode="all", max_items=rows, table_id=table_id, dry_run=dry_run, shopify_check=shopify_check)
            elif choice == "2":
                num = input("How many rows to scrape? (default: 1): ").strip()
                rows = int(num) if num.isdigit() and int(num) > 0 else 1
                run_pipeline(mode="scrape", max_items=rows, table_id=table_id, dry_run=dry_run, shopify_check=shopify_check)
            elif choice == "3":
                num = input("How many pending rows to generate? (default: 1): ").strip()
                rows = int(num) if num.isdigit() and int(num) > 0 else 1
                run_pipeline(mode="generate", max_items=rows, table_id=table_id, dry_run=dry_run, shopify_check=shopify_check)
            elif choice == "4":
                rid = input("Enter Airtable Record ID (e.g., recXXXXXXXXXXXXXX): ").strip()
                if rid:
                    run_pipeline(mode="generate", record_id=rid, table_id=table_id, dry_run=dry_run, shopify_check=shopify_check)
            elif choice == "5":
                print("Goodbye!")
                break
            else:
                print("Invalid option. Please choose 1 to 5.")
        return True

    return False


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="End-to-End Product Showcase Feed (4:5 Ratio) AI Generation Pipeline."
    )
    parser.add_argument(
        "--mode",
        choices=["menu", "scrape", "generate", "all"],
        default="menu",
        help="Operation mode (default: menu).",
    )
    parser.add_argument(
        "--max-items",
        "--rows",
        type=int,
        default=1,
        help="Number of rows to scrape or process (default: 1).",
    )
    parser.add_argument(
        "--record-id",
        type=str,
        default=None,
        help="Target a specific Airtable Record ID for generation.",
    )
    parser.add_argument(
        "--table-id",
        type=str,
        default=DEFAULT_TABLE_ID,
        help=f"Target Airtable Table ID (default: {DEFAULT_TABLE_ID}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without modifying Airtable or calling paid AI models.",
    )
    parser.add_argument(
        "--no-shopify-check",
        action="store_true",
        default=False,
        help="Disable Shopify published products cross-check (default: enabled).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    success = run_pipeline(
        mode=args.mode,
        max_items=args.max_items,
        record_id=args.record_id,
        table_id=args.table_id,
        dry_run=args.dry_run,
        shopify_check=not args.no_shopify_check,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
