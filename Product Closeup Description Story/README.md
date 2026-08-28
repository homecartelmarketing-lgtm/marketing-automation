# 💡 Product Closeup w/ Description Story Automation (9:16 Vertical Story)

Kumpletong gabay at koleksyon ng mga script para sa **Product Closeup w/ Description Story** (1080 x 1920 px Instagram Story) gamit ang **Fal AI Nano Banana Pro**.

---

## 📁 Direktoryo ng mga Scripts (Organized & Simplified Names)

Lahat ng scripts para sa Product Closeup Description Story ay nakaayos na dito sa folder na ito:

| Script File | Ano ang ginagawa nito? (Simplified Description) | Kailan ito gagamitin? |
| :--- | :--- | :--- |
| **`1_Run_Full_Story_Automation.py`** | **One-Click End-to-End Automation**.<br>Mag-i-scrape ng 1 produkto mula Akeneo $\rightarrow$ ilalapat ang layout watermark (`layout_product_v2.jpg`) $\rightarrow$ ia-analyze at bubuuin ang 9:16 vertical Instagram Story via Fal AI Nano Banana Pro $\rightarrow$ ia-upload sa Airtable (`Product Closeup Description Converted`). | Kapag nais mag-produce ng bagong kumpletong Product Closeup Description Story mula simula hanggang dulo. |
| **`2_Generate_Pending_Stories.py`** | **Story Generator Lamang (Pending Rows sa Airtable)**.<br>Kukunin ang mga rows sa Airtable na may scraped product at layout na pero wala pang generated Story Card, at bubuuin ang final image gamit ang Fal AI Nano Banana Pro. | Kapag may rows na sa Airtable at gusto mo lang i-generate ang mga Story Cards nang hindi nag-i-scrape ng bagong items. |
| **`3_Scrape_Akeneo_Chandeliers.py`** | Kukuha ng mga active na Chandeliers (`tblDcT6jovdAbKnfw`) mula Akeneo (1 product per row + layout watermark). | Para mag-scrape ng Chandeliers. |
| **`3_Scrape_Akeneo_Pendant_Lights.py`** | Kukuha ng mga active na Pendant Lights (`tblDD2w4v0Idb4jAZ`) mula Akeneo (1 product per row + layout watermark). | Para mag-scrape ng Pendant Lights. |
| **`3_Scrape_Akeneo_Floor_Lamps.py`** | Kukuha ng mga active na Floor Lamps (`tblPvHyKGByWJCMtY`) mula Akeneo (1 product per row + layout watermark). | Para mag-scrape ng Floor Lamps. |
| **`3_Scrape_Akeneo_Cluster_Chandeliers.py`** | Kukuha ng mga active na Cluster Chandeliers (`tblnIOQVywHcTgAtv`) mula Akeneo (1 product per row + layout watermark). | Para mag-scrape ng Cluster Chandeliers. |
| **`3_Scrape_Akeneo_Table_Lamps.py`** | Kukuha ng mga active na Table Lamps (`tbl5S9JEHSrjrLwxA`) mula Akeneo (1 product per row + layout watermark). | Para mag-scrape ng Table Lamps. |
| **`3_Scrape_Akeneo_Wall_Lights.py`** | Kukuha ng mga active na Wall Lights (`tblYqudlgjYMNRROM`) mula Akeneo (1 product per row + layout watermark). | Para mag-scrape ng Wall Lights. |
| **`4_Interactive_Menu.py`** | **Madaling Terminal Menu**.<br>Magbubukas ng console menu sa terminal kung saan pipili ka lang ng numero [0-4] nang walang kinakailangang mahahabang command. | Kapag nais mamili ng aksyon gamit ang interactive menu. |

---

## 🚀 Paano Gamitin / How to Run

### 1. Gamitin ang Interactive Menu (Pinakamadali):
```bash
python "Product Closeup Description Story/4_Interactive_Menu.py"
```

### 2. Patakbuhin ang Buong Automation (End-to-End):
```bash
# Chandeliers (Default):
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py"

# Iba pang mga Lighting Categories:
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target pendant_lights
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target floor_lamps
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target cluster_chandeliers
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target table_lamps
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target wall_lights

# Lahat ng 6 Categories nang sabay-sabay:
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target all

# Magproseso ng higit sa 1 item (hal. 3 products):
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target chandeliers --count 3

# Partikular na Airtable Record ID:
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target chandeliers --record-id recXXXXXXXXXXXXXX
```

### 3. I-generate ang mga Pending Records Lamang (Walang Scraping):
```bash
# Chandeliers (Default):
python "Product Closeup Description Story/2_Generate_Pending_Stories.py"

# Para sa partikular na category:
python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target pendant_lights --count 5
```

### 4. Mag-scrape ng Bagong Items (1 Product per Row + Layout Attachment):
```bash
# Chandeliers:
python "Product Closeup Description Story/3_Scrape_Akeneo_Chandeliers.py" --count 1

# Pendant Lights:
python "Product Closeup Description Story/3_Scrape_Akeneo_Pendant_Lights.py" --count 1

# Floor Lamps:
python "Product Closeup Description Story/3_Scrape_Akeneo_Floor_Lamps.py" --count 1

# Cluster Chandeliers:
python "Product Closeup Description Story/3_Scrape_Akeneo_Cluster_Chandeliers.py" --count 1

# Table Lamps:
python "Product Closeup Description Story/3_Scrape_Akeneo_Table_Lamps.py" --count 1

# Wall Lights:
python "Product Closeup Description Story/3_Scrape_Akeneo_Wall_Lights.py" --count 1
```

---

## 🎯 Mga Detalye ng Table IDs, Prompts & Settings

### 📋 Mga Naka-set na Table IDs:
- **Chandeliers**: Table `tblDcT6jovdAbKnfw` (`AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION`)
- **Pendant Lights**: Table `tblDD2w4v0Idb4jAZ` (`AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION`)
- **Floor Lamps**: Table `tblPvHyKGByWJCMtY` (`AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION`)
- **Cluster Chandelier**: Table `tblnIOQVywHcTgAtv` (`AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION`)
- **Table Lamps**: Table `tbl5S9JEHSrjrLwxA` (`AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION`)
- **Wall Lights**: Table `tblYqudlgjYMNRROM` (`AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION`)

### 🎨 Model & Prompt Specs:
- **AI Model**: Fal AI Nano Banana Pro (`fal-ai/nano-banana-pro/edit`)
- **Aspect Ratio**: `9:16` (1080 x 1920 px vertical story)
- **Watermark Layout**: `JSON Prompts/Product Closeup V2/layout_product_v2.jpg`
- **JSON Prompt Template**: `JSON Prompts/Product Closeup V2/product_desc.json`
- **Airtable Output Field**: `Product Closeup Description Converted`
- **Status Progression**: `Standby` $\rightarrow$ `Processing` $\rightarrow$ `Complete`
- **Execution Log**: `output/logs/fal_nano_product_description_logs.json`
