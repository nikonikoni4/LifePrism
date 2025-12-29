"""
Chatbot 模块的 schemas 定义

功能概述：
- 会话管理：选择、更新名称、删除会话
- 模型配置：搜索/深度思考开关
- 对话功能：流式输出、Token 估计
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ============================================================================
# 会话 Schemas
# ============================================================================

class ChatSession(BaseModel):
    """会话项"""
    id: str = Field(..., description="会话唯一标识符（thread_id）")
    name: str = Field(..., description="会话名称")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="最后更新时间")
    message_count: int = Field(default=0, description="消息数量")


class ChatSessionListResponse(BaseModel):
    """会话列表响应"""
    items: List[ChatSession] = Field(default=[], description="会话列表")
    total: int = Field(default=0, description="总数")


class UpdateSessionRequest(BaseModel):
    """更新会话请求"""
    name: str = Field(..., description="新的会话名称")


# ============================================================================
# 模型配置 Schemas
# ============================================================================

class ModelConfig(BaseModel):
    """模型配置"""
    enable_search: bool = Field(default=False, description="启用搜索功能")
    enable_thinking: bool = Field(default=False, description="启用深度思考模式")


class UpdateModelConfigRequest(BaseModel):
    """更新模型配置请求"""
    enable_search: Optional[bool] = Field(default=None, description="启用搜索功能")
    enable_thinking: Optional[bool] = Field(default=None, description="启用深度思考模式")


# ============================================================================
# 对话 Schemas
# ============================================================================

class ChatMessageRequest(BaseModel):
    """
    发送消息请求
    
    采用方式B设计：session_id 为空时自动创建新会话
    """
    session_id: Optional[str] = Field(default=None, description="会话 ID，为空时自动创建新会话")
    content: str = Field(..., description="消息内容")


class ChatStreamStartResponse(BaseModel):
    """
    流式响应的初始元数据
    
    在 SSE 流开始时发送，告知客户端会话信息
    """
    session_id: str = Field(..., description="会话 ID（新建或已有）")
    session_name: str = Field(..., description="会话名称")
    is_new_session: bool = Field(default=False, description="是否为新创建的会话")


class SSEEventType(str, Enum):
    """SSE 事件类型"""
    SESSION = "session"      # 会话信息
    STATUS = "status"        # 节点状态更新
    CONTENT = "content"      # AI 回复内容片段
    DONE = "done"            # 流结束标记
    ERROR = "error"          # 错误信息


class ChatNodeType(str, Enum):
    """聊天节点类型（用于 status 事件）"""
    INTENT_ROUTER = "intent_router"           # 意图识别
    FEAT_INTRO_ROUTER = "feat_intro_router"   # 功能文档检索
    FEATURE_INTRODUCE = "feature_introduce"   # 功能介绍生成
    NORM_CHAT = "norm_chat"                   # 普通对话生成


class ChatStreamEvent(BaseModel):
    """
    SSE 流式事件（统一格式）
    
    事件类型说明:
    - session: 会话信息，包含 session_id, session_name, is_new_session
    - status: 节点状态，包含 node, message
    - content: 内容片段，包含 node, message
    - done: 流结束标记
    - error: 错误信息，包含 error
    """
    type: SSEEventType = Field(..., description="事件类型")
    node: Optional[str] = Field(default=None, description="当前节点名称（status/content 事件）")
    message: Optional[str] = Field(default=None, description="状态描述或内容片段")
    session_id: Optional[str] = Field(default=None, description="会话 ID（session 事件）")
    session_name: Optional[str] = Field(default=None, description="会话名称（session 事件）")
    is_new_session: Optional[bool] = Field(default=None, description="是否新会话（session 事件）")
    error: Optional[str] = Field(default=None, description="错误信息（error 事件）")


class TokenUsageEstimate(BaseModel):
    """Token 使用估计"""
    input_tokens: int = Field(default=0, description="输入 tokens")
    output_tokens: int = Field(default=0, description="输出 tokens")
    total_tokens: int = Field(default=0, description="总 tokens")


class ChatCompletionResponse(BaseModel):
    """聊天完成响应（用于流结束时的汇总）"""
    content: str = Field(..., description="完整回复内容")
    token_usage: Optional[TokenUsageEstimate] = Field(default=None, description="Token 使用情况")


# ============================================================================
# 历史消息 Schemas
# ============================================================================

class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """聊天消息"""
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[str] = Field(default=None, description="消息时间戳")

class ChatHistoryResponse(BaseModel):
    """聊天历史响应"""
    session_id: str = Field(..., description="会话 ID")
    session_name: str = Field(..., description="会话名称")
    messages: Optional[List[ChatMessage]] = Field(default=[], description="消息列表")