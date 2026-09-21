"""Scrape Akeneo product images and names into dedicated Airtable fields."""

from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
import sys
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests

from ..akeneo_client import AkeneoClient
from ..media import DownloadedMedia, attachment_filename, download_to_temp_file
from ..shopify_client import ShopifyCatalogIndex, ShopifyClient
from . import categories
from .airtable import API_BASE, ScrapeAirtableClient
from .products import ProductItem, identity_key, select_new_products


LAYOUT_CONFIGURATIONS: list[tuple[tuple[str, ...], list[Path], str]] = [
    (
        (
            "Moodboard Layout",
            "Converted Moodboard Layout",
            "Layout Moodboard",
            "Moodboard #1 Layout",
        ),
        [
            Path("assets/moodboard_layout.jpg"),
            Path("JSON Prompts/Moodboard V1/firstlayoutmoodboard.jpg"),
            Path("JSON Prompts/Moodboard V1/moodboard_converted.png"),
            Path("firstlayoutmoodboard.jpg"),
            Path("moodboard_layout.jpg"),
        ],
        "moodboard_layout.jpg",
    ),
    (
        (
            "Moodboard #2 Layout",
            "Moodboard 2 Layout",
            "Moodboard V2 Layout",
        ),
        [
            Path("JSON Prompts/Moodboard V2/referencephoto_moodboard.png"),
            Path("assets/referencephoto_moodboard.png"),
            Path("referencephoto_moodboard.png"),
        ],
        "referencephoto_moodboard.png",
    ),
    (
        (
            "Product Closeup Description Layout",
            "Product Closeup Description Layout1",
        ),
        [
            Path("assets/layout_product_v2.jpg"),
            Path("JSON Prompts/Product Closeup V2/layout_product_v2.jpg"),
            Path("layout_product_v2.jpg"),
        ],
        "layout_product_v2.jpg",
    ),
    (
        (
            "Closeup Photo Layout",
            "Moodboard #1 Layout Closeup",
            "Product Closeup Layout",
            "Closeup Layout",
        ),
        [
            Path("assets/closeup_layout.jpg"),
            Path("closeup_layout.jpg"),
        ],
        "closeup_layout.jpg",
    ),
    (
        (
            "Product Closeup w/ Specs Layout",
            "Product Closeup with Specs Layout",
            "Product Closeup Specs Layout",
            "Product Specs Layout",
            "Specs Layout",
        ),
        [
            Path("assets/product_specs_layout.png"),
            Path("JSON Prompts/Product Closeup with Specs/product_specs_layout.png"),
            Path("product_specs_layout.png"),
        ],
        "product_specs_layout.png",
    ),
    (
        (
            "CTA Blended Image Watermark Layout",
            "CTA Layout",
            "CTA Watermark Layout",
        ),
        [
            Path("assets/cta_layout.jpg"),
            Path("JSON Prompts/CTA/cta_layout.jpg"),
            Path("JSON Prompts/cta_layout.jpg"),
            Path("cta_layout.jpg"),
        ],
        "cta_layout.jpg",
    ),
    (
        (
            "Logo",
            "HomeCartel Logo",
            "Brand Logo",
            "Watermark Logo",
            "Logo Image",
            "Logo Watermark For Story",
            "Logo Watermark",
            "Moodboard Watermark",
        ),
        [
            Path("assets/homecartel_logo.png"),
            Path("JSON Prompts/homecartel_logo.png"),
            Path("scratch/refined_logo.png"),
            Path("scratch/removed_bg_logo.png"),
            Path("content_automation/assets/logo.png"),
            Path("static/img/logo.png"),
            Path("logo.png"),
        ],
        "homecartel_logo.png",
    ),
    (
        ("This or That Layout",),
        [
            Path("assets/thisorthatlayout.jpg"),
            Path("JSON Prompts/This or That/thisorthatlayout.jpg"),
            Path("JSON Prompts/thisorthatlayout.jpg"),
            Path("thisorthatlayout.jpg"),
        ],
        "thisorthatlayout.jpg",
    ),
    (
        ("Myth Layout", "Myth Emoticon ", "Myth Emoticon"),
        [
            Path("JSON Prompts/Myth and Fact/myth_layout.jpg"),
            Path("JSON Prompts/Myth and Fact/0-02-06-324215afe8a9daad6830b53fe3a8da915f5961f75e8a0f58b567ce22fdda24c7_3001564131aaeb1d.jpg"),
        ],
        "myth_layout.jpg",
    ),
    (
        ("Fact Layout", "Fact Emoticon", "Fact Emoticon "),
        [
            Path("JSON Prompts/Myth and Fact/fact_layout.jpg"),
            Path("JSON Prompts/Myth and Fact/0-02-06-c1752a0e95b3c7b832ec15d361bc2fb1370bf58170d1cbd5d9d55189c581e426_759be242e44ec1f5.jpg"),
        ],
        "fact_layout.jpg",
    ),
    (
        ("Debunk Layout",),
        [
            Path("JSON Prompts/Myth and Fact/debunk_layout.jpg"),
            Path("JSON Prompts/Myth and Fact/debunk_myth_layout.jpg"),
        ],
        "debunk_layout.jpg",
    ),
    (
        ("Outro Layout",),
        [
            Path("assets/Outro-Myth-Fact.png"),
            Path("assets/outro_layout.jpg"),
            Path("Outro for All Reels/Outro.jpg"),
            Path("JSON Prompts/Myth and Fact/outro_layout.jpg"),
        ],
        "Outro-Myth-Fact.png",
    ),
    (
        ("Outro",),
        [
            Path("assets/outro_layout.jpg"),
            Path("Outro for All Reels/Outro.jpg"),
            Path("JSON Prompts/Myth and Fact/outro_layout.jpg"),
        ],
        "outro_layout.jpg",
    ),
]


