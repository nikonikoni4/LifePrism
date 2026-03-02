"""
习惯系统 API 路由

提供习惯 CRUD、打卡、统计、链式习惯等 RESTful 接口。
router 不带前缀，由 main.py 注册时指定 /api/v2/habit。
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from lifeprism.server.schemas.habit_schemas import (
    CreateHabitRequest, UpdateHabitRequest,
    BackfillCheckInRequest,
    SettlementActionRequest,
    CreateChainRequest, UpdateChainRequest,
    CreateNodeRequest, UpdateNodeRequest,
    ReorderNodesRequest,
)
from lifeprism.server.services.habit_service import habit_service
from lifeprism.server.services import habit_stats_service
from lifeprism.server.services.habit_chain_service import habit_chain_service
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import NotFoundError, ConflictError, ValidationError

logger = get_logger(__name__)

router = APIRouter(tags=["Habit"])


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


@router.get("/habits/{habit_id}")
async def get_habit(habit_id: str):
    """获取单个习惯详情"""
    try:
        return habit_service.get_habit_detail(habit_id)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )


@router.patch("/habits/{habit_id}")
async def update_habit(habit_id: str, req: UpdateHabitRequest):
    """更新习惯（PATCH 语义）"""
    try:
        return habit_service.update_habit(habit_id, req)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )


@router.delete("/habits/{habit_id}", status_code=204)
async def delete_habit(habit_id: str):
    """删除习惯"""
    try:
        habit_service.delete_habit(habit_id)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )


@router.post("/habits/{habit_id}/pause")
async def pause_habit(
    habit_id: str, req: Optional[SettlementActionRequest] = None,
):
    """暂停习惯"""
    try:
        return habit_service.pause_habit(habit_id, req)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_STATUS_TRANSITION", "message": str(e)},
        )


@router.post("/habits/{habit_id}/resume")
async def resume_habit(
    habit_id: str, req: Optional[SettlementActionRequest] = None,
):
    """恢复习惯"""
    try:
        return habit_service.resume_habit(habit_id, req)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_STATUS_TRANSITION", "message": str(e)},
        )


# ============================================================================
# 打卡操作
# ============================================================================

@router.post("/habits/{habit_id}/checkins")
async def checkin_today(habit_id: str):
    """今日打卡"""
    try:
        return habit_service.checkin_today(habit_id)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )
    except ConflictError:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "CHECKIN_ALREADY_EXISTS", "message": "Already checked in today"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "HABIT_NOT_ACTIVE", "message": str(e)},
        )


@router.delete("/habits/{habit_id}/checkins/{date_str}", status_code=200)
async def cancel_checkin(habit_id: str, date_str: str):
    """取消打卡（仅限今日）"""
    try:
        return habit_service.cancel_checkin(habit_id, date_str)
    except NotFoundError as e:
        msg = str(e)
        if "习惯不存在" in msg:
            raise HTTPException(
                status_code=404,
                detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
            )
        raise HTTPException(
            status_code=404,
            detail={"error_code": "CHECKIN_NOT_FOUND", "message": "Checkin not found"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "CANNOT_CANCEL_PAST_CHECKIN", "message": str(e)},
        )


@router.post("/habits/{habit_id}/checkins/backfill")
async def backfill_checkin(habit_id: str, req: BackfillCheckInRequest):
    """补签（过去 7 天内）"""
    try:
        return habit_service.backfill_checkin(habit_id, req)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )
    except ConflictError:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "CHECKIN_ALREADY_EXISTS", "message": "Already checked in on that date"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "HABIT_NOT_ACTIVE", "message": str(e)},
        )


# ============================================================================
# 挑战历史 & 结算
# ============================================================================

@router.get("/habits/{habit_id}/challenges")
async def get_challenge_history(
    habit_id: str,
    status: Optional[str] = Query(default=None),
):
    """获取习惯的挑战历史"""
    try:
        challenges = habit_service.get_challenge_history(habit_id, status)
        return {"challenges": challenges}
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HABIT_NOT_FOUND", "message": "Habit not found"},
        )


@router.post("/check-settlements")
async def check_settlements():
    """批量检查并结算到期挑战"""
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
async def get_weekly_stats():
    """本周完成率统计"""
    rate = habit_stats_service.get_weekly_stats(date.today())
    return {"completion_rate": rate}


@router.get("/stats/heatmap")
async def get_heatmap(days: int = Query(default=365, ge=7, le=730)):
    """热力图数据"""
    data = habit_stats_service.get_heatmap(date.today(), days)
    return {"heatmap": data}


# ============================================================================
# 链式习惯
# ============================================================================

@router.get("/chains")
async def list_chains(show_in_timeline: Optional[bool] = Query(default=None)):
    """获取链列表"""
    return habit_chain_service.get_chains(show_in_timeline)


@router.post("/chains", status_code=201)
async def create_chain(req: CreateChainRequest):
    """创建链"""
    return habit_chain_service.create_chain(req)


@router.get("/chains/timeline")
async def get_timeline():
    """获取 Timeline 视图数据"""
    return habit_chain_service.get_timeline()


@router.get("/chains/{chain_id}")
async def get_chain(chain_id: int):
    """获取链详情"""
    try:
        return habit_chain_service.get_chain_detail(chain_id)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "CHAIN_NOT_FOUND", "message": "Chain not found"},
        )


@router.patch("/chains/{chain_id}")
async def update_chain(chain_id: int, req: UpdateChainRequest):
    """更新链"""
    try:
        return habit_chain_service.update_chain(chain_id, req)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "CHAIN_NOT_FOUND", "message": "Chain not found"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "CHAIN_VALIDATION_FAILED", "message": str(e)},
        )


@router.delete("/chains/{chain_id}", status_code=204)
async def delete_chain(chain_id: int):
    """删除链"""
    try:
        habit_chain_service.delete_chain(chain_id)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "CHAIN_NOT_FOUND", "message": "Chain not found"},
        )


@router.post("/chains/{chain_id}/nodes", status_code=201)
async def create_node(chain_id: int, req: CreateNodeRequest):
    """在链中创建节点"""
    try:
        return habit_chain_service.create_node(chain_id, req)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "CHAIN_NOT_FOUND", "message": "Chain not found"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "CHAIN_NODE_VALIDATION_FAILED", "message": str(e)},
        )


@router.patch("/chains/{chain_id}/nodes/{node_id}")
async def update_node(chain_id: int, node_id: int, req: UpdateNodeRequest):
    """更新链节点"""
    try:
        return habit_chain_service.update_node(node_id, req)
    except NotFoundError as e:
        msg = str(e)
        if "Chain" in msg:
            raise HTTPException(
                status_code=404,
                detail={"error_code": "CHAIN_NOT_FOUND", "message": "Chain not found"},
            )
        raise HTTPException(
            status_code=404,
            detail={"error_code": "NODE_NOT_FOUND", "message": "Node not found"},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "CHAIN_NODE_VALIDATION_FAILED", "message": str(e)},
        )


@router.delete("/chains/{chain_id}/nodes/{node_id}", status_code=204)
async def delete_node(chain_id: int, node_id: int):
    """删除链节点"""
    try:
        habit_chain_service.delete_node(node_id)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "NODE_NOT_FOUND", "message": "Node not found"},
        )


@router.post("/chains/{chain_id}/nodes/reorder", status_code=200)
async def reorder_nodes(chain_id: int, req: ReorderNodesRequest):
    """重新排序链节点"""
    try:
        habit_chain_service.reorder_nodes(chain_id, req)
        return {"ok": True}
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "REORDER_VALIDATION_FAILED", "message": str(e)},
        )
