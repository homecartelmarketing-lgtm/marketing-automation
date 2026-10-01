"""Claude-written "Style Tip of the Day" sentence for the Tips & Edu Story."""

from __future__ import annotations

import re

MIN_WORDS = 8
MAX_WORDS = 28

TIP_SYSTEM_INSTRUCTION = (
    "You write the 'Style Tip of the Day' line for HomeCartel, a premium lighting brand, "
    "for an Instagram story. Look at the room photo and reply with ONE original, polished "
    "English interior-styling tip."
)

TIP_USER_PROMPT = (
    "The photo shows a '{item_title}' ({product_type}) installed in the room.\n"
    "Write exactly ONE sentence of 12-20 words, based on the furniture, materials, decor or "
    "lighting you can actually see.\n"
    "Rules: reply with the sentence only; no quotes, brackets, labels, bullet points, emoji or "
    "hashtags; do not mention a brand name or a price."
)

# Neutral tips used only if the Claude call fails or returns something unusable, so a run
# still completes (the tip is a styling line, never a product claim).
FALLBACK_TIPS: dict[str, str] = {
    "default": "Layer warm lighting with natural textures to make any room feel calm, inviting and beautifully balanced.",
    "pendant_lights": "Hang pendant lights at a comfortable height above the table so the glow feels warm and welcoming.",
    "chandeliers": "Let a statement chandelier anchor the room and echo its finish in nearby furniture and decor.",
    "cluster_chandeliers": "Use a cluster chandelier to fill tall ceilings and draw the eye upward in open spaces.",
    "floor_lamps": "Place a floor lamp beside seating to add a soft layer of light and balance the corner.",
    "table_lamps": "Pair a table lamp with a bedside surface to create a soft, relaxing glow for the evening.",
    "ceiling_mounted": "Choose a ceiling mounted light that blends with the architecture for clean, even brightness.",
}


def build_tip_prompt(item_title: str, product_type: str) -> str:
    return TIP_USER_PROMPT.format(
        item_title=item_title or "lighting fixture",
        product_type=product_type or "lighting",
    )


def fallback_tip(category_code: str = "") -> str:
    key = (category_code or "").strip().lower()
    return FALLBACK_TIPS.get(key, FALLBACK_TIPS["default"])


def sanitize_tip(raw: str) -> str:
    """Return a single clean sentence, or "" if the reply is unusable."""
    text = str(raw or "").strip()
    if not text:
        return ""
    # First non-empty line only (models sometimes add explanations afterwards).
    text = next((line.strip() for line in text.splitlines() if line.strip()), "")
    quotes = "\"'“”‘’[]() "
    text = re.sub(r"[*_`#>]+", "", text).strip().strip(quotes)
    text = re.sub(r"^\s*(style\s*tip(\s*of\s*the\s*day)?|tip)\s*[:\-]\s*", "", text, flags=re.I)
    text = text.strip().strip(quotes)
    text = " ".join(text.split())
    if not text:
        return ""
    words = text.split()
    if len(words) < MIN_WORDS or len(words) > MAX_WORDS:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def resolve_tip(raw_reply: str | None, category_code: str = "") -> tuple[str, bool]:
    """Return (tip, used_fallback)."""
    cleaned = sanitize_tip(raw_reply or "")
    if cleaned:
        return cleaned, False
    return fallback_tip(category_code), True
