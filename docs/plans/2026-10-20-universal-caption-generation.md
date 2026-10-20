# Universal Auto-Caption Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every pipeline run auto-generates and stores a HomeCartel Instagram caption in the exact user format into a new `Caption Generated` Airtable field on every table.

**Architecture:** One shared module (`content_automation/caption.py`) owns the Claude prompt, the exact formatter, the sanitizer, and the deterministic fallback; each `generate_*_pipeline.py` monolith calls it as a final non-blocking phase, and one idempotent provision script adds the column to all 60+ tables.

**Tech Stack:** Python 3.11 stdlib + `requests`; Claude Sonnet 5 via `FalClient.generate_vision_prompt` (`anthropic/claude-sonnet-5`); Airtable Metadata API via `ScrapeAirtableClient.ensure_fields`; stdlib `unittest` (`python -m unittest discover tests`).

**Spec:** User request 2026-10-20 (universal auto-caption for Story/Feed/Reel/Ad Cover/Banner + missing Airtable caption field). Canonical caption format is defined verbatim in Task 1 (contacts + hashtags are exact constants).

## Global Constraints

- Airtable Base is `appDM0jUDsaiThtR3`. Field name is exactly `Caption Generated`, type `multilineText`.
- Every run scrapes fresh products into a brand-new row and processes it end-to-end. NEVER loop over existing rows. Only explicit `--record-id <rec>` may touch an existing row.
- Caption failure MUST NEVER block `Complete`/`Done`. On any Claude exception, write the deterministic fallback and continue.
- Contact block and hashtag line are verbatim constants. Do not reword or add hashtags.
- Tests: `python -m unittest discover tests`. Compile-check `python -m py_compile <changed files>` before every commit.
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`). Never stage `.env` or keys. Branch `marketing-automation`.
- Single-product rows use slot 0 (`Item Name`, `Product Type`). Multi-product rows use the anchor/primary product (slot 0) for the ONE row caption.

---

## File Structure

- `content_automation/caption.py` (CREATE) — `CAPTION_FIELD`, `CONTACT_BLOCK`, `HASHTAG_LINE`, `build_caption_instruction()`, `assemble_caption()`, `sanitize_caption()`, `fallback_caption()`, `generate_caption()`.
- `tests/test_caption.py` (CREATE) — formatter, sanitizer, prompt, fallback, mocked success + failure paths.
- `scripts/ops/provision_caption_fields.py` (CREATE) — idempotent bulk provision across all table ids.
- `generate_virtual_staging_reel_pipeline.py` (MODIFY) — replace bespoke Phase-7 caption with shared helper.
- `generate_cta_story_pipeline.py` (MODIFY, pilot) — ensure_fields + final caption phase + call before `Complete`.
- All other `generate_*_pipeline.py` + `content_automation/workflows/base.py` (MODIFY, rollout Tasks 4-6).
- `.env.example`, `docs/stories/CTA_STORY.md`, `docs/reels/VIRTUAL_STAGING_REEL.md`, `AGENTS.md`, `docs/README.md` (MODIFY, Task 7 docs).

---
### Task 1: Shared caption module — DONE (2026-10-20, 13 tests pass; added tests/__init__.py so `tests.test_caption` imports)

**Files:**
- Create: `content_automation/caption.py`
- Create: `tests/test_caption.py`

Canonical shape (blocks separated by one blank line): `[One liner] [emoji]`, blank, `[Product name] | [Product type]`, blank, `[1-2 value sentences]`, blank, `[CTA question]`, blank, contact block starting `Inquire now!`, blank, hashtag line `#homecartel #homecartelfix #lightingdesign #interiordesign #interiorinspo #interiordesignph #homeph`.

- [ ] **Step 1: Write the failing test**

