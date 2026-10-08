"""微信会话命令反馈与历史兼容回归测试（修复前的 RED 契约）。

背景：微信侧会话命令需要一次历史兼容修复。修复后：

- `/new` 真正创建原生聊天会话并持久化新 ID，同时给出恢复上一个会话的指令；
- `/continue` 返回带 `[SUCCESS]` 前缀的确认与最近一轮对话摘要；
- `/session-list` 支持页码与日期筛选，并按 `include_preview` 取用户消息摘要；
- 失败路径统一用 `[ERROR]`，且不破坏已有会话引用。

本文件只描述修复后的目标契约，用于先跑出 RED。生产文件不在此修复范围内。

seam：
- `WechatChannel._handle_session_command(content, wechat_user_id) -> bool`
- `WechatChannel.send(msg: OutboundMessage)`

测试不依赖数据库、网络与真实会话文件：通过 `__new__` 构造 channel，
替换 `_save_user_data_to_db`、`send` 与模块级 `agent_runtime`。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = pytest.mark.regression

CHANNEL_MODULE = "lifeprism.llm.channel.wechat.channel"

USER_ID = "wx"
OLD_SID = "11111111-1111-4111-8111-111111111111"
NEW_SID = "22222222-2222-4222-8222-222222222222"
TARGET_SID = "abcdef01-1234-4abc-8def-0123456789ab"
DATE = "2026-10-01"


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
        模块级 `agent_runtime`（含 `execute` 记录器、带 `create`/`delete` 的 manager）。
    """
    from lifeprism.llm.channel.wechat.channel import WechatChannel

    channel = WechatChannel.__new__(WechatChannel)
    channel._user_data = {
        USER_ID: {"last_session_id": last_session_id, "context_token": context_token}
    }
    channel.send = AsyncMock()
    channel._save_user_data_to_db = Mock()

    sessions = sessions if sessions is not None else _init_manager()
    runtime = SimpleNamespace(chat_sessions=sessions, execute=AsyncMock())
    monkeypatch.setattr(f"{CHANNEL_MODULE}.agent_runtime", runtime)
    return channel, sessions, runtime


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


def _replies(channel: object) -> str:
    """拼接所有 send() 调用的回复文本。"""
    return "\n".join(call.args[0].response.content for call in channel.send.await_args_list)


def _sent_messages(channel: object) -> list:
    """取出所有 send() 调用的 OutboundMessage。"""
    return [
        call.args[0] if call.args else call.kwargs["msg"] for call in channel.send.await_args_list
    ]


# ==================== /new ====================


def test_new_creates_session_persists_and_offers_resume(monkeypatch):
    """契约：/new 创建新会话、持久化新 ID，并给出恢复上一个会话的指令。

    出站消息的 session_id 必须是新建会话的真实 ID。
    """
    sessions = _init_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/new", USER_ID))

    assert recognized is True
    sessions.create.assert_awaited_once()
    channel._save_user_data_to_db.assert_called_once()
    assert channel._user_data[USER_ID]["last_session_id"] == NEW_SID
    reply = _replies(channel)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert "新建会话" in reply, "缺少新建会话确认"
    assert NEW_SID in reply, "缺少新会话 ID"
    assert "恢复上一个会话" in reply, "缺少恢复指令"
    assert f"/continue {OLD_SID}" in reply, "恢复指令指向旧会话 ID"
    assert any(msg.session_id == NEW_SID for msg in _sent_messages(channel)), (
        "出站 session_id 应为新会话 ID"
    )


def test_new_without_previous_reference_hides_resume(monkeypatch):
    """契约：没有旧引用时不显示恢复指令，其余行为不变。"""
    sessions = _init_manager()
    channel, _, _ = _build_channel(monkeypatch, last_session_id="", sessions=sessions)

    asyncio.run(channel._handle_session_command("/new", USER_ID))

    reply = _replies(channel)
    assert "[SUCCESS]" in reply
    assert NEW_SID in reply
    assert "恢复上一个会话" not in reply, "无旧会话时不应显示恢复指令"


def test_new_create_failure_keeps_reference_without_success(monkeypatch):
    """契约：创建会话失败时保持旧引用、不写入、不回复成功。"""
    sessions = _init_manager()
    sessions.create = AsyncMock(side_effect=RuntimeError("create boom"))
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/new", USER_ID))

    assert recognized is True
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID, "应保持旧引用"
    channel._save_user_data_to_db.assert_not_called()
    assert "[SUCCESS]" not in _replies(channel)


def test_new_persist_failure_restores_reference_and_deletes_new_session(monkeypatch):
    """契约：新引用保存失败时恢复旧引用，并清理刚创建的空会话。"""
    sessions = _init_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)
    channel._save_user_data_to_db = Mock(side_effect=RuntimeError("db down"))

    recognized = asyncio.run(channel._handle_session_command("/new", USER_ID))

    assert recognized is True
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID, "应恢复旧引用"
    sessions.delete.assert_awaited_once_with(NEW_SID), "应清理刚创建的空会话"
    assert "[SUCCESS]" not in _replies(channel)


# ==================== /continue ====================


