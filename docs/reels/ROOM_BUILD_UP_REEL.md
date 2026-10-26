# Room Build-Up Reel Automation Pipeline

The **Room Build-Up Reel Automation Pipeline** generates a **~4.8-second 9:16 vertical stop-motion reel (1080 x 1920 px)** in which two rooms are furnished in four hard-cut steps each: empty room, then two intermediate layers, then the fully furnished room with a HomeCartel fixture installed. A short pop sound plays on every change.

The reel is built **in reverse**. Krea draws a fully furnished room, a fresh HomeCartel fixture is blended in, and Nano Banana Pro then removes the contents layer by layer (Full to Layer 2 to Layer 1 to Empty). The stills are finally played empty to furnished with local FFmpeg. The camera never moves, and there are no transitions, only hard cuts.

> **Reference video:** `new-contnet.mp4` (30 fps, 144 frames = 4.8 s, hard cuts, no transitions).

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, frame-exact cuts
- **Reel Duration**: `144` frames = `4.8s`
- **Structure**: 8 stills, 4 per room (Room 1, then Room 2). Cuts land on frames `19, 38, 57, 75, 95, 113, 132` (0.63 / 1.27 / 1.90 / 2.50 / 3.17 / 3.77 / 4.40 s).
  - **Room 1** (Pendant Light): `Empty` -> `Layer 1` -> `Layer 2` -> `Full`
  - **Room 2** (Chandelier): `Empty` -> `Layer 1` -> `Layer 2` -> `Full`
  - **Scene cut** (Room 1 to Room 2) is at frame `75` (2.50 s)
- **Audio**: ElevenLabs sound effects. A `whoosh` plays at the start (0.08 s) and at the Room 1 to Room 2 cut. A `pop` plays on every other cut. The two sounds are generated once through `fal_client.generate_elevenlabs_sound_effect` and saved under `assets/room_buildup_sfx/` (created on first run, not committed). If ElevenLabs does not answer within 60 s the pipeline uses a locally synthesized stand-in rather than stall the run.
- **No outro card, no captions, no on-screen text.**

---

## 2. Model Stack Phase Table (7 phases)

The log prints `[PHASE n/7]` markers that the Studio reads.

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape (2 fresh fixtures)** | Akeneo PIM API | Active ingestion + strict Shopify Active & Published verification + base-wide dedup | 1 Pendant Light (Room 1) + 1 Chandelier (Room 2) | Brand-new row, `Foreign Key ID`, `Furniture Item1..2`, `Item Name1..2`, `SKU1..2` -> Status: `In progress` |
| **Phase 2** | **Krea Furnished Interiors** | Krea AI | 9:16, 1K. Fixed prompt + moodboard ID per room | Moodboard ID + prompt per room | `Room 1 Interior`, `Room 2 Interior` |
| **Phase 3** | **Claude Blending Prompts** | Fal AI | `anthropic/claude-sonnet-5` (vision) | Room interior + scraped fixture | `Blending Prompt 1..2` |
| **Phase 4** | **Nano Banana Pro Fixture Blend** | Fal AI | `fal-ai/nano-banana-pro/edit`, 9:16, 1K | Interior + fixture + `Blending Prompt` | `Room 1 Full`, `Room 2 Full` |
| **Phase 5** | **Claude Removal Plans** | Fal AI | `anthropic/claude-sonnet-5` (vision) | `Room n Full` | `Removal Plan 1..2` (JSON: `inventory` + 3 cumulative `prompts`) |
| **Phase 6** | **Nano Banana Pro Chained Removals** | Fal AI | `fal-ai/nano-banana-pro/edit`. Chain: Full -> Layer 2 -> Layer 1 -> Empty | `Room n Full` + `Removal Plan n` | `Room n Layer 2`, `Room n Layer 1`, `Room n Empty` |
| **Phase 7** | **Hard-Cut Assembly + Sound** | Local FFmpeg + Fal ElevenLabs SFX | `imageio-ffmpeg`, frame-exact hard cuts | 8 stills + pop/whoosh sounds | `Raw Video`, `Final Video` -> Status: `Done` |

> **Measured scale guard:** every product-to-room blend goes through `content_automation/scale_guard.py`. A Claude Vision measurement sets the fixture to its real Akeneo size (or a conservative estimate when the row has none), and a second check retries once when the finished blend is more than ±15% off. Audit fields: `Scale Check`, `Scale Retry`, `Scale Audit`. `SCALE_GUARD_ENABLED=0` keeps the measurements in the prompt but skips both paid vision calls. Details: [`docs/SCALE_GUARD.md`](../SCALE_GUARD.md).

