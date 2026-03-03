"""业务异常到 HTTP 错误响应的统一映射。"""
from typing import Any, Dict, Tuple

from fastapi import HTTPException

from lifeprism.server.errors.error_codes import (
    BACKFILL_DATE_OUT_OF_WINDOW,
    CANNOT_CANCEL_PAST_CHECKIN,
    CHAIN_NODE_VALIDATION_FAILED,
    CHAIN_NOT_FOUND,
    CHAIN_VALIDATION_FAILED,
    CHALLENGE_NOT_FOUND,
    CHECKIN_ALREADY_EXISTS,
    CHECKIN_NOT_FOUND,
    CONFLICT,
    HABIT_NOT_ACTIVE,
    HABIT_NOT_FOUND,
    INTERNAL_ERROR,
    INVALID_STATUS_TRANSITION,
    NODE_NOT_FOUND,
    NOT_FOUND,
    REORDER_VALIDATION_FAILED,
    VALIDATION_FAILED,
)
from lifeprism.utils.exceptions import ConflictError, DataAccessError, LWBaseError, NotFoundError, ValidationError

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
    NOT_FOUND: 404,
    CONFLICT: 409,
    VALIDATION_FAILED: 422,
    INTERNAL_ERROR: 500,
}


def _fallback_code(error: LWBaseError) -> str:
    if isinstance(error, NotFoundError):
        return NOT_FOUND
    if isinstance(error, ConflictError):
        return CONFLICT
    if isinstance(error, ValidationError):
        return VALIDATION_FAILED
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
