/**
 * Chatbot Types
 * 
 * 聊天机器人模块专属类型定义
 */

/** 聊天显示模式 */
export type ChatDisplayMode = 'hidden' | 'sidebar' | 'overlay';

/** 聊天消息 */
export interface ChatMessage {
    id: string;
    role: 'user' | 'model';
    text: string;
    isLoading?: boolean;
}

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
