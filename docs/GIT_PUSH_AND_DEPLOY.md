# How the AI Pushes to GitHub (and Deploys to Railway)

This guide says exactly what an AI agent (Claude Code, or any other) will do when you ask it to commit and push this repository, step by step, so you know what to expect before you say "push it". It expands the short rule list in [`AGENTS.md`](../AGENTS.md) §11.

**Read this if you are:** the person asking the AI to push, or an AI agent about to push.

---

## 1. At a glance

- The AI **only commits or pushes when you ask.** Finishing a task does not push anything.
- You work on branch **`genspark_ai_developer`**. Railway deploys branch **`main`**. So a push to `main` is a **live production deploy**.
- The AI runs its checks first, then commits, then pushes `genspark_ai_developer`. **Before it pushes `main`, it tells you it is about to deploy and waits for your go-ahead** (unless you already said "push and deploy to main").
- It never force-pushes, never rewrites pushed history, never skips hooks, and never commits `.env` or other secrets.
- If any check fails, it stops and tells you. It does not push around a failure.

```
your working tree
   │  0. pre-flight (remote, branch, fetch, status)
   │  1. secret + stray-file check
   │  2. compile (py_compile) + unit tests
   │  3. rebuild frontend if UI Control/src changed
   │  4. docs check
   │  5. stage named files → review
   │  6. commit (conventional message)
   ▼
git push origin genspark_ai_developer        ← safe: does not deploy
   │  8. YOU confirm
   ▼
git merge --ff-only  →  git push origin main  ← triggers Railway build + deploy
   ▼
Railway builds the Dockerfile → gunicorn starts → GET /api/health
```

---

## 2. What the AI will and will not do

| The AI **will** | The AI **will never** |
| :--- | :--- |
| Run read-only checks (`git status`, `git fetch`, `git diff`, `git log`) | Force-push (`--force`, `--force-with-lease`) |
| Compile every modified `.py` file and run the unit tests | `git reset --hard`, `git checkout -- .`, or delete your uncommitted work |
| Rebuild `UI Control/dist/` when `UI Control/src/` changed | Amend or rebase commits that are already pushed |
| Stage **named files** after reviewing `git status` | Use `--no-verify` or bypass signing/hooks |
| Commit with a conventional message (`feat:`, `fix:`, `docs:` …) | Stage or commit `.env`, `.env.*` (except `*.example`), keys, tokens, customer data |
| Push `genspark_ai_developer` | Push `main` without telling you it is a production deploy |
| Push `main` by fast-forward only, after your go-ahead | Run git from a different folder (e.g. `Downloads/Marketing Output UI`) |
| Stop and report if anything looks wrong | Commit a stray file it can't explain (it asks you first) |

---

## 3. The setup this repo has (why the steps are what they are)

| Item | What it is | Why it matters |
| :--- | :--- | :--- |
| Remote | `origin` = `https://github.com/homecartelmarketing-lgtm/marketing-automation.git` | The AI checks this before any git command; if it differs, it stops. |
| Branches | Work on `genspark_ai_developer`; `main` is deployed | Two pushes are needed to ship. |
| Branch state (when this guide was written) | `main`, `genspark_ai_developer`, `origin/main`, `origin/genspark_ai_developer` were all the same commit, 0 ahead / 0 behind | The `main` fast-forward is clean *only if* `main` hasn't moved. The AI re-checks every time. |
| Railway | Builds the repo's `Dockerfile` on each push to `main` (per AGENTS.md §11). There is no `railway.json` or `Procfile` in the repo. | The push to `main` *is* the deploy button. |
| Docker image | `python:3.11-slim`, apt `ffmpeg`/`libgl1`/`libsndfile1`/`git`, `pip install -r requirements.txt`, then Ultralytics CLIP from GitHub (needed by YOLO-World name tagging; `git` is why it is in the apt list), pre-caches the YOLO weights, copies the whole repo, runs `gunicorn --workers 1 --threads 8` from `UI Control/` (one worker: queue state is in memory) | Your PC runs Python 3.12; the container runs 3.11. Compiling on 3.12 does not fully prove the container starts. |
| `UI Control/dist/` | The compiled React UI. **Tracked in git** (whitelisted in `.gitignore`) and copied into the image | If `src/` changes but `dist/` isn't rebuilt and committed, Railway serves the *old* UI. Old hashed files being deleted and new ones added must both be staged. |
| `.gitignore` | Shields `.env`, `.env.*`, `output/`, `tmp/`, `scratch/`, `*.pt`, `*.onnx`, `node_modules/`, `.claude/`. The `*.example` env templates **are** tracked on purpose. | `.env` holds live Airtable / Akeneo / Krea / Fal / Zoho credentials. It is not tracked. |
| GitHub Action | `.github/workflows/product_closeup_reel.yml`: **manual only** (`workflow_dispatch`), checks out `genspark_ai_developer`, uses your repo secrets | Pushing the branch never runs it by itself, but whatever is on that branch is what the action runs next time you trigger it. |
| Local git hooks | `post-commit` and `post-checkout` are the Qoder "AI tracker" hooks; both end with `\|\| true` | They can't block or fail a commit/checkout. The AI does not remove or bypass them. |
| Line endings | `core.autocrlf=true` | You will see harmless `LF will be replaced by CRLF` warnings. They are not errors. |
| Author | `Home Cartel Marketing <homecartelmarketing@gmail.com>` | Commits are authored as the repo owner; AI commits add a `Co-Authored-By` trailer. |

