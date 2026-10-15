# Skills Registration + Docs Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register the two newly added general skills (`graphify`, `icm-architect`) and the vendored `docs/icm/` reference library in every MD file the repo's own rules require, and fix the `.gitignore` bug that would ship the `graphify` skill broken.

**Architecture:** Docs-only change plus one `.gitignore` fix. No Python, no frontend, no Airtable, no pipeline behavior. The rulebook (`AGENTS.md` §8) names the mandatory sync targets for "an agent skill (added, removed, or repurposed)": `AGENTS.md` §12 and `docs/SKILLS_GUIDE.md`. Because the additions also create a new `docs/` subtree and a non-obvious provenance choice, three more files are in scope (`docs/README.md`, `README.md`, one `docs/memory/decisions/` note).

**Tech Stack:** Markdown, `.gitignore`, git.

**Spec:** `AGENTS.md` §2 (directory tree), §8 ("Docs to update when you change X"), §12 (skills inventory); `docs/SKILLS_GUIDE.md` §1/§2/§3; `docs/README.md` navigation / §6 / §7.

**Plan location note:** the writing-plans default is `docs/superpowers/plans/`. Repo convention wins: `docs/plans/` is the live plan index (`docs/README.md` §7), so this file lives there and Task 7 registers it.

## Global Constraints

- Commit/push **only if the user asks.** This plan ends at verification.
- Branch `marketing-automation`. No force-push, no `reset --hard`, no amend/rebase, no `--no-verify`.
- Never stage `.env`, `.env.*` (except `*.example`), `graphify-out/`, `.graphify*`, `output/`, `node_modules/`.
- Verify with `python -m unittest discover tests` (a docs-only change must not break the suite). No `py_compile` needed — no `.py` is touched.
- Conventional commit prefixes: `docs:`, `fix:`.
- Every claim written into the docs must be true of the filesystem at the time of writing — no aspirational counts.

---

## Current State (verified 2026-10-15)

| Fact | Evidence |
| :--- | :--- |
| `.agents/skills/graphify/` exists, 10 files | `Get-ChildItem -Recurse`: SKILL.md + 8 `references/*.md` + `.graphify_version` |
| `.agents/skills/icm-architect/` exists, 15 files | SKILL.md, README.md, LICENSE, 8 `assets/templates/*.md`, 4 `references/*.md` |
| `docs/icm/` exists, 190 untracked files, ~1.6 MB | `git ls-files --others --exclude-standard docs/icm` |
| `AGENTS.md` §12 says "12 version-controlled agent skills" | `AGENTS.md:460` — actual count on disk is 14 |
| `skills-lock.json` pins only 2 skills | `git-guardrails-claude-code`, `systematic-debugging` — both new skills are **absent** |
| `README.md:160` claims the lock holds "currently `git-guardrails-claude-code`" | Stale by one entry, silent about the two unpinned skills |
| `docs/README.md` tree omits `icm/` | Lines 17–82 vs. the actual `docs/` listing |
| `docs/README.md:195` claims `docs/superpowers/` was removed | False: `git ls-files docs/superpowers` returns the 2026-10-13 plan |
| `.gitignore:69` `.graphify*` is unanchored | `git check-ignore -v .agents/skills/graphify/.graphify_version` → **matched**; `git add -An .agents` stages 24 of 25 files |

---

## File Structure

**Modified (5 files):**

| File | What changes |
| :--- | :--- |
| `.gitignore` | Anchor the two graphify patterns so they stop swallowing the skill's own `.graphify_version`. |
| `AGENTS.md` | §2 directory tree gains `plans/` + `icm/`; §12 count 12→14 with entries 13 and 14. |
| `docs/SKILLS_GUIDE.md` | §1 general-skills table gains 2 rows; §2 gains 2 sections; §3 records that both are hand-vendored. |
| `docs/README.md` | Navigation tree gains `icm/`; §6 gains the decision-note row; §7 gains this plan's row; the false `docs/superpowers/` claim at line 195 is corrected. |
| `README.md` | The `skills-lock.json` row stops lying about what is pinned. |

**Created (2 files):**

| File | Responsibility |
| :--- | :--- |
| `docs/memory/decisions/2026-10-15-graphify-icm-vendored-skills.md` | Why these two skills are hand-vendored, what each is for, and why `docs/icm/` is reference material and not a pipeline doc. |
| `docs/plans/2026-10-15-skills-registration-md-sync.md` | This plan. |

