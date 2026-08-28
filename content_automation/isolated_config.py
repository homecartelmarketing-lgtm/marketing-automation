"""Configuration for automations that must not read the shared ``.env`` file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from .errors import ConfigurationError


WORKSPACE = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class IsolatedAutomationSettings:
    """Provider settings loaded exclusively from one named dotenv file."""

    workspace: Path
    env_path: Path
    automation: str
    airtable_token: str
    airtable_base_id: str
    akeneo_host: str
    akeneo_client_id: str
    akeneo_secret: str
    akeneo_username: str
    akeneo_password: str
    channel_name: str
    style_code: str
    krea_token: str
    krea_base_url: str
    qwen_api_key: str
    qwen_base_url: str
    fal_key: str
    output_dir: Path

    @classmethod
    def load(
        cls,
        automation: str,
        *,
        env_path: Path | None = None,
        workspace: Path | None = None,
    ) -> "IsolatedAutomationSettings":
        workspace = (workspace or WORKSPACE).resolve()
        expected = {
            "day_night_reel": (
                ".env.day-night-reel",
                "DAY_NIGHT_REEL_QWEN_API_KEY",
                True,
            ),
            "tips_edu_story": (
                ".env.tips-edu-story",
                "TIPS_EDU_STORY_QWEN_API_KEY",
                True,
            ),
        }
        if automation not in expected:
            raise ValueError(f"Unsupported isolated automation: {automation}")
        filename, qwen_key_name, requires_fal = expected[automation]
        source = (env_path or workspace / filename).resolve()
        if not source.is_file():
            raise ConfigurationError(
                f"Missing isolated configuration: {source}. Copy the matching .example file first."
            )

        # dotenv_values reads this file directly. It intentionally does not
        # consult process variables or the repository's shared .env file.
        raw = {
            str(key): str(value or "").strip()
            for key, value in dotenv_values(source).items()
            if key
        }
        required = {
            "AIRTABLE_TOKEN",
            "AIRTABLE_BASE_ID",
            "AKENEO_HOST",
            "AKENEO_CLIENT_ID",
            "AKENEO_SECRET",
            "AKENEO_USERNAME",
            "AKENEO_PASSWORD",
            "CHANNEL_NAME",
            "AKENEO_STYLE",
            "KREA_API_TOKEN",
            qwen_key_name,
        }
        if requires_fal:
            required.add("FAL_KEY")
        missing = sorted(name for name in required if not raw.get(name))
        if missing:
            raise ConfigurationError(
                f"Missing required values in {source.name}: " + ", ".join(missing)
            )

        configured_output = raw.get("CONTENT_AUTOMATION_OUTPUT_DIR", "output/content")
        output_dir = Path(configured_output)
        if not output_dir.is_absolute():
            output_dir = workspace / output_dir
        return cls(
            workspace=workspace,
            env_path=source,
            automation=automation,
            airtable_token=raw["AIRTABLE_TOKEN"],
            airtable_base_id=raw["AIRTABLE_BASE_ID"],
            akeneo_host=raw["AKENEO_HOST"].rstrip("/"),
            akeneo_client_id=raw["AKENEO_CLIENT_ID"],
            akeneo_secret=raw["AKENEO_SECRET"],
            akeneo_username=raw["AKENEO_USERNAME"],
            akeneo_password=raw["AKENEO_PASSWORD"],
            channel_name=raw["CHANNEL_NAME"],
            style_code=raw["AKENEO_STYLE"],
            krea_token=raw["KREA_API_TOKEN"],
            krea_base_url=raw.get("KREA_API_BASE", "https://api.krea.ai").rstrip("/"),
            qwen_api_key=raw[qwen_key_name],
            qwen_base_url=raw.get(
                "QWEN_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ).rstrip("/"),
            fal_key=raw.get("FAL_KEY", ""),
            output_dir=output_dir,
        )
