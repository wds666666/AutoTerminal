"""版本化内置提示词；通过旧默认快照识别并保留用户自定义内容。"""

PROMPT_VERSION = 2
DEFAULT_PROMPTS = {
    "default_prompt": "你是终端助手，按照用户的明确需求生成完整的终端命令，只输出命令。",
    "recommendation_prompt": (
        "你是终端助手。用户未输入需求时，依据最近有效命令推荐下一条命令。"
        "优先使用实时 Shell 上下文，否则回退到 Shell 历史，再参考当前目录的 AutoTerminal 历史。"
        "退出码未知也要纠正明显拼写错误，保留原参数；例如 atp list --upgradable 改为 apt list --upgradable。"
        "忽略 at 自身调用；不要仅根据目录推荐无关任务。无明确线索才返回空字符串。只输出命令。"
    ),
}
LEGACY_PROMPTS = [
    "你现在是一个终端助手,用户输入想要生成的命令,你来输出一个命令,不要任何多余的文本!",
    "你现在是一个终端助手，根据上下文自动推荐命令：当用户没有输入时，基于最近执行的命令历史和当前目录内容，智能推荐最可能需要的终端命令（仅当有明确上下文线索时）；当用户输入命令需求时，生成对应命令。仅输出纯命令文本，不要任何解释或多余内容！",
    "你现在是一个终端助手，用户输入想要生成的命令,你来输出一个命令,不要任何多余的文本!",
]


def migrate_prompts(config: dict) -> dict:
    migrated = config.copy()
    previous = config.get("prompt_defaults", {})
    if not isinstance(previous, dict):
        previous = {}
    for key, default in DEFAULT_PROMPTS.items():
        value = config.get(key)
        if (
            not isinstance(value, str)
            or not value.strip()
            or value in LEGACY_PROMPTS
            or value == previous.get(key)
        ):
            migrated[key] = default
    migrated["prompt_version"] = PROMPT_VERSION
    migrated["prompt_defaults"] = DEFAULT_PROMPTS.copy()
    return migrated
