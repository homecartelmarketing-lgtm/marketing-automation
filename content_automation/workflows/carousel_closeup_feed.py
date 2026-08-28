from __future__ import annotations

import json

from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


class CarouselCloseupFeedWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement("prompt_first_photo.jpg"),
        AssetRequirement("prompt_first_photo.json", "json"),
        AssetRequirement("prompt_second_photo.jpg"),
        AssetRequirement("prompt_second_photo.json", "json"),
        AssetRequirement("prompt_third_photo.jpg"),
        AssetRequirement("prompt_third_photo.json", "json"),
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=3)
    aspect_ratio = "4:5"
    final_filenames = (
        "carousel_closeup_1.jpg",
        "carousel_closeup_2.jpg",
        "carousel_closeup_3.jpg",
    )
    final_aspect_ratios = ("4:5", "4:5", "4:5")

    def execute(self):
        product = self.product_image()
        anchor = self.ctx.anchor
        metadata = json.dumps(
            {
                "item_name": anchor.item_name,
                "product_type": anchor.product_type,
                "measurement": anchor.measurement,
            },
            ensure_ascii=False,
        )
        configurations = (
            (
                "prompt_first_photo.jpg",
                "prompt_first_photo.json",
                "carousel_closeup_1.jpg",
                "",
            ),
            (
                "prompt_second_photo.jpg",
                "prompt_second_photo.json",
                "carousel_closeup_2.jpg",
                (
                    "\nAUTHORITATIVE SLIDE 2 RULE: This is the product-name and "
                    "measurement slide, not a macro/detail slide. Preserve the "
                    "white-background reference layout and its typography positions. "
                    "Render the item name in bold, product type in regular weight, "
                    "and measurement in the reference measurement position. Replace "
                    "all sample text exactly and do not add or change facts. "
                    f"RUNTIME METADATA: {metadata}"
                ),
            ),
            (
                "prompt_third_photo.jpg",
                "prompt_third_photo.json",
                "carousel_closeup_3.jpg",
                "",
            ),
        )
        finals: list[LocalImage] = []
        for layout_name, prompt_name, filename, runtime_instruction in configurations:
            finals.append(
                self.nano_image(
                    filename,
                    self.prompt(prompt_name) + runtime_instruction,
                    [
                        LocalImage(self.asset_path(layout_name), layout_name),
                        product,
                    ],
                    aspect_ratio="4:5",
                )
            )
        self.attach_exact(self.ctx.definition.final_field, finals)
        return self.success(finals)
