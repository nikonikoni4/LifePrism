"""
Custom Records API - 自定义记录模块路由

路由分组：类型管理 → 记录 CRUD
固定路径在参数化路径之前，避免路径冲突。
错误响应由全局 LWBaseError 异常处理器统一映射（API 层不写 try/except）。
"""

from fastapi import APIRouter, Path, Query

from lifeprism.server.schemas.custom_records_schemas import (
    CreateCustomRecordEntryRequest,
    CreateCustomRecordTypeRequest,
    CustomRecordEntryItem,
    CustomRecordEntryListResponse,
    CustomRecordTypeItem,
    CustomRecordTypeListResponse,
    UpdateFieldRoleRequest,
    UpdateTypeConfigRequest,
)
from lifeprism.server.services import custom_records_service

router = APIRouter(prefix="/custom-records", tags=["Custom Records"])


# ==================== 类型管理 ====================


@router.get("/types", response_model=CustomRecordTypeListResponse, summary="获取自定义记录类型列表")
async def get_custom_record_types():
    """获取所有自定义记录类型（含字段定义）"""
    return custom_records_service.get_types()


@router.post(
    "/types", response_model=CustomRecordTypeItem, status_code=201, summary="创建自定义记录类型"
)
async def create_custom_record_type(request: CreateCustomRecordTypeRequest):
    """创建自定义记录类型

    - slug 格式：^[a-z][a-z0-9_]*$
    - fields 至少 1 个
    - slug 全局唯一，冲突返回 409
    - 格式错误返回 422
    """
    return custom_records_service.create_type(request)


@router.get("/types/{type_id}", response_model=CustomRecordTypeItem, summary="获取单个类型详情")
async def get_custom_record_type(
    type_id: str = Path(..., description="类型 ID"),
):
    """获取单个类型详情（含字段定义）。类型不存在返回 404"""
    return custom_records_service.get_type(type_id)


@router.delete("/types/{type_id}", summary="删除自定义记录类型")
async def delete_custom_record_type(
    type_id: str = Path(..., description="类型 ID"),
):
    """硬删类型（DROP 数据表 + 删除 meta 记录）。类型不存在返回 404"""
    custom_records_service.delete_type(type_id)
    return {"message": f"类型 {type_id} 已删除"}


@router.patch("/types/{type_id}", response_model=CustomRecordTypeItem, summary="更新类型展示配置")
async def update_custom_record_type_config(
    request: UpdateTypeConfigRequest,
    type_id: str = Path(..., description="类型 ID"),
):
    """更新类型展示配置（card_template/icon/accent_color）。类型不存在返回 404"""
    return custom_records_service.update_type_config(type_id=type_id, request=request)


@router.patch(
    "/types/{type_id}/fields/{field_id}",
    response_model=CustomRecordTypeItem,
    summary="更新字段展示角色",
)
async def update_custom_record_field_role(
    request: UpdateFieldRoleRequest,
    type_id: str = Path(..., description="类型 ID"),
    field_id: str = Path(..., description="字段 ID"),
):
    """更新字段展示角色（display_role）。字段不存在返回 404"""
    return custom_records_service.update_field_role(
        type_id=type_id, field_id=field_id, request=request
    )


# ==================== 记录管理 ====================


@router.get(
    "/{type_id}/entries",
    response_model=CustomRecordEntryListResponse,
    summary="查询自定义记录",
)
async def get_custom_record_entries(
    type_id: str = Path(..., description="类型 ID"),
    start_date: str | None = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=50, ge=1, le=500, description="每页条数"),
):
    """查询记录（按创建时间倒序，支持日期筛选 + 分页）。类型不存在返回 404"""
    return custom_records_service.get_entries(
        type_id=type_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{type_id}/entries",
    response_model=CustomRecordEntryItem,
    status_code=201,
    summary="录入自定义记录",
)
async def create_custom_record_entry(
    request: CreateCustomRecordEntryRequest,
    type_id: str = Path(..., description="类型 ID"),
):
    """录入记录

    - data 中的 key 必须匹配类型的 field_key
    - field_key 错误返回 422，details 含 valid_fields
    - 缺失字段存为 NULL，空字典允许
    - 类型不存在返回 404
    """
    return custom_records_service.create_entry(type_id=type_id, request=request)


@router.delete(
    "/{type_id}/entries/{entry_id}",
    summary="删除自定义记录",
)
async def delete_custom_record_entry(
    type_id: str = Path(..., description="类型 ID"),
    entry_id: str = Path(..., description="记录 ID"),
):
    """删除单条记录。类型不存在返回 404"""
    custom_records_service.delete_entry(type_id=type_id, entry_id=entry_id)
    return {"message": f"记录 {entry_id} 已删除"}
