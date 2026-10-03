"""空推荐快速路径及短期缓存，不缓存网络错误或可执行命令。"""

import hashlib
import json
import os
import shlex
import time
from pathlib import Path

from autoterminal.shell import is_autoterminal_command
from autoterminal.utils.storage import write_json


def is_self_install(target):
    if target.get("returncode") not in (None, 0):
        return False
    try:
        words = shlex.split(target.get("command", ""))
    except ValueError:
        return False
    return words[:3] == ["uv", "tool", "install"] and any(
        word == "autoterminal" or word.startswith("autoterminal==")
        for word in words[3:]
    )


class EmptyRecommendationCache:
    def __init__(self, config, context, path=None):
        self.path = (
            Path(path)
            if path
            else Path.home() / ".autoterminal" / "empty-recommendation.json"
        )
        context = {**context, "cwd": os.getcwd(), "shell": os.getenv("SHELL", "")}
        context["shell_history"] = [
            cmd
            for cmd in context.get("shell_history", [])
            if not is_autoterminal_command(cmd)
        ]
        # Assistant invocations change their exit code without changing the underlying task.
        context.pop("shell_session", None)
        payload = json.dumps([config, context], ensure_ascii=False, sort_keys=True)
        self.key = hashlib.sha256(payload.encode()).hexdigest()

    def hit(self):
        try:
            data = json.loads(self.path.read_text())
            age = time.time() - data["time"]
            return data["key"] == self.key and 0 <= age < 120
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def remember(self):
        try:
            write_json(self.path, {"key": self.key, "time": time.time()})
        except OSError:
            pass
