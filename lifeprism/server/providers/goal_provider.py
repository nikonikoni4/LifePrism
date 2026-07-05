# """
# Goal 数据提供者
# 提供 Goal 目标的数据库操作
# """
# from typing import Optional, List, Dict, Any
# from datetime import datetime
# import uuid

# from lifeprism.repository import LWBaseDataProvider
# from lifeprism.utils import get_logger, LazySingleton

# logger = get_logger(__name__)


# class GoalProvider(LWBaseDataProvider):
#     """
#     目标数据提供者
    
#     继承 LWBaseDataProvider，提供 Goal 的 CRUD 操作
#     """
    
#     def __init__(self, db_manager=None):
#         super().__init__(db_manager)
    
#     # ==================== Goal 操作 ====================
    
#     def get_goals(
#         self,
#         status: Optional[str] = None,
#         category_id: Optional[str] = None,
#         page: int = 1,
#         page_size: int = 20
#     ) -> tuple[List[Dict[str, Any]], int]:
#         """
#         获取目标列表
        
#         Args:
#             status: 按状态筛选（active, completed, archived）
#             category_id: 按分类筛选
#             page: 页码（从1开始）
#             page_size: 每页数量
        
#         Returns:
#             tuple: (目标列表, 总数)
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # 构建查询条件
#                 conditions = []
#                 params = []
                
#                 if status:
#                     conditions.append("status = ?")
#                     params.append(status)
                
#                 if category_id:
#                     conditions.append("link_to_category_id = ?")
#                     params.append(category_id)
                
#                 where_clause = ""
#                 if conditions:
#                     where_clause = "WHERE " + " AND ".join(conditions)
                
#                 # 先获取总数
#                 count_sql = f"SELECT COUNT(*) FROM goal {where_clause}"
#                 cursor.execute(count_sql, params)
#                 total = cursor.fetchone()[0]
                
#                 # 获取分页数据
#                 offset = (page - 1) * page_size
#                 sql = f"""
#                 SELECT * FROM goal 
#                 {where_clause}
#                 ORDER BY order_index ASC, created_at DESC
#                 LIMIT ? OFFSET ?
#                 """
#                 cursor.execute(sql, params + [page_size, offset])
                
#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()
                
#                 items = [dict(zip(columns, row)) for row in rows]
#                 return items, total
                
#         except Exception as e:
#             logger.error("获取目标列表失败: error=%s", e)
#             return [], 0
    
#     def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
#         """
#         按 ID 获取单个目标
        
#         Args:
#             goal_id: 目标 ID (格式: goal-xxx)
        
#         Returns:
#             Optional[Dict]: 目标数据，不存在返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT * FROM goal WHERE id = ?", (goal_id,))
                
#                 row = cursor.fetchone()
#                 if row:
#                     columns = [description[0] for description in cursor.description]
#                     return dict(zip(columns, row))
#                 return None
                
#         except Exception as e:
#             logger.error("获取目标 %s 失败: error=%s", goal_id, e)
#             return None
    
#     def create_goal(self, data: Dict[str, Any]) -> Optional[str]:
#         """
#         创建新目标
        
#         Args:
#             data: 目标数据
        
#         Returns:
#             Optional[str]: 新目标 ID (格式: goal-xxx)，失败返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # 生成唯一 ID（与 category 格式一致）
#                 goal_id = f"goal-{str(uuid.uuid4())[:8]}"
                
#                 # 获取当前最大 order_index
#                 cursor.execute("SELECT COALESCE(MAX(order_index), -1) + 1 FROM goal")
#                 next_order = cursor.fetchone()[0]
                
#                 # 构建插入数据
#                 columns = [
#                     'id', 'name', 'content', 'color',
#                     'link_to_category_id', 'link_to_sub_category_id',
#                     'start_date', 'expected_finished_at',
#                     'value', 'commitment', 'time_unit', 'time_invested',
#                     'track_time_automatically', 'milestones',
#                     'status', 'order_index'
#                 ]
#                 values = [
#                     goal_id,
#                     data.get('name'),
#                     data.get('content', ''),
#                     data.get('color', '#5B8FF9'),
#                     data.get('link_to_category_id'),
#                     data.get('link_to_sub_category_id'),
#                     data.get('start_date'),
#                     data.get('expected_finished_at'),
#                     data.get('value'),
#                     data.get('commitment'),
#                     data.get('time_unit', 'HRS'),
#                     data.get('time_invested', 0),
#                     1 if data.get('track_time_automatically', True) else 0,
#                     data.get('milestones', '[]'),
#                     data.get('status', 'active'),
#                     next_order
#                 ]
                
