# Before & After Reel: every Studio run died at startup (ImportError)

**Symptom:** the Before & After Reel failed immediately when run from the Control UI ("Process exited with code 1", no phase ever started).

**Root cause:** `run_before_after_reel.py` imported `TERMINAL_AND_PROTECTED_STATUSES` from `generate_before_after_reel_pipeline.py`, which no longer defined it, so the subprocess crashed on import. Fixing that exposed more bugs behind it: the runner passed `record_ids=` to phase functions that did not accept it (TypeError), the runner re-processed old incomplete rows first ("BACKLOG FOUND", forbidden by AGENTS.md §5), the YOLO name-tag block referenced an undefined `category` (the tag was silently skipped; 4 of the 5 newest rows had no tagged image), media downloads bypassed the retry helper, a failed angle download still marked the record done, and the slideshow `finally` raised `UnboundLocalError` for `audio_temp`.

**Fix:** the constant is defined again and used by `restrict_records`; every phase accepts `record_ids`; the runner always scrapes a fresh row (explicit `--record-id` is the only exception) and exits non-zero when nothing new was scraped; downloads use `download_url_to_temp_file(fal.session, ...)`; angles/blended export are required before upload/Complete; the tag category comes from the target or the item name; explicit `[PHASE n/6]` markers drive the Studio phase display.

**Guard:** `tests/test_runner_imports.py` imports every root `run_*.py` / `generate_*.py`, and `tests/test_before_after_reel_runner.py` covers the flow. The earlier `tests/test_media_download_retry.py` failures were this same pipeline.

## Follow-up: the item name never appeared in the reel video

The video only used the title thumbnail, the 4 angle images (generated from the untagged blend) and the outro; the name-tagged `Blended Image with Name text` was only used for the Claude title and the Drive export. `build_before_after_slideshow_video` now takes `after_image_path` (3 s, right after the Before slide) and the slideshow phase passes the tagged blend, stamping the tag locally with `tag_blended_image` when the row only has the plain blend. Tests: `SlideshowAfterSlideTests`, `SlideshowPipelineNameTagTests` in `tests/test_before_after_reel_runner.py`. Reels made before this change need a re-render (`--record-id` after clearing the slideshow field) to get the name slide.
