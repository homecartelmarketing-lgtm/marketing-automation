# Room Reveal Reel Automation Pipeline

The **Room Reveal Reel Automation Pipeline** generates a **9:16 vertical reel (1080 x 1920 px)** filmed from **one locked camera angle**: it opens on the **bare room**, then the furniture appears piece by piece until the finished HomeCartel photo is complete, and the Final Video closes on the **branded 2.5 s outro card**.

The stills are **built in reverse**. Krea draws the furnished room, a fresh HomeCartel fixture is blended in, and Nano Banana Pro then removes the contents layer by layer (`Full` → `Layer 2` → `Layer 1` → `Empty`). Playback reverses that chain, so the room fills up instead of emptying:

```
Empty  →  Layer 1  →  Layer 2  →  Full  →  [outro card — Final Video only]
```

There are no transitions, only hard cuts, and the camera never moves. Every removal prompt carries a tripod/locked-camera suffix, and a local similarity check rejects any edit that changed the angle.

> **Reference video:** the client's "one room, two angles" MP4 (30 fps, 720x1280). This pipeline keeps the pacing and the empty-then-filled idea but renders at 1080x1920 from a single angle.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, frame-exact cuts
- **Raw Video Duration**: `100` frames = `3.33s` (silent build-up, no outro)
- **Final Video Duration**: `175` frames = `5.83s` (build-up + `2.5s` outro card)
- **Structure**: 4 build-up segments from 4 stills, then the outro card in the Final Video only. Cuts land on frames `24, 44, 64` (0.80 / 1.47 / 2.13 s); the outro starts at frame `100` (3.33 s):

| Segment | State | Frames | Raw Video | Final Video |
| :---: | :--- | :---: | :---: | :---: |
| 1 | `Empty` | 24 | yes | yes |
| 2 | `Layer 1` | 20 | yes | yes |
| 3 | `Layer 2` | 20 | yes | yes |
| 4 | `Full` | 36 | yes | yes |
| 5 | Outro card (`assets/outro_layout.jpg`) | 75 | no | yes |

The `Empty` state holds 24 frames (0.8 s) at the open and the finished `Full` photo holds 36 frames (1.2 s) before the outro, so the completed blend is what the viewer remembers.

- **Audio**: ElevenLabs sound effects (shared with Room Build-Up Reel). A `whoosh` plays at the start (0.08 s) and again as the outro card appears (3.33 s); a `pop` plays on every layer cut (0.80 / 1.47 / 2.13 s). The sounds live in `assets/room_buildup_sfx/` and are generated once; if ElevenLabs does not answer within 60 s the pipeline uses a locally synthesized stand-in rather than stall the run. The Raw Video stays silent.
- **Outro**: the shared 1080x1920 HomeCartel end card, held 2.5 s — Final Video only. No captions, no other on-screen text.

---

## 2. Model Stack Phase Table (7 phases)

The log prints `[PHASE n/7]` markers that the Studio reads.

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape (1 fresh fixture)** | Akeneo PIM API | Active ingestion + strict Shopify Active & Published verification + base-wide dedup | 1 fixture from `ROOM_REVEAL_REEL_CATEGORY` (default `chandeliers`) | Brand-new row, `Foreign Key ID`, `Furniture Item`, `Item Name`, `SKU`, `Product Type`, `Measurement` -> Status: `In progress` |
| **Phase 2** | **Krea Furnished Interior** | Krea AI | 9:16, 1K. Fixed prompt + moodboard (one room, one angle) | `PROMPT_ROOM_REVEAL_REEL` + `KREA_MOODBOARD_ID_ROOM_REVEAL_REEL` | `Room Interior` |
| **Phase 3** | **Claude Blending Prompt** | Fal AI | `anthropic/claude-sonnet-5` (vision) | `Room Interior` + `Furniture Item` + `Measurement` | `Blending Prompt` |
| **Phase 4** | **Nano Banana Pro Fixture Blend** | Fal AI + scale guard | `fal-ai/nano-banana-pro/edit`, 9:16, 1K, wrapped by `blend_with_scale_guard` | Interior + fixture + `Blending Prompt` | `Full` (+ scale audit fields) |
| **Phase 5** | **Claude Removal Plan** | Fal AI | `anthropic/claude-sonnet-5` (vision) | `Full` | `Removal Plan` (JSON: `inventory` + 3 cumulative `prompts`) |
| **Phase 6** | **Nano Banana Pro Removals** | Fal AI | `fal-ai/nano-banana-pro/edit`. Chain: `Full` → `Layer 2` → `Layer 1` → `Empty` | `Full` + `Removal Plan` | `Layer 2`, `Layer 1`, `Empty` |
| **Phase 7** | **Build-Up Assembly + Outro + Sound** | Local FFmpeg + Fal ElevenLabs SFX | `imageio-ffmpeg`, frame-exact hard cuts | 4 stills + `assets/outro_layout.jpg` + pop/whoosh sounds | `Raw Video` (silent build-up), `Final Video` (build-up + outro) -> Status: `Done` |

Every removal is applied to the **result of the previous step** (never to the raw Krea interior), so the blended fixture is what disappears first and the room unwinds from there.

---

## 3. Phase 5 & 6 Details: Removal Plan and Quality Gates

