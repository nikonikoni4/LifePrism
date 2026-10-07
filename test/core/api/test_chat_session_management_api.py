"""Chatbot 会话管理路由的端到端契约测试。

用真实 :class:`AgentRuntime` + ``FakeClient`` 注入共享 runtime，驱动
``/api/v2/chatbot/sessions`` 的列表、历史、改名与删除，校验成功响应与
400 / 404 / 409 / 500 的错误码边界，以及错误响应不泄露文件路径。

被测 seam: ``lifeprism/server/services/chatbot_service.py`` 里的 ``agent_runtime`` 全局。
"""

import asyncio
import contextlib
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

_INTEGRATION_DIR = Path(__file__).resolve().parents[1] / "integration"
if str(_INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_DIR))

from test_myagent_runtime import FakeClient, make_runtime  # noqa: E402

from lifeprism.llm.bus import InboundMessage, MessageType  # noqa: E402
from lifeprism.server.api import chatbot_api  # noqa: E402
from lifeprism.server.services.chatbot_service import ChatbotService  # noqa: E402

# services/__init__.py 导出的 chatbot_service 是单例，必须绕过它拿到模块本体
service_module = importlib.import_module("lifeprism.server.services.chatbot_service")

pytestmark = pytest.mark.core

SESSIONS = "/api/v2/chatbot/sessions"


class _FailingSessions:
    """让 chat_sessions 读取抛指定异常的替身。"""

    def __init__(self, error):
        self._error = error

    async def get_history(self, session_id):
        """始终抛出构造时注入的异常。"""
        raise self._error


class _StubRuntime:
    """只暴露 ``chat_sessions`` 的最小 runtime 替身。"""

    def __init__(self, sessions):
        self.chat_sessions = sessions


@contextlib.asynccontextmanager
async def _api(monkeypatch, runtime):
    """把共享 runtime 指向测试实例，并暴露只挂 chatbot 路由的异步客户端。"""
    monkeypatch.setattr(service_module, "agent_runtime", runtime, raising=False)
    monkeypatch.setattr(chatbot_api, "chatbot_service", ChatbotService())
    app = FastAPI()
    app.include_router(chatbot_api.router, prefix="/api/v2")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _new_chat(runtime, content="hi"):
    """执行一轮聊天并返回新建会话 id。"""
    result = await runtime.execute(InboundMessage(type=MessageType.CHAT, content=content))
    return result.session_id


def _chat_file(tmp_path, session_id):
    """返回统一聊天目录下的会话文件路径。"""
    return tmp_path / "sessions" / "chat" / f"{session_id}.jsonl"


async def test_list_sessions_returns_chat_items_with_is_running(tmp_path, monkeypatch):
    """守护列表接口返回 chat 会话条目，且带 is_running 与可解析时间。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        sid = await _new_chat(runtime, "list me")
        async with _api(monkeypatch, runtime) as client:
            response = await client.get(SESSIONS)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["id"] == sid
        assert item["is_running"] is False
        assert item["message_count"] >= 2
        for key in ("created_at", "updated_at"):
            datetime.fromisoformat(item[key])
    finally:
        await runtime.close()


async def test_history_returns_normalized_messages(tmp_path, monkeypatch):
    """守护历史接口返回归一化字符串消息。"""
    runtime = make_runtime(tmp_path, FakeClient(with_tool=True))
    try:
        sid = await _new_chat(runtime, "请回答")
        async with _api(monkeypatch, runtime) as client:
            response = await client.get(f"{SESSIONS}/{sid}/history")
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == sid
        assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
        assert all(isinstance(m["content"], str) for m in body["messages"])
    finally:
        await runtime.close()


async def test_history_missing_session_returns_404(tmp_path, monkeypatch):
    """守护合法但缺失的会话历史返回 404。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        async with _api(monkeypatch, runtime) as client:
            response = await client.get(f"{SESSIONS}/{uuid4()}/history")
        assert response.status_code == 404
    finally:
        await runtime.close()


async def test_history_invalid_identifier_returns_400(tmp_path, monkeypatch):
    """守护非 UUID 会话标识在读取历史时返回 400。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        async with _api(monkeypatch, runtime) as client:
            response = await client.get(f"{SESSIONS}/not-a-uuid/history")
        assert response.status_code == 400
    finally:
        await runtime.close()


async def test_rename_updates_name_and_persists(tmp_path, monkeypatch):
    """守护改名接口写入新名称并落盘。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        sid = await _new_chat(runtime, "rename me")
        async with _api(monkeypatch, runtime) as client:
            response = await client.patch(f"{SESSIONS}/{sid}", json={"name": "新名称"})
            assert response.status_code == 200
            assert response.json() == {"success": True}
            history = await client.get(f"{SESSIONS}/{sid}/history")
        assert history.json()["session_name"] == "新名称"
        lines = _chat_file(tmp_path, sid).read_text(encoding="utf-8").splitlines()
        assert json.loads(lines[0])["name"] == "新名称"
    finally:
        await runtime.close()


