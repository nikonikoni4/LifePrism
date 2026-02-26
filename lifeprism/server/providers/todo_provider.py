"""
Todo 数据提供者
提供 TodoList 的数据库操作（支持多层级 parent_id 关系）
"""
from typing import Optional, List, Dict, Any
import uuid

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import get_logger, LazySingleton

logger = get_logger(__name__)


def generate_todo_id() -> str:
    """生成 todo ID，格式：t-{uuid[:8]}"""
    return f"t-{uuid.uuid4().hex[:8]}"


class TodoProvider(LWBaseDataProvider):
    """
    Todo 数据提供者

    继承 LWBaseDataProvider，提供 TodoList 的 CRUD 操作（支持多层级 parent_id 关系）
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
    
    def get_todo_by_id(self, todo_id: str) -> Optional[Dict[str, Any]]:
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
    
    def create_todo(self, data: Dict[str, Any]) -> Optional[str]:
        """
        创建新任务

        Args:
            data: 任务数据（可包含 'id'，未提供则自动生成）

        Returns:
            Optional[str]: 新任务 ID，失败返回 None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 插入前生成 ID（如果未提供）
                todo_id = data.get('id') or generate_todo_id()

                # 获取当前最大 order_index
                cursor.execute(
                    "SELECT COALESCE(MAX(order_index), -1) + 1 FROM todo_list WHERE date = ?",
                    (data.get('date'),)
                )
                next_order = cursor.fetchone()[0]

                columns = ['id', 'order_index', 'pool_order_index', 'content', 'color', 'state',
                          'link_to_goal_id', 'date', 'expected_finished_at',
                          'actual_finished_at', 'cross_day', 'folder_id',
                          'parent_id', 'plan_doc_id',
                          'delay_days', 'delay_reason']
                values = [
                    todo_id,
                    next_order,
                    data.get('pool_order_index'),
                    data.get('content'),
                    data.get('color', '#FFFFFF'),
                    data.get('state', 'pool'),
                    data.get('link_to_goal_id'),
                    data.get('date'),
                    data.get('expected_finished_at'),
                    data.get('actual_finished_at'),
                    1 if data.get('cross_day') else 0,
                    data.get('folder_id'),
                    data.get('parent_id'),
                    data.get('plan_doc_id'),
                    data.get('delay_days'),
                    data.get('delay_reason')
                ]

                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join(columns)

                cursor.execute(
                    f"INSERT INTO todo_list ({columns_str}) VALUES ({placeholders})",
                    values
                )

                logger.info(f"创建任务成功，ID: {todo_id}")
                return todo_id
                
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            return None
    
    def update_todo(self, todo_id: str, data: Dict[str, Any]) -> bool:
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
                allowed_fields = [
                    'content', 'color', 'state', 'link_to_goal_id',
                    'date', 'expected_finished_at', 'actual_finished_at',
                    'cross_day', 'pool_order_index', 'folder_id',
                    'parent_id', 'plan_doc_id',
                    'delay_days', 'delay_reason', 'waid_order'
                ]
                for key, value in data.items():
                    if key in allowed_fields:
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
    
    def delete_todo(self, todo_id: str) -> bool:
        """
        删除任务

        Args:
            todo_id: 任务 ID

        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM todo_list WHERE id = ?", (todo_id,))

                success = cursor.rowcount > 0
                if success:
                    logger.info(f"删除任务 {todo_id} 成功")
                return success

        except Exception as e:
            logger.error(f"删除任务 {todo_id} 失败: {e}")
            return False

    def delete_todo_cascade(self, todo_id: str) -> int:
        """
        级联删除任务及其所有子任务（todo_list 中的 parent_id 关系）

        Args:
            todo_id: 任务 ID

        Returns:
            int: 删除的总任务数（包括子任务）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 递归获取所有子任务 ID
                def get_all_descendant_ids(parent_id: str) -> List[str]:
                    cursor.execute(
                        "SELECT id FROM todo_list WHERE parent_id = ?",
                        (parent_id,)
                    )
                    child_ids = [row[0] for row in cursor.fetchall()]
                    all_ids = list(child_ids)
                    for child_id in child_ids:
                        all_ids.extend(get_all_descendant_ids(child_id))
                    return all_ids

                # 获取所有要删除的 ID（包括自身）
                all_ids = get_all_descendant_ids(todo_id)
                all_ids.append(todo_id)

                # 从叶子节点开始删除（反向顺序）
                deleted_count = 0
                for tid in reversed(all_ids):
                    cursor.execute("DELETE FROM todo_list WHERE id = ?", (tid,))
                    if cursor.rowcount > 0:
                        deleted_count += 1

                logger.info(f"级联删除任务 {todo_id} 成功，共删除 {deleted_count} 个任务")
                return deleted_count

        except Exception as e:
            logger.error(f"级联删除任务 {todo_id} 失败: {e}")
            return 0

    def get_child_todos(self, parent_id: str) -> List[Dict[str, Any]]:
        """
        获取直接子任务列表

        Args:
            parent_id: 父任务 ID

        Returns:
            List[Dict]: 子任务列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM todo_list WHERE parent_id = ? ORDER BY pool_order_index ASC",
                    (parent_id,)
                )

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"获取子任务列表失败 (parent_id={parent_id}): {e}")
            return []

    def batch_delete_todos(self, todo_ids: List[str]) -> int:
        """
        批量删除任务（不级联删除子任务）

        Args:
            todo_ids: 任务 ID 列表

        Returns:
            int: 成功删除的数量
        """
        if not todo_ids:
            return 0

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                deleted_count = 0
                for todo_id in todo_ids:
                    cursor.execute("DELETE FROM todo_list WHERE id = ?", (todo_id,))
                    if cursor.rowcount > 0:
                        deleted_count += 1

                logger.info(f"批量删除 {deleted_count} 个任务成功")
                return deleted_count

        except Exception as e:
            logger.error(f"批量删除任务失败: {e}")
            return 0
    
    def reorder_todos(self, todo_ids: List[str]) -> bool:
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
    
    def reorder_pool_todos(self, todo_ids: List[str]) -> bool:
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
    
    def move_todo_to_folder(self, todo_id: str, folder_id: Optional[int]) -> bool:
        """
        移动任务到指定文件夹
        
        Args:
            todo_id: 任务 ID
            folder_id: 目标文件夹 ID（None 表示移到根级别）
        
        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE todo_list SET folder_id = ? WHERE id = ?",
                    (folder_id, todo_id)
                )
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"移动任务 {todo_id} 到文件夹 {folder_id}")
                return success
        except Exception as e:
            logger.error(f"移动任务失败: {e}")
            return False


    # ==================== 任务池查询 ====================
    
    def get_todos_for_taskpool(
        self,
        goal_id: Optional[str] = None,
        plan_doc_id: Optional[str] = None,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取任务池任务（支持筛选）
        
        Args:
            goal_id: 按目标筛选
            plan_doc_id: 按计划书筛选
            state: 按状态筛选（pool/scheduled/completed/all）
        
        Returns:
            List[Dict]: 任务列表（扁平结构，前端通过 parent_id 构建树）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                conditions = []
                params = []
                
                if state and state != 'all':
                    conditions.append("state = ?")
                    params.append(state)
                
                if goal_id:
                    conditions.append("link_to_goal_id = ?")
                    params.append(goal_id)
                
                if plan_doc_id:
                    conditions.append("plan_doc_id = ?")
                    params.append(plan_doc_id)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                sql = f"""
                SELECT * FROM todo_list 
                WHERE {where_clause}
                ORDER BY pool_order_index ASC, id ASC
                """
                
                cursor.execute(sql, params)
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取任务池任务失败: {e}")
            return []
    
    def get_todos_by_plan_doc(self, plan_doc_id: str) -> List[Dict[str, Any]]:
        """
        获取指定计划书关联的所有任务
        
        Args:
            plan_doc_id: 计划书 ID
        
        Returns:
            List[Dict]: 任务列表
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM todo_list WHERE plan_doc_id = ? ORDER BY pool_order_index ASC",
                    (plan_doc_id,)
                )
                
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"获取计划书任务失败 (plan_doc={plan_doc_id}): {e}")
            return []
    
    def batch_create_todos(self, todos: List[Dict[str, Any]]) -> List[str]:
        """
        批量创建任务

        Args:
            todos: 任务数据列表（可包含 'id'，未提供则自动生成）

        Returns:
            List[str]: 新创建的任务 ID 列表
        """
        new_ids = []
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                for data in todos:
                    todo_id = data.get('id') or generate_todo_id()
                    columns = [
                        'id', 'order_index', 'pool_order_index', 'content', 'color', 'state',
                        'link_to_goal_id', 'date', 'expected_finished_at',
                        'actual_finished_at', 'cross_day',
                        'parent_id', 'plan_doc_id',
                        'delay_days', 'delay_reason'
                    ]
                    values = [
                        todo_id,
                        data.get('order_index', 0),
                        data.get('pool_order_index', 0),
                        data.get('content'),
                        data.get('color', '#FFFFFF'),
                        data.get('state', 'pool'),
                        data.get('link_to_goal_id'),
                        data.get('date'),
                        data.get('expected_finished_at'),
                        data.get('actual_finished_at'),
                        1 if data.get('cross_day') else 0,
                        data.get('parent_id'),
                        data.get('plan_doc_id'),
                        data.get('delay_days'),
                        data.get('delay_reason')
                    ]

                    placeholders = ', '.join(['?' for _ in columns])
                    columns_str = ', '.join(columns)

                    cursor.execute(
                        f"INSERT INTO todo_list ({columns_str}) VALUES ({placeholders})",
                        values
                    )
                    new_ids.append(todo_id)
                
                logger.info(f"批量创建 {len(new_ids)} 个任务成功")
                return new_ids
                
        except Exception as e:
            logger.error(f"批量创建任务失败: {e}")
            return new_ids
    
    def batch_update_todos(self, updates: List[Dict[str, Any]]) -> int:
        """
        批量更新任务
        
        Args:
            updates: 更新数据列表，每项必须包含 'id' 字段
        
        Returns:
            int: 成功更新的数量
        """
        updated_count = 0
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                allowed_fields = [
                    'content', 'color', 'state', 'link_to_goal_id',
                    'date', 'expected_finished_at', 'actual_finished_at',
                    'cross_day', 'pool_order_index', 'order_index',
                    'parent_id', 'plan_doc_id',
                    'delay_days', 'delay_reason', 'waid_order'
                ]
                
                for data in updates:
                    todo_id = data.get('id')
                    if not todo_id:
                        continue
                    
                    set_clauses = []
                    values = []
                    for key, value in data.items():
                        if key in allowed_fields:
                            set_clauses.append(f"{key} = ?")
                            if key == 'cross_day':
                                values.append(1 if value else 0)
                            else:
                                values.append(value)
                    
                    if not set_clauses:
                        continue
                    
                    values.append(todo_id)
                    sql = f"UPDATE todo_list SET {', '.join(set_clauses)} WHERE id = ?"
                    
                    cursor.execute(sql, values)
                    if cursor.rowcount > 0:
                        updated_count += 1
                
                logger.info(f"批量更新 {updated_count} 个任务成功")
                return updated_count

        except Exception as e:
            logger.error(f"批量更新任务失败: {e}")
            return updated_count

    # ==================== WAID 浮窗操作 ====================

    def get_waid_todos(self) -> List[Dict[str, Any]]:
        """获取所有 waid_order IS NOT NULL 的 todo，按 waid_order ASC 排序"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM todo_list WHERE waid_order IS NOT NULL ORDER BY waid_order ASC"
                )
                rows = cursor.fetchall()
                if not rows:
                    return []
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"获取 WAID todo 列表失败: {e}")
            return []

    def batch_update_waid_order(self, todo_ids: List[str]) -> bool:
        """批量设置 waid_order，按数组索引顺序赋值 0,1,2...

        Args:
            todo_ids: todo ID 列表，索引即为新的 waid_order 值

        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for idx, tid in enumerate(todo_ids):
                    cursor.execute(
                        "UPDATE todo_list SET waid_order = ? WHERE id = ?",
                        (idx, tid)
                    )
                logger.info(f"批量更新 WAID 排序成功，共 {len(todo_ids)} 个")
                return True
        except Exception as e:
            logger.error(f"批量更新 WAID 排序失败: {e}")
            return False

    def clear_waid_order(self, todo_id: str) -> bool:
        """将指定 todo 的 waid_order 设为 NULL（从浮窗移除）

        Args:
            todo_id: 任务 ID

        Returns:
            bool: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE todo_list SET waid_order = NULL WHERE id = ?",
                    (todo_id,)
                )
                success = cursor.rowcount > 0
                if success:
                    logger.info(f"清除 todo {todo_id} 的 WAID 排序")
                return success
        except Exception as e:
            logger.error(f"清除 WAID 排序失败: {e}")
            return False


# 创建全局单例
todo_provider = LazySingleton(TodoProvider)