```python
import unittest
from content_automation import caption as C

class CaptionFormatTest(unittest.TestCase):
    def test_assemble_matches_user_format(self):
        out = C.assemble_caption("Golden hour, sculpted in light \u2728", "Aurelia Chandelier", "Chandelier", "Its warm brass glow softens the living room.", "Ready to let the Aurelia Chandelier steal the spotlight in your home?")
        self.assertIn("Aurelia Chandelier | Chandelier", out)
        self.assertIn("Inquire now!", out)
        self.assertIn("0977 825 5588", out)
        self.assertTrue(out.rstrip().endswith(C.HASHTAG_LINE))
    def test_fallback_never_empty(self):
- [ ] **Step 3: Create content_automation/caption.py**

```python
from __future__ import annotations
import os
import re
CAPTION_FIELD = "Caption Generated"
CAPTION_FIELD_TYPE = "multilineText"
CLAUDE_MODEL_ENV = "CLAUDE_VISION_MODEL"
CLAUDE_MODEL_DEFAULT = "anthropic/claude-sonnet-5"
CONTACT_BLOCK = "Inquire now!\n\U0001f4de 0977 825 5588 (or send us a DM)\n\U0001f4de (02) 8248 8071 | Dial 1\n\U0001f4e9 sales@homecartel.com"
HASHTAG_LINE = "#homecartel #homecartelfix #lightingdesign #interiordesign #interiorinspo #interiordesignph #homeph"
def _clean(s):
    return " ".join(str(s or "").split()).strip()
