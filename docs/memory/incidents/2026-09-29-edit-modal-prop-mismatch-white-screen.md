---
date: 2026-09-29
pipeline: Control UI (Studio frontend)
status: resolved
---

# Control UI: white screen when clicking the interior-prompt (or moodboard) edit pencil

## Symptom

In the Studio (`http://127.0.0.1:5200`), clicking the pencil next to **Prompt** (and, by the same defect, the pencil next to **Moodboard**) on any fixture card blanked the whole page. Nothing else needed to be done first; the rest of the UI worked until the click.

## Root cause

The frontend refactor moved the edit modals out of the old single `App.tsx` into `UI Control/src/app/components/modals/`, but `App.tsx` kept passing the old prop names:

| Component | `App.tsx` passed | The modal declares |
| :--- | :--- | :--- |
| `EditPromptModal` | `inputValue`, `isLoading` | `promptInput`, `isSaving` |
| `EditMoodboardModal` | `inputValue`, `isLoading` | `moodboardInput`, `isSaving` |
| `StudioPinModal` | *(nothing)* | `studioPin` (required) |

`promptInput` therefore arrived as `undefined`, and the modal's Save button did `!promptInput.trim()` during render. The modal returns `null` while no fixture is selected, so the crash only happened once the pencil set a fixture. That throw was uncaught: nothing in `src/` was an error boundary, so React unmounted the whole tree, which is the white screen.

The missing `studioPin` did not crash; it only hid the "Clear PIN" button.

## Why it wasn't caught

`UI Control` builds with plain `vite build`. TypeScript is not installed (no `tsc`, no `tsconfig.json`), so a wrong prop name is never flagged and the build succeeds. The existing `npm run test:render` smoke test only loads the page and looks for exceptions; it never clicks anything, so it can't see a bug that needs a click.

## Fix

- `UI Control/src/app/App.tsx`: pass the props the modals actually declare (`promptInput` / `moodboardInput`, `isSaving`, and `pipelineName` so the header names the real pipeline instead of always "Story"), and pass `studioPin` to `StudioPinModal`.
- Added `UI Control/src/app/components/ErrorBoundary.tsx`, wrapped around `<App />` in `src/main.tsx`. A future render error now shows a readable message with a Reload button instead of a blank page.
- Rebuilt `UI Control/dist/`.

## How it was verified

- `npm run build` exits 0.
- A headless Chrome run (DevTools protocol) against the running Studio clicked the prompt pencil and the moodboard pencil: the modals appeared, the prompt textarea was pre-filled, Cancel closed the modal, and there were zero uncaught page exceptions.

## Lessons

- After splitting a component out of `App.tsx`, **click-test every modal it opens.** Props are not type-checked in this project.
- If a UI component is rendered with `foo?.bar` style optionality, still pass every prop it requires; a missing string prop fails at `.trim()` inside render, not at the call site.
- Checked and **not a bug**: `RowInspectorModal.tsx` and `RunConfirmModal.tsx` do `if (!fixture) return null;` *before* their `useState`/`useEffect` calls, which looks like a rules-of-hooks violation. It was suspected of crashing on close, but a headless-Chrome test (open and close the inspector twice) showed no errors, and React's source explains why: the "rendered fewer hooks" error only fires if at least one hook ran in that render, so a component that returns before *any* hook is simply treated as a fresh mount on the next open. The side effect is that each open starts with clean state, which is the desired behavior. Don't "fix" this by moving the early return below the hooks without also resetting state, or the modal would briefly show the previous fixture's rows.
