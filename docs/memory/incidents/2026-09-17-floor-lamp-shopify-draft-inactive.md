---
date: 2026-09-17
pipeline: Tips & Edu Story — Floor Lamp
status: root-caused, code side-effect fixed; underlying catalog gap is an ops task
---

# Floor Lamp Tips & Edu Story: "No active/published Shopify products found"

## Symptom

Dashboard banner: *"Pipeline Error: No active/published Shopify products found among eligible Akeneo candidates (94 candidates checked, but all 94 are Draft/Inactive on Shopify)."*

Raised from [[strict-shopify-verification-policy|the strict Shopify verification step]] in `content_automation/phased_content.py` (`_phase_1`), when zero of the fetched Akeneo candidates pass `ShopifyCatalogIndex.contains()`.

## How it was diagnosed

1. Read the raise site: `content_automation/phased_content.py` around the Shopify cross-check loop, and `ShopifyCatalogIndex.contains()` in `content_automation/shopify_client.py`.
2. Checked whether the *cache itself* was the problem (stale or empty, which would reject everything regardless of real Shopify state) — it wasn't: `output/cache/shopify_catalog_cache.json` was 1.8h old with 35,786 SKUs / 37,673 titles indexed.
3. Pulled the actual failing run's stdout live from the running dashboard server: `GET http://127.0.0.1:5200/api/tips-edu/status` — the in-memory `TIPS_EDU_STATE["logs"]` still held the full `[SHOPIFY DRAFT/INACTIVE SKIP]` line for every one of the 94 rejected candidates, with real SKUs (e.g. `HALLBMOD-FLOOR-1917`, `8905F`, `JCKSON-FLRLMP-729-30`).
4. Cross-checked several of those SKUs/names against the cache directly (normalized SKU, normalized title, and substring fragment search) — **zero matches**, not even partial. Not a formatting/normalization near-miss.
5. Sanity-checked the cache's naming convention: 87.5% of live Shopify SKUs use Home Cartel's own `HC ...` prefix. None of the failing candidates did.

## Root cause

Not a code bug. These 94 Floor Lamp products are `enabled=True` in Akeneo (likely a bulk supplier-catalog import) but were **never created/published as products on the live Shopify store at all** — not merely set to Draft. The pipeline's strict verification correctly rejected all of them.

Compounding factor: [[strict-shopify-verification-policy|base-wide cross-table deduplication]] had already consumed the 532 previously-used Floor Lamp SKUs across other Airtable tables, so this stale, unpublished batch was literally all that was left to offer as "new" candidates.

## Resolution

- **Ops (not done by this session, needs action in Akeneo/Shopify directly)**: either publish these products on Shopify, or disable them in Akeneo so they stop being offered as candidates.
- **Code side-effect that *was* shipped**: the dashboard hid this exact diagnostic detail from the user the moment the run failed — `LiveLogViewer` (the console showing the per-SKU skip lines) only rendered while `pipelineState.status === 'running'` in `UI Control/src/app/App.tsx`. Widened the condition to also render on `status === 'error'`, so the full skip list stays visible under the red banner instead of requiring the manual API pull described above. See [[system-overview]] for where this fits in the dashboard's data flow.

## Related

- [[strict-shopify-verification-policy]] — why this check exists and hard-fails rather than degrading silently.
- [[system-overview]] — Akeneo → Shopify cross-check → Airtable → dashboard data flow.
