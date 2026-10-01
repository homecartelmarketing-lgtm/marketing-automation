# Sketch to Real: Studio ran a stale untracked script copy

**Symptom:** Sketch to Real Reel failed from the Control UI even after the root generator was fixed (CLI worked).

**Root cause:** `UI Control/routes/sketch_to_draw_reel.py` resolved the generator from `python-content-script/` first. That folder is an untracked, older snapshot (not in git, not on Railway) that still had the `search_products` call, bad `download_to_temp_file` calls and fake default tables.

**Fix:** the route now always runs the tracked root `generate_sketch_to_real_reel_pipeline.py`. Pendant Lights got its real table `tblSALsUd5MXXnkp6` (`STR-REEL-PE`) in the route, pipeline, fixtures, `foreign_key.py`, `.env.example` and docs.

**Lesson:** never make a Flask route prefer a script path outside tracked code; the generators were also written against invented client APIs, so verify calls against the real clients (`AkeneoClient.fetch_products`, `KreaClient.download_image`, `media.download_url_to_temp_file`).
