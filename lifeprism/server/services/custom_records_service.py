"""
自定义记录模块 Service 层

架构：纯函数模块（API 层薄包装，无业务逻辑）
核心逻辑在 Repository 层（slug 冲突、field_key 校验、valid_fields 构造等）
"""

from lifeprism.repository import custom_record_repository
from lifeprism.repository.exceptions import EntityNotFoundError
from lifeprism.server.schemas.custom_records_schemas import (
    CreateCustomRecordEntryRequest,
    CreateCustomRecordTypeRequest,
    CustomRecordEntryItem,
    CustomRecordEntryListResponse,
    CustomRecordTypeItem,
    CustomRecordTypeListResponse,
    FieldDefinition,
    UpdateFieldRoleRequest,
    UpdateTypeConfigRequest,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# ==================== 工具函数 ====================


def _convert_to_field_definition(item: dict) -> FieldDefinition:
    """将数据库字段记录转换为 FieldDefinition"""
    return FieldDefinition(
        id=item.get("id", ""),
        field_name=item["field_name"],
        field_key=item["field_key"],
        field_type=item.get("field_type", "text"),
        display_role=item.get("display_role", "auto"),
    )


def _convert_to_type_item(item: dict) -> CustomRecordTypeItem:
    """将数据库类型记录（含 fields）转换为 CustomRecordTypeItem"""
    return CustomRecordTypeItem(
        id=item["id"],
        name=item["name"],
        slug=item["slug"],
        description=item.get("description", "") or "",
        fields=[_convert_to_field_definition(f) for f in item.get("fields", [])],
        card_template=item.get("card_template", "clean"),
        icon=item.get("icon", "fileText"),
        accent_color=item.get("accent_color", "blue"),
        created_at=item.get("created_at", ""),
        updated_at=item.get("updated_at", ""),
    )


def _convert_to_entry_item(item: dict) -> CustomRecordEntryItem:
    """将数据库记录转换为 CustomRecordEntryItem"""
    return CustomRecordEntryItem(**item)


# ==================== 类型管理 ====================


def get_types() -> CustomRecordTypeListResponse:
    """获取所有自定义记录类型（含字段定义）"""
    types = custom_record_repository.list_types()
    items = [_convert_to_type_item(t) for t in types]
    return CustomRecordTypeListResponse(items=items)


def get_type(type_id: str) -> CustomRecordTypeItem:
    """获取单个类型详情（含字段定义）

    Raises:
        EntityNotFoundError: 类型不存在
    """
    type_dict = custom_record_repository.get_type_by_id(type_id)
    if type_dict is None:
        raise EntityNotFoundError(entity_type="CustomRecordType", entity_id=type_id)
    return _convert_to_type_item(type_dict)


def create_type(request: CreateCustomRecordTypeRequest) -> CustomRecordTypeItem:
    """创建自定义记录类型

    Raises:
        ValidationError: slug 格式错误 / field_key 格式错误 / fields 为空
        DuplicateEntityError: slug 冲突
    """
    type_id = custom_record_repository.create_type(
        name=request.name,
        slug=request.slug,
        fields=[f.model_dump() for f in request.fields],
        description=request.description,
    )
    type_dict = custom_record_repository.get_type_by_id(type_id)
    logger.info("创建自定义记录类型成功: type_id=%s, slug=%s", type_id, request.slug)
    return _convert_to_type_item(type_dict)


def delete_type(type_id: str) -> bool:
    """硬删类型（DROP 表 + 删 meta）

    Raises:
        EntityNotFoundError: 类型不存在
    """
    return custom_record_repository.delete_type(type_id)


# ==================== 记录管理 ====================


def get_entries(
    type_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> CustomRecordEntryListResponse:
    """查询记录（支持时间范围筛选 + 分页）

    Raises:
        EntityNotFoundError: 类型不存在
    """
    time_range = None
    if start_time or end_time:
        time_range = (start_time, end_time)

    entries, total_count = custom_record_repository.query_entries(
        type_id=type_id,
        date_range=time_range,
        page=page,
        page_size=page_size,
    )
    items = [_convert_to_entry_item(e) for e in entries]
    return CustomRecordEntryListResponse(items=items, total=total_count)


def create_entry(type_id: str, request: CreateCustomRecordEntryRequest) -> CustomRecordEntryItem:
    """录入记录

    Raises:
        EntityNotFoundError: 类型不存在
        ValidationError: field_key 错误（details 含 valid_fields）
    """
    entry_id = custom_record_repository.create_entry(type_id=type_id, data=request.data)
    entry_dict = custom_record_repository.get_entry(type_id=type_id, entry_id=entry_id)
    logger.info("录入自定义记录成功: type_id=%s, entry_id=%s", type_id, entry_id)
    return _convert_to_entry_item(entry_dict)


def delete_entry(type_id: str, entry_id: str) -> bool:
    """删除单条记录

    Raises:
        EntityNotFoundError: 类型不存在
    """
    return custom_record_repository.delete_entry(type_id=type_id, entry_id=entry_id)


# ==================== 配置更新 ====================


def update_type_config(type_id: str, request: UpdateTypeConfigRequest) -> CustomRecordTypeItem:
    """更新类型展示配置

    Raises:
        EntityNotFoundError: 类型不存在
    """
    custom_record_repository.update_type_config(
        type_id=type_id,
        card_template=request.card_template,
        icon=request.icon,
        accent_color=request.accent_color,
    )
    type_dict = custom_record_repository.get_type_by_id(type_id)
    logger.info("更新类型配置成功: type_id=%s", type_id)
    return _convert_to_type_item(type_dict)


def update_field_role(
    type_id: str, field_id: str, request: UpdateFieldRoleRequest
) -> CustomRecordTypeItem:
    """更新字段展示角色

    Raises:
        EntityNotFoundError: 类型不存在 / 字段不存在
    """
    custom_record_repository.update_field_role(
        type_id=type_id,
        field_id=field_id,
        display_role=request.display_role,
    )
    type_dict = custom_record_repository.get_type_by_id(type_id)
    logger.info("更新字段角色成功: type_id=%s, field_id=%s", type_id, field_id)
    return _convert_to_type_item(type_dict)
