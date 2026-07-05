"""独立测试脚本：ChatHistoryManager session_id 功能验证

这个脚本可以直接运行，不依赖 pytest，用于验证 ChatHistoryManager 的 session_id 功能。

运行方式：
    python scripts/test_chat_history_session_id.py
"""
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lifeprism.llm.session.manager import ChatHistoryManager


def test_add_content_with_session_id():
    """测试：add_content() 传入 session_id 后正确保存"""
    print("测试 1: 添加内容并传入 session_id")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "chat_history.json"
        manager = ChatHistoryManager(history_path)

        # 添加内容并传入 session_id
        test_content = "用户询问了关于 Python 异步编程的问题"
        test_session_id = "test-session-001"

        manager.add_content(test_content, session_id=test_session_id)
        manager.save_history()

        # 验证文件内容
        assert history_path.exists(), "文件未创建"

        with open(history_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 第一行是 metadata
        assert len(lines) >= 2, "文件内容不完整"
        metadata = json.loads(lines[0])
        assert metadata.get('_type') == 'metadata', "metadata 格式错误"

        # 第二行是实际内容
        entry = json.loads(lines[1])
        assert entry['content'] == test_content, "内容不匹配"
        assert entry['session_id'] == test_session_id, "session_id 不匹配"
        assert 'timestamp' in entry, "缺少 timestamp"

        print("✓ 测试通过：session_id 正确保存")


def test_add_content_without_session_id():
    """测试：add_content() 不传 session_id 时向后兼容"""
    print("\n测试 2: 添加内容但不传 session_id（向后兼容）")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "chat_history.json"
        manager = ChatHistoryManager(history_path)

        # 添加内容但不传 session_id
        test_content = "用户询问了关于 React 的问题"

        manager.add_content(test_content)
        manager.save_history()

        # 验证文件内容
        with open(history_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 第二行是实际内容
        entry = json.loads(lines[1])
        assert entry['content'] == test_content, "内容不匹配"
        assert 'session_id' not in entry, "不应该包含 session_id 字段"
        assert 'timestamp' in entry, "缺少 timestamp"

        print("✓ 测试通过：向后兼容，不写入 session_id")


def test_add_multiple_contents_with_different_sessions():
    """测试：添加多条内容，分别属于不同的 session"""
    print("\n测试 3: 添加多条内容，分别属于不同的 session")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "chat_history.json"
        manager = ChatHistoryManager(history_path)

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
        with open(history_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 跳过第一行 metadata，验证后续内容
        assert len(lines) == 5, f"应该有 5 行（1 metadata + 4 entries），实际有 {len(lines)} 行"

        entries = [json.loads(line) for line in lines[1:]]

        # 验证每条内容
        assert entries[0]['content'] == "会话1的内容", "内容1不匹配"
        assert entries[0]['session_id'] == "session-001", "session_id 1不匹配"

        assert entries[1]['content'] == "会话2的内容", "内容2不匹配"
        assert entries[1]['session_id'] == "session-002", "session_id 2不匹配"

        assert entries[2]['content'] == "会话1的另一条内容", "内容3不匹配"
        assert entries[2]['session_id'] == "session-001", "session_id 3不匹配"

        assert entries[3]['content'] == "没有session的内容", "内容4不匹配"
        assert 'session_id' not in entries[3], "内容4不应该有 session_id"

        print("✓ 测试通过：多个 session 的内容正确保存")


def test_load_existing_history_with_mixed_data():
    """测试：加载包含新旧混合格式的 chat_history.json"""
    print("\n测试 4: 加载包含新旧混合格式的文件")

    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = Path(tmpdir) / "chat_history.json"

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

        with open(history_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
            f.write(json.dumps(old_format_entry, ensure_ascii=False) + '\n')
            f.write(json.dumps(new_format_entry, ensure_ascii=False) + '\n')

        # 加载并验证
        manager = ChatHistoryManager(history_path)
        manager.load_histories()

        # 验证加载的内容
        assert len(manager.histories) == 2, f"应该加载2条记录，实际加载了 {len(manager.histories)} 条"

        # 旧格式记录没有 session_id
        assert manager.histories[0]['content'] == "旧格式的内容（没有 session_id）", "旧格式内容不匹配"
        assert 'session_id' not in manager.histories[0], "旧格式不应该有 session_id"

        # 新格式记录有 session_id
        assert manager.histories[1]['content'] == "新格式的内容（有 session_id）", "新格式内容不匹配"
        assert manager.histories[1]['session_id'] == "session-123", "新格式 session_id 不匹配"

        print("✓ 测试通过：新旧混合格式正确加载")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("ChatHistoryManager session_id 功能测试")
    print("=" * 60)

    try:
        test_add_content_with_session_id()
        test_add_content_without_session_id()
        test_add_multiple_contents_with_different_sessions()
        test_load_existing_history_with_mixed_data()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ 测试失败：{e}")
        return 1
    except Exception as e:
        print(f"\n✗ 测试出错：{e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
