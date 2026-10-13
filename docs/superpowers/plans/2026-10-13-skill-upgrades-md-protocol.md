# Generic Skill Upgrades + Mandatory MD Pre-Read Protocol — PART 1: Audit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 2 mismatched generic skills and enforce an MD pre-read protocol before every automation fix.

**Architecture:** Swap `prompt-optimizer` (wrong skill: ECC prompt rewriting, not Claude/Krea tuning) for `anthropic-claude-development` or equivalent; replace `python-testing-patterns` (pytest-only) with a unittest-matched skill or rewrite as repo skill. Add `systematic-debugging` as 13th skill. Enforce pre-fix MD reads via `AGENTS.md` §10 + skill-invocation rules.

**Tech Stack:** Agent skills, Markdown docs, unittest, Airtable, Claude/Krea/Fal APIs.

**Spec:** `docs/SKILLS_GUIDE.md` (11 skills: 5 repo + 6 general), `AGENTS.md` §8/§10/§11/§12, `docs/memory/README.md`.

## Global Constraints

- `.env`/secrets never staged. Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).
- `marketing-automation` = dev branch; `main` = live Railway deploy.
- No force-push, reset-hard, amend/rebase on pushed commits.
- Repo skills (`ship-to-railway`, `git-guardrails`) always override generic git skills on conflict.

---

## Audit: 6 General Skills (evidence from SKILL.md reads 2026-10-13)

| # | Skill | Verdict | Evidence |
|---|---|---|---|
| 1 | `airtable-automation` (claude-office-skills, 5.8K installs) | KEEP | SKILL.md covers views/automations/n8n — generic but no better alternative (official `airtable/skills` only 260 installs). Repo usage layer already in `SKILLS_GUIDE.md` §2 (10-per-call, PHT, FK). |
| 2 | `prompt-optimizer` (YannJY02 ECC, advisory-only) | REPLACE | SKILL.md says: "advisory only, never executes... match ECC commands... not for code". Repo needs Claude Sonnet 5 Vision JSON + Krea tuning. Zero overlap. |
| 3 | `python-testing-patterns` (pytest) | REPLACE | SKILL.md teaches pytest (`pytest test_example.py`, fixtures, markers). Repo runs `python -m unittest discover tests` stdlib. Mismatch causes wrong test commands. |
| 4 | `vercel-react-best-practices` (vercel-labs, 793.9K installs) | KEEP | Most-installed React skill in ecosystem. Matches `usePipelineData/usePipelineRunner/useQueue`. No better alternative. |
| 5 | `vite` (antfu, 37.8K installs) | KEEP | Matches `UI Control/dist/` build. No better alternative. |
| 6 | `git-guardrails-claude-code` | KEEP | Blocks destructive git. Complements (not replaced by) `git-workflow-and-versioning`. |

Missing skill: systematic debugging (`obra/superpowers@systematic-debugging`, 289.7K installs) — ADD as 13th skill alongside repo `debug-pipeline-run`.

(Part 2: tasks — in next chunk.)

### Task 1: Replace `prompt-optimizer` with Claude-aligned skill

**Files:**
- Remove: `.agents/skills/prompt-optimizer/SKILL.md`
- Create: `.agents/skills/claude-prompt-dev/SKILL.md` (new or installed)
- Modify: `docs/SKILLS_GUIDE.md` (table row + section 2 entry), `AGENTS.md` §12 entry 7
- Test: `python -m unittest discover tests` still passes (docs-only change)

**Interfaces:**
- Consumes: ecosystem candidates — `mindrally/skills@anthropic-claude-development` (711 installs), `jamesrochabrun/skills@anthropic-prompt-engineer` (221 installs), `davila7/claude-code-templates@prompt-caching` (434 installs)
- Produces: `.agents/skills/claude-prompt-dev/SKILL.md` teaching Claude Sonnet 5 Vision JSON output (no markdown fences), explicit key definitions (`blending_prompt`, `reel_headline`), Krea moodboard prompt tuning

- [ ] **Step 1: Evaluate the 3 candidates**

Run: `npx -y skills find anthropic claude development`
Expected: compare installs, source reputation (prefer official/known authors over under-100-star repos), SKILL.md relevance to Vision JSON + Krea prompts

- [ ] **Step 2: Install the winner under a repo-stable name**

Run: `npx skills add <owner/repo@skill> -y`
Expected: new directory under `.agents/skills/` with SKILL.md

- [ ] **Step 3: Normalize directory to `claude-prompt-dev` if needed**

Run: `Move-Item .agents/skills/<installed-name> .agents/skills/claude-prompt-dev`
Expected: `.agents/skills/claude-prompt-dev/SKILL.md` exists

- [ ] **Step 4: Remove the old ECC skill**

Run: `Remove-Item -Recurse -Force .agents/skills/prompt-optimizer`
Expected: directory gone

- [ ] **Step 5: Update `docs/SKILLS_GUIDE.md` table row + section 2 entry**

Replace the `prompt-optimizer` row text with the new skill name, directory link, and purpose: Claude Sonnet 5 Vision JSON + Krea moodboard prompt tuning. Replace the `### prompt-optimizer` section with a `### claude-prompt-dev` section carrying the same Rule lines (clean JSON, explicit keys).
Expected: `Select-String -Path docs/SKILLS_GUIDE.md -Pattern "prompt-optimizer"` returns no match

- [ ] **Step 6: Update `AGENTS.md` section 12 entry 7**
### Task 2: Replace `python-testing-patterns` (pytest) with unittest version

