"""
Reward 数据提供者
提供 Reward 奖励的数据库操作
"""
from typing import Optional, List, Dict, Any

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class RewardProvider(LWBaseDataProvider):
    """
    奖励数据提供者
    
    继承 LWBaseDataProvider，提供 Reward 的 CRUD 操作
    """
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== Reward 操作 ====================
    
    def get_rewards(self) -> List[Dict[str, Any]]:
        """
        获取所有奖励列表
        
        Returns:
            List[Dict]: 奖励列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM reward 
                    ORDER BY order_index ASC, created_at DESC
                """)
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取奖励列表失败: {e}")
            return []
    
    def get_reward_by_id(self, reward_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取单个奖励
        
        Args:
            reward_id: 奖励 ID
        
        Returns:
            Optional[Dict]: 奖励数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM reward WHERE id = ?", (reward_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取奖励 {reward_id} 失败: {e}")
            return None
    
    def get_reward_by_goal_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """
        按 Goal ID 获取关联的奖励
        
        Args:
            goal_id: 目标 ID
        
        Returns:
            Optional[Dict]: 奖励数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM reward WHERE goal_id = ?", (goal_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取目标 {goal_id} 的奖励失败: {e}")
            return None
    
    def create_reward(self, data: Dict[str, Any]) -> Optional[int]:
        """
        创建新奖励
        
        Args:
            data: 奖励数据
        
        Returns:
            Optional[int]: 新奖励 ID，失败返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取当前最大 order_index
                cursor.execute("SELECT COALESCE(MAX(order_index), -1) + 1 FROM reward")
                next_order = cursor.fetchone()[0]
                
                # 构建插入数据
                columns = ['goal_id', 'name', 'start_time', 'target_hours', 'order_index']
                values = [
                    data.get('goal_id'),
                    data.get('name'),
                    data.get('start_time'),
                    data.get('target_hours', 0),
                    next_order
                ]
                
                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join(columns)
                
                cursor.execute(
                    f"INSERT INTO reward ({columns_str}) VALUES ({placeholders})",
                    values
                )
                
                reward_id = cursor.lastrowid
                logger.info(f"创建奖励成功，ID: {reward_id}")
                return reward_id
                
        except Exception as e:
            logger.error(f"创建奖励失败: {e}")
            return None
    
    def update_reward(self, reward_id: int, data: Dict[str, Any]) -> bool:
        """
        更新奖励
        
        Args:
            reward_id: 奖励 ID
            data: 要更新的字段
        
        Returns:
            bool: 是否成功
        """
        try:
            if not data:
                return True
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 允许更新的字段
                allowed_fields = ['goal_id', 'name', 'start_time', 'target_hours', 'order_index']
                
                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in allowed_fields:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if not set_clauses:
                    return True
                
                values.append(reward_id)
                sql = f"UPDATE reward SET {', '.join(set_clauses)} WHERE id = ?"
                
                cursor.execute(sql, values)
                success = cursor.rowcount > 0
                
                if success:
                    logger.info(f"更新奖励 {reward_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"更新奖励 {reward_id} 失败: {e}")
            return False
    
    def delete_reward(self, reward_id: int) -> bool:
        """
        删除奖励
        
        Args:
            reward_id: 奖励 ID
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 先清除 goal 中关联的奖励引用
                cursor.execute(
                    "UPDATE goal SET link_to_reward_id = NULL WHERE link_to_reward_id = ?",
                    (reward_id,)
                )
                cleared_count = cursor.rowcount
                if cleared_count > 0:
                    logger.info(f"清除了 {cleared_count} 个目标的奖励关联")
                
                # 然后删除奖励
                cursor.execute("DELETE FROM reward WHERE id = ?", (reward_id,))
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"删除奖励 {reward_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"删除奖励 {reward_id} 失败: {e}")
            return False


# 创建全局单例
reward_provider = RewardProvider()
