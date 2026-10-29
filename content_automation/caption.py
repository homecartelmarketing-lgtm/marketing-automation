"""Shared universal Instagram caption generation for HomeCartel pipelines.

Every Feed and Reel run auto-generates one caption per Airtable row (slot-0 /
anchor product) in the exact user format and stores it in the
``Caption Generated`` (multilineText) field. Caption failure must NEVER
block ``Complete``/``Done`` -- callers use :func:`write_row_caption`, which
leaves the cell blank on any failure (no generic fallback caption).

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
from typing import Callable

CAPTION_FIELD = "Caption Generated"
CAPTION_FIELD_TYPE = "multilineText"
#: Same value as ``item_tagger.TARGET_BLENDED_FIELD`` (kept here to avoid its heavy import).
TAGGED_BLEND_FIELD = "Blended Image with Name text"

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
    flow: str = "",
) -> str:
    """Build the Claude Sonnet 5 vision prompt for the row caption."""
    item = _clean(item_name) or "featured lighting piece"
    ptype = _clean(product_type) or "lighting"
    cat = _clean(category)
    cat_line = f"Category context: {cat}.\n" if cat else ""
    flow_text = _clean(flow)
    flow_line = (
        f"About this post: {flow_text} Make the hook and value sentences "
        "fit this post, not a generic product ad.\n"
        if flow_text
        else ""
    )
    return (
        "You write the Instagram caption for HomeCartel, a premium lighting "
        "brand in the Philippines.\n"
        f"The photo shows the '{item}' ({ptype}) installed in a styled room.\n"
        f"{cat_line}"
        f"{flow_line}"
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


def collect_image_urls(
    fields: dict,
    field_names: "tuple[str, ...] | list[str]",
    limit: int = 4,
) -> list[str]:
    """Airtable attachment URLs from the named fields, in order, capped."""
    urls: list[str] = []
    for name in field_names:
        value = (fields or {}).get(name)
        if isinstance(value, str) and value.startswith("http"):
            urls.append(value.strip())
        elif isinstance(value, list):
            for att in value:
                url = att.get("url") if isinstance(att, dict) else att
                if isinstance(url, str) and url.strip().startswith("http"):
                    urls.append(url.strip())
        if len(urls) >= limit:
            break
    return urls[:limit]


def generate_caption(
    fal: object,
    item_name: str = "",
    product_type: str = "",
    image_urls: list[str] | None = None,
    category: str = "",
    flow: str = "",
) -> str:
    """Generate the row caption via Claude Vision. Never raises.

    Returns the cleaned caption, or ``""`` when the client is missing, the
    call fails, or the reply is unusable after one retry. There is no
    generic fallback caption: a blank cell is better than a wrong one.
    """
    item = _clean(item_name)
    ptype = _clean(product_type)
    if fal is None or not item:
        return ""
    instruction = build_caption_instruction(item, ptype, category, flow)
    model = os.environ.get(CLAUDE_MODEL_ENV, CLAUDE_MODEL_DEFAULT).strip()
    if not model:
        model = CLAUDE_MODEL_DEFAULT
    urls = [str(u).strip() for u in (image_urls or []) if str(u).strip()]
    for _attempt in range(2):
        try:
            generate = getattr(fal, "generate_vision_prompt")
            raw = generate(image_urls=urls, prompt=instruction, model=model)
            cleaned = sanitize_caption(raw, item)
            if cleaned:
                return cleaned
        except Exception:
            continue
    return ""


def write_row_caption(
    airtable: object,
    record_id: str,
    fields: "dict | None",
    fal: object,
    flow_key: str,
    *,
    image_fields: "tuple[str, ...] | list[str]" = (),
    image_urls: list[str] | None = None,
    slot: int = 0,
    item_name: str = "",
    product_type: str = "",
    category: str = "",
    update_fn: "Callable[[dict], object] | None" = None,
) -> str:
    """Generate and store ``Caption Generated`` for one finished row.

    Call it right before the row is marked Complete/Done. Pass ``fields=None``
    to re-read the row from Airtable. It never raises
    and never blocks completion: on any failure the cell stays blank and a
    ``[WARN]`` line is printed. An existing caption is kept as is (manual
    edits win). Returns the caption now on the row ("" when none).
    ``update_fn`` replaces the Airtable write for pipelines that use raw
    HTTP calls instead of a client object.
    """
    try:
        if fields is None:  # re-read so attachments uploaded this run are present
            fields = (airtable.get_record(record_id) or {}).get("fields") or {}  # type: ignore[attr-defined]
        existing = str((fields or {}).get(CAPTION_FIELD) or "").strip()
        if existing:
            return existing
        from content_automation.akeneo_client import split_item_name
        from content_automation.caption_flows import flow_for
        from content_automation.prompts.scale import (
            item_name_for_slot,
            product_type_for_slot,
        )

        raw_name = _clean(item_name) or item_name_for_slot(fields or {}, slot)
        raw_type = _clean(product_type) or product_type_for_slot(fields or {}, slot)
        name, ptype = split_item_name(raw_name, raw_type)
        urls = list(image_urls or []) or collect_image_urls(fields or {}, image_fields)
        print("  [INFO] Generating Instagram caption...")
        caption = generate_caption(
            fal, name, ptype, urls, category, flow_for(flow_key),
        )
        if not caption:
            print("  [WARN] Caption not generated; leaving it blank.")
            return ""
        ensure = getattr(airtable, "ensure_fields", None)
        if callable(ensure):  # create the column if the table lacks it
            try:
                try:
                    ensure({CAPTION_FIELD: CAPTION_FIELD_TYPE})
                except TypeError:  # AirtableClient.ensure_fields needs execute=
                    ensure({CAPTION_FIELD: CAPTION_FIELD_TYPE}, execute=True)
            except Exception:
                pass
        if update_fn is not None:
            update_fn({CAPTION_FIELD: caption})
        elif hasattr(airtable, "update_record"):
            airtable.update_record(record_id, {CAPTION_FIELD: caption})  # type: ignore[attr-defined]
        else:
            airtable.update_records([(record_id, {CAPTION_FIELD: caption})])  # type: ignore[attr-defined]
        print("  [OK] Caption generated.")
        return caption
    except Exception as err:  # never block Complete/Done
        print(f"  [WARN] Caption step failed: {err}")
        return ""
