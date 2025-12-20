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
