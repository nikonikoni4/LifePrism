"""会话命令服务契约测试（原 WechatChannel._handle_session_command 迁移）。

测试 seam:

- ``SessionCommandService(sessions, references).matches(text) -> bool``：精确识别
  ``/new``、``/continue``、``/session-list``。
- ``SessionCommandService(sessions, references).handle(text, route, *, is_running=False)
  -> OutboundMessage | None``：识别并回复会话命令，不触发模型执行；未识别返回 ``None``。
- ``ConversationClient(route, sender).send(msg)``：把命令回复路由到发送入口，
  并在 ``extra`` 中带上 ``wechat_user_id``。
- ``WechatSessionReferences(repository)``：只按 route 写 ``last_session_id`` 单字段。

微信渠道已改为纯收发：不再有 ``_handle_session_command``、``_user_data``、
``_persist_session_reference``、``_save_user_data_to_db``。命令业务由
``lifeprism.llm.conversation`` 层承担。

覆盖命令：``/session-list [正整数页码]``、``/continue <完整 UUID>``、``/new``。

测试不依赖数据库、网络与真实会话文件：``sessions`` 用 ``AsyncMock``，
引用用内存实现；不导入微信 channel 的命令 API。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from lifeprism.llm.bus import MessageQueue
from lifeprism.llm.channel import wire_wechat_channel
from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig
from lifeprism.llm.conversation.client import ConversationClient
from lifeprism.llm.conversation.commands import SessionCommandService
from lifeprism.llm.conversation.references import WechatSessionReferences
from lifeprism.llm.conversation.types import ConversationRoute

pytestmark = pytest.mark.core

USER_ID = "wx"
OLD_SID = "old"
# 含十六进制字母，用于验证 UUID 规范化（大写输入 → 小写输出）
TARGET_SID = "abcdef01-1234-4abc-8def-0123456789ab"
# /new 创建的新会话 ID：create() 固定返回它，用于断言保存的是新 UUID 而非空串
NEW_SID = "fedcba98-7654-4321-8abc-def012345678"

ROUTE = ConversationRoute(channel="wechat", recipient_id=USER_ID)


# ==================== 辅助构件 ====================


class _MemoryReferences:
    """内存会话引用：按 route 读写并记录 set 调用，可注入写失败。

    写失败时不提交内存，保持旧引用——与真实存储失败语义一致。
    """

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


def _init_command_manager(
    *, items: list[dict] | None = None, total: int = 0, new_session_id: str = NEW_SID
) -> Mock:
    """构造带 list_sessions / get_history / create / delete 的会话管理器 mock。

    ``create`` 固定返回 ``new_session_id``（默认 ``NEW_SID``），供 /new 断言
    保存的是新生成的 UUID。
    """
    sessions = Mock()
    sessions.list_sessions = AsyncMock(return_value={"items": items or [], "total": total})
    sessions.get_history = AsyncMock(return_value=None)
    sessions.create = AsyncMock(return_value={"session_id": new_session_id})
    sessions.delete = AsyncMock(return_value=None)
    return sessions


def _session_item(session_id: str, name: str, *, running: bool = False) -> dict:
    """构造 list_sessions 返回的单个会话条目。"""
    return {
        "id": session_id,
        "name": name,
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
    """构造 SessionCommandService 及可观测的内存引用。

    Returns:
        (service, references, sessions)
    """
    sessions = sessions if sessions is not None else _init_command_manager()
    references = _MemoryReferences(last_session_id, fail_set=fail_set)
    return SessionCommandService(sessions, references), references, sessions


def _content(message) -> str:
    """取出命令回复的文本。"""
    assert message is not None
    assert message.response is not None
    return message.response.content


def _route_reply(message) -> object:
    """经 ConversationClient 路由一条回复，返回发送入口收到的 OutboundMessage。"""
    sender = AsyncMock()
    asyncio.run(ConversationClient(ROUTE, sender).send(message))
    return sender.call_args.args[0]


def _channel_reply(channel: WechatChannel) -> str:
    """取出 channel.send 最近一次调用的回复文本。"""
    return channel.send.call_args.args[0].response.content


# ==================== /session-list ====================


def test_session_list_defaults_to_first_page():
    """契约：/session-list 无参数时按第 1 页、每页 10 条查询。

    回复必须列出会话名称、完整 ID、当前标记、运行标记与总页数。
    """
    sessions = _init_command_manager(
        items=[_session_item(TARGET_SID, "日记复盘", running=True)], total=12
    )
    service, _, _ = _build_service(last_session_id=TARGET_SID, sessions=sessions)

    message = asyncio.run(service.handle("/session-list", ROUTE))

    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    reply = _content(message)
    assert "日记复盘" in reply, "缺少会话名称"
    assert TARGET_SID in reply, "缺少完整 Session ID"
    assert "当前" in reply, "缺少当前会话标记"
    assert "运行中" in reply, "缺少运行标记"
    assert "第 1/2 页" in reply, "缺少总页数（12 条 → 2 页）"


def test_session_list_accepts_explicit_page():
    """契约：/session-list <正整数页码> 按指定页码查询。"""
    sessions = _init_command_manager(total=30)
    service, _, _ = _build_service(sessions=sessions)

    asyncio.run(service.handle("/session-list 2", ROUTE))

    sessions.list_sessions.assert_awaited_once_with(page=2, page_size=10, include_preview=True)


def test_session_list_empty_result_is_friendly():
    """契约：没有任何会话时给出友好提示，而不是空列表。"""
    sessions = _init_command_manager(items=[], total=0)
    service, _, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/session-list", ROUTE))

    reply = _content(message)
    assert "第 1/1 页" in reply
    assert "暂无聊天会话。" in reply


def test_session_list_page_beyond_range_is_friendly():
    """契约：页码超出总页数时提示此页没有会话，不报错。"""
    sessions = _init_command_manager(items=[], total=25)
    service, _, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/session-list 5", ROUTE))

    assert "此页没有会话。" in _content(message)


@pytest.mark.parametrize(
    "content",
    [
        "/session-list 0",
        "/session-list -1",
        "/session-list abc",
        "/session-list 1.5",
        "/session-list +1",
        "/session-list 1 2",
    ],
)
def test_session_list_invalid_page_shows_usage_without_manager(content):
    """契约：非法页码或多余参数只回复用法，不访问会话管理器。"""
    sessions = _init_command_manager(total=30)
    service, _, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(content, ROUTE))

    sessions.list_sessions.assert_not_called()
    assert "用法：/session-list [正整数页码]" in _content(message)


# ==================== /continue ====================


def test_continue_normalizes_uuid_and_updates_reference():
    """契约：/continue 规范化 UUID 后查询历史，命中则切换引用并确认名称。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "项目计划", "messages": []}
    )
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(f"/continue {TARGET_SID.upper()}", ROUTE))

    sessions.get_history.assert_awaited_once_with(TARGET_SID), "应以规范化后的 UUID 查询"
    assert references.get(ROUTE) == TARGET_SID
    assert references.set_calls == [(USER_ID, TARGET_SID)]
    reply = _content(message)
    assert "项目计划" in reply, "缺少会话名称确认"
    assert TARGET_SID in reply, "缺少规范化后的 Session ID"


