"""Foreign Key ID generator and table prefix mapping for HomeCartel marketing automation.

Format: <content idea abbreviation>-<content type>-<lighting fixture abbreviation>-<number of generation>
Examples:
  CTA-STORY-CH-1
  TNE-FEEDS-FL-1
  DN-STORY-PE-5
"""

from __future__ import annotations
import re
from typing import Any

# Standard Fixture Abbreviations
FIXTURE_ABBREVIATIONS = {
    "chandelier": "CH",
    "chandeliers": "CH",
    "pendant": "PE",
    "pendants": "PE",
    "pendant_light": "PE",
    "pendant_lights": "PE",
    "pendant lights": "PE",
    "floor_lamp": "FL",
    "floor_lamps": "FL",
    "floor lamp": "FL",
    "floor lamps": "FL",
    "table_lamp": "TL",
    "table_lamps": "TL",
    "table lamp": "TL",
    "table lamps": "TL",
    "cluster": "CL",
    "cluster_chandelier": "CL",
    "cluster_chandeliers": "CL",
    "cluster chandelier": "CL",
    "cluster chandeliers": "CL",
    "wall_light": "WL",
    "wall_lights": "WL",
    "wall light": "WL",
    "wall lights": "WL",
    "wall_sconces": "WL",
    "ceiling_mounted": "CM",
    "ceiling mounted": "CM",
}

# Table ID to Prefix Mapping
TABLE_PREFIX_MAP: dict[str, str] = {
    # 1. CTA Story
    "tblYHdVq14FjMWg5o": "CTA-STORY-CH",
    "tblfl7fqFZa2vUieB": "CTA-STORY-PE",
    "tblSpGJLO3faYfIDY": "CTA-STORY-CL",
    "tblKJeCCp4zQ6g7Em": "CTA-STORY-TL",
    "tblPKSYyjgbgMypE2": "CTA-STORY-FL",

    # 2. Tips & Educational Story
    "tblwnFN5a8fLzKuP4": "TNE-STORY-PE",
    "tblJxWwZexgBHl26B": "TNE-STORY-FL",
    "tblpFiaNn1Ym9fTTk": "TNE-STORY-CH",
    "tblGlRibUZXB9R3Gt": "TNE-STORY-CM",
    "tblZtENqILDAekLv2": "TNE-STORY-TL",
    "tbllzkE2prSyj9BaD": "TNE-STORY-CL",

    # 3. Collection Category Story
    "tblSSVJnubFk2yBm3": "CC-STORY-PE",
    "tbl98UU0h4uFyFIlL": "CC-STORY-WL",
    "tblJMJQlrnlDb1GtN": "CC-STORY-CH",
    "tblloZLRSKwOCg247": "CC-STORY-FL",
    "tblsXXcoZZD4q6WWt": "CC-STORY-CL",

    # 4. Day & Night Story
    "tblKkCf88UVQ3Yu07": "DN-STORY-CH",
    "tblaNyYZCR7E6TXtv": "DN-STORY-PE",
    "tblr1hlsjGcs9QKCy": "DN-STORY-FL",
    "tblhvM9Saq18YqONB": "DN-STORY-TL",
    "tblgcvB4WFKOpSIQl": "DN-STORY-CL",

    # 5. Moodboard Story
    "tblHQrci8d1K9ws2M": "MB-STORY-CH",
    "tblkm119i48y0M1IQ": "MB-STORY-PE",
    "tblBaNeiSZeYrUawW": "MB-STORY-FL",

    # 6. Product Specs Story
    "tblEGTB6BodRVDqBV": "PCS-STORY-CH",

    # 7. Style This? Story
    "tblYge5R7LwTJkEHC": "ST-STORY-CH",
    "tblvSAzXasTVI85r9": "ST-STORY-FL",

    # 8. Myth & Fact Story
    "tbl3OI7crWvN2Q7u6": "MNF-STORY-CH",
    "tblf5Yaki4ktwiLtx": "MNF-STORY-FL",
    "tblwBnWYRGcV6as45": "MNF-STORY-PE",

    # 9. Product Description Story
    "tblDcT6jovdAbKnfw": "PCD-STORY-CH",
    "tblDD2w4v0Idb4jAZ": "PCD-STORY-PE",
    "tblPvHyKGByWJCMtY": "PCD-STORY-FL",
    "tblnIOQVywHcTgAtv": "PCD-STORY-CL",
    "tbl5S9JEHSrjrLwxA": "PCD-STORY-TL",
    "tblYqudlgjYMNRROM": "PCD-STORY-WL",

    # 10. This or That Story
    "tblo42IkuhYLIQBzk": "TOT-STORY-CH",
    "tblS1VHp41RDfxztD": "TOT-STORY-PE",
    "tblaoqj8VPVHFmVQn": "TOT-STORY-FL",
    "tblYAhjKckXtjUayx": "TOT-STORY-CL",
    "tblm1Ty2QkAlUcHJt": "TOT-STORY-TL",
    "tblZw6jvSa27oZDiN": "TOT-STORY-WL",

    # 11. Feed Tables
    # Tips & Educational Feed
    "tblQ65S51Dmauwx4c": "TNE-FEEDS-CH",
    "tblIhCP3Gjg09QFCK": "TNE-FEEDS-PE",
    "tblQuhvktqYB59Ofw": "TNE-FEEDS-FL",
    "tblwY6eGQCD5bJeF1": "TNE-FEEDS-CL",

    # Collection Category Feed
    "tbl5o1j3XvUaUqmjs": "CC-FEEDS-SET",

    # Moodboard #1 Feed
    "tbl9u5vjgx8kuE44R": "MB1-FEEDS-CH",
    "tblOvvYdgsNTXh2zK": "MB1-FEEDS-PE",
    "tbl6uTmwM23KK9ocO": "MB1-FEEDS-FL",

    # Moodboard #2 Feed
    "tbltWgQKOYjuHw6tx": "MB2-FEEDS-CH",
    "tbl4TiV90SzdBz4KG": "MB2-FEEDS-PE",
    "tbl4YF9iXlBqGblEc": "MB2-FEEDS-FL",
    "tbljUk9JwzS1JeZJg": "MB2-FEEDS-WL",

    # 1 Product 3 Styles Feed
    "tblrlfqBGe5EjS5PI": "OP3S-FEEDS-CH",
    "tblRy52kCasisCWzd": "OP3S-FEEDS-PE",
    "tbl9GIq2QeYCwMhWU": "OP3S-FEEDS-FL",

    # Day and Night Feed
    "tblSceuLVvLMQ6wWp": "DN-FEEDS-CH",
    "tblIgRlTtO7Y2EGIo": "DN-FEEDS-PE",
    "tblcKHAVYgzIcmabT": "DN-FEEDS-FL",
    "tbljsKOEhc0618qbM": "DN-FEEDS-TL",

    # Product Showcase Feed
    "tbln0MNBaVVrZ0wrF": "PS-FEEDS-TL",

    # 12. Reel Tables
    # Product Closeup Reel
    "tblqBZ946hVdOpmDV": "PCR-REEL-TL",

    # Day & Night Reel
    "tblkTuM627s2f0FTN": "DN-REEL-PE",
    "tbl35JySlNuWh61tL": "DN-REEL-CH",
    "tblVPgI4C6HEFcKW9": "DN-REEL-FL",

    # Before & After Reel
    "tbleUP86Kw36G8Hdw": "BA-REEL-PE",
    "tbloMhCOngGDWFS2y": "BA-REEL-CH",

    # Style Reel Slideshow
    "tblFFEvkHb3jLKrcv": "SRS-REEL-SET",

    # Moodboard Reel
    "tbl026zbECJJ9FRfj": "MB-REEL-CH",
    "tblpjRudEy6fobIrP": "MB-REEL-PE",
    "tblJX6rd5nhhEuWbL": "MB-REEL-CL",
    "tblj4DVzllYa8pliK": "MB-REEL-LC",
    "tblF3ot4fdHN2VCQn": "MB-REEL-FL",
    "tbli7nuOEhR8inzva": "MB-REEL-WS",
    "tblr0uAYkDWDQZinl": "MB-REEL-TL",

    # 1 Product 3 Styles Reel
    "tbl6ls4AWcEcynBpZ": "OP3S-REEL-CH",
}


