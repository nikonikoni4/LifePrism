"""
OpenAI Provider

使用 langchain_openai.ChatOpenAI
"""

import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from .base_provider import BaseLLMProvider, ProviderCapability, ProviderConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI Provider

    特性:
    - 使用原生 OpenAI API
    - 不支持 thinking 和 web_search
    - 支持流式输出和工具调用
    """

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="OpenAI",
            provider_id="openai",
            base_url=None,  # 使用默认 OpenAI API
            default_model="gpt-4o",
            capabilities={
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
            },
            env_key_name="OPENAI_API_KEY"
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
        """创建 ChatOpenAI 模型实例"""
        # OpenAI 不支持 thinking 和 search，忽略这些参数
        if enable_search:
            logger.warning("OpenAI 不支持 web_search，已忽略该参数")
        if enable_thinking:
            logger.warning("OpenAI 不支持 thinking，已忽略该参数")

        model_kwargs = self.get_model_kwargs(**kwargs)

        return ChatOpenAI(
            model=model or self.config.default_model,
            temperature=temperature,
            api_key=api_key,
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
        OpenAI 参数格式:
        - 不支持 web_search 和 thinking
        """
        model_kwargs = {}

        # 合并其他 kwargs
        model_kwargs.update(kwargs.get("extra_model_kwargs", {}))

        return model_kwargs


# 单例实例
openai_provider = OpenAIProvider()
