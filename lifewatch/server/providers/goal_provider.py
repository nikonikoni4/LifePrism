"""
Goal 数据提供者
提供 Goal 目标的数据库操作
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class GoalProvider(LWBaseDataProvider):
    """
    目标数据提供者
    
    继承 LWBaseDataProvider，提供 Goal 的 CRUD 操作
    """
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== Goal 操作 ====================
    
    def get_goals(
        self,
        status: Optional[str] = None,
        category_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        获取目标列表
        
        Args:
            status: 按状态筛选（active, completed, archived）
            category_id: 按分类筛选
            page: 页码（从1开始）
            page_size: 每页数量
        
        Returns:
            tuple: (目标列表, 总数)
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                conditions = []
                params = []
                
                if status:
                    conditions.append("status = ?")
                    params.append(status)
                
                if category_id:
                    conditions.append("link_to_category_id = ?")
                    params.append(category_id)
                
                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)
                
                # 先获取总数
                count_sql = f"SELECT COUNT(*) FROM goal {where_clause}"
                cursor.execute(count_sql, params)
                total = cursor.fetchone()[0]
                
                # 获取分页数据
                offset = (page - 1) * page_size
                sql = f"""
                SELECT * FROM goal 
                {where_clause}
                ORDER BY order_index ASC, created_at DESC
                LIMIT ? OFFSET ?
                """
                cursor.execute(sql, params + [page_size, offset])
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                items = [dict(zip(columns, row)) for row in rows]
                return items, total
                
        except Exception as e:
            logger.error(f"获取目标列表失败: {e}")
            return [], 0
    
    def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取单个目标
        
        Args:
            goal_id: 目标 ID (格式: goal-xxx)
        
        Returns:
            Optional[Dict]: 目标数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM goal WHERE id = ?", (goal_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取目标 {goal_id} 失败: {e}")
            return None
    
    def create_goal(self, data: Dict[str, Any]) -> Optional[str]:
        """
        创建新目标
        
        Args:
            data: 目标数据
        
        Returns:
            Optional[str]: 新目标 ID (格式: goal-xxx)，失败返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 生成唯一 ID（与 category 格式一致）
                goal_id = f"goal-{str(uuid.uuid4())[:8]}"
                
                # 获取当前最大 order_index
                cursor.execute("SELECT COALESCE(MAX(order_index), -1) + 1 FROM goal")
                next_order = cursor.fetchone()[0]
                
                # 构建插入数据
                columns = [
                    'id', 'name', 'abstract', 'content', 'color',
                    'link_to_category_id', 'link_to_sub_category_id', 'link_to_reward_id',
                    'expected_finished_at', 'expected_hours',
                    'status', 'order_index'
                ]
                values = [
                    goal_id,
                    data.get('name'),
                    data.get('abstract'),
                    data.get('content', ''),
                    data.get('color', '#FFFFFF'),
                    data.get('link_to_category_id'),
                    data.get('link_to_sub_category_id'),
                    data.get('link_to_reward_id'),
                    data.get('expected_finished_at'),
                    data.get('expected_hours'),
                    data.get('status', 'active'),
                    next_order
                ]
                
                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join(columns)
                
                cursor.execute(
                    f"INSERT INTO goal ({columns_str}) VALUES ({placeholders})",
                    values
                )
                
                logger.info(f"创建目标成功，ID: {goal_id}")
                return goal_id
                
        except Exception as e:
            logger.error(f"创建目标失败: {e}")
            return None
    
    def update_goal(self, goal_id: str, data: Dict[str, Any]) -> bool:
        """
        更新目标
        
        Args:
            goal_id: 目标 ID (格式: goal-xxx)
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
                allowed_fields = [
                    'name', 'abstract', 'content', 'color',
                    'link_to_category_id', 'link_to_sub_category_id', 'link_to_reward_id',
                    'expected_finished_at', 'expected_hours',
                    'actual_finished_at', 'actual_hours',
                    'completion_rate', 'status', 'order_index'
                ]
                
                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in allowed_fields:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if not set_clauses:
                    return True
                
                values.append(goal_id)
                sql = f"UPDATE goal SET {', '.join(set_clauses)} WHERE id = ?"
                
                cursor.execute(sql, values)
                success = cursor.rowcount > 0
                
                if success:
                    logger.info(f"更新目标 {goal_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"更新目标 {goal_id} 失败: {e}")
            return False
    
    def delete_goal(self, goal_id: str) -> bool:
        """
        删除目标
        
        Args:
            goal_id: 目标 ID (格式: goal-xxx)
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 先清除 todo_list 中关联的目标
                cursor.execute(
                    "UPDATE todo_list SET link_to_goal_id = NULL WHERE link_to_goal_id = ?",
                    (goal_id,)
                )
                cleared_count = cursor.rowcount
                if cleared_count > 0:
                    logger.info(f"清除了 {cleared_count} 个任务的目标关联")
                
                # 然后删除目标
                cursor.execute("DELETE FROM goal WHERE id = ?", (goal_id,))
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"删除目标 {goal_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"删除目标 {goal_id} 失败: {e}")
            return False
    
    def reorder_goals(self, goal_ids: List[str]) -> bool:
        """
        批量更新目标排序
        
        Args:
            goal_ids: 目标 ID 列表（按新顺序排列）
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                for index, goal_id in enumerate(goal_ids):
                    cursor.execute(
                        "UPDATE goal SET order_index = ? WHERE id = ?",
                        (index, goal_id)
                    )
                
                logger.info(f"重排序 {len(goal_ids)} 个目标成功")
                return True
                
        except Exception as e:
            logger.error(f"重排序目标失败: {e}")
            return False
    
    def get_active_goals(self) -> List[Dict[str, Any]]:
        """
        获取所有进行中的目标（用于前端选择绑定）
        
        Returns:
            List[Dict]: 目标列表，包含 id 和 name
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, name FROM goal WHERE status = 'active' ORDER BY order_index ASC"
                )
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取活跃目标列表失败: {e}")
            return []
    
    def get_goals_linked_to_category(self, category_id: str) -> List[Dict[str, Any]]:
        """
        获取关联到特定分类的所有目标
        
        Args:
            category_id: 分类 ID
        
        Returns:
            List[Dict]: 目标列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM goal WHERE link_to_category_id = ? ORDER BY order_index ASC",
                    (category_id,)
                )
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取分类关联目标失败: {e}")
            return []

    def get_active_goals_for_classify(self) -> List[Dict[str, Any]]:
        """
        获取所有活跃目标（用于 LLM 分类时的名称-ID映射）
        
        Returns:
            List[Dict]: 包含 id, name, link_to_category_id, link_to_sub_category_id 的目标列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, link_to_category_id, link_to_sub_category_id 
                    FROM goal 
                    WHERE status = 'active' 
                    ORDER BY order_index ASC
                """)
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取活跃目标列表（用于分类）失败: {e}")
            return []


# 创建全局单例
goal_provider = GoalProvider()

