---
date: 2026-09-21
pipeline: Shopify Verification & Base-wide Pipelines
status: resolved
---

# Shopify Storefront Throttling (HTTP 429) & Partial Crawl Cache Corruption

## Symptom

During automated pipeline execution (such as Tips & Edu Story and other base-wide pipelines), product candidates scraped from Akeneo were unexpectedly rejected with `[SHOPIFY DRAFT/INACTIVE SKIP]` even when active on Shopify.
Log inspection revealed:
```
[WARN] Shopify rate-limited (HTTP 429) on page 27. Backing off 2.0s (attempt 1/5)...
...
[WARN] Skipping page 28 after exhausting retries.
```
Despite pages being skipped, the crawler printed `[OK] Shopify Index Ready` and overwrote `output/cache/shopify_catalog_cache.json` with a truncated product list.

## Root Cause

1. **Bursty concurrent crawl**: `ShopifyClient.fetch_all_products()` fired 4 concurrent worker threads in batches of 6 with only `0.3s` pause between batches and zero dispatch staggering between threads. Shopify's public storefront endpoint (`homecartel.net/products.json?limit=250&page=N`) throttled the sustained burst with `HTTP 429` starting around page 27.
2. **Rigid backoff & ignored headers**: `_fetch_storefront_page()` used linear backoff `2.0 * (attempt + 1)` and completely ignored the `Retry-After` header sent in Shopify's 429 response.
3. **Silent data loss and partial cache poisoning**: When a page exhausted retries, it was skipped with `[WARN] Skipping page N after exhausting retries`. However, `load_published_identities()` checked only `if skus or titles:` before saving to `output/cache/shopify_catalog_cache.json`. Because the partially fetched pages contained thousands of SKUs, the truncated dataset passed the check and overwrote the 12-hour disk cache. All products on skipped pages were then wrongly considered inactive for the next 12 hours.

## Resolution

1. **Retry-After Header Support & Jittered Exponential Backoff**:
   - Added `_parse_retry_after()` to parse numeric seconds and RFC 2822/7231 HTTP dates.
   - If present, backs off for the indicated duration (capped at 30.0s).
   - If absent, uses exponential backoff with random jitter: `min((2.0 ** attempt) + random.uniform(0.5, 2.5), 30.0)`.
   - Increased `max_retries` from 5 to 7.

2. **Gentler Pacing & Worker Dispatch Staggering**:
   - Reduced `batch_size` from 6 to 4 to match `max_workers=4`.
   - Staggered thread dispatch with per-slot `initial_delay = slot * 0.35s` inside each worker to prevent simultaneous request collisions.
   - Increased inter-batch pause from `0.3s` to `1.0s`.

3. **Sequential Single-Threaded Retry Pass**:
   - Pages that fail during the concurrent batch crawl are collected into `failed_page_numbers`.
   - After the concurrent pass finishes, failed pages are retried sequentially (single thread) with a `2.0s` cool-down pause between requests.

4. **Strict Partial Cache & Shrinkage Protection**:
   - `fetch_all_products()` now returns `(products, failed_pages)`.
   - If `failed_pages` is non-empty, `load_published_identities()` logs `[WARN] Shopify crawl incomplete — keeping previous cache` and strictly refuses to overwrite `SHOPIFY_CACHE_FILE`, falling back to the existing disk cache (or in-memory only on cold start).
   - Added a catalog shrinkage guard: even if all pages succeed, if the crawled SKU count is <75% of the existing disk cache SKU count, the overwrite is blocked to protect against silent upstream catalog truncation.
   - Normalized all SKUs loaded from disk cache to ensure strict, consistent matching.

## Verification & Results

1. **Automated Unit & Regression Suite** (`scratch/test_shopify_rate_limit_fallback.py`):
   - Verified `Retry-After` header parsing (seconds and HTTP-dates).
   - Verified `_fetch_storefront_page` backoff on mock 429 responses.
   - Verified disk cache preservation when crawl contains failed pages.
   - Verified catalog shrinkage guard preserves previous cache if fresh SKU count drops >25%.
   - Verified cold start fallback serves partial crawl in-memory without saving to disk.
   - Result: 5/5 tests passed (`OK`).

2. **Live Storefront Verification** (`load_published_identities(force_refresh=True)`):
   - Full live crawl completed across all 52 pages from `homecartel.net`.
   - Indexed **12,596 published products** (`52,185 SKUs`, `56,559 titles`).
   - Transient 429s were automatically caught and recovered on attempt 1 or 2 with exponential backoff and jitter.
   - `failed_pages: []` (0 failed pages). Fresh cache was verified and written cleanly.

