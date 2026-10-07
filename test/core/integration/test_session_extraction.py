"""聊天会话待处理轮次提取（``runtime.chat_sessions.process_pending``）契约测试。

覆盖：首次提取成功并落盘、重复调用不重复触发；handler 失败不推进；
``meta.extra`` 其他自定义键保留；真实内核继续一轮后只提取新消息；
提取期间对同一会话发起新轮次被拒绝。

用法契约（被测对象尚未实现时，访问 ``process_pending`` 会以 ``AttributeError``
呈现预期 RED）::

    runtime.chat_sessions.process_pending(session_id, handler) -> bool

    handler: async (messages, start_turn, end_turn) -> None
      - messages: 本次窗口的聊天投影（仅 user 与每轮最终 assistant，隐藏工具步骤）
      - start_turn: 窗口起始轮次，等于上次已处理轮次 + 1
      - end_turn: 会话当前最大已结束（存在 ``turn/end`` 记录）的轮次

语义：
  - 仅当存在 ``end_turn >= start_turn`` 的新已结束轮次时调用 handler 并返回 True；
    成功后把 ``end_turn`` 写入落盘 ``meta.extra.last_processed_turn``；
  - 没有新轮次时返回 False，且不调用 handler（幂等）；
  - handler 抛错时异常向调用方传播，且不推进 ``last_processed_turn``；
  - 处理期间预留会话，handler 内对同一会话发起新轮次被拒绝。
"""

import asyncio
import json

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.llm.bus import InboundMessage, MessageType

pytestmark = pytest.mark.core


def _chat_file(tmp_path, session_id):
    """返回统一聊天目录下的会话文件路径。"""
    return tmp_path / "sessions" / "chat" / f"{session_id}.jsonl"


def _read_meta(tmp_path, session_id):
    """读取落盘 JSONL 首行的会话元信息。"""
    lines = _chat_file(tmp_path, session_id).read_text(encoding="utf-8").splitlines()
    return json.loads(lines[0])


