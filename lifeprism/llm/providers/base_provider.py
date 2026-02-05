"""
LLM Provider 抽象基类

定义所有 LLM 服务商的通用接口和能力枚举
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from langchain_core.language_models.chat_models import BaseChatModel


class ProviderCapability(Enum):
    """服务商能力枚举"""
    WEB_SEARCH = auto()      # 网络搜索
    THINKING = auto()        # 深度思考/推理
    STREAMING = auto()       # 流式输出
    TOOL_CALLING = auto()    # 工具调用


@dataclass
class ProviderConfig:
    """服务商配置"""
    name: str                           # 显示名称，如 "阿里云百炼 (Aliyun)"
    provider_id: str                    # 内部标识，如 "aliyun"
    base_url: Optional[str] = None      # API 基础 URL
    default_model: str = ""             # 默认模型
    capabilities: Set[ProviderCapability] = field(default_factory=set)
    env_key_name: str = ""              # 环境变量名称，如 "DASHSCOPE_API_KEY"


class BaseLLMProvider(ABC):
    """
    LLM 服务商抽象基类

    所有服务商 Provider 必须继承此类并实现：
    - config 属性：返回 ProviderConfig
    - create_model 方法：创建 LangChain ChatModel 实例
    """

    @property
    @abstractmethod
    def config(self) -> ProviderConfig:
        """返回服务商配置"""
        pass

    @abstractmethod
    def create_model(
        self,
        model: str,
        api_key: str,
        temperature: float = 0.7,
        enable_search: bool = False,
        enable_thinking: bool = False,
        enable_streaming: bool = False,
        **kwargs
    ) -> BaseChatModel:
        """
        创建 LangChain ChatModel 实例

        Args:
            model: 模型名称
            api_key: API 密钥
            temperature: 温度参数
            enable_search: 启用网络搜索（如果支持）
            enable_thinking: 启用深度思考（如果支持）
            enable_streaming: 启用流式输出
            **kwargs: 其他参数

        Returns:
            BaseChatModel 实例
        """
        pass

    def supports(self, capability: ProviderCapability) -> bool:
        """
        检查是否支持某项能力

        Args:
            capability: 要检查的能力

        Returns:
            是否支持
        """
        return capability in self.config.capabilities

    def get_model_kwargs(
        self,
        enable_search: bool = False,
        enable_thinking: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取模型特定的 kwargs 参数

        子类可重写此方法以适配不同服务商的参数格式

        Args:
            enable_search: 启用网络搜索
            enable_thinking: 启用深度思考
            **kwargs: 其他参数

        Returns:
            model_kwargs 字典
        """
        return {}

    def get_capabilities_dict(self) -> Dict[str, bool]:
        """
        获取能力字典（供 API 返回）

        Returns:
            能力名称到布尔值的映射
        """
        return {
            "web_search": self.supports(ProviderCapability.WEB_SEARCH),
            "thinking": self.supports(ProviderCapability.THINKING),
            "streaming": self.supports(ProviderCapability.STREAMING),
            "tool_calling": self.supports(ProviderCapability.TOOL_CALLING),
        }
