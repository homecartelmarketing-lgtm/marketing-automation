# Tips & Educational Feed: Phase 5 `category_label` AttributeError & Missing Tips Stamping

**Symptom:** When running Tips & Educational Feed from the Web Control UI (which runs `--phase all`), rows were completed through Phase 4 (blending and tips text generation), but stopped before producing the final 3 feed slides in `Tips and Edu Feeds`, and no tips or numerals were stamped.

**Root cause:** 
1. Phase 5 in `run_tips_and_edu_feed.py` attempted to call `split_item_name(raw_name, fallback_product_type=self.category_label)`.
2. `TipsAndEduFeedRunner` had no `category_label` attribute (only `fixture_label`), causing an unhandled `AttributeError: 'TipsAndEduFeedRunner' object has no attribute 'category_label'`.
3. Because Phase 5 crashed, Phase 6 (`phase_6`: Programmatic PIL Layout Compositing) was never executed, leaving `Tips and Edu Feeds` empty.
4. Additionally, Airtable tables contained both `Tips 1..3` and legacy `Tip1..3` columns, causing potential view confusion when only one format was populated.

**Fix & Design Decisions:**
1. **No Synthetic Fallback Properties**: Rejected creating synthetic properties (`category_label` or `fallback_category_label`) on the runner class. Instead, Phase 5 strictly extracts `raw_name = fields.get("Item Name[1-3]")` and `product_type_val = fields.get("Product Type[1-3]")` directly from the Airtable record, passing `fallback_product_type=product_type_val` directly into `split_item_name`.
2. **Dual-Write Schema Sync**: Updated `generate_tips_texts` to dual-write tips into both primary (`Tips 1..3`, including trailing whitespace variations like `Tips 2 `) and legacy/alternative (`Tip1..3`) fields if present in the table schema.
3. **Studio Route Phase Alignment**: Updated `UI Control/routes/tips_edu_feed.py` initial state `total_phases` to `6` so the UI progress tracking correctly recognizes all 6 phases.
4. **Documentation**: Updated pipeline documentation in `docs/feeds/TIPS_AND_EDU_FEED.md`.

**Verification:**
- Ran full test suite: 469 tests passed cleanly (`Ran 469 tests in 42.493s, OK`).
- Verified Python bytecode compilation of modified scripts.
- Verified absence of surrogate properties in `run_tips_and_edu_feed.py`.
