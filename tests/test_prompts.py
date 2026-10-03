import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autoterminal.config.loader import ConfigLoader
from autoterminal.config.prompts import DEFAULT_PROMPTS, LEGACY_PROMPTS, migrate_prompts


class PromptMigrationTests(unittest.TestCase):
    def test_legacy_defaults_updated_and_credentials_preserved(self):
        for old in LEGACY_PROMPTS:
            config = {
                "api_key": "test",
                "model": "custom-model",
                "base_url": "https://example.com",
                "default_prompt": old,
            }
            updated = migrate_prompts(config)
            self.assertEqual(
                updated["default_prompt"], DEFAULT_PROMPTS["default_prompt"]
            )
            for key in ("api_key", "model", "base_url"):
                self.assertEqual(updated[key], config[key])

    def test_custom_prompts_preserved_and_previous_snapshot_upgraded(self):
        config = {
            "default_prompt": "用户自己写的内容",
            "recommendation_prompt": "旧版默认",
            "prompt_defaults": {"recommendation_prompt": "旧版默认"},
        }
        updated = migrate_prompts(config)
        self.assertEqual(updated["default_prompt"], config["default_prompt"])
        self.assertEqual(
            updated["recommendation_prompt"], DEFAULT_PROMPTS["recommendation_prompt"]
        )
        self.assertEqual(migrate_prompts(updated), updated)

    def test_load_persists_migration_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"api_key": "test"}))
            updated = ConfigLoader(str(path)).get_config()
            self.assertEqual(json.loads(path.read_text()), updated)
            with patch("autoterminal.config.loader.write_json") as write:
                self.assertEqual(ConfigLoader(str(path)).get_config(), updated)
                write.assert_not_called()

    def test_read_only_config_still_uses_new_defaults(self):
        with (
            patch.object(
                ConfigLoader, "load_from_file", return_value={"api_key": "test"}
            ),
            patch("autoterminal.config.loader.write_json", side_effect=PermissionError),
        ):
            updated = ConfigLoader("unused").get_config()
            self.assertEqual(
                updated["recommendation_prompt"],
                DEFAULT_PROMPTS["recommendation_prompt"],
            )
