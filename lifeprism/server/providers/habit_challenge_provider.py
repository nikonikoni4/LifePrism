# """habit_challenges 表数据访问层"""
# import uuid
# from datetime import datetime
# from typing import Optional, List, Dict, Any

# from lifeprism.repository import LWBaseDataProvider
# from lifeprism.utils import get_logger, LazySingleton

# logger = get_logger(__name__)


# def _generate_challenge_id() -> str:
#     return f"challenge-{str(uuid.uuid4())[:8]}"


# class HabitChallengeProvider(LWBaseDataProvider):
#     """habit_challenges 表的数据访问对象"""

#     def create_challenge(self, data: Dict[str, Any]) -> str:
#         """
#         创建挑战记录，返回新 challenge_id。

#         Args:
#             data: 挑战字段字典，必须包含 habit_id / challenge_weeks /
#                   required_completions / from_level / to_level /
#                   start_date / end_date。

#         Returns:
#             新生成的 challenge_id（格式：challenge-xxxxxxxx）
#         """
#         challenge_id = _generate_challenge_id()
#         with self.db.get_connection() as conn:
#             conn.execute(
#                 """INSERT INTO habit_challenges
#                 (id, habit_id, challenge_weeks, required_completions,
#                  from_level, to_level, start_date, end_date,
#                  completed_count, streak_base, status, finished_at)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
#                 (
#                     challenge_id,
#                     data["habit_id"],
#                     data["challenge_weeks"],
#                     data["required_completions"],
#                     data["from_level"],
#                     data["to_level"],
#                     data["start_date"],
#                     data["end_date"],
#                     data.get("completed_count", 0),
#                     data.get("streak_base", 0),
#                     data.get("status", "in_progress"),
#                     data.get("finished_at"),
#                 ),
#             )
#         logger.info(f"创建挑战成功: {challenge_id} (habit_id={data['habit_id']})")
#         return challenge_id

#     def get_challenge_by_id(self, challenge_id: str) -> Optional[Dict[str, Any]]:
#         """
#         按 ID 查询单个挑战，不存在返回 None。

#         Args:
#             challenge_id: 挑战 ID（格式：challenge-xxxxxxxx）

#         Returns:
#             挑战字典，或 None
#         """
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT * FROM habit_challenges WHERE id = ?", (challenge_id,)
#             )
#             row = cursor.fetchone()
#             if not row:
#                 return None
#             columns = [desc[0] for desc in cursor.description]
#             return dict(zip(columns, row))

#     def get_challenges_by_habit(self, habit_id: str) -> List[Dict[str, Any]]:
#         """获取某习惯的所有挑战记录，按创建时间升序"""
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT * FROM habit_challenges WHERE habit_id = ? ORDER BY created_at ASC",
#                 (habit_id,),
#             )
#             columns = [desc[0] for desc in cursor.description]
#             return [dict(zip(columns, row)) for row in cursor.fetchall()]

#     def get_current_challenge(self, habit_id: str) -> Optional[Dict[str, Any]]:
#         """
#         获取习惯当前进行中的挑战（status = 'in_progress'）。

#         Args:
#             habit_id: 习惯 ID

#         Returns:
#             进行中的挑战字典，或 None（无进行中挑战）
#         """
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT * FROM habit_challenges WHERE habit_id = ? AND status = 'in_progress' LIMIT 1",
#                 (habit_id,),
#             )
#             row = cursor.fetchone()
#             if not row:
#                 return None
#             columns = [desc[0] for desc in cursor.description]
#             return dict(zip(columns, row))

#     def update_challenge(self, challenge_id: str, update_data: Dict[str, Any]) -> bool:
#         """
#         更新挑战字段（PATCH 语义）。只更新 allowed_fields 中的字段，自动更新 updated_at。

#         Args:
#             challenge_id: 挑战 ID
#             update_data: 待更新的字段字典

#         Returns:
#             True（成功或无字段需更新）
#         """
#         allowed_fields = {"completed_count", "streak_base", "status", "finished_at"}
#         filtered = {k: v for k, v in update_data.items() if k in allowed_fields}
#         if not filtered:
#             return True
#         filtered["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         set_clause = ", ".join(f"{k} = ?" for k in filtered)
#         values = list(filtered.values()) + [challenge_id]
#         with self.db.get_connection() as conn:
#             conn.execute(
#                 f"UPDATE habit_challenges SET {set_clause} WHERE id = ?", values
#             )
#         return True

#     def mark_in_progress_challenge_failed(self, habit_id: str, challenge_id: str) -> bool:
#         """
#         将指定 in_progress 挑战原子更新为 failed。

#         条件：
#         - id = challenge_id
#         - habit_id = habit_id
#         - status = 'in_progress'
#         """
#         now = datetime.now().isoformat()
#         updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 """
#                 UPDATE habit_challenges
#                 SET status = ?, finished_at = ?, updated_at = ?
#                 WHERE id = ? AND habit_id = ? AND status = 'in_progress'
#                 """,
#                 ("failed", now, updated_at, challenge_id, habit_id),
#             )
#             return cursor.rowcount == 1

#     def get_expired_in_progress_challenges(self, today: str) -> List[Dict[str, Any]]:
#         """
#         获取所有 end_date < today 且 status = 'in_progress' 的挑战（到期未结算）。

#         Args:
#             today: 当前日期字符串，格式 YYYY-MM-DD

#         Returns:
#             到期未结算的挑战列表
#         """
#         with self.db.get_connection() as conn:
#             cursor = conn.execute(
#                 "SELECT * FROM habit_challenges WHERE status = 'in_progress'",
#             )
#             columns = [desc[0] for desc in cursor.description]
#             return [dict(zip(columns, row)) for row in cursor.fetchall()]

#     def get_challenge_history(
#         self, habit_id: str, status: Optional[str] = None
#     ) -> List[Dict[str, Any]]:
#         """
#         获取习惯的挑战历史（succeeded 和 failed），按 finished_at 倒序。
#         不包含 cancelled 和 in_progress 记录（除非显式指定 status）。

#         Args:
#             habit_id: 习惯 ID
#             status: 若指定则只返回该状态的记录；否则返回 succeeded 和 failed

#         Returns:
#             挑战历史列表，按 finished_at 倒序
#         """
#         with self.db.get_connection() as conn:
#             if status:
#                 cursor = conn.execute(
#                     """SELECT * FROM habit_challenges
#                     WHERE habit_id = ? AND status = ?
#                     ORDER BY finished_at DESC""",
#                     (habit_id, status),
#                 )
#             else:
#                 cursor = conn.execute(
#                     """SELECT * FROM habit_challenges
#                     WHERE habit_id = ? AND status IN ('succeeded', 'failed')
#                     ORDER BY finished_at DESC""",
#                     (habit_id,),
#                 )
#             columns = [desc[0] for desc in cursor.description]
#             return [dict(zip(columns, row)) for row in cursor.fetchall()]

#     def delete_by_habit_id(self, habit_id: str) -> bool:
#         """
#         删除习惯的所有挑战记录（级联清理用）。

#         Args:
#             habit_id: 习惯 ID

#         Returns:
#             True
#         """
#         with self.db.get_connection() as conn:
#             conn.execute(
#                 "DELETE FROM habit_challenges WHERE habit_id = ?", (habit_id,)
#             )
#         return True


# habit_challenge_provider = LazySingleton(HabitChallengeProvider)
