# Auto-caption for every Feed and Reel (no fallback template)

## Context
Calendar read-side fix is already done (Marketing Output UI, uncommitted). The write side is the bigger gap: only **Virtual Staging Reel** calls `generate_caption()`; Room Reveal / Room Build-Up only create an empty `Caption Generated` column; One Product 3 Styles Reel dumps its 3-5 word headline into it; the other Feeds/Reels write nothing. Stories, Ad Cover, Banners stay caption-free (decision 2026-10-26, guarded by `tests/test_caption_scope.py`).

User decisions: wire **all Feeds and Reels**, and **no generic fallback caption**: each content's own flow (from its md doc) goes into the prompt so the caption fits the content.

## Design
1. `content_automation/caption_flows.py` (new): `CAPTION_FLOWS: dict[str, str]`, one 1-2 sentence flow description per pipeline key, taken from `docs/feeds|reels/*.md` (e.g. `room_reveal`: "one locked camera, bare room, furniture appears layer by layer, ends on the fixture"; `day_night_feed`: "bright day slide vs same room at warm night"). Keys: tips_edu_feed, collection_feed, moodboard_1_feed, moodboard_2_feed, op3s_feed, day_night_feed, product_showcase_feed, day_night_reel, product_closeup_reel, before_after_reel, moodboard_reel, style_reel_slideshow, op3s_reel, oatl_reel, sketch_to_real_reel, house_tour_reel, room_build_up_reel, tmen_reel, virtual_staging_reel, room_reveal_reel.
2. `content_automation/caption.py`:
   - `build_caption_instruction(..., flow="")` adds the flow line to the Claude Vision prompt (format blocks unchanged).
   - `generate_caption(fal, item_name, product_type, image_urls, category, flow="") -> str`: one retry when the reply is unusable; returns `""` on any failure. **Delete `fallback_caption` and the `used_fallback` tuple.** Never raises.
   - New `write_row_caption(airtable, record_id, fields, fal, flow_key, item_name, product_type, image_urls, category) -> str`: skips if the row already has a caption (keeps manual edits), otherwise generates and writes `Caption Generated` in its own `try/except`; skips the write when empty. Name split via `akeneo_client.split_item_name`; type via `product_type_for_slot` (`prompts/scale.py`).
   - Failure never blocks `Complete`/`Done`; a failed caption just leaves the cell blank (logged `[WARN]`).
3. Call `write_row_caption` just **before** the Complete/Done update in each pipeline, re-reading the row so images are Airtable URLs (Product Closeup and Room Build-Up hold local paths). Anchor = slot 0 (Collection Feed uses slot 2; One at a Time Lights parses `Scraped Items`; Style Reel Slideshow uses the interior).