def resolve_layout_source(
    field_aliases: tuple[str, ...],
    candidates: list[Path],
    target_filename: str,
    has_field_fn: Any,
    existing_records: list[dict] | None = None,
    find_field_fn: Any = None,
) -> tuple[str | None, Path | DownloadedMedia | None, str]:
    """Find matching field name and source file/downloaded attachment."""
    target_field = None
    for f in field_aliases:
        if find_field_fn:
            actual = find_field_fn(f)
            if actual:
                target_field = actual
                break
        elif has_field_fn(f):
            target_field = f
            break
    if not target_field:
        return None, None, target_filename

    # 1. Local file candidate
    for p in candidates:
        if p.is_file():
            return target_field, p, target_filename

    # 2. Workspace search fallback for logos
    if "logo" in target_filename.lower():
        for base in [Path("assets"), Path("JSON Prompts"), Path("static"), Path(".")]:
            if base.is_dir():
                matches = list(base.rglob("*logo*.png"))
                if matches:
                    return target_field, matches[0], target_filename

    # 3. Hybrid fallback: find an existing record in the table that already has this layout attachment
    if existing_records:
        for record in existing_records:
            atts = record.get("fields", {}).get(target_field) or []
            if isinstance(atts, list) and atts:
                url = atts[0].get("url") if isinstance(atts[0], dict) else None
                if url:
                    try:
                        resp = requests.get(url, stream=True)
                        downloaded = download_to_temp_file(
                            resp,
                            prefix="layout_dl_",
                            suffix=Path(target_filename).suffix or ".jpg",
                            context=f"Download existing layout from {url}",
                        )
                        return target_field, downloaded, target_filename
                    except Exception as err:
                        print(f"[WARN] Failed downloading existing layout from Airtable: {err}")

    return target_field, None, target_filename


