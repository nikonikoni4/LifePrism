"""
Commitment 服务层 - 承诺模块业务逻辑

架构：纯函数模块（无内存缓存，不需要单例）
含状态转换校验逻辑。
"""
from typing import Optional

from lifeprism.server.schemas.value_schemas import (
    CommitmentItem,
    CommitmentListResponse,
    CreateCommitmentRequest,
    UpdateCommitmentRequest,
)
from lifeprism.server.providers.commitment_provider import commitment_provider
from lifeprism.server.providers.value_provider import value_provider
from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 合法的状态转换集合
VALID_TRANSITIONS = {
    ('active', 'completed'),
    ('completed', 'active'),
    ('active', 'archived'),
    ('archived', 'active'),
}


def _convert_to_commitment_item(item: dict) -> CommitmentItem:
    """将数据库记录转换为 CommitmentItem"""
    return CommitmentItem(
        id=item['id'],
        content=item['content'],
        value_id=item.get('value_id'),
        value_keyword=item.get('value_keyword'),
        status=item['status'],
        created_at=item.get('created_at', ''),
        updated_at=item.get('updated_at'),
    )


def get_commitments(status: Optional[str] = None, value_id: Optional[str] = None) -> CommitmentListResponse:
    """
    获取承诺列表

    Args:
        status: 状态筛选，支持逗号分隔多值
        value_id: 按价值 ID 筛选
    """
    items = commitment_provider.get_commitments(status, value_id)
    return CommitmentListResponse(
        items=[_convert_to_commitment_item(item) for item in items],
        total=len(items),
    )


def get_commitment_detail(commitment_id: str) -> Optional[CommitmentItem]:
    """
    获取单条承诺详情

    Args:
        commitment_id: 承诺 ID (格式: cmt-xxx)

    Returns:
        Optional[CommitmentItem]: 承诺详情，不存在返回 None
    """
    item = commitment_provider.get_commitment_by_id(commitment_id)
    if not item:
        return None
    return _convert_to_commitment_item(item)


def create_commitment(request: CreateCommitmentRequest) -> Optional[CommitmentItem]:
    """
    创建承诺（校验 value_id 存在性）

    Args:
        request: 创建请求

    Returns:
        Optional[CommitmentItem]: 新创建的承诺，失败返回 None

    Raises:
        ValueError: value_id 不存在
    """
    value = value_provider.get_value_by_id(request.value_id)
    if not value:
        raise ValueError(f"价值不存在: {request.value_id}")

    data = {'content': request.content, 'value_id': request.value_id}
    new_id = commitment_provider.create_commitment(data)
    if not new_id:
        return None
    item = commitment_provider.get_commitment_by_id(new_id)
    return _convert_to_commitment_item(item) if item else None


def update_commitment(commitment_id: str, request: UpdateCommitmentRequest) -> Optional[CommitmentItem]:
    """
    更新承诺（含状态转换校验）

    Args:
        commitment_id: 承诺 ID
        request: 更新请求

    Returns:
        Optional[CommitmentItem]: 更新后的承诺，不存在返回 None

    Raises:
        ValueError: 非法状态转换 / 无效 value_id
    """
    existing = commitment_provider.get_commitment_by_id(commitment_id)
    if not existing:
        return None

    explicitly_set = request.model_fields_set
    update_data = {}

    if 'status' in explicitly_set and request.status is not None:
        current_status = existing['status']
        new_status = request.status
        if current_status != new_status:
            if (current_status, new_status) not in VALID_TRANSITIONS:
                raise ValueError(f"不允许从 {current_status} 转换到 {new_status}")
            update_data['status'] = new_status

    if 'value_id' in explicitly_set and request.value_id is not None:
        value = value_provider.get_value_by_id(request.value_id)
        if not value:
            raise ValueError(f"价值不存在: {request.value_id}")
        update_data['value_id'] = request.value_id

    if 'content' in explicitly_set:
        update_data['content'] = request.content

    if update_data:
        commitment_provider.update_commitment(commitment_id, update_data)

    item = commitment_provider.get_commitment_by_id(commitment_id)
    return _convert_to_commitment_item(item) if item else None


def delete_commitment(commitment_id: str) -> bool:
    """
    删除承诺

    Args:
        commitment_id: 承诺 ID

    Returns:
        bool: 是否成功
    """
    return commitment_provider.delete_commitment(commitment_id)

