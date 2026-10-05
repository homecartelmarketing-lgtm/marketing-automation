"""CTA catalog consistency: routes, frontend, docs, and FK map must agree.

The fixture catalog (``content_automation/fixture_catalog.py``) is the single
source of truth for CTA Story wiring. This test fails the build on any drift
between the layers — the class of bug that froze CTA table-lamp on the wrong
moodboard (route ``351d992d`` vs docs/generator ``257569e1`` vs
``.env.example`` ``fb2487fb``).

Pure assertions + file reads, no network calls.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ROUTES_DIR = ROOT / "UI Control"
if str(ROUTES_DIR) not in sys.path:
    sys.path.insert(0, str(ROUTES_DIR))

from content_automation.fixture_catalog import (  # noqa: E402
    CTA_FIXTURES,
    active_fixtures,
    fixture_dict,
    resolve_moodboard_id,
    resolve_table_id,
)

WINNING_TABLE_LAMP_MOODBOARD = "257569e1-7be8-4412-a90f-acbc347e4646"


class CtaCatalogSelfTests(unittest.TestCase):
    def test_five_active_plus_one_parked(self):
        active = active_fixtures("cta-story")
        self.assertEqual(len(active), 5)
        parked = [e for e in CTA_FIXTURES if e.status == "parked"]
        self.assertEqual([e.fixture_id for e in parked], ["wall-light"])

    def test_unique_table_ids(self):
        ids = [e.table_id for e in CTA_FIXTURES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_table_lamp_winner(self):
        entry = next(e for e in CTA_FIXTURES if e.fixture_id == "table-lamp")
        self.assertEqual(entry.default_moodboard_id, WINNING_TABLE_LAMP_MOODBOARD)

    def test_resolvers_prefer_canonical_keys(self):
        import os
        from unittest.mock import patch

        entry = next(e for e in CTA_FIXTURES if e.fixture_id == "floor-lamp")
        env = {entry.moodboard_env_key: "", **{k: "" for k in entry.moodboard_alias_keys}}
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(
                resolve_moodboard_id(entry), entry.default_moodboard_id
            )
        with patch.dict(
            os.environ,
            {**env, "KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA": "alias-uuid"},
            clear=False,
        ):
            self.assertEqual(resolve_moodboard_id(entry), "alias-uuid")
        with patch.dict(
            os.environ,
            {
                **env,
                "KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA": "alias-uuid",
                entry.moodboard_env_key: "canonical-uuid",
            },
            clear=False,
        ):
            self.assertEqual(resolve_moodboard_id(entry), "canonical-uuid")


class CtaLayerAgreementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route = importlib.import_module("routes.cta_story")
        from content_automation.foreign_key import TABLE_PREFIX_MAP

        cls.fk_map = TABLE_PREFIX_MAP
        cls.fixtures_ts = (ROOT / "UI Control" / "src" / "app" / "constants" / "fixtures.ts").read_text(
            encoding="utf-8"
        )
        cls.doc = (ROOT / "docs" / "stories" / "CTA_STORY.md").read_text(encoding="utf-8")

    def test_route_fixtures_match_catalog(self):
        live = self.route.get_cta_fixtures()
        self.assertEqual(set(live), {e.fixture_id for e in active_fixtures("cta-story")})
        for entry in active_fixtures("cta-story"):
            with self.subTest(fixture=entry.fixture_id):
                expected = fixture_dict(entry)
                self.assertEqual(live[entry.fixture_id]["table_id"], expected["table_id"])
                self.assertEqual(live[entry.fixture_id]["moodboard_id"], expected["moodboard_id"])
                self.assertEqual(live[entry.fixture_id]["prompt"], expected["prompt"])

    def test_route_configs_derive_from_catalog(self):
        for entry in active_fixtures("cta-story"):
            with self.subTest(fixture=entry.fixture_id):
                self.assertEqual(
                    self.route.CTA_STORY_MOODBOARD_CONFIG[entry.fixture_id]["env_key"],
                    entry.moodboard_env_key,
                )
                self.assertEqual(
                    self.route.CTA_STORY_MOODBOARD_CONFIG[entry.fixture_id]["default"],
                    entry.default_moodboard_id,
                )
                self.assertEqual(
                    self.route.CTA_STORY_PROMPT_CONFIG[entry.fixture_id]["env_key"],
                    entry.prompt_env_key,
                )

    def test_frontend_fixtures_match_catalog(self):
        for entry in active_fixtures("cta-story"):
            with self.subTest(fixture=entry.fixture_id):
                self.assertIn(entry.table_id, self.fixtures_ts)
                self.assertIn(entry.default_moodboard_id, self.fixtures_ts)

    def test_docs_match_catalog(self):
        for entry in active_fixtures("cta-story"):
            with self.subTest(fixture=entry.fixture_id):
                self.assertIn(entry.table_id, self.doc)
                self.assertIn(entry.default_moodboard_id, self.doc)
                self.assertIn(entry.table_env_keys[0], self.doc)

    def test_fk_map_match_catalog(self):
        for entry in active_fixtures("cta-story"):
            with self.subTest(fixture=entry.fixture_id):
                self.assertEqual(self.fk_map.get(entry.table_id), entry.fk_prefix)


if __name__ == "__main__":
    unittest.main()
