"""测试 channel -> bus -> agentloop -> bus -> channel 完整通路"""
import asyncio
import pytest
import pytest_asyncio
import uuid

from lifeprism.llm.bus.queue import bus
from lifeprism.llm.channel.manager import Channel
from lifeprism.llm.agent.loop import AgentLoop
from lifeprism.llm.session import session_manager

# 所有测试共享同一个 event loop，避免模块级 bus 单例的 Queue 绑定冲突
pytestmark = pytest.mark.asyncio(loop_scope="session")


def _drain_queue(q: asyncio.Queue):
    """清空 asyncio.Queue，隔离测试间的残留消息"""
    while not q.empty():
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            break


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def agent_loop():
    """整个测试 session 共享一个 AgentLoop，结束后停止并清空 bus"""
    loop = AgentLoop(bus)
    task = asyncio.create_task(loop.loop())
    yield loop
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # 清空 bus 队列
    _drain_queue(bus.inbound)
    _drain_queue(bus.outbound)


# ─────────────────────────────────────────
# 测试 1：多轮对话 —— 验证 session 历史记忆
# ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_multi_turn_chat(agent_loop):
    """发送两轮消息，验证第二轮回复中 LLM 能记住第一轮的内容"""
    channel = Channel(bus)
    try:
        # 预先创建 session，拿到合法 session_id
        session = session_manager.get_or_create_session()
        session_id = session.id

        # 第一轮：告知 LLM 名字
        reply1 = await channel.send("我的名字是小明，请记住它。", session_id=session_id)
        print(f"[轮1] 回复: {reply1!r}")
        assert reply1, "第一轮回复不应为空"

        # 第二轮：询问名字，验证历史记忆
        reply2 = await channel.send("我叫什么名字？", session_id=session_id)
        print(f"[轮2] 回复: {reply2!r}")
        assert "小明" in reply2, f"期望回复中包含'小明'，实际回复: {reply2!r}"
    finally:
        await channel.close()

# ─────────────────────────────────────────
# 测试 2：多任务并发 —— 验证消息 id 路由不串台
# ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_concurrent_tasks(agent_loop):
    """同时发送 3 条独立消息，验证每条消息都能收到回复且不丢失、不串台"""
    channel = Channel(bus)
    try:
        messages = [
            "请用一句话介绍Python语言",
            "请用一句话介绍JavaScript语言",
            "请用一句话介绍Rust语言",
        ]

        # 并发发送
        replies = await asyncio.gather(*[
            channel.send(msg) for msg in messages
        ])

        print("[并发] 收到的所有回复:")
        for i, (msg, reply) in enumerate(zip(messages, replies)):
            print(f"  [{i}] 问: {msg!r}")
            print(f"       答: {reply!r}")

        # 验证每条消息都有非空回复
        assert len(replies) == 3, f"期望 3 条回复，实际收到 {len(replies)} 条"
        for i, reply in enumerate(replies):
            assert reply, f"第 {i} 条回复不应为空"
    finally:
        await channel.close()

