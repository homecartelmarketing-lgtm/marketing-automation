"""Turning Akeneo search results into the rows a scrape should create.

The selection rules exist because the same physical product reaches us more
than once: re-listed under a new SKU, re-photographed, or renamed. A row is
only worth creating when its SKU, its photo and its name are all new.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..akeneo_client import first_attribute, metadata_from_product
from ..fields import (
    LEGACY_SKU_FIELD,
    SLOT_COUNT,
    furniture_field,
    interior_field,
    item_name_field,
    measurement_field,
    product_type_field,
    sku_field,
)
from . import categories


@dataclass(frozen=True)
class ProductItem:
    """One Akeneo product, reduced to what a scrape writes to Airtable."""

    sku: str
    item_name: str
    media_code: str
    product_type: str = ""
    measurement: str = ""
    updated: str = ""
    cost: str = ""
    cost_value: float = 0.0


@dataclass(frozen=True)
class IncompleteSlot:
    """A row whose SKU was written but whose photo upload never landed."""

    record_id: str
    slot: int
    sku: str


@dataclass(frozen=True)
class AvailableSlot:
    """An entirely empty product slot that can safely receive a new item."""

    record_id: str
    slot: int


@dataclass
class SelectionStats:
    """Why products were passed over, for the end-of-run summary."""

    existing_sku: int = 0
    duplicate_sku: int = 0
    duplicate_photo: int = 0
    duplicate_name: int = 0
    excluded_category: int = 0
    ineligible: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(vars(self))


def normalize_sku(value: object) -> str:
    return str(value).strip() if value is not None else ""


def identity_key(value: object) -> str:
    """Collapse whitespace and case so near-identical values compare equal."""
    return " ".join(str(value or "").split()).casefold()


def parse_cost_value(cost_str: object) -> float:
    """Parse numeric price/cost value from text or Akeneo structures.

    Handles formats such as:
    - '100-200 USD' -> 200.0 (takes upper bound)
    - '150-250 USD' -> 250.0
    - '1025.00 元' -> ~142.36 (converts CNY to USD approx at 7.2)
    - '20.46 CNY' -> ~2.84
    - 'Approximately $50-$100' -> 100.0
    - 'High' -> 300.0
    - '0', '', None -> 0.0
    """
    if cost_str is None:
        return 0.0
    if isinstance(cost_str, (int, float)):
        return float(cost_str)
    if isinstance(cost_str, list):
        if not cost_str:
            return 0.0
        first = cost_str[0]
        if isinstance(first, dict):
            cost_str = first.get("data") or first.get("amount") or ""
        else:
            cost_str = str(first)

    text = str(cost_str).strip()
    if not text or text == "0":
        return 0.0

    is_cny = bool(re.search(r"(?i)(?:cny|rmb|\u5143|\xa5|yuan)", text))
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if not nums:
        if "high" in text.lower():
            return 300.0
        return 0.0

    val = max(float(n) for n in nums)
    if is_cny:
        val = val / 7.2
    return round(val, 2)


def product_item(product: dict | None) -> ProductItem | None:
    """Build a ProductItem, or None when the product cannot be published."""
    if not product:
        return None
    sku = normalize_sku(product.get("identifier"))
    name = first_attribute(product, "name")
    media_code = first_attribute(product, "image")
    if not sku or name is None or media_code is None:
        return None
    metadata = metadata_from_product(product)
    cost_raw = first_attribute(
        product, "Costing", "costing", "Selling_Price", "selling_price", "Price", "price"
    )
    cost_str = str(cost_raw).strip() if cost_raw is not None else ""
    cost_val = parse_cost_value(cost_raw)
    return ProductItem(
        sku=sku,
        item_name=metadata.get("Item Name") or str(name).strip(),
        media_code=str(media_code).strip(),
        product_type=metadata.get("Product Type", ""),
        measurement=metadata.get("Measurement", ""),
        updated=str(product.get("updated") or ""),
        cost=cost_str,
        cost_value=cost_val,
    )


def existing_product_identities(
    products: list[dict],
    existing_skus: set[str],
) -> tuple[set[str], set[str]]:
    """Resolve stored SKUs back to their Akeneo item-name and photo identities.

    Airtable only stores the SKU, so re-deriving the name and photo of what is
    already stored is what lets a renamed or re-photographed duplicate be seen.
    """
    stored = {identity_key(sku) for sku in existing_skus}
    item_names: set[str] = set()
    media_codes: set[str] = set()
    for product in products:
        item = product_item(product)
        if item and identity_key(item.sku) in stored:
            item_names.add(identity_key(item.item_name))
            media_codes.add(identity_key(item.media_code))
    return item_names, media_codes


@dataclass
class _CategoryFilter:
    """Keyword and category rules narrowing a shared Akeneo source category."""

    excluded_categories: set[str] = field(default_factory=set)
    excluded_keywords: set[str] = field(default_factory=set)
    included_keywords: set[str] = field(default_factory=set)

    @classmethod
    def for_category(cls, category_code: str | None) -> "_CategoryFilter":
        if not category_code:
            return cls()
        return cls(
            excluded_categories=categories.excluded_categories(category_code),
            excluded_keywords=categories.excluded_keywords(category_code),
            included_keywords=categories.included_keywords(category_code),
        )

    def rejects_raw_product(self, product: dict) -> bool:
        return bool(set(product.get("categories", [])) & self.excluded_categories)

    def rejects_item(self, item: ProductItem) -> bool:
        searchable_text = f"{item.item_name} {item.product_type}".lower()
        if any(keyword in searchable_text for keyword in self.excluded_keywords):
            return True
        if self.included_keywords:
            return not any(keyword in searchable_text for keyword in self.included_keywords)
        return False


def _sku_sort_key(sku: str) -> tuple:
    """Extract numeric chunks from SKU so e.g. SKU-100 > SKU-2 when dates match."""
    parts = re.split(r"(\d+)", sku)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def _newest_first(products: list[dict]) -> list[dict]:
    """Most recently created or updated first, so newest products are processed first."""
    return sorted(
        products,
        key=lambda product: (
            str(product.get("created") or product.get("updated") or ""),
            _sku_sort_key(normalize_sku(product.get("identifier"))),
        ),
        reverse=True,
    )


def select_new_products(
    products: list[dict],
    existing_skus: set[str],
    existing_item_names: set[str] | None = None,
    existing_media_codes: set[str] | None = None,
    category_code: str | None = None,
    sort_by_price_in_newest_pool: bool = False,
    price_pool_size: int = 50,
) -> tuple[list[ProductItem], dict[str, int]]:
    """Pick the products that deserve a new Airtable row.

    Returns the items to create plus a per-reason count of what was skipped.
    If sort_by_price_in_newest_pool is True, takes the top `price_pool_size`
    newest candidates and ranks them highest-to-lowest by price/cost.
    """
    stats = SelectionStats()
    filters = _CategoryFilter.for_category(category_code)

    stored_skus = {identity_key(sku) for sku in existing_skus}
    seen_skus = set(stored_skus)
    seen_names = {identity_key(name) for name in (existing_item_names or set())}
    seen_media = {identity_key(code) for code in (existing_media_codes or set())}

    selected: list[ProductItem] = []
    for product in _newest_first(products):
        if not product.get("enabled", False):
            stats.ineligible += 1
            continue
        sku_key = identity_key(normalize_sku(product.get("identifier")))
        if sku_key and sku_key in stored_skus:
            stats.existing_sku += 1
            continue
        if sku_key and sku_key in seen_skus:
            stats.duplicate_sku += 1
            continue
        if filters.rejects_raw_product(product):
            stats.excluded_category += 1
            continue

        item = product_item(product)
        if item is None:
            stats.ineligible += 1
            sku = normalize_sku(product.get("identifier"))
            print(f"[WARN] Skipping {sku or '<missing SKU>'}: missing item name or image")
            continue
        if filters.rejects_item(item):
            stats.excluded_category += 1
            continue

        media_key = identity_key(item.media_code)
        name_key = identity_key(item.item_name)
        if media_key in seen_media:
            stats.duplicate_photo += 1
            continue
        if name_key in seen_names:
            stats.duplicate_name += 1
            continue

        selected.append(item)
        seen_skus.add(sku_key)
        seen_media.add(media_key)
        seen_names.add(name_key)

    if sort_by_price_in_newest_pool and selected:
        pool_limit = max(1, price_pool_size)
        pool = selected[:pool_limit]
        remainder = selected[pool_limit:]
        # Sort pool highest price first; preserve newest order for equal/zero prices
        pool_sorted = sorted(
            pool,
            key=lambda it: it.cost_value,
            reverse=True,
        )
        selected = pool_sorted + remainder

    return selected, stats.as_dict()


def inventory_from_records(
    records: list[dict],
) -> tuple[set[str], list[IncompleteSlot]]:
    """Read stored SKUs and unfinished photo slots out of Airtable records."""
    existing_skus: set[str] = set()
    incomplete: list[IncompleteSlot] = []

    for record in records:
        fields = record.get("fields", {})

        # Pre-slot rows kept every SKU in one multiline field.
        legacy_value = fields.get(LEGACY_SKU_FIELD)
        if legacy_value is not None:
            existing_skus.update(
                sku
                for line in str(legacy_value).splitlines()
                if (sku := normalize_sku(line))
            )

        for slot in range(SLOT_COUNT):
            sku_val = fields.get(sku_field(slot)) or fields.get(f"SKU{slot+1}")
            sku = normalize_sku(sku_val)
            if not sku:
                continue
            existing_skus.add(sku)
            furniture_val = fields.get(furniture_field(slot)) or fields.get(f"Furniture Item{slot+1}")
            if not furniture_val:
                incomplete.append(
                    IncompleteSlot(record_id=record["id"], slot=slot, sku=sku)
                )

    return existing_skus, incomplete


def available_slots_from_records(
    records: list[dict],
    items_per_row: int,
) -> list[AvailableSlot]:
    """Return empty slots in existing rows without overwriting any row data.

    A slot is available only when all of its product and interior fields are
    empty.  This matters for older rows whose Krea pass may already have put an
    image into a slot even though its SKU is blank.
    """
    available: list[AvailableSlot] = []
    for record in records:
        fields = record.get("fields", {})
        for slot in range(items_per_row):
            names = (
                sku_field(slot),
                f"SKU{slot+1}",
                item_name_field(slot),
                f"Item Name{slot+1}",
                product_type_field(slot),
                f"Product Type{slot+1}",
                measurement_field(slot),
                f"Measurement{slot+1}",
                furniture_field(slot),
                f"Furniture Item{slot+1}",
                interior_field(slot),
                f"Interior{slot+1}",
            )
            if not any(fields.get(name) for name in names):
                available.append(AvailableSlot(record_id=record["id"], slot=slot))
    return available
