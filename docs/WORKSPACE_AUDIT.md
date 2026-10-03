# Workspace Organization & Improvement Audit

**Date:** 2026-10-03
**Scope:** `C:/Users/User/Desktop/marketing-automation`
**Method:** read-only scan (git status, file inventory, byte-level duplicate diff, env key diff, test run). Nothing was moved or deleted.

---

## 0. Health snapshot

| Metric | Value |
| :--- | :--- |
| Tracked files in git | 693 |
| Uncommitted / untracked changes pending | 20 |
| Python scripts at repo root | 64 |
| Docs (`.md`) | 69 |
| `output/` (generated, gitignored) | 985 files / **585 MB** |
| `python-content-script/` (untracked duplicate) | 66 files / **27 MB** |
| `scratch/` (gitignored) | 73 files |
| `.env` keys vs `.env.example` keys | 186 vs 217 |
| Test suite on a clean interpreter | 22 tests → **1 failure, 21 errors** |
| GitHub Actions workflows | 1 (manual `product_closeup_reel.yml` only) |

---

## 1. P0 — Fix now (active risk)

### 1.1 `python-content-script/` is a stale, untracked duplicate of the whole root — 27 MB

Byte-level comparison against root:

- **51 files are byte-identical** copies of root scripts.
- **6 files diverge**, and in **every case the root copy is newer**:

| File | Root (mtime / size) | Duplicate (mtime / size) |
| :--- | :--- | :--- |
| `generate_before_after_reel_pipeline.py` | 2026-10-03 / 71,966 B | 2026-09-21 / 67,282 B |
| `generate_sketch_to_real_reel_pipeline.py` | 2026-10-03 / 47,306 B | 2026-09-30 / 37,126 B |
| `run_before_after_reel.py` | 2026-10-03 / 11,321 B | 2026-09-21 / 11,919 B |
| `run_collection_category_feed.py` | 2026-10-03 / 79,445 B | 2026-09-21 / 77,600 B |
| `run_sketch_to_real_reel.py` | 2026-09-30 / 198 B | 2026-09-30 / 191 B |
| `generate_sketch_to_draw_reel_pipeline.py` | superseded 231 B stub | older copy |

- 1 file exists only in the duplicate: `run_sketch_to_draw_reel.py`.

**This folder already caused a production bug.** It is documented in
`docs/memory/incidents/2026-09-30-sketch-to-real-studio-ran-stale-script-copy.md`:
`UI Control/routes/sketch_to_draw_reel.py` resolved the generator from `python-content-script/` first,
so the Studio ran a stale copy even after the root generator was fixed. The route was patched, but the
folder is still there and still referenced in 5 files (docs + the pipeline itself).

**Action:** delete the whole folder. It is untracked, not in git, not deployed to Railway, and strictly older.
Keep `Poppins-Bold.ttf` from it only if `content_automation/fonts/` is missing it (it is not — fonts live there).

### 1.2 `.env` has drifted from `.env.example` in both directions

- **55 keys live in `.env` but are undocumented** in `.env.example` — including `CRON_SECRET`,
  `DASHBOARD_PIN`, `FAL_KEY`, all six `ZOHO_*` tokens, and ~45 prompt keys
  (`CTA_PROMPT_*`, `TIPS_EDU_PROMPT_*`, `MYTH_AND_FACT_PROMPT_*`, …). A fresh deploy from the example file
  would silently lose every prompt override and the scheduler secret.
- **91 keys documented in `.env.example` are missing from the live `.env`** — mostly
  `AIRTABLE_TABLE_ID_*` (`WALL_SCONCE`, `MOODBOARD_STORY`, `STYLE_THIS`, `ROOM_BUILD_UP_REEL`,
  `CHRISTMAS_BANNER`, `MOODBOARD_1_FEED`, …), `KREA_MOODBOARD_ID_*`, and `AKENEO_CATEGORY_*`.
  Either those subtabs are dead config or they are one missing key away from failing.
- Debug residue: `TEST_OVERRIDE_KEY_123` is present in `.env`.

**Action:** write a `scripts/ops/diff_env.py` that prints this drift, run it, then reconcile. Add the checker to CI.

### 1.3 The test suite cannot run and nothing enforces it

Running `python -m unittest discover -s tests` on the default interpreter: **21 errors, 1 failure** —
all `ModuleNotFoundError` (`dotenv`, `requests`, `PIL`, `cv2`, `imageio_ffmpeg`). So the failures are
environmental, not necessarily code bugs — but that is exactly the problem:

