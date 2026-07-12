"""
事件转换器
负责将 ActivityWatch 原始事件转换为标准化的 ProcessedEvent
"""

from datetime import datetime, timedelta, timezone

from lifeprism.config.settings_manager import settings
from lifeprism.processors.models.processed_event import ProcessedEvent
from lifeprism.utils import get_logger, is_multipurpose_app

logger = get_logger(__name__)


class EventTransformer:
    """
    ActivityWatch 事件转换器

    职责：
    - 将原始 AW 事件转换为标准化的 ProcessedEvent
    - 过滤短时长事件
    - 标准化时间戳、应用名称、窗口标题

    Note:
        迁移到 UTC 后，时间戳保持 UTC ISO 8601 格式，
        不再转换为本地时间。
    """

    def __init__(self, min_duration: int = None):
        """
        初始化转换器

        Args:
            min_duration: 最小事件时长（秒），低于此值的事件将被过滤
        """
        self.min_duration = min_duration or settings.data_cleaning_threshold

    def transform(self, raw_event: dict) -> ProcessedEvent | None:
        """
        转换单个事件：时长过滤，应用名称标准化，标题标准化，时间戳转换

        Args:
            raw_event: ActivityWatch 原始事件字典

        Returns:
            ProcessedEvent 或 None（如果被过滤）
        """
        # 1. 检查时长
        duration = int(raw_event.get("duration", 0))
        if duration < self.min_duration:
            return None

        # 2. 获取并标准化应用名称
        app_name = raw_event.get("data", {}).get("app")
        if not app_name:
            return None
        app_name = self._normalize_app_name(app_name)

        # 3. 获取并标准化标题
        title = raw_event.get("data", {}).get("title", "")
        title = self._normalize_title(title)

        # 4. 判断是否多用途应用
        is_multipurpose = is_multipurpose_app(app_name)

        # 5. 多用途应用必须有 title，否则视为脏数据过滤掉
        if is_multipurpose and not title:
            logger.debug("过滤脏数据: 多用途应用 %s 无 title", app_name)
            return None

        # 6. 转换时间戳（保持 UTC ISO 8601 格式）
        timestamp_str = raw_event.get("timestamp", "")
        start_time = self._convert_timestamp(timestamp_str)
        if not start_time:
            logger.warning("时间戳转换失败: %s", timestamp_str)
            return None

        # 7. 计算结束时间（UTC ISO 8601 格式）
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(seconds=duration)
        end_time = end_dt.isoformat()

        return ProcessedEvent(
            id=str(raw_event.get("id", "")),
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            app=app_name,
            title=title,
            is_multipurpose=is_multipurpose,
        )

    def transform_batch(self, raw_events: list[dict]) -> tuple[list[ProcessedEvent], int]:
        """
        批量转换事件：时长过滤，应用名称标准化，标题标准化，时间戳转换

        Args:
            raw_events: 原始事件列表

        Returns:
            (有效事件列表(时长>=min_duration的事件), 被过滤数量)
        """
        valid_events = []
        removed_count = 0

        for raw_event in raw_events:
            event = self.transform(raw_event)
            if event:
                valid_events.append(event)
            else:
                removed_count += 1

        return valid_events, removed_count

    def _normalize_app_name(self, app: str) -> str:
        """
        标准化应用名称

        - 转小写
        - 去除空白
        - 去除 .exe 后缀
        """
        return app.lower().strip().split(".exe")[0]

    def _normalize_title(self, title: str) -> str:
        """
        标准化窗口标题

        - 处理 "和另外" 多窗口后缀
        - 转小写
        - 去除空白
        """
        if not title:
            return ""
        return title.split("和另外")[0].strip().lower()

    def _convert_timestamp(self, utc_timestamp_str: str) -> str | None:
        """
        标准化 UTC 时间戳为 ISO 8601 格式

        迁移到 UTC 后，ActivityWatch 返回的 UTC 时间戳直接保留，
        不再转换为本地时间。

        Args:
            utc_timestamp_str: ISO 8601 格式的 UTC 时间戳

        Returns:
            UTC ISO 8601 格式的时间字符串（带时区标识），或 None
        """
        if not utc_timestamp_str:
            return None

        try:
            # 处理 Z 后缀（表示 UTC）
            clean_timestamp = utc_timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_timestamp)

            # 如果是 naive datetime，补充 UTC 时区
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.isoformat()
        except Exception as e:
            logger.warning("时间戳转换失败: %s -> %s", utc_timestamp_str, str(e))
            return None
