"""QuerySessionHistoryTool 和 QuerySessionListTool 单元测试"""
import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
import sys
import os

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lifeprism.llm.agent.tools.session_query import QuerySessionHistoryTool, QuerySessionListTool
from lifeprism.llm.agent.tools.base import ERROR


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
        monkeypatch.setattr(type(settings), 'session_path', property(lambda self: temp_session_dir))

        session_id = "test-session-001"
        session_path = temp_session_dir / f"{session_id}.jsonl"

        # 写入 metadata
        metadata = {
            "_type": "metadata",
            "created_at": "2026-07-01T10:00:00",
            "updated_at": "2026-07-01T12:00:00",
            "name": "测试会话",
            "last_compacted_loc": 0,
            "last_processed_loc": 0
        }

        # 写入多条消息（包括 user、assistant、tool）
        messages = [
            {
                "role": "user",
                "content": "第一条用户消息",
                "timestamp": "2026-07-01T10:01:00"
            },
            {
                "role": "assistant",
                "content": "第一条助手回复",
                "timestamp": "2026-07-01T10:02:00"
            },
            {
                "role": "tool",
                "content": "工具调用结果",
                "timestamp": "2026-07-01T10:03:00",
                "tool_call_id": "call_123"
            },
            {
                "role": "user",
                "content": "第二条用户消息",
                "timestamp": "2026-07-01T10:05:00"
            },
            {
                "role": "assistant",
                "content": "第二条助手回复",
                "timestamp": "2026-07-01T10:06:00"
            },
            {
                "role": "user",
                "content": "第三条用户消息",
                "timestamp": "2026-07-01T11:00:00"
            },
            {
                "role": "assistant",
                "content": "第三条助手回复",
                "timestamp": "2026-07-01T11:01:00"
            }
        ]

        with open(session_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + '\n')

        return session_id, session_path

    @pytest.mark.asyncio
    async def test_basic_query(self, sample_session_file):
        """测试基本查询功能：返回指定数量的历史消息"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        # 查询最近 3 条
        result = await tool.execute(session_id=session_id, limit=3)

        assert isinstance(result, list)
        assert len(result) == 3
        # 验证返回的是倒序（最新的在前）
        assert result[0]['content'] == "第三条助手回复"
        assert result[1]['content'] == "第三条用户消息"
        assert result[2]['content'] == "第二条助手回复"

    @pytest.mark.asyncio
    async def test_default_limit(self, sample_session_file):
        """测试默认 limit 参数"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        # 不传 limit，应该使用默认值 10
        result = await tool.execute(session_id=session_id)

        assert isinstance(result, list)
        # 实际消息只有 6 条（不包括 tool 消息），所以返回 6 条
        assert len(result) == 6

    @pytest.mark.asyncio
    async def test_limit_validation(self, sample_session_file):
        """测试 limit 参数验证：最大 50"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        # 请求超过 50 条，应该被限制为 50
        result = await tool.execute(session_id=session_id, limit=100)

        assert isinstance(result, list)
        # 实际消息只有 6 条，返回 6 条
        assert len(result) == 6

    @pytest.mark.asyncio
    async def test_filter_tool_messages(self, sample_session_file):
        """测试过滤掉 tool 消息"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        result = await tool.execute(session_id=session_id, limit=10)

        # 验证返回的消息中没有 tool 角色
        for msg in result:
            assert msg['role'] in ['user', 'assistant']
            assert msg['role'] != 'tool'

    @pytest.mark.asyncio
    async def test_session_not_exists(self, temp_session_dir, monkeypatch):
        """测试 session_id 不存在时返回错误消息"""
        from lifeprism.config.settings_manager import settings
        monkeypatch.setattr(type(settings), 'session_path', property(lambda self: temp_session_dir))

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
    async def test_message_format(self, sample_session_file):
        """测试返回消息的格式"""
        session_id, _ = sample_session_file
        tool = QuerySessionHistoryTool()

        result = await tool.execute(session_id=session_id, limit=1)

        assert len(result) == 1
        msg = result[0]
        # 验证必须包含的字段
        assert 'role' in msg
        assert 'content' in msg
        assert 'timestamp' in msg
        # 验证字段类型
        assert isinstance(msg['role'], str)
        assert isinstance(msg['content'], str)
        assert isinstance(msg['timestamp'], str)

    @pytest.mark.asyncio
    async def test_tool_schema(self):
        """测试工具的 schema 定义"""
        tool = QuerySessionHistoryTool()

        assert tool.name == "query_session_history"
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0

        params = tool.parameters
        assert params['type'] == 'object'
        assert 'session_id' in params['properties']
        assert 'limit' in params['properties']
        assert 'session_id' in params['required']
        # 验证 limit 的约束
        assert params['properties']['limit']['minimum'] == 1
        assert params['properties']['limit']['maximum'] == 50
        assert params['properties']['limit']['default'] == 10


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
        monkeypatch.setattr(type(settings), 'session_path', property(lambda self: temp_session_dir))
        monkeypatch.setattr(type(settings), 'lifeprism_data_path', property(lambda self: temp_data_dir))

        # 创建三个 session 文件
        sessions = [
            {
                "id": "session-001",
                "updated_at": "2026-07-01T10:00:00",
                "user_messages": [
                    {"content": "第一个会话的第一条消息", "timestamp": "2026-07-01T09:00:00"},
                    {"content": "第一个会话的第二条消息", "timestamp": "2026-07-01T09:30:00"}
                ]
            },
            {
                "id": "session-002",
                "updated_at": "2026-07-02T14:00:00",
                "user_messages": [
                    {"content": "第二个会话的唯一消息", "timestamp": "2026-07-02T14:00:00"}
                ]
            },
            {
                "id": "session-003",
                "updated_at": "2026-07-03T16:00:00",
                "user_messages": [
                    {"content": [
                        {"type": "text", "text": "多模态消息"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
                    ], "timestamp": "2026-07-03T16:00:00"}
                ]
            }
        ]

        for session in sessions:
            session_path = temp_session_dir / f"{session['id']}.jsonl"
            with open(session_path, 'w', encoding='utf-8') as f:
                # 写入 metadata
                metadata = {
                    "_type": "metadata",
                    "created_at": session["updated_at"],
                    "updated_at": session["updated_at"],
                    "name": f"测试会话 {session['id']}",
                    "last_compacted_loc": 0,
                    "last_processed_loc": 0
                }
                f.write(json.dumps(metadata, ensure_ascii=False) + '\n')

                # 写入用户消息
                for msg in session['user_messages']:
                    user_msg = {
                        "role": "user",
                        "content": msg["content"],
                        "timestamp": msg["timestamp"]
                    }
                    f.write(json.dumps(user_msg, ensure_ascii=False) + '\n')

                # 写入一条 assistant 消息
                assistant_msg = {
                    "role": "assistant",
                    "content": "助手回复",
                    "timestamp": session["updated_at"]
                }
                f.write(json.dumps(assistant_msg, ensure_ascii=False) + '\n')

        # 创建 chat_history.json
        chat_history_dir = temp_data_dir / "user" / "daily_data"
        chat_history_dir.mkdir(parents=True, exist_ok=True)
        chat_history_path = chat_history_dir / "chat_history.json"

        histories = [
            # session-001 的两条总结（取最新的）
            {
                "timestamp": "2026-07-01T09:10:00",
                "content": "session-001 的旧总结",
                "session_id": "session-001"
            },
            {
                "timestamp": "2026-07-01T10:00:00",
                "content": "session-001 的最新总结",
                "session_id": "session-001"
            },
            # session-002 的总结
            {
                "timestamp": "2026-07-02T14:30:00",
                "content": "session-002 的总结",
                "session_id": "session-002"
            },
            # session-003 没有总结
            # 旧数据（没有 session_id）
            {
                "timestamp": "2026-06-30T10:00:00",
                "content": "旧数据没有 session_id"
            }
        ]

        with open(chat_history_path, 'w', encoding='utf-8') as f:
            for history in histories:
                f.write(json.dumps(history, ensure_ascii=False) + '\n')

        return sessions

    @pytest.mark.asyncio
    async def test_basic_query(self, sample_sessions_with_history):
        """测试基本功能：返回格式正确，包含 last_summary 和 last_user_message"""
        tool = QuerySessionListTool()
        result = await tool.execute()

        assert isinstance(result, dict)
        assert len(result) == 3  # 三个 session

        # 验证 session-001
        assert "session-001" in result
        assert result["session-001"]["last_summary"] == "session-001 的最新总结"
        assert result["session-001"]["last_user_message"] == "第一个会话的第二条消息"

        # 验证 session-002
        assert "session-002" in result
        assert result["session-002"]["last_summary"] == "session-002 的总结"
        assert result["session-002"]["last_user_message"] == "第二个会话的唯一消息"

        # 验证 session-003（没有总结）
        assert "session-003" in result
        assert result["session-003"]["last_summary"] == ""
        assert result["session-003"]["last_user_message"] == "多模态消息"

    @pytest.mark.asyncio
    async def test_date_filter(self, sample_sessions_with_history):
        """测试日期过滤：只返回指定日期的 session"""
        tool = QuerySessionListTool()
        result = await tool.execute(date_filter="2026-07-02")

        assert isinstance(result, dict)
        assert len(result) == 1
        assert "session-002" in result
        assert "session-001" not in result
        assert "session-003" not in result

    @pytest.mark.asyncio
    async def test_date_filter_no_match(self, sample_sessions_with_history):
        """测试日期过滤：没有符合条件的 session 时返回空 dict"""
        tool = QuerySessionListTool()
        result = await tool.execute(date_filter="2026-07-10")

        assert isinstance(result, dict)
        assert len(result) == 0

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
        assert isinstance(result, dict)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_empty_session_path(self, temp_session_dir, temp_data_dir, monkeypatch):
        """测试 session_path 不存在时返回空 dict"""
        from lifeprism.config.settings_manager import settings
        non_existent_path = temp_session_dir / "non_existent"
        monkeypatch.setattr(type(settings), 'session_path', property(lambda self: non_existent_path))
        monkeypatch.setattr(type(settings), 'lifeprism_data_path', property(lambda self: temp_data_dir))

        tool = QuerySessionListTool()
        result = await tool.execute()

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_multimodal_content_handling(self, sample_sessions_with_history):
        """测试多模态消息处理：content 为 list 时正确提取文本"""
        tool = QuerySessionListTool()
        result = await tool.execute()

        # 验证 session-003 的多模态消息被正确提取
        assert "session-003" in result
        assert result["session-003"]["last_user_message"] == "多模态消息"

    @pytest.mark.asyncio
    async def test_tool_schema(self):
        """测试工具的 schema 定义"""
        tool = QuerySessionListTool()

        assert tool.name == "query_session_list"
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0

        params = tool.parameters
        assert params['type'] == 'object'
        assert 'date_filter' in params['properties']
        assert params['required'] == []  # date_filter 是可选的

