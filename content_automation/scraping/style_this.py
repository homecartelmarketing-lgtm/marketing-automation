"""Category-locked Akeneo packing for the Style This Airtable layout."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..akeneo_client import AkeneoClient
from ..errors import AutomationError
from ..fields import (
    furniture_field,
    item_name_field,
    measurement_field,
    product_type_field,
    sku_field,
    type_is_compatible,
)
from ..media import attachment_filename
from . import categories
from .airtable import ScrapeAirtableClient
from .products import (
    AvailableSlot,
    IncompleteSlot,
    ProductItem,
    existing_product_identities,
    product_item,
    select_new_products,
)


@dataclass(frozen=True)
class StyleThisColumn:
    slot: int
    category_code: str
    label: str


STYLE_THIS_COLUMNS: tuple[StyleThisColumn, ...] = (
    StyleThisColumn(0, "floor_lamps", "Floor Lamp"),
    StyleThisColumn(1, "table_lamps", "Table Lamp"),
    StyleThisColumn(2, "pendant_lights", "Pendant Light"),
    StyleThisColumn(3, "chandeliers", "Chandelier"),
)


def style_this_required_fields() -> dict[str, str]:
    required: dict[str, str] = {}
    for column in STYLE_THIS_COLUMNS:
        required[furniture_field(column.slot)] = "multipleAttachments"
        required[sku_field(column.slot)] = "multilineText"
        required[item_name_field(column.slot)] = "singleLineText"
        required[product_type_field(column.slot)] = "singleLineText"
        required[measurement_field(column.slot)] = "singleLineText"
    return required


class StyleThisRunner:
    """Fill one Airtable row with one Modern product from each category."""

    def __init__(
        self,
        akeneo: AkeneoClient,
        airtable: ScrapeAirtableClient,
        *,
        style_code: str = "modern",
        max_pairs: int | None = None,
    ):
        self.akeneo = akeneo
        self.airtable = airtable
        self.style_code = style_code
        self.max_pairs = max_pairs

    def _schema_preflight(self, *, execute: bool) -> None:
        required = style_this_required_fields()
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
            print("[OK] Airtable Style This fields are ready")

    def _fetch_candidates(
        self,
        existing_skus: set[str],
    ) -> dict[int, list[ProductItem]]:
        candidates: dict[int, list[ProductItem]] = {}
        for column in STYLE_THIS_COLUMNS:
            akeneo_category = categories.akeneo_category_code(
                column.category_code
            )
            query = {
                "categories": [
                    {"operator": "IN", "value": [akeneo_category]}
                ],
                "Style2": [
                    {"operator": "IN", "value": [self.style_code]}
                ],
            }
            print(
                f"[INFO] Fetching {self.style_code} {column.label} "
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
                category_code=column.category_code,
            )
            candidates[column.slot] = selected
            print(
                f"[PLAN] {column.label}: {len(selected)} new candidates "
                f"({stats['existing_sku']} existing, "
                f"{stats['excluded_category']} category-excluded, "
                f"{stats['ineligible']} incomplete)"
            )
        return candidates

    @staticmethod
    def _group_empty_slots(
        available: list[AvailableSlot],
    ) -> list[tuple[str, list[int]]]:
        grouped: dict[str, list[int]] = defaultdict(list)
        order: list[str] = []
        for target in available:
            if target.record_id not in grouped:
                order.append(target.record_id)
            grouped[target.record_id].append(target.slot)
        return [
            (record_id, sorted(grouped[record_id]))
            for record_id in order
        ]

    def _plan_existing_rows(
        self,
        available: list[AvailableSlot],
        candidates: dict[int, list[ProductItem]],
    ) -> list[tuple[str, list[tuple[int, ProductItem]]]]:
        planned: list[tuple[str, list[tuple[int, ProductItem]]]] = []
        for record_id, slots in self._group_empty_slots(available):
            relevant = [slot for slot in slots if slot in candidates]
            if not relevant or any(not candidates[slot] for slot in relevant):
                continue
            if self.max_pairs is not None and len(planned) >= self.max_pairs:
                break
            assignments = [
                (slot, candidates[slot].pop(0))
                for slot in relevant
            ]
            planned.append((record_id, assignments))
        return planned

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
        available = self.airtable.available_product_slots(
            len(STYLE_THIS_COLUMNS)
        )
        candidates = self._fetch_candidates(existing_skus)

        existing_plans = self._plan_existing_rows(available, candidates)
        remaining_capacity = None
        if self.max_pairs is not None:
            remaining_capacity = max(self.max_pairs - len(existing_plans), 0)

        pair_count = min(len(candidates[column.slot]) for column in STYLE_THIS_COLUMNS)
        if remaining_capacity is not None:
            pair_count = min(pair_count, remaining_capacity)
        new_pairs = [
            [candidates[column.slot][index] for column in STYLE_THIS_COLUMNS]
            for index in range(pair_count)
        ]

        floor_remaining = len(candidates[0])
        if pair_count < floor_remaining:
            print(
                f"[INFO] {floor_remaining} Floor Lamp candidates are available, "
                f"but this run is limited to {pair_count} complete four-item pair(s)"
            )
        print(
            f"[PLAN] repair_attachments={len(incomplete)}; "
            f"fill_existing_rows={len(existing_plans)}; "
            f"create_complete_rows={len(new_pairs)}"
        )
        if not execute:
            print("[DRY RUN] No Airtable rows or attachments were changed.")
            return True

        failures = self._repair_incomplete(incomplete)
        for record_id, assignments in existing_plans:
            try:
                self.airtable.assign_product_slots(record_id, assignments)
            except Exception as error:
                failures += len(assignments)
                print(f"[ERROR] Could not fill existing row {record_id}: {error}")
                continue
            for slot, item in assignments:
                if not self._upload(record_id, slot, item):
                    failures += 1

        for index, items in enumerate(new_pairs, start=1):
            print(
                f"[INFO] Creating complete Style This row "
                f"{index}/{len(new_pairs)}..."
            )
            try:
                record_id = self.airtable.create_product_record(items)
            except Exception as error:
                failures += len(items)
                print(f"[ERROR] Could not create paired row: {error}")
                continue
            for column, item in zip(STYLE_THIS_COLUMNS, items):
                if not self._upload(record_id, column.slot, item):
                    failures += 1

        if failures:
            print(
                f"[WARN] Style This scrape completed with {failures} failure(s); "
                "rerun it to repair incomplete attachments."
            )
            return False
        print(
            f"[OK] Style This scrape complete: "
            f"{len(existing_plans) + len(new_pairs)} row(s) processed"
        )
        return True