#                 placeholders = ', '.join(['?' for _ in columns])
#                 columns_str = ', '.join(columns)
                
#                 cursor.execute(
#                     f"INSERT INTO goal ({columns_str}) VALUES ({placeholders})",
#                     values
#                 )
                
#                 logger.info("创建目标成功，ID: %s", goal_id)
#                 return goal_id
                
#         except Exception as e:
#             logger.error("创建目标失败: error=%s", e)
#             return None
    
#     def update_goal(self, goal_id: str, data: Dict[str, Any]) -> bool:
#         """
#         更新目标
        
#         Args:
#             goal_id: 目标 ID (格式: goal-xxx)
#             data: 要更新的字段
        
#         Returns:
#             bool: 是否成功
#         """
#         try:
#             if not data:
#                 return True
            
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # 允许更新的字段
#                 allowed_fields = [
#                     'name', 'content', 'color',
#                     'link_to_category_id', 'link_to_sub_category_id',
#                     'start_date', 'expected_finished_at',
#                     'value', 'commitment', 'time_unit', 'time_invested',
#                     'track_time_automatically', 'milestones',
#                     'status', 'order_index', 'time_invested_updated_at'
#                 ]
                
#                 set_clauses = []
#                 values = []
#                 for key, value in data.items():
#                     if key in allowed_fields:
#                         set_clauses.append(f"{key} = ?")
#                         values.append(value)
                
#                 if not set_clauses:
#                     return True
                
#                 values.append(goal_id)
#                 sql = f"UPDATE goal SET {', '.join(set_clauses)} WHERE id = ?"
                
#                 cursor.execute(sql, values)
#                 success = cursor.rowcount > 0
                
#                 if success:
#                     logger.info("更新目标 %s 成功", goal_id)
#                 return success
                
#         except Exception as e:
#             logger.error("更新目标 %s 失败: error=%s", goal_id, e)
#             return False
    
#     def delete_goal(self, goal_id: str) -> bool:
#         """
#         删除目标
        
#         Args:
#             goal_id: 目标 ID (格式: goal-xxx)
        
#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 # 先清除 todo_list 中关联的目标
#                 cursor.execute(
#                     "UPDATE todo_list SET link_to_goal_id = NULL WHERE link_to_goal_id = ?",
#                     (goal_id,)
#                 )
#                 cleared_count = cursor.rowcount
#                 if cleared_count > 0:
#                     logger.info("清除了 %s 个任务的目标关联", cleared_count)
                
#                 # 然后删除目标
#                 cursor.execute("DELETE FROM goal WHERE id = ?", (goal_id,))
                
#                 success = cursor.rowcount > 0
#                 if success:
#                     logger.info("删除目标 %s 成功", goal_id)
#                 return success
                
#         except Exception as e:
#             logger.error("删除目标 %s 失败: error=%s", goal_id, e)
#             return False
    
#     def reorder_goals(self, goal_ids: List[str]) -> bool:
#         """
#         批量更新目标排序
        
#         Args:
#             goal_ids: 目标 ID 列表（按新顺序排列）
        
#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 for index, goal_id in enumerate(goal_ids):
#                     cursor.execute(
#                         "UPDATE goal SET order_index = ? WHERE id = ?",
#                         (index, goal_id)
#                     )
                
#                 logger.info("重排序 %s 个目标成功", len(goal_ids))
#                 return True
                
#         except Exception as e:
#             logger.error("重排序目标失败: error=%s", e)
#             return False
    
#     def get_active_goals(self) -> List[Dict[str, Any]]:
#         """
#         获取所有进行中的目标（用于前端选择绑定）
        
#         Returns:
#             List[Dict]: 目标列表，包含 id 和 name
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     "SELECT id, name FROM goal WHERE status = 'active' ORDER BY order_index ASC"
#                 )
                
#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()
                
#                 return [dict(zip(columns, row)) for row in rows]
                
#         except Exception as e:
#             logger.error("获取活跃目标列表失败: error=%s", e)
#             return []
    
