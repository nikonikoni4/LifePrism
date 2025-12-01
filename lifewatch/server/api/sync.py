"""
数据同步API路由
"""

from fastapi import APIRouter
from lifewatch.server.schemas.sync import SyncRequest, SyncResponse
from lifewatch.server.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["Data Synchronization"])
sync_service = SyncService()


@router.post("/activitywatch", response_model=SyncResponse, summary="从ActivityWatch同步数据")
async def sync_from_activitywatch(
    sync_request: SyncRequest = SyncRequest()
):
    """
    从 ActivityWatch 同步数据并可选择性自动分类
    
    **流程**:
    1. 从 ActivityWatch 获取最近N小时的数据
    2. 数据清洗和去重
    3. 识别未分类的应用
    4. （可选）自动抓取应用描述并调用 LLM 分类
    5. 保存到数据库
    
    **请求参数**:
    - hours: 同步最近N小时的数据（1-720小时）
    - auto_classify: 是否自动分类新应用
    
    **响应**:
    - status: 同步状态（success/failed/partial）
    - synced_events: 同步的事件数量
    - new_apps_classified: 新分类的应用数量
    - duration: 同步耗时（秒）
    
    **当前返回 Mock 数据**
    
    **注意**: 
    - 自动分类会调用 LLM API，可能需要较长时间
    - 建议首次同步使用较小的 hours 值进行测试
    """
    result = sync_service.sync_from_activitywatch(
        hours=sync_request.hours,
        auto_classify=sync_request.auto_classify
    )
    return result
