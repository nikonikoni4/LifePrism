"""
Commitment 服务层 - 承诺模块业务逻辑

架构：纯函数模块（无内存缓存，不需要单例）
含状态转换校验逻辑。
"""

from lifeprism.repository import commitment_repository as commitment_provider
from lifeprism.repository import value_repository as value_provider
from lifeprism.server.schemas.commitment_schemas import (
    CommitmentItem,
    CommitmentListResponse,
    CreateCommitmentRequest,
    UpdateCommitmentRequest,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 合法状态值集合
VALID_STATUSES = {"active", "completed", "archived"}

# 合法的状态转换集合
VALID_TRANSITIONS = {
    ("active", "completed"),
    ("completed", "active"),
    ("active", "archived"),
    ("archived", "active"),
}


def _convert_to_commitment_item(item: dict) -> CommitmentItem:
    """将数据库记录转换为 CommitmentItem"""
    return CommitmentItem(
        id=item["id"],
        content=item["content"],
        value_id=item.get("value_id"),
        value_keyword=item.get("value_keyword"),
        status=item["status"],
        created_at=item.get("created_at", ""),
        updated_at=item.get("updated_at"),
    )


def get_commitments(
    status: str | None = None, value_id: str | None = None
) -> CommitmentListResponse:
    """
    获取承诺列表

    Args:
        status: 状态筛选，支持逗号分隔多值（如 "active,archived"）
        value_id: 按价值 ID 筛选

    Raises:
        ValueError: status 包含非法值
    """
    # 校验 status 参数中的每个值是否合法
    if status:
        status_list = [s.strip() for s in status.split(",")]
        invalid = [s for s in status_list if s not in VALID_STATUSES]
        if invalid:
            raise ValueError(
                f"非法的 status 值: {', '.join(invalid)}。"
                f"允许的值: {', '.join(sorted(VALID_STATUSES))}"
            )

    items = commitment_provider.get_commitments(status, value_id)
    return CommitmentListResponse(
        items=[_convert_to_commitment_item(item) for item in items],
        total=len(items),
    )


def get_commitment_detail(commitment_id: str) -> CommitmentItem | None:
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


def create_commitment(request: CreateCommitmentRequest) -> CommitmentItem | None:
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

    data = {"content": request.content, "value_id": request.value_id}
    new_id = commitment_provider.create_commitment(data)
    if not new_id:
        return None
    item = commitment_provider.get_commitment_by_id(new_id)
    return _convert_to_commitment_item(item) if item else None


def update_commitment(
    commitment_id: str, request: UpdateCommitmentRequest
) -> CommitmentItem | None:
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

    update_data = request.model_dump(exclude_unset=True)

    # status 校验：不允许清空，需校验状态转换合法性
    if "status" in update_data:
        if update_data["status"] is None:
            raise ValueError("status 不允许清空")
        current_status = existing["status"]
        new_status = update_data["status"]
        if current_status == new_status:
            del update_data["status"]
        elif (current_status, new_status) not in VALID_TRANSITIONS:
            raise ValueError(f"不允许从 {current_status} 转换到 {new_status}")

    # value_id 校验：null 表示解除关联，非 null 需校验存在性
    if "value_id" in update_data and update_data["value_id"] is not None:
        value = value_provider.get_value_by_id(update_data["value_id"])
        if not value:
            raise ValueError(f"价值不存在: {update_data['value_id']}")

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
