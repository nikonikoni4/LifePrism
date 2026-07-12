"""
原始行为分析数据提供者

职责：提供 raw_behavior_analysis 表的所有数据访问接口
"""

from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError, ValidationError
from lifeprism.utils.time_utils import build_utc_time_range, get_utc_now_iso

logger = get_logger(__name__)


class RawBehaviorAnalysisProvider(LWBaseDataProvider):
    """
    原始行为分析数据提供者

    职责：提供 raw_behavior_analysis 表的所有数据访问接口
    存储按 bucket 强行切割的原始截图分析数据
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "raw_behavior_analysis"
    _PRIMARY_KEY = "start_time"
    _DATE_FIELD = None
    _TIME_FIELD = "start_time"
    _ON_CONFLICT = "replace"  # 原始行为分析数据可能重新分析，冲突时替换

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: set[str] = {"start_time", "end_time", "behavior", "screen_count", "created_at"}
    _ORDER_FIELDS: set[str] = {"start_time", "end_time", "created_at"}
    _SELECT_FIELDS: set[str] = {"start_time", "end_time", "behavior", "screen_count", "created_at"}
    _UPDATE_FIELDS: set[str] = {"end_time", "behavior", "screen_count"}

    # ==================== 核心 CRUD 方法 ====================

    def query_raw_behaviors(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 time_range: 时间范围查询（基于 start_time 字段）
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'behavior': 'working'})
            records, total = provider.query_raw_behaviors(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_raw_behaviors(options)
        """
        return self._generic_query(options)

    def get_raw_behavior_by_start_time(self, start_time: str) -> dict[str, Any] | None:
        """
        根据开始时间获取单条原始行为分析记录

        Args:
            start_time: 开始时间（YYYY-MM-DD HH:MM:SS 格式）

        Returns:
            dict | None: 记录或 None
        """
        options = QueryOptions(filters={self._PRIMARY_KEY: start_time}, order_by="start_time")
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def get_raw_behaviors_by_date_range(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """
        获取指定日期范围内的原始行为分析记录

        Args:
            start_date: 开始日期（YYYY-MM-DD 格式，本地时区）
            end_date: 结束日期（YYYY-MM-DD 格式，本地时区）

        Returns:
            list[dict]: 记录列表，按 start_time 升序排列
        """
        start_datetime, _ = build_utc_time_range(start_date)
        _, end_datetime = build_utc_time_range(end_date)

        sql = """
        SELECT * FROM raw_behavior_analysis
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time ASC
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, [start_datetime, end_datetime])
            rows = cursor.fetchall()
            if not rows:
                return []
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in rows]

    def create_raw_behavior(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        创建单条原始行为分析记录

        Args:
            data: dict, 包含 start_time, end_time, behavior, screen_count

        Returns:
            dict: 创建后的完整记录

        Raises:
            ValueError: 如果字段不合法
            DataAccessError: 数据库操作失败
        """
        try:
            # 白名单验证
            required_fields = {"start_time", "end_time", "behavior", "screen_count"}
            if not required_fields.issubset(data.keys()):
                missing = required_fields - set(data.keys())
                raise ValueError(f"Missing required fields: {missing}")

            allowed_fields = required_fields
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            # 使用 _generic_insert（_ON_CONFLICT = "replace"）
            self._generic_insert(data, on_conflict=self._ON_CONFLICT)
            logger.info("创建原始行为分析记录: %s", data["start_time"])

            # 返回刚插入的记录
            return self.get_raw_behavior_by_start_time(data["start_time"]) or {}
        except ValueError:
            raise
        except Exception as e:
            logger.error("创建原始行为分析记录失败: %s", e)
            raise DataAccessError(f"创建原始行为分析记录失败: {e}") from e

    def batch_create_raw_behaviors(self, data_list: list[dict[str, Any]]) -> int:
        """
        批量创建原始行为分析记录

        Args:
            data_list: list[dict], 记录列表

        Returns:
            int: 成功插入的记录数

        Raises:
            ValueError: 如果字段不合法
        """
        if not data_list:
            return 0

        required_fields = {"start_time", "end_time", "behavior", "screen_count"}

        # 验证所有记录
        for idx, data in enumerate(data_list):
            if not required_fields.issubset(data.keys()):
                missing = required_fields - set(data.keys())
                raise ValueError(f"Record {idx}: Missing required fields: {missing}")

            invalid_fields = set(data.keys()) - required_fields
            if invalid_fields:
                raise ValueError(f"Record {idx}: Invalid insert fields: {invalid_fields}")

        # 批量插入
        success_count = 0
        now_iso = get_utc_now_iso()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for data in data_list:
                try:
                    cursor.execute(
                        f"""INSERT INTO {self._TABLE_NAME}
                           (start_time, end_time, behavior, screen_count, created_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            data["start_time"],
                            data["end_time"],
                            data["behavior"],
                            data["screen_count"],
                            now_iso,
                        ),
                    )
                    success_count += 1
                except Exception as e:
                    logger.warning("插入记录失败 %s: %s", data["start_time"], e)
                    continue

        logger.info("批量创建原始行为分析记录: %s/%s", success_count, len(data_list))
        return success_count

    def update_raw_behavior(self, start_time: str, data: dict[str, Any]) -> bool:
        """
        更新原始行为分析记录

        Args:
            start_time: 开始时间（YYYY-MM-DD HH:MM:SS 格式）
            data: 要更新的字段（支持 end_time, behavior, screen_count）

        Returns:
            bool: 是否成功

        Raises:
            ValidationError: 字段验证失败
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_update(start_time, data)
            if success:
                logger.info("更新原始行为分析记录 %s 成功", start_time)
            return success
        except ValueError as e:
            logger.error("更新原始行为分析记录 %s 失败: %s", start_time, e)
            raise ValidationError(str(e)) from e
        except Exception as e:
            logger.error("更新原始行为分析记录 %s 失败: %s", start_time, e)
            raise DataAccessError(f"更新原始行为分析记录失败: {e}") from e

    def delete_raw_behaviors_by_date_range(self, start_date: str, end_date: str) -> int:
        """
        删除指定日期范围内的原始行为分析记录（用于重新生成）

        Args:
            start_date: 开始日期（YYYY-MM-DD 格式，本地时区）
            end_date: 结束日期（YYYY-MM-DD 格式，本地时区）

        Returns:
            int: 删除的记录数

        Raises:
            DataAccessError: 数据库操作失败
        """
        start_datetime, _ = build_utc_time_range(start_date)
        _, end_datetime = build_utc_time_range(end_date)

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""DELETE FROM {self._TABLE_NAME}
                       WHERE start_time >= ? AND start_time <= ?""",
                    (start_datetime, end_datetime),
                )
                affected_rows = cursor.rowcount
                logger.info(
                    "删除原始行为分析记录: %s 至 %s，共 %s 条", start_date, end_date, affected_rows
                )
                return affected_rows
        except Exception as e:
            logger.error("删除原始行为分析记录失败: %s", e)
            raise DataAccessError(f"删除原始行为分析记录失败: {e}") from e
