from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..akeneo_client import split_item_name
from ..config import DAY_NIGHT_STORY_TABLES
from ..item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
from ..models import CallEstimate, LocalImage
from ..overlay import HOMECARTEL_STORY_LOGO_BOX
from .base import BaseWorkflow, NIGHT_PROMPT


class DayNightStoryWorkflow(BaseWorkflow):
    requirements = ()
    estimate = CallEstimate(krea=1, qwen=0, kie=0, fal=2)
    aspect_ratio = "9:16"
    final_filenames = ("day_photo.jpg", "night_photo.jpg")
    final_aspect_ratios = ("9:16", "9:16")

    def execute(self):
        anchor = self.ctx.anchor
        item_name = anchor.item_name or anchor.fields.get("Item Name") or "Chandelier"
        print(f"\n{'='*64}")
        print(f" [START] Day & Night Story for: {item_name}")
        print(f" Record ID: {anchor.record_id}")
        print(f"{'='*64}")

        print("\n [PHASE 1/4] Generating 9:16 Daytime Interior (Krea AI)...")
        product = self.product_image()
        interior_prompt = self._get_interior_prompt()
        source = self.krea_image(
            "day_night_story_source.jpg",
            interior_prompt,
            aspect_ratio="9:16",
            moodboard_id=self.ctx.settings.moodboard_id(self.ctx.definition.table_code),
        )
        print(f"  [OK] Phase 1 Complete: Interior photo ready (prompt: \"{interior_prompt[:40]}...\")")
        self.attach_sources([source])

        print("\n [PHASE 2/4] Analyzing Scene & Writing Prompt (Fal AI Claude Sonnet 5)...")
        table_code = (self.ctx.definition.table_code or "").lower()
        placement_rule = ""
        for preset in DAY_NIGHT_STORY_TABLES.values():
            if preset.get("table_code") == table_code:
                placement_rule = preset.get("placement_rule", "")
                break
        blend_prompt = self.claude_blend_prompt(source, product, placement_rule=placement_rule)
        print(f"  [OK] Phase 2 Complete: Prompt generated ({len(blend_prompt)} chars)")
        self.update_field("Blending Prompt", blend_prompt)
        print("  [OK] Blending Prompt saved to Airtable field 'Blending Prompt'")

        print("\n [PHASE 3/4] Blending Day Photo at 9:16 (Fal AI Nano Banana Pro)...")
        day_raw = self.fal_image(
            "day_photo_raw.jpg",
            blend_prompt,
            [source, product],
            aspect_ratio="9:16",
        )
        print("  [OK] Phase 3 Complete: Daytime photo blended (day_photo_raw.jpg)")

        print("\n [PHASE 4/4] Creating Night Ambiance Version at 9:16 (Fal AI Nano Banana Pro)...")
        night = self.fal_image(
            "night_photo.jpg",
            NIGHT_PROMPT,
            [day_raw],
            aspect_ratio="9:16",
        )
        print("  [OK] Phase 4 Complete: Nighttime photo generated (night_photo.jpg)")

        # Retrieve Logo and stamp it on day photo
        logo = self._get_logo_image()
        day_dest = self.ctx.workdir / "day_photo.jpg"
        if logo:
            print("\n [LOGO OVERLAY] Stamping logo onto day photo at top-right position (X=781.7, Y=108)...")
            from ..overlay import stamp_logo
            stamp_logo(
                day_raw.path,
                logo.path,
                destination=day_dest,
                box=HOMECARTEL_STORY_LOGO_BOX,
            )
            day = LocalImage(day_dest, "day_photo.jpg", "image/jpeg")
            print("  [OK] Logo overlay stamped (day_photo.jpg)")
        else:
            print("\n [INFO] No 'Logo' attachment found. Using raw day photo as day_photo.jpg.")
            shutil.copyfile(day_raw.path, day_dest)
            day = LocalImage(day_dest, "day_photo.jpg", day_raw.content_type)

        finals = [day, night]
        print(f"\n [UPLOAD] Uploading 2 photos to Airtable column '{self.ctx.definition.final_field}'...")
        self.attach_exact(self.ctx.definition.final_field, finals)
        print("  [OK] Upload Complete: Photos attached to Airtable!")

        # Auto-tag furniture item name onto 9:16 Day & Night Story photos using zero-cost local YOLO-World
        try:
            raw_item_name = str(anchor.item_name or anchor.fields.get("Item Name") or anchor.sku or anchor.record_id).strip()
            item_title, product_type = split_item_name(
                raw_item_name, fallback_product_type=str(anchor.fields.get("Product Type") or "")
            )
            print(f"\n [ITEM TAGGING] Stamping item name ('{item_title}') onto Day & Night Story photos -> '{TARGET_BLENDED_FIELD}'...")
            tag_and_upload_blended_image(
                airtable=self.ctx.airtable,
                record_id=anchor.record_id,
                blended_source=[day.path, night.path],
                item_name=item_title,
                product_type=product_type,
                category=str(self.ctx.definition.table_code or "chandeliers"),
                target_field=TARGET_BLENDED_FIELD,
                output_filename_prefix="day_night_story_tagged",
            )
        except Exception as tag_err:
            print(f"  [WARN] Failed auto-tagging item name onto Day & Night Story photos: {tag_err}")

        print(f"{'='*64}\n")
        return self.success(finals)

    def _get_interior_prompt(self) -> str:
        anchor = self.ctx.anchor
        for field in ("Interior Prompt", "Prompt"):
            val = anchor.fields.get(field)
            if val and str(val).strip():
                return str(val).strip()

        table_code = (self.ctx.definition.table_code or "").lower()
        item_name = (anchor.item_name or anchor.fields.get("Item Name") or "").lower()

        if "pendant" in table_code or "pendant" in item_name:
            env_prompt = (
                os.getenv("DAY_NIGHT_STORY_PROMPT_PENDANT_LIGHTS", "").strip()
                or os.getenv("DAY_NIGHT_PROMPT_PENDANT_LIGHTS", "").strip()
                or os.getenv("DAY_NIGHT_PROMPT_PENDANT", "").strip()
            )
            return env_prompt or "Generate me a modern dining room with plain ceiling for hanging pendant light"
        if "table" in table_code or "table lamp" in item_name:
            env_prompt = (
                os.getenv("DAY_NIGHT_STORY_PROMPT_TABLE_LAMPS", "").strip()
                or os.getenv("DAY_NIGHT_PROMPT_TABLE_LAMPS", "").strip()
                or os.getenv("DAY_NIGHT_PROMPT_TABLE_LAMP", "").strip()
            )
            return env_prompt or "Generate me a modern bedroom with a bedside table for a table lamp"
        if "floor" in table_code or "floor lamp" in item_name:
            env_prompt = (
                os.getenv("DAY_NIGHT_STORY_PROMPT_FLOOR_LAMPS", "").strip()
                or os.getenv("DAY_NIGHT_PROMPT_FLOOR_LAMPS", "").strip()
                or os.getenv("DAY_NIGHT_PROMPT_FLOOR_LAMP", "").strip()
            )
            return env_prompt or "Generate me a modern living room with empty floor space for a standing floor lamp"
        if "cluster" in table_code or "cluster" in item_name:
            env_prompt = (
                os.getenv("DAY_NIGHT_STORY_PROMPT_CLUSTER_CHANDELIER", "").strip()
                or os.getenv("DAY_NIGHT_PROMPT_CLUSTER_CHANDELIER", "").strip()
            )
            return env_prompt or "Generate me a luxury modern room with high ceiling for a cluster chandelier"

        env_prompt = (
            os.getenv("DAY_NIGHT_STORY_PROMPT_CHANDELIER", "").strip()
            or os.getenv("DAY_NIGHT_PROMPT_CHANDELIER", "").strip()
        )
        return env_prompt or "Generate me a modern living room the ceiling and plain and hanging chandelier"

    def _get_logo_image(self) -> LocalImage | None:
        anchor = self.ctx.anchor
        for field in ("Overlay Logo", "Logo", "Brand Logo", "Watermark", "Logo Image"):
            if anchor.fields.get(field):
                try:
                    return self.record_attachment(field, "source_logo")
                except Exception:
                    pass
        for field in ("Overlay Logo", "Logo"):
            try:
                att = self.table_attachment(field, "source_logo")
                if att:
                    return att
            except Exception:
                pass

        # Fallback to local asset
        logo_candidates = [
            Path("assets/homecartel_logo.png"),
            Path("JSON Prompts/homecartel_logo.png"),
            Path("scratch/refined_logo.png"),
            Path("scratch/removed_bg_logo.png"),
            Path("content_automation/assets/logo.png"),
            Path("static/img/logo.png"),
            Path("logo.png"),
        ]
        logo_file = next((p for p in logo_candidates if p.is_file()), None)
        if logo_file:
            return LocalImage(logo_file, "homecartel_logo.png", "image/png")
        return None
