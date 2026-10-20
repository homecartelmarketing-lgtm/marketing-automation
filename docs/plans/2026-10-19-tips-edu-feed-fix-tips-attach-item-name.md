# Tips & Edu Feed — Tips Attach to Photo & Item Name Formatting Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Tips & Edu Feed so Phase 6 composites tips onto the correct YOLO-tagged photo per slot, and Phase 5 stamps a clean two-line Item Name / Product Type tag.

**Architecture:** Keep the 6-phase monolith in `run_tips_and_edu_feed.py`; add small pure helpers for slot field resolution, tagged-blend selection, and name normalization so Phase 5/6 are deterministic and testable without network calls. All layout stays local Pillow — zero image-API spend.

**Tech Stack:** Python 3.11+, Pillow, YOLO-World local CPU, Airtable REST via ScrapeAirtableClient, stdlib unittest.

**Spec:** `docs/feeds/TIPS_AND_EDU_FEED.md` sections 4-6; incidents `docs/memory/incidents/2026-10-15-tips-edu-feed-phase-5-attributeerror-and-tips-stamping.md`, `2026-10-15-tips-edu-feed-phase-5-6-labels-and-audit-sync.md`, `2026-10-15-tips-edu-feed-crash-leaves-row-processing.md`; `docs/REDFLAG_REPORT.md` H2.

## Global Constraints

- Zero API cost for layouts: local Pillow only.
- Brand-new row every run; explicit `--record-id` is the only retry exception.
- Strict Shopify Active & Published exact match; base-wide dedup.
- FK `TNE-FEEDS-<FIXTURE>-<ROWID>`; PHT timestamp on Complete; crashed phase goes `For Manual`, never stays `Processing`.
- Phase 5 reads `Item Name[1-3]` + `Product Type[1-3]` directly; no synthetic `category_label` properties.
- Dual-write tips `Tips 1..3` + legacy `Tip1..3`.
- Compile + test before commit: `python -m py_compile` and `python -m unittest discover tests`.
- Canvas Feed 1080x1350; numeral Poppins-Regular 196px; tip Poppins-Bold 32px; YOLO tag 19px two-line.

---

## File map

- Modify `run_tips_and_edu_feed.py`: Phase 5 lookup (~2041-2049), carousel upload (~2077-2093), Phase 6 source (~2114-2142), sorter (~577-594), new helpers near sorter.
- Create `tests/test_tips_edu_feed_attach_format.py`.
- Modify `docs/feeds/TIPS_AND_EDU_FEED.md` section 6C.
- Create `docs/memory/incidents/2026-10-19-tips-edu-feed-attach-format.md`.

---
### Task 1: Failing regression suite (TDD seed)

**Files:** Create `tests/test_tips_edu_feed_attach_format.py`.
**Produces:** 5 tests Tasks 2-6 must turn green.

- [ ] **Step 1: Write the failing test** — full file content:

```python
"""Tips & Edu Feed attach-to-photo + item-name formatting regressions."""
import unittest
import run_tips_and_edu_feed as feed

def make_att(filename, idx):
    return {"url": f"https://example.invalid/{filename}", "filename": filename, "id": f"att{idx}"}

class AttachFormatTests(unittest.TestCase):
    def test_space_variant_item_name_fields_resolve(self):
        from run_tips_and_edu_feed import get_slot_item_name_val, SLOTS
        fields = {"Item Name 2": "Zygadlo | Luxury Modern Chandelier"}
        self.assertEqual(get_slot_item_name_val(fields, SLOTS[1]), "Zygadlo | Luxury Modern Chandelier")
    def test_empty_name_never_returns_record_id(self):
        from run_tips_and_edu_feed import get_slot_item_name_val, SLOTS
        self.assertEqual(get_slot_item_name_val({"SKU2": "HC-1", "Item Name2": ""}, SLOTS[1]), "")
    def test_thumbnail_filtered_from_tagged_carousel(self):
        from run_tips_and_edu_feed import select_tagged_blends_for_layout
        atts = [make_att("temp_thumb_recT.jpg", 0), make_att("tips_edu_feed_tagged_2_recT.jpg", 2),
                make_att("tips_edu_feed_tagged_1_recT.jpg", 1), make_att("tips_edu_feed_tagged_3_recT.jpg", 3)]
        got = select_tagged_blends_for_layout(atts)
        self.assertEqual([a["filename"] for a in got],
            ["tips_edu_feed_tagged_1_recT.jpg", "tips_edu_feed_tagged_2_recT.jpg", "tips_edu_feed_tagged_3_recT.jpg"])
    def test_record_id_substring_does_not_fake_a_slot(self):
        from run_tips_and_edu_feed import select_tagged_blends_for_layout
        atts = [make_att("tips_edu_feed_tagged_1_rec01ABC.jpg", 1),
                make_att("tips_edu_feed_tagged_2_rec01ABC.jpg", 2), make_att("temp_thumb_rec01ABC.jpg", 0)]
        self.assertEqual(len(select_tagged_blends_for_layout(atts)), 2)
    def test_name_normalization_strips_pipe_and_variant_suffix(self):
        from run_tips_and_edu_feed import normalize_tips_edu_tag
        self.assertEqual(normalize_tips_edu_tag("Keyes I | Modern LED Floor Lamp", "Modern LED Floor Lamp", "Chandelier"),
                         ("Keyes", "Modern LED Floor Lamp"))
        t2, s2 = normalize_tips_edu_tag("Zerrie Linear Brass Island Chandelier", "", "Chandelier")
        self.assertEqual(t2, "Zerrie")
        self.assertTrue(s2)
```

