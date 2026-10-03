"""Banner Set: the Christmas, Sale and third banners are made on ONE Airtable row, in one run."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import generate_banner_set_pipeline as banner_set  # noqa: E402
from content_automation.errors import AutomationError  # noqa: E402

ALL_CODES = ["CH", "PE", "FL", "TL", "WL", "DP", "KA", "KB", "BA", "BB"]


def _fake_pick(_clients, slot, _style, base_skus, base_names, _shopify):
    n = len(base_skus)
    return {"code": slot["code"], "sku": f"SKU{n}", "clean_name": f"Name{n}", "media_code": "m.png",
            "cutout": Path("c.png"), "notes": "W 25cm" if slot["code"] == "DP" else ""}


class BannerSetScrapeTests(unittest.TestCase):
    def test_slots_are_christmas_then_sale_pendants_then_the_bedroom_table_lamps(self):
        codes = [s["code"] for s in banner_set.SLOTS]
        self.assertEqual(codes, ALL_CODES)
        self.assertEqual(len(set(codes)), 10)  # no code is used twice, so one row can hold all ten cutouts
        self.assertEqual([s["category"] for s in banner_set.SLOTS[5:8]], ["pendant_lights"] * 3)
        self.assertEqual([s["category"] for s in banner_set.SLOTS[8:]], ["table_lamps"] * 2)

    def test_one_new_row_with_ten_cutouts_and_the_christmas_category(self):
        clients = MagicMock()
        clients.airtable.create_record.return_value = "recSET"
        with patch.object(banner_set, "load_scrape_context", return_value=(set(), set(), None)), \
                patch.object(banner_set, "pick_fixture", side_effect=_fake_pick):
            record_id = banner_set.run_phase_1_scrape_set(clients)
        self.assertEqual(record_id, "recSET")
        self.assertEqual(clients.airtable.create_record.call_count, 1)  # ONE row for all three banners
        fields = clients.airtable.create_record.call_args.args[0]
        self.assertEqual(fields["Category"], "Christmas Banner")
        self.assertEqual(fields["Status"], "In progress")
        self.assertEqual([line.split(":")[0] for line in fields["SKU"].splitlines()], ALL_CODES)
        self.assertEqual(fields["Item Details"], "DP: W 25cm")
        self.assertNotIn("ID", fields)
        self.assertNotIn("Foreign Key ID", fields)
        self.assertEqual(clients.airtable.upload_attachment.call_count, 10)
        names = [c.args[3] for c in clients.airtable.upload_attachment.call_args_list]
        self.assertEqual([n.split("_")[0] for n in names], ALL_CODES)
        required = clients.airtable.ensure_fields.call_args.args[0]
        for field in ("Banner with Text", "Sale Banner", "Kitchen Blended", "Sale Panel Color",
                      "Bedroom Interior", "Bedroom Blended", "Third Banner"):
            self.assertIn(field, required)

    def test_every_pick_is_added_to_the_dedup_sets_so_no_product_repeats(self):
        clients = MagicMock()
        clients.airtable.create_record.return_value = "recSET"
        seen: list[int] = []

        def pick(_c, slot, _s, base_skus, base_names, _shopify):
            seen.append(len(base_skus))
            return _fake_pick(_c, slot, _s, base_skus, base_names, _shopify)

        with patch.object(banner_set, "load_scrape_context", return_value=(set(), set(), None)), \
                patch.object(banner_set, "pick_fixture", side_effect=pick):
            banner_set.run_phase_1_scrape_set(clients)
        self.assertEqual(seen, list(range(10)))

    def test_nothing_is_written_when_a_product_is_missing(self):
        clients = MagicMock()
        results = [_fake_pick(None, s, None, set(), set(), None) for s in banner_set.SLOTS[:9]] + [None]
        with patch.object(banner_set, "load_scrape_context", return_value=(set(), set(), None)), \
                patch.object(banner_set, "pick_fixture", side_effect=results):
            with self.assertRaises(AutomationError):
                banner_set.run_phase_1_scrape_set(clients)
        clients.airtable.create_record.assert_not_called()


class BannerSetRunTests(unittest.TestCase):
    CHRISTMAS = ("run_phase_2_interior", "run_phase_3_claude", "run_phase_4_blend", "run_phase_5_copy",
                 "run_phase_6_overlay")
    SALE = ("run_phase_2_interiors", "run_phase_3_claude", "run_phase_4_blend", "run_phase_5_captions",
            "run_phase_6_composite")
    THIRD = ("run_phase_2_interior", "run_phase_3_claude", "run_phase_4_blend", "run_phase_5_composite")
    MODULES = (("xmas", banner_set.christmas, CHRISTMAS), ("sale", banner_set.sale, SALE),
               ("third", banner_set.third, THIRD))

    def _run(self, **kwargs):
        order: list[str] = []
        patches = []
        mocks: dict[str, MagicMock] = {}
        for tag, module, names in self.MODULES:
            for name in names:
                mock = MagicMock(side_effect=lambda *a, _t=f"{tag}.{name}", **k: order.append(_t))
                mocks[f"{tag}.{name}"] = mock
                patches.append(patch.object(module, name, mock))
        scrape = MagicMock(return_value="recSET")
        patches.append(patch.object(banner_set, "run_phase_1_scrape_set", scrape))
        clients = MagicMock()
        patches.append(patch.object(banner_set, "PipelineClients", return_value=clients))
        for p in patches:
            p.start()
        try:
            banner_set.run_pipeline(**kwargs)
        finally:
            for p in patches:
                p.stop()
        return order, scrape, clients, mocks

    def test_all_three_banners_run_in_order_on_the_one_scraped_row(self):
        order, scrape, _, _ = self._run()
        self.assertEqual(scrape.call_count, 1)
        self.assertEqual(order, [
            "xmas.run_phase_2_interior", "xmas.run_phase_3_claude", "xmas.run_phase_4_blend",
            "xmas.run_phase_5_copy", "xmas.run_phase_6_overlay",
            "sale.run_phase_2_interiors", "sale.run_phase_3_claude", "sale.run_phase_4_blend",
            "sale.run_phase_5_captions", "sale.run_phase_6_composite",
            "third.run_phase_2_interior", "third.run_phase_3_claude", "third.run_phase_4_blend",
            "third.run_phase_5_composite",
        ])

    def test_every_phase_gets_the_same_record_and_only_the_third_banner_is_final(self):
        _, _, _, mocks = self._run()
        for key, mock in mocks.items():
            self.assertEqual(mock.call_args.args[1], "recSET", key)
        self.assertIs(mocks["xmas.run_phase_6_overlay"].call_args.kwargs["final"], False)
        self.assertIs(mocks["sale.run_phase_6_composite"].call_args.kwargs["final"], False)
        # the third banner's composite is the one that writes Done (it takes no `final` flag)
        self.assertNotIn("final", mocks["third.run_phase_5_composite"].call_args.kwargs)

    def test_options_reach_the_right_banner(self):
        overrides = {"kitchen": {"moodboard": "mb-k", "prompt": "p"}}
        _, _, _, mocks = self._run(
            moodboard_id="mb-x", interior_prompt="xp", month=11, year=2026, overrides=overrides,
            panel_color="#0B3D2E", third_moodboard_id="mb-3", third_prompt="p3", third_title="T3", third_subtitle="S3",
        )
        self.assertEqual(mocks["xmas.run_phase_2_interior"].call_args.kwargs,
                         {"custom_moodboard": "mb-x", "custom_prompt": "xp"})
        self.assertEqual(mocks["sale.run_phase_2_interiors"].call_args.kwargs["overrides"], overrides)
        self.assertEqual(mocks["sale.run_phase_5_captions"].call_args.kwargs,
                         {"month": 11, "year": 2026, "panel_color": "#0B3D2E"})
        self.assertEqual(mocks["third.run_phase_2_interior"].call_args.kwargs,
                         {"custom_moodboard": "mb-3", "custom_prompt": "p3"})
        self.assertEqual(mocks["third.run_phase_5_composite"].call_args.kwargs, {"title": "T3", "subtitle": "S3"})

    def test_a_failure_marks_the_row_for_manual_and_stops(self):
        clients = MagicMock()
        with patch.object(banner_set, "run_phase_1_scrape_set", return_value="recSET"), \
                patch.object(banner_set, "PipelineClients", return_value=clients), \
                patch.object(banner_set.christmas, "run_phase_2_interior"), \
                patch.object(banner_set.christmas, "run_phase_3_claude", side_effect=AutomationError("boom")), \
                patch.object(banner_set.sale, "run_phase_2_interiors") as sale_krea, \
                patch.object(banner_set.third, "run_phase_2_interior") as third_krea:
            with self.assertRaises(AutomationError):
                banner_set.run_pipeline()
        sale_krea.assert_not_called()
        third_krea.assert_not_called()
        self.assertEqual(clients.airtable.update_record.call_args, call("recSET", {"Status": "For Manual"}))

    def test_a_third_banner_failure_leaves_the_row_for_manual_not_done(self):
        clients = MagicMock()
        patches = [patch.object(banner_set, "run_phase_1_scrape_set", return_value="recSET"),
                   patch.object(banner_set, "PipelineClients", return_value=clients)]
        for _tag, module, names in self.MODULES:
            for name in names:
                effect = AutomationError("blend failed") if (module is banner_set.third and name == "run_phase_4_blend") else None
                patches.append(patch.object(module, name, MagicMock(side_effect=effect)))
        for p in patches:
            p.start()
        try:
            with self.assertRaises(AutomationError):
                banner_set.run_pipeline()
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(clients.airtable.update_record.call_args, call("recSET", {"Status": "For Manual"}))


class StudioBannerRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPO_ROOT / "UI Control"))
        try:
            from routes import christmas_banner
        finally:
            sys.path.pop(0)
        cls.route = christmas_banner

    def test_the_studio_banner_run_spawns_the_set_pipeline_with_fifteen_phases(self):
        self.assertEqual(self.route.SCRIPT_NAME, "generate_banner_set_pipeline.py")
        self.assertEqual(self.route.TOTAL_PHASES, banner_set.TOTAL_PHASES)
        self.assertEqual(self.route.TOTAL_PHASES, 15)
        self.assertEqual(sorted(self.route.PHASE_LABELS), list(range(1, 16)))
        self.assertTrue((REPO_ROOT / self.route.SCRIPT_NAME).is_file())

    def test_printed_phase_numbers_map_to_the_studio_phase_in_each_stage(self):
        idx = self.route.phase_index
        self.assertEqual([idx(n, 0) for n in range(1, 7)], [1, 2, 3, 4, 5, 6])      # Christmas banner
        self.assertEqual([idx(n, 1) for n in range(2, 7)], [7, 8, 9, 10, 11])        # Sale banner
        self.assertEqual([idx(n, 2) for n in range(2, 6)], [12, 13, 14, 15])         # third banner

    def test_every_mapped_phase_has_a_label(self):
        for stage, numbers in ((0, range(1, 7)), (1, range(2, 7)), (2, range(2, 6))):
            for n in numbers:
                self.assertIn(self.route.phase_index(n, stage), self.route.PHASE_LABELS)


if __name__ == "__main__":
    unittest.main()
