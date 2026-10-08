"""SessionCommandService 与微信会话引用适配器契约测试。

测试 seam:

- ``SessionCommandService.matches(text) -> bool``：精确识别
  ``/new``、``/continue``、``/session-list``。
- ``SessionCommandService.is_readonly(text) -> bool``：仅 ``/session-list`` 为只读。
- ``SessionCommandService.handle(text, route, *, is_running=False)``：
  返回 ``OutboundMessage | None``，不发送消息；发送由 ConversationClient 统一完成。
- ``WechatSessionReferences``：把 route 映射到 ``wechat_account_state.last_session_id``，
  只做单字段读写，不缓存凭据、不写 SQL。

断言内容复用（原文件不改动）：

- ``test/core/unit/llm/test_wechat_session_commands.py``
- ``test/regression/test_wechat_command_feedback.py``

设计参考：``docs/flows/2026-10-08-wechat-conversation-hitl-flow.md``（链路 3）。

测试不依赖数据库、网络与真实会话文件：``sessions`` 用 ``AsyncMock``，
引用用内存实现；不导入微信 channel，不触碰生产 DB。
"""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, Mock

import pytest

from lifeprism.llm.bus import OutboundMessage
from lifeprism.llm.conversation.commands import SessionCommandService
from lifeprism.llm.conversation.references import WechatSessionReferences
from lifeprism.llm.conversation.types import ConversationRoute

pytestmark = pytest.mark.core

USER_ID = "wx"
OLD_SID = "11111111-1111-4111-8111-111111111111"
NEW_SID = "22222222-2222-4222-8222-222222222222"
# 含十六进制字母，用于验证 UUID 规范化（大写输入 → 小写输出）
TARGET_SID = "abcdef01-1234-4abc-8def-0123456789ab"
DATE = "2026-10-01"

ROUTE = ConversationRoute(channel="wechat", recipient_id=USER_ID)

BUSY_REPLY_FRAGMENT = "正在执行"


# ==================== 内存构件 ====================


class _MemoryReferences:
    """内存会话引用；记录 set 调用，可注入读写失败。"""

    def __init__(
        self,
        last_session_id: str | None = None,
        *,
        fail_get: bool = False,
        fail_set: bool = False,
    ) -> None:
        self._data: dict[str, str] = {}
        if last_session_id is not None:
            self._data[USER_ID] = last_session_id
        self._fail_get = fail_get
        self._fail_set = fail_set
        self.set_calls: list[tuple[str, str]] = []

    def get(self, route: ConversationRoute) -> str | None:
        if self._fail_get:
            raise RuntimeError("get boom")
        return self._data.get(route.recipient_id)

    def set(self, route: ConversationRoute, session_id: str) -> None:
        if self._fail_set:
            # 失败时不得提交：不写入内存，保持旧引用
            raise RuntimeError("set boom")
        self._data[route.recipient_id] = session_id
        self.set_calls.append((route.recipient_id, session_id))


def _init_sessions(
    *,
    items: list[dict] | None = None,
    total: int = 0,
    history: dict | None = None,
    new_session_id: str = NEW_SID,
    create_error: Exception | None = None,
) -> Mock:
    """构造带 list_sessions / get_history / create / delete 的会话管理器 mock。"""
    sessions = Mock()
    sessions.list_sessions = AsyncMock(return_value={"items": items or [], "total": total})
    sessions.get_history = AsyncMock(return_value=history)
    if create_error is not None:
        sessions.create = AsyncMock(side_effect=create_error)
    else:
        sessions.create = AsyncMock(return_value={"session_id": new_session_id})
    sessions.delete = AsyncMock(return_value=None)
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


def _service(sessions: Mock, references: _MemoryReferences | None = None) -> SessionCommandService:
    return SessionCommandService(sessions, references or _MemoryReferences())


def _content(message: OutboundMessage | None) -> str:
    """取出返回消息的文本；None 视为空串。"""
    assert message is not None
    assert message.response is not None
    return message.response.content


# ==================== 引用适配器：WechatSessionReferences ====================


def test_wechat_references_get_reads_last_session_id():
    """契约：get 按 route.recipient_id 读取 last_session_id。"""
    repository = Mock()
    repository.get_state.return_value = {"last_session_id": TARGET_SID}
    references = WechatSessionReferences(repository=repository)

    assert references.get(ROUTE) == TARGET_SID
    repository.get_state.assert_called_once_with(USER_ID)


