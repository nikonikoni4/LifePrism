"""
Value 服务层 - 价值模块业务逻辑

架构：纯函数模块（无内存缓存，不需要单例）

级联删除协调（Slice 05 重构）：
- cascade=True：CommitmentProvider.delete_by_value_id（删除关联承诺，含写墓碑）
  + ValueProvider.delete_value（删除价值本身，含写墓碑）
- cascade=False：CommitmentProvider.null_value_id（置空关联承诺的 value_id，不写墓碑）
  + ValueProvider.delete_value（删除价值本身，含写墓碑）

级联协调属于业务逻辑，放在 Service 层；Provider 层只做单表 CRUD。
"""

import sqlite3

from lifeprism.repository.providers.commitment_provider import commitment_provider
from lifeprism.repository.providers.value_provider import value_provider
from lifeprism.server.schemas.commitment_schemas import CommitmentBriefItem
from lifeprism.server.schemas.value_schemas import (
    CreateValueRequest,
    UpdateValueRequest,
    ValueDetailItem,
    ValueItem,
    ValueListResponse,
)
from lifeprism.utils import ConflictError, get_logger

logger = get_logger(__name__)


def _convert_to_value_item(item: dict) -> ValueItem:
    """将数据库记录转换为 ValueItem"""
    return ValueItem(
        id=item["id"],
        keywords=item["keywords"],
        content_positive=item.get("content_positive"),
        content_negative=item.get("content_negative"),
        sort_order=item.get("sort_order", 0),
        created_at=item.get("created_at", ""),
        updated_at=item.get("updated_at"),
    )


def _convert_to_commitment_brief(item: dict) -> CommitmentBriefItem:
    """将数据库记录转换为 CommitmentBriefItem"""
    return CommitmentBriefItem(
        id=item["id"],
        content=item["content"],
        status=item["status"],
        created_at=item.get("created_at", ""),
    )


def get_values() -> ValueListResponse:
    """获取所有价值列表"""
    items = value_provider.get_values()
    return ValueListResponse(items=[_convert_to_value_item(item) for item in items])


def get_value_detail(value_id: str) -> ValueDetailItem | None:
    """
    获取价值详情（含关联承诺列表）

    Args:
        value_id: 价值 ID (格式: val-xxx)

    Returns:
        Optional[ValueDetailItem]: 价值详情，不存在返回 None
    """
    item = value_provider.get_value_by_id(value_id)
    if not item:
        return None

    commitments_data = commitment_provider.get_commitments_by_value(value_id)
    commitments = [_convert_to_commitment_brief(c) for c in commitments_data]

    return ValueDetailItem(
        id=item["id"],
        keywords=item["keywords"],
        content_positive=item.get("content_positive"),
        content_negative=item.get("content_negative"),
        sort_order=item.get("sort_order", 0),
        created_at=item.get("created_at", ""),
        updated_at=item.get("updated_at"),
        commitments=commitments,
    )


def create_value(request: CreateValueRequest) -> ValueItem | None:
    """
    创建价值

    Args:
        request: 创建请求

    Returns:
        Optional[ValueItem]: 新创建的价值，失败返回 None

    Raises:
        ConflictError: keywords 已存在
    """
    from lifeprism.utils.exceptions import DataAccessError

    data = request.model_dump()
    try:
        new_id = value_provider.create_value(data)
    except DataAccessError as e:
        # _generic_insert 将 sqlite3.IntegrityError（含 UNIQUE 冲突）包装为 DataAccessError
        # 此处检查 cause 是否为 IntegrityError，是则转 ConflictError（409），否则原样抛出
        if isinstance(e.cause, sqlite3.IntegrityError):
            raise ConflictError(f"keywords 已存在: {request.keywords}") from e
        raise
    if not new_id:
        return None
    item = value_provider.get_value_by_id(new_id)
    return _convert_to_value_item(item) if item else None


def update_value(value_id: str, request: UpdateValueRequest) -> ValueItem | None:
    """
    更新价值（部分更新）

    Args:
        value_id: 价值 ID
        request: 更新请求

    Returns:
        Optional[ValueItem]: 更新后的价值，不存在返回 None
    """
    existing = value_provider.get_value_by_id(value_id)
    if not existing:
        return None

    update_data = request.model_dump(exclude_unset=True)

    if update_data:
        value_provider.update_value(value_id, update_data)

    item = value_provider.get_value_by_id(value_id)
    return _convert_to_value_item(item) if item else None


def delete_value(value_id: str, cascade: bool) -> bool:
    """删除价值（Service 层协调级联删除）

    Slice 05 重构：级联协调从 Provider 层上移到 Service 层。
    - cascade=True：先调用 CommitmentProvider.delete_by_value_id 删除关联承诺（含写墓碑），
      再调用 ValueProvider.delete_value 删除价值本身（含写墓碑）
    - cascade=False：先调用 CommitmentProvider.null_value_id 置空关联承诺的 value_id
      （不删除承诺记录，不写墓碑），再调用 ValueProvider.delete_value 删除价值本身（含写墓碑）

    Args:
        value_id: 价值 ID
        cascade: True=级联删除承诺，False=置空关联承诺的 value_id

    Returns:
        bool: 是否成功（价值不存在时返回 False）
    """
    existing = value_provider.get_value_by_id(value_id)
    if not existing:
        return False

    # 先处理关联承诺（级联协调）
    if cascade:
        # 级联删除：删除该价值下所有承诺（含写墓碑到 commitments 墓碑表）
        deleted_count = commitment_provider.delete_by_value_id(value_id)
        logger.info("级联删除价值 %s 下 %s 条承诺", value_id, deleted_count)
    else:
        # 置空关联：将该价值下所有承诺的 value_id 置为 NULL（不删除承诺，不写墓碑）
        updated_count = commitment_provider.null_value_id(value_id)
        logger.info("置空价值 %s 下 %s 条承诺的 value_id", value_id, updated_count)

    # 再删除价值本身（走 _generic_delete，含写墓碑到 user_values 墓碑表）
    return value_provider.delete_value(value_id)
