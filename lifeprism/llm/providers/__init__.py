"""
LLM Providers 模块（新架构）
重构后的目录结构：
- llm_providers/: LLM 服务提供者
- dataset_providers/: 数据集提供者
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

# 从 dataset_providers 子模块导入
from .dataset_providers import (
    LLMLWDataProvider,
    llm_lw_data_provider,
    SummaryReadProvider,
    summary_read_provider,
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
    # 数据提供者
    "LLMLWDataProvider",
    "llm_lw_data_provider",
    "SummaryReadProvider",
    "summary_read_provider",
]
