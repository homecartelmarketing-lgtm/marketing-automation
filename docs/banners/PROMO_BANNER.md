# Promo Banner (1080 x 1920, 9:16 "Your Story")

The monthly promo ad that used to be rebuilt by hand in Canva: the HomeCartel logo, a tagline such as "Festive Glow, Festive Finds", a huge `10%OFF` / `15%OFF` and the date line, over a 9:16 version of the main (wide) banner.

- **Script:** `generate_promo_banner_pipeline.py` (CLI only; no Studio card, not part of the Banner Set).
- **Input:** the main banner as a **local file** (`--banner`). Use the text-free banner (for example `output/christmas_banner/christmas_banner_<rec>.jpg`, the "Blended Banner"): the logo and text are drawn on top, and Nano Banana Pro would extend any text already on the picture.
- **Output:** `output/promo_banner/promo_<MON-YYYY-NNOFF>_9x16.png` (for example `promo_SEP-2026-10OFF_9x16.png`) and the raw 9:16 background next to it (`..._bg.png`). A `--dry-run` is saved as `..._9x16_dryrun.png` / `..._dryrun_bg.png`, so a free layout test never overwrites a real promo or its live background.
- **Airtable:** none. No row is read or written, so the "always a brand-new row" rule does not apply.

## How it works

| # | Step | Engine |
| :-- | :-- | :-- |
| 1 | Upload the banner | `FalClient.upload_file` |
| 2 | 9:16 background | Nano Banana Pro (`fal-ai/nano-banana-pro/edit`), `aspect_ratio="9:16"`, `resolution=1K` (2K with `--resolution`), `output_format="png"`, with the outpaint prompt `PROMO_OUTPAINT_PROMPT`: keep the room and every fixture identical, extend the ceiling up and the floor down, keep the lower half calm, add no text, logo or watermark. The result is fitted to exactly 1080 x 1920 (LANCZOS). |
| 3 | Tagline | Claude Sonnet 5 through fal (`openrouter/router/vision`, `anthropic/claude-sonnet-5`, override `CLAUDE_VISION_MODEL`). The **banner's name** is the main source (the file name without extension, `_` and `-` as spaces, or `--banner-name`); the image is supporting context. 3-5 words, Title Case, plain text; cleaned (first line, no quotes, markdown or emoji, length limit). **A failed call never fails the run**: it uses `--tagline`, or else the cleaned banner name, and prints a warning. |
| 4 | Layout | Local Pillow (`overlay.py::draw_promo_banner`), zero API cost. |

`--dry-run` skips fal: the background is a centre-crop of the banner and the tagline is the cleaned banner name, so the layout can be tested for free (saved under a `_dryrun` name).

## Layout (Canva Position panel, 1080 x 1920)

Canva's Y is the top of a text box; the baseline is placed at `box_y + 0.94 x font px` (measured on the Sale banner). Canva font sizes are points, 1 pt = 4/3 px (`PROMO_FONT_PX`). All text is white and uses Canva's letter spacing **-130 = -0.13 em** (`PROMO_TRACKING_EM`): measured on the Canva screenshot, the date lines come out 682 / 698 px wide against 676 / 693 in Canva, the tagline 565 against 557, and the right edge of `OFF` at 1036 against 1033.

| Element | Font and size | Position |
| :-- | :-- | :-- |
| Logo | `assets/homecartel_logo.png`, width 890, height auto (943 x 138 becomes 890 x 130, never stretched) | x 92.6, y 1090.5 |
| Tagline | Poppins Regular 44 | centred, box y 1232.5 (shrinks only if too wide) |
| `10` / `15` | Poppins Regular 286 | box (41.9, 1229.4) |
| `%` | Poppins Regular 262, rotated -1.1 degrees | box (301.8, 1234.3) |
| `OFF` | Poppins Regular 230, rotated -1.1 degrees | box (577.4, 1262) |
| Date | **Poppins Medium** 38.7 (Canva's B toggle on Poppins renders Medium, not Bold), line spacing 0.91 (the two baselines 0.91 em apart, about 47 px), up to 2 balanced lines | centred, box y 1600.3 |

Two things in the spec were not verifiable without the Canva page, so they are single constants at the top of the Promo section of `content_automation/overlay.py` for fine-tuning: the weight of the big `10%OFF` (`PROMO_BIG_FONT`, Regular like the Sale banner's numbers) and the unit of the font sizes (`PROMO_FONT_PX`, 4/3 for points; use 1.0 if they are px). Every position (`PROMO_*_XY`, `PROMO_*_Y`) is a constant too.

## Date line

`{date}` is the month's window from the promotions calendar (`assets/calendar_config.json`, the same source as the Sale banner), with an en dash: `September 1–30, 2026`. The wording follows Canva: 10% = "On all items from curated monthly collection on {date}", 15% = "On all items from a curated collection on {date}". If a discount runs only part of the month (the Canva sample showed "August 20–31, 2026" for 15%), pass `--date-text "August 20–31, 2026"`.

## CLI

```bash
# free layout test (no fal calls)
python generate_promo_banner_pipeline.py --banner banner.jpg --discount 10 --month SEP --year 2026 --dry-run

# live (needs FAL_KEY): 1 Nano Banana Pro call + 1 Claude call
python generate_promo_banner_pipeline.py --banner "Festive Glow Banner.jpg" --discount 10 --month SEP --year 2026

# options
python generate_promo_banner_pipeline.py --banner b.jpg --discount 15 --month AUG --year 2026 \
    --banner-name "Festive Glow Banner" --tagline "Festive Glow, Festive Finds" \
    --date-text "August 20–31, 2026" --resolution 2K
```

`--month` takes `SEP`, `September` or `9`; `--discount` is 10 or 15; `--resolution` is 1K (default), 2K or 4K.

## Configuration

| Key | Purpose |
| :-- | :-- |
| `FAL_KEY` (or `FAL_API_KEY`) | Required for the live run. |
| `PROMO_BANNER_MODEL` | Background model (default `fal-ai/nano-banana-pro/edit`). |
| `PROMO_BANNER_RESOLUTION` | `1K` (default), `2K` or `4K`. |
| `CLAUDE_VISION_MODEL` | Tagline model (default `anthropic/claude-sonnet-5`). |

## Notes

- A wide banner (about 21:9) stays at the same width in the 9:16 frame, so the room fills only the middle of the picture and the model adds ceiling above and floor below. The logo and text sit over the lower half. For a tighter room, use a banner that is less wide, or `--resolution 2K` if the background looks soft.
- Check the first render against the Canva page and adjust the `PROMO_*` constants if a position is off by a few pixels.

## Tests

`python -m unittest discover -s tests -p "test_promo_banner.py"`: canvas size, the 890 x 130 logo, text blocks stacking without overlap and staying on the page, the tilt of `%` and `OFF` only, date wrapping, the calendar captions and en dash, tagline cleaning and fallbacks, the fal calls (mocked), `--dry-run` never touching fal, and the CLI limits.
