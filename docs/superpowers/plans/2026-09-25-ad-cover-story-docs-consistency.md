# Ad Cover 9:16 Story — Docs Consistency Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update every live markdown file in `marketing-automation` so the Ad Cover pipeline is described consistently as the 7-phase **1:1 + 9:16 Story** generator it now is.

**Architecture:** Code is already merged and verified (`generate_ad_cover_pipeline.py` Phases 1–7, `content_automation/overlay.py` story registry, `UI Control/routes/ad_cover.py` 7-phase `detect_phase`, `UI Control/src/app/App.tsx` `totalPhases: 7`, `UI Control/dist` rebuilt, Airtable columns provisioned). What is left is documentation: the pipeline spec itself is already correct, so the remaining drift is in the **cross-cutting index docs** (`AGENTS.md`, `README.md`, `docs/README.md`, `docs/UI_CONTROL_CONFIG.md`, `docs/OPERATIONS_AND_UTILITIES.md`, `docs/AUTO_POST_SCHEDULER.md`, `docs/memory/architecture/system-overview.md`) that still describe Ad Covers as a 1:1-only, 5-phase, 23-subtab world.

**Tech Stack:** Markdown only. Verification = `grep` assertions (no Python, no API calls).

**Spec:** `docs/ads/AD_COVER.md` (already updated — this is the source of truth the other files must agree with) and the approved feature plan `C:\Users\User\.qoder\plans\inner-gulf-crow.md`.

## Global Constraints

- **Repo root:** `C:/Users/User/Desktop/marketing-automation`. All paths below are relative to it. Run every command from there.
- **Never touch:** `.kilo/worktrees/**` (stale copies owned by another tool), `docs/superpowers/plans/2026-09-16-*` and `docs/superpowers/specs/2026-09-16-*` (point-in-time designs, marked reference-only in `docs/README.md`), and the legacy per-folder READMEs listed in `docs/README.md` §7 (`CTA Story/README.md`, `UI Control/README.md`, etc.).
- **Never stage** `.env`, `.env.*`, keys, or `output/`. `.env.example` IS safe to commit — it is already modified by the feature.
- **Canonical phrasing — copy verbatim wherever a task says "use CANON_x".** Mixing variants is the failure mode this plan exists to prevent:
  - `CANON_RATIO` = ``1:1 `1080 x 1080 px` + 9:16 Story `1080 x 1920 px` ``
  - `CANON_PHASES` = `7 phases`
  - `CANON_COMPLETE` = `` `Complete` is written by Phase 7 only ``
  - `CANON_FIELD_STORY_BLEND` = `` `Ad Cover Blended Image Story` `` (Phase 6 intermediate)
  - `CANON_FIELD_STORY_FINAL` = `` `Ad Cover Converted Image Story` `` (Phase 7 final deliverable)
  - `CANON_TAB` = `standalone 4th top-level Studio tab (not a sub-tab family)`
- **No new emoji or heading glyphs.** Existing emoji headings stay as-is; do not add any.
- **Commits:** one conventional-prefixed commit per task (`docs: …`) as the steps specify. If the user has not authorized committing, skip only the commit steps and leave the edits in the working tree — the grep checks still run.
- **Read-only guarantee:** this plan mutates zero code, zero Airtable rows, and calls zero paid APIs.

## File Structure

| File | Responsibility after this plan | Change |
| :-- | :-- | :-- |
| `AGENTS.md` | Master rulebook: FK format tokens, Pillow canvas table, CLI cheatsheet, asset tree | Modify 4 spots |
| `README.md` | Workspace front page: Studio tabs, model-stack diagram, CLI + verification commands | Modify 4 spots |
| `docs/UI_CONTROL_CONFIG.md` | Which Studio cards expose pencils and where values persist | Modify 3 spots |
| `docs/ads/AD_COVER.md` | The pipeline spec (already correct) — gets 2 cross-ref/pencil clarifications | Modify 2 spots |
| `docs/memory/architecture/system-overview.md` | How subsystems connect; must name Ad Covers as a deviation | Modify 3 spots |
| `docs/OPERATIONS_AND_UTILITIES.md` | Catalog of maintenance/diagnostic scripts | Modify 3 spots |
| `docs/AUTO_POST_SCHEDULER.md` | Organic publishing worker scope boundary | Modify 1 spot |
| `docs/README.md` | Documentation index; memory table must list the new decision note | Modify 3 spots |
| `docs/memory/incidents/2026-09-19-control-ui-infinite-running-status.md` | Incident note whose 4 repo-root links are one level short | Modify 4 links |
| `docs/memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md` | Incident note whose 3 repo-root links are one level short | Modify 3 links |

Each task ends with a `grep` assertion proving the file no longer contains its stale string and does contain the canonical one.

---

### Task 1: `AGENTS.md` — rulebook alignment

**Files:**
- Modify: `AGENTS.md:111` (assets tree line)
- Modify: `AGENTS.md:190` (§4A format token line)
- Modify: `AGENTS.md:255-257` (§6 Canvas Dimensions list)
- Modify: `AGENTS.md:366-370` (§9 CLI cheatsheet tail)

**Interfaces:**
- Consumes: `CANON_PHASES`, `CANON_COMPLETE`, `CANON_FIELD_STORY_FINAL` from Global Constraints.
- Produces: the §9 Ad Cover CLI block that `README.md` (Task 2) must not duplicate verbatim — Task 2 links here instead of restating all seven modes.

