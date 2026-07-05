"""
LLM Providers 模块（新架构）
重构后的目录结构：
- llm_providers/: LLM 服务提供者
"""

# 从 llm_providers 子模块导入
from .llm_providers import (
    LLMProvider,
    LLMResponse,
    ToolCallRequest,
    GenerationSettings,
    LiteLLMProvider,
    CustomProvider,
    ProviderSpec,
    PROVIDERS,
    find_by_model,
    find_gateway,
    find_by_name,
    create_llm_client,
)

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
