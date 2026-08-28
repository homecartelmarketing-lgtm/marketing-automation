import datetime
import json
from pathlib import Path
import requests
from ..errors import AssetValidationError
from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


class ProductDescriptionStoryWorkflow(BaseWorkflow):
    attachment_fields = ("Furniture Item",)
    required_columns = ("Furniture Item",)
    requirements = (
        AssetRequirement("layout_product_v2.jpg", aspect_ratio="9:16"),
        AssetRequirement("product_desc.json", "json"),
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=0, fal=1)
    aspect_ratio = "9:16"
    final_filenames = ("product_closeup_with_description.jpg",)
    final_aspect_ratios = ("9:16",)

    def execute(self):
        anchor = self.ctx.anchor
        product = self.product_image()
        item_name = anchor.item_name or str(anchor.fields.get("Item Name") or "Lighting Fixture")
        product_type = anchor.product_type or str(anchor.fields.get("Product Type") or "Lighting Fixture")
        runtime = json.dumps(
            {
                "item_name": item_name,
                "product_type": product_type,
            },
            ensure_ascii=False,
        )
        prompt_text = (
            self.prompt("product_desc.json")
            + "\nUse these exact confirmed values for item_name and product_type: "
            + runtime
            + "\nAutomatically generate the two description paragraphs based on the uploaded product image. Do not add dimensions, wattage, materials, warranty, or certifications."
        )

        layout_val = anchor.fields.get("Product Closeup Description Layout") or anchor.fields.get("Product Closeup Description Layout1") or []
        layout_img = None
        if layout_val:
            try:
                layout_img = self.record_attachment("Product Closeup Description Layout", "layout")
            except Exception:
                pass
        if not layout_img:
            layout_img = LocalImage(
                self.asset_path("layout_product_v2.jpg"),
                "layout_product_v2.jpg",
            )

        final = self.nano_image(
            "product_closeup_with_description.jpg",
            prompt_text,
            [
                layout_img,
                product,
            ],
            aspect_ratio="9:16",
            model="fal-ai/nano-banana-pro/edit",
        )
        final_field = (
            self.ctx.definition.final_field
            if self.ctx.definition.final_field
            else "Product Closeup Description Converted"
        )
        self.attach_exact(final_field, [final])
        return self.success([final])