def test_continue_unknown_session_keeps_reference():
    """契约：会话不存在时不改动原引用，也不保存。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(return_value=None)
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(f"/continue {TARGET_SID}", ROUTE))

    sessions.get_history.assert_awaited_once_with(TARGET_SID)
    assert references.get(ROUTE) == OLD_SID
    assert references.set_calls == []
    assert "不存在" in _content(message)


def test_continue_non_chat_session_keeps_reference():
    """契约：非 chat 会话（如工作流）取不到历史，等同于缺失，不改引用。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(return_value=None)
    service, references, _ = _build_service(sessions=sessions)

    asyncio.run(service.handle(f"/continue {TARGET_SID}", ROUTE))

    assert references.get(ROUTE) == OLD_SID
    assert references.set_calls == []


@pytest.mark.parametrize(
    "content",
    [
        "/continue",
        "/continue not-a-uuid",
        f"/continue {TARGET_SID} extra",
    ],
)
def test_continue_invalid_argument_keeps_reference(content):
    """契约：缺少参数、UUID 非法或参数过多时不改引用、不查询、不保存。"""
    sessions = _init_command_manager()
    service, references, _ = _build_service(sessions=sessions)

    asyncio.run(service.handle(content, ROUTE))

    sessions.get_history.assert_not_called()
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID


def test_continue_save_failure_restores_reference():
    """契约：保存失败时保留原引用并回复错误，不抛异常到调用方。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "n", "messages": []}
    )
    service, references, _ = _build_service(sessions=sessions, fail_set=True)

    message = asyncio.run(service.handle(f"/continue {TARGET_SID}", ROUTE))

    assert references.get(ROUTE) == OLD_SID, "应保留原引用"
    assert "失败" in _content(message)


def test_continue_read_error_replies_without_raising():
    """契约：读取接口异常时回复错误，不抛出，且不改引用。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(side_effect=OSError("io error"))
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(f"/continue {TARGET_SID}", ROUTE))

    assert references.get(ROUTE) == OLD_SID
    assert "失败" in _content(message)


