/**
 * Chatbot Types
 * 
 * 聊天机器人模块专属类型定义
 */

/** 聊天显示模式 */
export type ChatDisplayMode = 'hidden' | 'sidebar' | 'overlay';

/** 聊天消息类型 */
export type ChatMessageType = 'user' | 'model' | 'status' | 'token';

/** 聊天消息 */
export interface ChatMessage {
    id: string;
    role: 'user' | 'model';
    text: string;
    isLoading?: boolean;
    /** Token 使用情况（仅在 AI 回复后显示） */
    tokenUsage?: TokenUsage;
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
export type SSEEventType = 'session' | 'status' | 'content' | 'done' | 'error';

/** 聊天节点类型 */
export type ChatNodeType = 'intent_router' | 'feat_intro_router' | 'feature_introduce' | 'norm_chat';

/** 节点名称映射（用于显示） */
export const NODE_DISPLAY_NAMES: Record<ChatNodeType, string> = {
    intent_router: '意图识别',
    feat_intro_router: '文档检索',
    feature_introduce: '功能介绍',
    norm_chat: '对话生成',
};

/** SSE 事件数据 */
export interface SSEEvent {
    type: SSEEventType;
    /** 当前节点名称（status/content 事件） */
    node?: string;
    /** 状态描述或内容片段 */
    message?: string;
    /** 会话 ID（session 事件） */
    sessionId?: string;
    /** 会话名称（session 事件） */
    sessionName?: string;
    /** 是否新会话（session 事件） */
    isNewSession?: boolean;
    /** 错误信息（error 事件） */
    error?: string;
    /** @deprecated 使用 message 替代 */
    content?: string;
}

/** Token 使用统计 */
export interface TokenUsage {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    searchCount?: number;
}

/** 功能模式 */
export interface FeatureMode {
    id: string;
    name: string;
    icon: React.ReactNode;
    enabled?: boolean;
}
