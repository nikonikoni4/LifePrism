"""
MiniMax Provider

使用 langchain_openai.ChatOpenAI (OpenAI 兼容接口)
"""

import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from .base_provider import BaseLLMProvider, ProviderCapability, ProviderConfig

logger = logging.getLogger(__name__)


class MiniMaxProvider(BaseLLMProvider):
    """
    MiniMax Provider

    特性:
    - 使用 OpenAI 兼容接口
    - 支持 reasoning_split=True 启用推理模式
    - 不支持 web_search
    """

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="MiniMax",
            provider_id="minimax",
            base_url="https://api.minimax.chat/v1",
            default_model="MiniMax-Text-01",
            capabilities={
                ProviderCapability.THINKING,
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
            },
            env_key_name="MINIMAX_API_KEY"
        )

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
        """创建 ChatOpenAI 模型实例（MiniMax 兼容）"""
        # MiniMax 不支持 web_search
        if enable_search:
            logger.warning("MiniMax 不支持 web_search，已忽略该参数")

        model_kwargs = self.get_model_kwargs(
            enable_search=enable_search,
            enable_thinking=enable_thinking,
            **kwargs
        )

        return ChatOpenAI(
            model=model or self.config.default_model,
            temperature=temperature,
            api_key=api_key,
            base_url=self.config.base_url,
            streaming=enable_streaming,
            model_kwargs=model_kwargs
        )

    def get_model_kwargs(
        self,
        enable_search: bool = False,
        enable_thinking: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        MiniMax 参数格式:
        - reasoning_effort: "high" (启用推理模式)

        注意: MiniMax 使用 reasoning_effort 而不是 reasoning_split
        """
        model_kwargs = {}

        if enable_thinking and self.supports(ProviderCapability.THINKING):
            model_kwargs["reasoning_effort"] = "high"

        # 合并其他 kwargs
        model_kwargs.update(kwargs.get("extra_model_kwargs", {}))

        return model_kwargs


# 单例实例
minimax_provider = MiniMaxProvider()
