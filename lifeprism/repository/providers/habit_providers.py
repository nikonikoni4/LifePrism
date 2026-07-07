"""
Habit 模块数据提供者

包含 3 个独立的 Provider：
- HabitProvider: habits 表
- HabitChallengeProvider: habit_challenges 表
- HabitCheckinProvider: habit_checkins 表
"""

import sqlite3
import uuid
from datetime import date, datetime
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


def generate_id(prefix: str) -> str:
    """生成带前缀的短 UUID：{prefix}-{8位hex}"""
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


# ==================== HabitProvider ====================


class HabitProvider(LWBaseDataProvider):
    """
    习惯数据提供者（对应 habits 表）

    职责：提供 habits 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "habits"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    _FILTER_FIELDS: set[str] = {
        "id",
        "name",
        "status",
        "frequency_type",
        "current_level",
        "value_id",
        "commitment_id",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "name", "current_level", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "name",
        "description",
        "frequency_type",
        "frequency_config",
        "current_level",
        "status",
        "value_id",
        "commitment_id",
        "paused_at",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "name",
        "description",
        "frequency_type",
        "frequency_config",
        "current_level",
        "status",
        "value_id",
        "commitment_id",
        "paused_at",
    }

    # ==================== 核心方法 ====================

    def query_habits(self, options: QueryOptions | None = None) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'status': 'active'})
            records, total = provider.query_habits(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_habits(options)
        """
        return self._generic_query(options)

    def get_habits(self, status: str | None = None) -> list[dict[str, Any]]:
        """
        获取习惯列表，可按 status 过滤

        Args:
            status: 状态过滤（'active'|'paused'），None 返回全部

        Returns:
            习惯列表，按 created_at 升序
        """
        options = QueryOptions(
            filters={"status": status} if status else None, order_by="created_at", order_desc=False
        )
        results, _ = self._generic_query(options)
        return results

    def get_habit_by_id(self, habit_id: str) -> dict[str, Any] | None:
        """
        按 ID 查询单个习惯

        Args:
            habit_id: 习惯 ID

        Returns:
            习惯数据，不存在返回 None
        """
        options = QueryOptions(filters={"id": habit_id}, order_by="id", order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_habit(self, data: dict[str, Any]) -> str:
        """
        创建习惯，返回新生成的 habit_id

        Args:
            data: 习惯数据

        Returns:
            新生成的 habit_id
        """
        habit_id = generate_id("habit")
        insert_data = {
            "id": habit_id,
            "name": data["name"],
            "description": data.get("description"),
            "frequency_type": data.get("frequency_type", "daily"),
            "frequency_config": data.get("frequency_config"),
            "current_level": data.get("current_level", 0),
            "status": data.get("status", "active"),
            "value_id": data.get("value_id"),
            "commitment_id": data.get("commitment_id"),
            "paused_at": None,
        }
        self._generic_insert(insert_data)
        logger.info("创建习惯成功: %s", habit_id)
        return habit_id

    def update_habit(self, habit_id: str, update_data: dict[str, Any]) -> bool:
        """
        更新习惯（PATCH 语义）

        Args:
            habit_id: 习惯 ID
            update_data: 要更新的字段

        Returns:
            是否成功
        """
        if not update_data:
            return True

        # 白名单验证
        invalid_fields = set(update_data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            logger.warning("忽略非法更新字段: %s", invalid_fields)
            update_data = {k: v for k, v in update_data.items() if k in self._UPDATE_FIELDS}

        if not update_data:
            return True

        return self._generic_update(habit_id, update_data)

    def delete_habit(self, habit_id: str) -> bool:
        """
        删除习惯记录

        Args:
            habit_id: 习惯 ID

        Returns:
            是否成功
        """
        success = self._generic_delete(habit_id)
        if success:
            logger.info("删除习惯 %s 成功", habit_id)
        return success


# ==================== HabitChallengeProvider ====================


class HabitChallengeProvider(LWBaseDataProvider):
    """
    习惯挑战数据提供者（对应 habit_challenges 表）

    职责：提供 habit_challenges 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "habit_challenges"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = "start_date"  # 用于日期范围查询
    _TIME_FIELD = None

    _FILTER_FIELDS: set[str] = {
        "id",
        "habit_id",
        "status",
        "from_level",
        "to_level",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "start_date", "end_date", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "habit_id",
        "challenge_weeks",
        "required_completions",
        "from_level",
        "to_level",
        "start_date",
        "end_date",
        "completed_count",
        "streak_base",
        "status",
        "finished_at",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {"completed_count", "streak_base", "status", "finished_at"}

    # ==================== 核心方法 ====================

    def query_habit_challenges(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 date_range: 日期范围查询（基于 start_date 字段）
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'status': 'active'})
            records, total = provider.query_habit_challenges(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_habit_challenges(options)
        """
        return self._generic_query(options)

    def create_challenge(self, data: dict[str, Any]) -> str:
        """
        创建挑战记录，返回新 challenge_id

        Args:
            data: 挑战字段字典

        Returns:
            新生成的 challenge_id
        """
        challenge_id = generate_id("challenge")
        insert_data = {
            "id": challenge_id,
            "habit_id": data["habit_id"],
            "challenge_weeks": data["challenge_weeks"],
            "required_completions": data["required_completions"],
            "from_level": data["from_level"],
            "to_level": data["to_level"],
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "completed_count": data.get("completed_count", 0),
            "streak_base": data.get("streak_base", 0),
            "status": data.get("status", "in_progress"),
            "finished_at": data.get("finished_at"),
        }
        self._generic_insert(insert_data)
        logger.info("创建挑战成功: %s (habit_id=%s)", challenge_id, data["habit_id"])
        return challenge_id

    def get_challenge_by_id(self, challenge_id: str) -> dict[str, Any] | None:
        """
        按 ID 查询单个挑战

        Args:
            challenge_id: 挑战 ID

        Returns:
            挑战字典，或 None
        """
        options = QueryOptions(filters={"id": challenge_id}, order_by="id", order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def get_challenges_by_habit(self, habit_id: str) -> list[dict[str, Any]]:
        """
        获取某习惯的所有挑战记录，按创建时间升序

        Args:
            habit_id: 习惯 ID

        Returns:
            挑战列表
        """
        options = QueryOptions(
            filters={"habit_id": habit_id}, order_by="created_at", order_desc=False
        )
        results, _ = self._generic_query(options)
        return results

    def get_current_challenge(self, habit_id: str) -> dict[str, Any] | None:
        """
        获取习惯当前进行中的挑战（status = 'in_progress'）

        Args:
            habit_id: 习惯 ID

        Returns:
            进行中的挑战字典，或 None
        """
        options = QueryOptions(
            filters={"habit_id": habit_id, "status": "in_progress"},
            order_by="id",
            order_desc=False,
            page=1,
            page_size=1,
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def update_challenge(self, challenge_id: str, update_data: dict[str, Any]) -> bool:
        """
        更新挑战字段（PATCH 语义）

        Args:
            challenge_id: 挑战 ID
            update_data: 待更新的字段字典

        Returns:
            是否成功
        """
        if not update_data:
            return True

        # 白名单验证
        invalid_fields = set(update_data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            logger.warning("忽略非法更新字段: %s", invalid_fields)
            update_data = {k: v for k, v in update_data.items() if k in self._UPDATE_FIELDS}

        if not update_data:
            return True

        return self._generic_update(challenge_id, update_data)

    def mark_in_progress_challenge_failed(self, habit_id: str, challenge_id: str) -> bool:
        """
        将指定 in_progress 挑战原子更新为 failed

        条件：
        - id = challenge_id
        - habit_id = habit_id
        - status = 'in_progress'

        Args:
            habit_id: 习惯 ID
            challenge_id: 挑战 ID

        Returns:
            是否更新成功（True 表示更新了 1 行）
        """
        now = datetime.now().isoformat()
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE habit_challenges
                SET status = ?, finished_at = ?, updated_at = ?
                WHERE id = ? AND habit_id = ? AND status = 'in_progress'
                """,
                ("failed", now, updated_at, challenge_id, habit_id),
            )
            return cursor.rowcount == 1

    def get_expired_in_progress_challenges(self, today: str) -> list[dict[str, Any]]:
        """
        获取所有 status = 'in_progress' 的挑战（用于到期检查）

        Args:
            today: 当前日期字符串，格式 YYYY-MM-DD

        Returns:
            进行中的挑战列表
        """
        options = QueryOptions(filters={"status": "in_progress"}, order_by="id", order_desc=False)
        results, _ = self._generic_query(options)
        return results

    def get_challenge_history(
        self, habit_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        """
        获取习惯的挑战历史（succeeded 和 failed），按 finished_at 倒序

        Args:
            habit_id: 习惯 ID
            status: 若指定则只返回该状态的记录；否则返回 succeeded 和 failed

        Returns:
            挑战历史列表，按 finished_at 倒序
        """
        # 这个方法需要自定义 SQL，因为需要 IN 查询和特殊排序
        try:
            with self.db.get_connection() as conn:
                if status:
                    cursor = conn.execute(
                        """SELECT * FROM habit_challenges
                        WHERE habit_id = ? AND status = ?
                        ORDER BY finished_at DESC""",
                        (habit_id, status),
                    )
                else:
                    cursor = conn.execute(
                        """SELECT * FROM habit_challenges
                        WHERE habit_id = ? AND status IN ('succeeded', 'failed')
                        ORDER BY finished_at DESC""",
                        (habit_id,),
                    )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("获取挑战历史失败: error=%s", e)
            raise DataAccessError(f"获取挑战历史失败: {e}") from e

    def delete_by_habit_id(self, habit_id: str) -> bool:
        """
        删除习惯的所有挑战记录（级联清理用）

        Args:
            habit_id: 习惯 ID

        Returns:
            True
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM habit_challenges WHERE habit_id = ?", (habit_id,))
            return True
        except sqlite3.Error as e:
            logger.error("按习惯ID删除挑战失败: error=%s", e)
            raise DataAccessError(f"按习惯ID删除挑战失败: {e}") from e


# ==================== HabitCheckinProvider ====================


class HabitCheckinProvider(LWBaseDataProvider):
    """
    习惯打卡数据提供者（对应 habit_checkins 表）

    职责：提供 habit_checkins 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "habit_checkins"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = "date"  # 用于日期范围查询
    _TIME_FIELD = None

    _FILTER_FIELDS: set[str] = {"id", "habit_id", "challenge_id", "date", "created_at"}
    _ORDER_FIELDS: set[str] = {"id", "date", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "habit_id",
        "challenge_id",
        "date",
        "completed_at",
        "created_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "completed_at"  # 通常不更新打卡记录，但保留字段
    }

    # ==================== 核心方法 ====================

    def query_habit_checkins(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 date_range: 日期范围查询（基于 date 字段）
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'status': 'active'})
            records, total = provider.query_habit_checkins(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_habit_checkins(options)
        """
        return self._generic_query(options)

    def create_checkin(self, data: dict[str, Any]) -> str | None:
        """
        创建打卡记录，返回新 checkin_id
        若 UNIQUE(habit_id, date) 冲突（重复打卡），返回 None

        Args:
            data: 打卡数据

        Returns:
            新 checkin_id，或 None（重复打卡）
        """
        checkin_id = generate_id("checkin")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        insert_data = {
            "id": checkin_id,
            "habit_id": data["habit_id"],
            "challenge_id": data["challenge_id"],
            "date": data["date"],
            "completed_at": data.get("completed_at", now_str),
        }

        try:
            self._generic_insert(insert_data)
            logger.info("创建打卡记录成功: %s", checkin_id)
            return checkin_id
        except sqlite3.IntegrityError:
            logger.warning("打卡记录已存在: habit_id=%s, date=%s", data["habit_id"], data["date"])
            return None  # 重复打卡

    def get_checkin_by_date(self, habit_id: str, checkin_date: str) -> dict[str, Any] | None:
        """
        按习惯 ID 和日期查询打卡记录

        Args:
            habit_id: 习惯 ID
            checkin_date: 打卡日期 YYYY-MM-DD

        Returns:
            打卡记录，或 None
        """
        options = QueryOptions(
            filters={"habit_id": habit_id, "date": checkin_date}, order_by="id", order_desc=False
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def delete_checkin(self, habit_id: str, checkin_date: str) -> bool:
        """
        删除指定日期的打卡记录

        Args:
            habit_id: 习惯 ID
            checkin_date: 打卡日期

        Returns:
            True
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM habit_checkins WHERE habit_id = ? AND date = ?",
                    (habit_id, checkin_date),
                )
            return True
        except sqlite3.Error as e:
            logger.error("删除打卡记录失败: error=%s", e)
            raise DataAccessError(f"删除打卡记录失败: {e}") from e

    def delete_by_habit_id(self, habit_id: str) -> bool:
        """
        删除习惯的所有打卡记录

        Args:
            habit_id: 习惯 ID

        Returns:
            True
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM habit_checkins WHERE habit_id = ?", (habit_id,))
            return True
        except sqlite3.Error as e:
            logger.error("按习惯ID删除打卡失败: error=%s", e)
            raise DataAccessError(f"按习惯ID删除打卡失败: {e}") from e

    def get_checkin_dates_by_challenge(self, habit_id: str, challenge_id: str) -> list[str]:
        """
        获取某挑战期内所有打卡日期列表

        Args:
            habit_id: 习惯 ID
            challenge_id: 挑战 ID

        Returns:
            日期列表，按日期升序
        """
        options = QueryOptions(
            filters={"habit_id": habit_id, "challenge_id": challenge_id},
            order_by="date",
            order_desc=False,
            fields=["date"],
        )
        results, _ = self._generic_query(options)
        return [row["date"] for row in results]

    def count_checkins_by_challenge(self, challenge_id: str) -> int:
        """
        统计某挑战期内的打卡总次数

        Args:
            challenge_id: 挑战 ID

        Returns:
            打卡次数
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM habit_checkins WHERE challenge_id = ?",
                    (challenge_id,),
                )
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("统计打卡失败: error=%s", e)
            raise DataAccessError(f"统计打卡失败: {e}") from e

    def get_today_checkins(self, habit_ids: list[str]) -> dict[str, bool]:
        """
        批量查询今日打卡状态

        Args:
            habit_ids: 习惯 ID 列表

        Returns:
            {habit_id: True}，未打卡的习惯不出现在字典中
        """
        if not habit_ids:
            return {}

        today = date.today().isoformat()
        placeholders = ",".join("?" * len(habit_ids))

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    f"SELECT habit_id FROM habit_checkins WHERE date = ? AND habit_id IN ({placeholders})",
                    [today] + list(habit_ids),
                )
                return {row[0]: True for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error("获取今日打卡失败: error=%s", e)
            raise DataAccessError(f"获取今日打卡失败: {e}") from e

    def get_checkins_in_date_range(
        self,
        start_date: str,
        end_date: str,
        habit_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        查询日期范围内的打卡记录（热力图用）

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            habit_ids: 可选按 habit_ids 过滤

        Returns:
            打卡记录列表，按日期升序
        """
        if habit_ids:
            # 需要自定义 SQL 处理 IN 查询
            placeholders = ",".join("?" * len(habit_ids))
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    f"""SELECT * FROM habit_checkins
                    WHERE date >= ? AND date <= ? AND habit_id IN ({placeholders})
                    ORDER BY date ASC""",
                    [start_date, end_date] + list(habit_ids),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        else:
            # 使用通用方法
            options = QueryOptions(
                date_range=(start_date, end_date), order_by="date", order_desc=False
            )
            results, _ = self._generic_query(options)
            return results
