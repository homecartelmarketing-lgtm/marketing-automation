# 🎬 Before & After Reel Automation (9:16 Vertical Video Reel)

Kumpletong gabay at koleksyon ng mga script para sa **Before & After Reel** (1080 x 1920 px Instagram Reel / TikTok / Facebook Video).

---

## 📁 Direktoryo ng mga Scripts (Organized & Simplified Names)

Lahat ng scripts para sa Before & After Reel ay nakaayos na dito sa folder na ito:

| Script File | Ano ang ginagawa nito? (Simplified Description) | Kailan ito gagamitin? |
| :--- | :--- | :--- |
| **`1_Run_Full_Reel_Automation.py`** | **One-Click End-to-End Automation (5-Phase AI)**.<br>Kukuha ng produkto sa Akeneo $\rightarrow$ gagawa ng Before room sa Krea $\rightarrow$ susuriin ni Claude para sa blending prompt $\rightarrow$ ibe-blend ni Nano Banana ang produkto $\rightarrow$ kukuha ng 4 na camera angles $\rightarrow$ bubuuin ang 9:16 Video Reel na may ElevenLabs music, dynamic title, at outro $\rightarrow$ ise-sync sa Google Drive at Airtable. | Kapag nais mag-produce ng bagong kumpletong Before & After Video Reel. |
| **`2_Generate_Videos_Only.py`** | **Video Compiler Lang (Libre / Walang Image API Cost)**.<br>Kukunin ang mga na-generate nang photos sa Airtable at bubuuin agad ang Video Reel gamit ang ElevenLabs music. | Kapag may photos na sa Airtable at gusto mo lang i-compile ulit ang video. |
| **`3_Scrape_Akeneo_Floor_Lamps.py`** | Kukuha ng mga **Active** na Floor Lamps (`tbl2VoWOt7sSut4E2`) mula bago hanggang luma at may cross-table deduplication. | Para mag-scrape ng Floor Lamps. |
| **`3_Scrape_Akeneo_Pendant_Lights.py`** | Kukuha ng mga **Active** na Pendant Lights (`tbleUP86Kw36G8Hdw`) mula bago hanggang luma at may cross-table deduplication. | Para mag-scrape ng Pendant Lights. |
| **`3_Scrape_Akeneo_Chandeliers.py`** | Kukuha ng mga **Active** na Chandeliers (`tbloMhCOngGDWFS2y`) mula bago hanggang luma at may cross-table deduplication. | Para mag-scrape ng Chandeliers. |
| **`4_Interactive_Menu.py`** | **Madaling Terminal Menu**.<br>Magbubukas ng menu sa terminal kung saan pipili ka lang ng number [1-7] nang walang tinatype na mahahabang command. | Kapag nais mamili gamit ang interactive terminal menu. |

---

## 🚀 Paano Gamitin / How to Run

### 1. Gamitin ang Interactive Menu (Pinakamadali):
```bash
python "Before and After Reel/4_Interactive_Menu.py"
```

### 2. Patakbuhin ang Buong Automation (End-to-End):
```bash
# Floor Lamps (Default)
python "Before and After Reel/1_Run_Full_Reel_Automation.py"

# Pendant Lights
python "Before and After Reel/1_Run_Full_Reel_Automation.py" --target pendant_lights

# Chandeliers
python "Before and After Reel/1_Run_Full_Reel_Automation.py" --target chandeliers

# Magproseso ng higit sa 1 produkto (hal. 3 products):
python "Before and After Reel/1_Run_Full_Reel_Automation.py" --max-items 3
```

### 3. I-compile ang Video Reels Lamang (Mula sa Existing Airtable Photos):
```bash
# Floor Lamps
python "Before and After Reel/2_Generate_Videos_Only.py"

# Pendant Lights
python "Before and After Reel/2_Generate_Videos_Only.py" --target pendant_lights

# Chandeliers
python "Before and After Reel/2_Generate_Videos_Only.py" --target chandeliers
```

### 4. Mag-scrape ng Bagong Items (Active Only + Cross-Table Check):
```bash
# Floor Lamps:
python "Before and After Reel/3_Scrape_Akeneo_Floor_Lamps.py" --execute

# Pendant Lights:
python "Before and After Reel/3_Scrape_Akeneo_Pendant_Lights.py" --execute

# Chandeliers:
python "Before and After Reel/3_Scrape_Akeneo_Chandeliers.py" --execute
```

---

## 🎯 Mga Detalye ng Table IDs, Prompts & Settings (.env Driven)

Lahat ng Before & After Reel settings ay **100% kontrolado mula sa `.env`**. Walang kailangang baguhin sa Python code kapag may bagong table ID o gustong palitan ang moodboard at prompt.

