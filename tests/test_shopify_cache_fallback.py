"""Unit tests for ShopifyClient bundled cache fallback and Cloudflare resilience."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_automation.shopify_client import (
    BUNDLED_CACHE_FILE,
    PRIMARY_CACHE_FILE,
    ShopifyCatalogIndex,
    ShopifyClient,
    normalize_shopify_text,
)


class ShopifyCacheFallbackTests(unittest.TestCase):
    def test_bundled_cache_file_exists_and_indexes(self):
        self.assertTrue(
            BUNDLED_CACHE_FILE.is_file(),
            f"Bundled cache file {BUNDLED_CACHE_FILE} must exist in repository assets.",
        )
        client = ShopifyClient()
        idx = client.load_published_identities()
        self.assertIsInstance(idx, ShopifyCatalogIndex)
        self.assertGreater(len(idx.skus), 1000, "Bundled cache should contain thousands of published SKUs.")
        self.assertGreater(len(idx.titles), 1000, "Bundled cache should contain thousands of published titles.")

    def test_load_published_identities_falls_back_to_bundled_when_primary_missing(self):
        client = ShopifyClient()
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_primary = Path(tmpdir) / "nonexistent.json"
            with patch("content_automation.shopify_client.PRIMARY_CACHE_FILE", fake_primary):
                idx = client.load_published_identities(force_refresh=False)
                self.assertIsNotNone(idx)
                self.assertGreater(len(idx.skus), 1000)

    def test_cloudflare_challenge_sets_flag_and_aborts_crawl(self):
        client = ShopifyClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Cf-Mitigated": "challenge"}
        mock_resp.text = "<html><title>Just a moment...</title></html>"

        client.session = MagicMock()
        client.session.get.return_value = mock_resp

        page_num, items, success = client._fetch_storefront_page(page_num=21)
        self.assertFalse(success)
        self.assertEqual(items, [])
        self.assertTrue(client._cf_challenge_encountered)

    def test_index_contains_matching(self):
        idx = ShopifyCatalogIndex(
            skus={normalize_shopify_text("HC-PEND-RYLWNA"), normalize_shopify_text("10238P")},
            titles={normalize_shopify_text("Rylwna Pendant Light"), normalize_shopify_text("Modern Chandelier")},
            handles={"rylwna-pendant-light"},
        )
        self.assertTrue(idx.contains("HC-PEND-RYLWNA"))
        self.assertTrue(idx.contains("hc pend rylwna"))
        self.assertTrue(idx.contains("10238P-3L"))
        self.assertTrue(idx.contains("10238P"))
        self.assertTrue(idx.contains("", "Rylwna Pendant Light"))
        self.assertFalse(idx.contains("UNKNOWN-SKU-999", "Unknown Title"))


if __name__ == "__main__":
    unittest.main()
