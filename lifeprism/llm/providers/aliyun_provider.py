"""
阿里云百炼 (Aliyun/DashScope) Provider

使用 langchain_community.chat_models.ChatTongyi
"""

import logging
from typing import Any, Dict

from langchain_community.chat_models import ChatTongyi
import langchain_community.llms.tongyi as llms_tongyi_module
import langchain_community.chat_models.tongyi as chat_tongyi_module
from langchain_core.language_models.chat_models import BaseChatModel

from .base_provider import BaseLLMProvider, ProviderCapability, ProviderConfig

logger = logging.getLogger(__name__)


# Monkey patch check_response 来修复 langchain-community 的 bug
# 原始函数在抛出 HTTPError 时传入了 DashScope Response 对象,导致 KeyError: 'request'
def _patched_check_response(resp):
    """修复后的 check_response,在抛出异常前打印真实错误信息

    注意: resp 可能是两种类型:
    - 对象类型 (有 status_code 属性): 成功的响应或某些错误响应
    - dict 类型: 流式响应的 chunk 或某些 API 返回格式
    """
    # 根据 resp 类型获取 status_code
    if isinstance(resp, dict):
        status_code = resp.get('status_code', 200)
        get_value = lambda key, default='unknown': resp.get(key, default)
    else:
        status_code = getattr(resp, 'status_code', 200)
        get_value = lambda key, default='unknown': getattr(
            resp, key,
            resp.get(key, default) if hasattr(resp, 'get') else default
        )

    if status_code != 200:
        error_info = (
            f"\n{'='*60}\n"
            f"通义千问 API 调用失败!\n"
            f"  status_code: {get_value('status_code')}\n"
            f"  code: {get_value('code')}\n"
            f"  message: {get_value('message')}\n"
            f"{'='*60}\n"
        )
        logger.error(error_info)
        print(error_info)

        raise RuntimeError(
            f"通义千问 API 错误: status_code={get_value('status_code')}, "
            f"code={get_value('code')}, message={get_value('message')}"
        )
    return resp


# 应用 monkey patch 到两个模块
llms_tongyi_module.check_response = _patched_check_response
chat_tongyi_module.check_response = _patched_check_response


class AliyunProvider(BaseLLMProvider):
    """
    阿里云百炼 (DashScope) Provider

    特性:
    - 使用 ChatTongyi
    - 支持 enable_thinking=True 启用深度思考
    - 支持 enable_search=True 启用网络搜索
    """

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig(
            name="阿里云百炼 (Aliyun)",
            provider_id="aliyun",
            base_url=None,  # ChatTongyi 内部处理
            default_model="qwen-plus",
            capabilities={
                ProviderCapability.WEB_SEARCH,
                ProviderCapability.THINKING,
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
            },
            env_key_name="DASHSCOPE_API_KEY"
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
        """创建 ChatTongyi 模型实例"""
        model_kwargs = self.get_model_kwargs(
            enable_search=enable_search,
            enable_thinking=enable_thinking,
            **kwargs
        )

        return ChatTongyi(
            model=model or self.config.default_model,
            temperature=temperature,
            dashscope_api_key=api_key,
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
        阿里云参数格式:
        - enable_search: True/False
        - enable_thinking: True/False
        """
        model_kwargs = {}

        if enable_search and self.supports(ProviderCapability.WEB_SEARCH):
            model_kwargs["enable_search"] = True

        if enable_thinking and self.supports(ProviderCapability.THINKING):
            model_kwargs["enable_thinking"] = True

        # 合并其他 kwargs
        model_kwargs.update(kwargs.get("extra_model_kwargs", {}))

        return model_kwargs


# 单例实例
aliyun_provider = AliyunProvider()
