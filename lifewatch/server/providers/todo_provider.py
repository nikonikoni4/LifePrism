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
                       OR (cross_day = 1 AND completed = 0 AND date < ?)
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
                columns = ['order_index', 'content', 'color', 'completed', 
                          'link_to_goal', 'date', 'expected_finished_at', 
                          'actual_finished_at', 'cross_day']
                values = [
                    next_order,
                    data.get('content'),
                    data.get('color', '#FFFFFF'),
                    0,  # completed
                    data.get('link_to_goal'),
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
                    if key in ['content', 'color', 'completed', 'link_to_goal',
                              'expected_finished_at', 'actual_finished_at', 'cross_day']:
                        set_clauses.append(f"{key} = ?")
                        # 处理布尔值
                        if key in ['completed', 'cross_day']:
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


# 创建全局单例
todo_provider = TodoProvider()
