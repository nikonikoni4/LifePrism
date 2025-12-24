/**
 * Usage Page Types
 * 
 * API 使用量和费用追踪相关类型定义
 * 
 * 对应后端 schema: lifewatch/server/schemas/usage_schemas.py
 */

// ============================================================================
// Usage Overview - 使用总览
// ============================================================================

/** 使用总览（饼图总览部分）- 今日 + 全部统计 */
export interface UsageOverview {
    // 今日统计
    input_tokens: number;           // 今日输入 token 数
    output_tokens: number;          // 今日输出 token 数
    total_tokens: number;           // 今日总 token 数
    input_tokens_price: number;     // 输入 token 价格（每1000个token）
    output_tokens_price: number;    // 输出 token 价格（每1000个token）
    total_price: number;            // 今日总价格
    // 全部统计
    all_total_tokens: number;       // 全部总 token 数
    all_total_price: number;        // 全部总价格
}

// ============================================================================
// Data Processing Stats - 数据处理统计
// ============================================================================

/** 数据处理 tokens 消耗统计 - 今日 + 全部统计 */
export interface DataProcessingUsageStats {
    // 今日统计
    processing_items: number;       // 今日处理项目数
    avg_processing_tokens: number;  // 今日平均处理 token 数
    avg_cost: number;               // 今日平均处理 token 价格（每1000个token）
    total_tokens: number;           // 今日总 token 数
    total_cost: number;             // 今日总价格
    // 全部统计
    all_total_tokens: number;       // 全部数据处理总 token 数
    all_total_cost: number;         // 全部数据处理总价格
}

// ============================================================================
// Other Usage Stats - 其他消耗统计
// ============================================================================

/** 其他消耗统计 - 今日 + 全部统计 */
export interface OtherUsageStats {
    // 今日统计
    total_tokens: number;           // 今日其他消耗总 token 数
    total_cost: number;             // 今日其他消耗总价格
    // 全部统计
    all_total_tokens: number;       // 全部其他消耗总 token 数
    all_total_cost: number;         // 全部其他消耗总价格
}

// ============================================================================
// 7-Day Stats - 7天柱形图统计
// ============================================================================

/** 7天柱形图统计的单项 */
export interface UsageStats7DaysItem {
    day: string;                    // 日期
    total_cost: number;             // 总价格
    total_tokens: number;           // 总 token 数
}

/** 7天柱形图统计 */
export interface UsageStats7Days {
    items: UsageStats7DaysItem[];   // 7天柱形图统计列表
}

// ============================================================================
// Complete Response - 完整响应
// ============================================================================

/** GET /usage/stats 完整响应 */
export interface UsageStatsResponse {
    usage_overview: UsageOverview;                          // 使用总览
    data_processing_usage_stats: DataProcessingUsageStats;  // 数据处理使用统计
    other_usage_stats: OtherUsageStats;                     // 其他消耗使用统计
    usage_stats_7days: UsageStats7Days;                     // 7天使用统计
}
