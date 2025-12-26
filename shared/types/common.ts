/**
 * Common Types
 * 
 * 跨模块共享的类型定义
 */

/** Token 使用记录（用于 Usage 页面和 AI 消耗追踪） */
export interface TokenUsage {
    date: string;
    inputTokens: number;
    outputTokens: number;
    processedRecords: number;
}
