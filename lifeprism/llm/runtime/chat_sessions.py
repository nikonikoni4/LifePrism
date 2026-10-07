"""前端聊天管理：只读取统一 chat 目录，不管理工作流执行记录。"""

import json
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from lifeprism.utils import get_logger

if TYPE_CHECKING:
    from lifeprism.llm.runtime.service import AgentRuntime

logger = get_logger(__name__)


class ChatSessionManager:
    """复用 Runtime 的运行预留机制，管理原生 JSONL 聊天文件。"""

    def __init__(self, runtime: "AgentRuntime"):
        self.runtime = runtime

    async def process_pending(
        self,
        sid: str,
        handler: Callable[[list[dict], int, int], Awaitable[None]],
    ) -> bool:
        """处理已结束轮次；handler 完成历史保存后才提交独立业务游标。

        执行或管理中的会话跳过。预留期间阻止聊天、改名和删除；不绑定
        原生持久化 worker，避免缓存元信息覆盖业务进度。
        """
        self._path(sid)
        if self.runtime.is_session_running(sid) or sid in self.runtime._managed_sessions:
            return False
        async with self.runtime.manage_chat_session(sid):
            loaded = self._read(sid)
            if loaded is None:
                return False
            meta, records = loaded
            extra = meta.get("extra") or {}
            if not isinstance(extra, dict):
                raise ValueError("Session extra 必须为对象")
            previous = extra.get("last_processed_turn", 0)
            if type(previous) is not int or previous < 0:
                raise ValueError("last_processed_turn 必须为非负整数")
            ended = [
                r["turn"] for r in records if r["type"] == "turn/end" and type(r.get("turn")) is int
            ]
            end = max(ended, default=0)
            if end <= previous:
                return False
            messages = []
            # 后续轮次已结束时，补齐中间因进程退出而缺少turn/end的轮次。
            # 最后一轮仍未结束的记录位于end之后，不提前消费。
            grouped: dict[int, list[dict]] = {}
            for record in records:
                turn = record.get("turn")
                if type(turn) is int and previous < turn <= end:
                    grouped.setdefault(turn, []).append(record)
            for turn in sorted(grouped):
                if previous < turn <= end:
                    messages.extend(
                        {**message, "turn": turn} for message in self._messages(grouped[turn])
                    )
            if messages:
                await handler(messages, previous + 1, end)
            meta["extra"] = {**extra, "last_processed_turn": end}
            path = self._path(sid)
            original = path.read_bytes()
            _, _, ledger = original.partition(b"\n")
            temporary = path.with_name(f".{sid}.{uuid4().hex}.tmp")
            try:
                temporary.write_bytes(
                    json.dumps(meta, ensure_ascii=False).encode("utf-8") + b"\n" + ledger
                )
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return True

    def _path(self, sid: str) -> Path:
        """验证标准 UUID 及文件归属，拒绝符号链接。"""
        if str(UUID(sid)) != sid:
            raise ValueError("Session ID 必须为标准 UUID")
        path = self.runtime.chat_session_folder / f"{sid}.jsonl"
        if path.resolve() != path:
            raise ValueError("Session 文件不能使用符号链接")
        return path

    def _read(self, sid: str) -> tuple[dict, list[dict]] | None:
        """运行中的会话读内存快照，其余读取持久化账本。"""
        path = self._path(sid)
        slot = self.runtime._slots.get(sid)
        if slot is not None:
            if slot.session_folder != path.parent:
                return None
            session = slot.context.session
            return session.meta_data.meta_data(), [r.to_record_dict() for r in session.record_list]
        if not path.is_file():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise ValueError("Session 文件为空")
        meta = json.loads(lines[0])
        if meta.get("type") != "meta_data" or meta.get("session_id") != sid:
            raise ValueError("Session 元信息与文件不一致")
        return meta, [json.loads(line) for line in lines[1:] if line.strip()]

    @staticmethod
    def _messages(records: list[dict]) -> list[dict]:
        """投影用户文本及每轮最后的 assistant 答复，隐藏工具步骤。"""
        messages: list[dict] = []
        assistant_indexes: dict[Any, int] = {}
        for record in records:
            kind = record["type"]
            if kind not in ("user/message", "assistant/message"):
                continue
            message = record["data"]["message"]
            if kind == "assistant/message" and message.get("tool_calls"):
                continue
            content = message.get("content") or ""
            if isinstance(content, list):
                content = "\n".join(
                    block.get("text", "") if block.get("type") == "text" else "[图片]"
                    for block in content
                )
            projected = {
                "role": "user" if kind == "user/message" else "assistant",
                "content": content,
                "timestamp": record["timestamp"],
            }
            turn = record.get("turn")
            if kind == "assistant/message" and turn in assistant_indexes:
                messages[assistant_indexes[turn]] = projected
            else:
                if kind == "assistant/message":
                    assistant_indexes[turn] = len(messages)
                messages.append(projected)
        return messages

    async def list_sessions(self, page: int = 1, page_size: int = 20) -> dict:
        """按更新时间降序分页，包含尚未首次落盘的运行会话。"""
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("分页参数无效")
        folder = self.runtime.chat_session_folder
        ids = {path.stem for path in folder.glob("*.jsonl")}
        ids.update(
            sid for sid, slot in self.runtime._slots.items() if slot.session_folder == folder
        )
        items = []
        for sid in ids:
            try:
                loaded = self._read(sid)
                if loaded is None:
                    continue
                meta, records = loaded
                updated = records[-1]["timestamp"] if records else meta["updated_at"]
                items.append(
                    {
                        "id": sid,
                        "name": meta["name"],
                        "created_at": meta["created_at"],
                        "updated_at": max(meta["updated_at"], updated),
                        "message_count": len(self._messages(records)),
                        "is_running": self.runtime.is_session_running(sid),
                    }
                )
            except (ValueError, KeyError, TypeError, OSError):
                logger.warning("跳过无法读取的聊天会话: %s", sid, exc_info=True)
        items.sort(key=lambda item: (item["updated_at"], item["id"]), reverse=True)
        start = (page - 1) * page_size
        return {"items": items[start : start + page_size], "total": len(items)}

    async def get_history(self, sid: str) -> dict | None:
        """获取用户消息和最终答复，不触发模型或绑定持久化 worker。"""
        loaded = self._read(sid)
        if loaded is None:
            return None
        meta, records = loaded
        return {
            "session_id": sid,
            "session_name": meta["name"],
            "messages": self._messages(records),
        }

    async def rename(self, sid: str, name: str) -> None:
        """关闭空闲缓存后原子替换元信息，保留后续账本原始字节。"""
        path = self._path(sid)
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
            raise ValueError("会话名称须为 1–200 个字符")
        if not path.is_file():
            raise FileNotFoundError("会话不存在")
        async with self.runtime.manage_chat_session(sid):
            loaded = self._read(sid)
            if loaded is None:
                raise FileNotFoundError("会话不存在")
            meta, _ = loaded
            meta["name"] = name.strip()
            meta["updated_at"] = datetime.now(UTC).isoformat()
            original = path.read_bytes()
            _, _, records = original.partition(b"\n")
            temporary = path.with_name(f".{sid}.{uuid4().hex}.tmp")
            try:
                temporary.write_bytes(
                    json.dumps(meta, ensure_ascii=False).encode("utf-8") + b"\n" + records
                )
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)

    async def delete(self, sid: str) -> bool:
        """禁止删除执行及排队中的会话；空闲会话永久删除。"""
        path = self._path(sid)
        cached = self.runtime._slots.get(sid)
        existed = cached is not None and cached.session_folder == path.parent
        async with self.runtime.manage_chat_session(sid):
            if not path.is_file():
                return existed
            path.unlink()
            return True
