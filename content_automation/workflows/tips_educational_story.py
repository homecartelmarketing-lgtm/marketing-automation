from __future__ import annotations

from ..akeneo_client import split_item_name
from ..item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
from ..models import AssetRequirement, CallEstimate, LocalImage
from ..overlay import HOMECARTEL_STORY_LOGO_BOX
from .base import BaseWorkflow


class TipsEducationalStoryWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement("Tips and Edu Story/tips-and-edu.json", "json"),
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=2)
    aspect_ratio = "9:16"
    final_filenames = ("tips_educational_story.jpg",)
    final_aspect_ratios = ("9:16",)
    attachment_fields = ("Tips Edu Blended Image",)
    required_columns = ("Status", "Prompt", "Tips Edu layout")

    def execute(self):
        interior = self.interior_image("Interior")
        product = self.product_image()
        layout = self.record_attachment("Tips Edu layout", "tips_edu_layout")

        blended = self.nano_image(
            "tips_story_blended.jpg",
            self.record_prompt("Prompt"),
            [interior, product],
            aspect_ratio="9:16",
        )

        # Airtable is the visible checkpoint between the blend and conversion.
        self.attach_exact("Tips Edu Blended Image", [blended])
        attached_blend = self.refreshed_record_attachment(
            "Tips Edu Blended Image",
            "tips_edu_blended_input",
        )

        # Auto-tag furniture item name onto 9:16 Blended Image using zero-cost local YOLO-World
        try:
            anchor = self.ctx.anchor
            raw_item_name = str(anchor.item_name or anchor.fields.get("Item Name") or anchor.sku or anchor.record_id).strip()
            item_title, product_type = split_item_name(
                raw_item_name, fallback_product_type=str(anchor.fields.get("Product Type") or "")
            )
            print(f"\n [ITEM TAGGING] Stamping item name ('{item_title}') onto Blended Image -> '{TARGET_BLENDED_FIELD}'...")
            tag_and_upload_blended_image(
                airtable=self.ctx.airtable,
                record_id=anchor.record_id,
                blended_source=blended.path,
                item_name=item_title,
                product_type=product_type,
                category=str(self.ctx.definition.table_code or "pendant_lights"),
                target_field=TARGET_BLENDED_FIELD,
                output_filename_prefix="tips_edu_story_tagged",
            )
        except Exception as tag_err:
            print(f"  [WARN] Failed auto-tagging item name onto Tips & Edu Story photos: {tag_err}")

        # Use tagged blend for final layout conversion if available
        conversion_blend = attached_blend
        if anchor.record_id:
            try:
                tagged_attachment = self.refreshed_record_attachment(
                    TARGET_BLENDED_FIELD,
                    "tips_edu_tagged_blend_input",
                )
                if tagged_attachment:
                    conversion_blend = tagged_attachment
            except Exception:
                pass

        final = self.nano_image(
            "tips_educational_story.jpg",
            self.prompt("Tips and Edu Story/tips-and-edu.json"),
            # The fixed prompt defines the tagged blended photo as image 1 and the
            # locked Tips & Educational template as image 2.
            [conversion_blend, layout],
            aspect_ratio="9:16",
        )

        # Local PIL Brand Logo Stamping (Story Top-Right: X=781.7, Y=108.0 | 190.3 x 63.5 px)
        logo = self._get_logo_image()
        if logo:
            print("\n [LOGO STAMPING] Stamping HomeCartel Story logo onto final Tips & Edu Story conversion")
            print("   * Placement:     Top-Right (X=781.7, Y=108.0 | 190.3 x 63.5 px)")
            print("   * Cost:          Zero API Cost (Local High-Resolution PIL engine)")
            final = self.stamp_logo(
                f"tips_educational_story_stamped_{self.ctx.anchor.record_id}.jpg",
                final,
                logo,
                box=HOMECARTEL_STORY_LOGO_BOX,
            )

        self.attach_exact(self.ctx.definition.final_field, [final])
        return self.success([final])

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
