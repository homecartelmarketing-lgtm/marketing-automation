# 🛋️ Style This Story Automation (9:16 Vertical Story)

Kumpletong gabay at koleksyon ng mga script para sa **Style This Story** (1080 x 1920 px Instagram Story).

---

## 📁 Direktoryo ng mga Scripts (Simplified Names)

Lahat ng scripts para sa Style This Story ay nakaayos na dito sa folder na ito:

| Script File | Ano ang ginagawa nito? (Simplified Description) | Kailan ito gagamitin? |
| :--- | :--- | :--- |
| **`1_Run_Full_Story_Automation.py`** | Patatakbuhin ang buong automation mula simula hanggang upload sa Airtable (Scrape $\rightarrow$ Krea 4 interiors $\rightarrow$ Claude Prompts $\rightarrow$ Fal Blending $\rightarrow$ Story Cards $\rightarrow$ Complete). | Kapag nais mag-produce ng bagong kumpletong Style This Story. |
| **`2_Convert_Blended_Photos_To_Story_Cards.py`** | Kukuhain ang mga na-blend nang images sa `"Style This Blended"` (`style_this01..04`), ia-analyze ni Claude ang kulay at vibe, ise-save sa Airtable, at ilalapat ang layout ng Story Cards nang libre (walang Fal image API cost). | Kapag may blended images na sa Airtable at gusto na lang gawing Story Cards. |
| **`3_Scrape_Akeneo_Floor_Lamps.py`** | Kukuha ng mga **Active** na Floor Lamps (`tblvSAzXasTVI85r9`) mula **bago hanggang luma** at may cross-table deduplication. | Para sa Floor Lamps. |
| **`3_Scrape_Akeneo_Pendant_Lights.py`** | Kukuha ng mga **Active** na Pendant Lights (`tblWdz71nULR0TZx7`) mula **bago hanggang luma** at may cross-table deduplication. | Para sa Pendant Lights. |
| **`3_Scrape_Akeneo_Chandeliers.py`** | Kukuha ng mga **Active** na Chandeliers (`tblp6AMYb13NPqkuT`), **awtomatikong ini-skip ang Linear Chandeliers**, mula bago hanggang luma. | Para sa Chandeliers. |
| **`3_Scrape_Akeneo_Wall_Lights.py`** | Kukuha ng mga **Active** na Wall Lights (`tblXJrvSBkJNhRHLa`) mula **bago hanggang luma** at may cross-table deduplication. | Para sa Wall Lights. |
| **`4_Preview_Story_Cards_Locally.py`** | Mag-ge-generate ng preview images sa iyong computer (`output/style_this_preview/`) para makita ang hitsura ng Slide 1 at Slide 2 bago i-upload. | Kapag nais i-check ang posisyon ng text, logo, at kulay ng pill badge. |
| **`5_Interactive_Menu.py`** | Magbubukas ng madaling menu sa terminal kung saan mamimili ka muna ng Category/Table ID, tapos pipili ng aksyon (1 hanggang 6). | Kapag nais mamili ng category at action gamit ang interactive menu. |

---

## 🚀 Paano Gamitin / How to Run

### 1. Interactive Menu (Piliin ang Category / Table ID at Action)
```bash
python "Style This Story/5_Interactive_Menu.py"
```

### 2. Patakbuhin ang Buong Automation (End-to-End) para sa partikular na Category:
```bash
# Floor Lamps (Default)
python "Style This Story/1_Run_Full_Story_Automation.py"

# Pendant Lights
python "Style This Story/1_Run_Full_Story_Automation.py" --category pendant_lights

# Chandeliers (Auto-skips Linear Chandeliers)
python "Style This Story/1_Run_Full_Story_Automation.py" --category chandeliers

# Wall Lights
python "Style This Story/1_Run_Full_Story_Automation.py" --category wall_lights
```

### 3. I-convert ang Blended Photos na nasa Airtable
```bash
python "Style This Story/2_Convert_Blended_Photos_To_Story_Cards.py"
```

### 4. Mag-scrape ng Bagong Items (Active Only + Cross-Table Check)
```bash
# Floor Lamps:
python "Style This Story/3_Scrape_Akeneo_Floor_Lamps.py" --execute

# Pendant Lights:
python "Style This Story/3_Scrape_Akeneo_Pendant_Lights.py" --execute

# Chandeliers (Skips Linear):
python "Style This Story/3_Scrape_Akeneo_Chandeliers.py" --execute

# Wall Lights:
python "Style This Story/3_Scrape_Akeneo_Wall_Lights.py" --execute
```

---

## 🎯 Mga Detalye ng Table IDs, Prompts & Layout

### 📋 Mga Naka-set na Table IDs, Moodboard IDs & Prompts:
- **Floor Lamps**: Table `tblvSAzXasTVI85r9` | Moodboard: `b1641228-beec-4823-8d01-1de3eec8410d` | Prompt: `"Generate me a modern bedroom that have beside a floor lamp"`
- **Pendant Lights**: Table `tblWdz71nULR0TZx7` | Moodboard: `0844ad92-c34a-4dc8-9d70-d09498dc098c` | Prompt: `"Generate me a modern dining room"`
- **Chandeliers**: Table `tblp6AMYb13NPqkuT` | Moodboard: `fda7090c-787b-4116-94cd-3feef613eaaa` | Prompt: `"Generate me a modern bedroom"` *(Skips Linear Chandeliers)*
- **Wall Lights**: Table `tblXJrvSBkJNhRHLa` | Moodboard: *(Default)* | Prompt: `"Generate me a modern living room with a wall light"`

### 🎨 Layout Specs:
- **Slide 1 (`how_would_you_style_this.jpg`)**:
  - Logo sa Top-Right (`X=781.7`, `Y=108.0`, auto-stamped sa lahat ng photos)
  - *"How would you style this?"* at *"ft. [Item Name]"* (**Poppins-Light non-bold**, Solid White, **walang outline shadow**)
- **Slide 2, 3, 4 (`double_tap_blended01.jpg` .. `03.jpg`)**:
  - Logo sa Top-Right (`X=781.7`, `Y=108.0`, auto-stamped sa lahat ng photos)
  - Heart Emoji sa `X=250.8`, `Y=212.5`
  - *"Double tap if you choose:"* sa `X=346.6`, `Y=212.0` (**Poppins-Light non-bold**, Solid White, **walang outline shadow**)
  - Dynamic Pill Shape sa `Y=296.3` (direkta sa ilalim ng headline, horizontally centered) na may **Poppins-Light** text
- **Airtable Auto-Saved Fields**:
  - `style_this02.jpg` $\rightarrow$ **`Style This Text Generated1`** & **`Style This Auto Generated Color1`**
  - `style_this03.jpg` $\rightarrow$ **`Style This Text Generated2`** & **`Style This Auto Generated Color2`**
  - `style_this04.jpg` $\rightarrow$ **`Style This Text Generated3`** & **`Style This Auto Generated Color3`**
