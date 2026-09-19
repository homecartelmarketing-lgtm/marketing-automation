# Decision: Purged 7 dead entries from `TABLE_PREFIX_MAP` (2026-09-19)

During the docs-alignment pass we audited all 84 entries in `content_automation/foreign_key.py::TABLE_PREFIX_MAP` against the live Airtable base `appDM0jUDsaiThtR3` (`GET /meta/bases/.../tables`). Seven IDs do not exist in the base and were removed:

| Removed ID | Prefix | Why it was wrong |
| :--- | :--- | :--- |
| `tblRy52kCasisCwzd` | `OP3S-FEEDS-PE` | Case typo of the real `tblRy52kCasisCWzd` (Pendant Light 1 Product 3 Style Feed) |
| `tbltB7eKk4eQ90p1Z` | `OP3S-FEEDS-CH` | Duplicate of live `tblrlfqBGe5EjS5PI`; table never existed |
| `tbl5A7mN2pQ3eR8v0` | `OP3S-FEEDS-FL` | Placeholder-looking ID; duplicate of live `tbl9GIq2QeYCwMhWU` |
| `tblenVlUWDFqWDJ08` | `DN-STORY-TL` | Also still present in `.env.example` as `AIRTABLE_TABLE_ID_TABLE_LAMPS_DAY_NIGHT_STORY`; real table is `tblhvM9Saq18YqONB` |
| `tblFCavAUXzygHAt9` | `DN-STORY-CL` | Duplicate of live `tblgcvB4WFKOpSIQl` |
| `tblkAAzSXbb532uGL` | `MB-REEL-FL` | Duplicate; real table is `tblF3ot4fdHN2VCQn` |
| `tbl2VoWOt7sSut4E2` | `DN-REEL-FL` | Former Before & After / Day & Night Floor Lamp table — deleted from the base |

**Follow-ups this surfaced (NOT yet done):**
- The **Before & After Reel Floor Lamp table was deleted from the base**, but `generate_before_after_reel_pipeline.py` still defaults to `--target floor_lamps` (`DEFAULT_CATEGORY = "floor_lamps"`, and its fallback env is oddly `AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL` which points at the Day & Night reel table). Running the BA reel without `--target` will hit a missing/wrong table. Either recreate `AIRTABLE_TABLE_ID_BEFORE_AFTER_FLOOR_LAMPS` in Airtable or change the default to `chandeliers`.
- `.env.example` still sets `AIRTABLE_TABLE_ID_TABLE_LAMPS_DAY_NIGHT_STORY=tblenVlUWDFqWDJ08` (non-existent table) and `AIRTABLE_TABLE_ID_BEFORE_AFTER_FLOOR_LAMPS=tbl2VoWOt7sSut4E2` (deleted).
