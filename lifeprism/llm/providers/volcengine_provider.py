"""
火山引擎 (VolcEngine/Doubao) Provider

使用 langchain_openai.ChatOpenAI (OpenAI 兼容接口) 调用火山引擎原生接口

修改记录:
- 2026-02-12: 硬编码禁用网络搜索功能（enable_search 强制为 False）
  当前仅保留阿里云的网络搜索服务，火山引擎默认不启用搜索。
  如需重新启用，将 get_model_kwargs 中的 enable_search 硬编码覆盖移除即可。
- 2026-02-25: 将自定义 ChatVolcEngine 替换为 langchain_openai.ChatOpenAI
  原因: 自定义的 ChatVolcEngine 继承 BaseChatModel 但未实现 bind_tools 方法，
  导致 norm_chat 调用 bind_tools 时抛出 NotImplementedError。
  ChatOpenAI 已内置完整的 bind_tools 支持，且火山引擎接口与 OpenAI 兼容。
"""

import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from .base_provider import BaseLLMProvider, ProviderCapability, ProviderConfig

logger = logging.getLogger(__name__)


class VolcEngineProvider(BaseLLMProvider):
    """
    火山引擎 (VolcEngine/Doubao) Provider

    特性:
    - 使用 ChatOpenAI（OpenAI 兼容接口）调用火山引擎原生接口
    - 支持 web_search 启用网络搜索
    - 支持 thinking 启用深度思考
    - 支持 bind_tools 工具调用

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
        """创建 ChatOpenAI 模型实例（火山引擎兼容）"""
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
        火山引擎参数格式:
        - extra_body.web_search: {"enable": true}
        - extra_body.thinking: {"type": "enabled"}

        注意: 火山引擎特有参数需通过 extra_body 传递
        """
        model_kwargs = {}

        # 硬编码禁用：当前仅保留阿里云搜索服务，火山引擎暂不启用
        enable_search = False
        if enable_search and self.supports(ProviderCapability.WEB_SEARCH):
            # 火山引擎特有参数需要通过 extra_body 传递
            model_kwargs.setdefault("extra_body", {})
            model_kwargs["extra_body"]["web_search"] = {"enable": True}

        if enable_thinking and self.supports(ProviderCapability.THINKING):
            model_kwargs.setdefault("extra_body", {})
            model_kwargs["extra_body"]["thinking"] = {"type": "enabled"}

        # 合并其他 kwargs
        model_kwargs.update(kwargs.get("extra_model_kwargs", {}))

        return model_kwargs


# 单例实例
volcengine_provider = VolcEngineProvider()
