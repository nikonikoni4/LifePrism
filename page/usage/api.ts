/**
 * Usage Page API
 * 
 * API 使用量相关接口（目前使用 Mock 数据）
 */

import { TokenUsage, UsageStatsResponse } from './types';

// Mock 历史数据
const MOCK_USAGE_HISTORY: TokenUsage[] = [
    { date: '11-25', inputTokens: 4200, outputTokens: 1500, processedRecords: 120 },
    { date: '11-26', inputTokens: 5100, outputTokens: 2100, processedRecords: 155 },
    { date: '11-27', inputTokens: 3800, outputTokens: 1600, processedRecords: 110 },
    { date: '11-28', inputTokens: 6200, outputTokens: 2800, processedRecords: 185 },
    { date: '11-29', inputTokens: 4900, outputTokens: 1800, processedRecords: 140 },
    { date: '11-30', inputTokens: 7500, outputTokens: 3200, processedRecords: 210 },
    { date: '12-01', inputTokens: 5800, outputTokens: 2400, processedRecords: 168 },
];

/**
 * Usage API
 */
export const UsageAPI = {
    /**
     * 获取使用统计数据
     * 
     * @returns 使用统计响应
     */
    async getUsageStats(): Promise<UsageStatsResponse> {
        // TODO: 替换为真实 API 调用
        const history = MOCK_USAGE_HISTORY;
        const today = history[history.length - 1];

        return {
            today: {
                inputTokens: today.inputTokens,
                outputTokens: today.outputTokens,
                totalTokens: today.inputTokens + today.outputTokens,
                processedRecords: today.processedRecords,
            },
            history,
        };
    },

    /**
     * 获取使用历史
     * 
     * @param days 天数
     * @returns Token 使用历史记录
     */
    async getUsageHistory(days: number = 7): Promise<TokenUsage[]> {
        // TODO: 替换为真实 API 调用
        return MOCK_USAGE_HISTORY.slice(-days);
    },
};

export { MOCK_USAGE_HISTORY };
