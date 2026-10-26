"""Unit tests for the shared real-world scale prompt layer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.prompts import build_vision_blending_instruction
from content_automation.prompts.scale import (
    ESTIMATED_PRODUCT_SIZES,
    PRODUCT_TYPE_LABELS,
    SCALE_RULES_VERSION,
    blend_instruction_from_fields,
    build_scale_rule,
    build_size_fact,
    normalize_product_type,
    parse_measurement_cm,
    product_type_label,
    scale_cache_digest,
    scale_clause,
)


class ParseMeasurementTests(unittest.TestCase):
    def test_labelled_axes(self):
        self.assertEqual(parse_measurement_cm("W120*L120*H300cm"), (120.0, 120.0, 300.0))

    def test_labelled_axes_with_spaces(self):
        self.assertEqual(parse_measurement_cm("W 25cm x H 48cm"), (25.0, None, 48.0))

    def test_diameter_becomes_width_and_depth(self):
        self.assertEqual(parse_measurement_cm("Dia 60cm"), (60.0, 60.0, None))

    def test_bare_run_in_inches(self):
        width, depth, height = parse_measurement_cm('12" x 30"')
        self.assertAlmostEqual(width, 30.48)
        self.assertIsNone(depth)
        self.assertAlmostEqual(height, 76.2)

    def test_bare_run_with_shared_unit(self):
        self.assertEqual(parse_measurement_cm("120 x 80 x 25 cm"), (120.0, 80.0, 25.0))

    def test_mm_and_m_units(self):
        self.assertEqual(parse_measurement_cm("W 600mm x H 0.8m"), (60.0, None, 80.0))

    def test_empty_and_garbage_do_not_raise(self):
        self.assertEqual(parse_measurement_cm(""), (None, None, None))
        self.assertEqual(parse_measurement_cm("large statement piece"), (None, None, None))


class SizeFactTests(unittest.TestCase):
    def test_chandelier_height_over_140_is_treated_as_drop(self):
        fact = build_size_fact("chandelier", "W 80cm x H 300cm", label="chandelier")
        self.assertIn("maximum adjustable drop", fact)
        self.assertNotIn("300 cm tall", fact)

    def test_suspicious_width_is_ignored(self):
        fact = build_size_fact("pendant", "W 400cm x H 30cm", label="pendant")
        self.assertIn("implausibly large", fact)
        self.assertNotIn("400 cm wide", fact)

    def test_parsed_size_states_cm(self):
        fact = build_size_fact("chandelier", "W 80cm x H 70cm", label="chandelier")
        self.assertIn("W 80cm x H 70cm", fact)
        self.assertIn("80 cm wide", fact)
        self.assertIn("70 cm tall", fact)

    def test_unparsed_text_is_passed_as_a_hint(self):
        fact = build_size_fact("chandelier", "medium size", label="chandelier")
        self.assertIn('"medium size"', fact)
        self.assertIn("Convert it to centimetres", fact)

    def test_missing_size_uses_type_range(self):
        fact = build_size_fact("floor_lamp", "", label="floor lamp")
        self.assertIn("No supplier dimension", fact)
        self.assertIn("30-50 cm wide", fact)
        self.assertIn("150-180 cm tall", fact)

    def test_missing_type_is_generic(self):
        fact = build_size_fact("unknown object", "", label="the fixture")
        self.assertIn("No supplier dimension or product type", fact)
        self.assertIn("50-90 cm wide", fact)

    def test_article_labels_do_not_double_up(self):
        fact = build_size_fact("table_lamp", "W 25cm x H 48cm", label="the table lamp in Image 2")
        self.assertIn("plausible for the table lamp in Image 2", fact)
        self.assertNotIn("for a the", fact)

    def test_missing_size_with_article_label_stays_grammatical(self):
        fact = build_size_fact("pendant", "", label="the pendant light in Image 4")
        self.assertIn("a typical pendant light in Image 4", fact)
        self.assertNotIn("a typical the", fact)


class TypeNormalizationTests(unittest.TestCase):
    def test_aliases(self):
        expectations = {
            "Cluster Chandelier": "cluster",
            "Multi Pendant": "cluster",
            "Crystal Chandelier": "chandelier",
            "Linear Chandelier": "linear",
            "Kitchen Island Light": "linear",
            "Pendant Light": "pendant",
            "Table Lamp": "table_lamp",
            "Bedside Lamp": "table_lamp",
            "Floor Lamp": "floor_lamp",
            "Wall Sconce": "wall_sconce",
            "Ceiling Mounted": "ceiling",
            "Flush Mount": "ceiling",
            "Something Strange": "fixture",
        }
        for raw, expected in expectations.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_product_type(raw), expected)

    def test_every_normalized_type_has_a_size_range(self):
        for key in ("chandelier", "cluster", "pendant", "table_lamp", "floor_lamp", "wall_sconce", "ceiling", "linear", "fixture"):
            self.assertIn(key, ESTIMATED_PRODUCT_SIZES)

    def test_labels_are_readable(self):
        self.assertEqual(product_type_label("Ceiling Mounted"), "ceiling light")
        self.assertEqual(product_type_label("Cluster Chandelier"), "cluster chandelier")
        self.assertEqual(product_type_label("Something Strange"), "lighting fixture")

    def test_every_size_range_has_a_label(self):
        for key in ESTIMATED_PRODUCT_SIZES:
            self.assertIn(key, PRODUCT_TYPE_LABELS)


class BuilderTests(unittest.TestCase):
    def test_builder_inserts_measurement_and_scale_rule(self):
        instruction = build_vision_blending_instruction(
            "Room Interior",
            "Nordora | Chandelier",
            "9:16",
            product_type="Chandelier",
            measurement="W 80cm x H 70cm",
        )
        self.assertIn("3. SIZE AND SCALE", instruction)
        self.assertIn("W 80cm x H 70cm", instruction)
        self.assertIn("80 cm wide", instruction)
        self.assertIn("210 cm clear above the floor", instruction)
        # The stored "Name | Type" label must not be echoed as the product name.
        self.assertNotIn("'Nordora | Chandelier'", instruction)

    def test_builder_without_measurement_uses_type_range(self):
        instruction = build_vision_blending_instruction(
            "Room Interior",
            "Nordora",
            "9:16",
            product_type="Pendant Light",
        )
        self.assertIn("No supplier dimension", instruction)
        self.assertIn("20-50 cm wide", instruction)

    def test_builder_without_type_or_size_is_generic(self):
        instruction = build_vision_blending_instruction("Room Interior", "Mystery Fixture")
        self.assertIn("No supplier dimension or product type", instruction)

    def test_extra_instructions_stay_before_output_only(self):
        instruction = build_vision_blending_instruction(
            "Room Interior",
            "Nordora",
            "9:16",
            product_type="Chandelier",
            extra_instructions="Do not move the sofa.",
        )
        self.assertLess(instruction.index("Do not move the sofa."), instruction.index("Output ONLY"))
        self.assertIn("3. SIZE AND SCALE", instruction)

    def test_blend_instruction_from_fields_reads_slot_zero(self):
        fields = {
            "Item Name": "Nordora | Chandelier",
            "Product Type": "Chandelier",
            "Measurement": "W 80cm x H 70cm",
        }
        instruction = blend_instruction_from_fields(fields, 0, aspect_ratio="9:16")
        self.assertIn("W 80cm x H 70cm", instruction)
        self.assertIn("80 cm wide", instruction)


class ScaleClauseTests(unittest.TestCase):
    def test_clause_includes_its_own_label(self):
        clause = scale_clause("table_lamp", "W 30cm x H 60cm", label="the table lamp in Image 2")
        self.assertIn("the table lamp in Image 2", clause)
        self.assertIn("30 cm wide", clause)
        self.assertNotIn("pendant", clause.lower())


class CacheDigestTests(unittest.TestCase):
    def test_same_inputs_same_digest(self):
        self.assertEqual(
            scale_cache_digest("Chandelier", "W120*H80cm"),
            scale_cache_digest("chandelier", "W 120 x H 80 cm"),
        )

    def test_measurement_or_type_changes_digest(self):
        base = scale_cache_digest("chandelier", "W 80cm x H 70cm")
        self.assertNotEqual(base, scale_cache_digest("chandelier", "W 90cm x H 70cm"))
        self.assertNotEqual(base, scale_cache_digest("pendant", "W 80cm x H 70cm"))

    def test_digest_carries_the_rules_version(self):
        self.assertEqual(SCALE_RULES_VERSION, "scale-v1")
        self.assertEqual(len(scale_cache_digest("chandelier", "")), 10)


class ScaleRuleTests(unittest.TestCase):
    def test_rule_is_numbered_three_and_mentions_ceiling(self):
        rule = build_scale_rule("chandelier", "W 80cm x H 70cm", label="chandelier")
        self.assertTrue(rule.startswith("3. SIZE AND SCALE"))
        self.assertIn("ceiling height", rule)
        self.assertIn("80-90 cm above a dining table", rule)


if __name__ == "__main__":
    unittest.main()