- [ ] **Step 2: Run** `python -m unittest tests.test_tips_edu_feed_attach_format -v` — Expect FAIL ImportError.
- [ ] **Step 3: Add stubs** near `sort_attachments_by_slot` in runner:

```python
def get_slot_item_name_val(fields, slot): return ""
def get_slot_product_type_val(fields, slot): return ""
def normalize_tips_edu_tag(raw_name, product_type_val, fixture_label): return ("", "")
def select_tagged_blends_for_layout(attachments): return []
```

- [ ] **Step 4: Re-run** same command — Expect FAIL AssertionError (wired, not implemented).
- [ ] **Step 5: Commit** `git add tests/test_tips_edu_feed_attach_format.py run_tips_and_edu_feed.py && git commit -m "test: add failing Tips Edu Feed attach and name-format regressions"`

### Task 2: Slot field resolution + fail-closed naming (kill or-record_id)

**Files:** Modify `run_tips_and_edu_feed.py:2041-2049`.
**Produces:** `get_slot_item_name_val`, `get_slot_product_type_val`.

- [ ] **Step 1: Test** already in Task 1 (space-variant + empty-name). No new code.
- [ ] **Step 2: Run** the two tests — Expect FAIL (stubs).
- [ ] **Step 3: Implement** near sorter (line ~577):

```python
def _slot_field_candidates(slot, kind):
    base = slot.item_name_field if kind == "name" else slot.product_type_field
    cands = [base]
    for c in (base.replace(" ", ""), base.replace("Name2", "Name 2").replace("Name3", "Name 3").replace("Type2", "Type 2").replace("Type3", "Type 3"), base.strip()):
        if c not in cands: cands.append(c)
    return cands
def get_slot_item_name_val(fields, slot):
    for c in _slot_field_candidates(slot, "name"):
        v = str(fields.get(c) or "").strip()
        if v: return v
    return ""
def get_slot_product_type_val(fields, slot):
    for c in _slot_field_candidates(slot, "type"):
        v = str(fields.get(c) or "").strip()
        if v: return v
    return ""
```

Replace Phase 5 name lines with slot-config lookup; on empty name log WARN, `append_error_log(record_id, 5, ...)`, `all_succeeded=False`, `continue`. Delete `or SKU... or record_id` (REDFLAG H2).
- [ ] **Step 4: Run** the two tests — Expect PASS; then `python -m py_compile run_tips_and_edu_feed.py`.
- [ ] **Step 5: Commit** `git commit -m "fix: resolve Tips Edu slot name fields with space variants, fail closed on empty name"`

---

---
### Task 3: Phase 5 carousel — clear, branded thumb first, deterministic order

**Files:** Modify `run_tips_and_edu_feed.py:2077-2093`.
**Produces:** uploads exactly `[thumb_text, tagged_1..3]`, reruns do not duplicate.

- [ ] **Step 1: Write test** — add method to test file:

