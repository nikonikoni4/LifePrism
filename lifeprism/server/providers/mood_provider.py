# """
# Mood 数据提供者
# 提供 mood_types / mood_entries / mood_impacts 三张表的数据库操作
# """
# import uuid
# from typing import Optional, List, Dict, Any

# from lifeprism.storage import LWBaseDataProvider
# from lifeprism.utils import get_logger, LazySingleton

# logger = get_logger(__name__)


# class MoodProvider(LWBaseDataProvider):
#     """
#     心情模块数据提供者

#     继承 LWBaseDataProvider，提供 mood_types / mood_entries / mood_impacts 的 CRUD 操作。
#     """

#     def __init__(self, db_manager=None):
#         super().__init__(db_manager)

#     # ==================== mood_types ====================

#     def get_mood_types(self) -> List[Dict[str, Any]]:
#         """
#         获取所有心情类型（按 sort_order DESC 排序）

#         Returns:
#             List[Dict]: 心情类型列表
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT * FROM mood_types ORDER BY sort_order DESC")
#                 columns = [desc[0] for desc in cursor.description]
#                 return [dict(zip(columns, row)) for row in cursor.fetchall()]
#         except Exception as e:
#             logger.error(f"获取心情类型列表失败: {e}")
#             return []

#     def get_mood_type_by_id(self, mood_type_id: str) -> Optional[Dict[str, Any]]:
#         """
#         按 ID 获取心情类型

#         Args:
#             mood_type_id: 心情类型 ID

#         Returns:
#             Optional[Dict]: 心情类型，不存在返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT * FROM mood_types WHERE id = ?", (mood_type_id,))
#                 row = cursor.fetchone()
#                 if row:
#                     columns = [desc[0] for desc in cursor.description]
#                     return dict(zip(columns, row))
#                 return None
#         except Exception as e:
#             logger.error(f"获取心情类型 {mood_type_id} 失败: {e}")
#             return None

#     def create_mood_type(self, data: Dict[str, Any]) -> Optional[str]:
#         """
#         创建心情类型

#         Args:
#             data: 心情类型数据

