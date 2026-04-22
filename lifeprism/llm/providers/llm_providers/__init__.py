"""
LLM Providers 子模块
提供各种 LLM 服务的实现
"""

from .base import (
    LLMProvider,
    LLMResponse,
    ToolCallRequest,
    GenerationSettings,
)
from .litellm_provider import LiteLLMProvider
from .custom_provider import CustomProvider
from .registry import (
    ProviderSpec,
    PROVIDERS,
    find_by_model,
    find_gateway,
    find_by_name,
)
from .build_llm_client import create_llm_client

__all__ = [
    # 抽象层
    "LLMProvider",
    "LLMResponse",
    "ToolCallRequest",
    "GenerationSettings",
    # 实现类
    "LiteLLMProvider",
    "CustomProvider",
    # registry
    "ProviderSpec",
    "PROVIDERS",
    "find_by_model",
    "find_gateway",
    "find_by_name",
    # 工厂函数
    "create_llm_client",
]
