from __future__ import annotations

from ..models import CallEstimate
from .base import BaseWorkflow


NANO_BANANA_PRO = "nano-banana-pro"
SEEDANCE_2_FAST = "bytedance/seedance-2-fast"
DAY_NIGHT_REEL_DURATION = 15
DAY_NIGHT_REEL_GENERATE_AUDIO = True
DAY_NIGHT_TIMELAPSE_PROMPT = (
    "do a timelapse of this day photo starting from 9am then make it to 9pm "
    "as the time of day. apply appropriate lighting and shadow changes while "
    "timelapse is going"
)


class DayNightReelWorkflow(BaseWorkflow):
    """Blend a vertical daytime photo, attach it, then turn it into a reel.

    The image-to-video call downloads a fresh copy of the
    ``Day and Night Blended`` Airtable attachment, making that checkpoint the
    exact source for ``REEL - Day & Night``.
    """

    requirements = ()
    estimate = CallEstimate(krea=0, qwen=0, kie=2)
    aspect_ratio = "9:16"
    final_filenames = ("day_and_night_reel.mp4",)
    final_aspect_ratios = ("9:16",)
    attachment_fields = ("Day and Night Blended",)
    required_columns = ("Status", "Prompt", "Interior", "Furniture Item")

    def execute(self):
        interior = self.interior_image()
        product = self.product_image()
        blended = self.nano_image(
            "day_and_night_blended.jpg",
            self.record_prompt(),
            [interior, product],
            aspect_ratio="9:16",
            model=NANO_BANANA_PRO,
        )
        self.attach_exact("Day and Night Blended", [blended])

        attached_blend = self.refreshed_record_attachment(
            "Day and Night Blended",
            "day_and_night_blended_input",
        )
        reel = self.image_to_video(
            "day_and_night_reel.mp4",
            DAY_NIGHT_TIMELAPSE_PROMPT,
            attached_blend,
            model=SEEDANCE_2_FAST,
            duration=DAY_NIGHT_REEL_DURATION,
            resolution="720p",
            aspect_ratio="9:16",
            generate_audio=DAY_NIGHT_REEL_GENERATE_AUDIO,
        )
        self.attach_exact(self.ctx.definition.final_field, [reel])
        return self.success([reel])
