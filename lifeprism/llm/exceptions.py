"""LLM 模块异常定义。

LLM 模块所有异常继承自 LLMError(ExternalServiceError)，
由 API 层的全局异常处理器统一转换为 HTTP 503。

注意：PromptNotFoundError 继承自 NotFoundError，因为 Prompt 文件缺失
是配置/部署问题（持久性错误），不是外部服务故障（临时性错误）。
"""

from lifeprism.utils.exceptions import ExternalServiceError, NotFoundError


class LLMError(ExternalServiceError):
    """LLM 模块基础异常。"""

    pass


class LLMResponseError(LLMError):
    """LLM 返回空响应或格式错误（非 None 但内容无效）。"""

    def __init__(self, model: str, raw_response: str = "", cause: Exception = None):
        super().__init__(
            message=f"LLM ({model}) 返回无效响应",
            code="LLM_RESPONSE_ERROR",
            details={
                "model": model,
                "raw_response": raw_response[:500],
            },
            cause=cause,
        )


class LLMOutputParseError(LLMError):
    """LLM 输出解析失败（JSON 解析、Schema 校验失败等）。"""

    def __init__(self, expected_fields: list, actual_keys: list, raw_output: str = ""):
        super().__init__(
            message=f"LLM 输出解析失败，期望字段: {expected_fields}，实际字段: {actual_keys}",
            code="LLM_OUTPUT_PARSE_ERROR",
            details={
                "expected": expected_fields,
                "actual": actual_keys,
                "raw": raw_output[:500],
            },
        )


class PromptNotFoundError(NotFoundError):
    """Prompt 模板文件不存在或加载失败。

    继承 NotFoundError 而非 LLMError，因为 Prompt 缺失是配置问题（持久性错误），
    不是外部服务故障（临时性错误）。返回 HTTP 404 而非 503，避免客户端误重试。
    """

    def __init__(self, prompt_name: str, module: str):
        super().__init__(
            message=f"Prompt '{prompt_name}' 不存在于模块 '{module}'",
            code="PROMPT_NOT_FOUND",
            details={
                "prompt_name": prompt_name,
                "module": module,
            },
        )
