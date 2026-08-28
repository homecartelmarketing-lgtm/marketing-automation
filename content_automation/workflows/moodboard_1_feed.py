from __future__ import annotations

from ..errors import AssetValidationError
from ..models import CallEstimate
from .base import BaseWorkflow

import json

DEFAULT_WATERMARK_PLACEHOLDER_PROMPT = json.dumps({
  "assistant_instruction": {
    "generate_image": False,
    "instruction": "Do not generate an image. Use this JSON only as a reusable image-editing prompt."
  },
  "task": "replace_black_background_with_dynamic_uploaded_photo_and_preserve_homecartel_logo",
  "objective": "Use the first uploaded reference image as the fixed layout and logo reference. Replace ONLY the solid black background from the first reference image with the second uploaded reference photo. The second reference photo is dynamic and may be different every time this prompt is used, so always use whatever image is uploaded as Reference Image 2 as the new full-background photo. Preserve the HomeCartel® logo from Reference Image 1 exactly as it appears. Do not change, regenerate, redesign, move, resize, recolor, crop, distort, or recreate the logo. Only the black background must be replaced.",
  "reference_images": {
    "reference_image_1": {
      "role": "FIXED LAYOUT AND LOGO REFERENCE",
      "instruction": "Use the first uploaded image as the exact layout reference. It contains a black background and the original white HomeCartel® logo. The HomeCartel® logo must remain completely intact and locked in its exact original location.",
      "preserve": [
        "HomeCartel® logo artwork",
        "logo typography",
        "logo font appearance",
        "registered trademark symbol",
        "white logo color",
        "logo size",
        "logo width and height",
        "logo scale",
        "logo proportions",
        "logo spacing",
        "logo alignment",
        "exact horizontal position",
        "exact vertical position",
        "exact distance from the left edge",
        "exact distance from the bottom edge"
      ],
      "change": "Replace only the solid black background."
    },
    "reference_image_2": {
      "role": "DYNAMIC REPLACEMENT BACKGROUND",
      "instruction": "The second uploaded image can be any photo and will change between uses. Always treat the currently uploaded second reference image as the new background source. It may contain an interior, bedroom, living room, dining room, kitchen, furniture scene, architectural scene, product setting, or another photographic composition. Do not assume it will match any previously uploaded image.",
      "dynamic_rule": "Automatically use the latest image supplied as Reference Image 2. Never depend on a specific bedroom, furniture item, lamp, chandelier, wall color, room design, or previous image content.",
      "preservation_rule": "Preserve the current second reference photo as accurately as possible, including its existing subjects, furniture, architecture, objects, colors, lighting, shadows, reflections, materials, textures, perspective, depth, and overall photographic appearance."
    }
  },
  "editing_instruction": {
    "background_replacement": "Completely remove the solid black background from Reference Image 1 and replace it with the entire current Reference Image 2. The new photo must fill the complete canvas from edge to edge.",
    "layer_order": {
      "bottom_layer": "Current Reference Image 2 used as the full-background photograph.",
      "top_layer": "Original HomeCartel® logo preserved from Reference Image 1."
    },
    "black_removal_rule": "No portion of the original black background should remain visible unless black naturally exists inside the newly uploaded Reference Image 2 itself.",
    "background_fill": "The second reference photo must extend behind the logo and cover the full width and height of the canvas."
  },
  "image_fitting": {
    "instruction": "Fit the current Reference Image 2 into the exact aspect ratio and dimensions of Reference Image 1.",
    "method": "Use proportional scaling and intelligent composition-aware cropping only when necessary.",
    "priority": "Keep the main visual subject or important content of the current Reference Image 2 clearly visible while filling the entire frame.",
    "do_not": [
      "Do not stretch the photo",
      "Do not squeeze the photo",
      "Do not warp the photo",
      "Do not distort perspective",
      "Do not create empty spaces",
      "Do not add black bars",
      "Do not add colored borders"
    ]
  },
  "logo_lock": {
    "element": "Original HomeCartel® logo from Reference Image 1",
    "instruction": "Treat the logo as a locked overlay layer. Preserve the actual logo from the first image rather than generating a new approximation.",
    "position": "Keep the logo at the exact same X and Y coordinates relative to the canvas.",
    "size": "Maintain the exact original logo dimensions and scale.",
    "appearance": "Maintain the exact original typography, letter spacing, proportions, white color, and registered trademark symbol.",
    "strict_rule": "The logo must not move, shift, resize, rotate, recolor, become transparent, disappear, or be recreated using a substitute font."
  },
  "dynamic_photo_preservation": {
    "instruction": "Because Reference Image 2 changes every time, analyze the currently uploaded photo and preserve what actually exists in that specific image.",
    "preserve_current_content": [
      "main subjects",
      "furniture",
      "products",
      "decor",
      "architecture",
      "walls",
      "floors",
      "ceilings",
      "windows",
      "lighting fixtures",
      "objects",
      "colors",
      "materials",
      "textures",
      "natural lighting",
      "shadows",
      "reflections",
      "camera perspective"
    ],
    "rule": "Do not add, remove, replace, or redesign visible elements from the second reference photo unless minimal cropping is necessary to fit the first reference canvas."
  },
  "strict_rules": [
    "Change only the black background from Reference Image 1.",
    "Always use the currently uploaded Reference Image 2 as the replacement background.",
    "Never assume Reference Image 2 contains the same scene as a previous use.",
    "Preserve the HomeCartel® logo exactly.",
    "Do not move or resize the logo.",
    "Do not recreate the logo as typed text.",
    "Do not change the logo font.",
    "Do not remove the registered trademark symbol.",
    "Do not add product names.",
    "Do not add captions.",
    "Do not add extra logos.",
    "Do not add graphic shapes.",
    "Do not add frames or borders.",
    "Do not add gradients or overlays.",
    "Do not leave any empty canvas areas.",
    "Do not modify the new background unnecessarily."
  ],
  "output": {
    "aspect_ratio": "Match Reference Image 1 exactly.",
    "canvas": "Match the original first reference canvas dimensions whenever possible.",
    "background": "Current Reference Image 2 filling the entire canvas.",
    "foreground": "Original unchanged HomeCartel® logo from Reference Image 1.",
    "quality": "High-resolution, clean, sharp, natural, and photorealistic.",
    "final_result": "The final image must appear as the current uploaded Reference Image 2 placed as the complete full-frame background while the original HomeCartel® logo remains perfectly intact in the exact same position and size from Reference Image 1."
  }
}, indent=2)
DEFAULT_LAYOUT_PLACEHOLDER_PROMPT = json.dumps({
  "assistant_instruction": {
    "generate_image": False,
    "instruction": "Do not generate a new image from scratch. Use this JSON strictly as a reusable image-editing prompt to update the existing layout image provided as Reference Image 1."
  },
  "task": "edit_text_labels_and_materials_on_moodboard_layout",
  "objective": "Take Reference Image 1 (from field 'Moodboard Layout') as the exact fixed visual base layout template. Analyze Reference Image 2 (the uploaded 'Moodboard #1 Blended' interior photo) to identify the 3 primary design-defining materials in the room. Edit ONLY the text labels on the 3 swatches in Reference Image 1 so that each label accurately names a material detected in Reference Image 2, while preserving the exact font style, serif typeface, text color, position, and layout from Reference Image 1.",
  "reference_images": {
    "reference_image_1": {
      "role": "FIXED BASE LAYOUT AND TYPOGRAPHY TEMPLATE",
      "field_source": "Moodboard Layout",
      "instruction": "Use Reference Image 1 as the exact template for composition, 3-swatch layout structure, drop shadows, pure white background, and serif font typography style. All elements from Reference Image 1 must be preserved.",
      "preserve": [
        "exact 3-swatch layout placement and overlapping positions",
        "top-left, top-right, and bottom-center swatch arrangement",
        "soft realistic studio drop shadows under each swatch",
        "pure solid white background (#FFFFFF)",
        "exact serif font family, typography style, and letter spacing",
        "white font color and font sizing",
        "text label alignment and placement inside the top edge of each swatch"
      ]
    },
    "reference_image_2": {
      "role": "DYNAMIC INTERIOR SOURCE FOR MATERIAL LABELS",
      "field_source": "Moodboard #1 Blended",
      "instruction": "Analyze this uploaded interior photograph from scratch every run to detect the three primary materials, finishes, or fabrics present in the room scene (such as wood grain, marble veining, upholstery fabric, wool rug, metal finish, plaster, or tile)."
    }
  },
  "detailed_processing_steps": {
    "step_1_material_detection": "Examine Reference Image 2 and select the 3 most prominent materials visible in the interior photo.",
    "step_2_label_generation": "Create three concise 2-to-4 word descriptive text labels for the detected materials (e.g., Warm Oak Wood, Cream Boucle Upholstery, Dark Emperador Marble).",
    "step_3_text_editing": "Replace ONLY the text label strings printed on the swatches in Reference Image 1 with the newly generated material labels.",
    "step_4_texture_updating": "Update the physical surface textures of the 3 swatches in Reference Image 1 to display the textures and colors of the 3 detected materials from Reference Image 2, keeping the exact swatch shapes, overlapping arrangement, and drop shadows intact."
  },
  "typography_and_font_specifications": {
    "font_family": "Preserve the exact elegant serif font family from Reference Image 1 (high-contrast editorial serif like Didot, Bodoni, Playfair Display, or Garamond).",
    "font_color": "Crisp white text color with subtle natural drop shadow contrast.",
    "font_size": "Match the exact font size and letter spacing of the text in Reference Image 1.",
    "font_alignment": "Position each label near the top edge of its respective swatch, aligned horizontally near the center or top margin.",
    "strict_rule": "Never use sans-serif fonts, bold gothic fonts, or low-quality typography. The text style must be an exact clone of the serif typography in Reference Image 1."
  },
  "editing_and_replacement_rules": {
    "text_label_replacement": "Identify 3 materials from Reference Image 2. Replace ONLY the 3 text label strings printed on the swatches in Reference Image 1 with 2-to-4 word descriptive names.",
    "typography_preservation": "Keep the exact serif font typeface, font size, white text color, and positioning from Reference Image 1. Do not use sans-serif."
  },
  "strict_no_change_rules": [
    "Do not change 3-swatch layout placement from Reference Image 1.",
    "Do not change serif font family, text color, or position from Reference Image 1.",
    "Do not add extra text, captions, logos, or watermarks.",
    "Do not alter pure white background (#FFFFFF)."
  ],
  "output": {
    "aspect_ratio": "4:5 vertical portrait format.",
    "quality": "Photorealistic luxury editorial moodboard with crisp serif typography.",
    "final_result": "Reference Image 1 updated with new text labels and material textures matching Reference Image 2, while preserving exact layout, serif font style, and white background."
  }
}, indent=2)
DEFAULT_CLOSEUP_PLACEHOLDER_PROMPT = json.dumps({
  "assistant_instruction": {
    "generate_image": False,
    "instruction": "Do not generate an image from scratch. Use this JSON strictly as a reusable image-editing prompt to convert any uploaded furniture or lighting product into a luxury macro close-up photograph."
  },
  "task": "convert_furniture_item_to_macro_closeup_photo",
  "objective": "Take Reference Image 2 (the uploaded 'Furniture Item' product photo) and transform it into a dramatic, high-end commercial macro close-up photograph. Use Reference Image 1 ('Moodboard #1 Layout Closeup') as the exact visual reference for camera distance, extreme macro framing, shallow depth of field bokeh, studio lighting direction, shadow contrast, material texture fidelity, and editorial photography aesthetics.",
  "reference_images": {
    "reference_image_1": {
      "role": "MACRO PHOTOGRAPHY STYLE, LIGHTING, AND FRAMING REFERENCE",
      "field_source": "Moodboard #1 Layout Closeup",
      "instruction": "Use Reference Image 1 strictly for visual guidance on photographic style, camera positioning, extreme macro framing, warm ambient illumination, shallow depth-of-field bokeh, and material detail presentation. Do not copy the specific physical product depicted in Reference Image 1.",
      "preserve_style": [
        "extreme macro close-up framing and tight camera angle",
        "shallow depth of field with soft, buttery background blur (bokeh)",
        "dramatic studio accent lighting highlighting micro surface textures",
        "warm interior illumination glowing through translucent, glass, or metallic elements",
        "high-end luxury editorial commercial product photography aesthetic"
      ]
    },
    "reference_image_2": {
      "role": "PRODUCT SOURCE AND MATERIAL TRUTH",
      "field_source": "Furniture Item",
      "instruction": "This is the uploaded product photo. Replicate its exact materials, finishes, hardware, glass, brass/metal tones, crystals, fabric, wood grain, tile, or structural details with 100% material fidelity in extreme macro detail."
    }
  },
  "macro_photography_specifications": {
    "lens_and_framing": "Use a 100mm macro telephoto lens perspective with a tight crop focusing on the most intricate, visually compelling design feature of Reference Image 2 (such as glass discs, metal joints, brass arms, crystal pendants, textured fabric, or polished surfaces).",
    "depth_of_field": "Set an aperture around f/2.8 to f/4 to create a razor-sharp focal plane on the foreground detail while rendering background components in soft, dreamy bokeh.",
    "lighting_and_ambience": "Apply warm 3000K studio key lighting with subtle side rim highlights and soft natural drop shadows, showcasing authentic surface specular reflections, material translucency, brushed metal grain, or glass texture.",
    "color_and_tonality": "Maintain the true color palette, metallic undertones, and material finish of Reference Image 2 with rich contrast and clean highlight control."
  },
  "rendering_rules": {
    "material_accuracy": "Ensure 100% fidelity to the materials, colors, textures, and construction details of Reference Image 2. Do not alter or distort the product authentic design elements.",
    "surface_details": "Highlight micro surface features such as frosted texture, metal brushed grain, glass bubbles, fabric weave, or polished reflections."
  },
  "strict_no_copy_rules": [
    "Do not copy the specific chandelier or product design from Reference Image 1; use Reference Image 1 only for photography style and macro framing.",
    "Do not include full room backgrounds, furniture silhouettes, humans, watermarks, text, or logos in the closeup shot.",
    "Do not output flat, unlit, noisy, or low-resolution images."
  ],
  "output": {
    "aspect_ratio": "4:5 vertical portrait format.",
    "quality": "Ultra high-resolution photorealistic commercial macro product photography.",
    "final_result": "An extreme macro close-up photograph of the uploaded Furniture Item, rendered in the luxury editorial studio style of Moodboard #1 Layout Closeup."
  }
}, indent=2)


