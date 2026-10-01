"""IsolatedAutomationSettings: dotenv files win, process env is the hosted fallback."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from content_automation.errors import ConfigurationError
from content_automation.isolated_config import IsolatedAutomationSettings

FULL_ENV = {
    "AIRTABLE_TOKEN": "tok",
    "AIRTABLE_BASE_ID": "app123",
    "AKENEO_HOST": "https://akeneo.example/",
    "AKENEO_CLIENT_ID": "cid",
    "AKENEO_SECRET": "sec",
    "AKENEO_USERNAME": "user",
    "AKENEO_PASSWORD": "pw",
    "CHANNEL_NAME": "channel",
    "KREA_API_TOKEN": "krea",
    "FAL_KEY": "fal",
}


class IsolatedConfigTests(unittest.TestCase):
    def test_environment_is_used_when_no_dotenv_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, FULL_ENV, clear=True):
            settings = IsolatedAutomationSettings.load("tips_edu_story", workspace=Path(tmp))
        self.assertEqual(settings.airtable_token, "tok")
        self.assertEqual(settings.akeneo_host, "https://akeneo.example")
        self.assertEqual(settings.style_code, "modern")

    def test_missing_environment_key_is_named(self):
        env = {k: v for k, v in FULL_ENV.items() if k != "FAL_KEY"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigurationError) as ctx:
                IsolatedAutomationSettings.load("tips_edu_story", workspace=Path(tmp))
        self.assertIn("FAL_KEY", str(ctx.exception))
        self.assertIn("process environment", str(ctx.exception))

    def test_dotenv_file_takes_precedence_over_environment(self):
        lines = [f"{k}=file-{k}" for k in FULL_ENV] + ["AKENEO_STYLE=classic"]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, FULL_ENV, clear=True):
            (Path(tmp) / ".env").write_text("\n".join(lines), encoding="utf-8")
            settings = IsolatedAutomationSettings.load("tips_edu_story", workspace=Path(tmp))
        self.assertEqual(settings.airtable_token, "file-AIRTABLE_TOKEN")
        self.assertEqual(settings.style_code, "classic")


if __name__ == "__main__":
    unittest.main()
