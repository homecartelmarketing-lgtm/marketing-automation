# Tips & Edu Story: Nano Banana layout step redrew the room, doubled the logo, printed prompt text

**Symptom:** final stories (rows PE-20, PE-17) showed a different room than the blended image, two HomeCartel logos, and the literal words "Pre served Exactly" from the prompt. On Railway the name tag step also logged `No module named 'clip'`.

**Root cause:** Phase 5 sent the blended photo plus the Canva layout image to `fal-ai/nano-banana-pro/edit` with a JSON prompt. Nano Banana is a generator, not a compositor: it repaints the scene, re-draws the logo already present in the layout reference, and renders instruction text it cannot follow. This also broke AGENTS.md tenet 1 (layouts must be local Pillow). Separately, the Docker image had no `git`, so the YOLO-World/CLIP auto-install failed and the name tagger crashed.

**Fix:** Phase 5 now builds the story locally (`overlay.py::create_tips_edu_story_image`): blended photo as background, "Style Tip of the Day" (Poppins ExtraBold 40 pt) + underline + Claude-written tip (Poppins Regular 28 pt) + one logo via `stamp_logo`. The tip comes from Claude Sonnet 5 through `fal_client.generate_claude_vision` (`content_automation/story_tip.py`, with a per-category fallback). `item_tagger.tag_blended_image` falls back to the fixed tag position if YOLO/CLIP cannot load, and the Dockerfile installs `git` + Ultralytics CLIP before the YOLO pre-cache.

**Lesson:** never route text/logo layout through an image generator; measure the Canva layout and draw it with Pillow. Tests: `tests/test_tips_edu_story_layout.py`.
