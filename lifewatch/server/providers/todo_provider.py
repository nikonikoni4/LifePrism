"""
Goal 数据提供者
提供 TodoList 和 SubTodoList 的数据库操作
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class TodoProvider(LWBaseDataProvider):
    """
    目标模块数据提供者
    
    继承 LWBaseDataProvider，提供 TodoList 和 SubTodoList 的 CRUD 操作
    """
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # ==================== TodoList 操作 ====================
    
    def get_todos_by_date(
        self, 
        date: str, 
        include_cross_day: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取指定日期的任务列表
        
        Args:
            date: 日期（YYYY-MM-DD 格式）
            include_cross_day: 是否包含跨天未完成任务
        
        Returns:
            List[Dict]: 任务列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                if include_cross_day:
                    # 获取当天任务 + 跨天未完成任务
                    sql = """
                    SELECT * FROM todo_list 
                    WHERE date = ? 
                       OR (cross_day = 1 AND state = 'active' AND date < ?)
                    ORDER BY order_index ASC
                    """
                    cursor.execute(sql, (date, date))
                else:
                    # 仅获取当天任务
                    sql = """
                    SELECT * FROM todo_list 
                    WHERE date = ?
                    ORDER BY order_index ASC
                    """
                    cursor.execute(sql, (date,))
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return []
    
    def get_todo_by_id(self, todo_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取单个任务
        
        Args:
            todo_id: 任务 ID
        
        Returns:
            Optional[Dict]: 任务数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM todo_list WHERE id = ?", (todo_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取任务 {todo_id} 失败: {e}")
            return None
    
    def create_todo(self, data: Dict[str, Any]) -> Optional[int]:
        """
        创建新任务
        
        Args:
            data: 任务数据
        
        Returns:
            Optional[int]: 新任务 ID，失败返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取当前最大 order_index
                cursor.execute(
                    "SELECT COALESCE(MAX(order_index), -1) + 1 FROM todo_list WHERE date = ?",
                    (data.get('date'),)
                )
                next_order = cursor.fetchone()[0]
                
                # 插入数据
                columns = ['order_index', 'pool_order_index', 'content', 'color', 'state', 
                          'link_to_goal_id', 'date', 'expected_finished_at', 
                          'actual_finished_at', 'cross_day']
                values = [
                    next_order,
                    data.get('pool_order_index'),
                    data.get('content'),
                    data.get('color', '#FFFFFF'),
                    data.get('state', 'active'),
                    data.get('link_to_goal_id'),
                    data.get('date'),
                    data.get('expected_finished_at'),
                    data.get('actual_finished_at'),
                    1 if data.get('cross_day') else 0
                ]
                
                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join(columns)
                
                cursor.execute(
                    f"INSERT INTO todo_list ({columns_str}) VALUES ({placeholders})",
                    values
                )
                
                new_id = cursor.lastrowid
                logger.info(f"创建任务成功，ID: {new_id}")
                return new_id
                
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            return None
    
    def update_todo(self, todo_id: int, data: Dict[str, Any]) -> bool:
        """
        更新任务
        
        Args:
            todo_id: 任务 ID
            data: 要更新的字段
        
        Returns:
            bool: 是否成功
        """
        try:
            if not data:
                return True
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建 SET 子句
                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in ['content', 'color', 'state', 'link_to_goal_id',
                              'date', 'expected_finished_at', 'actual_finished_at', 
                              'cross_day', 'pool_order_index']:
                        set_clauses.append(f"{key} = ?")
                        # 处理布尔值
                        if key == 'cross_day':
                            values.append(1 if value else 0)
                        else:
                            values.append(value)
                
                if not set_clauses:
                    return True
                
                values.append(todo_id)
                sql = f"UPDATE todo_list SET {', '.join(set_clauses)} WHERE id = ?"
                
                cursor.execute(sql, values)
                success = cursor.rowcount > 0
                
                if success:
                    logger.info(f"更新任务 {todo_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"更新任务 {todo_id} 失败: {e}")
            return False
    
    def delete_todo(self, todo_id: int) -> bool:
        """
        删除任务（子任务会级联删除）
        
        Args:
            todo_id: 任务 ID
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 先删除子任务
                cursor.execute("DELETE FROM sub_todo_list WHERE parent_id = ?", (todo_id,))
                
                # 再删除主任务
                cursor.execute("DELETE FROM todo_list WHERE id = ?", (todo_id,))
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"删除任务 {todo_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"删除任务 {todo_id} 失败: {e}")
            return False
    
    def reorder_todos(self, todo_ids: List[int]) -> bool:
        """
        批量更新任务排序
        
        Args:
            todo_ids: 任务 ID 列表（按新顺序排列）
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                for index, todo_id in enumerate(todo_ids):
                    cursor.execute(
                        "UPDATE todo_list SET order_index = ? WHERE id = ?",
                        (index, todo_id)
                    )
                
                logger.info(f"重排序 {len(todo_ids)} 个任务成功")
                return True
                
        except Exception as e:
            logger.error(f"重排序任务失败: {e}")
            return False
    
    # ==================== Task Pool 操作 ====================
    
    def get_todos_by_state(self, state: str) -> List[Dict[str, Any]]:
        """
        根据状态获取任务列表
        
        Args:
            state: 任务状态 ('active', 'completed', 'inactive')
        
        Returns:
            List[Dict]: 任务列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 对于 inactive 状态（任务池），按 pool_order_index 排序
                if state == 'inactive':
                    sql = """
                    SELECT * FROM todo_list 
                    WHERE state = ?
                    ORDER BY pool_order_index ASC, id ASC
                    """
                else:
                    sql = """
                    SELECT * FROM todo_list 
                    WHERE state = ?
                    ORDER BY order_index ASC
                    """
                
                cursor.execute(sql, (state,))
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取任务列表失败 (state={state}): {e}")
            return []
    
    def reorder_pool_todos(self, todo_ids: List[int]) -> bool:
        """
        批量更新任务池排序 (pool_order_index)
        
        Args:
            todo_ids: 任务 ID 列表（按新顺序排列）
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                for index, todo_id in enumerate(todo_ids):
                    cursor.execute(
                        "UPDATE todo_list SET pool_order_index = ? WHERE id = ?",
                        (index, todo_id)
                    )
                
                logger.info(f"重排序任务池 {len(todo_ids)} 个任务成功")
                return True
                
        except Exception as e:
            logger.error(f"重排序任务池失败: {e}")
            return False
    
    # ==================== SubTodoList 操作 ====================
    
    def get_sub_todos_by_parent(self, parent_id: int) -> List[Dict[str, Any]]:
        """
        获取子任务列表
        
        Args:
            parent_id: 父任务 ID
        
        Returns:
            List[Dict]: 子任务列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM sub_todo_list WHERE parent_id = ? ORDER BY order_index ASC",
                    (parent_id,)
                )
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取子任务列表失败: {e}")
            return []
    
    def create_sub_todo(self, parent_id: int, content: str) -> Optional[int]:
        """
        创建子任务
        
        Args:
            parent_id: 父任务 ID
            content: 子任务内容
        
        Returns:
            Optional[int]: 新子任务 ID，失败返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取当前最大 order_index
                cursor.execute(
                    "SELECT COALESCE(MAX(order_index), -1) + 1 FROM sub_todo_list WHERE parent_id = ?",
                    (parent_id,)
                )
                next_order = cursor.fetchone()[0]
                
                cursor.execute(
                    "INSERT INTO sub_todo_list (parent_id, order_index, content, completed) VALUES (?, ?, ?, 0)",
                    (parent_id, next_order, content)
                )
                
                new_id = cursor.lastrowid
                logger.info(f"创建子任务成功，ID: {new_id}")
                return new_id
                
        except Exception as e:
            logger.error(f"创建子任务失败: {e}")
            return None
    
    def get_sub_todo_by_id(self, sub_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取子任务
        
        Args:
            sub_id: 子任务 ID
        
        Returns:
            Optional[Dict]: 子任务数据
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sub_todo_list WHERE id = ?", (sub_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取子任务 {sub_id} 失败: {e}")
            return None
    
    def update_sub_todo(self, sub_id: int, data: Dict[str, Any]) -> bool:
        """
        更新子任务
        
        Args:
            sub_id: 子任务 ID
            data: 要更新的字段
        
        Returns:
            bool: 是否成功
        """
        try:
            if not data:
                return True
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in ['content', 'completed']:
                        set_clauses.append(f"{key} = ?")
                        if key == 'completed':
                            values.append(1 if value else 0)
                        else:
                            values.append(value)
                
                if not set_clauses:
                    return True
                
                values.append(sub_id)
                sql = f"UPDATE sub_todo_list SET {', '.join(set_clauses)} WHERE id = ?"
                
                cursor.execute(sql, values)
                success = cursor.rowcount > 0
                
                if success:
                    logger.info(f"更新子任务 {sub_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"更新子任务 {sub_id} 失败: {e}")
            return False
    
    def delete_sub_todo(self, sub_id: int) -> bool:
        """
        删除子任务
        
        Args:
            sub_id: 子任务 ID
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sub_todo_list WHERE id = ?", (sub_id,))
                
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"删除子任务 {sub_id} 成功")
                return success
                
        except Exception as e:
            logger.error(f"删除子任务 {sub_id} 失败: {e}")
            return False
    
    def reorder_sub_todos(self, parent_id: int, sub_ids: List[int]) -> bool:
        """
        批量更新子任务排序
        
        Args:
            parent_id: 父任务 ID
            sub_ids: 子任务 ID 列表（按新顺序排列）
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                for index, sub_id in enumerate(sub_ids):
                    cursor.execute(
                        "UPDATE sub_todo_list SET order_index = ? WHERE id = ? AND parent_id = ?",
                        (index, sub_id, parent_id)
                    )
                
                logger.info(f"重排序 {len(sub_ids)} 个子任务成功")
                return True
                
        except Exception as e:
            logger.error(f"重排序子任务失败: {e}")
            return False
    
    # ==================== Daily Focus 操作 ====================
    
    def get_daily_focus(self, date: str) -> Optional[Dict[str, Any]]:
        """
        获取指定日期的焦点内容
        
        Args:
            date: 日期（YYYY-MM-DD 格式）
        
        Returns:
            Optional[Dict]: 焦点数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM daily_focus WHERE date = ?", (date,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取日焦点失败: {e}")
            return None
    
    def upsert_daily_focus(self, date: str, content: str) -> bool:
        """
        创建或更新日焦点（INSERT OR REPLACE）
        
        Args:
            date: 日期（YYYY-MM-DD 格式）
            content: 焦点内容
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO daily_focus (date, content) VALUES (?, ?)
                       ON CONFLICT(date) DO UPDATE SET content = excluded.content""",
                    (date, content)
                )
                logger.info(f"更新日焦点成功: {date}")
                return True
                
        except Exception as e:
            logger.error(f"更新日焦点失败: {e}")
            return False
    
    def get_daily_focuses_in_range(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取日期范围内的所有日焦点
        
        Args:
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
        
        Returns:
            List[Dict]: 日焦点列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM daily_focus WHERE date >= ? AND date <= ? ORDER BY date ASC",
                    (start_date, end_date)
                )
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取日焦点范围失败: {e}")
            return []
    
    # ==================== Weekly Focus 操作 ====================
    
    def get_weekly_focus(
        self, 
        year: int, 
        month: int, 
        week_num: int
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定周的焦点内容
        
        Args:
            year: 年份
            month: 月份（1-12）
            week_num: 周序号（1-4）
        
        Returns:
            Optional[Dict]: 焦点数据，不存在返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM weekly_focus WHERE year = ? AND month = ? AND week_num = ?",
                    (year, month, week_num)
                )
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"获取周焦点失败: {e}")
            return None
    
    def upsert_weekly_focus(
        self, 
        year: int, 
        month: int, 
        week_num: int, 
        content: str
    ) -> bool:
        """
        创建或更新周焦点
        
        Args:
            year: 年份
            month: 月份（1-12）
            week_num: 周序号（1-4）
            content: 焦点内容
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO weekly_focus (year, month, week_num, content) VALUES (?, ?, ?, ?)
                       ON CONFLICT(year, month, week_num) DO UPDATE SET content = excluded.content""",
                    (year, month, week_num, content)
                )
                logger.info(f"更新周焦点成功: {year}-{month} W{week_num}")
                return True
                
        except Exception as e:
            logger.error(f"更新周焦点失败: {e}")
            return False
    
    def get_weekly_focuses_in_month(
        self, 
        year: int, 
        month: int
    ) -> List[Dict[str, Any]]:
        """
        获取指定月份所有周的焦点
        
        Args:
            year: 年份
            month: 月份（1-12）
        
        Returns:
            List[Dict]: 周焦点列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM weekly_focus WHERE year = ? AND month = ? ORDER BY week_num ASC",
                    (year, month)
                )
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取月份周焦点失败: {e}")
            return []


# 创建全局单例
todo_provider = TodoProvider()