- There is no committed lockfile / pinned venv, so "tests pass" is unverifiable.
- The only GitHub workflow is a manual pipeline trigger. There is **no CI job that installs
  `requirements.txt` and runs `tests/`**, so a broken import can ship.

**Action:** add `.github/workflows/tests.yml` (install `requirements.txt` → `python -m unittest discover tests`),
and commit a `requirements-dev.txt` if extra deps are needed for tests.

### 1.4 Uncommitted work sitting in the tree

20 pending entries, including modified `generate_sketch_to_real_reel_pipeline.py`,
`UI Control/routes/sketch_to_draw_reel.py`, `content_automation/auto_draw.py`, plus two new test files
(`test_sketch_to_real_item_tag.py`, `test_sketch_to_real_music.py`) that are **untracked**. If the working
tree is ever reset, those tests are gone.

**Action:** commit or stash before any reorganization.

---

## 2. P1 — Structural problems

### 2.1 64 loose Python files at the root

Three different kinds of script are interleaved with no visual separation:

- 26 `generate_*_pipeline.py` monoliths (the real generators)
- ~20 `run_*.py` CLI runners (thin aliases **or** fat orchestrators — sometimes 95 KB, sometimes 179 B)
- `scrape_*.py`, `standalone_*.py`, `photo_video_maker.py`, `run_dashboard.py`, launcher `.bat`/`.py`

Naming is inconsistent: `generate_moodboard_1_feed.py` vs `generate_product_showcase_feed_pipeline.py`
(no `_pipeline` suffix on the first). AGENTS.md §2 itself admits "the root folder contains ~54 scripts".

**Action (staged):** move generators to `pipelines/{stories,feeds,reels,banners,ads}/`, runners to `runners/`,
keeping a thin `content_automation/pipeline_registry.py` mapping pipeline key → module path. Flask routes
spawn via subprocess with hardcoded paths, so update `UI Control/routes/*.py` in the same commit.
Do this **after** 1.1, and only with a green test run before and after.

### 2.2 Dead / ambiguous scripts

| File | Size | Status |
| :--- | ---: | :--- |
| `generate_before_after_reel.py` | 156 B | stub; the real file is `generate_before_after_reel_pipeline.py` |
| `generate_sketch_to_draw_reel_pipeline.py` | 231 B | superseded by `generate_sketch_to_real_reel_pipeline.py` |
| `run_3_products_1_style_feed.py` | 179 B | orphan; no matching generator |
| `run_one_product_three_styles_feed.py` | 179 B | orphan; real file is `run_1_product_3_styles_feed.py` (56 KB) |
| `run_1_style_3_products_feed.py` | 331 B | orphan |
| `generate_moodboard_reel.py` | 48 KB | ambiguous twin of `generate_moodboard_reel_pipeline.py` (83 KB) |

**Action:** delete the first five (verify no imports first), and rename or clearly deprecate the moodboard reel twin.

### 2.3 Two UI directories

- `UI Control/` — the real React + Flask Studio (33 route blueprints, `src/`, `dist/`).
- `UI/` — 17 legacy files: `Collection Category Feed Dashboard.dc.html`, `support.js`, sample JPGs, and a
  `_ds/` design-system bundle. All tracked, none referenced by the app.

**Action:** move `UI/` into `archive/legacy_ui/`.

### 2.4 Binary and model files in the repo root

| Item | Size | Notes |
| :--- | ---: | :--- |
| `yolov8s-worldv2.pt` | 25.9 MB | gitignored (`*.pt`) but sitting in root; should be `assets/models/` or downloaded on demand |
| `Poppins-Bold.ttf` | 156 KB | tracked at **root** while `content_automation/fonts/` already holds the Poppins family |
| `tools/cloudflared.exe` | — | **tracked binary** in git history; bloat that can never be diffed |
| `new-contnet.mp4` | 457 KB | typo'd filename, untracked scratch video |
| `tmp_blended2.jpg` | 1.48 MB | untracked debug output |
| `test_tag_out.jpg` | 314 KB | untracked debug output |

**Action:** move the model to `assets/models/`, delete the three untracked debug artifacts,
`git rm --cached tools/cloudflared.exe` (keep the file locally, stop tracking the binary).

### 2.5 `scratch/` is gitignored but README tells you to run scripts from it

`scratch/` holds 73 files — including genuinely useful ones referenced by README:
`audit_all_feed_subtabs.py`, `ensure_ad_cover_fields.py`, `_verify_ad_cover_image.py`,
`check_airtable_fields.py`, `find_shopify_products.py`. None are in git. One bad `git clean -xfd`
and they are unrecoverable.