**Deliberately not touched:** `docs/REMAINING_WORK.md` (pre-existing staleness about `docs/.obsidian/` and the §2.2 `AGENTS.md` split — separate work, separate plan). `skills-lock.json` (no hash can be honestly computed for hand-vendored skills; documenting the gap beats fabricating an entry).

---

## Task 1: Anchor the graphify `.gitignore` patterns (blocking prerequisite)

**Files:**
- Modify: `.gitignore:67-69`

**Interfaces:**
- Consumes: nothing.
- Produces: an ignore rule set under which `git add -An .agents` lists **25** files (currently 24) while `graphify-out/` stays ignored. Task 2 writes prose asserting `.agents/skills/` is git-safe — only true after this task.

- [ ] **Step 1: Read the current tail of `.gitignore`**

Run: `git -C "C:\Users\User\Desktop\marketing-automation" --no-pager diff -- .gitignore`
Expected: a hunk adding `graphify-out/` and `.graphify*` with no leading `/`.

- [ ] **Step 2: Replace the two unanchored patterns**

Exact `old_text`:

```
# Graphify knowledge graph outputs and cache
graphify-out/
.graphify*
```

Exact `new_text`:

```
# Graphify knowledge graph outputs and cache.
# Anchored on purpose: an unanchored `.graphify*` also matches
# .agents/skills/graphify/.graphify_version and silently drops it from every commit.
/graphify-out/
/.graphify*
```

- [ ] **Step 3: Verify the skill's version file is no longer ignored**

Run: `git -C "C:\Users\User\Desktop\marketing-automation" check-ignore -v ".agents/skills/graphify/.graphify_version"; Write-Output "exit=$LASTEXITCODE"`
Expected: no match line, `exit=1` (previously matched `.gitignore:69:.graphify*`, `exit=0`).

- [ ] **Step 4: Verify the real outputs are still ignored**

Run: `git -C "C:\Users\User\Desktop\marketing-automation" check-ignore -v "graphify-out/index.html" ".graphify_ast.json"; Write-Output "exit=$LASTEXITCODE"`
Expected: two match lines naming `/graphify-out/` and `/.graphify*`, `exit=0`.

- [ ] **Step 5: Verify the full skill set now stages**

Run: `git -C "C:\Users\User\Desktop\marketing-automation" add -An .agents | Measure-Object -Line`
Expected: `25` (10 graphify + 15 icm-architect). Was 24.

---

## Task 2: Register both skills in `AGENTS.md`

**Files:**
- Modify: `AGENTS.md:460` (count), `AGENTS.md:478` (append entries 13–14), `AGENTS.md:60-61` (directory tree)

**Interfaces:**
- Consumes: Task 1 (the §12 sentence asserts `.gitignore` whitelisting).
- Produces: the strings `graphify` and `icm-architect` in `AGENTS.md`, and the count `14`. `docs/SKILLS_GUIDE.md` (Task 3) must reuse these exact skill names in the same order.

- [ ] **Step 1: Fix the skill count**

Exact `old_text`:

```
The workspace includes 12 version-controlled agent skills in `.agents/skills/` (whitelisted in `.gitignore`).
```

Exact `new_text`:

```
The workspace includes 14 version-controlled agent skills in `.agents/skills/` (whitelisted in `.gitignore`).
```

- [ ] **Step 2: Append entries 13 and 14 after `systematic-debugging`**

Exact `old_text`:

```
12. **`systematic-debugging`** — General root-cause discipline (no fixes without investigation: reproduce, check changes, gather evidence, single-hypothesis fixes). Always paired with repo `debug-pipeline-run` for pipeline failures.
```

Exact `new_text`:

```
12. **`systematic-debugging`** — General root-cause discipline (no fixes without investigation: reproduce, check changes, gather evidence, single-hypothesis fixes). Always paired with repo `debug-pipeline-run` for pipeline failures.
13. **`graphify`** — Turns this repo (code, docs, papers, images) into a persistent knowledge graph with god nodes, community detection, and query/path/explain tools. Load it for cross-file relational questions ("what calls this", "what would changing X hit") instead of grep-walking the tree; a built graph lands in `graphify-out/` (git-ignored).
14. **`icm-architect`** — ICM (Interpretable Context Methodology) workspace design: numbered folders as sequencing, hierarchy as context scoping, plain markdown as state, one agent per walk. Load it to design a folder-shaped agent workflow or audit a repo into a walkable map. Reference library vendored at [`docs/icm/`](docs/icm/README.md). It shapes **new** workspaces; it never restructures this repo's existing pipelines.
```

