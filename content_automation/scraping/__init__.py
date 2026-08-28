"""Scraping Akeneo products into the slot-based Airtable product tables."""

from __future__ import annotations

from .airtable import ScrapeAirtableClient
from .furniture_item import (
    FurnitureItemScrapeRunner,
    attachment_filenames,
    item_name_with_product_type,
)
from .interiors import InteriorRunner, ensure_interior_fields, interior_records
from .products import (
    IncompleteSlot,
    ProductItem,
    existing_product_identities,
    identity_key,
    inventory_from_records,
    normalize_sku,
    product_item,
    select_new_products,
)
from .runner import ScrapeRunner
from .settings import ScrapeSettings, load_scrape_settings
from .tips_and_edu import TipsAndEduRunner

__all__ = [
    "FurnitureItemScrapeRunner",
    "IncompleteSlot",
    "InteriorRunner",
    "ProductItem",
    "ScrapeAirtableClient",
    "ScrapeRunner",
    "ScrapeSettings",
    "TipsAndEduRunner",
    "attachment_filenames",
    "ensure_interior_fields",
    "existing_product_identities",
    "identity_key",
    "interior_records",
    "inventory_from_records",
    "item_name_with_product_type",
    "load_scrape_settings",
    "normalize_sku",
    "product_item",
    "select_new_products",
]

