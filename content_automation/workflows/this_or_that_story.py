from __future__ import annotations

import json

from ..assets import MAX_PROMPT_LENGTH
from ..errors import AssetValidationError
from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


class ThisOrThatStoryWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement("this_or_that_json_prompt.json", "json"),
        AssetRequirement("thisorthatlayout.jpg", "image", aspect_ratio="9:16"),
    )
    estimate = CallEstimate(krea=0, qwen=0, kie=0, fal=1)
    aspect_ratio = "9:16"
    final_filenames = ("this_or_that.jpg",)
    final_aspect_ratios = ("9:16",)
    attachment_fields = (
        "This or That Converted",
        "STORY - This or That (1)",
        "Story This or That (1)",
    )
    schema_fields = {
        "This or That Layout": "multipleAttachments",
    }
    required_columns = (
        "Status",
        "This or That Layout",
    )

    def execute(self):
        layout = None
        try:
            layout = self.record_attachment(
                "This or That Layout",
                "source_this_or_that_layout",
            )
        except (AssetValidationError, Exception):
            layout = None

        if layout is None:
            layout_path = self.asset_path("thisorthatlayout.jpg")
            layout = LocalImage(
                layout_path,
                "source_this_or_that_layout.jpg",
                "image/jpeg",
            )
            try:
                if hasattr(self.ctx.airtable, "upload_attachment"):
                    self.ctx.airtable.upload_attachment(
                        self.ctx.anchor.record_id,
                        "This or That Layout",
                        LocalImage(layout_path, "thisorthatlayout.jpg", "image/jpeg"),
                    )
            except Exception:
                pass

        top_item = self._get_attachment(("Furniture Item1", "Furniture Item"), "source_top_item", slot=1)
        bottom_item = self._get_attachment(("Furniture Item2",), "source_bottom_item", slot=2)

        top_name = self._required_text("Item Name1", "Item Name")
        bottom_name = self._required_text("Item Name2")

        top_type = self._get_text(("Product Type1", "Product Type"), fallback=self.ctx.anchor.product_type or "Lighting Fixture")
        bottom_type = self._get_text(("Product Type2",), fallback=self._partner_product_type(2) or "Lighting Fixture")

        if "|" in top_name:
            parts = [p.strip() for p in top_name.split("|", 1)]
            top_name = parts[0]
            if len(parts) > 1 and parts[1]:
                top_type = parts[1]

        if "|" in bottom_name:
            parts = [p.strip() for p in bottom_name.split("|", 1)]
            bottom_name = parts[0]
            if len(parts) > 1 and parts[1]:
                bottom_type = parts[1]

        values = {
            "top_item_name": top_name,
            "top_item_type": top_type,
            "bottom_item_name": bottom_name,
            "bottom_item_type": bottom_type,
        }
        prompt = self._runtime_prompt(values)
        final = self.nano_image(
            "this_or_that.jpg",
            prompt,
            [
                layout,
                top_item,
                bottom_item,
            ],
            aspect_ratio="9:16",
            model="fal-ai/nano-banana-pro/edit",
        )

        has_schema = hasattr(self.ctx.airtable, "schema") and hasattr(self.ctx.airtable.schema, "__call__")
        schema_keys = list(self.ctx.airtable.schema().keys()) if has_schema else []
        final_field = None
        if self.ctx.definition.final_field and (not schema_keys or self.ctx.definition.final_field in schema_keys):
            final_field = self.ctx.definition.final_field
        elif "This or That Converted" in schema_keys:
            final_field = "This or That Converted"
        elif "STORY - This or That (1)" in schema_keys:
            final_field = "STORY - This or That (1)"
        elif "Story This or That (1)" in schema_keys:
            final_field = "Story This or That (1)"
        else:
            for key in schema_keys:
                if "this or that" in key.lower() and ("story" in key.lower() or "converted" in key.lower()):
                    final_field = key
                    break
        if not final_field:
            final_field = self.ctx.definition.final_field or "This or That Converted"

        self.attach_exact(final_field, [final])
        return self.success([final])

    def _get_attachment(self, field_names: tuple[str, ...], name: str, slot: int = 1):
        anchor = self.ctx.anchor
        for field in field_names:
            if anchor.fields.get(field):
                return self.record_attachment(field, name)
        if slot == 2 and self.ctx.reservation.partners:
            partner = self.ctx.reservation.partners[0]
            return self.product_image(partner)
        return self.record_attachment(field_names[0], name)

    def _get_text(self, field_names: tuple[str, ...], fallback: str = "") -> str:
        anchor = self.ctx.anchor
        for field in field_names:
            val = str(anchor.fields.get(field) or "").strip()
            if val:
                return val
        return fallback

    def _partner_product_type(self, slot: int) -> str:
        if slot == 2 and self.ctx.reservation.partners:
            return self.ctx.reservation.partners[0].product_type
        return ""

    def _required_text(self, *field_names: str) -> str:
        anchor = self.ctx.anchor
        for field in field_names:
            val = str(anchor.fields.get(field) or "").strip()
            if val:
                return val
        if self.ctx.reservation.partners and len(field_names) == 1 and field_names[0] == "Item Name2":
            partner = self.ctx.reservation.partners[0]
            if partner.item_name:
                return partner.item_name
        raise AssetValidationError(
            f"Record {anchor.record_id} has an empty "
            f"{field_names[0]} field"
        )

    def _runtime_prompt(self, values: dict[str, str]) -> str:
        """Insert exact Airtable labels into the complete supplied JSON."""
        try:
            data = json.loads(self._prompt_template())
            manual = data["manual_inputs"]
            manual["top_item"]["item_name"] = values["top_item_name"]
            manual["top_item"]["item_type"] = values["top_item_type"]
            manual["bottom_item"]["item_name"] = values["bottom_item_name"]
            manual["bottom_item"]["item_type"] = values["bottom_item_type"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise AssetValidationError(
                f"Invalid This or That runtime prompt structure: {error}"
            ) from error
        prompt = json.dumps(data, ensure_ascii=False)
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise AssetValidationError(
                f"This or That prompt is {len(prompt)} characters; "
                f"maximum is {MAX_PROMPT_LENGTH}"
            )
        return prompt

    def _prompt_template(self) -> str:
        """Read the full prompt without the generic 4,900-character cap."""
        path = self.asset_path("this_or_that_json_prompt.json")
        try:
            return path.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise AssetValidationError(
                f"Unreadable This or That prompt asset: {path}"
            ) from error
