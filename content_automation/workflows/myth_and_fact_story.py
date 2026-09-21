from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageOps

from ..models import AssetRequirement, CallEstimate, LocalImage
from .base import BaseWorkflow


def convert_outro_layout_slide(
    background_path: Path | str,
    layout_path: Path | str,
    output_path: Path | str,
    threshold: int = 35,
) -> Path:
    """Create Outro Slide (Slide 4) by overlaying Outro Layout onto background photo locally via PIL."""
    base_img = Image.open(background_path).convert("RGB")
    if base_img.size != (1080, 1920):
        base_img = ImageOps.fit(base_img, (1080, 1920), method=Image.LANCZOS, centering=(0.5, 0.5))
    base_rgba = base_img.convert("RGBA")

    layout_img = Image.open(layout_path).convert("RGBA")
    extrema = layout_img.getextrema()
    # If the layout is fully opaque (e.g. solid black background), turn black pixels transparent
    if extrema[3][0] >= 250:
        w, h = layout_img.size
        rgb_data = layout_img.convert("RGB").tobytes()
        alpha_data = bytearray(w * h)
        for i in range(w * h):
            r = rgb_data[i * 3]
            g = rgb_data[i * 3 + 1]
            b = rgb_data[i * 3 + 2]
            if not (r <= threshold and g <= threshold and b <= threshold):
                alpha_data[i] = 255
        layout_img.putalpha(Image.frombytes("L", (w, h), bytes(alpha_data)))

    layout_resized = layout_img.resize((1080, 1920), Image.Resampling.LANCZOS)
    composited = Image.alpha_composite(base_rgba, layout_resized)
    result = composited.convert("RGB")

    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    result.save(dest, "JPEG", quality=95, optimize=True)
    return dest


