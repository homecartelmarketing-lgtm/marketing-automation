from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


NANO_BANANA_PRO = "nano-banana-pro"
BLENDED_FIELD = "Tips and Edu Blended"
TAGGED_BLENDED_FIELD = "Tips and Edu Blended Attach Item Name"
LAYOUT_FIELDS = (
    "Tips and Edu Layout1",
    "Tips and Edu Layout2",
    "Tips and Edu Layout3",
)
PROMPT_FIELDS = ("Prompt1", "Prompt2", "Prompt3")
TIPS_FIELDS = ("Tips 1", "Tips 2", "Tips 3")
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
LAYOUT_ASSET_PATHS = (
    "assets/tipsandedufeed1layout.jpg",
    "assets/tipsandedufeed2layout.jpg",
    "assets/tipsandedufeed3layout.jpg",
)
LAYOUT_ASSET_FILENAMES = (
    "tipsandedufeed1layout.jpg",
    "tipsandedufeed2layout.jpg",
    "tipsandedufeed3layout.jpg",
)


class TipsEducationalFeedWorkflow(BaseWorkflow):
    """Blend three products into rooms, then apply three authored layouts."""

    requirements = tuple(
        AssetRequirement(path, "json") for path in LAYOUT_PROMPTS
    ) + tuple(
        AssetRequirement(path, "image", aspect_ratio="4:5") for path in LAYOUT_ASSET_PATHS
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=6)
    aspect_ratio = "4:5"
    final_filenames = FINAL_FILENAMES
    final_aspect_ratios = ("4:5", "4:5", "4:5")
    attachment_fields = (BLENDED_FIELD, TAGGED_BLENDED_FIELD)
    schema_fields = {
        **{
            field: "multipleAttachments"
            for field in (
                *INTERIOR_FIELDS,
                *FURNITURE_FIELDS,
                *LAYOUT_FIELDS,
                BLENDED_FIELD,
                TAGGED_BLENDED_FIELD,
            )
        },
        **{field: "multilineText" for field in (*PROMPT_FIELDS, *TIPS_FIELDS)},
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
            raw_blends = list(
                executor.map(
                    create,
                    zip(BLENDED_FILENAMES, interiors, products, prompts),
                )
            )

        # Upload the untagged original blends to the raw field
        self.attach_exact(BLENDED_FIELD, raw_blends)
        
        return self.refreshed_record_attachments(
            BLENDED_FIELD,
            "tips_blended_input",
            expected_count=3,
        )

    def _tag_and_attach_blends(self, raw_blends: list[LocalImage]) -> list[LocalImage]:
        # Apply zero-cost YOLO-World item name tagging locally to each blend
        from ..item_tagger import tag_blended_image
        from ..fields import item_name_field, product_type_field
        
        tagged_blends = []
        anchor = self.ctx.anchor
        category_code = str(self.ctx.definition.table_code or "chandeliers")
        
        for i, blend in enumerate(raw_blends):
            item_name = str(anchor.fields.get(item_name_field(i)) or "")
            product_type = str(anchor.fields.get(product_type_field(i)) or "")
            
            print(f"\n [ITEM TAGGING] Stamping item name ('{item_name}') onto Tips Edu Feed Blend {i+1}...")
            try:
                tagged_img, _ = tag_blended_image(
                    image_input=blend.path,
                    item_name=item_name,
                    product_type=product_type,
                    category=category_code,
                )
                if tagged_img:
                    tagged_path = blend.path.with_name(f"tagged_{blend.filename}")
                    tagged_img.save(tagged_path, quality=92)
                    tagged_blends.append(LocalImage(tagged_path, blend.filename, blend.mime_type))
                else:
                    tagged_blends.append(blend)
            except Exception as e:
                print(f"  [WARN] Failed to tag blend {i+1}: {e}")
                tagged_blends.append(blend)

        combined_tagged_carousel = []
        thumbnail_img = None
        if anchor.fields.get("Thumbnail"):
            thumbnail_img = self.record_attachment("Thumbnail", "tips_exterior")
            combined_tagged_carousel.append(thumbnail_img)
            
        combined_tagged_carousel.extend(tagged_blends)

        self.attach_exact(TAGGED_BLENDED_FIELD, combined_tagged_carousel)
        
        uploaded_tagged = self.refreshed_record_attachments(
            TAGGED_BLENDED_FIELD,
            "tips_tagged_input",
            expected_count=len(combined_tagged_carousel),
        )
        
        # Layouts only apply to the 3 interior blends, so return the last 3 items
        return uploaded_tagged[-3:]

    def _ensure_layout_attachments(self) -> None:
        anchor = self.ctx.anchor
        needs_refresh = False
        for field, asset_path_str, filename in zip(
            LAYOUT_FIELDS, LAYOUT_ASSET_PATHS, LAYOUT_ASSET_FILENAMES
        ):
            existing = anchor.fields.get(field) or []
            if not existing:
                path = self.asset_path(asset_path_str)
                image = LocalImage(path, filename, "image/jpeg")
                try:
                    self.ctx.airtable.upload_attachment(anchor.record_id, field, image)
                    needs_refresh = True
                except Exception as err:
                    print(f"[WARN] Could not upload layout template {filename} to {field}: {err}")
        if needs_refresh:
            try:
                refreshed = self.ctx.airtable.get_record(anchor.record_id)
                anchor.fields.update(refreshed.get("fields", {}))
            except Exception as err:
                print(f"[WARN] Could not refresh record after uploading layouts: {err}")

    def _apply_layouts(
        self,
        blends: list[LocalImage],
    ) -> list[LocalImage]:
        self._ensure_layout_attachments()
        anchor = self.ctx.anchor
        layouts = []
        for index, (field, asset_path_str, filename) in enumerate(
            zip(LAYOUT_FIELDS, LAYOUT_ASSET_PATHS, LAYOUT_ASSET_FILENAMES),
            start=1,
        ):
            if anchor.fields.get(field):
                layouts.append(self.record_attachment(field, f"tips_layout{index}"))
            else:
                layouts.append(
                    LocalImage(self.asset_path(asset_path_str), filename, "image/jpeg")
                )
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
        existing_tagged = self.ctx.anchor.fields.get(TAGGED_BLENDED_FIELD) or []
        existing_raw = self.ctx.anchor.fields.get(BLENDED_FIELD) or []
        
        if len(existing_tagged) >= 3:
            uploaded_tagged = self.refreshed_record_attachments(
                TAGGED_BLENDED_FIELD,
                "tips_tagged_input",
                expected_count=len(existing_tagged),
            )
            # The last 3 are always the interior blends (even if Thumbnail is prepended)
            blends = uploaded_tagged[-3:]
        else:
            if len(existing_raw) == 3:
                raw_blends = self.refreshed_record_attachments(
                    BLENDED_FIELD,
                    "tips_blended_input",
                    expected_count=3,
                )
            else:
                raw_blends = self._create_and_attach_blends()
                
            blends = self._tag_and_attach_blends(raw_blends)

        finals = self._apply_layouts(blends)
        self.attach_exact(self.ctx.definition.final_field, finals)
        return self.success(finals)