@pytest.mark.parametrize(
    "state",
    [None, {}, {"last_session_id": None}, {"last_session_id": ""}],
)
def test_wechat_references_get_absent_returns_none(state):
    """契约：无记录、空串或缺失字段一律返回 None。"""
    repository = Mock()
    repository.get_state.return_value = state
    references = WechatSessionReferences(repository=repository)

    assert references.get(ROUTE) is None


def test_wechat_references_set_writes_only_session_field():
    """契约：set 只调用 save_session_reference，不写凭据、不整体覆盖。"""
    repository = Mock()
    repository.save_session_reference.return_value = True
    references = WechatSessionReferences(repository=repository)

    references.set(ROUTE, TARGET_SID)

    repository.save_session_reference.assert_called_once_with(USER_ID, TARGET_SID)
    repository.save_state.assert_not_called()
    repository.save_context_token.assert_not_called()


def test_wechat_references_set_false_raises_runtime_error():
    """契约：save_session_reference 返回 False 时抛出 RuntimeError。"""
    repository = Mock()
    repository.save_session_reference.return_value = False
    references = WechatSessionReferences(repository=repository)

    with pytest.raises(RuntimeError):
        references.set(ROUTE, TARGET_SID)


def test_wechat_references_defaults_to_repository_singleton(monkeypatch):
    """契约：缺省 repository 时惰性使用 lifeprism.repository 单例。"""
    fake_module = types.ModuleType("lifeprism.repository")
    fake_repository = Mock()
    fake_repository.get_state.return_value = {"last_session_id": TARGET_SID}
    fake_module.wechat_account_state_repository = fake_repository
    monkeypatch.setitem(sys.modules, "lifeprism.repository", fake_module)

    references = WechatSessionReferences()

    assert references.get(ROUTE) == TARGET_SID
    fake_repository.get_state.assert_called_once_with(USER_ID)


# ==================== 识别与只读判定 ====================


@pytest.mark.parametrize(
    "text", ["/new", "/continue", "/session-list", "/new extra", "/session-list 2"]
)
def test_matches_recognizes_known_commands(text):
    """契约：三条命令（含参数）均被精确识别。"""
    assert _service(_init_sessions()).matches(text) is True


@pytest.mark.parametrize(
    "text",
    ["/continuefoo", "/session-list-extra", "/new2", "hello world", "", "   ", "/Session-List"],
)
def test_matches_rejects_unknown_content(text):
    """契约：未知命令与普通文本不被识别。"""
    assert _service(_init_sessions()).matches(text) is False


@pytest.mark.parametrize("text", ["/session-list", "/session-list 2", "/session-list 2026-10-01"])
def test_is_readonly_true_only_for_session_list(text):
    """契约：仅 /session-list 视为只读命令。"""
    assert _service(_init_sessions()).is_readonly(text) is True


@pytest.mark.parametrize("text", ["/new", "/continue", "hello", ""])
def test_is_readonly_false_for_others(text):
    """契约：/new、/continue 与普通文本都不是只读。"""
    assert _service(_init_sessions()).is_readonly(text) is False


@pytest.mark.asyncio
async def test_handle_returns_none_for_unknown_content():
    """契约：未知文本返回 None，且不访问会话管理器与引用。"""
    sessions = _init_sessions(total=30)
    references = _MemoryReferences(OLD_SID)
    service = _service(sessions, references)

    assert await service.handle("hello world", ROUTE) is None

    sessions.list_sessions.assert_not_called()
    sessions.get_history.assert_not_called()
    assert references.set_calls == []


# ==================== /new ====================


@pytest.mark.asyncio
async def test_new_creates_session_and_saves_new_uuid():
    """契约：/new 创建新会话并保存新生成的 UUID，回复含恢复旧会话指令。"""
    sessions = _init_sessions()
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle("/new", ROUTE)

    sessions.create.assert_awaited_once_with()
    sessions.delete.assert_not_awaited()
    assert references.get(ROUTE) == NEW_SID, "应保存新 UUID 而非空串"
    assert references.set_calls == [(USER_ID, NEW_SID)]
    reply = _content(message)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert "新建会话" in reply, "缺少新建会话确认"
    assert NEW_SID in reply, "缺少新 Session ID"
    assert "恢复上一个会话" in reply, "缺少恢复指令"
    assert f"/continue {OLD_SID}" in reply, "恢复指令指向旧会话 ID"
    assert message.session_id == NEW_SID, "出站 session_id 应为新会话 ID"


