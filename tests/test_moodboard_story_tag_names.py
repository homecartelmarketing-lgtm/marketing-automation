"""Moodboard Story tag names: Line 2 product type must survive the anchor handoff.

Regression test: `AirtableClient.product_from_record` splits
"Trude Une | Modern Floor Lamp" into bare `anchor.item_name` +
`anchor.product_type`. The workflow used to re-split the bare name with
only the (usually empty) "Product Type" field as fallback, so the tag
rendered Line 1 only. `resolve_item_tag_names` must prefer
`anchor.product_type`.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace


def make_anchor(item_name="", product_type="", fields=None, sku="SKU-1"):
    return SimpleNamespace(
        item_name=item_name,
        product_type=product_type,
        fields=dict(fields or {}),
        sku=sku,
        record_id="recTEST",
    )


class ResolveItemTagNamesTests(unittest.TestCase):
    def test_bare_name_with_anchor_product_type(self):
        # Exact Trude Une case: bare anchor name, type only on anchor, no field.
        from content_automation.workflows.moodboard_story import (
            resolve_item_tag_names,
        )

        anchor = make_anchor(item_name="Trude Une", product_type="Modern Floor Lamp")
        self.assertEqual(
            resolve_item_tag_names(anchor), ("Trude Une", "Modern Floor Lamp")
        )

    def test_pipe_name_still_splits(self):
        from content_automation.workflows.moodboard_story import (
            resolve_item_tag_names,
        )

        anchor = make_anchor(item_name="Ray | Pendant Light")
        self.assertEqual(resolve_item_tag_names(anchor), ("Ray", "Pendant Light"))

    def test_field_product_type_fallback(self):
        from content_automation.workflows.moodboard_story import (
            resolve_item_tag_names,
        )

        anchor = make_anchor(
            item_name="Aegnor", fields={"Product Type": "Chandelier"}
        )
        self.assertEqual(resolve_item_tag_names(anchor), ("Aegnor", "Chandelier"))

    def test_anchor_product_type_beats_field(self):
        from content_automation.workflows.moodboard_story import (
            resolve_item_tag_names,
        )

        anchor = make_anchor(
            item_name="Yareli",
            product_type="Table Lamp",
            fields={"Product Type": "Stale Type"},
        )
        self.assertEqual(resolve_item_tag_names(anchor), ("Yareli", "Table Lamp"))

    def test_shared_helper_matches_workflow_wrapper(self):
        from content_automation.item_tagger import resolve_tag_names

        anchor = make_anchor(item_name="Trude Une", product_type="Modern Floor Lamp")
        self.assertEqual(
            resolve_tag_names("Trude Une", anchor), ("Trude Une", "Modern Floor Lamp")
        )

    def test_shared_helper_empty_everything(self):
        from content_automation.item_tagger import resolve_tag_names

        anchor = make_anchor()
        self.assertEqual(resolve_tag_names("", anchor), ("", ""))


if __name__ == "__main__":
    unittest.main()
