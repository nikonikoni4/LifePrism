"""
习惯系统 API 路由

提供习惯 CRUD、打卡、统计、链式习惯等 RESTful 接口。
router 不带前缀，由 main.py 注册时指定 /api/v2/habit。
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from lifeprism.server.errors.api_error_mapping import to_http_exception
from lifeprism.server.errors.error_codes import (
    BACKFILL_DATE_OUT_OF_WINDOW,
    CANNOT_CANCEL_PAST_CHECKIN,
    CHAIN_NODE_VALIDATION_FAILED,
    CHAIN_NOT_FOUND,
    CHAIN_VALIDATION_FAILED,
    CHALLENGE_NOT_FOUND,
    CHECKIN_ALREADY_EXISTS,
    CHECKIN_NOT_FOUND,
    HABIT_NOT_ACTIVE,
    HABIT_NOT_FOUND,
    INVALID_STATUS_TRANSITION,
    NODE_NOT_FOUND,
    REORDER_VALIDATION_FAILED,
)
from lifeprism.server.schemas.habit_schemas import (
    BackfillAvailabilityRequest,
    BackfillCheckInRequest,
    ChallengeHistoryResponse,
    ChallengeObject,
    CreateChainRequest,
    CreateHabitRequest,
    CreateNodeRequest,
    ReorderNodesRequest,
    SettlementActionRequest,
    UpdateChainRequest,
    UpdateHabitRequest,
    UpdateNodeRequest,
)
from lifeprism.server.services import habit_stats_service
from lifeprism.server.services.habit_chain_service import habit_chain_service
from lifeprism.server.services.habit_service import habit_service
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ConflictError, LWBaseError, NotFoundError, ValidationError

logger = get_logger(__name__)

router = APIRouter(tags=["Habit"])


def _raise_app_error(
    error: LWBaseError,
    default_not_found: str = None,
    default_conflict: str = None,
    default_validation: str = None,
):
    default_code = None
    if isinstance(error, NotFoundError):
        default_code = default_not_found
    elif isinstance(error, ConflictError):
        default_code = default_conflict
    elif isinstance(error, ValidationError):
        default_code = default_validation
    raise to_http_exception(error, default_code=default_code)


# ============================================================================
# 习惯 CRUD
# ============================================================================

@router.get("/habits")
async def list_habits(status: Optional[str] = Query(default=None)):
    """获取习惯列表，可按 status 筛选"""
    return habit_service.get_habits(status)


@router.post("/habits", status_code=201)
async def create_habit(req: CreateHabitRequest):
    """创建习惯"""
    return habit_service.create_habit(req)


@router.get("/habits/{habitId}")
async def get_habit(habitId: str):
    """获取单个习惯详情"""
    try:
        return habit_service.get_habit_detail(habitId)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=HABIT_NOT_FOUND)


@router.patch("/habits/{habitId}")
async def update_habit(habitId: str, req: UpdateHabitRequest):
    """更新习惯（PATCH 语义）"""
    try:
        return habit_service.update_habit(habitId, req)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=HABIT_NOT_FOUND)


@router.delete("/habits/{habitId}", status_code=204)
async def delete_habit(habitId: str):
    """删除习惯"""
    try:
        habit_service.delete_habit(habitId)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=HABIT_NOT_FOUND)


@router.post("/habits/{habitId}/pause")
async def pause_habit(habitId: str, req: Optional[SettlementActionRequest] = None):
    """暂停习惯"""
    try:
        return habit_service.pause_habit(habitId, req)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=HABIT_NOT_FOUND,
            default_validation=INVALID_STATUS_TRANSITION,
        )


@router.post("/habits/{habitId}/resume")
async def resume_habit(habitId: str, req: Optional[SettlementActionRequest] = None):
    """恢复习惯"""
    try:
        return habit_service.resume_habit(habitId, req)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=HABIT_NOT_FOUND,
            default_validation=INVALID_STATUS_TRANSITION,
        )


# ============================================================================
# 打卡操作
# ============================================================================

@router.post("/habits/{habitId}/checkins")
async def checkin_today(habitId: str):
    """今日打卡"""
    try:
        return habit_service.checkin_today(habitId)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=HABIT_NOT_FOUND,
            default_conflict=CHECKIN_ALREADY_EXISTS,
            default_validation=HABIT_NOT_ACTIVE,
        )


@router.delete("/habits/{habitId}/checkins/{date}", status_code=200)
async def cancel_checkin(habitId: str, date: str):
    """取消打卡（仅限今日）"""
    try:
        return habit_service.cancel_checkin(habitId, date)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=CHECKIN_NOT_FOUND,
            default_validation=CANNOT_CANCEL_PAST_CHECKIN,
        )


@router.post("/habits/{habitId}/checkins/backfill")
async def backfill_checkin(habitId: str, req: BackfillCheckInRequest):
    """补签（过去 7 天内）"""
    try:
        return habit_service.backfill_checkin(habitId, req)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=CHALLENGE_NOT_FOUND,
            default_conflict=CHECKIN_ALREADY_EXISTS,
            default_validation=BACKFILL_DATE_OUT_OF_WINDOW,
        )


@router.post("/checkins/backfill/availability")
async def get_backfill_availability(req: BackfillAvailabilityRequest):
    """获取补录界面的近 7 天日期可用性"""
    try:
        return habit_service.get_backfill_availability(req)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=CHALLENGE_NOT_FOUND)


# ============================================================================
# 挑战历史 & 结算
# ============================================================================

@router.get("/habits/{habitId}/challenges", response_model=ChallengeHistoryResponse)
async def get_challenge_history(habitId: str, status: Optional[str] = Query(default=None)):
    """获取习惯的挑战历史"""
    try:
        raw_challenges = habit_service.get_challenge_history(habitId, status)
        # 历史记录的 remaining_rest_days 总是 0（见 _calculate_remaining_rest_days 逻辑）
        for c in raw_challenges:
            c["remaining_rest_days"] = 0
        challenges = [ChallengeObject(**c) for c in raw_challenges]
        return ChallengeHistoryResponse(challenges=challenges)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=HABIT_NOT_FOUND)


@router.post("/check-settlements")
async def check_settlements():
    """批量检查待处理结算项（成功落库，失败仅检测不落库）。"""
    return habit_service.check_settlements()


# ============================================================================
# 统计
# ============================================================================

@router.get("/stats/today")
async def get_today_stats():
    """今日概览统计"""
    result = habit_stats_service.get_today_overview(date.today())
    return {"overview": result}


@router.get("/stats/weekly")
async def get_weekly_stats(weeks: int = Query(default=12, gt=0)):
    """近 N 周完成率统计"""
    data = habit_stats_service.get_weekly_stats(date.today(), weeks)
    return {"weeks": data}


@router.get("/stats/heatmap")
async def get_heatmap(days: int = Query(default=365, ge=7, le=730)):
    """热力图数据"""
    data = habit_stats_service.get_heatmap(date.today(), days)
    return {"days": data}


# ============================================================================
# 链式习惯
# ============================================================================

@router.get("/chains")
async def list_chains(showInTimeline: Optional[bool] = Query(default=None)):
    """获取链列表"""
    return habit_chain_service.get_chains(showInTimeline)


@router.post("/chains", status_code=201)
async def create_chain(req: CreateChainRequest):
    """创建链"""
    return habit_chain_service.create_chain(req)


@router.get("/chains/timeline")
async def get_timeline():
    """获取 Timeline 视图数据"""
    return habit_chain_service.get_timeline()


@router.get("/chains/{chainId}")
async def get_chain(chainId: int):
    """获取链详情"""
    try:
        return habit_chain_service.get_chain_detail(chainId)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=CHAIN_NOT_FOUND)


@router.patch("/chains/{chainId}")
async def update_chain(chainId: int, req: UpdateChainRequest):
    """更新链"""
    try:
        return habit_chain_service.update_chain(chainId, req)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=CHAIN_NOT_FOUND,
            default_validation=CHAIN_VALIDATION_FAILED,
        )


@router.delete("/chains/{chainId}", status_code=204)
async def delete_chain(chainId: int):
    """删除链"""
    try:
        habit_chain_service.delete_chain(chainId)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=CHAIN_NOT_FOUND)


@router.post("/chains/{chainId}/nodes", status_code=201)
async def create_node(chainId: int, req: CreateNodeRequest):
    """在链中创建节点"""
    try:
        return habit_chain_service.create_node(chainId, req)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=CHAIN_NOT_FOUND,
            default_validation=CHAIN_NODE_VALIDATION_FAILED,
        )


@router.patch("/chains/{chainId}/nodes/reorder", status_code=200)
async def reorder_nodes(chainId: int, req: ReorderNodesRequest):
    """重新排序链节点"""
    try:
        habit_chain_service.reorder_nodes(chainId, req)
        return {"ok": True}
    except LWBaseError as e:
        _raise_app_error(e, default_validation=REORDER_VALIDATION_FAILED)


@router.patch("/chains/{chainId}/nodes/{nodeId:int}")
async def update_node(chainId: int, nodeId: int, req: UpdateNodeRequest):
    """更新链节点"""
    try:
        return habit_chain_service.update_node(nodeId, req)
    except LWBaseError as e:
        _raise_app_error(
            e,
            default_not_found=NODE_NOT_FOUND,
            default_validation=CHAIN_NODE_VALIDATION_FAILED,
        )


@router.delete("/chains/{chainId}/nodes/{nodeId:int}", status_code=204)
async def delete_node(chainId: int, nodeId: int):
    """删除链节点"""
    try:
        habit_chain_service.delete_node(nodeId)
    except LWBaseError as e:
        _raise_app_error(e, default_not_found=NODE_NOT_FOUND)
