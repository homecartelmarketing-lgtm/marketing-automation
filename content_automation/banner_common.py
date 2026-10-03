"""Building blocks shared by the banner pipelines (Christmas banner, Sale banner).

Everything here is generic: Akeneo scraping with dedup, Krea/Claude/Nano Banana helpers,
'CODE: value' line parsing for the Airtable text columns, and the phase selection logic behind
``--from-phase`` / ``--text-only`` / ``--only-phase``. Pipeline-specific constants (field names,
fixtures, prompts) stay in each ``generate_*_banner_pipeline.py``.
"""

from __future__ import annotations

import html
import os
import re
from typing import Any, Callable, Sequence

from .akeneo_client import AkeneoClient, split_item_name
from .config import load_settings
from .errors import AutomationError, ProviderError
from .fal_client import DEFAULT_FAL_MODEL, FalClient
from .krea_client import KreaClient
from .scraping.airtable import ScrapeAirtableClient
from .scraping.furniture_item import fetch_all_base_existing_identities
from .scraping.products import product_item
from .shopify_client import ShopifyClient


class PipelineClients:
    """Airtable + Akeneo + fal + Krea clients built from the environment for one table."""

    def __init__(self, table_id: str):
        settings = load_settings()
        self.settings = settings
        self.airtable = ScrapeAirtableClient(
            token=settings.airtable_token,
            base_id=settings.airtable_base_id,
            table_id=table_id,
        )
        self.akeneo = AkeneoClient(
            host=settings.akeneo_host,
            client_id=settings.akeneo_client_id,
            secret=settings.akeneo_secret,
            username=settings.akeneo_username,
            password=settings.akeneo_password,
            channel_name=os.getenv("CHANNEL_NAME", ""),
        )
        self.fal = FalClient(api_key=settings.fal_key)
        self.krea = KreaClient(token=settings.krea_token, base_url=settings.krea_base_url)
        self.table_id = table_id


# --------------------------------------------------------------------------
# 'CODE: value' text columns and '<CODE>_<sku>_<media>.png' attachment names
# --------------------------------------------------------------------------

def parse_coded_lines(value: Any) -> list[str]:
    """'CH: Aarhus\\nPE: Nova' -> ['aarhus', 'nova'] (lower-cased values without the code prefix)."""
    out: list[str] = []
    for line in str(value or "").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(re.sub(r"^[A-Z]{2}:\s*", "", line).strip().lower())
    return out


def attachment_code(att: dict[str, Any]) -> str:
    """Attachment filenames are '<CODE>_<sku>_<media>.png'; return the two-letter code or ''."""
    match = re.match(r"^([A-Z]{2})_", str(att.get("filename") or ""))
    return match.group(1) if match else ""


