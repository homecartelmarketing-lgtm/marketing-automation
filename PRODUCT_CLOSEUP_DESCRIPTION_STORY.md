# Product Closeup w/ Description Story Automation (9:16 Ratio)

End-to-end automated generation pipeline for **Product Closeup w/ Description Story** (1080 x 1920 px vertical Instagram Story) using **Fal AI Nano Banana Pro**.

---

## 🚀 Pipeline Workflow

| Phase | Action | Engine | Target Airtable Field | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Auto-Scrape Akeneo Product | `AkeneoClient` + `FurnitureItemScrapeRunner` | `Furniture Item`, `Item Name`, `SKU`, `Product Closeup Description Layout` | `Standby` |
| **Phase 2** | 9:16 Story Generation & Blending | `FalClient` (Nano Banana Pro) | `Product Closeup Description Converted` | `Complete` |

---

## 📋 Product Closeup w/ Description Category Table IDs

| Category | Airtable Table ID | Environment Key | Scraping Rules |
| :--- | :--- | :--- | :--- |
| **Chandeliers** | `tblDcT6jovdAbKnfw` | `AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION` | 1 Product per Row + `layout_product_v2.jpg` |
| **Pendant Lights** | `tblDD2w4v0Idb4jAZ` | `AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION` | 1 Product per Row + `layout_product_v2.jpg` |
| **Floor Lamps** | `tblPvHyKGByWJCMtY` | `AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION` | 1 Product per Row + `layout_product_v2.jpg` |
| **Cluster Chandeliers** | `tblnIOQVywHcTgAtv` | `AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION` | 1 Product per Row + `layout_product_v2.jpg` |
| **Table Lamps** | `tbl5S9JEHSrjrLwxA` | `AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION` | 1 Product per Row + `layout_product_v2.jpg` |
| **Wall Lights** | `tblYqudlgjYMNRROM` | `AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION` | 1 Product per Row + `layout_product_v2.jpg` |

---

## 📁 Dedicated Scripts Folder (`Product Closeup Description Story/`)

All scripts for Product Closeup Description Story are cleanly organized inside `Product Closeup Description Story/`:

- **`1_Run_Full_Story_Automation.py`**: Full end-to-end automation runner (Akeneo scrape $\rightarrow$ Fal AI Nano Banana Pro $\rightarrow$ Airtable upload).
- **`2_Generate_Pending_Stories.py`**: Generate story images for existing pending rows in Airtable without scraping new items.
- **`3_Scrape_Akeneo_Chandeliers.py`**: Scrape Chandeliers with layout.
- **`3_Scrape_Akeneo_Pendant_Lights.py`**: Scrape Pendant Lights with layout.
- **`3_Scrape_Akeneo_Floor_Lamps.py`**: Scrape Floor Lamps with layout.
- **`3_Scrape_Akeneo_Cluster_Chandeliers.py`**: Scrape Cluster Chandeliers with layout.
- **`3_Scrape_Akeneo_Table_Lamps.py`**: Scrape Table Lamps with layout.
- **`3_Scrape_Akeneo_Wall_Lights.py`**: Scrape Wall Lights with layout.
- **`4_Interactive_Menu.py`**: One-click terminal interactive menu.
- **`README.md`**: Detailed guide and usage instructions.

---

## 🚀 Quick Execution Examples

```bash
# Launch interactive terminal menu:
python "Product Closeup Description Story/4_Interactive_Menu.py"

# Run 1 item end-to-end:
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target chandeliers

# Run all 6 categories:
python "Product Closeup Description Story/1_Run_Full_Story_Automation.py" --target all

# Generate pending records only:
python "Product Closeup Description Story/2_Generate_Pending_Stories.py" --target chandeliers
```
