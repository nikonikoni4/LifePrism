import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.llm.bus import InboundMessage, MessageType
from lifeprism.llm.function import agent_schedule_job as jobs

pytestmark = pytest.mark.core


def test_job_saves_history_before_progress_and_is_incremental(tmp_path, monkeypatch):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="remember me"))
        monkeypatch.setattr(jobs, "settings", SimpleNamespace(lifeprism_data_path=tmp_path))
        monkeypatch.setattr("lifeprism.llm.runtime.agent_runtime", runtime)
        send = AsyncMock(
            return_value=SimpleNamespace(
                error=None, response=SimpleNamespace(content="用户喜欢阅读")
            )
        )
        monkeypatch.setattr(jobs.bus, "send", send)
        monkeypatch.setattr(jobs.llm_call_logger, "log_call", lambda *a, **k: None)
        monkeypatch.setattr(jobs.prompt_loader, "load_prompt", lambda *a, **k: "extract")
        monkeypatch.setattr(jobs, "write_date_md", lambda *a, **k: None)
        await jobs.process_session_message()
        await jobs.process_session_message()
        assert send.await_count == 1
        assert send.call_args.args[0].workflow_id == "chat-extraction"
        path = tmp_path / "user/daily_data/chat_history.json"
        history = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert history[1]["session_id"] == result.session_id
        assert history[1]["start_turn"] == history[1]["end_turn"] == 1
        await runtime.close()

    asyncio.run(scenario())


def test_extraction_failure_keeps_progress_for_retry(tmp_path, monkeypatch):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="remember"))
        monkeypatch.setattr(jobs, "settings", SimpleNamespace(lifeprism_data_path=tmp_path))
        monkeypatch.setattr("lifeprism.llm.runtime.agent_runtime", runtime)
        send = AsyncMock(return_value=SimpleNamespace(error="provider failed", response=None))
        monkeypatch.setattr(jobs.bus, "send", send)
        monkeypatch.setattr(jobs.prompt_loader, "load_prompt", lambda *a, **k: "extract")
        await jobs.process_session_message()
        meta = runtime.chat_sessions._read(result.session_id)[0]
        assert "last_processed_turn" not in meta["extra"]
        assert send.await_count == 1
        await runtime.close()

    asyncio.run(scenario())


def test_no_information_still_advances_and_next_day_is_not_repeated(tmp_path, monkeypatch):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="hi"))
        monkeypatch.setattr(jobs, "settings", SimpleNamespace(lifeprism_data_path=tmp_path))
        monkeypatch.setattr("lifeprism.llm.runtime.agent_runtime", runtime)
        send = AsyncMock(
            return_value=SimpleNamespace(
                error=None, response=SimpleNamespace(content="无可提取内容")
            )
        )
        monkeypatch.setattr(jobs.bus, "send", send)
        monkeypatch.setattr(jobs.llm_call_logger, "log_call", lambda *a, **k: None)
        monkeypatch.setattr(jobs.prompt_loader, "load_prompt", lambda *a, **k: "extract")
        await jobs.process_session_message()
        assert (
            runtime.chat_sessions._read(result.session_id)[0]["extra"]["last_processed_turn"] == 1
        )
        await jobs.process_session_message()
        assert send.await_count == 1
        await runtime.close()

    asyncio.run(scenario())


def test_two_runs_preserve_both_behavior_summaries(tmp_path, monkeypatch):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
        monkeypatch.setattr(jobs, "settings", SimpleNamespace(lifeprism_data_path=tmp_path))
        monkeypatch.setattr("lifeprism.llm.runtime.agent_runtime", runtime)
        send = AsyncMock(
            side_effect=[
                SimpleNamespace(error=None, response=SimpleNamespace(content="第一段总结")),
                SimpleNamespace(error=None, response=SimpleNamespace(content="第二段总结")),
            ]
        )
        monkeypatch.setattr(jobs.bus, "send", send)
        monkeypatch.setattr(jobs.llm_call_logger, "log_call", lambda *a, **k: None)
        monkeypatch.setattr(jobs.prompt_loader, "load_prompt", lambda *a, **k: "extract")
        await jobs.process_session_message()
        await runtime.execute(
            InboundMessage(type=MessageType.CHAT, content="second", session_id=result.session_id)
        )
        await jobs.process_session_message()
        content = (tmp_path / "user/daily_data/behavior.md").read_text(encoding="utf-8")
        assert content.count("第一段总结") == 1
        assert content.count("第二段总结") == 1
        await runtime.close()

    asyncio.run(scenario())


def test_saved_history_prevents_repeat_after_progress_commit_failure(tmp_path, monkeypatch):
    async def scenario():
        import lifeprism.llm.runtime.chat_sessions as sessions

        runtime = make_runtime(tmp_path, FakeClient())
        result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
        monkeypatch.setattr(jobs, "settings", SimpleNamespace(lifeprism_data_path=tmp_path))
        monkeypatch.setattr("lifeprism.llm.runtime.agent_runtime", runtime)
        send = AsyncMock(
            return_value=SimpleNamespace(error=None, response=SimpleNamespace(content="已保存"))
        )
        monkeypatch.setattr(jobs.bus, "send", send)
        monkeypatch.setattr(jobs.llm_call_logger, "log_call", lambda *a, **k: None)
        monkeypatch.setattr(jobs.prompt_loader, "load_prompt", lambda *a, **k: "extract")
        original = sessions.os.replace

        def fail_commit(source, target):
            if str(target).endswith(result.session_id + ".jsonl"):
                raise OSError("commit failed")
            return original(source, target)

        monkeypatch.setattr(sessions.os, "replace", fail_commit)
        await jobs.process_session_message()
        assert (
            "last_processed_turn" not in runtime.chat_sessions._read(result.session_id)[0]["extra"]
        )
        monkeypatch.setattr(sessions.os, "replace", original)
        await jobs.process_session_message()
        assert send.await_count == 1
        assert (
            runtime.chat_sessions._read(result.session_id)[0]["extra"]["last_processed_turn"] == 1
        )
        await runtime.close()

    asyncio.run(scenario())


def test_history_replace_failure_preserves_previous_history_and_progress(tmp_path, monkeypatch):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
        monkeypatch.setattr(jobs, "settings", SimpleNamespace(lifeprism_data_path=tmp_path))
        monkeypatch.setattr("lifeprism.llm.runtime.agent_runtime", runtime)
        monkeypatch.setattr(
            jobs.bus,
            "send",
            AsyncMock(
                return_value=SimpleNamespace(error=None, response=SimpleNamespace(content="总结"))
            ),
        )
        monkeypatch.setattr(jobs.llm_call_logger, "log_call", lambda *a, **k: None)
        monkeypatch.setattr(jobs.prompt_loader, "load_prompt", lambda *a, **k: "extract")
        await jobs.process_session_message()
        path = tmp_path / "user/daily_data/chat_history.json"
        original_bytes = path.read_bytes()
        await runtime.execute(
            InboundMessage(type=MessageType.CHAT, content="second", session_id=result.session_id)
        )
        replace = jobs.os.replace

        def fail_history(source, target):
            if target == path:
                raise OSError("history failed")
            return replace(source, target)

        monkeypatch.setattr(jobs.os, "replace", fail_history)
        with pytest.raises(OSError, match="history failed"):
            await jobs.process_session_message()
        assert path.read_bytes() == original_bytes
        assert (
            runtime.chat_sessions._read(result.session_id)[0]["extra"]["last_processed_turn"] == 1
        )
        await runtime.close()

    asyncio.run(scenario())
