"""
Goal 服务层 - Goal 目标业务逻辑

提供 Goal 的纯函数接口
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from lifewatch.server.schemas.goal_schemas import (
    GoalItem,
    GoalListResponse,
    CreateGoalRequest,
    UpdateGoalRequest,
    ReorderGoalRequest,
)
from lifewatch.server.providers.goal_provider import goal_provider
from lifewatch.server.services.category_service import category_service


# ============================================================================
# 辅助函数
# ============================================================================


def _get_category_name(category_id: Optional[str]) -> Optional[str]:
    """
    根据分类 ID 获取分类名称
    
    Args:
        category_id: 分类 ID
    
    Returns:
        分类名称，不存在返回 None
    """
    if not category_id:
        return None
    
    # 使用 category_service 的 category_name_map
    return category_service.category_name_map.get(str(category_id))


def _get_sub_category_name(sub_category_id: Optional[str]) -> Optional[str]:
    """
    根据子分类 ID 获取子分类名称
    
    Args:
        sub_category_id: 子分类 ID
    
    Returns:
        子分类名称，不存在返回 None
    """
    if not sub_category_id:
        return None
    
    # 使用 category_service 的 sub_category_name_map
    return category_service.sub_category_name_map.get(str(sub_category_id))


def _convert_db_item_to_goal_item(item: Dict[str, Any]) -> GoalItem:
    """
    将数据库记录转换为 GoalItem，同时将分类 ID 转换为名称
    
    Args:
        item: 数据库记录字典
    
    Returns:
        GoalItem: 目标项
    """
    # 获取分类名称
    category_name = _get_category_name(item.get('link_to_category_id'))
    sub_category_name = _get_sub_category_name(item.get('link_to_sub_category_id'))
    
    return GoalItem(
        id=item['id'],
        name=item['name'],
        abstract=item.get('abstract'),
        content=item.get('content', ''),
        color=item.get('color', '#5B8FF9'),
        created_at=item.get('created_at', ''),
        link_to_category=category_name,
        link_to_sub_category=sub_category_name,
        link_to_reward_id=item.get('link_to_reward_id'),
        expected_finished_at=item.get('expected_finished_at'),
        expected_hours=item.get('expected_hours'),
        actual_finished_at=item.get('actual_finished_at'),
        actual_hours=item.get('actual_hours'),
        completion_rate=item.get('completion_rate', 0.0),
        status=item.get('status', 'active'),
        order_index=item.get('order_index', 0)
    )


# ============================================================================
# Goal 服务
# ============================================================================


def get_goals(
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> GoalListResponse:
    """
    获取目标列表
    
    Args:
        status: 按状态筛选
        category_id: 按分类筛选
        page: 页码
        page_size: 每页数量
    
    Returns:
        GoalListResponse: 目标列表响应
    """
    items, total = goal_provider.get_goals(
        status=status,
        category_id=category_id,
        page=page,
        page_size=page_size
    )
    
    # 转换为响应模型
    goal_items = [_convert_db_item_to_goal_item(item) for item in items]
    
    return GoalListResponse(items=goal_items, total=total)


def get_goal_detail(goal_id: int) -> Optional[GoalItem]:
    """
    获取目标详情
    
    Args:
        goal_id: 目标 ID
    
    Returns:
        Optional[GoalItem]: 目标详情，不存在返回 None
    """
    item = goal_provider.get_goal_by_id(goal_id)
    if not item:
        return None
    
    return _convert_db_item_to_goal_item(item)


def create_goal(request: CreateGoalRequest) -> Optional[GoalItem]:
    """
    创建目标
    
    Args:
        request: 创建目标请求
    
    Returns:
        Optional[GoalItem]: 新创建的目标，失败返回 None
    """
    data = {
        'name': request.name,
        'abstract': request.abstract,
        'content': request.content,
        'color': request.color,
        'link_to_category_id': request.link_to_category_id,
        'link_to_sub_category_id': request.link_to_sub_category_id,
        'link_to_reward_id': request.link_to_reward_id,
        'expected_finished_at': request.expected_finished_at,
        'expected_hours': request.expected_hours,
    }
    
    new_id = goal_provider.create_goal(data)
    if new_id is None:
        return None
    
    return get_goal_detail(new_id)


def update_goal(goal_id: int, request: UpdateGoalRequest) -> Optional[GoalItem]:
    """
    更新目标
    
    Args:
        goal_id: 目标 ID
        request: 更新目标请求
    
    Returns:
        Optional[GoalItem]: 更新后的目标，失败返回 None
    """
    # 构建更新数据，只包含非 None 的字段
    update_data = {}
    
    if request.name is not None:
        update_data['name'] = request.name
    if request.abstract is not None:
        update_data['abstract'] = request.abstract
    if request.content is not None:
        update_data['content'] = request.content
    if request.color is not None:
        update_data['color'] = request.color
    if request.link_to_category_id is not None:
        update_data['link_to_category_id'] = request.link_to_category_id
    if request.link_to_sub_category_id is not None:
        update_data['link_to_sub_category_id'] = request.link_to_sub_category_id
    if request.link_to_reward_id is not None:
        update_data['link_to_reward_id'] = request.link_to_reward_id
    if request.expected_finished_at is not None:
        update_data['expected_finished_at'] = request.expected_finished_at
    if request.expected_hours is not None:
        update_data['expected_hours'] = request.expected_hours
    if request.actual_finished_at is not None:
        update_data['actual_finished_at'] = request.actual_finished_at
    if request.actual_hours is not None:
        update_data['actual_hours'] = request.actual_hours
    if request.completion_rate is not None:
        update_data['completion_rate'] = request.completion_rate
    if request.status is not None:
        update_data['status'] = request.status
    
    success = goal_provider.update_goal(goal_id, update_data)
    if not success:
        return None
    
    return get_goal_detail(goal_id)


def delete_goal(goal_id: int) -> bool:
    """
    删除目标
    
    Args:
        goal_id: 目标 ID
    
    Returns:
        bool: 是否成功
    """
    return goal_provider.delete_goal(goal_id)


def reorder_goals(request: ReorderGoalRequest) -> bool:
    """
    重排序目标
    
    Args:
        request: 重排序请求
    
    Returns:
        bool: 是否成功
    """
    return goal_provider.reorder_goals(request.goal_ids)

