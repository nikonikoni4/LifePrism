"""
Goal 服务层 - Goal 目标业务逻辑

提供 Goal 的有状态服务类，类似于 CategoryService
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from lifewatch.server.schemas.goal_schemas import (
    GoalItem,
    GoalListResponse,
    CreateGoalRequest,
    UpdateGoalRequest,
    ReorderGoalRequest,
    ActiveGoalItem,
    ActiveGoalNamesResponse,
)
from lifewatch.server.providers.goal_provider import goal_provider
from lifewatch.server.services.category_service import category_service
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class GoalService:
    """
    目标服务类
    
    维护 goal_name_map 缓存，提供目标的 CRUD 操作
    """
    
    def __init__(self):
        """
        初始化目标服务，构建 goal_name_map 缓存
        """
        self.goal_provider = goal_provider
        # 初始化 goal_name_map: goal_id -> goal_name
        self.goal_name_map: Dict[str, str] = {}
        self._refresh_cache()
    
    def _refresh_cache(self):
        """
        刷新目标名称缓存
        """
        try:
            # 获取所有目标
            items, _ = self.goal_provider.get_goals(page=1, page_size=1000)
            
            # 构建映射
            self.goal_name_map = {}
            for item in items:
                goal_id = str(item.get('id', ''))
                name = item.get('name', '')
                if goal_id and name:
                    self.goal_name_map[goal_id] = name
            
            logger.debug(f"刷新目标缓存成功，共 {len(self.goal_name_map)} 个目标")
        except Exception as e:
            logger.error(f"刷新目标缓存失败: {e}")
    
    def _get_category_name(self, category_id: Optional[str]) -> Optional[str]:
        """
        根据分类 ID 获取分类名称
        """
        if not category_id:
            return None
        return category_service.category_name_map.get(str(category_id))
    
    def _get_sub_category_name(self, sub_category_id: Optional[str]) -> Optional[str]:
        """
        根据子分类 ID 获取子分类名称
        """
        if not sub_category_id:
            return None
        return category_service.sub_category_name_map.get(str(sub_category_id))
    
    def _convert_db_item_to_goal_item(self, item: Dict[str, Any]) -> GoalItem:
        """
        将数据库记录转换为 GoalItem，同时将分类 ID 转换为名称
        """
        category_name = self._get_category_name(item.get('link_to_category_id'))
        sub_category_name = self._get_sub_category_name(item.get('link_to_sub_category_id'))
        
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
    
    def get_goals(
        self,
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
        items, total = self.goal_provider.get_goals(
            status=status,
            category_id=category_id,
            page=page,
            page_size=page_size
        )
        
        # 转换为响应模型
        goal_items = [self._convert_db_item_to_goal_item(item) for item in items]
        
        return GoalListResponse(items=goal_items, total=total)
    
    def get_goal_detail(self, goal_id: str) -> Optional[GoalItem]:
        """
        获取目标详情
        
        Args:
            goal_id: 目标 ID (格式: goal-xxx)
        
        Returns:
            Optional[GoalItem]: 目标详情，不存在返回 None
        """
        item = self.goal_provider.get_goal_by_id(goal_id)
        if not item:
            return None
        
        return self._convert_db_item_to_goal_item(item)
    
    def create_goal(self, request: CreateGoalRequest) -> Optional[GoalItem]:
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
        
        new_id = self.goal_provider.create_goal(data)
        if new_id is None:
            return None
        
        # 刷新缓存
        self._refresh_cache()
        
        return self.get_goal_detail(new_id)
    
    def update_goal(self, goal_id: str, request: UpdateGoalRequest) -> Optional[GoalItem]:
        """
        更新目标
        
        Args:
            goal_id: 目标 ID (格式: goal-xxx)
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
        
        success = self.goal_provider.update_goal(goal_id, update_data)
        if not success:
            return None
        
        # 如果更新了 name 或 status，刷新缓存
        if 'name' in update_data or 'status' in update_data:
            self._refresh_cache()
        
        return self.get_goal_detail(goal_id)
    
    def delete_goal(self, goal_id: str) -> bool:
        """
        删除目标
        
        Args:
            goal_id: 目标 ID (格式: goal-xxx)
        
        Returns:
            bool: 是否成功
        """
        success = self.goal_provider.delete_goal(goal_id)
        if success:
            # 刷新缓存
            self._refresh_cache()
        return success
    
    def reorder_goals(self, request: ReorderGoalRequest) -> bool:
        """
        重排序目标
        
        Args:
            request: 重排序请求
        
        Returns:
            bool: 是否成功
        """
        return self.goal_provider.reorder_goals(request.goal_ids)
    
    def get_active_goal_names(self) -> ActiveGoalNamesResponse:
        """
        获取所有进行中的目标名称（用于前端下拉选择）
        
        Returns:
            ActiveGoalNamesResponse: 活跃目标列表
        """
        items = self.goal_provider.get_active_goals()
        
        active_items = [
            ActiveGoalItem(
                id=item['id'],
                name=item['name']
            )
            for item in items
        ]
        
        return ActiveGoalNamesResponse(items=active_items)
    
    def get_goal_name(self, goal_id: str) -> Optional[str]:
        """
        根据目标 ID 获取目标名称（使用缓存）
        
        Args:
            goal_id: 目标 ID
        
        Returns:
            Optional[str]: 目标名称，不存在返回 None
        """
        return self.goal_name_map.get(str(goal_id))


# 创建全局单例
goal_service = GoalService()
