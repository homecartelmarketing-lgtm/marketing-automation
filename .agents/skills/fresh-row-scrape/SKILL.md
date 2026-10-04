---
name: fresh-row-scrape
description: Use when writing or changing any scrape phase, product selection, Akeneo/Shopify check, or dedup logic, or whenever tempted to reprocess existing Airtable rows. Enforces fresh rows, strict Shopify matching and base-wide dedup.
---

# Fresh Rows, Shopify Verification and Dedup

These rules protect the brand's live feeds. Reprocessing old rows overwrites content that may already be scheduled or posted. Products that are only "enabled" in Akeneo can be drafts or discontinued on the store, and a post linking to one is a dead end for customers. Repeats across tables make the feed look lazy. Agents have broken these rules often, so treat them as fixed.

## 1. Every run makes a brand-new row

Every pipeline run, from the Studio or from the CLI default (`--phase all` / no `--record-id`), must:

1. Scrape fresh active products from Akeneo.
2. Verify each one against Shopify (section 2).
3. Dedup across the whole base (section 3).
4. Insert a **new** Airtable row with the FK ID stamped (`ScrapeAirtableClient` handles FK and timestamp).
5. Process that row through every phase until `Complete`/`Done`.

Never query, loop over, or re-run leftover, pending or incomplete rows, even if it looks efficient. Existing rows stay untouched. The only exception is a developer passing an explicit `--record-id <rec_id>` to re-render one record. `TERMINAL_AND_PROTECTED_STATUSES` shields Posted/Scheduled rows in the phase engine, so don't weaken it.

## 2. Strict Shopify "Active & Published" check

- `enabled=True` in Akeneo isn't enough. Every candidate must be live on `homecartel.net/products.json` through `content_automation/shopify_client.py`.
- Draft, Inactive, Archived or Unlisted products are skipped, with this log:
  `[SHOPIFY DRAFT/INACTIVE SKIP] Item '<name>' (SKU: <sku>) is not active on Shopify -> skipping`
- Match only on exact normalized SKU equality, exact title equality, or the exact pre-pipe title. Substring matching (`s in clean_sku`) is banned, because short tokens like `'dl'` match everything.

### Cache behavior (don't regress it)

- The cache refreshes every 24h (`SHOPIFY_CACHE_TTL_HOURS`).
- Requests go through `curl_cffi` with Chrome 120 TLS impersonation and a `requests` fallback, with a fast fail on Cloudflare challenges.
- The crawler uses 4 workers, a 0.35s initial delay per worker, 1.0s pauses between batches, honors `Retry-After` or uses jittered exponential backoff (up to 7 tries, capped at 30s), then does a sequential retry pass.
- **Partial-cache guarantee:** if pages failed or the catalog shrank below 75% of the previous SKU count, don't overwrite the disk cache. A truncated cache falsely rejects real products (see the shopify-429 incidents).
- Check or force a refresh with `python -m content_automation.shopify_client --status` / `--refresh`.

## 3. Base-wide dedup

Before inserting into any Story, Feed or Reel table, check the SKU and item name against **all 60+ tables** with `fetch_all_base_existing_identities`. A product featured anywhere in the base is excluded.

## 4. Category routing

- Standard chandelier categories skip linear and cluster chandeliers, which go to their dedicated tables.
- Check that the room fits the slot, e.g. table lamps on bedside nightstands, chandeliers in high-ceiling living or dining spaces.
- Pass the real `category_code` downstream (for example to the YOLO item tagger). Don't hardcode one.
