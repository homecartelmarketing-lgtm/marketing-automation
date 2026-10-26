# Room Reveal stalled at Phase 7 on the ElevenLabs sound-effect poll

**Symptom.** A Studio run (row `recf63KlmhlCE6Ghj`, `RRV-REEL-SET-4`) never finished even though
everything visible was done: `Room Interior`, `Full`, `Layer 2`, `Layer 1`, `Empty` and `Raw Video`
were attached, `Status` sat on `In progress`, and no `Final Video` appeared. The process stayed alive
with flat CPU (16 s), no child processes, and a large thread count, so it looked "stuck after finishing".

**Root cause.** Not the images and not the video. `ensure_sfx_assets`
(`generate_room_build_up_reel_pipeline.py`, shared with Room Build-Up) calls
`FalClient.generate_elevenlabs_sound_effect` for the `pop`/`whoosh` sounds, and Fal's ElevenLabs
sound-effects queue job never completed. Two things made that fatal instead of cosmetic:

1. `poll_queue_raw` used the client-wide `max_wait` of **1200 s**.
2. When polling gave up (or the job reported `FAILED`) the method fell through to the *synchronous*
   endpoint with `timeout=180` and `request_with_retry`'s 5 attempts — up to 15 more minutes per sound.

So a wedged 1-second sound could hold an otherwise finished run for ~35 minutes per sound. A `py-spy
dump --pid <generator>` stack (the decisive evidence) showed `poll_queue_raw` →
`generate_elevenlabs_sound_effect` → `ensure_sfx_assets` → `phase7_assemble`. Process sockets were
the red herring: the open ones pointed at `fal.run`, not Zoho.

**Fix.**
- `FalClient.poll_queue_raw(..., max_wait=None)` accepts a per-call budget, and
  `generate_elevenlabs_sound_effect(..., max_wait=None)` re-raises `ProviderTimeout` instead of
  falling into the long synchronous call (a stuck queue will not be rescued by a second, slower path).
- `generate_room_build_up_reel_pipeline.SFX_MAX_WAIT_SECONDS = 60.0` is passed by `ensure_sfx_assets`,
  which already falls back to a locally synthesized stand-in under `assets/room_buildup_sfx/`.

**Recovering a row stuck this way.** Do not re-run the whole pipeline: phases 2-6 skip when their
field/attachment already exists, so `python run_room_reveal_reel.py --record-id <rec> --table-id
tbldk5nac1UeYHd77` re-downloads the existing stills and only redoes Phase 7 (zero paid API cost).
That re-run re-uploads `Raw Video`, which leaves two copies in the field; keep the newest with
`update_records([(rec, {"Raw Video": [{"id": <latest>}]})])`.

**Related.** `upload_attachment` mirrors every `.mp4` to Zoho WorkDrive, so Phase 7 also waits on two
Zoho uploads; that is bounded by `request_with_retry` but is still real wall-clock time in the log.
