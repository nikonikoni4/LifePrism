"""消息路由准入集成测试（Issue #19 适配）

seam: ``lifeprism.llm.channel.wire_wechat_channel`` 装配出的准入决策
（权限白名单 + 云端处理归属），以及 ``WechatChannel._handle_wechat_message``
对它的执行。

- 本地在线时，云端跳过消息处理（准入拒绝，不产生业务输出）
- 本地离线时，云端接管并处理消息（一次 RuntimeEvent 流 + 一条业务输出）
- 心跳超时后云端接管
- 显式 offline 事件后云端立即接管
- 准入决策与云端跳过/接管日志可观测
- 本地模式（full）下不受心跳状态影响

相对旧测试的变更：
- 旧的 ``Context`` / ``llm_call_logger`` / ``bus.send`` seam 已撤除。准入结果由
  ``channel.allow_input`` 观测，业务路由日志在应用装配模块保留。
- 权限/云端归属判断保留真实 ``heartbeat_manager`` 的在线 / 超时 / 显式 offline 逻辑。
- 渠道注入真实 ``WechatReplyStore``（凭据）与真实 ``MessageQueue``；会话引用、
  Runtime、微信协议客户端使用可控替身，全部隔离于 ``test_temp_data`` 全局数据库。

参考:
- lifeprism/llm/channel/__init__.py（wire_wechat_channel）
- lifeprism/sync/heartbeat_manager.py
- docs/flows/2026-10-08-wechat-conversation-hitl-flow.md
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.core


class _MemoryAccountState:
    """wechat_account_state 内存替身；隔离测试，不触碰 test_temp_data 全局库。"""

    def __init__(self) -> None:
        self.states: dict[str, dict] = {}

    def _record(self, wechat_user_id: str) -> dict:
        return self.states.setdefault(
            wechat_user_id,
            {"wechat_user_id": wechat_user_id, "context_token": None, "last_session_id": None},
        )

    def get_state(self, wechat_user_id: str) -> dict | None:
        return self.states.get(wechat_user_id)

    def save_context_token(self, wechat_user_id: str, context_token: str) -> bool:
        self._record(wechat_user_id)["context_token"] = context_token
        return True

    def save_session_reference(self, wechat_user_id: str, session_id: str) -> bool:
        self._record(wechat_user_id)["last_session_id"] = session_id
        return True

    def save_state(self, wechat_user_id, context_token, last_session_id) -> bool:
        self.states[wechat_user_id] = {
            "wechat_user_id": wechat_user_id,
            "context_token": context_token,
            "last_session_id": last_session_id,
        }
        return True


async def _no_command_sessions(*args, **kwargs):
    raise AssertionError("普通聊天不应触发会话命令管理")


class StubRuntime:
    """可观测 Runtime 替身：产出有效 RuntimeEvent 流，不调用模型或数据库。"""

    def __init__(self, reply: str = "agent-reply") -> None:
        self.reply = reply
        self.stream_calls = 0
        self.chat_sessions = SimpleNamespace(
            list_sessions=_no_command_sessions,
            get_history=_no_command_sessions,
            create=_no_command_sessions,
            delete=_no_command_sessions,
        )

    def start(self) -> None:
        pass

    async def stream(
        self, message, *, interaction_client=None, hitl_timeout=60, hitl_grant_steps=5
    ):
        """产出一轮会话头与 done 终态，模拟 Runtime 事件流契约。"""
        from lifeprism.llm.bus import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.llm.runtime.service import RuntimeEvent

        self.stream_calls += 1
        session_id = message.session_id or uuid4().hex
        yield RuntimeEvent(type="session", run_id="stub-run", session_id=session_id)
        yield RuntimeEvent(
            type="done",
            run_id="stub-run",
            session_id=session_id,
            result=OutboundMessage(
                id=message.id,
                response=LLMResponse(content=self.reply),
                session_id=session_id,
                extra=message.extra,
            ),
        )


class RecordingTransport:
    """记录出站请求的微信协议替身；不发起网络。"""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def api_post(self, endpoint: str, body: dict) -> dict:
        self.sent.append((endpoint, body))
        return {}


@pytest.fixture
def reset_heartbeat():
    """重置心跳单例状态，避免测试间互相影响"""
    from lifeprism.sync.heartbeat_manager import heartbeat_manager

    heartbeat_manager._last_heartbeat = None
    heartbeat_manager._last_event = None
    yield
    heartbeat_manager._last_heartbeat = None
    heartbeat_manager._last_event = None


@pytest.fixture
def channel_env():
    """按 ``wire_wechat_channel`` 真实装配构建渠道、服务与可观测替身。"""
    from lifeprism.llm import channel as assembly
    from lifeprism.llm.bus import MessageQueue
    from lifeprism.llm.channel import wire_wechat_channel
    from lifeprism.llm.channel.wechat.channel import WechatChannel
    from lifeprism.llm.channel.wechat.config import WechatConfig
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore
    from lifeprism.llm.conversation.references import WechatSessionReferences

    account = _MemoryAccountState()
    reply_store = WechatReplyStore(repository=account)
    channel = WechatChannel(WechatConfig(allow_from=["*"]), MessageQueue(), reply_store=reply_store)
    transport = RecordingTransport()
    # 真实 send() 的收发生命周期前置条件；协议调用由 RecordingTransport 承接。
    channel.client = transport
    channel._running = True
    runtime = StubRuntime()
    references = WechatSessionReferences(repository=account)
    service = wire_wechat_channel(channel, runtime, references)
    return SimpleNamespace(
        assembly=assembly,
        channel=channel,
        service=service,
        runtime=runtime,
        transport=transport,
        references=references,
        reply_store=reply_store,
    )


@pytest.fixture
def cloud_mode(channel_env, monkeypatch):
    """装配处于云端模式（agent_only）：权限检查包含心跳归属判断。"""
    monkeypatch.setattr(channel_env.assembly, "settings", SimpleNamespace(run_mode="agent_only"))
    return channel_env


@pytest.fixture
def local_mode(channel_env, monkeypatch):
    """装配处于本地模式（full）：不做心跳归属判断。"""
    monkeypatch.setattr(channel_env.assembly, "settings", SimpleNamespace(run_mode="local"))
    return channel_env


def _build_text_msg(
    content: str = "hello",
    from_user_id: str = "test_user",
    *,
    message_id: str = "message-1",
    token: str = "fresh-token",
) -> dict:
    """构造一条带回复凭据的纯文本微信消息字典。"""
    return {
        "from_user_id": from_user_id,
        "message_id": message_id,
        "context_token": token,
        "item_list": [{"type": 1, "text_item": {"text": content}}],
    }


def _route(recipient_id: str = "test_user"):
    from lifeprism.llm.bus import ChannelType
    from lifeprism.llm.conversation.types import ConversationRoute

    return ConversationRoute(channel=ChannelType.WECHAT, recipient_id=recipient_id)


def _run_message(env) -> None:
    """在独立事件循环中处理一条消息并等待后台任务收尾。"""

    async def scenario():
        await env.channel._handle_wechat_message(_build_text_msg("hello"))
        await env.service.drain()

    asyncio.run(scenario())


class TestMessageRouting:
    """消息路由测试"""

    def test_cloud_skips_message_when_local_online(self, cloud_mode, reset_heartbeat):
        """本地在线时，云端跳过消息处理（准入决策拒绝，无业务输出）"""
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        env = cloud_mode
        heartbeat_manager.set_event("online")
        assert heartbeat_manager.is_local_online() is True

        # 装配出的准入决策直接可观测：在线 -> 拒绝
        assert env.channel.allow_input(_route()) is False

        _run_message(env)

        # 被拒输入不进入执行路径，因此不产生任何业务输出
        assert env.transport.sent == []
        assert env.runtime.stream_calls == 0
        assert env.reply_store.get_token("test_user") == ""
        assert env.references.get(_route()) is None
        assert env.channel.bus._inbound is None and env.channel.bus._outbound is None

    def test_cloud_processes_message_when_local_offline(self, cloud_mode, reset_heartbeat):
        """本地离线时，云端接管：一次 RuntimeEvent 流、一条业务输出"""
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        env = cloud_mode
        # 初始状态：从未连接 -> 离线
        assert heartbeat_manager.is_local_online() is False

        _run_message(env)

        assert env.runtime.stream_calls == 1
        assert len(env.transport.sent) == 1
        endpoint, body = env.transport.sent[0]
        assert endpoint.endswith("sendmessage")
        assert body["msg"]["to_user_id"] == "test_user"
        assert body["msg"]["item_list"][0]["text_item"]["text"] == "agent-reply"
        # 回复凭据经 reply_store 现取，证明凭据链路生效
        assert body["msg"]["context_token"] == "fresh-token"

    def test_cloud_takeover_after_timeout(self, cloud_mode, reset_heartbeat):
        """超时后云端接管（初始在线 → 超时后离线 → 处理消息）"""
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        env = cloud_mode
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        timeout_time = base_time + timedelta(seconds=901)

        async def scenario():
            with patch("lifeprism.sync.heartbeat_manager.datetime") as mock_datetime:
                # 初始在线
                mock_datetime.now.return_value = base_time
                heartbeat_manager.set_event("online")
                assert heartbeat_manager.is_local_online() is True

                # 时间流逝超过 15 分钟（900 秒）阈值 -> 离线
                mock_datetime.now.return_value = timeout_time
                assert heartbeat_manager.is_local_online() is False

                await env.channel._handle_wechat_message(_build_text_msg("hello"))
                await env.service.drain()

        asyncio.run(scenario())

        assert env.runtime.stream_calls == 1
        assert len(env.transport.sent) == 1

    def test_explicit_offline_takeover(self, cloud_mode, reset_heartbeat):
        """显式 offline 事件后云端立即接管"""
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        env = cloud_mode
        heartbeat_manager.set_event("online")
        assert heartbeat_manager.is_local_online() is True

        # 显式 offline 立即生效（不等超时）
        heartbeat_manager.set_event("offline")
        assert heartbeat_manager.is_local_online() is False

        _run_message(env)

        assert env.runtime.stream_calls == 1
        assert len(env.transport.sent) == 1

    def test_routing_admission_decision_is_observable(self, cloud_mode, reset_heartbeat, caplog):
        """准入在线拒绝/离线放行可观测，保留跳过/接管业务日志。"""
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        env = cloud_mode
        route = _route()

        with caplog.at_level(logging.INFO, logger="lifeprism.llm.channel"):
            heartbeat_manager.set_event("online")
            assert env.channel.allow_input(route) is False
            assert any("跳过云端处理" in r.getMessage() for r in caplog.records)

            heartbeat_manager.set_event("offline")
            assert env.channel.allow_input(route) is True
            assert any("云端接管处理" in r.getMessage() for r in caplog.records)

        _run_message(env)

        assert env.runtime.stream_calls == 1
        assert len(env.transport.sent) == 1

    def test_local_always_processes_regardless_of_heartbeat(self, local_mode, reset_heartbeat):
        """本地模式（full）下，无论心跳状态如何，始终处理消息

        验证 run_mode 守卫：本地模式下即使 heartbeat_manager 被误更新为在线，
        消息也不会被跳过。
        """
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        env = local_mode
        # 即使本地"在线"（heartbeat_manager 被误更新），本地模式仍处理消息
        heartbeat_manager.set_event("online")
        assert heartbeat_manager.is_local_online() is True

        _run_message(env)

        assert env.runtime.stream_calls == 1
        assert len(env.transport.sent) == 1