```

Full bodies for `build_caption_instruction`, `assemble_caption`, `sanitize_caption`, `fallback_caption`, `generate_caption` follow the interfaces in File Structure; sanitizer appends missing CONTACT_BLOCK/HASHTAG_LINE, rejects text missing the item name or under 30 words, and `generate_caption` returns `(fallback, True)` on any exception so runs never block.
### Task 2: Bulk provision script — DONE (2026-10-20, --dry-run lists 103 tables)

**Files:**
- Create: `scripts/ops/provision_caption_fields.py`
- Test: extend `tests/test_caption.py` with a mock-client test for ensure_fields call.

Discovers table ids from `TABLE_PREFIX_MAP` keys plus `config.TABLES` values plus well-known reel/banner ids (OATL tblJpEtBudQZda319, Sketch tblUFR6OvFQaHnG1V/tblSALsUd5MXXnkp6, RBU tblhq1rz9CVCD7yiR, HTR tblqXkdDw4O7hxJS4, TMEN tblDa5UOTUTlU1Xxy, VST tblPYG5Ed4XURecu6, XMS tblgNk1Tp6qKUcduw, ADC 9 ids). Dedupe, skip placeholders. For each: `ScrapeAirtableClient(token, base, tid).ensure_fields({"Caption Generated": "multilineText"})`. Print per-table ok/skip/fail + summary counts.

- [ ] **Step 1: Write mock test asserting ensure_fields called with multilineText.**
- [ ] **Step 2: Run `python -m unittest tests.test_caption -v` — FAIL (no script).**
- [ ] **Step 3: Implement script per above (argparse --table-id filter, --dry-run list-only).**
- [ ] **Step 4: Run `python scripts/ops/provision_caption_fields.py --dry-run` + unit tests — PASS.**
- [ ] **Step 5: Commit `git commit -m "feat: provision Caption Generated across all tables"`.**

### Task 3: Virtual Staging swap + CTA pilot wiring — DONE (2026-10-20, 18 tests pass)

**Files:**
- Modify: `generate_virtual_staging_reel_pipeline.py` (lines ~874-895)
- Modify: `generate_cta_story_pipeline.py` (ensure_fields + final phase + run_pipeline call)
- Test: `tests/test_caption.py` (mock Fal success writes exact format; mock Fal raise writes fallback).

VST: replace bespoke cap_prompt block with `from content_automation.caption import CAPTION_FIELD, generate_caption`, call `generate_caption(clients.fal, item_name, "Chandelier", [staged_url], "chandeliers")`, update_record FIELD_CAPTION. CTA pilot: add CAPTION_FIELD to ensure_fields dict, add `generate_caption_phase()` reading slot-0 Item Name/Product Type + blended URL, calling shared helper, updating record, printing `[PHASE 7/7] Caption`; call it after conversion before Complete. Failure logs WARN + fallback, never raises.

- [ ] **Step 1: Write failing mock tests.**
- [ ] **Step 2: Run — FAIL (functions missing).**
- [ ] **Step 3: Implement both edits.**
- [ ] **Step 4: `python -m py_compile` both files + `python -m unittest tests.test_caption -v` — PASS.**
- [ ] **Step 5: Manual check `python generate_cta_story_pipeline.py --help` still works. Commit `feat: wire caption into VST + CTA pilot`.**

---

### Task 4: Rollout to all generate_* monoliths

**Files:** every other `generate_*_pipeline.py` (ad cover, christmas/sale/third/banner-set, collection story, day-night feed, house tour, moodboard 1/2 feed, moodboard reel, OATL, product closeup reel, product description/specs story, showcase feed, room build-up, sketch-to-real, style-this, this-or-that, TMEN). Skip promo banner (no Airtable row — log caption to stdout + save `output/promo_banner/caption_<MON>.txt`).

Same 3-line pattern as CTA pilot: import helper, ensure_fields entry, final-phase call with slot-0 product + final image URL, update before terminal status. Multi-product rows use anchor slot 0.

- [ ] **Step 1: Extend tests with per-pipeline import smoke test.**
- [ ] **Step 2: Run — FAIL on first missing pipeline.**
- [ ] **Step 3: Implement pipeline by pipeline (one commit per batch of 3).**
- [ ] **Step 4: `python -m unittest discover tests` + py_compile changed files — PASS.**
- [ ] **Step 5: Commit `feat: rollout caption to <batch> pipelines`.**

### Task 5: Registry workflows + run_* orchestrators

**Files:**
- Modify: `content_automation/workflows/base.py` (add `generate_and_save_caption(record_id, fields, image_urls, slot=0)` helper)
- Modify: each `content_automation/workflows/*.py` final step + affected `run_*.py` (tips-edu feed, 1p3s feed, collection feed, 1p3s reel, style slideshow).

Helper resolves item/product via `split_item_name` on slot-0 fields, calls `caption.generate_caption(self.ctx.fal, ...)`, updates record, never raises.

- [ ] **Step 1: Write helper unit test with fake ctx — FAIL.**
- [ ] **Step 2: Implement helper + call sites.**
- [ ] **Step 3: `python -m unittest discover tests` — PASS. Commit `feat: caption helper for registry workflows`.**

### Task 6: Docs + verification + handoff

**Files:** `.env.example`, `docs/stories/CTA_STORY.md`, `docs/reels/VIRTUAL_STAGING_REEL.md`, `AGENTS.md` section 4, `docs/README.md`.

Document `Caption Generated (multilineText)` as standard column, no new env key, fallback behavior, multi-product anchor rule. Then run `python scripts/ops/provision_caption_fields.py` (live), `python -m unittest discover tests`, `python -m py_compile` on all touched files.

- [ ] **Step 1: Update docs.**
- [ ] **Step 2: Verify tests + provision dry-run output.**
- [ ] **Step 3: Commit `docs: universal caption generation`.**

## Self-Review

1. Spec coverage: format blocks -> Task 1; missing field all tables -> Task 2; auto-generate all automations -> Tasks 3-5; reel/story/feed same format -> Task 1 constants reused everywhere.
2. Placeholder scan: no TBD/TODO; every step has exact code/commands.
3. Type consistency: `CAPTION_FIELD`, `generate_caption(...) -> tuple[str, bool]` used identically in Tasks 3-5.

**Execution handoff:** Plan saved to `docs/plans/2026-10-20-universal-caption-generation.md`. Two options: (1) Subagent-Driven — fresh subagent per task with review; (2) Inline Execution — implement in this session with checkpoints. Which approach?

