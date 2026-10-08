"""微信 /new 必须立即保存可跨重启恢复的原生空会话。"""

import asyncio
import json
from unittest.mock import Mock
from uuid import UUID

import pytest
from myagent.agent.core.session import SessionStore

from lifeprism.llm.runtime import AgentRuntime

pytestmark = pytest.mark.regression


def test_create_chat_without_model_is_saved_and_survives_restart(tmp_path):
    """命令创建不得调用provider、启动worker或写入虚构user轮次。"""

    async def scenario():
        factory = Mock(side_effect=AssertionError("创建空会话不能初始化模型"))
        runtime = AgentRuntime(data_path=tmp_path, client_factory=factory)
        created = await runtime.chat_sessions.create()
        sid = created["session_id"]
        assert str(UUID(sid)) == sid
        path = runtime.chat_session_folder / f"{sid}.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["session_id"] == sid
        assert SessionStore(runtime.chat_session_folder, flat=True).load(sid, tmp_path)
        assert runtime._slots == {}
        factory.assert_not_called()
        await runtime.close()
        restarted = AgentRuntime(data_path=tmp_path, client_factory=factory)
        try:
            assert (await restarted.chat_sessions.get_history(sid))["messages"] == []
            assert (await restarted.chat_sessions.list_sessions())["total"] == 1
        finally:
            await restarted.close()

    asyncio.run(scenario())


def test_date_filter_uses_local_updated_date_and_latest_user_preview(tmp_path, monkeypatch):
    """UTC跨日按用户时区筛选；预览取最新user，不取系统记录或助手。"""
    monkeypatch.setattr("lifeprism.utils.time_utils.get_user_timezone", lambda: "Asia/Shanghai")

    async def scenario():
        runtime = AgentRuntime(data_path=tmp_path)
        created = await runtime.chat_sessions.create()
        sid = created["session_id"]
        path = runtime.chat_session_folder / f"{sid}.jsonl"
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["created_at"] = meta["updated_at"] = "2026-10-07T16:30:00+00:00"
        records = [
            {
                "type": "user/message",
                "turn": 1,
                "timestamp": meta["updated_at"],
                "data": {"message": {"role": "user", "content": "用户最新消息摘要"}},
            },
            {
                "type": "assistant/message",
                "turn": 1,
                "timestamp": meta["updated_at"],
                "data": {"message": {"role": "assistant", "content": "不作为用户摘要"}},
            },
        ]
        path.write_text("\n".join(json.dumps(r) for r in [meta, *records]) + "\n", encoding="utf-8")
        try:
            page = await runtime.chat_sessions.list_sessions(
                date_filter="2026-10-08", include_preview=True
            )
            assert page["total"] == 1
            assert page["items"][0]["preview"] == "用户最新消息摘要"
            assert (await runtime.chat_sessions.list_sessions(date_filter="2026-10-07"))[
                "total"
            ] == 0
            with pytest.raises(ValueError):
                await runtime.chat_sessions.list_sessions(date_filter="2026-02-30")
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_empty_session_write_failure_leaves_no_partial_file(tmp_path, monkeypatch):
    """创建失败不能暴露半个新会话，也不能遗留临时文件。"""
    monkeypatch.setattr(
        "lifeprism.llm.runtime.chat_sessions.os.replace", Mock(side_effect=OSError("disk failed"))
    )

    async def scenario():
        runtime = AgentRuntime(data_path=tmp_path)
        try:
            with pytest.raises(OSError, match="disk failed"):
                await runtime.chat_sessions.create()
            assert list(runtime.chat_session_folder.iterdir()) == []
            assert runtime._slots == {}
        finally:
            await runtime.close()

    asyncio.run(scenario())
