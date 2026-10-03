"""Project myagent Runtime events into the existing local SSE contract."""

import contextlib
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException

from lifeprism.llm.chat.chat_bot import ChatBot
from lifeprism.server.schemas.chatbot_schemas import ChatStreamEvent, ModelConfig, SSEEventType
from lifeprism.utils import LazySingleton, get_logger

logger = get_logger(__name__)


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
            detail="会话管理与旧历史适配留到迁移 P4，当前可新建聊天并继续本次会话。",
        )

    async def get_sessions(self, page: int, page_size: int):
        self._session_deferred()

    async def update_session(self, session_id: str, request):
        self._session_deferred()

    async def delete_session(self, session_id: str):
        self._session_deferred()

    async def get_history(self, session_id: str):
        self._session_deferred()

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
