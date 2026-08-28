from __future__ import annotations

from pathlib import Path
from typing import List

from ..errors import AssetValidationError
from ..models import Attachment, AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


class ProductShowcaseFeedWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement("thumbnail_plat.jpg"),
        AssetRequirement("product-showcase-feed_thubmanail.json", "json"),
        AssetRequirement("solo_plat.jpg"),
        AssetRequirement("product-showcase-feed-solo.json", "json"),
    )
    estimate = CallEstimate(kie=4)
    aspect_ratio = "4:5"
    final_filenames = (
        "table_lamps_thumbnail.jpg",
        "table_lamp_solo1.jpg",
        "table_lamp_solo2.jpg",
        "table_lamp_solo3.jpg",
    )
    final_aspect_ratios = ("4:5", "4:5", "4:5", "4:5")
    attachment_fields = (
        "FEED - Product Showcase Feed",
        "FEED - Product Showcase Feed (4)",
    )

    def get_slot_product_images(self) -> List[LocalImage]:
        anchor = self.ctx.anchor
        images: List[LocalImage] = []
        for slot in range(3):
            slot_idx = slot + 1
            field_candidates = [
                f"Furniture Item{slot_idx}",
                f"Furniture Item {slot_idx}",
                f"Furniture Item{slot_idx if slot > 0 else ''}",
                f"Furniture Item {slot_idx if slot > 0 else ''}".strip(),
            ]
            attachments = []
            for fc in field_candidates:
                if anchor.fields.get(fc):
                    attachments = anchor.fields.get(fc)
                    break

            if attachments and hasattr(self.ctx.airtable, "download_attachment"):
                att = Attachment.from_airtable(attachments[0])
                ext = Path(att.filename).suffix or ".jpg"
                filename = f"source_product_slot_{slot + 1}_{anchor.record_id}{ext}"
                destination = self.ctx.workdir / filename
                if destination.is_file():
                    try:
                        self._verify_dynamic_image(destination)
                        images.append(LocalImage(destination, filename, att.content_type or "image/jpeg"))
                        continue
                    except AssetValidationError:
                        destination.unlink(missing_ok=True)
                downloaded = self.ctx.airtable.download_attachment(att, destination)
                self._verify_dynamic_image(downloaded.path)
                images.append(downloaded)
            elif slot == 0 or not images:
                images.append(self.product_image())
            else:
                images.append(images[0])

        while len(images) < 3 and images:
            images.append(images[0])

        return images[:3]

    def get_layout_image(self, field_name: str, default_asset_name: str) -> LocalImage:
        anchor = self.ctx.anchor
        candidates = [field_name, "Multiple Platform", "Thumbnail Platform", "Multiple Platform Layout"]
        attachments = []
        resolved_name = field_name
        for c in candidates:
            if anchor.fields.get(c):
                attachments = anchor.fields.get(c)
                resolved_name = c
                break

        if attachments:
            att = Attachment.from_airtable(attachments[0])
            ext = Path(att.filename).suffix or ".jpg"
            safe_field = resolved_name.lower().replace(" ", "_")
            filename = f"layout_{safe_field}_{anchor.record_id}{ext}"
            destination = self.ctx.workdir / filename
            if destination.is_file():
                try:
                    self._verify_dynamic_image(destination)
                    return LocalImage(destination, filename, att.content_type or "image/jpeg")
                except AssetValidationError:
                    destination.unlink(missing_ok=True)
            downloaded = self.ctx.airtable.download_attachment(att, destination)
            self._verify_dynamic_image(downloaded.path)
            return downloaded
        return LocalImage(self.asset_path(default_asset_name), default_asset_name)

    def get_solo_layout_image(self, slot: int) -> LocalImage:
        anchor = self.ctx.anchor
        slot_idx = slot + 1
        candidates = [
            f"Solo Thumbnail{slot_idx if slot > 0 else ''}",
            f"Solo Platform{slot_idx if slot > 0 else ''}",
            f"Solo Thumbnail {slot_idx}",
            f"Solo Platform {slot_idx}",
            "Solo Thumbnail",
            "Solo Platform",
        ]
        attachments = []
        resolved_name = "solo_platform"
        for c in candidates:
            if anchor.fields.get(c):
                attachments = anchor.fields.get(c)
                resolved_name = c
                break

        if not attachments:
            main_attachments = anchor.fields.get("Solo Thumbnail") or anchor.fields.get("Solo Platform") or []
            if len(main_attachments) > slot:
                attachments = [main_attachments[slot]]
            elif main_attachments:
                attachments = [main_attachments[0]]

        if attachments:
            att = Attachment.from_airtable(attachments[0])
            ext = Path(att.filename).suffix or ".jpg"
            safe_field = resolved_name.lower().replace(" ", "_")
            filename = f"layout_{safe_field}_slot_{slot + 1}_{anchor.record_id}{ext}"
            destination = self.ctx.workdir / filename
            if destination.is_file():
                try:
                    self._verify_dynamic_image(destination)
                    return LocalImage(destination, filename, att.content_type or "image/jpeg")
                except AssetValidationError:
                    destination.unlink(missing_ok=True)
            downloaded = self.ctx.airtable.download_attachment(att, destination)
            self._verify_dynamic_image(downloaded.path)
            return downloaded
        return LocalImage(self.asset_path("solo_plat.jpg"), "solo_plat.jpg")

    def execute(self):
        anchor = self.ctx.anchor
        product_images = self.get_slot_product_images()
        if not product_images:
            raise AssetValidationError(
                f"No product images attached in Furniture Item fields for {anchor.record_id}"
            )

        thumbnail_layout = self.get_layout_image("Multiple Platform", "thumbnail_plat.jpg")

        # 1. Generate Thumbnail Slide using thumbnail_plat.jpg + 3 product images
        thumbnail_prompt = self.prompt("product-showcase-feed_thubmanail.json")
        if len(thumbnail_prompt) > 5000:
            thumbnail_prompt = thumbnail_prompt[:5000]

        thumbnail = self.nano_image(
            "table_lamps_thumbnail.jpg",
            thumbnail_prompt,
            [thumbnail_layout, product_images[0], product_images[1], product_images[2]],
            aspect_ratio="4:5",
        )

        # 2. Generate Solo Slides for products 1 to 3
        solo_slides: List[LocalImage] = []
        for i in range(1, 4):
            solo_layout = self.get_solo_layout_image(i - 1)
            prod_img = product_images[i - 1]
            
            name_candidates = [
                f"Item Name{i}",
                f"Item Name {i}",
                f"Item Name{'' if i == 1 else i}",
                f"Item Name {'' if i == 1 else i}".strip(),
            ]
            item_name = ""
            for nc in name_candidates:
                val = anchor.fields.get(nc)
                if val:
                    item_name = str(val).strip()
                    break
            if not item_name and i == 1:
                item_name = str(anchor.item_name or "").strip()

            prompt = self.prompt("product-showcase-feed-solo.json")
            if item_name:
                prompt = prompt.replace("[INPUT_ITEM_NAME_HERE]", item_name)
                prompt = prompt.replace("[Item Name]", item_name)

            if len(prompt) > 5000:
                prompt = prompt[:5000]

            solo_slide = self.nano_image(
                f"table_lamp_solo{i}.jpg",
                prompt,
                [solo_layout, prod_img],
                aspect_ratio="4:5",
            )
            solo_slides.append(solo_slide)

        finals = [thumbnail, *solo_slides]
        
        target_field = self.ctx.definition.final_field
        if "FEED - Product Showcase Feed" in anchor.fields:
            target_field = "FEED - Product Showcase Feed"
        elif "FEED - Product Showcase Feed (4)" in anchor.fields:
            target_field = "FEED - Product Showcase Feed (4)"

        self.attach_exact(target_field, finals)
        return self.success(finals)
