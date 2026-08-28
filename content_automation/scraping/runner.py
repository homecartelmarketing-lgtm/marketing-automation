"""Driving one category's scrape from Akeneo into Airtable."""

from __future__ import annotations

from ..akeneo_client import AkeneoClient
from ..fields import furniture_field
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


class ScrapeRunner:
    """Creates packed rows for new products and repairs missing photos."""

    def __init__(
        self,
        akeneo: AkeneoClient,
        airtable: ScrapeAirtableClient,
        category_code: str,
        style_code: str,
        items_per_row: int | None = None,
        max_items: int | None = None,
    ):
        self.akeneo = akeneo
        self.airtable = airtable
        self.category_code = category_code
        self.style_code = style_code
        self.items_per_row = items_per_row
        self.max_items = max_items

    def _items_per_row(self) -> int:
        return self.items_per_row or categories.items_per_row(self.category_code)

    def _upload_item(self, record_id: str, slot: int, item: ProductItem) -> bool:
        """Download one product photo and attach it. False on failure."""
        field_name = self.airtable.resolve_slot_field("Furniture Item", slot)
        downloaded = None
        try:
            downloaded = self.akeneo.download_media(item.media_code)
            filename = attachment_filename(item.item_name, item.media_code)
            self.airtable.upload_attachment(record_id, field_name, downloaded, filename)
            print(f"[OK] {item.sku} -> {field_name} ({filename})")
            return True
        except Exception as error:
            print(f"[ERROR] {item.sku} -> {field_name} failed: {error}")
            return False
        finally:
            if downloaded:
                downloaded.cleanup()

    def repair_incomplete_slots(self, incomplete: list[IncompleteSlot]) -> int:
        """Re-upload photos for rows whose SKU landed but whose image did not."""
        if incomplete:
            print(f"[INFO] Repairing {len(incomplete)} incomplete attachment slots...")

        failures = 0
        for entry in incomplete:
            try:
                item = product_item(self.akeneo.find_product(entry.sku))
                if item is None:
                    raise RuntimeError(
                        "product is missing from Akeneo or has no name/image"
                    )
                if not self._upload_item(entry.record_id, entry.slot, item):
                    failures += 1
            except Exception as error:
                failures += 1
                print(f"[ERROR] Could not repair SKU {entry.sku}: {error}")
        return failures

    def _upload_this_or_that_layout(self, record_id: str) -> bool:
        """Upload thisorthatlayout.jpg to This or That Layout field."""
        layout_field = "This or That Layout"
        has_field = getattr(self.airtable, "has_field", lambda _n: False)
        if not ("this_or_that" in self.category_code or has_field(layout_field)):
            return False

        from pathlib import Path
        layout_candidates = [
            Path("JSON Prompts/This or That/thisorthatlayout.jpg"),
            Path("JSON Prompts/thisorthatlayout.jpg"),
            Path("thisorthatlayout.jpg"),
        ]
        layout_file = next((p for p in layout_candidates if p.is_file()), None)
        if not layout_file:
            for base in [Path("JSON Prompts"), Path(".")]:
                if base.is_dir():
                    matches = list(base.rglob("thisorthatlayout.jpg"))
                    if matches:
                        layout_file = matches[0]
                        break
        if not layout_file or not layout_file.is_file():
            print(f"[WARN] Layout file thisorthatlayout.jpg was not found.")
            return False

        try:
            self.airtable.upload_attachment(
                record_id,
                layout_field,
                layout_file,
                "thisorthatlayout.jpg",
            )
            print(f"[OK] {record_id} -> {layout_field} (thisorthatlayout.jpg)")
            return True
        except Exception as error:
            print(f"[WARN] Upload layout to {layout_field} failed: {error}")
            return False

    def _upload_cta_layout(self, record_id: str) -> bool:
        """Upload cta_layout.jpg to CTA Blended Image Watermark Layout field."""
        has_field = getattr(self.airtable, "has_field", lambda _n: False)
        layout_field = None
        for candidate in ("CTA Blended Image Watermark Layout", "CTA Layout", "Watermark Layout"):
            if "cta" in self.category_code or has_field(candidate):
                layout_field = candidate
                break
        if not layout_field:
            return False

        from pathlib import Path
        layout_candidates = [
            Path("JSON Prompts/CTA/cta_layout.jpg"),
            Path("JSON Prompts/cta_layout.jpg"),
            Path("cta_layout.jpg"),
        ]
        layout_file = next((p for p in layout_candidates if p.is_file()), None)
        if not layout_file:
            for base in [Path("JSON Prompts"), Path(".")]:
                if base.is_dir():
                    matches = list(base.rglob("cta_layout.jpg"))
                    if matches:
                        layout_file = matches[0]
                        break
        if not layout_file or not layout_file.is_file():
            print(f"[WARN] Layout file cta_layout.jpg was not found.")
            return False

        try:
            self.airtable.upload_attachment(
                record_id,
                layout_field,
                layout_file,
                "cta_layout.jpg",
            )
            print(f"[OK] {record_id} -> {layout_field} (cta_layout.jpg)")
            return True
        except Exception as error:
            print(f"[WARN] Upload layout to {layout_field} failed: {error}")
            return False

    def _upload_logo(self, record_id: str) -> bool:
        """Upload HomeCartel logo to Logo attachment field."""
        has_field = getattr(self.airtable, "has_field", lambda _n: False)
        logo_field = None
        for candidate in ("Logo", "Brand Logo", "Watermark", "Logo Image"):
            if has_field(candidate) or "cta" in self.category_code:
                logo_field = candidate
                break
        if not logo_field:
            return False

        from pathlib import Path
        logo_candidates = [
            Path("assets/homecartel_logo.png"),
            Path("JSON Prompts/homecartel_logo.png"),
            Path("scratch/refined_logo.png"),
            Path("scratch/removed_bg_logo.png"),
            Path("content_automation/assets/logo.png"),
            Path("static/img/logo.png"),
            Path("logo.png"),
        ]
        logo_file = next((p for p in logo_candidates if p.is_file()), None)
        if not logo_file:
            for base in [Path("assets"), Path("JSON Prompts"), Path("static"), Path(".")]:
                if base.is_dir():
                    matches = list(base.rglob("*logo*.png"))
                    if matches:
                        logo_file = matches[0]
                        break
        if not logo_file or not logo_file.is_file():
            print(f"[WARN] HomeCartel logo file was not found.")
            return False

        try:
            self.airtable.upload_attachment(
                record_id,
                logo_field,
                logo_file,
                "homecartel_logo.png",
            )
            print(f"[OK] {record_id} -> {logo_field} (homecartel_logo.png)")
            return True
        except Exception as error:
            print(f"[WARN] Upload logo to {logo_field} failed: {error}")
            return False

    def repair_missing_layouts(self) -> int:
        """Upload thisorthatlayout.jpg to any row that has products but lacks This or That Layout."""
        if "this_or_that" not in self.category_code and not getattr(self.airtable, "has_field", lambda _n: False)("This or That Layout"):
            return 0
        try:
            records = self.airtable.list_records(["This or That Layout", "Furniture Item", "Furniture Item1"])
        except Exception:
            return 0
        fixed = 0
        for r in records:
            rec_id = r.get("id")
            fields = r.get("fields", {})
            has_prod = bool(fields.get("Furniture Item") or fields.get("Furniture Item1"))
            has_layout = bool(fields.get("This or That Layout"))
            if has_prod and not has_layout:
                if self._upload_this_or_that_layout(rec_id):
                    fixed += 1
        if fixed:
            print(f"[OK] Backfilled {fixed} missing 'This or That Layout' attachment(s)")
        return fixed

    def repair_missing_cta_layouts(self) -> int:
        """Upload cta_layout.jpg to any row that has products but lacks CTA layout."""
        if "cta" not in self.category_code and not getattr(self.airtable, "has_field", lambda _n: False)("CTA Blended Image Watermark Layout"):
            return 0
        try:
            records = self.airtable.list_records(["CTA Blended Image Watermark Layout", "CTA Layout", "Watermark Layout", "Furniture Item", "Furniture Item1"])
        except Exception:
            return 0
        fixed = 0
        for r in records:
            rec_id = r.get("id")
            fields = r.get("fields", {})
            has_prod = bool(fields.get("Furniture Item") or fields.get("Furniture Item1"))
            has_layout = bool(fields.get("CTA Blended Image Watermark Layout") or fields.get("CTA Layout") or fields.get("Watermark Layout"))
            if has_prod and not has_layout:
                if self._upload_cta_layout(rec_id):
                    fixed += 1
        if fixed:
            print(f"[OK] Backfilled {fixed} missing CTA Layout attachment(s)")
        return fixed

    def repair_missing_logos(self) -> int:
        """Upload HomeCartel logo to any row that has products but lacks Logo."""
        has_field = getattr(self.airtable, "has_field", lambda _n: False)
        logo_field = None
        for candidate in ("Logo", "Brand Logo", "Watermark", "Logo Image"):
            if "cta" in self.category_code or has_field(candidate):
                logo_field = candidate
                break
        if not logo_field:
            return 0
        try:
            records = self.airtable.list_records([logo_field, "Furniture Item", "Furniture Item1"])
        except Exception:
            return 0
        fixed = 0
        for r in records:
            rec_id = r.get("id")
            fields = r.get("fields", {})
            has_prod = bool(fields.get("Furniture Item") or fields.get("Furniture Item1"))
            has_logo = bool(fields.get(logo_field))
            if has_prod and not has_logo:
                if self._upload_logo(rec_id):
                    fixed += 1
        if fixed:
            print(f"[OK] Backfilled {fixed} missing Logo attachment(s)")
        return fixed

    def create_new_records(self, items: list[ProductItem]) -> int:
        """Write the selected products out, packing rows per category rules."""
        per_row = self._items_per_row()
        chunks = [items[i : i + per_row] for i in range(0, len(items), per_row)]

        failures = 0
        for position, chunk in enumerate(chunks, start=1):
            skus = ", ".join(item.sku for item in chunk)
            print(
                f"[INFO] Creating product row {position}/{len(chunks)} "
                f"({len(chunk)} item(s)) for {skus}..."
            )
            try:
                record_id = self.airtable.create_product_record(chunk)
            except Exception as error:
                failures += len(chunk)
                print(f"[ERROR] Product row for {skus} was not created: {error}")
                continue

            for slot, item in enumerate(chunk):
                if not self._upload_item(record_id, slot, item):
                    failures += 1

            if "this_or_that" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("This or That Layout"):
                self._upload_this_or_that_layout(record_id)
            if "cta" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("CTA Blended Image Watermark Layout"):
                self._upload_cta_layout(record_id)
            if "cta" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("Logo") or getattr(self.airtable, "has_field", lambda _n: False)("Brand Logo"):
                self._upload_logo(record_id)
        return failures

    def fill_existing_slots(
        self,
        items: list[ProductItem],
        available: list[AvailableSlot],
    ) -> tuple[list[ProductItem], int]:
        """Fill safe empty slots before creating another partially full row."""
        assignment_count = min(len(items), len(available))
        if not assignment_count:
            return items, 0

        selected = list(zip(available[:assignment_count], items[:assignment_count]))
        grouped: list[tuple[str, list[tuple[int, ProductItem]]]] = []
        for target, item in selected:
            if not grouped or grouped[-1][0] != target.record_id:
                grouped.append((target.record_id, []))
            grouped[-1][1].append((target.slot, item))

        failures = 0
        for record_id, assignments in grouped:
            skus = ", ".join(item.sku for _, item in assignments)
            print(
                f"[INFO] Filling {len(assignments)} empty slot(s) in "
                f"existing row {record_id}: {skus}..."
            )
            try:
                self.airtable.assign_product_slots(record_id, assignments)
            except Exception as error:
                failures += len(assignments)
                print(
                    f"[ERROR] Could not assign products to existing row "
                    f"{record_id}: {error}"
                )
                continue

            for slot, item in assignments:
                if not self._upload_item(record_id, slot, item):
                    failures += 1

            if "this_or_that" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("This or That Layout"):
                self._upload_this_or_that_layout(record_id)
            if "cta" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("CTA Blended Image Watermark Layout"):
                self._upload_cta_layout(record_id)
            if "cta" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("Logo") or getattr(self.airtable, "has_field", lambda _n: False)("Brand Logo"):
                self._upload_logo(record_id)

        # Assigned products are considered consumed even on an ambiguous write
        # failure. A later run inventories Airtable and safely retries either
        # the attachment or the whole still-new product.
        return items[assignment_count:], failures

    def _fetch_candidates(self) -> list[dict]:
        akeneo_category = categories.akeneo_category_code(self.category_code)
        query = {
            "categories": [{"operator": "IN", "value": [akeneo_category]}],
            "Style2": [{"operator": "IN", "value": [self.style_code]}],
            "enabled": [{"operator": "=", "value": True}],
        }
        print(
            f"[INFO] Fetching all active {self.style_code} {self.category_code} "
            "products from Akeneo..."
        )
        return self.akeneo.fetch_products(query)

    def run(self) -> bool:
        """Run the scrape. True when nothing failed."""
        self.akeneo.authenticate()
        per_row = self._items_per_row()
        self.airtable.ensure_product_fields(items_per_row=per_row)
        if "this_or_that" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("This or That Layout"):
            try:
                self.airtable.ensure_fields({"This or That Layout": "multipleAttachments"})
            except Exception:
                pass
        if "cta" in self.category_code or getattr(self.airtable, "has_field", lambda _n: False)("CTA Blended Image Watermark Layout"):
            try:
                self.airtable.ensure_fields({"CTA Blended Image Watermark Layout": "multipleAttachments"})
            except Exception:
                pass
        existing_skus, incomplete = self.airtable.load_inventory()
        available = self.airtable.available_product_slots(per_row)
        if self.max_items is not None and incomplete:
            print(
                f"[INFO] Skipping {len(incomplete)} incomplete-slot repair(s) "
                "during a limited new-item run"
            )
            failures = 0
        else:
            failures = self.repair_incomplete_slots(incomplete)

        if "this_or_that" in self.category_code:
            self.repair_missing_layouts()
        if "cta" in self.category_code:
            self.repair_missing_cta_layouts()

        products = self._fetch_candidates()
        existing_names, existing_media = existing_product_identities(
            products, existing_skus
        )
        all_new_items, stats = select_new_products(
            products,
            existing_skus,
            existing_item_names=existing_names,
            existing_media_codes=existing_media,
            category_code=self.category_code,
        )
        new_items = (
            all_new_items[: self.max_items]
            if self.max_items is not None
            else all_new_items
        )
        limit_note = (
            f", limited to {len(new_items)} for this run"
            if len(new_items) != len(all_new_items)
            else ""
        )
        print(
            f"[INFO] Akeneo returned {len(products)} products: "
            f"{len(all_new_items)} unique new items{limit_note}, "
            f"{stats['existing_sku']} existing SKUs, "
            f"{stats['excluded_category']} excluded by category filter, "
            f"{stats['ineligible']} missing name/image, "
            f"{stats['duplicate_sku']} duplicate SKUs, "
            f"{stats['duplicate_photo']} duplicate photos, "
            f"{stats['duplicate_name']} duplicate item names"
        )

        label = categories.category_label(self.category_code).title()
        style_label = self.style_code.title()

        if new_items:
            remaining, fill_failures = self.fill_existing_slots(
                new_items, available
            )
            failures += fill_failures
            failures += self.create_new_records(remaining)
        else:
            print(f"[OK] No new {style_label} {label} products to upload")

        if failures:
            print(
                f"[WARN] Run completed with {failures} failed uploads/assignments. "
                "Run the scraper again to retry incomplete slots."
            )
            return False

        print(f"[OK] {style_label} {label} mass scrape completed successfully")
        return True
