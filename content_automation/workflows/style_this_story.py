from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..assets import MAX_PROMPT_LENGTH
from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


NANO_BANANA_PRO = "nano-banana-pro"
BLENDED_FIELD = "Style This Blended"
DOUBLE_TAP_CONVERTED_FIELD = "Double Tap Converted"
HOW_WOULD_YOU_LAYOUT_FIELD = "How would You Layout"
DOUBLE_TAP_LAYOUT_FIELD = "Double Tap"

INTERIOR_FIELDS = ("Interior", "Interior2", "Interior3", "Interior4")
FURNITURE_FIELD = "Furniture Item"
PROMPT_FIELDS = ("Prompt", "Prompt2", "Prompt3", "Prompt4")
BLENDED_FILENAMES = (
    "style_this01.jpg",
    "style_this02.jpg",
    "style_this03.jpg",
    "style_this04.jpg",
)
FINAL_FILENAMES = (
    "how_would_you_style_this.jpg",
    "double_tap_blended01.jpg",
    "double_tap_blended02.jpg",
    "double_tap_blended03.jpg",
)

HOW_WOULD_YOU_PROMPT = "Style This/how_would_you_layout.json"
DOUBLE_TAP_PROMPT = "Style This/double_tap.json"


def _runtime_first_prompt(item_label: str) -> str:
    return (
        "RUNTIME OVERRIDE — IMAGE 1 is the locked How Would You Layout "
        "reference and IMAGE 2 is the finished blended product/interior photo. "
        "Create exactly one 9:16 portrait image. Replace every item-name and "
        f"item-type placeholder with '{item_label}'. Never leave a placeholder "
        "visible. Preserve the actual blended scene as "
        "the full-frame photographic background and preserve the reference's "
        "HomeCartel branding, typography, placement, and hierarchy."
    )


DOUBLE_TAP_RUNTIME_PROMPT = (
    "RUNTIME OVERRIDE — IMAGE 1 is the locked Double Tap layout reference "
    "and IMAGE 2 is the finished blended product/interior photo. Create "
    "exactly one 9:16 portrait image. Replace the literal '[Item Color]' "
    "placeholder with a fresh, concise, visually lively color name derived "
    "only from IMAGE 2. Display the color name as plain text WITHOUT square "
    "brackets. Choose a more colorful but harmonious pill color from "
    "that same photo and automatically use readable contrasting text. Never "
    "leave '[Item Color]' visible. Never render square brackets around the "
    "color name. Preserve the heart, headline, HomeCartel "
    "branding, typography, placement, and hierarchy from the layout."
)


def _with_runtime_override(prompt: str, runtime: str) -> str:
    """Keep runtime values at the front when a fixed JSON prompt is long."""
    available = max(MAX_PROMPT_LENGTH - len(runtime) - 1, 0)
    return f"{runtime}\n{prompt[:available]}"


