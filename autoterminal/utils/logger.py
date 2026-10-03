import os
import sys

from loguru import logger

# 移除默认的 handler
logger.remove()

# 获取日志级别（从环境变量或默认为 ERROR，正式使用时只显示错误）
log_level = os.getenv("AUTOTERMINAL_LOG_LEVEL", "ERROR").upper()
if log_level not in {
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
}:
    log_level = "ERROR"

# 添加控制台输出（stderr）- 默认只显示错误
logger.add(
    sys.stderr,
    format="<level>{level}: {message}</level>",
    level=log_level,
    colorize=True,
)

# 添加文件输出（可选，存储在 ~/.autoterminal/ 目录）
enable_file_logging = os.getenv("AUTOTERMINAL_FILE_LOG", "true").lower() != "false"
if enable_file_logging:
    try:
        home_dir = os.path.expanduser("~")
        log_dir = os.path.join(home_dir, ".autoterminal")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "autoterminal.log")

        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",  # 文件记录所有级别的日志
            rotation="10 MB",  # 日志文件达到 10MB 时轮转
            retention="7 days",  # 保留最近 7 天的日志
            compression="zip",  # 压缩旧日志
            encoding="utf-8",
        )
    except OSError:
        pass  # 日志目录不可写不应阻止 CLI 启动。

# 导出 logger 供其他模块使用
__all__ = ["logger"]
