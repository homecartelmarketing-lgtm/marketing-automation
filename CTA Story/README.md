# 🎯 CTA Story Automation

> **Master Specification**: For complete architecture, model stack, Foreign Key conventions, and Canva coordinates, see [`../docs/stories/CTA_STORY.md`](../docs/stories/CTA_STORY.md) and [`../AGENTS.md`](../AGENTS.md).

Generates branded 9:16 vertical Instagram Stories (1080 x 1920 px) with AI-generated photorealistic interiors, Nano Banana Pro blending, Claude Vision headline analysis, and local Python Pillow CTA text watermark stamping.

---

## ⚡ Quick Launch: Interactive Menu

The easiest and recommended way to run the CTA Story Automation is via the interactive menu:

```bash
# Option 1: Direct script launcher
python "CTA Story/4_Interactive_Menu.py"

# Option 2: Main pipeline launcher
python generate_cta_story_pipeline.py

# Option 3: Multi-table round-robin menu
python run_cta_round_robin.py --menu
```

---

## 📊 Supported Tables & Categories

| # | Table Name | Category Code | Table ID (`.env`) | Moodboard ID (`.env`) | Interior Prompt (`.env`) |
|---|---|---|---|---|---|
| **1** | CTA Story Chandelier | `chandelier_cta_story` | `tblYHdVq14FjMWg5o`<br>`AIRTABLE_TABLE_ID_CHANDELIER_CTA` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24`<br>`KREA_MOODBOARD_ID_CHANDELIER_CTA` | `Generate me a modern living room`<br>`CTA_PROMPT_CHANDELIER` |
| **2** | CTA Story Pendant Light | `pendant_lights_cta_story` | `tblfl7fqFZa2vUieB`<br>`AIRTABLE_TABLE_ID_PENDANT_LIGHTS_CTA` | `0844ad92-c34a-4dc8-9d70-d09498dc098c`<br>`KREA_MOODBOARD_ID_PENDANT_LIGHTS_CTA` | `Generate me a modern dining room`<br>`CTA_PROMPT_PENDANT_LIGHTS` |
| **3** | CTA Story Cluster Chandelier | `cluster_chandelier_cta_story` | `tblSpGJLO3faYfIDY`<br>`AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_CTA` | `b5ffdcbb-192e-4528-8d86-d1a4cf496887`<br>`KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_CTA` | `Modern high-ceiling room interior...`<br>`CTA_PROMPT_CLUSTER_CHANDELIER` |
| **4** | CTA Story Table Lamp | `table_lamps_cta_story` | `tblKJeCCp4zQ6g7Em`<br>`AIRTABLE_TABLE_ID_TABLE_LAMPS_CTA` | `257569e1-7be8-4412-a90f-acbc347e4646`<br>`KREA_MOODBOARD_ID_TABLE_LAMPS_CTA` | `Generate me a modern bedroom...`<br>`CTA_PROMPT_TABLE_LAMPS` |
| **5** | CTA Story Floor Lamp | `floor_lamp_cta_story` | `tblPKSYyjgbgMypE2`<br>`AIRTABLE_TABLE_ID_FLOOR_LAMP_CTA` | `c4c15a18-a92d-4465-924f-c85cfe1958bc`<br>`KREA_MOODBOARD_ID_FLOOR_LAMP_CTA` | `Modern living room interior, lounge chair...`<br>`CTA_PROMPT_FLOOR_LAMPS` |

---

## 🛠️ Menu Options

When the interactive menu starts, you can:
1. **Choose your Target Table** (`[1]` to `[5]`, or custom Table ID, or multi-table round-robin).
2. **Choose the Phase to Execute**:
   - `[1]` Scrape Akeneo Products to Airtable (1 item)
   - `[2]` Krea AI Interior Generation (9:16) -> 'CTA Interior'
   - `[3]` Claude Sonnet 5 Prompt Generation -> 'Blending Prompt'
   - `[4]` Fal AI Nano Banana Pro Blending (9:16) -> 'CTA Blended Image'
   - `[5]` Claude Sonnet 5 Headline Generation -> 'Word Generated'
   - `[6]` Python Local CTA Layout & Logo Stamping (9:16) -> 'CTA Converted Image'
   - `[7]` Run Full End-to-End Pipeline (Row-by-Row: Scrape -> Steps 2 to 6)
   - `[8]` Multi-Table Round-Robin (All CTA Tables)
   - `[9]` Switch Target Table ID
   - `[10]` Exit