**Files:**
- Modify: `.agents/skills/python-testing-patterns/SKILL.md` (rewrite), delete stale `references/` if pytest-only
- Modify: `docs/SKILLS_GUIDE.md` row + section, `AGENTS.md` §12 entry 8
- Test: `python -m unittest discover tests` passes

**Interfaces:**
- Consumes: 2026-10-13 search showed NO unittest skill worth installing (all candidates under 100 installs). Decision: rewrite in place.
- Produces: SKILL.md teaching `python -m unittest discover tests`, `unittest.mock` for Akeneo/Fal/Krea, `py_compile` gate

- [ ] **Step 1: Confirm no candidate beats a rewrite**

Run: `npx -y skills find python unittest stdlib`
Expected: nothing over 1K installs from a reputable source — confirms rewrite

- [ ] **Step 2: Rewrite the SKILL.md for unittest**

Teach: stdlib unittest (not pytest), `unittest.mock.patch` for external clients, `py_compile` gate, `tests/test_*.py` convention. Delete pytest-only reference files.
Expected: `Select-String -Path .agents/skills/python-testing-patterns/SKILL.md -Pattern "pytest"` returns no match

- [ ] **Step 3: Update docs + commit**

Update `docs/SKILLS_GUIDE.md` row + Rule line to unittest. Then:
Run: `python -m unittest discover tests` (Expected: OK)
Run: `git add -A -- .agents/skills/python-testing-patterns docs/SKILLS_GUIDE.md AGENTS.md`
Run: `git commit -m "chore(skills): rewrite python-testing-patterns for stdlib unittest"`

---


Replace the `prompt-optimizer` list line with the new skill name + one-line purpose.
Expected: `Select-String -Path AGENTS.md -Pattern "prompt-optimizer"` returns no match

- [ ] **Step 7: Run tests and commit**
### Task 3: Add `systematic-debugging` (keep repo `debug-pipeline-run`)

**Files:**
- Create: `.agents/skills/systematic-debugging/SKILL.md` via `npx skills add obra/superpowers@systematic-debugging -y` (289.7K installs)
- Modify: `docs/SKILLS_GUIDE.md` (row + section), `AGENTS.md` §12 (count + entry)
- Test: suite passes (docs-only)

**Interfaces:**
- Consumes: `obra/superpowers@systematic-debugging` (alts: `mattpocock/skills@diagnosing-bugs` 768.2K, `addyosmani/agent-skills@debugging-and-error-recovery` 52.3K)
- Produces: installed skill; repo `debug-pipeline-run` stays as pipeline triage layer on top

- [ ] **Step 1: Install**

Run: `npx skills add obra/superpowers@systematic-debugging -y`
Expected: `.agents/skills/systematic-debugging/SKILL.md` exists

- [ ] **Step 2: Register in docs**

Add table row (purpose: general root-cause discipline) + `### systematic-debugging` section with Rule: always pair with repo `debug-pipeline-run` (check `docs/memory/incidents/` first, reproduce via `--record-id`, never sweep old rows).
Expected: 2 matches for `systematic-debugging` in SKILLS_GUIDE.md

- [ ] **Step 3: Register in AGENTS.md §12 + commit**

Bump count, append entry. Then `python -m unittest discover tests` (OK), `git add -A -- .agents/skills/systematic-debugging docs/SKILLS_GUIDE.md AGENTS.md`, `git commit -m "chore(skills): add systematic-debugging workspace skill"`

---

### Task 4: Enforce Mandatory MD Pre-Read Protocol

**Files:**
- Modify: `AGENTS.md` (§10 — append checklist), `docs/SKILLS_GUIDE.md` (`debug-pipeline-run` section — append read order)
- Test: manual — next fix shows the read order in tool calls

**Interfaces:**
- Consumes: Tasks 1-3 (final skill set), `docs/memory/README.md` layout
- Produces: written protocol every agent follows before touching code

- [ ] **Step 1: Append checklist to `AGENTS.md` §10**

Insert after the memory protocol paragraph:
```markdown
**Pre-fix MD read order (mandatory before any automation change):**
1. `AGENTS.md` (always loaded). 2. The ONE pipeline doc touched (`docs/stories|feeds|reels|ads|banners/*.md`). 3. `docs/memory/incidents/` — search symptom first. 4. The matching skill. 5. Only then: read code, reproduce with `--record-id`, implement, test, commit.
```

- [ ] **Step 2: Append read order to `debug-pipeline-run` section**

Append to its Rule: `Read order: pipeline doc, then docs/memory/incidents/, then this skill, then code.`
Expected: section contains `Read order:`

- [ ] **Step 3: Commit**

Run: `git add AGENTS.md docs/SKILLS_GUIDE.md`
Run: `git commit -m "docs: enforce mandatory MD pre-read protocol before automation fixes"`

---

## Self-Review

1. **Spec coverage:** Task 1 (prompt-optimizer), Task 2 (pytest skill), Task 3 (systematic-debugging), Task 4 (pre-read protocol). KEEPs need no task. No gaps.
2. **Placeholder scan:** exact paths/commands/expected outputs everywhere. No TBD/TODO.
3. **Type consistency:** names (`claude-prompt-dev`, `systematic-debugging`), paths, commit prefixes identical across tasks.

---

Plan complete and saved to `docs/superpowers/plans/2026-10-13-skill-upgrades-md-protocol.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks

**2. Inline Execution** — execute in this session with checkpoints

**Which approach?**


Run: `python -m unittest discover tests`
Expected: OK
Run: `git add -A -- .agents/skills/claude-prompt-dev .agents/skills/prompt-optimizer docs/SKILLS_GUIDE.md AGENTS.md`
Run: `git commit -m "chore(skills): replace ECC prompt-optimizer with Claude-aligned skill"`

---
