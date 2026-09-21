# 1 Product, 3 Styles Feed Automation Pipeline

> **Master Specification**: For complete architecture, model stack, Foreign Key conventions, and Canva coordinates, see [`../docs/feeds/ONE_PRODUCT_THREE_STYLES_FEED.md`](../docs/feeds/ONE_PRODUCT_THREE_STYLES_FEED.md) and [`../AGENTS.md`](../AGENTS.md).

The **1 Product, 3 Styles Feed Automation** is an automated marketing pipeline designed to take **1 lighting/furniture product** and blend it into **3 distinct luxury room interior styles** (e.g., Grand Living Room, Luxury Dining Room, High Ceiling Foyer) at **4:5 vertical Instagram Feed format (1K Resolution)**, with the **official HomeCartel® logo stamped onto the first blended image**.

---

## 📁 File Structure & Script Roles

| File | Description | When to Use |
| :--- | :--- | :--- |
| **`4_Interactive_Menu.py`** | Interactive console menu with one-key options for all tasks. | Pinakamadaling paraan para patakbuhin ang automation. |
| **`1_Run_Full_Feed_Automation.py`** | Runs full Phase 1 to Phase 4 end-to-end pipeline. | Kapag nais mag-scrape at mag-generate mula simula hanggang dulo. |
| **`2_Generate_Pending_Feeds.py`** | Processes existing rows in Airtable from Phase 2 onwards. | Kapag may mga Standby rows na at nais lamang mag-generate ng images. |
| **`3_Scrape_Akeneo_Chandeliers.py`** | Dedicated Akeneo scraper for Chandeliers (`tblrlfqBGe5EjS5PI`). | Para mag-scrape ng Chandeliers with Cross-Table Deduplication. |
| **`3_Scrape_Akeneo_Pendant_Lights.py`** | Dedicated Akeneo scraper for Pendant Lights (`tblRy52kCasisCWzd`). | Para mag-scrape ng Pendant Lights with Cross-Table Deduplication. |
| **`3_Scrape_Akeneo_Floor_Lamps.py`** | Dedicated Akeneo scraper for Floor Lamps (`tbl9GIq2QeYCwMhWU`). | Para mag-scrape ng Floor Lamps with Cross-Table Deduplication. |

---

## 🎯 Supported Category Presets & Table IDs

| Category | Airtable Table ID | Krea Moodboard ID | Room Styles Generated |
| :--- | :--- | :--- | :--- |
| **Chandeliers** | `tblrlfqBGe5EjS5PI` | `de6ad512-870d-4ab7-a48c-3f3ca85faf24` | 1. Grand Living Room (`Interior1` / `Prompt1`)<br>2. Luxury Dining Room (`Interior2` / `Prompt2`)<br>3. High Ceiling Foyer (`Interior3` / `Prompt3`) |
| **Pendant Lights** | `tblRy52kCasisCWzd` | `2a4a62bf-c6eb-49f8-8808-2543200634a0` | 1. Dining Room (`Interior1` / `Prompt1`)<br>2. Kitchen Island (`Interior2` / `Prompt2`)<br>3. Living Room Corner (`Interior3` / `Prompt3`) |
| **Floor Lamps** | `tbl9GIq2QeYCwMhWU` | `b1641228-beec-4823-8d01-1de3eec8410d` | 1. Living Room Lounge (`Interior1` / `Prompt1`)<br>2. Bedroom Corner (`Interior2` / `Prompt2`)<br>3. Study Reading Nook (`Interior3` / `Prompt3`) |

---

## 🛡️ Cross-Table Deduplication & Akeneo Filters

1. **Base-Wide Cross-Table Deduplication**:
   - Bago mag-create ng bagong row sa Airtable, ini-scan ang **lahat ng tables sa buong Airtable base** upang suriin ang existing SKUs, Item Names, at image filenames.
   - Hindi ma-u-upload ang product kung nagamit na ito sa ibang feed/story table.

2. **Active & Scoped Products Only**:
   - Tanging ang mga produktong `enabled: True` sa Akeneo at kabilang sa configured channel (`CHANNEL_NAME`) ang kinukuha.
   - Newest products are prioritized first with price sorting.

---

## 🚀 Execution Commands

### 1. Interactive Menu
```bash
python "1 Product 3 Styles Feed/4_Interactive_Menu.py"
```

### 2. Run Full Automation
```bash
# Chandeliers
python "1 Product 3 Styles Feed/1_Run_Full_Feed_Automation.py" --target chandeliers

# Pendant Lights
python "1 Product 3 Styles Feed/1_Run_Full_Feed_Automation.py" --target pendant_lights

# Floor Lamps
python "1 Product 3 Styles Feed/1_Run_Full_Feed_Automation.py" --target floor_lamps
```

### 3. Mass Scrape Akeneo Products
```bash
# Preview / Dry Run
python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Chandeliers.py"
python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Pendant_Lights.py"
python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Floor_Lamps.py"

# Live Execute (Save 3 items to Airtable)
python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Chandeliers.py" --execute --max-items 3
python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Pendant_Lights.py" --execute --max-items 3
python "1 Product 3 Styles Feed/3_Scrape_Akeneo_Floor_Lamps.py" --execute --max-items 3
```

### 4. Process Pending Rows Only (Phase 2 to 4)
```bash
python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target chandeliers --max-rows 3
python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target pendant_lights --max-rows 3
python "1 Product 3 Styles Feed/2_Generate_Pending_Feeds.py" --target floor_lamps --max-rows 3
```
