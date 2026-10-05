"""Print or export the Akeneo PIM category tree via the REST API.

Standalone: needs only `requests` and `python-dotenv`, plus these .env keys:
AKENEO_HOST, AKENEO_CLIENT_ID, AKENEO_SECRET, AKENEO_USERNAME, AKENEO_PASSWORD.

Usage:
    python scripts/akeneo_category_tree.py
    python scripts/akeneo_category_tree.py --root master --locale en_US
    python scripts/akeneo_category_tree.py --json tree.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PAGE_SIZE = 100


def authenticate(host: str, client_id: str, secret: str, username: str, password: str) -> str:
    response = requests.post(
        f"{host}/api/oauth/v1/token",
        auth=(client_id, secret),
        json={"grant_type": "password", "username": username, "password": password},
        timeout=30,
    )
    if not response.ok:
        raise SystemExit(f"Akeneo authentication failed: {response.status_code} {response.text[:300]}")
    token = response.json().get("access_token")
    if not token:
        raise SystemExit("Akeneo authentication returned no access_token")
    return token


def fetch_all_categories(host: str, token: str) -> list[dict[str, Any]]:
    """Return every category as a flat list, following pagination."""
    url = f"{host}/api/rest/v1/categories"
    params: dict[str, Any] = {"limit": PAGE_SIZE, "with_position": "true"}
    headers = {"Authorization": f"Bearer {token}"}
    items: list[dict[str, Any]] = []
    while url:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        if not response.ok:
            raise SystemExit(f"Akeneo categories request failed: {response.status_code} {response.text[:300]}")
        payload = response.json()
        items.extend(payload.get("_embedded", {}).get("items", []))
        url = (payload.get("_links", {}).get("next") or {}).get("href", "")
        params = {}  # the next href already carries its query string
    return items


def build_tree(items: list[dict[str, Any]], locale: str) -> list[dict[str, Any]]:
    """Nest the flat category list by `parent`; returns the root nodes."""
    nodes = {
        item["code"]: {
            "code": item["code"],
            "label": (item.get("labels") or {}).get(locale) or item["code"],
            "position": item.get("position"),
            "children": [],
        }
        for item in items
    }
    roots: list[dict[str, Any]] = []
    for item in items:
        node = nodes[item["code"]]
        parent = item.get("parent")
        if parent and parent in nodes:
            nodes[parent]["children"].append(node)
        else:
            roots.append(node)

    def sort_key(node: dict[str, Any]) -> tuple[int, str]:
        position = node.get("position")
        return (position if isinstance(position, int) else 10**9, node["code"])

    def sort_recursive(level: list[dict[str, Any]]) -> None:
        level.sort(key=sort_key)
        for child in level:
            sort_recursive(child["children"])

    sort_recursive(roots)
    return roots


def find_node(roots: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    for node in roots:
        if node["code"] == code:
            return node
        found = find_node(node["children"], code)
        if found:
            return found
    return None


def print_tree(nodes: list[dict[str, Any]], depth: int = 0) -> None:
    for node in nodes:
        label = node["label"]
        suffix = "" if label == node["code"] else f"  ({label})"
        print(f"{'  ' * depth}- {node['code']}{suffix}")
        print_tree(node["children"], depth + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", help="category code to print as the subtree root")
    parser.add_argument("--locale", default="en_US", help="label locale (default: en_US)")
    parser.add_argument("--json", metavar="FILE", help="write the tree to this JSON file instead of printing")
    parser.add_argument("--env", default=str(Path(__file__).resolve().parents[1] / ".env"), help="path to .env")
    args = parser.parse_args()

    load_dotenv(args.env, override=False)
    keys = ["AKENEO_HOST", "AKENEO_CLIENT_ID", "AKENEO_SECRET", "AKENEO_USERNAME", "AKENEO_PASSWORD"]
    missing = [key for key in keys if not os.getenv(key)]
    if missing:
        raise SystemExit(f"Missing in .env: {', '.join(missing)}")

    host = os.environ["AKENEO_HOST"].rstrip("/")
    token = authenticate(
        host,
        os.environ["AKENEO_CLIENT_ID"],
        os.environ["AKENEO_SECRET"],
        os.environ["AKENEO_USERNAME"],
        os.environ["AKENEO_PASSWORD"],
    )
    items = fetch_all_categories(host, token)
    tree = build_tree(items, args.locale)

    if args.root:
        node = find_node(tree, args.root)
        if not node:
            raise SystemExit(f"Category '{args.root}' not found")
        tree = [node]

    if args.json:
        Path(args.json).write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {len(items)} categories ({len(tree)} root(s) shown) to {args.json}")
    else:
        print_tree(tree)
        print(f"\n{len(items)} categories total", file=sys.stderr)


if __name__ == "__main__":
    main()
