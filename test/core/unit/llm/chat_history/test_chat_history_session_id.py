"""ChatHistoryManager session_id 功能测试

测试 ChatHistoryManager 对 session_id 字段的支持：
- add_content() 方法增加了 session_id 参数
- 保存时正确写入 session_id
- 向后兼容（不传 session_id 时不写入该字段）
"""
import pytest
import shutil
import json
from lifeprism.llm.session.manager import ChatHistoryManager
from pathlib import Path
from datetime import datetime


@pytest.mark.core
class TestChatHistoryManagerSessionId:
    """测试 ChatHistoryManager 的 session_id 功能"""

    @pytest.fixture
    def temp_history_file(self, tmp_path):
        """创建临时的 chat_history.json 路径"""
        history_path = tmp_path / "chat_history.json"
        return history_path

    def test_add_content_with_session_id(self, temp_history_file):
        """测试：add_content() 传入 session_id 后正确保存"""
        manager = ChatHistoryManager(temp_history_file)

        # 添加内容并传入 session_id
        test_content = "用户询问了关于 Python 异步编程的问题"
        test_session_id = "test-session-001"

        manager.add_content(test_content, session_id=test_session_id)
        manager.save_history()

        # 验证文件内容
        assert temp_history_file.exists()

        with open(temp_history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 第一行是 metadata
        assert len(lines) >= 2
        metadata = json.loads(lines[0])
        assert metadata.get('_type') == 'metadata'

        # 第二行是实际内容
        entry = json.loads(lines[1])
        assert entry['content'] == test_content
        assert entry['session_id'] == test_session_id
        assert 'timestamp' in entry

    def test_add_content_without_session_id(self, temp_history_file):
        """测试：add_content() 不传 session_id 时向后兼容（不写入该字段）"""
        manager = ChatHistoryManager(temp_history_file)

        # 添加内容但不传 session_id（向后兼容）
        test_content = "用户询问了关于 React 的问题"

        manager.add_content(test_content)
        manager.save_history()

        # 验证文件内容
        with open(temp_history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 第二行是实际内容
        entry = json.loads(lines[1])
        assert entry['content'] == test_content
        assert 'session_id' not in entry  # 不应该包含 session_id 字段
        assert 'timestamp' in entry

    def test_add_multiple_contents_with_different_sessions(self, temp_history_file):
        """测试：添加多条内容，分别属于不同的 session"""
        manager = ChatHistoryManager(temp_history_file)

        # 添加多条内容
        contents_with_sessions = [
            ("会话1的内容", "session-001"),
            ("会话2的内容", "session-002"),
            ("会话1的另一条内容", "session-001"),
            ("没有session的内容", None),
        ]

        for content, session_id in contents_with_sessions:
            if session_id:
                manager.add_content(content, session_id=session_id)
            else:
                manager.add_content(content)

        manager.save_history()

        # 验证文件内容
        with open(temp_history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 跳过第一行 metadata，验证后续内容
        assert len(lines) == 5  # 1 metadata + 4 entries

        entries = [json.loads(line) for line in lines[1:]]

        # 验证每条内容
        assert entries[0]['content'] == "会话1的内容"
        assert entries[0]['session_id'] == "session-001"

        assert entries[1]['content'] == "会话2的内容"
        assert entries[1]['session_id'] == "session-002"

        assert entries[2]['content'] == "会话1的另一条内容"
        assert entries[2]['session_id'] == "session-001"

        assert entries[3]['content'] == "没有session的内容"
        assert 'session_id' not in entries[3]

    def test_load_existing_history_with_mixed_data(self, temp_history_file):
        """测试：加载包含新旧混合格式的 chat_history.json"""
        # 手动创建一个包含新旧格式的文件
        metadata = {
            "_type": "metadata",
            "last_processed_time": datetime.now().isoformat()
        }

        old_format_entry = {
            "timestamp": "2026-07-01T10:00:00",
            "content": "旧格式的内容（没有 session_id）"
        }

        new_format_entry = {
            "timestamp": "2026-07-02T11:00:00",
            "content": "新格式的内容（有 session_id）",
            "session_id": "session-123"
        }

        with open(temp_history_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
            f.write(json.dumps(old_format_entry, ensure_ascii=False) + '\n')
            f.write(json.dumps(new_format_entry, ensure_ascii=False) + '\n')

        # 加载并验证（构造函数已经调用了 load_histories()）
        manager = ChatHistoryManager(temp_history_file)

        # 验证加载的内容
        assert len(manager.histories) == 2

        # 旧格式记录没有 session_id
        assert manager.histories[0]['content'] == "旧格式的内容（没有 session_id）"
        assert 'session_id' not in manager.histories[0]

        # 新格式记录有 session_id
        assert manager.histories[1]['content'] == "新格式的内容（有 session_id）"
        assert manager.histories[1]['session_id'] == "session-123"

    def test_session_id_none_vs_not_provided(self, temp_history_file):
        """测试：显式传入 None 和不传参数的行为一致"""
        manager = ChatHistoryManager(temp_history_file)

        # 测试显式传入 None
        manager.add_content("测试内容", session_id=None)
        manager.save_history()

        with open(temp_history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        entry = json.loads(lines[1])
        assert 'session_id' not in entry  # None 应该不写入字段
