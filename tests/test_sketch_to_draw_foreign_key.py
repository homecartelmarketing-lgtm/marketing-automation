"""Unit test for Sketch to Real / Draw Reel Foreign Key generation."""

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


class SketchToRealForeignKeyTests(unittest.TestCase):
    def test_sketch_to_real_default_prefixes(self):
        self.assertEqual(TABLE_PREFIX_MAP["tblSketchToRealReel"], "STR-REEL-SET")
        self.assertEqual(TABLE_PREFIX_MAP["tblSketchToRealChandeliers"], "STR-REEL-CH")
        self.assertEqual(TABLE_PREFIX_MAP["tblSketchToRealPendants"], "STR-REEL-PE")
        self.assertEqual(TABLE_PREFIX_MAP["tblSketchToRealFloorLamps"], "STR-REEL-FL")
        self.assertEqual(TABLE_PREFIX_MAP["tblSketchToRealTableLamps"], "STR-REEL-TL")
        self.assertEqual(TABLE_PREFIX_MAP["tblSketchToRealCeilingMounted"], "STR-REEL-CM")

    def test_generate_foreign_key(self):
        self.assertEqual(
            generate_foreign_key("tblSketchToRealChandeliers", 1),
            "STR-REEL-CH-1",
        )
        self.assertEqual(
            generate_foreign_key("tblSketchToRealPendants", 42),
            "STR-REEL-PE-42",
        )

    def test_resolve_table_prefix_with_table_name_fallback(self):
        prefix = resolve_table_prefix("tblUnknown123", "Sketch to Real Reel Chandeliers")
        self.assertEqual(prefix, "STR-REEL-CH")

        prefix_pendant = resolve_table_prefix("tblUnknown456", "Sketch to Real Pendant Lights")
        self.assertEqual(prefix_pendant, "STR-REEL-PE")


if __name__ == "__main__":
    unittest.main()
