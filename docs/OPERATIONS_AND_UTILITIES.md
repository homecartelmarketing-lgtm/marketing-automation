# Operations & Utility Scripts

Root-level scripts that keep the system healthy but aren't Story/Feed/Reel content pipelines and weren't previously catalogued anywhere. Descriptions are pulled from each script's own module docstring.

## Scheduling & hosting

| Script | Purpose |
| :--- | :--- |
| [`run_auto_post_scheduler.py`](../run_auto_post_scheduler.py) | Polls an external scheduling API every 60s and publishes due Stories/Feeds/Reels to Instagram at their scheduled PHT time. See [`AUTO_POST_SCHEDULER.md`](AUTO_POST_SCHEDULER.md) — has an undocumented cross-repo dependency worth reading before debugging it. |
| [`launch_studio_cloudflare.py`](../launch_studio_cloudflare.py) | Exposes the local Studio (`localhost:5200`) to the internet via a free Cloudflare Quick Tunnel, for sharing with coworkers without deploying anywhere. See [`CLOUDFLARE_TUNNEL_GUIDE.md`](CLOUDFLARE_TUNNEL_GUIDE.md). |

## Airtable data maintenance

| Script | Purpose |
| :--- | :--- |
| [`normalize_airtable_rows.py`](../normalize_airtable_rows.py) | Migrates legacy multi-product rows (several SKUs packed into numbered slots on one row) into one product per row. Only clears a legacy slot once its replacement row is confirmed created — safe to interrupt and re-run. |
| [`fill_missing_item_names.py`](../fill_missing_item_names.py) | Backfills the `Item Name` field on legacy one-SKU-per-row tables still on the pre-slot schema. No-op on any table already migrated. |
| [`backfill_myth_and_fact_assets.py`](../backfill_myth_and_fact_assets.py) | Backfills missing Logo Watermark / Outro Layout attachments specifically on the Chandelier Myth & Fact Story table. |
| [`backfill_1_product_3_styles_tags.py`](../backfill_1_product_3_styles_tags.py) | Backfills missing `Blended Image with Name text` attachments across all 1 Product 3 Styles Feed tables (Chandeliers, Pendants, Floor Lamps) by downloading blended images, running YOLO detection, and stamping product title + category labels. |
| [`backfill_moodboard_1_feed_tags.py`](../backfill_moodboard_1_feed_tags.py) | Backfills YOLO-World item name badges onto 'Moodboard V1 Blended' and 'Blended Image with Name text', and re-stamps the HomeCartel logo on 'Moodboard Added Watermark' across all Moodboard #1 Feed tables (Chandeliers, Pendants, Floor Lamps). |
| [`create_missing_zoho_folders.py`](../create_missing_zoho_folders.py) | Creates the per-style subfolders expected under each Zoho WorkDrive category. Re-run safe — an existing folder is skipped with a warning, not an error. |
| [`content_automation/cleanup.py`](../content_automation/cleanup.py) | Scratchpad/temp-file lifecycle manager for containerized deploys (Zoho Catalyst / Docker) — purges `output/temp`, `output/temp_uploads`, and other scratch directories after upload, or on a scheduled age-based sweep, to prevent container disk exhaustion. |

## Item tagging (YOLO-World)

| Script | Purpose |
| :--- | :--- |
| [`standalone_item_tagger.py`](../standalone_item_tagger.py) | Interactive local web app: upload a room photo, detect furniture fixtures with local open-vocabulary YOLO-World, stamp editorial name labels, download the result. Manual/ad-hoc use. |
| [`run_blended_item_tagger.py`](../run_blended_item_tagger.py) | Batch CLI version: scans an Airtable table for rows with a blended image, detects and tags furniture automatically, uploads the tagged photo back to the record. |

## Orchestration variants

| Script | Purpose |
| :--- | :--- |
| [`run_cta_round_robin.py`](../run_cta_round_robin.py) | Multi-table round-robin CTA Story orchestrator — processes one complete row (Phases 1–6) per table, then loops back to the start of the table queue for the next round, instead of exhausting one table before moving to the next. |

## Video assembly

| Script | Purpose |
| :--- | :--- |
| [`photo_video_maker.py`](../photo_video_maker.py) | Standalone vertical (9:16) product-photo video generator: Ken Burns zoom + push transitions between photos, optional title text, optional brand end card, optional audio track. Not wired to Airtable — takes a local photo folder and writes an MP4. |
| [`compile_product_description_videos.py`](../compile_product_description_videos.py) | Assembles the Product Closeup w/ Description Story's 9:16 video reel: generates background music via Fal AI ElevenLabs Music, stitches the converted closeup card with the outro layout, uploads the result to `Product Closeup Video Reel` and marks the record `Complete`. |

## Diagnostics (read-only, safe to run anytime)

| Script | Purpose |
| :--- | :--- |
| [`probe_akeneo.py`](../probe_akeneo.py) | Prints how many products a given Akeneo category/style query matches, plus a sample. Read-only sanity check for credentials and category codes — use this first when a pipeline reports zero/unexpected candidates, before assuming a code bug (see [`docs/memory/incidents/`](memory/incidents/) for a worked example). |
| [`preview_item_tag_overlay.py`](../preview_item_tag_overlay.py) | Renders a single test image of the item-name-tag overlay (used by the YOLO-World item taggers above) onto a room photo, without touching Airtable. Use to iterate on tag placement/typography quickly. |
| [`preview_tips_edu_thumbnail.py`](../preview_tips_edu_thumbnail.py) | Renders a single test image of the Tips & Educational Feed thumbnail title/subtitle text overlay onto a base image, without touching Airtable. |

---

Scripts not listed here (`generate_*.py`, `run_<fixture>_*.py`, `scrape_*.py`) are the Story/Feed/Reel pipeline entrypoints — those are catalogued in the main [`docs/README.md`](README.md) navigation index, not here.
