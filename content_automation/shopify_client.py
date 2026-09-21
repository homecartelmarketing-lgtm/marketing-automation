"""Shopify client for cross-checking products against published store inventory."""

from __future__ import annotations

import concurrent.futures
import email.utils
import json
import os
from pathlib import Path
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests


def _parse_retry_after(header_val: str | None) -> float | None:
    """Parse HTTP Retry-After header which can be integer/float seconds or RFC 2822/7231 date."""
    if not header_val:
        return None
    header_str = str(header_val).strip()
    try:
        return float(header_str)
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(header_str)
        diff = dt.timestamp() - time.time()
        return max(0.0, diff)
    except Exception:
        return None


DEFAULT_SHOPIFY_DOMAIN = (
    os.getenv("SHOPIFY_STORE_DOMAIN", "").strip()
    or os.getenv("SHOPIFY_DOMAIN", "").strip()
    or "homecartel.net"
)
SHOPIFY_CACHE_FILE = Path("output/cache/shopify_catalog_cache.json")


def normalize_shopify_text(text: object) -> str:
    """Standardize SKU/title string for case/whitespace-insensitive matching."""
    if not text:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", str(text)).strip().casefold()
    return " ".join(cleaned.split())


@dataclass
class ShopifyCatalogIndex:
    """Indexed identity sets for fast in-memory lookups."""

    skus: set[str]
    titles: set[str]
    handles: set[str]

    def contains(self, sku: str, title: str = "") -> bool:
        """Check if a SKU or title matches an active published product on Shopify.
        
        Uses strict exact normalized matching and validated base SKU prefix matching
        to prevent false positives from short variant tokens (e.g. 'dl').
        """
        clean_sku = normalize_shopify_text(sku)
        clean_title = normalize_shopify_text(title)

        if clean_sku:
            if clean_sku in self.skus:
                return True
            # For delimited variant SKUs (e.g. "10238P-3L" or "8971T/S"), check base SKU if >= 4 chars
            for delim in ("-", "/", " "):
                if delim in clean_sku:
                    base_sku = clean_sku.split(delim)[0].strip()
                    if len(base_sku) >= 4 and base_sku in self.skus:
                        return True

        if clean_title:
            if clean_title in self.titles:
                return True
            if "|" in str(title):
                base_title = normalize_shopify_text(str(title).split("|")[0])
                if base_title and base_title in self.titles:
                    return True
            handle_form = clean_title.replace(" ", "-")
            if handle_form in self.handles:
                return True

        return False


