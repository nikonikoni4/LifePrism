"""
自定义记录模块 Service 层

架构：纯函数模块（API 层薄包装，无业务逻辑）
核心逻辑在 Repository 层（slug 冲突、field_key 校验、valid_fields 构造等）
"""

from lifeprism.repository import custom_record_repository
from lifeprism.server.schemas.custom_records_schemas import (
    CreateCustomRecordEntryRequest,
    CreateCustomRecordTypeRequest,
    CustomRecordEntryItem,
    CustomRecordEntryListResponse,
    CustomRecordTypeItem,
    CustomRecordTypeListResponse,
    FieldDefinition,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# ==================== 工具函数 ====================


def _convert_to_field_definition(item: dict) -> FieldDefinition:
    """将数据库字段记录转换为 FieldDefinition"""
    return FieldDefinition(
        field_name=item["field_name"],
        field_key=item["field_key"],
        field_type=item.get("field_type", "text"),
    )


def _convert_to_type_item(item: dict, fields: list[dict]) -> CustomRecordTypeItem:
    """将数据库类型记录 + 字段列表转换为 CustomRecordTypeItem"""
    return CustomRecordTypeItem(
        id=item["id"],
        name=item["name"],
        slug=item["slug"],
        description=item.get("description", "") or "",
        fields=[_convert_to_field_definition(f) for f in fields],
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
    items = [_convert_to_type_item(t, t.get("fields", [])) for t in types]
    return CustomRecordTypeListResponse(items=items)


def get_type(type_id: str) -> CustomRecordTypeItem:
    """获取单个类型详情（含字段定义）

    Raises:
        EntityNotFoundError: 类型不存在
    """
    type_dict = custom_record_repository.get_type_by_id(type_id)
    fields = custom_record_repository.get_type_fields(type_id)
    return _convert_to_type_item(type_dict, fields)


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
    fields = custom_record_repository.get_type_fields(type_id)
    logger.info("创建自定义记录类型成功: type_id=%s, slug=%s", type_id, request.slug)
    return _convert_to_type_item(type_dict, fields)


def delete_type(type_id: str) -> bool:
    """硬删类型（DROP 表 + 删 meta）

    Raises:
        EntityNotFoundError: 类型不存在
    """
    return custom_record_repository.delete_type(type_id)


# ==================== 记录管理 ====================


def get_entries(
    type_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> CustomRecordEntryListResponse:
    """查询记录（支持日期筛选 + 分页）

    Raises:
        EntityNotFoundError: 类型不存在
    """
    date_range = None
    if start_date or end_date:
        date_range = (start_date, end_date)

    entries = custom_record_repository.query_entries(
        type_id=type_id,
        date_range=date_range,
        page=page,
        page_size=page_size,
    )
    items = [_convert_to_entry_item(e) for e in entries]
    return CustomRecordEntryListResponse(items=items, total=len(items))


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
