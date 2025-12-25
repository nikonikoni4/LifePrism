/**
 * Chatbot Service
 * 
 * 调用后端 Chatbot API 的服务层
 */

import { ChatSession, ModelConfig, SSEEvent, ChatMessage } from '../shared/types';

const API_BASE = 'http://localhost:8000/api/v2/chatbot';

// ============================================================================
// 会话管理
// ============================================================================

/**
 * 获取会话列表
 */
export async function getSessions(page = 1, pageSize = 20): Promise<{ items: ChatSession[], total: number }> {
    const response = await fetch(`${API_BASE}/sessions?page=${page}&page_size=${pageSize}`);
    if (!response.ok) {
        throw new Error(`Failed to get sessions: ${response.statusText}`);
    }
    const data = await response.json();
    // 转换字段名（后端 snake_case -> 前端 camelCase）
    return {
        items: data.items.map((item: any) => ({
            id: item.id,
            name: item.name,
            createdAt: item.created_at,
            updatedAt: item.updated_at,
            messageCount: item.message_count,
        })),
        total: data.total,
    };
}

/**
 * 更新会话名称
 */
export async function updateSessionName(sessionId: string, name: string): Promise<boolean> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
    });
    return response.ok;
}

/**
 * 删除会话
 */
export async function deleteSession(sessionId: string): Promise<boolean> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: 'DELETE',
    });
    return response.ok;
}

/**
 * 获取会话历史
 */
export async function getChatHistory(sessionId: string): Promise<ChatMessage[]> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/history`);
    if (!response.ok) {
        throw new Error(`Failed to get chat history: ${response.statusText}`);
    }
    const data = await response.json();
    return data.messages.map((msg: any) => ({
        id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        role: msg.role === 'assistant' ? 'model' : msg.role,
        text: msg.content,
        timestamp: msg.timestamp,
    }));
}

// ============================================================================
// 模型配置
// ============================================================================

/**
 * 获取模型配置
 */
export async function getModelConfig(): Promise<ModelConfig> {
    const response = await fetch(`${API_BASE}/config`);
    if (!response.ok) {
        throw new Error(`Failed to get model config: ${response.statusText}`);
    }
    const data = await response.json();
    return {
        enableSearch: data.enable_search,
        enableThinking: data.enable_thinking,
    };
}

/**
 * 更新模型配置
 */
export async function updateModelConfig(config: Partial<ModelConfig>): Promise<ModelConfig> {
    const body: any = {};
    if (config.enableSearch !== undefined) body.enable_search = config.enableSearch;
    if (config.enableThinking !== undefined) body.enable_thinking = config.enableThinking;

    const response = await fetch(`${API_BASE}/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(`Failed to update model config: ${response.statusText}`);
    }
    const data = await response.json();
    return {
        enableSearch: data.enable_search,
        enableThinking: data.enable_thinking,
    };
}

// ============================================================================
// 流式聊天
// ============================================================================

/**
 * 发送消息（SSE 流式）
 * 
 * @param sessionId 会话ID，为null时自动创建新会话
 * @param content 消息内容
 * @param onEvent 事件回调
 * @param signal AbortSignal 用于取消请求（暂停功能）
 */
export async function sendMessageStream(
    sessionId: string | null,
    content: string,
    onEvent: (event: SSEEvent) => void,
    signal?: AbortSignal
): Promise<void> {
    const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            content: content,
        }),
        signal,
    });

    if (!response.ok) {
        throw new Error(`Chat request failed: ${response.statusText}`);
    }

    if (!response.body) {
        throw new Error('Response body is null');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // 解析 SSE 事件（每个事件以 \n\n 分隔）
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // 保留未完成的部分

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6); // 去掉 "data: " 前缀
                        const eventData = JSON.parse(jsonStr);

                        // 转换为 SSEEvent
                        const event: SSEEvent = {
                            type: eventData.type,
                            sessionId: eventData.session_id,
                            sessionName: eventData.session_name,
                            isNewSession: eventData.is_new_session,
                            content: eventData.content,
                            error: eventData.error,
                        };

                        onEvent(event);
                    } catch (e) {
                        console.error('Failed to parse SSE event:', e, line);
                    }
                }
            }
        }
    } finally {
        reader.releaseLock();
    }
}

/**
 * 发送消息的异步生成器版本（兼容原有接口）
 * 
 * @param sessionId 会话ID
 * @param content 消息内容
 */
export async function* sendMessage(
    sessionId: string | null,
    content: string
): AsyncGenerator<SSEEvent, void, unknown> {
    const events: SSEEvent[] = [];
    let resolveNext: ((value: SSEEvent | null) => void) | null = null;
    let done = false;

    // 启动流式请求
    sendMessageStream(
        sessionId,
        content,
        (event) => {
            if (resolveNext) {
                resolveNext(event);
                resolveNext = null;
            } else {
                events.push(event);
            }
            if (event.type === 'done' || event.type === 'error') {
                done = true;
            }
        }
    ).catch((e) => {
        events.push({ type: 'error', error: e.message });
        done = true;
        if (resolveNext) {
            resolveNext(null);
        }
    });

    while (!done || events.length > 0) {
        if (events.length > 0) {
            yield events.shift()!;
        } else {
            const event = await new Promise<SSEEvent | null>((resolve) => {
                resolveNext = resolve;
            });
            if (event) {
                yield event;
            }
        }
    }
}
