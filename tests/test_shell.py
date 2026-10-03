import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autoterminal.shell import get_shell_session, shell_init

main_module = importlib.import_module("autoterminal.main")


class ShellTests(unittest.TestCase):
    def test_live_bash_and_zsh_history(self):
        for shell in ("bash", "zsh"):
            executable = shutil.which(shell)
            if not executable:
                continue
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "context.json"
                binary = root / "at"
                binary.write_text(
                    f"#!{sys.executable}\nimport os, json\n"
                    f'open({str(output)!r}, "w").write(json.dumps(dict(os.environ)))\n'
                )
                binary.chmod(0o700)
                env = {
                    **os.environ,
                    "PATH": directory + os.pathsep + os.environ["PATH"],
                    "HISTFILE": "/dev/null",
                    "HISTSIZE": "100",
                    "SAVEHIST": "0",
                }
                flags = (
                    ["--noprofile", "--norc", "-i"] if shell == "bash" else ["-f", "-i"]
                )
                # A fake apt avoids executing a package manager, while retaining the exact history command.
                script = (
                    shell_init(shell)
                    + "\napt() { return 100; }\napt insall\nat\nexit\n"
                )
                result = subprocess.run(
                    [executable, *flags],
                    input=script,
                    text=True,
                    env=env,
                    capture_output=True,
                    timeout=10,
                )
                self.assertTrue(output.exists(), result.stderr)
                received = json.loads(output.read_text())
                self.assertEqual(
                    received["AUTOTERMINAL_PREVIOUS_COMMAND"].strip(), "apt insall"
                )
                self.assertEqual(received["AUTOTERMINAL_PREVIOUS_STATUS"], "100")

    def test_session_filter_and_status(self):
        with patch.dict(
            os.environ,
            {
                "AUTOTERMINAL_PREVIOUS_COMMAND": "apt insall",
                "AUTOTERMINAL_PREVIOUS_STATUS": "100",
            },
        ):
            self.assertEqual(get_shell_session()["returncode"], 100)
            self.assertEqual(get_shell_session()["command"], "apt insall")
        with patch.dict(
            os.environ,
            {
                "AUTOTERMINAL_PREVIOUS_COMMAND": "export API_KEY=secret",
                "AUTOTERMINAL_PREVIOUS_STATUS": "0",
            },
        ):
            self.assertNotIn("command", get_shell_session())

    def test_show_context_needs_no_credentials_and_zero_disables_session(self):
        for extra, expected in (([], "apt insall"), (["--history-count", "0"], None)):
            with (
                patch.object(sys, "argv", ["at", "--show-context", *extra]),
                patch.object(main_module, "ConfigLoader") as loader,
                patch.object(main_module, "LLMClient") as client,
                patch.dict(
                    os.environ,
                    {
                        "AUTOTERMINAL_PREVIOUS_COMMAND": "apt insall",
                        "AUTOTERMINAL_PREVIOUS_STATUS": "100",
                    },
                ),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                loader.return_value.get_config.return_value = {}
                self.assertEqual(main_module.main(), 0)
                self.assertEqual(
                    json.loads(stdout.getvalue())["shell_session"].get("command"),
                    expected,
                )
                client.assert_not_called()

    def test_history_fallback_without_shell_integration(self):
        for session in ({}, {"command": "at", "returncode": 130}):
            with (
                patch.object(sys, "argv", ["at"]),
                patch.object(main_module, "ConfigLoader") as loader,
                patch.object(main_module, "LLMClient") as client,
                patch.object(main_module, "get_shell_session", return_value=session),
                patch.object(
                    main_module,
                    "get_shell_history",
                    return_value=["atp list --upgradable", "at", "at --show-context"],
                ),
                patch("builtins.input", return_value="cancel"),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                loader.return_value.get_config.return_value = {
                    "api_key": "test",
                    "base_url": "https://example.com",
                    "model": "test",
                }
                client.return_value.generate_command.return_value = (
                    "apt list --upgradable"
                )
                self.assertEqual(main_module.main(), 0)
                context = client.return_value.generate_command.call_args.kwargs[
                    "recommendation_context"
                ]
                self.assertEqual(
                    context,
                    {
                        "command": "atp list --upgradable",
                        "source": "shell_history",
                        "returncode": None,
                    },
                )
                self.assertIn("$ apt list --upgradable", stdout.getvalue())
                self.assertNotIn("Shell", stdout.getvalue())

    def test_live_session_takes_priority_over_disk_history(self):
        from autoterminal.shell import recommendation_target

        session = {"command": "git stats", "returncode": 1, "source": "parent_shell"}
        self.assertEqual(recommendation_target(session, ["atp install"], []), session)
        self.assertEqual(recommendation_target({}, ["at", "at --show-context"], []), {})
