"""WechatChannel 聊天会话命令契约测试。

测试 seam:
- `WechatChannel._handle_session_command(content, wechat_user_id) -> bool`
  只切换渠道侧的会话引用并回复用户，不触发模型执行。
- `WechatChannel._handle_wechat_message(msg)` 入口集成：会话命令在进入
  runtime 之前短路，不调用 `agent_runtime.execute`，也不向消息总线投递。

覆盖命令：`/session-list [正整数页码]`、`/continue <完整 UUID>`、`/new`。

实现文件：lifeprism/llm/channel/wechat/channel.py

测试不依赖数据库、网络与真实媒体文件：通过 `__new__` 构造 channel，
并替换 `_save_user_data_to_db`、`send` 与模块级 `agent_runtime`。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = pytest.mark.core

CHANNEL_MODULE = "lifeprism.llm.channel.wechat.channel"

USER_ID = "wx"
OLD_SID = "old"
# 含十六进制字母，用于验证 UUID 规范化（大写输入 → 小写输出）
TARGET_SID = "abcdef01-1234-4abc-8def-0123456789ab"
# /new 创建的新会话 ID：create() 固定返回它，用于断言保存的是新 UUID 而非空串
NEW_SID = "fedcba98-7654-4321-8abc-def012345678"


# ==================== 辅助函数 ====================


def _build_channel(
    monkeypatch: pytest.MonkeyPatch,
    *,
    last_session_id: str = OLD_SID,
    context_token: str = "ctx",
    sessions: Mock | None = None,
) -> tuple[object, Mock, SimpleNamespace]:
    """用 `__new__` 构造 WechatChannel，绕过数据库与网络初始化。

    Returns:
        (channel, sessions_manager, runtime)：替换后的会话管理器与
        模块级 `agent_runtime`（含 `execute` 记录器）。
    """
    from lifeprism.llm.channel.wechat.channel import WechatChannel

    channel = WechatChannel.__new__(WechatChannel)
    channel._user_data = {
        USER_ID: {"last_session_id": last_session_id, "context_token": context_token}
    }
    channel.send = AsyncMock()
    channel._save_user_data_to_db = Mock()

    sessions = sessions if sessions is not None else _init_command_manager()
    runtime = SimpleNamespace(chat_sessions=sessions, execute=AsyncMock())
    monkeypatch.setattr(f"{CHANNEL_MODULE}.agent_runtime", runtime)
    return channel, sessions, runtime


def _init_command_manager(
    *, items: list[dict] | None = None, total: int = 0, new_session_id: str = NEW_SID
) -> Mock:
    """构造带 list_sessions / get_history / create / delete 的会话管理器 mock。

    `create` 固定返回 `new_session_id`（默认 `NEW_SID`），供 /new 断言
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


def _reply(channel: object) -> str:
    """取出 send() 最近一次调用的回复文本。"""
    return channel.send.call_args.args[0].response.content


def _sent_message(channel: object):
    """取出 send() 最近一次调用的 OutboundMessage。"""
    return channel.send.call_args.args[0]


# ==================== /session-list ====================


