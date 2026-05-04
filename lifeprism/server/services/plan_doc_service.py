"""
PlanDoc 服务层 - Plan Doc 计划书业务逻辑

设计原则：数据库只存 meta 信息，内容存 md 文件
文件存储路径：lifeprismData/plan/{id}.md

架构：纯函数模块（无内存缓存，不需要单例）
"""
from typing import Optional
from pathlib import Path

from lifeprism.server.schemas.goal_schemas import (
    PlanDocItem,
    PlanDocListResponse,
    CreatePlanDocRequest,
    UpdatePlanDocRequest,
)
from lifeprism.repository import plan_doc_repository
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def _get_plan_doc_dir() -> Path:
    """获取计划书目录路径"""
    from lifeprism.config.settings_manager import settings
    return settings.lifeprism_data_path / "plan"

def _ensure_plan_doc_dir():
    """确保计划书目录存在"""
    try:
        _get_plan_doc_dir().mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"创建计划书目录失败: {e}")


def _get_plan_doc_path(doc_id: str) -> Path:
    """获取计划书文件路径"""
    return _get_plan_doc_dir() / f"{doc_id}.md"


def _read_content_from_file(doc_id: str) -> str:
    """从文件读取内容，不存在则返回空字符串"""
    file_path = _get_plan_doc_path(doc_id)
    try:
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        return ""
    except Exception as e:
        logger.error(f"读取计划书文件 {doc_id} 失败: {e}")
        return ""


def _write_content_to_file(doc_id: str, content: str):
    """写入内容到文件"""
    file_path = _get_plan_doc_path(doc_id)
    try:
        _ensure_plan_doc_dir()
        file_path.write_text(content, encoding='utf-8')
        logger.info(f"写入计划书文件 {doc_id} 成功")
    except Exception as e:
        logger.error(f"写入计划书文件 {doc_id} 失败: {e}")


def _delete_content_file(doc_id: str):
    """删除对应的 md 文件"""
    file_path = _get_plan_doc_path(doc_id)
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"删除计划书文件 {doc_id} 成功")
    except Exception as e:
        logger.error(f"删除计划书文件 {doc_id} 失败: {e}")


def _convert_db_item_to_plan_doc_item(item: dict, include_content: bool = False) -> PlanDocItem:
    """
    将数据库记录转换为 PlanDocItem

    Args:
        item: 数据库记录
        include_content: 是否从文件读取内容
    """
    content = ""
    if include_content:
        content = _read_content_from_file(item['id'])

    return PlanDocItem(
        id=item['id'],
        goal_id=item['goal_id'],
        content=content,
        status=item.get('status', 'active'),
        order_index=item.get('order_index', 0),
        created_at=item.get('created_at', ''),
        updated_at=item.get('updated_at')
    )


