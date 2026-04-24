# """habits 表数据访问层"""
# import uuid
# from datetime import datetime
# from typing import Optional, List, Dict, Any

# from lifeprism.storage import LWBaseDataProvider
# from lifeprism.utils import get_logger, LazySingleton

# logger = get_logger(__name__)


# def generate_id(prefix: str) -> str:
#     """生成带前缀的短 UUID：{prefix}-{8位hex}"""
#     return f"{prefix}-{str(uuid.uuid4())[:8]}"


# class HabitProvider(LWBaseDataProvider):
#     """habits 表的数据访问对象"""

#     def get_habits(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
#         """获取习惯列表，可按 status 过滤"""
#         with self.db.get_connection() as conn:
#             if status:
#                 cursor = conn.execute(
#                     "SELECT * FROM habits WHERE status = ? ORDER BY created_at ASC",
#                     (status,)
#                 )
#             else:
#                 cursor = conn.execute(
#                     "SELECT * FROM habits ORDER BY created_at ASC"
#                 )
#             columns = [desc[0] for desc in cursor.description]
#             return [dict(zip(columns, row)) for row in cursor.fetchall()]

#     def get_habit_by_id(self, habit_id: str) -> Optional[Dict[str, Any]]:
#         """按 ID 查询单个习惯，不存在返回 None"""
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT * FROM habits WHERE id = ?", (habit_id,)
#             )
#             row = cursor.fetchone()
#             if not row:
#                 return None
#             columns = [desc[0] for desc in cursor.description]
#             return dict(zip(columns, row))

#     def create_habit(self, data: Dict[str, Any]) -> str:
#         """创建习惯，返回新生成的 habit_id"""
#         habit_id = generate_id("habit")
#         with self.db.get_connection() as conn:
#             conn.execute(
#                 """INSERT INTO habits
#                 (id, name, description, frequency_type, frequency_config,
#                  current_level, status, value_id, commitment_id,
#                  paused_at)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
#                 (
#                     habit_id,
#                     data["name"],
#                     data.get("description"),
#                     data.get("frequency_type", "daily"),
#                     data.get("frequency_config"),
#                     data.get("current_level", 0),
#                     data.get("status", "active"),
#                     data.get("value_id"),
#                     data.get("commitment_id"),
#                     None,
#                 ),
#             )
#         return habit_id

#     def update_habit(self, habit_id: str, update_data: Dict[str, Any]) -> bool:
#         """
#         更新习惯（PATCH 语义）。
#         只更新 allowed_fields 中存在的字段，自动更新 updated_at。
#         """
#         allowed_fields = {
#             "name", "description", "frequency_type", "frequency_config",
#             "current_level", "status", "value_id", "commitment_id", "paused_at",
#         }
#         filtered = {k: v for k, v in update_data.items() if k in allowed_fields}
#         if not filtered:
#             return True
#         filtered["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         set_clause = ", ".join(f"{k} = ?" for k in filtered)
#         values = list(filtered.values()) + [habit_id]
#         with self.db.get_connection() as conn:
#             conn.execute(f"UPDATE habits SET {set_clause} WHERE id = ?", values)
#         return True

#     def delete_habit(self, habit_id: str) -> bool:
#         """删除习惯记录"""
#         with self.db.get_connection() as conn:
#             conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
#         return True


# habit_provider = LazySingleton(HabitProvider)
