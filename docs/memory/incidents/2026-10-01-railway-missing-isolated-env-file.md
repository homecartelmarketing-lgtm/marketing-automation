# Railway: "Missing isolated configuration: /app/.env.tips-edu-story"

**Symptom:** Tips & Edu Story (and Day & Night Reel) failed on Railway with `Missing isolated configuration ... Copy the matching .example file first.`

**Root cause:** `content_automation/isolated_config.py` only read dotenv files (`.env.<automation>`, then `.env`). Both are gitignored and absent from the Docker image; Railway provides configuration as environment variables. It worked locally only because the shared `.env` exists.

**Fix:** when no dotenv file exists, the loader reads the process environment (same required keys; `AKENEO_STYLE` defaults to `modern`). Files still take precedence locally. Covered by `tests/test_isolated_config.py`.

**If it still fails on Railway:** the error now lists the missing variables; add them in the Railway service Variables (not in git).
