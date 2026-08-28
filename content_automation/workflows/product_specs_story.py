from __future__ import annotations

import json

from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


class ProductSpecsStoryWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement("product_specs_layout.png", aspect_ratio="9:16"),
        AssetRequirement("product_closeup_specs.json", "json"),
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=1)
    aspect_ratio = "9:16"
    final_filenames = ("product_closeup_with_specifications.jpg",)
    final_aspect_ratios = ("9:16",)

    def execute(self):
        anchor = self.ctx.anchor
        metadata = json.dumps(
            {
                "item_name": anchor.item_name,
                "product_type": anchor.product_type,
                "measurement": anchor.measurement,
            },
            ensure_ascii=False,
        )
        final = self.nano_image(
            "product_closeup_with_specifications.jpg",
            self.prompt("product_closeup_specs.json")
            + "\nReplace every sample product text with these exact confirmed values: "
            + metadata
            + "\nDo not invent or infer any other specification.",
            [
                LocalImage(
                    self.asset_path("product_specs_layout.png"),
                    "product_specs_layout.png",
                    "image/png",
                ),
                self.product_image(),
            ],
            aspect_ratio="9:16",
        )
        self.attach_exact(self.ctx.definition.final_field, [final])
        return self.success([final])
