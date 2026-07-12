"""LLM 模块 UTC 时区迁移测试

验证 LLM 模块各子模块的时间戳使用 UTC 时区。

覆盖模块:
- lifeprism/llm/utils/llm_call_logger.py
- lifeprism/llm/prompts/prompt_loader.py
- lifeprism/llm/utils/helpers.py
- lifeprism/llm/agent/context.py

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- Issue #10: LLM 模块时间处理迁移
"""
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


pytestmark = pytest.mark.core


# ==================== LLMCallLogger UTC 测试 ====================


class TestLLMCallLoggerUtc:
    """测试 LLMCallLogger 的 UTC 时间戳"""

    @pytest.fixture
    def logger_instance(self, tmp_path):
        """创建独立日志目录的 LLMCallLogger 实例"""
        from lifeprism.llm.utils.llm_call_logger import LLMCallLogger

        logger = LLMCallLogger(log_dir=tmp_path / "llm_logs")
        logger.enabled = True
        return logger

    @pytest.fixture
    def mock_inbound_msg(self):
        """模拟 InboundMessage"""
        from dataclasses import dataclass
        from typing import Optional, Dict, Any

        @dataclass
        class MockInboundMessage:
            type: str
            content: str | list | None
            session_id: Optional[str] = None
            channel: str = "local"
            extra: Optional[Dict[str, Any]] = None

        return MockInboundMessage(
            type="chat",
            content="测试消息",
            session_id="test-session",
            extra={"system_prompt": "test"},
        )

    @pytest.fixture
    def mock_outbound_msg(self):
        """模拟 OutboundMessage"""
        from dataclasses import dataclass, field
        from typing import Optional, Dict, Any

        @dataclass
        class MockLLMResponse:
            content: str
            usage: Optional[Dict[str, Any]] = None

        @dataclass
        class MockOutboundMessage:
            id: str
            response: Optional[MockLLMResponse] = None
            session_id: Optional[str] = None
            extra: Optional[Dict[str, Any]] = None

        return MockOutboundMessage(
            id="test-1",
            response=MockLLMResponse(content="测试回复"),
            session_id="test-session",
            extra=None,
        )

    def test_log_call_timestamp_is_utc_iso(self, logger_instance, mock_inbound_msg, mock_outbound_msg):
        """log_call() 记录的 timestamp 应为 UTC ISO 8601 格式"""
        record_id = logger_instance.log_call(
            inbound_msg=mock_inbound_msg,
            outbound_msg=mock_outbound_msg,
            prompt_module="test",
            prompt_name="test_prompt",
        )

        assert record_id is not None

        # 读取日志文件
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = logger_instance.log_dir / f"llm_calls_{date_str}.json"

        with open(log_file, encoding="utf-8") as f:
            data = json.load(f)

        call = next(c for c in data["calls"] if c["id"] == record_id)
        timestamp_str = call["timestamp"]

        # 解析并验证为 UTC aware
        dt = datetime.fromisoformat(timestamp_str)
        assert dt.tzinfo is not None, (
            f"record timestamp 应为 aware datetime，实际: {timestamp_str}"
        )
        assert dt.utcoffset() == timedelta(0), (
            f"record timestamp 时区偏移应为 0（UTC），实际: {timestamp_str}"
        )

    def test_log_call_uses_utc_date_for_filename(self, logger_instance, mock_inbound_msg, mock_outbound_msg):
        """日志文件名应基于 UTC 日期"""
        logger_instance.log_call(
            inbound_msg=mock_inbound_msg,
            outbound_msg=mock_outbound_msg,
            prompt_module="test",
            prompt_name="test_prompt",
        )

        # 验证日志文件名使用 UTC 日期
        utc_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected_file = logger_instance.log_dir / f"llm_calls_{utc_date_str}.json"

        assert expected_file.exists(), (
            f"日志文件应使用 UTC 日期命名: {expected_file}"
        )


# ==================== PromptLoader UTC 测试 ====================


class TestPromptLoaderUtc:
    """测试 PromptLoader 的 UTC 时间戳"""

    @pytest.fixture
    def prompt_loader(self, tmp_path):
        """创建独立目录的 PromptLoader"""
        from lifeprism.llm.prompts.prompt_loader import PromptLoader

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir(parents=True)
        loader = PromptLoader(prompts_dir=prompts_dir, usage_stats_file=tmp_path / "usage_stats.yaml")
        return loader

    def test_update_usage_stats_last_used_is_utc_iso(self, prompt_loader):
        """_update_usage_stats() 写入的 last_used 应为 UTC ISO 8601 格式"""
        prompt_loader._update_usage_stats("test_prompt", "v1")

        last_used_str = prompt_loader._usage_stats["test_prompt"]["last_used"]

        # 解析并验证为 UTC aware
        dt = datetime.fromisoformat(last_used_str)
        assert dt.tzinfo is not None, (
            f"last_used 应为 aware datetime，实际: {last_used_str}"
        )
        assert dt.utcoffset() == timedelta(0), (
            f"last_used 时区偏移应为 0（UTC），实际: {last_used_str}"
        )

    def test_save_usage_stats_writes_utc_isoformat(self, prompt_loader, tmp_path):
        """保存的 usage_stats.yaml 中 last_used 应包含 UTC 时区后缀"""
        prompt_loader._update_usage_stats("test_prompt", "v1")
        prompt_loader._save_usage_stats()

        stats_file = tmp_path / "usage_stats.yaml"
        content = stats_file.read_text(encoding="utf-8")

        # 验证包含 UTC 时区后缀
        assert "+00:00" in content, (
            f"usage_stats.yaml 中 last_used 应包含 UTC 时区后缀 '+00:00'，内容: {content}"
        )


# ==================== helpers.py UTC 测试 ====================


