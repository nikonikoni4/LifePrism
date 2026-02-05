"""
LLM 统一工厂函数

提供统一的 LLM 创建入口，自动根据配置选择服务商
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel

from lifeprism.config.settings_manager import settings
from lifeprism.llm.providers import (
    BaseLLMProvider,
    aliyun_provider,
    volcengine_provider,
    openai_provider,
    minimax_provider,
)

logger = logging.getLogger(__name__)

# Provider ID 到实例的映射
PROVIDER_REGISTRY: Dict[str, BaseLLMProvider] = {
    "aliyun": aliyun_provider,
    "volcengine": volcengine_provider,
    "openai": openai_provider,
    "minimax": minimax_provider,
}

# 显示名称到 Provider ID 的映射
PROVIDER_NAME_TO_ID: Dict[str, str] = {
    "阿里云百炼 (Aliyun)": "aliyun",
    "火山引擎 (VolcEngine)": "volcengine",
    "OpenAI": "openai",
    "MiniMax": "minimax",
}

# Provider ID 到显示名称的映射
PROVIDER_ID_TO_NAME: Dict[str, str] = {v: k for k, v in PROVIDER_NAME_TO_ID.items()}


def get_provider_id(provider_name: Optional[str] = None) -> str:
    """
    获取 Provider ID

    Args:
        provider_name: 服务商名称（显示名称或 ID），None 时从 settings 读取

    Returns:
        Provider ID
    """
    if provider_name is None:
        provider_name = settings.provider

    # 如果已经是 ID，直接返回
    if provider_name in PROVIDER_REGISTRY:
        return provider_name

    # 尝试从显示名称映射
    provider_id = PROVIDER_NAME_TO_ID.get(provider_name)
    if provider_id:
        return provider_id

    # 默认使用阿里云
    logger.warning(f"未知的服务商 '{provider_name}'，使用默认服务商 'aliyun'")
    return "aliyun"


def get_provider(provider: Optional[str] = None) -> BaseLLMProvider:
    """
    获取 Provider 实例

    Args:
        provider: 服务商名称或 ID，None 时从 settings 读取

    Returns:
        BaseLLMProvider 实例
    """
    provider_id = get_provider_id(provider)
    return PROVIDER_REGISTRY.get(provider_id, aliyun_provider)


def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    enable_search: bool = False,
    enable_thinking: bool = False,
    enable_streaming: bool = False,
    **kwargs
) -> BaseChatModel:
    """
    统一 LLM 创建入口

    自动根据配置选择服务商并创建对应的 ChatModel 实例

    Args:
        provider: 服务商名称或 ID，None 时从 settings 读取
        model: 模型名称，None 时从 settings 读取
        api_key: API 密钥，None 时从 settings 读取
        temperature: 温度参数，默认 0.2
        enable_search: 启用网络搜索（如果服务商支持）
        enable_thinking: 启用深度思考（如果服务商支持）
        enable_streaming: 启用流式输出
        **kwargs: 其他参数

    Returns:
        BaseChatModel 实例

    Example:
        # 使用默认配置
        llm = create_llm()

        # 指定服务商和参数
        llm = create_llm(
            provider="openai",
            model="gpt-4o",
            temperature=0.7
        )

        # 启用特殊功能
        llm = create_llm(
            enable_search=True,
            enable_thinking=True
        )
    """
    # 获取 Provider
    llm_provider = get_provider(provider)
    provider_id = get_provider_id(provider)

    # 获取配置值
    actual_model = model or settings.model or llm_provider.config.default_model
    actual_api_key = api_key or settings.get_api_key(provider_id)

    if not actual_api_key:
        raise ValueError(
            f"未配置 API Key。请在设置中配置 {llm_provider.config.name} 的 API Key，"
            f"或设置环境变量 {llm_provider.config.env_key_name}"
        )

    logger.debug(
        f"创建 LLM: provider={provider_id}, model={actual_model}, "
        f"search={enable_search}, thinking={enable_thinking}"
    )

    return llm_provider.create_model(
        model=actual_model,
        api_key=actual_api_key,
        temperature=temperature,
        enable_search=enable_search,
        enable_thinking=enable_thinking,
        enable_streaming=enable_streaming,
        **kwargs
    )


def get_provider_capabilities(provider: Optional[str] = None) -> Dict[str, Any]:
    """
    获取服务商支持的能力

    Args:
        provider: 服务商名称或 ID，None 时从 settings 读取

    Returns:
        能力字典，包含:
        - provider_id: 服务商 ID
        - provider_name: 服务商显示名称
        - capabilities: 能力布尔值字典
        - default_model: 默认模型
    """
    llm_provider = get_provider(provider)
    config = llm_provider.config

    return {
        "provider_id": config.provider_id,
        "provider_name": config.name,
        "capabilities": llm_provider.get_capabilities_dict(),
        "default_model": config.default_model,
    }


def list_providers() -> list:
    """
    获取所有支持的服务商列表

    Returns:
        服务商信息列表
    """
    result = []
    for provider_id, provider in PROVIDER_REGISTRY.items():
        config = provider.config
        result.append({
            "provider_id": config.provider_id,
            "provider_name": config.name,
            "capabilities": provider.get_capabilities_dict(),
            "default_model": config.default_model,
        })
    return result


# ===================== 向后兼容别名 =====================

def create_ChatTongyiModel(
    temperature: float = 0.2,
    enable_search: bool = True,
    enable_thinking: bool = False,
    enable_streaming: bool = False
) -> BaseChatModel:
    """
    向后兼容的别名函数

    保持与旧代码的兼容性，内部调用 create_llm

    Args:
        temperature: 温度参数
        enable_search: 启用网络搜索
        enable_thinking: 启用深度思考
        enable_streaming: 启用流式输出

    Returns:
        BaseChatModel 实例
    """
    return create_llm(
        temperature=temperature,
        enable_search=enable_search,
        enable_thinking=enable_thinking,
        enable_streaming=enable_streaming
    )


if __name__ == "__main__":
    import asyncio

    # 测试代码
    print("=" * 60)
    print("测试 LLM 工厂函数")
    print("=" * 60)

    # 列出所有服务商
    print("\n支持的服务商:")
    for p in list_providers():
        print(f"  - {p['provider_name']} ({p['provider_id']})")
        print(f"    默认模型: {p['default_model']}")
        print(f"    能力: {p['capabilities']}")

    # 获取当前配置的服务商能力
    print(f"\n当前服务商: {settings.provider}")
    caps = get_provider_capabilities()
    print(f"  能力: {caps['capabilities']}")

    # ===================== 连接测试 =====================
    print("\n" + "=" * 60)
    print("测试 LLM 连接")
    print("=" * 60)

    provider_id = get_provider_id()
    api_key = settings.get_api_key(provider_id)

    print(f"\n配置信息:")
    print(f"  Provider: {settings.provider}")
    print(f"  Provider ID: {provider_id}")
    print(f"  Model: {settings.model}")
    print(f"  API Key 来源: keyring ({provider_id})")
    print(f"  API Key 存在: {api_key is not None}")
    if api_key:
        print(f"  API Key 前缀: {api_key[:8]}..." if len(api_key) > 8 else f"  API Key: {api_key}")

    if not api_key:
        print("\n[错误] 未找到 API Key，请先在设置中配置")
    else:
        print("\n正在测试连接...")
        try:
            llm = create_llm(temperature=0.1, enable_search=False)
            print(f"  LLM 实例创建成功: {type(llm).__name__}")

            async def test():
                response = await llm.ainvoke("请回复'连接成功'这四个字。")
                return response.content if hasattr(response, 'content') else str(response)

            result = asyncio.run(test())
            print(f"\n[成功] 模型回复: {result}")
        except Exception as e:
            print(f"\n[失败] 错误: {e}")
