# Remaining Work Checklist (post-audit follow-ups)

**Created:** 2026-10-04
**Source:** [`WORKSPACE_AUDIT.md`](WORKSPACE_AUDIT.md) (steps 1-12 done) + Phase 1 cleanup PR #4 (merged as `a4536a3`).
**How to use:** work top to bottom. Tick a box only after it is merged to `main` and verified. Each phase = its own PR.

---

## 0. Verify the PR #4 Railway deploy (do this first)

PR #4 changed docs + `requirements.txt` (`ultralytics>=8.3.0,<9`). Railway rebuilt from `main`.

- [ ] Railway build finished with no errors (check the build log for the `pip install -r requirements.txt` step)
- [ ] Studio loads on the Railway URL (port `5200` service is up, no white screen)
- [ ] Run **one** small pipeline end-to-end from the Studio (e.g. one Ad Cover fixture) and confirm the row reaches `Done`
- [ ] YOLO item tagging still works (any pipeline that stamps the item-name tag) - this is the only thing the ultralytics pin can affect
- [ ] If anything broke: revert `a4536a3` and note it in `docs/memory/incidents/`

---

## 1. Phase 1 leftover (needs a decision)

- [ ] **`docs/.obsidian/`** is still tracked in git.
  - If the Obsidian vault is NOT used: `git rm -r --cached docs/.obsidian` and add `docs/.obsidian/` to `.gitignore`.
  - If it IS used: leave it, and add one line to `docs/README.md` saying it is intentional.
- [ ] **Zoho Catalyst configs** (`app-config.json`, `catalyst.json`) - now documented in README. If Catalyst is never going to be used, delete both and remove the README rows.

---

## 2. Phase 2 - Tidy-up

### 2.1 Turn TODO/FIXME comments into GitHub issues

- [ ] Scan all root generators for `TODO` / `FIXME` (audit counted ~20)
- [ ] Priority files: `generate_christmas_banner_pipeline.py` (4), `generate_sale_banner_pipeline.py` (4)
- [ ] One GitHub issue per real item (title, file + line, what to do). Label `tech-debt`
- [ ] Delete TODOs that are stale or already fixed
- [ ] Replace kept TODOs in code with `# TODO(#<issue>)` so they link to the issue

### 2.2 Split `AGENTS.md` (52 KB, single file)

- [ ] Create `docs/agents/` with sections (suggested): `architecture.md`, `airtable-schema.md`, `foreign-keys.md`, `status-badges.md`, `pillow-rendering.md`, `structure-map.md`
- [ ] Keep root `AGENTS.md` as a short index + the mandatory rules, linking to each section
- [ ] Update the "docs to update when you change X" checklist and any links in README / `docs/README.md`
- [ ] Make sure the structure map (audit §3) is current: `docs/banners/`, `templates/`, `tools/`, `archive/`, the two isolated `.env.*.example` files, real root script count

---

## 3. Phase 3 - Structural refactor (OPTIONAL, audit step 13)

Do this only in a quiet week with no new pipelines shipping. Own branch, many small PRs.

- [ ] **Baseline:** `tests.yml` green on `main` before starting
- [ ] **Registry first:** add `content_automation/pipeline_registry.py` (pipeline key -> module/script path). Point all `UI Control/routes/*.py` at the registry **while files are still at the root**. Ship + verify on Railway.
- [ ] Move generators one family at a time, smallest first, leaving a thin shim at the old root path:
  - [ ] `pipelines/banners/`
  - [ ] `pipelines/ads/`
  - [ ] `pipelines/stories/`
  - [ ] `pipelines/feeds/`
  - [ ] `pipelines/reels/`
- [ ] After each family: tests green, one Studio run of that family, Railway deploy OK
- [ ] Move `run_*.py` / `scrape_*.py` into `runners/` the same way
- [ ] Update Dockerfile, README commands, AGENTS.md structure map, `docs/GIT_PUSH_AND_DEPLOY.md`
- [ ] After 1 stable week: delete the root shims
- [ ] Optional: rename `UI Control/` -> `studio/` (no space in path)

---

## Done (for reference)

- [x] Audit steps 1-12 (see `WORKSPACE_AUDIT.md` §5)
- [x] README: Banners section in docs index (PR #4)
- [x] README: Reel = 8 subtabs, Banner tab = one "Banner Set" sub-tab (PR #4)
- [x] README: root config files table (PR #4)
- [x] `requirements.txt`: `ultralytics>=8.3.0,<9` (PR #4)
