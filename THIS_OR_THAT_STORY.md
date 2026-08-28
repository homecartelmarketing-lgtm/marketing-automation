# This or That Story Automation (9:16 Ratio)

End-to-end automated generation pipeline for **This or That Story** (1080 x 1920 px vertical Instagram Story) using **Fal AI Nano Banana Pro**.

---

## 🚀 Pipeline Workflow

| Phase | Action | Engine | Target Airtable Field | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Auto-Scrape Akeneo 2 Products | `AkeneoClient` + `ScrapeRunner` | `Furniture Item`, `Furniture Item2`, `Item Name`, `Item Name2`, `SKU`, `SKU2`, `This or That Layout` | `Standby` |
| **Phase 2** | 9:16 Story Generation & Blending | `FalClient` (Nano Banana Pro) | `Story This or That (1)` / `This or That Converted` | `Complete` |

---

## 📋 This or That Category Table IDs

| Category | Airtable Table ID | Environment Key | Scraping Rules |
| :--- | :--- | :--- | :--- |
| **Wall Lights** | `tblZw6jvSa27oZDiN` | `AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT` | 2 Products per Row + `thisorthatlayout.jpg` |
| **Table Lamps** | `tblm1Ty2QkAlUcHJt` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_THIS_OR_THAT` | 2 Products per Row + `thisorthatlayout.jpg` |
| **Cluster Chandelier** | `tblYAhjKckXtjUayx` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_THIS_OR_THAT` | 2 Products per Row + `thisorthatlayout.jpg` |
| **Floor Lamps** | `tblaoqj8VPVHFmVQn` | `AIRTABLE_TABLE_ID_FLOOR_LAMP_THIS_OR_THAT` | 2 Products per Row + `thisorthatlayout.jpg` |
| **Chandeliers** | `tblo42IkuhYLIQBzk` | `AIRTABLE_TABLE_ID_CHANDELIERS_THIS_OR_THAT` | 2 Products per Row + `thisorthatlayout.jpg` |
| **Pendant Lights** | `tblS1VHp41RDfxztD` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_THIS_OR_THAT` | 2 Products per Row + `thisorthatlayout.jpg` |

---

## 📁 Dedicated Scripts Folder (`This or That Story/`)

All scripts for This or That Story are cleanly organized inside `This or That Story/`:

- **`1_Run_Full_Story_Automation.py`**: Full end-to-end automation runner (Akeneo scrape $\rightarrow$ Fal AI Nano Banana Pro $\rightarrow$ Airtable upload).
- **`2_Generate_Pending_Stories.py`**: Generate story images for existing pending rows in Airtable without scraping new items.
- **`3_Scrape_Akeneo_Wall_Lights.py`**: Scrape 2-item pairs of Wall Lights with layout.
- **`3_Scrape_Akeneo_Table_Lamps.py`**: Scrape 2-item pairs of Table Lamps with layout.
- **`3_Scrape_Akeneo_Cluster_Chandeliers.py`**: Scrape 2-item pairs of Cluster Chandeliers with layout.
- **`3_Scrape_Akeneo_Floor_Lamps.py`**: Scrape 2-item pairs of Floor Lamps with layout.
- **`3_Scrape_Akeneo_Chandeliers.py`**: Scrape 2-item pairs of Chandeliers with layout.
- **`3_Scrape_Akeneo_Pendant_Lights.py`**: Scrape 2-item pairs of Pendant Lights with layout.
- **`4_Interactive_Menu.py`**: One-click terminal interactive menu.
- **`README.md`**: Guide and usage instructions.

---

## 🚀 Quick Execution Examples

```bash
# Launch interactive terminal menu:
python "This or That Story/4_Interactive_Menu.py"

# Run 1 row end-to-end:
python "This or That Story/1_Run_Full_Story_Automation.py" --target wall_lights

# Run all 6 categories:
python "This or That Story/1_Run_Full_Story_Automation.py" --target all

# Generate pending records only:
python "This or That Story/2_Generate_Pending_Stories.py" --target wall_lights
```
