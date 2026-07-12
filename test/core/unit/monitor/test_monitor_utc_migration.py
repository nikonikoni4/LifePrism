"""
Monitor 模块 UTC 时区迁移单元测试

验证 Monitor 模块的时间戳生成符合 UTC ISO 8601 格式要求。

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- .scratch/utc-timezone-migration/11-monitor-module-migration.md
"""

import re
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.core


# UTC ISO 8601 格式正则：YYYY-MM-DDTHH:MM:SS.ffffff+00:00
UTC_ISO_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$"
)


@pytest.fixture(autouse=True)
def mock_windows_api():
    """Mock lifeprism.monitor.windows_monitor.windows_api 模块

    windows_api 依赖 win32api/win32gui 等 Windows 专有库，
    在测试环境（无 pywin32）下无法导入，需要 mock。
    """
    mock_module = MagicMock()
    original = sys.modules.get("lifeprism.monitor.windows_monitor.windows_api")
    sys.modules["lifeprism.monitor.windows_monitor.windows_api"] = mock_module
    yield
    if original is not None:
        sys.modules["lifeprism.monitor.windows_monitor.windows_api"] = original
    else:
        sys.modules.pop("lifeprism.monitor.windows_monitor.windows_api", None)


# ==================== Slice 1: WindowMonitor._flush() ====================


class TestWindowMonitorTimestampUtcIso:
    """WindowMonitor._flush() 应使用 UTC ISO 8601 格式的时间戳"""

    def test_flush_generates_utc_iso_timestamp(self):
        """_flush() 生成的时间戳应为 UTC ISO 8601 格式

        场景：WindowMonitor 检测到窗口切换时，调用 _flush() 保存前一个窗口的事件
        验证：传给 provider.save_event() 的 timestamp 是 UTC ISO 格式（带 +00:00）
        """
        from lifeprism.monitor.windows_monitor.monitor import WindowMonitor

        provider = MagicMock()
        monitor = WindowMonitor(provider)

        # 模拟一个已开始的事件（UTC aware datetime，必须早于当前时间以保证 duration > 0）
        start_time = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        monitor.current_app = "test_app"
        monitor.current_title = "test_title"
        monitor.start_time = start_time

        monitor._flush()

        provider.save_event.assert_called_once()
        call_kwargs = provider.save_event.call_args.kwargs
        timestamp = call_kwargs.get("timestamp")

        assert timestamp is not None, "save_event 应接收 timestamp 参数"
        # 验证是 UTC ISO 8601 格式（带时区标识）
        assert UTC_ISO_PATTERN.match(timestamp), (
            f"timestamp 应为 UTC ISO 8601 格式（带 +00:00），实际: {timestamp}"
        )

    def test_flush_preserves_utc_timezone_from_start_time(self):
        """_flush() 应保留 start_time 的 UTC 时区信息

        场景：start_time 是 UTC aware datetime
        验证：timestamp 字符串包含 +00:00 时区标识，能被 fromisoformat 解析为 UTC
        """
        from lifeprism.monitor.windows_monitor.monitor import WindowMonitor

        provider = MagicMock()
        monitor = WindowMonitor(provider)

        start_time = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        monitor.current_app = "code"
        monitor.current_title = "monitor.py"
        monitor.start_time = start_time

        monitor._flush()

        timestamp = provider.save_event.call_args.kwargs["timestamp"]
        parsed = datetime.fromisoformat(timestamp)

        # 验证是 aware datetime
        assert parsed.tzinfo is not None, (
            f"timestamp 解析后应为 aware datetime，实际 tzinfo=None: {timestamp}"
        )
        # 验证时区是 UTC
        assert parsed.utcoffset() == timedelta(0), (
            f"timestamp 时区应为 UTC（offset=0），实际: {parsed.utcoffset()}"
        )


# ==================== Slice 2: ScreenshotStore.capture() ====================


