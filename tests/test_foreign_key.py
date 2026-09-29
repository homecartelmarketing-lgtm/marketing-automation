"""Foreign key mapping tests, including the One at a time Lights Reel table."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
