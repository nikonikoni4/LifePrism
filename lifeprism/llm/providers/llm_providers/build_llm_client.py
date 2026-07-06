"""
创建llm client的统一接口，支持litellmProvider + CustomProvider（OpenAI SDK），
通过providers.yaml 中 is_direct 进行路由
True -> CustomProvider
False -> litellmProvider
"""

from lifeprism.config import provider_manager, settings
from lifeprism.llm.providers.llm_providers.custom_provider import CustomProvider
from lifeprism.llm.providers.llm_providers.litellm_provider import LiteLLMProvider
from lifeprism.llm.providers.llm_providers.registry import find_by_name


def create_llm_client():
    """
    直接使用配置文件中的provider，api_key, api_base
    """
    provider = provider_manager.get_provider_id(settings.provider)
    spec = find_by_name(provider)
    if not provider:
        raise ValueError("config.yaml中没有设置provider,请在设置界面选择provider")
    if not spec:
        raise ValueError(f"无效的provider ： {provider}")

    is_direct = spec.is_direct
    # 1. 路由：查看is_direct
    if is_direct:
        return CustomProvider(
            api_key=provider_manager.get_api_key(provider) or "no-key",
            api_base=settings.api_base,
            default_model=settings.model,
        )
    else:
        return LiteLLMProvider(
            api_key=provider_manager.get_api_key(provider),
            api_base=settings.api_base,
            default_model=settings.model,
            provider_name=provider,
        )


if __name__ == "__main__":
    llm_client = create_llm_client()

    async def main():
        response = await llm_client.chat(
            [{"role": "user", "content": [{"type": "text", "text": "你好"}]}]
        )
        print(response)

    import asyncio

    asyncio.run(main())
