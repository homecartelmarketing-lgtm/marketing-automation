---
tags: [decision, shopify, akeneo, data-integrity]
---

# Why the pipeline hard-fails instead of using Draft/Inactive Shopify products

## The rule

`enabled=True` in Akeneo PIM is not sufficient to scrape a product. Every candidate must additionally match a **live, published** product on Shopify (`homecartel.net`) by SKU or title — checked via `ShopifyCatalogIndex.contains()` in [`content_automation/shopify_client.py`](../../../content_automation/shopify_client.py), called from [`content_automation/phased_content.py`](../../../content_automation/phased_content.py). If *zero* candidates pass, the pipeline raises `AutomationError` and stops — it does not fall back to using an unverified product, and it does not silently skip the fixture and continue.

This is called out as a top-level "Core Operating Tenet" in [`AGENTS.md`](../../../AGENTS.md) (§1, §4): *"Strict Shopify 'Active & Published' Ingestion... Any product that is Draft, Inactive, Archived, or Unlisted on Shopify MUST be immediately rejected and skipped."*

## Why

Akeneo PIM is the product *catalog* source of truth, but it lags reality — it accumulates discontinued, draft, or not-yet-published items that haven't been disabled in PIM even though they were never (or are no longer) sellable. Generating and posting social content for a product nobody can actually buy is worse than not posting: it sends traffic to a dead/nonexistent product page.

## Why hard-fail rather than degrade gracefully

The alternative — e.g. "if nothing matches, just use the best Akeneo candidate anyway" — would silently reintroduce exactly the failure mode this check exists to prevent, and nobody would notice until a customer did. A hard failure is loud by design: it shows up as a red banner in the dashboard ([[../incidents/2026-09-17-floor-lamp-shopify-draft-inactive|worked example]]) rather than quietly publishing bad content.

## Matching rules (also intentional, also in `AGENTS.md` §4)

- **Strict normalized equality only** for SKU/title matching (plus one narrow exception: splitting on `-`, `/`, ` ` to check a base SKU prefix ≥4 chars, for delimited variant SKUs like `10238P-3L`).
- **Substring matching is explicitly banned** — a naive `s in clean_sku` check previously caused false-positive matches on short tokens (e.g. `'dl'` matching unrelated SKUs). This is why `ShopifyCatalogIndex.contains()` doesn't do simple substring checks.
- **Catalog cache TTL is 12 hours** (`output/cache/shopify_catalog_cache.json`), so a product recently unpublished on Shopify can't keep being scraped indefinitely on stale cache data.
- **Zero partial-cache overwrite guarantee**: If the storefront crawl has any unrecovered failed pages (`failed_pages != []`), the crawler strictly refuses to overwrite the disk cache and falls back to the existing cache (or operates in-memory only on cold start). A partial crawl will never poison the disk cache.
- **Catalog shrinkage guard**: Even on complete crawls, if the new crawl yields <75% of the existing disk cache SKU count, the overwrite is blocked to protect against silent upstream catalog cuts.
- **Crawler pacing & backoff**: Concurrent storefront crawling uses max 4 workers with per-slot initial delays (`slot * 0.35s`), 1.0s inter-batch pauses, `Retry-After` header parsing (or jittered exponential backoff up to 7 attempts capped at 30s), and a final sequential single-threaded retry pass for any failed pages. See [[../incidents/2026-09-21-shopify-429-partial-cache]].

## Consequence worth knowing

Because this check is strict and multiplicative with [[../../AGENTS.md|base-wide cross-table deduplication]] (a candidate must be both unused everywhere in the base *and* live on Shopify), a category can run dry — every remaining Akeneo-enabled candidate for a fixture might already be either used elsewhere or unpublished — well before Akeneo "looks" empty. See [[../incidents/2026-09-17-floor-lamp-shopify-draft-inactive]] for exactly this happening.