```python
    def test_phase5_clears_tagged_field_and_uses_thumbnail_with_text(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        runner = feed.TipsAndEduFeedRunner.__new__(feed.TipsAndEduFeedRunner)
        runner.category_code = "chandeliers"; runner.fixture_label = "Chandelier"
        runner.airtable = mock.Mock()
        runner.airtable.get_record.return_value = {"fields": {
            feed.BLENDED_FIELD: [{"url": "https://example.invalid/b1.jpg", "filename": "tips_and_edu_blended_1_recT.jpg"},
                                 {"url": "https://example.invalid/b2.jpg", "filename": "tips_and_edu_blended_2_recT.jpg"},
                                 {"url": "https://example.invalid/b3.jpg", "filename": "tips_and_edu_blended_3_recT.jpg"}],
            "Item Name": "Zygadlo | Luxury Modern Chandelier", "Item Name2": "Keyes | Modern Floor Lamp",
            "Item Name3": "Dorvalira D | Contemporary Floor Lamp",
            "Product Type": "Chandelier", "Product Type2": "Floor Lamp", "Product Type3": "Floor Lamp",
            feed.THUMBNAIL_WITH_TEXT_FIELD: [{"url": "https://example.invalid/thumb.jpg", "filename": "thumb_text.jpg"}]}}
        tmp = Path(tempfile.mkdtemp())
        runner._artifact_path = lambda rec, name: tmp / name
        runner._download = mock.Mock()
        cleared = {}
        runner.airtable.clear_attachment_field = lambda rec, field: cleared.setdefault(field, True)
        with mock.patch.object(feed, "tag_blended_image", return_value=(mock.Mock(save=mock.Mock()), {"x": 1})), \
             mock.patch.object(feed, "append_error_log"):
            runner.phase_5("recT", execute=True)
        assert cleared.get(feed.TAGGED_BLENDED_FIELD) is True
        self.assertEqual(runner.airtable.upload_attachment.call_args_list[0].args[1], feed.TAGGED_BLENDED_FIELD)
```

- [ ] **Step 2: Run** new test — Expect FAIL (no clear call).
- [ ] **Step 3: Implement** — at phase_5 execute start: `try: self.airtable.clear_attachment_field(record_id, TAGGED_BLENDED_FIELD) / except Exception: pass`. Thumb source = `fields.get(THUMBNAIL_WITH_TEXT_FIELD) or fields.get(THUMBNAIL_FIELD)` uploaded first, then tagged in slot order.
- [ ] **Step 4: Run** `python -m unittest tests.test_tips_edu_feed_attach_format tests.test_tips_edu_feed_failure_status -v` — Expect PASS.
- [ ] **Step 5: Commit** `git commit -m "fix: clear Tips Edu tagged carousel and prepend branded thumbnail"`

### Task 4: Name normalization — clean two-line tag

**Files:** Modify `run_tips_and_edu_feed.py` (new `normalize_tips_edu_tag` near ~577).
**Produces:** `normalize_tips_edu_tag(raw, ptype, fixture) -> (title, subtitle)`, pipe-free, subtitle never empty.

- [ ] **Step 1: Test** already in Task 1. No new code.
- [ ] **Step 2: Run** normalization test — Expect FAIL (stub).
- [ ] **Step 3: Implement:**

```python
import re as _re
_VARIANT_SUFFIX = _re.compile(r"\s+(?:[IVXLCDM]+|[A-Z]|\d+|[A-Z]\d+)$", _re.IGNORECASE)
def normalize_tips_edu_tag(raw_name, product_type_val, fixture_label):
    from content_automation.akeneo_client import split_item_name
    title, subtitle = split_item_name(str(raw_name or "").strip(), str(product_type_val or "").strip())
    title = " ".join(str(title or "").split()).strip().strip("[]\"'`")
    subtitle = " ".join(str(subtitle or "").split()).strip().strip("[]\"'`")
    if "|" in title: title = title.split("|", 1)[0].strip()
    title = _VARIANT_SUFFIX.sub("", title).strip() or title
    if not subtitle:
        subtitle = " ".join(str(fixture_label or "").split()).strip().title() or "Chandelier"
    return title, subtitle
```

`Keyes I | Modern LED Floor Lamp` gives `("Keyes", "Modern LED Floor Lamp")`. Pipe guard in `item_tagger.py:479-483` stays as defense-in-depth.
- [ ] **Step 4: Run** test — Expect PASS; `python -m py_compile run_tips_and_edu_feed.py`.
- [ ] **Step 5: Commit** `git commit -m "fix: normalize Tips Edu item tags to clean two-line title and subtitle"`

### Task 5: Phase 6 source — tagged only, thumbnail excluded, no silent fallback

**Files:** Modify `run_tips_and_edu_feed.py:2114-2142` + new `select_tagged_blends_for_layout`.
**Produces:** exactly 3 tagged slot photos `[1,2,3]` or FM (never untagged fallback).

- [ ] **Step 1: Test** already in Task 1 (thumbnail-filter + rec-id tests).
- [ ] **Step 2: Run** thumbnail test — Expect FAIL (stub).
- [ ] **Step 3: Implement** near sorter:

```python
_SLOT_RE = _re.compile(r"(?:blended|tagged|feed|layout|slide)[-_]?0?([123])\b", _re.IGNORECASE)
_THUMB_RE = _re.compile(r"thumb", _re.IGNORECASE)
def _slot_of(att):
    name = str((att or {}).get("filename") or "")
    if _THUMB_RE.search(name): return None
    m = _SLOT_RE.search(name)
    return int(m.group(1)) if m else None
