"""
业务异常定义

层级职责：
- Provider 层：捕获外部异常，转换为下列业务异常
- Service 层：通常让异常冒泡，必要时捕获包装
- API 层：捕获业务异常映射为 HTTPException
"""


class LWBaseError(Exception):
    """项目异常基类"""


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
