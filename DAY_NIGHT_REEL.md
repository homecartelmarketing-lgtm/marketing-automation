# Day & Night Reel Automation Pipeline

Ang **Day & Night Reel automation** ay isang 8-phase marketing workflow na awtomatikong lumilikha ng photorealistic **18-segundong 9:16 vertical video reel** para sa social media (Instagram Reels / TikTok / Facebook).

Ipinapakita nito ang lighting product (pendant lights, chandeliers, o floor lamps) sa loob ng isang modernong kwarto habang nagta-timelapse mula umaga (**Day**) hanggang gabi (**Night** kung saan bukas ang ilaw), kumpleto sa AI jazz background music at branded outro.

---

## 🏗️ Architecture & Model Stack

| Phase | Pangalan ng Phase | Provider / Tool | Model Code / Source | Output Airtable Field |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Akeneo Scrape** | Akeneo PIM API | Akeneo Client | `Furniture Item`, `SKU`, `Item Name` |
| **Phase 2** | **Krea AI Room Interior** | Krea AI | `krea-2-medium` (1K, 9:16) | `Interior` |
| **Phase 3** | **Claude Sonnet 5 Vision Analysis** | Fal AI (OpenRouter) | `anthropic/claude-sonnet-5` | `Prompt for Blending` |
| **Phase 4** | **Fal AI Nano Banana Pro Day Blending** | Fal AI | `fal-ai/nano-banana-pro/edit` (1K, 9:16) | Local `day_and_night_blended.jpg` |
| **Phase 5** | **Airtable Blended Image Sync** | Internal Validator | 9:16 validation | `Day and Night Blended` |
| **Phase 6** | **Fal AI Kling Timelapse Video** | Fal AI | `fal-ai/kling-video/v3/turbo/pro/image-to-video` (15s) | `REEL - Day & Night` |
| **Phase 7** | **Claude Sonnet 5 + Stable Audio 3 Jazz** | Fal AI | `anthropic/claude-sonnet-5` + `fal-ai/stable-audio-3/...` (18s) | `Music Generated` |
| **Phase 8** | **FFmpeg Video + Outro + Audio Merge** | Local FFmpeg | 15s video + 3s outro + 18s jazz audio | `Day and Night Reel with Music and Outro` |

---

## 🎯 Supported Categories & Airtable Tables

1. **Pendant Lights**
   * Table ID: `tblkTuM627s2f0FTN`
   * Krea Moodboard: `de5f4ff8-518c-4d6b-b606-ce1d5dac51f3`
   * Prompt: *"Generate me a modern dining room hanging chandelier"*

2. **Chandeliers**
   * Table ID: `tblODnfaNVP6SXn0A`
   * Krea Moodboard: `b5ffdcbb-192e-4528-8d86-d1a4cf496887`
   * Prompt: *"Generate me a modern living room with hanging chandelier from the ceiling"*

3. **Floor Lamps**
   * Table ID: `tbl2VoWOt7sSut4E2`
   * Krea Moodboard: `b1641228-beec-4823-8d01-1de3eec8410d`
   * Prompt: *"Generate me a bedroom that have beside a floor lamp"*

---

## 🚀 Quick Usage Commands

```bash
# 1. Interactive Runner (Pipili sa menu: 1=Pendant, 2=Chandelier, 3=Floor Lamp)
python run_day_night_reel.py

# 2. Direktang target kategorya
python run_day_night_reel.py --target pendant_lights
python run_day_night_reel.py --target chandeliers
python run_day_night_reel.py --target floor_lamps

# 3. Patakbuhin ang isang specific phase lang (e.g. Phase 3 para sa prompt analysis)
python run_day_night_reel.py --target pendant_lights --phase 3

# 4. Magpatuloy mula sa kung saan natigil (Automatic Resuming)
python run_day_night_reel.py --target pendant_lights --phase all
```

---

## 🔍 Resumability & Error Handling
- Kung may network error o maantala ang alinmang phase (hal. Phase 6 video generation o Phase 7 music generation), muling patakbuhin ang script gamit ang `--phase all` at awtomatiko nitong tutukuyin ang huling hindi pa tapos na phase para ipagpatuloy nang hindi inuulit ang mga naunang natapos na hakbang.
- Lahat ng request at raw provider responses ay naka-log sa `output/logs/day_night_reel_*.json` para sa madaling auditing at debugging.