---

## 4. Step by step

Every step lists the command, what it is for, what a bad result looks like, and what the AI does about it.

### Step 0. Pre-flight (read-only)

```bash
git remote -v                       # must show the homecartelmarketing-lgtm/marketing-automation URL
git branch --show-current           # expect: genspark_ai_developer
git fetch origin                    # read-only: updates remote refs, changes no files
git status --short                  # what changed
git rev-list --left-right --count main...genspark_ai_developer      # expect "0  0" before your new commit
git rev-list --left-right --count genspark_ai_developer...origin/genspark_ai_developer
```

- **Bad:** wrong remote, wrong folder, or you're on a different branch → the AI **stops** and asks.
- **Bad:** `origin/genspark_ai_developer` is *ahead* of local (someone else pushed) → the AI does not push; it tells you and asks how to reconcile.
- A note like `There are too many unreachable loose objects; run 'git prune'` from `git fetch` is harmless housekeeping. It is not a failure.

### Step 1. Secret and stray-file check

```bash
git check-ignore -v .env                       # expect: .gitignore:2:.env  .env
git ls-files | grep -E '^\.env' | grep -v '\.example$'   # expect: nothing
```

After staging (Step 5) the AI also scans what is about to be committed:

```bash
git diff --cached --name-only | grep -E '(^|/)\.env($|\.)' | grep -v '\.example$'   # expect: nothing
git diff --cached | grep -nEi "^\+.*(key|secret|token|password)[A-Za-z_]*[\"' ]*[=:][\"' ]*[A-Za-z0-9_-]{16,}" | grep -v "your_"   # expect: nothing
```

This scan only looks at lines being *added* and ignores the `your_…` placeholder values used in `.env.example`. It catches long key-like values (16+ characters). It is a safety net, not the main protection: the main protection is that `.env` is git-ignored and never staged.

- **Bad:** either command prints something → the AI unstages it and **stops**.
- **Stray files:** any untracked file that is not code, docs, tests, or an obvious asset (a spreadsheet, a dump, a CSV of customers, model weights) is **not** added silently. The AI lists it and asks. Example at the time of writing: `assets/oct-calendar.xlsx` is untracked and *not* ignored, so the AI would ask before committing it.

### Step 2. Compile and test

```bash
python -m py_compile path/one.py path/two.py       # every .py file you changed, listed by name
python -m unittest discover tests                  # the suites in tests/
```

- **Bad:** any syntax/import error or failing test → the AI fixes it if it's within the task, otherwise **stops and reports** the failure output. It never pushes code that fails to compile.
- **Caveat:** compiling runs on your Python (3.12); Railway runs 3.11. If the change uses very new syntax, the AI mentions the risk instead of claiming the deploy is proven.

### Step 3. Rebuild the frontend (only if `UI Control/src/` changed)

```bash
cd "UI Control" && npm run build && cd ..          # must exit 0
```

- **Bad:** non-zero exit → **stop**. The AI does not commit a stale `dist/`.
- Afterwards the AI stages all of `UI Control/dist/`, **including deletions** of the old hashed files (`git add -A -- "UI Control/dist"`). Missing either side breaks the deployed UI.

### Step 4. Docs check

The AI applies the "Docs to update when you change X" table in `AGENTS.md` §8. If you added a fixture, pipeline, env key, or changed the frontend layout, the matching `.md` files are updated in the same commit, and it mentions any doc it deliberately left alone.

### Step 5. Stage named files and review

```bash
git add path/one.py path/two.py docs/SOMETHING.md   # explicit paths, not a blind "git add ."
git diff --cached --stat                            # review exactly what will be committed
```

`AGENTS.md` §11 shows `git add .`; that only works safely on a tree where every changed file belongs in the commit. The AI stages named paths after reading `git status`, so stray files don't ride along.

### Step 6. Commit

```bash
git commit -m "$(cat <<'EOF'
feat: add One at a time Lights reel pipeline

<one or two lines on why, if not obvious>

Co-Authored-By: <AI model name> <noreply@anthropic.com>
EOF
)"
```

- Prefixes: `feat:` new pipeline/feature · `fix:` bug/layout/API repair · `refactor:` no behavior change · `docs:` docs/memory only · `chore:` deps, gitignore, build config.
- The AI never uses `--amend` on a commit that has been pushed, and never `--no-verify`.
- If a hook rejects the commit, the AI fixes the cause and makes a **new** commit.

### Step 7. Push the dev branch (does not deploy)

```bash
git push origin genspark_ai_developer
```