### 📋 Built-in Categories sa `.env`:

| Kategorya | Airtable Table ID Env | Krea Moodboard Env | Default Interior Prompt | Scrape Source |
| :--- | :--- | :--- | :--- | :--- |
| **Floor Lamps** | `AIRTABLE_TABLE_ID_BEFORE_AFTER_FLOOR_LAMPS` | `KREA_MOODBOARD_ID_BEFORE_AFTER_FLOOR_LAMPS` | `"Generate me a bedroom that have beside a floor lamp"` | `floor_lamps` |
| **Pendant Lights** | `AIRTABLE_TABLE_ID_BEFORE_AFTER_PENDANT_LIGHTS` | `KREA_MOODBOARD_ID_BEFORE_AFTER_PENDANT_LIGHTS` | `"Generate me a modern dining room"` | `pendant_lights` |
| **Chandeliers** | `AIRTABLE_TABLE_ID_BEFORE_AFTER_CHANDELIER` | `KREA_MOODBOARD_ID_BEFORE_AFTER_CHANDELIER` | `"Generate me a photo a modern living room hanging chandelier from the ceiling"` | `chandeliers` |
| **Wall Lights** | `AIRTABLE_TABLE_ID_BEFORE_AFTER_WALL_LIGHTS` | `KREA_MOODBOARD_ID_BEFORE_AFTER_WALL_LIGHTS` | `"Generate me a modern living room with a wall light"` | `wall_lights` |
| **Table Lamps** | `AIRTABLE_TABLE_ID_BEFORE_AFTER_TABLE_LAMPS` | `KREA_MOODBOARD_ID_BEFORE_AFTER_TABLE_LAMPS` | `"Generate me a modern living room with a table lamp on a side table"` | `table_lamps` |

---

## ➕ Magdagdag ng Bagong Table ID (.env Lang — Walang Python Code Change)

Kada may bagong Table ID ka, magdagdag lang ng numbered block sa iyong `.env` file (N = 1, 2, 3, ...):

```dotenv
BEFORE_AFTER_CUSTOM_1_NAME=Table Lamps
BEFORE_AFTER_CUSTOM_1_TABLE_ID=tblXXXXXXXXXXXXXX
BEFORE_AFTER_CUSTOM_1_MOODBOARD_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
BEFORE_AFTER_CUSTOM_1_PROMPT=Generate me a modern living room with a table lamp
BEFORE_AFTER_CUSTOM_1_AKENEO_CATEGORY=table_lamps   # Aling produkto ang i-scrape sa Akeneo
```

| Setting | Required? | Paliwanag |
| :--- | :--- | :--- |
| `BEFORE_AFTER_CUSTOM_N_NAME` | Recommended | Pangalan na makikita sa menu at magiging `--target` slug (hal. `Table Lamps` $\rightarrow$ `table_lamps`) |
| `BEFORE_AFTER_CUSTOM_N_TABLE_ID` | **Yes** | Airtable Destination Table ID (`tbl...`) |
| `BEFORE_AFTER_CUSTOM_N_MOODBOARD_ID` | Optional | Krea Moodboard ID para sa kategoryang ito |
| `BEFORE_AFTER_CUSTOM_N_PROMPT` | Optional | Krea interior prompt para sa Before photo |
| `BEFORE_AFTER_CUSTOM_N_AKENEO_CATEGORY` | Optional | Akeneo category source (`floor_lamps`, `pendant_lights`, `chandeliers`, `table_lamps`, `wall_lights`, etc.) |
| `BEFORE_AFTER_CUSTOM_N_PLACEMENT_RULE` | Optional | Claude Sonnet Vision prompt instruction para sa blending |

Pagkatapos ilagay sa `.env`, patakbuhin gamit ang:
```bash
# Direktang slug:
python run_before_after_reel.py --target table_lamps

# O pumili mula sa interactive menu:
python "Before and After Reel/4_Interactive_Menu.py"
```

---

### 📂 Output Location:
- **Lokal:** `output/content/before_and_after_reel/<Petsa - Pangalan ng Item - SKU (RecordID)>/`
  - `01_FINAL_REEL_VIDEO/` $\rightarrow$ Ang final `.mp4` video na handa nang i-post.
  - `02_SOURCE_ASSETS/` $\rightarrow$ Lahat ng raw photos (Interior, Blended, 4 Angle shots, Outro, Thumbnail).
- **Google Drive Backup:** `G:/My Drive/Before & After Reels/` (awtomatikong sini-sync pagkatapos ma-compile).

