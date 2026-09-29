"""Ad Cover AI Generation Pipeline (1:1 1080x1080 + 9:16 1080x1920 Story).

Runs the complete 7-phase pipeline for the Ad Covers Studio tab on Airtable:
1. Akeneo scrape (highest-priced modern chandelier of the newest 50 candidates,
   strictly cross-verified against live Shopify) -> brand-new Airtable row,
   Status -> 'Standby'
2. Krea AI interior photo generation (1:1) -> 'Ad Cover Interior',
   Status -> 'Ad Cover Interior Generated'
3. Claude Sonnet 5 blending prompt via Fal AI -> 'Prompt',
   Status -> 'Blending Prompt Generated'
4. Fal AI Nano Banana Pro blend (1:1) -> 'Ad Cover Blended Image',
   Status -> 'Ad Cover Blended Image Generated'
5. Local Python Pillow composite of the fixture's transparent ad-cover overlay
   -> 'Ad Cover Converted Image',
   Status -> 'Ad Cover Converted Image Generated'
6. Fal AI Nano Banana Pro re-extension of the 1:1 blend to 9:16 ->
   'Ad Cover Blended Image Story', Status -> 'Ad Cover Blended Image Story Generated'
7. Local Python Pillow composite of the 9:16 story overlay ->
   'Ad Cover Converted Image Story', Status -> 'Complete' (+ PHT timestamp)

Phases 5 and 7 make zero API calls: the collection banner and HomeCartel mark
already live in 1:1 collection overlays (e.g. ``assets/chand-collection.png``,
``assets/trending.png``, etc.) and ``assets/ad-cover-<fixture>-story.png``.
Phase 7 is the only terminal phase; a failing story branch leaves the finished
1:1 ad cover 'Complete' rather than parking the row on an unbadged status.

Usage::

    python generate_ad_cover_pipeline.py --fixture chandelier --mode all
    python generate_ad_cover_pipeline.py --fixture chandelier --mode scrape
    python generate_ad_cover_pipeline.py --fixture chandelier --mode story-blend --record-id recXXXX
    python generate_ad_cover_pipeline.py --fixture chandelier --mode story-conversion --record-id recXXXX
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import requests

from content_automation.airtable_client import current_pht_timestamp
from content_automation.config import TABLES, load_settings
from content_automation.fal_client import FalClient
from content_automation.fields import price_field
from content_automation.krea_client import KreaClient
from content_automation.media import download_url_to_temp_file
from content_automation.overlay import (
    AD_COVER_FIXTURE_ASSETS,
    AD_COVER_STORY_ASSETS,
    AD_COVER_STORY_CANVAS_SIZE,
    overlay_ad_cover_layout,
)
from content_automation.prompts import build_vision_blending_instruction
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ProductItem,
    ScrapeAirtableClient,
    identity_key,
    load_scrape_settings,
    normalize_sku,
)
from content_automation.scraping.categories import moodboard_id_for_category
from content_automation.scraping.products import _newest_first

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DEFAULT_FIXTURE = "chandelier"

AD_COVER_FIXTURES: dict[str, dict[str, Any]] = {
    "chandelier": {
        "label": "Ad Cover Chandelier",
        "category_code": "chandelier_ad_cover",
        "fixture_code": "CH",
        "moodboard_env": "KREA_MOODBOARD_ID_CHANDELIER_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_CHANDELIER",
        "default_moodboard_id": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        "default_prompt": "Generate me a modern living room",
        "asset": AD_COVER_FIXTURE_ASSETS["chandelier"],
        "story_asset": AD_COVER_STORY_ASSETS.get("chandelier", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "floor-lamp": {
        "label": "Ad Cover Trending Lights",
        "category_code": "floor_lamp_ad_cover",
        "fixture_code": "FL",
        "moodboard_env": "KREA_MOODBOARD_ID_FLOOR_LAMP_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_FLOOR_LAMP",
        "default_moodboard_id": "c4c15a18-a92d-4465-924f-c85cfe1958bc",
        "default_prompt": "Generate me a modern living room with a standing floor lamp beside a sofa or lounge chair",
        "asset": AD_COVER_FIXTURE_ASSETS["floor-lamp"],
        "story_asset": AD_COVER_STORY_ASSETS.get("floor-lamp", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "table-lamp": {
        "label": "Ad Cover Table Lamp",
        "category_code": "table_lamp_ad_cover",
        "fixture_code": "TL",
        "moodboard_env": "KREA_MOODBOARD_ID_TABLE_LAMP_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_TABLE_LAMP",
        "default_moodboard_id": "fb2487fb-2895-4d2c-9758-805aaf1bac69",
        "default_prompt": "Generate me a modern luxury bedroom bedside table or console with a table lamp",
        "asset": AD_COVER_FIXTURE_ASSETS["table-lamp"],
        "story_asset": AD_COVER_STORY_ASSETS.get("table-lamp", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "cluster-chandelier": {
        "label": "Ad Cover Cluster Chandelier",
        "category_code": "cluster_chandelier_ad_cover",
        "fixture_code": "CL",
        "moodboard_env": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_CLUSTER_CHANDELIER",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "default_prompt": "Generate me a luxury modern room with high ceiling featuring a cluster chandelier",
        "asset": AD_COVER_FIXTURE_ASSETS["cluster-chandelier"],
        "story_asset": AD_COVER_STORY_ASSETS.get("cluster-chandelier", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "pendant": {
        "label": "Ad Cover Pendant Light",
        "category_code": "pendant_ad_cover",
        "fixture_code": "PE",
        "moodboard_env": "KREA_MOODBOARD_ID_PENDANT_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_PENDANT",
        "default_moodboard_id": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
        "default_prompt": "Generate me a modern luxury dining room with hanging pendant light",
        "asset": AD_COVER_FIXTURE_ASSETS["pendant"],
        "story_asset": AD_COVER_STORY_ASSETS.get("pendant", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "wall-light": {
        "label": "Ad Cover Wall Light",
        "category_code": "wall_light_ad_cover",
        "fixture_code": "WL",
        "moodboard_env": "KREA_MOODBOARD_ID_WALL_LIGHT_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_WALL_LIGHT",
        "default_moodboard_id": "20c3beaf-0995-44bf-a7a3-ac790fe8f315",
        "default_prompt": "Generate me a modern luxury living room with wall sconce mounted on the wall",
        "asset": AD_COVER_FIXTURE_ASSETS["wall-light"],
        "story_asset": AD_COVER_STORY_ASSETS.get("wall-light", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "new-collection": {
        "label": "Ad Cover New Collection",
        "category_code": "new_collection_ad_cover",
        "fixture_code": "NEW",
        "moodboard_env": "KREA_MOODBOARD_ID_NEW_COLLECTION_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_NEW_COLLECTION",
        "default_moodboard_id": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        "default_prompt": "Generate me a modern luxury living room",
        "asset": AD_COVER_FIXTURE_ASSETS["new-collection"],
        "story_asset": AD_COVER_STORY_ASSETS.get("new-collection", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "on-sale": {
        "label": "Ad Cover On Sale Designs",
        "category_code": "on_sale_ad_cover",
        "fixture_code": "SALE",
        "moodboard_env": "KREA_MOODBOARD_ID_ON_SALE_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_ON_SALE",
        "default_moodboard_id": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        "default_prompt": "Generate me a modern luxury living room with chandelier",
        "asset": AD_COVER_FIXTURE_ASSETS["on-sale"],
        "story_asset": AD_COVER_STORY_ASSETS.get("on-sale", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
    "on-stock": {
        "label": "Ad Cover On Stock Designs",
        "category_code": "on_stock_ad_cover",
        "fixture_code": "STOCK",
        "moodboard_env": "KREA_MOODBOARD_ID_ON_STOCK_AD_COVER",
        "prompt_env": "AD_COVER_PROMPT_ON_STOCK",
        "default_moodboard_id": "de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        "default_prompt": "Generate me a modern interior with ambient lighting",
        "asset": AD_COVER_FIXTURE_ASSETS["on-stock"],
        "story_asset": AD_COVER_STORY_ASSETS.get("on-stock", ""),
        "story_canvas_size": AD_COVER_STORY_CANVAS_SIZE,
    },
}

# ---------------------------------------------------------------------------
# Fields & statuses
# ---------------------------------------------------------------------------

FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"
STATUS_FIELD = "Status"
PRICE_FIELD = price_field(0)
MOODBOARD_FIELD = "Moodboard ID"
PROMPT_FIELD = "Prompt"
INTERIOR_FIELD = "Ad Cover Interior"
BLENDED_FIELD = "Ad Cover Blended Image"
CONVERTED_FIELD = "Ad Cover Converted Image"
BLENDED_STORY_FIELD = "Ad Cover Blended Image Story"
CONVERTED_STORY_FIELD = "Ad Cover Converted Image Story"

STATUS_STANDBY = "Standby"
STATUS_INTERIOR_GENERATED = "Ad Cover Interior Generated"
STATUS_PROMPT_GENERATED = "Blending Prompt Generated"
STATUS_BLENDED_GENERATED = "Ad Cover Blended Image Generated"
STATUS_CONVERTED_GENERATED = "Ad Cover Converted Image Generated"
STATUS_BLENDED_STORY_GENERATED = "Ad Cover Blended Image Story Generated"
STATUS_CONVERTED_STORY_GENERATED = "Ad Cover Converted Image Story Generated"
STATUS_COMPLETE = "Complete"

AD_COVER_FIELDS: dict[str, str] = {
    "Foreign Key ID": "singleLineText",
    "Date and Time Generated": "dateTime",
    MOODBOARD_FIELD: "singleLineText",
    PROMPT_FIELD: "multilineText",
    PRICE_FIELD: "number",
    INTERIOR_FIELD: "multipleAttachments",
    BLENDED_FIELD: "multipleAttachments",
    CONVERTED_FIELD: "multipleAttachments",
    BLENDED_STORY_FIELD: "multipleAttachments",
    CONVERTED_STORY_FIELD: "multipleAttachments",
}

# Strict Shopify check + base-wide cross-table dedup are on by default. Price
# ranking takes the highest-priced item out of the newest `PRICE_POOL_SIZE`
# candidates rather than the global maximum, so the pick stays "fresh".
SORT_BY_PRICE = True
PRICE_POOL_SIZE = 50

ASPECT_RATIO = "1:1"
STORY_ASPECT_RATIO = "9:16"
STORY_RESOLUTION = "1K"
TOTAL_PHASES = 7
OUTPUT_DIR = Path("output/ad_cover")

FAL_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5"
FAL_BLENDING_MODEL = os.getenv("FAL_BLENDING_MODEL", "").strip() or "fal-ai/nano-banana-pro/edit"
FAL_STORY_MODEL = os.getenv("FAL_STORY_MODEL", "").strip() or FAL_BLENDING_MODEL

# Phase 6 is a frame-extension job, not a second blend: it must keep the room the
# Phase 4 output already produced and only grow it vertically. Reusing the Phase 3
# 'Prompt' text here would let the model redesign the space instead.
FAL_STORY_CONVERSION_PROMPT = (
    os.getenv("AD_COVER_STORY_CONVERSION_PROMPT", "").strip()
    or (
        "Convert the supplied 1:1 photograph into a vertical 9:16 version of the "
        "EXACT SAME room. This is an outpainting / frame-extension task, not a "
        "redesign: keep the original framing pixel-accurate in the centre and "
        "seamlessly continue the architecture above and below it.\n"
        "STRICT RULES:\n"
        "1. The lighting fixture must remain IDENTICAL: same model, silhouette, arm "
        "count, metal finish, glass/crystal/stone material, canopy, cord length, "
        "illuminated state, colour temperature and glow. Do not restyle, resize, "
        "reposition, duplicate or replace it. Keep it on the same vertical axis "
        "(horizontally centred) in the upper third of the new frame.\n"
        "2. Preserve exactly: camera angle, lens and perspective, wall and floor "
        "colours, all furniture, textiles, art, decor, daylight direction, "
        "artificial light pools, exposure, white balance, grain and photorealistic "
        "8K interior-photography render style.\n"
        "3. Extend the ceiling, cornice and upper wall upward so the fixture keeps "
        "its natural suspension height, and extend the floor and lower furniture "
        "downward, so the composition fills a full 9:16 frame. Fill every new area "
        "by continuing the existing materials, lighting and geometry plausibly.\n"
        "4. Add no new objects, no people, no animals, no text, no typography, no "
        "logos, no watermarks, no borders, no second light source. No visible "
        "seams, no stretched or smeared regions. The result must be one seamless, "
        "uninterrupted 9:16 luxury interior photograph, sharp edge to edge."
    )
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def get_first_field_value(fields: dict[str, Any], field_names: list[str]) -> Any:
    for name in field_names:
        if name in fields:
            return fields.get(name)
    return None


def extract_attachment_url(attachments: Any) -> str:
    if not attachments:
        return ""
    if isinstance(attachments, str):
        return attachments.strip()
    if isinstance(attachments, list):
        for entry in attachments:
            if isinstance(entry, dict) and entry.get("url"):
                return str(entry["url"]).strip()
    if isinstance(attachments, dict) and attachments.get("url"):
        return str(attachments["url"]).strip()
    return ""


def safe_update_status(airtable: ScrapeAirtableClient, record_id: str, status_value: str) -> None:
    """Set Status, stamping the PHT timestamp when the row reaches Complete."""
    payload: dict[str, Any] = {STATUS_FIELD: status_value}
    if status_value == STATUS_COMPLETE:
        try:
            payload["Date and Time Generated"] = current_pht_timestamp()
        except Exception:
            pass
    try:
        airtable.update_records([(record_id, payload)])
    except Exception:
        try:
            airtable.update_records([(record_id, {STATUS_FIELD: status_value})])
        except Exception:
            pass


def ensure_ad_cover_fields(airtable: ScrapeAirtableClient) -> None:
    """Create any missing Ad Cover column before a phase reads or writes it."""
    airtable.ensure_fields(AD_COVER_FIELDS)
    airtable.ensure_product_fields(items_per_row=1)
    airtable.ensure_single_select_options(
        STATUS_FIELD,
        (
            STATUS_STANDBY,
            STATUS_INTERIOR_GENERATED,
            STATUS_PROMPT_GENERATED,
            STATUS_BLENDED_GENERATED,
            STATUS_CONVERTED_GENERATED,
            STATUS_BLENDED_STORY_GENERATED,
            STATUS_CONVERTED_STORY_GENERATED,
            STATUS_COMPLETE,
        ),
    )


def resolve_fixture_config(fixture: str) -> dict[str, Any]:
    if fixture not in AD_COVER_FIXTURES:
        raise SystemExit(
            f"Unknown fixture {fixture!r}. Known fixtures: {sorted(AD_COVER_FIXTURES)}"
        )
    cfg = dict(AD_COVER_FIXTURES[fixture])
    if fixture == "floor-lamp":
        from content_automation.overlay import _resolve_asset_file
        if _resolve_asset_file("floor-lamp-collection.png") is not None:
            cfg["asset"] = "floor-lamp-collection.png"
        else:
            cfg["asset"] = AD_COVER_FIXTURE_ASSETS.get("floor-lamp", "trending.png")
    else:
        cfg["asset"] = AD_COVER_FIXTURE_ASSETS.get(fixture, cfg.get("asset", ""))
    return cfg


def resolve_table_id(fixture: str, override: str | None = None) -> str:
    cfg = resolve_fixture_config(fixture)
    table = TABLES.get(cfg["category_code"])
    table_id = (override or "").strip() or (table.table_id if table else "")
    if not table_id:
        raise SystemExit(f"No Airtable table id configured for fixture {fixture!r}")
    return table_id


def resolve_moodboard_id(fixture: str, override: str | None = None) -> str:
    cfg = resolve_fixture_config(fixture)
    env_value = (os.getenv(cfg["moodboard_env"], "") or "").strip()
    return (
        (override or "").strip()
        or env_value
        or moodboard_id_for_category(cfg["category_code"], cfg["default_moodboard_id"])
        or cfg["default_moodboard_id"]
    )


def resolve_prompt(fixture: str, override: str | None = None) -> str:
    cfg = resolve_fixture_config(fixture)
    env_value = (os.getenv(cfg["prompt_env"], "") or "").strip()
    return (override or "").strip() or env_value or cfg["default_prompt"]


def newest_record(airtable: ScrapeAirtableClient, fields: list[str]) -> dict[str, Any] | None:
    """The single highest-ID row, or None. Never loops a backlog."""
    records = airtable.list_records(fields)
    if not records:
        return None

    def sort_key(record: dict[str, Any]) -> tuple[int, Any]:
        value = record.get("fields", {}).get("ID")
        try:
            return (0, int(value))
        except (TypeError, ValueError):
            return (1, record.get("createdTime", ""))

    return sorted(records, key=sort_key)[-1]


# ---------------------------------------------------------------------------
# Phase 1 -- scrape
# ---------------------------------------------------------------------------


class AdCoverScrapeRunner(FurnitureItemScrapeRunner):
    """Selects the highest-priced product inside the newest-50 candidate pool.

    ``select_new_products`` applies a cyclic-alphabet re-sort *after* its price
    ranking, so by the time ``max_items`` trims the list the price order is
    already gone. This override asks the shared selector for the full deduped
    candidate set (stable alphabetical order), rebuilds the newest-50 pool in
    the selector's own newest-first order, and keeps the priciest entry.

    It also records the chosen ``ProductItem`` so the Ad Cover row can store its
    price in 'Item Price' -- the base runner only exposes record ids.
    """

    def __init__(self, *args: Any, fixture: str = "chandelier", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fixture = fixture
        self.selected_items: list[ProductItem] = []
        self.uploaded_items: list[ProductItem] = []
        self.pool_size = 0
        self.pool_priced = 0
        self.csv_rates: dict[str, float] = {}

    def _fetch_candidates(self) -> list[dict]:
        if self.fixture in ("new-collection", "on-sale", "on-stock"):
            return self._fetch_csv_products()
        return super()._fetch_candidates()

    def _fetch_csv_products(self) -> list[dict]:
        import csv
        import glob
        import random
        exports_dir = Path(r"C:\Users\User\Desktop\Auto Export Inventory\exports")
        if self.fixture == "on-sale":
            # 15% off chandelier
            matches = glob.glob(str(exports_dir / "*Long_Duration_Sale*Chandelier*.csv"))
            if not matches:
                matches = glob.glob(str(exports_dir / "*Long_Duration_Sale*ALL*.csv"))
            target_cat = "Chandelier"
        elif self.fixture == "on-stock":
            # 10% off any item
            matches = glob.glob(str(exports_dir / "*10__Off*.csv"))
            target_cat = None
        else:  # new-collection
            # 15% off any lighting fixture
            matches = glob.glob(str(exports_dir / "*Long_Duration_Sale*ALL*.csv"))
            target_cat = None

        if not matches:
            print(f"[WARN] No CSV export files found for {self.fixture} in {exports_dir}")
            return super()._fetch_products()

        latest_csv = max(matches, key=os.path.getmtime)
        print(f"[INFO] [{self.fixture.upper()}] Reading candidate items from latest CSV: {Path(latest_csv).name}")

        with open(latest_csv, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        candidate_skus: list[str] = []
        for r in rows:
            if target_cat and r.get("Category", "").strip().lower() != target_cat.lower():
                continue
            sku = r.get("SKU", "").strip()
            if sku:
                candidate_skus.append(sku)
                try:
                    self.csv_rates[normalize_sku(sku)] = float(r.get("Selling Rate", 0) or 0)
                except Exception:
                    pass

        if not candidate_skus:
            print(f"[WARN] No matching SKUs found in {latest_csv}")
            return super()._fetch_products()

        # Shuffle candidates so every execution selects a fresh candidate
        random.shuffle(candidate_skus)
        pool_skus = candidate_skus[:100]

        products: list[dict] = []
        chunk_size = 50
        for i in range(0, len(pool_skus), chunk_size):
            chunk = pool_skus[i : i + chunk_size]
            try:
                found = self.akeneo.fetch_products({"identifier": [{"operator": "IN", "value": chunk}]})
                products.extend(found)
            except Exception as err:
                print(f"[WARN] Akeneo fetch error: {err}")

        print(f"[INFO] Fetched {len(products)} products from Akeneo for {len(pool_skus)} candidate CSV SKUs.")
        return products

    def _new_items(
        self,
        products: list[dict],
        existing_filenames: set[str],
        existing_skus: set[str] | None = None,
        existing_names: set[str] | None = None,
    ) -> tuple[list[ProductItem], dict[str, int], int]:
        saved = (self.max_items, self.sort_by_price, self.starting_letter)
        self.max_items = None
        self.sort_by_price = False
        self.starting_letter = "A"
        try:
            items, stats, already_attached = super()._new_items(
                products, existing_filenames, existing_skus, existing_names
            )
        finally:
            self.max_items, self.sort_by_price, self.starting_letter = saved

        if self.fixture in ("new-collection", "on-stock"):
            # For random items that passed dedup & Shopify check
            chosen = items[0] if items else None
        else:
            chosen = self._highest_price_in_newest_pool(products, items)

        self.selected_items = [chosen] if chosen else []
        return self.selected_items, stats, already_attached

    def _highest_price_in_newest_pool(
        self, products: list[dict], candidates: list[ProductItem]
    ) -> ProductItem | None:
        if not candidates:
            return None

        remaining = {identity_key(item.sku): item for item in candidates}
        pool: list[ProductItem] = []
        for product in _newest_first(products):
            key = identity_key(normalize_sku(product.get("identifier")))
            item = remaining.pop(key, None)
            if item is None:
                continue
            pool.append(item)
            if len(pool) >= PRICE_POOL_SIZE:
                break

        self.pool_size = len(pool)
        priced = [item for item in pool if item.cost_value > 0]
        self.pool_priced = len(priced)
        if priced:
            chosen = max(priced, key=lambda item: item.cost_value)
            print(
                f"[INFO] Highest-priced pick from the newest {len(pool)} candidates "
                f"({len(priced)} priced): '{chosen.item_name}' (SKU {chosen.sku}, "
                f"{chosen.cost or chosen.cost_value})"
            )
            return chosen

        print(
            f"[WARN] None of the newest {len(pool)} candidates carries a Costing value; "
            "falling back to the newest candidate."
        )
        return pool[0] if pool else None

    def _upload_item(self, item: ProductItem) -> bool:
        uploaded = super()._upload_item(item)
        if uploaded:
            self.uploaded_items.append(item)
        return uploaded


def phase_scrape(
    airtable: ScrapeAirtableClient,
    *,
    fixture: str,
    table_id: str,
    style_code: str,
) -> str | None:
    """Scrape exactly one brand-new, highest-priced row. Returns its record id."""
    cfg = resolve_fixture_config(fixture)
    scrape_settings = load_scrape_settings(
        category_code=cfg["category_code"],
        style_code=style_code,
        table_id_override=table_id,
    )

    print(
        f"[INFO] [Phase 1/{TOTAL_PHASES}] Scraping the highest-priced {style_code} {cfg.get('label', fixture)} "
        f"from the newest {PRICE_POOL_SIZE} Akeneo candidates..."
    )

    existing_ids = {record["id"] for record in airtable.list_records([STATUS_FIELD])}

    runner = AdCoverScrapeRunner(
        akeneo=_build_akeneo_client(scrape_settings),
        airtable=airtable,
        fixture=fixture,
        category_code=scrape_settings.category_code,
        style_code=scrape_settings.style_code,
        field_name=FIELD_NAME,
        item_name_field=ITEM_NAME_FIELD,
        sku_field=SKU_FIELD,
        status_field=STATUS_FIELD,
        default_status=STATUS_STANDBY,
        max_items=1,
        cross_table_dedup=True,
        sort_by_price=SORT_BY_PRICE,
        price_pool_size=PRICE_POOL_SIZE,
        backfill_layouts=False,
        shopify_cross_check=True,
    )

    runner.run(execute=True)

    new_ids = [rid for rid in runner.created_record_ids if rid not in existing_ids]
    if not new_ids:
        print("[WARN] No brand-new product row was created (dedup/Shopify filtered everything).")
        return None

    record_id = new_ids[0]
    rec_data = airtable.get_record(record_id) or {}
    row_id = rec_data.get("fields", {}).get("ID", "")
    fk_prefix = f"ADC-ADS-{cfg.get('fixture_code', 'CH')}"
    fields: dict[str, Any] = {
        "Foreign Key ID": f"{fk_prefix}-{row_id}" if row_id else fk_prefix,
        MOODBOARD_FIELD: resolve_moodboard_id(fixture),
        PROMPT_FIELD: resolve_prompt(fixture),
    }
    if runner.selected_items:
        item = runner.selected_items[0]
        price_val = item.cost_value
        if price_val <= 0:
            price_val = runner.csv_rates.get(normalize_sku(item.sku), 0.0)
        fields[PRICE_FIELD] = price_val
        print(
            f"[INFO] Selected '{item.item_name}' (SKU {item.sku}) | "
            f"price {price_val} from '{item.cost or 'no Costing value'}' | "
            f"pool {runner.pool_priced}/{runner.pool_size} priced"
        )
    airtable.update_records([(record_id, fields)])
    safe_update_status(airtable, record_id, STATUS_STANDBY)
    print(f"[OK] Brand-new Ad Cover row {record_id} created with Status '{STATUS_STANDBY}'.")
    return record_id


def _build_akeneo_client(scrape_settings: Any) -> Any:
    from content_automation.akeneo_client import AkeneoClient

    return AkeneoClient(
        scrape_settings.akeneo_host,
        scrape_settings.akeneo_client_id,
        scrape_settings.akeneo_secret,
        scrape_settings.akeneo_username,
        scrape_settings.akeneo_password,
        channel_name=scrape_settings.channel_name,
    )


# ---------------------------------------------------------------------------
# Phase 2 -- Krea 1:1 interior
# ---------------------------------------------------------------------------


def phase_interior(
    krea: KreaClient,
    airtable: ScrapeAirtableClient,
    *,
    record_id: str,
    moodboard_id: str,
    prompt: str,
) -> bool:
    print(
        f"[INFO] [Phase 2/{TOTAL_PHASES}] Generating a {ASPECT_RATIO} interior with Krea AI "
        f"(moodboard {moodboard_id})..."
    )
    print(f'[INFO] [Phase 2/{TOTAL_PHASES}] Krea prompt: "{prompt}"')

    downloaded = None
    try:
        image_url = krea.generate(prompt, aspect_ratio=ASPECT_RATIO, moodboard_id=moodboard_id)
        downloaded = krea.download_image(image_url)
        airtable.upload_attachment(
            record_id,
            INTERIOR_FIELD,
            downloaded,
            f"ad_cover_interior_{record_id}.jpg",
        )
        safe_update_status(airtable, record_id, STATUS_INTERIOR_GENERATED)
        print(f"[OK] Attached Krea interior to '{INTERIOR_FIELD}' on {record_id}.")
        return True
    except Exception as error:
        print(f"[ERROR] Krea interior generation failed for {record_id}: {error}")
        return False
    finally:
        if downloaded:
            downloaded.cleanup()


# ---------------------------------------------------------------------------
# Phase 3 -- Claude blending prompt
# ---------------------------------------------------------------------------


def phase_prompt(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    record_id: str,
) -> bool:
    record = airtable.get_record(record_id)
    fields = record.get("fields", {}) if record else {}
    item_name = str(
        get_first_field_value(fields, [ITEM_NAME_FIELD, SKU_FIELD]) or "Lighting Fixture"
    ).strip()

    interior_url = extract_attachment_url(fields.get(INTERIOR_FIELD))
    furniture_url = extract_attachment_url(fields.get(FIELD_NAME))
    image_urls = [url for url in (interior_url, furniture_url) if url]
    if not image_urls:
        print(f"[ERROR] {record_id} has no accessible source images for the prompt phase.")
        return False

    print(f"[INFO] [Phase 3/{TOTAL_PHASES}] Analyzing photos with Claude Sonnet 5 ({FAL_VISION_MODEL})...")
    try:
        generated = fal.generate_vision_prompt(
            image_urls=image_urls,
            prompt=build_vision_blending_instruction(
                interior_label=f"Room Interior ('{INTERIOR_FIELD}')",
                item_name=item_name,
                aspect_ratio=ASPECT_RATIO,
            ),
            model=FAL_VISION_MODEL,
        )
        airtable.update_records([(record_id, {PROMPT_FIELD: generated.strip()})])
        safe_update_status(airtable, record_id, STATUS_PROMPT_GENERATED)
        print(f"[OK] Wrote a {len(generated.strip())}-char blending prompt to '{PROMPT_FIELD}'.")
        return True
    except Exception as error:
        print(f"[ERROR] Claude blending prompt failed for {record_id}: {error}")
        return False


# ---------------------------------------------------------------------------
# Phase 4 -- Nano Banana Pro blend
# ---------------------------------------------------------------------------


def phase_blend(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    record_id: str,
) -> bool:
    record = airtable.get_record(record_id)
    fields = record.get("fields", {}) if record else {}

    prompt_str = str(fields.get(PROMPT_FIELD) or "").strip()
    if not prompt_str:
        print(f"[ERROR] {record_id} has no '{PROMPT_FIELD}' to blend with.")
        return False

    interior_url = extract_attachment_url(fields.get(INTERIOR_FIELD))
    furniture_url = extract_attachment_url(fields.get(FIELD_NAME))
    image_urls = [url for url in (interior_url, furniture_url) if url]
    if not image_urls:
        print(f"[ERROR] {record_id} has no accessible source images for the blend phase.")
        return False

    print(f"[INFO] [Phase 4/{TOTAL_PHASES}] Blending with Fal AI Nano Banana Pro ({FAL_BLENDING_MODEL})...")
    downloaded = None
    try:
        image_url = fal.generate(
            prompt=prompt_str,
            image_urls=image_urls,
            aspect_ratio=ASPECT_RATIO,
            resolution="1K",
            model=FAL_BLENDING_MODEL,
        )
        downloaded = download_url_to_temp_file(
            requests.Session(),
            image_url,
            prefix="ad_cover_blend_",
            suffix=".jpg",
            context=f"Download Ad Cover blended image from {image_url}",
        )
        airtable.upload_attachment(
            record_id,
            BLENDED_FIELD,
            downloaded,
            f"ad_cover_blended_{record_id}.jpg",
        )
        safe_update_status(airtable, record_id, STATUS_BLENDED_GENERATED)
        print(f"[OK] Attached blended image to '{BLENDED_FIELD}' on {record_id}.")
        return True
    except Exception as error:
        print(f"[ERROR] Nano Banana Pro blending failed for {record_id}: {error}")
        return False
    finally:
        if downloaded:
            downloaded.cleanup()


# ---------------------------------------------------------------------------
# Phase 5 -- local Pillow composite (zero API cost)
# ---------------------------------------------------------------------------


def phase_conversion(
    airtable: ScrapeAirtableClient,
    *,
    fixture: str,
    record_id: str,
) -> bool:
    cfg = resolve_fixture_config(fixture)
    record = airtable.get_record(record_id)
    fields = record.get("fields", {}) if record else {}

    blended_url = extract_attachment_url(fields.get(BLENDED_FIELD))
    if not blended_url:
        print(f"[ERROR] {record_id} has no '{BLENDED_FIELD}' to composite over.")
        return False

    print(
        f"[INFO] [Phase 5/{TOTAL_PHASES}] Compositing '{cfg['asset']}' locally with Python Pillow "
        f"(no API call)..."
    )
    blended_file = None
    try:
        blended_file = download_url_to_temp_file(
            requests.Session(),
            blended_url,
            prefix="ad_cover_src_",
            suffix=".jpg",
            context=f"Download Ad Cover blended image for local composite ({record_id})",
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUTPUT_DIR / f"ad_cover_converted_{record_id}.jpg"
        overlay_ad_cover_layout(blended_file.path, fixture, dest)

        airtable.upload_attachment(
            record_id,
            CONVERTED_FIELD,
            dest,
            f"ad_cover_converted_{record_id}.jpg",
        )
        # 'Complete' belongs to Phase 7, the last phase. Status is a singleSelect,
        # so stamping it here would be overwritten by Phase 6 and lost for good if
        # the story branch then failed.
        safe_update_status(airtable, record_id, STATUS_CONVERTED_GENERATED)
        print(f"[OK] Attached final 1:1 ad cover to '{CONVERTED_FIELD}' on {record_id}.")
        return True
    except Exception as error:
        print(f"[ERROR] Local Ad Cover composite failed for {record_id}: {error}")
        return False
    finally:
        if blended_file:
            blended_file.cleanup()


# ---------------------------------------------------------------------------
# Phase 6 -- Nano Banana Pro 9:16 extension of the 1:1 blend
# ---------------------------------------------------------------------------


def phase_story_blend(
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    *,
    fixture: str,
    record_id: str,
) -> bool:
    cfg = resolve_fixture_config(fixture)
    if not cfg.get("story_asset"):
        print(
            f"[WARN] [Phase 6/{TOTAL_PHASES}] Fixture {fixture!r} has no 9:16 story overlay "
            "registered; skipping the story branch."
        )
        return True

    record = airtable.get_record(record_id)
    fields = record.get("fields", {}) if record else {}
    blended_url = extract_attachment_url(fields.get(BLENDED_FIELD))
    if not blended_url:
        print(
            f"[ERROR] {record_id} has no '{BLENDED_FIELD}' to extend to "
            f"{STORY_ASPECT_RATIO}."
        )
        return False

    print(
        f"[INFO] [Phase 6/{TOTAL_PHASES}] Extending the 1:1 blend to "
        f"{STORY_ASPECT_RATIO} with Fal AI Nano Banana Pro ({FAL_STORY_MODEL})..."
    )
    downloaded = None
    try:
        image_url = fal.generate(
            prompt=FAL_STORY_CONVERSION_PROMPT,
            image_urls=[blended_url],
            aspect_ratio=STORY_ASPECT_RATIO,
            resolution=STORY_RESOLUTION,
            model=FAL_STORY_MODEL,
        )
        downloaded = download_url_to_temp_file(
            requests.Session(),
            image_url,
            prefix="ad_cover_story_blend_",
            suffix=".jpg",
            context=f"Download Ad Cover 9:16 story blend from {image_url}",
        )
        airtable.upload_attachment(
            record_id,
            BLENDED_STORY_FIELD,
            downloaded,
            f"ad_cover_blended_story_{record_id}.jpg",
        )
        safe_update_status(airtable, record_id, STATUS_BLENDED_STORY_GENERATED)
        print(f"[OK] Attached 9:16 story blend to '{BLENDED_STORY_FIELD}' on {record_id}.")
        return True
    except Exception as error:
        print(f"[ERROR] Nano Banana Pro 9:16 story extension failed for {record_id}: {error}")
        return False
    finally:
        if downloaded:
            downloaded.cleanup()


# ---------------------------------------------------------------------------
# Phase 7 -- local Pillow 9:16 story composite (zero API cost, terminal)
# ---------------------------------------------------------------------------


def phase_story_conversion(
    airtable: ScrapeAirtableClient,
    *,
    fixture: str,
    record_id: str,
) -> bool:
    cfg = resolve_fixture_config(fixture)
    if not cfg.get("story_asset"):
        print(
            f"[WARN] [Phase 7/{TOTAL_PHASES}] Fixture {fixture!r} has no 9:16 story overlay "
            "registered; skipping the story composite."
        )
        return True

    record = airtable.get_record(record_id)
    fields = record.get("fields", {}) if record else {}
    story_url = extract_attachment_url(fields.get(BLENDED_STORY_FIELD))
    if not story_url:
        print(
            f"[ERROR] {record_id} has no '{BLENDED_STORY_FIELD}' to composite over. "
            "Run --mode story-blend first."
        )
        return False

    print(
        f"[INFO] [Phase 7/{TOTAL_PHASES}] Compositing '{cfg['story_asset']}' over the "
        f"{STORY_ASPECT_RATIO} story blend locally with Python Pillow (no API call)..."
    )
    story_file = None
    try:
        story_file = download_url_to_temp_file(
            requests.Session(),
            story_url,
            prefix="ad_cover_story_src_",
            suffix=".jpg",
            context=f"Download Ad Cover 9:16 story blend for local composite ({record_id})",
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUTPUT_DIR / f"ad_cover_converted_story_{record_id}.jpg"
        overlay_ad_cover_layout(
            story_file.path,
            fixture,
            dest,
            asset_name=cfg["story_asset"],
            canvas_size=cfg["story_canvas_size"],
        )

        airtable.upload_attachment(
            record_id,
            CONVERTED_STORY_FIELD,
            dest,
            f"ad_cover_converted_story_{record_id}.jpg",
        )
        safe_update_status(airtable, record_id, STATUS_CONVERTED_STORY_GENERATED)
        safe_update_status(airtable, record_id, STATUS_COMPLETE)
        print(
            f"[OK] Attached final 9:16 ad cover story to '{CONVERTED_STORY_FIELD}' "
            "and set Status 'Complete'."
        )
        return True
    except Exception as error:
        print(f"[ERROR] Local Ad Cover 9:16 story composite failed for {record_id}: {error}")
        return False
    finally:
        if story_file:
            story_file.cleanup()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline(
    *,
    fixture: str = DEFAULT_FIXTURE,
    mode: str = "all",
    style_code: str | None = None,
    table_id_override: str | None = None,
    max_items: int = 1,
    custom_prompt: str | None = None,
    custom_moodboard_id: str | None = None,
    record_id: str | None = None,
) -> int:
    cfg = resolve_fixture_config(fixture)
    table_id = resolve_table_id(fixture, table_id_override)
    moodboard_id = resolve_moodboard_id(fixture, custom_moodboard_id)
    interior_prompt = resolve_prompt(fixture, custom_prompt)
    style = (style_code or os.getenv("AKENEO_STYLE", "")).strip() or "modern"

    settings = load_settings()
    scrape_settings = load_scrape_settings(
        category_code=cfg["category_code"],
        style_code=style,
        table_id_override=table_id,
    )
    airtable = ScrapeAirtableClient(
        token=scrape_settings.airtable_token,
        base_id=scrape_settings.airtable_base_id,
        table_id=table_id,
    )

    print("\n" + "=" * 70)
    print(f" [AD COVER RUNNER] Fixture:     {cfg['label']} ({fixture})")
    print(f" [AD COVER RUNNER] Table:       {table_id}")
    print(f" [AD COVER RUNNER] Overlay:     assets/{cfg['asset']}")
    print(f" [AD COVER RUNNER] Story:       assets/{cfg.get('story_asset') or 'not registered'}")
    print(f" [AD COVER RUNNER] Moodboard:   {moodboard_id}")
    print(f' [AD COVER RUNNER] Krea prompt: "{interior_prompt}"')
    print(f" [AD COVER RUNNER] Aspect:      {ASPECT_RATIO} + {STORY_ASPECT_RATIO}")
    print(f" [AD COVER RUNNER] Base:        {scrape_settings.airtable_base_id}")
    print("=" * 70 + "\n")

    count = max(1, max_items or 1)

    if mode == "scrape":
        ensure_ad_cover_fields(airtable)
        created = 0
        for _ in range(count):
            if phase_scrape(airtable, fixture=fixture, table_id=table_id, style_code=style):
                created += 1
        return 0 if created else 1

    if record_id:
        ensure_ad_cover_fields(airtable)
        target_ids = [record_id]
    elif mode in (
        "interior",
        "prompt",
        "blend",
        "conversion",
        "story-blend",
        "story-conversion",
    ):
        ensure_ad_cover_fields(airtable)
        latest = newest_record(
            airtable,
            [
                INTERIOR_FIELD,
                PROMPT_FIELD,
                BLENDED_FIELD,
                CONVERTED_FIELD,
                BLENDED_STORY_FIELD,
                CONVERTED_STORY_FIELD,
                ITEM_NAME_FIELD,
                SKU_FIELD,
            ],
        )
        if not latest:
            print("[WARN] The Ad Cover table has no rows to resume.")
            return 1
        target_ids = [latest["id"]]
        print(f"[INFO] Resuming the newest row {latest['id']} (no --record-id given).")
    else:
        target_ids = []

    settings.require({"krea", "fal"})
    krea = KreaClient(settings.krea_token, base_url=settings.krea_base_url)
    fal = FalClient(settings.fal_key)

    if mode == "interior":
        return 0 if all(
            phase_interior(
                krea,
                airtable,
                record_id=rid,
                moodboard_id=moodboard_id,
                prompt=interior_prompt,
            )
            for rid in target_ids
        ) else 1

    if mode == "prompt":
        return 0 if all(phase_prompt(fal, airtable, record_id=rid) for rid in target_ids) else 1

    if mode == "blend":
        return 0 if all(phase_blend(fal, airtable, record_id=rid) for rid in target_ids) else 1

    if mode == "conversion":
        return 0 if all(
            phase_conversion(airtable, fixture=fixture, record_id=rid) for rid in target_ids
        ) else 1

    if mode == "story-blend":
        return 0 if all(
            phase_story_blend(fal, airtable, fixture=fixture, record_id=rid)
            for rid in target_ids
        ) else 1

    if mode == "story-conversion":
        return 0 if all(
            phase_story_conversion(airtable, fixture=fixture, record_id=rid)
            for rid in target_ids
        ) else 1

    # mode == "all": one brand-new row, processed end-to-end (1 through 7).
    failures = 0
    story_failures = 0
    for row_idx in range(1, count + 1):
        print(f"\n{'=' * 28} ROW {row_idx}/{count} {'=' * 28}")

        if record_id:
            target_record_id = record_id
            print(f"[INFO] Re-rendering the explicitly requested record {target_record_id}.")
        else:
            ensure_ad_cover_fields(airtable)
            target_record_id = phase_scrape(
                airtable, fixture=fixture, table_id=table_id, style_code=style
            )
            if not target_record_id:
                print("[WARN] Scrape produced no new row; stopping this run.")
                failures += 1
                break

        if not phase_interior(
            krea,
            airtable,
            record_id=target_record_id,
            moodboard_id=moodboard_id,
            prompt=interior_prompt,
        ):
            failures += 1
            continue

        if not phase_prompt(fal, airtable, record_id=target_record_id):
            failures += 1
            continue

        if not phase_blend(fal, airtable, record_id=target_record_id):
            failures += 1
            continue

        if not phase_conversion(airtable, fixture=fixture, record_id=target_record_id):
            failures += 1
            continue

        # The 1:1 deliverable is finished in Phase 5.
        # Check if this fixture has an actual 9:16 story overlay file on disk:
        cfg = resolve_fixture_config(fixture)
        story_asset_name = cfg.get("story_asset", "")
        from content_automation.overlay import _resolve_asset_file
        has_story_file = bool(story_asset_name and _resolve_asset_file(story_asset_name) is not None)

        if not has_story_file:
            # Fixtures with only 1:1 collection overlays complete cleanly here
            safe_update_status(airtable, target_record_id, STATUS_COMPLETE)
            print(
                f"[ROW {row_idx} COMPLETE] Record {target_record_id} is 100% COMPLETE "
                f"({ASPECT_RATIO} 1:1 Ad Cover)."
            )
        else:
            story_ok = phase_story_blend(fal, airtable, fixture=fixture, record_id=target_record_id)
            if story_ok:
                story_ok = phase_story_conversion(
                    airtable, fixture=fixture, record_id=target_record_id
                )

            if story_ok:
                print(
                    f"[ROW {row_idx} COMPLETE] Record {target_record_id} is 100% COMPLETE "
                    f"({ASPECT_RATIO} + {STORY_ASPECT_RATIO})."
                )
            else:
                story_failures += 1
                safe_update_status(airtable, target_record_id, STATUS_COMPLETE)
                print(
                    f"[WARN] The {STORY_ASPECT_RATIO} story branch failed for "
                    f"{target_record_id}; the {ASPECT_RATIO} ad cover is finished, so Status "
                    f"is 'Complete'. Re-run with --mode story-blend / story-conversion "
                    f"--record-id {target_record_id}."
                )

    return 1 if (failures or story_failures) else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ad Cover AI Generation Pipeline (1:1 + 9:16 Story)"
    )
    parser.add_argument(
        "--fixture",
        default=DEFAULT_FIXTURE,
        choices=list(AD_COVER_FIXTURES.keys()),
        help=f"Ad Cover fixture (default: {DEFAULT_FIXTURE})",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=[
            "scrape",
            "interior",
            "prompt",
            "blend",
            "conversion",
            "story-blend",
            "story-conversion",
            "all",
        ],
        default="all",
        help="Which phase to run (default: all, i.e. phases 1 through 7)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override the Airtable destination table ID",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=1,
        metavar="N",
        help="Number of brand-new rows to generate (default: 1)",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Override the Krea moodboard ID",
    )
    parser.add_argument(
        "--prompt",
        "-p",
        default=None,
        help="Override the Krea interior prompt",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=None,
        help="Akeneo style filter (default: AKENEO_STYLE or 'modern')",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Re-render one exact Airtable record instead of scraping a new row",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_pipeline(
            fixture=args.fixture,
            mode=args.mode,
            style_code=args.style,
            table_id_override=args.table_id,
            max_items=args.max_items,
            custom_prompt=args.prompt,
            custom_moodboard_id=args.moodboard_id,
            record_id=args.record_id,
        )
    except KeyboardInterrupt:
        print("\n[INFO] Exited Ad Cover Pipeline. Goodbye!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