class TestScreenshotStoreTimestampIsoFormat:
    """ScreenshotStore.capture() 应保留 captured_at 的 ISO 格式"""

    def test_capture_keeps_iso_format_timestamp(self):
        """capture() 存储的 captured_at 应保留 ISO 格式，不转换为 'YYYY-MM-DD HH:MM:SS'

        场景：CaptureRequest.captured_at 是 UTC ISO 格式
        验证：写入数据库的 captured_at 字段保持 ISO 格式
        """
        from lifeprism.monitor.screenshot.models import CaptureReason, CaptureRequest
        from lifeprism.monitor.screenshot.store import ScreenshotStore

        provider = MagicMock()
        provider.create_capture.return_value = True

        capture_backend = MagicMock()
        store = ScreenshotStore(
            provider=provider,
            capture_backend=capture_backend,
            data_root=MagicMock(),
            id_factory=lambda: "cap-test-001",
        )

        # UTC ISO 格式的 captured_at
        captured_at = "2026-07-12T10:30:00.000000+00:00"
        request = CaptureRequest(
            reason=CaptureReason.ACTIVE,
            captured_at=captured_at,
            window_app="Code.exe",
            window_title="monitor.py",
            frequency_level=2,
            engaged_segment_id="seg-001",
            is_afk=False,
        )

        store.capture(request)

        provider.create_capture.assert_called_once()
        payload = provider.create_capture.call_args.args[0]

        # 验证 captured_at 保持 ISO 格式（带 T 和时区标识）
        assert "T" in payload["captured_at"], (
            f"captured_at 应保持 ISO 格式（含 T），实际: {payload['captured_at']}"
        )
        assert "+00:00" in payload["captured_at"], (
            f"captured_at 应保留 UTC 时区标识（+00:00），实际: {payload['captured_at']}"
        )


# ==================== Slice 3: MonitorRuntime.iso_time_source ====================


class TestMonitorRuntimeIsoTimeSourceUtc:
    """MonitorRuntime 默认 iso_time_source 应生成 UTC ISO 格式"""

    def test_default_iso_time_source_generates_utc_iso(self):
        """默认 iso_time_source 应生成带 UTC 时区标识的 ISO 时间戳

        场景：MonitorRuntime 未传入 iso_time_source，使用默认实现
        验证：默认 iso_time_source 返回的字符串包含 +00:00
        """
        from lifeprism.monitor.windows_monitor.runtime import MonitorRuntime

        # 构造一个最小化的 MonitorRuntime（不触发 for_test 的复杂初始化）
        runtime = MonitorRuntime(
            window_context_source=MagicMock(),
            input_tracker=MagicMock(),
            scheduler=MagicMock(),
            screenshot_store=MagicMock(),
            screenshot_provider=MagicMock(),
            cleanup_worker=MagicMock(),
            input_listener=MagicMock(),
            db_manager=MagicMock(),
        )

        iso_str = runtime.iso_time_source()

        # 验证是 UTC ISO 格式
        assert "+00:00" in iso_str, (
            f"默认 iso_time_source 应生成 UTC ISO（含 +00:00），实际: {iso_str}"
        )
        parsed = datetime.fromisoformat(iso_str)
        assert parsed.utcoffset() == timedelta(0), (
            f"iso_time_source 时区应为 UTC，实际 offset: {parsed.utcoffset()}"
        )


# ==================== Slice 4: EventTransformer ====================