class Moodboard1FeedWorkflow(BaseWorkflow):
    estimate = CallEstimate(kie=4)
    aspect_ratio = "4:5"
    required_columns = ("Status", "Prompt")
    attachment_fields = (
        "Moodboard #1 Blended",
        "Moodboard Watermark Converted",
        "Converted Moodboard",
        "Moodboard Closeup Photo",
    )
    final_filenames = (
        "moodboard_1_blended.jpg",
        "moodboard_watermark_converted.jpg",
        "converted_moodboard.jpg",
        "moodboard_closeup_photo.jpg",
    )
    final_aspect_ratios = ("4:5", "4:5", "4:5", "4:5")

    def execute(self):
        anchor = self.ctx.anchor

        # Step 1: Moodboard #1 Blended (Reuse if already present)
        existing_blended = anchor.fields.get("Moodboard #1 Blended") or []
        if existing_blended:
            blended_image = self.record_attachment("Moodboard #1 Blended", "moodboard_1_blended")
        else:
            source_interior = self.interior_image()
            product = self.product_image()
            blend_prompt = self.record_prompt("Prompt")

            blended_image = self.nano_image(
                "moodboard_1_blended.jpg",
                blend_prompt,
                [source_interior, product],
                aspect_ratio="4:5",
                model="nano-banana-pro",
            )
            self.attach_exact("Moodboard #1 Blended", [blended_image])

        # Step 2: Moodboard Watermark Converted (Reuse if already present)
        existing_watermark_converted = anchor.fields.get("Moodboard Watermark Converted") or []
        if existing_watermark_converted:
            watermark_converted = self.record_attachment("Moodboard Watermark Converted", "moodboard_watermark_converted")
        else:
            watermark_image = self.table_attachment("Moodboard Watermark", "watermark")
            watermark_prompt = (
                str(anchor.fields.get("Moodboard Watermark Prompt") or "").strip()
                or DEFAULT_WATERMARK_PLACEHOLDER_PROMPT
            )
            watermark_converted = self.nano_image(
                "moodboard_watermark_converted.jpg",
                watermark_prompt,
                [blended_image, watermark_image],
                aspect_ratio="4:5",
                model="nano-banana-pro",
            )
            self.attach_exact("Moodboard Watermark Converted", [watermark_converted])

        # Step 3: Converted Moodboard (Reuse if already present, generate if missing)
        existing_converted_moodboard = anchor.fields.get("Converted Moodboard") or []
        if existing_converted_moodboard:
            converted_moodboard = self.record_attachment("Converted Moodboard", "converted_moodboard")
        else:
            layout_image = self.table_attachment("Moodboard Layout", "layout")
            layout_prompt = (
                str(anchor.fields.get("Converted Moodboard Prompt") or anchor.fields.get("Moodboard Layout Prompt") or "").strip()
                or DEFAULT_LAYOUT_PLACEHOLDER_PROMPT
            )
            converted_moodboard = self.nano_image(
                "converted_moodboard.jpg",
                layout_prompt,
                [blended_image, layout_image],
                aspect_ratio="4:5",
                model="nano-banana-pro",
            )
            self.attach_exact("Converted Moodboard", [converted_moodboard])

        # Step 4: Moodboard Closeup Photo (Reuse if already present, generate if missing)
        existing_closeup = anchor.fields.get("Moodboard Closeup Photo") or []
        if existing_closeup:
            closeup_photo = self.record_attachment("Moodboard Closeup Photo", "moodboard_closeup_photo")
        else:
            product = self.product_image()
            layout_closeup = self.table_attachment("Moodboard #1 Layout Closeup", "layout_closeup")
            closeup_prompt = (
                str(anchor.fields.get("Moodboard Closeup Photo Prompt") or "").strip()
                or DEFAULT_CLOSEUP_PLACEHOLDER_PROMPT
            )
            closeup_photo = self.nano_image(
                "moodboard_closeup_photo.jpg",
                closeup_prompt,
                [layout_closeup, product],
                aspect_ratio="4:5",
                model="nano-banana-pro",
            )
            self.attach_exact("Moodboard Closeup Photo", [closeup_photo])

        finals = [blended_image, watermark_converted, converted_moodboard, closeup_photo]
        self.attach_exact(self.ctx.definition.final_field, finals)

        return self.success(finals)
