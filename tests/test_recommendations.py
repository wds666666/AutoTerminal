import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from autoterminal.llm.client import LLMClient
from autoterminal.recommendations import EmptyRecommendationCache, is_self_install


class RecommendationTests(unittest.TestCase):
    def test_install_fast_path_does_not_hide_failure_or_typo(self):
        self.assertTrue(
            is_self_install(
                {
                    "command": "uv tool install --force autoterminal==1.1.1",
                    "returncode": None,
                }
            )
        )
        self.assertFalse(
            is_self_install(
                {"command": "uv tool install autoterminal", "returncode": 1}
            )
        )
        self.assertFalse(is_self_install({"command": "atp list --upgradable"}))

    def test_empty_cache_expiry_and_changed_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            context = {"shell_history": ["atp install", "at"]}
            cache = EmptyRecommendationCache({"model": "a"}, context, path)
            self.assertFalse(cache.hit())
            with patch("autoterminal.recommendations.time.time", return_value=100):
                cache.remember()
                self.assertTrue(cache.hit())
                self.assertTrue(
                    EmptyRecommendationCache(
                        {"model": "a"},
                        {"shell_history": ["atp install", "at --show-context"]},
                        path,
                    ).hit()
                )
                self.assertFalse(
                    EmptyRecommendationCache({"model": "b"}, context, path).hit()
                )
            with patch("autoterminal.recommendations.time.time", return_value=221):
                self.assertFalse(cache.hit())

    def test_recommendation_timeout_no_retries_and_no_command_marker(self):
        with patch("autoterminal.llm.client.OpenAI") as sdk:
            create = sdk.return_value.with_options.return_value.chat.completions.create
            create.return_value = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content="NO_COMMAND"),
                    )
                ]
            )
            client = LLMClient(
                {"api_key": "test", "base_url": "https://example.com", "model": "test"}
            )
            self.assertEqual(client.generate_command(""), "")
            sdk.return_value.with_options.assert_called_once_with(
                timeout=8, max_retries=0
            )
            self.assertEqual(create.call_args.kwargs["max_tokens"], 1024)

    def test_cli_self_install_skips_network(self):
        import contextlib
        import importlib
        import io
        import sys

        main = importlib.import_module("autoterminal.main")
        with (
            patch.object(sys, "argv", ["at"]),
            patch.object(main, "ConfigLoader") as loader,
            patch.object(main, "LLMClient") as client,
            patch.object(main, "get_shell_session", return_value={}),
            patch.object(
                main,
                "get_shell_history",
                return_value=["uv tool install --force autoterminal==1.1.1", "at"],
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            loader.return_value.get_config.return_value = {
                "api_key": "test",
                "base_url": "https://example.com",
                "model": "test",
            }
            self.assertEqual(main.main(), 0)
            client.assert_not_called()
