from typing import List, Optional, Any
from lifeprism.llm.bus import MessageType
from lifeprism.llm.channel.manager import channel_manager, Channel
from lifeprism.llm.providers.base import LLMResponse
from lifeprism.llm.session.manager import session_manager, Session
from lifeprism.utils import get_logger

logger = get_logger(__name__)

class ChatBot:
    def __init__(self):
        # 现在的 Channel 自动管理接收循环和单例状态，ChatBot 变为无状态包装器
        self._channel_manager: Channel = channel_manager
        self._session_manager = session_manager

    async def chat(self, content: str, session_id: str = None, **extra) -> LLMResponse:
        """使用 channel 发送聊天消息并返回响应。会话持久化由 AgentLoop 负责。"""
        try:
            # 1. 确保会话存在
            session = self._session_manager.get_or_create_session(session_id)

            # 2. 发送消息
            # 注意：不再此处手动添加消息，因为 AgentLoop 会处理消息的接收、存储和回复存储
            response_data = await self._channel_manager.send(
                content=content,
                session_id=session.id,
                type=MessageType.CHAT,
                extra=extra
            )

            # 3. 包装响应
            if isinstance(response_data, LLMResponse):
                return response_data
            if isinstance(response_data, str):
                return LLMResponse(content=response_data)

            return response_data
        except Exception as e:
            logger.error(f"[ChatBot] Chat error: {e}")
            return LLMResponse(content=f"Error: {str(e)}", finish_reason="error")

    # ========== 会话管理 API ==========

    def get_or_create_session(self, session_id: str = None) -> Session:
        """获取或创建会话"""
        return self._session_manager.get_or_create_session(session_id)

    def save_session(self, session: Session):
        """保存会话"""
        self._session_manager.save_session(session)

    def delete_session(self, session_id: str):
        """删除会话"""
        self._session_manager.delete_session(session_id)

    def list_sessions(self) -> List[str]:
        """获取所有会话 ID 列表"""
        # session_manager.show_session_list 返回的是文件名列表，需要处理
        files = self._session_manager.show_session_list()
        return [f.replace('.jsonl', '') for f in files]

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取现有会话，不存在则返回 None"""
        try:
            return self._session_manager.get_or_create_session(session_id)
        except Exception:
            return None

    def update_session_name(self, session_id: str, name: str):
        """更新会话名称"""
        session = self.get_session(session_id)
        if session:
            session.name = name
            self.save_session(session)

    def stop(self):
        """停止 ChatBot（现在是空操作，Channel 自行管理生命周期）。"""
        pass