- **Bad:** `rejected (non-fast-forward)` → the AI runs `git fetch`, looks at what's on the remote, and asks you before merging/rebasing. It does **not** force-push.
- Safe to run on its own. The Action workflow and Railway are unaffected.

### Step 8. Ship to `main` (production deploy)

The AI first says something like: *"Ready to fast-forward `main` and push. This triggers a Railway deploy. Go ahead?"* and waits, unless your original message already asked for the deploy.

```bash
git fetch origin
git checkout main
git merge --ff-only genspark_ai_developer
git push origin main
git checkout genspark_ai_developer                 # always return to the dev branch
```

- `--ff-only` means git refuses if `main` has commits the dev branch doesn't. If it refuses, the AI **stops** (someone changed `main`). It never fixes this with a force-push or a merge commit on `main` without asking.
- The AI always switches back to `genspark_ai_developer`, even after a failure, so the next task starts on the right branch.

### Step 9. After the push: what to expect

1. Railway sees the new `main` commit and rebuilds the image from the `Dockerfile` (installing `requirements.txt` is the slow layer).
2. The container starts `gunicorn` (`--workers 1 --threads 8 --timeout 600`; keep it at 1 worker because the queue and pipeline state are in memory) from `UI Control/`.
3. Railway's health check calls `GET /api/health`. Open `https://<your-railway-url>/api/health`: it returns JSON with `"status": "ok"` and a `modules` list of the registered pipelines. After the One at a time Lights release, `one_at_a_time_lights_reel` should appear in that list.
4. If the build fails, the AI can't see Railway's logs. It asks you to paste the build log from the Railway dashboard, then diagnoses it. Common causes: a package missing from `requirements.txt` (this is why `curl_cffi` is listed), or syntax that is valid on 3.12 but not 3.11.

---

## 5. When something goes wrong

| What happens | What the AI does |
| :--- | :--- |
| Wrong remote / folder / branch (Step 0) | Stops, says what it saw, asks |
| Remote branch is ahead of local | Doesn't push; explains and asks how to reconcile |
| A secret-looking string or `.env` is staged | Unstages it, stops, tells you which file/line |
| Unknown untracked file (e.g. a spreadsheet) | Leaves it out, lists it, asks |
| `py_compile` or a unit test fails | Fixes if in scope; otherwise stops and shows the error |
| `npm run build` fails | Stops; does not commit `dist/` |
| `git push` rejected (non-fast-forward) | Fetches, inspects, asks; never force-pushes |
| `git merge --ff-only` refuses on `main` | Stops; reports that `main` moved; never forces |
| Railway build fails after `main` push | Asks for the Railway build log, diagnoses, fixes on the dev branch, repeats Steps 2-9 |
| A bad change reached `main` and is live | Recommends the safe options: **`git revert <commit>`** then push (this adds a new commit, keeping history), or use Railway's own "redeploy previous deployment". It does **not** use `reset --hard` + force-push. |

---

## 6. The GitHub Action (Product Closeup Reel)

`.github/workflows/product_closeup_reel.yml` is the only workflow. It:

- runs **only when you click "Run workflow"** in the GitHub Actions tab (inputs: `phase`, `max_rows`, `record_id`),
- checks out **`genspark_ai_developer`** (not `main`) and uses Python 3.12,
- installs `requirements.txt` and runs `generate_product_closeup_reel_pipeline.py`,
- reads credentials from **GitHub repository secrets** (`AIRTABLE_TOKEN`, `KREA_API_TOKEN`, `FAL_KEY`, the Akeneo values …), never from `.env`.

So pushing code never starts it, but it always runs whatever is currently on `genspark_ai_developer`. The AI will not edit this workflow or its secrets unless you ask.

---

## 7. What to tell the AI (copy-paste prompts)

| You want | Say |
| :--- | :--- |
| A preview only | "Show me what would be committed and pushed. Don't commit anything yet." |
| Save work safely, no deploy | "Commit my changes and push to genspark_ai_developer only." |
| Full release | "Commit, push genspark_ai_developer, then fast-forward main and push it (deploy)." |
| Deploy what's already committed | "Fast-forward main to genspark_ai_developer and push." |
| Exclude a file | "Don't include assets/oct-calendar.xlsx." |
| Undo a bad deploy | "Revert the last commit on main and push." (uses `git revert`) |

---

## 8. Quick reference

```bash
# Look (safe)
git remote -v && git branch --show-current
git fetch origin
git status --short
git diff --cached --stat
git log --oneline -5

# Checks
python -m py_compile <changed files>
python -m unittest discover tests
cd "UI Control" && npm run build && cd ..

# Ship
git add <named paths>
git commit -m "feat: ..."
git push origin genspark_ai_developer
git checkout main && git merge --ff-only genspark_ai_developer && git push origin main && git checkout genspark_ai_developer
```

See also: [`AGENTS.md`](../AGENTS.md) §8 (docs to update when you change X) and §11 (the short rule list), [`OPERATIONS_AND_UTILITIES.md`](OPERATIONS_AND_UTILITIES.md), and the incident notes in [`memory/incidents/`](memory/incidents/).
