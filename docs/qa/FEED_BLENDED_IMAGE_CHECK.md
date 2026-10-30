# Feed Blended-Image Check — instructions for the checker

> Audience: the AI reviewer (Claude) that checks generated Feed images **before a human sees them**.
> Written 2026-10-29 from a read-only scan of the live Airtable base (21 feed tables, 102 tables in the base), then updated with a vision pass over the 11 `For Manual`/`Discard` rows (§5).
> Companion plan: `C:\Users\User\.hermes\plans\2026-10-29_143500-qa-gate-before-airtable.md` (the automated gate). This file is the *rubric and field map* that plan's reviewer follows for Feeds.

## 0. What you are doing

For each Feed row that is waiting for review, look at the blended room photos and decide **Pass / Review / Reject**:

1. **Accurate** — is the product in the room the same product as the cutout (shape, finish, colour, parts), exactly once?
2. **Fits the interior** — correct size for the room, mounted/standing where it physically makes sense, the old fixture removed, room unchanged, lighting believable.
3. **Quality / vibe** — photorealistic, no AI artifacts, matches HomeCartel's Instagram look (warm, editorial, luxury, uncluttered).
4. **Finish** — item-name tag and logo present and correct, no placeholder text, nothing clipped.

You can only see what you are given. If an image cannot be opened or compared, the verdict is **Review** with the reason, never Pass.

## 1. Rules of engagement

- **Read-only by default.** Do not write to Airtable, change `Status`, delete or re-upload attachments. The QA columns (`QA Verdict`, `QA Flags`) do not exist yet. Output is a report in chat (format in §6).
- Only look at the Feed tables listed in §3. Do not scan other tables.
- Never print or store the Airtable token or any key. Attachment URLs expire after a few hours — fetch, review, discard.
- A human makes the final call. You reduce their work, you do not replace the decision.

## 2. What each Status means (verified in the data)

| Status | Meaning for you |
|---|---|
| `Posted`, `Scheduled` | **Human-approved.** Use as the *good* reference. |
| `For Manual`, `Discard` | **Human-rejected** (or the pipeline failed the row). Use as the *bad* reference. No reason is stored anywhere (there is no notes column in any feed table), so you must infer why. |
| `Complete` / `Done` / `Completed` | **Generated, not yet reviewed. These are the rows you check.** Do not treat them as approved. |
| `Standby`, `Processing`, `In progress`, `Phase N - …`, `Already attached a room Interior`, `Interior Generated`, `Blended Image Generated`, blank | Unfinished. Skip. |

