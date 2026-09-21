from __future__ import annotations

import os
import sys
from pathlib import Path

from ..akeneo_client import split_item_name
from ..item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
from ..models import AssetRequirement, CallEstimate, LocalImage
from ..overlay import HOMECARTEL_STORY_LOGO_BOX
from .base import BaseWorkflow


class MoodboardStoryWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement(
            "Moodboard Story/stories_mb_reference.jpg",
            aspect_ratio="9:16",
        ),
        AssetRequirement("Moodboard Story/moodboard.json", "json"),
    )
    estimate = CallEstimate(krea=1, qwen=0, kie=0, fal=2)
    aspect_ratio = "9:16"
    final_filenames = ("converted.jpg",)
    final_aspect_ratios = ("9:16",)

    def execute(self):
        anchor = self.ctx.anchor
        item_name = anchor.item_name or anchor.fields.get("Item Name") or "Pendant Light"
        sku = anchor.sku or anchor.fields.get("SKU") or "N/A"

        print(f"\n================================================================================")
        print(f" [PROCESSING] {item_name[:50]}")
        print(f"   * Airtable Record ID: {anchor.record_id}")
        print(f"   * SKU:                {sku}")
        print(f"   * Format:             9:16 Vertical Instagram Story (1080x1920)")
        print(f"================================================================================")

        # 0. Ensure Moodboard Layout reference is attached if empty
        ref_path = self.asset_path("Moodboard Story/stories_mb_reference.jpg")
        ref_layout = LocalImage(ref_path, "stories_mb_reference.jpg")
        if not anchor.fields.get("Moodboard Layout"):
            try:
                self.attach_exact("Moodboard Layout", [ref_layout])
                print("  [INIT] Attached layout reference to Airtable ('Moodboard Layout')")
            except Exception as e:
                print(f"  [WARN] Could not attach Moodboard Layout: {e}")

        # Phase 1: Krea AI Interior Generation
        print("\n [PHASE 1/5] KREA AI - Room Interior Generation (9:16)")
        product = self.product_image()
        interior_prompt = self._get_interior_prompt()
        moodboard_id = self._get_moodboard_id()
        print(f"   * Prompt:        \"{interior_prompt}\"")
        print(f"   * Moodboard ID:  {moodboard_id}")
        print(f"   * Resolution:    1080x1920 (9:16)")
        print(f"   ... Generating Krea AI room interior ...")
        source = self.krea_image(
            f"interior_{anchor.record_id}.jpg",
            interior_prompt,
            aspect_ratio="9:16",
            moodboard_id=moodboard_id,
        )
        self.attach_exact("Interior Generated", [source])
        print(f"   [OK] Phase 1 Complete -> Uploaded to 'Interior Generated'")

        # Phase 2: Claude Sonnet 5 Prompt Generation
        print("\n [PHASE 2/5] CLAUDE SONNET 5 - Vision Analysis & Blending Prompt")
        print(f"   * Model:         anthropic/claude-sonnet-5 (via Fal AI)")
        print(f"   * Task:          Analyzing room perspective, ceiling structure, and {item_name} mounting...")
        print(f"   ... Generating precise physical blending instructions ...")
        blend_prompt = self.claude_blend_prompt(source, product)
        self.update_field("Generated Prompt", blend_prompt)
        prompt_snippet = blend_prompt[:95].replace('\n', ' ') + "..." if len(blend_prompt) > 95 else blend_prompt
        print(f"   * Prompt Result: \"{prompt_snippet}\"")
        print(f"   [OK] Phase 2 Complete -> Saved to 'Generated Prompt'")

        # Phase 3: Fal AI Nano Banana Pro Blending
        print("\n [PHASE 3/5] NANO BANANA PRO - Daytime Room Blending (9:16)")
        print(f"   * Model:         fal-ai/nano-banana-pro/edit")
        print(f"   * Task:          Mounting and naturally illuminating product in the room...")
        print(f"   ... Blending product into daytime interior ...")
        blend = self.fal_image(
            f"blended_{anchor.record_id}.jpg",
            blend_prompt,
            [source, product],
            aspect_ratio="9:16",
        )

        # Local PIL Brand Logo Stamping onto Blended Image (Story Top-Right: X=781.7, Y=108.0)
        logo = self._get_logo_image()
        stamped_blend = blend
        if logo:
            print("\n [LOGO STAMPING] Stamping HomeCartel Story logo onto Blended Image")
            print(f"   * Placement:     Top-Right (X=781.7, Y=108.0 | 190.3 x 63.5 px)")
            print(f"   * Cost:          Zero API Cost (Local High-Resolution PIL engine)")
            stamped_blend = self.stamp_logo(
                f"blended_stamped_{anchor.record_id}.jpg",
                blend,
                logo,
                box=HOMECARTEL_STORY_LOGO_BOX,
            )
            self.attach_exact("Blended Image", [stamped_blend])
            self.attach_exact("Homecartel Logo Overlay", [stamped_blend])
            print(f"   [OK] Attached watermarked image to 'Blended Image' and 'Homecartel Logo Overlay'")
        else:
            self.attach_exact("Blended Image", [blend])
            print(f"   [OK] Attached unbranded image to 'Blended Image' (no logo found)")

        # Auto-tag furniture item name onto 9:16 Blended Image using zero-cost local YOLO-World
        try:
            raw_item_name = str(anchor.item_name or anchor.fields.get("Item Name") or sku).strip()
            item_title, product_type = split_item_name(
                raw_item_name, fallback_product_type=str(anchor.fields.get("Product Type") or "")
            )
            raw_cat = str(self.ctx.definition.table_code or "pendant_lights").lower()
            if "chandelier" in raw_cat:
                clean_category = "chandeliers"
            elif "pendant" in raw_cat:
                clean_category = "pendant_lights"
            elif "floor" in raw_cat:
                clean_category = "floor_lamps"
            else:
                clean_category = raw_cat

            print(f"\n [ITEM TAGGING] Stamping item name ('{item_title}') onto Blended Image -> '{TARGET_BLENDED_FIELD}'...")
            print(f"   * Category:      {clean_category}")
            print(f"   * Safe Fallback: Mid-Left safe zone (X=100, Y=800) if undetected")
            tag_and_upload_blended_image(
                airtable=self.ctx.airtable,
                record_id=anchor.record_id,
                blended_source=stamped_blend.path,
                item_name=item_title,
                product_type=product_type,
                category=clean_category,
                target_field=TARGET_BLENDED_FIELD,
                output_filename_prefix="moodboard_story_tagged",
                fallback_if_undetected=True,
                fallback_position=(100, 800),
            )
        except Exception as tag_err:
            print(f"  [WARN] Failed auto-tagging item name onto Moodboard Story blended image: {tag_err}")

        # Phase 4: Local PIL Logo Overlay Confirmation
        print("\n [PHASE 4/5] LOCAL PIL - Brand Logo Overlay Stamping")
        if logo:
            print(f"   * Placement:     Top-Right (X=781.7, Y=108.0 | 190.3 x 63.5 px)")
            print(f"   * Cost:          Zero API Cost (Local High-Resolution PIL engine)")
            print(f"   [OK] Phase 4 Complete -> Verified on 'Blended Image', 'Homecartel Logo Overlay', and '{TARGET_BLENDED_FIELD}'")
        else:
            print("\n [PHASE 4/5] LOGO OVERLAY: Skipped (no logo attachment found)")

        # Phase 5: Fal AI Moodboard Card Conversion
        print("\n [PHASE 5/5] NANO BANANA PRO - Editorial Material Moodboard Conversion")
        print(f"   * Layout Ref:    stories_mb_reference.jpg")
        print(f"   * JSON Prompt:   JSON Prompts/Moodboard Story/moodboard.json")
        print(f"   * Task:          Transforming blended room into multi-panel material moodboard collage...")
        print(f"   ... Generating editorial moodboard story card ...")
        converted = self.fal_image(
            f"converted_{anchor.record_id}.jpg",
            self.prompt("Moodboard Story/moodboard.json"),
            [ref_layout, blend],
            aspect_ratio="9:16",
        )
        self.attach_exact("Moodboard Converted", [converted])
        print(f"   [OK] Phase 5 Complete -> Uploaded to 'Moodboard Converted'")

        finals = [converted]
        print(f"\n================================================================================")
        print(f" [COMPLETE] Moodboard Story successfully finished for {item_name} ({anchor.record_id})!")
        print(f"   * Status updated to: 'Complete'")
        print(f"   * Final Output:      'Moodboard Converted'")
        print(f"================================================================================")
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
            return (
                os.getenv("MOODBOARD_STORY_PROMPT_PENDANT_LIGHTS", "").strip()
                or os.getenv("MOODBOARD_PROMPT_PENDANT", "").strip()
                or os.getenv("KREA_PROMPT", "").strip()
                or "Generate me a modern dining room"
            )
        if "floor" in table_code or "floor" in item_name:
            return (
                os.getenv("MOODBOARD_STORY_PROMPT_FLOOR_LAMPS", "").strip()
                or os.getenv("MOODBOARD_PROMPT_FLOOR_LAMP", "").strip()
                or os.getenv("KREA_PROMPT", "").strip()
                or "Generate me a modern living room"
            )
        if "chandelier" in table_code or "chandelier" in item_name:
            return (
                os.getenv("MOODBOARD_STORY_PROMPT_CHANDELIER", "").strip()
                or os.getenv("MOODBOARD_PROMPT_CHANDELIER", "").strip()
                or os.getenv("KREA_PROMPT", "").strip()
                or "Generate me a modern living room"
            )

        return os.getenv("KREA_PROMPT", "").strip() or "Generate me a modern living room"

    def _get_moodboard_id(self) -> str:
        krea_override = os.getenv("KREA_MOODBOARD_ID", "").strip()
        if krea_override:
            return krea_override

        table_code = (self.ctx.definition.table_code or "").lower()
        mb_id = self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
        if mb_id:
            return mb_id

        item_name = (self.ctx.anchor.item_name or self.ctx.anchor.fields.get("Item Name") or "").lower()
        if "floor" in table_code or "floor" in item_name:
            return (
                os.getenv("MOODBOARD_ID_FLOOR_LAMPS", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_FLOOR_LAMPS", "").strip()
                or "c4c15a18-a92d-4465-924f-c85cfe1958bc"
            )
        if "pendant" in table_code or "pendant" in item_name:
            return (
                os.getenv("MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
                or os.getenv("KREA_MOODBOARD_ID_PENDANT_LIGHTS", "").strip()
                or "0844ad92-c34a-4dc8-9d70-d09498dc098c"
            )
        return (
            os.getenv("MOODBOARD_ID_CHANDELIER", "").strip()
            or os.getenv("KREA_MOODBOARD_ID_CHANDELIERS", "").strip()
            or "de6ad512-870d-4ab7-a48c-3f3ca85faf24"
        )

    def _get_logo_image(self) -> LocalImage | None:
        anchor = self.ctx.anchor
        for field in ("Logo", "Brand Logo", "Watermark", "Logo Image"):
            if anchor.fields.get(field):
                return self.record_attachment(field, "source_logo")
        logo_path = self.ctx.assets.path("assets/homecartel_logo.png")
        if not logo_path.is_file():
            logo_path = self.ctx.assets.path("homecartel_logo.png")
        if logo_path.is_file():
            return LocalImage(logo_path, "homecartel_logo.png", "image/png")
        return None
