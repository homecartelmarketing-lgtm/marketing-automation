# Sale Banner (1800 x 600)

A wide sale banner in the style of the Canva reference: a **centre panel** with the sale text (its colour is suggested by Claude for each run, red `#FF3131` as the fallback), and on each side a Krea-generated **modern Christmas interior** with scraped fixtures blended in by Nano Banana Pro.

- **Left:** dining room with **1 pendant light**. **Right:** bedroom with **2 table lamps** (one per bedside table).
- **Text:** `Limited -Time Offer` / `SALE` / two blocks `UP TO 10% OFF` and `UP TO 15% OFF`, each with a caption such as `On all items from curated monthly collection on October 1-31, 2026`. Percentages and dates (with the year) come from the promotions calendar.
- **Script:** `generate_sale_banner_pipeline.py` - **Studio:** second sub-tab of the **Banner** tab, `/api/sale-banner/*` (`UI Control/routes/sale_banner.py`).
- **Airtable:** shares the Christmas banner table (`tblgNk1Tp6qKUcduw`); rows are told apart by `Category = Sale Banner`, and each banner's Studio counts only its own rows. Missing columns are created on the first run. `ID` is an autoNumber and is never written.

## Phases

| # | Phase | Detail | Airtable |
| :-- | :-- | :-- | :-- |
| 1 | Akeneo scrape | Newest unused Shopify-active `pendant_lights` item (code `PE`) and two `table_lamps` items (`TA`, `TB`). Nothing is written if any is missing. | New row; `Furniture Item` (PE, TA, TB cutouts), `SKU`, `Item Name`, `Item Details` |
| 2 | Krea x2 | 4:5 (each side slot is 483x600), 1K. Dining moodboard `de5f4ff8-...`, bedroom moodboard `fb2487fb-...`; "modern ... with a Christmas theme" prompts. | `Dining Interior`, `Bedroom Interior`, `Dining Interior Prompt`, `Bedroom Interior Prompt` |
| 3 | Claude x2 | For each room Claude studies that room and its items and writes a blending prompt (same three stages and validation as the Christmas banner; no reserved text zone; the bedroom rule puts one lamp on each bedside table). | `Dining Blending Prompt`, `Bedroom Blending Prompt` |
| 4 | Nano Banana Pro x2 | `fal-ai/nano-banana-pro/edit`, 4:5, jpeg, resolution `2K`: `[dining interior, pendant]` and `[bedroom interior, lamp A, lamp B]`. | `Dining Blended`, `Bedroom Blended` |
| 5 | Captions + panel colour | Percent and date window (with the year) read from `calendar_config.json` (see below). Then one Claude Sonnet 5 vision call over the two room blends suggests the panel's hex colour (see below). | `Sale Percent Left/Right`, `Sale Caption Left/Right`, `Sale Panel Color` |
| 6 | Composite | Local Pillow: blends cover-fitted into the side slots, panel in the stored colour, Poppins text. | `Sale Banner` (final), `Status = Done`, `Date and Time Generated` |

Local copies go to `output/sale_banner/` (`dining_blend_<rec>.jpg`, `bedroom_blend_<rec>.jpg`, `sale_banner_<rec>.jpg`).

## Percentages and captions (the calendar)

`HC Monthly Promotions Calendar.pdf` is one flattened page and has no caption wording or date strings, so the runtime source is its structured version, `calendar_config.json` (hand-transcribed from the PDF and also used by the monthly sale automation in `Auto Export Inventory`). A copy lives in `assets/calendar_config.json`; `PROMO_CALENDAR_PATH` overrides it. **If the promotion plan changes, update that copy.**

| Side | Event key | Percent | Caption template |
| :-- | :-- | :-- | :-- |
| Left | `ten_off_monthly` | parsed from the event name ("10% OFF ...") | `On all items from curated monthly collection on {date}` |
| Right | `fifteen_off_monthly` | parsed from the event name ("15% OFF ...") | `On all items from a curated collection on {date}` |

