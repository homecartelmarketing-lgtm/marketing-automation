from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..assets import MAX_PROMPT_LENGTH
from ..errors import AssetValidationError
from ..models import CallEstimate, LocalImage
from .base import BaseWorkflow


NANO_BANANA_PRO = "nano-banana-pro"
BLENDED_FIELD = "1 Product 3 Style Blended"
SLIDE_SECONDS = 0.5
SLIDESHOW_SECONDS = 10.0
OUTRO_SECONDS = 5.0
OUTRO_TRANSITION_SECONDS = 0.5
OUTRO_FADE_SECONDS = 0.5
MUSIC_FIELD = "Music1"
MUSIC_REEL_FILENAME = "1_product_3_styles_reel_with_music.mp4"


class OneProductThreeStylesReelWorkflow(BaseWorkflow):
    """Blend three products into one shared Interior and assemble a reel."""

    requirements = ()
    estimate = CallEstimate(krea=0, qwen=0, kie=3)
    aspect_ratio = "9:16"
    final_filenames = (MUSIC_REEL_FILENAME,)
    final_aspect_ratios = ("9:16",)
    attachment_fields = (BLENDED_FIELD,)
    required_columns = (
        "Status",
        "Interior",
        "Furniture Item",
        "Furniture Item2",
        "Furniture Item3",
        "Prompt2",
        "Prompt3",
        "Outro",
        MUSIC_FIELD,
    )

    @classmethod
    def estimate_for(cls, reservation) -> CallEstimate:
        if len(reservation.anchor.fields.get(BLENDED_FIELD) or []) == 3:
            return CallEstimate()
        return cls.estimate

    def _blend_prompt(self, field_name: str, fallback: str = "") -> str:
        fields = self.ctx.anchor.fields
        value = str(fields.get(field_name) or "").strip()
        if not value and fallback:
            value = str(fields.get(fallback) or "").strip()
        if not value:
            names = f"{field_name} or {fallback}" if fallback else field_name
            raise AssetValidationError(
                f"Record {self.ctx.anchor.record_id} has an empty {names} field"
            )
        return value[:MAX_PROMPT_LENGTH]

    def execute(self):
        existing_blends = self.ctx.anchor.fields.get(BLENDED_FIELD) or []
        if len(existing_blends) == 3:
            attached_blends = self.refreshed_record_attachments(
                BLENDED_FIELD,
                "1_product_3_style_blended_input",
                expected_count=3,
            )
        else:
            attached_blends = self._create_and_attach_blends()

        outro = self.table_attachment("Outro", "shared_outro")
        reel = self.slideshow_video(
            "1_product_3_styles_reel.mp4",
            attached_blends,
            outro,
            slide_seconds=SLIDE_SECONDS,
            slideshow_seconds=SLIDESHOW_SECONDS,
            outro_seconds=OUTRO_SECONDS,
            transition_to_outro_seconds=OUTRO_TRANSITION_SECONDS,
            fade_out_seconds=OUTRO_FADE_SECONDS,
        )
        music = self.record_file_attachment(MUSIC_FIELD, "music1")
        music_reel = self.add_onbeat_music(
            MUSIC_REEL_FILENAME,
            reel,
            music,
            cut_seconds=SLIDE_SECONDS,
            total_seconds=SLIDESHOW_SECONDS + OUTRO_SECONDS,
            outro_seconds=OUTRO_SECONDS,
        )
        self.attach_preserving_existing(
            self.ctx.definition.final_field,
            [music_reel],
        )
        return self.success([music_reel])

    def _create_and_attach_blends(self) -> list[LocalImage]:
        interior = self.interior_image("Interior")
        products = [
            self.record_attachment("Furniture Item", "source_furniture1"),
            self.record_attachment("Furniture Item2", "source_furniture2"),
            self.record_attachment("Furniture Item3", "source_furniture3"),
        ]
        prompts = [
            self._blend_prompt("Prompt", fallback="Prompt1"),
            self._blend_prompt("Prompt2"),
            self._blend_prompt("Prompt3"),
        ]
        filenames = [
            "1_product_3_style_blended_01.jpg",
            "1_product_3_style_blended_02.jpg",
            "1_product_3_style_blended_03.jpg",
        ]

        def create_blend(values) -> LocalImage:
            filename, product, prompt = values
            return self.nano_image(
                filename,
                prompt,
                [interior, product],
                aspect_ratio="9:16",
                model=NANO_BANANA_PRO,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            blended = list(
                executor.map(create_blend, zip(filenames, products, prompts))
            )
        self.attach_exact(BLENDED_FIELD, blended)

        return self.refreshed_record_attachments(
            BLENDED_FIELD,
            "1_product_3_style_blended_input",
            expected_count=3,
        )
