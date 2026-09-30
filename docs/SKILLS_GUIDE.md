# HomeCartel Marketing Automation -- Integrated Skills Guide

> **Location:** `.agents/skills/`  
> This directory contains curated agent skills integrated directly into the workspace. Any AI agent (Antigravity, Claude Code, Cursor, Copilot) operating on this repository automatically inherits these skills.

---

## 1. Summary of Workspace Skills

| Skill | Directory | Primary Purpose in this Repo |
| :--- | :--- | :--- |
| **`airtable-automation`** | [`.agents/skills/airtable-automation`](file:///c:/Users/User/Desktop/marketing-automation/.agents/skills/airtable-automation/SKILL.md) | Airtable slot-based schema rules, batch updates (10-per-call), and `update_record` convenience patterns across 60+ tables. |
| **`prompt-optimizer`** | [`.agents/skills/prompt-optimizer`](file:///c:/Users/User/Desktop/marketing-automation/.agents/skills/prompt-optimizer/SKILL.md) | Structured JSON prompt engineering for Claude Sonnet 5 Vision analysis (Phase 3 in Stories/Feeds/Reels) and Krea moodboard prompts. |
| **`python-testing-patterns`** | [`.agents/skills/python-testing-patterns`](file:///c:/Users/User/Desktop/marketing-automation/.agents/skills/python-testing-patterns/SKILL.md) | Unittest suite organization, test isolation, mocking external AI APIs (Akeneo, Fal, Krea), and pre-commit checks. |
| **`vercel-react-best-practices`** | [`.agents/skills/vercel-react-best-practices`](file:///c:/Users/User/Desktop/marketing-automation/.agents/skills/vercel-react-best-practices/SKILL.md) | React component optimization, hook composition (`usePipelineData`, `usePipelineRunner`, `useQueue`), and eliminating unnecessary re-renders in Web Studio. |
| **`vite`** | [`.agents/skills/vite`](file:///c:/Users/User/Desktop/marketing-automation/.agents/skills/vite/SKILL.md) | Production Vite bundling (`UI Control/dist/`), asset hashing, and client-side SPA routing integration with Flask. |
| **`git-guardrails-claude-code`** | [`.agents/skills/git-guardrails-claude-code`](file:///c:/Users/User/Desktop/marketing-automation/.agents/skills/git-guardrails-claude-code/SKILL.md) | Intercepts and blocks destructive git operations (`git push --force`, `git reset --hard`, accidental wipeouts). |

---

## 2. How to Use Each Skill

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
To update any workspace skill, run:
```bash
npx skills add <owner/repo@skill> -y
```
from the repository root. Git will track changes to `.agents/skills/` while ignoring temporary IDE configs.
