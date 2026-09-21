# UI Control editable configuration and counts

The Studio has 23 subtabs: 10 Story, 7 Feed, and 6 Reel. Eighteen of those expose pencil controls for a Krea moodboard ID and room-interior prompt. Each pencil saves the fixture's mapped environment key through `UI Control/routes/common.py::save_config_override`. The value is written to `output/config_overrides.json` and `.env`, and the active server receives it immediately. At startup, saved overrides are loaded over `.env`.

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

The non-editable subtabs are Product Closeup Specs, Product Closeup Description, and This or That Story; Collection Category and Product Showcase Feed. Their cards still display live counts.

`GET /counts` returns `completed` from the `C` status badge only. Posted, pending, and processing are tracked in `P`; scheduled in `S`; discarded in `D`; and manual/revision in `FM`. Format and subtab totals add fixture `C` values only after all fixture requests are available. Until then, the UI shows `—` rather than a guessed zero. Target capacities are reference values for progress percentages, not generated-row totals.

The 1 Product, 3 Styles Reel uses the chandelier table configured by `AIRTABLE_TABLE_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL` (default `tbl6ls4AWcEcynBpZ`). Its three blended photos compile for 5, 4, and 4 seconds, followed by the existing 5-second outro. There are no Floor Lamp or other fixture table fields for that Reel's Studio card.
