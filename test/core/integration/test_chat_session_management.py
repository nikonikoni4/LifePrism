"""聊天会话管理（``runtime.chat_sessions``）的统一 chat/ 目录契约测试。

覆盖列表、历史投影、改名、永久删除与生命周期约束。管理器只处理统一
``chat/<session_id>.jsonl``；工作流会话不属于其职责范围。

用法契约（被测对象尚未实现时，整体以 ``AttributeError`` 呈现预期 RED）::

    runtime.chat_sessions.list_sessions(page=1, page_size=20) -> dict
    runtime.chat_sessions.get_history(session_id) -> dict | None
    runtime.chat_sessions.rename(session_id, name) -> None
    runtime.chat_sessions.delete(session_id) -> bool
"""

import asyncio
import contextlib
import json
from datetime import datetime
from uuid import uuid4

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.llm.bus import InboundMessage, MessageType

pytestmark = pytest.mark.core

ITEM_KEYS = {"id", "name", "created_at", "updated_at", "message_count", "is_running"}
HISTORY_KEYS = {"session_id", "session_name", "messages"}
MESSAGE_KEYS = {"role", "content", "timestamp"}


def _chat_file(tmp_path, session_id):
    """返回统一聊天目录下的会话文件路径。"""
    return tmp_path / "sessions" / "chat" / f"{session_id}.jsonl"


def _read_jsonl(path):
    """按行解析 JSONL，供断言文件未被损坏。"""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


async def _new_chat(runtime, content="hi"):
    """执行一轮聊天并返回新建会话的原生 id。"""
    result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content=content))
    return result.session_id


async def _drain(runtime, session_id, content="queued"):
    """在指定会话上消费整条事件流，用于占住该会话的锁。"""
    return [
        event
        async for event in runtime.stream(
            InboundMessage(type=MessageType.CHAT, content=content, session_id=session_id)
        )
    ]


