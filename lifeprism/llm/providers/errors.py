"""Provider error classification; this module describes failures without choosing recovery."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from typing import Any, Literal

import openai
from litellm import exceptions as lite

from lifeprism.llm.exceptions import LLMError


class ProviderErrorKind(StrEnum):
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UNAVAILABLE = "unavailable"
    REQUEST = "request"
    QUOTA_EXCEEDED = "quota_exceeded"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"


class LLMProviderError(LLMError):
    """Stable provider failure facts. Recovery policy belongs to the agent loop."""

    def __init__(
        self,
        message: str,
        *,
        kind: ProviderErrorKind | str,
        reason: str,
        provider: str,
        model: str,
        status_code: int | None = None,
        provider_error_code: str | None = None,
        phase: Literal["request", "streaming", "response"] = "request",
        partial_output: bool = False,
        retry_after: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.kind = ProviderErrorKind(kind)
        self.reason = reason
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.provider_error_code = provider_error_code
        self.phase = phase
        self.partial_output = partial_output
        self.retry_after = retry_after
        super().__init__(
            message=message, code="LLM_PROVIDER_ERROR", cause=cause, details=self._facts()
        )

    def _facts(self) -> dict[str, Any]:
        return {
            key: getattr(self, key)
            for key in (
                "kind",
                "reason",
                "provider",
                "model",
                "status_code",
                "provider_error_code",
                "phase",
                "partial_output",
                "retry_after",
            )
        }


def _error_code(error: BaseException) -> str | None:
    seen = set()
    current = error
    for _ in range(5):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        body = getattr(current, "body", None)
        if not isinstance(body, dict):
            response = getattr(current, "response", None)
            try:
                body = response.json() if response is not None else None
            except (ValueError, AttributeError):
                body = None
        if isinstance(body, dict):
            payload = body.get("error", body)
            if isinstance(payload, dict) and payload.get("code"):
                return str(payload["code"])
        code = getattr(current, "code", None)
        if code and str(code) not in ("429", "500"):
            return str(code)
        current = current.__cause__
    return None


def _retry_after(error: BaseException) -> float | None:
    response = getattr(error, "response", None)
    value = getattr(response, "headers", {}).get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


def classify_provider_error(error, *, provider, model, phase="request", partial_output=False):
    """Normalize SDK errors only; cancellation and programming failures pass through."""
    if isinstance(error, LLMProviderError):
        if phase == "streaming":
            error.phase = phase
        error.partial_output |= partial_output
        error.details.update(error._facts())
        return error
    if not isinstance(error, (openai.OpenAIError, lite.BudgetExceededError)):
        return error
    code = _error_code(error)
    status = getattr(error, "status_code", None)
    kind, reason = "unknown", "unknown"
    if isinstance(error, lite.BudgetExceededError) or code in {
        "insufficient_quota",
        "billing_hard_limit_reached",
        "budget_exceeded",
        "billing_not_active",
        "credit_balance_too_low",
    }:
        kind, reason = "quota_exceeded", code or "budget_exceeded"
    elif isinstance(error, openai.APITimeoutError):
        kind, reason = "timeout", "timeout"
    elif isinstance(error, openai.APIConnectionError):
        kind, reason = "connection", "connection"
    elif isinstance(error, openai.APIResponseValidationError):
        kind, reason = "invalid_response", "validation"
    else:
        specific = (
            (lite.ContextWindowExceededError, "context_limit"),
            (lite.ContentPolicyViolationError, "content_policy"),
            (lite.UnsupportedParamsError, "unsupported"),
            (openai.AuthenticationError, "authentication"),
            (openai.PermissionDeniedError, "permission"),
            (openai.NotFoundError, "not_found"),
            (openai.BadRequestError, "invalid"),
        )
        for cls, request_reason in specific:
            if isinstance(error, cls):
                kind, reason = "request", request_reason
                break
        else:
            if isinstance(error, openai.RateLimitError) or status == 429:
                kind, reason = "rate_limit", "rate_limit"
            elif status is not None and status >= 500:
                kind, reason = "unavailable", "service_unavailable"
            elif status in (400, 401, 403, 404, 422):
                kind, reason = (
                    "request",
                    {401: "authentication", 403: "permission", 404: "not_found"}.get(
                        status, "invalid"
                    ),
                )
    return LLMProviderError(
        str(error),
        kind=kind,
        reason=reason,
        provider=provider,
        model=model,
        status_code=status,
        provider_error_code=code,
        phase=phase,
        partial_output=partial_output,
        retry_after=_retry_after(error),
        cause=error,
    )
