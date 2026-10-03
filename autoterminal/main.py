#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys

from autoterminal.config.loader import ConfigLoader
from autoterminal.config.manager import ConfigManager
from autoterminal.config.providers import PROVIDERS
from autoterminal.history import HistoryManager
from autoterminal.llm.client import LLMClient
from autoterminal.recommendations import EmptyRecommendationCache, is_self_install
from autoterminal.shell import get_shell_session, recommendation_target, shell_init
from autoterminal.utils.helpers import (
    clean_command,
    get_directory_context,
    get_shell_history,
)
from autoterminal.utils.logger import logger


def nonnegative_int(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("必须是非负整数")
    return number


def main():
    parser = argparse.ArgumentParser(description="AutoTerminal - 智能终端工具")
    parser.add_argument("user_input", nargs="*", help="用户输入的自然语言命令")
    parser.add_argument("--api-key", help="API 密钥")
    parser.add_argument("--base-url", help="自定义 Base URL")
    parser.add_argument("--model", help="模型名称")
    parser.add_argument("--provider", choices=PROVIDERS, help="选择服务商")
    parser.add_argument("--configure", action="store_true", help="重新配置服务商")
    parser.add_argument(
        "--history-count", type=nonnegative_int, help="历史上下文数量，0 禁用历史上下文"
    )
    parser.add_argument(
        "--shell-init", choices=("bash", "zsh"), help="输出 Shell 接入脚本"
    )
    parser.add_argument(
        "--show-context", action="store_true", help="显示上下文，不调用模型或执行命令"
    )
    args = parser.parse_args()
    if args.shell_init:
        print(shell_init(args.shell_init))
        return 0
    config = {} if args.configure else ConfigLoader().get_config()
    if args.provider:
        # 切换服务商时不可复用上一个服务商的凭据及模型。
        if config.get("base_url", "").rstrip("/") != PROVIDERS[args.provider][1].rstrip(
            "/"
        ):
            for key in ("api_key", "model"):
                config.pop(key, None)
        config.update(provider=args.provider, base_url=PROVIDERS[args.provider][1])
    for key in ("api_key", "base_url", "model"):
        value = getattr(args, key)
        if value is not None:
            config[key] = value.strip()
    if not args.show_context:
        config = ConfigManager().get_or_create_config(config)
    if not config and not args.show_context:
        return 1
    if args.configure:
        return 0 if ConfigManager().save_config(config) else 1
    retention = config.get("max_history", 10)
    if type(retention) is not int or retention < 0:
        logger.error("max_history 必须是非负整数")
        return 1
    count = args.history_count if args.history_count is not None else retention
    user_input = " ".join(args.user_input).strip()
    client = None
    try:
        history_manager = HistoryManager(max_history=retention)
        context = dict(
            user_input=user_input,
            history=history_manager.get_recent_history(min(count, 100)),
            current_dir_content=get_directory_context(),
            shell_history=get_shell_history(min(count, 100)),
            last_executed_command=history_manager.get_last_executed_command()
            if count
            else "",
            shell_session=get_shell_session() if count else {},
        )
        context["recommendation_context"] = recommendation_target(
            context["shell_session"], context["shell_history"], context["history"]
        )
        if args.show_context:
            print(
                json.dumps(
                    {"cwd": os.getcwd(), **context}, ensure_ascii=False, indent=2
                )
            )
            return 0
        if not user_input and not context["recommendation_context"]:
            print(
                '没有找到相关的命令建议。可以直接输入需求，例如：at "查看当前目录下的文件"'
            )
            return 0
        cache = None
        if not user_input:
            cache = EmptyRecommendationCache(config, context)
            if is_self_install(context["recommendation_context"]) or cache.hit():
                print("没有找到相关的命令建议。")
                return 0
        client = LLMClient(config)
        generated = client.generate_command(**context)
        command = clean_command(generated)
        if not command:
            if cache is not None:
                cache.remember()
            print("没有找到相关的命令建议。" if not user_input else "模型未生成命令。")
            return 0 if not user_input else 1
        print(f"$ {command}")
        if input("按 Enter 执行，输入其他内容或 Ctrl+C 取消: ").strip():
            print("已取消。")
            return 0
        shell = os.getenv("SHELL") if os.name != "nt" else None
        result = subprocess.run(command, shell=True, executable=shell)
        history_manager.add_command(
            user_input or "自动推荐", command, returncode=result.returncode
        )
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return 130
    except Exception as exc:
        logger.error(f"处理失败: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
