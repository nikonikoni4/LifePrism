"""QuerySessionHistoryTool 和 QuerySessionListTool 单元测试"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lifeprism.llm.agent.tools.base import ERROR
from lifeprism.llm.agent.tools.session_query import QuerySessionHistoryTool, QuerySessionListTool


@pytest.mark.core
class TestQuerySessionHistoryTool:
    """QuerySessionHistoryTool 测试类"""

    @pytest.fixture
    def temp_session_dir(self):
        """创建临时 session 目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # 清理
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_session_file(self, temp_session_dir, monkeypatch):
        """创建示例 session 文件"""
        from lifeprism.config.settings_manager import settings

        # Mock settings.session_path property
        monkeypatch.setattr(type(settings), "session_path", property(lambda self: temp_session_dir))

        session_id = "test-session-001"
        session_path = temp_session_dir / f"{session_id}.jsonl"

        # 写入 metadata
        metadata = {
            "_type": "metadata",
            "created_at": "2026-07-01T10:00:00",
            "updated_at": "2026-07-01T12:00:00",
            "name": "测试会话",
            "last_compacted_loc": 0,
            "last_processed_loc": 0,
        }

        # 写入多条消息（包括 user、assistant、tool）
        messages = [
            {"role": "user", "content": "第一条用户消息", "timestamp": "2026-07-01T10:01:00"},
            {"role": "assistant", "content": "第一条助手回复", "timestamp": "2026-07-01T10:02:00"},
            {
                "role": "tool",
                "content": "工具调用结果",
                "timestamp": "2026-07-01T10:03:00",
                "tool_call_id": "call_123",
            },
            {"role": "user", "content": "第二条用户消息", "timestamp": "2026-07-01T10:05:00"},
            {"role": "assistant", "content": "第二条助手回复", "timestamp": "2026-07-01T10:06:00"},
            {"role": "user", "content": "第三条用户消息", "timestamp": "2026-07-01T11:00:00"},
            {"role": "assistant", "content": "第三条助手回复", "timestamp": "2026-07-01T11:01:00"},
        ]

        with open(session_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        return session_id, session_path

    @pytest.mark.asyncio
    async def test_basic_query(self, sample_session_file):
        """测试基本查询功能：返回格式化的 Markdown 字符串"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        # 查询最近 3 条
        result = await tool.execute(session_id=session_id, limit=3)

        assert isinstance(result, str)
        # 验证标题格式
        assert f"会话 {session_id[:8]}...{session_id[-8:]}" in result
        assert "最近 3 轮对话" in result
        # 验证包含序号和角色
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result
        assert "用户" in result
        assert "助手" in result
        # 验证内容存在（注意顺序是正序，最早的在前）
        assert "第二条助手回复" in result
        assert "第三条用户消息" in result
        assert "第三条助手回复" in result

    @pytest.mark.asyncio
    async def test_default_limit(self, sample_session_file):
        """测试默认 limit 参数"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        # 不传 limit，应该使用默认值 10
        result = await tool.execute(session_id=session_id)

        assert isinstance(result, str)
        # 验证标题中包含实际返回的消息数量（6 条）
        assert "最近 6 轮对话" in result
        # 验证包含所有 6 条消息的序号
        for i in range(1, 7):
            assert f"[{i}]" in result

    @pytest.mark.asyncio
    async def test_limit_validation(self, sample_session_file):
        """测试 limit 参数验证：最大 50"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        # 请求超过 50 条，应该被限制为 50
        result = await tool.execute(session_id=session_id, limit=100)

        assert isinstance(result, str)
        # 实际消息只有 6 条，返回 6 条
        assert "最近 6 轮对话" in result

    @pytest.mark.asyncio
    async def test_filter_tool_messages(self, sample_session_file):
        """测试过滤掉 tool 消息"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        result = await tool.execute(session_id=session_id, limit=10)

        # 验证返回的字符串中只包含用户和助手的消息，不包含 tool
        assert isinstance(result, str)
        assert "用户" in result
        assert "助手" in result
        # tool 消息应该被过滤掉，不出现在结果中
        assert "工具调用结果" not in result

    @pytest.mark.asyncio
    async def test_session_not_exists(self, temp_session_dir, monkeypatch):
        """测试 session_id 不存在时返回错误消息"""
        from lifeprism.config.settings_manager import settings

        monkeypatch.setattr(type(settings), "session_path", property(lambda self: temp_session_dir))

        tool = QuerySessionHistoryTool()
        result = await tool.execute(session_id="non-existent-session")

        assert isinstance(result, str)
        assert result.startswith(ERROR)
        assert "不存在" in result

    @pytest.mark.asyncio
    async def test_empty_session_id(self):
        """测试空 session_id 参数"""
        tool = QuerySessionHistoryTool()
        result = await tool.execute(session_id="")

        assert isinstance(result, str)
        assert result.startswith(ERROR)
        assert "不能为空" in result

    @pytest.mark.asyncio
    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="UTC")
    async def test_message_format(self, _mock_tz, sample_session_file):
        """测试返回消息的格式：验证时间戳格式为 MM-DD HH:MM"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        result = await tool.execute(session_id=session_id, limit=1)

        assert isinstance(result, str)
        # 验证时间戳格式为 MM-DD HH:MM（UTC 时区下转换前后一致）
        assert "07-01 11:01" in result  # 最新的一条消息时间
        # 验证包含角色标识
        assert "助手" in result

    @pytest.mark.asyncio
    async def test_tool_schema(self):
        """测试工具的 schema 定义"""
        tool = QuerySessionHistoryTool()

        assert tool.name == "query_session_history"
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0

        params = tool.parameters
        assert params["type"] == "object"
        assert "session_id" in params["properties"]
        assert "limit" in params["properties"]
        assert "session_id" in params["required"]
        # 验证 limit 的约束
        assert params["properties"]["limit"]["minimum"] == 1
        assert params["properties"]["limit"]["maximum"] == 50
        assert params["properties"]["limit"]["default"] == 10

    @pytest.mark.asyncio
    async def test_empty_message_handling(self, temp_session_dir, monkeypatch):
        """测试空消息处理：显示 (空消息)"""
        from lifeprism.config.settings_manager import settings

        monkeypatch.setattr(type(settings), "session_path", property(lambda self: temp_session_dir))

        session_id = "test-empty-msg"
        session_path = temp_session_dir / f"{session_id}.jsonl"

        metadata = {
            "_type": "metadata",
            "created_at": "2026-07-01T10:00:00",
            "updated_at": "2026-07-01T10:00:00",
        }
        messages = [
            {"role": "user", "content": "", "timestamp": "2026-07-01T10:01:00"},
            {"role": "assistant", "content": "   ", "timestamp": "2026-07-01T10:02:00"},
        ]

        with open(session_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        tool = QuerySessionHistoryTool()
        result = await tool.execute(session_id=session_id)

        assert "(空消息)" in result
        # 应该出现两次（两条空消息）
        assert result.count("(空消息)") == 2

    @pytest.mark.asyncio
    async def test_long_message_truncation(self, temp_session_dir, monkeypatch):
        """测试长消息截断：超过 100 字符截断为 80 字符 + 省略提示"""
        from lifeprism.config.settings_manager import settings

        monkeypatch.setattr(type(settings), "session_path", property(lambda self: temp_session_dir))

        session_id = "test-long-msg"
        session_path = temp_session_dir / f"{session_id}.jsonl"

        long_content = "这是一条非常长的消息内容" * 20  # 超过 100 字符

        metadata = {
            "_type": "metadata",
            "created_at": "2026-07-01T10:00:00",
            "updated_at": "2026-07-01T10:00:00",
        }
        messages = [{"role": "user", "content": long_content, "timestamp": "2026-07-01T10:01:00"}]

        with open(session_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        tool = QuerySessionHistoryTool()
        result = await tool.execute(session_id=session_id)

        assert "(内容较长，已省略)" in result
        # 验证截断后的内容不超过原始内容
        assert len(result) < len(long_content)

    @pytest.mark.asyncio
    @patch("lifeprism.utils.time_utils.get_user_timezone", return_value="UTC")
    async def test_cross_day_timestamp(self, _mock_tz, temp_session_dir, monkeypatch):
        """测试跨天时间戳：验证日期部分正确显示"""
        from lifeprism.config.settings_manager import settings

        monkeypatch.setattr(type(settings), "session_path", property(lambda self: temp_session_dir))

        session_id = "test-cross-day"
        session_path = temp_session_dir / f"{session_id}.jsonl"

        metadata = {
            "_type": "metadata",
            "created_at": "2026-07-05T10:00:00",
            "updated_at": "2026-07-06T10:00:00",
        }
        messages = [
            {"role": "user", "content": "第一天的消息", "timestamp": "2026-07-05T23:30:00"},
            {"role": "assistant", "content": "第二天的回复", "timestamp": "2026-07-06T00:15:00"},
        ]

        with open(session_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        tool = QuerySessionHistoryTool()
        result = await tool.execute(session_id=session_id)

        # 验证两个不同的日期都出现（UTC 时区下转换前后一致）
        assert "07-05 23:30" in result
        assert "07-06 00:15" in result

    @pytest.mark.asyncio
    async def test_multimodal_content_extraction(self, temp_session_dir, monkeypatch):
        """测试多模态消息内容提取：正确提取文本部分"""
        from lifeprism.config.settings_manager import settings

        monkeypatch.setattr(type(settings), "session_path", property(lambda self: temp_session_dir))

        session_id = "test-multimodal"
        session_path = temp_session_dir / f"{session_id}.jsonl"

        metadata = {
            "_type": "metadata",
            "created_at": "2026-07-01T10:00:00",
            "updated_at": "2026-07-01T10:00:00",
        }
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这是文本部分"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
                ],
                "timestamp": "2026-07-01T10:01:00",
            }
        ]

        with open(session_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        tool = QuerySessionHistoryTool()
        result = await tool.execute(session_id=session_id)

        # 验证提取了文本部分
        assert "这是文本部分" in result
        # 验证不包含图片 URL
        assert "base64" not in result


@pytest.mark.core
class TestQuerySessionListTool:
    """QuerySessionListTool 测试类"""

    @pytest.fixture
    def temp_session_dir(self):
        """创建临时 session 目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # 清理
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def temp_data_dir(self):
        """创建临时数据目录（用于 chat_history.json）"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # 清理
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_sessions_with_history(self, temp_session_dir, temp_data_dir, monkeypatch):
        """创建多个 session 文件和 chat_history.json"""
        from lifeprism.config.settings_manager import settings

        # Mock settings.session_path 和 lifeprism_data_path properties
        monkeypatch.setattr(type(settings), "session_path", property(lambda self: temp_session_dir))
        monkeypatch.setattr(
            type(settings), "lifeprism_data_path", property(lambda self: temp_data_dir)
        )

        # 创建三个 session 文件
        sessions = [
            {
                "id": "session-001",
                "updated_at": "2026-07-01T10:00:00",
                "user_messages": [
                    {"content": "第一个会话的第一条消息", "timestamp": "2026-07-01T09:00:00"},
                    {"content": "第一个会话的第二条消息", "timestamp": "2026-07-01T09:30:00"},
                ],
            },
            {
                "id": "session-002",
                "updated_at": "2026-07-02T14:00:00",
                "user_messages": [
                    {"content": "第二个会话的唯一消息", "timestamp": "2026-07-02T14:00:00"}
                ],
            },
            {
                "id": "session-003",
                "updated_at": "2026-07-03T16:00:00",
                "user_messages": [
                    {
                        "content": [
                            {"type": "text", "text": "多模态消息"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64,..."},
                            },
                        ],
                        "timestamp": "2026-07-03T16:00:00",
                    }
                ],
            },
        ]

        for session in sessions:
            session_path = temp_session_dir / f"{session['id']}.jsonl"
            with open(session_path, "w", encoding="utf-8") as f:
                # 写入 metadata
                metadata = {
                    "_type": "metadata",
                    "created_at": session["updated_at"],
                    "updated_at": session["updated_at"],
                    "name": f"测试会话 {session['id']}",
                    "last_compacted_loc": 0,
                    "last_processed_loc": 0,
                }
                f.write(json.dumps(metadata, ensure_ascii=False) + "\n")

                # 写入用户消息
                for msg in session["user_messages"]:
                    user_msg = {
                        "role": "user",
                        "content": msg["content"],
                        "timestamp": msg["timestamp"],
                    }
                    f.write(json.dumps(user_msg, ensure_ascii=False) + "\n")

                # 写入一条 assistant 消息
                assistant_msg = {
                    "role": "assistant",
                    "content": "助手回复",
                    "timestamp": session["updated_at"],
                }
                f.write(json.dumps(assistant_msg, ensure_ascii=False) + "\n")

        # 创建 chat_history.json
        chat_history_dir = temp_data_dir / "user" / "daily_data"
        chat_history_dir.mkdir(parents=True, exist_ok=True)
        chat_history_path = chat_history_dir / "chat_history.json"

        histories = [
            # session-001 的两条总结（取最新的）
            {
                "timestamp": "2026-07-01T09:10:00",
                "content": "session-001 的旧总结",
                "session_id": "session-001",
            },
            {
                "timestamp": "2026-07-01T10:00:00",
                "content": "session-001 的最新总结",
                "session_id": "session-001",
            },
            # session-002 的总结
            {
                "timestamp": "2026-07-02T14:30:00",
                "content": "session-002 的总结",
                "session_id": "session-002",
            },
            # session-003 没有总结
            # 旧数据（没有 session_id）
            {"timestamp": "2026-06-30T10:00:00", "content": "旧数据没有 session_id"},
        ]

        with open(chat_history_path, "w", encoding="utf-8") as f:
            for history in histories:
                f.write(json.dumps(history, ensure_ascii=False) + "\n")

        return sessions

    @pytest.mark.asyncio
    async def test_basic_query(self, sample_sessions_with_history):
        """测试基本功能：返回 JSON 字符串，包含 last_summary 和 last_user_message"""
        tool = QuerySessionListTool()
        result = await tool.execute()

        assert isinstance(result, str)
        # 解析 JSON
        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == 3  # 三个 session

        # 验证 session-001
        assert "session-001" in data
        assert data["session-001"]["last_summary"] == "session-001 的最新总结"
        assert data["session-001"]["last_user_message"] == "第一个会话的第二条消息"

        # 验证 session-002
        assert "session-002" in data
        assert data["session-002"]["last_summary"] == "session-002 的总结"
        assert data["session-002"]["last_user_message"] == "第二个会话的唯一消息"

        # 验证 session-003（没有总结）
        assert "session-003" in data
        assert data["session-003"]["last_summary"] == ""
        assert data["session-003"]["last_user_message"] == "多模态消息"

    @pytest.mark.asyncio
    async def test_date_filter(self, sample_sessions_with_history):
        """测试日期过滤：只返回指定日期的 session"""
        tool = QuerySessionListTool()
        result = await tool.execute(date_filter="2026-07-02")

        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == 1
        assert "session-002" in data
        assert "session-001" not in data
        assert "session-003" not in data

    @pytest.mark.asyncio
    async def test_date_filter_no_match(self, sample_sessions_with_history):
        """测试日期过滤：没有符合条件的 session 时返回空 JSON 对象"""
        tool = QuerySessionListTool()
        result = await tool.execute(date_filter="2026-07-10")

        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_invalid_date_format(self, sample_sessions_with_history):
        """测试日期格式错误：返回错误消息"""
        tool = QuerySessionListTool()
        result = await tool.execute(date_filter="2026/07/01")

        assert isinstance(result, str)
        assert result.startswith(ERROR)
        assert "日期格式错误" in result

    @pytest.mark.asyncio
    async def test_compatibility_with_old_data(self, sample_sessions_with_history):
        """测试兼容旧数据：chat_history.json 中没有 session_id 的记录不影响查询"""
        tool = QuerySessionListTool()
        result = await tool.execute()

        # 验证查询成功，且返回了三个 session（旧数据被跳过）
        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_empty_session_path(self, temp_session_dir, temp_data_dir, monkeypatch):
        """测试 session_path 不存在时返回空 JSON 对象"""
        from lifeprism.config.settings_manager import settings

        non_existent_path = temp_session_dir / "non_existent"
        monkeypatch.setattr(
            type(settings), "session_path", property(lambda self: non_existent_path)
        )
        monkeypatch.setattr(
            type(settings), "lifeprism_data_path", property(lambda self: temp_data_dir)
        )

        tool = QuerySessionListTool()
        result = await tool.execute()

        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_multimodal_content_handling(self, sample_sessions_with_history):
        """测试多模态消息处理：content 为 list 时正确提取文本"""
        tool = QuerySessionListTool()
        result = await tool.execute()

        # 验证 session-003 的多模态消息被正确提取
        assert isinstance(result, str)
        data = json.loads(result)
        assert "session-003" in data
        assert data["session-003"]["last_user_message"] == "多模态消息"

    @pytest.mark.asyncio
    async def test_tool_schema(self):
        """测试工具的 schema 定义"""
        tool = QuerySessionListTool()

        assert tool.name == "query_session_list"
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0

        params = tool.parameters
        assert params["type"] == "object"
        assert "date_filter" in params["properties"]
        assert params["required"] == []  # date_filter 是可选的