@pytest.mark.asyncio
async def test_new_without_previous_reference_hides_resume():
    """契约：没有旧引用时不显示恢复指令，其余行为不变。"""
    sessions = _init_sessions()
    references = _MemoryReferences()  # 无旧引用

    message = await _service(sessions, references).handle("/new", ROUTE)

    reply = _content(message)
    assert "[SUCCESS]" in reply
    assert NEW_SID in reply
    assert "恢复上一个会话" not in reply, "无旧会话时不应显示恢复指令"


@pytest.mark.asyncio
async def test_new_with_argument_shows_usage():
    """契约：/new 带参数时只回复用法，不创建、不保存、不改引用。"""
    sessions = _init_sessions()
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle("/new now", ROUTE)

    sessions.create.assert_not_awaited()
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID
    assert "[ERROR]" in _content(message)
    assert "用法：/new" in _content(message)


@pytest.mark.asyncio
async def test_new_create_failure_keeps_reference_without_success():
    """契约：创建会话失败时保持旧引用、不写入、不回复成功。"""
    sessions = _init_sessions(create_error=RuntimeError("create boom"))
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle("/new", ROUTE)

    assert references.get(ROUTE) == OLD_SID, "应保持旧引用"
    assert references.set_calls == []
    assert "[SUCCESS]" not in _content(message)


@pytest.mark.asyncio
async def test_new_save_failure_restores_reference_and_deletes_session():
    """契约：新引用保存失败时保留旧引用，并清理刚创建的空会话。"""
    sessions = _init_sessions()
    references = _MemoryReferences(OLD_SID, fail_set=True)

    message = await _service(sessions, references).handle("/new", ROUTE)

    sessions.create.assert_awaited_once_with()
    sessions.delete.assert_awaited_once_with(NEW_SID), "应清理未绑定的新会话"
    assert references.get(ROUTE) == OLD_SID, "应保留旧引用"
    assert "[SUCCESS]" not in _content(message)


# ==================== /continue ====================


@pytest.mark.asyncio
async def test_continue_normalizes_uuid_and_updates_reference():
    """契约：/continue 规范化 UUID 后查询历史，命中则切换引用并确认名称。"""
    sessions = _init_sessions(
        history={"session_id": TARGET_SID, "session_name": "项目计划", "messages": []}
    )
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle(f"/continue {TARGET_SID.upper()}", ROUTE)

    sessions.get_history.assert_awaited_once_with(TARGET_SID), "应以规范化后的 UUID 查询"
    assert references.get(ROUTE) == TARGET_SID
    assert references.set_calls == [(USER_ID, TARGET_SID)]
    reply = _content(message)
    assert "项目计划" in reply, "缺少会话名称确认"
    assert TARGET_SID in reply, "缺少规范化后的 Session ID"
    assert message.session_id == TARGET_SID, "出站 session_id 应为切换到的真实 ID"


@pytest.mark.asyncio
async def test_continue_reports_success_with_recent_pair():
    """契约：/continue 附带最近一轮 user/assistant 摘要，更早历史不出现。"""
    sessions = _init_sessions(
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

    message = await _service(sessions, _MemoryReferences(OLD_SID)).handle(
        f"/continue {TARGET_SID}", ROUTE
    )

    reply = _content(message)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert "继续会话" in reply, "缺少继续会话确认"
    assert "user:\n最近问题" in reply, "缺少最近一条 user 摘要"
    assert "A:\n最近回答" in reply, "缺少最近一条 assistant 摘要"
    assert "旧问题" not in reply, "不应包含更早的历史消息"
    assert "旧回答" not in reply, "不应包含更早的历史消息"


@pytest.mark.asyncio
async def test_continue_empty_history_omits_last_turn_section():
    """契约：会话无消息时给出确认，但不显示最后两轮对话摘要。"""
    sessions = _init_sessions(
        history={"session_id": TARGET_SID, "session_name": "空的", "messages": []}
    )

    message = await _service(sessions, _MemoryReferences(OLD_SID)).handle(
        f"/continue {TARGET_SID}", ROUTE
    )

    reply = _content(message)
    assert "[SUCCESS]" in reply
    assert TARGET_SID in reply
    assert "最后两轮对话" not in reply, "空历史不应显示摘要区块"


@pytest.mark.asyncio
async def test_continue_unknown_session_keeps_reference():
    """契约：会话不存在时回复 [ERROR]，保持原引用，不写入。"""
    sessions = _init_sessions(history=None)
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle(f"/continue {TARGET_SID}", ROUTE)

    sessions.get_history.assert_awaited_once_with(TARGET_SID)
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID
    assert "[ERROR]" in _content(message)
    assert "不存在" in _content(message)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    ["/continue", "/continue not-a-uuid", f"/continue {TARGET_SID} extra"],
)
async def test_continue_invalid_argument_keeps_reference(text):
    """契约：缺少参数、UUID 非法或参数过多时不改引用、不查询、不保存。"""
    sessions = _init_sessions()
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle(text, ROUTE)

    sessions.get_history.assert_not_called()
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID
    assert "[ERROR]" in _content(message)


