"""
数据同步API路由
"""

from fastapi import APIRouter
from lifewatch.server.schemas.sync import SyncRequest, SyncResponse, SyncTimeRangeRequest
from lifewatch.server.services.sync_service import SyncService
from lifewatch.utils import LazySingleton

router = APIRouter(prefix="/sync", tags=["Data Synchronization"])
sync_service = LazySingleton(SyncService)


@router.post("/activitywatch", response_model=SyncResponse, summary="增量同步ActivityWatch数据")
async def sync_from_activitywatch(
    sync_request: SyncRequest = SyncRequest()
):
    """
    增量同步 ActivityWatch 数据（从数据库最新时间同步到现在）
    
    **流程**:
    1. 从数据库获取最新的 end_time
    2. 从 ActivityWatch 获取该时间到现在的数据
    3. 数据清洗和去重
    4. 识别未分类的应用
    5. （可选）自动抓取应用描述并调用 LLM 分类
    6. 保存到数据库
    
    **请求参数**:
    - auto_classify: 是否自动分类新应用（默认开启）
    
    **响应**:
    - status: 同步状态（success/failed/partial）
    - synced_events: 同步的事件数量
    - new_apps_classified: 新分类的应用数量
    - duration: 同步耗时（秒）
    
    **注意**: 
    - 自动分类会调用 LLM API，可能需要较长时间
    - 如需同步指定时间范围，请使用 /activitywatch/timerange 接口
    """
    print("sync_request (incremental)", sync_request)
    result = sync_service.sync_from_activitywatch(
        auto_classify=sync_request.auto_classify
    )
    return result


@router.post("/activitywatch/timerange", response_model=SyncResponse, summary="按时间范围同步ActivityWatch数据")
async def sync_from_activitywatch_by_time_range(
    sync_request: SyncTimeRangeRequest
):
    """
    按指定时间范围从 ActivityWatch 同步数据
    
    **流程**:
    1. 从 ActivityWatch 获取指定时间范围的数据
    2. 数据清洗和去重
    3. 识别未分类的应用
    4. （可选）自动抓取应用描述并调用 LLM 分类
    5. 保存到数据库
    
    **请求参数**:
    - start_time: 开始时间，格式: YYYY-MM-DD HH:MM:SS
    - end_time: 结束时间，格式: YYYY-MM-DD HH:MM:SS
    - auto_classify: 是否自动分类新应用
    
    **响应**:
    - status: 同步状态（success/failed/partial）
    - synced_events: 同步的事件数量
    - new_apps_classified: 新分类的应用数量
    - duration: 同步耗时（秒）
    
    **注意**: 
    - 自动分类会调用 LLM API，可能需要较长时间
    - 时间范围不宜过大，建议不超过7天
    """
    print("sync_time_range_request", sync_request)
    result = sync_service.sync_by_time_range(
        start_time=sync_request.start_time,
        end_time=sync_request.end_time,
        auto_classify=sync_request.auto_classify
    )
    return result