def resolve_fixture_abbr(fixture_name_or_key: str) -> str:
    """Map fixture identifier to standard 2-letter abbreviation."""
    norm = fixture_name_or_key.strip().lower().replace("-", "_").replace(" ", "_")
    for k, v in FIXTURE_ABBREVIATIONS.items():
        if k in norm:
            return v
    return "CH"


def resolve_table_prefix(table_id: str, table_name: str = "") -> str:
    """Resolve prefix for a given Airtable Table ID or name."""
    if table_id in TABLE_PREFIX_MAP:
        return TABLE_PREFIX_MAP[table_id]

    # Fallback heuristic using table name
    t_lower = table_name.lower()
    idea = "HC"
    if "cta" in t_lower:
        idea = "CTA"
    elif "tips" in t_lower or "edu" in t_lower:
        idea = "TNE"
    elif "collection" in t_lower:
        idea = "CC"
    elif "day and night" in t_lower or "day & night" in t_lower:
        idea = "DN"
    elif "moodboard" in t_lower:
        idea = "MB"
    elif "spec" in t_lower:
        idea = "PCS"
    elif "style this" in t_lower:
        idea = "ST"
    elif "myth" in t_lower or "fact" in t_lower:
        idea = "MNF"
    elif "description" in t_lower:
        idea = "PCD"
    elif "this or that" in t_lower:
        idea = "TOT"
    elif "1 product 3 style" in t_lower:
        idea = "OP3S"
    elif "product closeup" in t_lower:
        idea = "PCR"
    elif "before and after" in t_lower or "before & after" in t_lower:
        idea = "BA"
    elif "style reel" in t_lower or "slideshow" in t_lower:
        idea = "SRS"

    if "reel" in t_lower:
        content_type = "REEL"
    elif "feed" in t_lower:
        content_type = "FEEDS"
    else:
        content_type = "STORY"

    fixture = resolve_fixture_abbr(table_name)
    return f"{idea}-{content_type}-{fixture}"


def generate_foreign_key(table_id: str, row_id: Any, table_name: str = "") -> str:
    """Generate human readable Foreign Key ID (e.g. CTA-STORY-CH-1)."""
    prefix = resolve_table_prefix(table_id, table_name)
    row_num = str(row_id).strip() if row_id is not None else "0"
    return f"{prefix}-{row_num}"
