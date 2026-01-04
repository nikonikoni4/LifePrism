/**
 * Usage Page API
 * 
 * API 使用量相关接口
 * 
 * 对应后端 API: lifeprism/server/api/usage.py
 */

import { UsageStatsResponse } from './types';

const API_BASE = 'http://localhost:8000/api/v2';

// ============================================================================
// Usage API
// ============================================================================

export const UsageAPI = {
    /**
     * 获取 Token 使用统计数据
     * 
     * @param date 查询日期 (YYYY-MM-DD 格式)
     * @returns 使用统计响应（包含总览、7天趋势、数据处理统计）
     * 
     * @example
     * const stats = await UsageAPI.getUsageStats('2025-12-20');
     * // 返回 2025-12-20 当天的使用总览，以及从 2025-12-14 到 2025-12-20 的7天趋势
     */
    async getUsageStats(date: string): Promise<UsageStatsResponse> {
        const response = await fetch(`${API_BASE}/usage/stats?date=${date}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch usage stats: ${response.statusText}`);
        }

        return response.json();
    },
};

