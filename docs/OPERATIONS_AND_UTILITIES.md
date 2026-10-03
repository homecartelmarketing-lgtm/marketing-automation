# Operations & Utility Scripts

Scripts that keep the system healthy but aren't Story/Feed/Reel/Ad Cover content pipelines and weren't previously catalogued anywhere. Root-level scripts plus the `scratch/` schema and verification helpers that a pipeline doc alone would not surface. Descriptions are pulled from each script's own module docstring.

## Scheduling & hosting

| Script | Purpose |
| :--- | :--- |
| [`run_auto_post_scheduler.py`](../run_auto_post_scheduler.py) | Polls an external scheduling API every 60s and publishes due Stories/Feeds/Reels to Instagram at their scheduled PHT time. See [`AUTO_POST_SCHEDULER.md`](AUTO_POST_SCHEDULER.md) — has an undocumented cross-repo dependency worth reading before debugging it. |
| [`launch_studio_cloudflare.py`](../launch_studio_cloudflare.py) | Exposes the local Studio (`localhost:5200`) to the internet via a free Cloudflare Quick Tunnel, for sharing with coworkers without deploying anywhere. See [`CLOUDFLARE_TUNNEL_GUIDE.md`](CLOUDFLARE_TUNNEL_GUIDE.md). |

## Airtable data maintenance

| Script | Purpose |
| :--- | :--- |
| [`normalize_airtable_rows.py`](../scripts/ops/normalize_airtable_rows.py) | Migrates legacy multi-product rows (several SKUs packed into numbered slots on one row) into one product per row. Only clears a legacy slot once its replacement row is confirmed created — safe to interrupt and re-run. |
| [`fill_missing_item_names.py`](../scripts/ops/fill_missing_item_names.py) | Backfills the `Item Name` field on legacy one-SKU-per-row tables still on the pre-slot schema. No-op on any table already migrated. |
| [`backfill_myth_and_fact_assets.py`](../scripts/ops/backfill_myth_and_fact_assets.py) | Backfills missing Logo Watermark / Outro Layout attachments specifically on the Chandelier Myth & Fact Story table. |
| [`backfill_1_product_3_styles_tags.py`](../scripts/ops/backfill_1_product_3_styles_tags.py) | Backfills missing `Blended Image with Name text` attachments across all 1 Product 3 Styles Feed tables (Chandeliers, Pendants, Floor Lamps) by downloading blended images, running YOLO detection, and stamping product title + category labels. |
| [`backfill_moodboard_1_feed_tags.py`](../scripts/ops/backfill_moodboard_1_feed_tags.py) | Backfills YOLO-World item name badges onto 'Moodboard V1 Blended' and 'Blended Image with Name text', and re-stamps the HomeCartel logo on 'Moodboard Added Watermark' across all Moodboard #1 Feed tables (Chandeliers, Pendants, Floor Lamps). |
| [`create_missing_zoho_folders.py`](../scripts/ops/create_missing_zoho_folders.py) | Creates the per-style subfolders expected under each Zoho WorkDrive category. Re-run safe — an existing folder is skipped with a warning, not an error. |
| [`provision_sketch_to_real_fields.py`](../scripts/ops/provision_sketch_to_real_fields.py) | Provisions the 8-phase Sketch to Real Reel schema (`Product Type`, `Music Generated`, and updated `Status` choices). Idempotent across all Sketch to Real tables. |
| [`scripts/ops/ensure_ad_cover_fields.py`](../scripts/ops/ensure_ad_cover_fields.py) | Provisions an Ad Cover table schema (default Chandelier `tblwIsDGZBPuYJV2Z`; all 9 fixture tables are wired — see `docs/ads/AD_COVER.md` §4 for the IDs): the standard columns (`Foreign Key ID`, `Moodboard ID`, `Prompt`, `Date and Time Generated`), the four product columns (`Furniture Item`, `SKU`, `Item Name`, `Item Price`), the five image attachment columns, the 8 `Status` choices, and the two 9:16 story attachment columns. Idempotent — creates only what is missing and reports the full field inventory. `--table-id` targets any other Ad Cover fixture table. |
| [`diff_env.py`](../scripts/ops/diff_env.py) | Scans and reconciles environment variable drift between `.env` and `.env.example`. Supports `--sync` to add safe placeholders for missing keys. |
| [`prune_output.py`](../scripts/ops/prune_output.py) | Safely prunes stale files in `output/` older than 30 days while preserving the latest 5 files per directory. Supports `--dry-run`. |
| [`content_automation/cleanup.py`](../content_automation/cleanup.py) | Scratchpad/temp-file lifecycle manager for containerized deploys (Zoho Catalyst / Docker) — purges `output/temp`, `output/temp_uploads`, and other scratch directories after upload, or on a scheduled age-based sweep, to prevent container disk exhaustion. |

## Item tagging (YOLO-World)

| Script | Purpose |
| :--- | :--- |
| [`standalone_item_tagger.py`](../standalone_item_tagger.py) | Interactive local web app: upload a room photo, detect furniture fixtures with local open-vocabulary YOLO-World, stamp editorial name labels, download the result. Manual/ad-hoc use. |
| [`run_blended_item_tagger.py`](../scripts/ops/run_blended_item_tagger.py) | Batch CLI version: scans an Airtable table for rows with a blended image, detects and tags furniture automatically, uploads the tagged photo back to the record. |

## Orchestration variants

| Script | Purpose |
| :--- | :--- |
| [`run_cta_round_robin.py`](../run_cta_round_robin.py) | Multi-table round-robin CTA Story orchestrator — processes one complete row (Phases 1–6) per table, then loops back to the start of the table queue for the next round, instead of exhausting one table before moving to the next. |

## Video assembly

