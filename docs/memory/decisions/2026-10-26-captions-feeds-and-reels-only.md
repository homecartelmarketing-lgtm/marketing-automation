# Captions are feeds-and-reels only

**Date:** 2026-10-26

The Instagram caption phase (`content_automation.caption.generate_caption()` →
`Caption Generated`) was removed from the six Story pipelines, the Ad Cover
pipeline and both banner pipelines. It now belongs to Feed and Reel pipelines
only.

**Why:** the user wants the auto-generated caption on feeds and reels, not on
stories, ads or banners. The `Caption Generated` column and the caption values
already written by past runs are untouched; only new generation was removed.

**How to apply:**

- Do not add a caption phase to a Story, Ad Cover or Banner pipeline.
- `generate_room_build_up_reel_pipeline.py` and
  `generate_room_reveal_reel_pipeline.py` still provision the empty
  `Caption Generated` column for manual use; that is not generation.
- The Sale Banner's `Sale Caption Left` / `Sale Caption Right` fields are
  calendar text baked into the banner image. They are a separate feature and
  stay.
- `tests/test_caption_scope.py` guards the scope; update it if a new pipeline
  legitimately needs a caption.