@pytest.mark.asyncio
async def test_continue_save_failure_restores_reference():
    """契约：保存失败时保留原引用并回复 [ERROR]，不抛出到调用方。"""
    sessions = _init_sessions(
        history={"session_id": TARGET_SID, "session_name": "n", "messages": []}
    )
    references = _MemoryReferences(OLD_SID, fail_set=True)

    message = await _service(sessions, references).handle(f"/continue {TARGET_SID}", ROUTE)

    assert references.get(ROUTE) == OLD_SID, "应保留原引用"
    assert "[ERROR]" in _content(message)


@pytest.mark.asyncio
async def test_continue_read_error_replies_without_raising():
    """契约：读取历史接口异常时回复 [ERROR]，不抛出，且不改引用。"""
    sessions = _init_sessions()
    sessions.get_history = AsyncMock(side_effect=OSError("io error"))
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle(f"/continue {TARGET_SID}", ROUTE)

    assert references.get(ROUTE) == OLD_SID
    assert "[ERROR]" in _content(message)


# ==================== /session-list ====================


@pytest.mark.asyncio
async def test_session_list_defaults_to_first_page():
    """契约：/session-list 无参数按第 1 页查询，回复含名称/ID/当前/运行/总页数。"""
    sessions = _init_sessions(items=[_session_item(TARGET_SID, "日记复盘", running=True)], total=12)
    references = _MemoryReferences(TARGET_SID)

    message = await _service(sessions, references).handle("/session-list", ROUTE)

    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    reply = _content(message)
    assert "[SUCCESS]" in reply, "缺少成功标记"
    assert "日记复盘" in reply, "缺少会话名称"
    assert TARGET_SID in reply, "缺少完整 Session ID"
    assert "当前" in reply, "缺少当前会话标记"
    assert "运行中" in reply, "缺少运行标记"
    assert "第 1/2 页" in reply, "缺少总页数（12 条 → 2 页）"
    assert message.session_id is None, "只读命令不携带会话 ID"


@pytest.mark.asyncio
async def test_session_list_defaults_to_first_page_with_preview():
    """契约：/session-list 请求 preview 摘要并展示用户消息。"""
    sessions = _init_sessions(
        items=[_session_item(TARGET_SID, "日记复盘", preview="今天心情不错")], total=1
    )

    message = await _service(sessions, _MemoryReferences(OLD_SID)).handle("/session-list", ROUTE)

    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    reply = _content(message)
    assert TARGET_SID in reply, "缺少完整 Session ID"
    assert "今天心情不错" in reply, "缺少 preview 用户消息摘要"


@pytest.mark.asyncio
async def test_session_list_accepts_explicit_page():
    """契约：/session-list <正整数页码> 按指定页码查询。"""
    sessions = _init_sessions(total=30)

    await _service(sessions, _MemoryReferences(OLD_SID)).handle("/session-list 2", ROUTE)

    sessions.list_sessions.assert_awaited_once_with(page=2, page_size=10, include_preview=True)


@pytest.mark.asyncio
async def test_session_list_empty_result_is_friendly():
    """契约：没有任何会话时给出友好提示，而不是空列表。"""
    sessions = _init_sessions(items=[], total=0)

    message = await _service(sessions, _MemoryReferences(OLD_SID)).handle("/session-list", ROUTE)

    reply = _content(message)
    assert "第 1/1 页" in reply
    assert "暂无聊天会话。" in reply


@pytest.mark.asyncio
async def test_session_list_page_beyond_range_is_friendly():
    """契约：页码超出总页数时提示此页没有会话，不报错。"""
    sessions = _init_sessions(items=[], total=25)

    message = await _service(sessions, _MemoryReferences(OLD_SID)).handle("/session-list 5", ROUTE)

    assert "此页没有会话。" in _content(message)


