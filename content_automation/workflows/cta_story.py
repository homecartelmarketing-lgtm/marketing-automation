from __future__ import annotations

from ..akeneo_client import split_item_name
from ..item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
from ..models import AssetRequirement, CallEstimate
from .base import BaseWorkflow


class CtaStoryWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement("CTA.json", "json"),
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=2)
    aspect_ratio = "9:16"
    attachment_fields = ("CTA Blended Image", "CTA Blended")
    required_columns = ("CTA Layout",)
    final_filenames = ("cta_blended_image.jpg",)
    final_aspect_ratios = ("9:16",)

    def execute(self):
        product = self.product_image()
        interior_field = "CTA Interior"
        for candidate in ("CTA Interior", "CTA Interior Image", "Interior", "Interior Image", "Interior1"):
            if self.ctx.anchor.fields.get(candidate):
                interior_field = candidate
                break
        source = self.interior_image(interior_field)
        layout = self.record_attachment("CTA Layout", "cta_layout")
        prompt_field = "CTA Prompt Blending" if "CTA Prompt Blending" in self.ctx.anchor.fields else "Prompt"

        blend = self.nano_image(
            "cta_blended.jpg",
            self.record_prompt(prompt_field),
            [source, product],
            aspect_ratio="9:16",
        )
        # Publish the first Nano Banana result before the CTA conversion.
        blended_field = (
            "CTA Blended Image"
            if "CTA Blended Image" in self.ctx.anchor.fields
            or (
                hasattr(self.ctx.airtable, "schema")
                and hasattr(self.ctx.airtable.schema, "__call__")
                and "CTA Blended Image" in self.ctx.airtable.schema()
            )
            else "CTA Blended"
        )
        self.attach_exact(blended_field, [blend])
        attached_blend = self.refreshed_record_attachment(
            blended_field,
            "cta_blended_input",
        )

        # Auto-tag furniture item name onto 9:16 Story blended photos using zero-cost local YOLO-World (with fallback)
        anchor = self.ctx.anchor
        try:
            raw_item_name = str(anchor.fields.get("Item Name") or anchor.fields.get("SKU") or anchor.record_id).strip()
            item_title, product_type = split_item_name(
                raw_item_name, fallback_product_type=str(anchor.fields.get("Product Type") or "")
            )
            print(f"\n [ITEM TAGGING] Stamping item name ('{item_title}') onto Blended Image -> '{TARGET_BLENDED_FIELD}'...")
            tag_and_upload_blended_image(
                airtable=self.ctx.airtable,
                record_id=anchor.record_id,
                blended_source=blend.path,
                item_name=item_title,
                product_type=product_type,
                category=str(self.ctx.definition.table_code or "chandeliers"),
                target_field=TARGET_BLENDED_FIELD,
                output_filename_prefix="cta_story_tagged",
                fallback_if_undetected=True,
            )
        except Exception as tag_err:
            print(f"  [WARN] Failed auto-tagging item name onto CTA Story photos: {tag_err}")

        # Use tagged blend for final layout conversion if available
        conversion_blend = attached_blend
        if anchor.record_id:
            try:
                tagged_attachment = self.refreshed_record_attachment(
                    TARGET_BLENDED_FIELD,
                    "cta_tagged_blend_input",
                )
                if tagged_attachment:
                    conversion_blend = tagged_attachment
            except Exception:
                pass

        final = self.nano_image(
            "cta_blended_image.jpg",
            self.prompt("CTA.json"),
            # CTA.json defines the blended scene as the first uploaded image
            # and the poster layout as the second reference image.
            [conversion_blend, layout],
            aspect_ratio="9:16",
        )
        final_field = (
            "CTA Converted Blended"
            if "CTA Converted Blended" in self.ctx.anchor.fields
            else (self.ctx.definition.final_field or "CTA Converted Image")
        )
        self.attach_exact(final_field, [final])
        return self.success([final])
