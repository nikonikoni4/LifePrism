"""
Kimi (Moonshot AI) Provider

使用 langchain_openai.ChatOpenAI (OpenAI 兼容接口)
"""

import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from .base_provider import BaseLLMProvider, ProviderCapability, ProviderConfig

logger = logging.getLogger(__name__)


class KimiProvider(BaseLLMProvider):
    """
    Kimi (Moonshot AI) Provider

    特性:
    - 使用 OpenAI 兼容接口
    - 支持流式输出和工具调用
    - 不支持 web_search 和 thinking
    """

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="Kimi (Moonshot AI)",
            provider_id="kimi",
            base_url="https://api.moonshot.cn/v1",
            default_model="moonshot-v1-128k",
            capabilities={
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
            },
            env_key_name="MOONSHOT_API_KEY"
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
        """创建 ChatOpenAI 模型实例（Kimi 兼容）"""
        if enable_search:
            logger.warning("Kimi 不支持 web_search，已忽略该参数")
        if enable_thinking:
            logger.warning("Kimi 不支持 thinking，已忽略该参数")

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
        Kimi 参数格式:
        - 不支持 web_search 和 thinking
        """
        model_kwargs = {}

        # 合并其他 kwargs
        model_kwargs.update(kwargs.get("extra_model_kwargs", {}))

        return model_kwargs


# 单例实例
kimi_provider = KimiProvider()
