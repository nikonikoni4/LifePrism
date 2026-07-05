"""业务异常定义。"""
from typing import Any, Dict, Optional


class LWBaseError(Exception):
    """项目异常基类。

    所有业务异常必须继承此类。通过 code / details / cause 携带结构化上下文，
    to_dict() 提供统一的 JSON 序列化接口。
    """

    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        final_message = message or self.__class__.__name__
        self.code = code
        self.message = final_message
        self.details = details or {}
        self.cause = cause
        super().__init__(final_message)
        if cause is not None:
            self.__cause__ = cause

    def to_dict(self) -> Dict[str, Any]:
        """将异常序列化为 API 响应格式。"""
        result: Dict[str, Any] = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }
        if self.cause is not None:
            result["cause"] = str(self.cause)
        return result


class DataAccessError(LWBaseError):
    """Provider 层数据库操作失败"""


class NotFoundError(LWBaseError):
    """资源不存在，API 层应转换为 404"""


class ConflictError(LWBaseError):
    """资源冲突（如 UNIQUE 约束违反），API 层应转换为 409"""


class ValidationError(LWBaseError):
    """业务校验失败（非 Pydantic 校验），API 层应转换为 422"""


class ExternalServiceError(LWBaseError):
    """外部服务调用失败（LLM/网络）"""