# ==================== /new ====================


def test_new_creates_session_and_saves_new_uuid():
    """契约：/new 创建新会话并保存新生成的 UUID（而非空字符串）。

    回复必须包含“新建会话”与新 Session ID，并提供恢复旧会话的 /continue 指令。
    """
    sessions = _init_command_manager()
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/new", ROUTE))

    sessions.create.assert_awaited_once_with()
    sessions.delete.assert_not_awaited()
    assert references.get(ROUTE) == NEW_SID, "应保存新 UUID 而非空串"
    assert references.set_calls == [(USER_ID, NEW_SID)]
    reply = _content(message)
    assert "新建会话" in reply, "缺少新建会话确认"
    assert NEW_SID in reply, "缺少新 Session ID"
    assert OLD_SID in reply, "缺少恢复旧会话的指令"


def test_new_with_argument_shows_usage():
    """契约：/new 带参数时只回复用法，不创建、不保存、不改引用。"""
    sessions = _init_command_manager()
    service, references, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle("/new now", ROUTE))

    sessions.create.assert_not_awaited()
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID
    assert "用法：/new" in _content(message)


def test_new_save_failure_restores_reference_and_deletes_session():
    """契约：/new 保存失败时保留原引用、删除新会话并回复错误。"""
    sessions = _init_command_manager()
    service, references, _ = _build_service(sessions=sessions, fail_set=True)

    message = asyncio.run(service.handle("/new", ROUTE))

    sessions.create.assert_awaited_once_with()
    sessions.delete.assert_awaited_once_with(NEW_SID), "应清理未绑定的新会话"
    assert references.get(ROUTE) == OLD_SID
    assert "失败" in _content(message)


def test_reference_save_writes_only_the_selected_user():
    """契约：WechatSessionReferences.set 只写发起者的 last_session_id 单字段。

    不整行 save_state、不写 context_token，也不触碰其他用户。
    """
    repository = Mock()
    repository.save_session_reference.return_value = True
    references = WechatSessionReferences(repository=repository)

    references.set(ROUTE, TARGET_SID)

    repository.save_session_reference.assert_called_once_with(USER_ID, TARGET_SID)
    assert [call.args[0] for call in repository.save_session_reference.call_args_list] == [USER_ID]
    repository.save_state.assert_not_called()
    repository.save_context_token.assert_not_called()


# ==================== 识别与拒绝 ====================


@pytest.mark.parametrize(
    "content",
    ["/continuefoo", "/session-list-extra", "/new2", "hello world", "", "   ", "/Session-List"],
)
def test_unrecognized_content_returns_none_without_side_effect(content):
    """契约：未知命令与普通文本不被识别，handle 返回 None 且无副作用。"""
    sessions = _init_command_manager(total=30)
    service, references, _ = _build_service(sessions=sessions)

    assert service.matches(content) is False
    assert asyncio.run(service.handle(content, ROUTE)) is None

    sessions.list_sessions.assert_not_called()
    sessions.get_history.assert_not_called()
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID


@pytest.mark.parametrize("content", ["/new", f"/continue {TARGET_SID}", "/session-list"])
def test_recognized_command_returns_message(content):
    """契约：三条已识别命令均被 matches 识别并返回回复消息。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "x", "messages": []}
    )
    service, _, _ = _build_service(sessions=sessions)

    assert service.matches(content) is True
    assert asyncio.run(service.handle(content, ROUTE)) is not None


@pytest.mark.parametrize(
    "content",
    [
        "/new",
        "/new extra",
        f"/continue {TARGET_SID}",
        "/continue bad",
        "/session-list",
        "/session-list 0",
    ],
)
def test_all_replies_carry_wechat_user_id(content):
    """契约：命令回复经 ConversationClient 路由后 extra.wechat_user_id 为发起用户。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "x", "messages": []}
    )
    service, _, _ = _build_service(sessions=sessions)

    message = asyncio.run(service.handle(content, ROUTE))

    assert _route_reply(message).extra["wechat_user_id"] == USER_ID


# ==================== 入口装配 ====================


def test_wired_entry_short_circuits_session_command(monkeypatch):
    """入口装配：命令经 wire 注入的 service 短路，不调用 runtime.stream，不投递总线。"""
    sessions = _init_command_manager(items=[], total=0)
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

    # 命令被识别：走命令分支并回复，而非进入 runtime
    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    channel.send.assert_awaited_once()
    assert "聊天会话" in _channel_reply(channel)
    runtime.stream.assert_not_awaited(), "会话命令不得调用 runtime.stream"
    assert channel.bus._inbound is None and channel.bus._outbound is None, "不得使用消息总线"
