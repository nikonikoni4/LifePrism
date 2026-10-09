"""RAG 失败诊断：分条记录调用链，脱敏凭据，不输出请求正文。"""

import logging
import re
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx

from lifeprism.rag.config import KEYS, SettingsSource


@contextmanager
def rag_stage(stage: str, **context: object) -> Iterator[None]:
    """在重新抛出的原异常上附加失败阶段及非正文上下文。"""
    try:
        yield
    except Exception as exc:
        exc.add_note(f"RAG stage={stage} " + " ".join(f"{k}={v}" for k, v in context.items()))
        raise


def _redactor(config: SettingsSource) -> Callable[..., str]:
    """一次读取凭据，为同一诊断的所有行复用脱敏器。"""
    secrets = [config.get_storage_key(key) for key in (*KEYS.values(), "sync_api_key")]

    def safe(value: object, limit: int = 1200) -> str:
        text = str(value)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"(?i)(Bearer\s+)[^\s'\"]+", r"\1[REDACTED]", text)
        text = re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[REDACTED]", text)
        return text.replace("\r", " ").replace("\n", " ")[:limit]

    return safe


def failure_summary(error: BaseException, config: SettingsSource) -> str:
    """供连接测试显示简短、脱敏后的具体原因。"""
    return f"{type(error).__name__}: {_redactor(config)(error, 500)}"


def log_rag_failure(
    logger: logging.Logger, label: str, error: BaseException, config: SettingsSource
) -> None:
    """逐条输出原因、HTTP 错误字段与栈帧，避开 2000 字符格式器截断。"""
    safe = _redactor(config)

    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        logger.error("%s: %s: %s", label, type(current).__name__, safe(current))
        for note in getattr(current, "__notes__", []):
            logger.error("%s context: %s", label, safe(note))
        if isinstance(current, httpx.HTTPStatusError):
            response = current.response
            logger.error("%s HTTP status=%s", label, response.status_code)
            if len(response.content) <= 65536:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                if isinstance(body, dict):
                    detail = body.get("error", body)
                    if isinstance(detail, dict):
                        for field in ("code", "message"):
                            if isinstance(detail.get(field), (str, int)):
                                logger.error(
                                    "%s provider %s=%s", label, field, safe(detail[field], 600)
                                )
        # 不读取源码行或局部变量：它们可能包含 Key 字面量、请求正文或文档内容。
        for frame, line in traceback.walk_tb(current.__traceback__):
            logger.error(
                "%s stack: File %s, line %s, in %s",
                label,
                safe(frame.f_code.co_filename),
                line,
                frame.f_code.co_name,
            )
        current = current.__cause__ or (
            current.__context__ if not current.__suppress_context__ else None
        )
