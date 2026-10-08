"""微信会话命令反馈与历史兼容回归测试（迁移到会话命令服务 seam）。

背景：微信侧会话命令需要一次历史兼容修复。修复后的目标契约：

- ``/new`` 真正创建原生聊天会话并持久化新 ID，同时给出恢复上一个会话的指令；
- ``/continue`` 返回带 ``[SUCCESS]`` 前缀的确认与最近一轮对话摘要；
- ``/session-list`` 支持页码与日期筛选，并按 ``include_preview`` 取用户消息摘要；
- 失败路径统一用 ``[ERROR]``，且不破坏已有会话引用。

微信渠道已改为纯收发，命令业务迁到 ``lifeprism.llm.conversation``：

seam:
- ``SessionCommandService(sessions, references).handle(text, route, *, is_running=False)
  -> OutboundMessage | None``
- ``wire_wechat_channel(channel, runtime, references)`` 装配的 ``channel.send`` 发送入口

测试不依赖数据库、网络与真实会话文件：``sessions`` 用 ``AsyncMock``，
引用用内存实现；入口装配用 ``wire_wechat_channel`` 注入。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from lifeprism.llm.bus import MessageQueue
from lifeprism.llm.channel import wire_wechat_channel
from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig
from lifeprism.llm.conversation.commands import SessionCommandService
from lifeprism.llm.conversation.types import ConversationRoute

pytestmark = pytest.mark.regression

USER_ID = "wx"
OLD_SID = "11111111-1111-4111-8111-111111111111"
NEW_SID = "22222222-2222-4222-8222-222222222222"
TARGET_SID = "abcdef01-1234-4abc-8def-0123456789ab"
DATE = "2026-10-01"

ROUTE = ConversationRoute(channel="wechat", recipient_id=USER_ID)


# ==================== 辅助构件 ====================


class _MemoryReferences:
    """内存会话引用：按 route 读写并记录 set 调用，可注入写失败。"""

    def __init__(self, last_session_id: str | None = None, *, fail_set: bool = False) -> None:
        self._data: dict[str, str] = {}
        if last_session_id is not None:
            self._data[USER_ID] = last_session_id
        self._fail_set = fail_set
        self.set_calls: list[tuple[str, str]] = []

    def get(self, route: ConversationRoute) -> str | None:
        return self._data.get(route.recipient_id)

    def set(self, route: ConversationRoute, session_id: str) -> None:
        if self._fail_set:
            raise RuntimeError("set boom")
        self._data[route.recipient_id] = session_id
        self.set_calls.append((route.recipient_id, session_id))


def _init_manager(
    *,
    items: list[dict] | None = None,
    total: int = 0,
    history: dict | None = None,
    create_result: dict | None = None,
) -> Mock:
    """构造带 create / delete / list_sessions / get_history 的会话管理器 mock。"""
    sessions = Mock()
    sessions.create = AsyncMock(
        return_value=create_result
        if create_result is not None
        else {"session_id": NEW_SID, "session_name": "新会话"}
    )
    sessions.delete = AsyncMock(return_value=True)
    sessions.list_sessions = AsyncMock(return_value={"items": items or [], "total": total})
    sessions.get_history = AsyncMock(return_value=history)
    return sessions


def _session_item(session_id: str, name: str, *, preview: str = "", running: bool = False) -> dict:
    """构造 list_sessions(include_preview=True) 返回的单个会话条目。"""
    return {
        "id": session_id,
        "name": name,
        "preview": preview,
        "created_at": "2026-10-01T00:00:00+00:00",
        "updated_at": "2026-10-02T00:00:00+00:00",
        "message_count": 4,
        "is_running": running,
    }


def _build_service(
    *,
    last_session_id: str | None = OLD_SID,
    sessions: Mock | None = None,
    fail_set: bool = False,
) -> tuple[SessionCommandService, _MemoryReferences, Mock]:
    """构造 SessionCommandService 及可观测的内存引用。"""
    sessions = sessions if sessions is not None else _init_manager()
    references = _MemoryReferences(last_session_id, fail_set=fail_set)
    return SessionCommandService(sessions, references), references, sessions


def _reply(message) -> str:
    """取出命令回复文本。"""
    assert message is not None
    assert message.response is not None
    return message.response.content


def _channel_reply(channel: WechatChannel) -> str:
    """取出 channel.send 最近一次调用的回复文本。"""
    return channel.send.call_args.args[0].response.content


# ==================== /new ====================


def test_new_creates_session_persists_and_offers_resume():
    """契约：/new 创建新会话、持久化新 ID，并给出恢复上一个会话的指令。

    出站消息的 session_id 必须是新建会话的真实 ID。
    """
    sessions = _init_manager()
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/new", ROUTE))

    sessions.create.assert_awaited_once()
    assert references.set_calls == [(USER_ID, NEW_SID)]
    assert references.get(ROUTE) == NEW_SID
    reply = _reply(message)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert "新建会话" in reply, "缺少新建会话确认"
    assert NEW_SID in reply, "缺少新会话 ID"
    assert "恢复上一个会话" in reply, "缺少恢复指令"
    assert f"/continue {OLD_SID}" in reply, "恢复指令指向旧会话 ID"
    assert message.session_id == NEW_SID, "出站 session_id 应为新会话 ID"


def test_new_without_previous_reference_hides_resume():
    """契约：没有旧引用时不显示恢复指令，其余行为不变。"""
    sessions = _init_manager()
    service, _, _ = _build_service(last_session_id="", sessions=sessions)

    message = asyncio.run(service.handle("/new", ROUTE))

    reply = _reply(message)
    assert "[SUCCESS]" in reply
    assert NEW_SID in reply
    assert "恢复上一个会话" not in reply, "无旧会话时不应显示恢复指令"


def test_new_create_failure_keeps_reference_without_success():
    """契约：创建会话失败时保持旧引用、不写入、不回复成功。"""
    sessions = _init_manager()
    sessions.create = AsyncMock(side_effect=RuntimeError("create boom"))
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/new", ROUTE))

    assert references.get(ROUTE) == OLD_SID, "应保持旧引用"
    assert references.set_calls == []
    assert "[SUCCESS]" not in _reply(message)


def test_new_persist_failure_restores_reference_and_deletes_new_session():
    """契约：新引用保存失败时保留旧引用，并清理刚创建的空会话。"""
    sessions = _init_manager()
    service, references, _ = _build_service(sessions=sessions, fail_set=True)

    message = asyncio.run(service.handle("/new", ROUTE))

    assert references.get(ROUTE) == OLD_SID, "应保留旧引用"
    sessions.delete.assert_awaited_once_with(NEW_SID), "应清理刚创建的空会话"
    assert "[SUCCESS]" not in _reply(message)


# ==================== /continue ====================


def test_continue_reports_success_with_recent_pair():
    """契约：/continue 命中后确认切换，并附带最近一轮 user/assistant 摘要。

    更早的历史消息不出现在回复中；出站 session_id 为被切换到的真实 ID。
    """
    sessions = _init_manager(
        history={
            "session_id": TARGET_SID,
            "session_name": "项目计划",
            "messages": [
                {"role": "user", "content": "旧问题", "timestamp": "t1"},
                {"role": "assistant", "content": "旧回答", "timestamp": "t2"},
                {"role": "user", "content": "最近问题", "timestamp": "t3"},
                {"role": "assistant", "content": "最近回答", "timestamp": "t4"},
            ],
        }
    )
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(f"/continue {TARGET_SID}", ROUTE))

    sessions.get_history.assert_awaited_once_with(TARGET_SID)
    assert references.get(ROUTE) == TARGET_SID
    assert references.set_calls == [(USER_ID, TARGET_SID)]
    reply = _reply(message)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert "继续会话" in reply, "缺少继续会话确认"
    assert TARGET_SID in reply, "缺少目标会话 ID"
    assert "user:\n最近问题" in reply, "缺少最近一条 user 摘要"
    assert "A:\n最近回答" in reply, "缺少最近一条 assistant 摘要"
    assert "旧问题" not in reply, "不应包含更早的历史消息"
    assert "旧回答" not in reply, "不应包含更早的历史消息"
    assert message.session_id == TARGET_SID, "出站 session_id 应为切换到的真实 ID"


def test_continue_empty_history_omits_last_turn_section():
    """契约：会话无消息时给出确认，但不显示"最后两轮对话"摘要。"""
    sessions = _init_manager(
        history={"session_id": TARGET_SID, "session_name": "空的", "messages": []}
    )
    service, _, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(f"/continue {TARGET_SID}", ROUTE))

    reply = _reply(message)
    assert "[SUCCESS]" in reply
    assert TARGET_SID in reply
    assert "最后两轮对话" not in reply, "空历史不应显示摘要区块"


def test_continue_missing_argument_returns_error():
    """契约：缺少参数时回复 [ERROR]，不查询历史、不改引用。"""
    sessions = _init_manager()
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/continue", ROUTE))

    assert "[ERROR]" in _reply(message)
    sessions.get_history.assert_not_called()
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID


def test_continue_unknown_session_returns_error():
    """契约：会话不存在时回复 [ERROR]，保持原引用。"""
    sessions = _init_manager(history=None)
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(f"/continue {TARGET_SID}", ROUTE))

    assert "[ERROR]" in _reply(message)
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID


# ==================== /session-list ====================


def test_session_list_defaults_to_first_page_with_preview():
    """契约：/session-list 无参数时按第 1 页查询并请求 preview 摘要。"""
    sessions = _init_manager(
        items=[_session_item(TARGET_SID, "日记复盘", preview="今天心情不错")], total=1
    )
    service, _, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/session-list", ROUTE))

    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    reply = _reply(message)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert TARGET_SID in reply, "缺少完整 Session ID"
    assert "今天心情不错" in reply, "缺少 preview 用户消息摘要"


def test_session_list_explicit_page_with_preview():
    """契约：/session-list <页码> 按指定页码查询并请求 preview。"""
    sessions = _init_manager(total=30)
    service, _, _ = _build_service(sessions=sessions)

    asyncio.run(service.handle("/session-list 2", ROUTE))

    sessions.list_sessions.assert_awaited_once_with(page=2, page_size=10, include_preview=True)


def test_session_list_date_filter_uses_first_page():
    """契约：/session-list <日期> 等价于带 date_filter 的第 1 页查询。"""
    sessions = _init_manager()
    service, _, _ = _build_service(sessions=sessions)

    asyncio.run(service.handle(f"/session-list {DATE}", ROUTE))

    sessions.list_sessions.assert_awaited_once_with(
        page=1, page_size=10, include_preview=True, date_filter=DATE
    )


def test_session_list_date_filter_with_page():
    """契约：/session-list <日期> <页码> 同时保留页码与日期筛选。"""
    sessions = _init_manager(total=30)
    service, _, _ = _build_service(sessions=sessions)

    asyncio.run(service.handle(f"/session-list {DATE} 2", ROUTE))

    sessions.list_sessions.assert_awaited_once_with(
        page=2, page_size=10, include_preview=True, date_filter=DATE
    )


@pytest.mark.parametrize(
    "bad_date",
    ["2026-02-30", "2026-13-01", "2026-00-10", "2026-10-00"],
)
def test_session_list_invalid_date_shows_error_without_manager(bad_date):
    """契约：严格无效的日期只回复 [ERROR] 用法，不访问会话管理器。"""
    sessions = _init_manager()
    service, _, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(f"/session-list {bad_date}", ROUTE))

    sessions.list_sessions.assert_not_called()
    reply = _reply(message)
    assert "[ERROR]" in reply, "缺少错误标记"
    assert "用法" in reply, "缺少用法提示"


# ==================== 无效参数不换引用 ====================


@pytest.mark.parametrize(
    "content",
    [
        "/new extra",
        "/continue",
        "/continue not-a-uuid",
        "/session-list abc",
        "/session-list 0",
    ],
)
def test_invalid_arguments_keep_reference(content):
    """契约：普通无效参数不创建会话、不写入、不改引用。"""
    sessions = _init_manager()
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(content, ROUTE))

    sessions.create.assert_not_awaited(), "无效参数不应创建会话"
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID
    assert "[ERROR]" in _reply(message)


# ==================== 入口装配 ====================


def test_wired_entry_short_circuits_session_command(monkeypatch):
    """入口装配：命令经 wire 注入的 service 短路，不调用 runtime.stream，不投递总线。"""
    sessions = _init_manager(items=[_session_item(TARGET_SID, "日记复盘")], total=1)
    runtime = SimpleNamespace(chat_sessions=sessions, stream=AsyncMock())
    references = _MemoryReferences()
    channel = WechatChannel(
        WechatConfig(allow_from=["*"]),
        MessageQueue(),
        reply_store=SimpleNamespace(remember=Mock()),
    )
    channel.send = AsyncMock()
    channel.media = SimpleNamespace(download_media=AsyncMock(return_value=None))
    service = wire_wechat_channel(channel, runtime, references)

    # wire 注入真实接收入口与准入检查，而不是渠道内的命令分支
    assert channel.on_message == service.submit
    assert channel.allow_input == service.can_receive

    from lifeprism.llm.channel.wechat.message import WechatMessage

    monkeypatch.setattr(
        WechatMessage,
        "parse_message",
        staticmethod(
            lambda msg: {
                "from_user_id": USER_ID,
                "content": "/session-list",
                "media": [],
                "context_token": "ctx",
            }
        ),
    )

    from lifeprism.config.settings_manager import settings

    monkeypatch.setattr(type(settings), "run_mode", property(lambda self: "full"))

    async def scenario():
        await channel._handle_wechat_message({"from_user_id": USER_ID})
        await service.drain()

    asyncio.run(scenario())

    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    channel.send.assert_awaited_once()
    runtime.stream.assert_not_awaited(), "会话命令不得调用 runtime.stream"
    assert channel.bus._inbound is None and channel.bus._outbound is None, "不得使用消息总线"
