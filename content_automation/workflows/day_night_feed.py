from __future__ import annotations

from ..models import CallEstimate
from .base import BaseWorkflow, NIGHT_PROMPT


# The feed remains the original two-photo workflow.
NANO_BANANA_2 = "nano-banana-2"


class DayNightFeedWorkflow(BaseWorkflow):
    """Blend the record's interior and product, then create a night photo."""

    requirements = ()
    estimate = CallEstimate(krea=0, qwen=0, kie=2)
    aspect_ratio = "4:5"
    final_filenames = ("day_photo.jpg", "night_photo.jpg")
    final_aspect_ratios = ("4:5", "4:5")
    required_columns = ("Status", "Prompt", "Interior", "Furniture Item", "Logo")

    def execute(self):
        record_id = self.ctx.anchor.record_id
        field = self.ctx.definition.final_field

        interior = self.interior_image()
        product = self.product_image()
        logo = self.logo_image()

        day_source = self.nano_image(
            "day_photo_raw.jpg",
            self.record_prompt(),
            [interior, product],
            model=NANO_BANANA_2,
        )
        day = self.stamp_logo("day_photo.jpg", day_source, logo)
        self.ctx.airtable.clear_attachment_field(record_id, field)
        self.ctx.airtable.upload_attachment(record_id, field, day)

        night = self.nano_image(
            "night_photo.jpg",
            NIGHT_PROMPT,
            [day_source],
            model=NANO_BANANA_2,
        )
        self.ctx.airtable.upload_attachment(record_id, field, night)

        finals = [day, night]
        self.ctx.airtable.verify_attachment_filenames(
            record_id,
            field,
            [image.filename for image in finals],
        )
        return self.success(finals)