#         Returns:
#             Optional[str]: 新创建的 ID，失败返回 None
#         """
#         try:
#             new_id = f"mood-type-{str(uuid.uuid4())[:8]}"
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("""
#                     INSERT INTO mood_types (id, name, icon, color, score, is_dark, sort_order)
#                     VALUES (?, ?, ?, ?, ?, ?, ?)
#                 """, (new_id, data['name'], data['icon'], data['color'],
#                       data['score'], data.get('is_dark', 0), data.get('sort_order', 0)))
#             logger.info(f"创建心情类型成功: {new_id}")
#             return new_id
#         except Exception as e:
#             logger.error(f"创建心情类型失败: {e}")
#             return None

#     def update_mood_type(self, mood_type_id: str, data: Dict[str, Any]) -> bool:
#         """
#         更新心情类型

#         Args:
#             mood_type_id: 心情类型 ID
#             data: 要更新的字段

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             if not data:
#                 return True
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 allowed_fields = ['name', 'icon', 'color', 'score', 'is_dark', 'sort_order']
#                 set_clauses = []
#                 values = []
#                 for key, value in data.items():
#                     if key in allowed_fields:
#                         set_clauses.append(f"{key} = ?")
#                         values.append(value)
#                 if not set_clauses:
#                     return True
#                 values.append(mood_type_id)
#                 sql = f"UPDATE mood_types SET {', '.join(set_clauses)} WHERE id = ?"
#                 cursor.execute(sql, values)
#                 return cursor.rowcount > 0
#         except Exception as e:
#             logger.error(f"更新心情类型 {mood_type_id} 失败: {e}")
#             return False

#     def delete_mood_type(self, mood_type_id: str) -> bool:
#         """
#         删除心情类型

#         Args:
#             mood_type_id: 心情类型 ID

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("DELETE FROM mood_types WHERE id = ?", (mood_type_id,))
#                 return cursor.rowcount > 0
#         except Exception as e:
#             logger.error(f"删除心情类型 {mood_type_id} 失败: {e}")
#             return False

#     def count_entries_by_type(self, mood_type_id: str) -> int:
#         """
#         统计某心情类型关联的记录数

#         Args:
#             mood_type_id: 心情类型 ID

#         Returns:
#             int: 记录数，查询失败返回 -1
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT COUNT(*) FROM mood_entries WHERE mood_type_id = ?", (mood_type_id,))
#                 return cursor.fetchone()[0]
#         except Exception as e:
#             logger.error(f"统计心情类型 {mood_type_id} 关联记录数失败: {e}")
#             return -1

#     # ==================== mood_entries ====================

#     def get_mood_entries(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
#         """
#         获取心情记录列表（按 created_at ASC 排序）

#         Args:
#             start_date: 开始日期 YYYY-MM-DD（可选）
#             end_date: 结束日期 YYYY-MM-DD（可选）

#         Returns:
#             List[Dict]: 心情记录列表
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 conditions = []
#                 params = []
#                 if start_date:
#                     conditions.append("date(created_at) >= ?")
#                     params.append(start_date)
#                 if end_date:
#                     conditions.append("date(created_at) <= ?")
#                     params.append(end_date)
#                 where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
#                 cursor.execute(f"SELECT * FROM mood_entries{where} ORDER BY created_at ASC", params)
#                 columns = [desc[0] for desc in cursor.description]
#                 return [dict(zip(columns, row)) for row in cursor.fetchall()]
#         except Exception as e:
#             logger.error(f"获取心情记录列表失败: {e}")
#             return []

#     def get_mood_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
#         """
#         按 ID 获取心情记录

#         Args:
#             entry_id: 心情记录 ID

#         Returns:
#             Optional[Dict]: 心情记录，不存在返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT * FROM mood_entries WHERE id = ?", (entry_id,))
#                 row = cursor.fetchone()
#                 if row:
#                     columns = [desc[0] for desc in cursor.description]
#                     return dict(zip(columns, row))
#                 return None
#         except Exception as e:
#             logger.error(f"获取心情记录 {entry_id} 失败: {e}")
#             return None

#     def create_mood_entry(self, data: Dict[str, Any]) -> Optional[str]:
#         """
#         创建心情记录

#         Args:
#             data: 心情记录数据（需包含 mood_type_id, score）

#         Returns:
#             Optional[str]: 新创建的 ID，失败返回 None
#         """
#         try:
#             new_id = f"mood-{str(uuid.uuid4())[:8]}"
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("""
#                     INSERT INTO mood_entries (id, mood_type_id, score, content, factors)
#                     VALUES (?, ?, ?, ?, ?)
#                 """, (new_id, data['mood_type_id'], data['score'],
#                       data.get('content'), data.get('factors')))
#             logger.info(f"创建心情记录成功: {new_id}")
#             return new_id
#         except Exception as e:
#             logger.error(f"创建心情记录失败: {e}")
#             return None

#     def update_mood_entry(self, entry_id: str, data: Dict[str, Any]) -> bool:
#         """
#         更新心情记录

#         Args:
#             entry_id: 心情记录 ID
#             data: 要更新的字段

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             if not data:
#                 return True
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 allowed_fields = ['mood_type_id', 'score', 'content', 'factors']
#                 set_clauses = []
#                 values = []
#                 for key, value in data.items():
#                     if key in allowed_fields:
#                         set_clauses.append(f"{key} = ?")
#                         values.append(value)
#                 if not set_clauses:
#                     return True
#                 values.append(entry_id)
#                 sql = f"UPDATE mood_entries SET {', '.join(set_clauses)} WHERE id = ?"
#                 cursor.execute(sql, values)
#                 return cursor.rowcount > 0
#         except Exception as e:
#             logger.error(f"更新心情记录 {entry_id} 失败: {e}")
#             return False

#     def delete_mood_entry(self, entry_id: str) -> bool:
#         """
#         删除心情记录

#         Args:
#             entry_id: 心情记录 ID

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("DELETE FROM mood_entries WHERE id = ?", (entry_id,))
#                 return cursor.rowcount > 0
#         except Exception as e:
#             logger.error(f"删除心情记录 {entry_id} 失败: {e}")
#             return False

#     # ==================== mood_impacts ====================

#     def get_mood_impacts(self) -> List[Dict[str, Any]]:
#         """
#         获取所有影响因素（按 sort_order DESC 排序）

#         Returns:
#             List[Dict]: 影响因素列表
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT * FROM mood_impacts ORDER BY sort_order DESC")
#                 columns = [desc[0] for desc in cursor.description]
#                 return [dict(zip(columns, row)) for row in cursor.fetchall()]
#         except Exception as e:
#             logger.error(f"获取影响因素列表失败: {e}")
#             return []

#     def create_mood_impact(self, data: Dict[str, Any]) -> Optional[int]:
#         """
#         创建影响因素

#         Args:
#             data: 影响因素数据（需包含 name）

#         Returns:
#             Optional[int]: 新创建的 ID，失败返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("""
#                     INSERT INTO mood_impacts (name, sort_order)
#                     VALUES (?, ?)
#                 """, (data['name'], data.get('sort_order', 0)))
#                 logger.info(f"创建影响因素成功: {data['name']}")
#                 return cursor.lastrowid
#         except Exception as e:
#             logger.error(f"创建影响因素失败: {e}")
#             return None

#     def delete_mood_impact(self, impact_id: int) -> bool:
#         """
#         删除影响因素

#         Args:
#             impact_id: 影响因素 ID

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("DELETE FROM mood_impacts WHERE id = ?", (impact_id,))
#                 return cursor.rowcount > 0
#         except Exception as e:
#             logger.error(f"删除影响因素 {impact_id} 失败: {e}")
#             return False


# # 创建全局单例
# mood_provider = LazySingleton(MoodProvider)