class TestEventTransformerUtcIso:
    """EventTransformer 应返回 UTC ISO 格式的时间戳，不转换为本地时间"""

    def test_convert_timestamp_returns_utc_iso(self):
        """_convert_timestamp() 应返回 UTC ISO 格式，不转换为本地时间

        场景：输入是 ActivityWatch 的 UTC ISO 时间戳
        验证：输出也是 UTC ISO 格式（带 +00:00），不是本地时间 'YYYY-MM-DD HH:MM:SS'
        """
        from lifeprism.processors.components.event_transformer import EventTransformer

        transformer = EventTransformer()

        # ActivityWatch 返回的 UTC ISO 时间戳
        utc_input = "2026-07-12T02:00:00.000000+00:00"
        result = transformer._convert_timestamp(utc_input)

        assert result is not None, "时间戳转换不应失败"
        # 验证是 UTC ISO 格式（带 T 和 +00:00），不是 'YYYY-MM-DD HH:MM:SS'
        assert "T" in result, (
            f"应返回 ISO 格式（含 T），实际: {result}"
        )
        assert "+00:00" in result, (
            f"应返回 UTC 时区标识（+00:00），实际: {result}"
        )

    def test_convert_timestamp_preserves_utc_not_local(self):
        """_convert_timestamp() 不应将 UTC 转为本地时间

        场景：输入 UTC 02:00（北京时间 10:00）
        验证：输出仍是 UTC 02:00（+00:00），不是本地 10:00
        """
        from lifeprism.processors.components.event_transformer import EventTransformer

        transformer = EventTransformer()
        utc_input = "2026-07-12T02:00:00.000000+00:00"

        result = transformer._convert_timestamp(utc_input)
        parsed = datetime.fromisoformat(result)

        # 验证小时数是 02（UTC），不是 10（本地 UTC+8）
        assert parsed.hour == 2, (
            f"应保留 UTC 时间（小时=2），实际小时={parsed.hour}，"
            f"说明可能被转换为本地时间"
        )
        assert parsed.utcoffset() == timedelta(0), (
            f"时区应为 UTC，实际: {parsed.utcoffset()}"
        )

    def test_transform_returns_utc_iso_start_end_time(self):
        """transform() 返回的 ProcessedEvent 的 start_time/end_time 应为 UTC ISO 格式"""
        from lifeprism.processors.components.event_transformer import EventTransformer

        transformer = EventTransformer(min_duration=0)

        raw_event = {
            "id": "evt-001",
            "timestamp": "2026-07-12T02:00:00.000000+00:00",
            "duration": 300,
            "data": {"app": "Code.exe", "title": "test.py"},
        }

        event = transformer.transform(raw_event)

        assert event is not None, "事件不应被过滤"
        # 验证 start_time 和 end_time 都是 UTC ISO 格式
        for field_name in ("start_time", "end_time"):
            value = getattr(event, field_name)
            assert "T" in value, (
                f"{field_name} 应为 ISO 格式（含 T），实际: {value}"
            )
            assert "+00:00" in value, (
                f"{field_name} 应含 UTC 时区标识，实际: {value}"
            )

    def test_transformer_has_no_local_timezone_dependency(self):
        """EventTransformer 不应依赖 LOCAL_TIMEZONE 进行转换

        验证：EventTransformer 实例不应有 _target_tz 属性（本地时区）
        """
        from lifeprism.processors.components.event_transformer import EventTransformer

        transformer = EventTransformer()

        # 迁移后不应存在 _target_tz 属性（本地时区 pytz 对象）
        assert not hasattr(transformer, "_target_tz"), (
            "EventTransformer 不应持有 _target_tz 属性（本地时区依赖），"
            "迁移后应直接使用 UTC"
        )


# ==================== Slice 5: data_clean.py convert_utc_to_local 移除 ====================


class TestDataCleanNoUtcToLocalConversion:
    """data_clean.py 不应再将 UTC 转换为本地时间"""

    def test_convert_utc_to_local_function_removed(self):
        """convert_utc_to_local 函数应已移除（或不再被调用）

        迁移后数据库统一使用 UTC，不应再将 AW 的 UTC 时间转为本地时间。
        """
        import lifeprism.processors.data_clean as data_clean_module

        # 函数应已移除
        assert not hasattr(data_clean_module, "convert_utc_to_local"), (
            "convert_utc_to_local 函数应已移除，"
            "迁移后数据库统一使用 UTC，不再需要 UTC→本地转换"
        )


# ==================== Slice 6: ProcessorMonitorDataProvider ====================