---

## 3. Phase 5 & 6 Details: Removal Plan and Quality Gates

### Phase 5: Claude removal plan
Claude looks at the furnished room and returns `{"inventory": [...], "prompts": [p1, p2, p3]}`. The three prompts are **cumulative**, and each is applied to the result of the previous one:
1. Remove the fixture and the small decor and accessories. Everything else stays.
2. Remove soft furnishings and secondary pieces (rugs, curtains, wall art, side tables...). Only the largest furniture stays.
3. Remove all remaining furniture so only bare walls, floor, windows and ceiling remain, restoring the surfaces behind every removed object.

If Claude's JSON is unusable, `DEFAULT_REMOVAL_PROMPTS` supplies exactly 3 generic prompts. Every prompt gets a "keep camera angle, framing, walls, windows, floor, ceiling and lighting identical" suffix.

### Phase 6: Step validation
Each removal gets up to `MAX_STEP_ATTEMPTS = 3` attempts. A result passes when it stays similar to its input (`MIN_STEP_SIMILARITY = 0.72`) and has less visual detail than the previous state (`MIN_DETAIL_DROP = 0.97`, edge density). This keeps the camera locked and ensures each layer really removes something. If no attempt passes, the best attempt that is still similar enough is kept. If none is usable, the step raises an `AutomationError`.

---

## 4. Foreign Key ID Convention & Examples

$$\text{Format: } \mathbf{RBU\text{-}REEL\text{-}SET\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `RBU` (Room Build-Up)
- **Content Format**: `REEL`
- **Fixture Code**: `SET` (two-room set)

Examples: `RBU-REEL-SET-1`, `RBU-REEL-SET-2`.

---

## 5. Supported Airtable Table & Env Vars Map

| Category Name | Fixture Code | Airtable Table ID | Primary Environment Variable |
| :--- | :--- | :--- | :--- |
| **Room Build-Up** | `SET` | `tblhq1rz9CVCD7yiR` | `AIRTABLE_TABLE_ID_ROOM_BUILD_UP_REEL` |

| Krea Setting | Room 1 | Room 2 |
| :--- | :--- | :--- |
| Moodboard ID | `KREA_MOODBOARD_ID_ROOM_BUILD_UP_REEL_ROOM1` (default `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3`) | `KREA_MOODBOARD_ID_ROOM_BUILD_UP_REEL_ROOM2` (default `b5ffdcbb-192e-4528-8d86-d1a4cf496887`) |
| Interior prompt | `PROMPT_ROOM_BUILD_UP_REEL_ROOM1` | `PROMPT_ROOM_BUILD_UP_REEL_ROOM2` |

Both prompts default to `Generate me a modern living room`. The Studio pencils edit one value and write it to **both** rooms (see [`../UI_CONTROL_CONFIG.md`](../UI_CONTROL_CONFIG.md)).

### Airtable Schema (`tblhq1rz9CVCD7yiR`)

| Field | Type |
| :--- | :--- |
| `Foreign Key ID`, `Date and Time Generated`, `Date and Time Scheduled` | singleLineText / dateTime |
| `Caption Generated` | multilineText |
| `Status` | singleSelect (`In progress` / `Done` / `Scheduled` / `Posted` / `Discard` / `For Manual`) |
| `Furniture Item1..2` | attachment (scraped fixture photo) |
| `Item Name1..2`, `SKU1..2` | multilineText / singleLineText |
| `Room 1..2 Interior` | attachment |
| `Blending Prompt 1..2`, `Removal Plan 1..2` | multilineText |
| `Room 1..2 Full`, `Layer 2`, `Layer 1`, `Empty` | attachment (the 4 states per room) |
| `Raw Video`, `Final Video` | attachment |

The pipeline creates any missing field on first run.

---

## 6. Web Studio (UI Control) & CLI

- **Flask route**: `UI Control/routes/room_build_up_reel.py` (`/api/room-build-up-reel/*`). It spawns `generate_room_build_up_reel_pipeline.py`.
- **Studio location**: Reel tab, subtab **"Room Build-Up"** (single card, id `room-build-up`).
- **CLI**:
  ```bash
  # Thin alias; flags: --phase all|scrape|generate, --max-rows N, --record-id, --style, --moodboard-id, --force
  python run_room_build_up_reel.py --max-rows 1
  ```
  `--record-id` re-renders one explicit row and skips scraping. Without it, every run scrapes a brand-new row (AGENTS.md §1 and §5).