def format_item_name_with_product_type(
    item_name: str,
    product_type: str = "",
    category_code: str = "",
) -> str:
    """Standardize item name formatting as 'Item Name | Product Type'."""
    category_defaults = {
        "floor_lamps": "Floor Lamp",
        "floor_lamp": "Floor Lamp",
        "pendant_lights": "Pendant Light",
        "pendant_light": "Pendant Light",
        "chandeliers": "Chandelier",
        "chandelier": "Chandelier",
        "cluster_chandeliers": "Cluster Chandelier",
        "table_lamps": "Table Lamp",
        "table_lamp": "Table Lamp",
        "wall_lights": "Wall Light",
        "wall_light": "Wall Light",
        "ceiling_mounted": "Ceiling Mounted",
        "ceiling_lights": "Ceiling Mounted",
        "ceiling_light": "Ceiling Mounted",
    }
    cat_fallback = category_defaults.get((category_code or "").lower().strip(), "")
    raw_type = (product_type or "").strip()
    styles_list = {"modern", "contemporary", "classic", "vintage", "nordic", "industrial", "minimalist"}
    if raw_type and raw_type.lower() not in styles_list:
        chosen_type = raw_type
    elif cat_fallback:
        chosen_type = cat_fallback
    else:
        chosen_type = ""

    raw_name = (item_name or "").strip()
    if not raw_name:
        return chosen_type

    if " | " in raw_name:
        parts = [p.strip() for p in raw_name.split(" | ") if p.strip()]
        if len(parts) >= 2:
            return f"{parts[0]} | {parts[1]}"
        raw_name = parts[0]

    if chosen_type:
        if raw_name.lower().endswith(chosen_type.lower()):
            base = raw_name[:-len(chosen_type)].strip(" -|,")
            if base:
                return f"{base} | {chosen_type}"
            return f"{raw_name} | {chosen_type}"
        elif chosen_type.lower() not in raw_name.lower():
            return f"{raw_name} | {chosen_type}"
        else:
            return f"{raw_name} | {chosen_type}"
    return raw_name


def fetch_all_base_existing_identities(
    airtable_client: ScrapeAirtableClient,
    max_workers: int = 10,
) -> tuple[set[str], set[str], set[str]]:
    """Fetch all unique SKUs, normalized Item Names, and attachment filenames across ALL tables in the Airtable base."""
    url = f"{API_BASE}/meta/bases/{airtable_client.base_id}/tables"
    try:
        response = airtable_client._request("GET", url, retry_server_errors=True)
        if not response.ok:
            return set(), set(), set()
        tables = response.json().get("tables", [])
    except Exception:
        return set(), set(), set()

    all_skus: set[str] = set()
    all_names: set[str] = set()
    all_filenames: set[str] = set()

    def _scan_table(table_info: dict) -> tuple[set[str], set[str], set[str]]:
        t_id = table_info.get("id")
        fields = table_info.get("fields", [])
        sku_fields = [
            f["name"]
            for f in fields
            if any(k in f.get("name", "").lower() for k in ("sku", "legacy sku"))
        ]
        name_fields = [
            f["name"]
            for f in fields
            if any(
                k in f.get("name", "").lower()
                for k in ("item name", "item_name", "product name", "product_name", "title")
            )
        ]
        att_fields = [
            f["name"]
            for f in fields
            if f.get("type") == "multipleAttachments"
            and any(
                k in f.get("name", "").lower()
                for k in ("furniture", "item", "product", "photo", "image", "interior", "blend")
            )
        ]
        query_fields = list(set(sku_fields + name_fields + att_fields))
        if not query_fields:
            return set(), set(), set()

        t_skus: set[str] = set()
        t_names: set[str] = set()
        t_files: set[str] = set()
        req_url = f"{API_BASE}/{airtable_client.base_id}/{t_id}?pageSize=100"
        offset = None
        while True:
            fetch_url = req_url + (f"&offset={offset}" if offset else "")
            try:
                resp = airtable_client._request("GET", fetch_url, retry_server_errors=True)
                if not resp.ok:
                    break
                data = resp.json()
                for rec in data.get("records", []):
                    rf = rec.get("fields", {})
                    for sf in sku_fields:
                        val = rf.get(sf)
                        if val:
                            if isinstance(val, list):
                                for item in val:
                                    s_str = str(item).strip()
                                    t_skus.add(s_str)
                                    t_skus.add(identity_key(s_str))
                            else:
                                for line in str(val).splitlines():
                                    s_str = line.strip()
                                    if s_str:
                                        t_skus.add(s_str)
                                        t_skus.add(identity_key(s_str))
                    for nf in name_fields:
                        n_val = rf.get(nf)
                        if n_val:
                            n_str = str(n_val).strip()
                            t_names.add(identity_key(n_str))
                            if " | " in n_str:
                                base_part = n_str.split(" | ")[0].strip()
                                if base_part:
                                    t_names.add(identity_key(base_part))
                    for af in att_fields:
                        atts = rf.get(af) or []
                        if isinstance(atts, list):
                            for att in atts:
                                if isinstance(att, dict) and att.get("filename"):
                                    t_files.add(identity_key(att["filename"]))
                offset = data.get("offset")
                if not offset:
                    break
            except Exception:
                break
        return t_skus, t_names, t_files

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for skus, names, files in executor.map(_scan_table, tables):
            all_skus.update(skus)
            all_names.update(names)
            all_filenames.update(files)

    return all_skus, all_names, all_filenames


