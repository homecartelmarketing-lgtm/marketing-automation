"""Unified Before & After Reel Automation Script.

Runs the complete end-to-end workflow for Before & After Reels:
1. Scrapes 1 new product from Akeneo (sorted Newest to Oldest) into Airtable ('Furniture Item', 'Item Name', 'SKU', Status: 'Standby')
2. Generates Krea AI Room Interior ('Interior Generated Photo', Status: 'Processing Interior Generated Photo')
3. Generates Fal AI Claude Sonnet 5 Blending Prompt ('Blending Prompt', Status: 'Processing Blending Prompt')
4. Generates Fal AI Nano Banana Pro Day Blended Photo ('Blended Image', Status: 'Processing Day Image')
5. Generates Fal AI Multiple Angles ('Multiple Angle Blended Image')
6. Compiles Slideshow Video Reel with Centered Typography & Exports to Google Drive ('Slide Show Before and After Reel', Status: 'Complete')

Supported Destination Tables:
- Floor Lamp Before & After Reel: tbl2VoWOt7sSut4E2 (Category: floor_lamps)
- Pendant Light Before & After Reel: tbleUP86Kw36G8Hdw (Category: pendant_lights)
- Chandelier Before & After Reel: tbloMhCOngGDWFS2y (Category: chandeliers)

Usage::

    python run_before_after_reel.py
    python run_before_after_reel.py --target floor_lamps
    python run_before_after_reel.py --target pendant_lights
"""

from __future__ import annotations

import argparse
import os
import sys

from content_automation.akeneo_client import AkeneoClient
from content_automation.config import REEL_TABLES, load_settings, resolve_reel_table
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.krea_client import KreaClient
from content_automation.scraping import (
    FurnitureItemScrapeRunner,
    ScrapeAirtableClient,
    load_scrape_settings,
)
from content_automation.scraping.categories import moodboard_id_for_category
from generate_before_after_reel_pipeline import (
    generate_claude_blending_prompts,
    generate_krea_interiors_pipeline,
    generate_multiple_angles_pipeline,
    generate_nano_banana_pro_blends,
    generate_qwen_blending_prompts,
    generate_qwen_image_blends,
    generate_slideshow_reels_pipeline,
    regenerate_multiple_angles_with_gpt_image_pipeline,
)

FIELD_NAME = "Furniture Item"
ITEM_NAME_FIELD = "Item Name"
SKU_FIELD = "SKU"
STATUS_FIELD = "Status"
SELECT_STATUS = "Standby"
DEFAULT_STYLE = os.getenv("AKENEO_STYLE", "").strip() or "modern"


