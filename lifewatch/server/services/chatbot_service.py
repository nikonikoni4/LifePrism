"""
Chatbot 服务层 - 聊天机器人业务逻辑

负责管理 ChatBot 实例和会话管理
采用方式B设计：发送消息时自动创建会话
"""
from typing import Optional, List, Dict, Any, AsyncGenerator
from datetime import datetime
import uuid

from lifewatch.llm.llm_classify.chat.chat_bot import ChatBot
from lifewatch.server.schemas.chatbot_schemas import (
    ChatSession,
    ChatSessionListResponse,
    UpdateSessionRequest,
    ModelConfig,
    UpdateModelConfigRequest,
    ChatMessage,
    ChatHistoryResponse,
    MessageRole,
    ChatStreamStartResponse,
)
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class ChatbotService:
    """
    聊天机器人服务类
    
    管理 ChatBot 实例和会话
    """
    
    def __init__(self):
        """初始化服务"""
        self._chatbot: Optional[ChatBot] = None
        self._chatbot_context = None  # 异步上下文管理器
        self._current_session_id: Optional[str] = None
        self._model_config = ModelConfig()
        # 会话元数据缓存: session_id -> metadata
        self._session_metadata: Dict[str, Dict[str, Any]] = {}
        self._is_initialized = False
    
    async def initialize(self):
        """
        初始化 ChatBot 实例（使用持久化存储）
        
        在首次使用时调用
        """
        if self._is_initialized:
            return
        
        try:
            # 使用持久化存储的异步上下文管理器
            self._chatbot_context = ChatBot.create_with_persistence()
            self._chatbot = await self._chatbot_context.__aenter__()
            self._is_initialized = True
            logger.info("ChatBot 初始化成功")
        except Exception as e:
            logger.error(f"ChatBot 初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭服务，清理资源"""
        if self._chatbot_context:
            try:
                await self._chatbot_context.__aexit__(None, None, None)
                self._is_initialized = False
                logger.info("ChatBot 已关闭")
            except Exception as e:
                logger.error(f"ChatBot 关闭失败: {e}")
    
    async def _ensure_initialized(self):
        """确保服务已初始化"""
        if not self._is_initialized:
            await self.initialize()
    
    # ========== 会话管理 ==========
    
    def _generate_session_id(self) -> str:
        """生成新的会话 ID"""
        return f"session-{uuid.uuid4().hex[:8]}"
    
    def _generate_session_name(self, first_message: str) -> str:
        """
        根据首条消息生成会话名称
        
        Args:
            first_message: 用户的第一条消息
            
        Returns:
            str: 会话名称（截取前20个字符）
        """
        # 截取消息前20个字符作为会话名称
        name = first_message.strip()[:20]
        if len(first_message) > 20:
            name += "..."
        return name or f"新会话 {datetime.now().strftime('%m-%d %H:%M')}"
    
    async def get_sessions(self, page: int, page_size: int) -> ChatSessionListResponse:
        """
        获取会话列表
        
        Args:
            page: 页码
            page_size: 每页数量
            
        Returns:
            ChatSessionListResponse: 会话列表
        """
        # 从缓存获取会话列表
        all_sessions = list(self._session_metadata.values())
        
        # 按更新时间降序排序
        all_sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        
        total = len(all_sessions)
        start = (page - 1) * page_size
        end = start + page_size
        
        items = [
            ChatSession(
                id=meta["id"],
                name=meta["name"],
                created_at=meta["created_at"],
                updated_at=meta["updated_at"],
                message_count=meta.get("message_count", 0)
            )
            for meta in all_sessions[start:end]
        ]
        
        return ChatSessionListResponse(items=items, total=total)
    
    async def get_or_create_session(
        self, 
        session_id: Optional[str], 
        first_message: str
    ) -> ChatStreamStartResponse:
        """
        获取或创建会话（方式B核心逻辑）
        
        Args:
            session_id: 会话 ID，为 None 时创建新会话
            first_message: 用户的第一条消息（用于生成会话名称）
            
        Returns:
            ChatStreamStartResponse: 会话信息
        """
        await self._ensure_initialized()
        
        is_new = False
        
        if session_id is None or session_id not in self._session_metadata:
            # 创建新会话
            session_id = self._generate_session_id()
            name = self._generate_session_name(first_message)
            
            self._session_metadata[session_id] = {
                "id": session_id,
                "name": name,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "message_count": 0
            }
            is_new = True
            logger.info(f"创建新会话: {session_id}")
        else:
            name = self._session_metadata[session_id]["name"]
        
        # 设置当前会话
        self._current_session_id = session_id
        self._chatbot.set_thread_id(session_id)
        
        return ChatStreamStartResponse(
            session_id=session_id,
            session_name=name,
            is_new_session=is_new
        )
    
    async def update_session_name(self, session_id: str, request: UpdateSessionRequest) -> bool:
        """
        更新会话名称
        
        Args:
            session_id: 会话 ID
            request: 更新请求
            
        Returns:
            bool: 是否成功
        """
        if session_id not in self._session_metadata:
            return False
        
        self._session_metadata[session_id]["name"] = request.name
        self._session_metadata[session_id]["updated_at"] = datetime.now().isoformat()
        return True
    
    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            bool: 是否成功
        """
        # TODO: 从 checkpoint 数据库删除会话历史
        if session_id in self._session_metadata:
            del self._session_metadata[session_id]
            
            # 如果删除的是当前会话，清空当前会话
            if self._current_session_id == session_id:
                self._current_session_id = None
            
            return True
        return False
    
    # ========== 模型配置 ==========
    
    async def get_model_config(self) -> ModelConfig:
        """获取当前模型配置"""
        return self._model_config
    
    async def update_model_config(self, request: UpdateModelConfigRequest) -> ModelConfig:
        """
        更新模型配置
        
        Args:
            request: 更新请求
            
        Returns:
            ModelConfig: 更新后的配置
        """
        await self._ensure_initialized()
        
        if request.enable_search is not None:
            self._model_config.enable_search = request.enable_search
        if request.enable_thinking is not None:
            self._model_config.enable_thinking = request.enable_thinking
        
        # 重新创建 agent 以应用新配置
        if self._chatbot:
            self._chatbot.get_new_agent(
                enable_search=self._model_config.enable_search,
                enable_thinking=self._model_config.enable_thinking
            )
            logger.info(f"模型配置已更新: search={self._model_config.enable_search}, thinking={self._model_config.enable_thinking}")
        
        return self._model_config
    
    # ========== 对话功能 ==========
    
    async def chat_stream(
        self, 
        session_id: str, 
        content: str
    ) -> AsyncGenerator[str, None]:
        """
        流式对话
        
        Args:
            session_id: 会话 ID
            content: 用户消息
            
        Yields:
            str: 响应内容片段
        """
        await self._ensure_initialized()
        
        # 确保使用正确的会话
        if self._current_session_id != session_id:
            self._current_session_id = session_id
            self._chatbot.set_thread_id(session_id)
        
        # 更新会话的消息计数和时间
        if session_id in self._session_metadata:
            self._session_metadata[session_id]["message_count"] += 1
            self._session_metadata[session_id]["updated_at"] = datetime.now().isoformat()
        
        # 流式输出
        async for chunk in self._chatbot.chat(content):
            yield chunk
    
    async def get_chat_history(self, session_id: str) -> Optional[ChatHistoryResponse]:
        """
        获取会话历史
        
        Args:
            session_id: 会话 ID
            
        Returns:
            Optional[ChatHistoryResponse]: 历史消息，不存在返回 None
        """
        if session_id not in self._session_metadata:
            return None
        
        # TODO: 从 checkpoint 读取历史消息
        # 目前返回空消息列表
        return ChatHistoryResponse(
            session_id=session_id,
            session_name=self._session_metadata[session_id]["name"],
            messages=[]
        )
    
    def get_last_token_usage(self) -> Dict[str, Any]:
        """
        获取上次对话的 token 使用情况
        
        Returns:
            Dict: 包含 input_tokens, output_tokens, total_tokens, search_count
        """
        if self._chatbot:
            return self._chatbot.tokens_usage
        return {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'search_count': 0
        }


# 创建全局单例
chatbot_service = ChatbotService()
