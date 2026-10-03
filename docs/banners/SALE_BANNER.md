# Sale Banner (1800 x 600)

A wide sale banner in the style of the Canva reference: a **centre panel** with the sale text (its colour is suggested by Claude for each run, red `#FF3131` as the fallback), and on each side a Krea-generated **modern Christmas interior** with scraped fixtures blended in by Nano Banana Pro.

- **Left:** dining room with **1 pendant light**. **Right:** kitchen with **2 pendant lights** hung side by side over the island.
- **Text:** `Limited -Time Offer` / `SALE` / two blocks `UP TO 10% OFF` and `UP TO 15% OFF`, each with a caption such as `On all items from curated monthly collection on October 1-31, 2026`. Percentages and dates (with the year) come from the promotions calendar.
- **One row with the Christmas banner:** in the Studio and in normal use the Sale banner is made together with the main banner by the **Banner Set** ([`BANNER_SET.md`](BANNER_SET.md), `generate_banner_set_pipeline.py`): one scrape, one new row, both banners on it (`Banner with Text` and `Sale Banner`). The set runs this script's phases 2-6 as its phases 7-11 on that same row.
- **Script:** `generate_sale_banner_pipeline.py` - on its own (CLI only) it still creates its own row with `Category = Sale Banner` (Phase 1); with `--record-id` it works on an existing row, such as one made by the Banner Set. **Studio:** no separate sub-tab any more (it would have created a second row); `/api/sale-banner/*` (`UI Control/routes/sale_banner.py`) remains for the API.
- **Airtable:** shares the Christmas banner table (`tblgNk1Tp6qKUcduw`). Missing columns are created on the first run. `ID` is an autoNumber and is never written.

## Phases

