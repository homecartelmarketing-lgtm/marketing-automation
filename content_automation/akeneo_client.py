from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import quote

import requests

from .http import request_with_retry, response_error
from .media import DownloadedMedia, download_to_temp_file, media_extension


# Attributes requested for every product search. Akeneo installs disagree on
# casing, so both spellings are asked for and `first_attribute` picks whichever
# came back populated.
PRODUCT_SEARCH_ATTRIBUTES = (
    "name,image,Style2,measurement,Measurement,"
    "width,height,length,diameter,dimension,description,Description,"
    "Costing,Selling_Price"
)

# Narrower set for single-product lookups, where only identity is needed.
PRODUCT_DETAIL_ATTRIBUTES = "name,image,Style2"

PRODUCT_PAGE_SIZE = 100


class AkeneoClient:
    """Akeneo PIM REST client.

    Authentication is lazy: any call that needs a token will fetch one, and a
    401 mid-session triggers exactly one silent re-authentication before the
    error is surfaced.
    """

    def __init__(
        self,
        host: str,
        client_id: str,
        secret: str,
        username: str,
        password: str,
        channel_name: str = "",
        session: requests.Session | None = None,
    ):
        self.host = host.rstrip("/")
        self.client_id = client_id
        self.secret = secret
        self.username = username
        self.password = password
        self.channel_name = channel_name
        self.session = session or requests.Session()
        self.token = ""

    def authenticate(self) -> str:
        response = request_with_retry(
            self.session,
            "POST",
            f"{self.host}/api/oauth/v1/token",
            retry_non_idempotent=True,
            auth=(self.client_id, self.secret),
            json={
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            },
        )
        if not response.ok:
            raise response_error(response, "Akeneo authentication")
        self.token = str(response.json().get("access_token") or "")
        if not self.token:
            raise response_error(response, "Akeneo authentication returned no token")
        return self.token

    def _authorized(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Issue a request, authenticating first and retrying once on 401."""
        if not self.token:
            self.authenticate()
        headers = dict(kwargs.pop("headers", None) or {})
        headers["Authorization"] = f"Bearer {self.token}"
        response = request_with_retry(
            self.session, method, url, headers=headers, **kwargs
        )
        if response.status_code == 401:
            self.authenticate()
            headers["Authorization"] = f"Bearer {self.token}"
            response = request_with_retry(
                self.session, method, url, headers=headers, **kwargs
            )
        return response

    def _product_url(self, sku: str) -> str:
        return f"{self.host}/api/rest/v1/products/{quote(sku, safe='')}"

    def get_product(self, sku: str) -> dict[str, Any]:
        """Fetch one product, raising if it is missing."""
        params: dict[str, Any] = {
            "attributes": PRODUCT_DETAIL_ATTRIBUTES,
        }
        if self.channel_name:
            params["scope"] = self.channel_name
        response = self._authorized(
            "GET",
            self._product_url(sku),
            params=params,
        )
        if not response.ok:
            raise response_error(response, f"Akeneo product {sku}")
        return response.json()

    def find_product(self, sku: str) -> dict[str, Any] | None:
        """Fetch one product, returning None when Akeneo has no such SKU."""
        params: dict[str, Any] = {
            "attributes": PRODUCT_DETAIL_ATTRIBUTES,
        }
        if self.channel_name:
            params["scope"] = self.channel_name
        response = self._authorized(
            "GET",
            self._product_url(sku),
            params=params,
        )
        if response.status_code == 404:
            return None
        if not response.ok:
            raise response_error(response, f"Akeneo product {sku}")
        return response.json()

    def fetch_products(self, search_query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch every product matching a search query, following pagination."""
        url = f"{self.host}/api/rest/v1/products"
        params: dict[str, Any] = {
            "search": json.dumps(search_query),
            "attributes": PRODUCT_SEARCH_ATTRIBUTES,
            "limit": PRODUCT_PAGE_SIZE,
        }
        if self.channel_name:
            params["scope"] = self.channel_name
        products: list[dict[str, Any]] = []

        while url:
            response = self._authorized("GET", url, params=params)
            if not response.ok:
                raise response_error(response, "Akeneo product search")
            payload = response.json()
            products.extend(payload.get("_embedded", {}).get("items", []))
            # Follow-up pages carry their query in the returned href already.
            url = (payload.get("_links", {}).get("next") or {}).get("href", "")
            params = {}

        return products

    def download_media(self, media_code: str) -> DownloadedMedia:
        """Download a product image to a temp file."""
        url = (
            f"{self.host}/api/rest/v1/media-files/"
            f"{quote(media_code, safe='/')}/download"
        )
        response = self._authorized("GET", url, stream=True)
        return download_to_temp_file(
            response,
            prefix="akeneo_",
            suffix=media_extension(media_code),
            context=f"Akeneo media {media_code}",
        )


def first_attribute(product: dict[str, Any], *codes: str) -> Any:
    values = product.get("values", {})
    for code in codes:
        for entry in values.get(code, []):
            data = entry.get("data")
            if data is not None and str(data).strip():
                return data
    return None


def split_item_name(raw_name: str, fallback_product_type: str = "") -> tuple[str, str]:
    raw_name = str(raw_name or "").strip()
    if "|" not in raw_name:
        return raw_name, str(fallback_product_type or "").strip()
    item_name, product_type = (part.strip() for part in raw_name.split("|", 1))
    return item_name, product_type or str(fallback_product_type or "").strip()


_UNIT_SUFFIXES = {
    "centimeter": "cm",
    "millimeter": "mm",
    "meter": "m",
    "inch": "in",
}

_DIMENSION_ATTRIBUTES = (
    ("W", ("Width", "width")),
    ("L", ("Length", "length")),
    ("D", ("Diameter", "diameter")),
    ("H", ("Height", "height")),
)

_BLOCK_TAGS = re.compile(r"(?i)<br\s*/?>|</p>|</li>|</div>")
_ANY_TAG = re.compile(r"<[^>]+>")
_INLINE_LABEL = re.compile(
    r"(?i)(?:dimension|dimensions|measurement|measurements|size|spec|specs)\s*[:\-]\s*(.+)"
)
_HEADER_ONLY = re.compile(
    r"(?i)^(?:dimension|dimensions|measurement|measurements|size)\s*[:\-]?$"
)
_NEXT_SECTION = re.compile(
    r"(?i)^(?:specifications|specs|description|material|color|weight|voltage|wattage|features)\b"
)
_AXIS_VALUE = re.compile(r"(?i)^(?:w|l|d|h|width|length|diameter|height)\s*[:\-]?\s*\d+")
_HAS_MEASURE = re.compile(r"(?i)\b(?:[WLDH]\s*\d+|\d+\s*(?:cm|mm|m|in))\b")
_AXIS_LABEL = re.compile(r"(?i)^(?:width|length|diameter|height)\s*[:\-]?\s*")
_HEIGHT_LINE = re.compile(r"(?i)^height\s*[:\-]\s*(.+)")
_DIMENSION_RUN = re.compile(
    r"(?i)\b(?:[WLDH]\s*\d+[\d\.]*\s*(?:cm|mm|m|in)?\s*[\*xX×\s]*)+"
    r"[WLDH]?\s*\d+[\d\.]*\s*(?:cm|mm|m|in)?\b"
)


def _text_lines(text: str) -> tuple[list[str], str]:
    """Flatten HTML into visible lines plus the whole stripped body."""
    clean = html.unescape(text)
    structured = _BLOCK_TAGS.sub("\n", clean)
    stripped = _ANY_TAG.sub(" ", structured)
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    return lines, stripped


def _dimensions_under_header(lines: list[str]) -> str:
    """Collect the run of dimension lines following a bare 'Dimensions:' header."""
    header_index = next(
        (i for i, line in enumerate(lines) if _HEADER_ONLY.match(line)), -1
    )
    if header_index == -1:
        return ""

    collected: list[str] = []
    for line in lines[header_index + 1 :]:
        starts_new_section = _NEXT_SECTION.match(line) and not _AXIS_VALUE.match(line)
        if starts_new_section and collected:
            break
        if _HAS_MEASURE.search(line) or _AXIS_LABEL.match(line):
            collected.append(line)
        elif collected:
            break
    return " x ".join(collected)


def extract_measurement_from_text(text: str) -> str:
    """Pull a measurement out of a free-text or HTML description."""
    if not text:
        return ""
    lines, stripped = _text_lines(text)

    for line in lines:
        if match := _INLINE_LABEL.search(line):
            if extracted := match.group(1).strip():
                return extracted

    if under_header := _dimensions_under_header(lines):
        return under_header

    for line in lines:
        if _HEIGHT_LINE.match(line):
            return line

    if match := _DIMENSION_RUN.search(stripped):
        return match.group(0).strip()

    return ""


def _format_dimension_value(data: Any) -> str:
    """Render one axis value, unpacking Akeneo's {amount, unit} metric shape."""
    if not isinstance(data, dict):
        return str(data).strip()
    amount = data.get("amount")
    if amount is None:
        return ""
    unit = str(data.get("unit") or "").lower()
    return f"{amount}{_UNIT_SUFFIXES.get(unit, unit)}"


def format_measurement(product: dict[str, Any]) -> str:
    """Best available measurement: direct attribute, then axes, then description."""
    direct = first_attribute(
        product, "measurement", "Measurement", "dimension", "dimensions", "size", "Size"
    )
    if direct is not None and str(direct).strip():
        return str(direct).strip()

    parts: list[str] = []
    for label, codes in _DIMENSION_ATTRIBUTES:
        data = first_attribute(product, *codes)
        if data is None:
            continue
        if value := _format_dimension_value(data):
            parts.append(f"{label} {value}")
    if parts:
        return " x ".join(parts)

    description = first_attribute(product, "description", "Description")
    if description is not None:
        return extract_measurement_from_text(str(description))

    return ""


def metadata_from_product(product: dict[str, Any]) -> dict[str, str]:
    raw_name = str(first_attribute(product, "name", "Name") or "")
    fallback_type = str(first_attribute(product, "Product_Type", "product_type", "Style2") or "")
    item_name, product_type = split_item_name(raw_name, fallback_type)
    return {
        "Item Name": item_name,
        "Product Type": product_type,
        "Measurement": format_measurement(product),
    }
