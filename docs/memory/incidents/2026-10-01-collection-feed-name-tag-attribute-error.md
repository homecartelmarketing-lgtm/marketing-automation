# Collection Category Feed: `Blended Image with Name text` had no item-name tags

**Symptom:** rows `CC-FEEDS-SET-23` and `-24` had 4 images in `Blended Image with Name text`, but none showed the YOLO item-name tag (only the HomeCartel logo).

**Root cause:** Phase 5 in `run_collection_category_feed.py` read `slot.suggest_furniture_field`, an attribute `SlotConfig` does not have (the real one is `suggest_field_candidates`). The `AttributeError` was caught by a broad `except` that only printed `[WARN] YOLO tagging notice ...`, so tagging was silently skipped and the untagged image was still logo-stamped and uploaded to both `Blended ImageN` and `Blended Image with Name text`. Introduced in `fb756e5`.

**Fix:** tagging moved into `stamp_item_name_tag` (returns True only when a tag was drawn). Category comes from the `[CATEGORY: table_lamps]` token in `Suggest Furniture ItemN` (long free text could not be matched by `item_tagger.get_detection_queries_for_category`), the second tag line is the product type instead of the room name, the log says `NOT stamped` on failure, and untagged images are no longer mirrored to the name-text field. Tests: `tests/test_collection_category_feed_tagging.py`.

**Existing rows:** rows created before the fix keep untagged images (Phase 5 skips slots that already have a blended image); they need a one-off backfill.

**Lesson:** a broad `except Exception` around a whole step hides typos; log the exception type and never report success unless the step really ran.
