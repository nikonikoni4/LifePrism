from typing import Optional, List, Dict, Any, AsyncGenerator
from datetime import datetime
import uuid
import warnings

from lifeprism.server.schemas.chatbot_schemas import (
    ChatSession,
    ChatSessionListResponse,
    UpdateSessionRequest,
    ModelConfig,
    ChatMessage,
    ChatHistoryResponse,
    ChatStreamStartResponse,
    ChatStreamEvent,
    SSEEventType,
)
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import NotFoundError

logger = get_logger(__name__)


class ChatbotServiceV1:
    """
    聊天机器人服务类 V1（已弃用）
    """
    def __init__(self):
        warnings.warn(
            "ChatbotServiceV1 已弃用，请使用 ChatbotService（V2版本）",
            DeprecationWarning,
            stacklevel=2
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        pass


class ChatbotService:
    """
    聊天机器人服务类 V2

    已重构：
    - 移除了冗余的 SQLite 会话存储，完全依赖 ChatBot (JSONL)
    - 简化了会话生命周期管理
    """

    def __init__(self):
        """初始化服务"""
        from lifeprism.llm.chat.chat_bot import ChatBot
        self._chatbot = ChatBot()  # 直接实例化，它现在是业务逻辑的入口
        self._current_session_id: Optional[str] = None
        self._model_config = ModelConfig()
        self._is_initialized = True

    async def initialize(self):
        """初始化（保持兼容性）"""
        pass

    async def shutdown(self):
        """清理资源（保持兼容性）"""
        pass

    async def _ensure_initialized(self):
        """确保服务已初始化"""
        pass

    # ========== 会话管理 ==========

    async def get_sessions(self, page: int, page_size: int) -> ChatSessionListResponse:
        """获取会话列表（优化版：只读取元数据）"""
        from lifeprism.llm.session.manager import SessionManager

        session_ids = self._chatbot.list_sessions()
        all_items = []
        for sid in session_ids:
            metadata = SessionManager.get_session_metadata(sid)
            if metadata:
                all_items.append(ChatSession(
                    id=sid,
                    name=metadata.get('name', 'default_name'),
                    created_at=metadata.get('created_at', datetime.now().isoformat()),
                    updated_at=metadata.get('updated_at', datetime.now().isoformat()),
                    message_count=metadata.get('message_len', 0)
                ))

        # 简单的内存分页
        all_items.sort(key=lambda x: x.updated_at, reverse=True)
        total = len(all_items)
        start = (page - 1) * page_size
        end = start + page_size
        items = all_items[start:end]

        return ChatSessionListResponse(items=items, total=total)

    async def get_or_create_session(
        self,
        session_id: Optional[str],
        first_message: str
    ) -> ChatStreamStartResponse:
        """获取或创建会话"""
        # 如果传入了 ID，尝试获取现有会话
        if session_id:
            session = self._chatbot.get_session(session_id)
            if session:
                self._current_session_id = session_id
                return ChatStreamStartResponse(
                    session_id=session_id,
                    session_name=session.name,
                    is_new_session=False
                )

        # 创建新会话
        session = self._chatbot.get_or_create_session(session_id)
        # 如果是新会话（消息列表为空），更新名称
        if not session.messages:
            name = first_message.strip()[:20]
            if len(first_message) > 20: name += "..."
            session.name = name or f"新会话 {datetime.now().strftime('%m-%d %H:%M')}"
            self._chatbot.save_session(session)
            is_new = True
        else:
            is_new = False

        self._current_session_id = session.id
        return ChatStreamStartResponse(
            session_id=session.id,
            session_name=session.name,
            is_new_session=is_new
        )

    async def update_session(
        self,
        session_id: str,
        request: UpdateSessionRequest
    ) -> ChatSession:
        """更新会话名称"""
        self._chatbot.update_session_name(session_id, request.name)
        session = self._chatbot.get_session(session_id)
        if session:
            return ChatSession(
                id=session.id,
                name=session.name,
                created_at=session.created_at.isoformat() if session.created_at else datetime.now().isoformat(),
                updated_at=session.updated_at.isoformat() if session.updated_at else datetime.now().isoformat(),
                message_count=len(session.messages)
            )
        raise NotFoundError(message=f"会话 {session_id} 不存在", code="SESSION_NOT_FOUND")

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        self._chatbot.delete_session(session_id)
        return True

    async def get_history(self, session_id: str) -> ChatHistoryResponse:
        """获取会话历史记录"""
        session = self._chatbot.get_session(session_id)
        if not session:
            return ChatHistoryResponse(session_id=session_id, session_name="未知", messages=[])

        messages = [
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=msg.get('timestamp')
            )
            for msg in session.messages
        ]
        return ChatHistoryResponse(
            session_id=session.id,
            session_name=session.name,
            messages=messages
        )

    # ========== 模型配置 ==========

    async def get_model_config(self) -> ModelConfig:
        """获取当前模型配置"""
        return self._model_config

    async def update_model_config(self, request: Any) -> ModelConfig:
        """更新模型配置"""
        if isinstance(request, dict):
            if 'enable_search' in request: self._model_config.enable_search = request['enable_search']
            if 'enable_thinking' in request: self._model_config.enable_thinking = request['enable_thinking']
        else:
            if hasattr(request, 'enable_search') and request.enable_search is not None:
                self._model_config.enable_search = request.enable_search
            if hasattr(request, 'enable_thinking') and request.enable_thinking is not None:
                self._model_config.enable_thinking = request.enable_thinking
        return self._model_config

    # ========== 对话功能 ==========

    async def send_message(
        self,
        content: str,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """发送消息并生成流式响应事件 (重构为调用 ChatBot.chat)"""
        # 1. 确保会话存在
        start_info = await self.get_or_create_session(session_id, content)
        sid = start_info.session_id

        # 2. 发送 session 事件
        yield ChatStreamEvent(
            type=SSEEventType.SESSION,
            session_id=sid,
            session_name=start_info.session_name,
            is_new_session=start_info.is_new_session
        )

        # 3. 调用 ChatBot 发送消息
        try:
            response = await self._chatbot.chat(content, sid)

            # 发送 content 事件
            yield ChatStreamEvent(
                type=SSEEventType.CONTENT,
                message=response.content
            )

            # 发送 done 事件
            yield ChatStreamEvent(
                type=SSEEventType.DONE,
                message=response.content
            )

        except Exception as e:
            logger.error("对话失败: error=%s", e)
            yield ChatStreamEvent(
                type=SSEEventType.ERROR,
                error=str(e)
            )

    async def get_tokens_usage(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """获取 Token 使用情况统计 (已简化)"""
        default_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'search_count': 0
        }
        return {
            'turn_usage': default_usage.copy(),
            'session_usage': default_usage.copy()
        }


# 创建单例
from lifeprism.utils import LazySingleton
chatbot_service = LazySingleton(ChatbotService)

def get_chatbot_service_v1():
    return ChatbotServiceV1()
