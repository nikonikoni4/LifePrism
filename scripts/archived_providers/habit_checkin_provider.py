# """habit_checkins 表数据访问层"""
# import sqlite3
# import uuid
# from datetime import date, datetime
# from typing import Optional, List, Dict, Any

# from lifeprism.repository import LWBaseDataProvider
# from lifeprism.utils import get_logger, LazySingleton

# logger = get_logger(__name__)


# def _generate_checkin_id() -> str:
#     return f"checkin-{str(uuid.uuid4())[:8]}"


# class HabitCheckinProvider(LWBaseDataProvider):
#     """habit_checkins 表的数据访问对象"""

#     def create_checkin(self, data: Dict[str, Any]) -> Optional[str]:
#         """
#         创建打卡记录，返回新 checkin_id。
#         若 UNIQUE(habit_id, date) 冲突（重复打卡），返回 None。
#         """
#         checkin_id = _generate_checkin_id()
#         now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         try:
#             with self.db.get_connection() as conn:
#                 conn.execute(
#                     """INSERT INTO habit_checkins
#                     (id, habit_id, challenge_id, date, completed_at)
#                     VALUES (?, ?, ?, ?, ?)""",
#                     (
#                         checkin_id,
#                         data["habit_id"],
#                         data["challenge_id"],
#                         data["date"],
#                         data.get("completed_at", now_str),
#                     ),
#                 )
#             return checkin_id
#         except sqlite3.IntegrityError:
#             return None  # 重复打卡

#     def get_checkin_by_date(self, habit_id: str, checkin_date: str) -> Optional[Dict[str, Any]]:
#         """按习惯 ID 和日期查询打卡记录"""
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT * FROM habit_checkins WHERE habit_id = ? AND date = ?",
#                 (habit_id, checkin_date),
#             )
#             row = cursor.fetchone()
#             if not row:
#                 return None
#             columns = [desc[0] for desc in cursor.description]
#             return dict(zip(columns, row))

#     def delete_checkin(self, habit_id: str, checkin_date: str) -> bool:
#         """删除指定日期的打卡记录"""
#         with self.db.get_connection() as conn:
#             conn.execute(
#                 "DELETE FROM habit_checkins WHERE habit_id = ? AND date = ?",
#                 (habit_id, checkin_date),
#             )
#         return True

#     def delete_by_habit_id(self, habit_id: str) -> bool:
#         """删除习惯的所有打卡记录"""
#         with self.db.get_connection() as conn:
#             conn.execute(
#                 "DELETE FROM habit_checkins WHERE habit_id = ?", (habit_id,)
#             )
#         return True

#     def get_checkin_dates_by_challenge(
#         self, habit_id: str, challenge_id: str
#     ) -> List[str]:
#         """获取某挑战期内所有打卡日期列表"""
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT date FROM habit_checkins WHERE habit_id = ? AND challenge_id = ? ORDER BY date ASC",
#                 (habit_id, challenge_id),
#             )
#             return [row[0] for row in cursor.fetchall()]

#     def count_checkins_by_challenge(self, challenge_id: str) -> int:
#         """统计某挑战期内的打卡总次数"""
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT COUNT(*) FROM habit_checkins WHERE challenge_id = ?",
#                 (challenge_id,),
#             )
#             return cursor.fetchone()[0]

#     def get_today_checkins(self, habit_ids: List[str]) -> Dict[str, bool]:
#         """
#         批量查询今日打卡状态。
#         返回 {habit_id: True}，未打卡的习惯不出现在字典中（get() 默认返回 False）。
#         """
#         if not habit_ids:
#             return {}
#         today = date.today().isoformat()
#         placeholders = ",".join("?" * len(habit_ids))
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 f"SELECT habit_id FROM habit_checkins WHERE date = ? AND habit_id IN ({placeholders})",
#                 [today] + list(habit_ids),
#             )
#             return {row[0]: True for row in cursor.fetchall()}

#     def get_checkins_in_date_range(
#         self,
#         start_date: str,
#         end_date: str,
#         habit_ids: Optional[List[str]] = None,
#     ) -> List[Dict[str, Any]]:
#         """
#         查询日期范围内的打卡记录（热力图用）。
#         可选按 habit_ids 过滤。
#         """
#         with self.db.get_connection() as conn:
#             if habit_ids:
#                 placeholders = ",".join("?" * len(habit_ids))
#                 cursor = conn.execute(
#                     f"""SELECT * FROM habit_checkins
#                     WHERE date >= ? AND date <= ? AND habit_id IN ({placeholders})
#                     ORDER BY date ASC""",
#                     [start_date, end_date] + list(habit_ids),
#                 )
#             else:
#                 cursor = conn.execute(
#                     "SELECT * FROM habit_checkins WHERE date >= ? AND date <= ? ORDER BY date ASC",
#                     (start_date, end_date),
#                 )
#             columns = [desc[0] for desc in cursor.description]
#             return [dict(zip(columns, row)) for row in cursor.fetchall()]


# habit_checkin_provider = LazySingleton(HabitCheckinProvider)
