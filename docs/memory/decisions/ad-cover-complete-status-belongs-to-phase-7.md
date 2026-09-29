# Ad Cover: `Complete` moved from Phase 5 to Phase 7

When Phases 6-7 (9:16 Story branch) were added to `generate_ad_cover_pipeline.py`, Phase 5
stopped writing `Status: Complete`. Only Phase 7 stamps it now.

**Why:** `Status` is an Airtable `singleSelect`, so every phase write overwrites the previous
value, and `fetch_status_breakdown` only badges `Complete/Completed/Done` — every
`… Generated` status lands in **no** badge. If Phase 5 kept stamping `Complete`, Phase 6
would replace it with `Ad Cover Blended Image Story Generated` and the row would vanish from
the `C` badge for the rest of the run — permanently, if the story branch then died. The Ad
Covers card count would quietly drop rows that actually had a finished 1:1 deliverable.

**How the failure path works:** if Phase 6 or 7 fails, the `all` loop prints `[ERROR]`, counts
a separate `story_failures`, **re-asserts `Complete`** (the 1:1 cover is done and must keep its
badge + PHT timestamp) and still exits non-zero so the Studio shows a red banner. Recovery is
the sanctioned `--mode story-blend` / `--mode story-conversion --record-id rec…` pair.

**Other decisions in the same change:**
- Story assets live in their own registry (`AD_COVER_STORY_ASSETS` / `AD_COVER_STORY_CANVAS_SIZE`)
  rather than reusing the square one, so a fixture without a story PNG can't get the square
  overlay stretched across 1080x1920. A missing story asset is a **skip** (`return True`), not a failure.
- Phase 6 uses a dedicated outpaint prompt (`AD_COVER_STORY_CONVERSION_PROMPT`), not the Phase 3
  `Prompt` field — re-describing the room would let Nano Banana Pro redesign it instead of
  extending the frame. `overlay_ad_cover_layout` centre-crops, so a square answer from Phase 6
  would chop the left/right thirds of the room in Phase 7.
- The Studio `detect_phase()` became numeric-first (`phase (\d+)/\d+` against
  `AD_COVER_PHASE_LABELS`) because substring rules mis-classified the new story lines, and the
  startup banner is now ignored (an old `"ad cover" in lower` disjunct matched every banner line
  and opened runs at "Phase 5").
