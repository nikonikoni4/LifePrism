"""
Reward 服务层 - Reward 奖励业务逻辑

提供 Reward 的有状态服务类
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

from lifeprism.server.schemas.goal_schemas import (
    RewardItem,
    RewardListResponse,
    CreateRewardRequest,
    UpdateRewardRequest,
    RewardHistoryPoint,
    RewardStatsResponse,
    MilestoneItem,
)
from lifeprism.server.providers.reward_provider import reward_provider
from lifeprism.server.providers.goal_stats_provider import goal_stats_provider
from lifeprism.server.providers.goal_provider import goal_provider
from lifeprism.utils import get_logger

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
        # 解析 milestones JSON
        milestones = []
        milestones_json = item.get('milestones')
        if milestones_json:
            try:
                milestones_data = json.loads(milestones_json)
                for key, value in milestones_data.items():
                    milestones.append(MilestoneItem(
                        id=key,
                        content=value.get('content', ''),
                        state=value.get('state', 0),
                        finish_time=value.get('finish_time'),
                        order_index=value.get('order_index', int(key) if key.isdigit() else 0)
                    ))
                # 按 order_index 排序
                milestones.sort(key=lambda m: m.order_index)
            except json.JSONDecodeError:
                logger.warning(f"解析 milestones JSON 失败: {milestones_json}")
        
        return RewardItem(
            id=item['id'],
            goal_id=item['goal_id'],
            name=item['name'],
            start_time=item.get('start_time', ''),
            target_hours=item.get('target_hours', 0),
            milestones=milestones,
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
            'milestones': request.milestones,
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
        if 'milestones' in explicitly_set_fields:
            update_data['milestones'] = request.milestones
        
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
    
    def update_milestone_state(self, reward_id: int, milestone_id: str, state: int) -> Optional[RewardItem]:
        """
        更新里程碑状态，并实现自动交换逻辑：
        当后面的里程碑被点亮，但前面有未点亮的 (state=0)，则交换位置
        
        例如：1(state=1), 2(state=1), 3(state=0), 4(state=1)
        第一个 state=0 是 3，第一个在它之后的 state=1 是 4
        所以 3 和 4 的 order_index 交换
        
        Args:
            reward_id: 奖励 ID
            milestone_id: 里程碑 ID
            state: 新状态 0: 未达成, 1: 已达成
        
        Returns:
            Optional[RewardItem]: 更新后的奖励，失败返回 None
        """
        reward = reward_provider.get_reward_by_id(reward_id)
        if not reward:
            logger.warning(f"奖励 {reward_id} 不存在")
            return None
        
        milestones_json = reward.get('milestones')
        if not milestones_json:
            logger.warning(f"奖励 {reward_id} 没有里程碑")
            return None
        
        try:
            milestones_data = json.loads(milestones_json)
        except json.JSONDecodeError:
            logger.error(f"解析 milestones JSON 失败: {milestones_json}")
            return None
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 更新目标里程碑状态
        if milestone_id not in milestones_data:
            logger.warning(f"里程碑 {milestone_id} 不存在")
            return None
        
        milestones_data[milestone_id]['state'] = state
        if state == 1:
            milestones_data[milestone_id]['finish_time'] = today
        else:
            milestones_data[milestone_id]['finish_time'] = None
        
        # 转换为列表并按 order_index 排序
        milestones_list = []
        for k, v in milestones_data.items():
            milestones_list.append({
                'id': k,
                'content': v.get('content', ''),
                'state': v.get('state', 0),
                'finish_time': v.get('finish_time'),
                'order_index': v.get('order_index', int(k) if k.isdigit() else 0)
            })
        milestones_list.sort(key=lambda m: m['order_index'])
        
        # 实现交换逻辑：
        # 找到第一个 state == 0 的节点
        # 然后找到它之后第一个 state == 1 的节点
        # 交换它们的 order_index
        first_incomplete_idx = None
        for i, m in enumerate(milestones_list):
            if m['state'] == 0:
                first_incomplete_idx = i
                break
        
        if first_incomplete_idx is not None:
            # 检查后面是否有已完成的 (state == 1)
            for j in range(first_incomplete_idx + 1, len(milestones_list)):
                if milestones_list[j]['state'] == 1:
                    # 交换 order_index
                    old_order_i = milestones_list[first_incomplete_idx]['order_index']
                    old_order_j = milestones_list[j]['order_index']
                    milestones_list[first_incomplete_idx]['order_index'] = old_order_j
                    milestones_list[j]['order_index'] = old_order_i
                    logger.info(f"交换里程碑位置: {milestones_list[first_incomplete_idx]['id']} 和 {milestones_list[j]['id']}")
                    break
        
        # 重新构建 JSON
        new_milestones = {}
        for m in milestones_list:
            mid = m['id']
            new_milestones[mid] = {
                'content': m['content'],
                'state': m['state'],
                'finish_time': m['finish_time'],
                'order_index': m['order_index']
            }
        
        success = reward_provider.update_reward(reward_id, {'milestones': json.dumps(new_milestones)})
        if not success:
            return None
        
        return self.get_reward_detail(reward_id)


# 创建全局单例
reward_service = RewardService()