#     def get_active_goals_with_category(self) -> List[Dict[str, Any]]:
#         """
#         获取所有绑定了分类的进行中目标（用于 Map Cache 编辑界面）
        
#         只返回 link_to_category_id 不为空的目标
        
#         Returns:
#             List[Dict]: 目标列表，包含 id, name, link_to_category_id, link_to_sub_category_id
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("""
#                     SELECT id, name, link_to_category_id, link_to_sub_category_id 
#                     FROM goal 
#                     WHERE status = 'active' AND link_to_category_id IS NOT NULL
#                     ORDER BY order_index ASC
#                 """)
                
#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()
                
#                 return [dict(zip(columns, row)) for row in rows]
                
#         except Exception as e:
#             logger.error("获取绑定分类的活跃目标列表失败: error=%s", e)
#             return []
    
#     def get_goals_linked_to_category(self, category_id: str) -> List[Dict[str, Any]]:
#         """
#         获取关联到特定分类的所有目标
        
#         Args:
#             category_id: 分类 ID
        
#         Returns:
#             List[Dict]: 目标列表
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     "SELECT * FROM goal WHERE link_to_category_id = ? ORDER BY order_index ASC",
#                     (category_id,)
#                 )
                
#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()
                
#                 return [dict(zip(columns, row)) for row in rows]
                
#         except Exception as e:
#             logger.error("获取分类关联目标失败: error=%s", e)
#             return []

#     def get_active_goals_for_classify(self) -> List[Dict[str, Any]]:
#         """
#         获取所有活跃目标（用于 LLM 分类时的名称-ID映射）

#         只返回满足以下条件的目标：
#         1. 目标状态为 active
#         2. 目标开启了自动时间追踪（track_time_automatically == 1）
#         3. 目标必须绑定了主分类（link_to_category_id IS NOT NULL）
#         4. 关联的主分类未被禁用（category.state != 0）
#         5. 关联的子分类未被禁用（sub_category.state != 0 或未关联子分类）

#         Returns:
#             List[Dict]: 包含 id, name, link_to_category_id, link_to_sub_category_id 的目标列表
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("""
#                     SELECT g.id, g.name, g.link_to_category_id, g.link_to_sub_category_id
#                     FROM goal g
#                     INNER JOIN category c ON g.link_to_category_id = c.id
#                     LEFT JOIN sub_category sc ON g.link_to_sub_category_id = sc.id
#                     WHERE g.status = 'active'
#                       AND g.track_time_automatically = 1
#                       AND g.link_to_category_id IS NOT NULL
#                       AND c.state != 0
#                       AND (sc.state IS NULL OR sc.state != 0)
#                     ORDER BY g.order_index ASC
#                 """)

#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()

#                 return [dict(zip(columns, row)) for row in rows]

#         except Exception as e:
#             logger.error("获取活跃目标列表（用于分类）失败: error=%s", e)
#             return []

#     def calculate_time_invested(self, goal_id: str) -> int:
#         """
#         从 user_app_behavior_log 计算目标的总投入时间

#         Args:
#             goal_id: 目标 ID

#         Returns:
#             int: 总投入时间（秒）
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("""
#                     SELECT COALESCE(SUM(duration), 0) as total_seconds
#                     FROM user_app_behavior_log
#                     WHERE link_to_goal_id = ?
#                 """, (goal_id,))

#                 result = cursor.fetchone()
#                 total_seconds = int(result[0]) if result and result[0] else 0
#                 return total_seconds

#         except Exception as e:
#             logger.error("计算目标 %s 投入时间失败: error=%s", goal_id, e)
#             return 0

#     def update_time_invested(self, goal_id: str, time_invested: int) -> bool:
#         """
#         更新目标的投入时间和更新时间戳

#         Args:
#             goal_id: 目标 ID
#             time_invested: 投入时间（秒）

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#                 cursor.execute("""
#                     UPDATE goal
#                     SET time_invested = ?, time_invested_updated_at = ?
#                     WHERE id = ?
#                 """, (time_invested, now, goal_id))

#                 success = cursor.rowcount > 0
#                 if success:
#                     logger.debug("更新目标 %s 投入时间: %s 分钟", goal_id, time_invested)
#                 return success

#         except Exception as e:
#             logger.error("更新目标 %s 投入时间失败: error=%s", goal_id, e)
#             return False


# # 创建全局单例
# goal_provider = LazySingleton(GoalProvider)

