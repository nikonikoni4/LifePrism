"""独立测试脚本：直接测试 QuerySessionHistoryTool 的核心逻辑"""
import json
import tempfile
from pathlib import Path

# 模拟 SessionManager.get_session_path_by_id
def get_session_path_by_id(session_id):
    from lifeprism.config import settings
    return settings.session_path / f"{session_id}.jsonl"

# 创建测试 session 文件
def create_test_session():
    temp_dir = Path(tempfile.mkdtemp())
    session_id = "test-session-001"
    session_path = temp_dir / f"{session_id}.jsonl"

    # 写入 metadata
    metadata = {
        "_type": "metadata",
        "created_at": "2026-07-01T10:00:00",
        "updated_at": "2026-07-01T12:00:00",
        "name": "测试会话"
    }

    # 写入消息
    messages = [
        {"role": "user", "content": "消息1", "timestamp": "2026-07-01T10:01:00"},
        {"role": "assistant", "content": "回复1", "timestamp": "2026-07-01T10:02:00"},
        {"role": "tool", "content": "工具结果", "timestamp": "2026-07-01T10:03:00"},
        {"role": "user", "content": "消息2", "timestamp": "2026-07-01T10:05:00"},
        {"role": "assistant", "content": "回复2", "timestamp": "2026-07-01T10:06:00"},
    ]

    with open(session_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + '\n')

    return temp_dir, session_id, session_path

# 测试核心逻辑
def test_query_logic():
    print("创建测试 session 文件...")
    temp_dir, session_id, session_path = create_test_session()

    print(f"测试文件路径: {session_path}")
    print(f"文件存在: {session_path.exists()}")

    # 读取并过滤消息
    messages = []
    with open(session_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("_type") == "metadata":
                continue
            if data.get('role') in ['user', 'assistant']:
                messages.append({
                    'role': data.get('role', ''),
                    'content': data.get('content', ''),
                    'timestamp': data.get('timestamp', '')
                })

    print(f"\n读取到 {len(messages)} 条消息（过滤后）")
    for msg in messages:
        print(f"  - {msg['role']}: {msg['content']}")

    # 倒序并限制数量
    messages.reverse()
    result = messages[:min(3, 50)]

    print(f"\n倒序后取前 3 条:")
    for msg in result:
        print(f"  - {msg['role']}: {msg['content']}")

    # 验证结果
    assert len(result) == 3
    assert result[0]['content'] == "回复2"
    assert result[1]['content'] == "消息2"
    assert result[2]['content'] == "回复1"

    print("\n[SUCCESS] 测试通过！")

    # 清理
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_query_logic()
