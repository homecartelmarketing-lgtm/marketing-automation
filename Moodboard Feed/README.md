# 🖼️ Moodboard Feed Automation (4:5 Instagram Carousel)

> **Master Specification**: For complete architecture, model stack, Foreign Key conventions, and layout specs, see [`../docs/feeds/MOODBOARD_1_FEED.md`](../docs/feeds/MOODBOARD_1_FEED.md), [`../docs/feeds/MOODBOARD_2_FEED.md`](../docs/feeds/MOODBOARD_2_FEED.md), and [`../AGENTS.md`](../AGENTS.md).

Thin wrapper scripts for the **Moodboard #1** and **Moodboard #2** Feed pipelines (`1080 x 1350 px` Instagram Feed / Carousel). Both scripts here just call the equivalent root-level `run_full_moodboard_*_feed.py` entrypoint — they exist so the two Moodboard feed pipelines can be launched from one dedicated folder alongside the other per-pipeline folders in this repo.

---

## 📁 Scripts in This Folder

| Script File | Ano ang ginagawa nito? | Kailan ito gagamitin? |
| :--- | :--- | :--- |
| **`1_Run_Full_Moodboard_Feed.py`** | Tumatawag sa `run_full_moodboard_1_feed.main()`: mag-i-scrape ng bagong produkto mula Akeneo (may cross-table dedup) $\rightarrow$ bubuuin ang 4-slide Moodboard #1 carousel (room blend, watermark, 3-swatch moodboard, macro closeup) end-to-end. | Kapag nais mag-produce ng bagong kumpletong Moodboard #1 Feed mula simula hanggang dulo. |
| **`2_Run_Full_Moodboard_2_Feed.py`** | Tumatawag sa `run_full_moodboard_2_feed.main()`: mag-i-scrape ng bagong produkto $\rightarrow$ bubuuin ang 2-slide Moodboard #2 carousel (room blend + editorial flat-lay moodboard) end-to-end. | Kapag nais mag-produce ng bagong kumpletong Moodboard #2 Feed mula simula hanggang dulo. |

---

## 🎯 Quick Execution Commands

```bash
# Moodboard #1 Feed (default: modern chandeliers, 1 item)
python "Moodboard Feed/1_Run_Full_Moodboard_Feed.py"

# Moodboard #1 Feed, specific category & count
python "Moodboard Feed/1_Run_Full_Moodboard_Feed.py" --category pendant_lights --max-items 3

# Moodboard #2 Feed, interactive category menu (no args, run in a terminal)
python "Moodboard Feed/2_Run_Full_Moodboard_2_Feed.py"

# Moodboard #2 Feed, specific category & count
python "Moodboard Feed/2_Run_Full_Moodboard_2_Feed.py" --category wall_lights --max-items 3

# Process existing Standby records only, without scraping new ones
python "Moodboard Feed/2_Run_Full_Moodboard_2_Feed.py" --skip-scrape
```

Both scripts accept the same flags as their root-level counterparts — see [`run_full_moodboard_1_feed.py`](../run_full_moodboard_1_feed.py) and [`run_full_moodboard_2_feed.py`](../run_full_moodboard_2_feed.py) (`--category`, `--style`, `--max-items`/`--count`, `--table-id`, `--skip-scrape`, `--no-backfill`, `--no-shopify-check`, `--moodboard-id`, `--prompt`).

---

## 🎯 Table IDs & Categories

See [`../docs/feeds/MOODBOARD_1_FEED.md`](../docs/feeds/MOODBOARD_1_FEED.md) (Chandelier, Pendant, Floor Lamp) and [`../docs/feeds/MOODBOARD_2_FEED.md`](../docs/feeds/MOODBOARD_2_FEED.md) (Chandelier, Pendant, Floor Lamp, Wall Light) for the full category → Airtable table ID → Foreign Key prefix map.

### 🎨 Model & Prompt Specs:
- **Moodboard #1**: Krea AI room interior $\rightarrow$ Claude Sonnet 5 prompt $\rightarrow$ Fal AI Nano Banana Pro (blend, 3-swatch conversion, macro closeup) $\rightarrow$ local Pillow logo watermark. Foreign Key prefix `MB1-FEEDS`.
- **Moodboard #2**: Krea AI room interior $\rightarrow$ Claude Sonnet 5 prompt $\rightarrow$ Fal AI Nano Banana Pro (blend + editorial flat-lay conversion). Foreign Key prefix `MB2-FEEDS`.
- **Status Progression**: `Standby`/`Pending` $\rightarrow$ `Drafting` $\rightarrow$ `Complete`/`Done`.
