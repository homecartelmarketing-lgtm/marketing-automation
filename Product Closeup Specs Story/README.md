# Product Closeup w/ Specs Story Automation

> **Master Specification**: For complete architecture, model stack, Foreign Key conventions, and layout specs, see [`../docs/stories/PRODUCT_CLOSEUP_SPECS_STORY.md`](../docs/stories/PRODUCT_CLOSEUP_SPECS_STORY.md) and [`../AGENTS.md`](../AGENTS.md).

End-to-end automated pipeline para sa **Product Closeup w/ Specs Story** (1080 x 1920 px vertical 9:16 Instagram Story) gamit ang **Fal AI Nano Banana Pro** (`fal-ai/nano-banana-pro/edit`).

---

## 🚀 Pipeline Workflow

| Phase | Action | Engine | Target Airtable Field | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Auto-Scrape Akeneo Product (Shopify & Base Deduplication) | `AkeneoClient` + `FurnitureItemScrapeRunner` | `Furniture item`, `Item Name`, `Product Closeup w/ Specs Layout` | `Standby` |
| **Phase 2** | 9:16 Story Card Generation & Blending | `FalClient` (`fal-ai/nano-banana-pro/edit`) | `PCS Story` | `Done` |

---

## 📋 Table Configuration

- **Table ID**: `tblEGTB6BodRVDqBV` (*Product Closeup w/ Specification Chandelier*)
- **Input 1**: `Product Closeup w/ Specs Layout` (attachment `product_specs_layout.png`)
- **Input 2**: `Furniture item` (Akeneo downloaded product photo)
- **Prompt Reference**: `JSON Prompts/Product Closeup with Specs/product_closeup_specs.json`
- **Output Field**: `PCS Story` (9:16 vertical poster)

---

## 📁 Dedicated Scripts Folder (`Product Closeup Specs Story/`)

- **`1_Run_Full_Story_Automation.py`**: Full end-to-end automation (Akeneo scrape $\rightarrow$ Fal AI Nano Banana Pro $\rightarrow$ `PCS Story` upload $\rightarrow$ Status: Done).
- **`2_Generate_Pending_Stories.py`**: I-generate ang story cards para sa mga existing pending rows nang hindi nag-i-scrape ng panibago.
- **`3_Scrape_Akeneo_Chandeliers.py`**: Scrape Chandeliers lamang na may layout attachment at Shopify deduplication.
- **`4_Interactive_Menu.py`**: Console interactive menu para sa madaling pagpapatakbo.

---

## 🚀 Quick Execution Examples

```bash
# Ilunsad ang interactive terminal menu:
python "Product Closeup Specs Story/4_Interactive_Menu.py"

# Patakbuhin ang 1 item end-to-end:
python "Product Closeup Specs Story/1_Run_Full_Story_Automation.py"

# I-generate ang mga pending records lamang:
python "Product Closeup Specs Story/2_Generate_Pending_Stories.py"

# Mag-scrape lamang ng 1 chandelier:
python "Product Closeup Specs Story/3_Scrape_Akeneo_Chandeliers.py" --count 1
```
