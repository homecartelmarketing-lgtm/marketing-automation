# Banner Set (Christmas banner + Sale banner + third banner, one row)

One run makes **all three banners on ONE Airtable row**: the main banner ([`CHRISTMAS_BANNER.md`](CHRISTMAS_BANNER.md), 21:9), the second banner ([`SALE_BANNER.md`](SALE_BANNER.md), 1800 x 600) and the third banner ([`THIRD_BANNER.md`](THIRD_BANNER.md), 1800 x 600, panel in the Sale colour). Nothing adds a second row for the Sale or the third banner.

- **Script:** `generate_banner_set_pipeline.py` (imports the three banner scripts and runs their phase functions on the same record).
- **Studio:** the **Banner** tab has one sub-tab, "Banner Set" (`/api/christmas-banner/*`, `UI Control/routes/christmas_banner.py`). One Run makes all three banners (15 phases). The old separate Sale Banner sub-tab is gone because its run would have created a second row; `/api/sale-banner/*` and `generate_sale_banner_pipeline.py` still exist for CLI re-runs.
- **Airtable:** table `tblgNk1Tp6qKUcduw`, `Category = Christmas Banner`, Foreign Key `XMS-BANNER-ALL-<ID>`. The row holds `Banner with Text` (Christmas), `Sale Banner` (Sale) and `Third Banner`.

## Phases

| # | Banner | What happens |
| :-- | :-- | :-- |
| 1 | all | Akeneo scrape of **10 different products** (Shopify-active, base-wide dedup, each pick is added to the dedup set before the next): chandelier `CH`, pendant `PE`, floor lamp `FL`, table lamp `TL`, wall light `WL` for the Christmas banner; three pendants `DP` (dining table), `KA` and `KB` (kitchen island) for the Sale banner; two table lamps `BA` and `BB` (bedside tables) for the third banner. One new row, 10 cutouts in `Furniture Item`. Nothing is written if any product is missing. |
| 2-6 | Christmas | Krea living room, Claude blending prompt, Nano Banana Pro 21:9 blend, Claude title + subtitle, local Pillow overlay. Phase 6 sets `Status = Christmas Banner Done` (not `Done`). |
| 7-11 | Sale | The Sale banner's own phases 2-6 (they print `[PHASE 2]` to `[PHASE 6]` again; the Studio shows them as 7-11): Krea dining room + kitchen, Claude blending prompts, Nano Banana Pro room blends, calendar captions + Claude panel colour, local Pillow composite. The composite sets `Status = Sale Banner Done`. |
| 12-15 | Third | The third banner's phases 2-5 (printed as `[PHASE 2]` to `[PHASE 5]`; the Studio shows 12-15): Krea modern Christmas bedroom, Claude blending prompt (2 table lamps), Nano Banana Pro blend, local Pillow composite with the Sale colour panel. The composite writes `Status = Done` and `Date and Time Generated`. |

On any error the row becomes `For Manual`.

## Why the codes differ

`Furniture Item` attachments are named `<CODE>_<sku>_<media>.png`, and each banner picks its cutouts by code. The Sale banner's dining pendant is `DP`, not `PE`, so it can never be mistaken for the Christmas banner's pendant in the same row; the third banner's lamps are `BA` and `BB`. The Christmas copy prompt (Phase 5) only lists the Christmas codes, so the other banners' products are not mentioned in the title/subtitle prompt.

## Krea prompts, the panel colour and the third banner

- Interior prompts are short on purpose; the moodboard carries the look (Christmas living room: moodboard `b5ffdcbb-...` and the Studio pencil; Sale dining room: `de5f4ff8-...`; Sale kitchen: the dining moodboard until `KREA_MOODBOARD_ID_SALE_BANNER_KITCHEN` is set; third banner bedroom: `KREA_MOODBOARD_ID_THIRD_BANNER`, default the Sale banner's old bedroom moodboard). Overrides: `SALE_BANNER_DINING_PROMPT`, `SALE_BANNER_KITCHEN_PROMPT`, `THIRD_BANNER_PROMPT`, or the CLI flags below.
- The Sale panel colour is chosen by Claude (Sonnet 5 vision through fal.ai) from the two Sale room photos. The prompt allows any hue and tells Claude not to default to red, so the colour changes with the photos; white text stays readable (contrast >= 4.5:1).
- The third banner reads that colour back from the row (`Sale Panel Color`) and paints its 951 px panel with it, so the second and third banners always match.

## CLI

```bash
python generate_banner_set_pipeline.py
python generate_banner_set_pipeline.py --month 11 --year 2026 --panel-color "#0B3D2E"
python generate_banner_set_pipeline.py --moodboard-id <id> --interior-prompt "<christmas living room prompt>"
python generate_banner_set_pipeline.py --dining-moodboard-id <id> --kitchen-moodboard-id <id> --kitchen-prompt "<prompt>"
python generate_banner_set_pipeline.py --third-moodboard-id <id> --third-title "Holiday Collection" --third-subtitle "Order today"
```

To redo one banner on a row this pipeline made, use its own script with `--record-id` (never another row): `generate_christmas_banner_pipeline.py --record-id <rec> --from-phase N`, `generate_sale_banner_pipeline.py --record-id <rec> --from-phase N` or `generate_third_banner_pipeline.py --record-id <rec> --from-phase N`. The Christmas and Sale scripts run without `--record-id` create their own separate row, as before; the third banner script refuses to run without it.

## Tests

`python -m unittest discover -s tests -p "test_banner_set.py"` (one row, ten cutouts, three banners in order on the same record, only the third banner writes `Done`, failure marks `For Manual`, the Studio route and its phase mapping).
