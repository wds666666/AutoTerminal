import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from autoterminal.config.loader import ConfigLoader
from autoterminal.config.manager import ConfigManager
from autoterminal.config.providers import PROVIDERS, fetch_models
from autoterminal.history import HistoryManager
from autoterminal.llm.client import LLMClient
from autoterminal.main import main
from autoterminal.utils.helpers import (
    clean_command,
    get_directory_context,
    get_shell_history,
)

main_module = importlib.import_module("autoterminal.main")


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = {
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
            "model": "test-model",
        }

    def test_provider_wizards(self):
        for number, (provider, (_, url)) in enumerate(PROVIDERS.items(), 1):
            with (
                self.subTest(provider=provider),
                patch("builtins.input", side_effect=[str(number), "2"]),
                patch("autoterminal.config.manager.getpass", return_value="key"),
                patch(
                    "autoterminal.config.manager.fetch_models", return_value=["a", "b"]
                ) as fetch,
            ):
                manager = ConfigManager(str(self.path / provider / "config.json"))
                config = manager.initialize_config()
                self.assertEqual(config["model"], "b")
                self.assertEqual(config["base_url"], url)
                fetch.assert_called_once_with("key", url)
                self.assertEqual(ConfigLoader(manager.config_file).get_config(), config)
                self.assertEqual(os.stat(manager.config_file).st_mode & 0o777, 0o600)

    def test_model_failure_and_partial_config(self):
        with (
            patch("builtins.input", return_value="manual-model"),
            patch("autoterminal.config.manager.fetch_models", side_effect=TimeoutError),
        ):
            config = ConfigManager(str(self.path / "config.json")).get_or_create_config(
                {**self.config, "model": ""}
            )
        self.assertEqual(config["model"], "manual-model")
        self.assertEqual(config["api_key"], "test-key")

    def test_custom_provider_and_bad_selection(self):
        with (
            patch(
                "builtins.input",
                side_effect=["bad", "5", "https://example.com/v1", "0", "1"],
            ),
            patch("autoterminal.config.manager.getpass", return_value="key"),
            patch(
                "autoterminal.config.manager.fetch_models",
                return_value=["custom-model"],
            ),
        ):
            result = ConfigManager(str(self.path / "config.json")).initialize_config()
        self.assertEqual(result["model"], "custom-model")
        self.assertEqual(result["provider"], "custom")

    def test_fetch_models_closes_client(self):
        with patch("autoterminal.config.providers.OpenAI") as sdk:
            sdk.return_value.__enter__.return_value.models.list.return_value.data = [
                SimpleNamespace(id="b"),
                SimpleNamespace(id="a"),
                SimpleNamespace(id="a"),
            ]
            self.assertEqual(fetch_models("key", self.config["base_url"]), ["a", "b"])
            sdk.return_value.__exit__.assert_called_once()

    def test_invalid_json_shapes(self):
        file = self.path / "data.json"
        file.write_text("[]")
        self.assertEqual(ConfigLoader(str(file)).get_config(), {})
        file.write_text("{}")
        self.assertEqual(HistoryManager(str(file)).history, [])

    def test_history_zero_and_exit_status(self):
        file = str(self.path / "history.json")
        manager = HistoryManager(file, max_history=10)
        manager.add_command("request", "false", returncode=1)
        self.assertEqual(manager.get_recent_history(0), [])
        self.assertEqual(HistoryManager(file).history[0]["returncode"], 1)
        self.assertEqual(manager.history[0]["cwd"], os.getcwd())
        disabled = HistoryManager(file, max_history=0)
        disabled.add_command("test", "true")
        self.assertEqual(len(HistoryManager(file).history), 1)

    def test_shell_history_formats_and_zero(self):
        file = self.path / "shell"
        file.write_text("#12345\nls\n: 123:0;pwd\nls\nexport API_KEY=secret\n")
        with patch.dict(os.environ, {"HISTFILE": str(file)}):
            self.assertEqual(get_shell_history(2), ["pwd", "ls"])
            self.assertEqual(get_shell_history(0), [])

    def test_command_cleaning_preserves_quotes(self):
        self.assertEqual(clean_command('```bash\nprintf "ok"\n```'), 'printf "ok"')
        self.assertEqual(
            clean_command('"/path with spaces/tool"'), '"/path with spaces/tool"'
        )
        with self.assertRaises(ValueError):
            clean_command("```bash\necho bad")

    def test_directory_includes_hidden_and_is_bounded(self):
        entries = [
            SimpleNamespace(name=".git", is_dir=lambda **kw: True),
            SimpleNamespace(name="a", is_dir=lambda **kw: False),
        ]
        with patch("autoterminal.utils.helpers.os.scandir") as scan:
            scan.return_value.__enter__.return_value = iter(entries)
            self.assertEqual(get_directory_context(1), [".git/", "（目录项已截断）"])

    def test_context_reaches_api_and_truncation_rejected(self):
        with patch("autoterminal.llm.client.OpenAI") as sdk:
            client = LLMClient(self.config)
            create = sdk.return_value.chat.completions.create
            choice = SimpleNamespace(
                finish_reason="stop", message=SimpleNamespace(content="pwd")
            )
            create.return_value = SimpleNamespace(choices=[choice])
            history = [
                {"generated_command": "first"},
                {"generated_command": "second", "returncode": 1},
            ]
            self.assertEqual(
                client.generate_command(
                    "where",
                    history=history,
                    current_dir_content=[".git/"],
                    shell_history=["pwd"],
                    shell_session={"command": "apt insall", "returncode": 100},
                ),
                "pwd",
            )
            content = create.call_args.kwargs["messages"][1]["content"]
            self.assertLess(content.index("first"), content.index("second"))
            self.assertIn(".git/", content)
            self.assertIn(os.getcwd(), content)
            self.assertIn("returncode", content)
            self.assertIn("apt insall", content)
            self.assertIn("优先纠正", create.call_args.kwargs["messages"][0]["content"])
            choice.finish_reason = "length"
            with self.assertRaises(ValueError):
                client.generate_command("where")
            choice.finish_reason = "stop"
            choice.message.content = None
            with self.assertRaises(ValueError):
                client.generate_command("where")

    def test_real_sdk_request_serialization(self):
        import json

        import httpx
        from openai import OpenAI

        requests = []

        def respond(request):
            requests.append(request)
            if request.url.path.endswith("/models"):
                return httpx.Response(
                    200,
                    json={
                        "object": "list",
                        "data": [
                            {
                                "id": "test-model",
                                "object": "model",
                                "created": 0,
                                "owned_by": "test",
                            }
                        ],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": "test",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "test-model",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "pwd"},
                        }
                    ],
                },
            )

        def make_client(**kwargs):
            return OpenAI(
                **kwargs,
                http_client=httpx.Client(transport=httpx.MockTransport(respond)),
            )

        with patch("autoterminal.config.providers.OpenAI", side_effect=make_client):
            self.assertEqual(
                fetch_models("test-key", self.config["base_url"]), ["test-model"]
            )
        with patch("autoterminal.llm.client.OpenAI", side_effect=make_client):
            client = LLMClient(self.config)
            try:
                self.assertEqual(
                    client.generate_command("where", current_dir_content=[".git"]),
                    "pwd",
                )
            finally:
                client.close()
        self.assertEqual(requests[0].url.path, "/v1/models")
        self.assertEqual(requests[1].url.path, "/v1/chat/completions")
        payload = json.loads(requests[1].content)
        self.assertIn(".git", payload["messages"][1]["content"])
        self.assertEqual(requests[1].headers["authorization"], "Bearer test-key")

    def run_cli(self, confirmation, count="0"):
        patches = [
            patch("sys.argv", ["at", "--history-count", count, "test"]),
            patch.object(main_module, "ConfigLoader"),
            patch.object(main_module, "HistoryManager"),
            patch.object(main_module, "LLMClient"),
            patch.object(main_module, "get_shell_history"),
            patch.object(main_module.subprocess, "run"),
            patch("builtins.input", return_value=confirmation),
        ]
        from contextlib import ExitStack

        with ExitStack() as stack:
            _, loader, history, client, shell, execute, _ = [
                stack.enter_context(p) for p in patches
            ]
            loader.return_value.get_config.return_value = self.config.copy()
            client.return_value.generate_command.return_value = "false"
            execute.return_value.returncode = 7
            result = main()
            return result, history, client, shell, execute

    def test_cli_cancel_never_executes(self):
        result, history, client, shell, execute = self.run_cli("no")
        self.assertEqual(result, 0)
        execute.assert_not_called()
        history.return_value.add_command.assert_not_called()
        client.return_value.close.assert_called_once()

    def test_cli_exit_status_and_history_disabled(self):
        result, history, client, shell, execute = self.run_cli("")
        self.assertEqual(result, 7)
        history.return_value.get_recent_history.assert_called_once_with(0)
        shell.assert_called_once_with(0)
        history.return_value.add_command.assert_called_once_with(
            "test", "false", returncode=7
        )
        self.assertEqual(
            client.return_value.generate_command.call_args.kwargs[
                "last_executed_command"
            ],
            "",
        )

    def test_cli_partial_overrides_survive_setup(self):
        with (
            patch("sys.argv", ["at", "--api-key", "override", "--model", "chosen"]),
            patch.object(main_module, "ConfigLoader") as loader,
            patch.object(main_module, "ConfigManager") as manager,
        ):
            loader.return_value.get_config.return_value = {}
            manager.return_value.get_or_create_config.return_value = {}
            self.assertEqual(main(), 1)
            manager.return_value.get_or_create_config.assert_called_once_with(
                {"api_key": "override", "model": "chosen"}
            )


if __name__ == "__main__":
    unittest.main()
