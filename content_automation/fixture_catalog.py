"""Single source of truth for per-pipeline fixture wiring (pilot: CTA Story).

One entry per (pipeline, fixture) holds the Airtable table, the FK prefix,
the canonical Krea moodboard / prompt env keys, and the default moodboard /
prompt. Routes, generators, the frontend fixture list, and docs must all agree
with this module — `tests/test_cta_catalog_consistency.py` enforces it.

Decisions frozen 2026-10-05 (see docs/REDFLAG_REPORT.md):
- CTA table-lamp moodboard winner: ``257569e1-7be8-4412-a90f-acbc347e4646``
  (docs + generator agreed; route/``fixtures.ts`` ``351d992d`` and
  ``.env.example`` ``fb2487fb`` were orphans).
- CTA wall-light stays ``parked`` (config-only, no Studio card yet).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def load_studio_overrides() -> dict[str, str]:
    """Overlay Studio-saved settings onto ``os.environ``.

    Mirrors ``UI Control/routes/common.py`` startup behavior so standalone CLI
    runs see the same values as server-spawned runs without touching ``.env``.
    Missing/unreadable file is a silent no-op.
    """
    markers = (
        Path(__file__).resolve().parent.parent / "output" / "config_overrides.json",
    )
    extra = os.getenv("CONFIG_OVERRIDES_PATH", "").strip()
    paths = [Path(extra)] if extra else []
    paths.extend(markers)
    for candidate in paths:
        try:
            if candidate.is_file():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for key, value in data.items():
                        if value is not None:
                            os.environ.setdefault(str(key), str(value))
                    return {str(k): str(v) for k, v in data.items() if v is not None}
        except Exception:
            continue
    return {}


# Applied on import so every consumer (routes, generators, tests) shares it.
load_studio_overrides()


@dataclass(frozen=True)
class FixtureEntry:
    """Wiring for one (pipeline, fixture)."""

    pipeline: str
    fixture_id: str
    name: str
    table_id: str
    table_env_keys: tuple[str, ...] = ()
    category_code: str = ""
    fk_prefix: str = ""
    moodboard_env_key: str = ""
    moodboard_alias_keys: tuple[str, ...] = ()
    default_moodboard_id: str = ""
    prompt_env_key: str = ""
    prompt_alias_keys: tuple[str, ...] = ()
    default_prompt: str = ""
    total: int = 100
    status: str = "active"  # "active" | "parked"


CTA_FIXTURES: tuple[FixtureEntry, ...] = (
    FixtureEntry(
        pipeline="cta-story",
        fixture_id="chandelier",
        name="Chandelier",
        table_id="tblYHdVq14FjMWg5o",
        table_env_keys=("AIRTABLE_TABLE_ID_CHANDELIER_CTA", "AIRTABLE_TABLE_ID_CTA_STORY"),
        category_code="chandelier_cta_story",
        fk_prefix="CTA-STORY-CH",
        moodboard_env_key="KREA_MOODBOARD_ID_CHANDELIER_CTA",
        moodboard_alias_keys=("KREA_MOODBOARD_ID_CHANDELIERS",),
        default_moodboard_id="de6ad512-870d-4ab7-a48c-3f3ca85faf24",
        prompt_env_key="CTA_PROMPT_CHANDELIER",
        prompt_alias_keys=("PROMPT_CHANDELIER",),
        default_prompt="Generate me a modern living room",
    ),
    FixtureEntry(
        pipeline="cta-story",
        fixture_id="pendant",
        name="Pendant Lights",
        table_id="tblfl7fqFZa2vUieB",
        table_env_keys=("AIRTABLE_TABLE_ID_PENDANT_LIGHTS_CTA",),
        category_code="pendant_lights_cta_story",
        fk_prefix="CTA-STORY-PE",
        moodboard_env_key="KREA_MOODBOARD_ID_PENDANT_LIGHTS_CTA",
        moodboard_alias_keys=("KREA_MOODBOARD_ID_PENDANT_LIGHTS",),
        default_moodboard_id="0844ad92-c34a-4dc8-9d70-d09498dc098c",
        prompt_env_key="CTA_PROMPT_PENDANT_LIGHTS",
        prompt_alias_keys=("PROMPT_PENDANT_LIGHTS",),
        default_prompt="Generate me a modern dining room",
    ),
    FixtureEntry(
        pipeline="cta-story",
        fixture_id="cluster-chandelier",
        name="Cluster Chandelier",
        table_id="tblSpGJLO3faYfIDY",
        table_env_keys=("AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_CTA",),
        category_code="cluster_chandelier_cta_story",
        fk_prefix="CTA-STORY-CL",
        moodboard_env_key="KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_CTA",
        moodboard_alias_keys=(
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        default_moodboard_id="b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        prompt_env_key="CTA_PROMPT_CLUSTER_CHANDELIER",
        prompt_alias_keys=("PROMPT_CLUSTER_CHANDELIER",),
        default_prompt=(
            "Modern high-ceiling room interior, luxury contemporary architecture, "
            "warm neutral tones, clean open ceiling space ready for cluster "
            "chandelier integration, photorealistic 8k vertical portrait"
        ),
    ),
    FixtureEntry(
        pipeline="cta-story",
        fixture_id="table-lamp",
        name="Table Lamps",
        table_id="tblKJeCCp4zQ6g7Em",
        table_env_keys=("AIRTABLE_TABLE_ID_TABLE_LAMPS_CTA",),
        category_code="table_lamps_cta_story",
        fk_prefix="CTA-STORY-TL",
        moodboard_env_key="KREA_MOODBOARD_ID_TABLE_LAMPS_CTA",
        moodboard_alias_keys=(
            "KREA_MOODBOARD_ID_TABLE_LAMPS_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        default_moodboard_id="257569e1-7be8-4412-a90f-acbc347e4646",
        prompt_env_key="CTA_PROMPT_TABLE_LAMPS",
        prompt_alias_keys=("PROMPT_TABLE_LAMPS",),
        default_prompt="Generate me a modern bedroom with a table lamp side by side",
    ),
    FixtureEntry(
        pipeline="cta-story",
        fixture_id="floor-lamp",
        name="Floor Lamp",
        table_id="tblPKSYyjgbgMypE2",
        table_env_keys=(
            "AIRTABLE_TABLE_ID_FLOOR_LAMPS_CTA",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_CTA",
        ),
        category_code="floor_lamp_cta_story",
        fk_prefix="CTA-STORY-FL",
        moodboard_env_key="KREA_MOODBOARD_ID_FLOOR_LAMP_CTA",
        moodboard_alias_keys=(
            "KREA_MOODBOARD_ID_FLOOR_LAMPS_CTA",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        default_moodboard_id="c4c15a18-a92d-4465-924f-c85cfe1958bc",
        prompt_env_key="CTA_PROMPT_FLOOR_LAMPS",
        prompt_alias_keys=("PROMPT_FLOOR_LAMPS",),
        default_prompt=(
            "Modern living room interior, stylish lounge chair, warm ambient "
            "lighting, spacious floor corner ready for floor lamp integration, "
            "photorealistic 8k vertical portrait"
        ),
    ),
    FixtureEntry(
        pipeline="cta-story",
        fixture_id="wall-light",
        name="Wall Light",
        table_id="tblsllKrNcffItIua",
        table_env_keys=("AIRTABLE_TABLE_ID_WALL_LIGHTS_CTA",),
        category_code="wall_lights_cta_story",
        fk_prefix="CTA-STORY-WL",
        moodboard_env_key="KREA_MOODBOARD_ID_WALL_SCONCE",
        moodboard_alias_keys=(),
        default_moodboard_id="",
        prompt_env_key="CTA_PROMPT_WALL_LIGHTS",
        prompt_alias_keys=(),
        default_prompt="",
        status="parked",
    ),
)

CATALOG: dict[tuple[str, str], FixtureEntry] = {
    (entry.pipeline, entry.fixture_id): entry for entry in CTA_FIXTURES
}


def get_fixture(pipeline: str, fixture_id: str) -> FixtureEntry:
    """Return the catalog entry for a (pipeline, fixture); raises KeyError."""
    return CATALOG[(pipeline, fixture_id)]


def _first_set(keys: tuple[str, ...]) -> str:
    for key in keys:
        if not key:
            continue
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def resolve_table_id(entry: FixtureEntry) -> str:
    """Canonical table env key first, then legacy aliases, then catalog default."""
    return _first_set(entry.table_env_keys) or entry.table_id


def resolve_moodboard_id(entry: FixtureEntry) -> str:
    """Canonical moodboard env key first, then aliases, then catalog default."""
    return _first_set((entry.moodboard_env_key,) + entry.moodboard_alias_keys) or entry.default_moodboard_id


def resolve_prompt(entry: FixtureEntry) -> str:
    """Canonical prompt env key first, then aliases, then catalog default."""
    return _first_set((entry.prompt_env_key,) + entry.prompt_alias_keys) or entry.default_prompt


def active_fixtures(pipeline: str) -> tuple[FixtureEntry, ...]:
    """Catalog entries with ``status == "active"`` for a pipeline."""
    return tuple(e for e in CTA_FIXTURES if e.pipeline == pipeline and e.status == "active")


def fixture_dict(entry: FixtureEntry) -> dict:
    """Shape compatible with the legacy ``get_*_fixtures()`` dicts."""
    return {
        "id": entry.fixture_id,
        "name": entry.name,
        "table_id": resolve_table_id(entry),
        "category_code": entry.category_code,
        "moodboard_id": resolve_moodboard_id(entry),
        "prompt": resolve_prompt(entry),
        "total": entry.total,
    }
