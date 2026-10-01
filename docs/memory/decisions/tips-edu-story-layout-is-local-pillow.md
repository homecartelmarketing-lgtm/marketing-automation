---
tags: [decision, tips-edu-story, pillow]
---

# Tips & Edu Story: the layout is drawn locally, never by an image generator

**Decision:** Phase 5 composes the story with Pillow (`overlay.py::create_tips_edu_story_image`) on top of the blended photo. Claude Sonnet 5 (via Fal) only writes the one-sentence tip. Nano Banana Pro is used for the room blend (Phase 4) and nowhere else in this pipeline.

**Why:** an image generator repaints the whole frame, so it changed the room, duplicated the logo and printed prompt text (see [[../incidents/2026-10-01-tips-edu-story-nano-banana-layout-redrew-room]]). Local drawing is exact, free, and matches AGENTS.md tenet 1.

**Details worth keeping:**
- Sizes from Canva are points: 1 pt = 4/3 px (`CANVA_PT_TO_PX`), so 40 pt is 53.33 px and 28 pt is 37.33 px. Reading them as literal pixels makes the title visibly smaller than the Canva layout.
- Positions were measured from `JSON Prompts/Tips and Edu Story/stories (33).jpg` (title ink x=121, y=1369; underline x=113-632, y=1437; tip origin x=113, y=1541).
- A bottom gradient (`TIPS_EDU_STORY_GRADIENT_START_Y`, `TIPS_EDU_STORY_GRADIENT_MAX_ALPHA` in `overlay.py`) keeps white text readable on light rooms. The Canva layout is plain black; set the alpha to 0 to remove the gradient.
- If the Claude call fails or returns an unusable sentence, `story_tip.fallback_tip` supplies a neutral per-category tip so the run still reaches Complete (logged as `tip_used_fallback`).

Doc: [[../../stories/TIPS_AND_EDU_STORY]].
