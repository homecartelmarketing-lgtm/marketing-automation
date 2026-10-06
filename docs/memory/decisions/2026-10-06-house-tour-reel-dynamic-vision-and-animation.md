---
date: 2026-10-06
pipeline: House Tour Reel
status: decided
---

# House Tour Reel: Reference Pacing, Dynamic Claude Vision Analysis, Animated Poppins Reveal, and Zero Fallback Policy

## Decision

The House Tour Reel (`generate_house_tour_reel_pipeline.py`, table `tblqXkdDw4O7hxJS4`) has been modernized with the following architectural standards:

1. **Pre-Crafted Prompts & Unified Moodboard**:
   Replaced dynamic reference MP4 clip splitting with 11 ultra-detailed, video-accurate room prompts derived frame-by-frame from `assets/house_tour_reference.mp4`, paired with a single unified Japandi moodboard ID (`fda7090c-787b-4116-94cd-3feef613eaaa`) across all 11 rooms.

2. **Phase 2.5 Dynamic Room Analysis (Claude 3.5 Sonnet Vision)**:
   After Krea generates room interiors (Phase 2), Claude Vision inspects each interior image to extract:
   - Specific fixture placement guidance used to instruct Claude blending prompts in Phase 3.
   - An editorial lowercase room title (`5. ROOM TITLE: ...`, e.g., `living room lounge`, `dining nook`, `kitchen counter`).

3. **Strict Zero Default Fallback Policy for Room Titles**:
   If Claude Vision fails, times out, or omits a room title, the upper-third text is **completely omitted** (`""` — no text filter is generated).
   - Hardcoded room dictionaries (`REFERENCE_MILESTONE_TITLES` and `SLOT_DEFAULT_ROOM_TITLES`) are **completely removed**.
   - No generic/fallback room styles (such as `"mini home tour"`, `"living room"`, `"kitchen"`, etc.) will ever be stamped unless explicitly identified by Claude Vision.

4. **Lower-Third Animated Product Reveal (Poppins Typography)**:
   Phase 8 FFmpeg assembly renders an animated product reveal at `y = 1600` (lower-third) using `Poppins-Medium.ttf` (32px):
   - Text is formatted as normalized **Item Name + Product Type** (e.g., `kansa table lamp`, `indus wall light`).
   - The reveal slides upward by 20px and fades in opacity from 0 to 1 between `t = 0.25s` and `t = 0.55s` into each shot cut via dynamic FFmpeg expressions.
   - All video layout and typography execution is 100% local with zero API cost.

5. **22.0s Pacing (2.0s per Room)**:
   The video cut structure uses exactly **2.0 seconds per room** across all 11 rooms (`22.0s` total runtime with clean snap cuts; `24.5s` with optional outro). Trims `0.5s` to `2.5s` from each 3.0s Kling clip to capture constant camera velocity. This gives viewers ample time to appreciate the interior design and read the animated product reveal without feeling rushed. Optional relaxed 24.5s crossfade pacing remains supported via `--pacing relaxed`.

## Rationale

- Eliminates fragile reference-video splitting during runtime, guaranteeing consistent, ultra-high-fidelity Japandi room aesthetics.
- Dynamic Claude Vision placement avoids awkward product placements in diverse generated scenes.
- Removing hardcoded room fallbacks ensures that inaccurate room labels are never stamped on the final video when vision analysis is unavailable.
- Lower-third animated typography provides high luxury editorial engagement matching TikTok and Instagram Reels design trends while strictly honoring the repository's zero-API-cost layout tenet.

See [[HOUSE_TOUR_REEL]] for the complete pipeline specification.
