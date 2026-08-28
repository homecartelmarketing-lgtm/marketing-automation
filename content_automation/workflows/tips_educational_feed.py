from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


NANO_BANANA_PRO = "nano-banana-pro"
BLENDED_FIELD = "Tips and Edu Blended"
LAYOUT_FIELDS = (
    "Tips and Edu Layout1",
    "Tips and Edu Layout2",
    "Tips and Edu Layout3",
)
PROMPT_FIELDS = ("Prompt1", "Prompt2", "Prompt3")
INTERIOR_FIELDS = ("Interior", "Interior2", "Interior3")
FURNITURE_FIELDS = (
    "Furniture Item",
    "Furniture Item2",
    "Furniture Item3",
)
BLENDED_FILENAMES = (
    "tips_and_edu_blended_01.jpg",
    "tips_and_edu_blended_02.jpg",
    "tips_and_edu_blended_03.jpg",
)
FINAL_FILENAMES = (
    "tips_and_edu_feed_01.jpg",
    "tips_and_edu_feed_02.jpg",
    "tips_and_edu_feed_03.jpg",
)
LAYOUT_PROMPTS = (
    "Tips and Edu Feeds/tipsedufeeds1.json",
    "Tips and Edu Feeds/tipsedufeeds2.json",
    "Tips and Edu Feeds/tipsedufeeds3.json",
)


class TipsEducationalFeedWorkflow(BaseWorkflow):
    """Blend three products into rooms, then apply three authored layouts."""

    requirements = tuple(
        AssetRequirement(path, "json") for path in LAYOUT_PROMPTS
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=6)
    aspect_ratio = "9:16"
    final_filenames = FINAL_FILENAMES
    final_aspect_ratios = ("9:16", "9:16", "9:16")
    attachment_fields = (BLENDED_FIELD,)
    schema_fields = {
        **{
            field: "multipleAttachments"
            for field in (
                *INTERIOR_FIELDS,
                *FURNITURE_FIELDS,
                *LAYOUT_FIELDS,
                BLENDED_FIELD,
            )
        },
        **{field: "multilineText" for field in PROMPT_FIELDS},
    }

    @classmethod
    def estimate_for(cls, reservation) -> CallEstimate:
        if len(reservation.anchor.fields.get(BLENDED_FIELD) or []) == 3:
            return CallEstimate(kie=3)
        return cls.estimate

    def _create_and_attach_blends(self) -> list[LocalImage]:
        interiors = [
            self.record_attachment(field, f"tips_interior{index}")
            for index, field in enumerate(INTERIOR_FIELDS, start=1)
        ]
        products = [
            self.record_attachment(field, f"tips_furniture{index}")
            for index, field in enumerate(FURNITURE_FIELDS, start=1)
        ]
        prompts = [
            self.record_prompt(field)
            for field in PROMPT_FIELDS
        ]

        def create(values) -> LocalImage:
            filename, interior, product, prompt = values
            return self.nano_image(
                filename,
                prompt,
                [interior, product],
                aspect_ratio=self.aspect_ratio,
                model=NANO_BANANA_PRO,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            blends = list(
                executor.map(
                    create,
                    zip(BLENDED_FILENAMES, interiors, products, prompts),
                )
            )
        self.attach_exact(BLENDED_FIELD, blends)
        return self.refreshed_record_attachments(
            BLENDED_FIELD,
            "tips_blended_input",
            expected_count=3,
        )

    def _apply_layouts(
        self,
        blends: list[LocalImage],
    ) -> list[LocalImage]:
        layouts = [
            self.record_attachment(field, f"tips_layout{index}")
            for index, field in enumerate(LAYOUT_FIELDS, start=1)
        ]
        prompts = [self.prompt(path) for path in LAYOUT_PROMPTS]

        def create(values) -> LocalImage:
            filename, layout, blend, prompt = values
            return self.nano_image(
                filename,
                prompt,
                [layout, blend],
                aspect_ratio=self.aspect_ratio,
                model=NANO_BANANA_PRO,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            return list(
                executor.map(
                    create,
                    zip(FINAL_FILENAMES, layouts, blends, prompts),
                )
            )

    def execute(self):
        existing = self.ctx.anchor.fields.get(BLENDED_FIELD) or []
        if len(existing) == 3:
            blends = self.refreshed_record_attachments(
                BLENDED_FIELD,
                "tips_blended_input",
                expected_count=3,
            )
        else:
            blends = self._create_and_attach_blends()

        finals = self._apply_layouts(blends)
        self.attach_exact(self.ctx.definition.final_field, finals)
        return self.success(finals)
