"""
Chatbot 服务层 - 聊天机器人业务逻辑

负责管理 ChatBot 实例和会话管理
采用方式B设计：发送消息时自动创建会话

V1: 使用 chat_bot.py (已弃用)
V2: 使用 chat_bot_graph.py (当前版本，支持带状态的流式输出)
"""
from typing import Optional, List, Dict, Any, AsyncGenerator
from datetime import datetime
import uuid
import warnings

from lifeprism.server.schemas.chatbot_schemas import (
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
from lifeprism.server.providers.chat_session_provider import get_chat_session_provider
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class ChatbotServiceV1:
    """
    聊天机器人服务类 V1（已弃用）
    
    @deprecated: 此类已弃用，请使用 ChatbotService（V2版本）
    V2 版本使用 LangGraph 实现，支持意图识别、功能介绍等高级特性
    
    管理 ChatBot 实例和会话
    """
    
    def __init__(self):
        """初始化服务"""
        warnings.warn(
            "ChatbotServiceV1 已弃用，请使用 ChatbotService（V2版本）",
            DeprecationWarning,
            stacklevel=2
        )
        from lifeprism.llm.llm_classify.chat.chat_bot import ChatBot
        self._ChatBot = ChatBot
        self._chatbot: Optional[Any] = None
        self._chatbot_context = None  # 异步上下文管理器
        self._current_session_id: Optional[str] = None
        self._model_config = ModelConfig()
        self._session_provider = get_chat_session_provider()  # 会话元数据持久化
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
            self._chatbot_context = self._ChatBot.create_with_persistence()
            self._chatbot = await self._chatbot_context.__aenter__()
            self._is_initialized = True
            logger.info("ChatBot V1 初始化成功")
        except Exception as e:
            logger.error(f"ChatBot V1 初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭服务，清理资源"""
        if self._chatbot_context:
            try:
                await self._chatbot_context.__aexit__(None, None, None)
                self._is_initialized = False
                logger.info("ChatBot V1 已关闭")
            except Exception as e:
                logger.error(f"ChatBot V1 关闭失败: {e}")
    
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
        # 从数据库获取会话列表
        offset = (page - 1) * page_size
        sessions = self._session_provider.get_all_sessions(limit=page_size, offset=offset)
        total = self._session_provider.get_session_count()
        
        items = [
            ChatSession(
                id=s["id"],
                name=s["name"],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
                message_count=s.get("message_count", 0)
            )
            for s in sessions
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
        
        # 检查会话是否存在
        if session_id is None or not self._session_provider.session_exists(session_id):
            # 创建新会话
            session_id = self._generate_session_id()
            name = self._generate_session_name(first_message)
            
            # 持久化到数据库
            self._session_provider.create_session(session_id, name)
            is_new = True
            logger.info(f"创建新会话: {session_id}")
        else:
            # 获取现有会话信息
            session_data = self._session_provider.get_session_by_id(session_id)
            name = session_data["name"] if session_data else "未知会话"
        
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
        return self._session_provider.update_session_name(session_id, request.name)
    
    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            bool: 是否成功
        """
        # TODO: 从 checkpoint 数据库删除会话历史
        success = self._session_provider.delete_session(session_id)
        
        # 如果删除的是当前会话，清空当前会话
        if success and self._current_session_id == session_id:
            self._current_session_id = None
        
        return success
    
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
        
        # 更新会话的消息计数
        self._session_provider.increment_message_count(session_id)
        
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
        await self._ensure_initialized()
        
        session_data = self._session_provider.get_session_by_id(session_id)
        if not session_data:
            return None
        
        # 从 checkpoint 读取历史消息
        messages: List[ChatMessage] = []
        
        try:
            config = {"configurable": {"thread_id": session_id}}
            checkpoint_tuple = await self._chatbot.checkpointer.aget_tuple(config)
            
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
                raw_messages = channel_values.get("messages", [])
                
                for msg in raw_messages:
                    msg_type = type(msg).__name__
                    
                    if msg_type == "HumanMessage":
                        role = MessageRole.USER
                    elif msg_type in ("AIMessage", "AIMessageChunk"):
                        role = MessageRole.ASSISTANT
                    elif msg_type == "SystemMessage":
                        role = MessageRole.SYSTEM
                    else:
                        # 跳过未知类型的消息
                        continue
                    
                    messages.append(ChatMessage(
                        role=role,
                        content=msg.content,
                        timestamp=None  # checkpoint 中没有单独的时间戳
                    ))
                    
            logger.debug(f"会话 {session_id} 读取到 {len(messages)} 条历史消息")
            
        except Exception as e:
            logger.error(f"读取会话历史失败: {e}")
            # 出错时返回空消息列表，而不是 None
        
        return ChatHistoryResponse(
            session_id=session_id,
            session_name=session_data["name"],
            messages=messages
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


class ChatbotService:
    """
    聊天机器人服务类 V2
    
    使用 LangGraph 实现，支持：
    - 意图识别（Intent Router）
    - 功能介绍路由（Feature Intro Router）
    - 带状态的流式输出（Stream with Status）
    
    管理 ChatBot 实例和会话
    """
    
    def __init__(self):
        """初始化服务"""
        from lifeprism.llm.llm_classify.chat.chat_bot_graph import ChatBot
        self._ChatBot = ChatBot
        self._chatbot: Optional[Any] = None
        self._chatbot_context = None  # 异步上下文管理器
        self._current_session_id: Optional[str] = None
        self._model_config = ModelConfig()
        self._session_provider = get_chat_session_provider()  # 会话元数据及tokens_usage持久化
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
            self._chatbot_context = self._ChatBot.create_with_persistence()
            self._chatbot = await self._chatbot_context.__aenter__()
            self._is_initialized = True
            logger.info("ChatBot V2 (Graph) 初始化成功")
        except Exception as e:
            logger.error(f"ChatBot V2 初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭服务，清理资源"""
        if self._chatbot_context:
            try:
                await self._chatbot_context.__aexit__(None, None, None)
                self._is_initialized = False
                logger.info("ChatBot V2 已关闭")
            except Exception as e:
                logger.error(f"ChatBot V2 关闭失败: {e}")
    
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
        # 从数据库获取会话列表
        offset = (page - 1) * page_size
        sessions = self._session_provider.get_all_sessions(limit=page_size, offset=offset)
        total = self._session_provider.get_session_count()
        
        items = [
            ChatSession(
                id=s["id"],
                name=s["name"],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
                message_count=s.get("message_count", 0)
            )
            for s in sessions
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
        
        # 检查会话是否存在
        if session_id is None or not self._session_provider.session_exists(session_id):
            # 创建新会话
            session_id = self._generate_session_id()
            name = self._generate_session_name(first_message)
            
            # 持久化到数据库
            self._session_provider.create_session(session_id, name)
            is_new = True
            logger.info(f"创建新会话: {session_id}")
        else:
            # 获取现有会话信息
            session_data = self._session_provider.get_session_by_id(session_id)
            name = session_data["name"] if session_data else "未知会话"
        
        # 设置当前会话
        self._current_session_id = session_id
        self._chatbot.set_thread_id(session_id)
        
        # 从数据库加载该会话的已有使用量到 chatbot.session_tokens_usage
        existing_usage = self._session_provider.get_session_tokens_usage(session_id)
        if existing_usage:
            self._chatbot.session_tokens_usage[session_id] = existing_usage
            logger.debug(f"从数据库加载会话 {session_id} 的累计使用量: {existing_usage}")
        
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
        return self._session_provider.update_session_name(session_id, request.name)
    
    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            bool: 是否成功
        """
        # TODO: 从 checkpoint 数据库删除会话历史
        success = self._session_provider.delete_session(session_id)
        
        # 如果删除的是当前会话，清空当前会话
        if success and self._current_session_id == session_id:
            self._current_session_id = None
        
        return success
    
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
            self._chatbot.llm_streaming = self._chatbot.get_new_agent(
                enable_search=self._model_config.enable_search,
                enable_thinking=self._model_config.enable_thinking,
                enable_streaming=True,
                temperature=0.5
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
        流式对话（仅返回内容，不带状态）
        
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
        
        # 更新会话的消息计数
        self._session_provider.increment_message_count(session_id)
        
        # 使用 chat_stream 进行流式输出
        async for chunk in self._chatbot.chat_stream(content):
            yield chunk
        
        # 对话完成后，保存使用量到数据库
        await self._save_session_tokens_usage(session_id)
    
    async def chat_stream_with_status(
        self,
        session_id: str,
        content: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        带状态的流式对话（V2新增功能）
        
        返回包含节点状态和内容的事件，前端可以根据 type 区分：
        - type="status": 当前执行的步骤（节点开始时触发）
        - type="content": AI 回复的内容片段
        
        Args:
            session_id: 会话 ID
            content: 用户消息
            
        Yields:
            dict: {"type": "status"|"content", "message": str, "node": str}
        """
        await self._ensure_initialized()
        
        # 确保使用正确的会话
        if self._current_session_id != session_id:
            self._current_session_id = session_id
            self._chatbot.set_thread_id(session_id)
        
        # 更新会话的消息计数
        self._session_provider.increment_message_count(session_id)
        
        # 使用 chat_stream_with_status 进行带状态的流式输出
        async for event in self._chatbot.chat_stream_with_status(content):
            yield event
        
        # 对话完成后，保存使用量到数据库
        await self._save_session_tokens_usage(session_id)
    
    async def get_chat_history(self, session_id: str) -> Optional[ChatHistoryResponse]:
        """
        获取会话历史
        
        Args:
            session_id: 会话 ID
            
        Returns:
            Optional[ChatHistoryResponse]: 历史消息，不存在返回 None
        """
        await self._ensure_initialized()
        
        session_data = self._session_provider.get_session_by_id(session_id)
        if not session_data:
            return None
        
        # 从 checkpoint 读取历史消息
        messages: List[ChatMessage] = []
        
        try:
            config = {"configurable": {"thread_id": session_id}}
            checkpoint_tuple = await self._chatbot.checkpointer.aget_tuple(config)
            
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
                raw_messages = channel_values.get("messages", [])
                
                for msg in raw_messages:
                    msg_type = type(msg).__name__
                    
                    if msg_type == "HumanMessage":
                        role = MessageRole.USER
                    elif msg_type in ("AIMessage", "AIMessageChunk"):
                        role = MessageRole.ASSISTANT
                    elif msg_type == "SystemMessage":
                        role = MessageRole.SYSTEM
                    else:
                        # 跳过未知类型的消息
                        continue
                    
                    messages.append(ChatMessage(
                        role=role,
                        content=msg.content,
                        timestamp=None  # checkpoint 中没有单独的时间戳
                    ))
                    
            logger.debug(f"会话 {session_id} 读取到 {len(messages)} 条历史消息")
            
        except Exception as e:
            logger.error(f"读取会话历史失败: {e}")
            # 出错时返回空消息列表，而不是 None
        
        return ChatHistoryResponse(
            session_id=session_id,
            session_name=session_data["name"],
            messages=messages
        )
    
    async def _save_session_tokens_usage(self, session_id: str):
        """
        保存会话的 token 使用量到数据库
        
        使用 session_tokens_usage（会话累计使用量）进行保存
        
        Args:
            session_id: 会话 ID
        """
        try:
            if not self._chatbot or session_id not in self._chatbot.session_tokens_usage:
                return
            
            usage_data = self._chatbot.session_tokens_usage[session_id].copy()
            # 添加 mode 字段标识为 chatbot
            usage_data['mode'] = 'chatbot'
            
            self._session_provider.upsert_session_tokens_usage(session_id, usage_data)
            logger.debug(f"保存会话 {session_id} 的累计使用量到数据库: {usage_data}")
        except Exception as e:
            logger.error(f"保存会话 {session_id} 的使用量失败: {e}")
    
    def get_last_token_usage(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定会话的 token 使用情况
        
        Args:
            session_id: 会话 ID，为 None 时使用当前会话
        
        Returns:
            Dict: 包含 turn_usage (本轮对话) 和 session_usage (会话累计)
        """
        default_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'search_count': 0
        }
        
        result = {
            'turn_usage': default_usage.copy(),      # 本轮对话使用量
            'session_usage': default_usage.copy()   # 会话累计使用量
        }
        
        if not self._chatbot:
            return result
        
        # 使用指定的 session_id 或当前会话 ID
        target_session = session_id or self._current_session_id
        if not target_session:
            return result
        
        # 获取本轮对话使用量
        result['turn_usage'] = self._chatbot.tokens_usage.get(target_session, default_usage.copy())
        
        # 获取会话累计使用量
        result['session_usage'] = self._chatbot.session_tokens_usage.get(target_session, default_usage.copy())
        
        return result


# 创建全局单例
chatbot_service = ChatbotService()

# 保留 V1 单例供向后兼容（已弃用）
chatbot_service_v1 = None  # 惰性初始化，避免警告

def get_chatbot_service_v1():
    """获取 V1 服务实例（已弃用）"""
    global chatbot_service_v1
    if chatbot_service_v1 is None:
        chatbot_service_v1 = ChatbotServiceV1()
    return chatbot_service_v1
