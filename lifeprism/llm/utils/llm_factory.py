"""
LLM 统一工厂函数

提供统一的 LLM 创建入口，自动根据配置选择服务商
"""

import logging
from typing import Any, Dict, Optional

from lifeprism.config.settings_manager import settings
from lifeprism.config.provider_manager import provider_manager
from lifeprism.llm.providers.registry import find_by_name

logger = logging.getLogger(__name__)


def get_provider_id(provider_name: Optional[str] = None) -> str:
    """
    获取 Provider ID (区分于display name 显示名称)

    Args:
        provider_name: 服务商名称（显示名称或 ID），None 时从 settings 读取

    Returns:
        Provider ID
    """
    if provider_name is None:
        provider_name = settings.provider

    # 使用 provider_manager 统一转换
    return provider_manager.get_provider_id(provider_name)


def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    enable_search: bool = False,
    enable_thinking: bool = False,
    enable_streaming: bool = False,
    **kwargs
):
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
    from lifeprism.llm.providers.litellm_provider import LiteLLMProvider

    provider_id = get_provider_id(provider)
    spec = find_by_name(provider_id)

    actual_model = model or settings.model or (spec.default_model if spec else "")
    actual_api_key = api_key or settings.get_api_key(provider_id)
    actual_api_base = (spec.default_api_base if spec else "") or ""
    provider_name = provider_id

    if not actual_api_key:
        raise ValueError(
            f"未配置 API Key。请在设置中配置 {provider_id} 的 API Key。"
        )

    logger.debug(
        f"创建 LLM: provider={provider_id}, model={actual_model}, "
        f"search={enable_search}, thinking={enable_thinking}"
    )

    llm_provider = LiteLLMProvider(
        api_key=actual_api_key,
        api_base=actual_api_base,
        default_model=actual_model,
        provider_name=provider_name,
    )
    return llm_provider


def get_provider_capabilities(provider: Optional[str] = None) -> Dict[str, Any]:
    """
    获取服务商信息（来自 provider_manager）。

    Args:
        provider: 服务商名称或 ID，None 时从 settings 读取

    Returns:
        包含 name/display_name/default_model/default_api_base/has_api_key 的字典
    """
    provider_id = get_provider_id(provider)
    spec = find_by_name(provider_id)
    if spec is None:
        return {
            "name": provider_id,
            "display_name": provider_id,
            "default_model": "",
            "default_api_base": "",
            "has_api_key": False,
        }
    return {
        "name": spec.name,
        "display_name": spec.display_name,
        "default_model": spec.default_model,
        "default_api_base": spec.default_api_base,
        "has_api_key": bool(spec.env_key),
    }


def list_providers() -> list:
    """
    获取所有支持的服务商列表（来自 provider_manager）。

    Returns:
        服务商信息列表，字段：name/display_name/default_model/default_api_base/has_api_key
    """
    return provider_manager.get_all_providers(allowed_only=True)


# ===================== 向后兼容别名 =====================

def create_ChatTongyiModel(
    temperature: float = 0.2,
    enable_search: bool = True,
    enable_thinking: bool = False,
    enable_streaming: bool = False
):
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
        print(f"  - {p['display_name']} ({p['name']})")
        print(f"    默认模型: {p['default_model']}")

    # 获取当前配置的服务商信息
    print(f"\n当前服务商: {settings.provider}")
    caps = get_provider_capabilities()
    print(f"  Provider ID: {caps['name']}, 显示名: {caps['display_name']}")

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
                response = await llm.chat([{"role": "user", "content": "请回复'连接成功'这四个字。"}])
                return response.content or ""

            result = asyncio.run(test())
            print(f"\n[成功] 模型回复: {result}")
        except Exception as e:
            print(f"\n[失败] 错误: {e}")
