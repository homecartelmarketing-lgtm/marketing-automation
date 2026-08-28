"""Which Akeneo category feeds which Airtable table, and how rows are filtered.

Table ids, labels and moodboard env names are *not* redefined here -- they come
from ``config.TABLES``, which is the one registry of destinations. This module
only adds the facts that are specific to scraping: where a category's products
come from in Akeneo, and which of them belong in the destination table.
"""

from __future__ import annotations

import os

from ..config import TABLES
from ..fields import DEFAULT_ITEMS_PER_ROW


# Order is the scrape order for `--category all`. The Tips & Educational table
# is populated by its dedicated three-product feed workflow, not the generic
# Akeneo row packer.
SCRAPE_CATEGORIES: tuple[str, ...] = tuple(
    code
    for code in TABLES
    if code not in {
        "chandeliers_tips_educational_feed",
        # Populated by the category-locked four-column StyleThisRunner.
        "style_this",
    }
)

# Purpose-specific destinations keep the exact number of products consumed by
# their workflow.  Anything absent is a normal product table and gets ten
# products per row.
ITEMS_PER_ROW: dict[str, int] = {
    "pendant_lights": 1,
    "chandeliers_day_night_4_5": 1,
    "chandeliers_day_night_reel": 1,
    "floor_lamps_day_night_reel": 1,
    "pendant_lights_day_night_reel": 1,
    "cta_story": 1,
    "chandelier_cta_story": 1,
    "pendant_lights_cta_story": 1,
    "floor_lamp_cta_story": 1,
    "cluster_chandelier_cta_story": 1,
    "table_lamps_cta_story": 1,
    "wall_lights_cta_story": 1,
    "pendant_lights_tips_edu_story": 1,
    "floor_lamps_tips_edu_story": 1,
    "chandeliers_tips_edu_story": 1,
    "ceiling_mounted_tips_edu_story": 1,
    "table_lamps_tips_edu_story": 1,
    "cluster_chandeliers_tips_edu_story": 1,
    "product_description_story": 1,
    "chandelier_product_description_story": 1,
    "chandelier_myth_and_fact_story": 1,
    "myth_and_fact_story": 1,
    "pendant_lights_product_description_story": 1,
    "floor_lamp_product_description_story": 1,
    "cluster_chandelier_product_description_story": 1,
    "table_lamps_product_description_story": 1,
    "wall_lights_product_description_story": 1,
    # Day & Night Story destinations
    "day_night_story": 1,
    "chandelier_day_night_story": 1,
    "chandeliers_day_night_story": 1,
    "pendant_lights_day_night_story": 1,
    "table_lamps_day_night_story": 1,
    "floor_lamps_day_night_story": 1,
    "cluster_chandelier_day_night_story": 1,
    "cluster_chandeliers_day_night_story": 1,
    "chandeliers_this_or_that": 2,
    "pendant_lights_this_or_that": 2,
    "floor_lamp_this_or_that": 2,
    "cluster_chandelier_this_or_that": 2,
    "table_lamps_this_or_that": 2,
    "wall_lights_this_or_that": 2,
    "table_lamps": 4,
    "chandelier_modern": 4,
    "pendant_lights_reel": 4,
    "cluster_chandeliers_reel": 4,
    "linear_chandeliers_reel": 4,
    "floor_lamps_reel": 4,
    "wall_sconces_reel": 4,
    "table_lamps_reel": 4,
    "chandelier_collec_story": 3,
    "pendant_lights_collec_story": 3,
    "cluster_chandeliers_collec_story": 3,
    "linear_chandeliers_collec_story": 3,
    "floor_lamps_collec_story": 3,
    "table_lamps_collec_story": 3,
    "wall_sconces_collec_story": 3,
}

