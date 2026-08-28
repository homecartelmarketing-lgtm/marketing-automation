from __future__ import annotations

from ..models import AssetRequirement, CallEstimate
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

        final = self.nano_image(
            "tips_educational_story.jpg",
            self.prompt("Tips and Edu Story/tips-and-edu.json"),
            # The fixed prompt defines the blended photo as image 1 and the
            # locked Tips & Educational template as image 2.
            [attached_blend, layout],
            aspect_ratio="9:16",
        )

        self.attach_exact(self.ctx.definition.final_field, [final])
        return self.success([final])
