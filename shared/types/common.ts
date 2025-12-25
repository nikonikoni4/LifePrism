/**
 * Common Types
 * 
 * 跨模块共享的类型定义
 */

/** 聊天消息 */
export interface ChatMessage {
    id: string;
    role: 'user' | 'model';
    text: string;
    isLoading?: boolean;
}

/** Token 使用记录（用于 Usage 页面和 AI 消耗追踪） */
export interface TokenUsage {
    date: string;
    inputTokens: number;
    outputTokens: number;
    processedRecords: number;
}

// ============================================================================
// Chatbot 相关类型
// ============================================================================

/** 聊天会话 */
export interface ChatSession {
    id: string;
    name: string;
    createdAt: string;
    updatedAt: string;
    messageCount: number;
}

/** 模型配置 */
export interface ModelConfig {
    enableSearch: boolean;
    enableThinking: boolean;
}

/** SSE 事件类型 */
export type SSEEventType = 'session' | 'content' | 'done' | 'error';

/** SSE 事件数据 */
export interface SSEEvent {
    type: SSEEventType;
    sessionId?: string;
    sessionName?: string;
    isNewSession?: boolean;
    content?: string;
    error?: string;
}

/** 功能模式 */
export interface FeatureMode {
    id: string;
    name: string;
    icon: React.ReactNode;
    enabled?: boolean;
}

