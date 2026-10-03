"""LLM 重试策略：订阅 request/error，只裁决，由 myagent loop 执行。"""

from collections.abc import Awaitable, Callable
from typing import Any

from myagent.infra.events.payload import RequestErrorPayLoad

from lifeprism.llm.providers.errors import LLMProviderError, ProviderErrorKind


class LLMRetry:
    """认领瞬时 provider 错误，其余错误委托给 waterfall 后续处理器。

    重试预算由 AgentConfig.max_retry_count 控制。loop 负责指数退避、消费
    error.details 中的 Retry-After、写入 llm/retry 记录及重新执行请求。
    """

    backoff_retry_kinds = frozenset(
        {
            ProviderErrorKind.CONNECTION,
            ProviderErrorKind.TIMEOUT,
            ProviderErrorKind.RATE_LIMIT,
            ProviderErrorKind.UNAVAILABLE,
        }
    )
    backoff_policy = {"base_delay": 1.0, "multiplier": 2.0, "cap": 30.0}

    def __init__(self, policy: dict[str, float] | None = None):
        """Accept a per-context snapshot of native backoff parameters."""
        self.backoff_policy = dict(policy if policy is not None else type(self).backoff_policy)

    async def request_error_event(
        self,
        payload: RequestErrorPayLoad,
        _next: Callable[[], Awaitable[Any]],
    ) -> Any:
        """返回 loop 的退避重试裁决，或 await 下一个订阅方。

        Args:
            payload: error_type 携带实际异常对象。
            _next: waterfall 下一个订阅方。

        Returns:
            loop 使用的 decision/policy，或后续订阅方的裁决。
        """
        error = payload.error_type
        if (
            isinstance(error, LLMProviderError)
            and error.kind in self.backoff_retry_kinds
            and not error.partial_output
        ):
            return {"decision": "backoff_retry", "policy": dict(self.backoff_policy)}
        return await _next()
