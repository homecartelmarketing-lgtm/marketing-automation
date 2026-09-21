# Project Memory

Durable knowledge about *this* automation system that isn't derivable just by reading the code: why things broke, why choices were made, and how the pieces actually connect. Meant to be opened as an [Obsidian](https://obsidian.md) vault rooted at `docs/` (File → Open folder as vault) — notes here link to each other and out to the pipeline docs with `[[wikilinks]]`.

## Why this exists

The rest of `docs/` (see [`../README.md`](../README.md)) documents *what each pipeline does*. It doesn't capture the things that get re-discovered from scratch every time someone hits them: a pipeline failure that took real investigation to diagnose, a design decision whose reasoning isn't obvious from the code alone, or how a subsystem fits into the bigger picture.

## Layout

- **[`incidents/`](incidents/)** — one file per debugged production/pipeline issue. Symptom, root cause, how it was diagnosed, what (if anything) was fixed.
- **[`decisions/`](decisions/)** — one file per non-obvious design choice. The "why" behind a piece of code that isn't self-explanatory from reading it.
- **[`architecture/`](architecture/)** — a small number of overview notes on how subsystems fit together end to end.

## When to add a note here

- **Before debugging a pipeline failure**, check `incidents/` for the same category/error — it may already be diagnosed.
- **After resolving anything non-trivial** (a failure that took real investigation, or a decision made on the fly that isn't obvious from the diff), add a note. A few sentences is enough; the point is not re-doing the investigation next time.

This applies to AI agents working in this repo too — see the protocol note in [`../../AGENTS.md`](../../AGENTS.md).
