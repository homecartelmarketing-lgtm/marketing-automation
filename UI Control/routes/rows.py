"""Rows Inspector Blueprint - Fetch records from Airtable for deep linking and inspection.

Endpoint:
  GET /api/rows?table_id=<table_id>&status=<optional_status>
"""

from __future__ import annotations
from pathlib import Path
import sys
import time
from typing import Any

from flask import Blueprint, jsonify, request
import requests

CURRENT_DIR = Path(__file__).resolve().parent
MARKETING_DIR = CURRENT_DIR.parent.parent
if str(MARKETING_DIR) not in sys.path:
    sys.path.insert(0, str(MARKETING_DIR))

from routes.common import is_authorized
from content_automation.config import load_settings
from content_automation.foreign_key import generate_foreign_key

rows_bp = Blueprint("rows", __name__, url_prefix="/api/rows")

CACHE: dict[str, Any] = {}
CACHE_TTL = 10.0


@rows_bp.route("", methods=["GET"])
def get_rows():
    """Return rows for an Airtable table with Foreign Key IDs and direct deep links."""
    table_id = request.args.get("table_id", "").strip()
    status_filter = request.args.get("status", "").strip()
    force = request.args.get("refresh", "").lower() in ("true", "1")

    if not table_id:
        return jsonify({"status": "error", "error": "table_id is required"}), 400

    now = time.time()
    cache_key = f"{table_id}:{status_filter.lower()}"
    if not force and cache_key in CACHE:
        cached_entry = CACHE[cache_key]
        if now - cached_entry["time"] < CACHE_TTL:
            return jsonify({
                "status": "success",
                "cached": True,
                "table_id": table_id,
                "base_id": cached_entry["base_id"],
                "total": len(cached_entry["rows"]),
                "rows": cached_entry["rows"],
            })

    try:
        settings = load_settings(MARKETING_DIR / ".env")
        base_id = settings.airtable_base_id
        token = settings.airtable_token

        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"

        params: dict[str, Any] = {
            "pageSize": 100,
        }

        # Optional Status formula filter
        if status_filter:
            norm_status = status_filter.strip().lower()
            if norm_status == "p":
                params["filterByFormula"] = "{Status} = 'Posted'"
            elif norm_status == "s":
                params["filterByFormula"] = "OR({Status} = 'Scheduled', {Status} = 'Schedule')"
            elif norm_status == "c":
                params["filterByFormula"] = "OR({Status} = 'Complete', {Status} = 'Completed', {Status} = 'Done')"
            elif norm_status == "d":
                params["filterByFormula"] = "OR({Status} = 'Discard', {Status} = 'Discarded')"
            elif norm_status == "fm":
                params["filterByFormula"] = "OR({Status} = 'For Manual', {Status} = 'For  Manual', {Status} = 'Minor revision', {Status} = 'Minor Revision', {Status} = 'FM')"
            else:
                params["filterByFormula"] = f"LOWER({{Status}}) = '{norm_status}'"

        all_rows = []
        offset = None

        while True:
            req_params = dict(params)
            if offset:
                req_params["offset"] = offset

            resp = requests.get(url, headers=headers, params=req_params, timeout=12)
            if not resp.ok:
                return jsonify({
                    "status": "error",
                    "error": f"Airtable API error: {resp.status_code} {resp.text}",
                }), resp.status_code

            data = resp.json()
            records = data.get("records", [])

            for rec in records:
                rid = rec["id"]
                fields = rec.get("fields", {})
                row_id = fields.get("ID")
                fk_id = fields.get("Foreign Key ID")
                if not fk_id and row_id is not None:
                    fk_id = generate_foreign_key(table_id, row_id)

                furniture_attach = (
                    fields.get("Furniture Item")
                    or fields.get("Furniture Items")
                    or fields.get("Final Stamped Output")
                    or fields.get("Image")
                    or []
                )
                thumbnail_url = None
                if isinstance(furniture_attach, list) and furniture_attach:
                    first_att = furniture_attach[0]
                    if isinstance(first_att, dict):
                        thumbs = first_att.get("thumbnails", {})
                        thumbnail_url = thumbs.get("small", {}).get("url") or first_att.get("url")

                airtable_deep_link = f"https://airtable.com/{base_id}/{table_id}/{rid}"

                all_rows.append({
                    "record_id": rid,
                    "id": row_id,
                    "foreign_key_id": fk_id or f"ROW-{row_id or '?'}",
                    "sku": fields.get("SKU") or fields.get("Product SKU") or fields.get("sku") or "",
                    "item_name": fields.get("Item Name") or fields.get("Name") or fields.get("Product Name") or "",
                    "status": fields.get("Status") or "Standby",
                    "date_and_time": (
                        fields.get("Date and Time Generated")
                        or fields.get("Date and Time")
                        or fields.get("Date & Time")
                        or ""
                    ),
                    "thumbnail_url": thumbnail_url,
                    "airtable_url": airtable_deep_link,
                })

            offset = data.get("offset")
            if not offset:
                break

        # Sort descending by ID so newest rows appear first
        all_rows.sort(key=lambda x: (x["id"] if isinstance(x["id"], int) else 0), reverse=True)

        CACHE[cache_key] = {
            "time": now,
            "base_id": base_id,
            "rows": all_rows,
        }

        return jsonify({
            "status": "success",
            "cached": False,
            "table_id": table_id,
            "base_id": base_id,
            "total": len(all_rows),
            "rows": all_rows,
        })

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
