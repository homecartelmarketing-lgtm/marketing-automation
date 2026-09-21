---
date: 2026-09-19
pipeline: 1 Product 3 Styles Feed (Chandeliers, Pendant Lights, Floor Lamps)
status: resolved
---

# 1 Product 3 Styles Feed: Missing `split_item_name` Import Causing Unpopulated Item Tagging

## Symptom

When running the 1 Product 3 Styles Feed pipeline from either CLI or the Control UI, the pipeline successfully blended all 3 rooms, stamped the brand logo onto Slide 1, and uploaded to `1 Product 3 Style Blended`. However, the tagged version field **`Blended Image with Name text`** remained completely empty. 

The console logged:
```
[WARN] Failed auto-tagging item name onto blended slides for record recAaLnxVlpOBORpp: name 'split_item_name' is not defined
```

## How it was diagnosed

1. Inspected line 677 of [`run_1_product_3_styles_feed.py`](../../run_1_product_3_styles_feed.py):
   ```python
   item_title, product_type = split_item_name(raw_item_name, item_type or target_fixture)
   ```
2. Checked imports at top of `run_1_product_3_styles_feed.py`. Only `AkeneoClient` was imported from `content_automation.akeneo_client`:
   ```python
   from content_automation.akeneo_client import AkeneoClient  # split_item_name was missing
   ```
3. Because the call was wrapped in a broad `try...except Exception as tag_err:` block, the `NameError` did not fail the pipeline but silently skipped stamping and uploading the 3 tagged slides to `Blended Image with Name text`.

## Root Cause

`split_item_name` was omitted from the `from content_automation.akeneo_client import ...` statement when the item tagging block was originally introduced into `run_1_product_3_styles_feed.py`.

## Resolution

1. **Import Fixed**: Added `split_item_name` to the import list in [`run_1_product_3_styles_feed.py`](../../run_1_product_3_styles_feed.py).
2. **Category Fallbacks**: Added fallback defaults for product categories (`Chandelier`, `Pendant Light`, `Floor Lamp`) so rows with missing `Product Type` fields still receive clean, accurate 2-line tags.
3. **Automated Backfill**: Developed and executed [`backfill_1_product_3_styles_tags.py`](../../backfill_1_product_3_styles_tags.py), which audited all 3 tables:
   - `tblrlfqBGe5EjS5PI` (Chandeliers): 4 records backfilled (`rec5NlHXJzXh3fAlJ`, `rec5YlcAV2N8BdZsW`, `rec9WrLcg6SSsGqeb`, `recFR1ZfwXaIOcJwW`).
   - `tblRy52kCasisCWzd` (Pendant Lights): 5 records backfilled (`recAaLnxVlpOBORpp`, `recIxm4lzlw2QXtMC`, `recOhYMIYBr4AKICG`, `recj60WkrU9JJQZva`, `recoZyH2y3E7bAwtb`).
   - `tbl9GIq2QeYCwMhWU` (Floor Lamps): 0 untagged records found.
4. **Verification**: Final audit confirmed 0 untagged completed rows remain across the entire 1 Product 3 Styles Feed base.
