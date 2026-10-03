import json
import os
from datetime import datetime
from typing import Any

from autoterminal.utils.logger import logger
from autoterminal.utils.storage import write_json


class HistoryManager:
    """历史命令管理器，用于记录和检索命令历史"""

    def __init__(self, history_file: str = None, max_history: int = 10):
        if history_file is None:
            # 将历史文件存储在用户主目录下的.autoterminal目录中
            home_dir = os.path.expanduser("~")
            config_dir = os.path.join(home_dir, ".autoterminal")
            self.history_file = os.path.join(config_dir, "history.json")
        else:
            self.history_file = history_file

        if type(max_history) is not int or max_history < 0:
            raise ValueError("max_history 必须是非负整数")
        self.max_history = max_history
        self.history = self.load_history()

    def load_history(self) -> list[dict[str, Any]]:
        """从历史文件加载命令历史"""
        if os.path.exists(self.history_file):
            try:
                logger.debug(f"从文件加载历史: {self.history_file}")
                with open(self.history_file, encoding="utf-8") as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    raise ValueError("历史记录必须是数组")
                history = [entry for entry in history if isinstance(entry, dict)]
                logger.info(f"加载了 {len(history)} 条历史记录")
                return history
            except Exception as e:
                logger.error(f"无法读取历史文件 {self.history_file}: {e}")
        else:
            logger.debug(f"历史文件不存在: {self.history_file}")
        return []

    def save_history(self) -> bool:
        """保存命令历史到文件"""
        try:
            write_json(self.history_file, self.history)
            logger.debug("历史文件保存成功")
            return True
        except Exception as e:
            logger.error(f"无法保存历史文件 {self.history_file}: {e}")
            return False

    def add_command(
        self,
        user_input: str,
        generated_command: str,
        executed: bool = True,
        returncode: int = None,
    ) -> None:
        """添加命令到历史记录"""
        logger.debug(f"添加命令到历史: {generated_command}")
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "generated_command": generated_command,
            "executed": executed,
            "cwd": os.getcwd(),
            "returncode": returncode,
        }

        if self.max_history == 0:
            return
        self.history.append(entry)

        # 保持历史记录在最大数量限制内
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]
            logger.debug(f"历史记录已截断到 {self.max_history} 条")

        # 保存到文件
        self.save_history()

    def get_last_executed_command(self) -> str:
        """获取最后一条已执行的命令"""
        for entry in reversed(self.history):
            if entry.get("executed", False):
                return entry.get("generated_command", "")
        return ""

    def get_recent_history(self, count: int = None) -> list[dict[str, Any]]:
        """获取最近的命令历史"""
        if count is None:
            count = self.max_history

        return self.history[-count:] if self.history and count > 0 else []

    def get_last_command(self) -> dict[str, Any]:
        """获取最后一条命令"""
        if self.history:
            return self.history[-1]
        return {}
