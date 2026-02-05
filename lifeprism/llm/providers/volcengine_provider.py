"""
火山引擎 (VolcEngine/Doubao) Provider

使用 OpenAI SDK 调用火山引擎原生接口，包装为 LangChain 兼容的 ChatModel
"""

import logging
from typing import Any, Dict, List, Optional, Iterator

from openai import OpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

from .base_provider import BaseLLMProvider, ProviderCapability, ProviderConfig

logger = logging.getLogger(__name__)


class ChatVolcEngine(BaseChatModel):
    """
    火山引擎 LangChain ChatModel 包装器

    使用 OpenAI SDK 调用火山引擎的 chat/completions 接口
    """

    client: Any = None
    model: str = "doubao-1-5-pro-32k-250115"
    temperature: float = 0.7
    streaming: bool = False
    model_kwargs: Dict[str, Any] = {}

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-1-5-pro-32k-250115",
        temperature: float = 0.7,
        streaming: bool = False,
        model_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
        self.model = model
        self.temperature = temperature
        self.streaming = streaming
        self.model_kwargs = model_kwargs or {}

    @property
    def _llm_type(self) -> str:
        return "volcengine-doubao"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """将 LangChain 消息转换为 OpenAI 格式"""
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})
            else:
                # 默认作为 user 消息
                result.append({"role": "user", "content": str(msg.content)})
        return result

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """同步生成"""
        openai_messages = self._convert_messages(messages)

        # 合并参数
        request_kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            **self.model_kwargs,
            **kwargs
        }

        if stop:
            request_kwargs["stop"] = stop

        # 调用 API
        response = self.client.chat.completions.create(**request_kwargs)

        # 解析响应
        content = response.choices[0].message.content or ""

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=content))],
            llm_output={
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            }
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """异步生成 - 使用同步方法（OpenAI SDK 的异步需要 AsyncOpenAI）"""
        # 简单实现：直接调用同步方法
        # 如果需要真正的异步，可以使用 AsyncOpenAI
        return self._generate(messages, stop, run_manager, **kwargs)


class VolcEngineProvider(BaseLLMProvider):
    """
    火山引擎 (VolcEngine/Doubao) Provider

    特性:
    - 使用 OpenAI SDK 调用火山引擎原生接口
    - 支持 web_search 启用网络搜索
    - 支持 thinking 启用深度思考

    注意:
    - 火山引擎需要使用 Endpoint ID（格式：ep-xxx）而不是模型名称
    - 用户需要在火山引擎控制台创建推理接入点获取 Endpoint ID
    """

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="火山引擎 (VolcEngine)",
            provider_id="volcengine",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            default_model="ep-xxxxxxxxxx",  # 需要用户填写自己的 Endpoint ID
            capabilities={
                ProviderCapability.WEB_SEARCH,
                ProviderCapability.THINKING,
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
            },
            env_key_name="ARK_API_KEY"
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
        """创建 ChatVolcEngine 模型实例"""
        model_kwargs = self.get_model_kwargs(
            enable_search=enable_search,
            enable_thinking=enable_thinking,
            **kwargs
        )

        return ChatVolcEngine(
            api_key=api_key,
            model=model or self.config.default_model,
            temperature=temperature,
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
        火山引擎参数格式:
        - web_search: {"enable": true}
        - thinking: {"type": "enabled"}
        """
        model_kwargs = {}

        if enable_search and self.supports(ProviderCapability.WEB_SEARCH):
            model_kwargs["web_search"] = {"enable": True}

        if enable_thinking and self.supports(ProviderCapability.THINKING):
            model_kwargs["thinking"] = {"type": "enabled"}

        # 合并其他 kwargs
        model_kwargs.update(kwargs.get("extra_model_kwargs", {}))

        return model_kwargs


# 单例实例
volcengine_provider = VolcEngineProvider()