def test_session_list_defaults_to_first_page(monkeypatch):
    """契约：/session-list 无参数时按第 1 页、每页 10 条查询。

    回复必须列出会话名称、完整 ID、当前标记、运行标记与总页数。
    """
    sessions = _init_command_manager(
        items=[_session_item(TARGET_SID, "日记复盘", running=True)], total=12
    )
    channel, _, _ = _build_channel(monkeypatch, last_session_id=TARGET_SID, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/session-list", USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    reply = _reply(channel)
    assert "日记复盘" in reply, "缺少会话名称"
    assert TARGET_SID in reply, "缺少完整 Session ID"
    assert "当前" in reply, "缺少当前会话标记"
    assert "运行中" in reply, "缺少运行标记"
    assert "第 1/2 页" in reply, "缺少总页数（12 条 → 2 页）"


def test_session_list_accepts_explicit_page(monkeypatch):
    """契约：/session-list <正整数页码> 按指定页码查询。"""
    sessions = _init_command_manager(total=30)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/session-list 2", USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_awaited_once_with(page=2, page_size=10, include_preview=True)


def test_session_list_empty_result_is_friendly(monkeypatch):
    """契约：没有任何会话时给出友好提示，而不是空列表。"""
    sessions = _init_command_manager(items=[], total=0)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    asyncio.run(channel._handle_session_command("/session-list", USER_ID))

    reply = _reply(channel)
    assert "第 1/1 页" in reply
    assert "暂无聊天会话。" in reply


def test_session_list_page_beyond_range_is_friendly(monkeypatch):
    """契约：页码超出总页数时提示此页没有会话，不报错。"""
    sessions = _init_command_manager(items=[], total=25)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    asyncio.run(channel._handle_session_command("/session-list 5", USER_ID))

    assert "此页没有会话。" in _reply(channel)


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
def test_session_list_invalid_page_shows_usage_without_manager(monkeypatch, content):
    """契约：非法页码或多余参数只回复用法，不访问会话管理器。"""
    sessions = _init_command_manager(total=30)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(content, USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_not_called()
    assert "用法：/session-list [正整数页码]" in _reply(channel)


# ==================== /continue ====================


def test_continue_normalizes_uuid_and_updates_reference(monkeypatch):
    """契约：/continue 规范化 UUID 后查询历史，命中则切换引用并确认名称。

    命令本身不执行模型。
    """
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "项目计划", "messages": []}
    )
    channel, _, runtime = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(
        channel._handle_session_command(f"/continue {TARGET_SID.upper()}", USER_ID)
    )

    assert recognized is True
    sessions.get_history.assert_awaited_once_with(TARGET_SID), "应以规范化后的 UUID 查询"
    assert channel._user_data[USER_ID]["last_session_id"] == TARGET_SID
    channel._save_user_data_to_db.assert_called_once()
    reply = _reply(channel)
    assert "项目计划" in reply, "缺少会话名称确认"
    assert TARGET_SID in reply, "缺少规范化后的 Session ID"
    runtime.execute.assert_not_awaited(), "会话命令不得触发模型执行"


def test_continue_unknown_session_keeps_reference(monkeypatch):
    """契约：会话不存在时不改动原引用，也不保存。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(return_value=None)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(f"/continue {TARGET_SID}", USER_ID))

    assert recognized is True
    sessions.get_history.assert_awaited_once_with(TARGET_SID)
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID
    channel._save_user_data_to_db.assert_not_called()
    assert "不存在" in _reply(channel)


def test_continue_non_chat_session_keeps_reference(monkeypatch):
    """契约：非 chat 会话（如工作流）取不到历史，等同于缺失，不改引用。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(return_value=None)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    asyncio.run(channel._handle_session_command(f"/continue {TARGET_SID}", USER_ID))

    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID
    channel._save_user_data_to_db.assert_not_called()


@pytest.mark.parametrize(
    "content",
    [
        "/continue",
        "/continue not-a-uuid",
        f"/continue {TARGET_SID} extra",
    ],
)
def test_continue_invalid_argument_keeps_reference(monkeypatch, content):
    """契约：缺少参数、UUID 非法或参数过多时不改引用、不查询、不保存。"""
    sessions = _init_command_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(content, USER_ID))

    assert recognized is True
    sessions.get_history.assert_not_called()
    channel._save_user_data_to_db.assert_not_called()
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID


def test_continue_save_failure_restores_reference(monkeypatch):
    """契约：保存失败时恢复原引用并回复错误，不抛异常到调用方。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "n", "messages": []}
    )
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)
    channel._save_user_data_to_db = Mock(side_effect=RuntimeError("db down"))

    recognized = asyncio.run(channel._handle_session_command(f"/continue {TARGET_SID}", USER_ID))

    assert recognized is True
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID, "应恢复原引用"
    assert "失败" in _reply(channel)


def test_continue_read_error_replies_without_raising(monkeypatch):
    """契约：读取接口异常时回复错误，不抛出，且不改引用。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(side_effect=OSError("io error"))
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(f"/continue {TARGET_SID}", USER_ID))

    assert recognized is True
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID
    assert "失败" in _reply(channel)


# ==================== /new ====================


def test_new_creates_session_and_saves_new_uuid(monkeypatch):
    """契约：/new 创建新会话并保存新生成的 UUID（而非空字符串）。

    回复必须包含“新建会话”与新 Session ID，并提供恢复旧会话的 /continue 指令。
    """
    sessions = _init_command_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/new", USER_ID))

    assert recognized is True
    sessions.create.assert_awaited_once_with()
    sessions.delete.assert_not_awaited()
    assert channel._user_data[USER_ID]["last_session_id"] == NEW_SID, "应保存新 UUID 而非空串"
    channel._save_user_data_to_db.assert_called_once()
    reply = _reply(channel)
    assert "新建会话" in reply, "缺少新建会话确认"
    assert NEW_SID in reply, "缺少新 Session ID"
    assert OLD_SID in reply, "缺少恢复旧会话的指令"


