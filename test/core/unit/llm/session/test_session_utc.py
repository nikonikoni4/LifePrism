"""Session 模块 UTC 时区迁移测试

验证 Session 和 SessionManager 的时间戳使用 UTC 时区。

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- Issue #10: LLM 模块时间处理迁移
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from lifeprism.llm.session.manager import Session, SessionManager, ChatHistoryManager


pytestmark = pytest.mark.core


class TestSessionUtcTimestamps:
    """测试 Session dataclass 的 UTC 时间戳"""

    def test_created_at_is_utc_aware(self):
        """Session.created_at 应为 UTC aware datetime"""
        session = Session()
        assert session.created_at.tzinfo is not None, (
            "created_at 应为 aware datetime（tzinfo 不为 None）"
        )
        assert session.created_at.utcoffset() == timedelta(0), (
            "created_at 时区偏移应为 0（UTC）"
        )

    def test_updated_at_is_utc_aware(self):
        """Session.updated_at 应为 UTC aware datetime"""
        session = Session()
        assert session.updated_at.tzinfo is not None, (
            "updated_at 应为 aware datetime（tzinfo 不为 None）"
        )
        assert session.updated_at.utcoffset() == timedelta(0), (
            "updated_at 时区偏移应为 0（UTC）"
        )

    def test_add_message_timestamp_is_utc_iso(self):
        """Session.add_message() 写入的 timestamp 应为 UTC ISO 8601 格式"""
        session = Session()
        session.add_message(role="user", content="测试消息")

        timestamp_str = session.messages[-1]["timestamp"]
        # 解析 ISO 格式
        dt = datetime.fromisoformat(timestamp_str)

        # 验证为 aware datetime
        assert dt.tzinfo is not None, (
            f"message timestamp 应为 aware datetime，实际: {timestamp_str}"
        )
        assert dt.utcoffset() == timedelta(0), (
            f"message timestamp 时区偏移应为 0（UTC），实际 offset={dt.utcoffset()}"
        )

    def test_add_message_updates_updated_at_to_utc(self):
        """add_message 后 updated_at 应为 UTC aware"""
        session = Session()
        original_updated = session.updated_at
        # 确保有微小时间差
        import time as time_module

        time_module.sleep(0.001)
        session.add_message(role="user", content="测试")

        assert session.updated_at > original_updated
        assert session.updated_at.tzinfo is not None
        assert session.updated_at.utcoffset() == timedelta(0)

    def test_session_name_uses_utc_time(self):
        """Session.name 应基于 UTC 时间生成

        session_name 格式为 session_YYYYMMDDHHMM，应使用 UTC 时间。
        验证方式：name 中的时间应接近 datetime.now(timezone.utc)
        """
        before = datetime.now(timezone.utc)
        session = Session()
        after = datetime.now(timezone.utc)

        # 从 name 提取时间
        # 格式: session_YYYYMMDDHHMM
        name_time_str = session.name.replace("session_", "")
        name_dt = datetime.strptime(name_time_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)

        # name 中的时间应在 before 和 after 之间（分钟级精度）
        # 由于是分钟级，允许 1 分钟的误差
        assert before - timedelta(minutes=1) <= name_dt <= after + timedelta(minutes=1), (
            f"session name 时间 ({name_dt}) 应接近 UTC 当前时间 "
            f"({before} ~ {after})"
        )


class TestSessionManagerUtcPersistence:
    """测试 SessionManager 的 UTC 时间戳持久化"""

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """临时 session 目录"""
        return tmp_path / "sessions"

    @pytest.fixture
    def session_manager(self, temp_session_dir):
        """使用临时目录的 SessionManager"""
        manager = SessionManager()
        return manager

    def test_save_and_load_session_preserves_utc_timestamps(self, session_manager, temp_session_dir):
        """保存再加载 session，时间戳应保持 UTC aware"""
        with patch.object(SessionManager, "get_session_path_by_id") as mock_path:
            temp_session_dir.mkdir(parents=True, exist_ok=True)
            mock_path.return_value = temp_session_dir / "test-session.jsonl"

            session = Session(id="test-session")
            session.add_message(role="user", content="测试消息")
            original_created_at = session.created_at
            original_updated_at = session.updated_at

            session_manager.save_session(session)

            # 清除缓存后重新加载
            session_manager._cache.clear()
            loaded = session_manager._load_session("test-session")

            assert loaded.created_at.tzinfo is not None, (
                "加载后的 created_at 应为 aware datetime"
            )
            assert loaded.updated_at.tzinfo is not None, (
                "加载后的 updated_at 应为 aware datetime"
            )
            # 时间值应一致（ISO 格式序列化后可能损失微秒精度，用秒级比较）
            assert loaded.created_at.replace(microsecond=0) == original_created_at.replace(microsecond=0)
            assert loaded.updated_at.replace(microsecond=0) == original_updated_at.replace(microsecond=0)

    def test_saved_metadata_contains_utc_isoformat(self, session_manager, temp_session_dir):
        """保存的 metadata 行中 created_at/updated_at 应为 UTC ISO 8601 格式"""
        with patch.object(SessionManager, "get_session_path_by_id") as mock_path:
            temp_session_dir.mkdir(parents=True, exist_ok=True)
            session_path = temp_session_dir / "test-session.jsonl"
            mock_path.return_value = session_path

            session = Session(id="test-session")
            session_manager.save_session(session)

            # 读取文件第一行（metadata）
            with open(session_path, encoding="utf-8") as f:
                metadata = json.loads(f.readline())

            created_at_str = metadata["created_at"]
            updated_at_str = metadata["updated_at"]

            # 验证 ISO 格式包含时区后缀（+00:00）
            assert "+00:00" in created_at_str, (
                f"created_at 应包含 UTC 时区后缀 '+00:00'，实际: {created_at_str}"
            )
            assert "+00:00" in updated_at_str, (
                f"updated_at 应包含 UTC 时区后缀 '+00:00'，实际: {updated_at_str}"
            )

    def test_saved_message_timestamp_is_utc_isoformat(self, session_manager, temp_session_dir):
        """保存的消息 timestamp 应为 UTC ISO 8601 格式"""
        with patch.object(SessionManager, "get_session_path_by_id") as mock_path:
            temp_session_dir.mkdir(parents=True, exist_ok=True)
            session_path = temp_session_dir / "test-session.jsonl"
            mock_path.return_value = session_path

            session = Session(id="test-session")
            session.add_message(role="user", content="测试消息")
            session_manager.save_session(session)

            # 读取第二行（第一条消息）
            with open(session_path, encoding="utf-8") as f:
                f.readline()  # skip metadata
                msg_line = f.readline()

            msg = json.loads(msg_line)
            timestamp_str = msg["timestamp"]

            # 验证包含 UTC 时区后缀
            assert "+00:00" in timestamp_str, (
                f"message timestamp 应包含 UTC 时区后缀 '+00:00'，实际: {timestamp_str}"
            )

    def test_load_session_backward_compat_naive_timestamp(self, session_manager, tmp_path):
        """加载旧的 naive 时间戳 session 文件应正常工作

        向后兼容：旧 session 文件中的时间戳是 naive 本地时间，
        迁移后应能正常加载（datetime.fromisoformat 支持解析 naive 字符串）。
        """
        session_path = tmp_path / "old-session.jsonl"
        # 模拟旧格式：naive ISO 时间戳
        metadata = {
            "_type": "metadata",
            "name": "old_session",
            "created_at": "2026-06-01T10:00:00",  # naive，无时区
            "updated_at": "2026-06-01T10:30:00",
            "last_compacted_loc": 0,
            "last_processed_loc": 0,
            "message_len": 1,
        }
        msg = {
            "role": "user",
            "content": "旧消息",
            "timestamp": "2026-06-01T10:00:00",  # naive
        }
        with open(session_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        with patch.object(SessionManager, "get_session_path_by_id", return_value=session_path):
            loaded = session_manager._load_session("old-session")

        # 应能正常加载
        assert loaded is not None
        assert loaded.name == "old_session"
        assert len(loaded.messages) == 1


class TestChatHistoryManagerUtcTimestamps:
    """测试 ChatHistoryManager 的 UTC 时间戳"""

    @pytest.fixture
    def temp_history_file(self, tmp_path):
        return tmp_path / "chat_history.json"

    def test_init_last_processed_time_is_utc_aware(self, temp_history_file):
        """ChatHistoryManager 初始化时 last_processed_time 应为 UTC aware"""
        manager = ChatHistoryManager(temp_history_file)
        assert manager.last_processed_time.tzinfo is not None, (
            "last_processed_time 应为 aware datetime"
        )
        assert manager.last_processed_time.utcoffset() == timedelta(0), (
            "last_processed_time 时区偏移应为 0（UTC）"
        )

    def test_add_content_timestamp_is_utc_iso(self, temp_history_file):
        """add_content() 写入的 timestamp 应为 UTC ISO 8601 格式"""
        manager = ChatHistoryManager(temp_history_file)
        manager.add_content("测试内容")

        timestamp_str = manager.histories[-1]["timestamp"]
        dt = datetime.fromisoformat(timestamp_str)

        assert dt.tzinfo is not None, (
            f"history item timestamp 应为 aware datetime，实际: {timestamp_str}"
        )
        assert dt.utcoffset() == timedelta(0), (
            f"history item timestamp 时区偏移应为 0（UTC），实际: {timestamp_str}"
        )

    def test_save_history_writes_utc_isoformat(self, temp_history_file):
        """save_history() 写入文件的 last_processed_time 应为 UTC ISO 格式"""
        manager = ChatHistoryManager(temp_history_file)
        manager.add_content("测试内容")
        manager.save_history()

        with open(temp_history_file, encoding="utf-8") as f:
            metadata = json.loads(f.readline())

        last_processed_str = metadata["last_processed_time"]
        assert "+00:00" in last_processed_str, (
            f"last_processed_time 应包含 UTC 时区后缀，实际: {last_processed_str}"
        )

    def test_load_backward_compat_naive_timestamp(self, temp_history_file):
        """加载旧的 naive 时间戳 chat_history 文件应正常工作

        向后兼容：旧文件中的 last_processed_time 是 naive，
        迁移后应能正常加载，不会因 naive/aware 比较出错。
        """
        # 创建旧格式文件
        metadata = {
            "_type": "metadata",
            "last_processed_time": "2026-06-01T10:00:00",  # naive
        }
        old_entry = {
            "timestamp": "2026-06-01T10:30:00",  # naive
            "content": "旧记录",
        }
        with open(temp_history_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            f.write(json.dumps(old_entry, ensure_ascii=False) + "\n")

        # 应能正常加载，不抛出异常
        manager = ChatHistoryManager(temp_history_file)
        assert len(manager.histories) == 1
        assert manager.histories[0]["content"] == "旧记录"

    def test_get_histories_to_dream_mixed_naive_and_aware(self, temp_history_file):
        """get_histories_to_dream 应能处理混合 naive/aware 时间戳

        向后兼容场景：旧记录是 naive，新记录是 aware，
        比较时不应抛出 TypeError。
        """
        manager = ChatHistoryManager(temp_history_file)
        # 模拟加载旧记录（naive）
        manager.histories = [
            {"timestamp": "2026-06-01T10:00:00", "content": "旧记录"},  # naive
        ]
        # last_processed_time 设为 aware UTC
        manager.last_processed_time = datetime.now(timezone.utc) - timedelta(days=1)

        # 应能正常比较，不抛出 TypeError
        # 注意：旧记录的 naive 时间戳会被 fromisoformat 解析为 naive datetime
        # 与 aware last_processed_time 比较会抛出 TypeError
        # 迁移后需要处理这种情况（naive 视为 UTC）
        try:
            result = manager.get_histories_to_dream()
            # 如果没有抛出 TypeError，说明处理了 naive/aware 兼容
        except TypeError as e:
            pytest.fail(
                f"get_histories_to_dream 不应因 naive/aware datetime 比较抛出 TypeError: {e}"
            )
