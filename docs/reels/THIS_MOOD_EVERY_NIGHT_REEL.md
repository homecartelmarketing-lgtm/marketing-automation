# This Mood Every Night Reel Automation Pipeline

The **This Mood Every Night Reel Automation Pipeline** generates an ultra-aesthetic, high-engagement **9:16 vertical video reel (1080 x 1920 px)** capturing the warm, moody, cinematic nighttime atmosphere of a luxury home illuminated by HomeCartel lighting fixtures.

Derived directly from the reference video [`assets/this_mood_every_night_reference.mp4`](file:///c:/Users/User/Desktop/marketing-automation/assets/this_mood_every_night_reference.mp4) (provided as `new content.mp4`), this format leverages a signature rhythmic pacing of **7 rapid, hypnotic cuts (~1.35 seconds per shot)** synchronized to a cozy lo-fi ambient soundtrack, with a persistent centered lowercase title: **`this mood every night`**.

---

## 1. Output Specs & Canvas Dimensions

- **Canvas Dimensions**: `1080 x 1920 px` (Aspect Ratio `9:16`)
- **Video Format**: H.264 MP4, 30 FPS, High Profile
- **Total Duration**: `~9.5 seconds`
- **Reel Structure & Rhythm**:
  - **7 Continuous Ambient Night Shots** (~1.35s each, matching reference cut timestamps: `0.00s`, `1.37s`, `2.70s`, `4.07s`, `5.40s`, `6.73s`, `8.10s` to `9.54s`).
  - **Cut Style**: Direct beat-matched snap cut (or subtle 0.15s cross-dissolve).
  - **Signature Center Text Overlay**:
    - **Copy**: `this mood every night` (strictly lowercase).
    - **Placement**: Centered (`x = center, y = center`), subtle warm ambient shadow / drop shadow for maximum legibility against light and dark backgrounds.
    - **Typography**: Poppins-Light / Regular (matching HomeCartel brand standards) or optional luxury editorial serif font (Cormorant / Playfair).
  - **Color & Lighting Palette**:
    - Nighttime ambient contrast (dark exterior night windows, moody shadows, 2700K warm incandescent glows, fireplace flicker, architectural cove & step lighting).
- **Audio Profile**: Stereo AAC @ 192 kbps warm lo-fi night piano / ambient instrumental (~72 BPM, softly rhythmic with warm vinyl texture).
- **Outro**: Seamless infinite loop (`--outro none` default) or optional brief HomeCartel outro.

---

## 2. Shot-by-Shot Scene Breakdown (7 Slots)

| Slot | Room / Scene | Primary Lighting Fixture Category | Camera Motion / Framing | Atmospheric Details |
| :---: | :--- | :--- | :--- | :--- |
| **Slot 1** | **Living Room Vista** | Ambient Cove & Fireplace | Slow push-in looking through black industrial steel glass grid partition | Warm flickering hearth, illuminated shelving niche, lounge chairs |
| **Slot 2** | **Kitchen Island** | Fluted Pleated Pendant (`pendant_lights`) | Low slow tilt-up toward statement fabric pendant | Luxury marble waterfall counter, warm 2700K pendant glow |
| **Slot 3** | **Fireplace Hearth & TV Wall** | Recessed Niche Lighting | Subtle horizontal pan across mantel | Clean modern plaster fireplace, warm LED cove shelves, glowing candles |
| **Slot 4** | **Kitchen Island Detail** | Island Pendant (`pendant_lights`) | Macro slow push on brass gooseneck faucet & marble counter | Warm reflections, candle glow, pendant soft diffusion in background |
| **Slot 5** | **Dining Room vista** | Modern Dining Chandelier (`chandeliers`) + Floor Lamp (`floor_lamps`) | Medium shot through glass divider | Branch/candelabra chandelier over wood dining table, tall pleated floor lamp in corner |
| **Slot 6** | **Kitchen & Dining Open Vista** | Kitchen Pendant Light (`pendant_lights`) | Wide shot from counter across open-plan room | Counter flowers, dramatic night windows, layered warm light points |
| **Slot 7** | **Interior Staircase** | Recessed Step Lights (`wall_sconces` / footlights) | Low angle tilt looking up staircase | Minimalist dark steps with square warm footlights cascading light down each tread |

---

## 3. Model Stack Phase Table

| Phase | Phase Name | Provider / Engine | Model / Settings | Input Fields / Triggers | Output Fields / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo 7-Fixture Scrape** | Akeneo PIM API | Active ingestion (`enabled=true`) + Shopify Published check + base-wide dedup | Akeneo catalog (7 matching night fixture categories) | `Furniture Item1..7`, `Item Name1..7`, `SKU1..7` -> Status: `Standby` |
| **Phase 2** | **Krea Nighttime Room Interiors** | Krea AI | `krea-2-medium` (9:16, 1K)<br>7 specialized night/moody interior prompts + warm lighting moodboard | `Interior Prompt1..7` (Studio override > built-in night prompt) | `Interior1..7` (+ `Interior Prompt`, `Moodboard ID`) -> Status: `Interior Generated` |
| **Phase 3** | **Claude Sonnet 5 Vision Analysis** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` (vision mode) | `Interior1..7` | `Interior Analysis1..7` (fixture night lighting direction, glow warmth) -> Status: `Interior Analyzed` |
| **Phase 4** | **Claude Blend Prompts** | Fal AI / OpenRouter | `anthropic/claude-sonnet-5` | `InteriorN` + `Furniture ItemN` + `Interior AnalysisN` | `Generated Prompt1..7` -> Status: `Prompt Generated` |
| **Phase 5** | **Nano Banana Pro Blending** | Fal AI + local YOLO-World | `fal-ai/nano-banana-pro/edit`<br>Aspect Ratio: `9:16`, Resolution: `1K` | `Interior` + `Product` + `Prompt` | `Blended Image1..7` (photorealistic night blend with warm illuminated bulbs) -> Status: `Blended Image Generated` |
| **Phase 6** | **Motion Generation (Kling or Local Ken Burns)** | Fal AI or Local FFmpeg | `fal-ai/kling-video/v3/turbo/pro/image-to-video` (3s clip trimmed to 1.35s) OR local 60fps Ken Burns zoom/drift | `Blended Image1..7` + subtle night camera drift prompts | `Motion Video1..7` -> Status: `Motion Generated` |
| **Phase 7** | **Soundtrack Generation / Mux** | Fal AI ElevenLabs / Local Audio | `fal-ai/elevenlabs/music` or reference audio track ([`assets/this_mood_every_night_reference.mp4`](file:///c:/Users/User/Desktop/marketing-automation/assets/this_mood_every_night_reference.mp4)) | Audio track | `Music Generated` -> Status: `Music Generated` |
| **Phase 8** | **FFmpeg Reel Assembly** | Local FFmpeg | 1080x1920 H.264 30fps: 7 snap cuts @ 1.35s, center `"this mood every night"` overlay, audio mux | 7 motion clips + audio | `Final Video` -> Status: `Done` + PHT timestamp |

---

## 4. Foreign Key ID Convention & Database Wiring

$$\text{Format: } \mathbf{TMEN\text{-}REEL\text{-}SET\text{-}\langle ROW\_ID\rangle}$$

- **Idea Abbreviation**: `TMEN` (This Mood Every Night)
- **Content Format**: `REEL`
- **Set Identifier**: `SET` (7-room night sequence)
- **Table ID**: Provisioned in Airtable Base `appDM0jUDsaiThtR3`
- **Primary Env Key**: `AIRTABLE_TABLE_ID_THIS_MOOD_EVERY_NIGHT_REEL`

### Examples:
- `TMEN-REEL-SET-1`
- `TMEN-REEL-SET-5`

---

## 5. Local Typography & Assembly Specs (FFmpeg Engine)

- **Zero-Cost Layout Assembly**: All video cuts, text rendering, and audio muxing are executed 100% locally via FFmpeg.
- **Center Hook Overlay**:
  - Filter: `drawtext=fontfile='content_automation/fonts/Poppins-Light.ttf':text='this mood every night':fontcolor=white@0.92:fontsize=46:x=(w-text_w)/2:y=(h-text_h)/2:shadowcolor=black@0.4:shadowx=2:shadowy=2`
- **Shot Duration Matrix**:
  - `Shot 1`: `0.00s` to `1.35s`
  - `Shot 2`: `1.35s` to `2.70s`
  - `Shot 3`: `2.70s` to `4.05s`
  - `Shot 4`: `4.05s` to `5.40s`
  - `Shot 5`: `5.40s` to `6.75s`
  - `Shot 6`: `6.75s` to `8.10s`
  - `Shot 7`: `8.10s` to `9.50s`

---

## 6. Web Studio (UI Control) Registration Plan

1. **Flask Route**: `UI Control/routes/this_mood_every_night_reel.py` (`/api/this-mood-every-night-reel/*`)
2. **React Pipeline Config**: Subtab under the **Reels** tab in Web Studio.
3. **Queue Integration**: Full integration with `UI Control/routes/queue_manager.py` for FIFO queuing and progress monitoring.