`{date}` is the event window for the target month, always with the year: whole-month events give `October 1-31, 2026`; events with `start_md`/`end_md` give `October 25 - November 30, 2026` or `December 12-14, 2026`, and a window that crosses New Year gives `December 25, 2026 - January 5, 2027`. The target month is the current month, or the next one from day 24 (same rule as `run_monthly_sale.py`); override with `--month` and `--year`. Code: `content_automation/promo_calendar.py`.

## Panel colour (Phase 5)

Claude Sonnet 5 receives `Dining Blended` and `Bedroom Blended` and is asked for ONE `#RRGGBB` that goes with both photos, looks like a bold festive sale banner and keeps white text readable. The reply is parsed for the first hex code and saved in `Sale Panel Color`.

- **Contrast guard:** if white text on the colour is below 4.5:1 (WCAG AA), the colour is darkened in small steps, keeping its hue, until it passes.
- **Fallback:** an API error, a missing blend or two replies without a hex code use the sample's red `#FF3131`; the run never fails because of the colour.
- **Override:** `--panel-color "#0B3D2E"` skips Claude and uses that colour as given (a warning is printed if it is low-contrast). To change the colour of an existing banner, edit `Sale Panel Color` in Airtable and run `--only-phase 6`, or re-roll Claude's suggestion with `--only-phase 5` then `--only-phase 6`.

## Layout spec (Phase 6)

Fitted numerically to the reference sample (`content_automation/overlay.py`, `draw_sale_banner`). Canvas 1800 x 600; panel columns 483-1316 (the two edge columns are a 50% mix of panel and photo, like the sample), red `(255, 49, 49)` in the sample and `Sale Panel Color` in a run; photos in columns 0-482 and 1317-1799, cover-fitted. All text is white Poppins, tracking about -0.09 em.

| Element | Font | Canva size (px) | Notes |
| :-- | :-- | :-- | :-- |
| `Limited -Time Offer` | Medium | 60.9 pt (81.2 px) | baseline y=117; text is exactly as in the sample; ink centred on x=909.5 |
| `SALE` | Medium | 168 pt (224 px) | baseline y=299; ink centred on x=900.5 |
| Big number (`10`, `15`) | Medium | 141 pt (188 px) | baseline y=493; digits use -0.09 em (the sample's `XX` was fitted at -0.17 em because the X glyphs overlap) |
| `%` (over `OFF`) | Regular | 50.5 pt (67.3 px) | superscript, baseline y=401 |
| `OFF` | Regular | 51.3 pt (68.4 px) | baseline y=462 |
| `UP TO` | Regular | 26.7 pt (35.6 px) | rotated 90 degrees counter-clockwise, ink bottom y=408 |
| Captions | Regular | 17.8 px | centred under each block, greedy wrap at 290 px (reproduces the sample's line breaks), baseline pitch 20.6 px |

Font sizes are the values shown in Canva, in points; the code converts them with 1 pt = 4/3 px (`SALE_PT_TO_PX`, `SALE_*_PT` in `overlay.py`). Change a size there and the headline, `SALE` and the percent blocks re-centre themselves on their anchors.

The two percent blocks use one shared geometry (the sample's right block sits a few pixels off the left one; here they are aligned) and each block is centred on its slot (x 709.5 and 1092.5).

## Configuration

| Key | Purpose |
| :-- | :-- |
| `AIRTABLE_TABLE_ID_SALE_BANNER` | Optional. Default: `AIRTABLE_TABLE_ID_CHRISTMAS_BANNER`, then `tblgNk1Tp6qKUcduw`. |
| `KREA_MOODBOARD_ID_SALE_BANNER_DINING` / `_BEDROOM` | Krea moodboards (defaults in `.env.example`). There are no Studio pencils for these. |
| `SALE_BANNER_DINING_PROMPT` / `SALE_BANNER_BEDROOM_PROMPT` | Krea prompts. |
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
python generate_sale_banner_pipeline.py --dining-moodboard-id <id> --bedroom-prompt "<prompt>"
```

`--only-phase N` runs that phase alone and prints a note about which outputs are now stale (for example after `--only-phase 4`, run `--only-phase 6` to rebuild `Sale Banner`). It needs `--record-id` and cannot be combined with `--from-phase` or `--text-only`. On any exception the row is set to `For Manual`.
