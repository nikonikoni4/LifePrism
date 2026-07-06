"""
Screen Capture Provider - 截屏记录数据访问层

职责：提供 screen_captures 表的所有数据访问接口
"""

from typing import Any

from lifeprism.repository import LWBaseDataProvider
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

from .common_query_options import QueryOptions

logger = get_logger(__name__)


class ScreenCaptureProvider(LWBaseDataProvider):
    """
    截屏记录数据提供者

    职责：提供 screen_captures 表的所有数据访问接口
    注意：id (sc-{uuid[:8]}) 作为主键
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "screen_captures"
    _PRIMARY_KEY = "id"  # ✅ screen_captures 表使用 id 作为主键
    _DATE_FIELD = None  # ❌ screen_captures 表没有 date 字段
    _TIME_FIELD = "captured_at"  # ✅ screen_captures 表有 captured_at 时间字段
    _ON_CONFLICT = "replace"  # 冲突时替换

    _FILTER_FIELDS: set[str] = {
        "id",
        "captured_at",
        "capture_reason",
        "file_path",
        "window_app",
        "window_title",
        "frequency_level",
        "engaged_segment_id",
        "is_afk",
        "created_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "captured_at", "created_at", "frequency_level"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "captured_at",
        "capture_reason",
        "file_path",
        "window_app",
        "window_title",
        "frequency_level",
        "engaged_segment_id",
        "is_afk",
        "created_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "captured_at",
        "capture_reason",
        "file_path",
        "window_app",
        "window_title",
        "frequency_level",
        "engaged_segment_id",
        "is_afk",
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_screen_captures(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口（使用基类方法）

        Args:
            options: 查询选项
                - 支持 time_range: 时间范围查询（基于 captured_at 字段）
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 查询时间范围
            options = QueryOptions(time_range=("2026-04-25T10:00:00", "2026-04-25T12:00:00"))
            captures, total = provider.query_screen_captures(options)

            # 查询特定原因
            options = QueryOptions(filters={'capture_reason': 'scheduled'})
            captures, total = provider.query_screen_captures(options)

            # 查询特定应用
            options = QueryOptions(filters={'window_app': 'Chrome'})
            captures, total = provider.query_screen_captures(options)
        """
        return self._generic_query(options)  # ✅ 直接调用基类方法

    def get_screen_capture_by_id(self, capture_id: str) -> dict[str, Any] | None:
        """
        按主键（id）获取单条截屏记录（使用基类方法）

        Args:
            capture_id: 截屏记录 ID (格式: sc-{uuid[:8]})

        Returns:
            截屏记录，不存在返回 None
        """
        options = QueryOptions(filters={"id": capture_id})
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_screen_capture(self, capture_id: str, data: dict[str, Any] | None = None) -> bool:
        """
        创建截屏记录（使用基类方法）

        Args:
            capture_id: 截屏记录 ID (格式: sc-{uuid[:8]})
            data: 其他字段（必须包含 captured_at, capture_reason, file_path）

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            insert_data = {"id": capture_id}
            if data:
                # 白名单验证
                invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
                if invalid_fields:
                    raise ValueError(f"Invalid insert fields: {invalid_fields}")
                insert_data.update(data)

            self._generic_insert(insert_data)
            logger.info("创建截屏记录 %s 成功", capture_id)
            return True
        except Exception as e:
            logger.error("创建截屏记录 %s 失败: %s", capture_id, e)
            raise DataAccessError(f"创建截屏记录 {capture_id} 失败") from e

    def update_screen_capture(self, capture_id: str, data: dict[str, Any]) -> bool:
        """
        更新截屏记录（使用基类方法）

        Args:
            capture_id: 截屏记录 ID (格式: sc-{uuid[:8]})
            data: 要更新的字段

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

            return self._generic_update(capture_id, data)
        except Exception as e:
            logger.error("更新截屏记录 %s 失败: %s", capture_id, e)
            raise DataAccessError(f"更新截屏记录 {capture_id} 失败") from e

    def delete_screen_capture(self, capture_id: str) -> bool:
        """
        删除截屏记录（使用基类方法）

        Args:
            capture_id: 截屏记录 ID (格式: sc-{uuid[:8]})

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(capture_id)
            if success:
                logger.info("删除截屏记录 %s 成功", capture_id)
            return success
        except Exception as e:
            logger.error("删除截屏记录 %s 失败: %s", capture_id, e)
            raise DataAccessError(f"删除截屏记录 {capture_id} 失败") from e

    # ==================== 便捷方法 ====================

    def query_screenshots(
        self,
        start_time: str,
        end_time: str,
        capture_reason: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        查询截图记录（便捷方法）

        这是对 query_screen_captures 的封装，提供更简洁的接口用于时间范围查询。

        Args:
            start_time: 开始时间（ISO 格式或 YYYY-MM-DD HH:MM:SS 格式）
            end_time: 结束时间（ISO 格式或 YYYY-MM-DD HH:MM:SS 格式）
            capture_reason: 截图原因过滤（可选，如 'active', 'scheduled'）

        Returns:
            List[Dict]: 截图列表，按时间升序排序

        Example:
            >>> provider = ScreenCaptureProvider()
            >>> screenshots = provider.query_screenshots(
            ...     start_time="2026-04-19T09:00:00",
            ...     end_time="2026-04-19T10:00:00",
            ...     capture_reason="active"
            ... )
        """
        # 将 ISO 格式（带 T）转换为数据库格式（空格分隔）
        start_time_db = start_time.replace("T", " ") if "T" in start_time else start_time
        end_time_db = end_time.replace("T", " ") if "T" in end_time else end_time

        filters = {}
        if capture_reason is not None:
            filters["capture_reason"] = capture_reason

        options = QueryOptions(
            time_range=(start_time_db, end_time_db),
            filters=filters,
            order_by="captured_at",
            order_desc=False,  # 升序排序
        )

        results, _ = self.query_screen_captures(options)
        return results
