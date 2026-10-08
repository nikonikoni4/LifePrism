"""会话命令服务

职责：识别并处理 ``/new``、``/continue``、``/session-list``，返回业务回复。

边界：
- 不发送消息：只返回 ``OutboundMessage``，实际 send 由 ConversationClient 统一完成；
- 不导入微信 channel，不写 SQL；
- 会话引用经 ``SessionReferences`` 读写，Agent 会话经注入的 sessions 管理器操作。

业务逻辑与反馈文案机械提取自 ``WechatChannel._handle_session_command``。

参考 Flow: docs/flows/2026-10-08-wechat-conversation-hitl-flow.md（链路 3）
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from lifeprism.llm.bus import OutboundMessage
from lifeprism.llm.conversation.references import SessionReferences
from lifeprism.llm.conversation.types import ConversationRoute
from lifeprism.llm.providers import LLMResponse
from lifeprism.utils import get_logger

logger = get_logger(__name__)

_COMMANDS = frozenset({"/new", "/continue", "/session-list"})
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

_LIST_USAGE = "[ERROR] 用法：/session-list [正整数页码] 或 /session-list YYYY-MM-DD [正整数页码]"
_BUSY_REPLY = "[ERROR] 当前有正在执行的任务，请等待完成后再切换会话。"
_GENERIC_ERROR = "[ERROR] 会话命令执行失败，请稍后重试。"


class _ChatSessions(Protocol):
    """agent_runtime.chat_sessions 的最小依赖契约（便于测试注入）。"""

    async def list_sessions(self, **kwargs: Any) -> dict[str, Any]: ...

    async def get_history(self, session_id: str) -> dict[str, Any] | None: ...

    async def create(self) -> dict[str, Any]: ...

    async def delete(self, session_id: str) -> Any: ...


class SessionCommandService:
    """识别并处理微信聊天会话命令，不触发模型执行。"""

    def __init__(self, sessions: _ChatSessions, references: SessionReferences) -> None:
        """
        初始化会话命令服务

        Args:
            sessions: Agent 会话管理器（agent_runtime.chat_sessions）
            references: 会话引用存储
        """
        self._sessions = sessions
        self._references = references

    def matches(self, text: str) -> bool:
        """判断文本是否为已识别的会话命令。"""
        parts = text.strip().split()
        return bool(parts) and parts[0] in _COMMANDS

    def is_readonly(self, text: str) -> bool:
        """判断命令是否为只读（仅 /session-list），执行中仍允许。"""
        parts = text.strip().split()
        return bool(parts) and parts[0] == "/session-list"

    async def handle(
        self, text: str, route: ConversationRoute, *, is_running: bool = False
    ) -> OutboundMessage | None:
        """
        处理会话命令并返回回复消息

        Args:
            text: 用户文本内容
            route: 会话收发路由
            is_running: 该 route 当前是否有正在执行的任务；执行中拒绝 /new 与 /continue

        Returns:
            OutboundMessage：命令回复（session_id 为新建或切换到的会话 ID）；
            未识别时返回 None
        """
        parts = text.strip().split()
        if not parts or parts[0] not in _COMMANDS:
            return None
        command = parts[0]
        reply: str
        response_session_id: str | None = None
        try:
            if command == "/session-list":
                reply = await self._handle_list(parts[1:], route)
            elif is_running:
                reply = _BUSY_REPLY
            elif command == "/continue":
                reply, response_session_id = await self._handle_continue(parts, route)
            else:
                reply, response_session_id = await self._handle_new(parts, route)
        except Exception:
            # 文件系统、状态存储错误隔离在命令边界，避免终止调用方循环。
            logger.exception("微信会话命令失败: command=%s", command)
            response_session_id = None
            reply = _GENERIC_ERROR
        return OutboundMessage(
            response=LLMResponse(content=reply),
            session_id=response_session_id,
        )

    async def _handle_list(self, arguments: list[str], route: ConversationRoute) -> str:
        """处理 /session-list：分页、日期筛选、当前/运行标记与预览。"""
        try:
            page, date_filter = self._session_list_arguments(arguments)
        except ValueError:
            return _LIST_USAGE
        options = {"date_filter": date_filter} if date_filter else {}
        listing = await self._sessions.list_sessions(
            page=page, page_size=10, include_preview=True, **options
        )
        total = listing["total"]
        pages = max(1, (total + 9) // 10)
        current = self._references.get(route)
        scope = f"（{date_filter}）" if date_filter else ""
        lines = [f"[SUCCESS] 聊天会话{scope}：第 {page}/{pages} 页，共 {total} 个"]
        for item in listing["items"]:
            markers = []
            if item["id"] == current:
                markers.append("当前")
            if item["is_running"]:
                markers.append("运行中")
            label = f" [{', '.join(markers)}]" if markers else ""
            name = " ".join(item["name"].split())[:80]
            preview = item.get("preview") or "暂无用户消息"
            lines.append(f"• {name}{label}\n{item['id']}: {preview}")
        if not listing["items"]:
            empty = f"暂无{date_filter}的会话记录。" if date_filter else "暂无聊天会话。"
            lines.append(empty if total == 0 else "此页没有会话。")
        lines.append("发送 /continue <完整 Session ID> 切换会话。")
        if page < pages:
            prefix = f"{date_filter} " if date_filter else ""
            lines.append(f"下一页：/session-list {prefix}{page + 1}")
        return "\n\n".join(lines)

    async def _handle_continue(
        self, parts: list[str], route: ConversationRoute
    ) -> tuple[str, str | None]:
        """处理 /continue：校验 UUID、回顾最近一轮并切换引用。"""
        if len(parts) != 2:
            return "[ERROR] 请提供会话ID，用法：/continue <完整 Session ID>", None
        try:
            sid = str(UUID(parts[1]))
        except ValueError:
            return "[ERROR] Session ID 无效，请从 /session-list 复制完整 ID。", None
        history = await self._sessions.get_history(sid)
        if history is None:
            return f"[ERROR] 会话 {sid} 不存在，请通过 /session-list 查看可用会话。", None
        self._references.set(route, sid)
        name = " ".join(history["session_name"].split())[:80]
        reply = f"[SUCCESS] 继续会话 {sid}\n{name}"
        last_messages: dict[str, str] = {}
        for message in reversed(history["messages"]):
            role = message["role"]
            if role in {"user", "assistant"} and role not in last_messages:
                last_messages[role] = message["content"]
        if any(last_messages.values()):
            reply += "\n\n最后两轮对话："
            if last_messages.get("user"):
                reply += f"\nuser:\n{last_messages['user']}"
            if last_messages.get("assistant"):
                reply += f"\n\nA:\n{last_messages['assistant']}"
        return reply, sid

    async def _handle_new(
        self, parts: list[str], route: ConversationRoute
    ) -> tuple[str, str | None]:
        """处理 /new：新建会话并落盘引用，失败时清理空会话并保留旧引用。"""
        if len(parts) != 1:
            return "[ERROR] 用法：/new", None
        previous = self._references.get(route)
        created = await self._sessions.create()
        sid = created["session_id"]
        try:
            self._references.set(route, sid)
        except Exception:
            try:
                await self._sessions.delete(sid)
            except Exception:
                logger.exception("清理未绑定的微信空会话失败: session_id=%s", sid)
            raise
        reply = f"[SUCCESS] 新建会话 {sid} --- 可以开始新的聊天了！"
        if previous:
            reply += f"\n\n可以通过使用以下指令恢复上一个会话：\n/continue {previous}"
        return reply, sid

    @staticmethod
    def _session_list_arguments(arguments: list[str]) -> tuple[int, str | None]:
        """解析页码与严格本地日期；日期筛选可带第二个分页参数。"""
        if len(arguments) > 2:
            raise ValueError("参数过多")
        page, date_filter = 1, None
        if arguments:
            first = arguments[0]
            if _DATE_PATTERN.fullmatch(first):
                date_filter = date.fromisoformat(first).isoformat()
                page_text = arguments[1] if len(arguments) == 2 else "1"
            elif len(arguments) == 1:
                page_text = first
            else:
                raise ValueError("日期参数无效")
            if not page_text.isascii() or not page_text.isdecimal() or int(page_text) < 1:
                raise ValueError("页码无效")
            page = int(page_text)
        return page, date_filter