| # | Phase | Detail | Airtable |
| :-- | :-- | :-- | :-- |
| 1 | Akeneo scrape | Three different newest unused Shopify-active `pendant_lights` items: `DP` (dining room; not `PE`, which is the Christmas banner's pendant in a shared row) and `KA`, `KB` (kitchen island). Nothing is written if any is missing. In the Banner Set this phase is part of the set's Phase 1 (8 products). | New row; `Furniture Item` (DP, KA, KB cutouts), `SKU`, `Item Name`, `Item Details` |
| 2 | Krea x2 | 4:5 (each side slot is 483x600), 1K. Dining moodboard `de5f4ff8-...`; the kitchen reuses that moodboard until `KREA_MOODBOARD_ID_SALE_BANNER_KITCHEN` is set. The prompts are short defaults on purpose ("Generate me a modern luxury dining room with a Christmas theme" / "... kitchen ..."): the moodboard carries the look. | `Dining Interior`, `Kitchen Interior`, `Dining Interior Prompt`, `Kitchen Interior Prompt` |
| 3 | Claude x2 | For each room Claude studies that room and its items and writes a blending prompt (same three stages and validation as the Christmas banner; no reserved text zone; the kitchen rule hangs the two pendants side by side over the island). | `Dining Blending Prompt`, `Kitchen Blending Prompt` |
| 4 | Nano Banana Pro x2 | `fal-ai/nano-banana-pro/edit`, 4:5, jpeg, resolution `2K`: `[dining interior, pendant]` and `[kitchen interior, pendant A, pendant B]`. | `Dining Blended`, `Kitchen Blended` |
| 5 | Captions + panel colour | Percent and date window (with the year) read from `calendar_config.json` (see below). Then one Claude Sonnet 5 vision call over the two room blends suggests the panel's hex colour (see below). | `Sale Percent Left/Right`, `Sale Caption Left/Right`, `Sale Panel Color` |
| 6 | Composite | Local Pillow: blends cover-fitted into the side slots, panel in the stored colour, Poppins text. | `Sale Banner` (final), `Status = Done`, `Date and Time Generated` when run alone; in the Banner Set it writes `Status = Sale Banner Done` and the third banner finishes the row |

Local copies go to `output/sale_banner/` (`dining_blend_<rec>.jpg`, `kitchen_blend_<rec>.jpg`, `sale_banner_<rec>.jpg`). Rows made before the kitchen change carry `Bedroom ...` fields and cannot be re-composited (Phase 6 needs `Kitchen Blended`).

## Percentages and captions (the calendar)

`HC Monthly Promotions Calendar.pdf` is one flattened page and has no caption wording or date strings, so the runtime source is its structured version, `calendar_config.json` (hand-transcribed from the PDF and also used by the monthly sale automation in `Auto Export Inventory`). A copy lives in `assets/calendar_config.json`; `PROMO_CALENDAR_PATH` overrides it. **If the promotion plan changes, update that copy.**

| Side | Event key | Percent | Caption template |
| :-- | :-- | :-- | :-- |
| Left | `ten_off_monthly` | parsed from the event name ("10% OFF ...") | `On all items from curated monthly collection on {date}` |
| Right | `fifteen_off_monthly` | parsed from the event name ("15% OFF ...") | `On all items from a curated collection on {date}` |

`{date}` is the event window for the target month, always with the year: whole-month events give `October 1-31, 2026`; events with `start_md`/`end_md` give `October 25 - November 30, 2026` or `December 12-14, 2026`, and a window that crosses New Year gives `December 25, 2026 - January 5, 2027`. The target month is the current month, or the next one from day 24 (same rule as `run_monthly_sale.py`); override with `--month` and `--year`. Code: `content_automation/promo_calendar.py`.

## Panel colour (Phase 5)

Claude Sonnet 5 receives `Dining Blended` and `Kitchen Blended` and is asked for ONE `#RRGGBB` taken from the actual palettes of the two photos, in any hue (it is told **not to default to red**, so the colour changes with the photos), rich rather than pastel, and mid-dark so white text stays readable. The prompt describes the two photos as a dining room and a kitchen and contains no example colour that could anchor the answer. The reply is parsed for the first hex code and saved in `Sale Panel Color`.

- **Contrast guard:** if white text on the colour is below 4.5:1 (WCAG AA), the colour is darkened in small steps, keeping its hue, until it passes.
- **Fallback:** an API error, a missing blend or two replies without a hex code use the sample's red `#FF3131`; the run never fails because of the colour.
- **Override:** `--panel-color "#0B3D2E"` skips Claude and uses that colour as given (a warning is printed if it is low-contrast). To change the colour of an existing banner, edit `Sale Panel Color` in Airtable and run `--only-phase 6`, or re-roll Claude's suggestion with `--only-phase 5` then `--only-phase 6`.

## Layout spec (Phase 6)

Fitted numerically to the reference sample (`content_automation/overlay.py`, `draw_sale_banner`). Canvas 1800 x 600; panel columns 483-1316 (the two edge columns are a 50% mix of panel and photo, like the sample), red `(255, 49, 49)` in the sample and `Sale Panel Color` in a run; photos in columns 0-482 and 1317-1799, cover-fitted. All text is white Poppins, tracking about -0.09 em.

| Element | Font | Canva size (px) | Notes |
| :-- | :-- | :-- | :-- |
| `Limited -Time Offer` | Medium (what Canva's B toggle renders) | 60.9 pt (81.2 px) | baseline y=117; text is exactly as in the sample; ink centred on x=909.5; ink ~643 px wide like the Canva box |
| `SALE` | Medium (what Canva's B toggle renders) | 168 pt (224 px) | baseline y=299; ink centred on x=900.5; Canva letter spacing -94 = -0.094 em, ink ~418 px wide |
| Big number (`10`, `15`) | Regular | 141 pt (188 px) | baseline y=493; digits use -0.09 em (the sample's `XX` was fitted at -0.17 em because the X glyphs overlap) |
| `%` (over `OFF`) | Regular | 50.5 pt (67.3 px) | superscript, baseline y=401 |
| `OFF` | Regular | 51.3 pt (68.4 px) | baseline y=462 |
| `UP TO` | Regular | 26.7 pt (35.6 px) | rotated 90 degrees counter-clockwise, ink bottom y=408 |
| Captions | Regular | 13.6 pt (18.1 px) | centred under each block, greedy wrap at 290 px (reproduces the sample's line breaks), baseline pitch 21.0 px (a 2-line Canva box is 41.8 px tall) |

Font sizes are the values shown in Canva, in points; the code converts them with 1 pt = 4/3 px (`SALE_PT_TO_PX`, `SALE_*_PT` in `overlay.py`). Change a size there and the headline, `SALE` and the percent blocks re-centre themselves on their anchors.

The two percent blocks use one shared geometry (the sample's right block sits a few pixels off the left one; here they are aligned) and each block is centred on its slot (x 709.5 and 1092.5).

## Configuration

| Key | Purpose |
| :-- | :-- |
| `AIRTABLE_TABLE_ID_SALE_BANNER` | Optional. Default: `AIRTABLE_TABLE_ID_CHRISTMAS_BANNER`, then `tblgNk1Tp6qKUcduw`. |
| `KREA_MOODBOARD_ID_SALE_BANNER_DINING` / `_KITCHEN` | Krea moodboards (the dining default is in `.env.example`; the kitchen falls back to the dining moodboard). There are no Studio pencils for these. |
| `SALE_BANNER_DINING_PROMPT` / `SALE_BANNER_KITCHEN_PROMPT` | Krea prompts. |
| `SALE_BANNER_RESOLUTION` | `1K`, `2K` (default) or `4K` for the two blends. |
| `PROMO_CALENDAR_PATH` | Path to `calendar_config.json`. |
| `CLAUDE_VISION_MODEL`, `FAL_BLENDING_MODEL` | Optional model overrides (shared with the Christmas banner). |

## CLI

```powershell
cd C:\Users\User\Desktop\marketing-automation
python generate_sale_banner_pipeline.py                                          # full run, fresh row
python generate_sale_banner_pipeline.py --month 11 --year 2026                   # captions for another month
python generate_sale_banner_pipeline.py --record-id recXXXX --from-phase 3       # new prompts + blends + banner, same rooms and items
python generate_sale_banner_pipeline.py --record-id recXXXX --only-phase 4       # room blends only
python generate_sale_banner_pipeline.py --record-id recXXXX --only-phase 5       # captions + a new Claude panel colour (one Claude call)
python generate_sale_banner_pipeline.py --record-id recXXXX --only-phase 6       # rebuild the banner only (no API cost)
python generate_sale_banner_pipeline.py --record-id recXXXX --text-only          # = --from-phase 5: captions + panel colour + composite (one Claude call, no image generation)
python generate_sale_banner_pipeline.py --record-id recXXXX --from-phase 5 --panel-color "#0B3D2E"   # your own panel colour, no Claude
python generate_sale_banner_pipeline.py --dining-moodboard-id <id> --kitchen-prompt "<prompt>"
```

`--only-phase N` runs that phase alone and prints a note about which outputs are now stale (for example after `--only-phase 4`, run `--only-phase 6` to rebuild `Sale Banner`). It needs `--record-id` and cannot be combined with `--from-phase` or `--text-only`. On any exception the row is set to `For Manual`.
