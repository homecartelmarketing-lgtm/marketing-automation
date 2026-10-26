# Decision: real-world scale lives in the prompt, not in extra AI calls (2026-10-26)

Oversized fixtures in blended rooms were caused by two gaps: the shared blend
instruction had no scale rule, and the supplier `Measurement` already in
Airtable never reached Claude. Fixed with one shared helper,
`content_automation/prompts/scale.py`, wired into every room-blend path.

## Choices and why

- **One helper owns all wording and type ranges.** Pipelines call
  `blend_instruction_from_fields` (shared builder) or `scale_clause` (pipelines
  with their own instruction). Editing the rule in one file updates every
  format, and `SCALE_RULES_VERSION` + `scale_cache_digest` in the prompt-cache
  keys prevent stale `qwen_outputs.json` entries from surviving a rule change.
- **No room-scale anchors and no post-blend verification.** Both were proposed;
  the user chose size-in-prompt only. The room is AI-generated, so exact pixels
  are unknowable, but an LLM can reason in ratios once it has real cm plus
  visible references (door ~2.0 m, table ~75 cm, seat ~45 cm, ceiling ~2.6 m).
  This costs zero extra API calls and keeps phase counts unchanged.
- **Missing size falls back to a typical range per fixture type.** Most rows
  today have no `Measurement`; `ESTIMATED_PRODUCT_SIZES` is deliberately marked
  as typical ranges, not catalogue data. Tune those numbers after reviewing the
  first batch instead of adding a paid measurement pass.
- **Every multi-fixture prompt gets a labelled clause per fixture.** Passing one
  unlabelled rule lets a table lamp's 48 cm height leak onto a chandelier;
  labels such as "the table lamp in Image 2" keep each size local.
- **Data plumbing only applies to new rows.** `Measurement` is now requested on
  Akeneo detail lookups, ensured on shared and custom row schemas, and written
  by single-row and custom scrapers. Old rows are intentionally not backfilled
  (fresh-row rule); `scripts/ops/normalize_airtable_rows.py` can do that
  manually if ever needed.
- **Clamp implausible numbers inside the prompt.** A height over 140 cm on a
  hanging type is treated as adjustable drop, and width over 200 cm is treated
  as suspicious. Shipping/packaging sizes would otherwise render as giant
  bodies.

## Not done on purpose

Room-prompt scale anchors remain out of scope. The paid post-blend check is
implemented separately (below) and only runs on room + single-product blends.

# Decision: measured target + check + one retry for room blends (2026-10-26)

The prompt-only rule still left the model free to guess. The user then chose
the paid option: measure the scene, lock a numeric target, verify the blend, and
retry once. Implemented in `content_automation/scale_guard.py` and wired into
every room + single-product blend path.

## How it works

1. A Claude Vision call inspects the room and cutout, picks a nearby
   known-size reference (table 75 cm, seat 45 cm, door 200 cm, ceiling 260 cm)
   and returns its visible fraction plus the fixture's visible fraction.
2. The realised target comes from either the supplier cm or the typical range
   for the normalised fixture type, and is appended to Claude's existing blend
   prompt as a numeric `MEASURED SCALE TARGET` block.
3. The normal Nano Banana Pro blend runs.
4. A second Claude Vision call measures the blended result against the same
   reference, and the implied cm is compared with the target.
5. Outside ±15% (`SCALE_GUARD_TOLERANCE`, clamped 0.05-0.50) the guard re-blends
   once with a correction line, checks again, and keeps whichever attempt has
   the smaller absolute error. It never fails the pipeline.

## Choices and why

- **Separate measure and check calls.** They see different images (inputs vs
  output) and the user confirmed the two-call split. Budget is about
  $0.002-0.005 per 10-image batch for the checks, plus one re-blend only when
  the first attempt misses.
- **Guard is room + one product only.** Multi-fixture blends (One at a Time
  Lights, This or That, Christmas/Sale banners) and single-image transforms
  (night versions, empty-room stripping, moodboard conversions) stay on the
  prompt-only rule; there is no single product/reference pair to measure.
- **Airtable audit fields, no database.** `Scale Audit` (multilineText),
  `Scale Check` and `Scale Retry` (singleSelect) plus optional
  `Rejected Blend` (attachment) are ensured/idempotently created per table by
  `ensure_scale_fields`; `scripts/ops/provision_scale_fields.py` can pre-create
  them across the base. Old rows are not backfilled (fresh-row rule).
- **Global switch.** `SCALE_GUARD_ENABLED=0` disables the call pair without a
  code change; the prompt-only scale rule still applies.

## Not done on purpose

No room-prompt changes and no persistent size database. Known-size furniture
plus the supplier cm is enough of a ruler, and adding anchors would change every
generated room for a benefit this loop already measures.

## Coverage across the codebase

Every room + single-product blend now calls `BaseWorkflow.fal_blend` (or
`blend_with_scale_guard` directly), so the numeric target, check and one retry
apply the same way in the Studio monoliths and in the legacy registry workflows
under `content_automation/workflows/`.

- Single-product multi-room workflows (Style This, 1 Product 3 Styles, Day &
  Night, Moodboard, Tips & Edu, CTA, Virtual Staging, Sketch to Real) pass
  `slot=0`, so the record's own `Measurement` / `Product Type` drives every
  room instead of a shared number.
- Parallel blends on one record serialize their audit writes behind a lock, so a
  later slot cannot overwrite an earlier slot's `Scale Audit` block.
- Registry workflows that used `nano_image` (Kie) for the room blend were moved
  to `fal_blend`. This is a provider change for those legacy CLI paths only
  (Studio always runs the monoliths, which already used Fal). It was accepted
  because the guard needs Fal's Claude Vision calls and because the documented
  architecture defines blends as Fal Nano Banana Pro. Non-blend steps (night
  versions, layout cards) keep the provider they had.
- Multi-fixture blends (One at a Time Lights, This or That, Christmas/Sale
  banners), layout/podium conversions and single-image transforms (night
  versions, room stripping, moodboard cards) stay on the prompt-only rule: there
  is no single product/reference pair to measure.
