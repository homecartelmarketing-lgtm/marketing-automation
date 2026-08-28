"""Resolving the connection and destination settings for one category scrape."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..config import Settings, load_settings
from ..errors import ConfigurationError
from . import categories


@dataclass(frozen=True)
class ScrapeSettings:
    """Everything one category's scrape needs, already validated."""

    airtable_token: str
    airtable_base_id: str
    airtable_table_id: str
    channel_name: str
    akeneo_host: str
    akeneo_client_id: str
    akeneo_secret: str
    akeneo_username: str
    akeneo_password: str
    category_code: str
    style_code: str

    @property
    def category_label(self) -> str:
        return categories.category_label(self.category_code)


def load_scrape_settings(
    category_code: str | None = None,
    style_code: str | None = None,
    table_id_override: str | None = None,
    settings: Settings | None = None,
) -> ScrapeSettings:
    """Build ScrapeSettings from the environment, failing fast on gaps."""
    base = settings or load_settings()
    base.require({"airtable", "akeneo"})

    channel_name = (os.environ.get("CHANNEL_NAME") or "").strip()
    style = (style_code or os.environ.get("AKENEO_STYLE") or "").strip()
    missing = [
        name
        for name, value in (("CHANNEL_NAME", channel_name), ("AKENEO_STYLE", style))
        if not value
    ]
    if missing:
        raise ConfigurationError(
            "Missing required .env settings: " + ", ".join(missing)
        )

    category = (category_code or os.environ.get("AKENEO_CATEGORY") or "").strip()
    if not category:
        raise ConfigurationError(
            "Missing target category. Pass --category or set AKENEO_CATEGORY in .env"
        )

    table_id = (table_id_override or "").strip() or categories.table_id_for_category(
        category,
        fallback_table_id=(os.environ.get("AIRTABLE_TABLE_ID") or "").strip(),
    )
    if not table_id:
        raise ConfigurationError(
            f"Missing Airtable Table ID for category '{category}'. Define it in .env"
        )

    return ScrapeSettings(
        airtable_token=base.airtable_token,
        airtable_base_id=base.airtable_base_id,
        airtable_table_id=table_id,
        channel_name=channel_name,
        akeneo_host=base.akeneo_host,
        akeneo_client_id=base.akeneo_client_id,
        akeneo_secret=base.akeneo_secret,
        akeneo_username=base.akeneo_username,
        akeneo_password=base.akeneo_password,
        category_code=category,
        style_code=style,
    )