async def test_rename_missing_session_returns_404(tmp_path, monkeypatch):
    """守护改名缺失会话返回 404。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        async with _api(monkeypatch, runtime) as client:
            response = await client.patch(f"{SESSIONS}/{uuid4()}", json={"name": "x"})
        assert response.status_code == 404
    finally:
        await runtime.close()


async def test_rename_invalid_identifier_returns_400(tmp_path, monkeypatch):
    """守护非法标识改名返回 400。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        async with _api(monkeypatch, runtime) as client:
            response = await client.patch(f"{SESSIONS}/session_20261002", json={"name": "x"})
        assert response.status_code == 400
    finally:
        await runtime.close()


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
async def test_rename_blank_name_is_rejected(tmp_path, monkeypatch, blank):
    """守护空白名称在 schema 层被拒绝，且不触碰存储。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        sid = await _new_chat(runtime, "keep")
        async with _api(monkeypatch, runtime) as client:
            response = await client.patch(f"{SESSIONS}/{sid}", json={"name": blank})
        assert response.status_code == 422
    finally:
        await runtime.close()


async def test_delete_removes_session_and_file(tmp_path, monkeypatch):
    """守护删除接口释放缓存、移除文件，后续历史返回 404。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        sid = await _new_chat(runtime, "delete me")
        async with _api(monkeypatch, runtime) as client:
            response = await client.delete(f"{SESSIONS}/{sid}")
            assert response.status_code == 200
            assert response.json() == {"success": True}
            after = await client.get(f"{SESSIONS}/{sid}/history")
        assert after.status_code == 404
        assert not _chat_file(tmp_path, sid).exists()
        assert sid not in runtime._slots
    finally:
        await runtime.close()


async def test_delete_missing_session_returns_404(tmp_path, monkeypatch):
    """守护删除缺失会话返回 404。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        async with _api(monkeypatch, runtime) as client:
            response = await client.delete(f"{SESSIONS}/{uuid4()}")
        assert response.status_code == 404
    finally:
        await runtime.close()


async def test_delete_invalid_identifier_returns_400(tmp_path, monkeypatch):
    """守护非法标识删除返回 400，且不越权触碰文件。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        async with _api(monkeypatch, runtime) as client:
            response = await client.delete(f"{SESSIONS}/C:escape")
        assert response.status_code == 400
    finally:
        await runtime.close()


async def test_delete_running_session_returns_409(tmp_path, monkeypatch):
    """守护正在执行的会话删除返回 409，文件保留。"""
    client = FakeClient(block=True)
    runtime = make_runtime(tmp_path, client)
    stream = runtime.stream(InboundMessage(type=MessageType.CHAT, content="hold"))
    try:
        first = await anext(stream)
        sid = first.session_id
        while not client.calls:
            await asyncio.sleep(0)
        async with _api(monkeypatch, runtime) as http:
            response = await http.delete(f"{SESSIONS}/{sid}")
        assert response.status_code == 409
        assert _chat_file(tmp_path, sid).is_file()
    finally:
        await stream.aclose()
        await runtime.close()


async def test_rename_running_session_returns_409(tmp_path, monkeypatch):
    """守护正在执行的会话改名返回 409。"""
    client = FakeClient(block=True)
    runtime = make_runtime(tmp_path, client)
    stream = runtime.stream(InboundMessage(type=MessageType.CHAT, content="hold"))
    try:
        first = await anext(stream)
        sid = first.session_id
        while not client.calls:
            await asyncio.sleep(0)
        async with _api(monkeypatch, runtime) as http:
            response = await http.patch(f"{SESSIONS}/{sid}", json={"name": "blocked"})
        assert response.status_code == 409
    finally:
        await stream.aclose()
        await runtime.close()


async def test_corrupted_session_file_is_rejected_without_leaking_path(tmp_path, monkeypatch):
    """守护损坏会话文件被拒绝，且响应体不含文件系统路径。"""
    runtime = make_runtime(tmp_path, FakeClient())
    try:
        sid = str(uuid4())
        path = _chat_file(tmp_path, sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        async with _api(monkeypatch, runtime) as client:
            response = await client.get(f"{SESSIONS}/{sid}/history")
        assert response.status_code == 400
        assert str(tmp_path) not in response.text
    finally:
        await runtime.close()


async def test_storage_failure_is_sanitized_500_without_path(tmp_path, monkeypatch):
    """守护存储层 OSError 映射为 500，且不回传原始路径。"""
    secret = str(tmp_path / "sessions" / "chat" / "secret.jsonl")
    runtime = _StubRuntime(_FailingSessions(PermissionError(f"Permission denied: '{secret}'")))
    async with _api(monkeypatch, runtime) as client:
        response = await client.get(f"{SESSIONS}/{uuid4()}/history")
    assert response.status_code == 500
    assert secret not in response.text
