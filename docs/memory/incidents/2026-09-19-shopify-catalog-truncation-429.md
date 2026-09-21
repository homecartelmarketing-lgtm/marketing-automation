---
date: 2026-09-19
pipeline: Tips & Edu Story (Pendant Lights) & Base-wide Pipelines
status: resolved
---

# Shopify Catalog Truncation: "No active/published Shopify products found"

## Symptom

Dashboard console error when executing Tips & Edu Story:
*"[FATAL] No active/published Shopify products found among eligible Akeneo candidates (242 candidates checked, but all 242 are Draft/Inactive on Shopify)."*

## How it was diagnosed

1. Checked `output/cache/shopify_catalog_cache.json`. The cache only held 19,572 SKUs from 7,250 products (stopping at page 29).
2. Probed the live Shopify storefront (`https://homecartel.net/products.json?limit=250&page=32`) for one of the reported skipped items (*Riina Quatre*, SKU `10805P`), which returned `200 OK` and proved the product was fully active and published on Shopify.
3. Inspected `ShopifyClient.fetch_all_products()` and `_fetch_storefront_page()`:
   - High concurrency (`max_workers=8`) caused Shopify/Cloudflare to throttle storefront requests with `HTTP 429 (Too Many Requests)` starting around page 28–30.
   - `_fetch_storefront_page()` silently swallowed errors and returned `[]` on status 429.
   - `fetch_all_products()` treated receiving `[]` as reaching the end of the store catalog (`hit_end = True`), prematurely halting pagination at page 29.
   - Consequently, **pages 30 through 52** (5,346+ published products) were truncated and omitted from the cache.

## Root Cause

Shopify storefront crawler lacked rate-limit handling and exponential backoff for `HTTP 429`. Transient rate-limit errors were misinterpreted as the true end of the catalog, truncating the cache to ~57% of the actual published inventory.

## Resolution

1. **Exponential Backoff & Retry**: Updated `_fetch_storefront_page()` in `content_automation/shopify_client.py` to recognize `HTTP 429`, back off exponentially (`2s * attempt`), and retry up to 5 times.
2. **Pacing & Concurrency**: Restricted worker pool to 4 threads and added polite 0.3s inter-batch pacing to avoid triggering rate limits.
3. **Double-Empty Catalog End Guard**: Required 2 consecutive successful empty pages (`consecutive_empty >= 2`) before marking `hit_end = True`.
4. **Cache Regeneration**: Rebuilt `output/cache/shopify_catalog_cache.json`, bringing total published products indexed to **12,596 products** (52,185 SKUs, 56,559 titles).
5. **Verification**: 665 out of 673 deduplicated Akeneo pendant light candidates are now verified active and immediately eligible for generation.
