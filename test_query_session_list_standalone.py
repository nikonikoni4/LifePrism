"""独立测试 QuerySessionListTool（绕过循环导入）"""
import tempfile
import json
from pathlib import Path
import asyncio

# 创建临时测试环境
def setup_test_environment():
    """创建测试用的临时文件"""
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)

    session_dir = temp_path / "sessions"
    session_dir.mkdir()

    data_dir = temp_path / "data"
    data_dir.mkdir(parents=True)

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
        session_path = session_dir / f"{session['id']}.jsonl"
        with open(session_path, 'w', encoding='utf-8') as f:
            # metadata
            metadata = {
                "_type": "metadata",
                "created_at": session["updated_at"],
                "updated_at": session["updated_at"],
                "name": f"测试会话 {session['id']}",
                "last_compacted_loc": 0,
                "last_processed_loc": 0
            }
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')

            # user messages
            for msg in session['user_messages']:
                user_msg = {
                    "role": "user",
                    "content": msg["content"],
                    "timestamp": msg["timestamp"]
                }
                f.write(json.dumps(user_msg, ensure_ascii=False) + '\n')

            # assistant message
            assistant_msg = {
                "role": "assistant",
                "content": "助手回复",
                "timestamp": session["updated_at"]
            }
            f.write(json.dumps(assistant_msg, ensure_ascii=False) + '\n')

    # 创建 chat_history.json
    chat_history_dir = data_dir / "user" / "daily_data"
    chat_history_dir.mkdir(parents=True)
    chat_history_path = chat_history_dir / "chat_history.json"

    histories = [
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
        {
            "timestamp": "2026-07-02T14:30:00",
            "content": "session-002 的总结",
            "session_id": "session-002"
        },
        {
            "timestamp": "2026-06-30T10:00:00",
            "content": "旧数据没有 session_id"
        }
    ]

    with open(chat_history_path, 'w', encoding='utf-8') as f:
        for history in histories:
            f.write(json.dumps(history, ensure_ascii=False) + '\n')

    return session_dir, data_dir


async def test_basic_functionality():
    """测试基本功能"""
    print("=" * 60)
    print("测试 1: 基本功能")
    print("=" * 60)

    session_dir, data_dir = setup_test_environment()

    # Mock settings
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from lifeprism.config import settings

    original_session_path = settings.session_path
    original_data_path = settings.lifeprism_data_path

    settings._session_path = session_dir
    settings._lifeprism_data_path = data_dir

    try:
        from lifeprism.llm.agent.tools.session_query import QuerySessionListTool

        tool = QuerySessionListTool()
        result = await tool.execute()

        print(f"✓ 返回类型正确: {type(result).__name__}")
        print(f"✓ 返回结果数: {len(result)}")

        assert isinstance(result, dict), "返回类型应该是 dict"
        assert len(result) == 3, f"应该返回 3 个 session，实际返回 {len(result)}"

        # 验证 session-001
        assert "session-001" in result
        assert result["session-001"]["last_summary"] == "session-001 的最新总结"
        assert result["session-001"]["last_user_message"] == "第一个会话的第二条消息"
        print("✓ session-001 数据正确")

        # 验证 session-002
        assert "session-002" in result
        assert result["session-002"]["last_summary"] == "session-002 的总结"
        assert result["session-002"]["last_user_message"] == "第二个会话的唯一消息"
        print("✓ session-002 数据正确")

        # 验证 session-003（没有总结）
        assert "session-003" in result
        assert result["session-003"]["last_summary"] == ""
        assert result["session-003"]["last_user_message"] == "多模态消息"
        print("✓ session-003 数据正确（多模态消息处理正确）")

        print("\n✅ 测试 1 通过\n")

    finally:
        settings._session_path = original_session_path
        settings._lifeprism_data_path = original_data_path


async def test_date_filter():
    """测试日期过滤"""
    print("=" * 60)
    print("测试 2: 日期过滤")
    print("=" * 60)

    session_dir, data_dir = setup_test_environment()

    from lifeprism.config import settings
    original_session_path = settings.session_path
    original_data_path = settings.lifeprism_data_path

    settings._session_path = session_dir
    settings._lifeprism_data_path = data_dir

    try:
        from lifeprism.llm.agent.tools.session_query import QuerySessionListTool

        tool = QuerySessionListTool()
        result = await tool.execute(date_filter="2026-07-02")

        print(f"✓ 日期过滤结果数: {len(result)}")
        assert len(result) == 1, f"应该返回 1 个 session，实际返回 {len(result)}"
        assert "session-002" in result
        assert "session-001" not in result
        assert "session-003" not in result
        print("✓ 日期过滤正确")

        print("\n✅ 测试 2 通过\n")

    finally:
        settings._session_path = original_session_path
        settings._lifeprism_data_path = original_data_path


async def test_invalid_date():
    """测试无效日期格式"""
    print("=" * 60)
    print("测试 3: 无效日期格式")
    print("=" * 60)

    session_dir, data_dir = setup_test_environment()

    from lifeprism.config import settings
    from lifeprism.llm.agent.tools.base import ERROR

    original_session_path = settings.session_path
    original_data_path = settings.lifeprism_data_path

    settings._session_path = session_dir
    settings._lifeprism_data_path = data_dir

    try:
        from lifeprism.llm.agent.tools.session_query import QuerySessionListTool

        tool = QuerySessionListTool()
        result = await tool.execute(date_filter="2026/07/01")

        assert isinstance(result, str)
        assert result.startswith(ERROR)
        assert "日期格式错误" in result
        print("✓ 日期格式验证正确")

        print("\n✅ 测试 3 通过\n")

    finally:
        settings._session_path = original_session_path
        settings._lifeprism_data_path = original_data_path


async def main():
    """运行所有测试"""
    print("\n开始测试 QuerySessionListTool\n")

    try:
        await test_basic_functionality()
        await test_date_filter()
        await test_invalid_date()

        print("=" * 60)
        print("所有测试通过!")
        print("=" * 60)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