- [ ] **Step 1: Confirm all four stale strings are present (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -n "1:1 square ad cover" AGENTS.md
grep -n "watermark templates, emojis" AGENTS.md
sed -n '255,257p' AGENTS.md
grep -n "# Test API Endpoints & Airtable Counts" AGENTS.md
```
Expected: 4 hits — line 190 says `(1:1 square ad cover)`, line 111 ends `emojis`, the canvas list shows only Story and Feed, and §9 ends with the two feed scratch commands. If any is absent, STOP: the file changed under this plan.

- [ ] **Step 2: Fix the `ADS` format token line (190)**

Replace:
```markdown
- **Format**: `STORY` (9:16), `FEEDS` (4:5), `REEL` (9:16 video), or `ADS` (1:1 square ad cover)
```
with:
```markdown
- **Format**: `STORY` (9:16), `FEEDS` (4:5), `REEL` (9:16 video), or `ADS` (Ad Cover row: carries the 1:1 cover and its 9:16 Story twin; the FK token stays `ADS`)
```

- [ ] **Step 3: Add Ad Cover to the §6 canvas list**

Replace:
```markdown
- **Canvas Dimensions**:
  - **Story (9:16)**: `1080 x 1920 px`
  - **Feed (4:5)**: `1080 x 1350 px`
```
with:
```markdown
- **Canvas Dimensions**:
  - **Story (9:16)**: `1080 x 1920 px`
  - **Feed (4:5)**: `1080 x 1350 px`
  - **Ad Cover (1:1)**: `1080 x 1080 px`, plus its 9:16 Story twin at `1080 x 1920 px` (`overlay.py::AD_COVER_STORY_CANVAS_SIZE`)
```

- [ ] **Step 4: Document both overlay PNGs in the assets tree line (111)**

Replace:
```
├── assets/                                  # homecartel_logo.png, *_layout.jpg watermark templates, emojis
```
with:
```
├── assets/                                  # homecartel_logo.png, *_layout.jpg watermark templates, emojis,
│                                            #   ad-covers-chandelier.png (1:1) + ad-cover-chandelier-story.png (9:16)
```

- [ ] **Step 5: Extend the §9 CLI cheatsheet with the Ad Cover run + recovery + helpers**

Replace:
```markdown
# Run Style This Story Pipeline (CLI)
python run_style_this_story.py --category chandeliers

# Test API Endpoints & Airtable Counts
python scratch/test_feed_apis.py
python scratch/audit_all_feed_subtabs.py
```
with:
```markdown
# Run Style This Story Pipeline (CLI)
python run_style_this_story.py --category chandeliers

# Run the Ad Cover pipeline — modes: scrape|interior|prompt|blend|conversion|story-blend|story-conversion|all
# One --mode all run produces BOTH the 1:1 cover and the 9:16 Story twin; see docs/ads/AD_COVER.md §7
python generate_ad_cover_pipeline.py --fixture chandelier --mode all --max-items 1

# Test API Endpoints & Airtable Counts
python scratch/test_feed_apis.py
python scratch/audit_all_feed_subtabs.py

# Ad Cover schema provisioning (idempotent) + row/image verification (read-only)
python scratch/ensure_ad_cover_fields.py --table-id tblwIsDGZBPuYJV2Z
python scratch/_verify_ad_cover_row.py [record_id]
python scratch/_verify_ad_cover_image.py [record_id]
```

- [ ] **Step 6: Run the passing test**

```bash
grep -c "9:16 Story" AGENTS.md
grep -n "1:1 square ad cover" AGENTS.md ; echo "exit=$?"
grep -n "ad-cover-chandelier-story.png" AGENTS.md
grep -n "story-conversion|all" AGENTS.md
grep -n "AD_COVER_STORY_CANVAS_SIZE" AGENTS.md
```
Expected: `9:16 Story` appears in ≥4 lines; the `1:1 square ad cover` grep returns `exit=1` (no match); the other three greps each return exactly one line.

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md
git commit -m "docs: align AGENTS.md canvas, asset, FK-token and CLI notes with the 7-phase Ad Cover pipeline"
```

---

### Task 2: `README.md` — front page, diagram, and commands

**Files:**
- Modify: `README.md:34` (Studio tab bullet)
- Modify: `README.md:114` (mermaid interior-ratio edge label)
- Modify: `README.md:158-159` (end of the CLI pipelines block)
- Modify: `README.md:169-173` (§3 verification block)

**Interfaces:**
- Consumes: `CANON_RATIO`, `CANON_TAB`, and the §7 CLI pointer created in Task 1 Step 5.
- Produces: the `### 4. Ad Covers` heading text `Ad Covers (1:1 \`1080 x 1080 px\` + 9:16 Story \`1080 x 1920 px\`)` (already on disk at line 99) that Task 3 Step 1 must match in `docs/UI_CONTROL_CONFIG.md`.

- [ ] **Step 1: Confirm the stale strings (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -n "9:16 / 4:5 Interiors" README.md
grep -n "per-fixture run cards" README.md
grep -c "generate_ad_cover_pipeline" README.md
grep -n "python scratch/test_feed_apis.py" README.md
```
Expected: lines for the diagram edge and the tab bullet, `0` for `generate_ad_cover_pipeline` (proving the Ad Cover CLI command is absent), and one line for the verification block. Use `per-fixture run cards` rather than the full phrase — in the file the words `Ad Covers` are wrapped in `**` bold markers, so a longer literal pattern will not match.

- [ ] **Step 2: Name both formats in the Studio tab bullet (34)**

Replace:
```markdown
- **Interactive Format Tabs**: Switch between **Feed** (7 subtabs), **Story** (10 subtabs), **Reel** (6 subtabs), and **Ad Covers** (per-fixture run cards), with summed completed counts on each format and subtab.
```
with:
```markdown
- **Interactive Format Tabs**: Switch between **Feed** (7 subtabs), **Story** (10 subtabs), **Reel** (6 subtabs), and **Ad Covers** — a `CANON_TAB` of per-fixture run cards, one press producing both the 1:1 cover and its 9:16 Story twin — with summed completed counts on each format and subtab.
```
(Write `CANON_TAB` as its literal text: *standalone 4th top-level Studio tab (not a sub-tab family)*.)

- [ ] **Step 3: Fix the model-stack diagram (114)**

Replace:
```
    C -->|9:16 / 4:5 Interiors| D[Claude Sonnet 5 Prompt & Headline Engine]
```
with:
```
    C -->|9:16 / 4:5 / 1:1 Interiors| D[Claude Sonnet 5 Prompt & Headline Engine]
```

- [ ] **Step 4: Add the Ad Cover command to §2 Run CLI Pipelines**

Replace:
```bash
# Product Showcase Feed (4:5)
python generate_product_showcase_feed_pipeline.py --mode all --max-items 3
```
with:
```bash
# Product Showcase Feed (4:5)
python generate_product_showcase_feed_pipeline.py --mode all --max-items 3

# Ad Cover (CANON_RATIO) — 7 phases; one run writes both Ad Cover Converted Image
# and Ad Cover Converted Image Story. Full mode list: docs/ads/AD_COVER.md §7
python generate_ad_cover_pipeline.py --fixture chandelier --mode all --max-items 1
```
(Substitute `CANON_RATIO` and `CANON_FIELD_STORY_FINAL` with their literal values from Global Constraints.)

- [ ] **Step 5: Add the Ad Cover helpers to §3 Verify Live Status Counts**

Replace:
```bash
python scratch/audit_all_feed_subtabs.py
python scratch/test_feed_apis.py
```
with:
```bash
python scratch/audit_all_feed_subtabs.py
python scratch/test_feed_apis.py

# Ad Cover: provision the table schema (idempotent), then verify one row's 4 attachments
# and assert the 1:1 / 9:16 geometry of both converted images
python scratch/ensure_ad_cover_fields.py --table-id tblwIsDGZBPuYJV2Z
python scratch/_verify_ad_cover_row.py
python scratch/_verify_ad_cover_image.py
```

- [ ] **Step 6: Run the passing test**

```bash
grep -c "9:16 / 4:5 Interiors" README.md ; echo "exit=$?"
grep -n "9:16 / 4:5 / 1:1 Interiors" README.md
grep -n "generate_ad_cover_pipeline.py" README.md
grep -n "_verify_ad_cover_image.py" README.md
```
Expected: the first grep prints `0` then `exit=1`; the last three each return a line.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: add the Ad Cover 1:1 + 9:16 Story run and verification commands to the workspace README"
```

---

### Task 3: `docs/UI_CONTROL_CONFIG.md` — Ad Covers tab and its pencil scope

**Files:**
- Modify: `docs/UI_CONTROL_CONFIG.md:3` (subtab census)
- Modify: `docs/UI_CONTROL_CONFIG.md:26-28` (editable table tail + non-editable sentence)

**Interfaces:**
- Consumes: the verified fact that `UI Control/routes/ad_cover.py` registers `/moodboard` (line 282) and `/prompt` (line 315) and persists through `save_config_override(...)` against `AD_COVER_MOODBOARD_CONFIG` / `AD_COVER_PROMPT_CONFIG` env keys.
- Produces: the sentence "the Phase 6 story prompt is env-only" that Task 7 Step 3 mirrors in the pipeline spec.

- [ ] **Step 1: Confirm the stale census (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -n "The Studio has 23 subtabs" docs/UI_CONTROL_CONFIG.md
grep -n "1 Product, 3 Styles Reel" docs/UI_CONTROL_CONFIG.md
grep -c -i "ad cover" docs/UI_CONTROL_CONFIG.md
```
Expected: 2 hits and a count of `0` — Ad Covers is not documented at all in this file, even though `AGENTS.md` points here for "Studio moodboard/prompt pencils … mapped in docs/UI_CONTROL_CONFIG.md".

- [ ] **Step 2: Amend the census sentence (3)**

Replace:
```markdown
The Studio has 23 subtabs: 10 Story, 7 Feed, and 6 Reel. Eighteen of those expose pencil controls for a Krea moodboard ID and room-interior prompt.
```
with:
```markdown
The Studio has 23 subtabs across 10 Story, 7 Feed, and 6 Reel, plus **Ad Covers** as a standalone 4th top-level tab of 6 per-fixture cards (only Chandelier is runnable). Eighteen subtabs expose pencil controls for a Krea moodboard ID and room-interior prompt; the Ad Covers Chandelier card exposes the same two pencils through `/api/ad-cover/moodboard` and `/api/ad-cover/prompt`.
```

- [ ] **Step 3: Add the Ad Covers row to the editable table**

Replace:
```markdown
| Reel | 1 Product, 3 Styles | `/api/one-product-3-styles-reel` | Chandelier only; editor controls first interior style |
```
with:
```markdown
| Reel | 1 Product, 3 Styles | `/api/one-product-3-styles-reel` | Chandelier only; editor controls first interior style |
| Ads | Ad Covers — Chandelier (top-level tab, not a subtab) | `/api/ad-cover` | Fixture settings → `--moodboard-id` / `--prompt`; `KREA_MOODBOARD_ID_CHANDELIER_AD_COVER` / `AD_COVER_PROMPT_CHANDELIER` |
```

- [ ] **Step 4: Record what the pencils do NOT reach**

Replace:
```markdown
The non-editable subtabs are Product Closeup Specs, Product Closeup Description, and This or That Story; Collection Category and Product Showcase Feed. Their cards still display live counts.
```
with:
```markdown
The non-editable subtabs are Product Closeup Specs, Product Closeup Description, and This or That Story; Collection Category and Product Showcase Feed. Their cards still display live counts. The five disabled Ad Covers cards (Pendant, Floor Lamp, Table Lamp, Cluster Chandelier, Wall Light) are unrunnable and hold no saved settings.

Ad Cover pencils control Phases 1–2 only. The 9:16 extension prompt used by Phase 6 is deliberately **not** Studio-editable — it is environment-only (`AD_COVER_STORY_CONVERSION_PROMPT`, with `FAL_STORY_MODEL` to swap the model), because it is a frame-extension instruction rather than a room description. See [`ads/AD_COVER.md`](ads/AD_COVER.md) §4.
```

- [ ] **Step 5: Run the passing test**

```bash
grep -n "AD_COVER_STORY_CONVERSION_PROMPT" docs/UI_CONTROL_CONFIG.md
grep -n "/api/ad-cover" docs/UI_CONTROL_CONFIG.md
grep -n "4th top-level tab" docs/UI_CONTROL_CONFIG.md
grep -c "23 subtabs: 10 Story" docs/UI_CONTROL_CONFIG.md
```
Expected: 1 line each for the first three; the last prints `0`.

- [ ] **Step 6: Commit**

```bash
git add docs/UI_CONTROL_CONFIG.md
git commit -m "docs: map the Ad Covers tab pencils and the env-only Phase 6 story prompt in the Studio config doc"
```

---

### Task 4: `docs/memory/architecture/system-overview.md` — name the deviation

**Files:**
- Modify: `docs/memory/architecture/system-overview.md:7`
- Modify: `docs/memory/architecture/system-overview.md:29-37`
- Modify: `docs/memory/architecture/system-overview.md:41`

**Interfaces:**
- Consumes: `CANON_COMPLETE`, and `AD_COVER_PHASE_LABELS` / `[Phase N/7]` emitted by `generate_ad_cover_pipeline.py`.
- Produces: a `[[../decisions/ad-cover-complete-status-belongs-to-phase-7]]` wikilink that Task 8 Step 2 lists in the docs index — the target file already exists.

- [ ] **Step 1: Confirm the gaps (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -n "docs/reels/\`" docs/memory/architecture/system-overview.md
grep -n "Every pipeline (Story/Feed/Reel)" docs/memory/architecture/system-overview.md
grep -n "AGENTS.md\` §6" docs/memory/architecture/system-overview.md
```
Expected: 3 hits. The `§6` reference is wrong independently of this feature: the subtab inventory is `AGENTS.md` §**7** (§6 is the Pillow rendering guidelines), so an agent following that pointer lands on the wrong section.

- [ ] **Step 2: Include `docs/ads/` in the orientation line (7)**

Replace:
```markdown
A short map of the real data flow, for orientation before diving into a specific pipeline doc under [`docs/stories/`](../../stories/), [`docs/feeds/`](../../feeds/), or [`docs/reels/`](../../reels/).
```
with:
```markdown
A short map of the real data flow, for orientation before diving into a specific pipeline doc under [`docs/stories/`](../../stories/), [`docs/feeds/`](../../feeds/), [`docs/reels/`](../../reels/), or [`docs/ads/`](../../ads/).
```

- [ ] **Step 3: Fix the pipeline-family sentence and the section cross-reference (37)**

Replace:
```markdown
Every pipeline (Story/Feed/Reel) is a variation on this shape — see `AGENTS.md` §6 for the full subtab inventory and `docs/README.md` for per-pipeline detail.
```
with:
```markdown
Every pipeline (Story/Feed/Reel/Ad Cover) is a variation on this shape — see `AGENTS.md` §7 for the full subtab inventory and `docs/README.md` for per-pipeline detail.

Ad Covers is the one deviation worth knowing before reading the diagram:

- It is a `standalone 4th top-level Studio tab (not a sub-tab family)` with **7 phases**, and one run writes **two** deliverables from the same blend: `Ad Cover Converted Image` (1:1) and `Ad Cover Converted Image Story` (9:16), the latter produced by a Phase 6 Nano Banana Pro frame extension and a Phase 7 local Pillow composite.
- Phase 6 re-uses the Phase 4 output, not the room prompt, so a single run costs 1 Krea call + **2** Fal calls.
- `Complete` is written by Phase 7 only. Reason in [[../decisions/ad-cover-complete-status-belongs-to-phase-7]].
- The Studio progress bar is driven by the generator's `[Phase N/7]` stdout markers, parsed numerically by `UI Control/routes/ad_cover.py::detect_phase`.
```

- [ ] **Step 4: Correct the blueprint count framing in §2 (41)**

Replace:
```markdown
`UI Control/api_server.py` — Flask app on **port 5200** — registers one Blueprint per pipeline under `UI Control/routes/`.
```
with:
```markdown
`UI Control/api_server.py` — Flask app on **port 5200** — registers one Blueprint per pipeline under `UI Control/routes/`; Ad Covers is one Blueprint covering six fixture cards rather than one per subtab.
```

- [ ] **Step 5: Run the passing test**

```bash
grep -n "docs/ads/" docs/memory/architecture/system-overview.md
grep -n "AGENTS.md\` §7" docs/memory/architecture/system-overview.md
grep -n "ad-cover-complete-status-belongs-to-phase-7" docs/memory/architecture/system-overview.md
grep -c "AGENTS.md\` §6" docs/memory/architecture/system-overview.md
```
Expected: 1 line each for the first three; the last prints `0`. The wikilink target must exist: `ls docs/memory/decisions/ad-cover-complete-status-belongs-to-phase-7.md`.

- [ ] **Step 6: Commit**

```bash
git add docs/memory/architecture/system-overview.md
git commit -m "docs: record the Ad Cover dual-output 7-phase deviation in the architecture overview"
```

---

### Task 5: `docs/OPERATIONS_AND_UTILITIES.md` — catalog the Ad Cover helpers

**Files:**
- Modify: `docs/OPERATIONS_AND_UTILITIES.md:3`
- Modify: `docs/OPERATIONS_AND_UTILITIES.md:22` (tail of the Airtable maintenance table)
- Modify: `docs/OPERATIONS_AND_UTILITIES.md:49-50` (tail of the Diagnostics table)

**Interfaces:**
- Consumes: `scratch/ensure_ad_cover_fields.py` (idempotent, `--table-id` flag), `scratch/_verify_ad_cover_row.py` and `scratch/_verify_ad_cover_image.py` (both accept an optional `record_id` argv; the image one asserts `(1080, 1080)` and `(1080, 1920)`).
- Produces: table rows that Task 2 Step 5's commands and Task 1 Step 5's commands refer to, so the three files must name the same paths.

- [ ] **Step 1: Confirm the helpers are uncatalogued (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -c -i "ad_cover" docs/OPERATIONS_AND_UTILITIES.md
grep -n "^## Airtable data maintenance" docs/OPERATIONS_AND_UTILITIES.md
```
Expected: `0` and one heading line. A new agent hunting for "how do I add an Ad Cover column" has no pointer today.

- [ ] **Step 2: Widen the scope sentence (3)**

Replace:
```markdown
Root-level scripts that keep the system healthy but aren't Story/Feed/Reel content pipelines and weren't previously catalogued anywhere. Descriptions are pulled from each script's own module docstring.
```
with:
```markdown
Scripts that keep the system healthy but aren't Story/Feed/Reel/Ad Cover content pipelines and weren't previously catalogued anywhere. Root-level scripts plus the `scratch/` schema and verification helpers that a pipeline doc alone would not surface. Descriptions are pulled from each script's own module docstring.
```

- [ ] **Step 3: Add the provisioning helper to Airtable data maintenance**

Replace:
```markdown
| [`content_automation/cleanup.py`](../content_automation/cleanup.py) | Scratchpad/temp-file lifecycle manager for containerized deploys (Zoho Catalyst / Docker) — purges `output/temp`, `output/temp_uploads`, and other scratch directories after upload, or on a scheduled age-based sweep, to prevent container disk exhaustion. |
```
with:
```markdown
| [`content_automation/cleanup.py`](../content_automation/cleanup.py) | Scratchpad/temp-file lifecycle manager for containerized deploys (Zoho Catalyst / Docker) — purges `output/temp`, `output/temp_uploads`, and other scratch directories after upload, or on a scheduled age-based sweep, to prevent container disk exhaustion. |
| [`scratch/ensure_ad_cover_fields.py`](../scratch/ensure_ad_cover_fields.py) | Provisions the Ad Cover Chandelier table schema (`tblwIsDGZBPuYJV2Z`): text/attachment/dateTime/number columns, the five product columns, the 8 `Status` choices, and the two 9:16 story attachment columns. Idempotent — creates only what is missing and reports the full field inventory. `--table-id` targets another fixture once one is wired. |
```

- [ ] **Step 4: Add the two verifiers to Diagnostics**

Replace:
```markdown
| [`preview_tips_edu_thumbnail.py`](../preview_tips_edu_thumbnail.py) | Renders a single test image of the Tips & Educational Feed thumbnail title/subtitle text overlay onto a base image, without touching Airtable. |
```
with:
```markdown
| [`preview_tips_edu_thumbnail.py`](../preview_tips_edu_thumbnail.py) | Renders a single test image of the Tips & Educational Feed thumbnail title/subtitle text overlay onto a base image, without touching Airtable. |
| [`scratch/_verify_ad_cover_row.py`](../scratch/_verify_ad_cover_row.py) | Prints every Ad Cover row's FK, status, PHT timestamp and the attachment filenames/sizes in all four image fields (`Ad Cover Interior`, `Ad Cover Blended Image`, `Ad Cover Blended Image Story`, `Ad Cover Converted Image`, `Ad Cover Converted Image Story`). Read-only `list_records`; optional `record_id` argv. |
| [`scratch/_verify_ad_cover_image.py`](../scratch/_verify_ad_cover_image.py) | Downloads both Ad Cover deliverables and asserts exact geometry — `(1080, 1080)` for `Ad Cover Converted Image` and `(1080, 1920)` for `Ad Cover Converted Image Story` — then samples the top/bottom bands for near-white pixels to prove the brand overlay actually composited. Exits 1 on any mismatch and skips an empty story field instead of failing. |
```

- [ ] **Step 5: Run the passing test**

```bash
grep -c "scratch/ensure_ad_cover_fields.py" docs/OPERATIONS_AND_UTILITIES.md
grep -c "scratch/_verify_ad_cover" docs/OPERATIONS_AND_UTILITIES.md
python -c "import pathlib,sys; [print(p, 'OK') for p in ['scratch/ensure_ad_cover_fields.py','scratch/_verify_ad_cover_row.py','scratch/_verify_ad_cover_image.py'] if pathlib.Path(p).is_file()]"
```
Expected: `1`, `2`, then three `OK` lines — this proves every relative link added actually resolves on disk.

- [ ] **Step 6: Commit**

```bash
git add docs/OPERATIONS_AND_UTILITIES.md
git commit -m "docs: catalog the Ad Cover schema provisioning and 1:1/9:16 geometry verification helpers"
```

---

### Task 6: `docs/AUTO_POST_SCHEDULER.md` — close the ads/publishing ambiguity

**Files:**
- Modify: `docs/AUTO_POST_SCHEDULER.md:3-6`

**Interfaces:**
- Consumes: the verified fact that `tblwIsDGZBPuYJV2Z` is referenced only by `content_automation/config.py`, `content_automation/foreign_key.py`, `UI Control/routes/ad_cover.py`, `generate_ad_cover_pipeline.py` and the three `scratch/` helpers — no posting code path reads it.
- Produces: nothing consumed later.

- [ ] **Step 1: Confirm the gap (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -n "Stories, Feeds, and Reels" docs/AUTO_POST_SCHEDULER.md
grep -n "docs/stories/\`, \`docs/feeds/\`, \`docs/reels/\`" docs/AUTO_POST_SCHEDULER.md
grep -rln "tblwIsDGZBPuYJV2Z" --include="*.py" . | grep -v worktrees
```
Expected: 2 hits, then the code-reference list — which contains **no** auto-post script. That is the evidence for the wording in Step 2.

- [ ] **Step 2: State the scope boundary**

Replace:
```markdown
> Publishes finished Stories, Feeds, and Reels to Instagram at their scheduled Philippine Time (PHT).

- **Script**: [`run_auto_post_scheduler.py`](../run_auto_post_scheduler.py)
- **Not covered elsewhere**: this worker isn't part of the Story/Feed/Reel generation pipelines documented under `docs/stories/`, `docs/feeds/`, `docs/reels/` — it runs *after* content is generated, as a separate always-on process.
```
with:
```markdown
> Publishes finished Stories, Feeds, and Reels to Instagram at their scheduled Philippine Time (PHT).

- **Script**: [`run_auto_post_scheduler.py`](../run_auto_post_scheduler.py)
- **Not covered elsewhere**: this worker isn't part of the Story/Feed/Reel generation pipelines documented under `docs/stories/`, `docs/feeds/`, `docs/reels/` — it runs *after* content is generated, as a separate always-on process.
- **Ad Covers are out of scope here**: the 1:1 `Ad Cover Converted Image` and its 9:16 `Ad Cover Converted Image Story` are paid-ad creatives, and nothing in this repository posts them — the Ad Cover table id appears only in the config/foreign-key maps, `UI Control/routes/ad_cover.py`, `generate_ad_cover_pipeline.py` and three `scratch/` verifiers. Whether the external port-3000 app pulls them is decided in that other codebase; do not assume an Ad Cover row at `Complete` will go live organically. See [`ads/AD_COVER.md`](ads/AD_COVER.md).
```

- [ ] **Step 3: Run the passing test**

```bash
grep -n "Ad Covers are out of scope" docs/AUTO_POST_SCHEDULER.md
grep -n "Ad Cover Converted Image Story" docs/AUTO_POST_SCHEDULER.md
```
Expected: 1 line each.

- [ ] **Step 4: Commit**

```bash
git add docs/AUTO_POST_SCHEDULER.md
git commit -m "docs: mark Ad Cover creatives as out of scope for the organic auto-post worker"
```

---

### Task 7: `docs/ads/AD_COVER.md` — pencil scope and helper cross-refs

**Files:**
- Modify: `docs/ads/AD_COVER.md:102`
- Modify: `docs/ads/AD_COVER.md:200`

**Interfaces:**
- Consumes: `CANON_FIELD_STORY_FINAL`; the Task 3 Step 4 statement that Phase 6's prompt is env-only.
- Produces: the §7 pointer other tasks cite (`docs/ads/AD_COVER.md §7`) — it must stay section 7 after these edits, so do not insert or renumber sections.

- [ ] **Step 1: Confirm the two weak spots (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -n "to provision the two story columns idempotently" docs/ads/AD_COVER.md
grep -n "Use the MB / Prompt pencils" docs/ads/AD_COVER.md
grep -n "^## 7. CLI & Web UI Execution Commands" docs/ads/AD_COVER.md
```
Expected: 1, 1, 1 — the §7 anchor the rest of the docs point at must survive this task.

- [ ] **Step 2: Point the provisioning line at the operations catalog**

Replace:
```markdown
Run `python scratch/ensure_ad_cover_fields.py` to provision the two story columns idempotently.
```
with:
```markdown
Run `python scratch/ensure_ad_cover_fields.py --table-id tblwIsDGZBPuYJV2Z` to provision the two story columns and the 8 `Status` choices idempotently; the helper and the two read-only verifiers are catalogued in [`../OPERATIONS_AND_UTILITIES.md`](../OPERATIONS_AND_UTILITIES.md). Provisioning must precede the first story-branch run — Phase 6 cannot upload into a column that does not exist.
```

- [ ] **Step 3: Bound what the Studio pencils control**

Replace:
```markdown
5. Use the MB / Prompt pencils on the card to override the Krea moodboard or interior prompt (persisted to `.env` via `output/config_overrides.json`); the 5 status pills (`P, S, C, D, FM`) and Rows count stay live.
```
with:
```markdown
5. Use the MB / Prompt pencils on the card to override the Krea moodboard or interior prompt (persisted to `.env` via `output/config_overrides.json`); the 5 status pills (`P, S, C, D, FM`) and Rows count stay live. Those pencils reach Phases 1–2 only — the Phase 6 9:16 extension prompt is environment-only (`AD_COVER_STORY_CONVERSION_PROMPT`), as mapped in [`../UI_CONTROL_CONFIG.md`](../UI_CONTROL_CONFIG.md).
```

- [ ] **Step 4: Run the passing test**

```bash
grep -n "OPERATIONS_AND_UTILITIES.md" docs/ads/AD_COVER.md
grep -n "UI_CONTROL_CONFIG.md" docs/ads/AD_COVER.md
grep -n "^## 7. CLI & Web UI Execution Commands" docs/ads/AD_COVER.md
grep -c "Phase 5" docs/ads/AD_COVER.md
```
Expected: 1, 1, 1 (the §7 anchor unchanged), and a nonzero count for the Phase 5 row.

- [ ] **Step 5: Commit**

```bash
git add docs/ads/AD_COVER.md
git commit -m "docs: cross-reference Ad Cover provisioning helpers and bound the Studio pencil scope to Phases 1-2"
```

---

### Task 8: `docs/README.md` — memory index and heading numbering

**Files:**
- Modify: `docs/README.md:148-152` (memory table)
- Modify: `docs/README.md:154` (duplicate `## 🚧 6.` heading)

**Interfaces:**
- Consumes: the wikilink target created in Task 4 Step 3 and the file `docs/memory/decisions/ad-cover-complete-status-belongs-to-phase-7.md`.
- Produces: nothing consumed later.

- [ ] **Step 1: Confirm the index is stale (the failing test)**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -c "ad-cover-complete-status" docs/README.md
grep -n "memory/decisions/2026-09-19-foreign-key-map-purge.md" docs/README.md
grep -n "^## . 6\." docs/README.md
ls docs/memory/incidents/ | grep -c "2026-09-21"
```
Expected: `0` (the new decision note is unlisted), one line for the last listed decision, two headings numbered `6` (Project Memory and Planned-but-NOT-Implemented), and `3` incident files dated 2026-09-21 that the table never lists — pre-existing drift in the same table this task is already editing.

- [ ] **Step 2: Add the missing memory rows**

Replace:
```markdown
| [`memory/decisions/2026-09-19-foreign-key-map-purge.md`](memory/decisions/2026-09-19-foreign-key-map-purge.md) | Why 7 dead table IDs were removed from `TABLE_PREFIX_MAP`, and the missing Before & After Floor Lamp table follow-up. |
```
with:
```markdown
| [`memory/decisions/2026-09-19-foreign-key-map-purge.md`](memory/decisions/2026-09-19-foreign-key-map-purge.md) | Why 7 dead table IDs were removed from `TABLE_PREFIX_MAP`, and the missing Before & After Floor Lamp table follow-up. |
| [`memory/decisions/ad-cover-complete-status-belongs-to-phase-7.md`](memory/decisions/ad-cover-complete-status-belongs-to-phase-7.md) | Why `Complete` moved off Phase 5 onto Phase 7 (singleSelect overwrite semantics), why a story-branch failure still leaves the row `Complete`, and why Phase 6 needs its own outpaint prompt. |
```

- [ ] **Step 3: List the three 2026-09-21 incidents the index never picked up**

Replace:
```markdown
| [`memory/incidents/2026-09-19-shopify-catalog-truncation-429.md`](memory/incidents/2026-09-19-shopify-catalog-truncation-429.md) | Shopify catalog truncation / HTTP 429 incident and mitigation. |
```
with:
```markdown
| [`memory/incidents/2026-09-19-shopify-catalog-truncation-429.md`](memory/incidents/2026-09-19-shopify-catalog-truncation-429.md) | Shopify catalog truncation / HTTP 429 incident and mitigation. |
| [`memory/incidents/2026-09-21-shopify-429-partial-cache.md`](memory/incidents/2026-09-21-shopify-429-partial-cache.md) | Why a partially failed catalog crawl must never overwrite the disk cache. |
| [`memory/incidents/2026-09-21-day-night-feed-stamp-lost-in-refactor.md`](memory/incidents/2026-09-21-day-night-feed-stamp-lost-in-refactor.md) | Day & Night Feed stamping lost during a refactor, and how it was restored. |
| [`memory/incidents/2026-09-21-item-name-stamp-inconsistencies.md`](memory/incidents/2026-09-21-item-name-stamp-inconsistencies.md) | `Item Name` stamp drift across pipelines. |
```
Before committing, read each of those three incident files and correct these one-line summaries if they misdescribe the note — the links must not ship with invented captions.

- [ ] **Step 4: Renumber the duplicated heading**

Replace:
```markdown
## 🚧 6. Planned but NOT Implemented (`docs/superpowers/`)
```
with:
```markdown
## 🚧 7. Planned but NOT Implemented (`docs/superpowers/`)
```
and the following `## 📂 7. Legacy Per-Folder Notes` becomes `## 📂 8. Legacy Per-Folder Notes`. The trailing sentence in that section refers to "sections 1–3 above", which stays accurate.

- [ ] **Step 5: Run the passing test**

```bash
grep -c "ad-cover-complete-status" docs/README.md
grep -c "2026-09-21" docs/README.md
grep -n "^## .* 6\.\|^## .* 7\.\|^## .* 8\." docs/README.md
```
Expected: `1`; `3`; and five distinct heading numbers `1–8` with no duplicate `6`.

- [ ] **Step 6: Commit**

```bash
git add docs/README.md
git commit -m "docs: index the Ad Cover story decision note and fix duplicated section numbering"
```

---

### Task 9: Repair pre-existing broken links in the two 2026-09-19 incident notes

**Files:**
- Modify: `docs/memory/incidents/2026-09-19-control-ui-infinite-running-status.md:48,49,51,53`
- Modify: `docs/memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md:20,36`

**Interfaces:**
- Consumes: nothing.
- Produces: a green link check for Task 10 Step 3 (that step's checker must return zero broken links, so these seven must be fixed first — they are not Ad Cover drift but they are the only thing that would make the sweep report red).

**Why this is in scope:** while building the sweep I ran the link checker and found these seven are dead for an unrelated reason: the notes live at `docs/memory/incidents/`, so the repository root is **three** levels up, but every link says `../../` (two). The targets all exist — `run_1_product_3_styles_feed.py`, `backfill_1_product_3_styles_tags.py`, `UI Control/routes/*.py`, `UI Control/src/app/App.tsx`, `UI Control/src/app/components/planning/LiveLogViewer.tsx`. The link depth is simply wrong, so Obsidian renders them as unresolvable.

- [ ] **Step 1: Confirm the seven links are dead (the failing test)**

Run the checker from Task 10 Step 3 (it URL-decodes `%20` and skips `.kilo` / `superpowers`). Expected: `REAL BROKEN: 7`, all of them in these two files. If it reports a different count or other files, STOP and reconcile — the plan's assumption about repo state is wrong.

- [ ] **Step 2: Fix the four links in the Control UI incident**

In `docs/memory/incidents/2026-09-19-control-ui-infinite-running-status.md`, replace each occurrence of `(../../UI%20Control/` with `(../../../UI%20Control/` — four links on lines 48, 49, 51 and 53. Resulting targets:

```markdown
../../../UI%20Control/routes/one_product_three_styles_feed.py
../../../UI%20Control/routes/queue_manager.py
../../../UI%20Control/src/app/App.tsx
../../../UI%20Control/src/app/components/planning/LiveLogViewer.tsx
```

- [ ] **Step 3: Fix the three links in the tagging incident**

In `docs/memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md`, replace each occurrence of `(../../run_1_product_3_styles_feed.py)` with `(../../../run_1_product_3_styles_feed.py)` (lines 20 and 36), and `(../../backfill_1_product_3_styles_tags.py)` with `(../../../backfill_1_product_3_styles_tags.py)` (line 38 area).

- [ ] **Step 4: Run the passing test**

```bash
grep -c "(\.\./\.\./UI%20Control\|(\.\./\.\./run_1_product_3_styles_feed.py\|(\.\./\.\./backfill_1_product_3_styles_tags.py" docs/memory/incidents/2026-09-19-control-ui-infinite-running-status.md docs/memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md
```
Expected: `0` for both files (no two-level links to those paths remain), then re-run the Task 10 Step 3 checker and expect `REAL BROKEN: 0`.

- [ ] **Step 5: Commit**

```bash
git add docs/memory/incidents/2026-09-19-control-ui-infinite-running-status.md docs/memory/incidents/2026-09-19-one-product-3-styles-tagging-nameerror.md
git commit -m "fix: repair three-level relative links in the 2026-09-19 incident notes"
```

---

### Task 10: Repo-wide consistency sweep

**Files:**
- Modify: none expected — this task only proves the other nine.

**Interfaces:**
- Consumes: every canonical string from Tasks 1–9, and the zero-broken-link state produced by Task 9.
- Produces: the green gate to report to the user before any commit/push of the feature branch.

- [ ] **Step 1: No live doc still claims a 5-phase or square-only Ad Cover**

```bash
cd "C:/Users/User/Desktop/marketing-automation"
grep -rn --include="*.md" -iE "5 phase|5-phase" . | grep -v worktrees | grep -v "superpowers/plans" | cut -c1-120
grep -rn --include="*.md" "1:1 square ad cover" . | grep -v worktrees
grep -rn --include="*.md" "9:16 / 4:5 Interiors" . | grep -v worktrees | grep -v "superpowers/plans"
```
Baseline before this plan (so you can tell a real regression from known noise): the first grep returns exactly four lines — `Before and After Reel/README.md:15` (legacy per-folder note, excluded by `docs/README.md` §7), `docs/feeds/COLLECTION_CATEGORY_FEED.md:102`, `docs/reels/MOODBOARD_REEL.md:96`, and this plan's own text. After Task 1 those three foreign-pipeline hits must be **unchanged** (they describe their own 5-phase flows, not Ad Cover) and `AGENTS.md` / `README.md` / `docs/README.md` must contribute none. The second and third greps must return **zero** lines.

- [ ] **Step 2: Every live doc that names Ad Cover agrees on the phase count**

```bash
grep -rn --include="*.md" -iE "ad.?cover" README.md AGENTS.md docs/*.md docs/ads/ docs/memory/ | grep -viE "7 phase|7-phase|story|1:1|ads/AD_COVER|adc|ad-cover|ad cover" | cut -c1-120
```
Expected: empty. Anything left over is a sentence that mentions Ad Cover while asserting a conflicting shape — fix it in place and re-run.

- [ ] **Step 3: Internal links resolve**

```bash
python - <<'PY'
import pathlib, re, urllib.parse
root = pathlib.Path('.')
files = [pathlib.Path(p) for p in ['README.md', 'AGENTS.md']] + sorted((root / 'docs').rglob('*.md'))
bad = []
for md in files:
    if '.kilo' in md.parts or 'superpowers' in md.parts:
        continue                       # worktree copies and quoted-snippet plans are not live docs
    for label, target in re.findall(r'\[([^\]]+)\]\((?!https?:)([^)]+)\)',
                                    md.read_text(encoding='utf-8', errors='ignore')):
        path = urllib.parse.unquote(target.split('#')[0])   # resolve %20 in "UI Control" paths
        if not path:
            continue
        if not (md.parent / path).resolve().exists():
            bad.append(f'{md}: [{label}]({target})')
print('checked', len(files), 'files')
print('\n'.join(bad) if bad else 'ALL MD LINKS RESOLVE')
print('REAL BROKEN:', len(bad))
PY
```
Expected: `ALL MD LINKS RESOLVE` and `REAL BROKEN: 0` — reachable only after Task 9. Before Task 9 the same check prints `REAL BROKEN: 7`, all inside the two 2026-09-19 incident notes. If new names appear, correct those paths before committing.

- [ ] **Step 4: Prove the docs match the code, not just each other**

```bash
python generate_ad_cover_pipeline.py --help | grep -o "story-blend\|story-conversion" | sort -u
python -c "import generate_ad_cover_pipeline as g; print(g.TOTAL_PHASES, g.STORY_ASPECT_RATIO, g.BLENDED_STORY_FIELD, '|', g.CONVERTED_STORY_FIELD)"
python -c "from content_automation.overlay import AD_COVER_STORY_ASSETS as S, AD_COVER_STORY_CANVAS_SIZE as C; print(S['chandelier'], C)"
grep -o "Phase 6\|Phase 7" docs/ads/AD_COVER.md | sort | uniq -c
```
Expected `story-blend`/`story-conversion`; `7 9:16 Ad Cover Blended Image Story | Ad Cover Converted Image Story`; `ad-cover-chandelier-story.png (1080, 1920)`; and both `Phase 6` and `Phase 7` present in the spec. If a doc field name differs by even one character, the doc is wrong — fix the doc.

- [ ] **Step 5: Commit the sweep (only if Steps 1–4 forced edits)**

```bash
git status --porcelain
git add -u README.md AGENTS.md docs
git commit -m "docs: final consistency sweep for the Ad Cover 1:1 + 9:16 Story pipeline"
```
If `git status --porcelain` shows no doc changes, skip the commit — an empty docs commit is noise.

- [ ] **Step 6: Report, do not push**

Summarize for the user: which files changed, that `.env` was never staged, and that **pushing is still their call** — `AGENTS.md` §11.6 fast-forwards `genspark_ai_developer` → `main`, and a `main` push triggers the Railway deploy. `assets/ad-cover-chandelier-story.png` must be in the pushed tree or Phase 7 skips in production (it is still untracked from the feature work).

---

## Self-Review

**Spec coverage** (against the feature plan's documentation item, "`AGENTS.md` §7 … `docs/README.md` / `README.md` … any 5-phase mention for Ad Cover"):
- Feature §7 `AGENTS.md` bullet + `docs` tree line — already on disk; Task 1 covers the *other* four Ad Cover-relevant spots (§2 assets, §4A token, §6 canvases, §9 cheatsheet).
- `docs/ads/AD_COVER.md` §1–§7 — already on disk; Task 7 adds only the pencil-scope and provisioning-order clarifications the feature plan implied but did not state.
- `docs/memory/decisions/` note — exists; Task 4 links it and Task 8 indexes it.
- Found while auditing, not part of the Ad Cover feature: seven repo-root links in the two 2026-09-19 incident notes are one `../` short, and `docs/README.md` numbers two sections `6`. Both are cheap to repair while those files are already open, and Task 10 Step 3's link gate cannot go green until they are fixed — hence Tasks 8 (renumbering) and 9 (links).
- Not covered by any task, deliberately: `docs/superpowers/**` and `.kilo/worktrees/**` (Global Constraints exclude them); `UI Control/README.md` and the legacy per-folder READMEs (`docs/README.md` marks them manual/legacy — that section renumbers from 7 to 8 in Task 8 Step 4, so cite it by name, not number, in later edits).

**Placeholder scan:** every step carries literal old/new text. The two places that intentionally say "write the canonical value" (`CANON_TAB` in Task 4 Step 3, `CANON_RATIO` in Task 2 Step 4) restate the literal string in a parenthetical immediately below. Task 8 Step 3 instructs the executor to *verify* three captions against the incident files rather than trust them — that is a real check, not a placeholder.

**Type/name consistency:** `Ad Cover Blended Image Story` and `Ad Cover Converted Image Story` are spelled identically in Tasks 1, 2, 5, 7, 10 and match the constants printed by Task 10 Step 4. `ensure_ad_cover_fields.py`, `_verify_ad_cover_row.py`, `_verify_ad_cover_image.py` keep the same paths in Tasks 1, 2, 5. `AD_COVER_STORY_CONVERSION_PROMPT` / `FAL_STORY_MODEL` appear in Tasks 3 and 7 with the same spelling used in Task 10 Step 4's check. Section anchor "§7" of `docs/ads/AD_COVER.md` is asserted preserved in Task 7 Step 4 because Tasks 1 and 2 point at it. Task 9's seven repaired links are the exact paths Task 10 Step 3's checker verifies.