Counts when this was written: approved 63, rejected 11, **pending 19** (Tips & Edu 2, Collection Category 2, Moodboard #1 7, Moodboard #2 1, 1 Product 3 Styles 2, Day & Night 4, Product Showcase 1). Re-fetch; these change.

## 3. Field map per feed (Airtable base `appDM0jUDsaiThtR3`)

"Blend field" = what you judge. "Reference inputs" = what you compare it against. "Approved count" = number of files seen in `Posted`/`Scheduled` rows; a pending row with a different count gets a flag.

### 3.1 Tips & Educational — `TNE-FEEDS-<CH|PE|FL|CL>`
- Tables: Chandelier `tblQ65S51Dmauwx4c`, Pendant `tblIhCP3Gjg09QFCK`, Floor Lamp `tblQuhvktqYB59Ofw` (0 rows), Cluster `tblwY6eGQCD5bJeF1` (0 rows).
- **Blend field: `Tips and Edu Blended`** — 3 raw blends (slide N = product N in Interior N). Approved count: **3** (13 rows) or 4 (2 rows, a duplicate-upload leftover).
- Companions: `Tips and Edu Blended Attach Item Name` (4 = thumbnail + 3 tagged blends), `Blended Image with Name text` (3, but empty on 11 of 15 approved rows — do not require it), `Tips and Edu Feeds` (3 final slides with numeral + tip text; this is what ships), `Thumbnail with Text` (cover).
- Reference inputs: `Interior1/2/3` (room before), `Furniture Item` (slot 1), `Furniture Item2`, `Furniture Item3` (slots 2, 3; `Furniture Item4` is an unused 4th scrape), `Item Name`, `Item Name2..4`, `Product Type`, `Measurement`, `Tips 1..3`.
- Also check: the three tips read as sensible lighting advice for that room/fixture, no typos.

### 3.2 Collection Category — `CC-FEEDS-SET-<n>`
- Tables: `tbl5o1j3XvUaUqmjs` (Collection Category Feed, the live one), `tbl0R6o61lGJmt44n` (Chandelier Collection Category, 1 blank row — ignore).
- **Blend field: `Blended Image with Name text`** — **4 photos** = slides 2–5 (bedroom, dining room, kitchen, living room) each with the item-name tag. Approved count: 4 (5 rows) or 0 (5 rows — the tag step did not mirror; then judge `Blended Image2..5` instead and flag "tag column empty").
- Slide 1 is the exterior cover in `Blended Image1` (no tag, logo only). `Blended Image1..5` = 5 files, one each. **Output UI shows `Blended Image1..5`**, not the tagged field — check both and confirm they are the same pictures.
- Reference inputs: `Interior2..5`, `Furniture Item2`, `Furniture item3` (lowercase i, real column name), `Furniture Item4`, `Furniture Item5`, `Item Name1..5`, `Suggest Furniture Item2..5`, `Blending Prompt2..5`.
- Also check: the four fixtures look like one coordinated collection, and each room matches its slot (bedroom lamp is a bedroom-appropriate fixture, etc.).

### 3.3 Moodboard #1 — `MB1-FEEDS-<CH|PE|FL>`
- Tables: Chandelier `tbl9u5vjgx8kuE44R`, Pendant `tblOvvYdgsNTXh2zK`, Floor Lamp `tbl6uTmwM23KK9ocO`.
- **Blend field: `Moodboard V1 Blended`** — slide 1, the product blended into `Interior Generated`, name-tagged. Approved count: 1 or 2 (4 approved rows: two have 2 files). **Open question 2.**
- Companions: `Blended Image with Name text` (mirror, 1–2), `Moodboard Added Watermark` (slide 2 = slide 1 + logo), `Moodboard Converted` (slide 3, 3-swatch material board), `Closeup Photo` (slide 4, macro detail).
- Reference inputs: `Interior Generated`, `Furniture Item`, `Item Name`, `Prompt for Blending`.
- Also check: slides 2–4 are consistent with slide 1 (same room, same product materials in the swatches/closeup).

### 3.4 Moodboard #2 — `MB2-FEEDS-<CH|PE|FL|WL>`
- Tables: Chandelier `tbltWgQKOYjuHw6tx`, Pendant `tbl4TiV90SzdBz4KG`, Floor Lamp `tbl4YF9iXlBqGblEc`, Wall Lights `tbljUk9JwzS1JeZJg` (0 rows).
- **Blend field: `Blended Image`** (1 file, watermarked; slide 1). `Blended Image with Name text` is the tagged copy and is often empty (4 of 5 approved rows) — do not require it.
- **Quirk:** the Floor Lamp table stores its slide-1 blend in `Moodboard V1 Blended` and its room in `Interior Generated`, not `Blended Image` / `Interior Photo`.
- Slide 2 = `Moodboard #2 Converted` (flat-lay of two interior photos + 7–12 swatches). Check that its swatches and photos come from the slide-1 room.
- Reference inputs: `Interior Photo`, `Furniture Item`, `Item Name`, `Blending Prompt`.

### 3.5 1 Product, 3 Styles — `OP3S-FEEDS-<CH|PE|FL>`
- Tables: Chandelier `tblrlfqBGe5EjS5PI`, Pendant `tblRy52kCasisCWzd`, Floor Lamp `tbl9GIq2QeYCwMhWU`.
- **Blend field: `1 Product 3 Style Blended`** — exactly **3** files (3/3 on all 13 approved rows) + mirror `Blended Image with Name text` (3). Slide 1 also carries the logo.
- The key rule: **the same single product must appear in all three rooms** and look identical in each. Three different-looking fixtures = Reject.
- Reference inputs: `Interior1/2/3`, `Furniture Item`, `Item Name`, `Product Type`.

### 3.6 Day & Night — `DN-FEEDS-<CH|PE|FL|TL>`
- Tables: Chandelier `tblSceuLVvLMQ6wWp`, Pendant `tblIgRlTtO7Y2EGIo`, Floor Lamp `tblcKHAVYgzIcmabT`, Table Lamp `tbljsKOEhc0618qbM`.
- **Blend fields: `Day Image` (1) and `Night Image` (1)**; `Blended Image with Name text` (2) is the tagged pair (empty on 2 of 8 approved rows). Output UI shows Day + Night.
- Rule: same room, same camera angle, same fixture in both. Night must have the fixture visibly **on** with believable light bloom; day must look like daylight. If the room layout, furniture or fixture differs between the two = Reject.
- Reference inputs: `Interior Generated Photo`, `Furniture Item`, `Item Name`.

### 3.7 Product Showcase — `PS-FEEDS-TL-<n>`
- Table: Table Lamp `tbln0MNBaVVrZ0wrF` (only table with rows).
- **Not a room blend.** Studio podium scene. **Field: `FEED - Product Showcase Feed`** — exactly **4** files (4/4 on all 8 approved): slide 1 = 3 lamps on pedestals, slides 2–4 = one solo spotlight each. Logo on all 4.
- Reference inputs: `Furniture Item1..3`. Check that slide 1 shows all three lamps, each solo slide shows the matching lamp, and the lamps are not duplicated or merged.
- `Solo Thumbnail`, `Multiple Platform`, `Blended Image with Name text` are inconsistent across approved rows; ignore them.

## 4. Procedure for one pending row

**Step A — fetch** the row (snippet in §8) and download the images listed in §3 for the blend field and the reference inputs. Re-fetch right before reviewing; attachment URLs expire in hours.

**Step B — free deterministic checks (do these first):**

| Check | Failing means |
|---|---|
| File count in the blend field equals the "approved count" in §3 | Too few = Reject (incomplete; `CC-FEEDS-SET-5` had blends for only 2 of its 4 rooms). More than expected = Review (duplicate-upload leftover). |
| Image shape. Raw blend fields (`Tips and Edu Blended`, `Day Image`, etc.) are **928×1152 (4:5)** straight from the model. Only finished, composited slides (`Tips and Edu Feeds`, Product Showcase) are 1080×1350. | Aspect not 4:5 (±3%) = Reject. Do not reject a raw blend for being 928×1152. |
| Item names present in the slot-numbered columns (`Item Name`, `Item Name2..`; Collection Category and Product Showcase use `Item Name1..N`). Do not read only `Item Name`: it is blank on `CC-FEEDS-SET-25` while `Item Name1..4` are filled. | Any slot name blank, a `rec…` ID, or `Furniture Item` = Reject (the tag will be wrong). |
| `Measurement` / `Measurement2..` | **Empty on all 120 feed rows today (0/120); `Product Type` is filled on only 3/120.** So there is no supplier size to compare against. Do the reference-object scale check in §5A. If a Measurement ever appears, use rule 1 of §5A. |
| `Scale Check` / `Scale Audit` (written by the pipeline's scale guard) | Present on only 6 of 120 feed rows. If it says `Too Big`, `Too Small` or `Error` = Review. |
| `Caption Generated` on Feed rows | Blank = Review (0 of 63 approved rows have one yet, so never Reject on this). |

**Step C — visual check, one slide at a time.** Give the vision model the images in a fixed order: **room before, product cutout(s), blended result, finished slide (if any)**, plus any extras (cover, swatch board, closeup). Ask for **facts as JSON**, not a verdict. The shape used in the 2026-10-29 pass (script in `docs/qa/evidence/run_vision_feed_check.py`):

```json
{"slides":[{"label":"","fixture_count":0,"matches_cutout":"yes|partial|no|na",
 "competing_fixture_left":false,"placement_plausible":true,
 "scale_reference":"","est_width_cm":null,"est_height_cm":null,"listed_width_cm":null,
 "scale_ratio":null,"size":"ok|too_big|too_small|na","scale_reasoning":"",
 "room_preserved":true,"artifacts":[],"photoreal":1,"vibe":1,
 "tag_present":null,"tag_text":"","logo_count":null,"finished_slide_issues":[],"notes":""}],
 "row":{"same_product_across_slides":null,"same_room_across_slides":null,
        "extras_consistent":null,"overall_notes":""}}
```
Questions behind those keys: how many copies of the product, does it match the cutout, is a competing fixture left, is it mounted/standing correctly, **how big is it in cm against a visible reference object (§5A)**, is the room unchanged, visible defects, photoreal and vibe 1–5, is the item-name tag present/legible/correct, how many logos, any clipped or overlapping text.

**Step D — decide per slide, then per row (worst slide wins).** Thresholds below come from the vision pass on the 11 rejected rows (§5). Treat them as the current best guess; the false-positive rate on approved rows has **not** been measured yet.

- **Reject** if any of:
  - blend photo missing / row incomplete;
  - product count ≠ 1 (Showcase hero: ≠ 3), or `matches_cutout = no`;
  - the room in the blend is not the room in `room_before` (a different scene, e.g. `TNE-FEEDS-CH-6` slides 2–3);
  - a floor lamp or table lamp is not standing on a floor/surface (`CC-FEEDS-SET-25` Valhalla sat on the sofa/coffee-table corner with no contact shadow);
  - the product differs between slides that must show the same one (1P3S rooms; Showcase hero vs solo; Day vs Night);
  - scale rule 2 of §5A hits the Reject line.
- **Review** if any of:
  - `partial` match or product design drift (mirrored, doubled ring/globe, wrong shape);
  - any scale rule of §5A hits the Review line;
  - a competing or old fixture is still lit/visible (`DN-FEEDS-CH-6` day slide kept a lit wall sconce);
  - a **major artifact**: the room changed, objects doubled, garbled or illegible tag text, an object floating or ungrounded;
  - a colour cast on the room compared with `room_before` (warm yellow cast on furniture and floor in `TNE-FEEDS-CH-5`, `-6`, `-9`);
  - finished-slide problems: tip text covering furniture/product, tag illegible or cut off, text clipped;
  - photoreal ≤ 3 or vibe ≤ 3;
  - the Step B flags above.
- **Minor, never enough on their own:** slight softening, a small decor item removed or added, garbled text on a book, a barely visible light streak. Every slide in the pass had at least one of these, so counting "any artifact" as Review would flag everything.
- Pass otherwise. When unsure between Pass and Review choose Review; between Review and Reject choose Review. The human decides.

## 5. What the vision pass on the 11 rejected rows showed (2026-10-29)

Only `For Manual` / `Discard` rows were reviewed (by the user's instruction: those are the basis for learning). Reviewer: Claude Sonnet via Claude Code (subscription), blind to the row status, one call per row with the room, cutouts, blends and finished slides. Raw results: `docs/qa/evidence/feed_vision_rejected_2026-10-29.json`.

| Row | Status | What the vision pass found (blend photos unless stated) | Why a rule would catch it |
|---|---|---|---|
| `TNE-FEEDS-CH-7` rec0gFogg3RBQLN3e | Discard | Slide 1: 8-globe chandelier ≈190 cm wide, about 3.5× the framed portraits, wider than the sofa → `too_big`. Slide 3: fixture mirrored vs cutout. Slide 2: rug yellow cast + a hard gray rectangle on the rug. | scale (§5A rule 2), design drift, colour cast |
| `TNE-FEEDS-CH-9` recOVjiL5W4TLnrp2 | Discard | Blends fine (est. 120–200 cm, all `ok`). **Finished slides** are the problem: tip text lies over furniture on all three, tags small/low contrast (one white on a white curtain, nearly illegible), sofa/rug tones shifted warmer. | finished-slide check, colour cast |
| `TNE-FEEDS-CH-5` recb6okDbhZCavevt | For Manual | Scale `ok` on all 3 (105/170/140 cm). Warm yellow cast on sofa and floor, strongest on slide 1; slide 2 fixture floats between dining and lounge zones, not over a table. Tagged copy empty. | colour cast, off-centre placement (weak) |
| `TNE-FEEDS-CH-6` recrA7IGiifJktVMT | For Manual | Slide 1 fine. **Slides 2 and 3 are not the room in `room_before`** (new scene), slide 3 product design drifted (`partial`). Slide 2 has two extra suspension wires not in the cutout. | room replaced = Reject |
| `CC-FEEDS-SET-5` recEZh2JFgFUcQ5Nz | Discard | **Only 2 of 4 room blends exist** (kitchen, living room missing; tagged copy absent). Room 3 table lamp ≈65×80 cm → `too_big`. Images re-cropped narrower. | file count (Step B), scale |
| `CC-FEEDS-SET-25` recfzGU0YVNlIJRSd | Discard | Bedroom: ring and globe doubled (`partial`). Dining: chandelier hangs only 40–60 cm above the table top, off-centre over the artwork. Kitchen: semi-flush ≈115 cm wide, oversized next to the hood, floats off the island → `too_big`. Living room: floor lamp sits on the sofa/table corner, not the floor, no glow, tag overlapping plant leaves. | design drift, hanging height, scale, grounding |
| `MB1-FEEDS-CH-101` recu7wBr0zQGM4zmn | For Manual | Only minor findings: garbled book cover, logo touching the ottoman trim, low-contrast tag, arms slightly shortened vs cutout. Scale ≈145 cm, `ok`. | **not explained** (see §5B) |
| `OP3S-FEEDS-CH-3` rec5NlHXJzXh3fAlJ | Discard | Same ring chandelier in all three rooms but **≈190, 230 and 200 cm wide: `too_big` in every room**, crowding the window and artwork. | scale (strongest signal in the set) |
| `DN-FEEDS-CH-6` rec0pH8z06y2V2ncf | For Manual | Day: old brass wall sconce still lit next to the new pendant (competing fixture), tag nearly invisible and cut off, pendant has no shadow and glows in full daylight. Night: sconce gone, garden replaced by darkness, **no tag and no logo**, so day and night are not the same room. | competing fixture, tag legibility, room not preserved between slides |
| `PS-FEEDS-TL-11` recMOGrw1ROCXUHGl | For Manual | Hero slide shows a perfect-sphere globe lamp but the solo Silgrin slide shows the oval pebble glass from the cutout: **the product differs between hero and solo**. Back lamp ≈1.6× taller than the solo ratio (cutouts say ≈1.13×). | cross-slide product match, relative scale |
| `PS-FEEDS-TL-15` recVl3FdpF33J0vsp | For Manual | **No defect found.** Hero lamps match the solos in order; heights ≈45–60 cm, plausible. | **not explained** (see §5B) |

Nine of the eleven have a concrete, rule-catchable finding (`TNE-5` is the weakest: a colour cast only). Two have none.

### 5A. Scale rules learned (the user's main concern)

1. **Supplier size is not available** (`Measurement` is empty on all 120 feed rows), so scale must be judged from a reference object visible in the room (door ≈200 cm, sofa seat ≈45 cm, dining table top ≈75 cm, kitchen counter ≈90 cm, ceiling ≈260 cm). Ask the vision model for the fixture's estimated width and height in cm and for the reference it used. When a Measurement *is* present, compare: estimated width ÷ listed width outside 0.7–1.4 = Review.
2. **Compare the estimate with the typical size for the product type** (`content_automation/prompts/scale.py`, `ESTIMATED_PRODUCT_SIZES`): chandelier 60–100 cm wide, cluster 50–120, pendant 20–50, linear 90–150, table lamp 25–45 wide and 45–75 tall, floor lamp 30–50 wide and 150–180 tall, wall sconce 10–25, ceiling light 30–60. **Current guess:** estimated width ≥ 1.5× the type's maximum = Review; ≥ 2× = Reject candidate for the human to confirm. Evidence: `OP3S-FEEDS-CH-3` ring chandelier 190/230/200 cm (1.9–2.3× the 100 cm max); `CC-FEEDS-SET-25` Hedda 115 cm vs a 50 cm pendant max (2.3×); `CC-FEEDS-SET-5` table lamp 65×80 cm vs 25–45 wide (1.4×, flagged borderline); `TNE-FEEDS-CH-7` slide 1 ≈190 cm (1.9×). **Counter-evidence you must not ignore:** the reviewer called `TNE-FEEDS-CH-7` slide 2 (ring, ≈210 cm) and `TNE-FEEDS-CH-9` slide 2 (leaf pendant ≈150 cm, 3× the pendant max) "ok". Either those are legitimately large statement pieces or the verdict is unstable, so these thresholds are untested. Product type must therefore come from the cutout/name; today the column is empty, so identify it from the cutout.
3. **Do not trust one scale verdict.** The same slide (`TNE-FEEDS-CH-7` slide 1) was judged "a little smaller than the original fixture but in proportion" in the first run and `too_big` (≈190 cm) in the second. Use the estimated centimetres with the type table above, run the check twice, and take the larger estimate when they disagree.
4. **Hanging height.** Lowest part of a dining fixture should be about 80–90 cm above the table top and a kitchen-island fixture 85–95 cm above the counter, with at least 210 cm clear above the floor where people walk (same rule the pipeline's blend prompt uses). `CC-FEEDS-SET-25` Deimos hung 40–60 cm above the table → Review.
5. **Grounding.** Floor and table lamps must touch the floor/surface and cast a contact shadow; hanging fixtures need a canopy on the ceiling. A fixture that floats or stands on furniture is a Reject.
6. **Relative scale across slides of one post.** Showcase hero vs solos and 1P3S rooms must agree on the product's proportions. `PS-FEEDS-TL-11` hero back lamp was ≈1.6× taller than the solo ratio. Review when relative height differs by more than ~25%.
7. **Placement relative to what it serves.** A statement chandelier should sit over the table/seating it belongs to, not off to the side (`TNE-6` slide 2, `CC-25` slides 3–4).

### 5B. What the pass could not explain

- `PS-FEEDS-TL-15`: no visible defect. Either the reviewer missed something, the human rejected for a non-visual reason (a failed phase also writes `For Manual`), or taste.
- `MB1-FEEDS-CH-101`: only minor issues (garbled book text, logo touching trim, tag contrast).
- Ask the user for one line each (§9). Do not invent a reason.

### 5C. Limits of this calibration

- Eleven rows, one reviewer run each (two runs on one slide disagreed). It is a sanity set, not training data.
- Only rejected rows were checked, so the **false-positive rate is unknown**: a rule that flags all 11 rejects could also flag most approved rows. Before relying on these thresholds, run them on ~10 `Posted`/`Scheduled` rows (needs the user's OK) and loosen anything that flags approved work.
- Vision models read cm from pixels with a rough reference; treat the numbers as ±30%.
- Colour cast and tag legibility can be measured without a vision model (colour statistics against `room_before`; contrast ratio around the tag box), which would be cheaper and stable.

## 6. Report format (one block per pending row)

```
<Feed> · <Foreign Key ID> · <record id> · <table name>
Item: <Item Name | Product Type>   Status now: Complete   Scale Check: <value or none>
Verdict: PASS | REVIEW | REJECT
  slide 1 (<field>): <Pass/Review/Reject> — <one line why, with the fact that triggered it>
  slide 2 …
Free checks: counts <ok/x>, size <ok/x>, item name <ok/x>, caption <present/blank>
Evidence: <what you compared; e.g. "cutout has 3 glass tiers, blend shows 2">
```
Finish with a summary table: row, verdict, main reason. Sort Reject first, then Review, then Pass. Do not claim an image looks fine if you could not open it.

## 7. Known data quirks (do not report these as image defects)

- **Field names differ per table.** Always use the table-specific fields in §3 (MB2 Floor Lamp uses `Moodboard V1 Blended` / `Interior Generated`; CC has `Furniture item3` in lowercase; the Tips tables carry ~40 unrelated leftover attachment columns like `Moodboard V1`, `STORY - CTA (1)` — ignore them).
- **Tagged mirror `Blended Image with Name text` is unreliable:** empty on 11/15 TNE approved rows, 5/10 CC, 4/5 MB2, 2/8 DN, 6/8 PS. Empty is not a defect unless §3 says the feed requires it.
- **What the human sees is not always the blend field.** The Output UI shows: TNE = `Thumbnail with Text` + `Tips and Edu Feeds`; CC = `Blended Image1..5`; MB2 = `Moodboard #2 Converted` + `Blended Image`; D&N = `Day Image` + `Night Image`; the rest per `lib/output-media.ts`. Check the blend field **and** the shipped field and confirm they are the same pictures with the tag/text/logo correctly applied.
- Duplicate uploads: two approved TNE rows have 4 files in `Tips and Edu Blended`. A pending row with 4 should be Review, not Reject.
- Several tables are nearly empty (TNE Floor Lamp/Cluster 0 rows, MB2 Wall Lights 0). Normal.

## 8. How to fetch (read-only)

Run from `C:\Users\User\Desktop\marketing-automation` (credentials come from `.env`; the snippet never prints them):

```python
import requests
from content_automation.config import load_settings

s = load_settings()
H = {"Authorization": f"Bearer {s.airtable_token}"}
BASE = s.airtable_base_id

def pending_rows(table_id):
    """Rows waiting for review: Status Complete/Done/Completed."""
    rows, offset = [], None
    while True:
        params = {"pageSize": 100, "filterByFormula": "OR({Status}='Complete',{Status}='Done',{Status}='Completed')"}
        if offset:
            params["offset"] = offset
        r = requests.get(f"https://api.airtable.com/v0/{BASE}/{table_id}", headers=H, params=params, timeout=60)
        r.raise_for_status()
        j = r.json()
        rows += j["records"]
        offset = j.get("offset")
        if not offset:
            return rows

# attachments come back as [{"url": ..., "filename": ..., "width": ..., "height": ...}]
for row in pending_rows("tblQ65S51Dmauwx4c"):
    f = row["fields"]
    print(row["id"], f.get("Foreign Key ID"), len(f.get("Tips and Edu Blended", [])), f.get("Scale Check"))
```

To review images, pass the attachment URLs to the vision model in this order: **room (before), product cutout, blended result** (never the blended result alone). The pipeline's own call is `FalClient.generate_claude_vision(prompt, image_urls)` in `content_automation/fal_client.py`.

## 9. Open questions for the user (answers change the rubric)

1. **Why were these rejected?** One line each, especially `PS-FEEDS-TL-15` (no defect found), `MB1-FEEDS-CH-101` (minor findings only) and `TNE-FEEDS-CH-5` (colour cast only). Those three decide whether the rubric is missing something the human sees.
2. **Is "too big" the main reason** for `OP3S-FEEDS-CH-3` (ring chandelier ≈190–230 cm in all three rooms) and `TNE-FEEDS-CH-7`? If yes, rule 2 of §5A is right in direction and only the cut-off needs tuning.
3. Which large statement fixtures are **fine** (so the cut-off does not reject them)? The reviewer called a ≈210 cm ring and a ≈150 cm leaf pendant "ok".
4. Is it intended that Tips & Educational **finished slides carry no HomeCartel logo** (docs say the logo is on the cover only)? The reviewer reported it missing on all three slides of `TNE-FEEDS-CH-9`.
5. May I run the rubric on ~10 `Posted`/`Scheduled` rows to measure false positives? (Subscription usage only, read-only.)
6. Moodboard #1: should `Moodboard V1 Blended` hold 1 file or 2? Approved rows have both.
7. Collection Category: the human sees `Blended Image1..5`; the tagged `Blended Image with Name text` has 4. Which one do you judge?
8. The real brand look (one paragraph, plus 5–10 best-performing post images). Until then vibe only produces Review.
9. `Measurement` is empty on all feed rows and `Product Type` is almost empty. The pipeline now writes both for **new** rows (2026-10-26 scale work). Do you want the checker to read them as soon as they appear, and should old rows be backfilled?
