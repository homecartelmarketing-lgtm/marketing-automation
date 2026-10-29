# Captions on every Feed and Reel, no fallback template (2026-10-29)

**Decision.** Every Feed and Reel pipeline writes `Caption Generated` just before `Complete`/`Done` using `content_automation/caption.py::write_row_caption`. The prompt carries a per-content flow description (`content_automation/caption_flows.py`, copied from `docs/feeds|reels/*.md`) so the caption matches what the post shows (day to night, empty to furnished, 3 styles, ...).

**No fallback.** The old deterministic template (`fallback_caption`, `used_fallback`) is removed. Claude gets one retry; if the reply is still unusable the cell stays blank and a `[WARN]` is logged. A blank cell is visible and easy to fix by hand, a generic caption looks real and gets published.

**Why.** Only Virtual Staging Reel wrote a caption, so the Marketing Output UI content calendar showed none for other Feeds/Reels once scheduled. The read side was fixed in `Marketing Output UI/lib/caption.ts` (`Caption Generated` first, then `Generated Caption`, `Caption`).

**Rules kept.** Never blocks `Complete`/`Done`; existing captions are never overwritten; Stories, Ad Cover and Banners stay caption-free (2026-10-26 note, `tests/test_caption_scope.py`). `Reel Headline` is not a caption: One Product 3 Styles Reel no longer writes its headline into `Caption Generated`.

**How to apply.** New Feed/Reel pipeline: add a key to `CAPTION_FLOWS`, call `write_row_caption(...)` before the Done update, and list the module in `tests/test_caption_scope.py::CAPTION_PIPELINES`.

**Known gap.** `generate_moodboard_1_feed.finalize_completed_records` bulk-completes rows that have a Closeup Photo without going through the caption step.
