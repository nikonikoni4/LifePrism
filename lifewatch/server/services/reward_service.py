"""
Reward 服务层 - Reward 奖励业务逻辑

提供 Reward 的有状态服务类
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from lifewatch.server.schemas.goal_schemas import (
    RewardItem,
    RewardListResponse,
    CreateRewardRequest,
    UpdateRewardRequest,
    RewardHistoryPoint,
    RewardStatsResponse,
)
from lifewatch.server.providers.reward_provider import reward_provider
from lifewatch.server.providers.goal_stats_provider import goal_stats_provider
from lifewatch.server.providers.goal_provider import goal_provider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class RewardService:
    """
    奖励服务类
    
    提供奖励的 CRUD 操作和统计数据获取
    """
    
    def __init__(self):
        """初始化奖励服务"""
        pass
    
    def _convert_db_item_to_reward_item(self, item: Dict[str, Any]) -> RewardItem:
        """
        将数据库记录转换为 RewardItem
        """
        return RewardItem(
            id=item['id'],
            goal_id=item['goal_id'],
            name=item['name'],
            start_time=item.get('start_time', ''),
            target_hours=item.get('target_hours', 0),
            order_index=item.get('order_index', 0),
            created_at=item.get('created_at', '')
        )
    
    def get_rewards(self) -> RewardListResponse:
        """
        获取所有奖励列表
        
        Returns:
            RewardListResponse: 奖励列表响应
        """
        items = reward_provider.get_rewards()
        reward_items = [self._convert_db_item_to_reward_item(item) for item in items]
        return RewardListResponse(items=reward_items)
    
    def get_reward_detail(self, reward_id: int) -> Optional[RewardItem]:
        """
        获取奖励详情
        
        Args:
            reward_id: 奖励 ID
        
        Returns:
            Optional[RewardItem]: 奖励详情，不存在返回 None
        """
        item = reward_provider.get_reward_by_id(reward_id)
        if not item:
            return None
        return self._convert_db_item_to_reward_item(item)
    
    def get_reward_stats(self, reward_id: int) -> Optional[RewardStatsResponse]:
        """
        获取奖励统计数据（含历史累积数据）
        
        核心方法：实现懒加载更新
        1. 获取 reward 关联的 goal_id
        2. 同步 goal_stats 到今天
        3. 返回累积数据
        
        Args:
            reward_id: 奖励 ID
        
        Returns:
            Optional[RewardStatsResponse]: 统计数据响应
        """
        # 1. 获取奖励信息
        reward_item = reward_provider.get_reward_by_id(reward_id)
        if not reward_item:
            logger.warning(f"奖励 {reward_id} 不存在")
            return None
        
        goal_id = reward_item['goal_id']
        start_time = reward_item.get('start_time')  # 获取 reward 的开始时间
        
        # 2. 获取目标名称
        goal = goal_provider.get_goal_by_id(goal_id)
        goal_name = goal['name'] if goal else 'Unknown Goal'
        
        # 3. 同步统计数据到今天（从 start_time 开始）
        today = datetime.now().strftime("%Y-%m-%d")
        goal_stats_provider.sync_stats_to_date(goal_id, today, start_date=start_time)
        
        # 4. 获取累积统计数据
        cumulative_stats = goal_stats_provider.get_cumulative_stats(goal_id, limit=30)
        
        # 5. 转换为响应格式
        history = []
        for stat in cumulative_stats:
            # 格式化日期为 MM-DD 格式用于图表显示
            date_str = stat['date']
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                display_date = dt.strftime("%m-%d")
            except:
                display_date = date_str
            
            history.append(RewardHistoryPoint(
                date=display_date,
                cumulative_time_spent=stat['cumulative_time_spent'] // 60,  # 转换为分钟
                cumulative_todo_count=stat['cumulative_todo_count']
            ))
        
        return RewardStatsResponse(
            reward=self._convert_db_item_to_reward_item(reward_item),
            goal_name=goal_name,
            history=history
        )
    
    def create_reward(self, request: CreateRewardRequest) -> Optional[RewardItem]:
        """
        创建奖励
        
        Args:
            request: 创建奖励请求
        
        Returns:
            Optional[RewardItem]: 新创建的奖励，失败返回 None
        """
        data = {
            'goal_id': request.goal_id,
            'name': request.name,
            'start_time': request.start_time,
            'target_hours': request.target_hours,
        }
        
        reward_id = reward_provider.create_reward(data)
        if not reward_id:
            return None
        
        return self.get_reward_detail(reward_id)
    
    def update_reward(self, reward_id: int, request: UpdateRewardRequest) -> Optional[RewardItem]:
        """
        更新奖励
        
        Args:
            reward_id: 奖励 ID
            request: 更新奖励请求
        
        Returns:
            Optional[RewardItem]: 更新后的奖励，失败返回 None
        """
        # 获取显式设置的字段
        explicitly_set_fields = request.model_fields_set
        
        update_data = {}
        if 'goal_id' in explicitly_set_fields:
            update_data['goal_id'] = request.goal_id
        if 'name' in explicitly_set_fields:
            update_data['name'] = request.name
        if 'start_time' in explicitly_set_fields:
            update_data['start_time'] = request.start_time
        if 'target_hours' in explicitly_set_fields:
            update_data['target_hours'] = request.target_hours
        
        if not update_data:
            # 没有要更新的字段，直接返回当前数据
            return self.get_reward_detail(reward_id)
        
        success = reward_provider.update_reward(reward_id, update_data)
        if not success:
            return None
        
        return self.get_reward_detail(reward_id)
    
    def delete_reward(self, reward_id: int) -> bool:
        """
        删除奖励
        
        Args:
            reward_id: 奖励 ID
        
        Returns:
            bool: 是否成功
        """
        return reward_provider.delete_reward(reward_id)


# 创建全局单例
reward_service = RewardService()