# Some Airtable destinations are subsets of a broader Akeneo category and have
# no category of their own in the PIM. They read from a shared source category
# and then narrow it with the inclusion keywords below.
AKENEO_SOURCE_CATEGORY: dict[str, str] = {
    "ceiling_mounted": "chandeliers",
    "chandeliers_day_night_4_5": "chandeliers",
    "chandeliers_day_night_reel": "chandeliers",
    "floor_lamps_day_night_reel": "floor_lamps",
    "pendant_lights_day_night_reel": "pendant_lights",
    "wall_sconces_collec_story": "wall_lights",
    "pendant_lights_collec_story": "pendant_lights",
    "chandelier_collec_story": "chandeliers",
    "cluster_chandeliers_collec_story": "cluster_chandeliers",
    "linear_chandeliers_collec_story": "linear_chandeliers",
    "floor_lamps_collec_story": "floor_lamps",
    "table_lamps_collec_story": "table_lamps",
    # CTA Story destinations
    "cta_story": "cluster_chandeliers",
    "chandelier_cta_story": "chandeliers",
    "pendant_lights_cta_story": "pendant_lights",
    "floor_lamp_cta_story": "floor_lamps",
    "cluster_chandelier_cta_story": "cluster_chandeliers",
    "table_lamps_cta_story": "table_lamps",
    "wall_lights_cta_story": "wall_lights",

    # Product Closeup w/ Description destinations
    "product_description_story": "chandeliers",
    "chandelier_product_description_story": "chandeliers",
    "chandelier_myth_and_fact_story": "chandeliers",
    "myth_and_fact_story": "chandeliers",
    "pendant_lights_product_description_story": "pendant_lights",
    "floor_lamp_product_description_story": "floor_lamps",
    "cluster_chandelier_product_description_story": "cluster_chandeliers",
    "table_lamps_product_description_story": "table_lamps",
    "wall_lights_product_description_story": "wall_lights",

    # Day & Night Story destinations
    "day_night_story": "chandeliers",
    "chandelier_day_night_story": "chandeliers",
    "chandeliers_day_night_story": "chandeliers",
    "pendant_lights_day_night_story": "pendant_lights",
    "table_lamps_day_night_story": "table_lamps",
    "floor_lamps_day_night_story": "floor_lamps",
    "cluster_chandelier_day_night_story": "cluster_chandeliers",
    "cluster_chandeliers_day_night_story": "cluster_chandeliers",
    # Akeneo files linear chandeliers under the general Chandelier category.
    "linear_chandeliers": "chandeliers",
    # The destination is named Wall Sconce; Akeneo groups the same products
    # (Wall Light, Wall Lamp, ...) under Wall Lights.
    "wall_sconces": "wall_lights",
    # Chandelier Modern reads from the same Akeneo chandeliers category.
    "chandelier_modern": "chandeliers",
    # This or That destinations
    "chandeliers_this_or_that": "chandeliers",
    "pendant_lights_this_or_that": "pendant_lights",
    "floor_lamp_this_or_that": "floor_lamps",
    "cluster_chandelier_this_or_that": "cluster_chandeliers",
    "table_lamps_this_or_that": "table_lamps",
    "wall_lights_this_or_that": "wall_lights",
    # Moodboard reel destinations have no category of their own in the PIM
    # either; each reads the same Akeneo category as the product table it
    # mirrors, so every one of them needs an entry here.
    "pendant_lights_reel": "pendant_lights",
    "cluster_chandeliers_reel": "cluster_chandeliers",
    "linear_chandeliers_reel": "chandeliers",
    "floor_lamps_reel": "floor_lamps",
    "wall_sconces_reel": "wall_lights",
    "table_lamps_reel": "table_lamps",
}

# Env overrides for the category code to send to Akeneo. Keys are *source*
# categories, i.e. post-`AKENEO_SOURCE_CATEGORY` resolution.
AKENEO_CATEGORY_ENV: dict[str, str] = {
    "chandeliers": "AKENEO_CATEGORY_CHANDELIERS",
    "pendant_lights": "AKENEO_CATEGORY_PENDANT_LIGHTS",
    "floor_lamps": "AKENEO_CATEGORY_FLOOR_LAMPS",
    "wall_lights": "AKENEO_CATEGORY_WALL_LIGHTS",
    "cluster_chandeliers": "AKENEO_CATEGORY_CLUSTER_CHANDELIERS",
}

