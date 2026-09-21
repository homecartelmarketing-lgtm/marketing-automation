---
date: 2026-09-21
pipeline: Day & Night Feed (4:5 Ratio)
status: resolved
---

# Day & Night Feed: Logo Watermark & Final Multi-Attachment Field Never Saved to Airtable

## Symptom

1. Newly processed Day & Night Feed rows in Airtable (such as *Zoe Floor Lamp*, *Fabia*, *Janus*) had 0 attachments in the final multi-attachment field **`STORY - Day & Night (2)`**.
2. Slide 1 (**`Day Image`**) in Airtable did not have the HomeCartel logo watermark stamped on it, showing only the un-watermarked blend.

## Diagnosis

1. **Airtable Schema Verified**: Inspection of all 4 Day & Night Feed tables (`tblSceuLVvLMQ6wWp` Chandelier, `tblIgRlTtO7Y2EGIo` Pendant, `tblcKHAVYgzIcmabT` Floor Lamp, `tbljsKOEhc0618qbM` Table Lamp) confirmed that both `Blended Image with Name text` and `STORY - Day & Night (2)` columns exist in the Airtable base.
2. **Discarded Stamped Image**: In `generate_day_night_feed_pipeline.py::finalize_feed_record()`, Step A stamped the HomeCartel logo onto a temp copy of the Day photo (`stamped_day_file`). However, `stamped_day_file` was only used as input for YOLO tagging (`tag_and_upload_blended_image`) and was then immediately deleted in `finally` via `unlink()`. No Airtable attachment field ever received the stamped Day image.
3. **Regression in Final Slide Upload**: An earlier uncommitted refactor removed the code that uploaded `[day_photo.jpg, night_photo.jpg]` to `STORY - Day & Night (2)`, leaving that column completely unpopulated on all new pipeline runs.

## Resolution

In [`generate_day_night_feed_pipeline.py`](../../../generate_day_night_feed_pipeline.py):

1. **Constant Definition**:
   Defined `STORY_FINAL_FIELD = "STORY - Day & Night (2)"`.

2. **Overwrite `Day Image` with Stamped Logo**:
   In `finalize_feed_record()`, after Step A logo stamping, the stamped Day photo is uploaded over `Day Image` using `airtable.clear_attachment_field(record_id, DAY_IMAGE_FIELD)` + `airtable.upload_attachment(...)`.

3. **Populate `STORY - Day & Night (2)`**:
   Uploaded both the stamped Day photo (`day_photo.jpg`) and the Night photo (`night_photo.jpg`) to `STORY - Day & Night (2)` after clearing the field.

4. **Robust Fallback**:
   If logo stamping fails, the pipeline logs a warning and falls back to using the raw `downloaded_day.path`, ensuring that neither `Day Image` nor `STORY - Day & Night (2)` is ever left empty.

5. **Dry-Run Logging**:
   Updated `dry_run` logging to explicitly display:
   - `Would upload stamped Day photo to 'Day Image'`
   - `Would upload stamped Day + Night to 'STORY - Day & Night (2)'`

## Verification

1. `python -m py_compile generate_day_night_feed_pipeline.py` passed with 0 errors.
2. `python run_day_night_feed.py --dry-run` passed with 0 errors, validating the complete sequence of dry-run logs.
