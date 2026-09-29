---
date: 2026-09-29
pipeline: One at a time Lights Reel
status: decided
---

# One at a time Lights Reel: progressive blends + FFmpeg crossfade instead of Seedance

## Decision

The reel is built from **3 fixtures** (Table Lamp, Ceiling Mounted, Pendant) that are blended into one Krea bedroom. Phase 5 then generates three "only this light is ON" variations with Nano Banana Pro. Phase 6 assembles them locally with FFmpeg `xfade` crossfades: ~11s, silent, plus the brand outro. It does **not** use Seedance 2.0 reference-to-video.

The earlier plan (`docs/superpowers/plans/2026-09-28-one-at-a-time-lights-reel.md`) specified Seedance with 4 fixtures and a ~13s reel. It was superseded within a day.

## Why

The spec (`docs/reels/ONE_AT_A_TIME_LIGHTS_REEL.md`) states the goal: zero morphing artifacts and a stationary camera. Image edits from one base blend give that framing, and local FFmpeg assembly keeps Phase 6 at zero API cost. (The exact reason for dropping Seedance was not recorded; this is the rationale the spec gives.)

## Leftovers to know about

- `FalClient.generate_seedance_video` (`content_automation/fal_client.py`) and its tests (`tests/test_fal_client.py`) still exist but no pipeline calls them.
- `ONE_AT_A_TIME_LIGHTS_MOTION_PROMPT` in `.env.example` is a Seedance leftover and is unused.
- `content_automation/video.py::merge_video_with_outro_and_audio` gained an optional `fade_in_seconds` (default `0.0`, so every other reel is unchanged). The shipped One at a time Lights pipeline does not use it; it assembles its own crossfade and deliberately has no black fade-in.

See [[ONE_AT_A_TIME_LIGHTS_REEL]] for the current spec.