- [ ] **Step 3: Add the two missing `docs/` subtrees to the §2 tree**

Exact `old_text`:

```
│   ├── ads/                                 # 1 Ad Cover pipeline spec (1:1 1080x1080 + 9:16 Story 1080x1920)
│   ├── AUTO_POST_SCHEDULER.md               # Instagram auto-publish worker (external, cross-repo dependency)
```

Exact `new_text`:

```
│   ├── ads/                                 # 1 Ad Cover pipeline spec (1:1 1080x1080 + 9:16 Story 1080x1920)
│   ├── plans/                               # Implementation plans, one file each (live index in docs/README.md §7)
│   ├── icm/                                 # Vendored ICM reference library for the icm-architect skill (NOT a pipeline doc)
│   ├── AUTO_POST_SCHEDULER.md               # Instagram auto-publish worker (external, cross-repo dependency)
```

- [ ] **Step 4: Verify all three edits landed**

Run: `git -C "C:\Users\User\Desktop\marketing-automation" --no-pager diff --stat -- AGENTS.md`
Expected: `AGENTS.md | 7 ++++-` (2 tree lines inserted, 1 count swap, 2 entries appended).

Run: `Select-String -Path "C:\Users\User\Desktop\marketing-automation\AGENTS.md" -Pattern '14 version-controlled','13\. \*\*`graphify`','14\. \*\*`icm-architect`','docs/icm/' | Measure-Object`
Expected: `4` matches.

---

## Task 3: Register both skills in `docs/SKILLS_GUIDE.md`

**Files:**
- Modify: `docs/SKILLS_GUIDE.md:32` (append 2 table rows), `docs/SKILLS_GUIDE.md:85` (append 2 sections), `docs/SKILLS_GUIDE.md:91` (§3 provenance note)

**Interfaces:**
- Consumes: Task 2's exact skill names (`graphify`, `icm-architect`) — no renames.
- Produces: 2 rows in the general-skills table and 2 `###` sections. Task 5 reuses the phrase "vendored by hand" introduced here, so write it verbatim.

- [ ] **Step 1: Append the two rows to the general-skills table**

Exact `old_text`:

```
| **`systematic-debugging`** | [`.agents/skills/systematic-debugging`](../.agents/skills/systematic-debugging/SKILL.md) | General root-cause discipline (no fixes without investigation). Always paired with repo `debug-pipeline-run` for pipeline failures. |
```

Exact `new_text`:

```
| **`systematic-debugging`** | [`.agents/skills/systematic-debugging`](../.agents/skills/systematic-debugging/SKILL.md) | General root-cause discipline (no fixes without investigation). Always paired with repo `debug-pipeline-run` for pipeline failures. |
| **`graphify`** | [`.agents/skills/graphify`](../.agents/skills/graphify/SKILL.md) | Builds a queryable knowledge graph of this repo (code, docs, papers, images) with god nodes, community detection, and query/path/explain tools. Answers cross-file relational questions that grep-walking gets wrong or gets slowly. Outputs land in `graphify-out/` (git-ignored). |
| **`icm-architect`** | [`.agents/skills/icm-architect`](../.agents/skills/icm-architect/SKILL.md) | ICM workspace design and audit: numbered folders as sequencing, hierarchy as context scoping, markdown as state, one agent per walk. Reference library vendored at [`docs/icm/`](README.md). |
```

- [ ] **Step 2: Append the two §2 sections**

Exact `old_text`:

```
- **Pre-fix MD read order:** pipeline doc → `docs/memory/incidents/` → this skill + `debug-pipeline-run` → code.

---
```

Exact `new_text`:

