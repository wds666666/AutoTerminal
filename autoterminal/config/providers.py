"""国内服务商的 OpenAI 兼容接口；模型由账号实时查询。"""

from openai import OpenAI

PROVIDERS = {
    "deepseek": ("DeepSeek", "https://api.deepseek.com/v1"),
    "zhipu": ("智谱（中国）", "https://open.bigmodel.cn/api/paas/v4"),
    "kimi": ("Kimi（月之暗面）", "https://api.moonshot.cn/v1"),
    "qwen": ("Qwen（百炼·北京）", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
}


def fetch_models(api_key: str, base_url: str) -> list[str]:
    with OpenAI(
        api_key=api_key, base_url=base_url, timeout=10, max_retries=0
    ) as client:
        return sorted(
            {
                model.id
                for model in client.models.list().data
                if isinstance(model.id, str) and model.id.strip()
            }
        )