def coded_map(value: Any) -> dict[str, str]:
    """'CH: Aegnor\\nPE: Nova' -> {'CH': 'Aegnor', 'PE': 'Nova'}."""
    out: dict[str, str] = {}
    for line in str(value or "").splitlines():
        m = re.match(r"^([A-Z]{2}):\s*(.+)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


NOTES_MAX_CHARS = 300


def clean_item_notes(raw: Any, max_chars: int = NOTES_MAX_CHARS) -> str:
    """Akeneo description HTML -> one short plain-text line (dimensions and materials survive)."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(raw or "")))
    text = re.sub(r"\s+", " ", text).strip(" -|;:,")
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip(" -|;:,") + "..."
    return text


def product_notes(product: dict[str, Any]) -> str:
    values = (product.get("values") or {}).get("description") or []
    for entry in values:
        notes = clean_item_notes(entry.get("data") if isinstance(entry, dict) else entry)
        if notes:
            return notes
    return ""


def fixtures_from_record(
    fields: dict[str, Any],
    defs: Sequence[dict[str, str]],
    *,
    furniture_field: str = "Furniture Item",
    name_field: str = "Item Name",
    details_field: str = "Item Details",
) -> list[dict[str, str]]:
    """Ordered fixture dicts (code/label/name/notes/url) for the slots in ``defs``, from a row's fields.

    Cutout attachments are named '<CODE>_<sku>_<media>.png'; ``Item Name`` / ``Item Details`` hold one
    'CODE: value' line per fixture. Slots without a matching attachment are simply absent.
    """
    names = coded_map(fields.get(name_field))
    notes = coded_map(fields.get(details_field))
    by_code = {d["code"]: d for d in defs}
    order = {d["code"]: i for i, d in enumerate(defs)}
    items: list[dict[str, str]] = []
    for att in fields.get(furniture_field) or []:
        code = attachment_code(att)
        if code in by_code and att.get("url"):
            label = by_code[code]["label"]
            items.append({
                "code": code,
                "label": label,
                "name": names.get(code, label),
                "notes": notes.get(code, ""),
                "url": att["url"],
            })
    items.sort(key=lambda it: order[it["code"]])
    return items


# --------------------------------------------------------------------------
# Scraping
# --------------------------------------------------------------------------

def load_scrape_context(
    clients: PipelineClients,
    *,
    sku_field: str = "SKU",
    name_field: str = "Item Name",
) -> tuple[set[str], set[str], Any]:
    """(used SKUs, used names, Shopify index or None): base-wide dedup plus this table's coded lines."""
    base_names: set[str] = set()
    base_skus: set[str] = set()
    try:
        _, base_names, base_skus = fetch_all_base_existing_identities(clients.airtable)
        print(f"  [OK] Base-wide dedup: {len(base_skus)} SKU(s), {len(base_names)} title(s) registered.")
    except Exception as e:
        print(f"  [WARN] Base-wide dedup notice: {e}")

    try:
        for r in clients.airtable.list_records([sku_field, name_field]):
            f = r.get("fields", {})
            # SKU / Item Name hold one 'CODE: value' line per fixture in this table.
            base_skus.update(parse_coded_lines(f.get(sku_field)))
            base_names.update(parse_coded_lines(f.get(name_field)))
    except Exception:
        pass

    shopify_index = None
    try:
        print("  [INFO] Verifying live published catalog from Shopify (homecartel.net)...")
        shopify_index = ShopifyClient().load_published_identities()
        print(f"  [OK] Shopify Index loaded: {len(shopify_index.skus)} active published SKU(s).")
    except Exception as e:
        print(f"  [WARN] Shopify index skipped: {e}")
    return base_skus, base_names, shopify_index


def pick_fixture(
    clients: PipelineClients,
    fx: dict[str, str],
    style: str,
    base_skus: set[str],
    base_names: set[str],
    shopify_index: Any,
) -> dict[str, Any] | None:
    """Newest Akeneo item for one fixture slot that is unused, Shopify-active and downloadable.

    ``fx`` is ``{"code", "category", "label"}``. The caller adds the returned SKU/name to
    ``base_skus`` / ``base_names`` before picking the next slot, so two slots of the same category
    (for example the two kitchen pendants) never get the same item.
    """
    print(f"  [INFO] Querying Akeneo for '{fx['category']}'...")
    query: dict[str, Any] = {
        "categories": [{"operator": "IN", "value": [fx["category"]]}],
        "enabled": [{"operator": "=", "value": True}],
    }
    if style and style.lower() != "all":
        query["Style2"] = [{"operator": "IN", "value": [style]}]

    raw = clients.akeneo.fetch_products(query)
    raw.sort(key=lambda x: str(x.get("updated") or x.get("created") or ""), reverse=True)

    for product in raw:
        item = product_item(product)
        if not item:
            continue
        sku = (item.sku or "").strip()
        clean_name, _ = split_item_name((item.item_name or "").strip())
        if not sku or not item.media_code:
            continue
        if sku.lower() in base_skus or clean_name.lower() in base_names:
            continue
        if shopify_index and not shopify_index.contains(sku, clean_name):
            print(f"    [SKIP] {sku} ({clean_name}) is not active on Shopify.")
            continue
        try:
            cutout = clients.akeneo.download_media(item.media_code)
        except Exception as err:
            print(f"    [WARN] Failed to download media for {sku}: {err}")
            continue
        print(f"    [OK] {fx['label']}: {clean_name} (SKU {sku})")
        return {
            "code": fx["code"],
            "sku": sku,
            "clean_name": clean_name,
            "media_code": item.media_code,
            "cutout": cutout,
            "notes": product_notes(product),
        }
    return None


# --------------------------------------------------------------------------
# Krea
# --------------------------------------------------------------------------

def krea_generate_room(
    clients: PipelineClients,
    *,
    prompt: str,
    moodboard_id: str,
    aspect_ratio: str,
    fallback_aspect_ratio: str = "16:9",
    resolution: str = "1K",
) -> str:
    """Krea image URL; retries once at a safe ratio unless the error is really about the moodboard."""
    try:
        return clients.krea.generate(
            prompt=prompt, moodboard_id=moodboard_id, aspect_ratio=aspect_ratio, resolution=resolution
        )
    except ProviderError as err:
        # KreaClient words a real moodboard problem as "Krea moodboard '<id>' was not found ...".
        if moodboard_id and moodboard_id in str(err):
            raise
        print(f"  [WARN] Krea rejected {aspect_ratio} ({err}); retrying at {fallback_aspect_ratio}.")
        return clients.krea.generate(
            prompt=prompt, moodboard_id=moodboard_id, aspect_ratio=fallback_aspect_ratio, resolution=resolution
        )


# --------------------------------------------------------------------------
# Claude blending prompt
# --------------------------------------------------------------------------

BLEND_PROMPT_MIN_CHARS = 1200
BLEND_PROMPT_MAX_CHARS = 6000
_PREAMBLE_RE = re.compile(r"^\s*(here(?:'s| is)|sure|certainly|of course|below|okay|ok)\b", re.IGNORECASE)


def clean_blend_prompt(text: Any) -> str:
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", str(text or "").strip())
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    return cleaned.strip('"').strip()


def validate_blend_prompt(
    prompt: str,
    fixture_count: int,
    *,
    min_chars: int = BLEND_PROMPT_MIN_CHARS,
    max_chars: int = BLEND_PROMPT_MAX_CHARS,
) -> tuple[bool, str]:
    """(ok, reason). A usable prompt is long enough, names every Image 2..N and has no preamble/fences."""
    text = str(prompt or "").strip()
    if len(text) < min_chars:
        return False, f"it is only {len(text)} characters; write at least {min_chars}"
    if len(text) > max_chars:
        return False, f"it is {len(text)} characters; keep it under {max_chars}"
    if "```" in text or _PREAMBLE_RE.match(text):
        return False, "it contains markdown fences or a preamble; output only the prompt text"
    missing = [n for n in range(2, fixture_count + 2) if not re.search(rf"\bImage\s*{n}\b", text)]
    if missing:
        return False, "it never mentions " + ", ".join(f"Image {n}" for n in missing)
    return True, ""


def request_blend_prompt(
    clients: PipelineClients,
    *,
    instruction: str,
    image_urls: Sequence[str],
    fixture_count: int,
    fallback: str,
    min_chars: int = BLEND_PROMPT_MIN_CHARS,
    system_instruction: str = "You are an expert luxury interior lighting creative director for HomeCartel.",
) -> str:
    """Ask Claude Sonnet 5 (vision) for the blending prompt; validate, retry once, then use ``fallback``."""
    prompt = ""
    for attempt in (1, 2):
        try:
            candidate = clean_blend_prompt(clients.fal.generate_claude_vision(
                prompt=instruction,
                image_urls=list(image_urls),
                system_instruction=system_instruction,
                model=os.getenv("CLAUDE_VISION_MODEL", "").strip() or "anthropic/claude-sonnet-5",
            ))
        except Exception as err:
            print(f"  [WARN] Claude vision failed on attempt {attempt} ({err}).")
            continue
        ok, reason = validate_blend_prompt(candidate, fixture_count, min_chars=min_chars)
        if ok:
            prompt = candidate
            break
        print(f"  [WARN] Blending prompt attempt {attempt} rejected: {reason}.")
        instruction += f"\n\nYour previous answer was rejected because {reason}. Write the full prompt again, following every rule."
    if not prompt:
        print("  [WARN] Using the deterministic fallback prompt.")
        prompt = fallback
    return prompt


def nano_banana_blend(
    clients: PipelineClients,
    *,
    prompt: str,
    image_urls: Sequence[str],
    aspect_ratio: str,
    resolution: str,
) -> str:
    """Nano Banana Pro edit: returns the result image URL (jpeg)."""
    return clients.fal.generate(
        prompt=prompt,
        image_urls=list(image_urls),
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        model=os.getenv("FAL_BLENDING_MODEL", "").strip() or DEFAULT_FAL_MODEL,
        output_format="jpeg",
    )


# --------------------------------------------------------------------------
# Phase selection for --from-phase / --text-only / --only-phase
# --------------------------------------------------------------------------

FIRST_PHASE = 2  # phase 1 (scrape) only runs for a brand-new row
LAST_PHASE = 6
TEXT_PHASE = 5


def phases_to_run(
    from_phase: int = FIRST_PHASE,
    text_only: bool = False,
    only_phase: int | None = None,
    *,
    has_record: bool,
) -> list[int]:
    """The phase numbers (2-6) to run after phase 1. Raises AutomationError for invalid combinations.

    - default: 2..6 (a fresh row also runs phase 1 first)
    - ``from_phase=N`` / ``text_only`` (= 5): N..6, needs an existing record
    - ``only_phase=N``: just [N], needs an existing record, cannot be mixed with the others
    """
    valid = range(FIRST_PHASE, LAST_PHASE + 1)
    if only_phase is not None:
        if text_only or from_phase != FIRST_PHASE:
            raise AutomationError("--only-phase cannot be combined with --text-only or --from-phase.")
        if only_phase not in valid:
            raise AutomationError(f"--only-phase must be 2-6 (got {only_phase}).")
        if not has_record:
            raise AutomationError("--only-phase needs --record-id (it re-uses that row's existing images).")
        return [only_phase]
    start = TEXT_PHASE if text_only else from_phase
    if start not in valid:
        raise AutomationError(f"--from-phase must be 2-6 (got {start}).")
    if start > FIRST_PHASE and not has_record:
        raise AutomationError("--from-phase / --text-only need --record-id (they re-use that row's existing images).")
    return list(range(start, LAST_PHASE + 1))


def stale_output_note(only_phase: int | None, notes: dict[int, str]) -> str:
    """One-line reminder printed after a single-phase run whose later outputs are now out of date."""
    if only_phase is None:
        return ""
    return notes.get(only_phase, "")
