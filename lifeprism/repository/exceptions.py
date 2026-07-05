"""Repository 模块异常定义。

Repository 模块所有异常继承自 RepositoryError(DataAccessError)，
由 API 层的全局异常处理器统一转换为 HTTP 500。
"""
from lifeprism.utils.exceptions import DataAccessError


from lifeprism.utils.exceptions import ConflictError, NotFoundError


class RepositoryError(DataAccessError):
    """Repository 模块基础异常。"""
    pass


class EntityNotFoundError(NotFoundError):
    """通用实体未找到（数据库返回空结果）。

    替代目前在 Provider 中 return None 的做法，
    让调用方能区分"不存在"和"数据库故障"。
    """

    def __init__(self, entity_type: str, entity_id: str, **extra_details):
        super().__init__(
            message=f"{entity_type} 未找到: {entity_id}",
            code=f"{entity_type.upper()}_NOT_FOUND",
            details={
                "entity_type": entity_type,
                "entity_id": entity_id,
                **extra_details,
            },
        )


class DuplicateEntityError(ConflictError):
    """唯一约束冲突（INSERT 时已存在）。"""

    def __init__(self, entity_type: str, entity_id: str, conflict_field: str = ""):
        msg = f"{entity_type} 已存在: {entity_id}"
        if conflict_field:
            msg += f" (冲突字段: {conflict_field})"
        super().__init__(
            message=msg,
            code=f"{entity_type.upper()}_ALREADY_EXISTS",
            details={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "conflict_field": conflict_field,
            },
        )