class StyleThisStoryWorkflow(BaseWorkflow):
    """Blend four Airtable product/room pairs, then create four story cards."""

    requirements = (
        AssetRequirement(HOW_WOULD_YOU_PROMPT, "json"),
        AssetRequirement(DOUBLE_TAP_PROMPT, "json"),
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=8)
    aspect_ratio = "9:16"
    final_filenames = FINAL_FILENAMES
    final_aspect_ratios = ("9:16", "9:16", "9:16", "9:16")
    attachment_fields = (
        BLENDED_FIELD,
        DOUBLE_TAP_CONVERTED_FIELD,
    )
    schema_fields = {
        **{
            field: "multipleAttachments"
            for field in (
                *INTERIOR_FIELDS,
                FURNITURE_FIELD,
                HOW_WOULD_YOU_LAYOUT_FIELD,
                DOUBLE_TAP_LAYOUT_FIELD,
                BLENDED_FIELD,
                DOUBLE_TAP_CONVERTED_FIELD,
            )
        },
        **{field: "multilineText" for field in PROMPT_FIELDS},
        "Product Type": "singleLineText",
    }
    required_columns = (
        *INTERIOR_FIELDS,
        FURNITURE_FIELD,
        *PROMPT_FIELDS,
        "Item Name",
        "Product Type",
        HOW_WOULD_YOU_LAYOUT_FIELD,
        DOUBLE_TAP_LAYOUT_FIELD,
    )

    @classmethod
    def estimate_for(cls, reservation) -> CallEstimate:
        if len(reservation.anchor.fields.get(BLENDED_FIELD) or []) == 4:
            return CallEstimate(kie=4)
        return cls.estimate

    def _create_and_attach_blends(self) -> list[LocalImage]:
        interiors = [
            self.record_attachment(field, f"style_interior{index}")
            for index, field in enumerate(INTERIOR_FIELDS, start=1)
        ]
        product = self.record_attachment(
            FURNITURE_FIELD,
            "style_furniture",
        )
        prompts = [self.record_prompt(field) for field in PROMPT_FIELDS]

        def create(values) -> LocalImage:
            filename, interior, product, prompt = values
            return self.nano_image(
                filename,
                prompt,
                [interior, product],
                aspect_ratio=self.aspect_ratio,
                model=NANO_BANANA_PRO,
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            blends = list(
                executor.map(
                    create,
                    zip(
                        BLENDED_FILENAMES,
                        interiors,
                        [product] * len(BLENDED_FILENAMES),
                        prompts,
                    ),
                )
            )

        self.attach_exact(BLENDED_FIELD, blends)
        return self.refreshed_record_attachments(
            BLENDED_FIELD,
            "style_this_blended_input",
            expected_count=4,
        )

    def _item_label(self) -> str:
        fields = self.ctx.anchor.fields
        item_name = str(
            fields.get("Item Name") or self.ctx.anchor.item_name or ""
        ).strip()
        product_type = str(
            fields.get("Product Type") or self.ctx.anchor.product_type or ""
        ).strip()
        if "|" in item_name:
            left, right = (part.strip() for part in item_name.split("|", 1))
            item_name = left
            product_type = product_type or right
        return " | ".join(part for part in (item_name, product_type) if part)

    def _create_story_cards(
        self,
        blends: list[LocalImage],
    ) -> list[LocalImage]:
        how_layout = self.record_attachment(
            HOW_WOULD_YOU_LAYOUT_FIELD,
            "how_would_you_layout",
        )
        double_tap_layout = self.record_attachment(
            DOUBLE_TAP_LAYOUT_FIELD,
            "double_tap_layout",
        )

        how_prompt = _with_runtime_override(
            self.prompt(HOW_WOULD_YOU_PROMPT).replace(
                "[Item Name & Item Type]",
                self._item_label(),
            ),
            _runtime_first_prompt(self._item_label()),
        )
        first = self.nano_image(
            FINAL_FILENAMES[0],
            how_prompt,
            [how_layout, blends[0]],
            aspect_ratio=self.aspect_ratio,
            model=NANO_BANANA_PRO,
        )

        double_prompt = _with_runtime_override(
            self.prompt(DOUBLE_TAP_PROMPT),
            DOUBLE_TAP_RUNTIME_PROMPT,
        )

        def create(values) -> LocalImage:
            filename, blend = values
            return self.nano_image(
                filename,
                double_prompt,
                [double_tap_layout, blend],
                aspect_ratio=self.aspect_ratio,
                model=NANO_BANANA_PRO,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            converted = list(
                executor.map(
                    create,
                    zip(FINAL_FILENAMES[1:], blends[1:]),
                )
            )

        self.attach_exact(DOUBLE_TAP_CONVERTED_FIELD, converted)
        return [first, *converted]

    def execute(self):
        existing_blends = self.ctx.anchor.fields.get(BLENDED_FIELD) or []
        if len(existing_blends) == 4:
            blends = self.refreshed_record_attachments(
                BLENDED_FIELD,
                "style_this_blended_input",
                expected_count=4,
            )
        else:
            blends = self._create_and_attach_blends()

        finals = self._create_story_cards(blends)
        self.attach_exact(self.ctx.definition.final_field, finals)
        return self.success(finals)