# Products to drop from a category, by Akeneo category or by item-name keyword.
CATEGORY_EXCLUSIONS: dict[str, dict[str, set[str]]] = {
    "chandeliers": {
        "categories": {"cluster_chandeliers", "linear_chandeliers"},
        "keywords": {"cluster", "linear"},
    },
    "chandelier_modern": {
        "categories": {"cluster_chandeliers", "linear_chandeliers"},
        "keywords": {"cluster", "linear"},
    },
    "moodboard_1_feed": {
        "categories": {"cluster_chandeliers", "linear_chandeliers"},
        "keywords": {"cluster", "linear"},
    },
}

# Products to keep from a shared source category. When a category appears here,
# an item must match at least one keyword to survive.
CATEGORY_INCLUSIONS: dict[str, dict[str, set[str]]] = {
    "linear_chandeliers": {
        "keywords": {"linear chandelier"},
    },
    "linear_chandeliers_reel": {
        "keywords": {"linear chandelier"},
    },
}


def _env_override(env_var: str) -> str:
    val = (os.environ.get(env_var) or "").strip()
    if "input here" in val.lower() or "your_" in val.lower():
        return ""
    return val


def category_label(category_code: str) -> str:
    """Human-facing name for a category, e.g. "Linear Chandelier"."""
    table = TABLES.get(category_code)
    return table.label if table else category_code


def items_per_row(category_code: str) -> int:
    if category_code in ITEMS_PER_ROW:
        return ITEMS_PER_ROW[category_code]
    from ..config import REEL_TABLES
    for preset in REEL_TABLES.values():
        if category_code == preset.get("table_code"):
            return 1
    return DEFAULT_ITEMS_PER_ROW


def akeneo_category_code(category_code: str) -> str:
    """The category code to query Akeneo with for a destination category."""
    if category_code in AKENEO_SOURCE_CATEGORY:
        source = AKENEO_SOURCE_CATEGORY[category_code]
    else:
        from ..config import REEL_TABLES
        source = category_code
        for preset in REEL_TABLES.values():
            if category_code == preset.get("table_code"):
                source = preset.get("category_code", category_code)
                break
    env_var = AKENEO_CATEGORY_ENV.get(source)
    if env_var and (override := _env_override(env_var)):
        return override
    return source


def table_id_for_category(category_code: str, fallback_table_id: str = "") -> str:
    """Airtable table id for a category.

    The env var is re-read on each call rather than trusting the value captured
    at import, so editing .env does not depend on module import order.
    """
    table = TABLES.get(category_code)
    if table is None:
        return fallback_table_id
    if override := _env_override(table.table_env):
        return override
    return table.table_id or fallback_table_id


def moodboard_id_for_category(category_code: str, fallback: str = "") -> str:
    """Krea moodboard id for a category.

    Falls back to the shared ``KREA_MOODBOARD_ID`` when the category has no
    moodboard of its own, so a single board can cover every table.
    """
    table = TABLES.get(category_code)
    if table and (value := _env_override(table.moodboard_env)):
        return value
    if shared := _env_override("KREA_MOODBOARD_ID"):
        return shared
    return fallback


def excluded_categories(category_code: str) -> set[str]:
    if category_code in CATEGORY_EXCLUSIONS:
        return CATEGORY_EXCLUSIONS[category_code].get("categories", set())
    if category_code in CATEGORY_INCLUSIONS:
        return set()
    source = AKENEO_SOURCE_CATEGORY.get(category_code, category_code)
    return CATEGORY_EXCLUSIONS.get(source, {}).get("categories", set())


def excluded_keywords(category_code: str) -> set[str]:
    if category_code in CATEGORY_EXCLUSIONS:
        return CATEGORY_EXCLUSIONS[category_code].get("keywords", set())
    if category_code in CATEGORY_INCLUSIONS:
        return set()
    source = AKENEO_SOURCE_CATEGORY.get(category_code, category_code)
    return CATEGORY_EXCLUSIONS.get(source, {}).get("keywords", set())


def included_keywords(category_code: str) -> set[str]:
    return CATEGORY_INCLUSIONS.get(category_code, {}).get("keywords", set())
