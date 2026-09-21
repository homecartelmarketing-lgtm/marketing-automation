"""End-to-End CLI Runner for Day & Night Story Pipeline.

Workflow:
  1. Auto-Scrape (if needed): Scrapes new unique product(s) from Akeneo -> Airtable (Status: 'Standby')
  2. [Phase 1/4] Krea AI Interior Generation -> 'Interior Generated Photo'
  3. [Phase 2/4] Fal AI Claude Sonnet 5 Prompt Generation -> 'Blending Prompt'
  4. [Phase 3/4] Fal AI Nano Banana Pro Daytime Blending -> 'day_photo_raw.jpg'
  5. [Phase 4/4] Fal AI Nano Banana Pro Night Transformation -> 'night_photo.jpg'
  6. [Logo Overlay] Stamping 'Logo' attachment at top-right (X=781.7, Y=108) -> 'day_photo.jpg'
  7. [Upload & Complete] Uploads both images to 'STORY - Day & Night (2)' & sets Status to 'Complete'.

Usage::

    # Interactive table selection:
    python run_day_night_story.py

    # Target specific lighting category:
    python run_day_night_story.py --target chandeliers
    python run_day_night_story.py --target pendant_lights
    python run_day_night_story.py --target table_lamps
    python run_day_night_story.py --target floor_lamps
    python run_day_night_story.py --target cluster_chandeliers

    # Run specific number of rows sequentially:
    python run_day_night_story.py --target chandeliers --limit 3

    # Run on a specific Airtable Record ID:
    python run_day_night_story.py --record-id rechngJM56W0l7aKn

    # Dry run (test only, no API calls or Airtable writes):
    python run_day_night_story.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import requests

from content_automation.akeneo_client import AkeneoClient, split_item_name
from content_automation.airtable_client import AirtableClient
from content_automation.item_tagger import (
    TARGET_BLENDED_FIELD,
    tag_and_upload_blended_image,
)
from content_automation.config import (
    TABLES,
    DAY_NIGHT_STORY_TABLES,
    load_settings,
    resolve_day_night_story_table,
)
from content_automation.models import LocalImage
from content_automation.overlay import HOMECARTEL_STORY_LOGO_BOX, stamp_logo
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.categories import akeneo_category_code
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner
from run_content_automation import main as automation_main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Day & Night Story: End-to-end automated scraping & generation pipeline."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[
            "1", "2", "3", "4", "5",
            "chandeliers", "chandelier",
            "pendant_lights", "pendant_light", "pendant",
            "table_lamps", "table_lamp", "table",
            "floor_lamps", "floor_lamp", "floor",
            "cluster_chandeliers", "cluster_chandelier", "cluster",
            "tblkkcf88uvq3yu07", "tbl35JySlNuWh61tL",
            "tblanyyzcr7e6txtv", "tblhvm9saq18yqonb", "tblenvluwdfqwdj08",
            "tblr1hlsjgcs9qkcy", "tbldzp777tozevmvu",
            "tblgcvb4wfkopslql", "tblfcavauxzyghat9",
        ],
        default=None,
        help="Target lighting category / table (default: interactive prompt or chandelier)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Override destination Airtable Table ID",
    )
    parser.add_argument(
        "--limit",
        "--batch-size",
        "-n",
        dest="batch_size",
        type=int,
        default=1,
        help="Number of rows to process sequentially (default: 1)",
    )
    parser.add_argument(
        "--record-id",
        "-r",
        action="append",
        default=[],
        help="Specific Airtable Record ID to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a test run without paid API calls or Airtable writes",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip auto-scraping even if there are no pending rows in Airtable",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape products from Akeneo into Airtable without running generation",
    )
    parser.add_argument(
        "--stamp-only",
        action="store_true",
        help="Re-stamp HomeCartel logo onto Day photo of existing completed or specified rows without AI calls (Zero API cost)",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Override Krea Moodboard ID",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Override Krea room interior prompt",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if already completed",
    )
    parser.add_argument(
        "--style",
        default="modern",
        help="Akeneo style filter (default: modern)",
    )
    return parser.parse_args(argv)


def get_standby_record_count(settings, table_def=None, table_id: str | None = None) -> int:
    """Check how many records currently have Status == 'Standby'."""
    tid = table_id or getattr(table_def, "table_id", str(table_def))
    url = f"https://api.airtable.com/v0/{settings.airtable_base_id}/{tid}"
    headers = {"Authorization": f"Bearer {settings.airtable_token}"}
    params = {
        "filterByFormula": "{Status}='Standby'",
        "fields[]": "Status",
        "pageSize": 100,
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.ok:
            return len(r.json().get("records", []))
    except Exception as e:
        print(f"[WARN] Failed fetching standby count for {tid}: {e}")
    return 0


def scrape_new_products(settings, table_id: str, akeneo_cat: str, count: int, style: str) -> bool:
    """Scrape unique products from Akeneo into Airtable with Status 'Standby'."""
    print(f"\n[PHASE 0: SCRAPE] Checking & scraping {count} new product(s) from Akeneo (category={akeneo_cat}, style={style})...")
    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )
    runner = FurnitureItemScrapeRunner(
        akeneo,
        airtable,
        category_code=akeneo_cat,
        style_code=style,
        field_name="Furniture Item",
        item_name_field="Item Name",
        sku_field="SKU",
        status_field="Status",
        default_status="Standby",
        include_product_type_in_name=True,
        max_items=count,
    )
    return runner.run()


def run_stamp_only(
    settings,
    table_def,
    record_ids: list[str],
    batch_size: int = 1,
    dry_run: bool = False,
    category: str = "chandeliers",
) -> int:
    """Re-stamp HomeCartel logo onto Day photo of existing records without paid AI calls."""
    client = AirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_def,
    )

    records: list[dict[str, Any]] = []
    if record_ids:
        for rid in record_ids:
            try:
                rec = client.get_record(rid)
                if rec:
                    records.append(rec)
            except Exception as err:
                print(f"[ERROR] Could not fetch record {rid}: {err}")
    else:
        all_recs = client.list_records()
        for r in all_recs:
            if r.get("fields", {}).get("STORY - Day & Night (2)"):
                records.append(r)
            if len(records) >= batch_size:
                break

    if not records:
        print("[INFO] No records found with existing 'STORY - Day & Night (2)' attachments to stamp.")
        return 0

    print(f"\n[STAMP ONLY] Found {len(records)} record(s) to stamp with HomeCartel logo (zero AI cost)...")

    local_logo_candidates = [
        Path("assets/homecartel_logo.png"),
        Path("JSON Prompts/homecartel_logo.png"),
        Path("content_automation/assets/logo.png"),
        Path("static/img/logo.png"),
        Path("logo.png"),
    ]
    default_local_logo = next((p for p in local_logo_candidates if p.is_file()), None)

    out_dir = Path("tmp") / "stamp_only_day_night"
    out_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    for rec in records:
        rid = rec["id"]
        fields = rec.get("fields", {})
        item_name = fields.get("Item Name") or rid
        story_attachments = fields.get("STORY - Day & Night (2)", [])

        if not story_attachments:
            print(f"[WARN] Record {rid} ({item_name}) has no attachments in 'STORY - Day & Night (2)'. Skipping.")
            continue

        day_att = story_attachments[0]
        night_att = story_attachments[1] if len(story_attachments) > 1 else None

        print(f"\n--- Processing Record {rid}: {item_name} ---")
        day_url = day_att.get("url")
        if not day_url:
            print(f"[WARN] No URL for Day attachment on {rid}. Skipping.")
            continue

        day_raw_path = out_dir / f"day_raw_{rid}.jpg"
        print("  [+] Downloading current Day photo from Airtable...")
        resp = requests.get(day_url, timeout=30)
        resp.raise_for_status()
        day_raw_path.write_bytes(resp.content)

        logo_path = None
        logo_attachments = fields.get("Overlay Logo") or fields.get("Logo")
        if logo_attachments and isinstance(logo_attachments, list) and len(logo_attachments) > 0:
            logo_url = logo_attachments[0].get("url")
            if logo_url:
                try:
                    logo_temp = out_dir / f"logo_{rid}.png"
                    print("  [+] Downloading logo from Airtable attachment...")
                    l_resp = requests.get(logo_url, timeout=30)
                    l_resp.raise_for_status()
                    logo_temp.write_bytes(l_resp.content)
                    logo_path = logo_temp
                except Exception as l_err:
                    print(f"  [WARN] Failed downloading logo from Airtable: {l_err}. Using local fallback.")

        if not logo_path and default_local_logo:
            print(f"  [+] Using local logo asset: {default_local_logo}")
            logo_path = default_local_logo

        if not logo_path:
            print(f"  [ERROR] No logo found (neither in Airtable nor local). Skipping record {rid}.")
            continue

        stamped_day_path = out_dir / f"day_photo_{rid}.jpg"
        print("  [+] Stamping HomeCartel logo onto Day photo at top-right (X=781.7, Y=108.0)...")
        stamp_logo(
            day_raw_path,
            logo_path,
            destination=stamped_day_path,
            box=HOMECARTEL_STORY_LOGO_BOX,
        )
        print(f"  [OK] Successfully stamped Day photo -> {stamped_day_path}")

        night_path = None
        if night_att and night_att.get("url"):
            night_path = out_dir / f"night_photo_{rid}.jpg"
            n_resp = requests.get(night_att["url"], timeout=30)
            n_resp.raise_for_status()
            night_path.write_bytes(n_resp.content)

        if dry_run:
            print(f"  [DRY RUN] Stamped Day photo ready at {stamped_day_path}. Skipping Airtable upload.")
            success_count += 1
            continue

        print("  [+] Uploading stamped Day photo (+ Night photo) to 'STORY - Day & Night (2)'...")
        client.clear_attachment_field(rid, "STORY - Day & Night (2)")
        client.upload_attachment(
            rid,
            "STORY - Day & Night (2)",
            LocalImage(stamped_day_path, "day_photo.jpg", "image/jpeg"),
        )
        if night_path and night_path.is_file():
            client.upload_attachment(
                rid,
                "STORY - Day & Night (2)",
                LocalImage(night_path, "night_photo.jpg", "image/jpeg"),
            )

        # Auto-tag furniture item name onto Day & Night Story photos using zero-cost local YOLO-World
        try:
            raw_item_name = str(fields.get("Item Name") or fields.get("SKU") or rid).strip()
            item_title, product_type = split_item_name(
                raw_item_name, fallback_product_type=str(fields.get("Product Type") or "")
            )
            photo_sources = [stamped_day_path]
            if night_path and night_path.is_file():
                photo_sources.append(night_path)
            if TARGET_BLENDED_FIELD in client.schema():
                tag_and_upload_blended_image(
                    airtable=client,
                    record_id=rid,
                    blended_source=photo_sources,
                    item_name=item_title,
                    product_type=product_type,
                    category=str(category or "chandeliers"),
                    target_field=TARGET_BLENDED_FIELD,
                    output_filename_prefix="day_night_story_tagged",
                )
        except Exception as tag_err:
            print(f"  [WARN] Failed auto-tagging item name onto Day & Night Story photos: {tag_err}")

        client.update_records([(rid, {"Status": "Complete"})])
        print(f"  [OK] Record {rid} updated to Status 'Complete' with stamped Day photo!")
        success_count += 1

    print(f"\n[SUMMARY] Stamped {success_count} / {len(records)} record(s) successfully.")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = load_settings()

    selected_preset = resolve_day_night_story_table(
        target_arg=args.target,
        prompt_if_interactive=not args.dry_run and not args.target and not args.table_id and not args.record_id,
    )
    table_code = selected_preset["table_code"]
    table_def = TABLES.get(table_code, TABLES["chandelier_day_night_story"])
    table_id = args.table_id or os.getenv(selected_preset.get("env_table_key", ""), "").strip() or table_def.table_id
    cat_code = selected_preset.get("category_code", "chandeliers")
    akeneo_cat = akeneo_category_code(cat_code)

    print("\n" + "=" * 64)
    print(" HomeCartel - Day & Night Story End-to-End Pipeline")
    print(f" Target Preset: {selected_preset['label']}")
    print(f" Target Table ID: {table_id}")
    print(f" Category: {cat_code} (Akeneo: {akeneo_cat})")
    print(f" Mode: {'DRY RUN (Simulation)' if args.dry_run else 'LIVE EXECUTION'}")
    print(f" Batch Size: {args.batch_size} row(s)")
    if args.record_id:
        print(f" Target Record(s): {', '.join(args.record_id)}")
    print("=" * 64)

    if args.moodboard_id:
        os.environ["KREA_MOODBOARD_ID_CHANDELIERS"] = args.moodboard_id
        os.environ["KREA_MOODBOARD_ID_PENDANT_LIGHTS"] = args.moodboard_id
        os.environ["KREA_MOODBOARD_ID_FLOOR_LAMPS"] = args.moodboard_id
        os.environ["KREA_MOODBOARD_ID_TABLE_LAMPS"] = args.moodboard_id
        os.environ["KREA_MOODBOARD_ID_CLUSTER_CHANDELIER"] = args.moodboard_id

    if args.prompt:
        os.environ["DAY_NIGHT_STORY_PROMPT_CHANDELIER"] = args.prompt
        os.environ["DAY_NIGHT_PROMPT_CHANDELIER"] = args.prompt
        os.environ["DAY_NIGHT_STORY_PROMPT_PENDANT_LIGHTS"] = args.prompt
        os.environ["DAY_NIGHT_PROMPT_PENDANT_LIGHTS"] = args.prompt
        os.environ["DAY_NIGHT_STORY_PROMPT_FLOOR_LAMPS"] = args.prompt
        os.environ["DAY_NIGHT_PROMPT_FLOOR_LAMPS"] = args.prompt
        os.environ["DAY_NIGHT_STORY_PROMPT_TABLE_LAMPS"] = args.prompt
        os.environ["DAY_NIGHT_PROMPT_TABLE_LAMPS"] = args.prompt
        os.environ["DAY_NIGHT_STORY_PROMPT_CLUSTER_CHANDELIER"] = args.prompt
        os.environ["DAY_NIGHT_PROMPT_CLUSTER_CHANDELIER"] = args.prompt

    if args.stamp_only:
        return run_stamp_only(
            settings,
            table_def,
            record_ids=args.record_id,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            category=cat_code,
        )

    # 1. Check if we need to scrape new products from Akeneo
    if not args.dry_run and not args.record_id and not args.no_scrape:
        standby_count = get_standby_record_count(settings, table_def, table_id=table_id)
        if standby_count < args.batch_size:
            needed = args.batch_size - standby_count
            print(f"[INFO] Found {standby_count} 'Standby' row(s) in {table_id}. Auto-scraping {needed} new item(s) from Akeneo...")
            success = scrape_new_products(settings, table_id, akeneo_cat, needed, args.style)
            if not success:
                print("[WARN] Akeneo scrape returned no new items or encountered an issue.")
        else:
            print(f"[INFO] Found {standby_count} existing 'Standby' row(s) ready for generation in {table_id}.")

    if args.scrape_only:
        print("\n[OK] Scrape complete. Exiting (--scrape-only).")
        return 0

    # 2. Run the Generation Pipeline via content_automation generic runner
    forward_args = [
        "--phase", "stories",
        "--assignment", table_code,
        "--batch-size", str(args.batch_size),
    ]
    if not args.dry_run:
        forward_args.append("--execute")
    if args.force:
        forward_args.append("--force")
    for rid in args.record_id:
        forward_args.extend(["--record-id", rid])

    return automation_main(forward_args)


if __name__ == "__main__":
    sys.exit(main())
