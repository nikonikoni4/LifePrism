"""
Chatbot API - 聊天机器人接口

提供会话管理、模型配置和对话的 RESTful API
采用方式B设计：发送消息时自动创建会话
"""
from fastapi import APIRouter, Query, HTTPException, Path
from fastapi.responses import StreamingResponse
from typing import Optional
import json

from lifewatch.server.schemas.chatbot_schemas import (
    ChatSession,
    ChatSessionListResponse,
    UpdateSessionRequest,
    ModelConfig,
    UpdateModelConfigRequest,
    ChatMessageRequest,
    ChatHistoryResponse,
    TokenUsageEstimate,
)
from lifewatch.server.services.chatbot_service import chatbot_service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


# ============================================================================
# 会话管理接口
# ============================================================================

@router.get("/sessions", response_model=ChatSessionListResponse)
async def get_sessions(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量")
):
    """
    获取会话列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大100
    
    返回按更新时间降序排列的会话列表
    """
    return await chatbot_service.get_sessions(page, page_size)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str = Path(..., description="会话 ID"),
    request: UpdateSessionRequest = ...
):
    """
    更新会话名称
    
    请求体:
    - **name**: 新的会话名称
    """
    success = await chatbot_service.update_session_name(session_id, request)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str = Path(..., description="会话 ID")
):
    """
    删除会话
    
    删除指定会话及其所有历史消息
    """
    success = await chatbot_service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True}


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str = Path(..., description="会话 ID")
):
    """
    获取会话的聊天历史
    
    返回指定会话的所有历史消息
    """
    result = await chatbot_service.get_chat_history(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="会话不存在")
    return result


# ============================================================================
# 模型配置接口
# ============================================================================

@router.get("/config", response_model=ModelConfig)
async def get_model_config():
    """
    获取当前模型配置
    
    返回:
    - **enable_search**: 是否启用搜索功能
    - **enable_thinking**: 是否启用深度思考模式
    """
    return await chatbot_service.get_model_config()


@router.patch("/config", response_model=ModelConfig)
async def update_model_config(request: UpdateModelConfigRequest):
    """
    更新模型配置
    
    请求体（所有字段可选）:
    - **enable_search**: 启用搜索功能
    - **enable_thinking**: 启用深度思考模式
    
    更新后会立即重新创建 agent 以应用新配置
    """
    return await chatbot_service.update_model_config(request)


# ============================================================================
# 对话接口
# ============================================================================

@router.post("/chat/stream")
async def chat_stream(request: ChatMessageRequest):
    """
    流式对话（SSE）
    
    请求体:
    - **session_id**: 会话 ID（可选，为空时自动创建新会话）
    - **content**: 消息内容
    
    返回: Server-Sent Events 流
    
    SSE 事件格式:
    1. 首条消息（会话信息）: `{"type": "session", "session_id": "...", "session_name": "...", "is_new_session": true/false}`
    2. 内容片段: `{"type": "content", "content": "..."}`
    3. 结束标记: `{"type": "done", "content": ""}`
    4. 错误: `{"type": "error", "error": "..."}`
    
    客户端可通过断开连接来暂停输出
    """
    async def generate():
        try:
            # 1. 获取或创建会话
            session_info = await chatbot_service.get_or_create_session(
                request.session_id,
                request.content
            )
            
            # 发送会话信息
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_info.session_id, 'session_name': session_info.session_name, 'is_new_session': session_info.is_new_session}, ensure_ascii=False)}\n\n"
            
            # 2. 流式输出内容
            async for chunk in chatbot_service.chat_stream(
                session_info.session_id,
                request.content
            ):
                yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"
            
            # 3. 发送结束标记
            yield f"data: {json.dumps({'type': 'done', 'content': ''}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )



