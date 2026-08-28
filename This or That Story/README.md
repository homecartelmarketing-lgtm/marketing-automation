# ⚖️ This or That Story Automation (9:16 Vertical Story)

Kumpletong gabay at koleksyon ng mga script para sa **This or That Story** (1080 x 1920 px Instagram Story) gamit ang **Fal AI Nano Banana Pro**.

---

## 📁 Direktoryo ng mga Scripts (Organized & Simplified Names)

Lahat ng scripts para sa This or That Story ay nakaayos na dito sa folder na ito:

| Script File | Ano ang ginagawa nito? (Simplified Description) | Kailan ito gagamitin? |
| :--- | :--- | :--- |
| **`1_Run_Full_Story_Automation.py`** | **One-Click End-to-End Automation**.<br>Mag-i-scrape ng 2 produkto mula Akeneo $\rightarrow$ ilalapat ang layout watermark $\rightarrow$ ia-analyze at bubuuin ang 9:16 vertical Instagram Story via Fal AI Nano Banana Pro $\rightarrow$ ia-upload sa Airtable (`Story This or That (1)`). | Kapag nais mag-produce ng bagong kumpletong This or That Story mula simula hanggang dulo. |
| **`2_Generate_Pending_Stories.py`** | **Story Generator Lamang (Pending Rows sa Airtable)**.<br>Kukunin ang mga rows sa Airtable na may scraped products na pero wala pang generated Story Card, at bubuuin ang final image gamit ang Fal AI Nano Banana Pro. | Kapag may rows na sa Airtable at gusto mo lang i-generate ang mga Story Cards nang hindi nag-i-scrape ng bagong items. |
| **`3_Scrape_Akeneo_Wall_Lights.py`** | Kukuha ng mga active na Wall Lights (`tblZw6jvSa27oZDiN`) mula Akeneo (2 products per row + layout watermark). | Para mag-scrape ng Wall Lights pairs. |
| **`3_Scrape_Akeneo_Table_Lamps.py`** | Kukuha ng mga active na Table Lamps (`tblm1Ty2QkAlUcHJt`) mula Akeneo (2 products per row + layout watermark). | Para mag-scrape ng Table Lamps pairs. |
| **`3_Scrape_Akeneo_Cluster_Chandeliers.py`** | Kukuha ng mga active na Cluster Chandeliers (`tblYAhjKckXtjUayx`) mula Akeneo (2 products per row + layout watermark). | Para mag-scrape ng Cluster Chandeliers pairs. |
| **`3_Scrape_Akeneo_Floor_Lamps.py`** | Kukuha ng mga active na Floor Lamps (`tblaoqj8VPVHFmVQn`) mula Akeneo (2 products per row + layout watermark). | Para mag-scrape ng Floor Lamps pairs. |
| **`3_Scrape_Akeneo_Chandeliers.py`** | Kukuha ng mga active na Chandeliers (`tblo42IkuhYLIQBzk`) mula Akeneo (2 products per row + layout watermark). | Para mag-scrape ng Chandeliers pairs. |
| **`3_Scrape_Akeneo_Pendant_Lights.py`** | Kukuha ng mga active na Pendant Lights (`tblS1VHp41RDfxztD`) mula Akeneo (2 products per row + layout watermark). | Para mag-scrape ng Pendant Lights pairs. |
| **`4_Interactive_Menu.py`** | **Madaling Terminal Menu**.<br>Magbubukas ng console menu sa terminal kung saan pipili ka lang ng numero [0-4] nang walang kinakailangang mahahabang command. | Kapag nais mamili ng aksyon gamit ang interactive menu. |

---

## 🚀 Paano Gamitin / How to Run

### 1. Gamitin ang Interactive Menu (Pinakamadali):
```bash
python "This or That Story/4_Interactive_Menu.py"
```

### 2. Patakbuhin ang Buong Automation (End-to-End):
```bash
# Wall Lights (Default):
python "This or That Story/1_Run_Full_Story_Automation.py"

# Iba pang mga Lighting Categories:
python "This or That Story/1_Run_Full_Story_Automation.py" --target table_lamps
python "This or That Story/1_Run_Full_Story_Automation.py" --target cluster_chandelier
python "This or That Story/1_Run_Full_Story_Automation.py" --target floor_lamp
python "This or That Story/1_Run_Full_Story_Automation.py" --target chandeliers
python "This or That Story/1_Run_Full_Story_Automation.py" --target pendant_lights

# Lahat ng 6 Categories nang sabay-sabay:
python "This or That Story/1_Run_Full_Story_Automation.py" --target all

# Magproseso ng higit sa 1 pair (hal. 3 rows):
python "This or That Story/1_Run_Full_Story_Automation.py" --target wall_lights --count 3

# Partikular na Airtable Record ID:
python "This or That Story/1_Run_Full_Story_Automation.py" --target wall_lights --record-id recXXXXXXXXXXXXXX
```

### 3. I-generate ang mga Pending Records Lamang (Walang Scraping):
```bash
# Wall Lights (Default):
python "This or That Story/2_Generate_Pending_Stories.py"

# Para sa partikular na category:
python "This or That Story/2_Generate_Pending_Stories.py" --target pendant_lights --count 5
```

### 4. Mag-scrape ng Bagong Items (2 Products per Row + Layout Attachment):
```bash
# Wall Lights:
python "This or That Story/3_Scrape_Akeneo_Wall_Lights.py" --rows 1

# Table Lamps:
python "This or That Story/3_Scrape_Akeneo_Table_Lamps.py" --rows 1

# Cluster Chandeliers:
python "This or That Story/3_Scrape_Akeneo_Cluster_Chandeliers.py" --rows 1

# Floor Lamps:
python "This or That Story/3_Scrape_Akeneo_Floor_Lamps.py" --rows 1

# Chandeliers:
python "This or That Story/3_Scrape_Akeneo_Chandeliers.py" --rows 1

# Pendant Lights:
python "This or That Story/3_Scrape_Akeneo_Pendant_Lights.py" --rows 1
```

---

## 🎯 Mga Detalye ng Table IDs, Prompts & Settings

### 📋 Mga Naka-set na Table IDs:
- **Wall Lights**: Table `tblZw6jvSa27oZDiN` (`AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT`)
- **Table Lamps**: Table `tblm1Ty2QkAlUcHJt` (`AIRTABLE_TABLE_ID_TABLE_LAMPS_THIS_OR_THAT`)
- **Cluster Chandelier**: Table `tblYAhjKckXtjUayx` (`AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_THIS_OR_THAT`)
- **Floor Lamp**: Table `tblaoqj8VPVHFmVQn` (`AIRTABLE_TABLE_ID_FLOOR_LAMP_THIS_OR_THAT`)
- **Chandeliers**: Table `tblo42IkuhYLIQBzk` (`AIRTABLE_TABLE_ID_CHANDELIERS_THIS_OR_THAT`)
- **Pendant Lights**: Table `tblS1VHp41RDfxztD` (`AIRTABLE_TABLE_ID_PENDANT_LIGHTS_THIS_OR_THAT`)

### 🎨 Model & Prompt Specs:
- **AI Model**: Fal AI Nano Banana Pro (`fal-ai/nano-banana-pro/edit`)
- **Aspect Ratio**: `9:16` (1080 x 1920 px vertical story)
- **Watermark Layout**: `JSON Prompts/This or That/thisorthatlayout.jpg`
- **JSON Prompt Template**: `JSON Prompts/This or That/this_or_that_json_prompt.json`
- **Airtable Output Field**: `Story This or That (1)` o `This or That Converted`