def test_continue_reports_success_with_recent_pair(monkeypatch):
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
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(f"/continue {TARGET_SID}", USER_ID))

    assert recognized is True
    sessions.get_history.assert_awaited_once_with(TARGET_SID)
    assert channel._user_data[USER_ID]["last_session_id"] == TARGET_SID
    channel._save_user_data_to_db.assert_called_once()
    reply = _replies(channel)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert "继续会话" in reply, "缺少继续会话确认"
    assert TARGET_SID in reply, "缺少目标会话 ID"
    assert "user:\n最近问题" in reply, "缺少最近一条 user 摘要"
    assert "A:\n最近回答" in reply, "缺少最近一条 assistant 摘要"
    assert "旧问题" not in reply, "不应包含更早的历史消息"
    assert "旧回答" not in reply, "不应包含更早的历史消息"
    assert any(msg.session_id == TARGET_SID for msg in _sent_messages(channel)), (
        "出站 session_id 应为切换到的真实 ID"
    )


def test_continue_empty_history_omits_last_turn_section(monkeypatch):
    """契约：会话无消息时给出确认，但不显示"最后两轮对话"摘要。"""
    sessions = _init_manager(
        history={"session_id": TARGET_SID, "session_name": "空的", "messages": []}
    )
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    asyncio.run(channel._handle_session_command(f"/continue {TARGET_SID}", USER_ID))

    reply = _replies(channel)
    assert "[SUCCESS]" in reply
    assert TARGET_SID in reply
    assert "最后两轮对话" not in reply, "空历史不应显示摘要区块"


def test_continue_missing_argument_returns_error(monkeypatch):
    """契约：缺少参数时回复 [ERROR]，不查询历史、不改引用。"""
    sessions = _init_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/continue", USER_ID))

    assert recognized is True
    assert "[ERROR]" in _replies(channel)
    sessions.get_history.assert_not_called()
    channel._save_user_data_to_db.assert_not_called()
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID


def test_continue_unknown_session_returns_error(monkeypatch):
    """契约：会话不存在时回复 [ERROR]，保持原引用。"""
    sessions = _init_manager(history=None)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(f"/continue {TARGET_SID}", USER_ID))

    assert recognized is True
    assert "[ERROR]" in _replies(channel)
    channel._save_user_data_to_db.assert_not_called()
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID


# ==================== /session-list ====================


def test_session_list_defaults_to_first_page_with_preview(monkeypatch):
    """契约：/session-list 无参数时按第 1 页查询并请求 preview 摘要。"""
    sessions = _init_manager(
        items=[_session_item(TARGET_SID, "日记复盘", preview="今天心情不错")], total=1
    )
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/session-list", USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    reply = _replies(channel)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert TARGET_SID in reply, "缺少完整 Session ID"
    assert "今天心情不错" in reply, "缺少 preview 用户消息摘要"


def test_session_list_explicit_page_with_preview(monkeypatch):
    """契约：/session-list <页码> 按指定页码查询并请求 preview。"""
    sessions = _init_manager(total=30)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command("/session-list 2", USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_awaited_once_with(page=2, page_size=10, include_preview=True)


def test_session_list_date_filter_uses_first_page(monkeypatch):
    """契约：/session-list <日期> 等价于带 date_filter 的第 1 页查询。"""
    sessions = _init_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(f"/session-list {DATE}", USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_awaited_once_with(
        page=1, page_size=10, include_preview=True, date_filter=DATE
    )


def test_session_list_date_filter_with_page(monkeypatch):
    """契约：/session-list <日期> <页码> 同时保留页码与日期筛选。"""
    sessions = _init_manager(total=30)
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(f"/session-list {DATE} 2", USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_awaited_once_with(
        page=2, page_size=10, include_preview=True, date_filter=DATE
    )


@pytest.mark.parametrize(
    "bad_date",
    ["2026-02-30", "2026-13-01", "2026-00-10", "2026-10-00"],
)
def test_session_list_invalid_date_shows_error_without_manager(monkeypatch, bad_date):
    """契约：严格无效的日期只回复 [ERROR] 用法，不访问会话管理器。"""
    sessions = _init_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(f"/session-list {bad_date}", USER_ID))

    assert recognized is True
    sessions.list_sessions.assert_not_called()
    reply = _replies(channel)
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
def test_invalid_arguments_keep_reference(monkeypatch, content):
    """契约：普通无效参数不创建会话、不写入、不改引用。"""
    sessions = _init_manager()
    channel, _, _ = _build_channel(monkeypatch, sessions=sessions)

    recognized = asyncio.run(channel._handle_session_command(content, USER_ID))

    assert recognized is True
    sessions.create.assert_not_awaited(), "无效参数不应创建会话"
    channel._save_user_data_to_db.assert_not_called()
    assert channel._user_data[USER_ID]["last_session_id"] == OLD_SID
    assert "[ERROR]" in _replies(channel)


# ==================== 入口集成 ====================


def test_handle_wechat_message_short_circuits_session_command(monkeypatch):
    """入口集成：会话命令在 _handle_wechat_message 内短路，不触发模型执行。"""
    sessions = _init_manager(items=[_session_item(TARGET_SID, "日记复盘")], total=1)
    channel, _, runtime = _build_channel(monkeypatch, sessions=sessions)

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

    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    channel.send.assert_awaited_once()
    runtime.execute.assert_not_awaited(), "会话命令不得调用 runtime.execute"
    assert channel.bus.mock_calls == [], "会话命令不得向消息总线投递"
