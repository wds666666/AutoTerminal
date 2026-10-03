"""父 Shell 接入：只传递上一条命令和状态，不捕获终端输出。"""

import os
import shlex


def shell_init(shell: str) -> str:
    if shell not in ("bash", "zsh"):
        raise ValueError("仅支持 Bash 和 Zsh")
    return """at() {
    local _at_previous_status=$?
    local _at_previous_command
    _at_previous_command=$(builtin fc -ln -1 2>/dev/null)
    AUTOTERMINAL_PREVIOUS_COMMAND="$_at_previous_command" \\
    AUTOTERMINAL_PREVIOUS_STATUS="$_at_previous_status" \\
    command at "$@"
}"""


def get_shell_session() -> dict:
    command = os.getenv("AUTOTERMINAL_PREVIOUS_COMMAND", "").strip()
    code = os.getenv("AUTOTERMINAL_PREVIOUS_STATUS", "")
    if not command or not code.isdecimal() or not 0 <= int(code) <= 255:
        return {}
    # 与历史文件采用相同的敏感信息过滤，避免绕过原有保护。
    if any(
        word in command.lower()
        for word in ("password", "passwd", "secret", "key", "token")
    ):
        return {"source": "parent_shell", "command_filtered": True}
    return {
        "source": "parent_shell",
        "command": command[:8000],
        "returncode": int(code),
        "command_truncated": len(command) > 8000,
    }


def is_autoterminal_command(command: str) -> bool:
    """连续调用助手不是新的终端任务，避免把取消状态当作待修复错误。"""
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if words and words[0] == "command":
        words = words[1:]
    return bool(words) and (
        os.path.basename(words[0]) == "at" or words[:3] == ["uv", "run", "at"]
    )


def recommendation_target(
    session: dict, shell_history: list[str], history: list[dict]
) -> dict:
    """优先实时会话，否则参考历史；磁盘历史没有可验证的退出码。"""
    if session.get("command_filtered") or session.get("command_truncated"):
        return {}
    command = session.get("command", "")
    if command and not is_autoterminal_command(command):
        return session.copy()
    for command in reversed(shell_history):
        if (
            command.strip()
            and command.strip() not in ("clear", "history")
            and not is_autoterminal_command(command)
        ):
            return {"source": "shell_history", "command": command, "returncode": None}
    for entry in reversed(history):
        if (
            entry.get("cwd") == os.getcwd()
            and entry.get("executed")
            and entry.get("generated_command")
        ):
            return {
                "source": "autoterminal_history",
                "command": entry["generated_command"],
                "returncode": entry.get("returncode"),
            }
    return {}