def test_list_sessions_includes_only_chat_and_exposes_required_fields(tmp_path):
    """守护列表只包含统一 chat/ 会话，且条目字段完整、可比较。"""

    async def scenario():
        """在 `asyncio.run` 下驱动列表场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            chat_id = await _new_chat(runtime, "chat session")
            workflow = await runtime.execute(
                InboundMessage(
                    type=MessageType.GENERAL_TASK,
                    workflow_id="daily-memory",
                    content="workflow job",
                )
            )
            page = await runtime.chat_sessions.list_sessions()
            assert page["total"] == 1
            assert [item["id"] for item in page["items"]] == [chat_id]

            item = page["items"][0]
            assert ITEM_KEYS <= set(item)
            assert item["is_running"] is False
            assert isinstance(item["message_count"], int) and item["message_count"] >= 2
            assert isinstance(item["name"], str) and item["name"]
            # 时间戳对外是可直接解析的 ISO 8601 字符串
            for key in ("created_at", "updated_at"):
                assert isinstance(item[key], str) and item[key]
                datetime.fromisoformat(item[key])

            # 工作流会话不属于聊天管理器，不能按 chat 历史读取
            assert await runtime.chat_sessions.get_history(workflow.session_id) is None
            assert not _chat_file(tmp_path, workflow.session_id).exists()
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_history_keeps_user_and_final_answer_without_tool_intermediates(tmp_path):
    """守护历史投影保留完整 user/assistant，且工具中间消息不重复最终回答。"""

    async def scenario():
        """在 `asyncio.run` 下驱动工具轮次的历史场景。"""
        runtime = make_runtime(tmp_path, FakeClient(with_tool=True))
        try:
            sid = await _new_chat(runtime, "请回答")
            history = await runtime.chat_sessions.get_history(sid)
            assert HISTORY_KEYS <= set(history)
            assert history["session_id"] == sid
            assert isinstance(history["session_name"], str) and history["session_name"]

            messages = history["messages"]
            assert [m["role"] for m in messages] == ["user", "assistant"]
            for message in messages:
                assert MESSAGE_KEYS <= set(message)
                # content 必须归一化为字符串，而不是多模态块列表
                assert isinstance(message["content"], str)
                datetime.fromisoformat(message["timestamp"])
            assert "请回答" in messages[0]["content"]
            # 中间工具轮次（"checking"）不进入历史，最终回答只出现一次
            assert [m["content"] for m in messages if m["role"] == "assistant"] == ["hello"]
            assert all("checking" not in m["content"] for m in messages)
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_rename_persists_unicode_long_name_and_keeps_records_intact(tmp_path):
    """守护改名为 Unicode 长名称后重启仍可恢复，且历史记录不被损坏。"""

    long_name = "会话-" + "长名称测试" * 12

    async def scenario():
        """在 `asyncio.run` 下驱动改名与重启场景。"""
        runtime = make_runtime(tmp_path, FakeClient(with_tool=True))
        sid = await _new_chat(runtime, "rename me")
        before = await runtime.chat_sessions.get_history(sid)
        try:
            await runtime.chat_sessions.rename(sid, long_name)
            renamed = await runtime.chat_sessions.get_history(sid)
            assert renamed["session_name"] == long_name
            # 改名只动名称，不改动既有记录
            assert renamed["messages"] == before["messages"]

            # 缓存内继续对话不能把名称写回旧值
            await runtime.execute(
                InboundMessage(type=MessageType.CHAT, content="more", session_id=sid)
            )
        finally:
            await runtime.close()

        resumed = make_runtime(tmp_path, FakeClient())
        try:
            history = await resumed.chat_sessions.get_history(sid)
            assert history["session_name"] == long_name
            assert [m["role"] for m in history["messages"]] == [
                "user",
                "assistant",
                "user",
                "assistant",
            ]
            # 前一轮的完整记录逐字段保留
            assert history["messages"][:2] == before["messages"]
            page = await resumed.chat_sessions.list_sessions()
            assert next(i for i in page["items"] if i["id"] == sid)["name"] == long_name
        finally:
            await resumed.close()

        # 文件仍是合法 JSONL，且名称已落到 meta 行
        lines = _read_jsonl(_chat_file(tmp_path, sid))
        assert lines[0]["name"] == long_name

    asyncio.run(scenario())


def test_delete_releases_idle_cache_removes_file_and_stays_deleted(tmp_path):
    """守护删除空闲会话会释放缓存、移除文件，且后续继续失败不重建。"""

    async def scenario():
        """在 `asyncio.run` 下驱动空闲删除场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            sid = await _new_chat(runtime, "delete me")
            path = _chat_file(tmp_path, sid)
            assert path.is_file()
            assert sid in runtime._slots

            assert await runtime.chat_sessions.delete(sid) is True
            assert sid not in runtime._slots
            assert not path.exists()

            assert await runtime.chat_sessions.get_history(sid) is None
            page = await runtime.chat_sessions.list_sessions()
            assert all(item["id"] != sid for item in page["items"])

            # 继续使用同一 id 应当失败，且不得重建文件
            with pytest.raises(ValueError):
                await runtime.execute(
                    InboundMessage(type=MessageType.CHAT, content="again", session_id=sid)
                )
            assert not path.exists()
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_delete_rejects_running_and_queued_session(tmp_path):
    """守护执行中与排队中的会话都拒绝删除，并在列表中标记为运行中。"""

    async def scenario():
        """在 `asyncio.run` 下驱动运行中/排队拒删场景。"""
        client = FakeClient(block=True)
        runtime = make_runtime(tmp_path, client)
        stream = runtime.stream(InboundMessage(type=MessageType.CHAT, content="hold"))
        queued = None
        try:
            first = await anext(stream)
            sid = first.session_id
            while not client.calls:
                await asyncio.sleep(0)

            # 执行中：拒删
            with pytest.raises(RuntimeError):
                await runtime.chat_sessions.delete(sid)
            page = await runtime.chat_sessions.list_sessions()
            assert next(i for i in page["items"] if i["id"] == sid)["is_running"] is True

            # 排队中：第二个请求阻塞在同一会话的锁上，同样拒删
            queued = asyncio.create_task(_drain(runtime, sid))
            for _ in range(100):
                await asyncio.sleep(0)
            assert not queued.done()
            with pytest.raises(RuntimeError):
                await runtime.chat_sessions.delete(sid)

            # 文件仍在，未被拒删动作破坏
            assert _chat_file(tmp_path, sid).is_file()
        finally:
            if queued is not None:
                queued.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await queued
            await stream.aclose()
            await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "bad_id",
    ["not-a-uuid", "../escape", "../../chat/x", "a/b", "a\\b", "C:escape", "session_20261002"],
)
def test_invalid_session_identifier_is_rejected(tmp_path, bad_id):
    """守护非法 UUID 与路径式标识在读取、改名、删除时一律拒绝。"""

    async def scenario():
        """在 `asyncio.run` 下驱动非法标识场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            with pytest.raises(ValueError):
                await runtime.chat_sessions.get_history(bad_id)
            with pytest.raises(ValueError):
                await runtime.chat_sessions.rename(bad_id, "new name")
            with pytest.raises(ValueError):
                await runtime.chat_sessions.delete(bad_id)
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_missing_session_returns_none_and_false(tmp_path):
    """守护不存在的原生会话：历史返回 None，删除返回 False。"""

    async def scenario():
        """在 `asyncio.run` 下驱动缺失会话场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            missing = str(uuid4())
            assert await runtime.chat_sessions.get_history(missing) is None
            assert await runtime.chat_sessions.delete(missing) is False
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_list_sessions_paginates_with_total(tmp_path):
    """守护分页按页切片，各页不重叠且 total 保持全量。"""

    async def scenario():
        """在 `asyncio.run` 下驱动分页场景。"""
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            created = {await _new_chat(runtime, f"message {index}") for index in range(3)}

            first = await runtime.chat_sessions.list_sessions(page=1, page_size=2)
            second = await runtime.chat_sessions.list_sessions(page=2, page_size=2)
            third = await runtime.chat_sessions.list_sessions(page=3, page_size=2)

            assert first["total"] == 3
            assert second["total"] == 3
            assert third["total"] == 3
            assert len(first["items"]) == 2
            assert len(second["items"]) == 1
            assert third["items"] == []

            ids_first = [item["id"] for item in first["items"]]
            ids_second = [item["id"] for item in second["items"]]
            assert set(ids_first).isdisjoint(ids_second)
            assert set(ids_first) | set(ids_second) == created
            assert all(ITEM_KEYS <= set(item) for item in first["items"] + second["items"])
        finally:
            await runtime.close()

    asyncio.run(scenario())