| Pipeline | File / function (approx. line of the Done write) | Images passed to Vision |
| :-- | :-- | :-- |
| Tips & Edu Feed | `run_tips_and_edu_feed.py` `phase_6` (2191, 2305) | Tips and Edu Feeds, Thumbnail |
| Collection Category Feed | `run_collection_category_feed.py` `run_phase_5_for_record` (1544) | Blended Image1..5 |
| Moodboard #1 Feed | `generate_moodboard_1_feed.py` (897, backstop 917) | Moodboard V1 Blended / Converted |
| Moodboard #2 Feed | `generate_moodboard_2_feed.py` (803) | Blended Image, Moodboard #2 Converted |
| 1 Product 3 Styles Feed | `run_1_product_3_styles_feed.py` (675) | 1 Product 3 Style Blended |
| Day & Night Feed | `generate_day_night_feed_pipeline.py` `finalize_feed_record` (631, 637; add `fal` arg) | Day Image, Night Image |
| Product Showcase Feed | `generate_product_showcase_feed_pipeline.py` (618) | FEED - Product Showcase Feed |
| Day & Night Reel | `phased_content.py` `_phase_8` / `_run_phase` (1049) | Day and Night Blended |
| Product Closeup Reel | `generate_product_closeup_reel_pipeline.py` (788) | tagged blends |
| Before & After Reel | `generate_before_after_reel_pipeline.py` (1437) | Blended Image, Multiple Angle |
| Moodboard Reel | `generate_moodboard_reel_pipeline.py` `run_phase_5_reel` (1654; add `fal` arg) | Moodboard Blended, Converted |
| Style Reel Slideshow | `run_style_reel_slideshow.py` (1857, 1651) | Interior1, Blended Image2..5 |
| 1 Product 3 Styles Reel | `run_one_product_three_styles_reel.py` (687, 742) | 1 Product 3 Style Blended |
| One at a Time Lights Reel | `generate_one_at_a_time_lights_reel_pipeline.py` (934) | Blended Image, Converted Image1..3 |
| Sketch to Real Reel | `generate_sketch_to_real_reel_pipeline.py` (1080) | tagged blend, Blended Image |
| House Tour Reel | `generate_house_tour_reel_pipeline.py` (2014) | tagged blend, Blended Image1..11 |
| Room Build-Up Reel | `generate_room_build_up_reel_pipeline.py` (822) | Room 1/2 Full |
| This Mood Every Night Reel | `generate_this_mood_every_night_reel_pipeline.py` (1091; uses `clients.fal()`) | tagged blends |
| Virtual Staging Reel | `generate_virtual_staging_reel_pipeline.py` (1069-1083) | switch to new helper, drop hardcoded "Chandelier" |
| Room Reveal Reel | `generate_room_reveal_reel_pipeline.py` (667) | Full |

4. Remove the headline-into-`Caption Generated` branch in `run_one_product_three_styles_reel.py` (~502-503) so it cannot block real captions.
5. Add `Caption Generated: multilineText` to the ensure-field lists that lack it (writing to a missing column would 422), and run `python scripts/ops/provision_caption_fields.py --dry-run` then for real (idempotent).

## Tests (stdlib unittest)
- `tests/test_caption.py`: replace the fallback tests (`test_fallback_never_empty`, `test_failure_returns_fallback_never_raises`, `test_unusable_reply_returns_fallback`, `test_none_client_returns_fallback`) with: failure / None client / short reply -> `""`; flow text appears in the prompt; retry happens once; existing caption is not overwritten; empty result writes nothing; `PipelineWiringTest` updated for the new VST call.
- `tests/test_caption_scope.py`: add a test that every Feed/Reel module above references `write_row_caption` and that `FLOWS` has all keys; stories/ads/banners still forbidden.
- Fix tests the wiring touches: `test_house_tour_kling.py:43` (`test_caption_is_gone`, now inverted), `test_sketch_to_real_music.py:132` (`update_record.assert_called_once` -> caption is a separate non-blocking write), `test_this_mood_every_night_pipeline.py:150` and `test_before_after_reel_runner.py:152` (patch `generate_caption`).

## Docs
AGENTS.md §4F ("Wired today", fallback sentence), `docs/feeds|reels/*.md` caption lines (Room Reveal L105, Sketch to Real L110, House Tour/Sketch docstrings "No caption"), `docs/README.md`, new note `docs/memory/decisions/2026-10-29-captions-all-feeds-reels-no-fallback.md` (supersedes "Wired today"; records that blank beats a generic template).

## Verification
- `python -m py_compile` on changed files; `python -m unittest discover tests`.
- One live check: call `write_row_caption` against a single already-Complete row of one reel and one feed via an explicit `--record-id`-style script (1 Claude Vision call each, no pipeline re-run), confirm text in Airtable and the Marketing Output UI calendar modal.
- No full pipeline re-runs (they create new rows and cost API credits).

## Not in scope / needs your OK
Commit / push / `main` deploy; captions for Stories, Ad Cover, Banners; back-filling captions on old completed rows (can add a one-off script later).

