# """
# Plan Doc 数据提供者
# 提供 Plan Doc 计划书的数据库操作
# """
# from typing import Optional, List, Dict, Any

# from lifeprism.repository import LWBaseDataProvider
# from lifeprism.utils import get_logger, LazySingleton

# logger = get_logger(__name__)


# class PlanDocProvider(LWBaseDataProvider):
#     """
#     计划书数据提供者

#     继承 LWBaseDataProvider，提供 Plan Doc 的 CRUD 操作
#     """

#     def __init__(self, db_manager=None):
#         super().__init__(db_manager)

#     def get_all_plan_docs(self) -> List[Dict[str, Any]]:
#         """
#         获取所有计划书

#         Returns:
#             List[Dict]: 计划书列表，按排序索引升序排列
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     """
#                     SELECT * FROM plan_doc
#                     ORDER BY order_index ASC, created_at DESC
#                     """
#                 )

#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()

#                 return [dict(zip(columns, row)) for row in rows]

#         except Exception as e:
#             logger.error("获取所有计划书失败: error=%s", e)
#             return []

#     def get_plan_docs_by_goal(self, goal_id: str) -> List[Dict[str, Any]]:
#         """
#         获取指定目标的所有计划书

#         Args:
#             goal_id: 目标 ID

#         Returns:
#             List[Dict]: 计划书列表，按排序索引升序排列
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     """
#                     SELECT * FROM plan_doc
#                     WHERE goal_id = ?
#                     ORDER BY order_index ASC, created_at DESC
#                     """,
#                     (goal_id,)
#                 )

#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()

#                 return [dict(zip(columns, row)) for row in rows]

#         except Exception as e:
#             logger.error("获取目标 %s 的计划书失败: error=%s", goal_id, e)
#             return []

#     def get_plan_doc_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
#         """
#         按 ID 获取单个计划书

#         Args:
#             doc_id: 计划书 ID (格式: plandoc-xxx)

#         Returns:
#             Optional[Dict]: 计划书数据，不存在返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT * FROM plan_doc WHERE id = ?", (doc_id,))

#                 row = cursor.fetchone()
#                 if row:
#                     columns = [description[0] for description in cursor.description]
#                     return dict(zip(columns, row))
#                 return None

#         except Exception as e:
#             logger.error("获取计划书 %s 失败: error=%s", doc_id, e)
#             return None

#     def create_plan_doc(self, data: Dict[str, Any]) -> Optional[str]:
#         """
#         创建新计划书

#         Args:
#             data: 计划书数据，title 将作为 id 使用

#         Returns:
#             Optional[str]: 新计划书 ID (即 title)，失败返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()

#                 # 使用 id 
#                 doc_id = data.get('id', '')
#                 if not doc_id:
#                     logger.error("创建计划书失败: id 不能为空")
#                     return None

#                 # 获取当前目标下最大 order_index
#                 cursor.execute(
#                     "SELECT COALESCE(MAX(order_index), -1) + 1 FROM plan_doc WHERE goal_id = ?",
#                     (data.get('goal_id'),)
#                 )
#                 next_order = cursor.fetchone()[0]

#                 # 构建插入数据（content 存储在文件系统中，不存数据库）
#                 columns = [
#                     'id', 'goal_id', 'status', 'order_index'
#                 ]
#                 values = [
#                     doc_id,
#                     data.get('goal_id'),
#                     data.get('status', 'active'),
#                     next_order
#                 ]

#                 placeholders = ', '.join(['?' for _ in columns])
#                 columns_str = ', '.join(columns)

#                 cursor.execute(
#                     f"INSERT INTO plan_doc ({columns_str}) VALUES ({placeholders})",
#                     values
#                 )

#                 logger.info("创建计划书成功，ID: %s", doc_id)
#                 return doc_id

#         except Exception as e:
#             logger.error("创建计划书失败: error=%s", e)
#             return None

#     def update_plan_doc(self, doc_id: str, data: Dict[str, Any]) -> bool:
#         """
#         更新计划书

#         Args:
#             doc_id: 计划书 ID (格式: plandoc-xxx)
#             data: 要更新的字段

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             if not data:
#                 return True

#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()

#                 # 允许更新的字段（content 存储在文件系统中，不在数据库更新）
#                 allowed_fields = [
#                     'status', 'order_index'
#                 ]

#                 set_clauses = []
#                 values = []
#                 for key, value in data.items():
#                     if key in allowed_fields:
#                         set_clauses.append(f"{key} = ?")
#                         values.append(value)

#                 if not set_clauses:
#                     return True

#                 # 添加 updated_at
#                 set_clauses.append("updated_at = datetime('now')")

#                 values.append(doc_id)
#                 sql = f"UPDATE plan_doc SET {', '.join(set_clauses)} WHERE id = ?"

#                 cursor.execute(sql, values)
#                 success = cursor.rowcount > 0

#                 if success:
#                     logger.info("更新计划书 %s 成功", doc_id)
#                 return success

#         except Exception as e:
#             logger.error("更新计划书 %s 失败: error=%s", doc_id, e)
#             return False

#     def delete_plan_doc(self, doc_id: str) -> bool:
#         """
#         删除计划书

#         Args:
#             doc_id: 计划书 ID (格式: plandoc-xxx)

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("DELETE FROM plan_doc WHERE id = ?", (doc_id,))

#                 success = cursor.rowcount > 0
#                 if success:
#                     logger.info("删除计划书 %s 成功", doc_id)
#                 return success

#         except Exception as e:
#             logger.error("删除计划书 %s 失败: error=%s", doc_id, e)
#             return False

#     def rename_plan_doc(self, old_id: str, new_id: str) -> bool:
#         """
#         重命名计划书（修改 ID 并级联更新关联表）

#         Args:
#             old_id: 旧 ID
#             new_id: 新 ID

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
                
#                 #开启事务 (SQLite context manager does this, but being explicit helps readability)
                
#                 # 1. 更新 plan_doc 表的主键 ID 
#                 cursor.execute(
#                     "UPDATE plan_doc SET id = ?, updated_at = datetime('now') WHERE id = ?",
#                     (new_id, old_id)
#                 )
                
#                 if cursor.rowcount == 0:
#                     logger.warning("重命名失败: 计划书 %s 不存在", old_id)
#                     return False
                
#                 # 2. 级联更新 todo_list 表 (Task Pool) 中的引用
#                 # todo_list 表中有 plan_doc_id 字段
#                 cursor.execute(
#                     "UPDATE todo_list SET plan_doc_id = ? WHERE plan_doc_id = ?",
#                     (new_id, old_id)
#                 )
                
#                 logger.info("重命名计划书成功: %s -> %s, 关联任务更新数: %s", old_id, new_id, cursor.rowcount)
#                 return True

#         except Exception as e:
#             logger.error("重命名计划书 %s -> %s 失败: error=%s", old_id, new_id, e)
#             return False


# # 创建全局单例
# plan_doc_provider = LazySingleton(PlanDocProvider)
