from __future__ import annotations

import base64
import csv
from datetime import datetime, timezone, timedelta
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests

from .config import CONTROL_FIELDS
from .errors import AutomationError
from .http import request_with_retry, response_error
from .models import Attachment, LocalImage, ProductRecord, TableConfig

PHT_TIMEZONE = timezone(timedelta(hours=8))


def current_pht_timestamp() -> str:
    """Return current Philippine Time (PHT, UTC+8) in ISO 8601 format."""
    return datetime.now(PHT_TIMEZONE).isoformat()


COMPLETION_STATUSES = {
    "complete",
    "completed",
    "done",
    "already attached a room interior",
}


def inject_generated_timestamp(fields: dict[str, Any]) -> dict[str, Any]:
    """Ensure 'Date and Time Generated' is stamped with current PHT time on completion."""
    updated = dict(fields)
    status_str = str(updated.get("Status") or "").strip().lower()
    if status_str in COMPLETION_STATUSES:
        updated["Date and Time Generated"] = current_pht_timestamp()
    elif "Date and Time" in updated and "Date and Time Generated" not in updated:
        updated["Date and Time Generated"] = updated.pop("Date and Time")
    return updated


class AirtableClient:
    API_BASE = "https://api.airtable.com/v0"
    CONTENT_BASE = "https://content.airtable.com/v0"

    def __init__(
        self,
        token: str,
        base_id: str,
        table: TableConfig,
        session: requests.Session | None = None,
    ):
        self.token = token
        self.base_id = base_id
        self.table = table
        self.session = session or requests.Session()
        self._fields: dict[str, str] | None = None

    @property
    def table_id(self) -> str:
        return self.table.table_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("headers", self._headers())
        response = request_with_retry(
            self.session,
            method,
            url,
            retry_non_idempotent=True,
            **kwargs,
        )
        return response

    def schema(self, *, refresh: bool = False) -> dict[str, str]:
        if self._fields is not None and not refresh:
            return dict(self._fields)
        url = f"{self.API_BASE}/meta/bases/{self.base_id}/tables"
        response = self._request("GET", url)
        if not response.ok:
            raise response_error(response, f"Airtable schema lookup for {self.table.label}")
        for table in response.json().get("tables", []):
            if table.get("id") == self.table_id:
                self._fields = {
                    str(field["name"]): str(field["type"])
                    for field in table.get("fields", [])
                }
                return dict(self._fields)
        raise AutomationError(f"Airtable table not found: {self.table_id}")

    def schema_conflicts(self, required: dict[str, str]) -> list[str]:
        existing = self.schema()
        compatible = {
            "singleLineText": {"singleLineText", "multilineText"},
            "multilineText": {"singleLineText", "multilineText"},
        }
        conflicts = []
        for name, expected in required.items():
            actual = existing.get(name)
            if actual and actual not in compatible.get(expected, {expected}):
                conflicts.append(f"{name}: expected {expected}, found {actual}")
        return conflicts

    def ensure_fields(self, required: dict[str, str], *, execute: bool) -> list[str]:
        conflicts = self.schema_conflicts(required)
        if conflicts:
            raise AutomationError(
                f"Airtable schema conflicts in {self.table.label}: " + "; ".join(conflicts)
            )
        existing = self.schema()
        missing = [name for name in required if name not in existing]
        if not execute:
            return missing
        url = f"{self.API_BASE}/meta/bases/{self.base_id}/tables/{self.table_id}/fields"
        for name in missing:
            response = self._request(
                "POST",
                url,
                json={"name": name, "type": required[name]},
            )
            if not response.ok:
                raise response_error(response, f"Create Airtable field {name}")
        if missing:
            self.schema(refresh=True)
        return missing

    def ensure_automation_schema(
        self,
        final_fields: Iterable[str],
        *,
        execute: bool,
    ) -> list[str]:
        existing = set(self.schema())
        required: dict[str, str] = {}

        has_sku = any(f in existing for f in ("SKU", "SKU1", "SKU 1", "Legacy SKU"))
        has_name = any(f in existing for f in ("Item Name", "Item Name1", "Item Name 1"))
        has_furniture = any(f in existing for f in ("Furniture Item", "Furniture Item1", "Furniture Item 1"))

        # Only require generic columns if table has no product columns at all
        if not (has_sku or has_name or has_furniture):
            required["SKU"] = "singleLineText"
            required["Item Name"] = "singleLineText"
            required["Furniture Item"] = "multipleAttachments"

        # Only add final field if none of the workflow's final output fields exist in Airtable
        has_any_final = any(f in existing for f in final_fields)
        if not has_any_final:
            for field in final_fields:
                if field not in existing:
                    required[field] = "multipleAttachments"
                    break

        if not required:
            return []
        return self.ensure_fields(required, execute=execute)

    def list_records(
        self,
        *,
        fields: Iterable[str] | None = None,
        formula: str | None = None,
        sort_field: str | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self.API_BASE}/{self.base_id}/{self.table_id}"
        requested = [field for field in (fields or []) if field in self.schema()]
        records: list[dict[str, Any]] = []
        offset = ""
        while True:
            params: list[tuple[str, str]] = [("pageSize", "100")]
            params.extend(("fields[]", field) for field in requested)
            if formula:
                params.append(("filterByFormula", formula))
            if sort_field:
                params.extend(
                    [("sort[0][field]", sort_field), ("sort[0][direction]", "asc")]
                )
            if offset:
                params.append(("offset", offset))
            response = self._request("GET", url, params=params)
            if not response.ok:
                raise response_error(response, f"List Airtable records in {self.table.label}")
            payload = response.json()
            records.extend(payload.get("records", []))
            offset = str(payload.get("offset") or "")
            if not offset:
                break
        records.sort(key=lambda item: str(item.get("id") or ""))
        return records

    def get_record(self, record_id: str) -> dict[str, Any]:
        url = f"{self.API_BASE}/{self.base_id}/{self.table_id}/{record_id}"
        response = self._request("GET", url)
        if not response.ok:
            raise response_error(response, f"Read Airtable record {record_id}")
        return response.json()

    def update_record(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.API_BASE}/{self.base_id}/{self.table_id}/{record_id}"
        req_fields = inject_generated_timestamp(fields)
        response = self._request("PATCH", url, json={"fields": req_fields})
        if not response.ok and ("Date and Time Generated" in response.text or "Date and Time" in response.text):
            # Fallback attempt 1: Try "Date and Time" if "Date and Time Generated" was rejected
            fallback_fields = dict(req_fields)
            if "Date and Time Generated" in fallback_fields:
                fallback_fields["Date and Time"] = fallback_fields.pop("Date and Time Generated")
                response = self._request("PATCH", url, json={"fields": fallback_fields})
            # Fallback attempt 2: Strip date fields if table does not support either
            if not response.ok and ("Date and Time Generated" in response.text or "Date and Time" in response.text):
                clean_fields = {
                    k: v for k, v in req_fields.items()
                    if k not in ("Date and Time Generated", "Date and Time")
                }
                response = self._request("PATCH", url, json={"fields": clean_fields})
        if not response.ok:
            raise response_error(response, f"Update Airtable record {record_id}")
        
        ret = response.json()
        try:
            f = ret.get("fields", {})
            if not f.get("Foreign Key ID") and f.get("ID") is not None:
                from .foreign_key import generate_foreign_key
                fk = generate_foreign_key(self.table_id, f["ID"])
                patch_resp = self._request("PATCH", url, json={"fields": {"Foreign Key ID": fk}, "typecast": True})
                if patch_resp.ok:
                    ret = patch_resp.json()
        except Exception:
            pass

        return ret

    def update_records(
        self,
        updates: Iterable[tuple[str, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        records = [
            {"id": record_id, "fields": fields}
            for record_id, fields in updates
        ]
        if not records:
            return []
        results: list[dict[str, Any]] = []
        url = f"{self.API_BASE}/{self.base_id}/{self.table_id}"
        for start in range(0, len(records), 10):
            batch = records[start : start + 10]
            prepared_batch = [
                {"id": item["id"], "fields": inject_generated_timestamp(item.get("fields", {}))}
                for item in batch
            ]

            response = self._request(
                "PATCH",
                url,
                json={"records": prepared_batch},
            )
            if not response.ok and ("Date and Time Generated" in response.text or "Date and Time" in response.text):
                # Fallback attempt 1: Try "Date and Time" instead of "Date and Time Generated"
                fallback_batch = []
                for item in prepared_batch:
                    f_fields = dict(item.get("fields", {}))
                    if "Date and Time Generated" in f_fields:
                        f_fields["Date and Time"] = f_fields.pop("Date and Time Generated")
                    fallback_batch.append({"id": item["id"], "fields": f_fields})
                response = self._request(
                    "PATCH",
                    url,
                    json={"records": fallback_batch},
                )
                # Fallback attempt 2: Strip date fields completely so batch succeeds
                if not response.ok and ("Date and Time Generated" in response.text or "Date and Time" in response.text):
                    clean_batch = [
                        {
                            "id": item["id"],
                            "fields": {
                                k: v for k, v in item.get("fields", {}).items()
                                if k not in ("Date and Time Generated", "Date and Time")
                            },
                        }
                        for item in prepared_batch
                    ]
                    response = self._request(
                        "PATCH",
                        url,
                        json={"records": clean_batch},
                    )
            if not response.ok:
                raise response_error(
                    response,
                    f"Batch update Airtable records in {self.table.label}",
                )
            
            batch_result = response.json().get("records", [])
            try:
                records_to_patch = []
                for rec in batch_result:
                    f = rec.get("fields", {})
                    if not f.get("Foreign Key ID") and f.get("ID") is not None:
                        from .foreign_key import generate_foreign_key
                        fk = generate_foreign_key(self.table_id, f["ID"])
                        records_to_patch.append({"id": rec["id"], "fields": {"Foreign Key ID": fk}})
                if records_to_patch:
                    patch_resp = self._request("PATCH", url, json={"records": records_to_patch, "typecast": True})
                    if patch_resp.ok:
                        patch_data = patch_resp.json().get("records", [])
                        patched_map = {r["id"]: r for r in patch_data}
                        for i, rec in enumerate(batch_result):
                            if rec["id"] in patched_map:
                                batch_result[i] = patched_map[rec["id"]]
            except Exception:
                pass

            results.extend(batch_result)
        return results

    def create_record(self, fields: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.API_BASE}/{self.base_id}/{self.table_id}"
        response = self._request("POST", url, json={"fields": fields})
        if not response.ok:
            raise response_error(response, f"Create Airtable record in {self.table.label}")
        
        ret = response.json()
        try:
            f = ret.get("fields", {})
            if not f.get("Foreign Key ID") and f.get("ID") is not None:
                from .foreign_key import generate_foreign_key
                fk = generate_foreign_key(self.table_id, f["ID"])
                patch_url = f"{url}/{ret['id']}"
                patch_resp = self._request("PATCH", patch_url, json={"fields": {"Foreign Key ID": fk}, "typecast": True})
                if patch_resp.ok:
                    ret = patch_resp.json()
        except Exception:
            pass

        return ret

    def upload_attachment(
        self,
        record_id: str,
        field_name: str,
        image: LocalImage,
    ) -> None:
        if not image.path.is_file():
            raise FileNotFoundError(image.path)
        content_type = image.content_type or mimetypes.guess_type(image.filename)[0] or "image/jpeg"
        encoded_field = quote(field_name, safe="")
        url = (
            f"{self.CONTENT_BASE}/{self.base_id}/{record_id}/"
            f"{encoded_field}/uploadAttachment"
        )
        payload = {
            "contentType": content_type,
            "file": base64.b64encode(image.path.read_bytes()).decode("ascii"),
            "filename": image.filename,
        }
        response = self._request("POST", url, json=payload)
        if not response.ok:
            raise response_error(response, f"Upload {image.filename} to {field_name}")

    def set_attachment_ids(
        self,
        record_id: str,
        field_name: str,
        attachment_ids: Iterable[str],
    ) -> None:
        attachments = [{"id": attachment_id} for attachment_id in attachment_ids]
        self.update_record(record_id, {field_name: attachments})

    def clear_attachment_field(self, record_id: str, field_name: str) -> None:
        self.update_record(record_id, {field_name: []})

    def verify_attachment_filenames(
        self,
        record_id: str,
        field_name: str,
        expected: list[str],
        *,
        attempts: int = 6,
        delay: float = 1.0,
    ) -> None:
        actual: list[str] = []
        for attempt in range(attempts):
            record = self.get_record(record_id)
            actual = [
                str(item.get("filename") or "")
                for item in record.get("fields", {}).get(field_name, [])
            ]
            if actual == expected:
                return
            if attempt < attempts - 1:
                time.sleep(delay)
        raise AutomationError(
            f"Airtable attachment verification failed for {record_id} / "
            f"{field_name}: expected {expected}, found {actual}"
        )

    def remove_attachments_by_filename(
        self,
        record_id: str,
        field_name: str,
        filenames: set[str],
    ) -> None:
        record = self.get_record(record_id)
        current = record.get("fields", {}).get(field_name, [])
        keep_ids = [
            item["id"]
            for item in current
            if item.get("id") and str(item.get("filename") or "") not in filenames
        ]
        self.set_attachment_ids(record_id, field_name, keep_ids)

    def download_attachment(self, attachment: Attachment, destination: Path) -> LocalImage:
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = request_with_retry(self.session, "GET", attachment.url)
        if not response.ok:
            raise response_error(response, f"Download Airtable attachment {attachment.filename}")
        destination.write_bytes(response.content)
        content_type = (response.headers.get("Content-Type") or attachment.content_type).split(";")[0]
        return LocalImage(destination, destination.name, content_type or "image/jpeg")

    @staticmethod
    def product_from_record(table: TableConfig, record: dict[str, Any]) -> ProductRecord | None:
        fields = record.get("fields", {})
        attachments = (
            fields.get("Furniture Item")
            or fields.get("Furniture Item1")
            or []
        )
        if not attachments:
            return None
        raw_name = str(
            fields.get("Item Name") or fields.get("Item Name1") or ""
        ).strip()
        item_name = raw_name
        product_type = str(
            fields.get("Product Type") or fields.get("Product Type1") or ""
        ).strip()
        if "|" in raw_name:
            left, right = (part.strip() for part in raw_name.split("|", 1))
            item_name = left
            product_type = product_type or right
        return ProductRecord(
            table=table,
            record_id=str(record["id"]),
            sku=str(fields.get("SKU") or fields.get("SKU1") or "").strip(),
            item_name=item_name,
            product_type=product_type,
            measurement=str(fields.get("Measurement") or fields.get("Measurement1") or "").strip(),
            furniture=Attachment.from_airtable(attachments[0]),
            fields=fields,
        )

    def list_products(self) -> list[ProductRecord]:
        fields = [
            "SKU",
            "SKU1",
            "Item Name",
            "Item Name1",
            "Item Name2",
            "Item Name3",
            "Product Type",
            "Product Type1",
            "Measurement",
            "Measurement1",
            "Furniture Item",
            "Furniture Item1",
            "Furniture Item2",
            "Furniture Item3",
            "Furniture Item4",
            "This or That Layout",
            "Thumbnail Platform",
            "Solo Platform",
            "Interior",
            "Interior1",
            "Interior2",
            "Interior3",
            "Interiro3",
            "Interior4",
            "Furniture Item copy",
            "Furniture Item copy1",
            "Furniture Item copy2",
            "Furniture Item copy3",
            "CTA Interior",
            "CTA Layout",
            "CTA Blended",
            "CTA Blended Image",
            "CTA Prompt Blending",
            "CTA Converted Blended",
            "Prompt",
            "Prompt1",
            "Prompt2",
            "Prompt3",
            "Prompt4",
            "How would You Layout",
            "Double Tap",
            "Style This Blended",
            "Double Tap Converted",
            "STORY - Style This? (4)",
            "Blending Prompt2",
            "Blending Prompt3",
            "Myth Layout",
            "Fact Layout",
            "Debunk Myth Thumbnail",
            "Debunk Layout",
            "Outro Thumbnail",
            "Outro",
            "Logo",
            "Overlay Logo",
            "Interior Generated Photo",
            "Interior Generated",
            "Layout Tips and Edu Stories",
            "Tips and Edu Stories Blended",
            "Tips Edu layout",
            "Tips Edu Blended Image",
            "Tips and Edu Layout1",
            "Tips and Edu Layout2",
            "Tips and Edu Layout3",
            "Tips and Edu Blended",
            "Tips and Edu Feeds",
            "Tips and Edu Stories",
            "1 Product 3 Style Blended",
            "REEL - 1 Product, 3 Styles",
            "Music1",
            "Collection Categ Story Layout",
            "Collection Category Layout",
            "Story Collection Categ Blended",
            "Collection Category Blended",
            "Collection Category Blended Image1",
            "Collection Category Blended Image2",
            "Collection Category Blended Image3",
            "Collection Category Converted",
            "STORY - Collection Category (1)",
            "Product Type2",
            "Product Type3",
            "Item Name4",
            "Moodboard Watermark",
            "Moodboard Layout",
            "Moodboard #1 Blended",
            "Moodboard Watermark Converted",
            "Moodboard Layout Converted",
            "Moodboard #1 Layout Closeup",
            "Moodboard Closeup Photo",
            "Moodboard Closeup Photo Prompt",
            "Converted Moodboard",
            "Converted Moodboard Prompt",
            "Moodboard Watermark Prompt",
            "Moodboard Layout Prompt",
            "FEED - Moodboard #1 Feed (3)",
            # Selection state. Airtable only returns the columns named here, so
            # anything the state machine reads has to be requested explicitly --
            # omitting these made every record look unassigned and unfinished.
            "Status",
            "Content Status",
            "Content Assignment",
            "Content Role",
            "Content Run ID",
            "Content State",
            "Content Error",
            *CONTROL_FIELDS,
        ]
        records = self.list_records(fields=fields)
        products = [
            product
            for record in records
            if (product := self.product_from_record(self.table, record)) is not None
        ]
        return products

    def export_backup(self, destination_dir: Path) -> tuple[Path, Path, list[dict[str, Any]]]:
        destination_dir.mkdir(parents=True, exist_ok=True)
        records = self.list_records()
        json_path = destination_dir / f"{self.table.code}.json"
        csv_path = destination_dir / f"{self.table.code}.csv"
        json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        field_names = sorted(
            {name for record in records for name in record.get("fields", {}).keys()}
        )
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", *field_names])
            writer.writeheader()
            for record in records:
                fields = record.get("fields", {})
                writer.writerow(
                    {
                        "record_id": record.get("id", ""),
                        **{
                            name: json.dumps(fields.get(name, ""), ensure_ascii=False)
                            if isinstance(fields.get(name), (list, dict))
                            else fields.get(name, "")
                            for name in field_names
                        },
                    }
                )
        return json_path, csv_path, records


def fetch_status_breakdown(
    token: str = "", base_id: str = "", table_id: str = "", timeout: float = 6.0
) -> dict[str, int]:
    """Fetch live counts of P (Posted), S (Scheduled), C (Complete), D (Discard), and FM (For Manual) from Airtable."""
    import os
    # Smart detection: if first argument is a table_id (e.g. starts with "tbl")
    if token and token.startswith("tbl") and not table_id:
        table_id = token
        token = ""

    if not token or not base_id:
        try:
            from .config import load_settings
            settings = load_settings()
            token = token or settings.airtable_token
            base_id = base_id or settings.airtable_base_id
        except Exception:
            token = token or os.getenv("AIRTABLE_API_KEY") or os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN") or ""
            base_id = base_id or os.getenv("AIRTABLE_BASE_ID") or "appDM0jUDsaiThtR3"

    counts = {"P": 0, "S": 0, "C": 0, "D": 0, "FM": 0}
    if not token or not base_id or not table_id:
        return counts

    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "fields[]": "Status",
        "pageSize": 100,
    }
    offset = None
    try:
        while True:
            req_params = dict(params)
            if offset:
                req_params["offset"] = offset
            resp = requests.get(url, headers=headers, params=req_params, timeout=timeout)
            if not resp.ok:
                break
            data = resp.json()
            for rec in data.get("records", []):
                raw = str(rec.get("fields", {}).get("Status") or "").strip().lower()
                norm = " ".join(raw.split())
                if norm in ("posted", "processing", "pending", "in progress"):
                    counts["P"] += 1
                elif norm in ("scheduled", "schedule"):
                    counts["S"] += 1
                elif norm in ("complete", "completed", "done", "already attached a room interior"):
                    counts["C"] += 1
                elif norm in ("discard", "discarded"):
                    counts["D"] += 1
                elif norm in ("for manual", "for  manual", "minor revision", "minor revisions", "fm"):
                    counts["FM"] += 1
            offset = data.get("offset")
            if not offset:
                break
    except Exception:
        pass
    return counts


def fetch_multiple_tables_status_breakdown(
    token: str, base_id: str, table_ids: list[str], max_workers: int = 8
) -> dict[str, dict[str, int]]:
    """Fetch status breakdown in parallel across multiple Airtable tables."""
    from concurrent.futures import ThreadPoolExecutor

    results: dict[str, dict[str, int]] = {}
    if not table_ids:
        return results

    with ThreadPoolExecutor(max_workers=min(len(table_ids), max_workers)) as pool:
        future_map = {
            pool.submit(fetch_status_breakdown, token, base_id, tid): tid
            for tid in table_ids
        }
        for future in future_map:
            tid = future_map[future]
            try:
                results[tid] = future.result()
            except Exception:
                results[tid] = {"P": 0, "C": 0, "D": 0, "FM": 0}
    return results
