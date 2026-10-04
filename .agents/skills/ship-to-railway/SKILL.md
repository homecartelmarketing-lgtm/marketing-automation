---
name: ship-to-railway
description: Use when the user asks to commit, push, or deploy this repo. Runs the pre-push checks, pushes marketing-automation, and only fast-forwards main (a live Railway deploy) after the user confirms.
---

# Commit, Push and Deploy

Railway deploys `main` on every push, so pushing `main` is pressing the production button. Everything here exists so that push only ever happens on purpose and with code that compiles. The full walkthrough, with failure handling, is `docs/GIT_PUSH_AND_DEPLOY.md`. Read it the first time you ship in a session.

Only commit or push when the user asks. Finishing a task is not a request to push.

## Sequence

0. **Pre-flight.** Run `git remote -v` (it must be `homecartelmarketing-lgtm/marketing-automation`), `git branch --show-current` (expect `marketing-automation`), `git fetch origin` and `git status --short`. If the remote branch is ahead of you, stop and ask.
1. **Secrets and stray files.** `.env` must be ignored (`git check-ignore -v .env`). Never stage `.env*` except `*.example`, keys, tokens, model weights or customer data. If there is an untracked file you can't explain (spreadsheets, dumps, CSVs), list it and ask instead of adding it.
2. **Compile and test.** Run `python -m py_compile <every changed .py>` and `python -m unittest discover tests`. If anything fails, stop. Your machine runs Python 3.12 but the container runs 3.11, so mention the risk if you used very new syntax.
3. **Frontend.** If anything under `UI Control/src/` changed, run `cd "UI Control" && npm run build` (it must exit 0), then `git add -A -- "UI Control/dist"` so the new hashed files and the deleted old ones are both staged.
4. **Docs.** Apply the AGENTS.md §8 "Docs to update" table.
5. **Stage named paths**, not `git add .`, then review `git diff --cached --stat` and re-scan the staged diff for secrets.
6. **Commit** with a conventional prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`) and an optional scope, e.g. `fix(moodboard-reel): ...`.
7. **Push the dev branch.** `git push origin marketing-automation`. This is safe and does not deploy.
8. **Deploy, only after the user says go** (unless they already asked for a deploy). Say: "Ready to fast-forward main and push. This triggers a Railway deploy. Go ahead?" Then:
   ```bash
   git fetch origin
   git checkout main
   git merge --ff-only marketing-automation
   git push origin main
   git checkout marketing-automation
   ```
   If `--ff-only` refuses, `main` moved, so stop and report it. Always switch back to `marketing-automation`, even after a failure.
9. **After deploy.** Ask the user to check `https://<railway-url>/api/health` (it should return `"status": "ok"` and the module list). If the build fails, ask for the Railway build log, because you can't see it.

## Hard lines

These protect work you can't recover or a live site:

- No `--force`/`--force-with-lease`, no `reset --hard`, no `--amend` or rebase on pushed commits, no `--no-verify`.
- To undo a bad deploy, use `git revert <commit>` and push, or Railway's "redeploy previous deployment". Never reset and force-push.
- Don't edit `.github/workflows/product_closeup_reel.yml` or its secrets unless asked. It runs whatever is on `marketing-automation` when triggered manually.
- The `git-guardrails-claude-code` skill blocks the destructive commands. Don't work around it.
