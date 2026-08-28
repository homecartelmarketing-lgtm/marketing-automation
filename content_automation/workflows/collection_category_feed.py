from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..errors import ConfigurationError
from ..models import CallEstimate
from .base import BaseWorkflow, FIXED_PRODUCT_BLEND_PROMPT


class CollectionCategoryFeedWorkflow(BaseWorkflow):
    requirements = ()
    estimate = CallEstimate(krea=4, qwen=3, kie=1)
    aspect_ratio = "4:5"
    final_filenames = (
        "collection_styled_1.jpg",
        "collection_categ_bedroom.jpg",
        "collection_categ_dining_room.jpg",
        "collection_categ_kitchen.jpg",
    )
    final_aspect_ratios = ("4:5", "4:5", "4:5", "4:5")
    attachment_fields = ("Styled Photo - Collection Category",)

    def preflight(self) -> None:
        super().preflight()
        if not self.ctx.settings.moodboard_id(self.ctx.definition.table_code):
            table = self.ctx.anchor.table
            raise ConfigurationError(
                f"Collection Feed requires {table.moodboard_env} for {table.label}"
            )

    def execute(self):
        moodboard_id = self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
        product = self.product_image()
        source = self.krea_image(
            "collection_source_modern_interior.jpg",
            (
                "Generate a premium photorealistic modern interior suitable for the "
                "featured lighting or furniture product, with warm neutral materials, "
                "balanced negative space, realistic architecture, and commercial "
                "editorial lighting. Do not add text."
            ),
            moodboard_id=moodboard_id,
            aspect_ratio="4:5",
        )
        self.attach_sources([source])
        base = self.nano_image(
            "collection_styled_1.jpg",
            FIXED_PRODUCT_BLEND_PROMPT,
            [source, product],
            aspect_ratio="4:5",
        )
        room_specs = (
            ("bedroom", "collection_categ_bedroom.jpg"),
            ("dining room", "collection_categ_dining_room.jpg"),
            ("kitchen", "collection_categ_kitchen.jpg"),
        )

        def qwen_prompt(spec):
            room_type, filename = spec
            return room_type, filename, self.qwen_room_transform_prompt(base, room_type)

        with ThreadPoolExecutor(max_workers=3) as executor:
            prompt_specs = list(executor.map(qwen_prompt, room_specs))

        def generate_room(spec):
            room_type, filename, prompt = spec
            image = self.krea_image(
                filename,
                prompt,
                moodboard_id=moodboard_id,
                style_reference=base,
                style_reference_strength=0.5,
                aspect_ratio="4:5",
            )
            return room_type, image

        with ThreadPoolExecutor(max_workers=3) as executor:
            derived = dict(executor.map(generate_room, prompt_specs))
        finals = [
            base,
            derived["bedroom"],
            derived["dining room"],
            derived["kitchen"],
        ]
        self.attach_exact(self.ctx.definition.final_field, finals)
        self.attach_exact("Styled Photo - Collection Category", finals)
        return self.success(finals)