def get_plan_docs(
    goal_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> PlanDocListResponse:
    """
    获取计划书列表（只返回 meta 信息，不含 content）

    Args:
        goal_id: 按目标筛选
        doc_type: 按类型筛选（暂未使用）
        page: 页码
        page_size: 每页数量

    Returns:
        PlanDocListResponse: 计划书列表响应
    """
    if goal_id:
        items = plan_doc_repository.get_plan_docs_by_goal(goal_id)
    else:
        items = plan_doc_repository.get_all_plan_docs()

    plan_doc_items = [_convert_db_item_to_plan_doc_item(item, include_content=False) for item in items]
    return PlanDocListResponse(items=plan_doc_items)


def get_plan_docs_by_goal(goal_id: str) -> PlanDocListResponse:
    """
    获取指定目标的所有计划书（只返回 meta 信息）

    Args:
        goal_id: 目标 ID

    Returns:
        PlanDocListResponse: 计划书列表响应
    """
    items = plan_doc_repository.get_plan_docs_by_goal(goal_id)
    plan_doc_items = [_convert_db_item_to_plan_doc_item(item, include_content=False) for item in items]
    return PlanDocListResponse(items=plan_doc_items)


def get_plan_doc_detail(doc_id: str) -> Optional[PlanDocItem]:
    """
    获取计划书详情（meta + 文件内容）

    Args:
        doc_id: 计划书 ID

    Returns:
        Optional[PlanDocItem]: 计划书详情，不存在返回 None
    """
    item = plan_doc_repository.get_plan_doc_by_id(doc_id)
    if not item:
        return None
    return _convert_db_item_to_plan_doc_item(item, include_content=True)


def _check_plan_doc_id_exists(doc_id: str) -> tuple[bool, str]:
    """
    检查计划书 ID 是否已存在（数据库 + 文件系统）

    Args:
        doc_id: 计划书 ID

    Returns:
        tuple[bool, str]: (是否存在, 冲突来源描述)
    """
    # 检查数据库
    if plan_doc_repository.get_plan_doc_by_id(doc_id):
        return True, "数据库中已存在同名计划书"

    # 检查文件系统
    file_path = _get_plan_doc_path(doc_id)
    if file_path.exists():
        return True, "文件系统中已存在同名文件"

    return False, ""


def create_plan_doc(request: CreatePlanDocRequest) -> Optional[PlanDocItem]:
    """
    创建计划书（数据库 + 文件）

    Args:
        request: 创建计划书请求

    Returns:
        Optional[PlanDocItem]: 新创建的计划书，失败返回 None

    Raises:
        ValueError: 当 ID 已存在时抛出
    """
    # 前置检查：ID 是否已存在
    exists, conflict_source = _check_plan_doc_id_exists(request.id)
    if exists:
        logger.warning(f"创建计划书失败: {conflict_source}, ID: {request.id}")
        raise ValueError(f"{conflict_source}: {request.id}")

    data = {
        'id': request.id,
        'goal_id': request.goal_id,
    }

    new_id = plan_doc_repository.create_plan_doc(data)
    if new_id is None:
        return None

    # 创建 md 文件
    _write_content_to_file(new_id, request.content)

    return get_plan_doc_detail(new_id)


def update_plan_doc(doc_id: str, request: UpdatePlanDocRequest) -> Optional[PlanDocItem]:
    """
    更新计划书（meta + 文件内容）

    Args:
        doc_id: 计划书 ID
        request: 更新计划书请求

    Returns:
        Optional[PlanDocItem]: 更新后的计划书，失败返回 None

    Raises:
        ValueError: 当重命名时新 ID 已存在
    """
    # 先检查文档是否存在
    existing = plan_doc_repository.get_plan_doc_by_id(doc_id)
    if not existing:
        logger.warning(f"计划书 {doc_id} 不存在")
        return None

    explicitly_set_fields = request.model_fields_set

    # 处理重命名逻辑 (当 new_id 存在时)
    if 'new_id' in explicitly_set_fields and request.new_id and request.new_id != doc_id:
        new_id = request.new_id
        logger.info(f"检测到重命名操作: {doc_id} -> {new_id}")

        # 1. 检查新 ID 是否已存在（数据库 + 文件系统）
        exists, conflict_source = _check_plan_doc_id_exists(new_id)
        if exists:
            logger.warning(f"重命名失败: {conflict_source}, ID: {new_id}")
            raise ValueError(f"{conflict_source}: {new_id}")

        # 2. 文件层操作：另存为新文件 (保留旧文件做备份)
        content_to_write = ""
        if 'content' in explicitly_set_fields:
            content_to_write = request.content
        else:
            content_to_write = _read_content_from_file(doc_id)

        _write_content_to_file(new_id, content_to_write)

        # 3. 数据库层操作：事务更新 ID 和级联引用
        success = plan_doc_repository.rename_plan_doc(doc_id, new_id)

        if not success:
            logger.error(f"数据库重命名失败，回滚文件操作 (删除 {new_id}.md)")
            _delete_content_file(new_id)
            return None
            
        # 4. 如果还有其他字段需要更新 (status)，则再更新一次新记录
        if 'status' in explicitly_set_fields:
             plan_doc_repository.update_plan_doc(new_id, {'status': request.status})
             
        return get_plan_doc_detail(new_id)

    # 常规更新逻辑 (非重命名)
    update_data = {}

    if 'status' in explicitly_set_fields:
        update_data['status'] = request.status

    # 更新数据库 meta
    if update_data:
        plan_doc_repository.update_plan_doc(doc_id, update_data)

    # 更新文件内容
    if 'content' in explicitly_set_fields:
        _write_content_to_file(doc_id, request.content)

    return get_plan_doc_detail(doc_id)


def delete_plan_doc(doc_id: str) -> bool:
    """
    删除计划书（数据库 + 文件）

    Args:
        doc_id: 计划书 ID

    Returns:
        bool: 是否成功
    """
    # 先删除文件
    _delete_content_file(doc_id)
    # 再删除数据库记录
    return plan_doc_repository.delete_plan_doc(doc_id)