def parse_args(argv=None):
    preset_keys = list(REEL_TABLES.keys())
    parser = argparse.ArgumentParser(
        description="Unified Before & After Reel Workflow (Scrape + Krea AI + Fal Claude Sonnet 5 + Fal Nano Banana Pro Blended + Fal Multiple Angles + Video)"
    )
    parser.add_argument(
        "--target",
        "-t",
        default=None,
        help=f"Target table preset ({', '.join(preset_keys)}) or table ID",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=1,
        metavar="N",
        help="Number of products to process per run (default: 1)",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=DEFAULT_STYLE,
        help=f"Akeneo style filter (default: {DEFAULT_STYLE})",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    parser.add_argument(
        "--moodboard-id",
        default=None,
        help="Krea Moodboard ID override",
    )
    parser.add_argument(
        "--no-cross-dedup",
        action="store_true",
        help="Disable base-wide cross-table deduplication (check current table only)",
    )
    parser.add_argument(
        "--no-price-sort",
        action="store_true",
        help="Disable highest-to-lowest price ranking (use pure chronological date order)",
    )
    parser.add_argument(
        "--price-pool-size",
        type=int,
        default=50,
        help="Number of newest products to consider in price ranking pool (default: 50)",
    )
    return parser.parse_args(argv)


def run_pipeline_for_table(
    krea: KreaClient,
    fal: FalClient,
    airtable: ScrapeAirtableClient,
    moodboard_id: str,
    interior_prompt: str,
    placement_rule: str = "",
    max_items: int | None = None,
) -> bool:
    """Run all 5 AI pipeline phases (Interior -> Claude Sonnet 5 Prompt -> Nano Banana Pro Blend -> Multiple Angles -> Slideshow Video) on Airtable records."""
    success = True
    print("\n[AI PIPELINE PHASE 1/5] Krea AI Room Interior Generation (Before Image)...")
    if not generate_krea_interiors_pipeline(krea, airtable, moodboard_id=moodboard_id, prompt=interior_prompt, limit_records=max_items):
        success = False

    print("\n[AI PIPELINE PHASE 2/5] Fal AI Claude Sonnet 5 Blending Prompt Generation...")
    if not generate_claude_blending_prompts(fal, airtable, placement_rule=placement_rule, limit_records=max_items):
        success = False

    print("\n[AI PIPELINE PHASE 3/5] Fal AI Nano Banana Pro Image Blending (After Image)...")
    if not generate_nano_banana_pro_blends(fal, airtable, limit_records=max_items):
        success = False

    print("\n[AI PIPELINE PHASE 4/5] Fal AI Multiple Angle Generation (4 Angles)...")
    if not generate_multiple_angles_pipeline(fal, airtable, limit_records=max_items):
        success = False

    print("\n[AI PIPELINE PHASE 5/5] Slideshow Reel Video Generation & Google Drive Export...")
    if not generate_slideshow_reels_pipeline(fal, airtable, limit_records=max_items):
        success = False

    return success


def count_incomplete_records(airtable: ScrapeAirtableClient) -> int:
    """Count records in Airtable that have not reached 'Complete' status."""
    records = airtable.list_records(["Status"])
    incomplete = 0
    for record in records:
        fields = record.get("fields", {})
        status = str(fields.get("Status") or "").strip().casefold()
        if status not in ("complete", "done"):
            incomplete += 1
    return incomplete


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    base = load_settings()
    base.require({"airtable", "krea", "fal"})

    reel_config = resolve_reel_table(args.target)
    table_id = (
        args.table_id
        or os.getenv(reel_config.get("env_table_key", ""), "").strip()
        or reel_config.get("default_table_id", "")
    )
    category_code = reel_config.get("table_code", "floor_lamps_day_night_reel")
    akeneo_cat = (
        reel_config.get("akeneo_category")
        or reel_config.get("category_code")
        or "floor_lamps"
    )
    moodboard_id = (
        (args.moodboard_id or "").strip()
        or os.getenv(reel_config.get("moodboard_env_key", ""), "").strip()
        or reel_config.get("default_moodboard_id", "")
        or moodboard_id_for_category(akeneo_cat)
    )
    interior_prompt = reel_config.get(
        "interior_prompt",
        "Generate me a modern bedroom that have beside a floor lamp",
    )
    placement_rule = reel_config.get("placement_rule", "")

    settings = load_scrape_settings(
        category_code=akeneo_cat,
        style_code=args.style,
        table_id_override=table_id,
        settings=base,
    )

    sort_mode = (
        f"Highest to Lowest Price (Top {args.price_pool_size} Newest Pool)"
        if not args.no_price_sort
        else "Newest to Oldest"
    )
    print("=" * 64)
    print(f"UNIFIED BEFORE & AFTER REEL AUTOMATION ({reel_config['label']})")
    print(f"Destination Table: {settings.airtable_base_id} / {table_id}")
    print(f"Akeneo Source Category: {akeneo_cat} ({sort_mode})")
    print(f"Krea Moodboard ID: {moodboard_id}")
    print(f"Interior Prompt: \"{interior_prompt}\"")
    print("=" * 64)

    akeneo = AkeneoClient(
        settings.akeneo_host,
        settings.akeneo_client_id,
        settings.akeneo_secret,
        settings.akeneo_username,
        settings.akeneo_password,
        channel_name=settings.channel_name,
    )
    airtable = ScrapeAirtableClient(
        settings.airtable_token,
        settings.airtable_base_id,
        table_id,
    )
    krea = KreaClient(base.krea_token, base.krea_base_url)
    fal = FalClient(base.fal_key)

    overall_success = True

    # Check existing Airtable rows for any incomplete fields
    incomplete_count = count_incomplete_records(airtable)
    if incomplete_count > 0:
        print(f"\n[BACKLOG FOUND] Found {incomplete_count} incomplete record(s) in Airtable. Completing existing rows FIRST...")
        if not run_pipeline_for_table(
            krea,
            fal,
            airtable,
            moodboard_id,
            interior_prompt,
            placement_rule=placement_rule,
            max_items=args.max_items,
        ):
            overall_success = False
        print(f"\n[INFO] Finished processing existing incomplete row(s). Skipping new Akeneo scrape to save API credits.")
    else:
        print("\n[AIRTABLE CLEAN] All existing rows in Airtable are 100% Complete! Scraping 1 new item from Akeneo...")
        runner = FurnitureItemScrapeRunner(
            akeneo,
            airtable,
            category_code=akeneo_cat,
            style_code=args.style,
            field_name=FIELD_NAME,
            item_name_field=ITEM_NAME_FIELD,
            sku_field=SKU_FIELD,
            status_field=STATUS_FIELD,
            default_status=SELECT_STATUS,
            include_product_type_in_name=True,
            max_items=args.max_items,
            cross_table_dedup=not args.no_cross_dedup,
            sort_by_price=not args.no_price_sort,
            price_pool_size=args.price_pool_size,
        )
        if runner.run():
            print(f"\n[NEW ITEM AI PIPELINE] Processing newly scraped item(s) through full AI pipeline...")
            if not run_pipeline_for_table(
                krea,
                fal,
                airtable,
                moodboard_id,
                interior_prompt,
                placement_rule=placement_rule,
                max_items=args.max_items,
            ):
                overall_success = False
        else:
            print("[INFO] Scraper found no new products to add.")

    print("\n" + "=" * 64)
    if overall_success:
        print(f"[OK] Complete Before & After Reel automation finished for {reel_config['label']}!")
    else:
        print("[WARN] Workflow completed with warnings or errors.")
    print("=" * 64)

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
