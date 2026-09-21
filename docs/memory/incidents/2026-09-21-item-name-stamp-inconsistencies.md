---
date: 2026-09-21
pipeline: OP3S Feed, Moodboard Reel, Collection Category Feed, Style This Story
status: resolved
---

# Item-name stamping inconsistencies across 4 pipelines (2026-09-21)

**Incident.** Studio runs left users seeing deliverables without the YOLO item-name stamp on
1 Product, 3 Styles Feed and Collection Category Feed, material words (BRASS/BOUCLE/VELVET…)
typographed onto Moodboard Reel slides (often repeating across slots), and Style This Story
re-processing leftover pending rows instead of scraping brand-new ones.

**Diagnosis — three distinct root causes, one symptom family:**

1. **Separate-column tags vs in-slide stamp (OP3S Feed).** Tagging code existed and ran fine
   (live audit: every generated OP3S row had 3/3 attachments in `Blended Image with Name text`),
   but the posted `1 Product 3 Style Blended` slides only ever received a logo on Slide 1 —
   the name never appeared in the content that ships.
2. **Uncommitted fix vs stale live rows (CC Feed).** `run_collection_category_feed.py` Phase 5
   already stamps name + logo onto each `Blended Image{1..5}` slide in the working tree, but the
   live posted rows (CC-FEEDS-SET-17..23) predate that code and show no stamp — the fix simply
   had not run in production yet. Latent bugs found nearby: no `clear_attachment_field` before
   uploads (SET-21 accumulated duplicate `Blended Image4/5` attachments) and a silent
   `except: pass` on the name-text mirror.
3. **Pending-row fallback (Style This Story).** `generate_style_this_story_pipeline.py`
   selected any non-Complete row with a `Furniture Item` and only scraped fresh when none
   existed — a direct violation of AGENTS.md Master Rule 2.

**Also: Moodboard Reel material typography.** Phase 4.2 generated 3 texture words per converted
moodboard via four independent Claude Vision calls (nothing prevented BRASS appearing in every
slot) and stamped them locally with Pillow underline-bar typography. Only the item name should
be stamped on screen; materials belong in the imagery.

**Resolution (2026-09-21):**
- **OP3S Feed**: YOLO name tag applied in place to all 3 blended slides before the Slide-1 logo
  stamp; stamped slides upload to `1 Product 3 Style Blended` and are mirrored to
  `Blended Image with Name text`.
- **Moodboard Reel**: Phase 4.2, `generate_textures_for_moodboard`, `overlay_moodboard_textures`
  usage, and `Moodboard Converted with Text` removed. New `generate_unique_material_words()` makes
  ONE Claude Vision call per row producing 12 globally-unique material words, saved to
  `Texture1..12` and injected into each slot's Nano Banana blending prompt (purely visual, no
  rendered text). Reel consumes `Converted Moodboard` directly; the only words on screen are the
  Phase-3 YOLO item-name tags.
- **CC Feed**: `clear_attachment_field` before per-slot uploads and once for the name-text column;
  mirror failures now print `[WARN]` instead of vanishing.
- **Style This Story**: `run_pipeline` now always scrapes fresh Shopify-active, base-wide-deduped
  products and processes only `runner.created_record_ids`; `--record-id` is the only way to touch
  an existing row; the `--no-scrape` flag was deleted.

**Affected pre-fix rows:** existing Posted/Scheduled rows were NOT re-stamped or re-run, per the
repo rule that finished content stays untouched. Verification was static (py_compile + trace);
first live proof is the next Studio run of each pipeline.
