from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..akeneo_client import split_item_name
from ..assets import MAX_PROMPT_LENGTH
from ..errors import AssetValidationError
from ..item_tagger import tag_and_upload_blended_image
from ..models import CallEstimate, LocalImage
from .base import BaseWorkflow


NANO_BANANA_PRO = "nano-banana-pro"
BLENDED_FIELD = "1 Product 3 Style Blended"
TAGGED_BLENDED_FIELD = "Blended Image with Name text"
FINAL_REEL_FIELD = "Converted Reel"
FINAL_REEL_FILENAME = "1_product_3_styles_reel.mp4"
SLIDE_SECONDS = 1.5
SLIDESHOW_SECONDS = 4.5
OUTRO_SECONDS = 5.0
OUTRO_TRANSITION_SECONDS = 0.5
OUTRO_FADE_SECONDS = 0.5


class OneProductThreeStylesReelWorkflow(BaseWorkflow):
    """Blend one product into three distinct room styles and assemble a silent 9:16 reel with YOLO item name tagging."""

    requirements = ()
    estimate = CallEstimate(krea=3, qwen=3, kie=3)
    aspect_ratio = "9:16"
    final_filenames = (FINAL_REEL_FILENAME,)
    final_aspect_ratios = ("9:16",)
    attachment_fields = (BLENDED_FIELD, TAGGED_BLENDED_FIELD)
    required_columns = (
        "Status",
        "Furniture Item",
    )

    room_specs = (
        ("living room", "interior_generated1.jpg", "1_product_3_style_blended1.jpg"),
        ("bedroom", "interior_generated2.jpg", "1_product_3_style_blended2.jpg"),
        ("dining room", "interior_generated3.jpg", "1_product_3_style_blended3.jpg"),
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
        return value[:MAX_PROMPT_LENGTH]

    def execute(self):
        fields = self.ctx.anchor.fields
        existing_blends = fields.get(BLENDED_FIELD) or []

        # 1. Obtain or generate the 3 blended images (9:16)
        if len(existing_blends) == 3:
            attached_blends = self.refreshed_record_attachments(
                BLENDED_FIELD,
                "1_product_3_style_blended_input",
                expected_count=3,
            )
        else:
            attached_blends = self._create_and_attach_blends()

        # 2. Extract item name & product type for YOLO tagging
        raw_name = str(fields.get("Item Name") or fields.get("SKU") or "Chandelier").strip()
        item_name, product_type = split_item_name(raw_name)
        if not product_type:
            product_type = "Chandelier"

        # 3. YOLO Item Name Tagging (CPU local, stamped to 9:16 safe zone)
        tagged_paths: list[Path] = []
        try:
            tag_and_upload_blended_image(
                airtable=self.ctx.airtable,
                record_id=self.ctx.anchor.record_id,
                blended_source=[b.path for b in attached_blends],
                item_name=item_name or raw_name,
                product_type=product_type,
                category="chandeliers",
                target_field=TAGGED_BLENDED_FIELD,
                output_filename_prefix="blended_named",
                fallback_if_undetected=True,
                output_tagged_paths=tagged_paths,
            )
        except Exception as err:
            print(f"[WARN] YOLO tagging encountered an issue: {err}")

        if tagged_paths and len(tagged_paths) == len(attached_blends):
            reel_slides = [LocalImage(p, p.name) for p in tagged_paths]
        else:
            reel_slides = attached_blends

        # 4. Outro: from row attachment or fallback to assets/outro_layout.jpg
        outro = None
        if fields.get("Outro"):
            try:
                outro = self.record_attachment("Outro", "source_outro")
            except Exception:
                outro = None
        if not outro:
            try:
                outro = self.table_attachment("Outro", "shared_outro")
            except Exception:
                outro = None
        if not outro:
            outro_path = Path("assets/outro_layout.jpg")
            if outro_path.is_file():
                outro = LocalImage(outro_path, "shared_outro.jpg", "image/jpeg")
            else:
                raise AssetValidationError("Outro image not found in record, table, or assets/outro_layout.jpg")

        # 5. Assemble silent 9:16 reel with 1.5s per slide
        reel = self.slideshow_video(
            FINAL_REEL_FILENAME,
            reel_slides,
            outro,
            slide_seconds=SLIDE_SECONDS,
            slideshow_seconds=SLIDESHOW_SECONDS,
            outro_seconds=OUTRO_SECONDS,
            transition_to_outro_seconds=OUTRO_TRANSITION_SECONDS,
            fade_out_seconds=OUTRO_FADE_SECONDS,
        )

        # 6. Upload final video to 'Converted Reel'
        self.attach_preserving_existing(
            FINAL_REEL_FIELD,
            [reel],
        )

        # 7. Stamp timestamp & update status
        try:
            from ..airtable_client import current_pht_timestamp
            self.ctx.airtable.update_records([{
                "id": self.ctx.anchor.record_id,
                "fields": {
                    "Status": "Complete",
                    "Date and Time Generated": current_pht_timestamp(),
                },
            }])
        except Exception as err:
            print(f"[WARN] Failed to update Status/Timestamp: {err}")

        return self.success([reel])

    def _create_and_attach_blends(self) -> list[LocalImage]:
        fields = self.ctx.anchor.fields
        if fields.get("Furniture Item"):
            product = self.record_attachment("Furniture Item", "source_furniture")
        else:
            product = self.product_image()

        interiors: list[LocalImage] = []
        for field_name, fallback_field in [("Interior1", "Interior"), ("Interior2", None), ("Interior3", None)]:
            if fields.get(field_name):
                interiors.append(self.record_attachment(field_name, f"source_{field_name.lower()}"))
            elif fallback_field and fields.get(fallback_field):
                interiors.append(self.record_attachment(fallback_field, f"source_{fallback_field.lower()}"))

        moodboard_id = ""
        try:
            moodboard_id = self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
        except Exception:
            pass

        if len(interiors) < 3:
            default_prompts = [
                self._blend_prompt("Prompt1", fallback="Prompt") or "Generate me a modern luxury living room with high ceiling for chandelier",
                self._blend_prompt("Prompt2") or "Generate me a modern luxury dining room with dining table for chandelier",
                self._blend_prompt("Prompt3") or "Generate me a modern luxury foyer entryway with high ceiling for chandelier",
            ]
            while len(interiors) < 3:
                idx = len(interiors)
                interiors.append(
                    self.krea_image(
                        f"interior_generated_{idx + 1}.jpg",
                        default_prompts[idx],
                        moodboard_id=moodboard_id,
                        aspect_ratio="9:16",
                    )
                )

        filenames = [
            "1_product_3_style_blended_01.jpg",
            "1_product_3_style_blended_02.jpg",
            "1_product_3_style_blended_03.jpg",
        ]

        def create_blend(args) -> LocalImage:
            idx, (interior, filename) = args
            prompt_key = f"Prompt{idx + 1}"
            custom_prompt = self._blend_prompt(prompt_key, fallback="Prompt" if idx == 0 else "")
            if not custom_prompt:
                try:
                    custom_prompt = self.qwen_blend_prompt(interior, product)
                except Exception:
                    custom_prompt = "Blend this chandelier naturally into the room with realistic lighting and reflections."
            return self.nano_image(
                filename,
                custom_prompt,
                [interior, product],
                aspect_ratio="9:16",
                model=NANO_BANANA_PRO,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            blended = list(
                executor.map(create_blend, enumerate(zip(interiors, filenames)))
            )

        self.attach_exact(BLENDED_FIELD, blended)

        return self.refreshed_record_attachments(
            BLENDED_FIELD,
            "1_product_3_style_blended_input",
            expected_count=3,
        )
