# HomeCartel Marketing Automation -- Integrated Skills Guide

> **Location:** `.agents/skills/`  
> This directory contains curated agent skills integrated directly into the workspace. Any AI agent (Antigravity, Claude Code, Cursor, Copilot) operating on this repository automatically inherits these skills.

There are two kinds. **Repo workflow skills** hold procedures specific to this codebase that used to live inline in `AGENTS.md`. **General skills** were installed from external sources (tracked in `skills-lock.json` when installed via `npx skills`).

---

## 1. Summary of Workspace Skills

### Repo workflow skills

| Skill | Directory | Load it when… |
| :--- | :--- | :--- |
| **`add-new-pipeline`** | [`.agents/skills/add-new-pipeline`](../.agents/skills/add-new-pipeline/SKILL.md) | Adding a pipeline, Studio subtab, Airtable table, or fixture (including Ad Cover fixtures). |
| **`ship-to-railway`** | [`.agents/skills/ship-to-railway`](../.agents/skills/ship-to-railway/SKILL.md) | The user asks to commit, push, or deploy. |
| **`debug-pipeline-run`** | [`.agents/skills/debug-pipeline-run`](../.agents/skills/debug-pipeline-run/SKILL.md) | A run fails, hangs, flickers, skips a phase, or produces wrong output. |
| **`pillow-layout`** | [`.agents/skills/pillow-layout`](../.agents/skills/pillow-layout/SKILL.md) | Building or changing any text, logo, watermark, pill, or name-tag layout. |
| **`fresh-row-scrape`** | [`.agents/skills/fresh-row-scrape`](../.agents/skills/fresh-row-scrape/SKILL.md) | Touching scrape phases, product selection, Shopify checks, or dedup, or tempted to reprocess old rows. |

### General skills

| Skill | Directory | Primary Purpose in this Repo |
| :--- | :--- | :--- |
| **`airtable-automation`** | [`.agents/skills/airtable-automation`](../.agents/skills/airtable-automation/SKILL.md) | Airtable slot-based schema rules, batch updates (10-per-call), and `update_record` convenience patterns across 60+ tables. |
| **`prompt-optimizer`** | [`.agents/skills/prompt-optimizer`](../.agents/skills/prompt-optimizer/SKILL.md) | Structured JSON prompt engineering for Claude Sonnet 5 Vision analysis (Phase 3 in Stories/Feeds/Reels) and Krea moodboard prompts. |
| **`python-testing-patterns`** | [`.agents/skills/python-testing-patterns`](../.agents/skills/python-testing-patterns/SKILL.md) | Unittest suite organization, test isolation, mocking external AI APIs (Akeneo, Fal, Krea), and pre-commit checks. |
| **`vercel-react-best-practices`** | [`.agents/skills/vercel-react-best-practices`](../.agents/skills/vercel-react-best-practices/SKILL.md) | React component optimization, hook composition (`usePipelineData`, `usePipelineRunner`, `useQueue`), and eliminating unnecessary re-renders in Web Studio. |
| **`vite`** | [`.agents/skills/vite`](../.agents/skills/vite/SKILL.md) | Production Vite bundling (`UI Control/dist/`), asset hashing, and client-side SPA routing integration with Flask. |
| **`git-guardrails-claude-code`** | [`.agents/skills/git-guardrails-claude-code`](../.agents/skills/git-guardrails-claude-code/SKILL.md) | Intercepts and blocks destructive git operations (`git push --force`, `git reset --hard`, accidental wipeouts). |

---

## 2. How to Use Each Skill

### `add-new-pipeline`
- Used for any new generator, Studio subtab, table ID, or fixture.
- **Rule:** Wire every layer (generator, `TABLE_PREFIX_MAP`, blueprint + `api_server.py`, `fixtures.ts`/`pipelines.ts`/`types`, build) and update the docs in the AGENTS.md §8 table in the same commit.

### `ship-to-railway`
- Used only when the user asks to commit, push, or deploy.
- **Rule:** Push `marketing-automation` freely after checks. Pushing `main` is a live Railway deploy, so confirm with the user first and fast-forward only. Full detail in [`GIT_PUSH_AND_DEPLOY.md`](GIT_PUSH_AND_DEPLOY.md).

### `debug-pipeline-run`
- Used when a Studio or CLI run misbehaves.
- **Rule:** Check `docs/memory/incidents/` first, reproduce with `--record-id` (never by sweeping old rows), add a regression test, and write an incident note if it took real investigation.

### `pillow-layout`
- Used when editing `content_automation/overlay.py`, `item_tagger.py`, or any final-layout phase.
- **Rule:** Typography, logos, and watermarks are local Pillow only. Image models never render layout text.

### `fresh-row-scrape`
- Used when editing `content_automation/scraping/`, `shopify_client.py`, `akeneo_client.py`, or any Phase 1 scrape.
- **Rule:** New row every run. Exact SKU/title Shopify match only. Base-wide dedup. Never overwrite the Shopify cache with a partial crawl.

### `git-guardrails-claude-code`
- Used whenever running git commands or automating git pushes.
- **Rule:** Blocks destructive commands like `git push --force`, `git reset --hard`, or indiscriminate file additions. Keeps deployments strictly aligned with [`docs/GIT_PUSH_AND_DEPLOY.md`](GIT_PUSH_AND_DEPLOY.md).

### `airtable-automation`
- Used whenever modifying `content_automation/airtable_client.py`, `content_automation/scraping/airtable.py`, or any pipeline's Airtable writes.
- **Rule:** Never exceed 10 records per PATCH call. Use `current_pht_timestamp()` when writing `Date and Time Generated`. Maintain Foreign Key ID conventions (`FK-FORMAT-CODE-ID`).

### `prompt-optimizer`
- Used in Phase 3 of all generator monoliths (`generate_*_pipeline.py`).
- **Rule:** Instruct Claude Vision to return clean JSON without markdown code fences. Structure user prompts with explicit key definitions (`blending_prompt`, `reel_headline`).

### `python-testing-patterns`
- Used whenever adding new pipelines, routes, or FK prefixes.
- **Rule:** Run `python -m unittest discover -s tests -p "test_*.py"` to test isolated units. Verify client credentials and mocks before pushing code.

### `vercel-react-best-practices`
- Used when editing `UI Control/src/app/` (`App.tsx`, hooks, components, modals).
- **Rule:** Separate stateful logic into custom hooks (`usePipelineData`, `usePipelineRunner`, `useQueue`). Keep components pure and memoize expensive derivations.

### `vite`
- Used whenever rebuilding Web Studio assets (`npm run build` in `UI Control/`).
- **Rule:** Always verify that `UI Control/dist/index.html` references the newly hashed JS bundle (`index-[hash].js`) before committing.

---

## 3. Maintenance & Updates

- **General skills:** to update one, run `npx skills add <owner/repo@skill> -y` from the repository root.
- **Repo workflow skills:** edit the `SKILL.md` directly. When the procedure it describes changes (e.g. a new deploy step), update the skill in the same commit and follow the AGENTS.md §8 "Docs to update" table.

Git tracks changes to `.agents/skills/` while ignoring temporary IDE configs.
