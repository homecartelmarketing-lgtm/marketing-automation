"""Airtable access for the slot-based scrape tables.

This is deliberately separate from ``content_automation.airtable_client``: that
one is built around a ``TableConfig`` and the content-automation schema, while a
scrape addresses a table by raw id and thinks in numbered product slots.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote

import requests

from ..fields import (
    DEFAULT_ITEMS_PER_ROW,
    ITEM_NAME_FIELD,
    LEGACY_SKU_FIELD,
    SLOT_COUNT,
    field_id_of,
    field_type_of,
    furniture_field,
    item_name_field,
    interior_field,
    measurement_field,
    product_type_field,
    sku_field,
    type_is_compatible,
)
from ..errors import AutomationError
from ..http import request_with_retry, response_error
from ..media import DownloadedMedia
from .products import (
    AvailableSlot,
    IncompleteSlot,
    available_slots_from_records,
    inventory_from_records,
)

API_BASE = "https://api.airtable.com/v0"
CONTENT_BASE = "https://content.airtable.com/v0"

PAGE_SIZE = 100


class ScrapeAirtableClient:
    """Reads and writes one slot-based product table."""

    def __init__(
        self,
        token: str,
        base_id: str,
        table_id: str,
        session: requests.Session | None = None,
    ):
        self.token = token
        self.base_id = base_id
        self.table_id = table_id
        self.session = session or requests.Session()
        self._schema: dict[str, Any] | None = None
        self._inventory_records: list[dict[str, Any]] | None = None

    # -- plumbing ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        url: str,
        *,
        retry_server_errors: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        """Send a request.

        Writes default to ``retry_server_errors=False`` so only a 429 is
        replayed; retrying a 5xx POST here could create a duplicate row.
        """
        kwargs.setdefault("headers", self._headers())
        return request_with_retry(
            self.session,
            method,
            url,
            retry_non_idempotent=True,
            retry_server_errors=retry_server_errors,
            **kwargs,
        )

    @property
    def records_url(self) -> str:
        return f"{API_BASE}/{self.base_id}/{self.table_id}"

    @property
    def fields_url(self) -> str:
        return f"{API_BASE}/meta/bases/{self.base_id}/tables/{self.table_id}/fields"

    # -- schema -----------------------------------------------------------

    def table_fields(self) -> dict[str, Any]:
        """Field name -> ``{"id", "type"}`` for this table."""
        url = f"{API_BASE}/meta/bases/{self.base_id}/tables"
        response = self._request("GET", url, retry_server_errors=True)
        if not response.ok:
            raise response_error(response, "Airtable schema lookup")
        for table in response.json().get("tables", []):
            if table.get("id") == self.table_id:
                return {
                    field["name"]: {
                        "id": field.get("id"),
                        "type": field.get("type"),
                        "choices": [
                            c.get("name")
                            for c in field.get("options", {}).get("choices", [])
                        ] if field.get("type") in ("singleSelect", "multipleSelects") else [],
                    }
                    for field in table["fields"]
                }
        raise AutomationError(f"Airtable table {self.table_id} was not found")

    def known_field_names(self, *, refresh: bool = False) -> set[str]:
        """Names of every field on the table, cached after the first lookup."""
        if self._schema is None or refresh:
            self._schema = self.table_fields()
        return set(self._schema)

    def has_field(self, name: str) -> bool:
        return name in self.known_field_names()

    def _retype_field(self, name: str, schema_entry: Any, expected: str) -> bool:
        """Try to widen a mistyped column in place. False if Airtable refuses."""
        field_id = field_id_of(schema_entry)
        if not field_id:
            return False
        response = self._request(
            "PATCH", f"{self.fields_url}/{field_id}", json={"type": expected}
        )
        if not response.ok:
            return False
        print(
            f"[OK] Updated field '{name}' type in Airtable from "
            f"{field_type_of(schema_entry)} to {expected}"
        )
        return True

    def ensure_fields(self, required: dict[str, str]) -> None:
        """Create missing columns and reconcile any whose type is wrong."""
        existing = self.table_fields()

        conflicts: list[str] = []
        for name, expected in required.items():
            if name not in existing:
                continue
            actual = field_type_of(existing[name])
            if type_is_compatible(actual, expected):
                continue
            if self._retype_field(name, existing[name], expected):
                existing[name] = {"id": field_id_of(existing[name]), "type": expected}
                continue
            readable = "Single line text" if expected == "singleLineText" else expected
            conflicts.append(
                f"'{name}' is currently set to '{actual}' in Airtable. "
                f"Please change this column's type in Airtable to '{readable}'."
            )
        if conflicts:
            raise AutomationError(
                "Airtable field type conflict:\n" + "\n".join(conflicts)
            )

        missing = [(name, kind) for name, kind in required.items() if name not in existing]
        if missing:
            print(f"[INFO] Creating {len(missing)} missing Airtable product fields...")
            for position, (name, kind) in enumerate(missing, start=1):
                response = self._request(
                    "POST", self.fields_url, json={"name": name, "type": kind}
                )
                if not response.ok:
                    raise response_error(response, f"Create Airtable field {name}")
                existing[name] = {"id": response.json().get("id"), "type": kind}
                print(f"[OK] Created field {name} ({position}/{len(missing)})")
        else:
            print("[OK] Airtable product fields are ready")

        self._schema = existing

    def ensure_single_select_options(
        self,
        field_name: str,
        choices: Sequence[str],
    ) -> None:
        """Ensure an automation-owned single-select field exists and has compatible type.

        Airtable Metadata API does not allow updating choices on an existing singleSelect field
        via PATCH (returns 422). Instead, missing choices are dynamically created on the fly
        when records are created/updated with typecast=True.
        """
        existing = self.table_fields()
        entry = existing.get(field_name)
        if entry is None:
            response = self._request(
                "POST",
                self.fields_url,
                json={
                    "name": field_name,
                    "type": "singleSelect",
                    "options": {"choices": [{"name": value} for value in choices]},
                },
            )
            if not response.ok:
                raise response_error(response, f"Create Airtable single select {field_name}")
            self._schema = None
            return
        if field_type_of(entry) not in ("singleSelect", "multipleSelects"):
            raise AutomationError(
                f"Airtable field type conflict: '{field_name}' must be singleSelect, "
                f"found {field_type_of(entry)}"
            )
        self._schema = existing

    def ensure_product_fields(
        self, items_per_row: int = DEFAULT_ITEMS_PER_ROW
    ) -> None:
        """Ensure product columns exist for slots only if no equivalent field exists."""
        existing = self.known_field_names()
        required: dict[str, str] = {}
        for slot in range(items_per_row):
            f_field = furniture_field(slot)
            if not any(f in existing for f in (f_field, f"Furniture Item{slot+1}", f"Furniture Item {slot+1}", "Furniture Item")):
                required[f_field] = "multipleAttachments"

            s_field = sku_field(slot)
            if not any(f in existing for f in (s_field, f"SKU{slot+1}", f"SKU {slot+1}", "SKU", "Legacy SKU")):
                required[s_field] = "multilineText"

            n_field = item_name_field(slot)
            if not any(f in existing for f in (n_field, f"Item Name{slot+1}", f"Item Name {slot+1}", "Item Name")):
                required[n_field] = "singleLineText"

        if required:
            self.ensure_fields(required)

    # -- records ----------------------------------------------------------

    def list_records(self, fields: Sequence[str] | None = None) -> list[dict[str, Any]]:
        """Every record in the table, requesting only existing fields."""
        records: list[dict[str, Any]] = []
        offset = ""
        valid_fields = self._present(fields) if fields else []
        while True:
            params: list[tuple[str, str]] = [("pageSize", str(PAGE_SIZE))]
            if valid_fields:
                params.extend(("fields[]", name) for name in valid_fields)
            if offset:
                params.append(("offset", offset))
            response = self._request(
                "GET", self.records_url, params=params, retry_server_errors=True
            )
            if not response.ok:
                raise response_error(response, "Airtable inventory lookup")
            payload = response.json()
            records.extend(payload.get("records", []))
            offset = str(payload.get("offset") or "")
            if not offset:
                return records

    def get_record(self, record_id: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            f"{self.records_url}/{record_id}",
            retry_server_errors=True,
        )
        if not response.ok:
            raise response_error(response, f"Read Airtable record {record_id}")
        return response.json()

    def _present(self, names: Iterable[str]) -> list[str]:
        known = self.known_field_names()
        return [name for name in names if name in known]

    def inventory_records(self) -> list[dict[str, Any]]:
        """Records carrying the SKU and photo fields a scrape needs to dedupe."""
        possible = [LEGACY_SKU_FIELD, ITEM_NAME_FIELD]
        for slot in range(SLOT_COUNT):
            possible.extend([
                self.resolve_slot_field("SKU", slot),
                self.resolve_slot_field("Furniture Item", slot),
                self.resolve_slot_field("Interior", slot),
                self.resolve_slot_field("Item Name", slot),
                self.resolve_slot_field("Product Type", slot),
                self.resolve_slot_field("Measurement", slot),
                f"SKU{slot+1}",
                f"Furniture Item{slot+1}",
                f"Interior{slot+1}",
                f"Item Name{slot+1}",
                f"Product Type{slot+1}",
                f"Measurement{slot+1}",
            ])
        fields = self._present(possible)
        return self.list_records(fields)

    def load_inventory(self) -> tuple[set[str], list[IncompleteSlot]]:
        self._inventory_records = self.inventory_records()
        existing_skus, incomplete = inventory_from_records(self._inventory_records)
        print(
            f"[OK] Found {len(existing_skus)} stored SKUs and "
            f"{len(incomplete)} incomplete attachment slots"
        )
        return existing_skus, incomplete

    def available_product_slots(self, items_per_row: int) -> list[AvailableSlot]:
        """Entirely empty slots that may be filled without moving old data."""
        records = (
            self._inventory_records
            if self._inventory_records is not None
            else self.inventory_records()
        )
        return available_slots_from_records(records, items_per_row)

    def update_records(self, updates: Sequence[tuple[str, dict[str, Any]]]) -> None:
        """Patch fields on existing rows, in Airtable's 10-per-call batches."""
        records = [{"id": record_id, "fields": fields} for record_id, fields in updates]
        for start in range(0, len(records), 10):
            batch = records[start : start + 10]
            response = self._request(
                "PATCH", self.records_url, json={"records": batch, "typecast": True}
            )
            if not response.ok:
                raise response_error(response, "Batch update Airtable records")
            print(f"[OK] Updated {len(batch)} records")

    def resolve_slot_field(self, base_name: str, slot: int) -> str:
        """Find the existing field name on Airtable for a given base field and slot."""
        indexed = f"{base_name}{slot + 1}"
        unindexed = base_name if slot == 0 else indexed
        if self._schema is not None:
            if indexed in self._schema:
                return indexed
            if unindexed in self._schema:
                return unindexed
        return unindexed

    def create_product_record(self, item: Any) -> str:
        """Create one row holding one or more products, returning its id."""
        items = item if isinstance(item, list) else [item]
        # Optional columns are only skipped when the schema is known to lack
        # them; an unfetched schema is not evidence of absence.
        known = set(self._schema) if self._schema is not None else None

        def writable(name: str) -> bool:
            return known is None or name in known

        fields: dict[str, Any] = {}
        for slot, product in enumerate(items):
            s_field = self.resolve_slot_field("SKU", slot)
            n_field = self.resolve_slot_field("Item Name", slot)
            pt_field = self.resolve_slot_field("Product Type", slot)
            m_field = self.resolve_slot_field("Measurement", slot)

            name = str(getattr(product, "item_name", "") or "").strip()
            ptype = str(getattr(product, "product_type", "") or "").strip()
            display_name = f"{name} | {ptype}" if ptype and ptype.lower() not in name.lower() else name

            fields[s_field] = product.sku
            fields[n_field] = display_name
            if product.product_type and writable(pt_field):
                fields[pt_field] = product.product_type
            if product.measurement and writable(m_field):
                fields[m_field] = product.measurement

        if writable("Status"):
            status_entry = self._schema.get("Status") if self._schema else None
            choices = status_entry.get("choices", []) if isinstance(status_entry, dict) else []
            if choices:
                matched = next((c for c in choices if c.casefold() == "standby".casefold()), None)
                if matched:
                    fields["Status"] = matched
            else:
                fields["Status"] = "Standby"

        skus = ", ".join(product.sku for product in items)
        response = self._request("POST", self.records_url, json={"fields": fields})
        if not response.ok:
            raise response_error(
                response, f"Create Airtable product record for {skus}"
            )
        record_id = response.json()["id"]
        print(f"[OK] Created product record {record_id}: {skus}")
        return record_id

    def create_empty_record(self) -> str:
        """Create a blank row for an attachment-only scrape."""
        return self.create_record({})

    def create_record(self, fields: dict[str, Any], *, typecast: bool = True) -> str:
        """Create one row with exactly the supplied fields, returning its id."""
        payload: dict[str, Any] = {"fields": fields}
        if typecast:
            payload["typecast"] = True
        response = self._request("POST", self.records_url, json=payload)
        if not response.ok:
            raise response_error(response, "Create Airtable record")
        record_id = response.json()["id"]
        written = ", ".join(fields) if fields else "no initial fields"
        print(f"[OK] Created product record {record_id} ({written})")
        return record_id

    def delete_record(self, record_id: str) -> None:
        """Delete a row created by this client after its attachment upload fails."""
        response = self._request("DELETE", f"{self.records_url}/{record_id}")
        if not response.ok:
            raise response_error(
                response, f"Delete incomplete Airtable record {record_id}"
            )
        print(f"[OK] Removed incomplete product record {record_id}")

    def assign_product_slots(
        self,
        record_id: str,
        assignments: Sequence[tuple[int, Any]],
    ) -> None:
        """Write new product metadata into empty slots on an existing row."""
        known = set(self._schema) if self._schema is not None else None

        def writable(name: str) -> bool:
            return known is None or name in known

        fields: dict[str, Any] = {}
        for slot, product in assignments:
            s_field = self.resolve_slot_field("SKU", slot)
            n_field = self.resolve_slot_field("Item Name", slot)
            pt_field = self.resolve_slot_field("Product Type", slot)
            m_field = self.resolve_slot_field("Measurement", slot)

            name = str(getattr(product, "item_name", "") or "").strip()
            ptype = str(getattr(product, "product_type", "") or "").strip()
            display_name = f"{name} | {ptype}" if ptype and ptype.lower() not in name.lower() else name

            fields[s_field] = product.sku
            fields[n_field] = display_name
            if product.product_type and writable(pt_field):
                fields[pt_field] = product.product_type
            if product.measurement and writable(m_field):
                fields[m_field] = product.measurement
        self.update_records([(record_id, fields)])

    def upload_attachment(
        self,
        record_id: str,
        field_name: str,
        downloaded: Any,
        filename: str,
    ) -> None:
        if hasattr(downloaded, "path"):
            path = Path(downloaded.path)
            content_type = getattr(downloaded, "content_type", "image/jpeg")
        else:
            path = Path(downloaded)
            import mimetypes
            content_type = mimetypes.guess_type(filename or path.name)[0] or "image/jpeg"

        if not path.is_file():
            raise FileNotFoundError(f"Downloaded file does not exist: {path}")
        fields_map = self.table_fields()
        field_target = fields_map.get(field_name, {}).get("id") or field_name
        url = (
            f"{CONTENT_BASE}/{self.base_id}/{record_id}/"
            f"{quote(field_target, safe='')}/uploadAttachment"
        )
        payload = {
            "contentType": content_type,
            "file": base64.b64encode(path.read_bytes()).decode("ascii"),
            "filename": filename,
        }
        response = self._request("POST", url, json=payload)
        if not response.ok:
            raise response_error(response, f"Upload {filename} to {field_name}")

    def clear_attachment_field(self, record_id: str, field_name: str) -> None:
        """Clear an attachment field before replacing its generated output."""
        self.update_records([(record_id, {field_name: []})])
