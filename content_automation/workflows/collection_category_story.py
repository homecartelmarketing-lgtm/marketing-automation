from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..assets import MAX_PROMPT_LENGTH
from ..errors import AssetValidationError
from ..models import AssetRequirement, Attachment, CallEstimate, LocalImage
from ..overlay import HOMECARTEL_STORY_LOGO_BOX, create_three_image_story_grid
from .base import BaseWorkflow

import os

COLLECTION_STORY_MODEL = os.getenv("COLLECTION_STORY_MODEL", "fal-ai/nano-banana-pro/edit")
COLLECTION_STORY_PROMPT_LIMIT = 5000


class CollectionCategoryStoryWorkflow(BaseWorkflow):
    requirements = ()
    estimate = CallEstimate(krea=0, qwen=0, kie=0, fal=3)
    aspect_ratio = "9:16"
    final_filenames = ("collection_category_story.jpg",)
    final_aspect_ratios = ("9:16",)
    attachment_fields = (
        "Story Collection Categ Blended",
        "Collection Category Blended",
        "Collection Category Blended Image1",
        "Collection Category Blended Image2",
        "Collection Category Blended Image3",
        "STORY - Collection Category (1)",
        "Collection Category Converted",
    )
    required_columns = (
        "Status",
        "Interior",
        "Prompt1",
    )

    def execute(self):
        has_schema = hasattr(self.ctx.airtable, "schema") and hasattr(self.ctx.airtable.schema, "__call__")
        schema_keys = list(self.ctx.airtable.schema().keys()) if has_schema else []
        all_keys = set(schema_keys) | set(self.ctx.anchor.fields.keys())

        existing_blends = self._get_existing_blends()
        if len(existing_blends) == 3:
            blends = existing_blends
        else:
            # 1. Gather inputs for the 3 slots:
            slots_data = []
            for i in range(1, 4):
                interior = self._get_slot_interior(i)
                furniture = self._get_slot_furniture(i)
                prompt_str = self._get_slot_prompt(i)
                slots_data.append((interior, furniture, prompt_str))

            # 2. Step 1: Generate 3 blended photos using fal-ai/nano-banana-pro/edit
            # in 16:9 ratio.
            def blend_job(args):
                index, (interior, furniture, prompt_str) = args
                return self.nano_image(
                    f"collection_story_blended{index}.jpg",
                    prompt_str,
                    [interior, furniture],
                    aspect_ratio="16:9",
                    model=COLLECTION_STORY_MODEL,
                )

            with ThreadPoolExecutor(max_workers=3) as executor:
                blends = list(executor.map(blend_job, enumerate(slots_data, start=1)))

            # 3. Attach the 3 blended photos to blended field(s)
            has_individual_blended = any(
                f"Collection Category Blended Image{i}" in all_keys for i in (1, 2, 3)
            )
            if has_individual_blended:
                for idx, blend_img in enumerate(blends, start=1):
                    field_name = f"Collection Category Blended Image{idx}"
                    if field_name in all_keys:
                        self.attach_exact(field_name, [blend_img])
            else:
                blended_field = (
                    "Collection Category Blended"
                    if "Collection Category Blended" in all_keys
                    else "Story Collection Categ Blended"
                )
                self.attach_exact(blended_field, blends)

        # 4. Step 2: Generate the final 9:16 auto-grid story from Collection Category Blended Image 1, 2, 3 + Logo + Poppins Bold Item Names
        # (Local PIL generation, no Fal API call)
        item_names = [self._get_slot_item_name(i) for i in range(1, 4)]
        logo_image = self._get_logo_image()
        final_dest = self.ctx.workdir / "collection_category_story.jpg"
        create_three_image_story_grid(
            [b.path for b in blends],
            destination=final_dest,
            logo_path=logo_image.path if logo_image else None,
            logo_box=HOMECARTEL_STORY_LOGO_BOX,
            item_names=item_names,
        )
        final = LocalImage(final_dest, "collection_category_story.jpg", "image/jpeg")

        # 5. Attach final photo
        final_field = (
            self.ctx.definition.final_field
            if self.ctx.definition.final_field and self.ctx.definition.final_field in schema_keys
            else (
                "Collection Category Converted"
                if "Collection Category Converted" in all_keys
                else (self.ctx.definition.final_field or "STORY - Collection Category (1)")
            )
        )
        self.attach_exact(final_field, [final])

        return self.success([final])

    def _get_logo_image(self) -> LocalImage | None:
        anchor = self.ctx.anchor
        for field in ("Logo", "Brand Logo", "Watermark", "Logo Image"):
            if anchor.fields.get(field):
                return self.record_attachment(field, "source_logo")
        return None

    def _get_existing_blends(self) -> list[LocalImage]:
        anchor = self.ctx.anchor
        indiv_fields = [
            "Collection Category Blended Image1",
            "Collection Category Blended Image2",
            "Collection Category Blended Image3",
        ]
        if all(anchor.fields.get(f) for f in indiv_fields):
            return [
                self.record_attachment(f, f"blended_input_{i}")
                for i, f in enumerate(indiv_fields, start=1)
            ]

        for array_field in ("Collection Category Blended", "Story Collection Categ Blended"):
            attachments = anchor.fields.get(array_field) or []
            if len(attachments) >= 3:
                res = []
                for idx in range(3):
                    att = Attachment.from_airtable(attachments[idx])
                    dest = self.ctx.workdir / f"existing_blend_{idx+1}_{att.filename}"
                    if dest.is_file():
                        res.append(LocalImage(dest, dest.name, att.content_type or "image/jpeg"))
                    else:
                        res.append(self.ctx.airtable.download_attachment(att, dest))
                return res
        return []

    def _get_slot_item_name(self, slot_num: int) -> str:
        anchor = self.ctx.anchor
        candidates = [
            f"Item Name{slot_num}",
            f"Item Name copy{slot_num}",
        ]
        if slot_num == 1:
            candidates.extend(["Item Name", "Item Name copy"])
        for field in candidates:
            val = anchor.fields.get(field)
            if val:
                return str(val).strip()
        if self.ctx.reservation.partners and slot_num > 1:
            partner_idx = slot_num - 2
            if partner_idx < len(self.ctx.reservation.partners):
                partner = self.ctx.reservation.partners[partner_idx]
                if partner.item_name:
                    return partner.item_name
        return anchor.item_name or f"Item {slot_num}"

    def _get_slot_interior(self, slot_num: int) -> LocalImage:
        anchor = self.ctx.anchor
        field_names = [f"Interior{slot_num}"]
        if slot_num == 1:
            field_names.append("Interior")
        if slot_num == 3:
            field_names.append("Interiro3")
        for field in field_names:
            if anchor.fields.get(field):
                return self.record_attachment(field, f"source_interior{slot_num}")
        if self.ctx.reservation.partners and slot_num > 1:
            partner_idx = slot_num - 2
            if partner_idx < len(self.ctx.reservation.partners):
                partner = self.ctx.reservation.partners[partner_idx]
                if partner.fields.get("Interior"):
                    attachment = Attachment.from_airtable(partner.fields["Interior"][0])
                    destination = (
                        self.ctx.workdir
                        / f"source_interior{slot_num}_{partner.record_id}.jpg"
                    )
                    if destination.is_file():
                        return LocalImage(
                            destination,
                            destination.name,
                            attachment.content_type or "image/jpeg",
                        )
                    return self.ctx.airtable.download_attachment(
                        attachment, destination
                    )
        primary_field = f"Interior{slot_num}" if slot_num > 1 else "Interior"
        return self.record_attachment(primary_field, f"source_interior{slot_num}")

    def _get_slot_furniture(self, slot_num: int) -> LocalImage:
        anchor = self.ctx.anchor
        field_names = [
            f"Furniture Item copy{slot_num}",
            f"Furniture Item{slot_num}",
        ]
        if slot_num == 1:
            field_names.extend(["Furniture Item copy", "Furniture Item"])
        for field in field_names:
            if anchor.fields.get(field):
                return self.record_attachment(field, f"source_furniture{slot_num}")
        if self.ctx.reservation.partners and slot_num > 1:
            partner_idx = slot_num - 2
            if partner_idx < len(self.ctx.reservation.partners):
                partner = self.ctx.reservation.partners[partner_idx]
                return self.product_image(partner)
        primary_field = (
            f"Furniture Item{slot_num}" if slot_num > 1 else "Furniture Item"
        )
        return self.record_attachment(primary_field, f"source_furniture{slot_num}")

    def _get_slot_prompt(self, slot_num: int) -> str:
        anchor = self.ctx.anchor
        field_names = (
            ["Prompt1", "Prompt"]
            if slot_num == 1
            else [f"Prompt{slot_num}", "Prompt1", "Prompt"]
        )
        for field in field_names:
            val = str(anchor.fields.get(field) or "").strip()
            if val:
                return val[:MAX_PROMPT_LENGTH]
        if self.ctx.reservation.partners and slot_num > 1:
            partner_idx = slot_num - 2
            if partner_idx < len(self.ctx.reservation.partners):
                partner = self.ctx.reservation.partners[partner_idx]
                for field in (f"Prompt{slot_num}", "Prompt1", "Prompt"):
                    val = str(partner.fields.get(field) or "").strip()
                    if val:
                        return val[:MAX_PROMPT_LENGTH]
        primary_field = f"Prompt{slot_num}" if slot_num > 1 else "Prompt1"
        fallback = "Prompt1" if "Prompt1" in anchor.fields else "Prompt"
        return self.record_prompt(fallback)

    def _get_layout_image(self) -> LocalImage:
        anchor = self.ctx.anchor
        for field_name in ("Collection Categ Story Layout", "Collection Category Layout"):
            if anchor.fields.get(field_name):
                return self.record_attachment(field_name, "source_layout")
        return self.record_attachment("Collection Category Layout", "source_layout")

    def _build_final_prompt(self, metadata: list[dict[str, str]]) -> str:
        prompt_text = self.prompt("Collection Categ/collection-categ.json")
        replacements = {
            "[Item Name]": metadata[0]["item_name"],
            "[Product Type]": metadata[0]["product_type"],
            "[Item Name2]": metadata[1]["item_name"],
            "[Product Type2]": metadata[1]["product_type"],
            "[Item Name3]": metadata[2]["item_name"],
            "[Product Type3]": metadata[2]["product_type"],
        }
        for placeholder, value in replacements.items():
            prompt_text = prompt_text.replace(placeholder, value)

        runtime_text = json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        final_prompt = f"{prompt_text}\nRUNTIME_PRODUCT_TEXT={runtime_text}"
        if len(final_prompt) > COLLECTION_STORY_PROMPT_LIMIT:
            raise AssetValidationError(
                "Collection Category Story prompt is "
                f"{len(final_prompt)} characters; maximum is "
                f"{COLLECTION_STORY_PROMPT_LIMIT}. Shorten the Item Name or "
                "Product Type values before generation."
            )
        return final_prompt

    def _build_metadata(self) -> list[dict[str, str]]:
        anchor = self.ctx.anchor
        res = []
        for i in range(1, 4):
            suffix = "" if i == 1 else str(i)
            item_name = str(
                anchor.fields.get(f"Item Name{i}")
                or anchor.fields.get(f"Item Name{suffix}")
                or (anchor.item_name if i == 1 else "")
                or ""
            ).strip()
            prod_type = str(
                anchor.fields.get(f"Product Type{i}")
                or anchor.fields.get(f"Product Type{suffix}")
                or (anchor.product_type if i == 1 else "")
                or ""
            ).strip()
            if not item_name and self.ctx.reservation.partners and i > 1:
                partner_idx = i - 2
                if partner_idx < len(self.ctx.reservation.partners):
                    partner = self.ctx.reservation.partners[partner_idx]
                    item_name = partner.item_name
                    prod_type = partner.product_type
            res.append({"item_name": item_name, "product_type": prod_type})
        return res
