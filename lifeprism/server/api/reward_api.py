"""
Reward API - 奖励接口

提供 Reward 的 RESTful API
"""
from fastapi import APIRouter, HTTPException, Path

from lifeprism.server.schemas.goal_schemas import (
    RewardItem,
    RewardListResponse,
    CreateRewardRequest,
    UpdateRewardRequest,
    RewardStatsResponse,
    UpdateMilestoneStateRequest,
)
from lifeprism.server.services.reward_service import reward_service


router = APIRouter(prefix="/goal", tags=["Goal - Reward"])


# ============================================================================
# Reward 接口
# ============================================================================

@router.get("/rewards", response_model=RewardListResponse)
async def get_rewards():
    """
    获取所有奖励列表
    """
    return reward_service.get_rewards()


@router.get("/rewards/{reward_id}", response_model=RewardItem)
async def get_reward_detail(
    reward_id: int = Path(..., description="奖励 ID")
):
    """
    获取单个奖励详情
    """
    item = reward_service.get_reward_detail(reward_id)
    if not item:
        raise HTTPException(status_code=404, detail="奖励不存在")
    return item


@router.get("/rewards/{reward_id}/stats", response_model=RewardStatsResponse)
async def get_reward_stats(
    reward_id: int = Path(..., description="奖励 ID")
):
    """
    获取奖励统计数据（含历史累积数据）
    
    此接口会自动同步统计数据到当前日期：
    - 从 user_app_behavior_log 聚合时间花费
    - 从 todo_list 统计完成的待办数量
    
    返回数据用于 Momentum Tracker 图表展示
    """
    stats = reward_service.get_reward_stats(reward_id)
    if not stats:
        raise HTTPException(status_code=404, detail="奖励不存在")
    return stats


@router.post("/rewards", response_model=RewardItem)
async def create_reward(request: CreateRewardRequest):
    """
    创建新奖励
    
    请求体:
    - **goal_id**: 关联的目标 ID（必需）
    - **name**: 奖励名称（必需）
    - **target_hours**: 达成奖励所需的累计小时数（可选，默认 0）
    - **target_todos**: 达成奖励所需的累计完成待办数（可选，默认 0）
    """
    item = reward_service.create_reward(request)
    if not item:
        raise HTTPException(status_code=500, detail="创建奖励失败")
    return item


@router.patch("/rewards/{reward_id}", response_model=RewardItem)
async def update_reward(
    reward_id: int = Path(..., description="奖励 ID"),
    request: UpdateRewardRequest = ...
):
    """
    更新奖励（部分更新）
    
    请求体（所有字段可选）:
    - **goal_id**: 关联的目标 ID
    - **name**: 奖励名称
    - **target_hours**: 达成奖励所需的累计小时数
    - **target_todos**: 达成奖励所需的累计完成待办数
    """
    item = reward_service.update_reward(reward_id, request)
    if not item:
        raise HTTPException(status_code=404, detail="奖励不存在或更新失败")
    return item


@router.delete("/rewards/{reward_id}")
async def delete_reward(
    reward_id: int = Path(..., description="奖励 ID")
):
    """
    删除奖励
    """
    success = reward_service.delete_reward(reward_id)
    if not success:
        raise HTTPException(status_code=404, detail="奖励不存在或删除失败")
    return {"success": True, "message": "奖励已删除"}


@router.patch("/rewards/{reward_id}/milestones/{milestone_id}", response_model=RewardItem)
async def update_milestone_state(
    reward_id: int = Path(..., description="奖励 ID"),
    milestone_id: str = Path(..., description="里程碑 ID"),
    request: UpdateMilestoneStateRequest = ...
):
    """
    更新里程碑状态（点亮/取消）
    
    请求体:
    - **state**: 0 = 未达成, 1 = 已达成
    
    此接口会自动处理里程碑位置交换逻辑：
    当后面的里程碑被点亮但前面有未点亮的，会交换它们的位置
    """
    item = reward_service.update_milestone_state(reward_id, milestone_id, request.state)
    if not item:
        raise HTTPException(status_code=404, detail="奖励或里程碑不存在")
    return item
