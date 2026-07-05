"""业务异常到 HTTP 错误响应的统一映射。"""
from typing import Any, Dict, Tuple

from fastapi import HTTPException

from lifeprism.server.errors.error_codes import (
    BACKFILL_DATE_OUT_OF_WINDOW,
    CACHE_UPDATE_ERROR,
    CANNOT_CANCEL_PAST_CHECKIN,
    CHAIN_NODE_VALIDATION_FAILED,
    CHAIN_NOT_FOUND,
    CHAIN_VALIDATION_FAILED,
    CHALLENGE_NOT_FOUND,
    CHECKIN_ALREADY_EXISTS,
    CHECKIN_NOT_FOUND,
    CLASSIFICATION_ERROR,
    CONFIG_FILE_NOT_FOUND,
    CONFLICT,
    ENTITY_ALREADY_EXISTS,
    ENTITY_NOT_FOUND,
    EXTERNAL_SERVICE_ERROR,
    HABIT_NOT_ACTIVE,
    HABIT_NOT_FOUND,
    INTERNAL_ERROR,
    INVALID_CONFIG,
    INVALID_STATUS_TRANSITION,
    LLM_OUTPUT_PARSE_ERROR,
    LLM_RESPONSE_ERROR,
    NODE_NOT_FOUND,
    NOT_FOUND,
    PROMPT_NOT_FOUND,
    REORDER_VALIDATION_FAILED,
    VALIDATION_FAILED,
)
from lifeprism.utils.exceptions import (
    ConflictError, DataAccessError, ExternalServiceError,
    LWBaseError, NotFoundError, ValidationError,
)
from lifeprism.config.exceptions import ConfigError

ERROR_CODE_TO_STATUS: Dict[str, int] = {
    HABIT_NOT_FOUND: 404,
    CHALLENGE_NOT_FOUND: 404,
    CHECKIN_NOT_FOUND: 404,
    CHAIN_NOT_FOUND: 404,
    NODE_NOT_FOUND: 404,
    CHECKIN_ALREADY_EXISTS: 409,
    HABIT_NOT_ACTIVE: 422,
    BACKFILL_DATE_OUT_OF_WINDOW: 422,
    CANNOT_CANCEL_PAST_CHECKIN: 422,
    INVALID_STATUS_TRANSITION: 422,
    CHAIN_VALIDATION_FAILED: 422,
    CHAIN_NODE_VALIDATION_FAILED: 422,
    REORDER_VALIDATION_FAILED: 422,
    # 通用
    NOT_FOUND: 404,
    CONFLICT: 409,
    VALIDATION_FAILED: 422,
    INTERNAL_ERROR: 500,
    EXTERNAL_SERVICE_ERROR: 503,
    # LLM 模块
    LLM_RESPONSE_ERROR: 503,
    LLM_OUTPUT_PARSE_ERROR: 503,
    PROMPT_NOT_FOUND: 404,
    # Repository 模块
    ENTITY_NOT_FOUND: 404,
    ENTITY_ALREADY_EXISTS: 409,
    # Processor 模块
    CLASSIFICATION_ERROR: 500,
    CACHE_UPDATE_ERROR: 500,
    # Config 模块
    CONFIG_FILE_NOT_FOUND: 500,
    INVALID_CONFIG: 500,
}


def _fallback_code(error: LWBaseError) -> str:
    if isinstance(error, NotFoundError):
        return NOT_FOUND
    if isinstance(error, ConflictError):
        return CONFLICT
    if isinstance(error, ValidationError):
        return VALIDATION_FAILED
    if isinstance(error, ExternalServiceError):
        return EXTERNAL_SERVICE_ERROR
    if isinstance(error, ConfigError):
        return INVALID_CONFIG
    if isinstance(error, DataAccessError):
        return INTERNAL_ERROR
    return INTERNAL_ERROR


def map_app_error(error: LWBaseError, default_code: str = None) -> Tuple[int, Dict[str, Any]]:
    """将 LWBaseError 映射为 HTTP status + detail payload。"""
    code = error.code or default_code or _fallback_code(error)
    status_code = ERROR_CODE_TO_STATUS.get(code)
    if status_code is None:
        status_code = 422 if isinstance(error, ValidationError) else 500

    detail = {
        "error_code": code,
        "message": error.message or str(error),
        "details": error.details or {},
    }
    return status_code, detail


def to_http_exception(error: LWBaseError, default_code: str = None) -> HTTPException:
    """将 LWBaseError 转换为 HTTPException。"""
    status_code, detail = map_app_error(error, default_code=default_code)
    return HTTPException(status_code=status_code, detail=detail)
