# UI Control editable configuration and counts

The Studio has 30 subtabs across 10 Story, 7 Feed, and 13 Reel, plus **Ad Covers** as a standalone 4th top-level tab of 9 per-fixture cards (all 9 fixtures are fully runnable) and a **Banner** tab (Christmas, Sale). Most subtabs/tabs expose pencil controls for a Krea moodboard ID and room-interior prompt; all 9 Ad Covers cards (Chandelier, Floor Lamp, Table Lamp, Cluster Chandelier, Pendant Light, Wall Light, New Collection, On Sale Designs, On Stock Designs) expose their respective pencils through `/api/ad-cover/moodboard` and `/api/ad-cover/prompt`. Each pencil saves the fixture's mapped environment key through `UI Control/routes/common.py::save_config_override`. The value is written to `output/config_overrides.json` and `.env`, and the active server receives it immediately. Empty values and the strings `none`, `null` and `undefined` are ignored (they used to be saved as the literal prompt "None"). At startup, saved overrides are loaded over `.env`.

For an edit, the UI posts `{fixture_id, moodboard_id}` to the active blueprint's `/moodboard` endpoint or `{fixture_id, prompt}` to `/prompt`. A run posts the current fixture settings to `/run`. A value supplied in that run takes precedence over its saved setting. Route modules own the fixture-to-key maps; keep those maps aligned with the runner's CLI arguments or environment lookup when adding a fixture.

Studio saves go to `output/config_overrides.json` (+ `os.environ`) only — never to `.env`. Standalone CLI runs read the same values via `content_automation.fixture_catalog.load_studio_overrides()`. Fixture wiring truth lives in `content_automation/fixture_catalog.py` (pilot: CTA Story; enforced by `tests/test_cta_catalog_consistency.py`).

The Studio header also carries a **Marketing Calendar** shortcut (`App.tsx::MARKETING_CALENDAR_URL`) that opens `https://homecartel-marketing-calendar-v2.vercel.app/` in a new tab. It is a plain external link with no Studio setting or backend route.

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
| Reel | Sketch to Real | `/api/sketch-to-draw-reel` | Chandelier and Pendant cards; `KREA_MOODBOARD_ID_SKETCH_TO_REAL_*` / `PROMPT_SKETCH_TO_REAL_REEL_*` (old `..._SKETCH_TO_DRAW_...` names still work as fallbacks) → Krea interior |
| Reel | House Tour | `/api/house-tour-reel` | Single card; its moodboard + prompt pencils each hold 11 labeled room fields (Living/Bedroom/Dining/Kitchen/Lounge/Hallway/Office/Bathroom/Entryway/Sunroom/Kids Bedroom) saved to `KREA_MOODBOARD_ID_HOUSE_TOUR_REEL_ROOM1..11` / `PROMPT_HOUSE_TOUR_REEL_ROOM1..11` (generic `KREA_MOODBOARD_ID_HOUSE_TOUR_REEL` / `PROMPT_HOUSE_TOUR_REEL` is fallback only). A Run processes the full 11-room tour |
| Reel | Room Build-Up | `/api/room-build-up-reel` | Single card (`room-build-up`); one moodboard edit and one prompt edit are each written to **both** rooms: `KREA_MOODBOARD_ID_ROOM_BUILD_UP_REEL_ROOM1` / `..._ROOM2` and `PROMPT_ROOM_BUILD_UP_REEL_ROOM1` / `..._ROOM2` (default prompt `Generate me a modern living room`) → the two furnished Krea interiors |
| Reel | This Mood Every Night | `/api/this-mood-every-night-reel` | Single card; its moodboard + prompt pencils hold 7 night room values saved to `KREA_MOODBOARD_ID_THIS_MOOD_EVERY_NIGHT_REEL_ROOM1..7` / `PROMPT_THIS_MOOD_EVERY_NIGHT_REEL_ROOM1..7` (built-in night prompts when unset). A Run processes all 7 rooms |
| Reel | Virtual Staging | `/api/virtual-staging-reel` | Chandelier card; Auto mode: `KREA_MOODBOARD_ID_VIRTUAL_STAGING_REEL` / `PROMPT_VIRTUAL_STAGING_REEL` → Krea luxury furnished interior; Upload mode: `POST /api/virtual-staging-reel/upload-empty-room` (9:16 crop & Fal CDN upload) + `KLING_PROMPT_VIRTUAL_STAGING_REEL` via `/api/virtual-staging-reel/kling-prompt` |
| Reel | Room Reveal | `/api/room-reveal-reel` | Single card (`room-reveal`); `KREA_MOODBOARD_ID_ROOM_REVEAL_REEL` / `PROMPT_ROOM_REVEAL_REEL` (default prompt `Generate me a modern living room`; scraped category via `ROOM_REVEAL_REEL_CATEGORY`, default `chandeliers`) → the one locked-angle Krea interior |
| Banner | Banner Set — 1 card (one run, one Airtable row, three banners: Christmas, Sale, third) | `/api/christmas-banner` | Card settings → `--moodboard-id` / `--interior-prompt` (Christmas living room); `KREA_MOODBOARD_ID_CHRISTMAS_BANNER` / `CHRISTMAS_BANNER_PROMPT`. The Sale rooms and the third banner's bedroom have no pencils, env only (`KREA_MOODBOARD_ID_THIRD_BANNER`, `THIRD_BANNER_PROMPT`, `THIRD_BANNER_TITLE`, `THIRD_BANNER_SUBTITLE`): `KREA_MOODBOARD_ID_SALE_BANNER_DINING` / `_KITCHEN`, `SALE_BANNER_DINING_PROMPT` / `_KITCHEN_PROMPT`. The separate Sale Banner sub-tab was removed (`/api/sale-banner` stays for API/CLI only). |
| Ads | Ad Covers — 9 Fixtures (Chandelier, Floor Lamp, Table Lamp, Cluster Chandelier, Pendant Light, Wall Light, New Collection, On Sale Designs, On Stock Designs) | `/api/ad-cover` | Fixture settings → `--moodboard-id` / `--prompt`; `KREA_MOODBOARD_ID_<FIXTURE>_AD_COVER` / `AD_COVER_PROMPT_<FIXTURE>` |

