from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..models import CallEstimate
from .base import BaseWorkflow


class OneProductThreeStylesFeedWorkflow(BaseWorkflow):
    requirements = ()
    estimate = CallEstimate(krea=3, qwen=3, kie=3)
    aspect_ratio = "4:5"
    final_filenames = (
        "1_product_3_style_blended1.jpg",
        "1_product_3_style_blended2.jpg",
        "1_product_3_style_blended3.jpg",
    )
    final_aspect_ratios = ("4:5", "4:5", "4:5")

    room_specs = (
        ("living room", "interior_generated1.jpg", "1_product_3_style_blended1.jpg"),
        ("bedroom", "interior_generated2.jpg", "1_product_3_style_blended2.jpg"),
        ("dining room", "interior_generated3.jpg", "1_product_3_style_blended3.jpg"),
    )

    def execute(self):
        moodboard_id = self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
        product = self.product_image()

        def create_source(spec):
            room_type, source_name, final_name = spec
            if room_type == "bedroom":
                prompt = "Generate me a bedroom with beside of table lamp"
            elif room_type == "living room":
                prompt = "Generate me a living room with beside of table lamp"
            elif room_type == "dining room":
                prompt = "Generate me a dining room with table lamp"
            else:
                prompt = f"Generate me a {room_type} with beside of table lamp"
            source = self.krea_image(
                source_name,
                prompt,
                moodboard_id=moodboard_id,
            )
            return room_type, source_name, final_name, source

        with ThreadPoolExecutor(max_workers=3) as executor:
            sources = list(executor.map(create_source, self.room_specs))
        self.attach_sources([spec[3] for spec in sources])

        def create_blend(spec):
            room_type, source_name, final_name, source = spec
            prompt = self.qwen_blend_prompt(source, product)
            return room_type, self.nano_image(final_name, prompt, [source, product])

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = dict(executor.map(create_blend, sources))
        finals = [results[room_type] for room_type, *_ in self.room_specs]
        self.attach_exact(self.ctx.definition.final_field, finals)
        return self.success(finals)
