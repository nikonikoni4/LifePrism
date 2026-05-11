"""
手动测试 auto_compact 功能
使用真实的 LLM 调用来压缩 session
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import shutil
from lifeprism.llm.agent.loop import AgentLoop
from lifeprism.llm.session import session_manager
from lifeprism.llm.bus import MessageQueue


async def main():
    # 从 compact_test_meta_data.jsonl 复制数据到 compact_test.jsonl
    session_dir = Path(project_root) / "localData" / "session"
    source_file = session_dir / "compact_test_meta_data.jsonl"
    target_file = session_dir / "compact_test.jsonl"
    
    if source_file.exists():
        shutil.copy2(source_file, target_file)
        print(f"已从 {source_file.name} 复制数据到 {target_file.name}")
    else:
        print(f"源文件不存在: {source_file}")
        return
    
    # 加载指定的 session
    session_id = "compact_test"
    print(f"加载 session: {session_id}")

    session = session_manager.get_or_create_session(session_id)

    print(f"\n原始 session 信息:")
    print(f"  消息数量: {len(session.messages)}")
    print(f"  last_compacted_loc: {session.last_compacted_loc}")
    print(f"  auto_compact: {session.auto_compact}")

    # 显示前3条和后3条消息
    print(f"\n前3条消息:")
    for i, msg in enumerate(session.messages[:3]):
        content = msg['content'][:100] if isinstance(msg['content'], str) else str(msg['content'])[:100]
        print(f"  [{i}] {msg['role']}: {content}...")

    print(f"\n后3条消息:")
    for i, msg in enumerate(session.messages[-3:], start=len(session.messages)-3):
        content = msg['content'][:100] if isinstance(msg['content'], str) else str(msg['content'])[:100]
        print(f"  [{i}] {msg['role']}: {content}...")

    # 创建 AgentLoop 实例
    bus = MessageQueue()
    agent_loop = AgentLoop(bus)

    # 强制触发压缩（临时修改 token_limit）
    from lifeprism.config import settings
    from lifeprism.llm.utils.helpers import estimate_prompt_tokens

    # 计算当前 token 数量
    current_tokens = estimate_prompt_tokens(session.get_history_message(), [])
    print(f"\n当前 session 的 token 数量: {current_tokens}")
    print(f"当前 token_limit: {settings.token_limit}")

    # 临时设置一个很小的 token_limit 来触发压缩
    print(f"\n临时设置 token_limit 为 100 以触发压缩...")

    # 直接修改 settings 对象的属性
    import types
    original_token_limit_value = settings.token_limit

    # 创建一个新的 property 来覆盖 token_limit
    def get_token_limit(self):
        return 100

    # 保存原始的 token_limit property
    original_token_limit_property = type(settings).token_limit

    # 临时替换为返回 100 的 property
    type(settings).token_limit = property(get_token_limit)

    try:
        # 执行压缩
        print(f"\n开始执行压缩...")
        tools = []

        # 备份原始消息数量
        original_message_count = len(session.messages)

        result_session = await agent_loop.auto_compact(session, tools)

        print(f"\n压缩完成!")
        print(f"\n压缩后 session 信息:")
        print(f"  消息数量: {len(result_session.messages)} (原始: {original_message_count})")
        print(f"  last_compacted_loc: {result_session.last_compacted_loc}")
        print(f"  新增消息数: {len(result_session.messages) - original_message_count}")

        # 显示压缩后添加的消息
        print(result_session.get_history_message())

        # 测试 get_history_message
        result_session.auto_compact = True
        history = result_session.get_history_message()
        print(f"\n启用 auto_compact 后，get_history_message() 返回 {len(history)} 条消息")
        print(f"  (应该从位置 {result_session.last_compacted_loc} 开始)")

    finally:
        # 恢复原始 token_limit
        type(settings).token_limit = original_token_limit_property
        print(f"\n恢复 token_limit 为 {settings.token_limit}")

        # 清除缓存，避免保存修改
        if session_id in session_manager._cache:
            del session_manager._cache[session_id]
        print(f"已清除 session 缓存，不会保存修改")


if __name__ == "__main__":
    asyncio.run(main())