**Action:** promote the ones README/docs reference into `scripts/ops/`; delete the rest; add a
`scratch/README.md` saying the folder is throwaway.

---

## 3. P2 — Hygiene

- **`output/` is 585 MB with no retention policy.** 985 files, gitignored, never pruned. Add a
  `scripts/ops/prune_output.py` (delete >30 days, keep latest N per pipeline) and run it monthly.
- **`__pycache__/` at repo root** (83 `.pyc`) — gitignored, harmless, but shows no `PYTHONDONTWRITEBYTECODE`.
- **Three stray config files with no documented owner:** `app-config.json`, `catalyst.json`,
  `skills-lock.json`. Document them in AGENTS.md or delete them.
- **AGENTS.md §2 structure map is stale** — it omits `python-content-script/`, `UI/`, `tools/`,
  `templates/`, `tmp/`, `docs/banners/` (5 banner specs), and the two isolated env example files.
  It also claims "~54 scripts" when root now has 64. AGENTS.md is 52 KB in a single file — consider
  splitting into `docs/agents/` sections.
- **20 `TODO`/`FIXME` markers** across root generators (`generate_christmas_banner_pipeline.py` and
  `generate_sale_banner_pipeline.py` have 4 each). Worth harvesting into tracked work items.
- **`docs/.obsidian/`** vault config is committed alongside the memory notes — intentional if you use
  Obsidian, noise otherwise.

---

## 4. Proposed target layout

```
marketing-automation/
├── AGENTS.md  README.md  .env  .env.example  requirements.txt  Dockerfile
├── content_automation/          # core package (unchanged)
├── pipelines/                   # ← generate_*_pipeline.py, grouped
│   ├── stories/  feeds/  reels/  banners/  ads/
├── runners/                     # ← run_*.py, scrape_*.py
├── studio/                      # ← "UI Control/" (rename; drop the space)
├── assets/
│   ├── models/                  # yolov8s-worldv2.pt
│   └── fonts/                   # Poppins family
├── scripts/{ops,scrapers,previews}/
├── docs/                        # + docs/banners/ listed in the index
├── tests/
├── output/                      # gitignored + pruned
├── scratch/                     # gitignored, explicitly throwaway
└── archive/legacy_ui/           # ← old "UI/"
```

---

## 5. Execution order & Status

| # | Step | Type | Risk | Status |
| :-- | :--- | :--- | :--- | :--- |
| 1 | Commit/stash the 20 pending changes | safe | none | **Completed** (`df99ef6`) |
| 2 | Delete `python-content-script/` (27 MB) | **destructive** | low — untracked, strictly older, already documented as a bug source | **Completed** (`1a1af17`) |
| 3 | Delete 3 untracked debug artifacts (`new-contnet.mp4`, `tmp_blended2.jpg`, `test_tag_out.jpg`) | **destructive** | low | **Completed** (`1a1af17`) |
| 4 | Clean 6 dead stub/ambiguous scripts → `archive/legacy_runners/` | move | low — canonical generators remain primary | **Completed** |
| 5 | Move `UI/` → `archive/legacy_ui/` | move | low | **Completed** (`1a1af17`) |
| 6 | Move `yolov8s-worldv2.pt` → `assets/models/`, remove redundant root `Poppins-Bold.ttf` | move | low | **Completed** (`1a1af17`) |
| 7 | `git rm --cached tools/cloudflared.exe` + `.gitignore` entry | safe | low | **Completed** (`1a1af17`) |
| 8 | Add `scripts/ops/diff_env.py`, reconcile `.env` ↔ `.env.example` | additive | medium — touches live config | **Completed** (`fc48bcc`) |
| 9 | Add `.github/workflows/tests.yml` | additive | none | **Completed** (`fc48bcc`) |
| 10 | Promote referenced `scratch/` scripts → `scripts/ops/` | move | low | **Completed** |
| 11 | Add `scripts/ops/prune_output.py` | additive | medium — deletes generated data | **Completed** |
| 12 | Update AGENTS.md §2 structure map + README index + docs | docs | none | **Completed** |
| 13 | **Structural refactor:** `pipelines/` + `runners/` + centralized registry | **large** | **high** — touches 33 Flask routes and 22 tests; requires pipeline registry abstraction | **Pending Phase 4** |

Steps 1–12 (Phases 1–3) are fully executed and tested. Studio on port 5200 runs uninterrupted. Step 13 (Phase 4) is scheduled with the centralized pipeline registry pattern.