```
- **Pre-fix MD read order:** pipeline doc → `docs/memory/incidents/` → this skill + `debug-pipeline-run` → code.

### `graphify`
- Used when a question spans many files ("what calls this", "what does changing X hit", "how do these docs relate"), or when `graphify-out/` already exists — then treat the question as a graphify query first.
- **Rule:** A graphify query beats reading the tree when the answer is relational rather than linear. Never commit the graph: `/graphify-out/` and `/.graphify*` are anchored in `.gitignore` so the skill's own `.agents/skills/graphify/.graphify_version` still ships.

### `icm-architect`
- Used when designing a new folder-driven agent workflow, or auditing a repo/folder/vault into a walkable map (objects, processes, change-impact).
- **Rule:** ICM shapes **new** workspaces. It never restructures this repo's pipelines, routes, or generators — those follow `AGENTS.md` §8 and the `add-new-pipeline` skill. The vendored reference library lives at `docs/icm/`; it is reference material, not documentation of anything this repo runs.

---
```

- [ ] **Step 3: Record the provenance in §3**

Exact `old_text`:

```
- **General skills:** to update one, run `npx skills add <owner/repo@skill> -y` from the repository root.
```

Exact `new_text`:

```
- **General skills:** to update one, run `npx skills add <owner/repo@skill> -y` from the repository root.
- **Hand-vendored skills:** `graphify` and `icm-architect` were dropped in by hand (not via `npx skills`), so they are absent from `skills-lock.json` and carry no content hash. Install them through the lockfile instead if a hash-pinned copy is ever wanted; see [`memory/decisions/2026-10-15-graphify-icm-vendored-skills.md`](memory/decisions/2026-10-15-graphify-icm-vendored-skills.md).
```

- [ ] **Step 4: Verify**

Run: `Select-String -Path "C:\Users\User\Desktop\marketing-automation\docs\SKILLS_GUIDE.md" -Pattern 'graphify','icm-architect' | Measure-Object`
Expected: at least `6` matches (2 table rows, 2 section headers, mentions in the §3 note).

Run: `Select-String -Path "C:\Users\User\Desktop\marketing-automation\docs\SKILLS_GUIDE.md" -Pattern '^### ' | Measure-Object`
Expected: `16` (was 14 — 12 per-skill sections plus the 2 group headers `### Repo workflow skills` / `### General skills`; now 14 per-skill sections plus the same 2 headers).

---

## Task 4: Add `docs/icm/` to the documentation navigation

**Files:**
- Modify: `docs/README.md` (§2 navigation tree), `docs/README.md:195` (false claim)

**Interfaces:**
- Consumes: Task 3 (the link target `docs/SKILLS_GUIDE.md` must already mention `icm-architect`).
- Produces: an `icm/` entry in the tree so the vendored library is discoverable, and a `docs/superpowers/` line that is actually true.

- [ ] **Step 1: Insert `icm/` into the navigation tree**

Exact `old_text`:

```
│   └── SALE_BANNER.md
│
└── memory/                              # Incidents, decisions, architecture notes (Obsidian vault)
```

Exact `new_text`:

```
│   └── SALE_BANNER.md
│
├── icm/                                 # Vendored ICM reference library (feeds the icm-architect skill; not a pipeline spec)
│
└── memory/                              # Incidents, decisions, architecture notes (Obsidian vault)
```

- [ ] **Step 2: Correct the false claim about `docs/superpowers/`**

`docs/README.md:195` currently reads "The old `docs/superpowers/` draft specs were removed 2026-10-05 (broken links cleaned)" — but `docs/superpowers/plans/2026-10-13-skill-upgrades-md-protocol.md` is still tracked in git (`git ls-files docs/superpowers` returns it).

Exact `old_text`:

```
> The old `docs/superpowers/` draft specs were removed 2026-10-05 (broken links cleaned).
```

Exact `new_text`:

```
> `docs/superpowers/` holds earlier draft specs kept for history. The live list is the table above (`docs/plans/`); broken links out of the old drafts were cleaned 2026-10-05.
```

- [ ] **Step 3: Verify the new path exists and the edit landed**

Run: `Test-Path "C:\Users\User\Desktop\marketing-automation\docs\icm\README.md"`
Expected: `True`

Run: `Select-String -Path "C:\Users\User\Desktop\marketing-automation\docs\README.md" -Pattern 'icm/','docs/superpowers/' | Measure-Object`
Expected: `2` matches.

---

## Task 5: Fix the stale `skills-lock.json` row in `README.md`

**Files:**
- Modify: `README.md:160`

**Interfaces:**
- Consumes: Task 3 §3 wording ("vendored by hand") — reuse it verbatim so the two files agree.
- Produces: a `skills-lock.json` description that matches the lockfile's real contents (2 pinned skills) and names the 2 unpinned ones.

