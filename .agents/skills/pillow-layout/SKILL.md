---
name: pillow-layout
description: Use when building or changing any Story, Feed, Reel cover, Ad Cover or Banner layout: text, logos, watermarks, pills, name tags. Covers canvas sizes, fonts, logo boxes and the local-only Pillow rule.
---

# Local Pillow Layouts

All layout composition runs locally in `content_automation/overlay.py` (plus `item_tagger.py` for YOLO name tags). This saves API cost, but mainly it keeps the output exact. When the Tips & Edu Story layout was sent to Nano Banana Pro, the model redrew the room, doubled the logo and printed prompt text into the image (`docs/memory/incidents/2026-10-01-tips-edu-story-nano-banana-layout-redrew-room.md`). Image models do blending and extensions. Pillow does every pixel of typography and branding.

## Canvas sizes

| Format | Size |
| :--- | :--- |
| Story (9:16) | 1080 x 1920 |
| Feed (4:5) | 1080 x 1350 |
| Ad Cover (1:1) | 1080 x 1080, plus its 9:16 Story twin at 1080 x 1920 (`AD_COVER_STORY_CANVAS_SIZE`) |
| Sale / third banner | 1800 x 600 |
| Christmas banner | 21:9 |

## Fonts

- Resolve fonts through `overlay.py::_resolve_font_path` from `content_automation/fonts/`: Poppins Bold, Regular and Light. ExtraBold is for the Tips & Edu title, Medium for banners. There is no `assets/fonts/`.
- Auto-scale every text block to its box, e.g. step from 48px down to 24px until it fits. Claude-written text varies in length, and an overflow ruins the post.

## Logo and watermarks

- The logo is `assets/homecartel_logo.png` (not `assets/Logo.png`). Resolve it with `find_homecartel_logo_path` or `AssetCatalog`.
- The boxes are `HOMECARTEL_LOGO_BOX` (4:5 feeds) and `HOMECARTEL_STORY_LOGO_BOX` (9:16). Story reference: 190.3 x 63.5 px at top-right X 781.7, Y 108.0 (a 108px margin).
- Watermark templates are `assets/*_layout.jpg`, resolved with `find_cta_layout_path` / `_resolve_asset_file`.
- For legibility on any room, use a soft multi-directional shadow `(0, 0, 0, 180)`.

## Coordinates

Per-format coordinates come from Canva exports in `JSON Prompts/<Format>/*.json`. Read positions from there instead of eyeballing them. When matching a Canva sample, keep the sub-pixel values.

## Checking your work

Render locally with the previewers in `scripts/previews/` before running a full pipeline. A full run creates a new Airtable row and spends Krea/Fal credits just to look at text placement. Check long and short text, and light and dark room backgrounds.
