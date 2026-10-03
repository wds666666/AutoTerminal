"""父 Shell 接入：只传递上一条命令和状态，不捕获终端输出。"""

import os


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