def select_tagged_blends_for_layout(attachments):
    if not isinstance(attachments, list): return []
    by_slot = {}
    for att in attachments:
        s = _slot_of(att) if isinstance(att, dict) else None
        if s is not None and s not in by_slot: by_slot[s] = att
    if len(by_slot) != 3: return []
    return [by_slot[1], by_slot[2], by_slot[3]]
```

Replace Phase 6 source block: `tagged_for_layout = select_tagged_blends_for_layout(fields.get(TAGGED_BLENDED_FIELD) or [])`; if not 3, WARN + FM + `return False`. Delete `[-3:]` slice and `BLENDED_FIELD` fallback. Rename local cache to `tips_and_edu_tagged_{slot}...`.
- [ ] **Step 4: Run** full new suite + `tests.test_tips_edu_feed_failure_status` — Expect PASS.
- [ ] **Step 5: Commit** `git commit -m "fix: select tagged blends per slot in Tips Edu Phase 6, drop untagged fallback"`
### Task 6: Harden sorter against record-id digit collisions

**Files:** Modify `run_tips_and_edu_feed.py:577-594`.
**Produces:** same `sort_attachments_by_slot` signature; thumb last; slot needs prefix.

- [ ] **Step 1: Test** already in Task 1 (rec-id substring test).
- [ ] **Step 2: Run** it — Expect FAIL on old impl (`01` in rec id fakes slot).
- [ ] **Step 3: Implement:**

```python
def sort_attachments_by_slot(attachments):
    """Sort attachments so slot 1, 2, 3 are in exact order (thumbnail last)."""
    if not isinstance(attachments, list): return []
    def get_slot_index(att):
        if not isinstance(att, dict): return 99
        filename = str(att.get("filename") or "")
        if _THUMB_RE.search(filename): return 99
        m = _SLOT_RE.search(filename)
        return int(m.group(1)) if m else 99
    return sorted(attachments, key=get_slot_index)
```

Stays total (never drops items); strict callers use Task 5 selector.
- [ ] **Step 4: Run** both suites — Expect PASS.
- [ ] **Step 5: Commit** `git commit -m "fix: harden Tips Edu slot sort against record-id digit collisions"`

---

### Task 7: Docs, incident note, full verification

**Files:** Modify `docs/feeds/TIPS_AND_EDU_FEED.md` 6C; create `docs/memory/incidents/2026-10-19-tips-edu-feed-attach-format.md`.

- [ ] **Step 1: Confirm docs stale** — `findstr select_tagged_blends docs/feeds/TIPS_AND_EDU_FEED.md` returns nothing.
- [ ] **Step 2: Update 6C** — append two bullets: attach rule (clear + `[thumb_text, 1..3]`, selector excludes thumb, <3 gives FM) and naming rule (slot-config resolution, normalize helper, never record_id/SKU).
- [ ] **Step 3: Write incident note** with symptom, fix, verification lines.
- [ ] **Step 4: Verify:**

```powershell
python -m py_compile run_tips_and_edu_feed.py content_automation/item_tagger.py content_automation/akeneo_client.py
python -m unittest tests.test_tips_edu_feed_attach_format tests.test_tips_edu_feed_failure_status -v
python -m unittest discover tests
```

Expect all PASS (~469 tests).
- [ ] **Step 5: Commit** `git commit -m "docs: document Tips Edu attach-to-photo and item-name formatting fix"`

---

## Self-Review

1. Spec coverage: Phase 5 tagging Tasks 2-4; Phase 6 compositing Task 5 (correct base photo; Pillow geometry untouched); dual-write out of scope (untouched); H2 Task 2; thumb prepend Task 3; pipe/variant Task 4.
2. Placeholder scan: every step has exact file:line, function names, runnable commands, copy-paste code. No TBD/TODO.
3. Type consistency: `get_slot_item_name_val(fields: dict, slot) -> str`, `normalize_tips_edu_tag(str, str, str) -> tuple[str, str]`, `select_tagged_blends_for_layout(list[dict]) -> list[dict]` used identically throughout.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-10-19-tips-edu-feed-fix-tips-attach-item-name.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.

**2. Inline Execution** — execute in this session with checkpoints.

**Which approach?**


---

---

---


