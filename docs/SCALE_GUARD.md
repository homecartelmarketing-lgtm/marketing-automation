# Measured Scale Guard

The scale guard keeps a blended fixture at the size it really is. Without it, a blend prompt only asked the model to "keep the item realistic", so a 90 cm pendant could render as small as a table lamp, or a large chandelier could fill the whole ceiling. The guard adds a measured target, checks the finished blend, and retries once when the size is off.

- Code: [`content_automation/scale_guard.py`](../content_automation/scale_guard.py)
- Entry point: `blend_with_scale_guard(...)` — guarded pipelines call this instead of the Fal blend directly.
- Prompt-only rule: [`content_automation/prompts/scale.py`](../content_automation/prompts/scale.py) `scale_clause()` for pipelines that do not run the paid guard (see §7).
- Decision note: [`memory/decisions/2026-10-26-real-world-scale-in-blend-prompts.md`](memory/decisions/2026-10-26-real-world-scale-in-blend-prompts.md)

---

## 1. What a guarded blend does

1. **Measure.** One Claude Sonnet 5 Vision call (`anthropic/claude-sonnet-5`) receives the room and the product image. It finds a reliable object already in the room (door, sofa, bed, counter, window, ...) and reports how much of the image height or width that object occupies, plus its real size.
2. **Set the target.** The fixture's real size comes from the scraped Akeneo `Measurement` (for example `Ø 90 cm x H 45 cm`). When the row has no usable measurement, [`prompts/scale.py`](../content_automation/prompts/scale.py) `ESTIMATED_PRODUCT_SIZES` supplies a conservative size for that product type. The target is `reference_fraction × fixture_cm ÷ reference_cm`.
3. **Lock the prompt.** `build_lock_text()` appends the measurement, the reference object, and the target fraction to the blending prompt.
4. **Blend.** One Nano Banana Pro call (`fal-ai/nano-banana-pro/edit`).
5. **Check.** A second Claude Vision call compares the fixture in the blend against the measured target and returns `Pass`, `Too Big` or `Too Small`.
6. **Retry once.** Outside the tolerance (`SCALE_GUARD_TOLERANCE`, default ±15%), one corrective Nano Banana Pro retry is made (`build_retry_correction()`). The closer attempt is kept. If attempt 1 is `No Reference` or `Error`, there is no retry.

The guard never fails a run. A failed measurement call, unparsable JSON, or no usable reference degrades to the prompt-only scale rule.

---

## 2. Airtable audit fields

| Field | Type | Values |
| :--- | :--- | :--- |
| `Scale Check` | singleSelect | `Pass`, `Pass After Retry`, `Too Big`, `Too Small`, `No Reference`, `Skipped`, `Error` |
| `Scale Retry` | singleSelect | `Not Needed`, `Retried`, `Retry Failed` |
| `Scale Audit` | multilineText | Per-slot block: size source + measurement, reference object, target fraction/px, attempt 1/2 ratios, retry decision |

- `merge_scale_fields()` builds one row-level update for every slot; the row shows the most severe verdict (`Error` > `Too Big`/`Too Small` > `Skipped`/`No Reference` > `Pass After Retry` > `Pass`).
- `write_scale_fields()` never raises. An audit write failure cannot fail a paid run; it retries with `typecast` and then only logs a warning.
- The fields are created automatically on first use by `ensure_scale_fields()`, but explicit provisioning is safer on a new table:

```bash
python scripts/ops/provision_scale_fields.py --dry-run
python scripts/ops/provision_scale_fields.py --table-id tblXXXXXXXXXXXXXX
python scripts/ops/provision_scale_fields.py            # every discovered room-blend table
```

`provision_scale_fields.py` is idempotent: it creates only the missing columns and the two select choices.

---

## 3. Environment keys

| Key | Default | Effect |
| :--- | :--- | :--- |
| `SCALE_GUARD_ENABLED` | on | `0`, `false`, `no`, `off`, or `disabled` runs one prompt-only blend with no measure/check/retry. `SCALE_GUARD` is accepted as an alias. |
| `SCALE_GUARD_TOLERANCE` | `0.15` | Accepted deviation from the target, clamped to `0.05`–`0.50`. |

Set `SCALE_GUARD_ENABLED=0` when you want to hold off the extra paid calls without changing code. The audit then shows `Scale Check = Skipped`.

---

## 4. Cost

Per guarded slot:

| Step | Calls |
| :--- | :--- |
| Measure | 1 Claude Sonnet 5 vision call |
| Blend | 1 Nano Banana Pro call (the normal paid blend) |
| Check | 1 Claude Sonnet 5 vision call |
| Retry (only when off by more than the tolerance) | 1 extra Nano Banana Pro call + 1 extra check |

A row with no usable reference costs one measurement call plus the normal blend. Disabling the guard removes every extra call. The guard adds no new vendor.

---

## 5. Guarded pipelines

| Format | Pipelines |
| :--- | :--- |
| Stories | CTA, Collection Category, Day & Night, Moodboard, Myth & Fact, Style This, Tips & Educational |
| Feeds | Collection Category, Day & Night, Moodboard #1, Moodboard #2, 1 Product 3 Styles, Tips & Educational |
| Reels | Before & After, Day & Night, House Tour, Moodboard, 1 Product 3 Styles, Product Closeup, Room Build-Up, Room Reveal, Sketch to Real, Style Reel Slideshow, This Mood Every Night, Virtual Staging |
| Ads | Ad Cover |

All of these run their product-to-room blend through `blend_with_scale_guard()`, including the pipelines that go through `content_automation/workflows/base.py` and `content_automation/phased_content.py`.

Pipelines that do **not** use the paid guard:

- **Prompt-only scale rule (§7):** One at a Time Lights Reel, This or That Story.
- **No product-to-room blend:** Product Showcase Feed, Product Closeup Specs Story, Product Closeup Description Story, Christmas Banner, Sale Banner, Promo Banner.

---

## 6. Reading the audit

`Scale Audit` is the place to look after a run. A passing row looks like this:

```text
scale-guard-v1 | slot 1 of 4
size: supplier Ø 90 cm -> 90 cm horizontal
reference: door 200 cm horizontal, 38% of image horizontal (high)
target: 17% of image horizontal (184 px)
attempt 1: 101% of target -> Pass
retry: Not Needed | kept: attempt 1
```

Common values:

| Value | Meaning |
| :--- | :--- |
| `Pass` | Attempt 1 landed inside the tolerance. |
| `Pass After Retry` | Attempt 1 was off; the retry landed inside the tolerance and was kept. |
| `Too Big` / `Too Small` | Both attempts were off. The closer one was kept. |
| `No Reference` | Claude could not find a reliable object to measure against, so the prompt-only scale rule was used. Not an error. |
| `Skipped` | `SCALE_GUARD_ENABLED=0`. |
| `Error` | The vision call failed or returned unreadable JSON. The blend still completed. |

---

## 7. Prompt-only scale rule (no paid guard)

[`content_automation/prompts/scale.py`](../content_automation/prompts/scale.py) `scale_clause()` writes the real size into the prompt without measuring, checking, or retrying. It is free and is used by:

- One at a Time Lights Reel
- This or That Story

These pipelines have no `Scale Check` / `Scale Retry` / `Scale Audit` entries because no guarded calls run. The clause still tells the model the true size and the item's role in the frame.

---

## 8. Tests

```bash
python -m unittest tests.test_scale_guard tests.test_scale_prompt
```

`tests/test_scale_guard.py` covers target math, pass/too-big/too-small verdicts, the retry decision, and the audit text. `tests/test_scale_prompt.py` covers the prompt-only clause and the estimated sizes.