- [ ] **Step 1: Confirm the lockfile contents before editing**

Run: `Get-Content "C:\Users\User\Desktop\marketing-automation\skills-lock.json" -Raw`
Expected: exactly two skills — `git-guardrails-claude-code` (mattpocock/skills) and `systematic-debugging` (obra/superpowers).

- [ ] **Step 2: Replace the row**

Exact `old_text`:

```
| `skills-lock.json` | Lockfile for the AI agent skills in `.agents/skills` (currently `git-guardrails-claude-code` from `mattpocock/skills`), pinned by content hash. |
```

Exact `new_text`:

```
| `skills-lock.json` | Lockfile for the AI agent skills in `.agents/skills` that were installed with `npx skills` — currently `git-guardrails-claude-code` (mattpocock/skills) and `systematic-debugging` (obra/superpowers), pinned by content hash. `graphify` and `icm-architect` are vendored by hand and therefore not hash-pinned here. |
```

- [ ] **Step 3: Verify**

Run: `Select-String -Path "C:\Users\User\Desktop\marketing-automation\README.md" -Pattern 'vendored by hand' | Measure-Object`
Expected: `1` match.

---

## Task 6: Write the decision note and cross-link it

**Files:**
- Create: `docs/memory/decisions/2026-10-15-graphify-icm-vendored-skills.md`
- Modify: `docs/README.md:187` (append the §6 row after the last row)

**Interfaces:**
- Consumes: Tasks 1–5 (the note describes what was actually registered).
- Produces: `docs/memory/decisions/2026-10-15-graphify-icm-vendored-skills.md`, referenced from `docs/SKILLS_GUIDE.md` §3 (Task 3) and `docs/README.md` §6.

Required by `AGENTS.md` §8: "A design decision that isn't obvious from the diff → a note in `docs/memory/decisions/`". Two such decisions exist here: hand-vendoring instead of a lockfile install, and parking a 1.6 MB third-party library inside `docs/`.

- [ ] **Step 1: Create the note with exactly this content**

Path: `C:\Users\User\Desktop\marketing-automation\docs\memory\decisions\2026-10-15-graphify-icm-vendored-skills.md`

````markdown
# graphify + icm-architect are vendored by hand (and `docs/icm/` is reference, not spec)

**Date:** 2026-10-15
**Status:** Accepted

## Decision

Two general agent skills were added to `.agents/skills/`:

- **`graphify`** (10 files) — builds a persistent knowledge graph of this repo with god nodes, community detection, and query/path/explain tools. For cross-file relational questions it replaces grep-walking.
- **`icm-architect`** (15 files, MIT) — ICM workspace design/audit: numbered folders as sequencing, hierarchy as context scoping, markdown as state, one agent per walk.

Neither was installed with `npx skills`, so neither appears in `skills-lock.json` and neither is hash-pinned. `docs/icm/` (190 files, ~1.6 MB — the ICM reference library including four `workspaces/` examples) was vendored alongside it as reading material.

## Why

Both skills arrived as complete drop-in folders with their own `LICENSE`, `README.md`, and `references/`. Re-deriving an `owner/repo@skill` locator for the lockfile would have meant inventing provenance we could not verify, and a fabricated `computedHash` is worse than no entry. Documenting the gap (in `docs/SKILLS_GUIDE.md` §3 and the `README.md` config table) is honest and reversible: `npx skills add` can pin them later without moving a file.

## Consequences

- `skills-lock.json` covers **only** `git-guardrails-claude-code` and `systematic-debugging`. Do not read the lockfile as the skill inventory; `AGENTS.md` §12 is.
- `docs/icm/` is reference material for the `icm-architect` skill. It documents **nothing this repo runs** — no pipeline reads it, and it is not part of the Story/Feed/Reel/Ad/Banner specs in `docs/README.md` §1–§4. Do not treat its `workspaces/*/` examples as HomeCartel conventions.
- `icm-architect` designs **new** folder-shaped workspaces. It never restructures existing pipelines, routes, or generators — those follow `AGENTS.md` §8 and the `add-new-pipeline` skill.
- `graphify` writes `graphify-out/` and `.graphify*`. Both `.gitignore` patterns are **anchored** (`/graphify-out/`, `/.graphify*`) because the unanchored form also matched `.agents/skills/graphify/.graphify_version` and silently dropped it from commits — which would have shipped a skill missing its version marker on every push.

