"""Project myagent Runtime events into the existing local SSE contract."""

import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException

from lifeprism.llm.chat.chat_bot import ChatBot
from lifeprism.llm.runtime import agent_runtime
from lifeprism.server.schemas.chatbot_schemas import ChatStreamEvent, ModelConfig, SSEEventType
from lifeprism.utils import LazySingleton, get_logger

if TYPE_CHECKING:
    from lifeprism.llm.runtime.chat_sessions import ChatSessionManager

logger = get_logger(__name__)

T = TypeVar("T")


class ChatbotService:
    def __init__(self):
        self._chatbot = ChatBot()
        self._model_config = ModelConfig()

    async def initialize(self) -> None:
        """Contexts are created only when a chat is submitted."""

    async def shutdown(self) -> None:
        """The application lifecycle owns the shared Runtime."""

    @staticmethod
    def _session_deferred() -> None:
        raise HTTPException(
            status_code=501,
            detail="历史 Token 用量查询暂未适配 myagent Session。",
        )

    @staticmethod
    def _sessions() -> "ChatSessionManager":
        """返回共享 Runtime 上只管理统一 chat 目录的会话接口。"""
        return agent_runtime.chat_sessions

    async def _guard(self, operation: Callable[[], Awaitable[T]], session_id: str = "") -> T:
        """执行会话操作，并把管理器异常映射为 HTTP 状态码。

        ValueError 包含非法标识与已损坏的会话文件，其消息不含文件路径；
        OSError 的原始消息会带绝对路径，因此只记日志、对外返回固定文案。
        """
        try:
            return await operation()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            logger.error(
                "会话存储访问失败: session_id=%s, error=%s", session_id, exc, exc_info=True
            )
            raise HTTPException(status_code=500, detail="会话存储访问失败") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def get_sessions(self, page: int, page_size: int) -> dict[str, Any]:
        """按更新时间降序分页返回 chat 会话，条目带 is_running。"""
        sessions = self._sessions()
        return await self._guard(lambda: sessions.list_sessions(page=page, page_size=page_size))

    async def update_session(self, session_id: str, request: Any) -> None:
        """重命名 chat 会话，名称须为 1–200 个非空白字符。"""
        name = request["name"] if isinstance(request, dict) else request.name
        sessions = self._sessions()
        await self._guard(lambda: sessions.rename(session_id, name), session_id)

    async def delete_session(self, session_id: str) -> bool:
        """永久删除空闲 chat 会话；会话不存在时返回 False。"""
        sessions = self._sessions()
        return await self._guard(lambda: sessions.delete(session_id), session_id)

    async def get_history(self, session_id: str) -> dict[str, Any] | None:
        """返回 chat 会话的 user/assistant 投影；会话不存在时返回 None。"""
        sessions = self._sessions()
        return await self._guard(lambda: sessions.get_history(session_id), session_id)

    async def get_model_config(self) -> ModelConfig:
        return self._model_config

    async def update_model_config(self, request: Any) -> ModelConfig:
        updates = request if isinstance(request, dict) else request.model_dump(exclude_unset=True)
        for name in ("enable_search", "enable_thinking"):
            if name in updates and updates[name] is not None:
                setattr(self._model_config, name, updates[name])
        return self._model_config

    async def send_message(
        self, content: str, session_id: str | None = None
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """Yield real deltas and one explicit completion or error event."""
        try:
            async with contextlib.aclosing(self._chatbot.stream(content, session_id)) as events:
                async for event in events:
                    common = {
                        "run_id": event.run_id,
                        "session_id": event.session_id,
                        "turn": event.turn,
                        "step": event.step,
                        "seq": event.seq,
                    }
                    if event.type == "session":
                        yield ChatStreamEvent(
                            type=SSEEventType.SESSION,
                            **common,
                            session_name=event.data["name"],
                            is_new_session=event.data["is_new"],
                        )
                    elif event.type == "content":
                        yield ChatStreamEvent(
                            type=SSEEventType.CONTENT, message=event.text, **common
                        )
                    elif event.type in ("tool/call", "tool/result"):
                        yield ChatStreamEvent(
                            type=SSEEventType.STATUS,
                            node=event.type,
                            message=event.data.get("tool_name"),
                            data=event.data,
                            **common,
                        )
                    elif event.type == "done":
                        usage = event.result.response.usage
                        yield ChatStreamEvent(
                            type=SSEEventType.DONE,
                            message=event.result.response.content,
                            usage={
                                "input_tokens": usage.get("prompt_tokens", 0),
                                "output_tokens": usage.get("completion_tokens", 0),
                                "total_tokens": usage.get("total_tokens", 0),
                            },
                            **common,
                        )
                    elif event.type == "error":
                        yield ChatStreamEvent(type=SSEEventType.ERROR, error=event.text, **common)
        except Exception as exc:
            logger.error("聊天流失败: %s", exc)
            yield ChatStreamEvent(type=SSEEventType.ERROR, error=str(exc))

    async def get_tokens_usage(self, session_id: str | None = None) -> dict[str, Any]:
        self._session_deferred()


chatbot_service = LazySingleton(ChatbotService)
