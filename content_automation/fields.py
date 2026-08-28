"""Single source of truth for Airtable slot-based field naming.

Airtable tables store products in numbered "slots". Slot 0 uses the bare field
name ("SKU", "Furniture Item"); every later slot appends its 1-based position
("SKU2", "Furniture Item2", ... up to ``SLOT_COUNT``).

Slot arguments here are always **0-based**. Before this module the codebase had
two competing conventions -- ``standalone_scrape_akeneo`` counted from 0 while
``normalize_airtable_rows`` counted from 1 -- which made call sites impossible
to read side by side. Everything now counts from 0.

Current scrapes pack up to ``DEFAULT_ITEMS_PER_ROW`` products into a row.  The
wider legacy slot count remains available so old rows can still be inventoried
and repaired without losing products that were written by earlier versions.
"""

from __future__ import annotations


# Number of products written to a standard newly scraped Airtable row.
DEFAULT_ITEMS_PER_ROW = 10

# Widest legacy row ever written: slots 0..23 -> "SKU" .. "SKU24".
SLOT_COUNT = 24

# Pre-slot schema, where every SKU on a row lived in one multiline field.
LEGACY_SKU_FIELD = "SKUs"

ITEM_NAME_FIELD = "Item Name"
PRODUCT_TYPE_FIELD = "Product Type"
MEASUREMENT_FIELD = "Measurement"


def _slot_name(base: str, slot: int) -> str:
    if slot < 0:
        raise ValueError(f"slot must be 0-based and non-negative, got {slot}")
    return base if slot == 0 else f"{base}{slot + 1}"


def sku_field(slot: int) -> str:
    """"SKU" for slot 0, "SKU2".."SKU24" for later slots."""
    return _slot_name("SKU", slot)


def furniture_field(slot: int) -> str:
    """"Furniture Item" for slot 0, "Furniture Item2".. for later slots."""
    return _slot_name("Furniture Item", slot)


def item_name_field(slot: int) -> str:
    return _slot_name(ITEM_NAME_FIELD, slot)


def measurement_field(slot: int) -> str:
    return _slot_name(MEASUREMENT_FIELD, slot)


def product_type_field(slot: int) -> str:
    return _slot_name(PRODUCT_TYPE_FIELD, slot)


def interior_field(slot: int) -> str:
    """"Interior" for slot 0, "Interior2".."Interior24" for later slots."""
    return _slot_name("Interior", slot)


def field_type_of(schema_value: object) -> str:
    """Read a field's type out of an Airtable schema entry.

    Airtable schema lookups are represented two ways in this codebase: as a
    plain type string, and as a ``{"id": ..., "type": ...}`` mapping when the
    field id is needed to PATCH a column. Callers should not have to care, and
    when they did care one of them got it wrong -- comparing a dict against a
    set of type names raised ``TypeError: unhashable type: 'dict'``.
    """
    if isinstance(schema_value, dict):
        return str(schema_value.get("type") or "")
    return str(schema_value or "")


def field_id_of(schema_value: object) -> str:
    """Read a field's id out of an Airtable schema entry, "" when unknown."""
    if isinstance(schema_value, dict):
        return str(schema_value.get("id") or "")
    return ""


# Airtable treats these as interchangeable for our purposes, so a column typed
# either way satisfies a requirement for the other.
_TEXT_TYPES = frozenset({"singleLineText", "multilineText"})


def type_is_compatible(actual: str, expected: str) -> bool:
    """Whether an existing column type satisfies a required type."""
    if not actual:
        return False
    if expected in _TEXT_TYPES:
        return actual in _TEXT_TYPES
    return actual == expected
