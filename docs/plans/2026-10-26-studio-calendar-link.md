# Studio Content Calendar Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a always-visible "Content Calendar" shortcut in the Studio header that opens `https://homecartel-marketing-calendar-v2.vercel.app/` in a new tab.

**Architecture:** One frontend-only change in `UI Control/src/app/App.tsx`. A module-level constant holds the URL, and an `<a>` styled like the existing "Sync Airtable" button sits in the header action cluster. No backend route, no API call, no new dependency.

**Tech Stack:** React 18, TypeScript, Tailwind CSS 4, lucide-react icons, Vite 6.

**Spec:** User request (2026-10-26): a clickable shortcut to the marketing calendar instead of typing the Vercel URL; implement locally first, do not commit or push.

## Global Constraints

- **Local only:** do not `git commit` or `git push` until the user reviews the change in the browser.
- **No backend change:** the link is a plain anchor; do not add a Flask route or proxy.
- **New tab:** `target="_blank"` with `rel="noopener noreferrer"`.
- **Match existing header styling:** reuse the "Sync Airtable" button classes so the header stays visually consistent.
- **URL is a constant:** one module-level `MARKETING_CALENDAR_URL` in `App.tsx`, no scattered literals.
- **Build required for local review:** Flask serves `UI Control/dist/`, so run `npm run build` after editing.

---

### Task 1: Add the Content Calendar header link

**Files:**
- Modify: `UI Control/src/app/App.tsx:5` (lucide import)
- Modify: `UI Control/src/app/App.tsx:20-22` (module constant)
- Modify: `UI Control/src/app/App.tsx:683-693` (header action cluster)
- Verify (generated, not hand-edited): `UI Control/dist/`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `MARKETING_CALENDAR_URL: string` module constant and one header `<a>` element with `data-testid="studio-calendar-link"` for verification.

- [ ] **Step 1: Extend the lucide import**

Replace line 5:

```tsx
import { RefreshCw, Key, Check, LogOut } from 'lucide-react';
```

with:

```tsx
import { RefreshCw, Key, Check, LogOut, CalendarDays, ExternalLink } from 'lucide-react';
```

- [ ] **Step 2: Add the URL constant**

Immediately after the last import (after the `import type { PipelineType, QueueJob, QueueHistoryItem } from './types';` line), add:

```tsx
// Marketing calendar v2 (separate Vercel app). Kept here so the Studio has one
// clickable shortcut instead of the team retyping the URL.
const MARKETING_CALENDAR_URL = 'https://homecartel-marketing-calendar-v2.vercel.app/';
```

- [ ] **Step 3: Render the link in the header action cluster**

Inside the header's right-hand `<div className="flex items-center gap-3">`, insert this anchor **before** `<ThemeToggle />`:

```tsx
<a
  href={MARKETING_CALENDAR_URL}
  target="_blank"
  rel="noopener noreferrer"
  data-testid="studio-calendar-link"
  title="Open the HomeCartel marketing calendar in a new tab"
  className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-card border border-slate-300 rounded-lg hover:bg-slate-50 active:bg-slate-100 transition shadow-xs cursor-pointer"
>
  <CalendarDays className="w-3.5 h-3.5" />
  <span className="hidden sm:inline">Content Calendar</span>
  <ExternalLink className="w-3 h-3 text-slate-400" />
</a>
```

The label collapses to an icon-only button below the `sm` breakpoint so the mobile header does not wrap.

- [ ] **Step 4: Build the frontend**

Run:

```bash
cd "UI Control" && npm run build
```

Expected: exit 0 and a new hashed bundle in `UI Control/dist/assets/`.

- [ ] **Step 5: Verify the link exists in the built bundle**

Run:

```bash
grep -rl "homecartel-marketing-calendar-v2.vercel.app" "UI Control/dist/assets"
```

Expected: at least one `.js` file is printed.

- [ ] **Step 6: Verify in the browser**

Start the Studio and open `http://localhost:5200`:

```bash
python "UI Control/api_server.py"
```

Expected: the header shows "Content Calendar"; clicking it opens the Vercel calendar in a new tab. If the local Studio is in login mode, sign in first.

- [ ] **Step 7: Stop and leave the change uncommitted**

Do **not** commit or push. Report the changed file and the build result to the user so they can review locally.

---

## Self-Review

- **Spec coverage:** the only requirement — a shortcut to the calendar inside the Studio — is implemented in Task 1, Steps 1-3, and verified in Steps 4-6.
- **Placeholder scan:** no TBD/TODO; every code step shows the exact code.
- **Type consistency:** `MARKETING_CALENDAR_URL` is defined once and used once; `data-testid` is unique; lucide icon names exist in `lucide-react@0.487.0`.
- **Out of scope:** no iframe embedding (the Vercel app can change its own headers), no backend config, no docs/skill changes, no commit or push.
