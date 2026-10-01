# Studio run used the literal prompt "None" (Tips & Edu Story, Pendant)

**Symptom:** Tips & Edu Story from the Control UI logged `Interior Prompt: None` and Phase 2 sent `Prompt: "None"` to Krea.

**Root cause:** `queue_manager._dispatch_job_run` POSTed `"moodboard_id": null, "prompt": null` to the pipeline's run route whenever the job had no override. Routes do `str(payload.get("moodboard_id", ""))`, which turns JSON null into the string `"None"`, treat it as a custom override, and `save_config_override` wrote it into `.env` (`KREA_MOODBOARD_ID_PENDANT_LIGHTS_TIPS_EDU_STORY='None'`, `TIPS_EDU_PROMPT_PENDANT_LIGHTS='None'`) and `output/config_overrides.json`, shadowing the real defaults on every later run.

**Fix:** the queue omits null overrides from the dispatch body; `save_config_override` ignores `None`/`null`/`undefined` values; the two poisoned keys were removed from `.env` and `config_overrides.json`.

**Check next time:** if a Studio run shows `None` for a moodboard or prompt, grep `.env` and `output/config_overrides.json` for `='None'`. Other routes still use the `str(payload.get(...))` pattern, so the queue-side fix is what protects them.
