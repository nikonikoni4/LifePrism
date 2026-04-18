"""
Diary API - 日记模块路由

路由顺序关键：/list 和 /templates/* 必须在 /{date} 之前，
否则 FastAPI 会把 "list"/"templates" 当作 date 参数。
"""
from fastapi import APIRouter, Query, HTTPException, Path

from lifeprism.server.schemas.diary_schemas import (
    DiaryItem,
    DiaryListResponse,
    DiaryAISummaryResponse,
    UpdateDiaryMetaRequest,
    SaveDiaryContentRequest,
    TemplateItem,
    TemplateListResponse,
    CreateTemplateRequest,
    UpdateTemplateRequest,
    GenerateDiaryAISummaryRangeRequest,
    GenerateDiaryAISummaryRangeResponse,
)
from lifeprism.server.services import diary_service

router = APIRouter(prefix="/diary", tags=["Diary"])


# ==================== 日记列表（必须在 /{date} 之前） ====================

@router.get("/list", response_model=DiaryListResponse, summary="获取日记列表")
async def get_diary_list(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """获取日期范围内的日记列表（仅 meta，用于日历标记）"""
    return diary_service.get_diary_list(start_date, end_date)


# ==================== 模板管理（必须在 /{date} 之前） ====================

@router.get("/templates", response_model=TemplateListResponse, summary="获取模板列表")
async def get_templates():
    """扫描模板目录，返回模板名称列表"""
    return diary_service.get_templates()


@router.get("/templates/{name}", response_model=TemplateItem, summary="获取模板内容")
async def get_template(
    name: str = Path(..., description="模板名称"),
):
    result = diary_service.get_template(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"模板不存在: {name}")
    return result


@router.post("/templates", response_model=TemplateItem, status_code=201, summary="创建模板")
async def create_template(request: CreateTemplateRequest):
    try:
        return diary_service.create_template(request)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/templates/{name}", response_model=TemplateItem, summary="更新模板")
async def update_template(
    request: UpdateTemplateRequest,
    name: str = Path(..., description="模板名称"),
):
    result = diary_service.update_template(name, request)
    if not result:
        raise HTTPException(status_code=404, detail=f"模板不存在: {name}")
    return result


@router.delete("/templates/{name}", summary="删除模板")
async def delete_template(
    name: str = Path(..., description="模板名称"),
):
    success = diary_service.delete_template(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"模板不存在: {name}")
    return {"message": f"模板 {name} 已删除"}


# ==================== 日记 CRUD ====================

@router.post("/ai_summary/range", response_model=GenerateDiaryAISummaryRangeResponse, summary="按日期范围更新日记 AI 总结")
async def generate_diary_ai_summary_range(request: GenerateDiaryAISummaryRangeRequest):
    """按日期范围批量更新日记 AI 总结，支持三种现有总结模式"""
    return await diary_service.generate_diary_ai_summary_range(request)


@router.get("/{date}", response_model=DiaryItem, summary="获取日记")
async def get_diary(
    date: str = Path(..., description="日期 YYYY-MM-DD"),
):
    """获取指定日期日记（meta + content），不存在则自动创建"""
    result = diary_service.get_diary(date)
    if not result:
        raise HTTPException(status_code=500, detail="获取日记失败")
    return result


@router.patch("/{date}", response_model=DiaryItem, summary="更新日记 meta")
async def update_diary_meta(
    request: UpdateDiaryMetaRequest,
    date: str = Path(..., description="日期 YYYY-MM-DD"),
):
    """更新日记 meta（心情、平凡程度、自定义 tag）"""
    result = diary_service.update_diary_meta(date, request)
    if not result:
        raise HTTPException(status_code=404, detail=f"日记不存在: {date}")
    return result


@router.put("/{date}/content", response_model=DiaryItem, summary="保存日记内容")
async def save_diary_content(
    request: SaveDiaryContentRequest,
    date: str = Path(..., description="日期 YYYY-MM-DD"),
):
    """保存日记 md 内容，同时更新 word_count"""
    result = diary_service.save_diary_content(date, request)
    if not result:
        raise HTTPException(status_code=404, detail=f"日记不存在: {date}")
    return result


@router.post("/{date}/ai_summary", response_model=DiaryAISummaryResponse, summary="生成日记 AI 总结")
async def generate_diary_ai_summary(
    date: str = Path(..., description="日期 YYYY-MM-DD"),
):
    """手动生成指定日期日记 AI 总结"""
    try:
        return await diary_service.generate_diary_ai_summary(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