def attachment_filenames(
    records: list[dict],
    field_name: str,
) -> set[str]:
    """Normalized filenames already attached to ``field_name``."""
    filenames: set[str] = set()
    for record in records:
        attachments = record.get("fields", {}).get(field_name) or []
        for attachment in attachments:
            filename = attachment.get("filename") if isinstance(attachment, dict) else ""
            if filename:
                filenames.add(identity_key(filename))
    return filenames


def item_name_with_product_type(item: ProductItem, category_code: str = "") -> str:
    """Join Akeneo's item name and product type for Airtable."""
    return format_item_name_with_product_type(
        item.item_name,
        item.product_type,
        category_code=category_code,
    )


class FurnitureItemScrapeRunner:
    """Create one row per Akeneo product with its name and source image."""

    def __init__(
        self,
        akeneo: AkeneoClient,
        airtable: ScrapeAirtableClient,
        *,
        category_code: str,
        style_code: str,
        field_name: str,
        item_name_field: str,
        sku_field: str | None = None,
        status_field: str | None = None,
        default_status: str = "Standby",
        include_product_type_in_name: bool = True,
        max_items: int | None = None,
        cross_table_dedup: bool = True,
        sort_by_price: bool = False,
        price_pool_size: int = 50,
        layout_fields: dict[str, str] | None = None,
        backfill_layouts: bool = True,
        shopify_cross_check: bool = True,
        starting_letter: str | None = None,
    ):
        self.akeneo = akeneo
        self.airtable = airtable
        self.starting_letter = starting_letter or os.getenv("SCRAPE_STARTING_LETTER")
        self.category_code = category_code
        self.style_code = style_code
        self.field_name = field_name
        self.item_name_field = item_name_field
        self.sku_field = sku_field
        self.status_field = status_field
        self.default_status = default_status
        self.include_product_type_in_name = include_product_type_in_name
        self.max_items = max_items
        self.cross_table_dedup = cross_table_dedup
        self.sort_by_price = sort_by_price
        self.price_pool_size = price_pool_size
        self.layout_fields = layout_fields or {}
        self.backfill_layouts = backfill_layouts
        self.shopify_cross_check = shopify_cross_check
        self._shopify_index: ShopifyCatalogIndex | None = None
        self._cached_records: list[dict] | None = None
        self.created_record_ids: list[str] = []

    def _fetch_candidates(self) -> list[dict]:
        akeneo_category = categories.akeneo_category_code(self.category_code)
        query = {
            "categories": [{"operator": "IN", "value": [akeneo_category]}],
            "enabled": [{"operator": "=", "value": True}],
        }
        if self.style_code and self.style_code.lower() != "all":
            query["Style2"] = [{"operator": "IN", "value": [self.style_code]}]
        print(
            f"[INFO] Fetching all active {self.style_code or 'all'} {self.category_code} "
            "products from Akeneo..."
        )
        return self.akeneo.fetch_products(query)

    def _new_items(
        self,
        products: list[dict],
        existing_filenames: set[str],
        existing_skus: set[str] | None = None,
        existing_names: set[str] | None = None,
    ) -> tuple[list[ProductItem], dict[str, int], int]:
        candidates, stats = select_new_products(
            products,
            existing_skus or set(),
            existing_item_names=existing_names,
            existing_media_codes=existing_filenames,
            category_code=self.category_code,
            sort_by_price_in_newest_pool=self.sort_by_price,
            price_pool_size=self.price_pool_size,
            starting_letter=self.starting_letter,
        )
        new_items: list[ProductItem] = []
        already_attached = 0
        excluded_shopify = 0
        for item in candidates:
            filename = attachment_filename(item.item_name, item.media_code)
            if identity_key(filename) in existing_filenames:
                try:
                    print(f"[DEDUP SKIP] Existing item: '{item.item_name}' (SKU: {item.sku}) already exists in Airtable")
                except Exception:
                    print(f"[DEDUP SKIP] Existing item: SKU {item.sku} already exists in Airtable")
                already_attached += 1
                continue
            if self.shopify_cross_check and self._shopify_index and (self._shopify_index.skus or self._shopify_index.titles):
                if not self._shopify_index.contains(item.sku, item.item_name):
                    try:
                        print(f"[SHOPIFY DRAFT/INACTIVE SKIP] Item '{item.item_name}' (SKU: {item.sku}) is Enabled in Akeneo but Draft/Inactive in Shopify -> skipping to next unique item")
                    except Exception:
                        print(f"[SHOPIFY DRAFT/INACTIVE SKIP] SKU {item.sku} is Enabled in Akeneo but Draft/Inactive in Shopify -> skipping")
                    excluded_shopify += 1
                    continue
            try:
                print(f"[DEDUP PASS] New unique product selected: '{item.item_name}' (SKU: {item.sku})")
            except Exception:
                print(f"[DEDUP PASS] New unique product selected: SKU {item.sku}")
            new_items.append(item)
        if self.max_items is not None:
            new_items = new_items[: self.max_items]
        stats["excluded_not_on_shopify"] = excluded_shopify
        return new_items, stats, already_attached

    def _upload_item(self, item: ProductItem) -> bool:
        downloaded = None
        record_id = ""
        try:
            downloaded = self.akeneo.download_media(item.media_code)
            filename = attachment_filename(item.item_name, item.media_code)
            display_name = (
                item_name_with_product_type(item, category_code=self.category_code)
                if self.include_product_type_in_name
                else item.item_name.strip()
            )
            record_fields = {self.item_name_field: display_name}
            if self.sku_field:
                record_fields[self.sku_field] = item.sku
            if self.status_field:
                record_fields[self.status_field] = self.default_status

            # Pre-populate fixed prompt if table schema has it
            has_layout_field = getattr(self.airtable, "has_field", lambda _name: False)
            find_layout_field = getattr(self.airtable, "find_field_name", None)
            fixed_prompt_field = None
            for alias in ("Moodboard Converstion Fixed Prompt", "Moodboard Conversion Fixed Prompt", "Fixed Prompt"):
                if find_layout_field:
                    actual = find_layout_field(alias)
                    if actual:
                        fixed_prompt_field = actual
                        break
                elif has_layout_field(alias):
                    fixed_prompt_field = alias
                    break
            if fixed_prompt_field:
                prompt_file = Path("JSON Prompts/Moodboard V2/second_moodboard.json")
                if prompt_file.is_file():
                    try:
                        record_fields[fixed_prompt_field] = prompt_file.read_text(encoding="utf-8")
                    except Exception:
                        pass

            record_id = self.airtable.create_record(record_fields)
            self.airtable.upload_attachment(
                record_id,
                self.field_name,
                downloaded,
                filename,
            )
            cost_desc = f" (Cost: {item.cost})" if item.cost else ""
            print(f"[OK] {item.sku}{cost_desc} -> {self.field_name} ({filename})")

            # Automatically populate all layout and logo fields present in the table schema
            uploaded_fields: set[str] = set()

            for field_aliases, candidates, target_name in LAYOUT_CONFIGURATIONS:
                target_field, source_file, target_fn = resolve_layout_source(
                    field_aliases,
                    candidates,
                    target_name,
                    has_layout_field,
                    existing_records=self._cached_records,
                    find_field_fn=find_layout_field,
                )
                if target_field and target_field not in uploaded_fields and source_file:
                    try:
                        self.airtable.upload_attachment(
                            record_id,
                            target_field,
                            source_file,
                            target_fn,
                        )
                        uploaded_fields.add(target_field)
                        print(f"[OK] {item.sku} -> {target_field} ({target_fn})")
                    except Exception as layout_err:
                        print(f"[WARN] Upload layout image to {target_field} failed: {layout_err}")
                    finally:
                        if hasattr(source_file, "cleanup"):
                            source_file.cleanup()

            if record_id:
                self.created_record_ids.append(record_id)
            return True
        except Exception as error:
            print(f"[ERROR] {item.sku} -> {self.field_name} failed: {error}")
            if record_id:
                if record_id in self.created_record_ids:
                    self.created_record_ids.remove(record_id)
                try:
                    self.airtable.delete_record(record_id)
                except Exception as cleanup_error:
                    print(
                        f"[WARN] Could not remove incomplete record "
                        f"{record_id}: {cleanup_error}"
                    )
            return False
        finally:
            if downloaded:
                downloaded.cleanup()

    def backfill_missing_layouts(self, records: list[dict] | None = None) -> int:
        """Scan table records and attach missing layout files to existing records."""
        has_layout_field = getattr(self.airtable, "has_field", lambda _name: False)
        find_layout_field = getattr(self.airtable, "find_field_name", None)
        all_records = records if records is not None else self.airtable.list_records()
        if not all_records:
            return 0

        total_backfilled = 0
        for record in all_records:
            record_id = record.get("id")
            if not record_id:
                continue
            fields = record.get("fields", {})
            sku = fields.get(self.sku_field) if self.sku_field else ""
            item_label = fields.get(self.item_name_field) or sku or record_id

            for field_aliases, candidates, target_name in LAYOUT_CONFIGURATIONS:
                target_field = next((f for f in field_aliases if has_layout_field(f)), None)
                if not target_field:
                    continue
                if find_layout_field:
                    actual_fn = find_layout_field(target_field)
                    if actual_fn:
                        target_field = actual_fn
                existing_att = fields.get(target_field)
                if not existing_att:
                    _, source_file, target_fn = resolve_layout_source(
                        field_aliases,
                        candidates,
                        target_name,
                        has_layout_field,
                        existing_records=all_records,
                        find_field_fn=find_layout_field,
                    )
                    if source_file:
                        try:
                            self.airtable.upload_attachment(
                                record_id,
                                target_field,
                                source_file,
                                target_fn,
                            )
                            total_backfilled += 1
                            print(f"[OK] [BACKFILL] {item_label} -> {target_field} ({target_fn})")
                        except Exception as b_err:
                            print(f"[WARN] [BACKFILL] Failed uploading {target_field} for {item_label}: {b_err}")
                        finally:
                            if hasattr(source_file, "cleanup"):
                                source_file.cleanup()

        if total_backfilled > 0:
            print(f"[OK] Successfully backfilled {total_backfilled} layout attachment(s) on existing records")
        return total_backfilled

    def run(self, execute: bool = True) -> bool:
        """Run the Furniture Item scrape. True when every upload succeeds."""
        self.created_record_ids = []
        self.akeneo.authenticate()

        # Reconcile exact casing of table fields
        if hasattr(self.airtable, "find_field_name"):
            exact_f = self.airtable.find_field_name(self.field_name)
            if exact_f:
                self.field_name = exact_f
            exact_item = self.airtable.find_field_name(self.item_name_field)
            if exact_item:
                self.item_name_field = exact_item
            if self.sku_field:
                exact_sku = self.airtable.find_field_name(self.sku_field)
                if exact_sku:
                    self.sku_field = exact_sku
            if self.status_field:
                exact_status = self.airtable.find_field_name(self.status_field)
                if exact_status:
                    self.status_field = exact_status

        required_fields = {
            self.field_name: "multipleAttachments",
            self.item_name_field: "singleLineText",
        }
        if self.sku_field:
            required_fields[self.sku_field] = "singleLineText"
        if self.status_field:
            required_fields[self.status_field] = "singleSelect"
        if self.layout_fields:
            for lk, lv in self.layout_fields.items():
                required_fields[lk] = lv

        if execute:
            self.airtable.ensure_fields(required_fields)

        list_fields = [self.field_name, self.item_name_field]
        if self.sku_field:
            list_fields.append(self.sku_field)
        if self.status_field:
            list_fields.append(self.status_field)
        if self.layout_fields:
            list_fields.extend(self.layout_fields.keys())
        for aliases, _, _ in LAYOUT_CONFIGURATIONS:
            for alias in aliases:
                if self.airtable.has_field(alias):
                    exact_alias = (
                        self.airtable.find_field_name(alias)
                        if hasattr(self.airtable, "find_field_name")
                        else alias
                    )
                    if exact_alias and exact_alias not in list_fields:
                        list_fields.append(exact_alias)

        records = self.airtable.list_records(list_fields)
        self._cached_records = records
        existing_filenames = attachment_filenames(records, self.field_name)

        # Run layout backfill on existing records if requested
        if self.backfill_layouts and execute:
            self.backfill_missing_layouts(records)

        existing_skus: set[str] = set()
        existing_names: set[str] = set()
        if self.sku_field:
            for record in records:
                val = record.get("fields", {}).get(self.sku_field)
                if val:
                    existing_skus.add(str(val).strip())
        for record in records:
            name_val = record.get("fields", {}).get(self.item_name_field)
            if name_val:
                n_str = str(name_val).strip()
                existing_names.add(identity_key(n_str))
                if " | " in n_str:
                    base_part = n_str.split(" | ")[0].strip()
                    if base_part:
                        existing_names.add(identity_key(base_part))

        if self.cross_table_dedup and getattr(self.airtable, "base_id", None):
            try:
                base_skus, base_names, base_filenames = fetch_all_base_existing_identities(self.airtable)
                existing_skus.update(base_skus)
                existing_names.update(base_names)
                existing_filenames.update(base_filenames)
                print(
                    f"[INFO] Cross-table deduplication active: Found {len(base_skus)} existing SKU(s), "
                    f"{len(base_names)} item name(s), and {len(base_filenames)} attachment filename(s) across all base tables."
                )
            except Exception as dedup_err:
                print(f"[WARN] Cross-table deduplication scan note: {dedup_err}")

        print(
            f"[OK] Found {len(existing_filenames)} total existing attachment filenames, "
            f"{len(existing_names)} item names, and {len(existing_skus)} existing SKUs to prevent duplicates"
        )

        if self.shopify_cross_check:
            try:
                shopify = ShopifyClient()
                self._shopify_index = shopify.load_published_identities()
            except Exception as s_err:
                print(f"[WARN] Shopify cross-check initialization note: {s_err}")

        products = self._fetch_candidates()
        items, stats, already_attached = self._new_items(
            products,
            existing_filenames,
            existing_skus,
            existing_names=existing_names,
        )
        shopify_note = (
            f"{stats.get('excluded_not_on_shopify', 0)} not published on Shopify, "
            if self.shopify_cross_check
            else ""
        )
        print(
            f"[INFO] Akeneo returned {len(products)} products: "
            f"{len(items)} new images selected, "
            f"{already_attached} already attached, "
            f"{shopify_note}"
            f"{stats['excluded_category']} excluded by category filter, "
            f"{stats['ineligible']} missing name/image/disabled, "
            f"{stats['duplicate_sku']} duplicate SKUs, "
            f"{stats['duplicate_photo']} duplicate photos, "
            f"{stats['duplicate_name']} duplicate item names"
        )

        if not items:
            print(
                f"[OK] No new {self.style_code.title()} "
                f"{categories.category_label(self.category_code).title()} "
                "images to upload"
            )
            return True

        if not execute:
            print(f"\n[DRY RUN] Would upload {len(items)} product image(s) to {self.field_name}:")
            for it in items:
                print(f"  - SKU: {it.sku} | Name: {it.item_name}")
            return True

        failures = sum(not self._upload_item(item) for item in items)
        if failures:
            print(f"[WARN] Run completed with {failures} failed image upload(s)")
            return False

        print(
            f"[OK] Uploaded {len(items)} product image(s) to {self.field_name} "
            f"with names in {self.item_name_field}"
        )
        return True
