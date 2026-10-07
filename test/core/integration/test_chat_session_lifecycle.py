"""Chat management must reserve idle sessions against concurrent turns."""

import asyncio
import contextlib

import pytest
from test_myagent_runtime import FakeClient, make_runtime

from lifeprism.llm.bus import InboundMessage, MessageType

pytestmark = pytest.mark.core


def test_management_reservation_blocks_turn_and_running_blocks_management(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
            sid = result.session_id
            async with runtime.manage_chat_session(sid):
                with pytest.raises(RuntimeError, match="管理"):
                    await runtime.execute(
                        InboundMessage(type=MessageType.CHAT, content="second", session_id=sid)
                    )
            events = runtime.stream(
                InboundMessage(type=MessageType.CHAT, content="third", session_id=sid)
            )
            async with contextlib.aclosing(events):
                await anext(events)
                assert runtime.is_session_running(sid)
                with pytest.raises(RuntimeError, match="执行"):
                    async with runtime.manage_chat_session(sid):
                        pass
            assert not runtime.is_session_running(sid)
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_missing_file_delete_succeeds_for_cached_session_and_rename_preserves_cache(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
            sid = result.session_id
            (runtime.chat_session_folder / f"{sid}.jsonl").unlink()
            with pytest.raises(FileNotFoundError):
                await runtime.chat_sessions.rename(sid, "renamed")
            assert sid in runtime._slots
            assert await runtime.chat_sessions.delete(sid)
            assert sid not in runtime._slots
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_listing_idle_session_does_not_change_update_time(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
            first = await runtime.chat_sessions.list_sessions()
            second = await runtime.chat_sessions.list_sessions()
            assert first["items"][0]["updated_at"] == second["items"][0]["updated_at"]
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_cancelled_waiter_releases_request_count(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path, FakeClient())
        try:
            result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content="first"))
            sid = result.session_id
            slot = runtime._slots[sid]
            await slot.lock.acquire()
            task = asyncio.create_task(
                runtime.execute(
                    InboundMessage(type=MessageType.CHAT, content="queued", session_id=sid)
                )
            )
            await asyncio.sleep(0)
            assert runtime.is_session_running(sid)
            with pytest.raises(RuntimeError, match="执行"):
                async with runtime.manage_chat_session(sid):
                    pass
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            slot.lock.release()
            assert not runtime.is_session_running(sid)
            assert await runtime.chat_sessions.delete(sid)
        finally:
            await runtime.close()

    asyncio.run(scenario())