### Phase 5: Claude removal plan
Claude looks at the blended `Full` room and returns `{"inventory": [...], "prompts": [p1, p2, p3]}`. The prompts are **cumulative**:

1. Remove the HomeCartel fixture plus small decor and accessories. Everything else stays.
2. Remove soft furnishings and secondary pieces (rugs, curtains, wall art, mirrors, side tables...). Only the largest furniture stays.
3. Remove all remaining furniture so only bare walls, floor, windows and ceiling remain, restoring the surfaces behind every removed object.

If Claude's JSON is unusable, `DEFAULT_REMOVAL_PROMPTS` supplies exactly 3 generic prompts. Every prompt gets `KEEP_IDENTICAL_SUFFIX`: the camera is locked on a tripod, and angle, perspective, framing, walls, windows, floor, ceiling and lighting must stay identical.

### Phase 6: Step validation
Each removal gets up to `MAX_STEP_ATTEMPTS = 3` attempts. A result passes when it stays similar to its input (`MIN_STEP_SIMILARITY = 0.72`, computed on a blurred 48x85 grayscale copy) and has less visual detail than the previous state (`MIN_DETAIL_DROP = 0.97`, edge density). This pins the camera angle and proves each layer actually removed something. If no attempt passes every check, the closest similar attempt is kept; if nothing is similar enough, the step raises an `AutomationError`.

---

## 4. Foreign Key ID Convention & Examples

$$\text{Format: } \mathbf{RRV\text{-}REEL\text{-}SET\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `RRV` (Room Reveal)
- **Content Format**: `REEL`
- **Fixture Code**: `SET` (one room set — the fixture type comes from `ROOM_REVEAL_REEL_CATEGORY`)

Examples: `RRV-REEL-SET-1`, `RRV-REEL-SET-2`.

---

## 5. Supported Airtable Table & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- |
| **Room Reveal** | `SET` | `tbldk5nac1UeYHd77` | `AIRTABLE_TABLE_ID_ROOM_REVEAL_REEL` |

| Krea Setting | Environment Variable | Default |
| :--- | :--- | :--- |
| Moodboard ID | `KREA_MOODBOARD_ID_ROOM_REVEAL_REEL` | `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3` |
| Interior prompt | `PROMPT_ROOM_REVEAL_REEL` | `Generate me a modern living room` |
| Scraped category | `ROOM_REVEAL_REEL_CATEGORY` | `chandeliers` |

The Studio pencils write the moodboard and prompt values to these keys (see [`../UI_CONTROL_CONFIG.md`](../UI_CONTROL_CONFIG.md)). The table `tbldk5nac1UeYHd77` is already provisioned (23 fields, `Status`, `ID`); the pipeline re-checks and creates anything missing on every run.

### Airtable Schema

| Field | Type |
| :--- | :--- |
| `Foreign Key ID`, `Date and Time Generated`, `Date and Time Scheduled` | singleLineText / dateTime |
| `Caption Generated` | multilineText (Instagram caption, written in Phase 7 before `Done`; blank if Claude fails) |
| `Status` | singleSelect (`In progress` / `Done` / `Scheduled` / `Posted` / `Discard` / `For Manual`) |
| `ID` | autoNumber (created if missing) |
| `Furniture Item` | attachment (scraped fixture photo) |
| `Item Name`, `SKU`, `Product Type`, `Measurement` | multilineText / singleLineText |
| `Room Interior` | attachment |
| `Blending Prompt`, `Removal Plan` | multilineText |
| `Full`, `Layer 2`, `Layer 1`, `Empty` | attachment (the 4 room states) |
| `Raw Video`, `Final Video` | attachment |

The pipeline creates any missing field on first run (and the scale-audit fields via `ensure_scale_fields`).

---

## 6. Web Studio (UI Control) & CLI

- **Generator**: `generate_room_reveal_reel_pipeline.py` (root monolith).
- **Runner alias**: `run_room_reveal_reel.py`.
- **Flask route**: `UI Control/routes/room_reveal_reel.py` (`/api/room-reveal-reel/*`). It spawns `run_room_reveal_reel.py`.
- **Studio location**: Reel tab, subtab **"Room Reveal"** (single card, id `room-reveal`), after Virtual Staging.
- **CLI**:
  ```bash
  # Thin alias; flags: --table-id, --phase all|scrape|generate, --max-rows/--max-items,
  # --record-id, --style, --category, --moodboard-id, --prompt, --force
  python run_room_reveal_reel.py --max-rows 1
  python run_room_reveal_reel.py --record-id recXXXXXXXX     # re-render one explicit row
  ```
  Without `--record-id` every run scrapes a brand-new row (AGENTS.md §1 and §5). `--phase generate` requires `--record-id`.

---

## 7. Cost Notes (one row, one attempt each)

| Step | Calls |
| :--- | :--- |
| Krea interior | 1 |
| Claude blending prompt | 1 |
| Nano Banana blend | 1 (2 when the scale guard retries) |
| Claude removal plan | 1 |
| Nano Banana removals | 3 (up to 9 when a step retries) |
| ElevenLabs SFX | 0 after the first run (cached in `assets/room_buildup_sfx/`) |

The per-run text log lives in the Studio's run panel only while the job runs; the Airtable row (`Removal Plan`, attachments) is what remains afterwards.
