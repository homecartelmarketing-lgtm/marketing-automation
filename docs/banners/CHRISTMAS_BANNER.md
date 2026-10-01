# Christmas Banner (21:9)

One run scrapes a fresh Akeneo item of **each** fixture type, generates a modern Christmas living room in Krea, and blends all five fixtures into it with Nano Banana Pro as a single **21:9** banner. Claude Sonnet 5 then writes a title + subtitle and a local Pillow phase stamps them on the banner (Poppins only, white text with a soft shadow).

- **Script:** `generate_christmas_banner_pipeline.py`
- **Studio:** standalone top-level **Banner** tab, `/api/christmas-banner/*` (`UI Control/routes/christmas_banner.py`)
- **Airtable table:** `tblgNk1Tp6qKUcduw` (default; `AIRTABLE_TABLE_ID_CHRISTMAS_BANNER` overrides it), foreign key prefix `XMS-BANNER-ALL`. Missing columns are created on the first run, including `Status`, `Foreign Key ID` and `Date and Time Generated`. The table's `ID` must be an autoNumber (the pipeline never writes it); `Foreign Key ID` is filled from it.

## Phases

| # | Phase | Detail | Airtable |
| :-- | :-- | :-- | :-- |
| 1 | Akeneo scrape | 1 newest eligible item each for `chandeliers`, `pendant_lights`, `floor_lamps`, `table_lamps`, `wall_lights` (style `modern`). Base-wide dedup + Shopify active check. Nothing is written if any of the 5 types has no eligible item. | New row; `Furniture Item` (5 cutouts, order CH, PE, FL, TL, WL), `SKU`, `Item Name` and `Item Details` (one `CODE: value` line per fixture; `Item Details` is the cleaned Akeneo description, max 300 characters, e.g. dimensions and materials) |
| 2 | Krea interior | `krea-2/medium`, **2.35:1** (Krea does not accept 21:9; 2.35:1 is its widest documented ratio, 1K only), moodboard `b5ffdcbb-192e-4528-8d86-d1a4cf496887`, modern Christmas living room prompt. Any non-moodboard rejection retries at 16:9. Phase 4 extends the room to 21:9. | `Room Interior`, `Interior Prompt` |
| 3 | Claude vision | Gets the interior, the 5 cutouts, each item's name, mounting type and `Item Details`, and works in three stages: (A) study the actual room (layout, ceiling, existing fixtures, light), (B) study each item (form, materials, mounting, glow, real size), (C) place every item at a landmark in *this* room and write one detailed paragraph per `Image 2..6`. The reply is validated (at least 1200 characters, mentions every Image 2..6, no fences or preamble); it is retried once with the reason, then falls back to a fixed prompt. | `Blending Prompt` |
| 4 | Nano Banana Pro | `fal-ai/nano-banana-pro/edit`, `image_urls = [interior, CH, PE, FL, TL, WL]`, `aspect_ratio="21:9"`, resolution `2K`, `output_format="jpeg"`. | `Blended Banner` (text-free) |
| 5 | Claude copy | Claude Sonnet 5 looks at the blended banner and returns JSON `{title, subtitle}` (title 2-4 words, at most 22 characters; subtitle at most 36). Falls back to "Light Up Your Christmas" / "Statement lighting for festive homes" on failure. | `Banner Title`, `Banner Subtitle` |
| 6 | Pillow overlay | Local, zero API cost. See the text spec below. | `Banner with Text` (final), `Status = Done`, `Date and Time Generated` |

Local copies: `output/christmas_banner/christmas_banner_<record>.jpg` (text-free) and `christmas_banner_text_<record>.jpg` (final). On any exception the row is set to `For Manual`.

## Text spec (Phase 6)

Matched to the Canva reference sample (1800 x 600 px, orange background, "Auto Generated Title / Subtitle"). Positions are measured on that **1800 x 600 px** design canvas (`BannerTextBox` in `content_automation/overlay.py`); font sizes are Canva points (1 pt = 4/3 px).

