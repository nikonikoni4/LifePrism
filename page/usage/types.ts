/**
 * Usage Page Types
 * 
 * API 使用量和费用追踪相关类型定义
 */

/** Token 使用记录 */
export interface TokenUsage {
    date: string;
    inputTokens: number;
    outputTokens: number;
    processedRecords: number;
}

/** 今日使用摘要 */
export interface TodayUsageSummary {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    processedRecords: number;
}

/** 费率配置 */
export interface RateConfig {
    inputRate: number;  // per 1k tokens
    outputRate: number;  // per 1k tokens
}

/** 带费用计算的使用数据 */
export interface UsageWithCost extends TokenUsage {
    cost: string;
}

/** 使用统计响应 */
export interface UsageStatsResponse {
    today: TodayUsageSummary;
    history: TokenUsage[];
}