@pytest.mark.asyncio
async def test_session_list_date_filter_uses_first_page():
    """契约：/session-list <日期> 等价于带 date_filter 的第 1 页查询。"""
    sessions = _init_sessions()

    await _service(sessions, _MemoryReferences(OLD_SID)).handle(f"/session-list {DATE}", ROUTE)

    sessions.list_sessions.assert_awaited_once_with(
        page=1, page_size=10, include_preview=True, date_filter=DATE
    )


@pytest.mark.asyncio
async def test_session_list_date_filter_with_page():
    """契约：/session-list <日期> <页码> 同时保留页码与日期筛选。"""
    sessions = _init_sessions(total=30)

    await _service(sessions, _MemoryReferences(OLD_SID)).handle(f"/session-list {DATE} 2", ROUTE)

    sessions.list_sessions.assert_awaited_once_with(
        page=2, page_size=10, include_preview=True, date_filter=DATE
    )


@pytest.mark.asyncio
async def test_session_list_ten_digit_page_not_treated_as_date():
    """契约：10 位纯数字是页码而非日期，不误判为无效日期。"""
    sessions = _init_sessions(total=30)

    await _service(sessions, _MemoryReferences(OLD_SID)).handle("/session-list 1234567890", ROUTE)

    sessions.list_sessions.assert_awaited_once_with(
        page=1234567890, page_size=10, include_preview=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "/session-list 0",
        "/session-list -1",
        "/session-list abc",
        "/session-list 1.5",
        "/session-list +1",
        "/session-list 1 2",
    ],
)
async def test_session_list_invalid_page_shows_usage_without_manager(text):
    """契约：非法页码或多余参数只回复用法，不访问会话管理器。"""
    sessions = _init_sessions(total=30)

    message = await _service(sessions, _MemoryReferences(OLD_SID)).handle(text, ROUTE)

    sessions.list_sessions.assert_not_called()
    assert "[ERROR]" in _content(message)
    assert "用法：/session-list [正整数页码]" in _content(message)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_date", ["2026-02-30", "2026-13-01", "2026-00-10", "2026-10-00"])
async def test_session_list_invalid_date_shows_error_without_manager(bad_date):
    """契约：严格无效的日期只回复 [ERROR] 用法，不访问会话管理器。"""
    sessions = _init_sessions()

    message = await _service(sessions, _MemoryReferences(OLD_SID)).handle(
        f"/session-list {bad_date}", ROUTE
    )

    sessions.list_sessions.assert_not_called()
    reply = _content(message)
    assert "[ERROR]" in reply, "缺少错误标记"
    assert "用法" in reply, "缺少用法提示"


# ==================== 执行中（忙）状态 ====================


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["/new", f"/continue {TARGET_SID}"])
async def test_running_rejects_switch_commands(text):
    """契约：执行中 /new 与 /continue 回复忙，不创建、不查询、不切换。"""
    sessions = _init_sessions(
        history={"session_id": TARGET_SID, "session_name": "n", "messages": []}
    )
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle(text, ROUTE, is_running=True)

    sessions.create.assert_not_awaited()
    sessions.get_history.assert_not_called()
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID
    reply = _content(message)
    assert "[ERROR]" in reply
    assert BUSY_REPLY_FRAGMENT in reply


@pytest.mark.asyncio
async def test_running_allows_readonly_session_list():
    """契约：执行中 /session-list 允许只读输出，不改变运行归属。"""
    sessions = _init_sessions(items=[_session_item(TARGET_SID, "日记复盘")], total=1)
    references = _MemoryReferences(OLD_SID)

    message = await _service(sessions, references).handle("/session-list", ROUTE, is_running=True)

    sessions.list_sessions.assert_awaited_once_with(page=1, page_size=10, include_preview=True)
    assert references.set_calls == []
    assert references.get(ROUTE) == OLD_SID
    assert "日记复盘" in _content(message)


# ==================== 引用读取失败 ====================


@pytest.mark.asyncio
async def test_references_get_failure_replies_error_without_raising():
    """契约：references.get 异常时回复 [ERROR]，不抛出，且不切换引用。"""
    sessions = _init_sessions(items=[_session_item(TARGET_SID, "日记复盘")], total=1)
    references = _MemoryReferences(OLD_SID, fail_get=True)

    message = await _service(sessions, references).handle("/session-list", ROUTE)

    assert "[ERROR]" in _content(message)
    assert references.set_calls == []