## Related

- Plan: [`docs/plans/2026-10-15-skills-registration-md-sync.md`](../../plans/2026-10-15-skills-registration-md-sync.md)
- Skill inventory: [`AGENTS.md` §12](../../../AGENTS.md), [`docs/SKILLS_GUIDE.md`](../../SKILLS_GUIDE.md)
````

- [ ] **Step 2: Add the §6 row to `docs/README.md`**

Exact `old_text` (the last row of the §6 table, line 187):

```
| [`memory/incidents/2026-10-05-tag-line2-anchor-fallback.md`](memory/incidents/2026-10-05-tag-line2-anchor-fallback.md) | Tag Line-2 lost when Product Type field empty (anchor handoff) + Floor Lamp Moodboard Story registry `KeyError`; fixed by shared `resolve_tag_names`. |
```

Exact `new_text`:

```
| [`memory/incidents/2026-10-05-tag-line2-anchor-fallback.md`](memory/incidents/2026-10-05-tag-line2-anchor-fallback.md) | Tag Line-2 lost when Product Type field empty (anchor handoff) + Floor Lamp Moodboard Story registry `KeyError`; fixed by shared `resolve_tag_names`. |
| [`memory/decisions/2026-10-15-graphify-icm-vendored-skills.md`](memory/decisions/2026-10-15-graphify-icm-vendored-skills.md) | Why `graphify` and `icm-architect` are vendored by hand (absent from `skills-lock.json`), what each is for, why `docs/icm/` is reference material rather than a pipeline spec, and why the graphify `.gitignore` patterns must stay anchored. |
```

- [ ] **Step 3: Verify both files**

Run: `Test-Path "C:\Users\User\Desktop\marketing-automation\docs\memory\decisions\2026-10-15-graphify-icm-vendored-skills.md"`
Expected: `True`

Run: `Select-String -Path "C:\Users\User\Desktop\marketing-automation\docs\README.md" -Pattern '2026-10-15-graphify-icm-vendored-skills' | Measure-Object`
Expected: `1` match.

---

## Task 7: Register this plan and verify the whole docs sync

**Files:**
- Modify: `docs/README.md:193` (append the §7 row)

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: this plan listed in the live plan index, and a green verification report.

- [ ] **Step 1: Add this plan to the `docs/plans/` table**

Exact `old_text` (the only existing row, line 193):

```
| [`plans/2026-10-05-calendar-import.md`](plans/2026-10-05-calendar-import.md) | Content Calendar XLSX → Studio queue import (implemented: `content_automation/calendar_import.py`, `UI Control/routes/calendar.py`, `scripts/ops/import_content_calendar.py`). |
```

Exact `new_text`:

```
| [`plans/2026-10-05-calendar-import.md`](plans/2026-10-05-calendar-import.md) | Content Calendar XLSX → Studio queue import (implemented: `content_automation/calendar_import.py`, `UI Control/routes/calendar.py`, `scripts/ops/import_content_calendar.py`). |
| [`plans/2026-10-15-skills-registration-md-sync.md`](plans/2026-10-15-skills-registration-md-sync.md) | Register `graphify` + `icm-architect` in `AGENTS.md` §12 and `docs/SKILLS_GUIDE.md`, add `docs/icm/` to the docs navigation, fix the stale `skills-lock.json` row, and anchor the graphify `.gitignore` patterns. Docs-only. |
```

- [ ] **Step 2: Run the test suite (must stay green)**

Run: `cd "C:\Users\User\Desktop\marketing-automation"; python -m unittest discover tests`
Expected: `OK`. No `.py` was touched, so any failure means an unintended edit — stop and find it.

- [ ] **Step 3: Verify every doc claim against the filesystem**

Run as one command:

```powershell
cd "C:\Users\User\Desktop\marketing-automation"
"skills on disk      : " + (Get-ChildItem .agents/skills -Directory).Count
"icm untracked files : " + (git ls-files --others --exclude-standard docs/icm).Count
"graphify version ign: " + (git check-ignore -v ".agents/skills/graphify/.graphify_version" | Measure-Object).Count
"staged under agents : " + (git add -An .agents | Measure-Object -Line)
"lock skills         : " + ((Get-Content skills-lock.json -Raw | ConvertFrom-Json).skills.PSObject.Properties.Name -join ', ')
```

