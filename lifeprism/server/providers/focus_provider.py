# """
# Focus 数据提供者
# 提供 Daily Focus 和 Weekly Focus 的数据库操作
# """
# from typing import Optional, List, Dict, Any

# from lifeprism.repository import LWBaseDataProvider
# from lifeprism.utils import get_logger, LazySingleton

# logger = get_logger(__name__)


# class FocusProvider(LWBaseDataProvider):
#     """
#     Focus 数据提供者

#     继承 LWBaseDataProvider，提供 Daily/Weekly Focus 的 CRUD 操作
#     """

#     def __init__(self, db_manager=None):
#         super().__init__(db_manager)

#     # ==================== Daily Focus 操作 ====================

#     def get_daily_focus(self, date: str) -> Optional[Dict[str, Any]]:
#         """
#         获取指定日期的焦点内容

#         Args:
#             date: 日期（YYYY-MM-DD 格式）

#         Returns:
#             Optional[Dict]: 焦点数据，不存在返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute("SELECT * FROM daily_focus WHERE date = ?", (date,))

#                 row = cursor.fetchone()
#                 if row:
#                     columns = [description[0] for description in cursor.description]
#                     return dict(zip(columns, row))
#                 return None

#         except Exception as e:
#             logger.error(f"获取日焦点失败: {e}")
#             return None

#     def upsert_daily_focus(self, date: str, content: str) -> bool:
#         """
#         创建或更新日焦点（INSERT OR REPLACE）

#         Args:
#             date: 日期（YYYY-MM-DD 格式）
#             content: 焦点内容

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     """INSERT INTO daily_focus (date, content) VALUES (?, ?)
#                        ON CONFLICT(date) DO UPDATE SET content = excluded.content""",
#                     (date, content)
#                 )
#                 logger.info(f"更新日焦点成功: {date}")
#                 return True

#         except Exception as e:
#             logger.error(f"更新日焦点失败: {e}")
#             return False

#     def get_daily_focuses_in_range(
#         self,
#         start_date: str,
#         end_date: str
#     ) -> List[Dict[str, Any]]:
#         """
#         获取日期范围内的所有日焦点

#         Args:
#             start_date: 开始日期（YYYY-MM-DD）
#             end_date: 结束日期（YYYY-MM-DD）

#         Returns:
#             List[Dict]: 日焦点列表
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     "SELECT * FROM daily_focus WHERE date >= ? AND date <= ? ORDER BY date ASC",
#                     (start_date, end_date)
#                 )

#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()

#                 return [dict(zip(columns, row)) for row in rows]

#         except Exception as e:
#             logger.error(f"获取日焦点范围失败: {e}")
#             return []

#     # ==================== Weekly Focus 操作 ====================

#     def get_weekly_focus(
#         self,
#         year: int,
#         month: int,
#         week_num: int
#     ) -> Optional[Dict[str, Any]]:
#         """
#         获取指定周的焦点内容

#         Args:
#             year: 年份
#             month: 月份（1-12）
#             week_num: 周序号（1-4）

#         Returns:
#             Optional[Dict]: 焦点数据，不存在返回 None
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     "SELECT * FROM weekly_focus WHERE year = ? AND month = ? AND week_num = ?",
#                     (year, month, week_num)
#                 )

#                 row = cursor.fetchone()
#                 if row:
#                     columns = [description[0] for description in cursor.description]
#                     return dict(zip(columns, row))
#                 return None

#         except Exception as e:
#             logger.error(f"获取周焦点失败: {e}")
#             return None

#     def upsert_weekly_focus(
#         self,
#         year: int,
#         month: int,
#         week_num: int,
#         content: str
#     ) -> bool:
#         """
#         创建或更新周焦点

#         Args:
#             year: 年份
#             month: 月份（1-12）
#             week_num: 周序号（1-4）
#             content: 焦点内容

#         Returns:
#             bool: 是否成功
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     """INSERT INTO weekly_focus (year, month, week_num, content) VALUES (?, ?, ?, ?)
#                        ON CONFLICT(year, month, week_num) DO UPDATE SET content = excluded.content""",
#                     (year, month, week_num, content)
#                 )
#                 logger.info(f"更新周焦点成功: {year}-{month} W{week_num}")
#                 return True

#         except Exception as e:
#             logger.error(f"更新周焦点失败: {e}")
#             return False

#     def get_weekly_focuses_in_month(
#         self,
#         year: int,
#         month: int
#     ) -> List[Dict[str, Any]]:
#         """
#         获取指定月份所有周的焦点

#         Args:
#             year: 年份
#             month: 月份（1-12）

#         Returns:
#             List[Dict]: 周焦点列表
#         """
#         try:
#             with self.db.get_connection() as conn:
#                 cursor = conn.cursor()
#                 cursor.execute(
#                     "SELECT * FROM weekly_focus WHERE year = ? AND month = ? ORDER BY week_num ASC",
#                     (year, month)
#                 )

#                 columns = [description[0] for description in cursor.description]
#                 rows = cursor.fetchall()

#                 return [dict(zip(columns, row)) for row in rows]

#         except Exception as e:
#             logger.error(f"获取月份周焦点失败: {e}")
#             return []


# focus_provider = LazySingleton(FocusProvider)
