# Marketing Automation — Redflag Report (Consolidated)

*Audit coverage: table config drift, Krea moodboard wiring, hallucination-prone code, queue robustness, subprocess safety. Every finding carries a `file:line`. Last verified: 2026-10-05.*

## 🔴 HIGH — wrong data posted as real

### H1. Shopify verification bypass (fail-open instead of fail-closed)

| File:line | Issue |
|---|---|
| `content_automation/scraping/runner.py:433-452` | When the Shopify check fails, continues with **unfiltered** Akeneo candidates (a `[WARN]` only) |
| `content_automation/scraping/furniture_item.py:789-794` + `:522` | `None` index skips the `contains()` check entirely, every candidate passes |
| `content_automation/banner_common.py:164-171` + `:209` | `None` index bypasses all Christmas / Sale / third-banner slots |

**Fix:** fail-closed — when the Shopify index cannot load, fail the run instead of continuing.

### H2. `or record_id` stamped as product name

Sites: `generate_moodboard_2_feed.py:575`, `generate_before_after_reel_pipeline.py:685`, `generate_cta_story_pipeline.py:1148`, `content_automation/cta_conversion.py:283`, `content_automation/phased_content.py:1664,1467,1535,1563`, `run_tips_and_edu_feed.py:1989`, `workflows/day_night_story.py:98`, `workflows/tips_educational_story.py:46`.
When Item Name + SKU are both empty, `recXXXXXXXX` is stamped as the YOLO tag and posted as the real product name.
**Fix:** fail the run (or flag `FM`) instead of stamping `rec…`.

### H3. Invented FK + invented price

| File:line | Issue |
|---|---|
| `content_automation/foreign_key.py:247,257,307` | Unknown fixture → `"CH"`, unknown idea → `"HC"`, missing row → `"0"` (e.g. `HC-STORY-CH-0`) |
| `generate_ad_cover_pipeline.py:611` | FK without number (`ADC-ADS-CH`) collides |
| `content_automation/scraping/products.py:116-117` | `Costing="High"` invented as `$300` → wrong "highest-priced" pick + `0.0` price written to Airtable |

**Fix:** `raise` instead of fallback; validate price before picking.

### H4. Dedup silently lost

- `furniture_item.py:313-314` (`return set(), set(), set()`), `:395-396` (`except: break` inside pagination) — base-wide dedup identities lost, duplicates return as "fresh".

### H5. Hang-forever runs (no `stdin=DEVNULL`, no watchdog)

- Every `generate_*` monolith has `input()` menus; route spawns (e.g. `cta_story.py:570-577` and the same pattern elsewhere) pass no `stdin=subprocess.DEVNULL` — if a run ever reaches `input()`, the child blocks forever, the Studio card stays "running", and the FIFO queue is wedged.
- `queue_manager.py:231-244` has no max-runtime/watchdog; `:130-131` masks errors as `"running"`.

**Fix:** `stdin=DEVNULL` on every spawn + max-runtime watchdog. (Implemented 2026-10-05 — see Step 8 of the CTA pilot.)

## 🟡 Config drift (killed by the catalog plan)

### C1. `config.py` TABLES vs live routes (~20 tables with no entry)

In FK/routes/docs but with no `TABLES` entry: all of MB2 (4 tables), Sketch-to-Real (2), OATL, SRS, PCR, Banner, RBU, Style-This-CH, DN feed +3, MB1 +2, Tips-Edu feed +2, DN reel 2. Stale entries with no UI: `wall_lights_cta_story` (`tblsllKrNcffItIua`), linear/table collection extras. DN-vs-BA mislabel at `config.py:219-231,442`.

### C2. `.env.example` drift — 14 stale IDs + duplicate keys

Collection Story IDs (`:109-113`), MB1 feed (`:15`), product tables (`:8,11`); `STYLE_THIS_CHANDELIER` twice (`:13` vs `:157`); deleted `tbl2VoWOt7sSut4E2` still present; CTA table-lamp `fb2487fb` (superseded by `257569e1` per CTA catalog decision 2026-10-05).

### C3. 70 route env keys missing from `.env.example`

MB1/MB2 feed, Myth-Fact, Before-After, Day-Night Reel, Tips-Edu Feed, Sketch extras — every Studio save becomes an untracked `.env` line forever. (Studio no longer writes `.env` as of 2026-10-05 — saves go to `output/config_overrides.json` only.)

### C4. Moodboard UUID conflicts

CTA table-lamp 3-way split (winner: `257569e1-7be8-4412-a90f-acbc347e4646`, decided 2026-10-05), Ad Cover table-lamp, Moodboard Story chandelier, Collection wall-light (2v2 tie — needs a Krea probe), Sketch ceiling-mounted sharing one env key with chandelier.

### C5. `None` handling only half-done

8 routes (`ad_cover`, `collection_story`, `cta_story`, `day_night_feed/story`, `one_product_three_styles_feed`, `style_this_story`, `tips_edu_story`) — `str(payload.get(...))` turns JSON null into truthy `"None"` for the active run.

## 🟢 Silent fallbacks (cosmetic, no flag)

- `"Singkwenta Dose"` headline (`cta_conversion.py:276-281`, `overlay.py:499,558,629`); Christmas fallback title/subtitle; Sale red panel hex; generic Nano Banana prompts; `MATERIAL_FALLBACK_POOL`; YOLO failure → `Complete` with no tag (8 sites). Only `story_tip.py` is clean (has a `tip_used_fallback` flag).
- Placeholder table IDs live in prod paths: `tblSketchToReal*`/`tblSketchToDraw*`. `fixtures.ts:248` "All 6" vs 9 Ad Covers. Sketch doc self-contradiction.

## Priority order

1. CTA pilot catalog + table-lamp UUID + `.env` write removal
2. `stdin=DEVNULL` + queue watchdog
3. Shopify fail-closed + `or record_id` guard + FK `raise`
4. Catalog rollout to remaining pipelines