def test_new_with_argument_shows_usage(monkeypatch):
    """契约：/new 带参数时只回复用法，不创建、不保存、不改引用。"""
    sessions = _init_command_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/new now", USER_ID))

    assert recognized is True
    sessions.create.assert_not_awaited()
    channel._save_user_data_to_db.assert_not_called()
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID
    assert "用法：/new" in _reply(channel)


def test_new_save_failure_restores_reference_and_deletes_session(monkeypatch):
    """契约：/new 保存失败时恢复原引用、删除新会话并回复错误。"""
    sessions = _init_command_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)
    channel._save_user_data_to_db = Mock(side_effect=RuntimeError("db down"))

    recognized = asyncio.run(channel._handle_session_command("/new", USER_ID))

    assert recognized is True
    sessions.create.assert_awaited_once_with()
    sessions.delete.assert_awaited_once_with(NEW_SID), "应清理未绑定的新会话"
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID
    assert "失败" in _reply(channel)


def test_reference_save_writes_only_the_selected_user(monkeypatch):
    """切换只持久化命令发起者，其他用户写入失败不能影响此次切换。"""
    from lifeprism.llm.channel.wechat.channel import WechatChannel

    channel, _, _ = _build_channel(monkeypatch)
    channel._user_data["other"] = {"last_session_id": "untouched", "context_token": "other"}
    channel._account_state_provider = Mock()
    channel._save_user_data_to_db = WechatChannel._save_user_data_to_db.__get__(channel)

    channel._persist_session_reference(USER_ID, TARGET_SID)

    channel._account_state_provider.save_state.assert_called_once_with(
        wechat_user_id=USER_ID, context_token="ctx", last_session_id=TARGET_SID
    )
    assert channel._user_data["other"]["last_session_id"] == "untouched"


# ==================== 识别与拒绝 ====================


@pytest.mark.parametrize(
    "content",
    ["/continuefoo", "/session-list-extra", "/new2", "hello world", "", "   ", "/Session-List"],
)
def test_unrecognized_content_returns_false_without_side_effect(monkeypatch, content):
    """契约：未知命令与普通文本返回 False，且无任何副作用。"""
    sessions = _init_command_manager(total=30)
    channel, _, runtime = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(content, USER_ID))

    assert recognized is False
    channel.send.assert_not_awaited()
    channel._save_user_data_to_db.assert_not_called()
    sessions.list_sessions.assert_not_called()
    sessions.get_history.assert_not_called()
    runtime.execute.assert_not_awaited()
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID
    assert channel._user_data[USER_ID]["context_token"] == "ctx"


@pytest.mark.parametrize("content", ["/new", f"/continue {TARGET_SID}", "/session-list"])
def test_recognized_command_returns_true(monkeypatch, content):
    """契约：三条已识别命令均返回 True。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "x", "messages": []}
    )
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    assert asyncio.run(channel._handle_session_command(content, USER_ID)) is True


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
def test_all_replies_carry_wechat_user_id(monkeypatch, content):
    """契约：所有命令回复的 extra.wechat_user_id 均为发起用户。"""
    sessions = _init_command_manager()
    sessions.get_history = AsyncMock(
        return_value={"session_id": TARGET_SID, "session_name": "x", "messages": []}
    )
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    asyncio.run(channel._handle_session_command(content, USER_ID))

    assert _sent_message(channel).extra["wechat_user_id"] == USER_ID


# ==================== 入口集成 ====================


def test_handle_wechat_message_short_circuits_session_command(monkeypatch):
    """入口集成：会话命令在 _handle_wechat_message 内短路。

    验证命令已识别并回复，但既不调用 `agent_runtime.execute`，
    也不向消息总线投递任何消息。
    """
    sessions = _init_command_manager(items=[], total=0)
    channel, _, runtime = _build_channel(monkeypatch, sessions=sessions)

    # 隔离入口级依赖：白名单、媒体下载、DB 刷新与消息总线
    channel.bus = Mock()
    channel.is_allowed = Mock(return_value=True)
    channel.media = SimpleNamespace(download_media=AsyncMock(return_value=None))
    channel._refresh_user_data_from_db = Mock()

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

    asyncio.run(channel._handle_wechat_message({"from_user_id": USER_ID}))

    # 命令被识别：走命令分支并回复，而非进入 runtime
    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    channel.send.assert_awaited_once()
    assert "聊天会话" in _reply(channel)
    runtime.execute.assert_not_awaited(), "会话命令不得调用 runtime.execute"
    assert channel.bus.mock_calls == [], "会话命令不得向消息总线投递"
