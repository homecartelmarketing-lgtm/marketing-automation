from __future__ import annotations

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

        final = self.nano_image(
            "cta_blended_image.jpg",
            self.prompt("CTA.json"),
            # CTA.json defines the blended scene as the first uploaded image
            # and the poster layout as the second reference image.
            [attached_blend, layout],
            aspect_ratio="9:16",
        )
        final_field = (
            "CTA Converted Blended"
            if "CTA Converted Blended" in self.ctx.anchor.fields
            else (self.ctx.definition.final_field or "CTA Converted Image")
        )
        self.attach_exact(final_field, [final])
        return self.success([final])
