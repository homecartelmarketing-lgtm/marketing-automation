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