def _edit_meta(path, mutate):
    """就地改写落盘 meta 行，保留其后的记录行内容。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = json.loads(lines[0])
    mutate(meta)
    lines[0] = json.dumps(meta, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def _new_chat(runtime, content="first"):
    """执行一轮聊天并返回新建会话的原生 id。"""
    result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content=content))
    return result.session_id


def test_process_pending_advances_once_and_skips_repeat(tmp_path):
    """守护首次提取调用 handler 并把已处理轮次落盘，重复调用不再触发。"""

    async def scenario():
        """在 `asyncio.run` 下驱动首次提取与重复提取场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        calls = []

        async def handler(messages, start_turn, end_turn):
            """记录本次窗口，验证投影形态后返回 None。"""
            calls.append((messages, start_turn, end_turn))

        try:
            sid = await _new_chat(runtime)
            assert await runtime.chat_sessions.process_pending(sid, handler) is True

            messages, start_turn, end_turn = calls[0]
            assert (start_turn, end_turn) == (1, 1)
            assert [m["role"] for m in messages] == ["user", "assistant"]
            assert "first" in messages[0]["content"]

            # 已处理轮次写入落盘 meta.extra，而不是只留在内存
            assert _read_meta(tmp_path, sid)["extra"]["last_processed_turn"] == 1

            # 没有新的已结束轮次：返回 False 且不再调用 handler
            assert await runtime.chat_sessions.process_pending(sid, handler) is False
            assert len(calls) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_process_pending_keeps_other_extra_keys(tmp_path):
    """守护落盘 metadata 的既有自定义键在提取后原样保留。"""

    async def scenario():
        """在 `asyncio.run` 下驱动自定义 extra 键保留场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            sid = await _new_chat(runtime)
        finally:
            await runtime.close()

        # 缓存已释放，直接改写落盘 metadata 注入调用方自定义键
        path = _chat_file(tmp_path, sid)
        _edit_meta(path, lambda meta: meta["extra"].update({"existing_key": "keep-me"}))

        async def handler(messages, start_turn, end_turn):
            """不做任何事，仅占位。"""
            return None

        resumed = make_runtime(tmp_path, FakeClient())
        try:
            assert await resumed.chat_sessions.process_pending(sid, handler) is True
            history = await resumed.chat_sessions.get_history(sid)
        finally:
            await resumed.close()

        # 元信息改写不得损坏其后的记录
        assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
        persisted = _read_meta(tmp_path, sid)["extra"]
        assert persisted["existing_key"] == "keep-me"
        assert persisted["last_processed_turn"] == 1

    asyncio.run(scenario())


def test_process_pending_does_not_advance_when_handler_fails(tmp_path):
    """守护 handler 抛错时异常上抛、不推进已处理轮次，且下一次可重试。"""

    async def scenario():
        """在 `asyncio.run` 下驱动 handler 失败与重试场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        attempts = []

        async def exploding(messages, start_turn, end_turn):
            """记录窗口后抛出错误，模拟处理失败。"""
            attempts.append((start_turn, end_turn))
            raise RuntimeError("handler boom")

        async def succeeding(messages, start_turn, end_turn):
            """记录窗口并正常返回。"""
            attempts.append((start_turn, end_turn))

        try:
            sid = await _new_chat(runtime)
            with pytest.raises(RuntimeError, match="handler boom"):
                await runtime.chat_sessions.process_pending(sid, exploding)

            # 未推进：失败没有把 last_processed_turn 落盘
            assert "last_processed_turn" not in _read_meta(tmp_path, sid)["extra"]

            # 失败被释放后重试仍能拿到同一窗口
            assert await runtime.chat_sessions.process_pending(sid, succeeding) is True
            assert attempts == [(1, 1), (1, 1)]
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_process_pending_extracts_only_new_turn_messages(tmp_path):
    """守护真实内核继续一轮后，提取窗口只覆盖新增轮次的消息。"""

    async def scenario():
        """在 `asyncio.run` 下驱动多轮增量提取场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        windows = []

        async def handler(messages, start_turn, end_turn):
            """按顺序记录每次提取的窗口。"""
            windows.append((messages, start_turn, end_turn))

        try:
            sid = await _new_chat(runtime, "first")
            assert await runtime.chat_sessions.process_pending(sid, handler) is True

            # 真实内核在同一会话上继续一轮
            await runtime.execute(
                InboundMessage(type=MessageType.CHAT, content="second", session_id=sid)
            )
            assert await runtime.chat_sessions.process_pending(sid, handler) is True

            first_messages, first_start, first_end = windows[0]
            second_messages, second_start, second_end = windows[1]
            assert (first_start, first_end) == (1, 1)
            assert (second_start, second_end) == (2, 2)

            # 第二轮窗口只含第二轮，不重复第一轮的消息
            assert [m["role"] for m in second_messages] == ["user", "assistant"]
            assert len(second_messages) == 2
            assert "second" in second_messages[0]["content"]
            assert all("first" not in m["content"] for m in second_messages)

            # 两轮窗口累计覆盖全部消息，无遗漏无重叠
            assert len(first_messages) + len(second_messages) == 4
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_process_pending_rejects_new_turn_during_handler(tmp_path):
    """守护提取期间预留会话，handler 内对同一会话发起新轮次被拒绝。"""

    async def scenario():
        """在 `asyncio.run` 下驱动处理期间发起新轮次场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        ran = []

        async def handler(messages, start_turn, end_turn):
            """在处理中尝试对同一会话发起新请求，必须被拒绝。"""
            with pytest.raises(RuntimeError, match="管理"):
                await runtime.execute(
                    InboundMessage(type=MessageType.CHAT, content="intrude", session_id=sid)
                )
            ran.append((start_turn, end_turn))

        try:
            sid = await _new_chat(runtime)
            assert await runtime.chat_sessions.process_pending(sid, handler) is True
            assert ran == [(1, 1)]
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_unfinished_turn_is_not_extracted(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        sid = await _new_chat(runtime)
        await runtime.close()
        path = _chat_file(tmp_path, sid)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows = [row for row in rows if row.get("type") != "turn/end"]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        calls = []

        async def handler(messages, start, end):
            calls.append(messages)

        resumed = make_runtime(tmp_path, FakeClient())
        assert not await resumed.chat_sessions.process_pending(sid, handler)
        assert calls == []
        assert "last_processed_turn" not in _read_meta(tmp_path, sid)["extra"]
        await resumed.close()

    asyncio.run(scenario())


def test_crashed_middle_turn_is_included_before_advancing(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        sid = await _new_chat(runtime, "crashed turn")
        await runtime.execute(
            InboundMessage(type=MessageType.CHAT, content="next turn", session_id=sid)
        )
        await runtime.close()
        path = _chat_file(tmp_path, sid)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows = [row for row in rows if not (row.get("type") == "turn/end" and row.get("turn") == 1)]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        windows = []

        async def handler(messages, start, end):
            windows.append(messages)

        resumed = make_runtime(tmp_path, FakeClient())
        assert await resumed.chat_sessions.process_pending(sid, handler)
        assert any("crashed turn" in m["content"] for m in windows[0])
        assert _read_meta(tmp_path, sid)["extra"]["last_processed_turn"] == 2
        await resumed.close()

    asyncio.run(scenario())
