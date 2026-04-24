"""
原始行为分析数据提供者

职责：提供 raw_behavior_analysis 表的所有数据访问接口
"""
from typing import Dict, Any, Optional, List, Set
from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger

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

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'start_time', 'end_time', 'behavior', 'screen_count', 'created_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'start_time', 'end_time', 'created_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'start_time', 'end_time', 'behavior', 'screen_count', 'created_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'end_time', 'behavior', 'screen_count'
    }

    # ==================== 核心 CRUD 方法 ====================

    def get_raw_behavior_by_start_time(self, start_time: str) -> Optional[Dict[str, Any]]:
        """
        根据开始时间获取单条原始行为分析记录

        Args:
            start_time: 开始时间（YYYY-MM-DD HH:MM:SS 格式）

        Returns:
            dict | None: 记录或 None
        """
        options = QueryOptions(
            filters={self._PRIMARY_KEY: start_time},
            order_by='start_time'
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def get_raw_behaviors_by_date_range(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取指定日期范围内的原始行为分析记录

        Args:
            start_date: 开始日期（YYYY-MM-DD 格式）
            end_date: 结束日期（YYYY-MM-DD 格式）

        Returns:
            list[dict]: 记录列表，按 start_time 升序排列
        """
        start_datetime = f"{start_date} 00:00:00"
        end_datetime = f"{end_date} 23:59:59"

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
            return [dict(zip(columns, row)) for row in rows]

    def create_raw_behavior(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建单条原始行为分析记录

        Args:
            data: dict, 包含 start_time, end_time, behavior, screen_count

        Returns:
            dict: 创建后的完整记录

        Raises:
            ValueError: 如果字段不合法
        """
        # 白名单验证
        required_fields = {'start_time', 'end_time', 'behavior', 'screen_count'}
        if not required_fields.issubset(data.keys()):
            missing = required_fields - set(data.keys())
            raise ValueError(f"Missing required fields: {missing}")

        allowed_fields = required_fields
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid insert fields: {invalid_fields}")

        self.db.insert(self._TABLE_NAME, data)
        logger.info(f"创建原始行为分析记录: {data['start_time']}")

        # 返回刚插入的记录
        return self.get_raw_behavior_by_start_time(data['start_time']) or {}

    def batch_create_raw_behaviors(self, data_list: List[Dict[str, Any]]) -> int:
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

        required_fields = {'start_time', 'end_time', 'behavior', 'screen_count'}

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
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for data in data_list:
                try:
                    cursor.execute(
                        f"""INSERT INTO {self._TABLE_NAME}
                           (start_time, end_time, behavior, screen_count, created_at)
                           VALUES (?, ?, ?, ?, datetime('now', 'localtime'))""",
                        (data['start_time'], data['end_time'], data['behavior'], data['screen_count'])
                    )
                    success_count += 1
                except Exception as e:
                    logger.warning(f"插入记录失败 {data['start_time']}: {e}")
                    continue

        logger.info(f"批量创建原始行为分析记录: {success_count}/{len(data_list)}")
        return success_count

    def delete_raw_behaviors_by_date_range(
        self,
        start_date: str,
        end_date: str
    ) -> int:
        """
        删除指定日期范围内的原始行为分析记录（用于重新生成）

        Args:
            start_date: 开始日期（YYYY-MM-DD 格式）
            end_date: 结束日期（YYYY-MM-DD 格式）

        Returns:
            int: 删除的记录数
        """
        start_datetime = f"{start_date} 00:00:00"
        end_datetime = f"{end_date} 23:59:59"

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""DELETE FROM {self._TABLE_NAME}
                       WHERE start_time >= ? AND start_time <= ?""",
                    (start_datetime, end_datetime)
                )
                affected_rows = cursor.rowcount
                logger.info(f"删除原始行为分析记录: {start_date} 至 {end_date}，共 {affected_rows} 条")
                return affected_rows
        except Exception as e:
            logger.error(f"删除原始行为分析记录失败: {e}")
            return 0



