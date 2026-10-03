from . import config, llm, utils
from .history import HistoryManager


def main():
    """延迟导入 CLI，避免 python -m 启动时重复加载模块。"""
    from .main import main as cli_main

    return cli_main()


__all__ = ["config", "llm", "utils", "HistoryManager", "main"]
