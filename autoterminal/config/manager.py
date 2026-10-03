from getpass import getpass
from typing import Any
from urllib.parse import urlparse

from autoterminal.config.loader import ConfigLoader
from autoterminal.config.prompts import migrate_prompts
from autoterminal.config.providers import PROVIDERS, fetch_models
from autoterminal.utils.logger import logger
from autoterminal.utils.storage import write_json


class ConfigManager:
    """保存配置，并以服务商优先的向导补齐缺失字段。"""

    def __init__(self, config_file: str = None):
        self.config_file = ConfigLoader(config_file).config_file
        self.required_keys = ["api_key", "base_url", "model"]
        self.default_config = {"max_history": 10}

    def save_config(self, config: dict[str, Any]) -> bool:
        try:
            write_json(self.config_file, config)
            return True
        except OSError as exc:
            logger.error(f"无法保存配置文件: {exc}")
            return False

    def validate_config(self, config: dict[str, Any]) -> bool:
        if not isinstance(config, dict):
            return False
        if not all(
            isinstance(config.get(key), str) and config[key].strip()
            for key in self.required_keys
        ):
            return False
        url = urlparse(config["base_url"])
        return url.scheme in ("http", "https") and bool(url.netloc)

    def initialize_config(self, existing=None) -> dict[str, Any]:
        print("欢迎使用 AutoTerminal 配置向导！")
        config = migrate_prompts({**self.default_config, **(existing or {})})
        for key in self.required_keys:
            value = config.get(key)
            config[key] = value.strip() if isinstance(value, str) else ""
        try:
            if not config.get("base_url"):
                names = list(PROVIDERS)
                for index, name in enumerate(names, 1):
                    print(f"{index}. {PROVIDERS[name][0]}")
                print("5. 其他（自定义 OpenAI 兼容服务）")
                while True:
                    selection = input("请选择服务商 [1-5]: ").strip().lower()
                    if selection in names:
                        provider = selection
                        break
                    if selection in ("1", "2", "3", "4", "5"):
                        provider = (
                            names[int(selection) - 1] if selection != "5" else "custom"
                        )
                        break
                    print("请输入有效序号或服务商名称。")
                config["provider"] = provider
                if provider == "custom":
                    config["base_url"] = input("请输入 Base URL: ").strip()
                else:
                    config["base_url"] = PROVIDERS[provider][1]
            url = urlparse(config["base_url"])
            if url.scheme not in ("http", "https") or not url.netloc:
                print("错误：Base URL 必须是有效的 HTTP(S) 地址。")
                return {}
            if not config.get("api_key"):
                config["api_key"] = getpass("请输入 API Key（隐藏输入）: ").strip()
            if not config["api_key"]:
                print("错误：API Key 不能为空。")
                return {}
            if not config.get("model"):
                print("正在获取模型列表…")
                try:
                    models = fetch_models(config["api_key"], config["base_url"])
                except Exception as exc:
                    # 不显示服务商返回的原始内容，避免回显凭据。
                    print(
                        f"模型列表获取失败（{type(exc).__name__}），可直接输入模型 ID。"
                    )
                    models = []
                for index, model in enumerate(models, 1):
                    print(f"{index}. {model}")
                if not models:
                    print("没有可用的模型列表，请手动输入模型 ID。")
                while True:
                    selection = input("选择模型序号，或直接输入模型 ID: ").strip()
                    if not selection:
                        print("模型不能为空。")
                    elif models and selection.isdecimal():
                        if 1 <= int(selection) <= len(models):
                            config["model"] = models[int(selection) - 1]
                            break
                        print("模型序号超出范围。")
                    else:
                        config["model"] = selection
                        break
        except (EOFError, KeyboardInterrupt):
            print("\n配置向导已取消。")
            return {}
        if self.validate_config(config) and self.save_config(config):
            print(f"配置已保存到 {self.config_file}")
            return config
        print("配置保存失败。")
        return {}

    def get_or_create_config(self, existing=None) -> dict[str, Any]:
        config = (
            ConfigLoader(self.config_file).get_config()
            if existing is None
            else existing
        )
        return (
            config if self.validate_config(config) else self.initialize_config(config)
        )
