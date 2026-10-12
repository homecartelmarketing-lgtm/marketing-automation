# This Mood Every Night Reel: AkeneoClient Missing Arguments TypeError

**Symptom:**
Pipeline failed during execution with:
`Pipeline Error: TypeError: AkeneoClient.__init__() missing 5 required positional arguments: 'host', 'client_id', 'secret', 'username', and 'password'`

**Root Cause:**
In `generate_this_mood_every_night_reel_pipeline.py`, the `Clients` container was written without passing `Settings` to client initializers. Calling `clients.akeneo()` called `AkeneoClient()` with zero positional arguments, whereas `AkeneoClient.__init__` requires `host`, `client_id`, `secret`, `username`, and `password`. Similarly, `clients.krea()` was calling `KreaClient()` with zero arguments (missing required `token`), and `clients.fal()` was created without `api_key`. In addition, downstream phases called unbacked method names (`akeneo.fetch_products_by_category`, `fal.describe_image`, `fal.edit_image`, `fal.kling_image_to_video`, `clients.airtable.upload_attachment_url`).

**How It Was Diagnosed:**
1. Inspected line 270 of [generate_this_mood_every_night_reel_pipeline.py](file:///c:/Users/User/Desktop/marketing-automation/generate_this_mood_every_night_reel_pipeline.py), confirming `self._akeneo = AkeneoClient()`.
2. Verified against [content_automation/akeneo_client.py](file:///c:/Users/User/Desktop/marketing-automation/content_automation/akeneo_client.py) and working multi-room reel implementations ([generate_house_tour_reel_pipeline.py](file:///c:/Users/User/Desktop/marketing-automation/generate_house_tour_reel_pipeline.py)).
3. Checked past incident note [[2026-09-30-sketch-to-real-studio-ran-stale-script-copy]] on invented client method signatures.

**Fix:**
1. Updated `Clients.__init__` in [generate_this_mood_every_night_reel_pipeline.py](file:///c:/Users/User/Desktop/marketing-automation/generate_this_mood_every_night_reel_pipeline.py) to accept and store `Settings` (or fallback to `load_settings()`), passing all credentials (`akeneo_host`, `akeneo_client_id`, `akeneo_secret`, `akeneo_username`, `akeneo_password`, `channel_name`) into `AkeneoClient`, `token` into `KreaClient`, and `fal_key` into `FalClient`.
2. Replaced `fetch_products_by_category` in Phase 1 with `categories.akeneo_category_code` + `akeneo.fetch_products(query)` + `select_new_products` + Shopify live catalog verification.
3. Added `upload_attachment_url` to [content_automation/scraping/airtable.py](file:///c:/Users/User/Desktop/marketing-automation/content_automation/scraping/airtable.py).
4. Wired real Fal AI endpoints: `fal.analyze_image` for Claude Sonnet 5 vision, `fal.generate(model="fal-ai/nano-banana-pro/edit")` for Nano Banana Pro blending, and `fal.generate_kling_video` for Kling motion clips.
5. Added unit regression test in [tests/test_this_mood_every_night_pipeline.py](file:///c:/Users/User/Desktop/marketing-automation/tests/test_this_mood_every_night_pipeline.py).
