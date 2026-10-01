# UI Control editable configuration and counts

The Studio has 24 subtabs across 10 Story, 7 Feed, and 7 Reel, plus **Ad Covers** as a standalone 4th top-level tab of 9 per-fixture cards (all 9 fixtures are fully runnable). Twenty subtabs/tabs expose pencil controls for a Krea moodboard ID and room-interior prompt; all 9 Ad Covers cards (Chandelier, Floor Lamp, Table Lamp, Cluster Chandelier, Pendant Light, Wall Light, New Collection, On Sale Designs, On Stock Designs) expose their respective pencils through `/api/ad-cover/moodboard` and `/api/ad-cover/prompt`. Each pencil saves the fixture's mapped environment key through `UI Control/routes/common.py::save_config_override`. The value is written to `output/config_overrides.json` and `.env`, and the active server receives it immediately. At startup, saved overrides are loaded over `.env`.

For an edit, the UI posts `{fixture_id, moodboard_id}` to the active blueprint's `/moodboard` endpoint or `{fixture_id, prompt}` to `/prompt`. A run posts the current fixture settings to `/run`. A value supplied in that run takes precedence over its saved setting. Route modules own the fixture-to-key maps; keep those maps aligned with the runner's CLI arguments or environment lookup when adding a fixture.

| Format | Editable subtab | API prefix | Interior-setting path |
| --- | --- | --- | --- |
| Story | CTA | `/api/cta` | Blueprint fixture settings → CLI runner |
| Story | Tips & Educational | `/api/tips-edu` | Blueprint fixture settings → runner |
| Story | Collection Category | `/api/collection-story` | Blueprint fixture settings → runner |
| Story | Day & Night | `/api/day-night-story` | Blueprint fixture settings → runner |
| Story | Moodboard | `/api/moodboard-story` | Blueprint fixture settings → runner |
| Story | Style This | `/api/style-this` | Blueprint fixture settings → runner |
| Story | Myth & Fact | `/api/myth-fact-story` | Blueprint fixture settings → runner |
| Feed | Tips & Educational | `/api/tips-edu-feed` | Saved setting → `--moodboard-id` / `--prompt` |
| Feed | Moodboard #1 | `/api/moodboard-1-feed` | Saved setting → `--moodboard-id` / `--prompt` |
| Feed | Moodboard #2 | `/api/moodboard-2-feed` | Saved setting → generator environment settings |
| Feed | 1 Product, 3 Styles | `/api/one-product-3-styles` | Saved fixture settings → runner |
| Feed | Day & Night | `/api/day-night-feed` | Saved fixture settings → runner |
| Reel | Product Closeup | `/api/product-closeup-reel` | Table Lamp editor → four Krea interiors |
| Reel | Day & Night | `/api/day-night-reel` | Fixture settings → explicit runner CLI overrides |
| Reel | Before & After | `/api/before-after-reel` | Fixture settings → explicit runner CLI overrides |
| Reel | Style Reel Slideshow | `/api/style-reel-slideshow` | Editor controls cover (slot 1); slots 2–5 retain fixture-specific boards/prompts |
| Reel | Moodboard | `/api/moodboard-reel` | Fixture settings → explicit runner CLI overrides |
| Reel | 1 Product, 3 Styles | `/api/one-product-3-styles-reel` | Chandelier only; editor controls first interior style |
| Reel | One at a time Lights | `/api/one-at-a-time-lights-reel` | Single card; `KREA_MOODBOARD_ID_ONE_AT_A_TIME_LIGHTS` / `PROMPT_ONE_AT_A_TIME_LIGHTS_REEL_INTERIOR` → bedroom interior |
| Banner | Christmas Banner — 1 card | `/api/christmas-banner` | Card settings → `--moodboard-id` / `--interior-prompt`; `KREA_MOODBOARD_ID_CHRISTMAS_BANNER` / `CHRISTMAS_BANNER_PROMPT` |
| Banner | Sale Banner — 1 card (no pencils) | `/api/sale-banner` | Env only: `KREA_MOODBOARD_ID_SALE_BANNER_DINING` / `_BEDROOM`, `SALE_BANNER_DINING_PROMPT` / `_BEDROOM_PROMPT` |
| Ads | Ad Covers — 9 Fixtures (Chandelier, Floor Lamp, Table Lamp, Cluster Chandelier, Pendant Light, Wall Light, New Collection, On Sale Designs, On Stock Designs) | `/api/ad-cover` | Fixture settings → `--moodboard-id` / `--prompt`; `KREA_MOODBOARD_ID_<FIXTURE>_AD_COVER` / `AD_COVER_PROMPT_<FIXTURE>` |

The non-editable subtabs are Product Closeup Specs, Product Closeup Description, and This or That Story; Collection Category and Product Showcase Feed. Their cards still display live counts. All nine Ad Covers cards are runnable and hold their own saved moodboard/prompt settings.

Ad Cover pencils control Phases 1–2 only. The 9:16 extension prompt used by Phase 6 is deliberately **not** Studio-editable — it is environment-only (`AD_COVER_STORY_CONVERSION_PROMPT`, with `FAL_STORY_MODEL` to swap the model), because it is a frame-extension instruction rather than a room description. See [`ads/AD_COVER.md`](ads/AD_COVER.md) §4.

`GET /counts` returns `completed` from the `C` status badge only. Posted, pending, and processing are tracked in `P`; scheduled in `S`; discarded in `D`; and manual/revision in `FM`. Format and subtab totals add fixture `C` values only after all fixture requests are available. Until then, the UI shows `—` rather than a guessed zero. Target capacities are reference values for progress percentages, not generated-row totals.

The 1 Product, 3 Styles Reel uses the chandelier table configured by `AIRTABLE_TABLE_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL` (default `tbl6ls4AWcEcynBpZ`). Its three blended photos compile for 5, 4, and 4 seconds, followed by the existing 5-second outro. There are no Floor Lamp or other fixture table fields for that Reel's Studio card.