class MythAndFactStoryWorkflow(BaseWorkflow):
    requirements = (
        AssetRequirement(
            "JSON Prompts/Myth and Fact/debunk.json", "json",
        ),
        AssetRequirement(
            "JSON Prompts/Myth and Fact/myth_slide.json", "json",
        ),
        AssetRequirement(
            "JSON Prompts/Myth and Fact/fact_slide.json", "json",
        ),
        AssetRequirement(
            "assets/debunk_thumb.jpg", "image",
        ),
        AssetRequirement(
            "assets/homecartel_logo.png", "image",
        ),
        AssetRequirement(
            "assets/Outro-Myth-Fact.png", "image",
        ),
    )
    estimate = CallEstimate(krea=3, fal=5)
    aspect_ratio = "9:16"
    final_filenames = (
        "debunk_layout.jpg",
        "myth1.jpg",
        "fact1.jpg",
        "outro.jpg",
    )
    final_aspect_ratios = ("9:16", "9:16", "9:16", "9:16")
    attachment_fields = (
        "Myth Blended",
        "Fact Blended",
        "Debunk Myth Thumbnail",
        "Outro Photo Generated",
        "Logo Watermark For Story",
        "Outro Layout",
        "Blended Image with Name text",
    )
    required_columns = (
        "Furniture Item",
    )

    def execute(self):
        row_status = str(self.ctx.anchor.fields.get("Status") or "").strip().casefold()
        if row_status in {"complete", "completed", "done"} and not self.ctx.force:
            print(f"\n[SKIP] Record {self.ctx.anchor.record_id} has Status '{self.ctx.anchor.fields.get('Status')}'. Skipping execution (even if some fields are missing). Use --force to override.\n")
            return self.success([])

        product = self.product_image()
        item_name = self.ctx.anchor.item_name or self.ctx.anchor.fields.get("Item Name") or "Chandelier"

        print(f"\n{'='*64}")
        print(f" [HOMECARTEL] MYTH & FACT STORY AUTOMATION")
        print(f" Product  : {item_name}")
        print(f" Record ID: {self.ctx.anchor.record_id}")
        print(f"{'='*64}")

        def _get_attachment(candidates: tuple[str, ...], prefix: str) -> LocalImage:
            for c in candidates:
                if self.ctx.anchor.fields.get(c):
                    return self.record_attachment(c, prefix)
            return self.record_attachment(candidates[0], prefix)

        def _get_layout_or_fallback(candidates: tuple[str, ...], fallback_files: list[Path], prefix: str) -> LocalImage:
            try:
                return _get_attachment(candidates, prefix)
            except Exception:
                for p in fallback_files:
                    if p.is_file():
                        return LocalImage(p, p.name)
                return _get_attachment(candidates, prefix)

        # 1. Resolve or generate Interior2 (Living room)
        print("\n [PHASE 1/5] Room Interiors (Krea AI)...")
        table_code = self.ctx.definition.table_code.lower()
        custom_prompt = ""
        if "chand" in table_code:
            custom_prompt = (
                os.getenv("MYTH_AND_FACT_PROMPT_CHANDELIER")
                or os.getenv("MYTH_FACT_PROMPT_CHANDELIER")
                or os.getenv("KREA_PROMPT")
                or ""
            ).strip()
        elif "floor" in table_code:
            custom_prompt = (
                os.getenv("MYTH_AND_FACT_PROMPT_FLOOR_LAMPS")
                or os.getenv("MYTH_FACT_PROMPT_FLOOR_LAMP")
                or os.getenv("MYTH_FACT_PROMPT_FLOOR_LAMPS")
                or os.getenv("KREA_PROMPT")
                or ""
            ).strip()
        elif "pendant" in table_code:
            custom_prompt = (
                os.getenv("MYTH_AND_FACT_PROMPT_PENDANT_LIGHTS")
                or os.getenv("MYTH_FACT_PROMPT_PENDANT")
                or os.getenv("MYTH_FACT_PROMPT_PENDANT_LIGHTS")
                or os.getenv("KREA_PROMPT")
                or ""
            ).strip()

        prompt2 = custom_prompt or "Modern luxury living room interior, curvilinear boucle furniture, warm neutral Japandi aesthetic, empty high ceiling ready for lighting fixture, soft daylight, vertical 9:16 portrait"
        prompt3 = (os.getenv("MYTH_AND_FACT_PROMPT_BEDROOM") or os.getenv("MYTH_AND_FACT_PROMPT_INTERIOR3") or "").strip() or "Generate me a modern bedroom"

        interior2 = None
        try:
            interior2 = self.record_attachment("Interior2", "source_interior2")
            print("  [OK] Using existing Interior 2 (Living Room)")
        except Exception:
            print(f"  [GEN] Generating new 9:16 Interior 2 (Prompt: '{prompt2}')...")
            moodboard_id = (
                os.getenv("KREA_MOODBOARD_ID")
                or self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
            )
            interior2 = self.krea_image("source_interior2.jpg", prompt2, aspect_ratio="9:16", moodboard_id=moodboard_id)
            try:
                self.attach_exact("Interior2", [interior2])
                print("  [OK] Uploaded Interior 2 to Airtable")
            except Exception as e:
                print(f"  [WARN] Could not upload Interior 2: {e}")

        # 2. Resolve or generate Interior3 (Modern Bedroom)
        interior3 = None
        try:
            interior3 = self.record_attachment("Interior3", "source_interior3")
            print("  [OK] Using existing Interior 3 (Bedroom)")
        except Exception:
            print(f"  [GEN] Generating new 9:16 Interior 3 (Prompt: '{prompt3}')...")
            moodboard_id3 = (os.getenv("KREA_MOODBOARD_ID_MYTH_AND_FACT_INTERIOR3") or "06fcc401-2e66-4638-b581-45220a8b497e").strip()
            interior3 = self.krea_image("source_interior3.jpg", prompt3, aspect_ratio="9:16", moodboard_id=moodboard_id3)
            try:
                self.attach_exact("Interior3", [interior3])
                print("  [OK] Uploaded Interior 3 to Airtable")
            except Exception as e:
                print(f"  [WARN] Could not upload Interior 3: {e}")

        # 3. Resolve or generate Outro Photo Generated (Modern Living Room)
        prompt_outro = (
            os.getenv("MYTH_AND_FACT_PROMPT_OUTRO_LIVING_ROOM")
            or "Modern luxury living room interior, curvilinear boucle furniture, warm neutral Japandi aesthetic, soft daylight, vertical 9:16 portrait"
        ).strip()
        outro_photo_generated = None
        try:
            outro_photo_generated = self.record_attachment("Outro Photo Generated", "source_outro_photo")
            print("  [OK] Using existing Outro Photo Generated (Living Room) from Airtable")
        except Exception:
            print(f"  [GEN] Generating new 9:16 Outro Photo Generated (Prompt: '{prompt_outro}')...")
            moodboard_id = self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
            outro_photo_generated = self.krea_image("source_outro_photo.jpg", prompt_outro, aspect_ratio="9:16", moodboard_id=moodboard_id)
            try:
                self.attach_exact("Outro Photo Generated", [outro_photo_generated])
                print("  [OK] Uploaded Outro Photo Generated to Airtable")
            except Exception as e:
                print(f"  [WARN] Could not upload Outro Photo Generated: {e}")

        # 4. Resolve Logo Watermark For Story
        logo_watermark_file = Path("assets/homecartel_logo.png")
        has_logo = False
        try:
            logo_att = self.record_attachment("Logo Watermark For Story", "logo_watermark")
            if logo_att and "homecartel_logo" in logo_att.filename.lower():
                has_logo = True
                print("  [OK] Using existing Logo Watermark For Story ('homecartel_logo.png') from Airtable")
        except Exception:
            has_logo = False

        if not has_logo and logo_watermark_file.is_file():
            print("  [UPLOAD] Uploading 'assets/homecartel_logo.png' to 'Logo Watermark For Story' in Airtable...")
            logo_img = LocalImage(logo_watermark_file, logo_watermark_file.name)
            try:
                self.attach_exact("Logo Watermark For Story", [logo_img])
                print("  [OK] Successfully uploaded 'assets/homecartel_logo.png' to 'Logo Watermark For Story'")
            except Exception as e:
                print(f"  [WARN] Could not upload Logo Watermark For Story: {e}")

        # 5. Resolve layout templates
        myth_layout = _get_layout_or_fallback(
            ("Myth Layout", "Myth Emoticon ", "Myth Emoticon"),
            [
                Path("JSON Prompts/Myth and Fact/myth_layout.jpg"),
                Path("JSON Prompts/Myth and Fact/0-02-06-324215afe8a9daad6830b53fe3a8da915f5961f75e8a0f58b567ce22fdda24c7_3001564131aaeb1d.jpg"),
            ],
            "myth_layout",
        )
        fact_layout = _get_layout_or_fallback(
            ("Fact Layout", "Fact Emoticon", "Fact Emoticon "),
            [
                Path("JSON Prompts/Myth and Fact/fact_layout.jpg"),
                Path("JSON Prompts/Myth and Fact/0-02-06-c1752a0e95b3c7b832ec15d361bc2fb1370bf58170d1cbd5d9d55189c581e426_759be242e44ec1f5.jpg"),
            ],
            "fact_layout",
        )
        debunk_layout = _get_layout_or_fallback(
            ("Debunk Layout",),
            [
                Path("JSON Prompts/Myth and Fact/debunk_layout.jpg"),
                Path("JSON Prompts/Myth and Fact/debunk_myth_layout.jpg"),
            ],
            "debunk_layout",
        )
        outro_layout_file = Path("assets/Outro-Myth-Fact.png")
        outro_layout = None
        has_correct_outro = False
        try:
            outro_layout = self.record_attachment("Outro Layout", "outro_layout")
            if outro_layout and ("outro-myth-fact" in outro_layout.filename.lower() or outro_layout.filename.lower().endswith(".png")):
                has_correct_outro = True
                print("  [OK] Using existing transparent Outro Layout from Airtable")
        except Exception:
            has_correct_outro = False

        if not has_correct_outro and outro_layout_file.is_file():
            print("  [UPLOAD] Uploading transparent 'assets/Outro-Myth-Fact.png' to 'Outro Layout' in Airtable...")
            outro_layout = LocalImage(outro_layout_file, outro_layout_file.name)
            try:
                self.attach_exact("Outro Layout", [outro_layout])
                print("  [OK] Successfully uploaded 'assets/Outro-Myth-Fact.png' to 'Outro Layout'")
            except Exception as e:
                print(f"  [WARN] Could not upload Outro Layout: {e}")
        elif not outro_layout and outro_layout_file.is_file():
            outro_layout = LocalImage(outro_layout_file, outro_layout_file.name)
        elif not outro_layout:
            outro_layout = _get_layout_or_fallback(
                ("Outro Layout", "Outro"),
                [
                    outro_layout_file,
                    Path("JSON Prompts/Myth and Fact/outro_layout.jpg"),
                    Path("Outro for All Reels/Outro.jpg"),
                ],
                "outro_layout",
            )

        # 6. Resolve or generate Debunk Myth Thumbnail Generated Interior
        debunk_thumbnail = None
        has_generated_thumb = False
        try:
            debunk_thumbnail = self.record_attachment("Debunk Myth Thumbnail Generated Interior", "debunk_thumb_interior")
            if debunk_thumbnail and not ("debunk_thumb.jpg" == debunk_thumbnail.filename.lower()):
                has_generated_thumb = True
                print("  [OK] Using existing Debunk Myth Thumbnail Generated Interior from Airtable")
        except Exception:
            has_generated_thumb = False

        if not has_generated_thumb:
            try:
                debunk_thumbnail = self.record_attachment("Debunk Myth Thumbnail", "debunk_thumbnail")
                if debunk_thumbnail and not ("debunk_thumb.jpg" == debunk_thumbnail.filename.lower()):
                    has_generated_thumb = True
                    print("  [OK] Using existing Debunk Myth Thumbnail from Airtable")
            except Exception:
                has_generated_thumb = False

        if not has_generated_thumb:
            prompt_debunk_thumb = (
                os.getenv("MYTH_AND_FACT_PROMPT_DEBUNK_THUMBNAIL")
                or custom_prompt
                or prompt2
                or "Modern luxury living room interior, curvilinear boucle furniture, warm neutral Japandi aesthetic, empty high ceiling ready for lighting fixture, soft daylight, vertical 9:16 portrait"
            ).strip()
            print(f"  [GEN] Generating new 9:16 Debunk Myth Thumbnail Generated Interior (Prompt: '{prompt_debunk_thumb}')...")
            moodboard_id = self.ctx.settings.moodboard_id(self.ctx.definition.table_code)
            debunk_thumbnail = self.krea_image("debunk_thumb_interior.jpg", prompt_debunk_thumb, aspect_ratio="9:16", moodboard_id=moodboard_id)
            try:
                self.attach_exact("Debunk Myth Thumbnail Generated Interior", [debunk_thumbnail])
                print("  [OK] Uploaded generated interior to 'Debunk Myth Thumbnail Generated Interior'")
            except Exception as e:
                print(f"  [WARN] Could not upload to 'Debunk Myth Thumbnail Generated Interior': {e}")
            try:
                self.attach_exact("Debunk Myth Thumbnail", [debunk_thumbnail])
                print("  [OK] Also uploaded generated interior to 'Debunk Myth Thumbnail'")
            except Exception as e:
                print(f"  [WARN] Could not upload to 'Debunk Myth Thumbnail': {e}")

        # 5. Resolve or generate blending prompts
        print("\n [PHASE 2/5] Writing Blending Prompts (Claude Sonnet)...")
        blending_prompt = ""
        try:
            blending_prompt = self.record_prompt("Blending Prompt2")
        except Exception:
            blending_prompt = ""
        if not blending_prompt or not blending_prompt.strip():
            print("  [GEN] Generating Blending Prompt 2 (Myth)...")
            blending_prompt = self.claude_blend_prompt(interior2, product)
            try:
                self.update_field("Blending Prompt2", blending_prompt)
                print("  [OK] Saved Blending Prompt 2 to Airtable")
            except Exception as e:
                print(f"  [WARN] Could not update Blending Prompt 2: {e}")
        else:
            print("  [OK] Using existing Blending Prompt 2")

        blending_prompt3 = ""
        try:
            blending_prompt3 = self.record_prompt("Blending Prompt3")
        except Exception:
            blending_prompt3 = ""
        if not blending_prompt3 or not blending_prompt3.strip():
            print("  [GEN] Generating Blending Prompt 3 (Fact)...")
            blending_prompt3 = self.claude_blend_prompt(interior3, product)
            try:
                self.update_field("Blending Prompt3", blending_prompt3)
                print("  [OK] Saved Blending Prompt 3 to Airtable")
            except Exception as e:
                print(f"  [WARN] Could not update Blending Prompt 3: {e}")
        else:
            print("  [OK] Using existing Blending Prompt 3")

        debunk_prompt = self.prompt("JSON Prompts/Myth and Fact/debunk.json")
        myth_prompt = self.prompt("JSON Prompts/Myth and Fact/myth_slide.json")
        fact_prompt = self.prompt("JSON Prompts/Myth and Fact/fact_slide.json")

        # 6. Slide 1 (Cover): Debunk slide
        print("\n [PHASE 3/5] Generating Slide 1 (Debunk Cover)...")
        debunk = self.fal_image(
            "debunk_layout.jpg",
            debunk_prompt,
            [debunk_layout, debunk_thumbnail],
            aspect_ratio="9:16",
        )
        print("  [OK] Slide 1 (Cover) Complete: debunk_layout.jpg")

        # 7. Slide 2: Myth blend + Myth layout
        print("\n [PHASE 4/5] Blending & Creating Myth & Fact Slides (Fal AI)...")
        print("  [BLENDING] Blending Interior 2 + Product for Myth...")
        blended = self.fal_image(
            "myth_blended.jpg",
            blending_prompt,
            [interior2, product],
            aspect_ratio="9:16",
        )
        self.attach_exact("Myth Blended", [blended])
        print("  [OK] Myth Interior Blended: myth_blended.jpg")

        # Auto-tag furniture item name onto Myth Blended Image using YOLO-World
        try:
            from ..akeneo_client import split_item_name
            from ..item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
            item_title, product_type = split_item_name(item_name, fallback_product_type="Chandelier")
            tag_and_upload_blended_image(
                airtable=self.ctx.airtable,
                record_id=self.ctx.anchor.record_id,
                blended_source=blended.path,
                item_name=item_title,
                product_type=product_type,
                target_field=TARGET_BLENDED_FIELD,
                output_filename_prefix="myth_tagged_blend",
                fallback_if_undetected=True,
            )
        except Exception as tag_err:
            print(f"  [WARN] Failed YOLO item tagging for Myth blend: {tag_err}")

        print("  [GEN] Generating Myth Slide with Text (Slide 2)...")
        myth1 = self.fal_image(
            "myth1.jpg",
            myth_prompt,
            [myth_layout, blended],
            aspect_ratio="9:16",
        )
        print("  [OK] Slide 2 (Myth) Complete: myth1.jpg")

        # 8. Slide 3: Fact blend + Fact debunking Myth text
        print("  [BLENDING] Blending Interior 3 + Product for Fact...")
        fact_blended = self.fal_image(
            "fact_blended.jpg",
            blending_prompt3,
            [interior3, product],
            aspect_ratio="9:16",
        )
        self.attach_exact("Fact Blended", [fact_blended])
        print("  [OK] Fact Interior Blended: fact_blended.jpg")

        # Auto-tag furniture item name onto Fact Blended Image using YOLO-World
        try:
            from ..akeneo_client import split_item_name
            from ..item_tagger import TARGET_BLENDED_FIELD, tag_and_upload_blended_image
            item_title, product_type = split_item_name(item_name, fallback_product_type="Chandelier")
            tag_and_upload_blended_image(
                airtable=self.ctx.airtable,
                record_id=self.ctx.anchor.record_id,
                blended_source=fact_blended.path,
                item_name=item_title,
                product_type=product_type,
                target_field=TARGET_BLENDED_FIELD,
                output_filename_prefix="fact_tagged_blend",
                fallback_if_undetected=True,
            )
        except Exception as tag_err:
            print(f"  [WARN] Failed YOLO item tagging for Fact blend: {tag_err}")

        print("  [GEN] Generating Fact Slide Debunking Myth (Slide 3)...")
        fact1 = self.fal_image(
            "fact1.jpg",
            fact_prompt,
            [fact_layout, fact_blended, myth1],
            aspect_ratio="9:16",
        )
        print("  [OK] Slide 3 (Fact) Complete: fact1.jpg")

        # 9. Slide 4: Outro slide (Composite Outro Layout over Outro Photo Generated via PIL)
        print("\n [PHASE 5/5] Creating Slide 4 (Outro Layout Local Conversion)...")
        outro_dest = self.ctx.workdir / "outro.jpg"
        convert_outro_layout_slide(outro_photo_generated.path, outro_layout.path, outro_dest)
        outro = LocalImage(outro_dest, "outro.jpg")
        print("  [OK] Slide 4 (Outro) Complete: outro.jpg (composite of Outro Photo Generated + Outro Layout)")

        # 10. Upload all 4 final slides to Airtable
        finals = [debunk, myth1, fact1, outro]
        print(f"\n [UPLOAD] Uploading 4 completed slides to '{self.ctx.definition.final_field}'...")
        self.attach_exact(self.ctx.definition.final_field, finals)
        print("  [OK] All 4 slides uploaded to Airtable successfully!")
        print(f"{'='*64}\n")
        return self.success(finals)