Expected:

```text
skills on disk      : 14
icm untracked files : 190
graphify version ign: 0
staged under agents : 25
lock skills         : git-guardrails-claude-code, systematic-debugging
```

These five numbers are exactly the claims written into `AGENTS.md` §12, the decision note, and the `README.md` config table. If a line disagrees, fix the doc — do not adjust the number.

- [ ] **Step 4: Placeholder scan**

Run: `Select-String -Path "C:\Users\User\Desktop\marketing-automation\AGENTS.md","C:\Users\User\Desktop\marketing-automation\docs\SKILLS_GUIDE.md","C:\Users\User\Desktop\marketing-automation\docs\README.md","C:\Users\User\Desktop\marketing-automation\README.md","C:\Users\User\Desktop\marketing-automation\docs\memory\decisions\2026-10-15-graphify-icm-vendored-skills.md" -Pattern 'TBD|TODO|FIXME' | Measure-Object`
Expected: `0` matches in the lines this plan added (pre-existing hits elsewhere in the repo are out of scope).

- [ ] **Step 5: Secret / artifact scan before any commit**

Run: `cd "C:\Users\User\Desktop\marketing-automation"; git status --porcelain`
Expected: modified `.gitignore`, `AGENTS.md`, `README.md`, `docs/README.md`, `docs/SKILLS_GUIDE.md`; untracked `.agents/skills/graphify/`, `.agents/skills/icm-architect/`, `docs/icm/`, `docs/plans/2026-10-15-skills-registration-md-sync.md`, `docs/memory/decisions/2026-10-15-graphify-icm-vendored-skills.md`. **No** `.env*`, `output/`, `graphify-out/`, `node_modules/`, or `UI Control/dist/`.

- [ ] **Step 6: Stop and report — do not commit unless asked**

Report the Step 3 verification block to the user and ask whether to commit. Per `AGENTS.md` §11, commit/push only on explicit request, and never push `main` (live Railway deploy) without telling the user first.

---

## Self-Review

1. **Spec coverage (`AGENTS.md` §8):**
   - "An agent skill (added, removed, or repurposed) → this file §12 and `docs/SKILLS_GUIDE.md`" → Tasks 2 and 3. Covered.
   - "A design decision that isn't obvious from the diff → `docs/memory/decisions/`" → Task 6 (hand-vendoring + the 1.6 MB vendored library). Covered.
   - "A new pipeline / subtab" → **not applicable**; no pipeline, route, fixture, or env key was added, so `.env.example` and `foreign_key.py` are correctly untouched.
   - "A new env key or table ID" → not applicable.
   - `docs/README.md` is not named in the §8 table, but it is the navigation index that §8 exists to keep trustworthy, and `docs/icm/` would otherwise be an undocumented 1.6 MB subtree → Task 4. Covered.
2. **Placeholder scan:** every step carries an exact command or an exact `old_text`/`new_text` pair. No TBD/TODO, no "similar to Task N", no "insert your values here".
3. **Type consistency:** skill names `graphify` / `icm-architect` are identical in `AGENTS.md`, `docs/SKILLS_GUIDE.md`, the decision note, and `README.md`. The phrase "vendored by hand" is shared deliberately between `docs/SKILLS_GUIDE.md` §3 and `README.md`. Commands use absolute paths; markdown links stay repo-relative to match existing convention (e.g. `../.agents/skills/...` from `docs/`).
4. **Count arithmetic:** `AGENTS.md` §12 → 14 skills; `docs/SKILLS_GUIDE.md` general-skills table → 8 rows (was 6); SKILLS_GUIDE `###` headings → 16 (was 14: 12 per-skill + 2 group headers, now 14 + 2); staged files under `.agents/` → 25 (was 24). All asserted in verification steps.
5. **Ordering:** Task 1 is deliberately first and blocking — Tasks 2 and 3 write prose asserting `.agents/skills/` is git-safe, which is false until the ignore patterns are anchored.
6. **TDD note:** intentionally skipped. `AGENTS.md` §9's suite is `python -m unittest discover tests`; there is no `.py` change and no behavior to drive out. Step 2 of Task 7 runs the suite as a regression guard instead of fabricating a test for markdown.

