from __future__ import annotations

from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


class RevisedMoodboardFeedWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement("promptforlayoutmoodboard.json", "json"),
        AssetRequirement("referencephoto_moodboard.png"),
        AssetRequirement("second_moodboard.json", "json"),
    )
    estimate = CallEstimate(krea=1, qwen=1, kie=3)
    aspect_ratio = "4:5"
    attachment_fields = ("Moodboard V1", "Moodboard V2")
    final_filenames = (
        "blended_image_revised_moodboard.jpg",
        "moodboard_converted_v1.jpg",
        "moodboard_converted_v2.jpg",
    )
    final_aspect_ratios = ("4:5", "4:5", "4:5")

    def execute(self):
        moodboard_id = self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
        product = self.product_image()
        source = self.krea_image(
            "moodboard_source_interior.jpg",
            (
                "Generate a premium modern interior with balanced negative space, "
                "warm neutral materials, and realistic editorial lighting, ready for "
                "a featured product placement. Do not add text."
            ),
            moodboard_id=moodboard_id,
        )
        self.attach_sources([source])
        blend = self.nano_image(
            "blended_image_revised_moodboard.jpg",
            self.qwen_blend_prompt(source, product),
            [source, product],
        )
        v1 = self.nano_image(
            "moodboard_converted_v1.jpg",
            self.prompt("promptforlayoutmoodboard.json"),
            [blend],
        )
        v2 = self.nano_image(
            "moodboard_converted_v2.jpg",
            self.prompt("second_moodboard.json"),
            [
                LocalImage(
                    self.asset_path("referencephoto_moodboard.png"),
                    "referencephoto_moodboard.png",
                    "image/png",
                ),
                blend,
            ],
        )
        finals = [blend, v1, v2]
        self.attach_exact(self.ctx.definition.final_field, finals)
        self.attach_exact("Moodboard V1", [blend, v1])
        self.attach_exact("Moodboard V2", [blend, v2])
        return self.success(finals)