class TestProcessorMonitorDataProviderIsoFormat:
    """ProcessorMonitorDataProvider 应使用 ISO 格式查询 lifeprism 数据源"""

    def test_get_window_events_uses_iso_format_for_lifeprism(self):
        """get_window_events 在 lifeprism 模式下应使用 ISO 格式查询

        场景：monitor_type='lifeprism'，传入 UTC aware datetime
        验证：SQL 查询参数使用 ISO 格式（带 T），不是 'YYYY-MM-DD HH:MM:SS'
        """
        from lifeprism.processors.provider.processor_monitor_data_provider import (
            ProcessorMonitorDataProvider,
        )

        provider = ProcessorMonitorDataProvider.__new__(ProcessorMonitorDataProvider)
        provider.db = MagicMock()

        # 模拟查询返回空列表
        mock_cursor = MagicMock()
        mock_cursor.description = []
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        provider.db.get_connection.return_value = mock_conn

        # UTC aware datetime
        start_time = datetime(2026, 7, 12, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 7, 12, 23, 59, 59, tzinfo=timezone.utc)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "lifeprism.processors.provider.processor_monitor_data_provider.settings",
                MagicMock(monitor_type="lifeprism"),
            )
            provider.get_window_events(start_time=start_time, end_time=end_time)

        # 验证 SQL 参数使用 ISO 格式（带 T）
        execute_args = mock_cursor.execute.call_args.args
        params = execute_args[1] if len(execute_args) > 1 else ()
        start_str = params[0] if len(params) > 0 else ""

        assert "T" in start_str, (
            f"lifeprism 模式下查询参数应为 ISO 格式（含 T），实际: {start_str}"
        )


# ==================== Slice 7: DataProcessingService._get_incremental_time_range ====================


class TestDataProcessingServiceIncrementalTimeRangeUtc:
    """_get_incremental_time_range() 应返回 UTC aware datetime"""

    def test_empty_database_returns_utc_aware_datetime(self):
        """数据库为空时，返回的 start_time/end_time 应为 UTC aware datetime

        场景：get_latest_end_time() 返回 None（首次同步）
        验证：返回的 start_time 和 end_time 都是 UTC aware（tzinfo 不为 None，offset=0）
        """
        from lifeprism.server.services.data_processing_service import DataProcessingService

        service = DataProcessingService.__new__(DataProcessingService)
        service.server_lw_data_provider = MagicMock()
        service.server_lw_data_provider.get_latest_end_time.return_value = None

        start_time, end_time = service._get_incremental_time_range()

        # 验证都是 UTC aware
        assert start_time.tzinfo is not None, "start_time 应为 aware datetime"
        assert end_time.tzinfo is not None, "end_time 应为 aware datetime"
        assert start_time.utcoffset() == timedelta(0), (
            f"start_time 时区应为 UTC（offset=0），实际: {start_time.utcoffset()}"
        )
        assert end_time.utcoffset() == timedelta(0), (
            f"end_time 时区应为 UTC（offset=0），实际: {end_time.utcoffset()}"
        )

    def test_with_utc_iso_data_returns_utc_aware_datetime(self):
        """数据库有 UTC ISO 数据时，正确解析并返回 UTC aware datetime

        场景：get_latest_end_time() 返回 UTC ISO 格式字符串
        验证：start_time 从 latest_end_time 解析，且为 UTC aware
        """
        from lifeprism.server.services.data_processing_service import DataProcessingService

        service = DataProcessingService.__new__(DataProcessingService)
        service.server_lw_data_provider = MagicMock()
        # 返回 UTC ISO 格式的 latest_end_time
        service.server_lw_data_provider.get_latest_end_time.return_value = (
            "2026-07-12T08:00:00.000000+00:00"
        )

        start_time, end_time = service._get_incremental_time_range()

        # 验证 start_time 解析正确
        assert start_time.tzinfo is not None, "start_time 应为 aware datetime"
        assert start_time.utcoffset() == timedelta(0), (
            f"start_time 时区应为 UTC，实际: {start_time.utcoffset()}"
        )
        assert start_time.hour == 8, (
            f"start_time 小时应为 8（UTC），实际: {start_time.hour}"
        )
        # end_time 也应为 UTC aware
        assert end_time.utcoffset() == timedelta(0), (
            f"end_time 时区应为 UTC，实际: {end_time.utcoffset()}"
        )