| | Title | Subtitle |
| :-- | :-- | :-- |
| Font | Poppins **Medium** (`Poppins-Medium.ttf`), 81.8 pt = 109 px | Poppins **Regular**, 46.3 pt = 62 px |
| Colour | white | white |
| Letter spacing | about -0.092 em | about -0.098 em |
| Effect | soft dark drop shadow, intensity 100 | same shadow, scaled to the font size |
| x / y | 60 / 340.7 | 60 / 457.9 |
| Box (w x h) | 1053.6 x 130.9 | 999.5 x 73.4 |

- **Why Medium, not Bold:** the reference title's stems are 11-12 px thick at 109 px; Poppins Bold would be 18-19 px and Medium is 11-12 px. The overlay code falls back to Bold only if `Poppins-Medium.ttf` is missing.
- **Shadow:** black, blur (sigma) 0.145 em, offset 0.04 em down, peak opacity 0.56, fitted numerically to the sample. There is no colour glow.
- **Mapping to the 21:9 banner:** the banner is 21:9, not 3:1, so `x`, box width and font size scale by `image_width / 1800`, while `y` and box height scale by `image_height / 600`. The text keeps its relative place in the frame; nothing is cropped.
- Each text is one line, vertically centred in its box, left-aligned at `x`, and shrinks (to no less than 60% of its size) to fit the box width.
- The Phase 3 blending prompt asks for the floor lamp, table lamp and wall light to sit in the right 40% of the frame so the lower-left stays clear for the text.

## Configuration

| Key | Purpose |
| :-- | :-- |
| `AIRTABLE_TABLE_ID_CHRISTMAS_BANNER` | Required. Banner table ID. |
| `KREA_MOODBOARD_ID_CHRISTMAS_BANNER` | Krea moodboard (default `b5ffdcbb-...`). Studio pencil writes this key. |
| `CHRISTMAS_BANNER_PROMPT` | Krea interior prompt. Studio pencil writes this key. |
| `CHRISTMAS_BANNER_RESOLUTION` | `1K`, `2K` (default) or `4K` for the blend. |
| `CLAUDE_VISION_MODEL` | Optional model override for Phases 3 and 5 (default `anthropic/claude-sonnet-5`). |
| `FAL_BLENDING_MODEL` | Optional model override for Phase 4. |

## CLI

```bash
python generate_christmas_banner_pipeline.py                       # full run, fresh row
python generate_christmas_banner_pipeline.py --record-id recXXXX   # re-run phases 2-6 on a row
python generate_christmas_banner_pipeline.py --record-id recXXXX --from-phase 3   # new Claude prompt + blend + text, same room and items (no Krea, no scrape)
python generate_christmas_banner_pipeline.py --record-id recXXXX --text-only   # = --from-phase 5: new copy + overlay only, no Krea/Nano Banana cost
python generate_christmas_banner_pipeline.py --record-id recXXXX --only-phase 4   # banner generation (Nano Banana blend) ONLY
python generate_christmas_banner_pipeline.py --record-id recXXXX --only-phase 6   # re-stamp title/subtitle only
python generate_christmas_banner_pipeline.py --moodboard-id <id> --interior-prompt "<prompt>" --style all
```

## Notes

- Because `SKU` / `Item Name` hold five values per row, the base-wide dedup in other pipelines does not see banner items as used; the banner pipeline itself parses them so each banner uses fresh items.
- The Phase 3 instruction lives in `content_automation/prompts/__init__.py::build_banner_multi_fixture_instruction`; `BANNER_MOUNT_HINTS` there are mounting facts per type, not fixed locations (Claude chooses locations from the actual room).
- `--from-phase N` (2-6) re-runs from that phase on `--record-id`, re-using the images already on the row.
- `--only-phase N` (2-6) runs just that phase and prints a note about the outputs that are now stale (for example after `--only-phase 4` run `--only-phase 6` to re-stamp `Banner with Text`). It needs `--record-id` and cannot be combined with `--from-phase` or `--text-only`.
- The Sale banner ([`SALE_BANNER.md`](SALE_BANNER.md)) shares this table; each banner's Studio counts only rows with its own `Category`.
