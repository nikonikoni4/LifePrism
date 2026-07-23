"""
Timeline 数据提供者（重构版）

职责：提供 timeline_custom_block 表的所有数据访问接口
"""

import sqlite3
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError
from lifeprism.utils.time_utils import build_utc_time_range

logger = get_logger(__name__)


class CustomBlockProvider(LWBaseDataProvider):
    """
    Timeline 自定义时间块数据提供者

    职责：提供 timeline_custom_block 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "timeline_custom_block"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None  # 没有单独的 date 字段
    _TIME_FIELD = "start_time"  # 使用 start_time 作为时间字段
    _ON_CONFLICT = "abort"  # 自定义时间块不应该有重复 ID，冲突时应该报错

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: set[str] = {
        "id",
        "start_time",
        "end_time",
        "duration",
        "content",
        "todo_id",
        "color",
        "category_id",
        "sub_category_id",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "start_time", "end_time", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "start_time",
        "end_time",
        "duration",
        "content",
        "todo_id",
        "color",
        "category_id",
        "sub_category_id",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "start_time",
        "end_time",
        "duration",
        "content",
        "todo_id",
        "color",
        "category_id",
        "sub_category_id",
    }

    # ==================== 核心 CRUD 方法 ====================

    def query_custom_blocks(
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
            options = QueryOptions(filters={'todo_id': 'task-123'})
            records, total = provider.query_custom_blocks(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_custom_blocks(options)
        """
        return self._generic_query(options)

    def get_custom_block_by_id(self, block_id: int) -> dict[str, Any] | None:
        """
        根据 ID 获取单条自定义时间块

        Args:
            block_id: int, 时间块 ID

        Returns:
            dict | None: 记录或 None
        """
        options = QueryOptions(filters={self._PRIMARY_KEY: block_id}, order_by="id")
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def get_custom_blocks_by_time_range(
        self, start_time: str, end_time: str
    ) -> list[dict[str, Any]]:
        """
        获取指定时间范围的所有自定义时间块

        Args:
            start_time: str, 开始时间（ISO 8601 UTC 格式）
            end_time: str, 结束时间（ISO 8601 UTC 格式）

        Returns:
            list[dict]: 时间块列表
        """
        # 使用原生 SQL 查询时间范围（复杂查询保留手写 SQL）
        sql = """
        SELECT * FROM timeline_custom_block
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time ASC
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, [start_time, end_time])
            rows = cursor.fetchall()
            if not rows:
                return []
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in rows]

    def create_custom_block(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        创建用户自定义时间块

        Args:
            data: dict, 包含 content, start_time, end_time, duration, category_id, sub_category_id

        Returns:
            dict: 创建后的完整记录（含 id 和时间戳）

        Raises:
            ValueError: 如果字段不合法
            DataAccessError: 数据库操作失败
        """
        try:
            # 白名单验证
            allowed_fields = self._UPDATE_FIELDS
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValueError(f"Invalid insert fields: {invalid_fields}")

            # 使用 _generic_insert（_ON_CONFLICT = "abort"）
            # 返回的是自增 ID
            block_id = self._generic_insert(data)

            if block_id:
                # 查询刚插入的记录
                return self.get_custom_block_by_id(int(block_id)) or {}
            return {}
        except ValueError:
            raise
        except Exception as e:
            logger.error("创建自定义时间块失败: %s", e)
            raise DataAccessError(f"创建自定义时间块失败: {e}") from e

    def update_custom_block(self, block_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        """
        更新用户自定义时间块

        Args:
            block_id: int, 时间块 ID
            data: dict, 要更新的字段

        Returns:
            dict | None: 更新后的完整记录或 None

        注意：
            - todo_id, category_id, sub_category_id 允许设置为 None（清除绑定）
            - 其他字段（content, start_time 等）不接受 None 值
        """
        # 可清空的字段列表（这些字段允许显式设置为 None）
        nullable_fields = {"todo_id", "category_id", "sub_category_id"}

        # 构建更新数据：
        # - 可清空字段：保留 None 值（用于清除绑定）
        # - 其他字段：过滤掉 None 值
        update_data = {}
        for k, v in data.items():
            if k in nullable_fields:
                # 可清空字段：无论是 None 还是有效值都保留
                update_data[k] = v
            elif v is not None:
                # 其他字段：只保留非 None 值
                update_data[k] = v

        if not update_data:
            return self.get_custom_block_by_id(block_id)

        # 白名单验证
        invalid_fields = set(update_data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {invalid_fields}")

        try:
            # 使用 _generic_update 自动处理 updated_at
            success = self._generic_update(block_id, update_data)
            if success:
                logger.info("更新自定义时间块: block_id=%s", block_id)
                return self.get_custom_block_by_id(block_id)
            return None
        except sqlite3.Error as e:
            logger.error("更新自定义时间块失败: block_id=%s, %s", block_id, e)
            raise DataAccessError(
                message="更新自定义时间块失败", details={"block_id": block_id, "error": str(e)}
            ) from e

    def delete_custom_block(self, block_id: int) -> bool:
        """
        删除用户自定义时间块

        走 _generic_delete 通道：timeline_custom_block 是 SYNC_TABLES 中的 AUTOINCREMENT 表
        （在 HASH_ID_PREFIXES 中，前缀 tcb-），删除时自动写墓碑到 deletion_log，
        墓碑 record_id = hash_id（由 _generic_delete 通过 _resolve_tombstone_record_id 解析）。

        Args:
            block_id: int, 时间块 ID

        Returns:
            bool: 是否删除成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(block_id)
            if success:
                logger.info("删除时间块 %s 成功", block_id)
            return success
        except DataAccessError:
            raise
        except Exception as e:
            logger.error("删除时间块 %s 失败: %s", block_id, e)
            raise DataAccessError(f"删除时间块 {block_id} 失败") from e

    # ============================================================================
    # WAID 累计时长查询（保留业务逻辑方法）
    # ============================================================================

    def get_duration_by_todo(self, todo_id: str, start_time: str, end_time: str) -> int:
        """查询指定 todo 在指定时间范围的累计时长（分钟）

        Args:
            todo_id: 待办事项 ID
            start_time: 开始时间（ISO 8601 UTC 格式）
            end_time: 结束时间（ISO 8601 UTC 格式）

        Returns:
            int: 累计时长（分钟），无记录返回 0

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""SELECT COALESCE(SUM(duration), 0) FROM {self._TABLE_NAME}
                       WHERE todo_id = ? AND start_time >= ? AND start_time <= ?""",
                    (todo_id, start_time, end_time),
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error("查询 todo %s 累计时长失败: %s", todo_id, e)
            raise DataAccessError(f"查询 todo {todo_id} 累计时长失败") from e

    def batch_get_duration_by_todos(
        self, todo_ids: list[str], start_time: str, end_time: str
    ) -> dict[str, int]:
        """批量查询多个 todo 在指定时间范围的累计时长

        Args:
            todo_ids: 待办事项 ID 列表
            start_time: 开始时间（ISO 8601 UTC 格式）
            end_time: 结束时间（ISO 8601 UTC 格式）

        Returns:
            dict: {todo_id: 累计分钟数}

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not todo_ids:
            return {}
        try:
            placeholders = ",".join("?" * len(todo_ids))
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""SELECT todo_id, COALESCE(SUM(duration), 0) as total
                        FROM {self._TABLE_NAME}
                        WHERE todo_id IN ({placeholders})
                          AND start_time >= ? AND start_time <= ?
                        GROUP BY todo_id""",
                    (*todo_ids, start_time, end_time),
                )
                result = {row[0]: row[1] for row in cursor.fetchall()}
                for tid in todo_ids:
                    if tid not in result:
                        result[tid] = 0
                return result
        except Exception as e:
            logger.error("批量查询累计时长失败: %s", e)
            raise DataAccessError("批量查询累计时长失败") from e

    # ============================================================================
    # 兼容旧接口（保留用于 timeline_builder）
    # ============================================================================

    def get_timeline_events_by_date(self, date: str, channel: str = "pc") -> list[dict[str, Any]]:
        """
        获取指定日期的时间线事件数据

        内部调用 get_activity_logs，封装为 timeline 专用格式

        Args:
            date: str, 日期（YYYY-MM-DD 格式）
            channel: str, 数据通道 ('pc' 或 'mobile'，当前仅支持 'pc')

        Returns:
            list[dict]: 事件列表
        """
        # 将本地日期转换为 UTC 时间范围
        start_time, end_time = build_utc_time_range(date)
        logs, _ = self.get_activity_logs(
            start_time=start_time,
            end_time=end_time,
            query_fields=[
                "id",
                "start_time",
                "end_time",
                "duration",
                "app",
                "title",
                "category_id",
                "sub_category_id",
            ],
            order_desc=False,  # 升序
        )

        # 转换为 timeline 格式
        events = []
        for log in logs:
            events.append(
                {
                    "id": log.get("id"),
                    "start_time": log.get("start_time"),
                    "end_time": log.get("end_time"),
                    "duration": log.get("duration"),
                    "app": log.get("app"),
                    "title": log.get("title"),
                    "category_id": log.get("category_id") or "",
                    "category_name": log.get("category_name") or "",
                    "sub_category_id": log.get("sub_category_id") or "",
                    "sub_category_name": log.get("sub_category_name") or "",
                    "app_description": "",  # 保留字段
                    "title_analysis": "",  # 保留字段
                    "device_type": "pc",
                }
            )

        return events
