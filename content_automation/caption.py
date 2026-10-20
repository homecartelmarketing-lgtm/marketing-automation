"""Shared universal Instagram caption generation for HomeCartel pipelines.

Every pipeline run auto-generates one caption per Airtable row (slot-0 /
anchor product) in the exact user format and stores it in the
``Caption Generated`` (multilineText) field. Caption failure must NEVER
block ``Complete``/``Done`` -- callers use :func:`generate_caption`,
which falls back deterministically on any error.

Canonical shape (blocks separated by one blank line):
    [One liner] [emoji]

    [Product name] | [Product type]

    [1-2 value sentences]

    [CTA question]

    [contact block starting ``Inquire now!``]

    [hashtag line]
"""

from __future__ import annotations

import os
import re

CAPTION_FIELD = "Caption Generated"
CAPTION_FIELD_TYPE = "multilineText"

CLAUDE_MODEL_ENV = "CLAUDE_VISION_MODEL"
CLAUDE_MODEL_DEFAULT = "anthropic/claude-sonnet-5"

CONTACT_BLOCK = (
    "Inquire now!\n"
    "\U0001f4de 0977 825 5588 (or send us a DM)\n"
    "\U0001f4de (02) 8248 8071 | Dial 1\n"
    "\U0001f4e9 sales@homecartel.com"
)

HASHTAG_LINE = (
    "#homecartel #homecartelfix #lightingdesign #interiordesign "
    "#interiorinspo #interiordesignph #homeph"
)

#: Minimum word count for a usable final caption.
MIN_CAPTION_WORDS = 30


def _clean(s: object) -> str:
    """Collapse whitespace and strip; never raises."""
    return " ".join(str(s or "").split()).strip()


def build_caption_instruction(
    item_name: str = "",
    product_type: str = "",
    category: str = "",
) -> str:
    """Build the Claude Sonnet 5 vision prompt for the row caption."""
    item = _clean(item_name) or "featured lighting piece"
    ptype = _clean(product_type) or "lighting"
    cat = _clean(category)
    cat_line = f"Category context: {cat}.\n" if cat else ""
    return (
        "You write the Instagram caption for HomeCartel, a premium lighting "
        "brand in the Philippines.\n"
        f"The photo shows the '{item}' ({ptype}) installed in a styled room.\n"
        f"{cat_line}"
        "Write the caption with 6 blocks separated by exactly one blank line:\n"
        "1. One short poetic hook line ending with one emoji.\n"
        f"2. Product line exactly: {item} | {ptype}\n"
        "3. One to two sentences about the warm glow, materials, and room "
        "feel (no prices, no specs, no brand claims).\n"
        f"4. One CTA question mentioning the {item}.\n"
        "5. Contact block exactly:\n"
        f"{CONTACT_BLOCK}\n"
        "6. Hashtag line exactly:\n"
        f"{HASHTAG_LINE}\n"
        "Rules: output ONLY the caption text, no markdown, no quotes. "
        "Keep it warm and elegant."
    )


def assemble_caption(
    one_liner: str = "",
    item_name: str = "",
    product_type: str = "",
    value_text: str = "",
    cta_question: str = "",
) -> str:
    """Assemble the exact 6-block user format. Never returns empty."""
    first = _clean(one_liner)
    item = _clean(item_name) or "Featured Piece"
    ptype = _clean(product_type) or "Lighting"
    value = _clean(value_text)
    cta = _clean(cta_question)
    blocks: list[str] = []
    if first:
        blocks.append(first)
    blocks.append(f"{item} | {ptype}")
    if value:
        blocks.append(value)
    if cta:
        blocks.append(cta)
    blocks.append(CONTACT_BLOCK)
    blocks.append(HASHTAG_LINE)
    return "\n\n".join(blocks).strip()


def sanitize_caption(raw: object, item_name: str = "") -> str:
    """Return a clean caption, or "" if the reply is unusable.

    Unusable = missing the item name, or fewer than
    :data:`MIN_CAPTION_WORDS` words of real caption body (contact block
    and hashtag line excluded from the count). Missing contact/hashtag
    blocks are appended verbatim.
    """
    text = str(raw or "").replace("\r\n", "\n").strip()
    if not text:
        return ""
    text = text.replace("```", "").strip()
    text = text.strip("\"' \u201c\u201d\u2018\u2019").strip()
    if not text:
        return ""
    lines = [re.sub(r"[ \t]+", " ", ln.rstrip()) for ln in text.split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not text:
        return ""
    item = _clean(item_name)
    if item and item.lower() not in text.lower():
        return ""
    # Count only the real caption body: drop the contact block and any
    # hashtag line so a two-word reply plus constants cannot pass.
    body_blocks = [
        blk for blk in text.split("\n\n")
        if blk.strip()
        and not blk.strip().startswith("Inquire now!")
        and "#homecartel" not in blk.lower()
        and not blk.strip().startswith("\U0001f4de")
        and not blk.strip().startswith("\U0001f4e9")
    ]
    if len(" ".join(body_blocks).split()) < MIN_CAPTION_WORDS:
        return ""
    if "Inquire now!" not in text:
        text = text.rstrip() + "\n\n" + CONTACT_BLOCK
    if "#homecartel" not in text.lower():
        text = text.rstrip() + "\n\n" + HASHTAG_LINE
    return text.strip()


def fallback_caption(
    item_name: str = "",
    product_type: str = "",
    category: str = "",  # noqa: ARG001 - uniform call signature
) -> str:
    """Deterministic caption used when Claude fails. Never empty."""
    item = _clean(item_name) or "Featured Piece"
    ptype = _clean(product_type) or "Lighting"
    one_liner = "Timeless glow, made for slow evenings \u2728"
    value = (
        "Its warm glow softens the room and pairs beautifully with wood, "
        f"linen, and stone, bringing quiet luxury to everyday moments "
        f"with the {item}."
    )
    cta = f"Ready to let the {item} steal the spotlight in your home?"
    return assemble_caption(one_liner, item, ptype, value, cta)


def generate_caption(
    fal: object,
    item_name: str = "",
    product_type: str = "",
    image_urls: list[str] | None = None,
    category: str = "",
) -> tuple[str, bool]:
    """Generate the row caption via Claude Vision. Never raises.

    Returns ``(caption, used_fallback)``. On any error -- missing client,
    API exception, or unusable reply -- returns the deterministic
    fallback with ``used_fallback=True`` so the run still completes.
    """
    item = _clean(item_name) or "Featured Piece"
    ptype = _clean(product_type) or "Lighting"
    try:
        if fal is None:
            raise ValueError("no Fal client available for caption")
        instruction = build_caption_instruction(item, ptype, category)
        model = os.environ.get(CLAUDE_MODEL_ENV, CLAUDE_MODEL_DEFAULT).strip()
        if not model:
            model = CLAUDE_MODEL_DEFAULT
        urls = [str(u).strip() for u in (image_urls or []) if str(u).strip()]
        generate = getattr(fal, "generate_vision_prompt")
        raw = generate(image_urls=urls, prompt=instruction, model=model)
        cleaned = sanitize_caption(raw, item)
        if cleaned:
            return cleaned, False
        return fallback_caption(item, ptype, category), True
    except Exception:
        return fallback_caption(item, ptype, category), True

