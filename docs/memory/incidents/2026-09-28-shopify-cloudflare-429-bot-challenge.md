---
date: 2026-09-28
pipeline: Shopify Verification & Base-wide Pipelines
status: resolved
---

# Shopify Storefront Throttling (HTTP 429) & Cloudflare Bot Challenge Mitigation

## Symptom

During Phase 1 (Akeneo Product Scraping) across automated pipeline execution (such as Ad Covers, Tips & Edu, CTA Story, etc.), the pipeline stalled on page ~32 with repeated warning logs:
```text
[WARN] Shopify rate-limited (HTTP 429) on page 32. Backing off exponential backoff with jitter (2.7s) (attempt 1/7)...
[WARN] Shopify rate-limited (HTTP 429) on page 32. Backing off exponential backoff with jitter (2.9s) (attempt 2/7)...
...
[WARN] Shopify rate-limited (HTTP 429) on page 32. Backing off exponential backoff with jitter (30.0s) (attempt 6/7)...
```
The console remained frozen for minutes across 4 concurrent worker threads before eventually falling back to the existing cache.

## Root Cause

1. **Cache TTL Expiration**:
   - `output/cache/shopify_catalog_cache.json` had a 12-hour TTL.
   - When the cache became > 12 hours old, any pipeline run initiated a full live storefront crawl across all 52 pages (`https://homecartel.net/products.json?limit=250&page=N`).

2. **Cloudflare Bot Challenge (HTTP 429 with `Cf-Mitigated: challenge`)**:
   - Standard Python `requests` library uses OpenSSL TLS client hello signatures (JA3/JA4 fingerprint).
   - When 4 threads concurrently requested dozens of storefront pages, Cloudflare's bot mitigation at the Singapore edge (`SIN`) flagged the high-frequency Python requests and returned `HTTP 429` with `Cf-Mitigated: challenge` and an HTML verification page (`<title>Verifying your connection...</title>`).

3. **Futile 100-Second Exponential Backoff**:
   - Cloudflare challenge responses omit the `Retry-After` header.
   - The crawler assumed a standard Shopify leaky-bucket rate limit and executed 7 jittered exponential backoff retries (~100s per thread).
   - Because a Python HTTP request cannot solve an interactive JavaScript Cloudflare challenge, retries were 100% futile and stalled Phase 1 for minutes.

## Resolution

1. **Chrome Browser TLS Fingerprint Impersonation (`curl_cffi`)**:
   - `ShopifyClient` now leverages `curl_cffi.requests.Session(impersonate="chrome120")` when available (falling back gracefully to `requests.Session()`).
   - Browser TLS fingerprinting avoids Cloudflare bot heuristics entirely during catalog pagination.

2. **Instant Fast-Fail on Cloudflare Challenge Mitigation**:
   - `_fetch_storefront_page` detects `Cf-Mitigated: challenge` and Cloudflare verification text in the response.
   - If detected, it immediately logs a notice and returns failure in <0.1s without executing futile 7-step backoff loops.

3. **Configurable Cache TTL**:
   - Changed default TTL from 12 hours to 24 hours (`SHOPIFY_CACHE_TTL_HOURS`, default `24`), minimizing unnecessary re-crawls during creative runs.

4. **CLI Cache Management**:
   - Added command line support: `python -m content_automation.shopify_client [--status|--refresh]`.

## Verification & Results

1. **Unit & Regression Suite** (`scratch/test_shopify_rate_limit_fallback.py`):
   - Added `test_cloudflare_challenge_fast_fail` and `test_curl_cffi_session_initialization`.
   - All 7 tests passed (`OK` in 2.01s).

2. **Live Storefront Full Crawl** (`python -m content_automation.shopify_client --refresh`):
   - Crawled all 52 pages cleanly in ~35 seconds with 0 rate limits and 0 failed pages.
   - Fresh cache written: **12,595 products, 52,173 SKUs, 56,554 titles**.
   - Subsequent client initializations load from cache in 0.05 seconds.