The non-editable subtabs are Product Closeup Specs, Product Closeup Description, and This or That Story; Collection Category and Product Showcase Feed. Their cards still display live counts. All nine Ad Covers cards are runnable and hold their own saved moodboard/prompt settings.

Ad Cover pencils control Phases 1–2 only. The 9:16 extension prompt used by Phase 6 is deliberately **not** Studio-editable — it is environment-only (`AD_COVER_STORY_CONVERSION_PROMPT`, with `FAL_STORY_MODEL` to swap the model), because it is a frame-extension instruction rather than a room description. See [`ads/AD_COVER.md`](ads/AD_COVER.md) §4.

`GET /counts` returns `completed` from the `C` status badge only. Posted, pending, and processing are tracked in `P`; scheduled in `S`; discarded in `D`; and manual/revision in `FM`. Format and subtab totals add fixture `C` values only after all fixture requests are available. Until then, the UI shows `—` rather than a guessed zero. Target capacities are reference values for progress percentages, not generated-row totals.

Scale-guard audit columns (`Scale Check`, `Scale Retry`, `Scale Audit`) are written by the generators, not the Studio, and are not editable in the UI. They appear in the Airtable table and in Row Inspector like any other column. `SCALE_GUARD_ENABLED=0` turns the extra measurement calls off for every pipeline ([`SCALE_GUARD.md`](SCALE_GUARD.md)).

The 1 Product, 3 Styles Reel uses the chandelier table configured by `AIRTABLE_TABLE_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL` (default `tbl6ls4AWcEcynBpZ`). Its three blended photos compile for 5, 4, and 4 seconds, followed by the existing 5-second outro. There are no Floor Lamp or other fixture table fields for that Reel's Studio card.

### RunCenter utilities (no pencils)

The **Calendar** import button in `RunCenter.tsx` (`components/planning/CalendarImportModal.tsx`, blueprint `routes/calendar.py`) has no moodboard/prompt settings — it uploads a Content Calendar workbook and enqueues `TO DO` slots via `POST /api/calendar/preview` + `POST /api/calendar/enqueue` into the queue above. Fixture pointer: `output/calendar_fixture_state.json` (gitignored). Idea→pipeline map: `assets/calendar_pipeline_map.json`.

## Studio login (email + password)

Not a Studio-editable setting: accounts and the session are configured through `.env` and the CLI.

| Key / tool | Purpose |
| :--- | :--- |
| `python scripts/ops/manage_studio_users.py add\|list\|set-password\|remove` | Create and manage accounts (admin-managed; "Sign Up" and "Forgot Password" on the login screen email the admin) |
| `STUDIO_USERS_PATH` | Accounts file, default `output/studio_users.json` |
| `STUDIO_ADMIN_EMAIL` / `STUDIO_ADMIN_PASSWORD` | Optional env-seeded admin that survives a wiped disk |
| `STUDIO_ADMIN_PASSWORD_HASH` | Hash of the admin password (print with `manage_studio_users.py env <email>`); use instead of the plaintext `STUDIO_ADMIN_PASSWORD` on Railway |
| `STUDIO_ADMIN2_EMAIL` / `STUDIO_ADMIN2_PASSWORD_HASH` | Optional second env-seeded account (`manage_studio_users.py env <email> --second`); also set `STUDIO_MAX_ACCOUNTS=2` |
| `STUDIO_SECRET_KEY` | Cookie signing key (auto-generated into `output/.studio_secret_key` when empty) |
| `STUDIO_MAX_ACCOUNTS` | Account limit, default `1` (one shared team login). The env-seeded admin counts toward it |
| `STUDIO_SESSION_HOURS`, `STUDIO_COOKIE_SECURE` | Session length (default 12) and the `Secure` cookie flag (set to `1` over HTTPS) |
| `DASHBOARD_PIN` | Legacy shared PIN. Single-field login until the first account exists; afterwards only for scripts |

Details: `UI Control/README.md` (Security & Access Control) and `docs/memory/decisions/2026-10-12-studio-email-password-login.md`.