class ShopifyClient:
    """Client for querying published products on Shopify."""

    def __init__(
        self,
        domain: str = DEFAULT_SHOPIFY_DOMAIN,
        access_token: str | None = None,
        session: requests.Session | None = None,
        max_workers: int = 8,
    ):
        clean_domain = domain.replace("https://", "").replace("http://", "").strip().rstrip("/")
        self.domain = clean_domain or "homecartel.net"
        self.access_token = access_token or os.getenv("SHOPIFY_ACCESS_TOKEN", "").strip() or None
        self.session = session or requests.Session()
        self.max_workers = max_workers
        self._cached_index: ShopifyCatalogIndex | None = None

    def _fetch_storefront_page(
        self,
        page_num: int,
        page_limit: int = 250,
        max_retries: int = 7,
        initial_delay: float = 0.0,
    ) -> tuple[int, list[dict[str, Any]], bool]:
        """Fetch a single storefront page with automatic exponential backoff on HTTP 429 rate limit.

        Returns: (page_num, products_list, is_success)
        """
        if initial_delay > 0:
            time.sleep(initial_delay)

        url = f"https://{self.domain}/products.json?limit={page_limit}&page={page_num}"
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 429:
                    retry_header = resp.headers.get("Retry-After")
                    delay = _parse_retry_after(retry_header)
                    if delay is not None:
                        sleep_s = min(max(delay, 1.0), 30.0)
                        source_msg = f"Retry-After header ({delay:.1f}s, capped to {sleep_s:.1f}s)"
                    else:
                        sleep_s = min((2.0 ** attempt) + random.uniform(0.5, 2.5), 30.0)
                        source_msg = f"exponential backoff with jitter ({sleep_s:.1f}s)"

                    print(
                        f"[WARN] Shopify rate-limited (HTTP 429) on page {page_num}. "
                        f"Backing off {source_msg} (attempt {attempt + 1}/{max_retries})...",
                        flush=True,
                    )
                    time.sleep(sleep_s)
                    continue
                if resp.ok:
                    items = resp.json().get("products", [])
                    return page_num, items, True
                print(
                    f"[WARN] Shopify storefront page {page_num} returned HTTP {resp.status_code}",
                    flush=True,
                )
            except Exception as err:
                print(
                    f"[WARN] Shopify storefront page {page_num} network error: {err}",
                    flush=True,
                )
            time.sleep(1.0)
        return page_num, [], False

    def fetch_all_products(
        self, max_pages: int = 80, batch_size: int = 4
    ) -> tuple[list[dict[str, Any]], list[int]]:
        """Fetch all published products from Shopify store using dynamic concurrent requests until catalog ends.

        Returns: (products, failed_pages)
        """
        products: list[dict[str, Any]] = []
        failed_pages: list[int] = []

        # If Admin API token is present, use Admin REST API
        if self.access_token:
            headers = {
                "X-Shopify-Access-Token": self.access_token,
                "Content-Type": "application/json",
            }
            url = f"https://{self.domain}/admin/api/2024-01/products.json?status=active&limit=250"
            while url and len(products) < (max_pages * 250):
                try:
                    resp = self.session.get(url, headers=headers, timeout=15)
                    if not resp.ok:
                        print(f"[WARN] Shopify Admin API request returned status {resp.status_code}")
                        break
                    data = resp.json()
                    page_products = data.get("products", [])
                    if not page_products:
                        break
                    products.extend(page_products)
                    link_header = resp.headers.get("Link", "")
                    next_url = None
                    if link_header:
                        for part in link_header.split(","):
                            if 'rel="next"' in part:
                                match = re.search(r"<(.*)>", part)
                                if match:
                                    next_url = match.group(1)
                    url = next_url
                except Exception as err:
                    print(f"[WARN] Failed fetching from Shopify Admin API: {err}")
                    break
            if products:
                return products, []

        # Storefront lookup: iterate in batches with rate-limit retry, staggered worker dispatch, and polite pacing
        current_page = 1
        consecutive_empty = 0
        failed_page_numbers: set[int] = set()

        while current_page <= max_pages:
            batch_end = min(current_page + batch_size, max_pages + 1)
            page_numbers = list(range(current_page, batch_end))
            workers_count = min(self.max_workers, 4)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers_count) as executor:
                futures = [
                    executor.submit(
                        self._fetch_storefront_page,
                        page_num=p,
                        page_limit=250,
                        max_retries=7,
                        initial_delay=(idx * 0.35),
                    )
                    for idx, p in enumerate(page_numbers)
                ]
                raw_results = [f.result() for f in futures]
            page_results = {p: (items, success) for p, items, success in raw_results}

            hit_end = False
            for p in sorted(page_results):
                items, success = page_results[p]
                if not success:
                    print(
                        f"[WARN] Page {p} failed after retries during concurrent crawl; queued for sequential retry.",
                        flush=True,
                    )
                    failed_page_numbers.add(p)
                    continue
                if not items:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        hit_end = True
                        break
                else:
                    consecutive_empty = 0
                    products.extend(items)

            if hit_end or len(page_numbers) < batch_size:
                break
            current_page = batch_end
            time.sleep(1.0)  # Gentle 1.0s pause between batches

        # Sequential single-threaded retry pass for failed pages
        if failed_page_numbers:
            print(
                f"[INFO] Sequentially retrying {len(failed_page_numbers)} failed page(s): {sorted(failed_page_numbers)}...",
                flush=True,
            )
            for p in sorted(failed_page_numbers):
                time.sleep(2.0)  # Generous cool-down before retry
                _, items, success = self._fetch_storefront_page(p, page_limit=250, max_retries=7)
                if success:
                    if items:
                        products.extend(items)
                    print(f"[OK] Sequential retry succeeded for page {p} ({len(items)} items).", flush=True)
                else:
                    print(f"[ERROR] Page {p} permanently failed after sequential retry.", flush=True)
                    failed_pages.append(p)

        return products, sorted(failed_pages)

    def load_published_identities(self, force_refresh: bool = False) -> ShopifyCatalogIndex:
        """Load and index all published product SKUs, titles, and handles from Shopify.
        
        Applies a 12-hour TTL cache policy. If cache is fresh, loads from disk.
        If cache is older than 12 hours, fetches live from Shopify and updates cache.
        Protects against partial cache truncation and catalog shrinkage.
        """
        CACHE_MAX_AGE_SECONDS = 12 * 3600  # 12 hours TTL

        if self._cached_index is not None and not force_refresh:
            return self._cached_index

        cache_is_fresh = False
        cached_skus_count = 0
        if SHOPIFY_CACHE_FILE.is_file():
            try:
                age = time.time() - SHOPIFY_CACHE_FILE.stat().st_mtime
                if age < CACHE_MAX_AGE_SECONDS:
                    cache_is_fresh = True
            except Exception:
                pass

        # 1. Try loading from disk cache first if not forced and cache is still fresh (< 12 hours)
        if not force_refresh and cache_is_fresh:
            try:
                data = json.loads(SHOPIFY_CACHE_FILE.read_text(encoding="utf-8"))
                skus = {normalize_shopify_text(s) for s in data.get("skus", []) if len(normalize_shopify_text(s)) >= 3}
                titles = set(data.get("titles", []))
                handles = set(data.get("handles", []))
                if skus or titles:
                    self._cached_index = ShopifyCatalogIndex(skus=skus, titles=titles, handles=handles)
                    print(
                        f"[OK] Shopify Index loaded from cache (fresh, <12h old): "
                        f"{len(skus)} SKUs, and {len(titles)} titles indexed ({SHOPIFY_CACHE_FILE.name})."
                    )
                    return self._cached_index
            except Exception:
                pass

        print(f"[INFO] Fetching published catalog from Shopify ({self.domain})...")
        products, failed_pages = self.fetch_all_products()

        # Build identities from crawled products
        skus: set[str] = set()
        titles: set[str] = set()
        handles: set[str] = set()

        for prod in products:
            p_title = prod.get("title") or ""
            p_handle = prod.get("handle") or ""
            if p_title:
                titles.add(normalize_shopify_text(p_title))
                if "|" in p_title:
                    pre_pipe = normalize_shopify_text(p_title.split("|")[0])
                    if pre_pipe:
                        titles.add(pre_pipe)
            if p_handle:
                handles.add(normalize_shopify_text(p_handle))

            for variant in prod.get("variants", []):
                v_sku = variant.get("sku") or ""
                v_title = variant.get("title") or ""
                if v_sku:
                    c_sku = normalize_shopify_text(v_sku)
                    if len(c_sku) >= 3:
                        skus.add(c_sku)
                    if "-" in v_sku:
                        parts = v_sku.rsplit("-", 1)
                        if len(parts) == 2:
                            c_part = normalize_shopify_text(parts[0])
                            if len(c_part) >= 3:
                                skus.add(c_part)
                if v_title and v_title.lower() != "default title":
                    combined = f"{p_title} {v_title}"
                    titles.add(normalize_shopify_text(combined))

        # Check existing disk cache content for fallback or shrinkage guard
        cached_data = None
        if SHOPIFY_CACHE_FILE.is_file():
            try:
                cached_data = json.loads(SHOPIFY_CACHE_FILE.read_text(encoding="utf-8"))
                cached_skus_count = len(cached_data.get("skus", []))
            except Exception:
                pass

        # Partial crawl guard: if any pages failed, never overwrite disk cache
        if failed_pages:
            print(
                f"[WARN] Shopify crawl incomplete (failed pages: {failed_pages}) — "
                f"keeping previous cache to avoid truncating published inventory.",
                flush=True,
            )
            if cached_data:
                cached_skus = {normalize_shopify_text(s) for s in cached_data.get("skus", []) if len(normalize_shopify_text(s)) >= 3}
                cached_titles = set(cached_data.get("titles", []))
                cached_handles = set(cached_data.get("handles", []))
                if cached_skus or cached_titles:
                    self._cached_index = ShopifyCatalogIndex(skus=cached_skus, titles=cached_titles, handles=cached_handles)
                    print(
                        f"[OK] Fallback to existing disk cache successful: "
                        f"{len(cached_skus)} SKUs, {len(cached_titles)} titles ({SHOPIFY_CACHE_FILE.name})."
                    )
                    return self._cached_index

            # Cold start fallback if no disk cache exists
            print(
                f"[WARN] No disk cache available; using partial crawl in-memory without caching to disk "
                f"({len(skus)} SKUs, {len(titles)} titles).",
                flush=True,
            )
            self._cached_index = ShopifyCatalogIndex(skus=skus, titles=titles, handles=handles)
            return self._cached_index

        # Catalog shrinkage guard: if new crawl has < 75% of previous cache SKU count
        if cached_skus_count > 0 and len(skus) < (0.75 * cached_skus_count):
            print(
                f"[WARN] Shopify crawl yielded {len(skus)} SKUs, which is <75% of previous cache "
                f"({cached_skus_count} SKUs). Possible silent endpoint truncation — preserving previous cache.",
                flush=True,
            )
            if cached_data:
                cached_skus = {normalize_shopify_text(s) for s in cached_data.get("skus", []) if len(normalize_shopify_text(s)) >= 3}
                cached_titles = set(cached_data.get("titles", []))
                cached_handles = set(cached_data.get("handles", []))
                if cached_skus or cached_titles:
                    self._cached_index = ShopifyCatalogIndex(skus=cached_skus, titles=cached_titles, handles=cached_handles)
                    return self._cached_index

        if skus or titles:
            try:
                SHOPIFY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                SHOPIFY_CACHE_FILE.write_text(
                    json.dumps({"skus": list(skus), "titles": list(titles), "handles": list(handles)}, indent=2),
                    encoding="utf-8",
                )
            except Exception as err:
                print(f"[WARN] Failed to write Shopify cache file: {err}")
            self._cached_index = ShopifyCatalogIndex(skus=skus, titles=titles, handles=handles)
            print(
                f"[OK] Shopify Index Ready: {len(products)} published products, "
                f"{len(skus)} SKUs, and {len(titles)} titles indexed from {self.domain}."
            )
            return self._cached_index

        # Fallback if 0 products returned and no failed_pages reported
        if cached_data:
            cached_skus = set(cached_data.get("skus", []))
            cached_titles = set(cached_data.get("titles", []))
            cached_handles = set(cached_data.get("handles", []))
            if cached_skus or cached_titles:
                self._cached_index = ShopifyCatalogIndex(skus=cached_skus, titles=cached_titles, handles=cached_handles)
                print(
                    f"[WARN] Network fetch returned 0 products. "
                    f"Using cached Shopify Index: {len(cached_skus)} SKUs, {len(cached_titles)} titles."
                )
                return self._cached_index

        print(f"[WARN] Shopify index is empty (storefront rate-limited or blocked).")
        self._cached_index = ShopifyCatalogIndex(skus=set(), titles=set(), handles=set())
        return self._cached_index

    def is_published(self, sku: str, title: str = "") -> bool:
        """Check if an item exists and is published on Shopify."""
        index = self.load_published_identities()
        return index.contains(sku, title)