| Script | Purpose |
| :--- | :--- |
| [`photo_video_maker.py`](../photo_video_maker.py) | Standalone vertical (9:16) product-photo video generator: Ken Burns zoom + push transitions between photos, optional title text, optional brand end card, optional audio track. Not wired to Airtable — takes a local photo folder and writes an MP4. |
| [`compile_product_description_videos.py`](../scripts/ops/compile_product_description_videos.py) | Assembles the Product Closeup w/ Description Story's 9:16 video reel: generates background music via Fal AI ElevenLabs Music, stitches the converted closeup card with the outro layout, uploads the result to `Product Closeup Video Reel` and marks the record `Complete`. |

## Diagnostics (read-only, safe to run anytime)

| Script | Purpose |
| :--- | :--- |
| [`probe_akeneo.py`](../scripts/ops/probe_akeneo.py) | Prints how many products a given Akeneo category/style query matches, plus a sample. Read-only sanity check for credentials and category codes — use this first when a pipeline reports zero/unexpected candidates, before assuming a code bug (see [`docs/memory/incidents/`](memory/incidents/) for a worked example). |
| [`preview_item_tag_overlay.py`](../scripts/previews/preview_item_tag_overlay.py) | Renders a single test image of the item-name-tag overlay (used by the YOLO-World item taggers above) onto a room photo, without touching Airtable. Use to iterate on tag placement/typography quickly. |
| [`preview_tips_edu_thumbnail.py`](../scripts/previews/preview_tips_edu_thumbnail.py) | Renders a single test image of the Tips & Educational Feed thumbnail title/subtitle text overlay onto a base image, without touching Airtable. |
| [`preview_logo_overlay.py`](../scripts/previews/preview_logo_overlay.py) | Renders a single test image of the HomeCartel logo watermark overlay, without touching Airtable. |
| [`preview_style_this_overlay.py`](../scripts/previews/preview_style_this_overlay.py) | Renders a single test image of the Style This story layout text/pill overlay, without touching Airtable. |
| [`verify_ad_cover_row.py`](../scripts/ops/verify_ad_cover_row.py) | Prints every Ad Cover row's FK, status, PHT timestamp and the attachment filenames/sizes in all five image fields (`Ad Cover Interior`, `Ad Cover Blended Image`, `Ad Cover Blended Image Story`, `Ad Cover Converted Image`, `Ad Cover Converted Image Story`). Read-only `list_records`; optional `record_id` argv. |
| [`verify_ad_cover_image.py`](../scripts/ops/verify_ad_cover_image.py) | Downloads both Ad Cover deliverables and asserts exact geometry — `(1080, 1080)` for `Ad Cover Converted Image` and `(1080, 1920)` for `Ad Cover Converted Image Story` — then samples the top/bottom bands for near-white pixels to prove the brand overlay actually composited. Exits 1 on any mismatch and skips an empty story field instead of failing. |
| [`audit_all_feed_subtabs.py`](../scripts/ops/audit_all_feed_subtabs.py) | Queries the running Studio server (port 5200) across all 7 Feed subtabs, verifying HTTP connectivity and dumping live row counts and status distributions. |

## Root entrypoints not covered by a pipeline doc

| Script | Purpose |
| :--- | :--- |
| [`generate_krea_interiors.py`](../generate_krea_interiors.py) | CLI to scrape Akeneo products and/or generate Krea room-interior photos. Run with no arguments in a terminal for an interactive menu; the implementation lives in `content_automation.scraping`. |
| [`run_dashboard.py`](../run_dashboard.py) | An older, separate web dashboard for Collection Category Feed automation. It reads from Google Drive (`G:/My Drive/Collection Category Feed`) and can open a free Cloudflare Tunnel (`--port`, `--no-tunnel`). It is **not** the Studio on port 5200 (`UI Control/api_server.py`). |
| [`scrape_product_description_story.py`](../scrape_product_description_story.py) | Scrapes Akeneo products into the Product Closeup w/ Description Story tables (Chandelier, Pendant Light, Floor Lamp, and others); imported by that story's runners. |

Thin aliases at root: `run_this_or_that.py` → `generate_this_or_that_pipeline.main`. Redundant and superseded alias stubs (`generate_before_after_reel.py`, `generate_sketch_to_draw_reel_pipeline.py`, `run_one_product_three_styles_feed.py`, `run_1_style_3_products_feed.py`, `run_3_products_1_style_feed.py`, and older `generate_moodboard_reel.py`) have been consolidated into `archive/legacy_runners/`.

## Unit tests (`tests/`)

Stdlib `unittest` suites; run all with `python -m unittest discover tests` from the repo root.

| File | Covers |
| :--- | :--- |
| `tests/test_foreign_key.py` | Foreign Key ID generation and `TABLE_PREFIX_MAP` prefixes |
| `tests/test_fal_client.py` | `FalClient.generate_seedance_video` (currently unused by any pipeline; see `docs/memory/decisions/one-at-a-time-lights-pivot-from-seedance.md`) |
| `tests/test_one_at_a_time_lights_pipeline.py` / `test_one_at_a_time_lights_route.py` | One at a time Lights Reel monolith (blend prompt, variations, item tags, crossfade assembly) and its Studio blueprint |
| `tests/test_generate_cta_story_pipeline.py`, `test_media_download_retry.py`, `test_studio_config_overrides.py` | CTA Story monolith, media download retry, Studio moodboard/prompt override persistence |
| `scratch/test_ad_cover_assets.py` | Ad Cover overlay-asset registry resolution |

---

Scripts not listed here (`generate_*.py`, `run_<fixture>_*.py`, `scripts/scrapers/scrape_*.py`) are the Story/Feed/Reel/Ad Cover pipeline entrypoints — those are catalogued in the main [`docs/README.md`](README.md) navigation index, not here.
