"""Foreign key mapping tests, including the One at a time Lights Reel table."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.foreign_key import (
    TABLE_PREFIX_MAP,
    generate_foreign_key,
    resolve_table_prefix,
)


class ForeignKeyTests(unittest.TestCase):
    def test_one_at_a_time_lights_prefix_registered(self):
        self.assertEqual(TABLE_PREFIX_MAP["tblJpEtBudQZda319"], "OATL-REEL-LR")

    def test_one_at_a_time_lights_resolves_without_name_fallback(self):
        self.assertEqual(
            resolve_table_prefix("tblJpEtBudQZda319"),
            "OATL-REEL-LR",
        )

    def test_one_at_a_time_lights_foreign_key(self):
        self.assertEqual(
            generate_foreign_key("tblJpEtBudQZda319", 7),
            "OATL-REEL-LR-7",
        )

    def test_existing_reel_prefixes_unchanged(self):
        self.assertEqual(resolve_table_prefix("tblqBZ946hVdOpmDV"), "PCR-REEL-TL")
        self.assertEqual(resolve_table_prefix("tbl6ls4AWcEcynBpZ"), "OP3S-REEL-CH")

    def test_house_tour_reel_prefix_registered(self):
        self.assertEqual(TABLE_PREFIX_MAP["tblqXkdDw4O7hxJS4"], "HTR-REEL-SET")

    def test_house_tour_reel_foreign_key(self):
        self.assertEqual(
            generate_foreign_key("tblqXkdDw4O7hxJS4", 7),
            "HTR-REEL-SET-7",
        )


if __name__ == "__main__":
    unittest.main()
