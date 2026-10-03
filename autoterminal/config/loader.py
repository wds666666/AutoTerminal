import json
import os

from autoterminal.config.prompts import migrate_prompts
from autoterminal.utils.logger import logger
from autoterminal.utils.storage import write_json


class ConfigLoader:
    """配置加载器，支持从文件加载配置"""

    def __init__(self, config_file: str = None):
        if config_file is None:
            # 从用户主目录下的.autoterminal目录中加载配置文件
            home_dir = os.path.expanduser("~")
            config_dir = os.path.join(home_dir, ".autoterminal")
            self.config_file = os.path.join(config_dir, "config.json")
        else:
            self.config_file = config_file

    def load_from_file(self) -> dict:
        """从配置文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                logger.debug(f"从文件加载配置: {self.config_file}")
                with open(self.config_file, encoding="utf-8") as f:
                    config = json.load(f)
                if not isinstance(config, dict):
                    raise ValueError("配置必须是 JSON 对象")
                logger.info("配置文件加载成功")
                return config
            except Exception as e:
                logger.error(f"无法读取配置文件 {self.config_file}: {e}")
        else:
            logger.debug(f"配置文件不存在: {self.config_file}")
        return {}

    def get_config(self) -> dict:
        """获取配置"""
        config = self.load_from_file()
        if not config:
            return config
        migrated = migrate_prompts(config)
        if migrated != config:
            try:
                write_json(self.config_file, migrated)
            except OSError as exc:
                logger.warning(f"默认提示词已更新，但无法保存配置: {exc}")
        return migrated
