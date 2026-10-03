import os
import re
from itertools import islice

from autoterminal.utils.logger import logger


def clean_command(command: str) -> str:
    """仅解包完整 Markdown 围栏，不破坏命令本身的引号。"""
    command = command.strip()
    if command.startswith("```"):
        match = re.fullmatch(r"```(?:bash|sh|shell|zsh)?\s*\n(.*?)\n```", command, re.S)
        if not match:
            raise ValueError("模型返回了不完整的代码块，未执行")
        command = match.group(1).strip()
    if "\x00" in command:
        raise ValueError("命令包含无效字符")
    return command


def get_directory_context(limit=200) -> list[str]:
    try:
        with os.scandir(".") as entries:
            names = [
                entry.name + ("/" if entry.is_dir(follow_symlinks=False) else "")
                for entry in islice(entries, limit + 1)
            ]
        return sorted(names[:limit]) + (
            ["（目录项已截断）"] if len(names) > limit else []
        )
    except OSError as exc:
        logger.warning(f"无法获取目录内容: {exc}")
        return []


def get_shell_history(count: int = 20) -> list[str]:
    """读取已落盘的 Bash/Zsh 历史，最多读取末尾 256 KiB。"""
    if count <= 0:
        return []
    histfile = os.getenv("HISTFILE")
    if not histfile:
        names = (
            (".zsh_history", ".zhistory", ".bash_history")
            if "zsh" in os.getenv("SHELL", "")
            else (".bash_history", ".zsh_history", ".zhistory")
        )
        histfile = next(
            (
                os.path.expanduser("~/" + name)
                for name in names
                if os.path.isfile(os.path.expanduser("~/" + name))
            ),
            None,
        )
    if not histfile:
        return []
    try:
        with open(os.path.expanduser(histfile), "rb") as stream:
            stream.seek(0, os.SEEK_END)
            offset = max(0, stream.tell() - 256 * 1024)
            stream.seek(offset)
            if offset:
                stream.readline()  # 丢弃可能截断的首行
            lines = stream.read().decode("utf-8", errors="replace").splitlines()
        commands, seen = [], set()
        for line in reversed(lines):
            line = re.sub(r"^: \d+:\d+;", "", line).strip()
            if not line or re.fullmatch(r"#\d+", line):
                continue
            if any(
                word in line.lower()
                for word in ("password", "passwd", "secret", "key", "token")
            ):
                continue
            if line not in seen:
                commands.append(line)
                seen.add(line)
                if len(commands) >= count:
                    break
        return list(reversed(commands))
    except OSError as exc:
        logger.warning(f"获取 Shell 历史失败: {exc}")
        return []
