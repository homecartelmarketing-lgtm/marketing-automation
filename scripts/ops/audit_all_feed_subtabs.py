"""Audit all Feed subtabs live status counts via the Studio API (port 5200).

Usage::

    python scripts/ops/audit_all_feed_subtabs.py
"""

from __future__ import annotations

import requests

SUBTABS = [
    ("Subtab 0: Tips & Educational", "/api/tips-edu-feed/counts?refresh=true"),
    ("Subtab 1: Collection Category", "/api/collection-feed/counts?refresh=true"),
    ("Subtab 2: Moodboard #1", "/api/moodboard-1-feed/counts?refresh=true"),
    ("Subtab 3: Moodboard #2", "/api/moodboard-2-feed/counts?refresh=true"),
    ("Subtab 4: 1 Product 3 Styles", "/api/one-product-3-styles/counts?refresh=true"),
    ("Subtab 5: Day & Night", "/api/day-night-feed/counts?refresh=true"),
    ("Subtab 6: Product Showcase", "/api/product-showcase-feed/counts?refresh=true"),
]


def audit_feeds(host: str = "http://127.0.0.1:5200") -> None:
    print(f"Connecting to Studio at {host}...")
    for name, url in SUBTABS:
        full_url = f"{host}{url}"
        try:
            r = requests.get(full_url, timeout=10)
            res = r.json()
            print(f"\n========================================================")
            print(f" {name} -> HTTP {r.status_code}")
            print(f"========================================================")
            for fix_key, data in res.get("counts", {}).items():
                tbl = data.get("table_id")
                sc = data.get("status_counts", {})
                total_rows = sum(sc.values())
                print(f"  * [{fix_key}]: {data.get('name')} (Table: {tbl})")
                print(f"      Rows: {total_rows} | P:{sc.get('P',0)} S:{sc.get('S',0)} C:{sc.get('C',0)} D:{sc.get('D',0)} FM:{sc.get('FM',0)}")
                if data.get("moodboard_id"):
                    print(f"      Moodboard: {data.get('moodboard_id')}")
                if data.get("prompt"):
                    print(f"      Prompt: {data.get('prompt')[:60]}...")
        except Exception as e:
            print(f"  [ERROR] {name} ({full_url}): {e}")


if __name__ == "__main__":
    audit_feeds()
