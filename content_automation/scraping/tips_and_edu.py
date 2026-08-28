"""Akeneo scraper runner for Tips and Edu Feeds layout (4 items per row)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..akeneo_client import AkeneoClient
from ..errors import AutomationError
from ..fields import (
    furniture_field,
    item_name_field,
    sku_field,
    type_is_compatible,
)
from ..media import attachment_filename
from . import categories
from .airtable import ScrapeAirtableClient
from .products import (
    IncompleteSlot,
    ProductItem,
    existing_product_identities,
    product_item,
    select_new_products,
)

ITEMS_PER_ROW = 4
DEFAULT_CATEGORIES = ("chandeliers",)


def tips_and_edu_required_fields() -> dict[str, str]:
    required: dict[str, str] = {}
    for slot in range(ITEMS_PER_ROW):
        required[furniture_field(slot)] = "multipleAttachments"
        required[sku_field(slot)] = "multilineText"
        required[item_name_field(slot)] = "singleLineText"
    return required


def is_linear_chandelier(item: ProductItem) -> bool:
    """Check if a product is a linear chandelier and should be excluded."""
    name_lower = (item.item_name or "").lower()
    sku_lower = (item.sku or "").lower()
    return "linear chandelier" in name_lower or "linear" in name_lower or "linear" in sku_lower


class TipsAndEduRunner:
    """Pack 4 Modern lighting products horizontally into Tips & Edu Feeds rows."""

    def __init__(
        self,
        akeneo: AkeneoClient,
        airtable: ScrapeAirtableClient,
        *,
        style_code: str = "modern",
        max_rows: int | None = None,
        seed: int | None = None,
        categories_list: tuple[str, ...] = DEFAULT_CATEGORIES,
    ):
        self.akeneo = akeneo
        self.airtable = airtable
        self.style_code = style_code
        self.max_rows = max_rows
        self.seed = seed
        self.categories_list = categories_list

    def _schema_preflight(self, *, execute: bool) -> None:
        required = tips_and_edu_required_fields()
        if execute:
            self.airtable.ensure_fields(required)
            return

        existing = self.airtable.table_fields()
        conflicts = [
            f"{name}: expected {expected}, found "
            f"{existing.get(name, {}).get('type', '')}"
            for name, expected in required.items()
            if name in existing
            and not type_is_compatible(
                str(existing[name].get("type") or ""),
                expected,
            )
        ]
        if conflicts:
            raise AutomationError(
                "Airtable field type conflict:\n" + "\n".join(conflicts)
            )
        missing = [name for name in required if name not in existing]
        if missing:
            print("[DRY RUN] Would create fields: " + ", ".join(missing))
        else:
            print("[OK] Airtable Tips & Edu fields are ready")

    def _fetch_candidates(
        self,
        existing_skus: set[str],
    ) -> list[ProductItem]:
        all_candidates: list[ProductItem] = []
        for category_code in self.categories_list:
            akeneo_category = categories.akeneo_category_code(category_code)
            query = {
                "categories": [
                    {"operator": "IN", "value": [akeneo_category]}
                ],
                "Style2": [
                    {"operator": "IN", "value": [self.style_code]}
                ],
            }
            print(
                f"[INFO] Fetching {self.style_code} {category_code} "
                f"products from Akeneo..."
            )
            products = self.akeneo.fetch_products(query)
            existing_names, existing_media = existing_product_identities(
                products,
                existing_skus,
            )
            selected, stats = select_new_products(
                products,
                existing_skus,
                existing_item_names=existing_names,
                existing_media_codes=existing_media,
                category_code=category_code,
            )
            
            # Filter out linear chandeliers explicitly
            filtered = [
                item for item in selected if not is_linear_chandelier(item)
            ]
            excluded_linear = len(selected) - len(filtered)
            all_candidates.extend(filtered)
            
            print(
                f"[PLAN] {category_code}: {len(filtered)} new candidates "
                f"({stats['existing_sku']} existing, "
                f"{stats['excluded_category'] + excluded_linear} category-excluded, "
                f"{stats['ineligible']} incomplete)"
            )
            
        return all_candidates

    def _repair_incomplete(
        self,
        incomplete: list[IncompleteSlot],
    ) -> int:
        failures = 0
        for entry in incomplete:
            try:
                item = product_item(self.akeneo.find_product(entry.sku))
                if item is None:
                    raise AutomationError(
                        "product is missing from Akeneo or has no image"
                    )
                if not self._upload(entry.record_id, entry.slot, item):
                    failures += 1
            except Exception as error:
                failures += 1
                print(
                    f"[ERROR] Could not repair {entry.sku} in "
                    f"{furniture_field(entry.slot)}: {error}"
                )
        return failures

    def _upload(
        self,
        record_id: str,
        slot: int,
        item: ProductItem,
    ) -> bool:
        downloaded = None
        field_name = furniture_field(slot)
        try:
            downloaded = self.akeneo.download_media(item.media_code)
            filename = attachment_filename(item.item_name, item.media_code)
            self.airtable.upload_attachment(
                record_id,
                field_name,
                downloaded,
                filename,
            )
            print(f"[OK] {item.sku} -> {record_id} / {field_name}")
            return True
        except Exception as error:
            print(f"[ERROR] {item.sku} -> {field_name} failed: {error}")
            return False
        finally:
            if downloaded:
                downloaded.cleanup()

    def run(self, *, execute: bool = False) -> bool:
        self._schema_preflight(execute=execute)
        self.akeneo.authenticate()
        existing_skus, incomplete = self.airtable.load_inventory()

        candidates = self._fetch_candidates(existing_skus)

        # Randomize/shuffle candidate products as requested
        rng = random.Random(self.seed)
        rng.shuffle(candidates)

        # Group candidates into 4-product rows
        new_rows = [
            candidates[i : i + ITEMS_PER_ROW]
            for i in range(0, len(candidates), ITEMS_PER_ROW)
            if len(candidates[i : i + ITEMS_PER_ROW]) == ITEMS_PER_ROW
        ]

        if self.max_rows is not None:
            new_rows = new_rows[: self.max_rows]

        print(
            f"[PLAN] repair_attachments={len(incomplete)}; "
            f"create_complete_rows={len(new_rows)} ({len(candidates)} candidates available)"
        )
        if not execute:
            print("[DRY RUN] No Airtable rows or attachments were changed.")
            return True

        failures = self._repair_incomplete(incomplete)

        for index, row_items in enumerate(new_rows, start=1):
            skus = ", ".join(item.sku for item in row_items)
            print(
                f"[INFO] Creating complete Tips & Edu row "
                f"{index}/{len(new_rows)} ({skus})..."
            )
            try:
                record_id = self.airtable.create_product_record(row_items)
            except Exception as error:
                failures += len(row_items)
                print(f"[ERROR] Could not create product row for {skus}: {error}")
                continue
            for slot, item in enumerate(row_items):
                if not self._upload(record_id, slot, item):
                    failures += 1

        if failures:
            print(
                f"[WARN] Tips & Edu scrape completed with {failures} failure(s); "
                "run the scraper again to retry."
            )
            return False

        print("[OK] Tips & Edu Feeds mass scrape completed successfully")
        return True