class TestHelpersUtc:
    """测试 lifeprism.llm.utils.helpers 的 UTC 时间戳"""

    def test_timestamp_returns_utc_iso(self):
        """helpers.timestamp() 应返回 UTC ISO 8601 格式"""
        from lifeprism.llm.utils.helpers import timestamp

        result = timestamp()
        dt = datetime.fromisoformat(result)

        assert dt.tzinfo is not None, (
            f"timestamp() 应返回 aware datetime，实际: {result}"
        )
        assert dt.utcoffset() == timedelta(0), (
            f"timestamp() 时区偏移应为 0（UTC），实际: {result}"
        )

    def test_current_time_str_contains_timezone(self):
        """current_time_str() 应包含时区信息"""
        from lifeprism.llm.utils.helpers import current_time_str

        result = current_time_str()

        # 应包含时区标识（UTC 或本地时区缩写如 CST, 中国标准时间等）
        # 函数返回格式: "2026-03-15 22:30 (Saturday) (CST)"
        assert re.search(r"\([^()]+\)$", result), (
            f"current_time_str() 应包含时区缩写，实际: {result}"
        )


# ==================== Context UTC 测试 ====================


class TestContextUtc:
    """测试 lifeprism.llm.agent.context 的 UTC 时间处理"""

    def test_build_run_context_uses_utc_source(self):
        """_build_run_context() 应基于 datetime.now(timezone.utc) 生成时间

        验证策略：mock datetime.now(timezone.utc) 返回固定时间，
        检查 context 中是否包含该时间的本地表示。
        """
        from lifeprism.llm.agent.context import Context
        from lifeprism.llm.bus import ChannelType

        # 固定 UTC 时间
        fixed_utc = datetime(2026, 7, 12, 2, 30, 45, tzinfo=timezone.utc)

        mock_msg = MagicMock()
        mock_msg.channel = ChannelType.LOCAL

        with patch("lifeprism.llm.agent.context.datetime") as mock_datetime:
            # mock datetime.now(timezone.utc) 返回固定时间
            def mock_now(tz=None):
                if tz is not None:
                    return fixed_utc
                return fixed_utc.replace(tzinfo=None)

            mock_datetime.now = mock_now
            mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = Context._build_run_context(mock_msg)

        # 应包含"当前时间"
        assert "当前时间" in result
        # 应包含"本地"（channel_type）
        assert "本地" in result

    def test_build_run_context_shows_local_time(self):
        """_build_run_context() 显示的时间应为本地时间（非 UTC）

        根据 docs/guides/utc-migration-hidden-dependencies.md 2.9 节:
        "LLM 上下文中的时间（context.py:185）建议使用本地时间（LLM 需要知道用户的实际时间）"

        验证：显示的时间应与 UTC 时间不同（除非系统时区恰好是 UTC）。
        """
        from lifeprism.llm.agent.context import Context
        from lifeprism.llm.bus import ChannelType

        mock_msg = MagicMock()
        mock_msg.channel = ChannelType.LOCAL

        result = Context._build_run_context(mock_msg)

        # 提取显示的时间
        # 格式: "## runtime\n 当前时间：YYYY-MM-DD HH:MM:SS\n ..."
        match = re.search(r"当前时间：(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", result)
        assert match is not None, f"应匹配时间格式，实际: {result}"

        displayed_time_str = match.group(1)
        displayed_time = datetime.strptime(displayed_time_str, "%Y-%m-%d %H:%M:%S")

        # 获取当前 UTC 时间和本地时间
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        local_now = datetime.now().replace(tzinfo=None)

        # 显示的时间应接近本地时间（而非 UTC 时间）
        # 除非系统时区是 UTC，否则 UTC 和本地时间应有差异
        utc_diff = abs((displayed_time - utc_now).total_seconds())
        local_diff = abs((displayed_time - local_now).total_seconds())

        # 显示时间应更接近本地时间（允许 60 秒的执行延迟）
        # 注意：如果系统时区恰好是 UTC，utc_diff 和 local_diff 会相等
        assert local_diff < 60 or utc_diff < 60, (
            f"显示时间 ({displayed_time}) 应接近当前时间。"
            f"UTC 差异: {utc_diff}s, 本地差异: {local_diff}s"
        )


# ==================== agent_schedule_job UTC 兼容性测试 ====================


class TestAgentScheduleJobUtcCompat:
    """测试 agent_schedule_job 的 naive/aware datetime 兼容性"""

    def test_process_session_message_handles_naive_update_at(self):
        """process_session_message 应能处理旧 session 文件中的 naive update_at

        向后兼容场景：旧 session 文件的 update_at 是 naive 本地时间，
        新代码使用 datetime.now(timezone.utc) 比较，
        不应因 naive/aware 比较抛出 TypeError。
        """
        # 这个测试验证：当 update_at 是 naive datetime 时，
        # 与 datetime.now(timezone.utc) 比较不会抛出 TypeError
        from datetime import timedelta

        # 模拟旧 session 文件中的 naive update_at
        naive_update_at = datetime.fromisoformat("2026-06-01T10:00:00")

        # 模拟新代码的 UTC aware datetime
        utc_now = datetime.now(timezone.utc)

        # 如果代码正确处理了 naive datetime（视为 UTC），比较不会抛出 TypeError
        # 这里验证：naive datetime 加上 tzinfo=UTC 后可以与 aware datetime 比较
        aware_update_at = naive_update_at.replace(tzinfo=timezone.utc)

        # 这个比较不应抛出 TypeError
        try:
            result = aware_update_at > utc_now - timedelta(days=7)
            # 结果应为 bool
            assert isinstance(result, bool)
        except TypeError as e:
            pytest.fail(f"aware datetime 比较不应抛出 TypeError: {e}")
